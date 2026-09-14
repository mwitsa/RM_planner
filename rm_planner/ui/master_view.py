"""MasterViewMixin behavior."""

from __future__ import annotations

from .common import *  # shared UI types and domain services


class MasterViewMixin:
    def _build_master_tab(self) -> None:
        source = ttk.LabelFrame(self.master_tab, text="Master workbook (Master PCK ING.xlsx)", padding=12)
        source.pack(fill=tk.X)
        source.columnconfigure(1, weight=1)

        ttk.Label(source, text="Excel file:").grid(row=0, column=0, sticky=tk.W, padx=(0, 8))
        ttk.Entry(source, textvariable=self.master_file_var).grid(row=0, column=1, sticky=tk.EW)
        ttk.Button(source, text="Browse…", command=self._browse_master_workbook).grid(
            row=0, column=2, padx=(8, 0)
        )
        self.load_master_button = ttk.Button(
            source,
            text="Load master data",
            command=self._start_master_load,
        )
        self.load_master_button.grid(row=0, column=3, padx=(8, 0))

        table_frame = ttk.Frame(self.master_tab)
        table_frame.pack(fill=tk.BOTH, expand=True, pady=(12, 0))
        master_columns = ("material", "description", "component_name", "mrp_controller")
        self.master_columns = master_columns
        self.master_headings = {
            "material": "Material",
            "description": "Description",
            "component_name": "Component name",
            "mrp_controller": "Component MRP Controller",
        }
        self.master_tree = ttk.Treeview(table_frame, columns=master_columns, show="headings")
        widths = {
            "material": 160,
            "description": 300,
            "component_name": 300,
            "mrp_controller": 160,
        }
        for column in master_columns:
            self.master_tree.heading(
                column,
                text=self.master_headings[column],
                command=lambda selected_column=column: self._sort_master_by(selected_column),
            )
            self.master_tree.column(column, width=widths[column], minwidth=80, anchor=tk.W)

        vertical = ttk.Scrollbar(table_frame, orient=tk.VERTICAL, command=self.master_tree.yview)
        horizontal = ttk.Scrollbar(table_frame, orient=tk.HORIZONTAL, command=self.master_tree.xview)
        self.master_tree.configure(yscrollcommand=vertical.set, xscrollcommand=horizontal.set)
        self.master_tree.grid(row=0, column=0, sticky="nsew")
        vertical.grid(row=0, column=1, sticky="ns")
        horizontal.grid(row=1, column=0, sticky="ew")
        table_frame.rowconfigure(0, weight=1)
        table_frame.columnconfigure(0, weight=1)

        status = ttk.Label(
            self.master_tab,
            textvariable=self.master_status_var,
            relief=tk.SUNKEN,
            anchor=tk.W,
            padding=(6, 3),
        )
        status.pack(fill=tk.X, pady=(8, 0))

    def _browse_master_workbook(self) -> None:
        selected = filedialog.askopenfilename(
            title="Select master workbook",
            filetypes=[("Excel workbook", "*.xlsx *.xlsm"), ("All files", "*.*")],
        )
        if selected:
            self.master_file_var.set(selected)

    def _start_master_load(self) -> None:
        if not self.master_file_var.get().strip():
            messagebox.showwarning("Missing source", "Please select the master Excel file.")
            return
        self.load_master_button.configure(state=tk.DISABLED)
        self.master_status_var.set("Loading master data…")
        threading.Thread(target=self._master_load_worker, daemon=True).start()

    def _master_load_worker(self) -> None:
        try:
            records = extract_master_data(self.master_file_var.get().strip())
        except Exception as exc:
            self.after(0, self._show_master_error, exc)
            return
        try:
            save_master_data(self.master_store_file_path, records)
        except ValueError as exc:
            self.after(0, self._show_master_error, exc)
            return
        self.after(0, self._show_master_result, records, True)

    def _show_master_result(self, records: list[MasterComponentRecord], imported: bool) -> None:
        self.master_records = records
        self.load_master_button.configure(state=tk.NORMAL)
        self._refresh_master_table()
        materials = {record.material for record in records if record.material}
        verb = "Imported" if imported else "Loaded"
        self.master_status_var.set(
            f"{verb} {len(records):,} component rows across {len(materials):,} materials."
        )

    def _show_master_error(self, exc: Exception) -> None:
        self.load_master_button.configure(state=tk.NORMAL)
        self.master_status_var.set("Failed to load master data.")
        messagebox.showerror("Master data error", str(exc))

    def _load_saved_master_data(self) -> None:
        try:
            records = load_master_data(self.master_store_file_path)
        except ValueError as exc:
            self.master_status_var.set(str(exc))
            return
        if records:
            self._show_master_result(records, False)

    def _sort_master_by(self, column: str) -> None:
        if self.master_sort_column == column:
            self.master_sort_descending = not self.master_sort_descending
        else:
            self.master_sort_column = column
            self.master_sort_descending = False
        self._refresh_master_table()

    def _refresh_master_table(self) -> None:
        self.master_tree.delete(*self.master_tree.get_children())
        rows = list(self.master_records)
        if self.master_sort_column is not None:
            rows.sort(
                key=lambda record: getattr(record, self.master_sort_column).casefold(),
                reverse=self.master_sort_descending,
            )
        for index, record in enumerate(rows):
            self.master_tree.insert(
                "",
                tk.END,
                iid=str(index),
                values=(
                    record.material,
                    record.description,
                    record.component_name,
                    record.mrp_controller,
                ),
            )
        for column, heading in self.master_headings.items():
            sort_marker = ""
            if column == self.master_sort_column:
                sort_marker = " ↓" if self.master_sort_descending else " ↑"
            self.master_tree.heading(column, text=f"{heading}{sort_marker}")
