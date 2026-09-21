"""RM stock balance screen and its cumulative-arrival presentation."""

from __future__ import annotations

from datetime import date

from .common import *  # shared UI types and domain services


RM_STOCK_DISPLAY_CLASSES = STOCK_SIZE_CLASSES
RM_STOCK_CARD_CLASSES = tuple(
    size_class for size_class in STOCK_SIZE_CLASSES if size_class != "Unused"
)
RECORD_TYPE_LABELS = {
    "actual": "Actual",
    "existing": "Existing",
    "prediction": "Prediction",
}


class StockOverviewMixin:
    def _build_rm_tab(self) -> None:
        self.rm_tab.rowconfigure(0, weight=1)
        self.rm_tab.columnconfigure(2, weight=1)

        sidebar = tk.Frame(self.rm_tab, width=190, background="#eef2f6")
        sidebar.grid(row=0, column=0, sticky="ns")
        sidebar.grid_propagate(False)
        ttk.Separator(self.rm_tab, orient=tk.VERTICAL).grid(row=0, column=1, sticky="ns")

        tk.Label(
            sidebar, text="RM", background="#eef2f6", foreground="#243447",
            font=("Segoe UI", 11, "bold"), anchor=tk.W, padx=16, pady=14,
        ).pack(fill=tk.X)
        self.rm_navigation_buttons: dict[str, tk.Button] = {}
        for key, label in RM_NAVIGATION_ITEMS:
            button = tk.Button(
                sidebar, text=label, command=lambda section=key: self._show_rm_section(section),
                relief=tk.FLAT, borderwidth=0, anchor=tk.W, padx=18, pady=10,
                background="#eef2f6", activebackground="#dce9f5", font=("Segoe UI", 10),
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
        for frame in (self.rm_timeline_tab, self.assortment_std_tab, self.assortment_actual_tab):
            frame.grid(row=0, column=0, sticky="nsew")
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
        """Build a concise stock-balance view over the existing arrival logic."""

        self.rm_stock_as_of_var = tk.StringVar(value="—")
        self.rm_stock_total_var = tk.StringVar(value="0 kg")
        self.rm_stock_unused_var = tk.StringVar(value="0 kg")
        self.rm_stock_mix_weights = tuple(0.0 for _ in RM_STOCK_DISPLAY_CLASSES)
        self.rm_stock_market_totals = {
            market: {size: 0.0 for size in RM_STOCK_CARD_CLASSES}
            for market in ("domestic", "export")
        }
        self.rm_stock_source_var = tk.StringVar(value="All")
        self.rm_stock_search_var = tk.StringVar()
        self.rm_stock_class_var = tk.StringVar(value="All")
        self.rm_stock_from_var = tk.StringVar()
        self.rm_stock_to_var = tk.StringVar()
        self.rm_timeline_status_var = tk.StringVar(
            value="Stock shown here is before generated Plan consumption."
        )

        page = tk.Frame(self.rm_timeline_tab, background="#f7f9fc")
        page.pack(fill=tk.BOTH, expand=True)

        header = tk.Frame(page, background="#f7f9fc", padx=2, pady=2)
        header.pack(fill=tk.X)
        tk.Label(
            header, text="RM Stock Balance", background="#f7f9fc", foreground="#182b49",
            font=("Segoe UI", 19, "bold"),
        ).pack(side=tk.LEFT)
        tk.Label(header, text="As of", background="#f7f9fc", foreground="#64748b",
                 font=("Segoe UI", 10)).pack(side=tk.LEFT, padx=(16, 5))
        tk.Label(header, textvariable=self.rm_stock_as_of_var, background="#f7f9fc",
                 foreground="#475569", font=("Segoe UI", 10, "bold")).pack(side=tk.LEFT)
        ttk.Button(header, text="+ Add stock", command=self._open_stock_editor).pack(side=tk.RIGHT)
        ttk.Button(header, text="Export", state=tk.DISABLED).pack(side=tk.RIGHT, padx=(0, 8))
        self.rm_stock_source_combo = ttk.Combobox(
            header, textvariable=self.rm_stock_source_var, values=("All",), state="readonly", width=15,
        )
        self.rm_stock_source_combo.pack(side=tk.RIGHT, padx=(0, 8))
        ttk.Label(header, text="Source").pack(side=tk.RIGHT, padx=(0, 5))

        notice = tk.Frame(page, background="#e5f2ff", highlightbackground="#9cc8ee", highlightthickness=1,
                          padx=12, pady=7)
        notice.pack(fill=tk.X, pady=(10, 10))
        tk.Label(notice, text="●", background="#e5f2ff", foreground="#1767ad",
                 font=("Segoe UI", 12, "bold")).pack(side=tk.LEFT)
        tk.Label(notice, text="Stock shown here is before generated Plan consumption.",
                 background="#e5f2ff", foreground="#175a96", font=("Segoe UI", 10, "bold")).pack(
                     side=tk.LEFT, padx=(8, 0))

        hero = tk.Frame(page, background="#f7f9fc")
        hero.pack(fill=tk.X)
        hero.columnconfigure(0, weight=2)
        hero.columnconfigure(1, weight=1)
        total_card = self._balance_card(hero)
        total_card.grid(row=0, column=0, sticky="ew", padx=(0, 5))
        tk.Label(total_card, text="Total RM Stock (before plan)", bg="white", fg="#27384f",
                 font=("Segoe UI", 10, "bold")).pack(anchor=tk.W)
        total_body = tk.Frame(total_card, background="white")
        total_body.pack(fill=tk.X, pady=(5, 0))
        tk.Label(total_body, textvariable=self.rm_stock_total_var, bg="white", fg="#0b5bc5",
                 font=("Segoe UI", 27, "bold")).pack(side=tk.LEFT)
        ttk.Separator(total_body, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=20)
        tk.Label(total_body, text="Cumulative arrivals\nbefore plan consumption.", bg="white", fg="#718096",
                 justify=tk.LEFT, font=("Segoe UI", 9)).pack(side=tk.LEFT)
        unused_card = self._balance_card(hero)
        unused_card.grid(row=0, column=1, sticky="ew", padx=(5, 0))
        tk.Label(unused_card, text="Unused Stock", bg="white", fg="#27384f",
                 font=("Segoe UI", 10, "bold")).pack(anchor=tk.W)
        unused_body = tk.Frame(unused_card, background="white")
        unused_body.pack(fill=tk.X, pady=(8, 0))
        tk.Label(unused_body, text="◈", background="white", foreground="#738396",
                 font=("Segoe UI", 24)).pack(side=tk.LEFT, padx=(4, 12))
        tk.Label(unused_body, textvariable=self.rm_stock_unused_var, background="white", foreground="#26364d",
                 font=("Segoe UI", 22, "bold")).pack(side=tk.LEFT)

        analysis = tk.Frame(page, background="#f7f9fc")
        analysis.pack(fill=tk.X, pady=(10, 10))
        analysis.columnconfigure(0, weight=1)
        analysis.columnconfigure(1, weight=1)
        mix_card = self._balance_card(analysis)
        mix_card.grid(row=0, column=0, sticky="nsew", padx=(0, 5))
        tk.Label(mix_card, text="Stock mix (by size class)", bg="white", fg="#27384f",
                 font=("Segoe UI", 10, "bold")).pack(anchor=tk.W)
        self.rm_stock_mix_canvas = tk.Canvas(mix_card, height=43, background="white", highlightthickness=0)
        self.rm_stock_mix_canvas.pack(fill=tk.X, pady=(10, 7))
        self.rm_stock_mix_canvas.bind("<Configure>", self._draw_rm_stock_mix)
        self.rm_stock_mix_legend = tk.Frame(mix_card, background="white")
        self.rm_stock_mix_legend.pack(fill=tk.X)
        self.rm_stock_mix_labels: dict[str, tk.StringVar] = {}
        for column, size_class in enumerate(RM_STOCK_CARD_CLASSES):
            self.rm_stock_mix_legend.columnconfigure(column, weight=1)
            item = tk.Frame(self.rm_stock_mix_legend, background="white")
            item.grid(row=0, column=column, sticky="ew")
            tk.Label(item, text="●", background="white", foreground=RM_STOCK_DISTRIBUTION_COLORS[size_class],
                     font=("Segoe UI", 14, "bold")).pack(side=tk.LEFT)
            variable = tk.StringVar(value=f"{size_class}\n0 kg\n0%")
            self.rm_stock_mix_labels[size_class] = variable
            tk.Label(item, textvariable=variable, background="white", foreground="#28384f", justify=tk.LEFT,
                     font=("Segoe UI", 9, "bold")).pack(side=tk.LEFT, padx=(4, 0))

        market_card = self._balance_card(analysis)
        market_card.grid(row=0, column=1, sticky="nsew", padx=(5, 0))
        tk.Label(market_card, text="Market allocation (kg)", bg="white", fg="#27384f",
                 font=("Segoe UI", 10, "bold")).pack(anchor=tk.W)
        self.rm_stock_market_canvas = tk.Canvas(market_card, height=158, background="white", highlightthickness=0)
        self.rm_stock_market_canvas.pack(fill=tk.X, pady=(5, 0))
        self.rm_stock_market_canvas.bind("<Configure>", self._draw_rm_stock_market_allocation)

        ledger_card = tk.Frame(page, background="white", highlightbackground="#d7e0ea", highlightthickness=1,
                               padx=10, pady=9)
        ledger_card.pack(fill=tk.BOTH, expand=True)
        ledger_toolbar = tk.Frame(ledger_card, background="white")
        ledger_toolbar.pack(fill=tk.X, pady=(0, 8))
        tk.Label(ledger_toolbar, text="Arrival ledger", background="white", foreground="#27384f",
                 font=("Segoe UI", 12, "bold")).pack(side=tk.LEFT, padx=(0, 16))
        ttk.Entry(ledger_toolbar, textvariable=self.rm_stock_search_var, width=23).pack(side=tk.LEFT)
        ttk.Label(ledger_toolbar, text="From").pack(side=tk.LEFT, padx=(12, 4))
        ttk.Entry(ledger_toolbar, textvariable=self.rm_stock_from_var, width=12).pack(side=tk.LEFT)
        ttk.Label(ledger_toolbar, text="To").pack(side=tk.LEFT, padx=(12, 4))
        ttk.Entry(ledger_toolbar, textvariable=self.rm_stock_to_var, width=12).pack(side=tk.LEFT)
        ttk.Label(ledger_toolbar, text="Class").pack(side=tk.LEFT, padx=(12, 4))
        self.rm_stock_class_combo = ttk.Combobox(
            ledger_toolbar, textvariable=self.rm_stock_class_var,
            values=("All", *RM_STOCK_CARD_CLASSES), state="readonly", width=9,
        )
        self.rm_stock_class_combo.pack(side=tk.LEFT)
        ttk.Button(ledger_toolbar, text="Reset", command=self._reset_rm_stock_filters).pack(side=tk.RIGHT)

        table_frame = tk.Frame(ledger_card, background="white")
        table_frame.pack(fill=tk.BOTH, expand=True)
        self.rm_stock_ledger_rows = ()
        self.rm_stock_ledger_canvas = tk.Canvas(
            table_frame, background="white", highlightthickness=0, borderwidth=0,
        )
        vertical = ttk.Scrollbar(table_frame, orient=tk.VERTICAL, command=self.rm_stock_ledger_canvas.yview)
        horizontal = ttk.Scrollbar(table_frame, orient=tk.HORIZONTAL, command=self.rm_stock_ledger_canvas.xview)
        self.rm_stock_ledger_canvas.configure(yscrollcommand=vertical.set, xscrollcommand=horizontal.set)
        self.rm_stock_ledger_canvas.grid(row=0, column=0, sticky="nsew")
        vertical.grid(row=0, column=1, sticky="ns")
        horizontal.grid(row=1, column=0, sticky="ew")
        table_frame.rowconfigure(0, weight=1)
        table_frame.columnconfigure(0, weight=1)
        self.rm_stock_ledger_canvas.bind("<Configure>", self._draw_rm_stock_ledger)
        tk.Label(page, textvariable=self.rm_timeline_status_var, background="#f7f9fc", foreground="#64748b",
                 anchor=tk.W, font=("Segoe UI", 9)).pack(fill=tk.X, pady=(7, 0))

        for variable in (self.rm_stock_search_var, self.rm_stock_from_var, self.rm_stock_to_var):
            variable.trace_add("write", lambda *_args: self._refresh_rm_timeline())
        self.rm_stock_class_var.trace_add("write", lambda *_args: self._refresh_rm_timeline())
        self.rm_stock_source_var.trace_add("write", lambda *_args: self._refresh_rm_timeline())
        self._refresh_rm_timeline()

    @staticmethod
    def _balance_card(parent: tk.Misc) -> tk.Frame:
        return tk.Frame(parent, background="white", highlightbackground="#d7e0ea", highlightthickness=1,
                        padx=14, pady=11)

    def _open_stock_editor(self) -> None:
        self._new_assortment_actual_form()
        self._show_rm_section("actual")

    def _reset_rm_stock_filters(self) -> None:
        self.rm_stock_source_var.set("All")
        self.rm_stock_search_var.set("")
        self.rm_stock_class_var.set("All")
        records = tuple(self.assortment_actual_records.values())
        dates = sorted(record.record_date for record in records)
        self.rm_stock_from_var.set(dates[0] if dates else "")
        self.rm_stock_to_var.set(dates[-1] if dates else "")

    def _filtered_rm_stock_records(self):
        records = tuple(self.assortment_actual_records.values())
        source = self.rm_stock_source_var.get().strip()
        search = self.rm_stock_search_var.get().strip().casefold()
        selected_class = self.rm_stock_class_var.get().strip()
        try:
            start = date.fromisoformat(self.rm_stock_from_var.get().strip()) if self.rm_stock_from_var.get().strip() else None
            end = date.fromisoformat(self.rm_stock_to_var.get().strip()) if self.rm_stock_to_var.get().strip() else None
        except ValueError:
            return (), "Date filters must use YYYY-MM-DD."
        ranges = self._current_assortment_size_range_definitions()
        filtered = []
        for record in records:
            record_day = date.fromisoformat(record.record_date)
            if (start and record_day < start) or (end and record_day > end):
                continue
            if source != "All" and record.source_label != source:
                continue
            if search and search not in record.source_label.casefold():
                continue
            if selected_class != "All" and self._record_class_totals(record, ranges)[selected_class] <= 0:
                continue
            filtered.append(record)
        return tuple(filtered), ""

    def _record_class_totals(self, record, ranges) -> dict[str, float]:
        totals = {size_class: 0.0 for size_class in RM_STOCK_DISPLAY_CLASSES}
        for entry in aggregate_entries_by_size_class(record.entries, ranges):
            totals[entry.size_class] += float(entry.weight)
        return totals

    def _draw_rm_stock_mix(self, _event: tk.Event | None = None) -> None:
        canvas = self.rm_stock_mix_canvas
        canvas.delete("all")
        width, height = max(canvas.winfo_width(), 1), max(canvas.winfo_height(), 1)
        percentages = stock_distribution_percentages(*self.rm_stock_mix_weights)
        left = 0.0
        for index, (size_class, percentage) in enumerate(zip(RM_STOCK_DISPLAY_CLASSES, percentages)):
            right = width if index == len(percentages) - 1 else left + width * percentage / 100
            canvas.create_rectangle(left, 0, right, height, fill=RM_STOCK_DISTRIBUTION_COLORS[size_class], outline="white")
            if percentage > 7 and right - left > 54:
                canvas.create_text((left + right) / 2, height / 2, text=f"{percentage:.1f}%", fill="white",
                                   font=("Segoe UI", 9, "bold"))
            left = right

    def _draw_rm_stock_market_allocation(self, _event: tk.Event | None = None) -> None:
        canvas = self.rm_stock_market_canvas
        canvas.delete("all")
        width = max(canvas.winfo_width(), 1)
        headers = ("Size class", "Domestic", "Export", "Total")
        columns = (0, int(width * .18), int(width * .54), int(width * .84), width)
        for index, label in enumerate(headers):
            canvas.create_rectangle(columns[index], 0, columns[index + 1], 24, fill="#edf3f8", outline="#d7e0ea")
            canvas.create_text((columns[index] + columns[index + 1]) / 2, 12, text=label, fill="#34465b",
                               font=("Segoe UI", 8, "bold"))
        for row, size_class in enumerate(RM_STOCK_CARD_CLASSES, start=1):
            top, bottom = 24 + (row - 1) * 25, 24 + row * 25
            domestic = self.rm_stock_market_totals["domestic"][size_class]
            export = self.rm_stock_market_totals["export"][size_class]
            total = domestic + export
            for index in range(4):
                canvas.create_rectangle(columns[index], top, columns[index + 1], bottom, fill="white", outline="#e1e8ef")
            color = RM_STOCK_DISTRIBUTION_COLORS[size_class]
            canvas.create_text(9, (top + bottom) / 2, text=f"●  {size_class}", anchor="w", fill=color,
                               font=("Segoe UI", 8, "bold"))
            for value, left, right in ((domestic, columns[1], columns[2]), (export, columns[2], columns[3])):
                bar_left, bar_right = left + 9, right - 54
                canvas.create_rectangle(bar_left, top + 7, bar_right, bottom - 7, fill="#e8edf3", outline="")
                if total > 0:
                    canvas.create_rectangle(bar_left, top + 7, bar_left + (bar_right - bar_left) * value / total,
                                            bottom - 7, fill=color, outline="")
                canvas.create_text(right - 6, (top + bottom) / 2, text=self._format_optional_number(value),
                                   anchor="e", fill="#334155", font=("Segoe UI", 8))
            canvas.create_text(columns[4] - 7, (top + bottom) / 2, text=self._format_optional_number(total),
                               anchor="e", fill="#1e293b", font=("Segoe UI", 8, "bold"))

    def _draw_rm_stock_ledger(self, _event: tk.Event | None = None) -> None:
        """Render the arrival ledger as a compact dashboard grid, including class bars."""
        canvas = self.rm_stock_ledger_canvas
        canvas.delete("all")
        rows = getattr(self, "rm_stock_ledger_rows", ())
        width = max(canvas.winfo_width(), 1120)
        header_height, row_height = 29, 33
        total_height = header_height + max(len(rows), 1) * row_height + 1
        canvas.configure(scrollregion=(0, 0, width, total_height))

        columns = (0, .105, .29, .39, .53, .87, 1)
        x = tuple(round(width * position) for position in columns)
        headings = ("Date ↓", "Farm / Source", "Record type", "Incoming (kg)",
                    "Class allocation (kg)", "Cumulative (kg)")
        for index, heading in enumerate(headings):
            canvas.create_rectangle(x[index], 0, x[index + 1], header_height,
                                    fill="#eff5fa", outline="#d9e4ee")
            canvas.create_text(
                (x[index] + x[index + 1]) / 2, header_height / 2, text=heading,
                fill="#3c4e63", font=("Segoe UI", 8, "bold"),
            )

        row_fills = {
            "actual": "#f8fcff", "existing": "#f5f7f9", "prediction": "#fffaf0",
        }
        type_chips = {
            "actual": ("#2f80ed", "white"),
            "existing": ("#d8e0e9", "#334155"),
            "prediction": ("#fde1a2", "#8a5b00"),
        }
        for index, row in enumerate(rows):
            top = header_height + index * row_height
            bottom = top + row_height
            fill = "#dceeff" if row["is_current"] else row_fills.get(row["record_type"], "white")
            canvas.create_rectangle(0, top, width, bottom, fill=fill, outline="#dfe8f0")
            for divider in x[1:-1]:
                canvas.create_line(divider, top, divider, bottom, fill="#e4ebf1")
            middle = (top + bottom) / 2
            canvas.create_text(x[0] + 18, middle, text=row["date"], anchor="w", fill="#213b5a",
                               font=("Segoe UI", 8, "bold" if row["is_current"] else "normal"))
            canvas.create_text(x[1] + 18, middle, text=row["source"], anchor="w", fill="#23364d",
                               font=("Segoe UI", 8))

            label = RECORD_TYPE_LABELS.get(row["record_type"], row["record_type"].title())
            chip_fill, chip_text = type_chips.get(row["record_type"], ("#e5e7eb", "#334155"))
            chip_width = max(58, len(label) * 6 + 20)
            chip_left = x[2] + (x[3] - x[2] - chip_width) / 2
            canvas.create_rectangle(chip_left, top + 7, chip_left + chip_width, bottom - 7,
                                    fill=chip_fill, outline="")
            canvas.create_text(chip_left + chip_width / 2, middle, text=label, fill=chip_text,
                               font=("Segoe UI", 8, "bold"))
            canvas.create_text(x[4] - 17, middle, text=self._format_optional_number(row["incoming"]),
                               anchor="e", fill="#223955", font=("Segoe UI", 8, "bold"))

            totals = row["totals"]
            allocation_total = sum(totals[size_class] for size_class in RM_STOCK_CARD_CLASSES)
            bar_left, bar_right = x[4] + 16, x[5] - 22
            if allocation_total > 0:
                left = bar_left
                for size_class in RM_STOCK_CARD_CLASSES:
                    amount = totals[size_class]
                    if amount <= 0:
                        continue
                    right = left + (bar_right - bar_left) * amount / allocation_total
                    canvas.create_rectangle(left, top + 7, right, bottom - 7,
                                            fill=RM_STOCK_DISTRIBUTION_COLORS[size_class], outline="")
                    if right - left >= 38:
                        canvas.create_text((left + right) / 2, middle,
                                           text=self._format_optional_number(amount), fill="white",
                                           font=("Segoe UI", 7, "bold"))
                    left = right
            else:
                canvas.create_rectangle(bar_left, top + 7, bar_right, bottom - 7,
                                        fill="#e6edf3", outline="")
                canvas.create_text((bar_left + bar_right) / 2, middle, text="Unused", fill="#64748b",
                                   font=("Segoe UI", 8))
            canvas.create_text(x[6] - 18, middle, text=self._format_optional_number(row["cumulative"]),
                               anchor="e", fill="#223955", font=("Segoe UI", 8, "bold"))

    def _refresh_rm_timeline(self, _event: tk.Event | None = None) -> None:
        if not hasattr(self, "rm_stock_ledger_canvas"):
            return
        try:
            records, filter_error = self._filtered_rm_stock_records()
            if filter_error:
                raise ValueError(filter_error)
            ranges = self._current_assortment_size_range_definitions()
            rows = build_rm_timeline(records, ranges, wonton_weight_settings=self.wonton_weight_settings)
            market_rows = {
                market: build_rm_timeline(records, ranges, market_type=market,
                                          wonton_weight_settings=self.wonton_weight_settings)
                for market in ("domestic", "export")
            }
        except ValueError as exc:
            self.rm_stock_ledger_rows = ()
            self.rm_stock_ledger_canvas.after_idle(self._draw_rm_stock_ledger)
            self.rm_stock_as_of_var.set("Unavailable")
            self.rm_stock_total_var.set("—")
            self.rm_stock_unused_var.set("—")
            self.rm_timeline_status_var.set(str(exc))
            return

        all_sources = sorted({record.source_label for record in self.assortment_actual_records.values()}, key=str.casefold)
        source_values = ("All", *all_sources)
        if tuple(self.rm_stock_source_combo.cget("values")) != source_values:
            self.rm_stock_source_combo.configure(values=source_values)
        all_dates = sorted(record.record_date for record in self.assortment_actual_records.values())
        if all_dates and not self.rm_stock_from_var.get():
            self.rm_stock_from_var.set(all_dates[0])
        if all_dates and not self.rm_stock_to_var.get():
            self.rm_stock_to_var.set(all_dates[-1])

        cumulative_by_date = {row.record_date: row.cumulative_kg for row in rows}
        ledger_rows = []
        for index, record in enumerate(sorted(records, key=lambda item: (item.record_date, item.record_id), reverse=True)):
            totals = self._record_class_totals(record, ranges)
            ledger_rows.append({
                "date": record.record_date,
                "source": record.source_label,
                "record_type": record.record_type,
                "incoming": float(record.total_weight),
                "totals": totals,
                "cumulative": cumulative_by_date.get(record.record_date, 0.0),
                "is_current": bool(rows and record.record_date == rows[-1].record_date),
            })
        self.rm_stock_ledger_rows = tuple(ledger_rows)
        if rows:
            final = rows[-1]
            self.rm_stock_as_of_var.set(final.record_date)
            self.rm_stock_total_var.set(f"{self._format_optional_number(final.cumulative_kg)} kg")
            self.rm_stock_unused_var.set(f"{self._format_size_class_summary(final.unused_stock)} kg")
            self.rm_stock_mix_weights = (
                final.m_stock.total, final.s_stock.total, final.ss_stock.total,
                final.hc_stock.total, final.bk_stock.total, final.unused_stock.total,
            )
            percentages = stock_distribution_percentages(*self.rm_stock_mix_weights)
            for size_class, summary in {
                "M": final.m_stock, "S": final.s_stock, "SS": final.ss_stock,
                "HC": final.hc_stock, "BK": final.bk_stock,
            }.items():
                percentage = percentages[RM_STOCK_DISPLAY_CLASSES.index(size_class)]
                self.rm_stock_mix_labels[size_class].set(
                    f"{size_class}\n{self._format_size_class_summary(summary)} kg\n{percentage:.1f}%"
                )
                for market, filtered_rows in market_rows.items():
                    market_summary = getattr(filtered_rows[-1], f"{size_class.lower()}_stock") if filtered_rows else SizeClassWeightSummary(0)
                    self.rm_stock_market_totals[market][size_class] = market_summary.total
            self.rm_timeline_status_var.set(
                f"{len(records):,} RM arrival records • {len(rows):,} dates • Stock is before Plan usage."
            )
        else:
            self.rm_stock_as_of_var.set("—")
            self.rm_stock_total_var.set("0 kg")
            self.rm_stock_unused_var.set("0 kg")
            self.rm_stock_mix_weights = tuple(0.0 for _ in RM_STOCK_DISPLAY_CLASSES)
            for size_class in RM_STOCK_CARD_CLASSES:
                self.rm_stock_mix_labels[size_class].set(f"{size_class}\n0 kg\n0%")
                for market in ("domestic", "export"):
                    self.rm_stock_market_totals[market][size_class] = 0.0
            self.rm_timeline_status_var.set("No RM stock records for these filters.")
        self.rm_stock_mix_canvas.after_idle(self._draw_rm_stock_mix)
        self.rm_stock_market_canvas.after_idle(self._draw_rm_stock_market_allocation)
        self.rm_stock_ledger_canvas.after_idle(self._draw_rm_stock_ledger)
