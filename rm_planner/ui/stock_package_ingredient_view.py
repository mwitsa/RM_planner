"""StockPackageIngredientViewMixin behavior."""

from __future__ import annotations

from .common import *  # shared UI types and domain services
from rm_planner.inventory.stock_package_ingredient import (
    StockRecord,
    choose_default_sheet,
    extract_stock_records,
    load_stock_records,
    save_stock_records,
)
from rm_planner.inventory.stock_package_ingredient import list_sheets as list_stock_sheets

STOCK_RECORD_COLUMNS = (
    ("material_code", "Material"),
    ("material_description", "Description"),
    ("storage_location", "SLoc"),
    ("plant", "Plant"),
    ("stock_type", "Type"),
    ("storage_bin", "Storage Bin"),
    ("batch", "Batch"),
    ("quantity", "Qty"),
    ("unit", "Unit"),
    ("gr_number", "GR Number"),
    ("gr_date", "GR Date"),
    ("sled_bbd", "SLED/BBD"),
    ("storage_unit", "Storage Unit"),
)
STOCK_SIDES = (("package", "package"), ("ingredient", "ing"))


class StockPackageIngredientViewMixin:
    def _build_stock_package_ingredient_tab(self) -> None:
        self.stock_package_ingredient_file_var = tk.StringVar()
        self.stock_package_ingredient_status_var = tk.StringVar(value="ยังไม่ได้เลือกไฟล์")
        self.stock_sides: dict[str, dict] = {}

        ttk.Label(
            self.stock_package_ingredient_tab,
            text="Stock Package/Ingredient",
            font=("Segoe UI", 16, "bold"),
        ).pack(anchor=tk.W)
        ttk.Label(
            self.stock_package_ingredient_tab,
            text="ติดตามสต๊อกบรรจุภัณฑ์และวัตถุดิบส่วนประกอบ",
        ).pack(anchor=tk.W, pady=(3, 18))

        source = ttk.LabelFrame(
            self.stock_package_ingredient_tab, text="Source workbook", padding=12,
        )
        source.pack(fill=tk.X)
        source.columnconfigure(1, weight=1)
        ttk.Label(source, text="Excel file:").grid(row=0, column=0, sticky=tk.W, padx=(0, 8))
        ttk.Entry(source, textvariable=self.stock_package_ingredient_file_var).grid(
            row=0, column=1, sticky=tk.EW
        )
        ttk.Button(
            source, text="Browse…", command=self._browse_stock_package_ingredient_workbook,
        ).grid(row=0, column=2, padx=(8, 0))
        ttk.Label(
            source,
            text="ไฟล์เดียวกัน มี 2 ชีทให้เลือก: หนึ่งสำหรับ Package และหนึ่งสำหรับ Ingredient",
            foreground="#64748b",
        ).grid(row=1, column=0, columnspan=3, sticky=tk.W, pady=(6, 0))

        ttk.Label(
            self.stock_package_ingredient_tab,
            textvariable=self.stock_package_ingredient_status_var,
            relief=tk.SUNKEN,
            anchor=tk.W,
            padding=(6, 3),
        ).pack(fill=tk.X, pady=(8, 0))

        sub_notebook = ttk.Notebook(self.stock_package_ingredient_tab)
        sub_notebook.pack(fill=tk.BOTH, expand=True, pady=(10, 0))

        for side, default_keyword in STOCK_SIDES:
            tab = ttk.Frame(sub_notebook, padding=10)
            sub_notebook.add(tab, text=side.capitalize())
            self._build_stock_side_tab(tab, side, default_keyword)

    def _build_stock_side_tab(self, tab: tk.Widget, side: str, default_keyword: str) -> None:
        store_path = (
            self.stock_package_file_path if side == "package" else self.stock_ingredient_file_path
        )
        state = {
            "default_keyword": default_keyword,
            "store_path": store_path,
            "sheet_var": tk.StringVar(),
            "status_var": tk.StringVar(value="ยังไม่ได้เลือกชีท"),
            "records": [],
            "sort_column": None,
            "sort_descending": False,
        }
        self.stock_sides[side] = state

        controls = ttk.Frame(tab)
        controls.pack(fill=tk.X)
        ttk.Label(controls, text="Worksheet:").pack(side=tk.LEFT, padx=(0, 8))
        state["sheet_combo"] = ttk.Combobox(
            controls, textvariable=state["sheet_var"], state="readonly", width=30,
        )
        state["sheet_combo"].pack(side=tk.LEFT)
        state["extract_button"] = ttk.Button(
            controls,
            text="Extract data",
            command=lambda: self._extract_stock_side(side),
            state=tk.DISABLED,
        )
        state["extract_button"].pack(side=tk.LEFT, padx=(8, 0))

        table_frame = ttk.Frame(tab)
        table_frame.pack(fill=tk.BOTH, expand=True, pady=(10, 0))
        columns = [key for key, _label in STOCK_RECORD_COLUMNS]
        tree = ttk.Treeview(table_frame, columns=columns, show="headings")
        for key, label in STOCK_RECORD_COLUMNS:
            tree.heading(
                key, text=label,
                command=lambda selected=key: self._sort_stock_side(side, selected),
            )
            anchor = tk.E if key == "quantity" else tk.W
            tree.column(key, width=110, minwidth=70, anchor=anchor, stretch=False)
        vertical = ttk.Scrollbar(table_frame, orient=tk.VERTICAL, command=tree.yview)
        horizontal = ttk.Scrollbar(table_frame, orient=tk.HORIZONTAL, command=tree.xview)
        tree.configure(yscrollcommand=vertical.set, xscrollcommand=horizontal.set)
        tree.grid(row=0, column=0, sticky="nsew")
        vertical.grid(row=0, column=1, sticky="ns")
        horizontal.grid(row=1, column=0, sticky="ew")
        table_frame.rowconfigure(0, weight=1)
        table_frame.columnconfigure(0, weight=1)
        state["tree"] = tree

        ttk.Label(
            tab, textvariable=state["status_var"], relief=tk.SUNKEN, anchor=tk.W, padding=(6, 3),
        ).pack(fill=tk.X, pady=(8, 0))

    def _browse_stock_package_ingredient_workbook(self) -> None:
        selected = filedialog.askopenfilename(
            title="Select stock package/ingredient workbook",
            filetypes=[("Excel workbook", "*.xls *.xlsx *.xlsm"), ("All files", "*.*")],
        )
        if selected:
            self.stock_package_ingredient_file_var.set(selected)
            self._load_stock_package_ingredient_sheets()

    def _load_stock_package_ingredient_sheets(self) -> None:
        workbook_path = self.stock_package_ingredient_file_var.get().strip()
        try:
            sheets = list_stock_sheets(workbook_path)
        except Exception as exc:
            for state in self.stock_sides.values():
                state["sheet_combo"].configure(values=[])
                state["sheet_var"].set("")
                state["extract_button"].configure(state=tk.DISABLED)
            self.stock_package_ingredient_status_var.set("Could not read workbook.")
            messagebox.showerror("Workbook error", str(exc))
            return
        for state in self.stock_sides.values():
            state["sheet_combo"].configure(values=sheets)
            state["sheet_var"].set(choose_default_sheet(sheets, state["default_keyword"]))
            state["extract_button"].configure(state=tk.NORMAL if sheets else tk.DISABLED)
        self.stock_package_ingredient_status_var.set(f"Loaded {len(sheets)} worksheets.")

    def _extract_stock_side(self, side: str) -> None:
        workbook_path = self.stock_package_ingredient_file_var.get().strip()
        state = self.stock_sides[side]
        sheet_name = state["sheet_var"].get()
        if not workbook_path or not sheet_name:
            messagebox.showwarning("Missing source", "Please select an Excel file and worksheet.")
            return
        try:
            records = extract_stock_records(workbook_path, sheet_name)
        except Exception as exc:
            state["status_var"].set("Extraction failed.")
            messagebox.showerror("Extraction error", str(exc))
            return
        state["records"] = records
        state["sort_column"] = None
        state["sort_descending"] = False
        self._refresh_stock_side_table(side)
        try:
            save_stock_records(
                state["store_path"], records, source_file=workbook_path, source_sheet=sheet_name,
            )
        except ValueError as exc:
            state["status_var"].set(f"Loaded {len(records):,} rows, but could not save: {exc}")
            return
        state["status_var"].set(f"Loaded and saved {len(records):,} rows from '{sheet_name}'.")

    def _load_saved_stock_package_ingredient_data(self) -> None:
        """Restore the last-extracted Package/Ingredient rows after a restart."""

        for side, state in self.stock_sides.items():
            try:
                records, source_file, source_sheet = load_stock_records(state["store_path"])
            except ValueError as exc:
                state["status_var"].set(str(exc))
                continue
            if not records:
                continue
            state["records"] = records
            if source_file and not self.stock_package_ingredient_file_var.get().strip():
                self.stock_package_ingredient_file_var.set(source_file)
            if source_sheet:
                state["sheet_var"].set(source_sheet)
            self._refresh_stock_side_table(side)
            state["status_var"].set(f"Loaded {len(records):,} saved rows from last extraction.")

    def _sort_stock_side(self, side: str, column: str) -> None:
        state = self.stock_sides[side]
        if state["sort_column"] == column:
            state["sort_descending"] = not state["sort_descending"]
        else:
            state["sort_column"] = column
            state["sort_descending"] = False
        self._refresh_stock_side_table(side)

    def _refresh_stock_side_table(self, side: str) -> None:
        state = self.stock_sides[side]
        tree = state["tree"]
        tree.delete(*tree.get_children())
        rows: list[StockRecord] = list(state["records"])
        sort_column = state["sort_column"]
        if sort_column is not None:
            if sort_column == "quantity":
                rows.sort(key=lambda record: record.quantity, reverse=state["sort_descending"])
            else:
                rows.sort(
                    key=lambda record: getattr(record, sort_column).casefold(),
                    reverse=state["sort_descending"],
                )
        for index, record in enumerate(rows):
            tree.insert(
                "",
                tk.END,
                iid=str(index),
                values=[
                    self._format_optional_number(record.quantity)
                    if key == "quantity" else getattr(record, key)
                    for key, _label in STOCK_RECORD_COLUMNS
                ],
            )
        for key, label in STOCK_RECORD_COLUMNS:
            marker = ""
            if key == sort_column:
                marker = " ↓" if state["sort_descending"] else " ↑"
            tree.heading(key, text=f"{label}{marker}")
