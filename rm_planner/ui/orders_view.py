"""OrdersView screen behavior."""

from __future__ import annotations

from .common import *  # shared UI types, domain services, and display constants


class OrdersViewMixin:
    def _load_default_workbook(self) -> None:
        candidate = PROJECT_ROOT / "Data" / "Order" / "แผน.xlsx"
        if candidate.is_file():
            self.file_var.set(str(candidate))
            self._load_sheets()
        else:
            self.file_var.set(str(candidate))
            self.status_var.set(f"Order workbook not found: {candidate}")

    def _browse(self) -> None:
        selected = filedialog.askopenfilename(
            title="Select production plan workbook",
            filetypes=[("Excel workbook", "*.xlsx *.xlsm"), ("All files", "*.*")],
        )
        if selected:
            self.file_var.set(selected)
            self._load_sheets()

    def _load_sheets(self) -> None:
        try:
            workbook_path = self.file_var.get().strip()
            sheets = list_sheets(workbook_path)
            default_sheet = choose_default_sheet(workbook_path)
            self.sheet_combo.configure(values=sheets)
            self.sheet_var.set(default_sheet)
            self.status_var.set(f"Loaded {len(sheets)} worksheets. Suggested: {default_sheet.strip()}")
        except Exception as exc:
            self.sheet_combo.configure(values=[])
            self.sheet_var.set("")
            self.status_var.set("Could not read workbook.")
            messagebox.showerror("Workbook error", str(exc))

    def _start_extraction(self) -> None:
        if not self.file_var.get().strip() or not self.sheet_var.get():
            messagebox.showwarning("Missing source", "Please select an Excel file and worksheet.")
            return
        self.extract_button.configure(state=tk.DISABLED)
        self.status_var.set("Extracting data…")
        threading.Thread(target=self._extract_worker, daemon=True).start()

    def _extract_worker(self) -> None:
        try:
            result = extract_orders(self.file_var.get().strip(), self.sheet_var.get())
            self.after(0, self._show_result, result)
        except Exception as exc:
            self.after(0, self._show_error, exc)

    def _show_result(self, result: ExtractionResult) -> None:
        auto_save_note = ""
        if result.header_row != 0:
            try:
                merged_records, added = merge_order_records(
                    self.saved_orders_file_path,
                    result.records,
                )
            except ValueError as exc:
                merged_records = result.records
                auto_save_note = f" Orders could not be auto-saved: {exc}"
            else:
                existing = len(merged_records) - added
                result = ExtractionResult(
                    records=merged_records,
                    issues=result.issues,
                    sheet_name=result.sheet_name,
                    header_row=result.header_row,
                )
                self.saved_order_records = {
                    record.record_id: record for record in merged_records
                }
                auto_save_note = (
                    f" Auto-saved {added:,} new orders; kept {existing:,} existing orders."
                )
        self._sync_order_classes(result.records)
        self.result = result
        self.order_records_by_id = {record.record_id: record for record in result.records}
        for key, _label in FILTER_SPECS:
            self.order_filter_selections[key] = ALL_FILTER
            self.order_filter_options[key] = filter_options(result.records, key)
        for button in self.order_action_buttons:
            button.configure(state=tk.NORMAL)
        self.extract_button.configure(state=tk.NORMAL)
        if result.header_row == 0:
            self.status_var.set(f"Loaded {len(result.records):,} locally saved orders.")
        else:
            self.status_var.set(
                f"Complete. Header row {result.header_row}; "
                f"{len(result.issues):,} incomplete/non-order rows skipped."
                f"{auto_save_note}"
            )
        self._refresh_preview()

    def _show_error(self, exc: Exception) -> None:
        self.extract_button.configure(state=tk.NORMAL)
        self.status_var.set("Extraction failed.")
        messagebox.showerror("Extraction error", str(exc))

    def _refresh_preview(self, changed_key: str | None = None) -> None:
        self.tree.delete(*self.tree.get_children())
        if not self.result:
            return
        filter_keys = tuple(key for key, _label in FILTER_SPECS)
        base_records = self.result.records
        if self.hide_past_orders:
            base_records = current_and_future_orders(base_records, date.today())
        selections, available_options = cascading_filter_state(
            base_records,
            self.order_filter_selections,
            filter_keys,
            preferred_key=changed_key,
        )
        for key in filter_keys:
            self.order_filter_selections[key] = selections[key]
            self.order_filter_options[key] = available_options[key]
        records = filter_orders(
            base_records,
            selections,
        )
        records = sort_orders(
            records,
            self.order_sort_column,
            self.order_sort_descending,
        )
        self._update_order_summary(records)
        for index, record in enumerate(records):
            item_id = record.record_id or f"order_{index}"
            self.tree.insert(
                "",
                tk.END,
                iid=item_id,
                values=(
                    record.prod_date_display,
                    record.load_date_display,
                    record.order_no,
                    record.country,
                    record.customer_name,
                    record.group_1,
                    record.group_2,
                    record.packaging,
                    record.rm_size,
                    record.soup,
                    self._format_optional_number(record.wontons_per_cup),
                    self._format_optional_number(record.order_unit),
                    self._format_optional_number(record.order_cups),
                    self._format_optional_number(record.cups_per_unit),
                    self._format_optional_number(record.total_wontons),
                    self._format_optional_number(record.ho_weight_kg),
                    self._format_optional_number(record.production),
                ),
            )
        filters_active = any(
            selection != ALL_FILTER
            for selection in self.order_filter_selections.values()
        )
        self.clear_order_filters_button.configure(
            state=tk.NORMAL if filters_active else tk.DISABLED
        )
        self._update_order_column_headings()

    def _set_order_sort(self, column: str, descending: bool) -> None:
        self.order_sort_column = column
        self.order_sort_descending = descending
        self._close_order_filter_popup()
        self._refresh_preview()

    def _update_order_column_headings(self) -> None:
        for column, heading in self.order_headings.items():
            filter_key = ORDER_COLUMN_FILTER_KEYS.get(column)
            filter_active = bool(
                filter_key
                and self.order_filter_selections[filter_key] != ALL_FILTER
            )
            filter_marker = " ●" if filter_active else ""
            sort_marker = ""
            if column == self.order_sort_column or (
                column == "date" and self.order_sort_column == SCHEDULE_DATE_COLUMN
            ) or (
                column == "prod_date" and self.order_sort_column == PROD_SCHEDULE_DATE_COLUMN
            ):
                sort_marker = " ↓" if self.order_sort_descending else " ↑"
            self.tree.heading(
                column,
                text=f"{heading}{filter_marker}{sort_marker} ▾",
            )

    def _open_order_column_filter(self, column: str) -> None:
        self._close_order_filter_popup()
        popup = tk.Toplevel(self)
        self._order_filter_popup = popup
        # A borderless Toplevel otherwise maps at (0, 0) on Windows before its
        # requested size is known. Keep it hidden until final placement.
        popup.withdraw()
        popup.transient(self)
        popup.overrideredirect(True)
        popup.resizable(False, False)
        popup.bind("<Escape>", lambda _event: self._close_order_filter_popup())

        border = tk.Frame(popup, background="#7a7a7a", padx=1, pady=1)
        border.pack(fill=tk.BOTH, expand=True)
        body = tk.Frame(border, background="white", padx=8, pady=8)
        body.pack(fill=tk.BOTH, expand=True)

        def menu_button(
            text: str,
            command: Callable[[], object],
            state: str = tk.NORMAL,
        ) -> tk.Button:
            button = tk.Button(
                body,
                text=text,
                command=command,
                state=state,
                anchor=tk.W,
                background="white",
                activebackground="#e5f1fb",
                relief=tk.FLAT,
                borderwidth=0,
                padx=6,
                pady=4,
            )
            button.pack(fill=tk.X)
            return button

        sort_column = (
            PROD_SCHEDULE_DATE_COLUMN if column == "prod_date"
            else SCHEDULE_DATE_COLUMN if column == "date"
            else column
        )
        numeric = column in NUMERIC_ORDER_COLUMNS
        is_date_column = column in ("date", "prod_date")
        ascending_label = (
            "↑  Sort Oldest to Newest"
            if is_date_column
            else "↑  Sort Smallest to Largest"
            if numeric
            else "A  Z  Sort A to Z"
        )
        descending_label = (
            "↓  Sort Newest to Oldest"
            if is_date_column
            else "↓  Sort Largest to Smallest"
            if numeric
            else "Z  A  Sort Z to A"
        )
        menu_button(
            ascending_label,
            lambda: self._set_order_sort(sort_column, False),
        )
        menu_button(
            descending_label,
            lambda: self._set_order_sort(sort_column, True),
        )

        filter_key = ORDER_COLUMN_FILTER_KEYS.get(column)
        if filter_key:
            current_selection = self.order_filter_selections[filter_key]
            filter_active = current_selection != ALL_FILTER
            tk.Frame(body, height=1, background="#d0d0d0").pack(fill=tk.X, pady=5)
            menu_button(
                f'Clear Filter From "{self.order_headings[column]}"',
                lambda: self._set_order_column_filter(filter_key, ALL_FILTER),
                state=tk.NORMAL if filter_active else tk.DISABLED,
            )

            available_values = list(self.order_filter_options.get(filter_key, []))
            if current_selection == ALL_FILTER:
                checked_values = set(available_values)
            elif isinstance(current_selection, str):
                checked_values = {current_selection}
            else:
                checked_values = set(current_selection)

            search_var = tk.StringVar()
            search_entry = tk.Entry(
                body,
                textvariable=search_var,
                width=38,
                relief=tk.SOLID,
                borderwidth=1,
            )
            search_entry.pack(fill=tk.X, pady=(8, 5))

            list_frame = tk.Frame(body, background="white")
            list_frame.pack(fill=tk.BOTH, expand=True)
            values_list = tk.Listbox(
                list_frame,
                height=11,
                width=42,
                exportselection=False,
                selectmode=tk.BROWSE,
                activestyle="none",
                relief=tk.SOLID,
                borderwidth=1,
            )
            scrollbar = ttk.Scrollbar(
                list_frame,
                orient=tk.VERTICAL,
                command=values_list.yview,
            )
            values_list.configure(yscrollcommand=scrollbar.set)
            values_list.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
            displayed_values: list[str] = []
            ok_button: ttk.Button | None = None

            def refresh_values(*_args: object) -> None:
                query = search_var.get().strip().casefold()
                displayed_values[:] = [
                    value
                    for value in available_values
                    if not query or query in value.casefold()
                ]
                values_list.delete(0, tk.END)
                displayed_set = set(displayed_values)
                selected_displayed = checked_values & displayed_set
                if displayed_values and selected_displayed == displayed_set:
                    select_all_mark = "☑"
                elif selected_displayed:
                    select_all_mark = "▣"
                else:
                    select_all_mark = "☐"
                values_list.insert(tk.END, f"{select_all_mark}  (Select All)")
                for value in displayed_values:
                    mark = "☑" if value in checked_values else "☐"
                    values_list.insert(tk.END, f"{mark}  {value}")
                if ok_button is not None:
                    ok_button.configure(
                        state=tk.NORMAL if checked_values else tk.DISABLED
                    )

            def toggle_value(event: tk.Event) -> str:
                index = values_list.nearest(event.y)
                if index == 0:
                    visible = set(displayed_values)
                    if visible and visible.issubset(checked_values):
                        checked_values.difference_update(visible)
                    else:
                        checked_values.update(visible)
                elif 0 < index <= len(displayed_values):
                    value = displayed_values[index - 1]
                    if value in checked_values:
                        checked_values.remove(value)
                    else:
                        checked_values.add(value)
                refresh_values()
                values_list.selection_clear(0, tk.END)
                return "break"

            def apply_selected() -> None:
                if not checked_values:
                    return
                if checked_values == set(available_values):
                    selection: str | frozenset[str] = ALL_FILTER
                else:
                    selection = frozenset(checked_values)
                self.order_filter_selections[filter_key] = selection
                self._close_order_filter_popup()
                self._refresh_preview(filter_key)

            search_var.trace_add("write", refresh_values)
            popup.bind("<Return>", lambda _event: apply_selected())
            actions = ttk.Frame(body)
            actions.pack(fill=tk.X, pady=(8, 0))
            ttk.Button(
                actions,
                text="Cancel",
                command=self._close_order_filter_popup,
            ).pack(side=tk.RIGHT)
            ok_button = ttk.Button(actions, text="OK", command=apply_selected)
            ok_button.pack(side=tk.RIGHT, padx=(0, 6))
            refresh_values()
            values_list.bind("<Button-1>", toggle_value)
            search_entry.focus_set()
        else:
            tk.Frame(body, height=1, background="#d0d0d0").pack(fill=tk.X, pady=5)
            menu_button("Close", self._close_order_filter_popup)

        popup.update_idletasks()
        popup_width = popup.winfo_reqwidth()
        popup_height = popup.winfo_reqheight()
        window_left = self.winfo_rootx()
        window_top = self.winfo_rooty()
        window_right = window_left + self.winfo_width()
        window_bottom = window_top + self.winfo_height()
        x = max(
            window_left,
            min(self.winfo_pointerx() - 16, window_right - popup_width),
        )
        y = max(
            window_top,
            min(self.winfo_pointery() + 16, window_bottom - popup_height),
        )
        popup.geometry(f"{popup_width}x{popup_height}+{x}+{y}")
        popup.deiconify()
        popup.lift()
        # Install after the header's current click has finished propagating;
        # otherwise that same click would immediately close the new popup.
        self.after_idle(self._enable_order_filter_outside_click, popup)

    def _enable_order_filter_outside_click(self, popup: tk.Toplevel) -> None:
        if self._order_filter_popup is not popup:
            return
        self._order_filter_outside_binding = self.bind(
            "<Button-1>",
            self._order_filter_clicked_outside,
            add="+",
        )

    def _set_order_column_filter(self, filter_key: str, value: str) -> None:
        self.order_filter_selections[filter_key] = value
        self._close_order_filter_popup()
        self._refresh_preview(filter_key)

    def _close_order_filter_popup(self) -> None:
        if self._order_filter_outside_binding is not None:
            self.unbind("<Button-1>", self._order_filter_outside_binding)
            self._order_filter_outside_binding = None
        if self._order_filter_popup is not None:
            try:
                self._order_filter_popup.destroy()
            except tk.TclError:
                pass
            self._order_filter_popup = None

    def _order_filter_clicked_outside(self, _event: tk.Event) -> None:
        self._close_order_filter_popup()

    def _clear_order_filters(self) -> None:
        self._close_order_filter_popup()
        for key in self.order_filter_selections:
            self.order_filter_selections[key] = ALL_FILTER
        self._refresh_preview()

    def _toggle_past_orders(self) -> None:
        self.hide_past_orders = not self.hide_past_orders
        self.past_orders_button.configure(
            text="Show past orders" if self.hide_past_orders else "Hide past orders"
        )
        self._refresh_preview()

    def _edit_production_cell(self, event: tk.Event) -> None:
        item_id = self.tree.identify_row(event.y)
        column_id = self.tree.identify_column(event.x)
        if not item_id or not column_id:
            return
        column_number = int(column_id.removeprefix("#"))
        columns = self.tree.cget("columns")
        if column_number < 1 or column_number > len(columns):
            return
        if columns[column_number - 1] != "production":
            return
        record = self.order_records_by_id.get(item_id)
        if record is None:
            return
        current = "" if record.production is None else self._format_optional_number(record.production)
        entered = simpledialog.askstring(
            "Production quantity",
            "Enter how much was produced. Leave blank to clear:",
            initialvalue=current,
            parent=self,
        )
        if entered is None:
            return
        cleaned = entered.strip().replace(",", "")
        if not cleaned:
            production = None
        else:
            try:
                production = float(cleaned)
            except ValueError:
                messagebox.showerror("Invalid production", "Production must be numeric or blank.")
                return
            if not math.isfinite(production) or production < 0:
                messagebox.showerror(
                    "Invalid production",
                    "Production must be a finite number greater than or equal to zero.",
                )
                return
            if production.is_integer():
                production = int(production)
        record.production = production
        self._refresh_preview()
        self.status_var.set("Production changed. Click Save orders to keep the change.")

    def _update_order_summary(self, records: list[OrderRecord]) -> None:
        if not self.result:
            return
        customers = {record.customer_name for record in records}
        months = {record.month_key for record in records}
        total_cups = sum(record.order_cups or 0 for record in records)
        total_wontons = sum(record.total_wontons or 0 for record in records)
        self.summary_var.set(
            f"{len(records):,} orders  |  {len(customers):,} customers  |  "
            f"{len(months):,} months  |  cups {total_cups:,.0f}  |  "
            f"wontons (จำนวนเกี๊ยว) {total_wontons:,.0f}"
        )

    def _save_orders(self) -> None:
        if not self.result:
            return
        try:
            save_order_records(self.saved_orders_file_path, self.result.records)
        except ValueError as exc:
            messagebox.showerror("Save orders", str(exc))
            return
        self.saved_order_records = {
            record.record_id: record for record in self.result.records
        }
        self.status_var.set(
            f"Saved {len(self.result.records):,} orders and production quantities locally."
        )

    def _load_saved_orders(self) -> None:
        try:
            records = load_order_records(self.saved_orders_file_path)
        except ValueError as exc:
            self.status_var.set(str(exc))
            return
        self.saved_order_records = {record.record_id: record for record in records}
        if records:
            self._show_result(
                ExtractionResult(
                    records=records,
                    issues=[],
                    sheet_name="Saved orders",
                    header_row=0,
                )
            )

    @staticmethod
    def _format_optional_number(value: int | float | None) -> str:
        if value is None:
            return ""
        return f"{value:,.2f}".rstrip("0").rstrip(".")
