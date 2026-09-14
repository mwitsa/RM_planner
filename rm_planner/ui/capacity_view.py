"""CapacityViewMixin behavior."""

from __future__ import annotations

from .common import *  # shared UI types and domain services


class CapacityViewMixin:
    def _build_capacity_tab(self) -> None:
        self.raw_capacity_percentage_var = tk.DoubleVar(value=50)
        self.cooked_capacity_percentage_var = tk.DoubleVar(value=50)
        self.raw_capacity_percentage_text_var = tk.StringVar(value="50%")
        self.cooked_capacity_percentage_text_var = tk.StringVar(value="50%")
        self.work_hours_per_day_var = tk.StringVar(value="8")
        self.raw_wonton_per_hour_var = tk.StringVar()
        self.cooked_wonton_per_hour_var = tk.StringVar()
        self.cooked_wonton_noodle_per_hour_var = tk.StringVar()
        self.raw_wonton_daily_var = tk.StringVar(value="Enter Prod Cap / hr and working hours")
        self.cooked_wonton_daily_var = tk.StringVar(value="Enter Prod Cap / hr and working hours")
        self.cooked_wonton_noodle_daily_var = tk.StringVar(value="Enter Prod Cap / hr and working hours")
        self.raw_wonton_scaled_var = tk.StringVar(value="Set base capacity first")
        self.cooked_wonton_scaled_var = tk.StringVar(value="Set base capacity first")

        ttk.Label(
            self.capacity_tab,
            text="Production Capacity Setup",
            style="Summary.TLabel",
        ).pack(anchor=tk.W)
        ttk.Label(
            self.capacity_tab,
            text=(
                "Set Prod Cap / hr and working hours per day. Each slider controls "
                "0–100% of its calculated daily capacity."
            ),
        ).pack(anchor=tk.W, pady=(2, 12))

        settings_frame = ttk.Frame(self.capacity_tab)
        settings_frame.pack(fill=tk.X, pady=(0, 12))
        settings_frame.columnconfigure(0, weight=1)
        settings_frame.columnconfigure(1, weight=1)

        raw_frame = ttk.LabelFrame(
            settings_frame,
            text="เกี๊ยวดิบ",
            padding=12,
        )
        raw_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 6))
        raw_frame.columnconfigure(0, weight=1)
        ttk.Label(raw_frame, text="Calculated maximum per day").grid(
            row=0,
            column=0,
            sticky=tk.W,
        )
        ttk.Label(raw_frame, textvariable=self.raw_wonton_daily_var, style="Summary.TLabel").grid(
            row=1, column=0, sticky=tk.W, pady=(4, 12))
        raw_percentage_row = ttk.Frame(raw_frame)
        raw_percentage_row.grid(row=2, column=0, sticky="ew")
        raw_percentage_row.columnconfigure(0, weight=1)
        ttk.Label(raw_percentage_row, text="Available capacity percentage").grid(
            row=0,
            column=0,
            sticky=tk.W,
        )
        ttk.Label(
            raw_percentage_row,
            textvariable=self.raw_capacity_percentage_text_var,
            style="Summary.TLabel",
        ).grid(row=0, column=1, sticky=tk.E)
        ttk.Scale(
            raw_frame,
            from_=0,
            to=100,
            variable=self.raw_capacity_percentage_var,
            command=self._capacity_slider_changed,
        ).grid(row=3, column=0, sticky="ew", pady=(6, 0))
        raw_scale_ends = ttk.Frame(raw_frame)
        raw_scale_ends.grid(row=4, column=0, sticky="ew")
        raw_scale_ends.columnconfigure(1, weight=1)
        ttk.Label(raw_scale_ends, text="0%").grid(row=0, column=0, sticky=tk.W)
        ttk.Label(raw_scale_ends, text="100%").grid(row=0, column=2, sticky=tk.E)
        ttk.Separator(raw_frame).grid(row=5, column=0, sticky="ew", pady=10)
        ttk.Label(raw_frame, text="Available for Plan").grid(
            row=6,
            column=0,
            sticky=tk.W,
        )
        ttk.Label(
            raw_frame,
            textvariable=self.raw_wonton_scaled_var,
            style="Summary.TLabel",
        ).grid(row=7, column=0, sticky=tk.W, pady=(3, 0))

        cooked_frame = ttk.LabelFrame(
            settings_frame,
            text="เกี๊ยวสุก",
            padding=12,
        )
        cooked_frame.grid(row=0, column=1, sticky="nsew", padx=(6, 0))
        cooked_frame.columnconfigure(0, weight=1)
        ttk.Label(cooked_frame, text="Calculated maximum per day").grid(
            row=0,
            column=0,
            sticky=tk.W,
        )
        ttk.Label(cooked_frame, textvariable=self.cooked_wonton_daily_var, style="Summary.TLabel").grid(
            row=1, column=0, sticky=tk.W, pady=(4, 12))
        cooked_percentage_row = ttk.Frame(cooked_frame)
        cooked_percentage_row.grid(row=2, column=0, sticky="ew")
        cooked_percentage_row.columnconfigure(0, weight=1)
        ttk.Label(cooked_percentage_row, text="Available capacity percentage").grid(
            row=0,
            column=0,
            sticky=tk.W,
        )
        ttk.Label(
            cooked_percentage_row,
            textvariable=self.cooked_capacity_percentage_text_var,
            style="Summary.TLabel",
        ).grid(row=0, column=1, sticky=tk.E)
        ttk.Scale(
            cooked_frame,
            from_=0,
            to=100,
            variable=self.cooked_capacity_percentage_var,
            command=self._capacity_slider_changed,
        ).grid(row=3, column=0, sticky="ew", pady=(6, 0))
        cooked_scale_ends = ttk.Frame(cooked_frame)
        cooked_scale_ends.grid(row=4, column=0, sticky="ew")
        cooked_scale_ends.columnconfigure(1, weight=1)
        ttk.Label(cooked_scale_ends, text="0%").grid(row=0, column=0, sticky=tk.W)
        ttk.Label(cooked_scale_ends, text="100%").grid(row=0, column=2, sticky=tk.E)
        ttk.Separator(cooked_frame).grid(row=5, column=0, sticky="ew", pady=10)
        ttk.Label(cooked_frame, text="Available for Plan").grid(
            row=6,
            column=0,
            sticky=tk.W,
        )
        ttk.Label(
            cooked_frame,
            textvariable=self.cooked_wonton_scaled_var,
            style="Summary.TLabel",
        ).grid(row=7, column=0, sticky=tk.W, pady=(3, 0))

        hourly_frame = ttk.LabelFrame(settings_frame, text="Prod Cap / hr", padding=12)
        hourly_frame.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(12, 0))
        for column in range(3):
            hourly_frame.columnconfigure(column, weight=1)
        ttk.Label(hourly_frame, text="Working hours per day").grid(row=0, column=0, sticky=tk.W)
        work_hours_entry = ttk.Entry(hourly_frame, textvariable=self.work_hours_per_day_var, width=10,
                                     font=("Segoe UI", 11))
        work_hours_entry.grid(row=1, column=0, sticky="w", pady=(4, 12))
        ttk.Label(hourly_frame, text="(used to calculate capacity per day)").grid(
            row=1, column=0, sticky=tk.W, padx=(90, 0), pady=(4, 12))
        for column, (label, variable, daily_var) in enumerate((
            ("Raw wonton", self.raw_wonton_per_hour_var, self.raw_wonton_daily_var),
            ("Cooked wonton", self.cooked_wonton_per_hour_var, self.cooked_wonton_daily_var),
            ("Cooked wonton + noodle", self.cooked_wonton_noodle_per_hour_var, self.cooked_wonton_noodle_daily_var),
        )):
            field = ttk.Frame(hourly_frame)
            field.grid(row=2, column=column, sticky="ew", padx=(0 if column == 0 else 8, 8 if column < 2 else 0))
            field.columnconfigure(0, weight=1)
            ttk.Label(field, text=label).grid(row=0, column=0, sticky=tk.W)
            entry = ttk.Entry(field, textvariable=variable, font=("Segoe UI", 11))
            entry.grid(
                row=1, column=0, sticky="ew", pady=(4, 0))
            ttk.Label(field, textvariable=daily_var).grid(row=2, column=0, sticky=tk.W, pady=(3, 0))
            entry.bind("<KeyRelease>", lambda _event: self._update_capacity_preview())
        work_hours_entry.bind("<KeyRelease>", lambda _event: self._update_capacity_preview())

        action_frame = ttk.Frame(self.capacity_tab)
        action_frame.pack(fill=tk.X)
        ttk.Button(
            action_frame,
            text="Save capacity settings",
            command=self._save_all_capacity_settings,
        ).pack(anchor=tk.E)

        ttk.Label(
            self.capacity_tab,
            textvariable=self.capacity_status_var,
            relief=tk.SUNKEN,
            anchor=tk.W,
            padding=(6, 3),
        ).pack(fill=tk.X, pady=(14, 0))

    def _capacity_slider_changed(self, _value: str) -> None:
        self._update_capacity_preview()

    def _update_capacity_preview(self) -> None:
        raw_percentage = round(self.raw_capacity_percentage_var.get())
        cooked_percentage = round(self.cooked_capacity_percentage_var.get())
        self.raw_capacity_percentage_text_var.set(f"{raw_percentage}%")
        self.cooked_capacity_percentage_text_var.set(f"{cooked_percentage}%")
        work_hours = self._preview_capacity_number(self.work_hours_per_day_var.get())
        raw_rate = self._preview_capacity_number(self.raw_wonton_per_hour_var.get())
        cooked_rate = self._preview_capacity_number(self.cooked_wonton_per_hour_var.get())
        noodle_rate = self._preview_capacity_number(self.cooked_wonton_noodle_per_hour_var.get())
        raw_base = self._daily_capacity_preview(raw_rate, work_hours)
        cooked_base = self._daily_capacity_preview(cooked_rate, work_hours)
        noodle_base = self._daily_capacity_preview(noodle_rate, work_hours)
        raw_wonton = None if raw_base is None else raw_base * raw_percentage / 100
        cooked_wonton = None if cooked_base is None else cooked_base * cooked_percentage / 100
        self.raw_wonton_daily_var.set(self._format_daily_capacity(raw_base))
        self.cooked_wonton_daily_var.set(self._format_daily_capacity(cooked_base))
        self.cooked_wonton_noodle_daily_var.set(self._format_daily_capacity(noodle_base))
        self.raw_wonton_scaled_var.set(
            "Enter a valid hourly capacity"
            if raw_wonton is None
            else f"{self._format_optional_number(raw_wonton)} wontons/day"
        )
        self.cooked_wonton_scaled_var.set(
            "Enter a valid hourly capacity"
            if cooked_wonton is None
            else f"{self._format_optional_number(cooked_wonton)} wontons/day"
        )

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
        self.raw_capacity_percentage_var.set(settings.raw_percentage)
        self.cooked_capacity_percentage_var.set(settings.cooked_percentage)
        self.raw_wonton_per_hour_var.set(self._format_optional_number(settings.raw_wonton_per_hour))
        self.cooked_wonton_per_hour_var.set(self._format_optional_number(settings.cooked_wonton_per_hour))
        self.cooked_wonton_noodle_per_hour_var.set(
            self._format_optional_number(settings.cooked_wonton_noodle_per_hour))
        self.work_hours_per_day_var.set(self._format_optional_number(settings.work_hours_per_day))
        self._update_capacity_preview()
        if self.capacity_file_path.exists():
            self.capacity_status_var.set("Loaded saved capacity settings.")
        self._plan_inputs_changed()

    def _save_all_capacity_settings(self) -> None:
        try:
            work_hours_per_day = self._parse_work_hours(self.work_hours_per_day_var.get())
            raw_wonton_per_hour = self._parse_capacity_number(
                self.raw_wonton_per_hour_var.get(), "Raw wonton / hr")
            cooked_wonton_per_hour = self._parse_capacity_number(
                self.cooked_wonton_per_hour_var.get(), "Cooked wonton / hr")
            cooked_wonton_noodle_per_hour = self._parse_capacity_number(
                self.cooked_wonton_noodle_per_hour_var.get(), "Cooked wonton + noodle / hr")
            settings = CapacitySettings(
                raw_percentage=round(self.raw_capacity_percentage_var.get()),
                cooked_percentage=round(self.cooked_capacity_percentage_var.get()),
                raw_wonton=None,
                cooked_wonton=None,
                raw_wonton_per_hour=raw_wonton_per_hour,
                cooked_wonton_per_hour=cooked_wonton_per_hour,
                cooked_wonton_noodle_per_hour=cooked_wonton_noodle_per_hour,
                work_hours_per_day=work_hours_per_day,
            )
            self.capacity_settings = save_capacity_settings(self.capacity_file_path, settings)
        except ValueError as exc:
            messagebox.showerror("Save capacity", str(exc))
            return
        self.raw_wonton_per_hour_var.set(self._format_optional_number(raw_wonton_per_hour))
        self.cooked_wonton_per_hour_var.set(self._format_optional_number(cooked_wonton_per_hour))
        self.cooked_wonton_noodle_per_hour_var.set(self._format_optional_number(cooked_wonton_noodle_per_hour))
        self.work_hours_per_day_var.set(self._format_optional_number(work_hours_per_day))
        self.raw_capacity_percentage_var.set(self.capacity_settings.raw_percentage)
        self.cooked_capacity_percentage_var.set(
            self.capacity_settings.cooked_percentage
        )
        self._update_capacity_preview()
        self.capacity_status_var.set(
            f"Saved hourly capacity with {self._format_optional_number(work_hours_per_day)} working hours/day; "
            f"ดิบ {self.capacity_settings.raw_percentage}% / "
            f"สุก {self.capacity_settings.cooked_percentage}%."
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

    def _format_daily_capacity(self, value: int | float | None) -> str:
        return "Enter valid Prod Cap / hr and working hours" if value is None else f"{self._format_optional_number(value)} wontons/day"

    @staticmethod
    def _parse_work_hours(value: str) -> int | float:
        hours = CapacityViewMixin._parse_capacity_number(value, "Working hours per day")
        if not 0 < hours <= 24:
            raise ValueError("Working hours per day must be more than 0 and no more than 24.")
        return hours
