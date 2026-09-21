"""CapacityViewMixin behavior."""

from __future__ import annotations

from .common import *  # shared UI types and domain services
from rm_planner.planning.alternatives import number
from rm_planner.planning.proposal_store import save_preferences


class CapacityViewMixin:
    def _build_capacity_tab(self) -> None:
        self.work_hours_per_day_var = tk.StringVar(value="8")
        self.raw_cups_per_hour_var = tk.StringVar()
        self.cooked_cups_per_hour_var = tk.StringVar()
        self.cooked_noodle_cups_per_hour_var = tk.StringVar()
        self.raw_wonton_daily_var = tk.StringVar(value="—")
        self.cooked_wonton_daily_var = tk.StringVar(value="—")
        self.cooked_wonton_noodle_daily_var = tk.StringVar(value="—")
        self.chill_days_var = tk.StringVar(value="0")
        self.chill_days_status_var = tk.StringVar(value="Chill-days setting has not been saved yet.")
        self.production_cooked_start_var = tk.StringVar(value="18:00")
        self.production_raw_start_var = tk.StringVar(value="19:00")
        self.production_start_status_var = tk.StringVar(
            value="Production start times have not been saved yet."
        )
        self.raw_labour_var = tk.StringVar(value="0")
        self.raw_wage_var = tk.StringVar(value="0")
        self.cooked_labour_var = tk.StringVar(value="0")
        self.cooked_wage_var = tk.StringVar(value="0")
        self.labour_status_var = tk.StringVar(value="Labour settings have not been saved yet.")

        page = ttk.Frame(self.capacity_tab, padding=18)
        page.pack(fill=tk.BOTH, expand=True)
        page.columnconfigure(1, weight=1)
        page.rowconfigure(0, weight=1)

        sidebar = tk.Frame(page, bg="#f5f7fa", width=210, padx=14, pady=16)
        sidebar.grid(row=0, column=0, sticky="nsw", padx=(0, 18))
        sidebar.grid_propagate(False)
        tk.Label(sidebar, text="Operations", bg="#f5f7fa", fg="#1f2937",
                 font=("Segoe UI", 13, "bold")).pack(anchor=tk.W)
        tk.Label(sidebar, text="Settings categories", bg="#f5f7fa", fg="#64748b",
                 font=("Segoe UI", 9)).pack(anchor=tk.W, pady=(2, 16))
        self.operations_capacity_button = tk.Button(
            sidebar,
            text="Capacity",
            anchor=tk.W,
            relief=tk.FLAT,
            borderwidth=0,
            padx=12,
            pady=10,
            bg="#dceeff",
            activebackground="#dceeff",
            fg="#24567b",
            activeforeground="#24567b",
            font=("Segoe UI", 10, "bold"),
        )
        self.operations_capacity_button.pack(fill=tk.X)

        content_host = ttk.Frame(page)
        content_host.grid(row=0, column=1, sticky="nsew")
        content_host.columnconfigure(0, weight=1)
        content_host.rowconfigure(0, weight=1)
        capacity_content = ttk.Frame(content_host)
        capacity_content.grid(row=0, column=0, sticky="nsew")
        ttk.Label(capacity_content, text="Capacity", font=("Segoe UI", 16, "bold")).pack(anchor=tk.W)
        ttk.Label(capacity_content, text="ตั้งค่ากำลังผลิตต่อชั่วโมงและชั่วโมงทำงานของโรงงาน").pack(
            anchor=tk.W, pady=(3, 18))

        hours_card = ttk.LabelFrame(capacity_content, text="เวลาทำงาน", padding=14)
        hours_card.pack(fill=tk.X)
        ttk.Label(hours_card, text="Working hours per day", font=("Segoe UI", 10, "bold")).pack(anchor=tk.W)
        hours_entry = ttk.Entry(hours_card, textvariable=self.work_hours_per_day_var, width=12,
                                font=("Segoe UI", 14))
        hours_entry.pack(anchor=tk.W, pady=(6, 3))
        ttk.Label(hours_card, text="ชั่วโมง/วัน  •  ใช้คูณกับกำลังผลิตเกี๊ยวต่อชั่วโมงของทุกประเภท").pack(anchor=tk.W)

        inputs = ttk.LabelFrame(capacity_content, text="Production capacity (ลูกเกี๊ยว / ชั่วโมง)", padding=14)
        inputs.pack(fill=tk.X, pady=(14, 0))
        for column in range(3):
            inputs.columnconfigure(column, weight=1)
        for column, (label, variable) in enumerate((
            ("Raw wonton", self.raw_cups_per_hour_var),
            ("Cooked wonton", self.cooked_cups_per_hour_var),
            ("Cooked wonton + noodle", self.cooked_noodle_cups_per_hour_var),
        )):
            field = ttk.Frame(inputs, padding=(0 if column == 0 else 8, 0, 8 if column < 2 else 0, 0))
            field.grid(row=0, column=column, sticky="ew")
            field.columnconfigure(0, weight=1)
            ttk.Label(field, text=label, font=("Segoe UI", 10, "bold")).grid(row=0, column=0, sticky=tk.W)
            entry = ttk.Entry(field, textvariable=variable, font=("Segoe UI", 14))
            entry.grid(row=1, column=0, sticky="ew", pady=(6, 0))
            ttk.Label(field, text="ลูกเกี๊ยว / ชั่วโมง").grid(row=2, column=0, sticky=tk.W, pady=(3, 0))
            entry.bind("<KeyRelease>", lambda _event: self._update_capacity_preview())
        hours_entry.bind("<KeyRelease>", lambda _event: self._update_capacity_preview())

        summary = ttk.LabelFrame(capacity_content, text="Calculated capacity per day", padding=14)
        summary.pack(fill=tk.X, pady=(14, 0))
        for column in range(3):
            summary.columnconfigure(column, weight=1)
        for column, (label, variable) in enumerate((
            ("Raw wonton", self.raw_wonton_daily_var),
            ("Cooked wonton", self.cooked_wonton_daily_var),
            ("Cooked wonton + noodle", self.cooked_wonton_noodle_daily_var),
        )):
            card = tk.Frame(summary, bg="#edf6fb", padx=14, pady=12)
            card.grid(row=0, column=column, sticky="ew", padx=(0 if column == 0 else 8, 8 if column < 2 else 0))
            tk.Label(card, text=label, bg="#edf6fb", anchor="w", font=("Segoe UI", 10, "bold")).pack(fill=tk.X)
            tk.Label(card, textvariable=variable, bg="#edf6fb", anchor="w", font=("Segoe UI", 17, "bold")).pack(
                fill=tk.X, pady=(5, 0))
            tk.Label(card, text="ลูกเกี๊ยว / วัน", bg="#edf6fb", anchor="w").pack(fill=tk.X)

        action_frame = ttk.Frame(capacity_content)
        action_frame.pack(fill=tk.X, pady=(18, 0))
        ttk.Button(
            action_frame,
            text="Save operations settings",
            command=self._save_all_capacity_settings,
        ).pack(anchor=tk.E)

        ttk.Label(
            capacity_content,
            textvariable=self.capacity_status_var,
            relief=tk.SUNKEN,
            anchor=tk.W,
            padding=(6, 3),
        ).pack(fill=tk.X, pady=(14, 0))

        self.operation_order_rule_tab = ttk.Frame(content_host)
        ttk.Label(
            self.operation_order_rule_tab,
            text="Operation order rule",
            font=("Segoe UI", 16, "bold"),
        ).pack(anchor=tk.W)
        ttk.Label(
            self.operation_order_rule_tab,
            text="กำหนดกฎและลำดับการเปลี่ยนงานของแต่ละไลน์ผลิต",
        ).pack(anchor=tk.W, pady=(3, 18))
        self._build_changeover_cost_settings()
        self._build_operation_rule_builder()

        self.chill_days_tab = ttk.Frame(content_host)
        self._build_chill_days_settings()

        self.production_start_tab = ttk.Frame(content_host)
        self._build_production_start_settings()

        self.labour_tab = ttk.Frame(content_host)
        self._build_labour_settings()

        self.master_tab = ttk.Frame(content_host)
        self._build_master_tab()

        self.class_define_tab = ttk.Frame(content_host)
        self._operations_sections = {
            "capacity": capacity_content,
            "chill_days": self.chill_days_tab,
            "production_start": self.production_start_tab,
            "labour": self.labour_tab,
            "master": self.master_tab,
            "operation_order_rule": self.operation_order_rule_tab,
            "class_define": self.class_define_tab,
        }
        self._operations_section_buttons = {
            "capacity": self.operations_capacity_button,
            "chill_days": tk.Button(
                sidebar,
                text="Chill days",
                anchor=tk.W,
                relief=tk.FLAT,
                borderwidth=0,
                padx=12,
                pady=10,
                bg="#f5f7fa",
                activebackground="#e7edf5",
                fg="#475569",
                activeforeground="#24567b",
                font=("Segoe UI", 10),
                command=lambda: self._select_operations_section("chill_days"),
            ),
            "production_start": tk.Button(
                sidebar,
                text="เวลาเริ่มผลิต",
                anchor=tk.W,
                relief=tk.FLAT,
                borderwidth=0,
                padx=12,
                pady=10,
                bg="#f5f7fa",
                activebackground="#e7edf5",
                fg="#475569",
                activeforeground="#24567b",
                font=("Segoe UI", 10),
                command=lambda: self._select_operations_section("production_start"),
            ),
            "labour": tk.Button(
                sidebar,
                text="Labour",
                anchor=tk.W,
                relief=tk.FLAT,
                borderwidth=0,
                padx=12,
                pady=10,
                bg="#f5f7fa",
                activebackground="#e7edf5",
                fg="#475569",
                activeforeground="#24567b",
                font=("Segoe UI", 10),
                command=lambda: self._select_operations_section("labour"),
            ),
            "master": tk.Button(
                sidebar,
                text="Master",
                anchor=tk.W,
                relief=tk.FLAT,
                borderwidth=0,
                padx=12,
                pady=10,
                bg="#f5f7fa",
                activebackground="#e7edf5",
                fg="#475569",
                activeforeground="#24567b",
                font=("Segoe UI", 10),
                command=lambda: self._select_operations_section("master"),
            ),
            "operation_order_rule": tk.Button(
                sidebar,
                text="Operation order rule",
                anchor=tk.W,
                relief=tk.FLAT,
                borderwidth=0,
                padx=12,
                pady=10,
                bg="#f5f7fa",
                activebackground="#e7edf5",
                fg="#475569",
                activeforeground="#24567b",
                font=("Segoe UI", 10),
                command=lambda: self._select_operations_section("operation_order_rule"),
            ),
            "class_define": tk.Button(
                sidebar,
                text="Class Define",
                anchor=tk.W,
                relief=tk.FLAT,
                borderwidth=0,
                padx=12,
                pady=10,
                bg="#f5f7fa",
                activebackground="#e7edf5",
                fg="#475569",
                activeforeground="#24567b",
                font=("Segoe UI", 10),
                command=lambda: self._select_operations_section("class_define"),
            ),
        }
        self.operations_capacity_button.configure(command=lambda: self._select_operations_section("capacity"))
        self._operations_section_buttons["chill_days"].pack(fill=tk.X, pady=(4, 0))
        self._operations_section_buttons["production_start"].pack(fill=tk.X, pady=(4, 0))
        self._operations_section_buttons["labour"].pack(fill=tk.X, pady=(4, 0))
        self._operations_section_buttons["master"].pack(fill=tk.X, pady=(4, 0))
        self._operations_section_buttons["operation_order_rule"].pack(fill=tk.X, pady=(4, 0))
        self._operations_section_buttons["class_define"].pack(fill=tk.X, pady=(4, 0))
        self._build_class_define_tab()
        self._select_operations_section("capacity")

    def _build_changeover_cost_settings(self) -> None:
        card = ttk.LabelFrame(self.operation_order_rule_tab, text="ค่าเปลี่ยนงาน", padding=12)
        card.pack(fill=tk.X, pady=(0, 14))
        self.changeover_cost_vars = {
            key: tk.StringVar(value=self._proposal_vars[key].get())
            for key in ('stop_cost', 'setup_minutes')
        }
        for column, (key, label) in enumerate((
            ('stop_cost', 'อัตราค่าเปลี่ยนงาน (บาท/ชั่วโมง)'),
            ('setup_minutes', 'เวลาเปลี่ยนงาน (นาที/ครั้ง)'),
        )):
            ttk.Label(card, text=label).grid(row=0, column=column, sticky=tk.W, padx=(0, 16))
            ttk.Entry(card, textvariable=self.changeover_cost_vars[key], width=24).grid(
                row=1, column=column, sticky=tk.W, padx=(0, 16), pady=6)
            # Keep this editor in sync when the same setting is saved from Plan.
            self._proposal_vars[key].trace_add(
                'write', lambda *_args, k=key:
                    self.changeover_cost_vars[k].set(self._proposal_vars[k].get()))
        ttk.Label(
            card,
            text="ค่าเปลี่ยนงานรายวัน = จำนวนครั้ง × นาทีต่อครั้ง ÷ 60 × บาทต่อชั่วโมง",
        ).grid(row=2, column=0, columnspan=3, sticky=tk.W)
        self.changeover_cost_status = tk.StringVar()
        ttk.Label(card, textvariable=self.changeover_cost_status).grid(
            row=3, column=0, columnspan=3, sticky=tk.W, pady=(6, 0))
        ttk.Button(card, text="บันทึกค่าเปลี่ยนงาน", command=self._save_changeover_cost_settings).grid(
            row=1, column=2, padx=8)

    def _save_changeover_cost_settings(self) -> None:
        try:
            values = {
                key: number(var.get().strip().replace(',', ''), key, optional=key == 'stop_cost')
                for key, var in self.changeover_cost_vars.items()
            }
            if values['setup_minutes'] > float(self.capacity_settings.work_hours_per_day) * 60:
                raise ValueError("เวลาเปลี่ยนงานต้องไม่เกินชั่วโมงทำงานต่อวัน")
            if self._proposal_load_error:
                raise ValueError(self._proposal_load_error)
            settings = dict(self._proposal_preferences['settings'], **values)
            data = dict(self._proposal_preferences, settings=settings)
            save_preferences(self._proposal_path, data)
        except (ValueError, OSError) as exc:
            messagebox.showerror("บันทึกค่าเปลี่ยนงาน", str(exc), parent=self)
            return
        self._proposal_preferences = data
        for key, value in values.items():
            self._proposal_vars[key].set('' if value is None else str(value))
        self.changeover_cost_status.set("บันทึกแล้ว — กำลังคำนวณต้นทุนแผนใหม่")

    def _build_chill_days_settings(self) -> None:
        """Build the future planning constraint for chilled RM usage."""

        ttk.Label(self.chill_days_tab, text="Chill days", font=("Segoe UI", 16, "bold")).pack(anchor=tk.W)
        ttk.Label(
            self.chill_days_tab,
            text="กำหนดจำนวนวันที่ใช้ RM แบบแช่เย็นได้ ก่อนต้อง Freeze เป็น Stock",
        ).pack(anchor=tk.W, pady=(3, 18))

        setting_card = ttk.LabelFrame(self.chill_days_tab, text="Chilled RM window", padding=14)
        setting_card.pack(fill=tk.X)
        ttk.Label(setting_card, text="Usable days before freezing", font=("Segoe UI", 10, "bold")).pack(anchor=tk.W)
        entry = ttk.Entry(setting_card, textvariable=self.chill_days_var, width=12, font=("Segoe UI", 14))
        entry.pack(anchor=tk.W, pady=(6, 3))
        ttk.Label(
            setting_card,
            text="วัน • ต้องเป็นจำนวนเต็มตั้งแต่ 0 ขึ้นไป; ระบบจะนำค่านี้ไปใช้กับ Timeline ในขั้นถัดไป",
        ).pack(anchor=tk.W)

        actions = ttk.Frame(self.chill_days_tab)
        actions.pack(fill=tk.X, pady=(18, 0))
        ttk.Button(actions, text="Save chill days", command=self._save_chill_days_settings).pack(anchor=tk.E)
        ttk.Label(
            self.chill_days_tab,
            textvariable=self.chill_days_status_var,
            relief=tk.SUNKEN,
            anchor=tk.W,
            padding=(6, 3),
        ).pack(fill=tk.X, pady=(14, 0))

    def _build_production_start_settings(self) -> None:
        """Build the daily start-time controls used by the production timeline."""

        ttk.Label(
            self.production_start_tab,
            text="เวลาเริ่มผลิต",
            font=("Segoe UI", 16, "bold"),
        ).pack(anchor=tk.W)
        ttk.Label(
            self.production_start_tab,
            text="กำหนดเวลาเริ่มงานของแต่ละไลน์ใน Production Timeline",
        ).pack(anchor=tk.W, pady=(3, 18))

        setting_card = ttk.LabelFrame(
            self.production_start_tab,
            text="Production line start time",
            padding=14,
        )
        setting_card.pack(fill=tk.X)
        for column in range(2):
            setting_card.columnconfigure(column, weight=1)
        for column, (label, variable) in enumerate((
            ("Cooked wonton", self.production_cooked_start_var),
            ("Raw wonton", self.production_raw_start_var),
        )):
            field = ttk.Frame(setting_card)
            field.grid(
                row=0,
                column=column,
                sticky="ew",
                padx=(0 if column == 0 else 10, 10 if column == 0 else 0),
            )
            ttk.Label(field, text=label, font=("Segoe UI", 10, "bold")).pack(anchor=tk.W)
            ttk.Combobox(
                field,
                textvariable=variable,
                values=production_time_options(),
                state="readonly",
                width=12,
                font=("Segoe UI", 13),
            ).pack(anchor=tk.W, pady=(6, 3))
            ttk.Label(field, text="เวลาเริ่มผลิตของวันนั้น").pack(anchor=tk.W)
        ttk.Label(
            setting_card,
            text="เลือกได้เฉพาะช่วง 16:00 ถึง 04:00 ตาม Timeframe ของ Timeline",
        ).grid(row=1, column=0, columnspan=2, sticky=tk.W, pady=(14, 0))

        actions = ttk.Frame(self.production_start_tab)
        actions.pack(fill=tk.X, pady=(18, 0))
        ttk.Button(
            actions,
            text="Save production start times",
            command=self._save_production_start_settings,
        ).pack(anchor=tk.E)
        ttk.Label(
            self.production_start_tab,
            textvariable=self.production_start_status_var,
            relief=tk.SUNKEN,
            anchor=tk.W,
            padding=(6, 3),
        ).pack(fill=tk.X, pady=(14, 0))

    def _build_labour_settings(self) -> None:
        """Build the labour and wage inputs for the two production lines."""

        ttk.Label(
            self.labour_tab,
            text="Labour",
            font=("Segoe UI", 16, "bold"),
        ).pack(anchor=tk.W)
        ttk.Label(
            self.labour_tab,
            text="กำหนดจำนวนแรงงานและค่าแรงแยกตามไลน์ผลิต",
        ).pack(anchor=tk.W, pady=(3, 18))

        settings_card = ttk.LabelFrame(
            self.labour_tab,
            text="Labour by production line",
            padding=14,
        )
        settings_card.pack(fill=tk.X)
        for column in range(2):
            settings_card.columnconfigure(column, weight=1)

        for column, (label, labour_var, wage_var) in enumerate((
            ("Cooked wonton", self.cooked_labour_var, self.cooked_wage_var),
            ("Raw wonton", self.raw_labour_var, self.raw_wage_var),
        )):
            field = ttk.Frame(settings_card)
            field.grid(
                row=0,
                column=column,
                sticky="ew",
                padx=(0 if column == 0 else 10, 10 if column == 0 else 0),
            )
            field.columnconfigure(0, weight=1)
            ttk.Label(field, text=label, font=("Segoe UI", 11, "bold")).grid(
                row=0, column=0, sticky=tk.W
            )
            ttk.Label(field, text="Number of labour").grid(
                row=1, column=0, sticky=tk.W, pady=(12, 3)
            )
            ttk.Entry(field, textvariable=labour_var, font=("Segoe UI", 14)).grid(
                row=2, column=0, sticky="ew"
            )
            ttk.Label(field, text="คน").grid(row=3, column=0, sticky=tk.W, pady=(3, 0))
            ttk.Label(field, text="Wage").grid(
                row=4, column=0, sticky=tk.W, pady=(12, 3)
            )
            ttk.Entry(field, textvariable=wage_var, font=("Segoe UI", 14)).grid(
                row=5, column=0, sticky="ew"
            )
            ttk.Label(field, text="บาท").grid(row=6, column=0, sticky=tk.W, pady=(3, 0))

        actions = ttk.Frame(self.labour_tab)
        actions.pack(fill=tk.X, pady=(18, 0))
        ttk.Button(
            actions,
            text="Save labour settings",
            command=self._save_labour_settings,
        ).pack(anchor=tk.E)
        ttk.Label(
            self.labour_tab,
            textvariable=self.labour_status_var,
            relief=tk.SUNKEN,
            anchor=tk.W,
            padding=(6, 3),
        ).pack(fill=tk.X, pady=(14, 0))

    def _select_operations_section(self, section: str) -> None:
        """Show one Operations Settings category in the shared content area."""

        if section == "master" and not getattr(self, "_master_data_loaded", False):
            self._master_data_loaded = True
            self._load_saved_master_data()

        for name, frame in self._operations_sections.items():
            if name == section:
                frame.grid(row=0, column=0, sticky="nsew")
            else:
                frame.grid_remove()
            selected = name == section
            button = self._operations_section_buttons[name]
            button.configure(
                bg="#dceeff" if selected else "#f5f7fa",
                activebackground="#dceeff" if selected else "#e7edf5",
                fg="#24567b" if selected else "#475569",
                activeforeground="#24567b",
                font=("Segoe UI", 10, "bold") if selected else ("Segoe UI", 10),
            )

    def _build_operation_rule_builder(self) -> None:
        """Build a small game-like canvas for ordering Class/Group rules."""

        self.operation_rule_status_var = tk.StringVar(value="เพิ่ม Rule แล้ววางกล่องจาก Class Define")
        self.operation_rules: list[dict] = []
        self._operation_rule_selected: tuple[int, int] | None = None
        self._operation_rule_selected_row: int | None = None
        self._operation_rule_drag: dict | None = None
        try:
            self.operation_rules = load_operation_rules(self.operation_rule_file_path)
        except ValueError as exc:
            self.operation_rule_status_var.set(str(exc))

        toolbar = ttk.Frame(self.operation_order_rule_tab)
        toolbar.pack(fill=tk.X, pady=(0, 10))
        ttk.Button(toolbar, text="+ Add rule", command=self._add_operation_rule).pack(side=tk.LEFT)
        ttk.Button(toolbar, text="Remove selected box", command=self._remove_selected_operation_rule_node).pack(side=tk.LEFT, padx=8)
        ttk.Button(toolbar, text="Rename selected rule", command=self._rename_selected_operation_rule).pack(side=tk.LEFT)
        ttk.Button(toolbar, text="Remove selected rule", command=self._remove_selected_operation_rule).pack(side=tk.LEFT, padx=(8, 0))
        order_help = ttk.Label(toolbar, text="ⓘ Order help", foreground="#24567b", cursor="hand2")
        order_help.pack(side=tk.RIGHT)
        order_help.bind("<Enter>", self._show_operation_rule_order_tip)
        order_help.bind("<Leave>", self._hide_operation_rule_order_tip)

        board = ttk.LabelFrame(self.operation_order_rule_tab, text="Workflow board", padding=1)
        board.pack(fill=tk.BOTH, expand=True)
        board.columnconfigure(0, weight=1)
        board.rowconfigure(0, weight=1)
        self.operation_rule_canvas = tk.Canvas(board, bg="#fbfcfe", highlightthickness=0, height=440)
        self.operation_rule_canvas.grid(row=0, column=0, sticky="nsew")
        vertical = ttk.Scrollbar(board, orient=tk.VERTICAL, command=self.operation_rule_canvas.yview)
        vertical.grid(row=0, column=1, sticky="ns")
        horizontal = ttk.Scrollbar(board, orient=tk.HORIZONTAL, command=self.operation_rule_canvas.xview)
        horizontal.grid(row=1, column=0, sticky="ew")
        self.operation_rule_canvas.configure(xscrollcommand=horizontal.set, yscrollcommand=vertical.set)
        self.operation_rule_canvas.bind("<Configure>", lambda _event: self._render_operation_rule_canvas())
        ttk.Label(self.operation_order_rule_tab, textvariable=self.operation_rule_status_var,
                  relief=tk.SUNKEN, anchor=tk.W, padding=(6, 3)).pack(fill=tk.X, pady=(10, 0))
        self._render_operation_rule_canvas()

    def _show_operation_rule_order_tip(self, event) -> None:
        self._hide_operation_rule_order_tip()
        tip = tk.Toplevel(self)
        tip.overrideredirect(True)
        tip.attributes("-topmost", True)
        tk.Label(
            tip,
            text="Run order\n• Each Rule: left → right\n• Then: top → bottom\n• Drag RULE to move the whole row",
            justify=tk.LEFT,
            background="#18324a",
            foreground="white",
            font=("Segoe UI", 9),
            padx=9,
            pady=7,
        ).pack()
        tip.geometry(f"+{event.x_root + 12}+{event.y_root + 14}")
        self._operation_rule_order_tip = tip

    def _hide_operation_rule_order_tip(self, _event=None) -> None:
        tip = getattr(self, "_operation_rule_order_tip", None)
        if tip is not None and tip.winfo_exists():
            tip.destroy()
        self._operation_rule_order_tip = None

    def _save_operation_rules(self) -> bool:
        try:
            save_operation_rules(self.operation_rule_file_path, self.operation_rules)
        except OSError as exc:
            messagebox.showerror("Operation order rule", str(exc), parent=self)
            return False
        self.operation_rule_status_var.set(
            f"Saved {len(self.operation_rules):,} rule(s). Order runs left → right, then top → bottom."
        )
        # Proposed plans retain a calculation snapshot, so regenerate them
        # immediately after the workflow changes. The baseline is unaffected.
        if hasattr(self, "_proposal_tables"):
            self._invalidate_proposals()
            self.after_idle(self._render_baseline_preview)
            self.after_idle(lambda: self._calculate_proposals(quiet=True))
        return True

    def _add_operation_rule(self) -> None:
        self.operation_rules.append({"name": f"RULE {len(self.operation_rules) + 1}", "nodes": []})
        self._operation_rule_selected = None
        self._operation_rule_selected_row = len(self.operation_rules) - 1
        self._save_operation_rules()
        self._render_operation_rule_canvas()

    def _rename_selected_operation_rule(self) -> None:
        rule_index = self._operation_rule_selected_row
        if rule_index is None or not 0 <= rule_index < len(self.operation_rules):
            messagebox.showinfo("Operation order rule", "คลิกชื่อ Rule ที่ต้องการแก้ไขก่อน", parent=self)
            return
        rule = self.operation_rules[rule_index]
        current_name = rule.get("name") or f"RULE {rule_index + 1}"
        name = simpledialog.askstring("Rename rule", "Rule name:", initialvalue=current_name, parent=self)
        if name is None:
            return
        name = name.strip()
        if not name:
            messagebox.showwarning("Rename rule", "กรุณาระบุชื่อ Rule", parent=self)
            return
        rule["name"] = name
        self._save_operation_rules()
        self._render_operation_rule_canvas()

    def _remove_selected_operation_rule(self) -> None:
        rule_index = self._operation_rule_selected_row
        if rule_index is None or not 0 <= rule_index < len(self.operation_rules):
            messagebox.showinfo("Operation order rule", "คลิกชื่อ Rule ที่ต้องการลบก่อน", parent=self)
            return
        node_count = len(self.operation_rules[rule_index]["nodes"])
        if not messagebox.askyesno(
            "Remove rule",
            f"ลบ Rule {rule_index + 1} พร้อมกล่อง {node_count:,} กล่องใช่หรือไม่?",
            parent=self,
        ):
            return
        self.operation_rules.pop(rule_index)
        self._operation_rule_selected = None
        self._operation_rule_selected_row = None
        self._save_operation_rules()
        self._render_operation_rule_canvas()

    def _add_operation_rule_node(self, rule_index: int) -> None:
        if not self.operation_rules:
            messagebox.showinfo("Operation order rule", "เพิ่ม Rule ก่อน แล้วจึงเพิ่มกล่อง Class", parent=self)
            return
        classes = sorted({item.class_value.strip() for item in self.class_definitions.values() if item.class_value.strip()})
        if not classes:
            messagebox.showinfo("Operation order rule", "ยังไม่มีข้อมูล Class Define", parent=self)
            return
        dialog = tk.Toplevel(self)
        dialog.title("Add class box")
        dialog.transient(self)
        dialog.resizable(False, False)
        body = ttk.Frame(dialog, padding=16)
        body.pack(fill=tk.BOTH, expand=True)
        class_var = tk.StringVar(value=classes[0])
        group_var = tk.StringVar()
        ttk.Label(body, text=f"Add to Rule {rule_index + 1}", style="Summary.TLabel").grid(
            row=0, column=0, columnspan=2, sticky=tk.W, pady=(0, 12)
        )
        ttk.Label(body, text="Class").grid(row=1, column=0, sticky=tk.W, pady=(0, 7))
        class_picker = ttk.Combobox(body, textvariable=class_var, values=classes, width=30, state="readonly")
        class_picker.grid(row=1, column=1, sticky="ew", padx=(12, 0), pady=(0, 7))
        ttk.Label(body, text="Group").grid(row=2, column=0, sticky=tk.W)
        group_picker = ttk.Combobox(body, textvariable=group_var, width=30, state="readonly")
        group_picker.grid(row=2, column=1, sticky="ew", padx=(12, 0))
        body.columnconfigure(1, weight=1)

        def refresh_groups(_event=None) -> None:
            groups = sorted({item.group.strip() for item in self.class_definitions.values()
                             if item.class_value.strip() == class_var.get().strip() and item.group.strip()})
            group_picker.configure(values=groups)
            group_var.set(groups[0] if groups else "")

        class_picker.bind("<<ComboboxSelected>>", refresh_groups)
        refresh_groups()

        def add_box() -> None:
            if not group_var.get():
                messagebox.showwarning("Add class box", "Class นี้ยังไม่มี Group ให้เลือก", parent=dialog)
                return
            self.operation_rules[rule_index]["nodes"].append({
                "class": class_var.get().strip(), "group": group_var.get().strip(),
            })
            self._operation_rule_selected = (rule_index, len(self.operation_rules[rule_index]["nodes"]) - 1)
            dialog.destroy()
            self._save_operation_rules()
            self._render_operation_rule_canvas()

        actions = ttk.Frame(body)
        actions.grid(row=3, column=0, columnspan=2, sticky=tk.E, pady=(16, 0))
        ttk.Button(actions, text="Cancel", command=dialog.destroy).pack(side=tk.RIGHT)
        ttk.Button(actions, text="Add box", command=add_box).pack(side=tk.RIGHT, padx=(0, 8))
        dialog.grab_set()

    def _remove_selected_operation_rule_node(self) -> None:
        if self._operation_rule_selected is None:
            messagebox.showinfo("Operation order rule", "เลือกกล่องที่ต้องการลบก่อน", parent=self)
            return
        rule_index, node_index = self._operation_rule_selected
        try:
            self.operation_rules[rule_index]["nodes"].pop(node_index)
        except (IndexError, KeyError):
            self._operation_rule_selected = None
            return
        self._operation_rule_selected = None
        self._save_operation_rules()
        self._render_operation_rule_canvas()

    def _render_operation_rule_canvas(self) -> None:
        if not hasattr(self, "operation_rule_canvas"):
            return
        canvas = self.operation_rule_canvas
        canvas.delete("all")
        row_height, first_x, node_width, node_height, gap = 130, 155, 205, 72, 76
        max_nodes = max((len(rule["nodes"]) for rule in self.operation_rules), default=0)
        width = max(canvas.winfo_width(), first_x + max(1, max_nodes) * (node_width + gap) + 70)
        height = max(canvas.winfo_height(), 70 + max(2, len(self.operation_rules)) * row_height)
        for coordinate in range(0, width + 1, 48):
            canvas.create_line(coordinate, 0, coordinate, height, fill="#edf1f5")
        for coordinate in range(0, height + 1, 48):
            canvas.create_line(0, coordinate, width, coordinate, fill="#edf1f5")
        if not self.operation_rules:
            canvas.create_text(first_x, 92, text="Add a rule to start building the workflow",
                               anchor=tk.W, fill="#64748b", font=("Segoe UI", 11))
        for rule_index, rule in enumerate(self.operation_rules):
            y = 48 + rule_index * row_height
            rule_tag = f"operation-rule:{rule_index}"
            row_selected = self._operation_rule_selected_row == rule_index
            canvas.create_rectangle(8, y + 12, 132, y + node_height - 12,
                                    fill="#dceeff" if row_selected else "#f2f6fa",
                                    outline="#24567b" if row_selected else "", tags=(rule_tag,))
            rule_name = rule.get("name") or f"RULE {rule_index + 1}"
            canvas.create_text(18, y + node_height / 2, text=f"{rule_name}  ↕", anchor=tk.W,
                               fill="#1f2937", font=("Segoe UI", 13, "bold"), tags=(rule_tag,))
            canvas.tag_bind(rule_tag, "<ButtonPress-1>",
                            lambda event, r=rule_index: self._start_operation_rule_row_drag(event, r))
            canvas.tag_bind(rule_tag, "<B1-Motion>", self._move_operation_rule_row_drag)
            canvas.tag_bind(rule_tag, "<ButtonRelease-1>", self._finish_operation_rule_row_drag)
            canvas.tag_bind(rule_tag, "<Double-1>",
                            lambda _event, r=rule_index: self._rename_operation_rule(r))
            nodes = rule["nodes"]
            for node_index, node in enumerate(nodes):
                x = first_x + node_index * (node_width + gap)
                if node_index:
                    canvas.create_line(x - gap + 9, y + node_height / 2, x - 10, y + node_height / 2,
                                       fill="#475569", width=2, arrow=tk.LAST)
                selected = self._operation_rule_selected == (rule_index, node_index)
                tag = f"operation-node:{rule_index}:{node_index}"
                canvas.create_rectangle(x, y, x + node_width, y + node_height, fill="#ffdc35",
                                        outline="#24567b" if selected else "#ffdc35",
                                        width=3 if selected else 1, tags=(tag,))
                canvas.create_text(x + node_width / 2, y + 27, text=node["class"],
                                   fill="#1f2937", font=("Segoe UI", 9), tags=(tag,))
                canvas.create_text(x + node_width / 2, y + 48, text=node["group"],
                                   fill="#1f2937", font=("Segoe UI", 11, "bold"), tags=(tag,))
                canvas.tag_bind(tag, "<ButtonPress-1>",
                                lambda event, r=rule_index, n=node_index: self._start_operation_rule_drag(event, r, n))
                canvas.tag_bind(tag, "<B1-Motion>", self._move_operation_rule_drag)
                canvas.tag_bind(tag, "<ButtonRelease-1>", self._finish_operation_rule_drag)
            add_x = first_x + len(nodes) * (node_width + gap) + 18
            add_tag = f"operation-add:{rule_index}"
            canvas.create_rectangle(add_x, y + 19, add_x + 36, y + 55, fill="#ffffff",
                                    outline="#7b8ca0", width=1, tags=(add_tag,))
            canvas.create_text(add_x + 18, y + 37, text="+", fill="#24567b",
                               font=("Segoe UI", 20, "bold"), tags=(add_tag,))
            canvas.tag_bind(add_tag, "<Button-1>",
                            lambda _event, target_rule=rule_index: self._add_operation_rule_node(target_rule))
        canvas.configure(scrollregion=(0, 0, width, height))

    def _start_operation_rule_row_drag(self, event, rule_index: int) -> None:
        self._operation_rule_selected_row = rule_index
        self._operation_rule_selected = None
        self._operation_rule_row_drag = {"rule": rule_index, "y": self.operation_rule_canvas.canvasy(event.y)}

    def _rename_operation_rule(self, rule_index: int) -> None:
        self._operation_rule_selected_row = rule_index
        self._rename_selected_operation_rule()

    def _move_operation_rule_row_drag(self, event) -> None:
        if not hasattr(self, "_operation_rule_row_drag") or self._operation_rule_row_drag is None:
            return
        canvas = self.operation_rule_canvas
        current_y = canvas.canvasy(event.y)
        delta_y = current_y - self._operation_rule_row_drag["y"]
        canvas.move(f"operation-rule:{self._operation_rule_row_drag['rule']}", 0, delta_y)
        self._operation_rule_row_drag["y"] = current_y

    def _finish_operation_rule_row_drag(self, event) -> None:
        drag = getattr(self, "_operation_rule_row_drag", None)
        if drag is None:
            return
        source_rule = drag["rule"]
        target_rule = min(max(0, int((self.operation_rule_canvas.canvasy(event.y) - 48) // 130)),
                          len(self.operation_rules) - 1)
        if target_rule != source_rule:
            rule = self.operation_rules.pop(source_rule)
            self.operation_rules.insert(target_rule, rule)
            self._operation_rule_selected = None
            self._operation_rule_selected_row = target_rule
            self._save_operation_rules()
        self._operation_rule_row_drag = None
        self._render_operation_rule_canvas()

    def _start_operation_rule_drag(self, event, rule_index: int, node_index: int) -> None:
        self._operation_rule_selected = (rule_index, node_index)
        canvas = self.operation_rule_canvas
        self._operation_rule_drag = {
            "rule": rule_index, "node": node_index,
            "x": canvas.canvasx(event.x), "y": canvas.canvasy(event.y),
        }

    def _move_operation_rule_drag(self, event) -> None:
        if self._operation_rule_drag is None:
            return
        canvas = self.operation_rule_canvas
        current_x, current_y = canvas.canvasx(event.x), canvas.canvasy(event.y)
        delta_x, delta_y = current_x - self._operation_rule_drag["x"], current_y - self._operation_rule_drag["y"]
        tag = f"operation-node:{self._operation_rule_drag['rule']}:{self._operation_rule_drag['node']}"
        canvas.move(tag, delta_x, delta_y)
        self._operation_rule_drag["x"], self._operation_rule_drag["y"] = current_x, current_y

    def _finish_operation_rule_drag(self, event) -> None:
        if self._operation_rule_drag is None:
            return
        source_rule, source_node = self._operation_rule_drag["rule"], self._operation_rule_drag["node"]
        node = self.operation_rules[source_rule]["nodes"].pop(source_node)
        canvas = self.operation_rule_canvas
        target_rule = min(max(0, int((canvas.canvasy(event.y) - 48) // 130)), len(self.operation_rules) - 1)
        target_nodes = self.operation_rules[target_rule]["nodes"]
        target_index = min(max(0, int((canvas.canvasx(event.x) - 155 + 140) // 281)), len(target_nodes))
        target_nodes.insert(target_index, node)
        self._operation_rule_selected = (target_rule, target_index)
        self._operation_rule_drag = None
        self._save_operation_rules()
        self._render_operation_rule_canvas()

    def _update_capacity_preview(self) -> None:
        work_hours = self._preview_capacity_number(self.work_hours_per_day_var.get())
        raw_rate = self._preview_capacity_number(self.raw_cups_per_hour_var.get())
        cooked_rate = self._preview_capacity_number(self.cooked_cups_per_hour_var.get())
        noodle_rate = self._preview_capacity_number(self.cooked_noodle_cups_per_hour_var.get())
        raw_base = self._daily_capacity_preview(raw_rate, work_hours)
        cooked_base = self._daily_capacity_preview(cooked_rate, work_hours)
        noodle_base = self._daily_capacity_preview(noodle_rate, work_hours)
        self.raw_wonton_daily_var.set(self._format_optional_number(raw_base) if raw_base is not None else "—")
        self.cooked_wonton_daily_var.set(self._format_optional_number(cooked_base) if cooked_base is not None else "—")
        self.cooked_wonton_noodle_daily_var.set(self._format_optional_number(noodle_base) if noodle_base is not None else "—")

    @staticmethod
    def _preview_capacity_number(value: str) -> int | float | None:
        cleaned = value.strip().replace(",", "")
        if not cleaned:
            return None
        try:
            numeric = float(cleaned)
        except ValueError:
            return None
        if not math.isfinite(numeric) or numeric < 0:
            return None
        return int(numeric) if numeric.is_integer() else numeric

    def _load_chill_days_settings(self) -> None:
        try:
            chill_days = load_chill_days(self.chill_days_file_path)
        except ValueError as exc:
            self.chill_days_status_var.set(str(exc))
            return
        self.chill_days_var.set(str(chill_days))
        if self.chill_days_file_path.exists():
            self.chill_days_status_var.set("Loaded saved chill-days setting.")

    def _save_chill_days_settings(self) -> None:
        value = self.chill_days_var.get().strip()
        try:
            if not value or not value.isdecimal():
                raise ValueError("Chill days must be a whole number of 0 or greater.")
            chill_days = save_chill_days(self.chill_days_file_path, int(value))
        except ValueError as exc:
            messagebox.showerror("Save chill days", str(exc), parent=self)
            return
        self.chill_days_var.set(str(chill_days))
        self.chill_days_status_var.set(
            f"Saved: RM can remain chilled for {chill_days:,} day(s) before freezing."
        )

    def _load_production_start_settings(self) -> None:
        try:
            settings = load_production_start_settings(self.production_start_file_path)
        except ValueError as exc:
            self.production_start_status_var.set(str(exc))
            return
        self.production_cooked_start_var.set(f"{settings.cooked_hour:02d}:00")
        self.production_raw_start_var.set(f"{settings.raw_hour:02d}:00")
        if self.production_start_file_path.exists():
            self.production_start_status_var.set("Loaded saved production start times.")

    def _save_production_start_settings(self) -> None:
        try:
            settings = ProductionStartSettings(
                cooked_hour=hour_from_time_label(self.production_cooked_start_var.get()),
                raw_hour=hour_from_time_label(self.production_raw_start_var.get()),
            )
            settings = save_production_start_settings(
                self.production_start_file_path,
                settings,
            )
        except ValueError as exc:
            messagebox.showerror("Save production start times", str(exc), parent=self)
            return
        self.production_cooked_start_var.set(f"{settings.cooked_hour:02d}:00")
        self.production_raw_start_var.set(f"{settings.raw_hour:02d}:00")
        self.production_start_status_var.set(
            f"Saved: Cooked starts {settings.cooked_hour:02d}:00 • "
            f"Raw starts {settings.raw_hour:02d}:00."
        )
        self._plan_inputs_changed()

    def _load_labour_settings(self) -> None:
        """Load the saved labour inputs without applying them to plan costs yet."""

        try:
            settings = load_labour_settings(self.labour_file_path)
        except ValueError as exc:
            self.labour_status_var.set(str(exc))
            return
        self.raw_labour_var.set(str(settings.raw_labour))
        self.raw_wage_var.set(self._format_optional_number(settings.raw_wage))
        self.cooked_labour_var.set(str(settings.cooked_labour))
        self.cooked_wage_var.set(self._format_optional_number(settings.cooked_wage))
        if self.labour_file_path.exists():
            self.labour_status_var.set("Loaded saved labour settings.")

    def _save_labour_settings(self) -> None:
        """Validate and persist the two labour-line settings."""

        try:
            settings = LabourSettings(
                raw_labour=self.raw_labour_var.get().strip().replace(",", ""),
                raw_wage=self.raw_wage_var.get().strip().replace(",", ""),
                cooked_labour=self.cooked_labour_var.get().strip().replace(",", ""),
                cooked_wage=self.cooked_wage_var.get().strip().replace(",", ""),
            )
            settings = save_labour_settings(self.labour_file_path, settings)
        except ValueError as exc:
            messagebox.showerror("Save labour settings", str(exc), parent=self)
            return
        self.raw_labour_var.set(str(settings.raw_labour))
        self.raw_wage_var.set(self._format_optional_number(settings.raw_wage))
        self.cooked_labour_var.set(str(settings.cooked_labour))
        self.cooked_wage_var.set(self._format_optional_number(settings.cooked_wage))
        self.labour_status_var.set("Saved labour settings.")

    def _load_capacity_settings(self) -> None:
        try:
            settings = load_capacity_settings(self.capacity_file_path)
        except ValueError as exc:
            self.capacity_status_var.set(str(exc))
            return
        self.capacity_settings = settings
        self.capacity_settings = CapacitySettings(
            raw_percentage=100, cooked_percentage=100,
            raw_cups_per_hour=settings.raw_cups_per_hour,
            cooked_cups_per_hour=settings.cooked_cups_per_hour,
            cooked_noodle_cups_per_hour=settings.cooked_noodle_cups_per_hour,
            work_hours_per_day=settings.work_hours_per_day,
        )
        self.raw_cups_per_hour_var.set(self._format_optional_number(settings.raw_cups_per_hour))
        self.cooked_cups_per_hour_var.set(self._format_optional_number(settings.cooked_cups_per_hour))
        self.cooked_noodle_cups_per_hour_var.set(
            self._format_optional_number(settings.cooked_noodle_cups_per_hour))
        self.work_hours_per_day_var.set(self._format_optional_number(settings.work_hours_per_day))
        self._update_capacity_preview()
        if self.capacity_file_path.exists():
            self.capacity_status_var.set("Loaded saved capacity settings.")
        self._plan_inputs_changed()

    def _save_all_capacity_settings(self) -> None:
        try:
            work_hours_per_day = self._parse_work_hours(self.work_hours_per_day_var.get())
            raw_cups_per_hour = self._parse_capacity_number(
                self.raw_cups_per_hour_var.get(), "Raw wontons / hr")
            cooked_cups_per_hour = self._parse_capacity_number(
                self.cooked_cups_per_hour_var.get(), "Cooked wontons / hr")
            cooked_noodle_cups_per_hour = self._parse_capacity_number(
                self.cooked_noodle_cups_per_hour_var.get(), "Cooked noodle wontons / hr")
            settings = CapacitySettings(
                raw_percentage=100,
                cooked_percentage=100,
                raw_wonton=None,
                cooked_wonton=None,
                raw_cups_per_hour=raw_cups_per_hour,
                cooked_cups_per_hour=cooked_cups_per_hour,
                cooked_noodle_cups_per_hour=cooked_noodle_cups_per_hour,
                work_hours_per_day=work_hours_per_day,
            )
            self.capacity_settings = save_capacity_settings(self.capacity_file_path, settings)
        except ValueError as exc:
            messagebox.showerror("Save capacity", str(exc))
            return
        self.raw_cups_per_hour_var.set(self._format_optional_number(raw_cups_per_hour))
        self.cooked_cups_per_hour_var.set(self._format_optional_number(cooked_cups_per_hour))
        self.cooked_noodle_cups_per_hour_var.set(self._format_optional_number(cooked_noodle_cups_per_hour))
        self.work_hours_per_day_var.set(self._format_optional_number(work_hours_per_day))
        self._update_capacity_preview()
        self.capacity_status_var.set(
            f"Saved hourly capacity with {self._format_optional_number(work_hours_per_day)} working hours/day."
        )
        self._plan_inputs_changed()

    @staticmethod
    def _parse_capacity_number(value: str, label: str) -> int | float:
        cleaned = value.strip().replace(",", "")
        if not cleaned:
            raise ValueError(f"Enter a number for {label}.")
        try:
            numeric = float(cleaned)
        except ValueError as exc:
            raise ValueError(f"{label} must be numeric.") from exc
        if not math.isfinite(numeric) or numeric < 0:
            raise ValueError(f"{label} must be zero or greater.")
        return int(numeric) if numeric.is_integer() else numeric

    @staticmethod
    def _parse_optional_capacity_number(value: str, label: str) -> int | float | None:
        return None if not value.strip() else CapacityViewMixin._parse_capacity_number(value, label)

    @staticmethod
    def _daily_capacity_preview(rate: int | float | None, work_hours: int | float | None) -> int | float | None:
        return None if rate is None or work_hours is None or not 0 < work_hours <= 24 else rate * work_hours

    @staticmethod
    def _parse_work_hours(value: str) -> int | float:
        hours = CapacityViewMixin._parse_capacity_number(value, "Working hours per day")
        if not 0 < hours <= 24:
            raise ValueError("Working hours per day must be more than 0 and no more than 24.")
        return hours
