"""Plan comparison UI. Domain calculations: planning/alternatives.py."""
from __future__ import annotations

from datetime import date, datetime, timedelta
import calendar
import tkinter as tk
from tkinter import ttk, messagebox
from uuid import uuid4
import threading
import json
from .common import PROJECT_ROOT
from rm_planner.planning.alternatives import (FACTORY_HOLIDAY_WEEKDAYS, build_context,
                                               compare, settings_defaults, signature, number)
from rm_planner.planning.proposal_store import load_preferences, save_preferences, save_approval

STATUS = {'invalid': 'ติดข้อจำกัด', 'conditional': 'รอตรวจข้อมูล', 'review': 'รอยืนยันทั้งชุด'}
READY = {'unknown': 'ยังไม่ทราบ', 'ready': 'พร้อม', 'partial': 'พร้อมบางส่วน', 'blocked': 'ไม่พร้อม'}


def next_factory_workday(value):
    """Return the first non-holiday day on or after ``value``."""

    while value.weekday() in FACTORY_HOLIDAY_WEEKDAYS:
        value += timedelta(days=1)
    return value


def fmt(value):
    return 'ยังไม่ระบุ' if value is None else f'{value:,.1f}'


class PlanViewMixin:
    def _build_plan_tab(self):
        self._proposal_path = PROJECT_ROOT / 'Data' / 'Planning' / 'preferences.json'
        self._proposal_load_error = ''
        try:
            self._proposal_preferences = load_preferences(self._proposal_path)
        except (ValueError, OSError) as exc:
            self._proposal_preferences = {'settings': {}, 'profiles': {}}
            self._proposal_load_error = str(exc)
        self._proposals = []
        self._proposal_selected = 0
        self.plan_start_date_var.set(next_factory_workday(date.today()).isoformat())
        options = dict(settings_defaults(), **self._proposal_preferences['settings'])
        options.pop('adjustment', None)  # Legacy duration; replaced by an explicit date.
        self._proposal_vars = {
            key: tk.StringVar(value=(
                str(int(float(value))) if key == 'lookahead' and value not in (None, '')
                else '' if value is None else str(value)
            ))
            for key, value in options.items()
        }
        saved_adjust_from = self._proposal_vars['adjust_from'].get()
        try:
            saved_adjust_from = next_factory_workday(date.fromisoformat(saved_adjust_from)).isoformat()
        except (TypeError, ValueError):
            saved_adjust_from = self.plan_start_date_var.get()
        self.adjust_from_var = tk.StringVar(value=saved_adjust_from)
        control = ttk.Frame(self.plan_tab)
        control.pack(fill='x', pady=8)
        ttk.Label(control, text='วันเริ่ม').pack(side='left')
        self.plan_start_date_entry = ttk.Entry(control, textvariable=self.plan_start_date_var, width=14,
                                                state='readonly', font=('Segoe UI', 12))
        self.plan_start_date_entry.pack(side='left', padx=(6, 0))
        ttk.Button(control, text='📅', width=3, command=self._open_plan_date_picker).pack(side='left', padx=(2, 6))
        ttk.Label(control, text='มองล่วงหน้า (วัน)').pack(side='left', padx=(8, 4))
        validate_integer = (self.register(self._is_day_integer), '%P')
        ttk.Spinbox(control, textvariable=self._proposal_vars['lookahead'], from_=1, to=31, increment=1,
                    width=5, validate='key', validatecommand=validate_integer).pack(side='left')
        ttk.Label(control, text='เริ่มปรับแผน').pack(side='left', padx=(8, 4))
        ttk.Entry(control, textvariable=self.adjust_from_var, width=14, state='readonly',
                  font=('Segoe UI', 12)).pack(side='left')
        ttk.Button(control, text='📅', width=3,
                   command=lambda: self._open_plan_date_picker(
                       self.adjust_from_var, self.plan_start_date_var.get(), 'เลือกวันเริ่มปรับแผน',
                       self._plan_horizon_end())).pack(side='left', padx=(2, 6))
        ttk.Button(control, text='ต้นทุน / สมมติฐาน', command=self._proposal_settings_dialog).pack(side='right')
        self._proposal_cards = ttk.Frame(self.plan_tab)
        self._proposal_cards.pack(fill='x', pady=8)
        self._proposal_detail = tk.StringVar(value='กำลังแสดงแผนเดิมจาก Prod.Date ของ Order')
        ttk.Label(self.plan_tab, textvariable=self._proposal_detail, wraplength=1050).pack(fill='x', pady=(0, 6))
        notebook = ttk.Notebook(self.plan_tab)
        notebook.pack(fill='both', expand=True)
        self._proposal_tables = {}
        for key, title, columns in [
            ('jobs', 'แผนผลิต (Excel format)', ('Order', 'แผนเดิม', 'แผนใหม่', 'ไลน์', 'RM', 'จำนวนเกี๊ยว', 'ความพร้อม', 'ล็อก'))]:
            frame = ttk.Frame(notebook)
            notebook.add(frame, text=title)
            tree = ttk.Treeview(frame, columns=columns, show='headings', height=8)
            for column in columns:
                tree.heading(column, text=column)
                tree.column(column, width=125, minwidth=60)
            tree.grid(row=0, column=0, sticky='nsew')
            vs = ttk.Scrollbar(frame, orient='vertical', command=tree.yview)
            vs.grid(row=0, column=1, sticky='ns')
            hs = ttk.Scrollbar(frame, orient='horizontal', command=tree.xview)
            hs.grid(row=1, column=0, sticky='ew')
            tree.configure(yscrollcommand=vs.set, xscrollcommand=hs.set)
            frame.columnconfigure(0, weight=1)
            frame.rowconfigure(0, weight=1)
            self._proposal_tables[key] = tree
        timeline = ttk.Frame(notebook)
        notebook.add(timeline, text='แผนผลิต (Timeline format)')
        timeline.rowconfigure(0, weight=1)
        timeline.columnconfigure(0, weight=1)
        self._proposal_timeline_canvas = tk.Canvas(timeline, bg='white', highlightthickness=0)
        self._proposal_timeline_canvas.grid(row=0, column=0, sticky='nsew')
        timeline_vertical = ttk.Scrollbar(timeline, orient='vertical', command=self._proposal_timeline_canvas.yview)
        timeline_vertical.grid(row=0, column=1, sticky='ns')
        timeline_horizontal = ttk.Scrollbar(timeline, orient='horizontal', command=self._proposal_timeline_canvas.xview)
        timeline_horizontal.grid(row=1, column=0, sticky='ew')
        self._proposal_timeline_canvas.configure(xscrollcommand=timeline_horizontal.set, yscrollcommand=timeline_vertical.set)
        self._proposal_timeline_canvas.bind('<Configure>', lambda _event: self._render_plan_timeline())
        notebook.bind('<<NotebookTabChanged>>', lambda _event: self._render_plan_timeline())
        actions = ttk.Frame(self.plan_tab)
        actions.pack(fill='x', pady=8)
        ttk.Button(actions, text='แก้ความพร้อม / วันผลิตเร็วที่สุด / ล็อกงาน', command=self._proposal_job_dialog).pack(side='left')
        ttk.Button(actions, text='แผนที่ยืนยันแล้ว', command=self._proposal_history).pack(side='left', padx=8)
        ttk.Button(actions, text='ตรวจและยืนยันแผนที่เลือก', command=self._approve_proposal).pack(side='right')
        self._proposal_tables['jobs'].bind('<Double-1>', lambda _: self._proposal_job_dialog())
        ttk.Label(self.plan_tab, textvariable=self.plan_status_var, relief='sunken', padding=5).pack(fill='x')
        self.plan_status_var.set(self._proposal_load_error or 'แสดงแผนเดิมจาก Order • ยังไม่ได้ตรวจ RM หรือ Capacity')
        for var in [self.plan_start_date_var, self.adjust_from_var, *self._proposal_vars.values()]:
            var.trace_add('write', lambda *_: self._plan_inputs_changed())

    def _plan_inputs_changed(self):
        try:
            start = date.fromisoformat(self.plan_start_date_var.get())
            adjust_from = date.fromisoformat(self.adjust_from_var.get())
            end = self._plan_horizon_end()
            normalized = min(max(adjust_from, start), end) if end else max(adjust_from, start)
            if normalized != adjust_from:
                self.adjust_from_var.set(normalized.isoformat())
        except ValueError:
            self.adjust_from_var.set(self.plan_start_date_var.get())
        self._invalidate_proposals()
        self.after_idle(self._render_baseline_preview)
        self.after_idle(lambda: self._calculate_proposals(quiet=True))

    @staticmethod
    def _is_day_integer(value):
        """Allow only whole days in the planning horizon controls."""
        return value == '' or value.isdigit()

    def _invalidate_proposals(self):
        self._proposals = []
        self._proposal_calculation_token = None
        if hasattr(self, '_proposal_cards'):
            for child in self._proposal_cards.winfo_children():
                child.destroy()
            for tree in self._proposal_tables.values():
                tree.delete(*tree.get_children())
            self._proposal_detail.set('ข้อมูลเปลี่ยนแล้ว กรุณาคำนวณใหม่')
            self.plan_status_var.set('กรุณาคำนวณใหม่ก่อนตรวจหรือยืนยัน')

    def _refresh_plan_date_options(self):
        """Keep the selected date valid after orders are refreshed.

        The date picker deliberately permits any future calendar date, rather
        than limiting staff to dates which happen to have an Order already.
        """
        try:
            selected = date.fromisoformat(self.plan_start_date_var.get().strip())
        except ValueError:
            selected = next_factory_workday(date.today())
        if selected < date.today():
            self.plan_start_date_var.set(next_factory_workday(date.today()).isoformat())
        self._plan_inputs_changed()

    def _plan_horizon_end(self):
        try:
            start = date.fromisoformat(self.plan_start_date_var.get())
            lookahead = int(self._proposal_vars['lookahead'].get())
            return start + timedelta(days=lookahead - 1) if 1 <= lookahead <= 31 else None
        except (TypeError, ValueError):
            return None

    def _open_plan_date_picker(self, target_var=None, minimum_date=None, dialog_title='เลือกวันเริ่ม', maximum_date=None):
        """Open a small dependency-free calendar for selecting a plan date."""
        target_var = target_var or self.plan_start_date_var
        try:
            selected = date.fromisoformat(target_var.get().strip())
        except ValueError:
            selected = date.today()
        try:
            minimum = date.fromisoformat(minimum_date) if minimum_date else date.today()
        except ValueError:
            minimum = date.today()
        selected = max(selected, minimum)
        if maximum_date:
            selected = min(selected, maximum_date)
        highlight_adjustable_days = target_var is self.adjust_from_var and maximum_date is not None
        picker = tk.Toplevel(self)
        picker.title(dialog_title)
        picker.transient(self)
        picker.resizable(False, False)
        month_var = tk.StringVar(value=f'{selected.year:04d}-{selected.month:02d}')
        body = ttk.Frame(picker, padding=10)
        body.pack(fill='both', expand=True)

        def current_month():
            year_text, month_text = month_var.get().split('-')
            return int(year_text), int(month_text)

        days = ttk.Frame(body)

        def select_day(day_number):
            year, month = current_month()
            chosen = date(year, month, day_number)
            if (chosen < minimum or (maximum_date and chosen > maximum_date)
                    or chosen.weekday() in FACTORY_HOLIDAY_WEEKDAYS):
                return
            target_var.set(chosen.isoformat())
            picker.destroy()

        def render_month():
            for child in days.winfo_children():
                child.destroy()
            year, month = current_month()
            month_var.set(f'{year:04d}-{month:02d}')
            title.configure(text=f'{calendar.month_name[month]} {year}')
            for column, name in enumerate(('Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun')):
                tk.Label(days, text=name, anchor='center', width=4,
                         foreground='#b22222' if column in FACTORY_HOLIDAY_WEEKDAYS else '#000000').grid(row=0, column=column, pady=(0, 3))
            for row, week in enumerate(calendar.monthcalendar(year, month), start=1):
                for column, day_number in enumerate(week):
                    if not day_number:
                        ttk.Label(days, text='', width=4).grid(row=row, column=column)
                        continue
                    chosen = date(year, month, day_number)
                    holiday = chosen.weekday() in FACTORY_HOLIDAY_WEEKDAYS
                    unavailable = holiday or chosen < minimum or (maximum_date and chosen > maximum_date)
                    highlighted = highlight_adjustable_days and selected <= chosen <= maximum_date
                    button = tk.Button(
                        days, text=str(day_number), width=3,
                        command=lambda value=day_number: select_day(value),
                        relief='flat', borderwidth=0,
                        background='#fde4e4' if holiday else '#d9eefb' if highlighted else '#ffffff',
                        activebackground='#f5caca' if holiday else '#b9def5' if highlighted else '#ececec',
                        disabledforeground='#b22222' if holiday else '#a0a0a0',
                    )
                    if unavailable:
                        button.configure(state='disabled', background='#fde4e4' if holiday else '#f3f3f3')
                    button.grid(row=row, column=column, padx=1, pady=1)

        def move_month(delta):
            year, month = current_month()
            absolute = year * 12 + month - 1 + delta
            target_year, target_month = divmod(absolute, 12)
            if date(target_year, target_month + 1, 1) < minimum.replace(day=1):
                return
            if maximum_date and date(target_year, target_month + 1, 1) > maximum_date.replace(day=1):
                return
            month_var.set(f'{target_year:04d}-{target_month + 1:02d}')
            render_month()

        header = ttk.Frame(body)
        header.pack(fill='x')
        ttk.Button(header, text='‹', width=3, command=lambda: move_month(-1)).pack(side='left')
        title = ttk.Label(header, anchor='center', font=('Segoe UI', 10, 'bold'))
        title.pack(side='left', fill='x', expand=True)
        ttk.Button(header, text='›', width=3, command=lambda: move_month(1)).pack(side='right')
        days.pack(pady=(8, 0))
        first_selectable = next_factory_workday(minimum)
        ttk.Button(body, text='วันแรกที่เลือกได้',
                   command=lambda: (target_var.set(first_selectable.isoformat()), picker.destroy()),
                   state=tk.NORMAL if not maximum_date or first_selectable <= maximum_date else tk.DISABLED).pack(fill='x', pady=(8, 0))
        render_month()
        picker.grab_set()

    def _refresh_plan_table(self):
        self._plan_inputs_changed()

    @staticmethod
    def _order_prod_date(order):
        """Return the original scheduled production date, never a load/data date."""
        try:
            return date(int(order.prod_year), int(order.prod_month), int(order.prod_date)).isoformat()
        except (TypeError, ValueError):
            return ''

    def _baseline_orders_in_window(self):
        try:
            start = date.fromisoformat(self.plan_start_date_var.get().strip())
            lookahead = int(float(self._proposal_vars['lookahead'].get()))
            if not 1 <= lookahead <= 31:
                return (), None
        except (TypeError, ValueError):
            return (), None
        end = start + timedelta(days=lookahead - 1)
        records = self.result.records if self.result is not None else list(self.saved_order_records.values())
        rows = []
        for order in records:
            planned = self._order_prod_date(order)
            if not planned or not start <= date.fromisoformat(planned) <= end:
                continue
            quantity = order.total_wontons
            rows.append((planned, order, quantity))
        return tuple(sorted(rows, key=lambda row: (row[0], row[1].order_no, row[1].record_id))), end

    def _render_baseline_preview(self):
        """Show the imported production schedule without requiring planning inputs."""
        if self._proposals or not hasattr(self, '_proposal_cards'):
            return
        rows, end = self._baseline_orders_in_window()
        if end is None:
            return
        for child in self._proposal_cards.winfo_children():
            child.destroy()
        box = tk.Frame(self._proposal_cards, bg='white', highlightthickness=2,
                       highlightbackground='#168078', padx=8, pady=8)
        box.pack(fill='x')
        total = sum(float(quantity or 0) for _, _, quantity in rows)
        tk.Label(box, text='คงแผนเดิม', bg='white', anchor='w', font=('Segoe UI', 10, 'bold')).pack(fill='x')
        tk.Label(box, text='แผนจาก Prod.Date ใน Order • ยังไม่ตรวจ RM / Capacity / ความพร้อม',
                 bg='white', anchor='w', font=('Segoe UI', 9)).pack(fill='x', pady=(2, 4))
        tk.Label(box, text=f'{len(rows):,} งาน  |  {fmt(total)} เกี๊ยว', bg='white', anchor='w',
                 font=('Segoe UI', 16, 'bold')).pack(fill='x')
        self._proposal_detail.set(
            f'แผนเดิม {self.plan_start_date_var.get()} ถึง {end.isoformat()} • '
            f'{len(rows):,} งาน • อ้างอิง Prod.Date ของ Order โดยตรง'
        )
        tree = self._proposal_tables['jobs']
        tree.delete(*tree.get_children())
        self._proposal_row_ids = {}
        for index, (planned, order, quantity) in enumerate(rows):
            iid = f'baseline:{index}'
            self._proposal_row_ids[iid] = order.record_id
            tree.insert('', 'end', iid=iid, values=(
                order.order_no, planned, planned, order.group_2 or order.group_1,
                order.rm_size or '—', fmt(quantity), 'ยังไม่ตรวจ', '—',
            ))
        self.plan_status_var.set(
            f'คงแผนเดิม: {len(rows):,} งาน ระหว่าง {self.plan_start_date_var.get()}–{end.isoformat()} '
            '• กำลังรอคำนวณทางเลือกอัตโนมัติ'
        )

    def _proposal_context(self):
        records = self.result.records if self.result is not None else list(self.saved_order_records.values())
        return build_context(records, self.assortment_actual_records.values(),
            self._current_assortment_size_range_definitions(), self.capacity_settings,
            tuple(self.class_definitions.values()), self.wonton_weight_settings,
            self.plan_start_date_var.get().strip(), {
                **{k: v.get() for k, v in self._proposal_vars.items()},
                'adjust_from': self.adjust_from_var.get(),
            },
            self._proposal_preferences['profiles'])

    def _calculate_proposals(self, quiet=False):
        try:
            context = self._proposal_context()
            if not context['jobs']:
                raise ValueError('ไม่พบ Order ที่มีวันที่ผลิตเดิมในช่วงนี้ ตรวจวันเริ่มและข้อมูล Order')
        except (ValueError, OSError, TypeError) as exc:
            if not quiet:
                self._invalidate_proposals()
                messagebox.showerror('คำนวณไม่ได้', str(exc), parent=self)
            return
        self._invalidate_proposals()
        token = object()
        self._proposal_calculation_token = token
        self.plan_status_var.set('กำลังคำนวณทางเลือก…')
        def work():
            try:
                plans = compare(context)
                self.after(0, lambda: finish(plans, None))
            except Exception as exc:
                self.after(0, lambda error=exc: finish(None, error))
        def finish(plans, error):
            if self._proposal_calculation_token is not token:
                return
            try:
                if signature(self._proposal_context()) != signature(context):
                    self.plan_status_var.set('ข้อมูลเปลี่ยนระหว่างคำนวณ กรุณาคำนวณใหม่')
                    return
            except (ValueError, OSError):
                return
            if error:
                self.plan_status_var.set('คำนวณไม่สำเร็จ')
                messagebox.showerror('คำนวณไม่ได้', str(error), parent=self)
                return
            self._show_proposals(context, plans)
        threading.Thread(target=work, daemon=True).start()

    def _show_proposals(self, context, plans):
        self._proposal_context_used = context
        self._proposals = plans
        self.plan_end_date_var.set((date.fromisoformat(context['start']) + timedelta(days=int(context['settings']['lookahead'])-1)).isoformat())
        self._select_proposal(0)
        self._refresh_summary_table()

    def _select_proposal(self, index):
        self._proposal_selected = index
        for child in self._proposal_cards.winfo_children():
            child.destroy()
        context = self._proposal_context_used
        for i, plan in enumerate(self._proposals):
            self._proposal_cards.columnconfigure(i, weight=1, uniform='proposal')
            box = tk.Frame(self._proposal_cards, bg='white', highlightthickness=2,
                           highlightbackground='#168078' if i == index else '#d8dce2', padx=8, pady=8)
            box.grid(row=0, column=i, sticky='nsew', padx=3)
            for title, font in [(plan['title'], ('Segoe UI', 10, 'bold')), (STATUS[plan['status']], ('Segoe UI', 9)),
                                (fmt(plan['remaining'])+' kg', ('Segoe UI', 19, 'bold')),
                                ('ต้นทุน ฿ '+fmt(plan['cost']), ('Segoe UI', 10, 'bold')),
                                (f"เปลี่ยน SKU {plan['changes']} ครั้ง • ย้าย {plan['moved']} งาน", ('Segoe UI', 9))]:
                tk.Label(box, text=title, bg='white', anchor='w', font=font).pack(fill='x', pady=2)
            ttk.Button(box, text='กำลังดูแผนนี้' if i == index else 'ดูรายละเอียด',
                       command=lambda n=i: self._select_proposal(n)).pack(fill='x', pady=(6, 0))
        p = self._proposals[index]
        delta = None if p['cost'] is None else self._proposals[0]['cost'] - p['cost']
        self._proposal_detail.set(f"วันนี้ RM เหลือ {fmt(p['daily'][0]['remaining'])} kg | ค่า Freeze สิ้นช่วง ฿ {fmt(p['freeze_cost'])} | "
            f"ค่าเปลี่ยนงาน ฿ {fmt(p['setup_cost'])} | ประหยัดเทียบฐาน ฿ {fmt(delta)} | งานเลยกำหนดส่ง {p['late']} งาน")
        jobs = {j['id']: j for j in context['jobs']}
        self._proposal_row_ids = {}
        tree = self._proposal_tables['jobs']
        tree.delete(*tree.get_children())
        for n, r in enumerate(sorted(p['rows'], key=lambda r: (r['day'], r['job']))):
            j = jobs[r['job']]
            self._proposal_row_ids[str(n)] = j['id']
            tree.insert('', 'end', iid=str(n), values=(j['order'], j['day'], r['day'], j['line'], j['size'],
                        fmt(r['qty']), READY[j['status']], 'ล็อก' if j['locked'] else 'ปรับได้'))
        self.plan_status_var.set(f"{p['title']} • {len(context['jobs'])} งาน • {context['start']} ถึง {self.plan_end_date_var.get()} • ข้อมูล ณ รอบคำนวณล่าสุด ยังไม่ยืนยัน")
        self._render_plan_timeline()

    def _render_plan_timeline(self):
        """Draw the selected plan in production-day time (12:00 to 08:00)."""
        if not hasattr(self, '_proposal_timeline_canvas'):
            return
        canvas = self._proposal_timeline_canvas
        canvas.delete('all')
        if not self._proposals:
            canvas.configure(scrollregion=(0, 0, max(canvas.winfo_width(), 1), max(canvas.winfo_height(), 1)))
            return
        plan = self._proposals[self._proposal_selected]
        jobs = {job['id']: job for job in self._proposal_context_used['jobs']}
        hours = tuple(range(12, 24)) + tuple(range(0, 9))
        label_width, hour_width, row_height, left = 140, 70, 58, 140
        timeline_hours = len(hours) - 1  # 12:00 through 08:00 next morning = 20 hours.
        width = left + timeline_hours * hour_width + 20
        entries_by_day = {}
        for entry in plan['schedule']:
            entries_by_day.setdefault(entry['day'], {}).setdefault(entry['line'], []).append(entry)
        colours = {'M': '#4f83cc', 'S': '#2f9d8f', 'SS': '#8268bd'}
        y = 12
        for day in sorted(entries_by_day):
            canvas.create_text(12, y + 14, text=day, anchor='w', fill='#31465a', font=('Segoe UI', 10, 'bold'))
            for offset, hour in enumerate(hours):
                x = left + offset * hour_width
                canvas.create_text(x + hour_width / 2, y + 14, text=f'{hour:02d}:00', fill='#557188', font=('Segoe UI', 9))
                canvas.create_line(x, y + 28, x, y + 28 + row_height * 2, fill='#d9e3eb', dash=(2, 3))
            y += 30
            for line, start_hour, thai_label in (('COOKED', 18, 'เกี๊ยวสุก'), ('RAW', 19, 'เกี๊ยวดิบ')):
                canvas.create_rectangle(left, y, left + timeline_hours * hour_width, y + row_height - 8,
                                        fill='#f2f6fa', outline='')
                canvas.create_text(12, y + 13, text=line, anchor='w', fill='#18324a', font=('Segoe UI', 10, 'bold'))
                canvas.create_text(12, y + 31, text=thai_label, anchor='w', fill='#6b7d8d', font=('Segoe UI', 8))
                for entry in entries_by_day[day].get(line, []):
                    job = jobs[entry['job']]
                    capacity = self._proposal_context_used['capacity'][line]
                    cup_quantity = entry['qty'] / job['qty'] * job['cups'] if job['qty'] else 0
                    duration = cup_quantity / capacity * self._proposal_context_used['settings']['shift_hours'] if capacity else 0
                    start_offset = (start_hour - 12) + entry['start_hours']
                    x1 = left + start_offset * hour_width
                    x2 = min(left + timeline_hours * hour_width, x1 + max(duration * hour_width, 3))
                    colour = colours.get(job['size'], '#98a6b3')
                    canvas.create_rectangle(x1, y + 4, x2, y + row_height - 12, fill=colour, outline='')
                    if x2 - x1 > 65:
                        canvas.create_text(x1 + 6, y + 17, text=job['order'], anchor='w', fill='white', font=('Segoe UI', 9, 'bold'))
                    if x2 - x1 > 115:
                        canvas.create_text(x1 + 6, y + 34, text=job['size'], anchor='w', fill='white', font=('Segoe UI', 8))
                y += row_height
            y += 14
        canvas.configure(scrollregion=(0, 0, width, max(y, canvas.winfo_height())))

    def _proposal_history(self):
        folder = PROJECT_ROOT / 'Data' / 'Planning' / 'approved'
        files = sorted(folder.glob('*.json'), reverse=True)
        if not files:
            messagebox.showinfo('แผนที่ยืนยัน', 'ยังไม่มีแผนที่ยืนยัน', parent=self)
            return
        dialog = tk.Toplevel(self)
        dialog.title('แผนที่ยืนยันแล้ว — ข้อมูล ณ วันที่ยืนยัน')
        dialog.geometry('1000x550')
        dialog.transient(self)
        selected = tk.StringVar(value=files[0].name)
        picker = ttk.Combobox(dialog, textvariable=selected, values=[p.name for p in files], state='readonly', width=65)
        picker.pack(fill='x', padx=10, pady=10)
        title = tk.StringVar()
        ttk.Label(dialog, textvariable=title, wraplength=950).pack(fill='x', padx=10, pady=5)
        frame = ttk.Frame(dialog)
        frame.pack(fill='both', expand=True, padx=10, pady=10)
        columns = ('Order', 'วันผลิต', 'ไลน์', 'RM', 'จำนวนเกี๊ยว')
        tree = ttk.Treeview(frame, columns=columns, show='headings')
        for column in columns:
            tree.heading(column, text=column)
            tree.column(column, width=170)
        tree.pack(side='left', fill='both', expand=True)
        scrollbar = ttk.Scrollbar(frame, command=tree.yview)
        scrollbar.pack(side='right', fill='y')
        tree.configure(yscrollcommand=scrollbar.set)
        paths = {p.name: p for p in files}
        def load(_=None):
            try:
                data = json.loads(paths[selected.get()].read_text(encoding='utf-8'))
                p = data['plan']
                jobs = {j['id']: j for j in data['context']['jobs']}
                tree.delete(*tree.get_children())
                for r in sorted(p['rows'], key=lambda r: (r['day'], r['job'])):
                    j = jobs[r['job']]
                    tree.insert('', 'end', values=(j['order'], r['day'], j['line'], j['size'], fmt(r['qty'])))
                title.set(f"{p['title']} | ผู้ยืนยัน {data['reviewer']} | {data['approved_at']} | RM เหลือ {fmt(p['remaining'])} kg | ต้นทุน ฿ {fmt(p['cost'])}")
            except (ValueError, OSError, KeyError, TypeError) as exc:
                messagebox.showerror('เปิดไม่ได้', str(exc), parent=dialog)
        picker.bind('<<ComboboxSelected>>', load)
        load()

    def _plan_form(self, title, fields):
        dialog = tk.Toplevel(self)
        dialog.title(title)
        dialog.transient(self)
        variables = {}
        for row, (key, label, value) in enumerate(fields):
            ttk.Label(dialog, text=label).grid(row=row, column=0, sticky='w', padx=12, pady=7)
            variables[key] = tk.StringVar(value='' if value is None else str(value))
            ttk.Entry(dialog, textvariable=variables[key], width=28).grid(row=row, column=1, padx=12)
        return dialog, variables

    def _proposal_settings_dialog(self):
        labels = [('shift_hours', 'ชั่วโมงต่อกะ (แปลง capacity เป็นเวลา)'), ('setup_minutes', 'เปลี่ยน SKU นาที/ครั้ง'),
                  ('stop_cost', 'หยุดไลน์ บาท/ชม. (ว่าง = ไม่ทราบ)'), ('freeze_cost', 'Freeze บาท/kg (ว่าง = ไม่ทราบ)'),
                  ('freeze_percent', 'RM เหลือเข้า Freeze สิ้นช่วง % (ว่าง = ไม่ทราบ)')]
        dialog, variables = self._plan_form('ต้นทุน / สมมติฐาน', [(k, t, self._proposal_vars[k].get()) for k, t in labels])
        def save():
            original = {k: self._proposal_vars[k].get() for k in variables}
            try:
                for k, v in variables.items(): self._proposal_vars[k].set(v.get())
                context = self._proposal_context()
                if self._proposal_load_error: raise ValueError(self._proposal_load_error)
                data = dict(self._proposal_preferences, settings=context['settings'])
                save_preferences(self._proposal_path, data)
                self._proposal_preferences = data
            except (ValueError, OSError) as exc:
                for k, v in original.items(): self._proposal_vars[k].set(v)
                messagebox.showerror('บันทึกไม่ได้', str(exc), parent=dialog)
                return
            dialog.destroy()
        ttk.Button(dialog, text='บันทึก', command=save).grid(row=len(labels), column=1, pady=12)

    def _proposal_job_dialog(self):
        tree = self._proposal_tables['jobs']
        if not self._proposals or not tree.selection():
            messagebox.showinfo('เลือก Order', 'คำนวณแล้วเลือกงานในตารางก่อน', parent=self)
            return
        jid = self._proposal_row_ids[tree.selection()[0]]
        job = next(j for j in self._proposal_context_used['jobs'] if j['id'] == jid)
        profile = self._proposal_preferences['profiles'].get(jid, {})
        fields = [('earliest', 'ผลิตเร็วที่สุด YYYY-MM-DD'), ('date', 'พร้อมเพิ่มวันที่ YYYY-MM-DD'),
                  ('max_qty', 'พร้อมเพิ่มสูงสุด (จำนวนเกี๊ยว)'), ('reviewer', 'ผู้ตรวจความพร้อม'),
                  ('egg', 'กลุ่มไข่ (กลุ่มเดียวกันผลิตร่วมได้)'), ('soup_rank', 'ลำดับซุป 0=ใส ค่าน้อยผลิตก่อน')]
        dialog, variables = self._plan_form('ตรวจ '+job['order'], [(k, t, profile.get(k, '')) for k, t in fields])
        status = tk.StringVar(value=READY[profile.get('status', 'unknown')])
        ttk.Combobox(dialog, textvariable=status, values=list(READY.values()), state='readonly').grid(row=6, column=1, pady=8)
        locked = tk.BooleanVar(value=profile.get('locked', False))
        ttk.Checkbutton(dialog, text='ล็อกวันและจำนวน / งานเริ่มผลิตแล้ว', variable=locked).grid(row=7, column=0, columnspan=2, pady=8)
        def save():
            p = {k: v.get().strip() for k, v in variables.items()}
            p.update(locked=locked.get(), status=next(k for k, v in READY.items() if v == status.get()))
            try:
                p['max_qty'] = number(p['max_qty'] or 0, 'จำนวน')
                p['soup_rank'] = number(p['soup_rank'], 'ลำดับซุป', optional=True)
                for k in ('earliest', 'date'):
                    if p[k]: date.fromisoformat(p[k])
                if p['status'] in ('ready', 'partial') and (not p['date'] or not p['reviewer']):
                    raise ValueError('สถานะพร้อมต้องมีวันที่และผู้ตรวจ')
                if self._proposal_load_error: raise ValueError(self._proposal_load_error)
                data = dict(self._proposal_preferences, profiles={**self._proposal_preferences['profiles'], jid: p})
                save_preferences(self._proposal_path, data)
                self._proposal_preferences = data
            except (ValueError, OSError) as exc:
                messagebox.showerror('บันทึกไม่ได้', str(exc), parent=dialog)
                return
            dialog.destroy()
            self._calculate_proposals()
        ttk.Button(dialog, text='บันทึกแล้วคำนวณใหม่', command=save).grid(row=8, column=1, pady=12)

    def _approve_proposal(self):
        if not self._proposals:
            messagebox.showinfo('คำนวณก่อน', 'กรุณาคำนวณทางเลือกใหม่', parent=self)
            return
        plan = self._proposals[self._proposal_selected]
        try:
            current = self._proposal_context()
            if signature(current) != plan['signature']:
                raise ValueError('ข้อมูลเปลี่ยนแล้ว กรุณาคำนวณและตรวจใหม่')
            if plan['errors'] or plan['pending']:
                raise ValueError('ยังมีข้อจำกัดหรือข้อมูลที่ต้องตรวจในสถานะแผนก่อนยืนยัน')
        except (ValueError, OSError) as exc:
            messagebox.showwarning('ยังยืนยันไม่ได้', str(exc), parent=self)
            return
        dialog = tk.Toplevel(self)
        dialog.title('ยืนยัน '+plan['title'])
        dialog.transient(self)
        checks = []
        for text in ('ตรวจ Stock เป็นยอดคงเหลือจริงหลังเบิกแล้ว', 'ตรวจ ingredient / packaging ร่วมทั้งชุด วันที่และจำนวนครบแล้ว',
                     'ตรวจงานเริ่มแล้ว งานล็อก งานที่ไม่เข้าฐาน และผลต่อวันถัดไปแล้ว'):
            v = tk.BooleanVar(value=False)
            checks.append(v)
            ttk.Checkbutton(dialog, text=text, variable=v).pack(anchor='w', padx=15, pady=8)
        name = tk.StringVar()
        ttk.Label(dialog, text='ผู้ยืนยัน').pack(anchor='w', padx=15)
        ttk.Entry(dialog, textvariable=name).pack(fill='x', padx=15, pady=8)
        def accept():
            try:
                if not all(v.get() for v in checks) or not name.get().strip():
                    raise ValueError('กรุณาตรวจทั้งชุดและระบุผู้ยืนยัน')
                if signature(self._proposal_context()) != plan['signature']:
                    raise ValueError('ข้อมูลเปลี่ยนหลังเปิดหน้าตรวจ กรุณาคำนวณใหม่')
                destination = PROJECT_ROOT / 'Data' / 'Planning' / 'approved' / (datetime.now().strftime('%Y%m%d_%H%M%S')+'_'+uuid4().hex[:8]+'.json')
                save_approval(destination, dict(approved_at=datetime.now().isoformat(), reviewer=name.get().strip(),
                              plan=plan, context=current, stock_checked=True, shared_materials_checked=True))
            except (ValueError, OSError) as exc:
                messagebox.showerror('ยืนยันไม่ได้', str(exc), parent=dialog)
                return
            dialog.destroy()
            self.plan_status_var.set('ยืนยันแล้ว: '+plan['title']+' • บันทึก '+destination.name)
            messagebox.showinfo('บันทึกแผนแล้ว', 'เก็บแผนและข้อมูลประกอบไว้ที่\n'+str(destination)+'\nยังไม่ได้เบิก Stock หรือแก้ Order ต้นฉบับ', parent=self)
        ttk.Button(dialog, text='ยืนยันและบันทึกแผน', command=accept).pack(pady=12)
