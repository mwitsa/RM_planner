"""CapacityViewMixin behavior."""

from __future__ import annotations

from .common import *  # shared UI types and domain services


class CapacityViewMixin:
    def _build_capacity_tab(self) -> None:
        self.work_hours_per_day_var = tk.StringVar(value="8")
        self.raw_cups_per_hour_var = tk.StringVar()
        self.cooked_cups_per_hour_var = tk.StringVar()
        self.cooked_noodle_cups_per_hour_var = tk.StringVar()
        self.raw_wonton_daily_var = tk.StringVar(value="—")
        self.cooked_wonton_daily_var = tk.StringVar(value="—")
        self.cooked_wonton_noodle_daily_var = tk.StringVar(value="—")

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
        ttk.Label(hours_card, text="ชั่วโมง/วัน  •  ใช้คูณกับ Prod Cap / hr ของทุกประเภท").pack(anchor=tk.W)

        inputs = ttk.LabelFrame(capacity_content, text="Prod Cap / hr", padding=14)
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
            ttk.Label(field, text="ถ้วย / ชั่วโมง").grid(row=2, column=0, sticky=tk.W, pady=(3, 0))
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
            tk.Label(card, text="ถ้วย / วัน", bg="#edf6fb", anchor="w").pack(fill=tk.X)

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
        ttk.LabelFrame(
            self.operation_order_rule_tab,
            text="Operation order rules",
            padding=16,
        ).pack(fill=tk.X)

        self.class_define_tab = ttk.Frame(content_host)
        self._operations_sections = {
            "capacity": capacity_content,
            "operation_order_rule": self.operation_order_rule_tab,
            "class_define": self.class_define_tab,
        }
        self._operations_section_buttons = {
            "capacity": self.operations_capacity_button,
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
        self._operations_section_buttons["operation_order_rule"].pack(fill=tk.X, pady=(4, 0))
        self._operations_section_buttons["class_define"].pack(fill=tk.X, pady=(4, 0))
        self._build_class_define_tab()
        self._select_operations_section("capacity")

    def _select_operations_section(self, section: str) -> None:
        """Show one Operations Settings category in the shared content area."""

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
                self.raw_cups_per_hour_var.get(), "Raw cups / hr")
            cooked_cups_per_hour = self._parse_capacity_number(
                self.cooked_cups_per_hour_var.get(), "Cooked cups / hr")
            cooked_noodle_cups_per_hour = self._parse_capacity_number(
                self.cooked_noodle_cups_per_hour_var.get(), "Cooked noodle cups / hr")
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
