"""StockOverviewMixin behavior."""

from __future__ import annotations

from .common import *  # shared UI types and domain services


RM_STOCK_DISPLAY_CLASSES = STOCK_SIZE_CLASSES
RM_STOCK_CARD_CLASSES = tuple(size_class for size_class in STOCK_SIZE_CLASSES if size_class != "Unused")


class StockOverviewMixin:
    def _build_rm_tab(self) -> None:
        self.rm_tab.rowconfigure(0, weight=1)
        self.rm_tab.columnconfigure(2, weight=1)

        sidebar = tk.Frame(self.rm_tab, width=190, background="#eef2f6")
        sidebar.grid(row=0, column=0, sticky="ns")
        sidebar.grid_propagate(False)
        ttk.Separator(self.rm_tab, orient=tk.VERTICAL).grid(row=0, column=1, sticky="ns")

        tk.Label(
            sidebar,
            text="RM",
            background="#eef2f6",
            foreground="#243447",
            font=("Segoe UI", 11, "bold"),
            anchor=tk.W,
            padx=16,
            pady=14,
        ).pack(fill=tk.X)

        self.rm_navigation_buttons: dict[str, tk.Button] = {}
        for key, label in RM_NAVIGATION_ITEMS:
            button = tk.Button(
                sidebar,
                text=label,
                command=lambda section=key: self._show_rm_section(section),
                relief=tk.FLAT,
                borderwidth=0,
                anchor=tk.W,
                padx=18,
                pady=10,
                background="#eef2f6",
                activebackground="#dce9f5",
                font=("Segoe UI", 10),
            )
            button.pack(fill=tk.X)
            self.rm_navigation_buttons[key] = button

        content = ttk.Frame(self.rm_tab)
        content.grid(row=0, column=2, sticky="nsew")
        content.rowconfigure(0, weight=1)
        content.columnconfigure(0, weight=1)

        self.rm_timeline_tab = ttk.Frame(content, padding=14)
        self.assortment_std_tab = ttk.Frame(content, padding=14)
        self.assortment_actual_tab = ttk.Frame(content, padding=14)
        self.rm_timeline_tab.grid(row=0, column=0, sticky="nsew")
        self.assortment_std_tab.grid(row=0, column=0, sticky="nsew")
        self.assortment_actual_tab.grid(row=0, column=0, sticky="nsew")
        self._build_rm_timeline_tab()
        self._build_assortment_std_tab()
        self._build_assortment_actual_tab()
        self._show_rm_section("timeline")

    def _show_rm_section(self, section: str) -> None:
        frames = {
            "timeline": self.rm_timeline_tab,
            "predict": self.assortment_std_tab,
            "actual": self.assortment_actual_tab,
        }
        if section not in frames:
            raise ValueError(f"Unknown RM section: {section}")
        frames[section].tkraise()
        navigation_section = rm_navigation_section(section)
        for key, button in self.rm_navigation_buttons.items():
            selected = key == navigation_section
            button.configure(
                background="#cfe3f5" if selected else "#eef2f6",
                foreground="#0b4f7a" if selected else "#243447",
                font=("Segoe UI", 10, "bold" if selected else "normal"),
            )

    def _build_rm_timeline_tab(self) -> None:
        self.rm_stock_as_of_var = tk.StringVar(value="—")
        self.rm_stock_total_var = tk.StringVar(value="0 kg")
        self.rm_stock_wontons_var = tk.StringVar(value="0")
        self.rm_stock_distribution_weights = tuple(0.0 for _ in RM_STOCK_DISPLAY_CLASSES)
        self.rm_stock_distribution_vars = {
            size_class: tk.StringVar(value=f"{size_class} 0% | 0 kg")
            for size_class in RM_STOCK_DISPLAY_CLASSES
        }
        self.rm_stock_size_vars = {
            size_class: {
                "stock": tk.StringVar(value="0 kg"),
                "domestic": tk.StringVar(value="0 kg"),
                "export": tk.StringVar(value="0 kg"),
                "domestic_wontons": tk.StringVar(value="0"),
                "export_wontons": tk.StringVar(value="0"),
            }
            for size_class in RM_STOCK_CARD_CLASSES
        }
        self.rm_timeline_status_var = tk.StringVar(
            value="Cumulative stock before generated Plan consumption."
        )

        overview = ttk.LabelFrame(
            self.rm_timeline_tab,
            text="Stock overview",
            padding=12,
        )
        overview.pack(fill=tk.X, pady=(0, 8))
        for column in range(3):
            overview.columnconfigure(column, weight=1)
        overview_fields = (
            ("As of", self.rm_stock_as_of_var),
            ("Total stock", self.rm_stock_total_var),
            ("Est. wontons", self.rm_stock_wontons_var),
        )
        for column, (label, variable) in enumerate(overview_fields):
            ttk.Label(overview, text=label).grid(
                row=0,
                column=column,
                sticky=tk.W,
                padx=(0, 20),
            )
            ttk.Label(
                overview,
                textvariable=variable,
                style="Summary.TLabel",
            ).grid(
                row=1,
                column=column,
                sticky=tk.W,
                padx=(0, 20),
                pady=(3, 0),
            )
        ttk.Button(
            overview,
            text="+ Add stock",
            command=self._open_stock_editor,
        ).grid(row=0, column=3, rowspan=2, sticky=tk.E)

        self.rm_stock_distribution_canvas = tk.Canvas(
            overview,
            height=38,
            background="#ffffff",
            highlightbackground="#b8b8b8",
            highlightthickness=1,
        )
        self.rm_stock_distribution_canvas.grid(
            row=2,
            column=0,
            columnspan=4,
            sticky="ew",
            pady=(12, 8),
        )
        self.rm_stock_distribution_canvas.bind(
            "<Configure>",
            self._draw_rm_stock_distribution,
        )

        distribution_legend = ttk.Frame(overview)
        distribution_legend.grid(row=3, column=0, columnspan=4, sticky="ew")
        for column, size_class in enumerate(RM_STOCK_DISPLAY_CLASSES):
            distribution_legend.columnconfigure(column, weight=1)
            legend_item = ttk.Frame(distribution_legend)
            legend_item.grid(row=0, column=column, sticky=tk.W)
            tk.Label(
                legend_item,
                text="  ",
                background=RM_STOCK_DISTRIBUTION_COLORS[size_class],
                width=2,
            ).pack(side=tk.LEFT, padx=(0, 6))
            ttk.Label(
                legend_item,
                textvariable=self.rm_stock_distribution_vars[size_class],
            ).pack(side=tk.LEFT)

        size_sections = ttk.Frame(self.rm_timeline_tab)
        size_sections.pack(fill=tk.X, pady=(0, 8))
        for column, size_class in enumerate(RM_STOCK_CARD_CLASSES):
            size_sections.columnconfigure(column, weight=1)
            background, border, foreground = RM_STOCK_CARD_COLORS[size_class]
            section = tk.Frame(
                size_sections,
                background=background,
                highlightbackground=border,
                highlightcolor=border,
                highlightthickness=1,
                padx=14,
                pady=12,
            )
            section.grid(
                row=0,
                column=column,
                sticky="nsew",
                padx=(
                    0 if column == 0 else 4,
                    0 if column == len(RM_STOCK_CARD_CLASSES) - 1 else 4,
                ),
            )
            card_header = tk.Frame(section, background=background)
            card_header.pack(fill=tk.X, pady=(0, 10))
            tk.Label(
                card_header,
                text=size_class,
                background=background,
                foreground=foreground,
                font=("Segoe UI", 12, "bold"),
            ).pack(side=tk.LEFT)
            tk.Label(
                card_header,
                text="Total stock",
                background=background,
                foreground="#555555",
            ).pack(side=tk.LEFT, padx=(14, 6))
            tk.Label(
                card_header,
                textvariable=self.rm_stock_size_vars[size_class]["stock"],
                background=background,
                foreground=foreground,
                font=("Segoe UI", 12, "bold"),
            ).pack(side=tk.LEFT)

            market_breakdown = tk.Frame(section, background=background)
            market_breakdown.pack(fill=tk.X)
            for market_column, market in enumerate(("domestic", "export")):
                market_breakdown.columnconfigure(market_column, weight=1)
                market_panel = tk.Frame(
                    market_breakdown,
                    background="#ffffff",
                    highlightbackground=border,
                    highlightcolor=border,
                    highlightthickness=1,
                    padx=12,
                    pady=10,
                )
                market_panel.grid(
                    row=0,
                    column=market_column,
                    sticky="nsew",
                    padx=(0, 5) if market_column == 0 else (5, 0),
                )
                tk.Label(
                    market_panel,
                    text=market_display_label(market),
                    background="#ffffff",
                    foreground=foreground,
                    font=("Segoe UI", 10, "bold"),
                ).pack(anchor=tk.W, pady=(0, 8))
                market_details = tk.Frame(market_panel, background="#ffffff")
                market_details.pack(fill=tk.X)
                market_details.columnconfigure(0, weight=1)
                market_details.columnconfigure(1, weight=1)
                tk.Label(
                    market_details,
                    text="Weight",
                    background="#ffffff",
                    foreground="#555555",
                ).grid(row=0, column=0, sticky=tk.W)
                tk.Label(
                    market_details,
                    text="Est. wonton",
                    background="#ffffff",
                    foreground="#555555",
                ).grid(row=0, column=1, sticky=tk.E)
                tk.Label(
                    market_details,
                    textvariable=self.rm_stock_size_vars[size_class][market],
                    background="#ffffff",
                    foreground=foreground,
                    font=("Segoe UI", 12, "bold"),
                ).grid(row=1, column=0, sticky=tk.W, pady=(3, 0))
                tk.Label(
                    market_details,
                    textvariable=self.rm_stock_size_vars[size_class][
                        f"{market}_wontons"
                    ],
                    background="#ffffff",
                    foreground=foreground,
                    font=("Segoe UI", 11, "bold"),
                ).grid(row=1, column=1, sticky=tk.E, pady=(3, 0))

        table_frame = ttk.LabelFrame(
            self.rm_timeline_tab,
            text="RM stock arrival details",
            padding=8,
        )
        table_frame.pack(fill=tk.BOTH, expand=True)
        table_frame.rowconfigure(0, weight=1)
        table_frame.columnconfigure(0, weight=1)
        columns = (
            "date",
            "sources",
            "incoming",
            "stock",
            "M",
            "S",
            "SS",
            "HC",
            "BK",
            "unused",
        )
        self.rm_timeline_tree = ttk.Treeview(table_frame, columns=columns, show="headings")
        headings = {
            "date": "Date",
            "sources": "ชื่อฟาร์ม",
            "incoming": "RM in (kg)",
            "stock": "Stock (kg)",
            "M": "M stock (kg)",
            "S": "S stock (kg)",
            "SS": "SS stock (kg)",
            "HC": "HC stock (kg)",
            "BK": "BK stock (kg)",
            "unused": "Unused stock (kg)",
        }
        widths = {
            "date": 95,
            "sources": 220,
            "incoming": 100,
            "stock": 100,
            "M": 110,
            "S": 110,
            "SS": 110,
            "HC": 110,
            "BK": 110,
            "unused": 125,
        }
        numeric = set(columns) - {"date", "sources"}
        for column in columns:
            self.rm_timeline_tree.heading(column, text=headings[column])
            self.rm_timeline_tree.column(
                column,
                width=widths[column],
                minwidth=75,
                anchor=tk.E if column in numeric else tk.W,
                stretch=column == "sources",
            )
        vertical = ttk.Scrollbar(
            table_frame,
            orient=tk.VERTICAL,
            command=self.rm_timeline_tree.yview,
        )
        horizontal = ttk.Scrollbar(
            table_frame,
            orient=tk.HORIZONTAL,
            command=self.rm_timeline_tree.xview,
        )
        self.rm_timeline_tree.configure(
            yscrollcommand=vertical.set,
            xscrollcommand=horizontal.set,
        )
        self.rm_timeline_tree.grid(row=0, column=0, sticky="nsew")
        vertical.grid(row=0, column=1, sticky="ns")
        horizontal.grid(row=1, column=0, sticky="ew")

        self.rm_timeline_status_label = ttk.Label(
            self.rm_timeline_tab,
            textvariable=self.rm_timeline_status_var,
            relief=tk.SUNKEN,
            anchor=tk.W,
            padding=(6, 3),
        )
        self.rm_timeline_status_label.pack(fill=tk.X, pady=(8, 0))
        self._refresh_rm_timeline()

    def _open_stock_editor(self) -> None:
        self._new_assortment_actual_form()
        self._show_rm_section("actual")

    def _set_rm_stock_distribution(
        self,
        *stock_weights: int | float,
    ) -> None:
        weights = tuple(float(weight) for weight in stock_weights)
        if len(weights) != len(RM_STOCK_DISPLAY_CLASSES):
            raise ValueError("RM stock distribution has an invalid number of classes.")
        percentages = stock_distribution_percentages(*weights)
        self.rm_stock_distribution_weights = weights
        for size_class, weight, percentage in zip(
            RM_STOCK_DISPLAY_CLASSES,
            weights,
            percentages,
        ):
            self.rm_stock_distribution_vars[size_class].set(
                f"{size_class} {self._format_optional_number(percentage)}% | "
                f"{self._format_optional_number(weight)} kg"
            )
        self.rm_stock_distribution_canvas.after_idle(self._draw_rm_stock_distribution)

    def _draw_rm_stock_distribution(self, _event: tk.Event | None = None) -> None:
        canvas = self.rm_stock_distribution_canvas
        canvas.delete("all")
        width = max(canvas.winfo_width() - 2, 1)
        height = max(canvas.winfo_height() - 2, 1)
        percentages = stock_distribution_percentages(
            *self.rm_stock_distribution_weights
        )
        if sum(percentages) == 0:
            canvas.create_rectangle(1, 1, width + 1, height + 1, fill="#eeeeee", outline="")
            canvas.create_text(
                (width + 2) / 2,
                (height + 2) / 2,
                text="No stock",
                fill="#555555",
                font=("Segoe UI", 9, "bold"),
            )
            return

        left = 1.0
        size_classes = RM_STOCK_DISPLAY_CLASSES
        for index, (size_class, percentage) in enumerate(zip(size_classes, percentages)):
            right = (
                width + 1.0
                if index == len(size_classes) - 1
                else left + (width * percentage / 100)
            )
            canvas.create_rectangle(
                left,
                1,
                right,
                height + 1,
                fill=RM_STOCK_DISTRIBUTION_COLORS[size_class],
                outline="#ffffff",
            )
            if right - left >= 72:
                canvas.create_text(
                    (left + right) / 2,
                    (height + 2) / 2,
                    text=(
                        f"{size_class} "
                        f"{self._format_optional_number(percentage)}%"
                    ),
                    fill="#ffffff",
                    font=("Segoe UI", 9, "bold"),
                )
            left = right

    def _refresh_rm_timeline(self, _event: tk.Event | None = None) -> None:
        if not hasattr(self, "rm_timeline_tree"):
            return
        try:
            records = tuple(self.assortment_actual_records.values())
            ranges = self._current_assortment_size_range_definitions()
            rows = build_rm_timeline(
                records,
                ranges,
                wonton_weight_settings=self.wonton_weight_settings,
            )
            market_rows = {
                market: build_rm_timeline(
                    records,
                    ranges,
                    market_type=market,
                    wonton_weight_settings=self.wonton_weight_settings,
                )
                for market in ("domestic", "export")
            }
        except ValueError as exc:
            self.rm_timeline_tree.delete(*self.rm_timeline_tree.get_children())
            self.rm_stock_as_of_var.set("Unavailable")
            self.rm_stock_total_var.set("—")
            self.rm_stock_wontons_var.set("—")
            self._set_rm_stock_distribution(*(0 for _ in RM_STOCK_DISPLAY_CLASSES))
            for variables in self.rm_stock_size_vars.values():
                for variable in variables.values():
                    variable.set("—")
            self.rm_timeline_status_var.set(str(exc))
            return

        self.rm_timeline_tree.delete(*self.rm_timeline_tree.get_children())
        for index, row in enumerate(rows):
            self.rm_timeline_tree.insert(
                "",
                tk.END,
                iid=f"rm-timeline:{index}",
                values=(
                    row.record_date,
                    ", ".join(row.source_labels),
                    self._format_optional_number(row.incoming_kg),
                    self._format_optional_number(row.cumulative_kg),
                    self._format_size_class_summary(row.m_stock),
                    self._format_size_class_summary(row.s_stock),
                    self._format_size_class_summary(row.ss_stock),
                    self._format_size_class_summary(row.hc_stock),
                    self._format_size_class_summary(row.bk_stock),
                    self._format_size_class_summary(row.unused_stock),
                ),
            )
        record_count = sum(len(row.source_labels) for row in rows)
        if rows:
            final = rows[-1]
            self.rm_stock_as_of_var.set(final.record_date)
            self.rm_stock_total_var.set(
                f"{self._format_optional_number(final.cumulative_kg)} kg"
            )
            self.rm_stock_wontons_var.set(
                self._format_optional_number(final.cumulative_wontons)
            )
            self._set_rm_stock_distribution(
                final.m_stock.total,
                final.s_stock.total,
                final.ss_stock.total,
                final.hc_stock.total,
                final.bk_stock.total,
                final.unused_stock.total,
            )
            size_summaries = {
                "M": final.m_stock,
                "S": final.s_stock,
                "SS": final.ss_stock,
                "HC": final.hc_stock,
                "BK": final.bk_stock,
            }
            for size_class, summary in size_summaries.items():
                variables = self.rm_stock_size_vars[size_class]
                variables["stock"].set(
                    f"{self._format_optional_number(summary.total)} kg"
                )
                for market, filtered_rows in market_rows.items():
                    market_total = 0.0
                    if filtered_rows:
                        market_final = filtered_rows[-1]
                        market_summary = getattr(market_final, f"{size_class.lower()}_stock")
                        market_total = market_summary.total
                        market_wontons = (
                            getattr(market_final, f"{size_class.lower()}_wontons")
                            if size_class in SIZE_CLASSES else 0
                        )
                    else:
                        market_wontons = 0
                    variables[market].set(
                        f"{self._format_optional_number(market_total)} kg"
                    )
                    variables[f"{market}_wontons"].set(
                        self._format_optional_number(market_wontons)
                    )
            self.rm_timeline_status_var.set(
                f"Combined from {record_count:,} RM records across {len(rows):,} dates. "
                "Stock is before Plan usage."
            )
        else:
            self.rm_stock_as_of_var.set("—")
            self.rm_stock_total_var.set("0 kg")
            self.rm_stock_wontons_var.set("0")
            self._set_rm_stock_distribution(*(0 for _ in RM_STOCK_DISPLAY_CLASSES))
            for variables in self.rm_stock_size_vars.values():
                variables["stock"].set("0 kg")
                for market in ("domestic", "export"):
                    variables[market].set("0 kg")
                    variables[f"{market}_wontons"].set("0")
            self.rm_timeline_status_var.set(
                "No RM stock records for these filters."
            )
