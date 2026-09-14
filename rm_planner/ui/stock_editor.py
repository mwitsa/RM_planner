"""StockEditorMixin behavior."""

from __future__ import annotations

from .common import *  # shared UI types and domain services


class StockEditorMixin:
    def _build_assortment_actual_tab(self) -> None:
        today = date.today()
        self.actual_day_var = tk.StringVar(value=f"{today.day:02d}")
        self.actual_month_var = tk.StringVar(value=f"{today.month:02d}")
        self.actual_year_var = tk.StringVar(value=f"{today.year:04d}")
        self.actual_market_type_var = tk.StringVar(value=market_display_label("domestic"))
        self.actual_farm_name_var = tk.StringVar()
        self.actual_lot_var = tk.StringVar()
        self.stock_harvest_size_var = tk.StringVar()
        self.stock_harvest_weight_var = tk.StringVar()

        editor_header = ttk.Frame(self.assortment_actual_tab)
        editor_header.pack(fill=tk.X, pady=(0, 6))
        ttk.Button(
            editor_header,
            text="Back to Stock",
            command=lambda: self._show_rm_section("timeline"),
        ).pack(side=tk.RIGHT, anchor=tk.N)

        pane = ttk.Panedwindow(self.assortment_actual_tab, orient=tk.HORIZONTAL)
        pane.pack(fill=tk.BOTH, expand=True)
        form_panel = ttk.Frame(pane, padding=(0, 0, 10, 0))
        history_panel = ttk.Frame(pane, padding=(10, 0, 0, 0), width=650)
        pane.add(form_panel, weight=4)
        pane.add(history_panel, weight=5)

        details_frame = ttk.LabelFrame(form_panel, text="1. Stock details", padding=10)
        details_frame.pack(fill=tk.X, pady=(0, 12))
        details_frame.columnconfigure(0, weight=2)
        details_frame.columnconfigure(1, weight=1)

        ttk.Label(details_frame, text="Availability date").grid(
            row=0, column=0, sticky=tk.W, padx=(0, 12)
        )
        ttk.Label(details_frame, text="Use for").grid(
            row=0, column=1, sticky=tk.W
        )

        date_inputs = ttk.Frame(details_frame)
        date_inputs.grid(row=1, column=0, sticky="ew", padx=(0, 12), pady=(4, 0))
        ttk.Combobox(
            date_inputs,
            textvariable=self.actual_day_var,
            values=[f"{day:02d}" for day in range(1, 32)],
            state="readonly",
            width=5,
        ).pack(side=tk.LEFT)
        ttk.Label(date_inputs, text="/").pack(side=tk.LEFT, padx=4)
        ttk.Combobox(
            date_inputs,
            textvariable=self.actual_month_var,
            values=[f"{month:02d}" for month in range(1, 13)],
            state="readonly",
            width=5,
        ).pack(side=tk.LEFT)
        ttk.Label(date_inputs, text="/").pack(side=tk.LEFT, padx=4)
        ttk.Combobox(
            date_inputs,
            textvariable=self.actual_year_var,
            values=[str(year) for year in range(today.year - 5, today.year + 6)],
            width=7,
        ).pack(side=tk.LEFT)
        ttk.Combobox(
            details_frame,
            textvariable=self.actual_market_type_var,
            values=MARKET_DISPLAY_OPTIONS,
            state="readonly",
            width=10,
        ).grid(row=1, column=1, sticky="ew", pady=(4, 0))
        ttk.Label(details_frame, text="ชื่อฟาร์ม").grid(
            row=2, column=0, sticky=tk.W, padx=(0, 12), pady=(10, 0)
        )
        ttk.Label(details_frame, text="LOT").grid(
            row=2, column=1, sticky=tk.W, pady=(10, 0)
        )
        ttk.Entry(
            details_frame,
            textvariable=self.actual_farm_name_var,
        ).grid(row=3, column=0, sticky="ew", padx=(0, 12), pady=(4, 0))
        ttk.Entry(
            details_frame,
            textvariable=self.actual_lot_var,
        ).grid(row=3, column=1, sticky="ew", pady=(4, 0))

        std_fill_frame = ttk.LabelFrame(
            form_panel,
            text="2. Fill from Assortment STD (optional)",
            padding=10,
        )
        std_fill_frame.pack(fill=tk.X, pady=(0, 12))
        std_fill_frame.columnconfigure(4, weight=1)
        ttk.Label(std_fill_frame, text="Harvest size").grid(
            row=0, column=0, sticky=tk.W
        )
        self.stock_harvest_size_combo = ttk.Combobox(
            std_fill_frame,
            textvariable=self.stock_harvest_size_var,
            width=12,
        )
        self.stock_harvest_size_combo.grid(
            row=0, column=1, sticky=tk.W, padx=(6, 18)
        )
        ttk.Label(std_fill_frame, text="Total weight (kg)").grid(
            row=0, column=2, sticky=tk.W
        )
        ttk.Entry(
            std_fill_frame,
            textvariable=self.stock_harvest_weight_var,
            width=16,
        ).grid(row=0, column=3, sticky=tk.W, padx=(6, 18))
        ttk.Button(
            std_fill_frame,
            text="Calculate rows",
            command=self._fill_stock_from_assortment_std,
        ).grid(row=0, column=4, sticky=tk.E)
        ttk.Label(
            std_fill_frame,
            text=(
                "Uses STD percentages, then combines all output sizes into "
                "M, S, SS, and Unused class totals."
            ),
        ).grid(row=1, column=0, columnspan=5, sticky=tk.W, pady=(6, 0))

        form_actions = ttk.Frame(form_panel)
        form_actions.pack(fill=tk.X, pady=(0, 12))
        ttk.Button(
            form_actions,
            text="Clear / New stock",
            command=self._new_assortment_actual_form,
        ).pack(side=tk.LEFT)
        self.assortment_actual_save_button = ttk.Button(
            form_actions,
            text="Save stock",
            command=self._save_assortment_actual,
        )
        self.assortment_actual_save_button.pack(side=tk.RIGHT)

        box_header = ttk.Frame(form_panel)
        box_header.pack(fill=tk.X, pady=(0, 6))
        ttk.Label(box_header, text="3. Class and weight", style="Summary.TLabel").pack(side=tk.LEFT)
        self.assortment_entry_summary_var = tk.StringVar(value="1 row | Total 0 kg")
        ttk.Label(
            box_header,
            textvariable=self.assortment_entry_summary_var,
        ).pack(side=tk.LEFT, padx=(12, 0))

        ttk.Label(
            form_panel,
            text="Enter stock directly as M, S, SS, or Unused. Each class may be used once.",
        ).pack(anchor=tk.W, pady=(0, 6))

        entry_headings = ttk.Frame(form_panel, padding=(6, 5))
        entry_headings.pack(fill=tk.X)
        entry_headings.columnconfigure(1, weight=1)
        entry_headings.columnconfigure(2, weight=1)
        ttk.Label(entry_headings, text="#", width=4).grid(row=0, column=0, sticky=tk.W)
        ttk.Label(entry_headings, text="Class").grid(row=0, column=1, sticky=tk.W)
        ttk.Label(entry_headings, text="Weight (kg)").grid(row=0, column=2, sticky=tk.W)
        ttk.Label(entry_headings, text="", width=8).grid(row=0, column=3)

        list_container = ttk.Frame(form_panel)
        list_container.pack(fill=tk.BOTH, expand=True)
        list_container.rowconfigure(0, weight=1)
        list_container.columnconfigure(0, weight=1)

        self.assortment_actual_canvas = tk.Canvas(list_container, highlightthickness=0)
        actual_scrollbar = ttk.Scrollbar(
            list_container,
            orient=tk.VERTICAL,
            command=self.assortment_actual_canvas.yview,
        )
        self.assortment_actual_canvas.configure(yscrollcommand=actual_scrollbar.set)
        self.assortment_actual_canvas.grid(row=0, column=0, sticky="nsew")
        actual_scrollbar.grid(row=0, column=1, sticky="ns")

        self.assortment_actual_list = ttk.Frame(self.assortment_actual_canvas, padding=(2, 2, 8, 2))
        self.assortment_actual_window = self.assortment_actual_canvas.create_window(
            (0, 0),
            window=self.assortment_actual_list,
            anchor="nw",
        )
        self.assortment_actual_list.bind(
            "<Configure>",
            lambda _event: self.assortment_actual_canvas.configure(
                scrollregion=self.assortment_actual_canvas.bbox("all")
            ),
        )
        self.assortment_actual_canvas.bind(
            "<Configure>",
            lambda event: self.assortment_actual_canvas.itemconfigure(
                self.assortment_actual_window,
                width=event.width,
            ),
        )

        self.assortment_actual_add_row_footer = ttk.Frame(
            self.assortment_actual_list,
            padding=(6, 6, 6, 2),
        )
        self.assortment_actual_add_row_footer.pack(fill=tk.X)
        ttk.Button(
            self.assortment_actual_add_row_footer,
            text="+ Add row",
            command=self._add_assortment_actual_box,
        ).pack(fill=tk.X)

        self.assortment_actual_boxes: list[dict[str, object]] = []
        self._add_assortment_actual_box()

        ttk.Label(history_panel, text="Saved stock", style="Summary.TLabel").pack(anchor=tk.W)
        ttk.Label(history_panel, text="Double-click a record to load and edit it.").pack(
            anchor=tk.W, pady=(2, 12)
        )
        history_table = ttk.Frame(history_panel)
        history_table.pack(fill=tk.BOTH, expand=True)
        history_table.rowconfigure(0, weight=1)
        history_table.columnconfigure(0, weight=1)
        self.assortment_actual_history_tree = ttk.Treeview(
            history_table,
            columns=(
                "farm_name",
                "lot",
                "market",
                "date",
                "weight",
                "M",
                "S",
                "SS",
                "unused",
                "est_wonton",
            ),
            show="headings",
            selectmode="browse",
        )
        self.assortment_actual_history_tree.heading("farm_name", text="ชื่อฟาร์ม")
        self.assortment_actual_history_tree.heading("lot", text="LOT")
        self.assortment_actual_history_tree.heading("market", text="Use for")
        self.assortment_actual_history_tree.heading("date", text="Date")
        self.assortment_actual_history_tree.heading("weight", text="Total weight")
        self.assortment_actual_history_tree.heading("M", text="M (kg)")
        self.assortment_actual_history_tree.heading("S", text="S (kg)")
        self.assortment_actual_history_tree.heading("SS", text="SS (kg)")
        self.assortment_actual_history_tree.heading("unused", text="Unused (kg)")
        self.assortment_actual_history_tree.heading("est_wonton", text="Est. wonton")
        self.assortment_actual_history_tree.column("farm_name", width=130, anchor=tk.W)
        self.assortment_actual_history_tree.column("lot", width=100, anchor=tk.W)
        self.assortment_actual_history_tree.column("market", width=90, anchor=tk.CENTER)
        self.assortment_actual_history_tree.column("date", width=95, anchor=tk.CENTER)
        self.assortment_actual_history_tree.column("weight", width=95, anchor=tk.E)
        self.assortment_actual_history_tree.column("M", width=105, anchor=tk.E)
        self.assortment_actual_history_tree.column("S", width=105, anchor=tk.E)
        self.assortment_actual_history_tree.column("SS", width=105, anchor=tk.E)
        self.assortment_actual_history_tree.column("unused", width=90, anchor=tk.E)
        self.assortment_actual_history_tree.column("est_wonton", width=115, anchor=tk.E)
        history_scrollbar = ttk.Scrollbar(
            history_table,
            orient=tk.VERTICAL,
            command=self.assortment_actual_history_tree.yview,
        )
        history_horizontal = ttk.Scrollbar(
            history_table,
            orient=tk.HORIZONTAL,
            command=self.assortment_actual_history_tree.xview,
        )
        self.assortment_actual_history_tree.configure(
            yscrollcommand=history_scrollbar.set,
            xscrollcommand=history_horizontal.set,
        )
        self.assortment_actual_history_tree.grid(row=0, column=0, sticky="nsew")
        history_scrollbar.grid(row=0, column=1, sticky="ns")
        history_horizontal.grid(row=1, column=0, sticky="ew")
        self.assortment_actual_history_tree.bind(
            "<Double-1>", lambda _event: self._edit_selected_assortment_actual()
        )
        history_actions = ttk.Frame(history_panel)
        history_actions.pack(fill=tk.X, pady=(8, 0))
        ttk.Button(
            history_actions,
            text="Edit selected stock",
            command=self._edit_selected_assortment_actual,
        ).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 4))
        ttk.Button(
            history_actions,
            text="Delete selected stock",
            command=self._delete_selected_assortment_actual,
        ).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(4, 0))
        ttk.Label(
            self.assortment_actual_tab,
            textvariable=self.assortment_actual_status_var,
            relief=tk.SUNKEN,
            anchor=tk.W,
            padding=(6, 3),
        ).pack(fill=tk.X, pady=(8, 0))

    def _add_assortment_actual_box(
        self,
        size_class: str = "",
        weight: str = "",
    ) -> None:
        size_class_var = tk.StringVar(value=normalize_size_class(size_class))
        weight_var = tk.StringVar(value=weight)
        row_number_var = tk.StringVar()
        box = ttk.Frame(self.assortment_actual_list, padding=(6, 5))
        self.assortment_actual_add_row_footer.pack_forget()
        box.pack(fill=tk.X, pady=(0, 2))
        self.assortment_actual_add_row_footer.pack(fill=tk.X)
        box.columnconfigure(1, weight=1)
        box.columnconfigure(2, weight=1)

        ttk.Label(box, textvariable=row_number_var, width=4).grid(
            row=0, column=0, sticky=tk.W
        )
        ttk.Combobox(
            box,
            textvariable=size_class_var,
            values=(*SIZE_CLASSES, "Unused"),
            state="readonly",
        ).grid(row=0, column=1, sticky="ew", padx=(0, 12))
        ttk.Entry(box, textvariable=weight_var).grid(
            row=0, column=2, sticky="ew"
        )

        ttk.Button(
            box,
            text="Remove",
            command=lambda current_box=box: self._remove_assortment_actual_box(current_box),
        ).grid(row=0, column=3, sticky=tk.E, padx=(8, 0))

        box_entry: dict[str, object] = {
            "frame": box,
            "size_class": size_class_var,
            "weight": weight_var,
            "row_number": row_number_var,
        }
        size_class_var.trace_add(
            "write",
            lambda *_args: self._update_assortment_entry_summary(),
        )
        weight_var.trace_add(
            "write",
            lambda *_args: self._update_assortment_entry_summary(),
        )
        self.assortment_actual_boxes.append(box_entry)
        self._renumber_assortment_actual_boxes()
        self._update_assortment_entry_summary()
        self.assortment_actual_canvas.after_idle(
            lambda: self.assortment_actual_canvas.configure(
                scrollregion=self.assortment_actual_canvas.bbox("all")
            )
        )

    def _remove_assortment_actual_box(self, box: ttk.Frame) -> None:
        for index, entry in enumerate(self.assortment_actual_boxes):
            if entry["frame"] == box:
                box.destroy()
                self.assortment_actual_boxes.pop(index)
                break
        if not self.assortment_actual_boxes:
            self._add_assortment_actual_box()
        else:
            self._renumber_assortment_actual_boxes()
        self._update_assortment_entry_summary()

    def _renumber_assortment_actual_boxes(self) -> None:
        for number, entry in enumerate(self.assortment_actual_boxes, start=1):
            row_number = entry.get("row_number")
            if isinstance(row_number, tk.StringVar):
                row_number.set(str(number))

    def _update_assortment_entry_summary(self) -> None:
        if not hasattr(self, "assortment_entry_summary_var"):
            return
        completed_rows = 0
        total_weight = 0.0
        for entry in self.assortment_actual_boxes:
            size_class = entry["size_class"]
            weight = entry["weight"]
            if not all(isinstance(value, tk.StringVar) for value in (size_class, weight)):
                continue
            if size_class.get().strip() and weight.get().strip():
                completed_rows += 1
            try:
                total_weight += float(weight.get().strip().replace(",", "") or 0)
            except ValueError:
                continue
        row_label = "row" if completed_rows == 1 else "rows"
        self.assortment_entry_summary_var.set(
            f"{completed_rows} completed {row_label} | "
            f"Total {self._format_optional_number(total_weight)} kg"
        )

    def _current_assortment_size_range_definitions(
        self,
    ) -> tuple[AssortmentSizeRange, ...]:
        if not self.assortment_table:
            return ()
        return tuple(
            AssortmentSizeRange(
                size_class,
                self.assortment_table.output_sizes[self.assortment_size_ranges[size_class][0]],
                self.assortment_table.output_sizes[self.assortment_size_ranges[size_class][1]],
            )
            for size_class in SIZE_CLASSES
        )

    def _new_assortment_actual_form(self, set_status: bool = True) -> None:
        today = date.today()
        self.actual_day_var.set(f"{today.day:02d}")
        self.actual_month_var.set(f"{today.month:02d}")
        self.actual_year_var.set(f"{today.year:04d}")
        self._editing_actual_record_id = None
        self.actual_market_type_var.set(market_display_label("domestic"))
        self.actual_farm_name_var.set("")
        self.actual_lot_var.set("")
        self.stock_harvest_size_var.set("")
        self.stock_harvest_weight_var.set("")
        self.assortment_actual_save_button.configure(text="Save stock")
        self._set_assortment_actual_boxes([])
        if set_status:
            self.assortment_actual_status_var.set("New stock form ready.")

    def _set_assortment_actual_boxes(self, entries: list[ActualAssortmentEntry]) -> None:
        for box_entry in self.assortment_actual_boxes:
            frame = box_entry["frame"]
            if isinstance(frame, ttk.Frame):
                frame.destroy()
        self.assortment_actual_boxes.clear()
        if entries:
            class_entries = aggregate_entries_by_size_class(
                entries,
                self._current_assortment_size_range_definitions(),
            )
            for entry in class_entries:
                self._add_assortment_actual_box(
                    entry.size_class,
                    self._format_weight(entry.weight),
                )
        else:
            self._add_assortment_actual_box()

    def _collect_assortment_actual_entries(self) -> list[ActualAssortmentEntry]:
        entries: list[ActualAssortmentEntry] = []
        used_classes: set[str] = set()
        for number, box_entry in enumerate(self.assortment_actual_boxes, start=1):
            size_class_var = box_entry["size_class"]
            weight_var = box_entry["weight"]
            if not all(
                isinstance(value, tk.StringVar)
                for value in (size_class_var, weight_var)
            ):
                continue
            size_class = normalize_size_class(size_class_var.get())
            weight_text = weight_var.get().strip().replace(",", "")
            if not size_class and not weight_text:
                continue
            if not size_class or not weight_text:
                raise ValueError(f"Row {number} needs Class and Weight.")
            if size_class not in (*SIZE_CLASSES, "Unused"):
                raise ValueError(f"Row {number} has an invalid Class.")
            if size_class in used_classes:
                raise ValueError(f"Class {size_class} is already used in another row.")
            try:
                weight = float(weight_text)
            except ValueError as exc:
                raise ValueError(f"Row {number} has an invalid Weight.") from exc
            used_classes.add(size_class)
            entries.append(
                ActualAssortmentEntry(
                    size=size_class,
                    weight=weight,
                    size_class=size_class,
                )
            )
        return entries

    def _selected_assortment_actual_date(self) -> str:
        try:
            selected_date = date(
                int(self.actual_year_var.get()),
                int(self.actual_month_var.get()),
                int(self.actual_day_var.get()),
            )
        except ValueError as exc:
            raise ValueError("Choose a valid Date, Month, and Year.") from exc
        return selected_date.isoformat()

    def _save_assortment_actual(self) -> None:
        try:
            record = upsert_actual_record(
                self.assortment_actual_file_path,
                self._selected_assortment_actual_date(),
                self._collect_assortment_actual_entries(),
                record_id=self._editing_actual_record_id,
                record_type="actual",
                market_type=self.actual_market_type_var.get(),
                farm_name=self.actual_farm_name_var.get(),
                lot=self.actual_lot_var.get(),
            )
        except ValueError as exc:
            messagebox.showerror("Save stock", str(exc))
            return
        action = "Updated" if self._editing_actual_record_id else "Saved"
        self._load_assortment_actual_history()
        self._new_assortment_actual_form(set_status=False)
        self.assortment_actual_status_var.set(
            f"{action} stock {record.source_label} for "
            f"{market_display_label(record.market_type)} "
            f"with {len(record.entries)} entries "
            f"for {record.record_date}."
        )
        self.rm_timeline_status_var.set(
            f"{action} stock {record.source_label} for {record.record_date}."
        )
        self._show_rm_section("timeline")

    def _load_assortment_actual_history(self) -> None:
        try:
            records = load_actual_records(self.assortment_actual_file_path)
        except ValueError as exc:
            self.assortment_actual_status_var.set(str(exc))
            return
        self.assortment_actual_records = {record.record_id: record for record in records}
        self._refresh_assortment_actual_history_table()
        self._refresh_rm_timeline()
        # Plan proposals consume these stock records directly. Refresh them
        # whenever a stock record is saved, edited, deleted, or reloaded.
        if hasattr(self, "_proposal_vars"):
            self._plan_inputs_changed()
        assortment_count = len(records)
        if assortment_count:
            self.assortment_actual_status_var.set(
                f"Loaded {assortment_count} saved stock records."
            )

    def _refresh_assortment_actual_history_table(self) -> None:
        selected = set(self.assortment_actual_history_tree.selection())
        self.assortment_actual_history_tree.delete(
            *self.assortment_actual_history_tree.get_children()
        )
        for record in self._sorted_saved_stock_records(
            self.assortment_actual_records.values()
        ):
            class_summaries = self._assortment_record_class_summaries(record)
            estimated_wontons = self._format_optional_number(
                self._estimate_wontons_from_class_summaries(class_summaries)
            )
            self.assortment_actual_history_tree.insert(
                "",
                tk.END,
                iid=record.record_id,
                values=(
                    record.farm_name or "—",
                    record.lot or record.rm_id,
                    market_display_label(record.market_type),
                    record.record_date,
                    self._format_weight(record.total_weight),
                    self._format_size_class_summary(class_summaries["M"]),
                    self._format_size_class_summary(class_summaries["S"]),
                    self._format_size_class_summary(class_summaries["SS"]),
                    self._format_size_class_summary(class_summaries["Unused"]),
                    estimated_wontons,
                ),
            )
        for record_id in selected:
            if self.assortment_actual_history_tree.exists(record_id):
                self.assortment_actual_history_tree.selection_add(record_id)

    @staticmethod
    def _sorted_saved_stock_records(
        records: Iterable[ActualAssortmentRecord],
    ) -> tuple[ActualAssortmentRecord, ...]:
        """Return every saved stock record, including legacy class-only stock."""

        return tuple(
            sorted(
                records,
                key=lambda item: (item.record_date, item.updated_at),
                reverse=True,
            )
        )

    def _assortment_record_class_summaries(
        self,
        record: ActualAssortmentRecord,
    ) -> dict[str, SizeClassWeightSummary]:
        aggregated = aggregate_entries_by_size_class(
            record.entries,
            self._current_assortment_size_range_definitions(),
        )
        totals = {size_class: 0.0 for size_class in (*SIZE_CLASSES, "Unused")}
        for entry in aggregated:
            totals[entry.size_class] += float(entry.weight)
        return {
            size_class: SizeClassWeightSummary(totals[size_class])
            for size_class in (*SIZE_CLASSES, "Unused")
        }

    def _format_size_class_summary(self, summary: SizeClassWeightSummary) -> str:
        return self._format_weight(summary.total)

    def _estimate_wontons_from_class_summaries(
        self,
        summaries: dict[str, SizeClassWeightSummary],
    ) -> float:
        return sum(
            self.wonton_weight_settings.estimate_wontons(
                size_class,
                summaries[size_class].total,
            )
            for size_class in SIZE_CLASSES
        )

    def _edit_selected_assortment_actual(self) -> None:
        selected = self.assortment_actual_history_tree.selection()
        if not selected:
            messagebox.showwarning("No stock selected", "Select a saved stock record to edit.")
            return
        record = self.assortment_actual_records.get(selected[0])
        if not record:
            messagebox.showerror("Stock error", "The selected stock record could not be found.")
            return
        year, month, day = record.record_date.split("-")
        self.actual_day_var.set(day)
        self.actual_month_var.set(month)
        self.actual_year_var.set(year)
        self.actual_market_type_var.set(market_display_label(record.market_type))
        self.actual_farm_name_var.set(record.farm_name)
        self.actual_lot_var.set(record.lot)
        self.stock_harvest_size_var.set("")
        self.stock_harvest_weight_var.set("")
        self._set_assortment_actual_boxes(list(record.entries))
        self._editing_actual_record_id = record.record_id
        self.assortment_actual_save_button.configure(text="Update stock")
        self.assortment_actual_status_var.set(
            f"Editing saved stock {record.source_label} for {record.record_date}."
        )

    def _delete_selected_assortment_actual(self) -> None:
        selected = self.assortment_actual_history_tree.selection()
        if not selected:
            messagebox.showwarning("No stock selected", "Select a saved stock record to delete.")
            return
        record = self.assortment_actual_records.get(selected[0])
        if not record:
            messagebox.showerror("Stock error", "The selected stock record could not be found.")
            return
        confirmed = messagebox.askyesno(
            "Delete saved stock",
            f"Permanently delete stock {record.source_label} for {record.record_date}?"
            "\n\nThis cannot be undone.",
        )
        if not confirmed:
            return
        try:
            deleted = delete_actual_record(
                self.assortment_actual_file_path,
                record.record_id,
            )
        except ValueError as exc:
            messagebox.showerror("Delete saved stock", str(exc))
            return
        if self._editing_actual_record_id == deleted.record_id:
            self._new_assortment_actual_form(set_status=False)
        self._load_assortment_actual_history()
        self.assortment_actual_status_var.set(
            f"Deleted stock {deleted.source_label} for {deleted.record_date}."
        )
