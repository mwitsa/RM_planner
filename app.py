"""Tkinter desktop UI for extracting production orders and planning inputs."""

from __future__ import annotations

import math
import threading
import tkinter as tk
from datetime import date
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog, ttk

from assortment import AssortmentTable, load_assortment
from assortment_actual_store import (
    ActualAssortmentEntry,
    ActualAssortmentRecord,
    load_actual_records,
    upsert_actual_record,
)
from class_store import (
    ClassDefinition,
    load_class_definitions,
    upsert_class_definition,
)
from extractor import (
    ExtractionResult,
    OrderRecord,
    choose_default_sheet,
    export_csv,
    export_json,
    extract_orders,
    list_sheets,
)
from order_store import load_order_records, save_order_records
from order_filters import ALL_FILTER, FILTER_SPECS, filter_options, filter_orders
from rule_store import load_rules, save_rules


class ProductionPlanApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Production Plan Extractor / โปรแกรมดึงข้อมูลแผนผลิต")
        self.geometry("1180x720")
        self.minsize(900, 560)

        self.file_var = tk.StringVar()
        self.sheet_var = tk.StringVar()
        self.order_filter_vars = {
            key: tk.StringVar(value=ALL_FILTER) for key, _label in FILTER_SPECS
        }
        self.filter_count_var = tk.StringVar(value="Showing 0 orders")
        self.summary_var = tk.StringVar(value="Select a workbook to begin.")
        self.status_var = tk.StringVar(value="Ready")
        self.rule_status_var = tk.StringVar(value="Rules apply from top to bottom.")
        self.assortment_status_var = tk.StringVar(value="Assortment master has not been loaded.")
        self.assortment_actual_status_var = tk.StringVar(value="No saved actual assortment history yet.")
        self.class_status_var = tk.StringVar(value="No saved classes yet.")
        self.class_value_var = tk.StringVar()
        self.class_name_var = tk.StringVar()
        self.result: ExtractionResult | None = None
        self.saved_order_records: dict[str, OrderRecord] = {}
        self.order_records_by_id: dict[str, OrderRecord] = {}
        self.assortment_table: AssortmentTable | None = None
        self.rule_file_path = Path(__file__).resolve().parent / "plan_rules.json"
        self.assortment_file_path = Path(__file__).resolve().parent / "Data" / "RM" / "assortment.xlsx"
        self.assortment_actual_file_path = (
            Path(__file__).resolve().parent / "Data" / "RM" / "assortment_actual.json"
        )
        self.saved_orders_file_path = (
            Path(__file__).resolve().parent / "Data" / "Order" / "saved_orders.json"
        )
        self.class_definitions_file_path = (
            Path(__file__).resolve().parent / "Data" / "Class" / "class_definitions.json"
        )
        self.class_definitions: dict[str, ClassDefinition] = {}
        self._editing_class_id: str | None = None
        self.assortment_actual_records: dict[str, ActualAssortmentRecord] = {}
        self._editing_actual_record_id: str | None = None
        self._rule_text_by_item: dict[str, str] = {}
        self._drag_rule_item: str | None = None
        self._rule_drag_changed = False

        self._configure_style()
        self._build_ui()
        self._load_default_workbook()
        self._load_saved_rules()
        self._load_assortment_data()
        self._load_assortment_actual_history()
        self._load_saved_orders()
        self._load_saved_class_definitions()

    def _configure_style(self) -> None:
        style = ttk.Style(self)
        if "vista" in style.theme_names():
            style.theme_use("vista")
        style.configure("TNotebook.Tab", font=("Segoe UI", 10, "bold"), padding=(18, 8))
        style.configure("Summary.TLabel", font=("Segoe UI", 10, "bold"))
        style.configure("Treeview", rowheight=25, font=("Segoe UI", 9))
        style.configure("Treeview.Heading", font=("Segoe UI", 9, "bold"))

    def _build_ui(self) -> None:
        container = ttk.Frame(self, padding=10)
        container.pack(fill=tk.BOTH, expand=True)

        self.notebook = ttk.Notebook(container)
        self.notebook.pack(fill=tk.BOTH, expand=True)

        self.order_tab = ttk.Frame(self.notebook, padding=14)
        self.notebook.add(self.order_tab, text="Order")

        self.plan_rule_tab = ttk.Frame(self.notebook, padding=14)
        self.notebook.add(self.plan_rule_tab, text="Plan Rule")
        self._build_plan_rule_tab()

        self.class_define_tab = ttk.Frame(self.notebook, padding=14)
        self.notebook.add(self.class_define_tab, text="Class Define")
        self._build_class_define_tab()

        self.assortment_std_tab = ttk.Frame(self.notebook, padding=14)
        self.notebook.add(self.assortment_std_tab, text="Assortment STD")
        self._build_assortment_std_tab()

        self.assortment_actual_tab = ttk.Frame(self.notebook, padding=14)
        self.notebook.add(self.assortment_actual_tab, text="Assortment Actual")
        self._build_assortment_actual_tab()

        source = ttk.LabelFrame(self.order_tab, text="Source workbook", padding=12)
        source.pack(fill=tk.X)
        source.columnconfigure(1, weight=1)

        ttk.Label(source, text="Excel file:").grid(row=0, column=0, sticky=tk.W, padx=(0, 8))
        ttk.Entry(source, textvariable=self.file_var).grid(row=0, column=1, sticky=tk.EW)
        ttk.Button(source, text="Browse…", command=self._browse).grid(row=0, column=2, padx=(8, 0))

        ttk.Label(source, text="Worksheet:").grid(row=1, column=0, sticky=tk.W, padx=(0, 8), pady=(10, 0))
        self.sheet_combo = ttk.Combobox(source, textvariable=self.sheet_var, state="readonly", width=35)
        self.sheet_combo.grid(row=1, column=1, sticky=tk.W, pady=(10, 0))
        self.extract_button = ttk.Button(source, text="Extract data", command=self._start_extraction)
        self.extract_button.grid(row=1, column=2, padx=(8, 0), pady=(10, 0))

        controls = ttk.Frame(self.order_tab)
        controls.pack(fill=tk.X, pady=(14, 8))
        ttk.Label(controls, textvariable=self.summary_var, style="Summary.TLabel").pack(side=tk.LEFT)
        self.export_json_button = ttk.Button(
            controls, text="Export JSON", command=self._export_json, state=tk.DISABLED
        )
        self.export_json_button.pack(
            side=tk.RIGHT, padx=(8, 0)
        )
        self.export_csv_button = ttk.Button(
            controls, text="Export CSV", command=self._export_csv, state=tk.DISABLED
        )
        self.export_csv_button.pack(side=tk.RIGHT)
        self.save_orders_button = ttk.Button(
            controls,
            text="Save orders",
            command=self._save_orders,
            state=tk.DISABLED,
        )
        self.save_orders_button.pack(side=tk.RIGHT, padx=(0, 8))
        self.order_action_buttons = (
            self.export_json_button,
            self.export_csv_button,
            self.save_orders_button,
        )

        filter_frame = ttk.LabelFrame(self.order_tab, text="Filters", padding=8)
        filter_frame.pack(fill=tk.X, pady=(0, 8))
        self.order_filter_combos: dict[str, ttk.Combobox] = {}
        for index, (key, label) in enumerate(FILTER_SPECS):
            row = index // 4
            column = index % 4
            field = ttk.Frame(filter_frame)
            field.grid(row=row, column=column, sticky="ew", padx=(0, 8), pady=(0, 6))
            field.columnconfigure(1, weight=1)
            ttk.Label(field, text=f"{label}:").grid(row=0, column=0, sticky=tk.W, padx=(0, 5))
            width = 22 if key in ("customer", "group_1", "group_2") else 15
            combo = ttk.Combobox(
                field,
                textvariable=self.order_filter_vars[key],
                state="readonly",
                width=width,
                values=[ALL_FILTER],
            )
            combo.grid(row=0, column=1, sticky="ew")
            combo.bind("<<ComboboxSelected>>", lambda _event: self._refresh_preview())
            self.order_filter_combos[key] = combo
            filter_frame.columnconfigure(column, weight=1)

        filter_footer = ttk.Frame(filter_frame)
        filter_footer.grid(row=3, column=0, columnspan=4, sticky="ew", pady=(2, 0))
        ttk.Button(filter_footer, text="Clear filters", command=self._clear_order_filters).pack(
            side=tk.LEFT
        )
        ttk.Label(filter_footer, textvariable=self.filter_count_var, style="Summary.TLabel").pack(
            side=tk.LEFT, padx=(12, 0)
        )
        ttk.Label(filter_footer, text="Double-click Production to edit.").pack(side=tk.RIGHT)

        table_frame = ttk.Frame(self.order_tab)
        table_frame.pack(fill=tk.BOTH, expand=True)
        columns = (
            "date",
            "month",
            "year",
            "country",
            "customer",
            "group_1",
            "group_2",
            "packaging",
            "soup",
            "volume",
            "production",
        )
        self.tree = ttk.Treeview(table_frame, columns=columns, show="headings")
        headings = {
            "date": "Date",
            "month": "Month",
            "year": "Year",
            "country": "Country",
            "customer": "Customer",
            "group_1": "Group 1",
            "group_2": "Group 2",
            "packaging": "Packaging",
            "soup": "Soup",
            "volume": "Order volume",
            "production": "Production",
        }
        widths = {
            "date": 70,
            "month": 70,
            "year": 80,
            "country": 100,
            "customer": 260,
            "group_1": 190,
            "group_2": 210,
            "packaging": 140,
            "soup": 130,
            "volume": 120,
            "production": 120,
        }
        for column in columns:
            self.tree.heading(column, text=headings[column])
            anchor = tk.E if column in ("volume", "production") else tk.W
            self.tree.column(column, width=widths[column], minwidth=70, anchor=anchor)
        self.tree.bind("<Double-1>", self._edit_production_cell)

        vertical = ttk.Scrollbar(table_frame, orient=tk.VERTICAL, command=self.tree.yview)
        horizontal = ttk.Scrollbar(table_frame, orient=tk.HORIZONTAL, command=self.tree.xview)
        self.tree.configure(yscrollcommand=vertical.set, xscrollcommand=horizontal.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        vertical.grid(row=0, column=1, sticky="ns")
        horizontal.grid(row=1, column=0, sticky="ew")
        table_frame.rowconfigure(0, weight=1)
        table_frame.columnconfigure(0, weight=1)

        status = ttk.Label(
            self.order_tab,
            textvariable=self.status_var,
            relief=tk.SUNKEN,
            anchor=tk.W,
            padding=(6, 3),
        )
        status.pack(fill=tk.X, pady=(8, 0))

    def _build_plan_rule_tab(self) -> None:
        ttk.Label(
            self.plan_rule_tab,
            text="Waterfall priority: rules are applied from top to bottom.",
            style="Summary.TLabel",
        ).pack(anchor=tk.W, pady=(0, 10))

        editor = ttk.LabelFrame(self.plan_rule_tab, text="Rule text", padding=12)
        editor.pack(fill=tk.X)
        editor.columnconfigure(0, weight=1)

        self.rule_text = tk.Text(editor, height=4, wrap=tk.WORD, font=("Segoe UI", 10), undo=True)
        self.rule_text.grid(row=0, column=0, columnspan=6, sticky="ew")

        ttk.Button(editor, text="Add rule", command=self._add_rule).grid(row=1, column=0, sticky=tk.W, pady=(10, 0))
        ttk.Button(editor, text="Update selected", command=self._update_rule).grid(
            row=1, column=1, sticky=tk.W, padx=(8, 0), pady=(10, 0)
        )
        ttk.Button(editor, text="Delete", command=self._delete_rule).grid(
            row=1, column=2, sticky=tk.W, padx=(8, 0), pady=(10, 0)
        )
        ttk.Button(editor, text="Move up", command=lambda: self._move_rule(-1)).grid(
            row=1, column=3, sticky=tk.W, padx=(24, 0), pady=(10, 0)
        )
        ttk.Button(editor, text="Move down", command=lambda: self._move_rule(1)).grid(
            row=1, column=4, sticky=tk.W, padx=(8, 0), pady=(10, 0)
        )
        ttk.Button(editor, text="Save rules", command=self._save_rules).grid(
            row=1, column=5, sticky=tk.E, padx=(24, 0), pady=(10, 0)
        )

        list_frame = ttk.Frame(self.plan_rule_tab)
        list_frame.pack(fill=tk.BOTH, expand=True, pady=(12, 0))
        list_frame.rowconfigure(0, weight=1)
        list_frame.columnconfigure(0, weight=1)

        self.rules_tree = ttk.Treeview(
            list_frame,
            columns=("priority", "rule"),
            show="headings",
            selectmode="browse",
        )
        self.rules_tree.heading("priority", text="Apply order")
        self.rules_tree.heading("rule", text="Rule")
        self.rules_tree.column("priority", width=100, minwidth=90, anchor=tk.CENTER, stretch=False)
        self.rules_tree.column("rule", width=850, minwidth=300, anchor=tk.W)
        rule_scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.rules_tree.yview)
        self.rules_tree.configure(yscrollcommand=rule_scrollbar.set)
        self.rules_tree.grid(row=0, column=0, sticky="nsew")
        rule_scrollbar.grid(row=0, column=1, sticky="ns")

        self.rules_tree.bind("<<TreeviewSelect>>", self._select_rule)
        self.rules_tree.bind("<ButtonPress-1>", self._start_rule_drag, add="+")
        self.rules_tree.bind("<B1-Motion>", self._drag_rule)
        self.rules_tree.bind("<ButtonRelease-1>", self._finish_rule_drag)

        ttk.Label(
            self.plan_rule_tab,
            textvariable=self.rule_status_var,
            relief=tk.SUNKEN,
            anchor=tk.W,
            padding=(6, 3),
        ).pack(fill=tk.X, pady=(8, 0))

    def _build_class_define_tab(self) -> None:
        ttk.Label(
            self.class_define_tab,
            text="Class definition master data",
            style="Summary.TLabel",
        ).pack(anchor=tk.W, pady=(0, 10))

        form = ttk.LabelFrame(self.class_define_tab, text="Class details", padding=12)
        form.pack(fill=tk.X)
        form.columnconfigure(0, weight=1)
        form.columnconfigure(1, weight=2)

        class_box = ttk.LabelFrame(form, text="1. Class", padding=10)
        class_box.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        class_box.columnconfigure(0, weight=1)
        ttk.Entry(class_box, textvariable=self.class_value_var).grid(row=0, column=0, sticky="ew")

        name_box = ttk.LabelFrame(form, text="2. Name", padding=10)
        name_box.grid(row=0, column=1, sticky="ew")
        name_box.columnconfigure(0, weight=1)
        ttk.Entry(name_box, textvariable=self.class_name_var).grid(row=0, column=0, sticky="ew")

        define_box = ttk.LabelFrame(form, text="3. Define", padding=10)
        define_box.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(10, 0))
        define_box.columnconfigure(0, weight=1)
        self.class_definition_text = tk.Text(
            define_box,
            height=4,
            wrap=tk.WORD,
            font=("Segoe UI", 10),
            undo=True,
        )
        self.class_definition_text.grid(row=0, column=0, sticky="ew")

        actions = ttk.Frame(form)
        actions.grid(row=2, column=0, columnspan=2, sticky="e", pady=(10, 0))
        ttk.Button(actions, text="New", command=self._new_class_form).pack(side=tk.LEFT)
        self.save_class_button = ttk.Button(
            actions,
            text="Save class",
            command=self._save_class_definition,
        )
        self.save_class_button.pack(side=tk.LEFT, padx=(8, 0))

        saved_frame = ttk.LabelFrame(self.class_define_tab, text="Saved classes", padding=10)
        saved_frame.pack(fill=tk.BOTH, expand=True, pady=(12, 0))
        saved_frame.rowconfigure(0, weight=1)
        saved_frame.columnconfigure(0, weight=1)
        self.class_tree = ttk.Treeview(
            saved_frame,
            columns=("class", "name", "define"),
            show="headings",
            selectmode="browse",
        )
        self.class_tree.heading("class", text="Class")
        self.class_tree.heading("name", text="Name")
        self.class_tree.heading("define", text="Define")
        self.class_tree.column("class", width=140, minwidth=100, stretch=False)
        self.class_tree.column("name", width=260, minwidth=160)
        self.class_tree.column("define", width=600, minwidth=260)
        class_scrollbar = ttk.Scrollbar(saved_frame, orient=tk.VERTICAL, command=self.class_tree.yview)
        self.class_tree.configure(yscrollcommand=class_scrollbar.set)
        self.class_tree.grid(row=0, column=0, sticky="nsew")
        class_scrollbar.grid(row=0, column=1, sticky="ns")
        self.class_tree.bind("<Double-1>", lambda _event: self._edit_selected_class())
        ttk.Button(saved_frame, text="Edit selected", command=self._edit_selected_class).grid(
            row=1, column=0, sticky="e", pady=(8, 0)
        )

        ttk.Label(
            self.class_define_tab,
            textvariable=self.class_status_var,
            relief=tk.SUNKEN,
            anchor=tk.W,
            padding=(6, 3),
        ).pack(fill=tk.X, pady=(8, 0))

    def _new_class_form(self, set_status: bool = True) -> None:
        self.class_value_var.set("")
        self.class_name_var.set("")
        self.class_definition_text.delete("1.0", tk.END)
        self._editing_class_id = None
        self.save_class_button.configure(text="Save class")
        if set_status:
            self.class_status_var.set("New class form ready.")

    def _save_class_definition(self) -> None:
        try:
            saved = upsert_class_definition(
                self.class_definitions_file_path,
                self.class_value_var.get(),
                self.class_name_var.get(),
                self.class_definition_text.get("1.0", "end-1c"),
                self._editing_class_id,
            )
        except ValueError as exc:
            messagebox.showerror("Save class", str(exc))
            return
        action = "Updated" if self._editing_class_id else "Saved"
        self._load_saved_class_definitions()
        self._new_class_form(set_status=False)
        self.class_status_var.set(f"{action} class {saved.class_value}.")

    def _load_saved_class_definitions(self) -> None:
        try:
            definitions = load_class_definitions(self.class_definitions_file_path)
        except ValueError as exc:
            self.class_status_var.set(str(exc))
            return
        self.class_definitions = {item.class_id: item for item in definitions}
        self.class_tree.delete(*self.class_tree.get_children())
        for item in sorted(definitions, key=lambda value: value.class_value.casefold()):
            self.class_tree.insert(
                "",
                tk.END,
                iid=item.class_id,
                values=(item.class_value, item.name, " ".join(item.definition.split())),
            )
        if definitions:
            self.class_status_var.set(f"Loaded {len(definitions)} saved classes.")

    def _edit_selected_class(self) -> None:
        selected = self.class_tree.selection()
        if not selected:
            messagebox.showwarning("No class selected", "Select a saved class to edit.")
            return
        item = self.class_definitions.get(selected[0])
        if not item:
            messagebox.showerror("Class error", "The selected class could not be found.")
            return
        self.class_value_var.set(item.class_value)
        self.class_name_var.set(item.name)
        self.class_definition_text.delete("1.0", tk.END)
        self.class_definition_text.insert("1.0", item.definition)
        self._editing_class_id = item.class_id
        self.save_class_button.configure(text="Update class")
        self.class_status_var.set(f"Editing class {item.class_value}.")

    def _build_assortment_std_tab(self) -> None:
        ttk.Label(
            self.assortment_std_tab,
            text="Shrimp size assortment master data",
            style="Summary.TLabel",
        ).pack(anchor=tk.W)
        ttk.Label(
            self.assortment_std_tab,
            text=(
                "Columns = base shrimp size harvested (for example S.43).  "
                "Rows = actual output size.  Cells = output yield percentage."
            ),
        ).pack(anchor=tk.W, pady=(2, 10))

        source_frame = ttk.Frame(self.assortment_std_tab)
        source_frame.pack(fill=tk.X, pady=(0, 10))
        ttk.Label(source_frame, text="Master file:", style="Summary.TLabel").pack(side=tk.LEFT)
        ttk.Label(source_frame, text=str(self.assortment_file_path)).pack(side=tk.LEFT, padx=(6, 0))
        ttk.Button(source_frame, text="Reload master", command=self._load_assortment_data).pack(side=tk.RIGHT)

        table_frame = ttk.Frame(self.assortment_std_tab)
        table_frame.pack(fill=tk.BOTH, expand=True)
        table_frame.rowconfigure(0, weight=1)
        table_frame.columnconfigure(0, weight=1)

        self.assortment_tree = ttk.Treeview(table_frame, show="headings", selectmode="browse")
        vertical = ttk.Scrollbar(table_frame, orient=tk.VERTICAL, command=self.assortment_tree.yview)
        horizontal = ttk.Scrollbar(table_frame, orient=tk.HORIZONTAL, command=self.assortment_tree.xview)
        self.assortment_tree.configure(yscrollcommand=vertical.set, xscrollcommand=horizontal.set)
        self.assortment_tree.grid(row=0, column=0, sticky="nsew")
        vertical.grid(row=0, column=1, sticky="ns")
        horizontal.grid(row=1, column=0, sticky="ew")
        self.assortment_tree.bind("<ButtonRelease-1>", self._describe_assortment_cell)

        ttk.Label(
            self.assortment_std_tab,
            textvariable=self.assortment_status_var,
            relief=tk.SUNKEN,
            anchor=tk.W,
            padding=(6, 3),
        ).pack(fill=tk.X, pady=(8, 0))

    def _build_assortment_actual_tab(self) -> None:
        today = date.today()
        self.actual_day_var = tk.StringVar(value=f"{today.day:02d}")
        self.actual_month_var = tk.StringVar(value=f"{today.month:02d}")
        self.actual_year_var = tk.StringVar(value=f"{today.year:04d}")

        pane = ttk.Panedwindow(self.assortment_actual_tab, orient=tk.HORIZONTAL)
        pane.pack(fill=tk.BOTH, expand=True)
        form_panel = ttk.Frame(pane, padding=(0, 0, 12, 0))
        history_panel = ttk.Frame(pane, padding=(12, 0, 0, 0), width=350)
        pane.add(form_panel, weight=3)
        pane.add(history_panel, weight=2)

        ttk.Label(form_panel, text="Actual shrimp assortment", style="Summary.TLabel").pack(anchor=tk.W)
        ttk.Label(
            form_panel,
            text="Choose the harvest date, then enter one Size and Weight pair in each box.",
        ).pack(anchor=tk.W, pady=(2, 10))

        date_frame = ttk.LabelFrame(form_panel, text="Harvest date", padding=10)
        date_frame.pack(fill=tk.X, pady=(0, 10))
        ttk.Label(date_frame, text="Date").pack(side=tk.LEFT)
        ttk.Combobox(
            date_frame,
            textvariable=self.actual_day_var,
            values=[f"{day:02d}" for day in range(1, 32)],
            state="readonly",
            width=5,
        ).pack(side=tk.LEFT, padx=(6, 14))
        ttk.Label(date_frame, text="Month").pack(side=tk.LEFT)
        ttk.Combobox(
            date_frame,
            textvariable=self.actual_month_var,
            values=[f"{month:02d}" for month in range(1, 13)],
            state="readonly",
            width=5,
        ).pack(side=tk.LEFT, padx=(6, 14))
        ttk.Label(date_frame, text="Year").pack(side=tk.LEFT)
        ttk.Combobox(
            date_frame,
            textvariable=self.actual_year_var,
            values=[str(year) for year in range(today.year - 5, today.year + 6)],
            width=7,
        ).pack(side=tk.LEFT, padx=(6, 0))
        self.assortment_actual_save_button = ttk.Button(
            date_frame,
            text="Save actual",
            command=self._save_assortment_actual,
        )
        self.assortment_actual_save_button.pack(side=tk.RIGHT)
        ttk.Button(date_frame, text="New", command=self._new_assortment_actual_form).pack(
            side=tk.RIGHT, padx=(0, 8)
        )

        box_header = ttk.Frame(form_panel)
        box_header.pack(fill=tk.X, pady=(0, 8))
        ttk.Label(box_header, text="Size / Weight entries", style="Summary.TLabel").pack(side=tk.LEFT)
        ttk.Button(
            box_header,
            text="+ Add another box",
            command=self._add_assortment_actual_box,
        ).pack(side=tk.RIGHT)

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

        self.assortment_actual_boxes: list[dict[str, object]] = []
        self._add_assortment_actual_box()

        ttk.Label(history_panel, text="Saved history", style="Summary.TLabel").pack(anchor=tk.W)
        ttk.Label(history_panel, text="Select a saved day to edit its entries.").pack(
            anchor=tk.W, pady=(2, 10)
        )
        history_table = ttk.Frame(history_panel)
        history_table.pack(fill=tk.BOTH, expand=True)
        history_table.rowconfigure(0, weight=1)
        history_table.columnconfigure(0, weight=1)
        self.assortment_actual_history_tree = ttk.Treeview(
            history_table,
            columns=("date", "entries", "weight"),
            show="headings",
            selectmode="browse",
        )
        self.assortment_actual_history_tree.heading("date", text="Date")
        self.assortment_actual_history_tree.heading("entries", text="Boxes")
        self.assortment_actual_history_tree.heading("weight", text="Total weight")
        self.assortment_actual_history_tree.column("date", width=105, anchor=tk.CENTER)
        self.assortment_actual_history_tree.column("entries", width=65, anchor=tk.CENTER)
        self.assortment_actual_history_tree.column("weight", width=110, anchor=tk.E)
        history_scrollbar = ttk.Scrollbar(
            history_table,
            orient=tk.VERTICAL,
            command=self.assortment_actual_history_tree.yview,
        )
        self.assortment_actual_history_tree.configure(yscrollcommand=history_scrollbar.set)
        self.assortment_actual_history_tree.grid(row=0, column=0, sticky="nsew")
        history_scrollbar.grid(row=0, column=1, sticky="ns")
        self.assortment_actual_history_tree.bind(
            "<Double-1>", lambda _event: self._edit_selected_assortment_actual()
        )
        ttk.Button(
            history_panel,
            text="Edit selected",
            command=self._edit_selected_assortment_actual,
        ).pack(fill=tk.X, pady=(8, 0))
        ttk.Label(
            self.assortment_actual_tab,
            textvariable=self.assortment_actual_status_var,
            relief=tk.SUNKEN,
            anchor=tk.W,
            padding=(6, 3),
        ).pack(fill=tk.X, pady=(8, 0))

    def _add_assortment_actual_box(self, size: str = "", weight: str = "") -> None:
        size_var = tk.StringVar(value=size)
        weight_var = tk.StringVar(value=weight)
        box = ttk.LabelFrame(self.assortment_actual_list, padding=12)
        box.pack(fill=tk.X, pady=(0, 10))
        box.columnconfigure(0, weight=1)
        box.columnconfigure(1, weight=1)

        size_section = ttk.LabelFrame(box, text="Size", padding=10)
        size_section.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        size_section.columnconfigure(0, weight=1)
        ttk.Entry(size_section, textvariable=size_var).grid(row=0, column=0, sticky="ew")

        weight_section = ttk.LabelFrame(box, text="Weight", padding=10)
        weight_section.grid(row=0, column=1, sticky="ew", padx=(0, 8))
        weight_section.columnconfigure(0, weight=1)
        ttk.Entry(weight_section, textvariable=weight_var).grid(row=0, column=0, sticky="ew")

        ttk.Button(
            box,
            text="Remove",
            command=lambda current_box=box: self._remove_assortment_actual_box(current_box),
        ).grid(row=0, column=2, sticky=tk.E)

        self.assortment_actual_boxes.append(
            {"frame": box, "size": size_var, "weight": weight_var}
        )
        self._renumber_assortment_actual_boxes()
        self.assortment_actual_canvas.after_idle(
            lambda: self.assortment_actual_canvas.configure(
                scrollregion=self.assortment_actual_canvas.bbox("all")
            )
        )

    def _remove_assortment_actual_box(self, box: ttk.LabelFrame) -> None:
        for index, entry in enumerate(self.assortment_actual_boxes):
            if entry["frame"] == box:
                box.destroy()
                self.assortment_actual_boxes.pop(index)
                break
        if not self.assortment_actual_boxes:
            self._add_assortment_actual_box()
        else:
            self._renumber_assortment_actual_boxes()

    def _renumber_assortment_actual_boxes(self) -> None:
        for number, entry in enumerate(self.assortment_actual_boxes, start=1):
            frame = entry["frame"]
            if isinstance(frame, ttk.LabelFrame):
                frame.configure(text=f"Assortment box {number}")

    def _new_assortment_actual_form(self, set_status: bool = True) -> None:
        today = date.today()
        self.actual_day_var.set(f"{today.day:02d}")
        self.actual_month_var.set(f"{today.month:02d}")
        self.actual_year_var.set(f"{today.year:04d}")
        self._editing_actual_record_id = None
        self.assortment_actual_save_button.configure(text="Save actual")
        self._set_assortment_actual_boxes([])
        if set_status:
            self.assortment_actual_status_var.set("New actual assortment form ready.")

    def _set_assortment_actual_boxes(self, entries: list[ActualAssortmentEntry]) -> None:
        for box_entry in self.assortment_actual_boxes:
            frame = box_entry["frame"]
            if isinstance(frame, ttk.LabelFrame):
                frame.destroy()
        self.assortment_actual_boxes.clear()
        if entries:
            for entry in entries:
                self._add_assortment_actual_box(entry.size, self._format_weight(entry.weight))
        else:
            self._add_assortment_actual_box()

    def _collect_assortment_actual_entries(self) -> list[ActualAssortmentEntry]:
        entries: list[ActualAssortmentEntry] = []
        for number, box_entry in enumerate(self.assortment_actual_boxes, start=1):
            size_var = box_entry["size"]
            weight_var = box_entry["weight"]
            if not isinstance(size_var, tk.StringVar) or not isinstance(weight_var, tk.StringVar):
                continue
            size = size_var.get().strip()
            weight_text = weight_var.get().strip().replace(",", "")
            if not size and not weight_text:
                continue
            if not size or not weight_text:
                raise ValueError(f"Assortment box {number} needs both Size and Weight.")
            try:
                weight = float(weight_text)
            except ValueError as exc:
                raise ValueError(f"Assortment box {number} has an invalid Weight.") from exc
            entries.append(ActualAssortmentEntry(size=size, weight=weight))
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
                self._editing_actual_record_id,
            )
        except ValueError as exc:
            messagebox.showerror("Save actual assortment", str(exc))
            return
        action = "Updated" if self._editing_actual_record_id else "Saved"
        self._load_assortment_actual_history()
        self._new_assortment_actual_form(set_status=False)
        self.assortment_actual_status_var.set(
            f"{action} {len(record.entries)} entries for {record.record_date}."
        )

    def _load_assortment_actual_history(self) -> None:
        try:
            records = load_actual_records(self.assortment_actual_file_path)
        except ValueError as exc:
            self.assortment_actual_status_var.set(str(exc))
            return
        self.assortment_actual_records = {record.record_id: record for record in records}
        self.assortment_actual_history_tree.delete(
            *self.assortment_actual_history_tree.get_children()
        )
        for record in sorted(
            records,
            key=lambda item: (item.record_date, item.updated_at),
            reverse=True,
        ):
            self.assortment_actual_history_tree.insert(
                "",
                tk.END,
                iid=record.record_id,
                values=(
                    record.record_date,
                    len(record.entries),
                    self._format_weight(record.total_weight),
                ),
            )
        if records:
            self.assortment_actual_status_var.set(f"Loaded {len(records)} saved history records.")

    def _edit_selected_assortment_actual(self) -> None:
        selected = self.assortment_actual_history_tree.selection()
        if not selected:
            messagebox.showwarning("No history selected", "Select a saved record to edit.")
            return
        record = self.assortment_actual_records.get(selected[0])
        if not record:
            messagebox.showerror("History error", "The selected record could not be found.")
            return
        year, month, day = record.record_date.split("-")
        self.actual_day_var.set(day)
        self.actual_month_var.set(month)
        self.actual_year_var.set(year)
        self._set_assortment_actual_boxes(list(record.entries))
        self._editing_actual_record_id = record.record_id
        self.assortment_actual_save_button.configure(text="Update saved")
        self.assortment_actual_status_var.set(
            f"Editing saved actual assortment for {record.record_date}."
        )

    @staticmethod
    def _format_weight(weight: float) -> str:
        return f"{weight:,.6f}".rstrip("0").rstrip(".")

    def _load_assortment_data(self) -> None:
        try:
            table = load_assortment(self.assortment_file_path)
        except (FileNotFoundError, ValueError) as exc:
            self.assortment_table = None
            self.assortment_tree.delete(*self.assortment_tree.get_children())
            self.assortment_status_var.set(str(exc))
            return

        self.assortment_table = table
        self._show_assortment_table(table)
        if table.invalid_base_sizes:
            invalid = ", ".join(
                f"{base_size} ({total:.1%})" for base_size, total in table.invalid_base_sizes
            )
            self.assortment_status_var.set(
                f"Warning: output percentages do not total 100% for {invalid}."
            )
        else:
            self.assortment_status_var.set(
                f"Loaded {len(table.base_sizes)} base sizes × {len(table.output_sizes)} output ranges "
                f"from sheet {table.sheet_name}. Every base-size distribution totals 100%."
            )

    def _show_assortment_table(self, table: AssortmentTable) -> None:
        self.assortment_tree.delete(*self.assortment_tree.get_children())
        columns = ("actual_output", *[f"base_{index}" for index in range(len(table.base_sizes))])
        self.assortment_tree.configure(columns=columns)
        self.assortment_tree.heading("actual_output", text="Actual output size")
        self.assortment_tree.column(
            "actual_output",
            width=150,
            minwidth=130,
            stretch=False,
            anchor=tk.CENTER,
        )
        for index, base_size in enumerate(table.base_sizes):
            column = f"base_{index}"
            self.assortment_tree.heading(column, text=base_size)
            self.assortment_tree.column(column, width=76, minwidth=65, stretch=False, anchor=tk.CENTER)

        for output_size, percentages in zip(table.output_sizes, table.percentages):
            display_percentages = ["" if value == 0 else f"{value:.1%}" for value in percentages]
            self.assortment_tree.insert("", tk.END, values=(output_size, *display_percentages))

    def _describe_assortment_cell(self, event: tk.Event) -> None:
        if not self.assortment_table:
            return
        item = self.assortment_tree.identify_row(event.y)
        column_id = self.assortment_tree.identify_column(event.x)
        if not item or not column_id:
            return
        displayed_column = int(column_id.removeprefix("#"))
        if displayed_column <= 1:
            return
        base_index = displayed_column - 2
        output_index = self.assortment_tree.index(item)
        if base_index >= len(self.assortment_table.base_sizes):
            return
        base_size = self.assortment_table.base_sizes[base_index]
        output_size = self.assortment_table.output_sizes[output_index]
        percentage = self.assortment_table.percentages[output_index][base_index]
        self.assortment_status_var.set(
            f"Base harvest {base_size} → actual output {output_size}: {percentage:.4%} "
            f"(displayed as {percentage:.1%})."
        )

    def _editor_rule_text(self) -> str:
        return self.rule_text.get("1.0", "end-1c").strip()

    def _insert_rule(self, text: str) -> str:
        item = self.rules_tree.insert("", tk.END, values=("", " ".join(text.split())))
        self._rule_text_by_item[item] = text
        self._renumber_rules()
        return item

    def _add_rule(self) -> None:
        text = self._editor_rule_text()
        if not text:
            messagebox.showwarning("Empty rule", "Enter the rule text first.")
            return
        item = self._insert_rule(text)
        self.rules_tree.selection_set(item)
        self.rules_tree.focus(item)
        self.rules_tree.see(item)
        self.rule_text.delete("1.0", tk.END)
        self.rule_status_var.set("Rule added. Click Save rules to keep this waterfall order.")

    def _update_rule(self) -> None:
        selected = self.rules_tree.selection()
        if not selected:
            messagebox.showwarning("No rule selected", "Select a rule to update.")
            return
        text = self._editor_rule_text()
        if not text:
            messagebox.showwarning("Empty rule", "Enter the updated rule text first.")
            return
        item = selected[0]
        self._rule_text_by_item[item] = text
        self._renumber_rules()
        self.rule_status_var.set("Rule updated. Click Save rules to keep the change.")

    def _delete_rule(self) -> None:
        selected = self.rules_tree.selection()
        if not selected:
            messagebox.showwarning("No rule selected", "Select a rule to delete.")
            return
        item = selected[0]
        self.rules_tree.delete(item)
        self._rule_text_by_item.pop(item, None)
        self.rule_text.delete("1.0", tk.END)
        self._renumber_rules()
        self.rule_status_var.set("Rule removed. Click Save rules to keep the change.")

    def _move_rule(self, direction: int) -> None:
        selected = self.rules_tree.selection()
        if not selected:
            messagebox.showwarning("No rule selected", "Select a rule to move.")
            return
        item = selected[0]
        current_index = self.rules_tree.index(item)
        destination = current_index + direction
        if destination < 0 or destination >= len(self.rules_tree.get_children()):
            return
        self.rules_tree.move(item, "", destination)
        self._renumber_rules()
        self.rules_tree.see(item)
        self.rule_status_var.set("Rule order changed. Click Save rules to keep the waterfall order.")

    def _select_rule(self, _event: tk.Event | None = None) -> None:
        selected = self.rules_tree.selection()
        if not selected:
            return
        text = self._rule_text_by_item.get(selected[0], "")
        self.rule_text.delete("1.0", tk.END)
        self.rule_text.insert("1.0", text)

    def _start_rule_drag(self, event: tk.Event) -> None:
        item = self.rules_tree.identify_row(event.y)
        self._drag_rule_item = item or None
        self._rule_drag_changed = False
        if item:
            self.rules_tree.selection_set(item)
            self.rules_tree.focus(item)

    def _drag_rule(self, event: tk.Event) -> str:
        if not self._drag_rule_item:
            return "break"
        target = self.rules_tree.identify_row(event.y)
        if target and target != self._drag_rule_item:
            self.rules_tree.move(self._drag_rule_item, "", self.rules_tree.index(target))
            self._renumber_rules()
            self._rule_drag_changed = True
        return "break"

    def _finish_rule_drag(self, _event: tk.Event) -> None:
        if self._rule_drag_changed:
            self.rule_status_var.set("Rule order changed. Click Save rules to keep the waterfall order.")
        self._drag_rule_item = None
        self._rule_drag_changed = False

    def _renumber_rules(self) -> None:
        for priority, item in enumerate(self.rules_tree.get_children(), start=1):
            text = self._rule_text_by_item[item]
            self.rules_tree.item(item, values=(priority, " ".join(text.split())))

    def _load_saved_rules(self) -> None:
        try:
            rules = load_rules(self.rule_file_path)
        except ValueError as exc:
            self.rule_status_var.set(str(exc))
            messagebox.showerror("Rule file error", str(exc))
            return
        for text in rules:
            self._insert_rule(text)
        if rules:
            self.rule_status_var.set(f"Loaded {len(rules)} saved rules. Top rule applies first.")

    def _save_rules(self) -> None:
        ordered_rules = [self._rule_text_by_item[item] for item in self.rules_tree.get_children()]
        try:
            save_rules(self.rule_file_path, ordered_rules)
        except ValueError as exc:
            messagebox.showerror("Save error", str(exc))
            return
        self.rule_status_var.set(f"Saved {len(ordered_rules)} rules in waterfall order.")

    def _load_default_workbook(self) -> None:
        candidate = Path(__file__).resolve().parent / "Data" / "Order" / "แผน.xlsx"
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
        for record in result.records:
            saved = self.saved_order_records.get(record.record_id)
            if saved is not None:
                record.production = saved.production
        self.result = result
        self.order_records_by_id = {record.record_id: record for record in result.records}
        for key, _label in FILTER_SPECS:
            self.order_filter_combos[key].configure(
                values=[ALL_FILTER, *filter_options(result.records, key)]
            )
            self.order_filter_vars[key].set(ALL_FILTER)
        self._update_order_summary()
        for button in self.order_action_buttons:
            button.configure(state=tk.NORMAL)
        self.extract_button.configure(state=tk.NORMAL)
        if result.header_row == 0:
            self.status_var.set(f"Loaded {len(result.records):,} locally saved orders.")
        else:
            self.status_var.set(
                f"Complete. Header row {result.header_row}; "
                f"{len(result.issues):,} incomplete/non-order rows skipped."
            )
        self._refresh_preview()

    def _show_error(self, exc: Exception) -> None:
        self.extract_button.configure(state=tk.NORMAL)
        self.status_var.set("Extraction failed.")
        messagebox.showerror("Extraction error", str(exc))

    def _refresh_preview(self) -> None:
        self.tree.delete(*self.tree.get_children())
        if not self.result:
            return
        records = filter_orders(
            self.result.records,
            {key: variable.get() for key, variable in self.order_filter_vars.items()},
        )
        for index, record in enumerate(records):
            item_id = record.record_id or f"order_{index}"
            self.tree.insert(
                "",
                tk.END,
                iid=item_id,
                values=(
                    record.date,
                    record.month,
                    record.year,
                    record.country,
                    record.customer_name,
                    record.group_1,
                    record.group_2,
                    record.packaging,
                    record.soup,
                    f"{record.order_volume:,.6f}".rstrip("0").rstrip("."),
                    self._format_optional_number(record.production),
                ),
            )
        self.filter_count_var.set(
            f"Showing {len(records):,} of {len(self.result.records):,} orders"
        )

    def _clear_order_filters(self) -> None:
        for variable in self.order_filter_vars.values():
            variable.set(ALL_FILTER)
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
        self._update_order_summary()
        self.status_var.set("Production changed. Click Save orders to keep the change.")

    def _update_order_summary(self) -> None:
        if not self.result:
            return
        records = self.result.records
        customers = {record.customer_name for record in records}
        months = {record.month_key for record in records}
        total_volume = sum(record.order_volume for record in records)
        total_production = sum(record.production or 0 for record in records)
        self.summary_var.set(
            f"{len(records):,} orders  |  {len(customers):,} customers  |  "
            f"{len(months):,} months  |  volume {total_volume:,.2f}  |  "
            f"production {total_production:,.2f}"
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
        return f"{value:,.6f}".rstrip("0").rstrip(".")

    def _export_csv(self) -> None:
        if not self.result:
            return
        destination = filedialog.asksaveasfilename(
            title="Export structured orders as CSV",
            defaultextension=".csv",
            initialfile="production_orders.csv",
            filetypes=[("CSV file", "*.csv")],
        )
        if destination:
            export_csv(self.result.records, destination)
            self.status_var.set(f"CSV exported: {destination}")
            messagebox.showinfo("Export complete", f"Saved {len(self.result.records):,} orders.")

    def _export_json(self) -> None:
        if not self.result:
            return
        destination = filedialog.asksaveasfilename(
            title="Export structured orders as JSON",
            defaultextension=".json",
            initialfile="production_orders.json",
            filetypes=[("JSON file", "*.json")],
        )
        if destination:
            export_json(self.result.records, destination)
            self.status_var.set(f"JSON exported: {destination}")
            messagebox.showinfo("Export complete", f"Saved {len(self.result.records):,} orders.")


if __name__ == "__main__":
    ProductionPlanApp().mainloop()
