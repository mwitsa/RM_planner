"""Rolling plan proposals. Pure calculations; never reserves or writes inventory.

Keep the imported production dates as baseline. Orders before ``adjust_from``
are frozen; only later dates may be pulled forward. Inspect the full horizon.
RM is usable kg (configured wonton yield), not workbook HO kg.
"""
from __future__ import annotations

import calendar
from collections import Counter, defaultdict
from copy import deepcopy
from datetime import date, timedelta
from hashlib import sha256
import json
import math

from .engine import (class_group_for_order, order_due_date, production_type_for_order, market_type_for_order,
                     outstanding_order_quantities, _inventory_lots)
from .capacity_store import capacities_at_percentage
from .production_start_store import (
    DEFAULT_COOKED_START_HOUR,
    DEFAULT_RAW_START_HOUR,
    PRODUCTION_WINDOW_START_HOUR,
    ProductionStartSettings,
)
from rm_planner.inventory.range_store import normalize_size_class

EPS = 1e-6
SPECIAL_RM_SIZES = frozenset(("HC", "BK"))
TITLES = {"baseline": "แผนเดิม", "material": "ลดการเก็บ RM", "balanced": "สมดุล"}
# The factory is closed every Monday and Tuesday.  Keep this rule in the
# calculation layer as well as the date picker so a saved or imported plan
# cannot accidentally schedule production on a closed day.
FACTORY_HOLIDAY_WEEKDAYS = frozenset((0, 1))
REPLAN_ORDER_LOOKAHEAD_MONTHS = 2


def _add_calendar_months(value, months):
    """Advance a date by whole calendar months, clamping the day if needed."""

    absolute_month = value.year * 12 + value.month - 1 + months
    year, month_index = divmod(absolute_month, 12)
    month = month_index + 1
    return date(year, month, min(value.day, calendar.monthrange(year, month)[1]))


def _load_date_within_replan_limit(order, cutoff):
    """Check the two-month limit without discarding a month-only Load date.

    The source workbook commonly records Load date as ``MM/YYYY``.  Since it
    contains no day, treating it as the month's last day would incorrectly
    exclude every November Order from a 16 Sep–16 Nov limit.  A month-only
    value is therefore eligible throughout its cutoff month; an explicit day
    still receives the exact-day comparison.
    """

    if not str(order.date or '').strip():
        return (int(order.year), int(order.month)) <= (cutoff.year, cutoff.month)
    return order_due_date(order) <= cutoff


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


def build_context(orders, stock, ranges, capacity, classes, weights, start, settings, profiles,
                  operation_rules=(), chill_days=None, production_start_settings=None,
                  labour_settings=None):
    """Adapt saved application records without mutating those records."""
    start = date.fromisoformat(start)
    classes = tuple(classes)
    operation_rules = tuple(
        {
            'name': str(rule.get('name', '')).strip(),
            'nodes': tuple(
                {'class': str(node.get('class', '')).strip(), 'group': str(node.get('group', '')).strip()}
                for node in rule.get('nodes', ())
                if isinstance(node, dict) and str(node.get('class', '')).strip() and str(node.get('group', '')).strip()
            ),
        }
        for rule in operation_rules if isinstance(rule, dict)
    )
    operation_classes = {
        node['class'] for rule in operation_rules for node in rule['nodes']
    }
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
    raw, cooked = capacities_at_percentage(capacity)
    if raw is None or cooked is None:
        raise ValueError("กรุณาตั้ง Capacity ดิบและสุกก่อน")
    # Capacity is entered as cups/hour; its configured work-day length is the
    # production shift used by both the feasibility check and the timeline.
    s['shift_hours'] = float(capacity.work_hours_per_day)
    end = start + timedelta(days=int(s['lookahead']) - 1)
    replan_load_cutoff = _add_calendar_months(start, REPLAN_ORDER_LOOKAHEAD_MONTHS)
    try:
        adjust_from = date.fromisoformat(str(s['adjust_from'] or start.isoformat()))
    except (TypeError, ValueError):
        raise ValueError("วันเริ่มปรับแผนไม่ถูกต้อง") from None
    if not start <= adjust_from <= end:
        raise ValueError("วันเริ่มปรับแผนต้องอยู่ระหว่างวันเริ่มและวันสุดท้ายที่มองล่วงหน้า")
    s['adjust_from'] = adjust_from.isoformat()
    labour_defaults = {
        'raw_labour': 0,
        'raw_wage': 0,
        'cooked_labour': 0,
        'cooked_wage': 0,
    }
    labour = dict(labour_defaults, **(labour_settings or {}))
    for key in labour_defaults:
        labour[key] = number(labour[key], key)
    if chill_days is not None and (isinstance(chill_days, bool) or not isinstance(chill_days, int) or chill_days < 0):
        raise ValueError("Chill days must be a whole number of 0 or greater.")
    if production_start_settings is None:
        production_start_settings = ProductionStartSettings()
    if not isinstance(production_start_settings, ProductionStartSettings):
        raise ValueError("Production-start settings have an invalid structure.")
    production_start_hours = {
        'COOKED': production_start_settings.cooked_hour,
        'RAW': production_start_settings.raw_hour,
    }
    jobs, notices, seen = [], [], set()
    for order in orders:
        try:
            planned = date(int(order.prod_year), int(order.prod_month), int(order.prod_date))
        except (TypeError, ValueError):
            notices.append(f"{order.order_no}: ไม่พบวันที่ผลิตเดิม จัดแผนให้อัตโนมัติไม่ได้")
            continue
        # Keep Orders after the visible period as possible pull-forward
        # candidates for the "reduce RM storage" proposal.  They are not part
        # of the baseline plan, and are included in a proposal only when the
        # whole Order is actually moved into the selected timeframe.
        if planned < start:
            continue
        candidate_only = planned > end
        load_date = order_due_date(order)
        _, _order_cups, qty = outstanding_order_quantities(order)
        if qty <= EPS:
            continue
        if not order.record_id or order.record_id in seen:
            raise ValueError("Order ต้องมี record_id ไม่ซ้ำกัน กรุณาบันทึก Order ก่อน")
        seen.add(order.record_id)
        p = profiles.get(order.record_id, {})
        size = normalize_size_class(order.rm_size)
        supported = size in ('M', 'S', 'SS')
        special_required_kg = None
        if size in SPECIAL_RM_SIZES:
            wt_pd_required_kg = number(order.wt_pd_kg, 'WT/PD kg', optional=True)
            special_required_kg = wt_pd_required_kg or number(
                order.ho_weight_kg, 'WT/HO kg', optional=True
            )
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
            country=order.country.strip(),
            class_groups={
                class_name.casefold(): class_group_for_order(order, class_name, classes).casefold()
                for class_name in operation_classes
            },
            line=production_type_for_order(order), market=market_type_for_order(order, classes),
            size=order.rm_size, stock_size=size, due=load_date.isoformat(),
            day=planned.isoformat(), qty=qty, cups=_order_cups, yield_rate=weights.wontons_per_kg(size) if supported else 0,
            rm_required_kg=special_required_kg,
            locked=bool(p.get('locked', False)), egg=p.get('egg', ''), soup_rank=rank,
            earliest=earliest, status=ready, ready_date=ready_date,
            max_qty=number(p.get('max_qty', 0), 'จำนวนที่พร้อม'), reviewer=p.get('reviewer', '').strip(),
            candidate_only=candidate_only,
            replan_eligible=_load_date_within_replan_limit(order, replan_load_cutoff)))
    lots = []
    stock = tuple(stock)
    stock_types = {record.record_id: record.record_type for record in stock}
    forecasts = [r.source_label for r in stock if r.record_type == 'prediction' and r.record_date <= end.isoformat()]
    for lot in _inventory_lots(stock, tuple(ranges), weights):
        lots.append(dict(day=lot.available_date.isoformat(), market=lot.market_type,
                         size=lot.eligible_classes[0], kg=lot.remaining_kg,
                         is_stock=stock_types.get(lot.record_id) == 'existing'))
    # Include unusable shrimp in residual/cost; never make it available to an order.
    # Calculate each record separately to preserve its arrival date.
    for r in stock:
        classified = sum(l.remaining_kg for l in _inventory_lots((r,), tuple(ranges), weights))
        special_stock = 0.0
        for entry in r.entries:
            special_size = normalize_size_class(entry.size_class)
            if special_size in SPECIAL_RM_SIZES:
                weight = float(entry.weight)
                lots.append(dict(
                    day=r.record_date,
                    market=entry.market_type or r.market_type,
                    size=special_size,
                    kg=weight,
                    is_stock=r.record_type == 'existing',
                ))
                special_stock += weight
        unused = sum(float(e.weight) for e in r.entries) - classified - special_stock
        if unused > EPS:
            lots.append(dict(day=r.record_date, market=r.market_type, size='Unused', kg=unused))
    for lot in lots:
        number(lot['kg'], 'Stock kg')
        lot['freeze_day'] = (
            (date.fromisoformat(lot['day']) + timedelta(days=chill_days)).isoformat()
            if chill_days is not None else None
        )
    # Do not bring every later Order into the search.  A candidate must use a
    # market/size RM pool that arrives in this timeframe and must be possible
    # to make as one complete Order from physical RM available by its end.
    # This keeps the no-split optimisation focused and predictable.
    physical_by_pool = defaultdict(float)
    timeframe_by_pool = defaultdict(float)
    for lot in lots:
        if lot['day'] <= end.isoformat():
            pool = (lot['market'], lot['size'])
            physical_by_pool[pool] += lot['kg']
            if lot['day'] >= start.isoformat() and not lot.get('is_stock'):
                timeframe_by_pool[pool] += lot['kg']

    def rm_requirement(job):
        if job['rm_required_kg'] is not None:
            return job['rm_required_kg']
        return job['qty'] / job['yield_rate'] if job['yield_rate'] > EPS else None

    jobs = [
        job for job in jobs
        if not job['candidate_only']
        or (
            job['replan_eligible']
            and
            rm_requirement(job) is not None
            and timeframe_by_pool[(job['market'], job['stock_size'])] > EPS
            and rm_requirement(job) <= physical_by_pool[(job['market'], job['stock_size'])] + EPS
        )
    ]
    return dict(start=start.isoformat(), settings=s, labour=labour, jobs=jobs, lots=lots,
                capacity={'RAW': float(raw), 'COOKED': float(cooked)}, notices=notices,
                forecasts=forecasts, operation_rules=operation_rules, chill_days=chill_days,
                production_start_hours=production_start_hours)


def signature(context):
    return sha256(json.dumps(context, sort_keys=True, ensure_ascii=False, allow_nan=False).encode()).hexdigest()


def _is_frozen_lot(lot, day, start):
    """Opening stock and chilled lots past their freeze day are frozen RM."""
    return (lot.get('is_stock', False) or lot['day'] < start
            or (lot.get('freeze_day') is not None and day >= lot['freeze_day']))


def baseline_rows(context):
    return [
        dict(job=j['id'], day=j['day'], qty=j['qty'])
        for j in context['jobs'] if not j.get('candidate_only', False)
    ]


def _operation_rule_rank(job, rules):
    """Return the workflow position for one cooked job, or a final fallback."""

    for rule_index, rule in enumerate(rules):
        for node_index, node in enumerate(rule['nodes']):
            if job.get('class_groups', {}).get(node['class'].casefold()) == node['group'].casefold():
                return rule_index, node_index
    return len(rules), 0


def evaluate(context, rows, apply_operation_rules=False, allow_unscheduled=False, allow_replan=False):
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
    deferred = []
    moved = defaultdict(float)
    for row in rows:
        if row['job'] not in jobs or number(row['qty'], 'จำนวนผลิต') <= EPS:
            raise ValueError("แถวแผนไม่ถูกต้อง")
        j = jobs[row['job']]
        totals[j['id']] += row['qty']
        if row['day'] != j['day']:
            moved[j['id']] += row['qty']
            # A normal proposal is only allowed to pull an Order forward.  A
            # reduce-storage proposal deliberately rebuilds the adjustable
            # portion of the schedule, so it may place a non-locked Order on
            # any valid day from ``adjust_from`` onward.
            if (j['locked'] or row['day'] < adjust_from
                    or (not allow_replan and row['day'] >= j['day'])):
                errors.append(f"{j['order']}: ย้ายงานนอกช่วงหรือเป็นงานล็อก")
            if j['earliest'] and row['day'] < j['earliest']:
                errors.append(f"{j['order']}: ยังไม่อนุญาตให้ผลิตเร็วในวันนี้")
            if j['status'] == 'blocked':
                errors.append(f"{j['order']}: วัสดุไม่พร้อม")
            elif j['status'] in ('ready', 'partial'):
                if j['ready_date'] != row['day'] or not j['reviewer'] or moved[j['id']] > j['max_qty'] + EPS:
                    errors.append(f"{j['order']}: เกินวันที่/จำนวนที่ยืนยัน")
            else:
                pending.append(f"{j['order']}: รอยืนยันวัสดุ {row['day']}")
    for j in jobs.values():
        if allow_unscheduled:
            if not j.get('candidate_only', False) and j['id'] not in totals:
                deferred.append(j['id'])
            continue
        if j.get('candidate_only', False) and j['id'] not in totals:
            continue
        if abs(totals[j['id']] - j['qty']) > EPS:
            errors.append(f"{j['order']}: จำนวนไม่ตรงกับออเดอร์คงเหลือ")
    # Preserve each lot while allocating RM.  Besides making the consumption
    # order deterministic, this lets an unconsumed chilled lot leave the
    # usable-RM balance on its configured Freeze day.
    lot_balances = [dict(lot, lot_id=index, remaining_kg=float(lot['kg']))
                    for index, lot in enumerate(context['lots'])]
    daily, schedule = [], []
    for offset in range(int(s['lookahead'])):
        day = (start + timedelta(days=offset)).isoformat()
        # Do not put work on a closed day even while displaying an invalid
        # imported/manual plan.  The error above tells the user what to fix.
        selected = [] if date.fromisoformat(day).weekday() in FACTORY_HOLIDAY_WEEKDAYS else [r for r in rows if r['day'] == day]
        changes = 0
        hours = {}
        day_schedule = []
        for line in ('RAW', 'COOKED'):
            def operation_key(row):
                job = jobs[row['job']]
                # On the raw line, CODE identifies the actual SKU changeover.
                # Keep matching codes together even where their other order
                # detail differs, so they become one uninterrupted run.
                return job['code'] if line == 'RAW' and job['code'] else job['sku']

            def work_key(row):
                job = jobs[row['job']]
                fallback = (
                    job['soup_rank'] if job['soup_rank'] is not None else 999,
                    operation_key(row),
                    row['job'],
                )
                if line == 'COOKED' and apply_operation_rules:
                    return (*_operation_rule_rank(job, context.get('operation_rules', ())), *fallback)
                return fallback if line == 'COOKED' else (operation_key(row), row['job'])

            work = sorted(
                (r for r in selected if jobs[r['job']]['line'] == line),
                key=work_key,
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
                # Raw product changes run continuously.  The standard 30-minute
                # break/setup applies only to the cooked line.
                if line != 'RAW' and previous is not None and previous != current_operation:
                    changes += 1
                    elapsed += s['setup_minutes'] / 60
                previous = current_operation
                planned_wontons = r['qty']
                duration = planned_wontons / context['capacity'][line] * s['shift_hours'] if context['capacity'][line] else float('inf')
                if not math.isfinite(duration):
                    errors.append(f"{day} {line}: capacity เป็นศูนย์")
                    duration = 0
                entry = dict(r, start_hours=elapsed, line=line)
                schedule.append(entry)
                day_schedule.append(entry)
                elapsed += duration
            hours[line] = elapsed
            if elapsed > s['shift_hours'] + EPS:
                errors.append(f"{day} {line}: ใช้ {elapsed:.2f} ชม. เกิน {s['shift_hours']:g} ชม.")
        # Allocate RM in the same time order displayed by the timeline.  This
        # does not change feasibility (the final balance is identical), but it
        # identifies exactly how much of each production run is covered.
        start_hours = context.get(
            'production_start_hours',
            {'COOKED': DEFAULT_COOKED_START_HOUR, 'RAW': DEFAULT_RAW_START_HOUR},
        )
        for entry in sorted(
            day_schedule,
            key=lambda item: (
                (start_hours.get(item['line'], PRODUCTION_WINDOW_START_HOUR)
                 - PRODUCTION_WINDOW_START_HOUR) % 24 + item['start_hours'],
                item['line'],
                item['job'],
            ),
        ):
            r = entry
            j = jobs[r['job']]
            special_required = j.get('rm_required_kg')
            if (j['line'] not in context['capacity'] or
                    (j['yield_rate'] <= 0 and (special_required is None or special_required <= EPS))):
                errors.append(f"{j['order']}: ยังไม่รองรับไลน์หรือ RM {j['size']}")
                entry.update(rm_required_kg=None, rm_allocated_kg=None,
                             rm_shortage_kg=None, rm_coverage=0.0)
                continue
            required = (
                r['qty'] / j['qty'] * special_required
                if special_required is not None else r['qty'] / j['yield_rate']
            )
            balance_key = (j['market'], j['stock_size'])
            available_lots = sorted(
                (
                    lot for lot in lot_balances
                    if lot['market'] == balance_key[0]
                    and lot['size'] == balance_key[1]
                    and lot['day'] <= day
                    and (context.get('allow_frozen_stock', False)
                         or not _is_frozen_lot(lot, day, context['start']))
                    and lot['remaining_kg'] > EPS
                ),
                key=lambda lot: (_is_frozen_lot(lot, day, context['start']), lot['day'], lot['lot_id']),
            )
            available = sum(lot['remaining_kg'] for lot in available_lots)
            allocated = min(required, available)
            shortage = required - allocated
            amount_to_allocate = allocated
            frozen_used = 0.0
            allocations = []
            for lot in available_lots:
                used = min(amount_to_allocate, lot['remaining_kg'])
                frozen = _is_frozen_lot(lot, day, context['start'])
                if frozen:
                    frozen_used += used
                allocations.append(dict(lot_id=lot['lot_id'], kg=used, frozen=frozen))
                lot['remaining_kg'] -= used
                amount_to_allocate -= used
                if amount_to_allocate <= EPS:
                    break
            entry.update(
                rm_required_kg=required,
                rm_allocated_kg=allocated,
                rm_shortage_kg=shortage,
                rm_coverage=allocated / required if required > EPS else 1.0,
                rm_frozen_kg=frozen_used,
                rm_fresh_kg=allocated - frozen_used,
                rm_allocations=allocations,
            )
            if shortage > EPS:
                errors.append(f"{day}: RM {balance_key[0]} {balance_key[1]} ขาด {shortage:,.1f} kg")
        # ``remaining`` is the physical RM left unused after the plan.  A lot
        # that reaches its Freeze day is no longer usable as chilled RM, but it
        # is still stock left over and must remain visible in the daily
        # operational balance.  This daily value includes opening stock so it
        # remains useful when allocating today's work; the plan-card residual
        # below applies the selected timeframe scope separately.
        by_size = {
            size: sum(
                lot['remaining_kg'] for lot in lot_balances
                if lot['size'] == size and lot['day'] <= day
            )
            for size in ('M', 'S', 'SS', 'HC', 'BK', 'Unused')
        }
        daily.append(dict(day=day, remaining=sum(by_size.values()), by_size=by_size,
                          changes=changes, hours=hours))
    active = [day for day in daily if day['day'] >= adjust_from]
    # Labour is paid for the configured shift even when a line has no work.
    # Closed factory days are excluded because staff are not scheduled then.
    labour = context.get('labour', {})
    labour_rates = {
        'RAW': (labour.get('raw_labour', 0), labour.get('raw_wage', 0)),
        'COOKED': (labour.get('cooked_labour', 0), labour.get('cooked_wage', 0)),
    }
    free_labour_daily = []
    free_labour_cost = 0.0
    for day in daily:
        if date.fromisoformat(day['day']).weekday() in FACTORY_HOLIDAY_WEEKDAYS:
            continue
        line_costs = {}
        for line, (labour_count, wage) in labour_rates.items():
            actual_hours = min(max(float(day['hours'].get(line, 0)), 0.0), s['shift_hours'])
            free_hours = max(s['shift_hours'] - actual_hours, 0.0)
            cost_for_line = free_hours * labour_count * wage
            line_costs[line] = {
                'actual_hours': actual_hours,
                'free_hours': free_hours,
                'cost': cost_for_line,
            }
            free_labour_cost += cost_for_line
        free_labour_daily.append(dict(day=day['day'], lines=line_costs,
                                      cost=sum(item['cost'] for item in line_costs.values())))
    # The proposal cards report only RM left over from arrivals inside the
    # selected planning timeframe.  Opening stock remains available to the
    # allocation above, but is not part of this timeframe residual.
    horizon_end = (start + timedelta(days=int(s['lookahead']) - 1)).isoformat()
    residual = sum(
        lot['remaining_kg'] for lot in lot_balances
        if context['start'] <= lot['day'] <= horizon_end and not lot.get('is_stock')
    )
    # Any RM left unused at the end of the selected timeframe must be moved
    # into Freeze in full.  ``freeze_percent`` is retained in saved settings
    # for backward compatibility, but no longer changes this business rule.
    freeze_kg = residual
    freeze_cost = None if freeze_kg is None or s['freeze_cost'] is None else freeze_kg * s['freeze_cost']
    change_count = sum(d['changes'] for d in active)
    setup_cost = None if s['stop_cost'] is None else change_count * s['setup_minutes'] / 60 * s['stop_cost']
    cost = None if freeze_cost is None or setup_cost is None else freeze_cost + setup_cost + free_labour_cost
    late = len({r['job'] for r in rows if r['day'] > jobs[r['job']]['due']})
    return dict(rows=rows, schedule=schedule, daily=daily, remaining=residual, freeze_kg=freeze_kg,
                freeze_cost=freeze_cost, setup_cost=setup_cost,
                free_labour_cost=free_labour_cost, free_labour_daily=free_labour_daily,
                cost=cost, changes=change_count,
                moved=len(moved), late=late, errors=list(dict.fromkeys(errors)),
                pending=list(dict.fromkeys(pending)), signature=signature(context),
                deferred=tuple(deferred),
                status='invalid' if errors else 'conditional' if pending else 'review')


def _rm_shortage(plan):
    """Return the RM shortage represented by a fully evaluated proposal."""

    return sum(max(float(entry.get('rm_shortage_kg') or 0), 0) for entry in plan['schedule'])


def _is_rm_shortage_error(error):
    return 'RM ' in error and ' ขาด ' in error


def _move_complete_job(rows, job, target):
    """Move one order as an indivisible unit, preserving all other rows."""

    moved = False
    result = []
    for row in rows:
        copied = dict(row)
        if copied['job'] == job['id']:
            if moved:
                raise ValueError('แผนลดการเก็บ RM รองรับเฉพาะ Order ที่ยังไม่ถูกแบ่ง')
            copied['day'] = target
            moved = True
        result.append(copied)
    if not moved:
        if not job.get('candidate_only', False):
            raise ValueError('ไม่พบ Order ที่ต้องการย้ายในแผน')
        result.append(dict(job=job['id'], day=target, qty=job['qty']))
    return result


def _complete_order_is_covered(plan, job_id):
    entries = [entry for entry in plan['schedule'] if entry['job'] == job_id]
    return bool(entries) and all((entry.get('rm_shortage_kg') or 0) <= EPS for entry in entries)


def _structural_errors(plan):
    """Errors which cannot be accepted merely to consume more RM."""

    return Counter(error for error in plan['errors'] if not _is_rm_shortage_error(error))


def _adds_structural_errors(trial, current):
    previous = _structural_errors(current)
    proposed = _structural_errors(trial)
    return any(proposed[error] > previous[error] for error in proposed)


def _job_rm_requirement(job):
    required = job.get('rm_required_kg')
    if required is not None:
        return required
    return job['qty'] / job['yield_rate'] if job['yield_rate'] > EPS else 0.0


def _eligible_days(job, days):
    """Return adjustable production dates compatible with readiness rules."""

    if job['locked'] or job['status'] == 'blocked':
        return ()
    if job['status'] == 'partial' and job['max_qty'] < job['qty'] - EPS:
        return ()
    result = []
    for target in days:
        if job['earliest'] and job['earliest'] > target:
            continue
        if job['status'] == 'ready' and (job['ready_date'] != target or not job['reviewer']):
            continue
        if job['status'] == 'partial' and (job['ready_date'] != target or not job['reviewer']):
            continue
        result.append(target)
    return tuple(result)


def _fill_candidate_orders(context, current, candidates, days, require_cost_reduction):
    """Greedily fill a draft while preserving its already chosen seed."""

    while True:
        best = None
        current_shortage = _rm_shortage(current)
        for job in candidates:
            if any(row['job'] == job['id'] for row in current['rows']):
                continue
            for target in _eligible_days(job, days):
                trial = evaluate(
                    context, [*current['rows'], dict(job=job['id'], day=target, qty=job['qty'])],
                    apply_operation_rules=True, allow_unscheduled=True, allow_replan=True,
                )
                if (_adds_structural_errors(trial, current)
                        or not _complete_order_is_covered(trial, job['id'])
                        or _rm_shortage(trial) > current_shortage + EPS
                        or trial['remaining'] >= current['remaining'] - EPS):
                    continue
                if require_cost_reduction:
                    if current['cost'] is None or trial['cost'] is None or trial['cost'] >= current['cost'] - EPS:
                        continue
                score = (trial['remaining'], _rm_shortage(trial), trial['changes'],
                         job['due'], job['id'], target)
                if best is None or score < best[0]:
                    best = (score, trial)
        if best is None:
            return current
        current = best[1]


def _reduce_material_plan(context, require_cost_reduction=False):
    """Rebuild the adjustable schedule to minimise end-of-window RM.

    This intentionally does *not* start from the old placement.  Everything
    from ``adjust_from`` onward is removed.  Every later Order, including an
    Order that was previously inside the visible window, becomes an optional
    whole-unit candidate.  The new schedule contains only the candidates that
    genuinely consume RM without creating a shortage or capacity/market
    conflict; all others are deferred beyond the window.
    """

    jobs = {job['id']: job for job in context['jobs']}
    settings = context['settings']
    start = date.fromisoformat(context['start'])
    adjust_from = date.fromisoformat(settings['adjust_from'])
    end = start + timedelta(days=int(settings['lookahead']) - 1)
    days = tuple(
        (start + timedelta(days=offset)).isoformat()
        for offset in range((adjust_from - start).days, int(settings['lookahead']))
        if (start + timedelta(days=offset)).weekday() not in FACTORY_HOLIDAY_WEEKDAYS
    )

    # Preserve only work that is genuinely outside the reset area: production
    # before the chosen date and explicit locked Orders.  Every other Order is
    # a selectable whole-order candidate.  In particular, an old HC placement
    # is not forced back into this window when selecting an SS Order uses the
    # available RM more effectively; that HC Order is simply deferred.
    frozen_rows = [
        dict(job=job['id'], day=job['day'], qty=job['qty'])
        for job in jobs.values()
        if not job.get('candidate_only', False)
        and (job['day'] < adjust_from.isoformat() or job['locked'])
    ]
    frozen_ids = {row['job'] for row in frozen_rows}
    candidates = [
        job for job in jobs.values()
        if job['id'] not in frozen_ids and job.get('replan_eligible', True)
    ]
    current = evaluate(
        context, frozen_rows, apply_operation_rules=True,
        allow_unscheduled=True, allow_replan=True,
    )

    # Market cannot be mixed within a production line/day.  A single greedy
    # path can otherwise fill every slot with the first market it encounters,
    # stranding an available domestic pool such as SS.  Evaluate the normal
    # path plus one seeded path for each market, then retain the best total-RM
    # result.  This remains generic: no size, customer, or date is hard coded.
    drafts = [_fill_candidate_orders(context, current, candidates, days, require_cost_reduction)]
    for market in sorted({job['market'] for job in candidates}):
        seed = None
        for job in (item for item in candidates if item['market'] == market):
            for target in _eligible_days(job, days):
                trial = evaluate(
                    context, [*current['rows'], dict(job=job['id'], day=target, qty=job['qty'])],
                    apply_operation_rules=True, allow_unscheduled=True, allow_replan=True,
                )
                if (_adds_structural_errors(trial, current)
                        or not _complete_order_is_covered(trial, job['id'])
                        or _rm_shortage(trial) > _rm_shortage(current) + EPS
                        or trial['remaining'] >= current['remaining'] - EPS):
                    continue
                if require_cost_reduction and (
                    current['cost'] is None or trial['cost'] is None or trial['cost'] >= current['cost'] - EPS
                ):
                    continue
                score = (trial['remaining'], _rm_shortage(trial), trial['changes'], job['due'], job['id'], target)
                if seed is None or score < seed[0]:
                    seed = (score, trial)
        if seed is not None:
            drafts.append(_fill_candidate_orders(context, seed[1], candidates, days, require_cost_reduction))
    current = min(drafts, key=lambda plan: (plan['remaining'], _rm_shortage(plan), plan['changes']))

    return evaluate(
        context, current['rows'], apply_operation_rules=True,
        allow_unscheduled=True, allow_replan=True,
    )


def compare(context):
    """Build baseline plus whole-order alternatives for the planning window."""

    base = evaluate(context, baseline_rows(context))
    material = _reduce_material_plan(context)
    balanced_context = dict(context, allow_frozen_stock=True)
    balanced = _reduce_material_plan(balanced_context, require_cost_reduction=True)
    balanced['signature'] = signature(context)
    return [
        dict(base, id='baseline', title=TITLES['baseline']),
        dict(material, id='material', title=TITLES['material']),
        dict(balanced, id='balanced', title=TITLES['balanced']),
    ]
