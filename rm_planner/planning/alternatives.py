"""Rolling plan proposals. Pure calculations; never reserves or writes inventory.

Keep the imported production dates as baseline. Orders before ``adjust_from``
are frozen; only later dates may be pulled forward. Inspect the full horizon.
RM is usable kg (configured wonton yield), not workbook HO kg.
"""
from __future__ import annotations

from collections import defaultdict
from copy import deepcopy
from datetime import date, timedelta
from hashlib import sha256
import json
import math

from .engine import (order_due_date, production_type_for_order, market_type_for_order,
                     outstanding_order_quantities, _inventory_lots)
from .capacity_store import capacities_at_percentage
from rm_planner.inventory.range_store import normalize_size_class

EPS = 1e-6
TITLES = {"baseline": "แผนเดิม", "material": "ลดการเก็บ RM", "balanced": "สมดุล"}
# The factory is closed every Monday and Tuesday.  Keep this rule in the
# calculation layer as well as the date picker so a saved or imported plan
# cannot accidentally schedule production on a closed day.
FACTORY_HOLIDAY_WEEKDAYS = frozenset((0, 1))


def number(value, name, optional=False):
    if optional and (value is None or value == ""):
        return None
    try:
        result = float(value)
    except (ValueError, TypeError):
        raise ValueError(f"{name}: กรุณาระบุตัวเลข") from None
    if not math.isfinite(result) or result < 0:
        raise ValueError(f"{name}: ต้องเป็นตัวเลขตั้งแต่ 0")
    return result


def settings_defaults():
    return dict(lookahead=7, adjust_from=None, shift_hours=8, setup_minutes=30,
                stop_cost=None, freeze_cost=None, freeze_percent=None)


def build_context(orders, stock, ranges, capacity, classes, weights, start, settings, profiles):
    """Adapt saved application records without mutating those records."""
    start = date.fromisoformat(start)
    s = dict(settings_defaults(), **settings)
    s.pop('adjustment', None)  # Legacy adjustment duration; replaced by a date.
    for key in s:
        if key == 'adjust_from':
            continue
        s[key] = number(s[key], key, key in ("stop_cost", "freeze_cost", "freeze_percent"))
    if not 1 <= s['lookahead'] <= 31 or s['lookahead'] != int(s['lookahead']):
        raise ValueError("มองล่วงหน้าต้องเป็นจำนวนเต็ม 1–31 วัน")
    if not 0 < s['shift_hours'] <= 24 or s['setup_minutes'] > s['shift_hours'] * 60:
        raise ValueError("ตรวจชั่วโมงทำงานและเวลาเปลี่ยน SKU")
    if s['freeze_percent'] is not None and s['freeze_percent'] > 100:
        raise ValueError("สัดส่วนเข้า Freeze ต้อง 0–100%")
    raw, cooked = capacities_at_percentage(capacity)
    if raw is None or cooked is None:
        raise ValueError("กรุณาตั้ง Capacity ดิบและสุกก่อน")
    # Capacity is entered as cups/hour; its configured work-day length is the
    # production shift used by both the feasibility check and the timeline.
    s['shift_hours'] = float(capacity.work_hours_per_day)
    end = start + timedelta(days=int(s['lookahead']) - 1)
    try:
        adjust_from = date.fromisoformat(str(s['adjust_from'] or start.isoformat()))
    except (TypeError, ValueError):
        raise ValueError("วันเริ่มปรับแผนไม่ถูกต้อง") from None
    if not start <= adjust_from <= end:
        raise ValueError("วันเริ่มปรับแผนต้องอยู่ระหว่างวันเริ่มและวันสุดท้ายที่มองล่วงหน้า")
    s['adjust_from'] = adjust_from.isoformat()
    jobs, notices, seen = [], [], set()
    for order in orders:
        try:
            planned = date(int(order.prod_year), int(order.prod_month), int(order.prod_date))
        except (TypeError, ValueError):
            notices.append(f"{order.order_no}: ไม่พบวันที่ผลิตเดิม จัดแผนให้อัตโนมัติไม่ได้")
            continue
        if not start <= planned <= end:
            continue
        _, cups, qty = outstanding_order_quantities(order)
        if qty <= EPS:
            continue
        if cups <= EPS:
            notices.append(f"{order.order_no}: ไม่มีจำนวนถ้วย จึงคำนวณ Capacity ถ้วย/วันไม่ได้")
            continue
        if not order.record_id or order.record_id in seen:
            raise ValueError("Order ต้องมี record_id ไม่ซ้ำกัน กรุณาบันทึก Order ก่อน")
        seen.add(order.record_id)
        p = profiles.get(order.record_id, {})
        size = normalize_size_class(order.rm_size)
        supported = size in ('M', 'S', 'SS')
        ready = p.get('status', 'unknown')
        if ready not in ('unknown', 'ready', 'partial', 'blocked'):
            raise ValueError("สถานะความพร้อมไม่ถูกต้อง")
        earliest = p.get('earliest', '')
        if earliest:
            date.fromisoformat(earliest)
        ready_date = p.get('date', '')
        if ready_date:
            date.fromisoformat(ready_date)
        rank = number(p.get('soup_rank'), 'ลำดับซุป', optional=True)
        jobs.append(dict(id=order.record_id, order=order.order_no, customer=order.customer_name,
            sku=' | '.join((order.group_1, order.group_2, order.packaging, order.soup, order.rm_size)),
            code=order.code.strip(),
            product=order.product.strip(),
            line=production_type_for_order(order), market=market_type_for_order(order, classes),
            size=order.rm_size, stock_size=size, due=order_due_date(order).isoformat(),
            day=planned.isoformat(), qty=qty, cups=cups, yield_rate=weights.wontons_per_kg(size) if supported else 0,
            locked=bool(p.get('locked', False)), egg=p.get('egg', ''), soup_rank=rank,
            earliest=earliest, status=ready, ready_date=ready_date,
            max_qty=number(p.get('max_qty', 0), 'จำนวนที่พร้อม'), reviewer=p.get('reviewer', '').strip()))
    lots = []
    stock = tuple(stock)
    forecasts = [r.source_label for r in stock if r.record_type == 'prediction' and r.record_date <= end.isoformat()]
    for lot in _inventory_lots(stock, tuple(ranges), weights):
        lots.append(dict(day=lot.available_date.isoformat(), market=lot.market_type,
                         size=lot.eligible_classes[0], kg=lot.remaining_kg))
    # Include unusable shrimp in residual/cost; never make it available to an order.
    # Calculate each record separately to preserve its arrival date.
    for r in stock:
        classified = sum(l.remaining_kg for l in _inventory_lots((r,), tuple(ranges), weights))
        unused = sum(float(e.weight) for e in r.entries) - classified
        if unused > EPS:
            lots.append(dict(day=r.record_date, market=r.market_type, size='Unused', kg=unused))
    for lot in lots:
        number(lot['kg'], 'Stock kg')
    return dict(start=start.isoformat(), settings=s, jobs=jobs, lots=lots,
                capacity={'RAW': float(raw), 'COOKED': float(cooked)}, notices=notices, forecasts=forecasts)


def signature(context):
    return sha256(json.dumps(context, sort_keys=True, ensure_ascii=False, allow_nan=False).encode()).hexdigest()


def baseline_rows(context):
    return [dict(job=j['id'], day=j['day'], qty=j['qty']) for j in context['jobs']]


def evaluate(context, rows):
    jobs = {j['id']: j for j in context['jobs']}
    s = context['settings']
    start = date.fromisoformat(context['start'])
    adjust_from = s['adjust_from']
    errors, pending = [], [f'RM {label}: เป็นยอด prediction ต้องยืนยันผลจริงก่อน' for label in context.get('forecasts', [])]
    for row in rows:
        try:
            planned_day = date.fromisoformat(row['day'])
        except (KeyError, TypeError, ValueError):
            errors.append('แถวแผนมีวันที่ผลิตไม่ถูกต้อง')
            continue
        if planned_day.weekday() in FACTORY_HOLIDAY_WEEKDAYS:
            errors.append(f"{row['day']}: โรงงานหยุดผลิตวันจันทร์และวันอังคาร")
    totals = defaultdict(float)
    moved = defaultdict(float)
    for row in rows:
        if row['job'] not in jobs or number(row['qty'], 'จำนวนผลิต') <= EPS:
            raise ValueError("แถวแผนไม่ถูกต้อง")
        j = jobs[row['job']]
        totals[j['id']] += row['qty']
        if row['day'] != j['day']:
            moved[j['id']] += row['qty']
            if j['locked'] or row['day'] < adjust_from or row['day'] >= j['day']:
                errors.append(f"{j['order']}: ย้ายงานนอกช่วงหรือเป็นงานล็อก")
            if not j['earliest'] or row['day'] < j['earliest']:
                errors.append(f"{j['order']}: ยังไม่อนุญาตให้ผลิตเร็วในวันนี้")
            if j['status'] == 'blocked':
                errors.append(f"{j['order']}: วัสดุไม่พร้อม")
            elif j['status'] in ('ready', 'partial'):
                if j['ready_date'] != row['day'] or not j['reviewer'] or moved[j['id']] > j['max_qty'] + EPS:
                    errors.append(f"{j['order']}: เกินวันที่/จำนวนที่ยืนยัน")
            else:
                pending.append(f"{j['order']}: รอยืนยันวัสดุ {row['day']}")
    for j in jobs.values():
        if abs(totals[j['id']] - j['qty']) > EPS:
            errors.append(f"{j['order']}: จำนวนไม่ตรงกับออเดอร์คงเหลือ")
    balances = defaultdict(float)
    daily, schedule = [], []
    for offset in range(int(s['lookahead'])):
        day = (start + timedelta(days=offset)).isoformat()
        for lot in context['lots']:
            if lot['day'] == day or (offset == 0 and lot['day'] < day):
                balances[(lot['market'], lot['size'])] += lot['kg']
        # Do not put work on a closed day even while displaying an invalid
        # imported/manual plan.  The error above tells the user what to fix.
        selected = [] if date.fromisoformat(day).weekday() in FACTORY_HOLIDAY_WEEKDAYS else [r for r in rows if r['day'] == day]
        changes = 0
        hours = {}
        for line in ('RAW', 'COOKED'):
            def operation_key(row):
                job = jobs[row['job']]
                # On the raw line, CODE identifies the actual SKU changeover.
                # Keep matching codes together even where their other order
                # detail differs, so they become one uninterrupted run.
                return job['code'] if line == 'RAW' and job['code'] else job['sku']

            work = sorted(
                (r for r in selected if jobs[r['job']]['line'] == line),
                key=lambda r: (
                    operation_key(r) if line == 'RAW' else (
                        jobs[r['job']]['soup_rank'] if jobs[r['job']]['soup_rank'] is not None else 999,
                        operation_key(r),
                    ),
                    r['job'],
                ),
            )
            groups = {(jobs[r['job']]['market'], jobs[r['job']]['egg']) for r in work}
            if len(groups) > 1:
                errors.append(f"{day} {line}: ตลาด/กลุ่มไข่ต่างกันในวันเดียวกัน")
            previous, elapsed = None, 0.0
            for r in work:
                j = jobs[r['job']]
                if not j['egg'] or j['soup_rank'] is None or j['market'] == 'unassigned':
                    pending.append(f"{j['order']}: ตรวจตลาด กลุ่มไข่ และลำดับซุป")
                current_operation = operation_key(r)
                if previous is not None and previous != current_operation:
                    changes += 1
                    elapsed += s['setup_minutes'] / 60
                previous = current_operation
                planned_cups = r['qty'] / j['qty'] * j['cups']
                duration = planned_cups / context['capacity'][line] * s['shift_hours'] if context['capacity'][line] else float('inf')
                if not math.isfinite(duration):
                    errors.append(f"{day} {line}: capacity เป็นศูนย์")
                    duration = 0
                schedule.append(dict(r, start_hours=elapsed, line=line))
                elapsed += duration
            hours[line] = elapsed
            if elapsed > s['shift_hours'] + EPS:
                errors.append(f"{day} {line}: ใช้ {elapsed:.2f} ชม. เกิน {s['shift_hours']:g} ชม.")
        for r in selected:
            j = jobs[r['job']]
            if j['line'] not in context['capacity'] or j['yield_rate'] <= 0:
                errors.append(f"{j['order']}: ยังไม่รองรับไลน์หรือ RM {j['size']}")
                continue
            balances[(j['market'], j['stock_size'])] -= r['qty'] / j['yield_rate']
        for (market, size), qty in balances.items():
            if qty < -EPS:
                errors.append(f"{day}: RM {market} {size} ขาด {-qty:,.1f} kg")
        by_size = {size: sum(max(0, q) for (_, z), q in balances.items() if z == size) for size in ('M', 'S', 'SS', 'Unused')}
        daily.append(dict(day=day, remaining=sum(by_size.values()), by_size=by_size,
                          changes=changes, hours=hours))
    active = [day for day in daily if day['day'] >= adjust_from]
    residual = active[-1]['remaining']
    freeze_kg = None if s['freeze_percent'] is None else residual * s['freeze_percent'] / 100
    freeze_cost = None if freeze_kg is None or s['freeze_cost'] is None else freeze_kg * s['freeze_cost']
    change_count = sum(d['changes'] for d in active)
    setup_cost = None if s['stop_cost'] is None else change_count * s['setup_minutes'] / 60 * s['stop_cost']
    cost = None if freeze_cost is None or setup_cost is None else freeze_cost + setup_cost
    late = len({r['job'] for r in rows if r['day'] > jobs[r['job']]['due']})
    return dict(rows=rows, schedule=schedule, daily=daily, remaining=residual, freeze_kg=freeze_kg,
                freeze_cost=freeze_cost, setup_cost=setup_cost, cost=cost, changes=change_count,
                moved=len(moved), late=late, errors=list(dict.fromkeys(errors)),
                pending=list(dict.fromkeys(pending)), signature=signature(context),
                status='invalid' if errors else 'conditional' if pending else 'review')


def compare(context):
    """Three bounded greedy policies, always validated against the entire window."""
    base = evaluate(context, baseline_rows(context))
    results = [dict(base, id='baseline', title=TITLES['baseline'])]
    jobs = {j['id']: j for j in context['jobs']}
    for policy in ('material', 'balanced'):
        current = deepcopy(base)
        if not base['errors'] and (policy != 'balanced' or base['cost'] is not None):
            # Start earliest; a moved job is considered only once, preserving readiness caps.
            used = set()
            first_adjustable = (date.fromisoformat(context['settings']['adjust_from']) - date.fromisoformat(context['start'])).days
            for offset in range(first_adjustable, int(context['settings']['lookahead'])):
                target = (date.fromisoformat(context['start']) + timedelta(days=offset)).isoformat()
                available = sorted(context['jobs'], key=lambda j: (-j['qty'] / max(j['yield_rate'], EPS), j['due'], j['id']))
                for j in available[:60]:
                    if (j['id'] in used or j['locked'] or j['day'] <= target or not j['earliest']
                            or j['earliest'] > target or not j['egg'] or j['soup_rank'] is None
                            or j['status'] == 'blocked' or j['yield_rate'] <= 0):
                        continue
                    cap = j['qty']
                    if j['status'] in ('ready', 'partial'):
                        if j['ready_date'] != target or not j['reviewer']:
                            continue
                        cap = min(cap, j['max_qty'])
                    best = None
                    low, high = 0., cap
                    for attempt in range(19):
                        amount = high if attempt == 0 else (low + high) / 2
                        if amount < EPS:
                            break
                        rows = [dict(r) for r in current['rows'] if r['job'] != j['id']]
                        rows.append(dict(job=j['id'], day=target, qty=amount))
                        if j['qty'] - amount > EPS:
                            rows.append(dict(job=j['id'], day=j['day'], qty=j['qty'] - amount))
                        trial = evaluate(context, rows)
                        if trial['errors']:
                            high = amount
                        else:
                            best = trial
                            low = amount
                            if attempt == 0:
                                break
                    if best is None:
                        continue
                    if policy == 'balanced' and best['cost'] >= current['cost'] - EPS:
                        continue
                    # Do not change a plan without reducing residual at the comparison boundary.
                    if best['remaining'] >= current['remaining'] - EPS:
                        continue
                    current, used = best, used | {j['id']}
        results.append(dict(current, id=policy, title=TITLES[policy]))
    return results
