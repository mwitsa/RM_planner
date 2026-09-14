"""ShipmentViewMixin behavior."""

from __future__ import annotations

from .common import *  # shared UI types and domain services


class ShipmentViewMixin:
    def _build_assortment_upload_tab(self) -> None:
        source = ttk.LabelFrame(
            self.assortment_upload_tab,
            text="Assortment workbook (per-shipment size distribution)",
            padding=12,
        )
        source.pack(fill=tk.X)
        source.columnconfigure(1, weight=1)

        ttk.Label(source, text="Excel file:").grid(row=0, column=0, sticky=tk.W, padx=(0, 8))
        ttk.Entry(source, textvariable=self.assortment_upload_file_var).grid(
            row=0, column=1, sticky=tk.EW
        )
        ttk.Button(
            source,
            text="Browse…",
            command=self._browse_assortment_upload_workbook,
        ).grid(row=0, column=2, padx=(8, 0))
        self.load_assortment_upload_button = ttk.Button(
            source,
            text="Load assortment data",
            command=self._start_assortment_upload_load,
        )
        self.load_assortment_upload_button.grid(row=0, column=3, padx=(8, 0))

        self.assortment_upload_table_frame = ttk.Frame(self.assortment_upload_tab)
        self.assortment_upload_table_frame.pack(fill=tk.BOTH, expand=True, pady=(12, 0))

        status = ttk.Label(
            self.assortment_upload_tab,
            textvariable=self.assortment_upload_status_var,
            relief=tk.SUNKEN,
            anchor=tk.W,
            padding=(6, 3),
        )
        status.pack(fill=tk.X, pady=(8, 0))

    def _browse_assortment_upload_workbook(self) -> None:
        selected = filedialog.askopenfilename(
            title="Select assortment workbook",
            filetypes=[("Excel workbook", "*.xlsx *.xlsm"), ("All files", "*.*")],
        )
        if selected:
            self.assortment_upload_file_var.set(selected)

    def _start_assortment_upload_load(self) -> None:
        if not self.assortment_upload_file_var.get().strip():
            messagebox.showwarning("Missing source", "Please select the assortment Excel file.")
            return
        self.load_assortment_upload_button.configure(state=tk.DISABLED)
        self.assortment_upload_status_var.set("Loading assortment data…")
        threading.Thread(target=self._assortment_upload_worker, daemon=True).start()

    def _assortment_upload_worker(self) -> None:
        try:
            sheet_name, field_labels, records = extract_assortment_shipments(
                self.assortment_upload_file_var.get().strip()
            )
        except Exception as exc:
            self.after(0, self._show_assortment_upload_error, exc)
            return
        try:
            save_assortment_shipments(
                self.assortment_upload_store_file_path,
                sheet_name,
                field_labels,
                records,
            )
        except ValueError as exc:
            self.after(0, self._show_assortment_upload_error, exc)
            return
        self.after(0, self._show_assortment_upload_result, sheet_name, field_labels, records, True)

    def _show_assortment_upload_result(
        self,
        sheet_name: str,
        field_labels: list[str],
        records: list[AssortmentShipmentRecord],
        imported: bool,
    ) -> None:
        self.assortment_upload_field_labels = field_labels
        self.assortment_upload_records = records
        self.assortment_upload_sort_column = None
        self.assortment_upload_sort_descending = False
        self._rebuild_assortment_upload_tree(field_labels)
        self._refresh_assortment_upload_table()
        self._refresh_summary_table()
        self.load_assortment_upload_button.configure(state=tk.NORMAL)
        verb = "Imported" if imported else "Loaded"
        sheet_note = f" from worksheet '{sheet_name}'" if sheet_name else ""
        self.assortment_upload_status_var.set(
            f"{verb} {len(records):,} shipments{sheet_note}."
        )

    def _show_assortment_upload_error(self, exc: Exception) -> None:
        self.load_assortment_upload_button.configure(state=tk.NORMAL)
        self.assortment_upload_status_var.set("Failed to load assortment data.")
        messagebox.showerror("Assortment data error", str(exc))

    def _load_saved_assortment_upload(self) -> None:
        try:
            sheet_name, field_labels, records = load_assortment_shipments(
                self.assortment_upload_store_file_path
            )
        except ValueError as exc:
            self.assortment_upload_status_var.set(str(exc))
            return
        if records:
            self._show_assortment_upload_result(sheet_name, field_labels, records, False)

    def _rebuild_assortment_upload_tree(self, field_labels: list[str]) -> None:
        for child in self.assortment_upload_table_frame.winfo_children():
            child.destroy()
        columns = [f"field_{index:02d}" for index in range(len(field_labels))]
        self.assortment_upload_columns = columns
        tree = ttk.Treeview(self.assortment_upload_table_frame, columns=columns, show="headings")
        wide_labels = {"ฟาร์ม", "จังหวัด"}
        for column, label in zip(columns, field_labels):
            tree.heading(
                column,
                text=label,
                command=lambda selected_column=column: self._sort_assortment_upload_by(
                    selected_column
                ),
            )
            width = 220 if label in wide_labels else 100
            tree.column(column, width=width, minwidth=70, anchor=tk.W)

        vertical = ttk.Scrollbar(
            self.assortment_upload_table_frame, orient=tk.VERTICAL, command=tree.yview
        )
        horizontal = ttk.Scrollbar(
            self.assortment_upload_table_frame, orient=tk.HORIZONTAL, command=tree.xview
        )
        tree.configure(yscrollcommand=vertical.set, xscrollcommand=horizontal.set)
        tree.grid(row=0, column=0, sticky="nsew")
        vertical.grid(row=0, column=1, sticky="ns")
        horizontal.grid(row=1, column=0, sticky="ew")
        self.assortment_upload_table_frame.rowconfigure(0, weight=1)
        self.assortment_upload_table_frame.columnconfigure(0, weight=1)
        self.assortment_upload_tree = tree

    def _sort_assortment_upload_by(self, column: str) -> None:
        if self.assortment_upload_sort_column == column:
            self.assortment_upload_sort_descending = not self.assortment_upload_sort_descending
        else:
            self.assortment_upload_sort_column = column
            self.assortment_upload_sort_descending = False
        self._refresh_assortment_upload_table()

    def _refresh_assortment_upload_table(self) -> None:
        if self.assortment_upload_tree is None:
            return
        self.assortment_upload_tree.delete(*self.assortment_upload_tree.get_children())
        rows = list(self.assortment_upload_records)
        if self.assortment_upload_sort_column is not None:
            index = self.assortment_upload_columns.index(self.assortment_upload_sort_column)

            def sort_key(record: AssortmentShipmentRecord) -> tuple[bool, float | str]:
                value = record.fields[index][1]
                try:
                    return (False, float(value.replace(",", "")))
                except ValueError:
                    return (True, value.casefold())

            rows.sort(key=sort_key, reverse=self.assortment_upload_sort_descending)
        for row_index, record in enumerate(rows):
            self.assortment_upload_tree.insert(
                "",
                tk.END,
                iid=str(row_index),
                values=[value for _label, value in record.fields],
            )
        for column, label in zip(self.assortment_upload_columns, self.assortment_upload_field_labels):
            sort_marker = ""
            if column == self.assortment_upload_sort_column:
                sort_marker = " ↓" if self.assortment_upload_sort_descending else " ↑"
            self.assortment_upload_tree.heading(column, text=f"{label}{sort_marker}")
