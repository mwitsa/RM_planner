"""RM stock balance screen and its cumulative-arrival presentation."""

from __future__ import annotations

from datetime import date

from .common import *  # shared UI types and domain services
from rm_planner.inventory._workbook_io import choose_default_sheet as choose_default_rm_data_sheet
from rm_planner.inventory.pd_actual_data import (
    PD_ACTUAL_COLUMNS,
    PD_ACTUAL_FLOAT_FIELDS,
    extract_pd_actual_records,
    load_pd_actual_records,
    pivot_weight_out_by_farm_and_size,
    save_pd_actual_records,
)
from rm_planner.inventory.rm_stock_data import (
    RM_STOCK_COLUMNS,
    extract_rm_stock_records,
    list_sheets as list_rm_data_sheets,
    load_rm_stock_records,
    pivot_gross_wt_by_remark_and_action_repack,
    save_rm_stock_records,
)


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
        self.rm_data_tab = ttk.Frame(content, padding=14)
        self.rm_pd_actual_tab = ttk.Frame(content, padding=14)
        self.rm_pd_tab = ttk.Frame(content, padding=14)
        self.rm_pd_actual_pivot_tab = ttk.Frame(content, padding=14)
        for frame in (
            self.rm_timeline_tab, self.assortment_std_tab, self.assortment_actual_tab,
            self.rm_data_tab, self.rm_pd_actual_tab, self.rm_pd_tab, self.rm_pd_actual_pivot_tab,
        ):
            frame.grid(row=0, column=0, sticky="nsew")
        self._build_rm_timeline_tab()
        self._build_assortment_std_tab()
        self._build_assortment_actual_tab()
        self._build_rm_data_tab()
        self._build_rm_pd_actual_tab()
        self._build_rm_pd_tab()
        self._build_rm_pd_actual_pivot_tab()
        self._show_rm_section("timeline")

    def _show_rm_section(self, section: str) -> None:
        frames = {
            "timeline": self.rm_timeline_tab,
            "predict": self.assortment_std_tab,
            "actual": self.assortment_actual_tab,
            "data": self.rm_data_tab,
            "pd_actual": self.rm_pd_actual_tab,
            "pd": self.rm_pd_tab,
            "pd_actual_pivot": self.rm_pd_actual_pivot_tab,
        }
        if section == "pd":
            self._refresh_rm_pd_filters()
        if section == "pd_actual_pivot":
            self._refresh_rm_pd_actual_pivot_filters()
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

    def _build_rm_data_tab(self) -> None:
        self.rm_data_file_var = tk.StringVar()
        self.rm_data_sheet_var = tk.StringVar()
        self.rm_data_status_var = tk.StringVar(value="ยังไม่ได้เลือกไฟล์")

        ttk.Label(
            self.rm_data_tab, text="อัพโหลดข้อมูล STOCK On Hand", font=("Segoe UI", 16, "bold"),
        ).pack(anchor=tk.W)
        ttk.Label(
            self.rm_data_tab, text="นำเข้าข้อมูล RM stock จากไฟล์ Excel",
        ).pack(anchor=tk.W, pady=(3, 18))

        source = ttk.LabelFrame(self.rm_data_tab, text="Source workbook", padding=12)
        source.pack(fill=tk.X)
        source.columnconfigure(1, weight=1)
        ttk.Label(source, text="Excel file:").grid(row=0, column=0, sticky=tk.W, padx=(0, 8))
        ttk.Entry(source, textvariable=self.rm_data_file_var).grid(row=0, column=1, sticky=tk.EW)
        ttk.Button(
            source, text="Browse…", command=self._browse_rm_data_workbook,
        ).grid(row=0, column=2, padx=(8, 0))

        ttk.Label(source, text="Worksheet:").grid(
            row=1, column=0, sticky=tk.W, padx=(0, 8), pady=(10, 0)
        )
        self.rm_data_sheet_combo = ttk.Combobox(
            source, textvariable=self.rm_data_sheet_var, state="readonly", width=35,
        )
        self.rm_data_sheet_combo.grid(row=1, column=1, sticky=tk.W, pady=(10, 0))
        self.rm_data_extract_button = ttk.Button(
            source, text="Extract data", command=self._start_rm_data_extraction, state=tk.DISABLED,
        )
        self.rm_data_extract_button.grid(row=1, column=2, padx=(8, 0), pady=(10, 0))

        ttk.Label(
            self.rm_data_tab,
            textvariable=self.rm_data_status_var,
            relief=tk.SUNKEN,
            anchor=tk.W,
            padding=(6, 3),
        ).pack(fill=tk.X, pady=(8, 0))

        self.rm_data_records: list = []
        self.rm_data_sort_column: str | None = None
        self.rm_data_sort_descending = False
        table_frame = ttk.Frame(self.rm_data_tab)
        table_frame.pack(fill=tk.BOTH, expand=True, pady=(10, 0))
        columns = [key for key, _label in RM_STOCK_COLUMNS]
        tree = ttk.Treeview(table_frame, columns=columns, show="headings")
        for key, label in RM_STOCK_COLUMNS:
            tree.heading(
                key, text=label, command=lambda selected=key: self._sort_rm_data(selected),
            )
            anchor = tk.E if key in ("gross_wt", "net_wt") else tk.W
            tree.column(key, width=100, minwidth=70, anchor=anchor, stretch=False)
        vertical = ttk.Scrollbar(table_frame, orient=tk.VERTICAL, command=tree.yview)
        horizontal = ttk.Scrollbar(table_frame, orient=tk.HORIZONTAL, command=tree.xview)
        tree.configure(yscrollcommand=vertical.set, xscrollcommand=horizontal.set)
        tree.grid(row=0, column=0, sticky="nsew")
        vertical.grid(row=0, column=1, sticky="ns")
        horizontal.grid(row=1, column=0, sticky="ew")
        table_frame.rowconfigure(0, weight=1)
        table_frame.columnconfigure(0, weight=1)
        self.rm_data_tree = tree

    def _browse_rm_data_workbook(self) -> None:
        selected = filedialog.askopenfilename(
            title="Select RM stock workbook",
            filetypes=[("Excel workbook", "*.xls *.xlsx *.xlsm"), ("All files", "*.*")],
        )
        if selected:
            self.rm_data_file_var.set(selected)
            self._load_rm_data_sheets()

    def _load_rm_data_sheets(self) -> None:
        try:
            workbook_path = self.rm_data_file_var.get().strip()
            sheets = list_rm_data_sheets(workbook_path)
            default_sheet = choose_default_rm_data_sheet(sheets, "data")
            self.rm_data_sheet_combo.configure(values=sheets)
            self.rm_data_sheet_var.set(default_sheet)
            self.rm_data_extract_button.configure(state=tk.NORMAL if sheets else tk.DISABLED)
            self.rm_data_status_var.set(f"Loaded {len(sheets)} worksheets.")
        except Exception as exc:
            self.rm_data_sheet_combo.configure(values=[])
            self.rm_data_sheet_var.set("")
            self.rm_data_extract_button.configure(state=tk.DISABLED)
            self.rm_data_status_var.set("Could not read workbook.")
            messagebox.showerror("Workbook error", str(exc))

    def _start_rm_data_extraction(self) -> None:
        workbook_path = self.rm_data_file_var.get().strip()
        sheet_name = self.rm_data_sheet_var.get()
        if not workbook_path or not sheet_name:
            messagebox.showwarning("Missing source", "Please select an Excel file and worksheet.")
            return
        try:
            records = extract_rm_stock_records(workbook_path, sheet_name)
        except Exception as exc:
            self.rm_data_status_var.set("Extraction failed.")
            messagebox.showerror("Extraction error", str(exc))
            return
        self.rm_data_records = records
        self.rm_data_sort_column = None
        self.rm_data_sort_descending = False
        self._refresh_rm_data_table()
        try:
            save_rm_stock_records(
                self.rm_stock_data_file_path, records,
                source_file=workbook_path, source_sheet=sheet_name,
            )
        except ValueError as exc:
            self.rm_data_status_var.set(f"Loaded {len(records):,} rows, but could not save: {exc}")
            return
        self.rm_data_status_var.set(f"Loaded and saved {len(records):,} rows from '{sheet_name}'.")

    def _load_saved_rm_stock_data(self) -> None:
        """Restore the last-extracted RM stock rows, so DATA/PD survive a restart."""

        try:
            records, source_file, source_sheet = load_rm_stock_records(self.rm_stock_data_file_path)
        except ValueError as exc:
            self.rm_data_status_var.set(str(exc))
            return
        if not records:
            return
        self.rm_data_records = records
        if source_file:
            self.rm_data_file_var.set(source_file)
        if source_sheet:
            self.rm_data_sheet_var.set(source_sheet)
        self._refresh_rm_data_table()
        self.rm_data_status_var.set(f"Loaded {len(records):,} saved rows from last extraction.")

    def _sort_rm_data(self, column: str) -> None:
        if self.rm_data_sort_column == column:
            self.rm_data_sort_descending = not self.rm_data_sort_descending
        else:
            self.rm_data_sort_column = column
            self.rm_data_sort_descending = False
        self._refresh_rm_data_table()

    def _refresh_rm_data_table(self) -> None:
        tree = self.rm_data_tree
        tree.delete(*tree.get_children())
        rows = list(self.rm_data_records)
        if self.rm_data_sort_column is not None:
            column = self.rm_data_sort_column
            if column in ("gross_wt", "net_wt"):
                rows.sort(key=lambda record: getattr(record, column), reverse=self.rm_data_sort_descending)
            else:
                rows.sort(
                    key=lambda record: getattr(record, column).casefold(),
                    reverse=self.rm_data_sort_descending,
                )
        for index, record in enumerate(rows):
            tree.insert(
                "", tk.END, iid=str(index),
                values=[getattr(record, key) for key, _label in RM_STOCK_COLUMNS],
            )
        for key, label in RM_STOCK_COLUMNS:
            marker = ""
            if key == self.rm_data_sort_column:
                marker = " ↓" if self.rm_data_sort_descending else " ↑"
            tree.heading(key, text=f"{label}{marker}")

    def _build_rm_pd_actual_tab(self) -> None:
        """Upload page for "อัพโหลดข้อมูล STOCK แกลง 2" (actual HO distribution/yield), same shape as DATA."""

        self.rm_pd_actual_file_var = tk.StringVar()
        self.rm_pd_actual_sheet_var = tk.StringVar()
        self.rm_pd_actual_status_var = tk.StringVar(value="ยังไม่ได้เลือกไฟล์")

        ttk.Label(
            self.rm_pd_actual_tab, text="อัพโหลดข้อมูล STOCK แกลง 2", font=("Segoe UI", 16, "bold"),
        ).pack(anchor=tk.W)
        ttk.Label(
            self.rm_pd_actual_tab, text="นำเข้าข้อมูล PD ที่เกิดขึ้นจริงจากไฟล์ Excel",
        ).pack(anchor=tk.W, pady=(3, 18))

        source = ttk.LabelFrame(self.rm_pd_actual_tab, text="Source workbook", padding=12)
        source.pack(fill=tk.X)
        source.columnconfigure(1, weight=1)
        ttk.Label(source, text="Excel file:").grid(row=0, column=0, sticky=tk.W, padx=(0, 8))
        ttk.Entry(source, textvariable=self.rm_pd_actual_file_var).grid(row=0, column=1, sticky=tk.EW)
        ttk.Button(
            source, text="Browse…", command=self._browse_rm_pd_actual_workbook,
        ).grid(row=0, column=2, padx=(8, 0))

        ttk.Label(source, text="Worksheet:").grid(
            row=1, column=0, sticky=tk.W, padx=(0, 8), pady=(10, 0)
        )
        self.rm_pd_actual_sheet_combo = ttk.Combobox(
            source, textvariable=self.rm_pd_actual_sheet_var, state="readonly", width=35,
        )
        self.rm_pd_actual_sheet_combo.grid(row=1, column=1, sticky=tk.W, pady=(10, 0))
        self.rm_pd_actual_extract_button = ttk.Button(
            source, text="Extract data", command=self._start_rm_pd_actual_extraction,
            state=tk.DISABLED,
        )
        self.rm_pd_actual_extract_button.grid(row=1, column=2, padx=(8, 0), pady=(10, 0))

        ttk.Label(
            self.rm_pd_actual_tab,
            textvariable=self.rm_pd_actual_status_var,
            relief=tk.SUNKEN,
            anchor=tk.W,
            padding=(6, 3),
        ).pack(fill=tk.X, pady=(8, 0))

        self.rm_pd_actual_records: list = []
        self.rm_pd_actual_sort_column: str | None = None
        self.rm_pd_actual_sort_descending = False
        table_frame = ttk.Frame(self.rm_pd_actual_tab)
        table_frame.pack(fill=tk.BOTH, expand=True, pady=(10, 0))
        columns = [key for key, _label in PD_ACTUAL_COLUMNS]
        tree = ttk.Treeview(table_frame, columns=columns, show="headings")
        for key, label in PD_ACTUAL_COLUMNS:
            tree.heading(
                key, text=label, command=lambda selected=key: self._sort_rm_pd_actual(selected),
            )
            anchor = tk.E if key in PD_ACTUAL_FLOAT_FIELDS else tk.W
            tree.column(key, width=100, minwidth=70, anchor=anchor, stretch=False)
        vertical = ttk.Scrollbar(table_frame, orient=tk.VERTICAL, command=tree.yview)
        horizontal = ttk.Scrollbar(table_frame, orient=tk.HORIZONTAL, command=tree.xview)
        tree.configure(yscrollcommand=vertical.set, xscrollcommand=horizontal.set)
        tree.grid(row=0, column=0, sticky="nsew")
        vertical.grid(row=0, column=1, sticky="ns")
        horizontal.grid(row=1, column=0, sticky="ew")
        table_frame.rowconfigure(0, weight=1)
        table_frame.columnconfigure(0, weight=1)
        self.rm_pd_actual_tree = tree

    def _browse_rm_pd_actual_workbook(self) -> None:
        selected = filedialog.askopenfilename(
            title="Select STOCK แกลง 2 workbook",
            filetypes=[("Excel workbook", "*.xls *.xlsx *.xlsm *.xlsb"), ("All files", "*.*")],
        )
        if selected:
            self.rm_pd_actual_file_var.set(selected)
            self._load_rm_pd_actual_sheets()

    def _load_rm_pd_actual_sheets(self) -> None:
        try:
            workbook_path = self.rm_pd_actual_file_var.get().strip()
            sheets = list_rm_data_sheets(workbook_path)
            default_sheet = choose_default_rm_data_sheet(sheets, "data")
            self.rm_pd_actual_sheet_combo.configure(values=sheets)
            self.rm_pd_actual_sheet_var.set(default_sheet)
            self.rm_pd_actual_extract_button.configure(state=tk.NORMAL if sheets else tk.DISABLED)
            self.rm_pd_actual_status_var.set(f"Loaded {len(sheets)} worksheets.")
        except Exception as exc:
            self.rm_pd_actual_sheet_combo.configure(values=[])
            self.rm_pd_actual_sheet_var.set("")
            self.rm_pd_actual_extract_button.configure(state=tk.DISABLED)
            self.rm_pd_actual_status_var.set("Could not read workbook.")
            messagebox.showerror("Workbook error", str(exc))

    def _start_rm_pd_actual_extraction(self) -> None:
        workbook_path = self.rm_pd_actual_file_var.get().strip()
        sheet_name = self.rm_pd_actual_sheet_var.get()
        if not workbook_path or not sheet_name:
            messagebox.showwarning("Missing source", "Please select an Excel file and worksheet.")
            return
        try:
            records = extract_pd_actual_records(workbook_path, sheet_name)
        except Exception as exc:
            self.rm_pd_actual_status_var.set("Extraction failed.")
            messagebox.showerror("Extraction error", str(exc))
            return
        self.rm_pd_actual_records = records
        self.rm_pd_actual_sort_column = None
        self.rm_pd_actual_sort_descending = False
        self._refresh_rm_pd_actual_table()
        try:
            save_pd_actual_records(
                self.pd_actual_data_file_path, records,
                source_file=workbook_path, source_sheet=sheet_name,
            )
        except ValueError as exc:
            self.rm_pd_actual_status_var.set(
                f"Loaded {len(records):,} rows, but could not save: {exc}"
            )
            return
        self.rm_pd_actual_status_var.set(
            f"Loaded and saved {len(records):,} rows from '{sheet_name}'."
        )

    def _load_saved_rm_pd_actual_data(self) -> None:
        """Restore the last-extracted STOCK แกลง 2 rows, so it survives a restart."""

        try:
            records, source_file, source_sheet = load_pd_actual_records(
                self.pd_actual_data_file_path
            )
        except ValueError as exc:
            self.rm_pd_actual_status_var.set(str(exc))
            return
        if not records:
            return
        self.rm_pd_actual_records = records
        if source_file:
            self.rm_pd_actual_file_var.set(source_file)
        if source_sheet:
            self.rm_pd_actual_sheet_var.set(source_sheet)
        self._refresh_rm_pd_actual_table()
        self.rm_pd_actual_status_var.set(f"Loaded {len(records):,} saved rows from last extraction.")

    def _sort_rm_pd_actual(self, column: str) -> None:
        if self.rm_pd_actual_sort_column == column:
            self.rm_pd_actual_sort_descending = not self.rm_pd_actual_sort_descending
        else:
            self.rm_pd_actual_sort_column = column
            self.rm_pd_actual_sort_descending = False
        self._refresh_rm_pd_actual_table()

    def _refresh_rm_pd_actual_table(self) -> None:
        tree = self.rm_pd_actual_tree
        tree.delete(*tree.get_children())
        rows = list(self.rm_pd_actual_records)
        if self.rm_pd_actual_sort_column is not None:
            column = self.rm_pd_actual_sort_column
            if column in PD_ACTUAL_FLOAT_FIELDS:
                rows.sort(
                    key=lambda record: getattr(record, column),
                    reverse=self.rm_pd_actual_sort_descending,
                )
            else:
                rows.sort(
                    key=lambda record: getattr(record, column).casefold(),
                    reverse=self.rm_pd_actual_sort_descending,
                )
        for index, record in enumerate(rows):
            tree.insert(
                "", tk.END, iid=str(index),
                values=[getattr(record, key) for key, _label in PD_ACTUAL_COLUMNS],
            )
        for key, label in PD_ACTUAL_COLUMNS:
            marker = ""
            if key == self.rm_pd_actual_sort_column:
                marker = " ↓" if self.rm_pd_actual_sort_descending else " ↑"
            tree.heading(key, text=f"{label}{marker}")

    def _build_rm_pd_tab(self) -> None:
        self.rm_pd_type_var = tk.StringVar()
        self.rm_pd_status_var = tk.StringVar(
            value="ยังไม่มีข้อมูล — ไปที่ อัพโหลดข้อมูล STOCK On Hand แล้วกด Extract data ก่อน"
        )

        ttk.Label(self.rm_pd_tab, text="PD Freeze", font=("Segoe UI", 16, "bold")).pack(anchor=tk.W)
        ttk.Label(
            self.rm_pd_tab, text="Sum of Gross wt แบ่งตาม Remark x Action Repack",
        ).pack(anchor=tk.W, pady=(3, 18))

        filters = ttk.Frame(self.rm_pd_tab)
        filters.pack(fill=tk.X)

        plant_frame = ttk.Frame(filters)
        plant_frame.pack(side=tk.LEFT, padx=(0, 20))
        ttk.Label(plant_frame, text="Plant").pack(anchor=tk.W)
        self.rm_pd_plant_listbox = tk.Listbox(
            plant_frame, selectmode=tk.EXTENDED, height=4, exportselection=False, width=18,
        )
        self.rm_pd_plant_listbox.pack()
        self.rm_pd_plant_listbox.bind("<<ListboxSelect>>", lambda _e: self._refresh_rm_pd_table())

        type_frame = ttk.Frame(filters)
        type_frame.pack(side=tk.LEFT)
        ttk.Label(type_frame, text="Type").pack(anchor=tk.W)
        self.rm_pd_type_combo = ttk.Combobox(
            type_frame, textvariable=self.rm_pd_type_var, state="readonly", width=22,
        )
        self.rm_pd_type_combo.pack()
        self.rm_pd_type_combo.bind("<<ComboboxSelected>>", lambda _e: self._refresh_rm_pd_table())

        ttk.Label(
            self.rm_pd_tab,
            textvariable=self.rm_pd_status_var,
            relief=tk.SUNKEN,
            anchor=tk.W,
            padding=(6, 3),
        ).pack(fill=tk.X, pady=(10, 0))

        table_frame = ttk.Frame(self.rm_pd_tab)
        table_frame.pack(fill=tk.BOTH, expand=True, pady=(10, 0))
        tree = ttk.Treeview(table_frame, show="headings")
        vertical = ttk.Scrollbar(table_frame, orient=tk.VERTICAL, command=tree.yview)
        horizontal = ttk.Scrollbar(table_frame, orient=tk.HORIZONTAL, command=tree.xview)
        tree.configure(yscrollcommand=vertical.set, xscrollcommand=horizontal.set)
        tree.grid(row=0, column=0, sticky="nsew")
        vertical.grid(row=0, column=1, sticky="ns")
        horizontal.grid(row=1, column=0, sticky="ew")
        table_frame.rowconfigure(0, weight=1)
        table_frame.columnconfigure(0, weight=1)
        self.rm_pd_tree = tree

    def _refresh_rm_pd_filters(self) -> None:
        records = self.rm_data_records
        if not records:
            self.rm_pd_status_var.set("ยังไม่มีข้อมูล — ไปที่ อัพโหลดข้อมูล STOCK On Hand แล้วกด Extract data ก่อน")
            self.rm_pd_plant_listbox.delete(0, tk.END)
            self.rm_pd_type_combo.configure(values=[])
            self.rm_pd_type_var.set("")
            self._refresh_rm_pd_table()
            return

        plants = sorted({record.plant for record in records if record.plant})
        types = sorted({record.type for record in records if record.type})
        previously_selected_plants = {
            self.rm_pd_plant_listbox.get(index)
            for index in self.rm_pd_plant_listbox.curselection()
        }
        self.rm_pd_plant_listbox.delete(0, tk.END)
        for plant in plants:
            self.rm_pd_plant_listbox.insert(tk.END, plant)
        for index, plant in enumerate(plants):
            if not previously_selected_plants or plant in previously_selected_plants:
                self.rm_pd_plant_listbox.selection_set(index)

        self.rm_pd_type_combo.configure(values=["All", *types])
        if self.rm_pd_type_var.get() not in types:
            self.rm_pd_type_var.set("RM For Wonton" if "RM For Wonton" in types else "All")
        self._refresh_rm_pd_table()

    def _refresh_rm_pd_table(self) -> None:
        tree = self.rm_pd_tree
        tree.delete(*tree.get_children())
        records = self.rm_data_records
        if not records:
            tree.configure(columns=())
            return

        selected_plants = {
            self.rm_pd_plant_listbox.get(index)
            for index in self.rm_pd_plant_listbox.curselection()
        }
        type_filter = self.rm_pd_type_var.get()
        stock_type = None if type_filter in ("", "All") else type_filter
        pivot = pivot_gross_wt_by_remark_and_action_repack(
            records, plants=selected_plants or None, stock_type=stock_type,
        )

        columns = ("remark", *pivot.column_keys, "grand_total")
        tree.configure(columns=columns)
        tree.heading("remark", text="Remark")
        tree.column("remark", width=140, minwidth=100, anchor=tk.W, stretch=False)
        for key in pivot.column_keys:
            tree.heading(key, text=key)
            tree.column(key, width=140, minwidth=90, anchor=tk.E, stretch=False)
        tree.heading("grand_total", text="Grand Total")
        tree.column("grand_total", width=140, minwidth=100, anchor=tk.E, stretch=False)

        for row in pivot.row_keys:
            values = (
                [row]
                + [
                    self._format_optional_number(pivot.matrix[row][col])
                    if pivot.matrix[row][col] else ""
                    for col in pivot.column_keys
                ]
                + [self._format_optional_number(pivot.row_totals[row])]
            )
            tree.insert("", tk.END, values=values)
        grand_row = (
            ["Grand Total"]
            + [self._format_optional_number(pivot.column_totals[col]) for col in pivot.column_keys]
            + [self._format_optional_number(pivot.grand_total)]
        )
        tree.insert("", tk.END, values=grand_row, tags=("grand_total",))
        tree.tag_configure("grand_total", font=("Segoe UI", 12, "bold"))

        self.rm_pd_status_var.set(
            f"{len(pivot.row_keys)} Remark × {len(pivot.column_keys)} Action Repack "
            f"• Grand Total {self._format_optional_number(pivot.grand_total)}"
        )

    def _build_rm_pd_actual_pivot_tab(self) -> None:
        """Pivot of STOCK แกลง 2 data: Sum of น้ำหนัก(กก.)ออก by ฟาร์ม-บ่อ → ขนาด Out."""

        self.rm_pd_actual_pivot_date_var = tk.StringVar(value="All")
        self.rm_pd_actual_pivot_status_var = tk.StringVar(
            value="ยังไม่มีข้อมูล — ไปที่ อัพโหลดข้อมูล STOCK แกลง 2 แล้วกด Extract data ก่อน"
        )

        ttk.Label(
            self.rm_pd_actual_pivot_tab, text="Pivot STOCK แกลง 2", font=("Segoe UI", 16, "bold"),
        ).pack(anchor=tk.W)
        ttk.Label(
            self.rm_pd_actual_pivot_tab,
            text="Sum of น้ำหนัก(กก.)ออก แบ่งตาม ฟาร์ม-บ่อ x ขนาด Out",
        ).pack(anchor=tk.W, pady=(3, 18))

        filters = ttk.Frame(self.rm_pd_actual_pivot_tab)
        filters.pack(fill=tk.X)
        date_frame = ttk.Frame(filters)
        date_frame.pack(side=tk.LEFT)
        ttk.Label(date_frame, text="วันที่ทำรายการ").pack(anchor=tk.W)
        self.rm_pd_actual_pivot_date_combo = ttk.Combobox(
            date_frame, textvariable=self.rm_pd_actual_pivot_date_var, state="readonly", width=22,
        )
        self.rm_pd_actual_pivot_date_combo.pack()
        self.rm_pd_actual_pivot_date_combo.bind(
            "<<ComboboxSelected>>", lambda _e: self._refresh_rm_pd_actual_pivot_table()
        )

        ttk.Label(
            self.rm_pd_actual_pivot_tab,
            textvariable=self.rm_pd_actual_pivot_status_var,
            relief=tk.SUNKEN,
            anchor=tk.W,
            padding=(6, 3),
        ).pack(fill=tk.X, pady=(10, 0))

        table_frame = ttk.Frame(self.rm_pd_actual_pivot_tab)
        table_frame.pack(fill=tk.BOTH, expand=True, pady=(10, 0))
        tree = ttk.Treeview(table_frame, columns=("total",), show="tree headings")
        tree.heading("#0", text="ฟาร์ม-บ่อ / ขนาด Out")
        tree.column("#0", width=320, minwidth=200, anchor=tk.W, stretch=False)
        tree.heading("total", text="Total")
        tree.column("total", width=140, minwidth=100, anchor=tk.E, stretch=False)
        vertical = ttk.Scrollbar(table_frame, orient=tk.VERTICAL, command=tree.yview)
        horizontal = ttk.Scrollbar(table_frame, orient=tk.HORIZONTAL, command=tree.xview)
        tree.configure(yscrollcommand=vertical.set, xscrollcommand=horizontal.set)
        tree.grid(row=0, column=0, sticky="nsew")
        vertical.grid(row=0, column=1, sticky="ns")
        horizontal.grid(row=1, column=0, sticky="ew")
        table_frame.rowconfigure(0, weight=1)
        table_frame.columnconfigure(0, weight=1)
        self.rm_pd_actual_pivot_tree = tree

    def _refresh_rm_pd_actual_pivot_filters(self) -> None:
        records = self.rm_pd_actual_records
        if not records:
            self.rm_pd_actual_pivot_status_var.set(
                "ยังไม่มีข้อมูล — ไปที่ อัพโหลดข้อมูล STOCK แกลง 2 แล้วกด Extract data ก่อน"
            )
            self.rm_pd_actual_pivot_date_combo.configure(values=["All"])
            self.rm_pd_actual_pivot_date_var.set("All")
            self._refresh_rm_pd_actual_pivot_table()
            return

        dates = sorted({record.transaction_date for record in records if record.transaction_date})
        self.rm_pd_actual_pivot_date_combo.configure(values=["All", *dates])
        if self.rm_pd_actual_pivot_date_var.get() not in ("All", *dates):
            self.rm_pd_actual_pivot_date_var.set("All")
        self._refresh_rm_pd_actual_pivot_table()

    def _refresh_rm_pd_actual_pivot_table(self) -> None:
        tree = self.rm_pd_actual_pivot_tree
        tree.delete(*tree.get_children())
        records = self.rm_pd_actual_records
        if not records:
            return

        date_filter = self.rm_pd_actual_pivot_date_var.get()
        transaction_dates = None if date_filter in ("", "All") else {date_filter}
        pivot = pivot_weight_out_by_farm_and_size(records, transaction_dates=transaction_dates)

        for farm in pivot.farm_keys:
            farm_id = tree.insert(
                "", tk.END, text=farm,
                values=(self._format_optional_number(pivot.farm_totals[farm]),),
                open=False,
            )
            for size in pivot.size_keys_by_farm[farm]:
                tree.insert(
                    farm_id, tk.END, text=size,
                    values=(self._format_optional_number(pivot.matrix[farm][size]),),
                )
        grand_id = tree.insert(
            "", tk.END, text="Grand Total",
            values=(self._format_optional_number(pivot.grand_total),),
            tags=("grand_total",),
        )
        tree.tag_configure("grand_total", font=("Segoe UI", 12, "bold"))

        self.rm_pd_actual_pivot_status_var.set(
            f"{len(pivot.farm_keys)} ฟาร์ม-บ่อ "
            f"• Grand Total {self._format_optional_number(pivot.grand_total)}"
        )

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
