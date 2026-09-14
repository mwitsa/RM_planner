"""DataView screen behavior."""

from __future__ import annotations

from .common import *  # shared UI types, domain services, and display constants


class DataViewMixin:
    def _build_data_tab(self) -> None:
        controls = ttk.Frame(self.data_tab)
        controls.pack(fill=tk.X, pady=(0, 8))
        ttk.Label(
            controls,
            text=(
                "Raw column B:AI from the workbook and worksheet selected on the Order "
                "tab, plus a computed น้ำหนัก HO column."
            ),
        ).pack(side=tk.LEFT)
        self.load_raw_data_button = ttk.Button(
            controls,
            text="Load raw data",
            command=self._start_raw_data_load,
        )
        self.load_raw_data_button.pack(side=tk.RIGHT)
        self.clear_raw_data_filters_button = ttk.Button(
            controls,
            text="Clear column filters",
            command=self._clear_raw_data_filters,
            state=tk.DISABLED,
        )
        self.clear_raw_data_filters_button.pack(side=tk.RIGHT, padx=(0, 8))

        table_frame = ttk.Frame(self.data_tab)
        table_frame.pack(fill=tk.BOTH, expand=True)
        raw_columns = [f"col_{column:02d}" for column in range(RAW_DATA_FIRST_COLUMN, RAW_DATA_LAST_COLUMN + 1)
                       if column not in RAW_DATA_EXCLUDED_COLUMNS]
        raw_columns.append("ho_weight")
        self.raw_data_columns = raw_columns
        self.raw_data_tree = ttk.Treeview(table_frame, columns=raw_columns, show="headings")
        column_letters = [
            get_column_letter(index)
            for index in range(RAW_DATA_FIRST_COLUMN, RAW_DATA_LAST_COLUMN + 1)
            if index not in RAW_DATA_EXCLUDED_COLUMNS
        ]
        column_letters.append("น้ำหนัก HO")
        self.raw_data_headers = column_letters
        for column, letter in zip(raw_columns, column_letters):
            self.raw_data_tree.heading(
                column,
                text=letter,
                command=lambda selected_column=column: self._open_data_column_filter(selected_column),
            )
            self.raw_data_tree.column(column, width=110, minwidth=60, anchor=tk.W)

        vertical = ttk.Scrollbar(table_frame, orient=tk.VERTICAL, command=self.raw_data_tree.yview)
        horizontal = ttk.Scrollbar(table_frame, orient=tk.HORIZONTAL, command=self.raw_data_tree.xview)
        self.raw_data_tree.configure(yscrollcommand=vertical.set, xscrollcommand=horizontal.set)
        self.raw_data_tree.grid(row=0, column=0, sticky="nsew")
        vertical.grid(row=0, column=1, sticky="ns")
        horizontal.grid(row=1, column=0, sticky="ew")
        table_frame.rowconfigure(0, weight=1)
        table_frame.columnconfigure(0, weight=1)

        status = ttk.Label(
            self.data_tab,
            textvariable=self.data_status_var,
            relief=tk.SUNKEN,
            anchor=tk.W,
            padding=(6, 3),
        )
        status.pack(fill=tk.X, pady=(8, 0))

    def _start_raw_data_load(self) -> None:
        if not self.file_var.get().strip() or not self.sheet_var.get():
            messagebox.showwarning("Missing source", "Please select an Excel file and worksheet on the Order tab.")
            return
        self.load_raw_data_button.configure(state=tk.DISABLED)
        self.data_status_var.set("Loading raw data…")
        threading.Thread(target=self._raw_data_worker, daemon=True).start()

    def _raw_data_worker(self) -> None:
        try:
            result = extract_raw_data(self.file_var.get().strip(), self.sheet_var.get())
            self.after(0, self._show_raw_data_result, result)
        except Exception as exc:
            self.after(0, self._show_raw_data_error, exc)

    def _show_raw_data_result(self, result: RawDataResult) -> None:
        self.raw_data_result = result
        self.raw_data_all_rows = result.rows
        self.raw_data_headers = result.headers
        self.raw_data_filter_selections = {key: ALL_FILTER for key in self.raw_data_columns}
        self.raw_data_sort_column = None
        self.raw_data_sort_descending = False
        self.load_raw_data_button.configure(state=tk.NORMAL)
        self._refresh_raw_data_table()
        self._refresh_plan_date_options()

    def _show_raw_data_error(self, exc: Exception) -> None:
        self.load_raw_data_button.configure(state=tk.NORMAL)
        self.data_status_var.set("Failed to load raw data.")
        messagebox.showerror("Raw data error", str(exc))

    def _raw_data_cell_value(self, row: tuple[str, ...], column_key: str) -> str:
        value = row[self.raw_data_columns.index(column_key)]
        return value if value else BLANK_FILTER

    def _raw_data_filtered_rows(self, exclude_column: str | None = None) -> list[tuple[str, ...]]:
        rows = self.raw_data_all_rows
        for key, selection in self.raw_data_filter_selections.items():
            if key == exclude_column or selection == ALL_FILTER:
                continue
            allowed = {selection} if isinstance(selection, str) else set(selection)
            rows = [row for row in rows if self._raw_data_cell_value(row, key) in allowed]
        return rows

    def _raw_data_filter_options(self, column_key: str) -> list[str]:
        candidates = self._raw_data_filtered_rows(exclude_column=column_key)
        values = {self._raw_data_cell_value(row, column_key) for row in candidates}
        return sorted(values, key=lambda value: (value == BLANK_FILTER, value.casefold()))

    def _raw_data_column_is_numeric(self, column_key: str) -> bool:
        index = self.raw_data_columns.index(column_key)
        saw_value = False
        for row in self.raw_data_all_rows:
            value = row[index]
            if not value:
                continue
            saw_value = True
            try:
                float(value.replace(",", ""))
            except ValueError:
                return False
        return saw_value

    def _raw_data_sorted_rows(self, rows: list[tuple[str, ...]]) -> list[tuple[str, ...]]:
        column = self.raw_data_sort_column
        if column is None:
            return rows
        index = self.raw_data_columns.index(column)
        populated: list[tuple[str, tuple[str, ...]]] = []
        blanks: list[tuple[str, ...]] = []
        for row in rows:
            value = row[index]
            if not value:
                blanks.append(row)
            else:
                populated.append((value, row))

        def as_number(value: str) -> float | None:
            try:
                return float(value.replace(",", ""))
            except ValueError:
                return None

        numeric_values = [as_number(value) for value, _row in populated]
        if populated and all(value is not None for value in numeric_values):
            keyed = list(zip(numeric_values, (row for _value, row in populated)))
            keyed.sort(key=lambda item: item[0], reverse=self.raw_data_sort_descending)
            ordered = [row for _value, row in keyed]
        else:
            populated.sort(key=lambda item: item[0].casefold(), reverse=self.raw_data_sort_descending)
            ordered = [row for _value, row in populated]
        return ordered + blanks

    def _refresh_raw_data_table(self) -> None:
        self.raw_data_tree.delete(*self.raw_data_tree.get_children())
        if self.raw_data_result is None:
            return
        filtered = self._raw_data_filtered_rows()
        ordered = self._raw_data_sorted_rows(filtered)
        for index, row in enumerate(ordered):
            self.raw_data_tree.insert("", tk.END, iid=str(index), values=row)
        filters_active = any(
            selection != ALL_FILTER for selection in self.raw_data_filter_selections.values()
        )
        self.clear_raw_data_filters_button.configure(
            state=tk.NORMAL if filters_active else tk.DISABLED
        )
        self._update_raw_data_column_headings()
        self.data_status_var.set(
            f"Showing {len(ordered):,} of {len(self.raw_data_all_rows):,} rows from "
            f"'{self.raw_data_result.sheet_name.strip()}' (columns B:AI, header row "
            f"{self.raw_data_result.header_row})."
        )

    def _update_raw_data_column_headings(self) -> None:
        for column, header in zip(self.raw_data_columns, self.raw_data_headers):
            filter_active = self.raw_data_filter_selections.get(column, ALL_FILTER) != ALL_FILTER
            filter_marker = " ●" if filter_active else ""
            sort_marker = ""
            if column == self.raw_data_sort_column:
                sort_marker = " ↓" if self.raw_data_sort_descending else " ↑"
            self.raw_data_tree.heading(column, text=f"{header}{filter_marker}{sort_marker} ▾")

    def _set_raw_data_sort(self, column: str, descending: bool) -> None:
        self.raw_data_sort_column = column
        self.raw_data_sort_descending = descending
        self._close_data_filter_popup()
        self._refresh_raw_data_table()

    def _set_raw_data_column_filter(self, column: str, value: str) -> None:
        self.raw_data_filter_selections[column] = value
        self._close_data_filter_popup()
        self._refresh_raw_data_table()

    def _clear_raw_data_filters(self) -> None:
        self._close_data_filter_popup()
        for key in self.raw_data_filter_selections:
            self.raw_data_filter_selections[key] = ALL_FILTER
        self._refresh_raw_data_table()

    def _open_data_column_filter(self, column: str) -> None:
        if self.raw_data_result is None:
            return
        self._close_data_filter_popup()
        popup = tk.Toplevel(self)
        self._data_filter_popup = popup
        popup.withdraw()
        popup.transient(self)
        popup.overrideredirect(True)
        popup.resizable(False, False)
        popup.bind("<Escape>", lambda _event: self._close_data_filter_popup())

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

        heading_text = self.raw_data_headers[self.raw_data_columns.index(column)]
        numeric = self._raw_data_column_is_numeric(column)
        ascending_label = "↑  Sort Smallest to Largest" if numeric else "A  Z  Sort A to Z"
        descending_label = "↓  Sort Largest to Smallest" if numeric else "Z  A  Sort Z to A"
        menu_button(ascending_label, lambda: self._set_raw_data_sort(column, False))
        menu_button(descending_label, lambda: self._set_raw_data_sort(column, True))

        current_selection = self.raw_data_filter_selections.get(column, ALL_FILTER)
        filter_active = current_selection != ALL_FILTER
        tk.Frame(body, height=1, background="#d0d0d0").pack(fill=tk.X, pady=5)
        menu_button(
            f'Clear Filter From "{heading_text}"',
            lambda: self._set_raw_data_column_filter(column, ALL_FILTER),
            state=tk.NORMAL if filter_active else tk.DISABLED,
        )

        available_values = self._raw_data_filter_options(column)
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
        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=values_list.yview)
        values_list.configure(yscrollcommand=scrollbar.set)
        values_list.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        displayed_values: list[str] = []
        ok_button: ttk.Button | None = None

        def refresh_values(*_args: object) -> None:
            query = search_var.get().strip().casefold()
            displayed_values[:] = [
                value for value in available_values if not query or query in value.casefold()
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
                ok_button.configure(state=tk.NORMAL if checked_values else tk.DISABLED)

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
            self.raw_data_filter_selections[column] = selection
            self._close_data_filter_popup()
            self._refresh_raw_data_table()

        search_var.trace_add("write", refresh_values)
        popup.bind("<Return>", lambda _event: apply_selected())
        actions = ttk.Frame(body)
        actions.pack(fill=tk.X, pady=(8, 0))
        ttk.Button(actions, text="Cancel", command=self._close_data_filter_popup).pack(side=tk.RIGHT)
        ok_button = ttk.Button(actions, text="OK", command=apply_selected)
        ok_button.pack(side=tk.RIGHT, padx=(0, 6))
        refresh_values()
        values_list.bind("<Button-1>", toggle_value)
        search_entry.focus_set()

        popup.update_idletasks()
        popup_width = popup.winfo_reqwidth()
        popup_height = popup.winfo_reqheight()
        window_left = self.winfo_rootx()
        window_top = self.winfo_rooty()
        window_right = window_left + self.winfo_width()
        window_bottom = window_top + self.winfo_height()
        x = max(window_left, min(self.winfo_pointerx() - 16, window_right - popup_width))
        y = max(window_top, min(self.winfo_pointery() + 16, window_bottom - popup_height))
        popup.geometry(f"{popup_width}x{popup_height}+{x}+{y}")
        popup.deiconify()
        popup.lift()
        self.after_idle(self._enable_data_filter_outside_click, popup)

    def _enable_data_filter_outside_click(self, popup: tk.Toplevel) -> None:
        if self._data_filter_popup is not popup:
            return
        self._data_filter_outside_binding = self.bind(
            "<Button-1>",
            self._data_filter_clicked_outside,
            add="+",
        )

    def _close_data_filter_popup(self) -> None:
        if self._data_filter_outside_binding is not None:
            self.unbind("<Button-1>", self._data_filter_outside_binding)
            self._data_filter_outside_binding = None
        if self._data_filter_popup is not None:
            try:
                self._data_filter_popup.destroy()
            except tk.TclError:
                pass
            self._data_filter_popup = None

    def _data_filter_clicked_outside(self, _event: tk.Event) -> None:
        self._close_data_filter_popup()
