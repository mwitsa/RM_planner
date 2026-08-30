"""Tkinter desktop UI for extracting production orders and planning inputs."""

from __future__ import annotations

import math
import threading
import tkinter as tk
from collections.abc import Callable, Iterable
from datetime import date
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog, ttk

from assortment import AssortmentTable, load_assortment, predict_assortment
from assortment_range_store import (
    SIZE_CLASSES,
    AssortmentSizeRange,
    classify_size_range,
    default_size_ranges,
    load_size_ranges,
    normalize_size_class,
    save_size_ranges,
    SizeClassWeightSummary,
    summarize_size_class_weight_details,
)
from assortment_actual_store import (
    ActualAssortmentEntry,
    ActualAssortmentRecord,
    combine_size_range,
    delete_actual_record,
    estimate_wonton_pieces,
    load_actual_records,
    split_size_range,
    upsert_actual_record,
)
from class_store import (
    ALL_CLASS_FILTER,
    ClassDefinition,
    add_missing_class_definitions,
    class_filter_options,
    filter_class_definitions,
    load_class_definitions,
    order_class_names,
    upsert_class_definition,
)
from capacity_store import (
    CapacitySettings,
    capacities_at_percentage,
    load_capacity_settings,
    save_capacity_settings,
)
from extractor import (
    ExtractionResult,
    OrderRecord,
    choose_default_sheet,
    extract_orders,
    list_sheets,
)
from order_store import load_order_records, merge_order_records, save_order_records
from order_filters import (
    ALL_FILTER,
    FILTER_SPECS,
    NUMERIC_ORDER_COLUMNS,
    SCHEDULE_DATE_COLUMN,
    cascading_filter_state,
    current_and_future_orders,
    filter_options,
    filter_orders,
    sort_orders,
)
from plan_engine import PlanResult, generate_plan
from rm_timeline import build_rm_timeline
from rule_store import load_rules, save_rules


RM_NAVIGATION_ITEMS = (
    ("timeline", "Stock"),
    ("predict", "Assortment STD"),
)


def rm_navigation_section(section: str) -> str:
    """Map the nested stock editor to its parent Stock navigation item."""

    return "timeline" if section == "actual" else section


ASSORTMENT_CLASS_WIDTH = 72
ASSORTMENT_OUTPUT_WIDTH = 150
ASSORTMENT_BASE_WIDTH = 76
ASSORTMENT_HEADER_HEIGHT = 34
ASSORTMENT_ROW_HEIGHT = 29
ASSORTMENT_CLASS_COLORS = {
    "M": ("#d8edff", "#2374ab"),
    "S+": ("#dcf5df", "#338a3e"),
}
ORDER_COLUMN_FILTER_KEYS = {
    "order_no": "order_no",
    "year": "year",
    "month": "month",
    "date": "date",
    "country": "country",
    "customer": "customer",
    "group_1": "group_1",
    "group_2": "group_2",
    "packaging": "packaging",
    "rm_size": "rm_size",
    "soup": "soup",
    "wontons_per_cup": "wontons_per_cup",
    "order_unit": "order_unit",
    "order_cups": "order_cups",
    "cups_per_unit": "cups_per_unit",
    "total_wontons": "total_wontons",
    "production": "production",
}
DEFAULT_EXISTING_STOCK_PIECES_PER_KG = {
    "M": "53",
    "S+": "69.25",
}


class ProductionPlanApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Production Plan Extractor / โปรแกรมดึงข้อมูลแผนผลิต")
        self.geometry("1180x720")
        self.minsize(900, 560)

        self.file_var = tk.StringVar()
        self.sheet_var = tk.StringVar()
        self.order_filter_selections: dict[str, str | frozenset[str]] = {
            key: ALL_FILTER for key, _label in FILTER_SPECS
        }
        self.order_filter_options: dict[str, list[str]] = {
            key: [] for key, _label in FILTER_SPECS
        }
        self._order_filter_popup: tk.Toplevel | None = None
        self._order_filter_outside_binding: str | None = None
        self.summary_var = tk.StringVar(value="Select a workbook to begin.")
        self.status_var = tk.StringVar(value="Ready")
        self.rule_status_var = tk.StringVar(value="Rules apply from top to bottom.")
        self.assortment_status_var = tk.StringVar(value="Assortment master has not been loaded.")
        self.assortment_actual_status_var = tk.StringVar(value="No saved stock records yet.")
        self.existing_stock_status_var = tk.StringVar(value="No saved existing stock yet.")
        self.class_status_var = tk.StringVar(value="No saved classes yet.")
        self.class_value_var = tk.StringVar()
        self.class_name_var = tk.StringVar()
        self.class_filter_var = tk.StringVar(value=ALL_CLASS_FILTER)
        self.class_name_search_var = tk.StringVar()
        self.class_group_filter_var = tk.StringVar(value=ALL_CLASS_FILTER)
        self.class_filter_count_var = tk.StringVar(value="Showing 0 classes")
        self.capacity_status_var = tk.StringVar(value="Capacity settings have not been saved yet.")
        self.plan_summary_var = tk.StringVar(value="Generate a plan from the saved preparation data.")
        self.plan_status_var = tk.StringVar(value="Ready to generate a production plan.")
        self.result: ExtractionResult | None = None
        self.saved_order_records: dict[str, OrderRecord] = {}
        self.order_records_by_id: dict[str, OrderRecord] = {}
        self.order_sort_column: str | None = SCHEDULE_DATE_COLUMN
        self.order_sort_descending = False
        self.hide_past_orders = True
        self.assortment_table: AssortmentTable | None = None
        self.rule_file_path = Path(__file__).resolve().parent / "plan_rules.json"
        self.assortment_file_path = Path(__file__).resolve().parent / "Data" / "RM" / "assortment.xlsx"
        self.assortment_size_range_file_path = (
            Path(__file__).resolve().parent / "Data" / "RM" / "assortment_size_ranges.json"
        )
        self.assortment_actual_file_path = (
            Path(__file__).resolve().parent / "Data" / "RM" / "assortment_actual.json"
        )
        self.saved_orders_file_path = (
            Path(__file__).resolve().parent / "Data" / "Order" / "saved_orders.json"
        )
        self.class_definitions_file_path = (
            Path(__file__).resolve().parent / "Data" / "Class" / "class_definitions.json"
        )
        self.capacity_file_path = (
            Path(__file__).resolve().parent / "Data" / "Capacity" / "capacity.json"
        )
        self.capacity_settings = CapacitySettings()
        self.plan_result: PlanResult | None = None
        self.class_definitions: dict[str, ClassDefinition] = {}
        self._editing_class_id: str | None = None
        self.assortment_actual_records: dict[str, ActualAssortmentRecord] = {}
        self.assortment_size_ranges: dict[str, tuple[int, int]] = {}
        self._assortment_range_drag: dict[str, object] | None = None
        self._assortment_range_drag_changed = False
        self._editing_actual_record_id: str | None = None
        self._editing_existing_stock_id: str | None = None
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
        self._load_capacity_settings()

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

        self.plan_tab = ttk.Frame(self.notebook, padding=14)
        self.notebook.add(self.plan_tab, text="Plan")
        self._build_plan_tab()

        self.rm_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.rm_tab, text="RM")
        self._build_rm_tab()

        self.plan_rule_tab = ttk.Frame(self.notebook, padding=14)
        self.notebook.add(self.plan_rule_tab, text="Class Rule")
        self._build_plan_rule_tab()

        self.class_define_tab = ttk.Frame(self.notebook, padding=14)
        self.notebook.add(self.class_define_tab, text="Class Define")
        self._build_class_define_tab()

        self.capacity_tab = ttk.Frame(self.notebook, padding=14)
        self.notebook.add(self.capacity_tab, text="Capacity")
        self._build_capacity_tab()

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
        self.save_orders_button = ttk.Button(
            controls,
            text="Save orders",
            command=self._save_orders,
            state=tk.DISABLED,
        )
        self.save_orders_button.pack(side=tk.RIGHT, padx=(0, 8))
        self.clear_order_filters_button = ttk.Button(
            controls,
            text="Clear column filters",
            command=self._clear_order_filters,
            state=tk.DISABLED,
        )
        self.clear_order_filters_button.pack(side=tk.RIGHT, padx=(0, 8))
        self.past_orders_button = ttk.Button(
            controls,
            text="Show past orders",
            command=self._toggle_past_orders,
        )
        self.past_orders_button.pack(side=tk.RIGHT, padx=(0, 8))
        self.order_action_buttons = (self.save_orders_button,)

        table_frame = ttk.Frame(self.order_tab)
        table_frame.pack(fill=tk.BOTH, expand=True)
        columns = (
            "order_no",
            "date",
            "month",
            "year",
            "country",
            "customer",
            "group_1",
            "group_2",
            "packaging",
            "rm_size",
            "soup",
            "wontons_per_cup",
            "order_unit",
            "order_cups",
            "cups_per_unit",
            "total_wontons",
            "production",
        )
        self.tree = ttk.Treeview(table_frame, columns=columns, show="headings")
        self.order_headings = {
            "order_no": "Order No.",
            "date": "Date",
            "month": "Month",
            "year": "Year",
            "country": "Country",
            "customer": "Customer",
            "group_1": "Group 1",
            "group_2": "Group 2",
            "packaging": "Packaging",
            "rm_size": "RM Size",
            "soup": "Soup",
            "wontons_per_cup": "ลูกเกี๊ยว/ถ้วย",
            "order_unit": "Order (unit)",
            "order_cups": "Order (ถ้วย)",
            "cups_per_unit": "ถ้วย/Unit",
            "total_wontons": "จำนวนเกี๊ยว",
            "production": "Production",
        }
        widths = {
            "order_no": 105,
            "date": 70,
            "month": 70,
            "year": 80,
            "country": 100,
            "customer": 260,
            "group_1": 190,
            "group_2": 210,
            "packaging": 140,
            "rm_size": 90,
            "soup": 130,
            "wontons_per_cup": 120,
            "order_unit": 120,
            "order_cups": 120,
            "cups_per_unit": 110,
            "total_wontons": 130,
            "production": 120,
        }
        for column in columns:
            self.tree.heading(
                column,
                text=self.order_headings[column],
                command=lambda selected_column=column: self._open_order_column_filter(
                    selected_column
                ),
            )
            anchor = tk.E if column in (
                "order_unit",
                "order_cups",
                "cups_per_unit",
                "wontons_per_cup",
                "total_wontons",
                "production",
            ) else tk.W
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
        self.rm_timeline_market_var = tk.StringVar(value="ALL")
        self.rm_stock_as_of_var = tk.StringVar(value="—")
        self.rm_stock_total_var = tk.StringVar(value="0 kg")
        self.rm_stock_unused_var = tk.StringVar(value="0 kg")
        self.rm_stock_wontons_var = tk.StringVar(value="0")
        self.rm_stock_size_vars = {
            size_class: {
                "stock": tk.StringVar(value="0 kg"),
                "domestic": tk.StringVar(value="0 kg"),
                "export": tk.StringVar(value="0 kg"),
                "domestic_wontons": tk.StringVar(value="0"),
                "export_wontons": tk.StringVar(value="0"),
            }
            for size_class in SIZE_CLASSES
        }
        self.rm_timeline_status_var = tk.StringVar(
            value="Cumulative stock before generated Plan consumption."
        )

        header = ttk.Frame(self.rm_timeline_tab)
        header.pack(fill=tk.X, pady=(0, 10))
        header_text = ttk.Frame(header)
        header_text.pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Label(
            header_text,
            text="RM Stock",
            style="Summary.TLabel",
        ).pack(anchor=tk.W)
        ttk.Label(
            header_text,
            text="Current incoming RM stock before generated Plan usage.",
        ).pack(anchor=tk.W, pady=(2, 0))
        ttk.Button(
            header,
            text="+ Add stock",
            command=self._open_stock_editor,
        ).pack(side=tk.RIGHT, anchor=tk.N)

        controls = ttk.LabelFrame(self.rm_timeline_tab, text="Stock filters", padding=8)
        controls.pack(fill=tk.X, pady=(0, 8))
        ttk.Label(controls, text="Use for").pack(side=tk.LEFT)
        market_combo = ttk.Combobox(
            controls,
            textvariable=self.rm_timeline_market_var,
            values=("ALL", "DOMESTIC", "EXPORT", "UNASSIGNED"),
            state="readonly",
            width=12,
        )
        market_combo.pack(side=tk.LEFT, padx=(6, 16))
        ttk.Button(
            controls,
            text="Clear filters",
            command=self._clear_rm_timeline_filters,
        ).pack(side=tk.LEFT)
        market_combo.bind("<<ComboboxSelected>>", self._refresh_rm_timeline)

        overview = ttk.LabelFrame(
            self.rm_timeline_tab,
            text="Stock overview",
            padding=12,
        )
        overview.pack(fill=tk.X, pady=(0, 8))
        for column in range(4):
            overview.columnconfigure(column, weight=1)
        overview_fields = (
            ("As of", self.rm_stock_as_of_var),
            ("Total stock", self.rm_stock_total_var),
            ("Unused stock", self.rm_stock_unused_var),
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

        size_sections = ttk.Frame(self.rm_timeline_tab)
        size_sections.pack(fill=tk.X, pady=(0, 8))
        stock_card_colors = {
            "M": ("#eaf3fb", "#8bb8dd", "#174f78"),
            "S+": ("#edf7ee", "#97c79b", "#285f2d"),
        }
        for column, size_class in enumerate(SIZE_CLASSES):
            size_sections.columnconfigure(column, weight=1)
            background, border, foreground = stock_card_colors[size_class]
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
                    0 if column == len(SIZE_CLASSES) - 1 else 4,
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
            for market_column, market_name in enumerate(("DOMESTIC", "EXPORT")):
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
                    text=market_name,
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
                    textvariable=self.rm_stock_size_vars[size_class][market_name.casefold()],
                    background="#ffffff",
                    foreground=foreground,
                    font=("Segoe UI", 12, "bold"),
                ).grid(row=1, column=0, sticky=tk.W, pady=(3, 0))
                tk.Label(
                    market_details,
                    textvariable=self.rm_stock_size_vars[size_class][
                        f"{market_name.casefold()}_wontons"
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
            "rm_ids",
            "incoming",
            "stock",
            "M",
            "S+",
            "unused",
            "incoming_wontons",
            "stock_wontons",
        )
        self.rm_timeline_tree = ttk.Treeview(table_frame, columns=columns, show="headings")
        headings = {
            "date": "Date",
            "rm_ids": "RM IDs",
            "incoming": "RM in (kg)",
            "stock": "Stock (kg)",
            "M": "M stock (kg)",
            "S+": "S+ stock (kg)",
            "unused": "Unused stock (kg)",
            "incoming_wontons": "RM in Est. wonton",
            "stock_wontons": "Stock Est. wonton",
        }
        widths = {
            "date": 95,
            "rm_ids": 190,
            "incoming": 100,
            "stock": 100,
            "M": 110,
            "S+": 110,
            "unused": 125,
            "incoming_wontons": 135,
            "stock_wontons": 135,
        }
        numeric = set(columns) - {"date", "rm_ids"}
        for column in columns:
            self.rm_timeline_tree.heading(column, text=headings[column])
            self.rm_timeline_tree.column(
                column,
                width=widths[column],
                minwidth=75,
                anchor=tk.E if column in numeric else tk.W,
                stretch=column == "rm_ids",
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

    def _clear_rm_timeline_filters(self) -> None:
        self.rm_timeline_market_var.set("ALL")
        self._refresh_rm_timeline()

    def _refresh_rm_timeline(self, _event: tk.Event | None = None) -> None:
        if not hasattr(self, "rm_timeline_tree"):
            return
        try:
            records = tuple(self.assortment_actual_records.values())
            ranges = self._current_assortment_size_range_definitions()
            selected_market = self.rm_timeline_market_var.get().strip().casefold()
            rows = build_rm_timeline(
                records,
                ranges,
                market_type=selected_market,
            )
            market_rows = {}
            for market in ("domestic", "export"):
                if selected_market == market:
                    market_rows[market] = rows
                elif selected_market == "all":
                    market_rows[market] = build_rm_timeline(
                        records,
                        ranges,
                        market_type=market,
                    )
                else:
                    market_rows[market] = ()
        except ValueError as exc:
            self.rm_timeline_tree.delete(*self.rm_timeline_tree.get_children())
            self.rm_stock_as_of_var.set("Unavailable")
            self.rm_stock_total_var.set("—")
            self.rm_stock_unused_var.set("—")
            self.rm_stock_wontons_var.set("—")
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
                    ", ".join(row.rm_ids),
                    self._format_optional_number(row.incoming_kg),
                    self._format_optional_number(row.cumulative_kg),
                    self._format_size_class_summary(row.m_stock),
                    self._format_size_class_summary(row.s_plus_stock),
                    self._format_size_class_summary(row.unused_stock),
                    self._format_optional_number(row.incoming_wontons),
                    self._format_optional_number(row.cumulative_wontons),
                ),
            )
        record_count = sum(len(row.rm_ids) for row in rows)
        if rows:
            final = rows[-1]
            self.rm_stock_as_of_var.set(final.record_date)
            self.rm_stock_total_var.set(
                f"{self._format_optional_number(final.cumulative_kg)} kg"
            )
            self.rm_stock_unused_var.set(
                f"{self._format_optional_number(final.unused_stock.total)} kg"
            )
            self.rm_stock_wontons_var.set(
                self._format_optional_number(final.cumulative_wontons)
            )
            size_summaries = {
                "M": final.m_stock,
                "S+": final.s_plus_stock,
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
                        market_summary = (
                            market_final.m_stock
                            if size_class == "M"
                            else market_final.s_plus_stock
                        )
                        market_total = market_summary.total
                        market_wontons = (
                            market_final.m_wontons
                            if size_class == "M"
                            else market_final.s_plus_wontons
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
            self.rm_stock_unused_var.set("0 kg")
            self.rm_stock_wontons_var.set("0")
            for variables in self.rm_stock_size_vars.values():
                variables["stock"].set("0 kg")
                for market in ("domestic", "export"):
                    variables[market].set("0 kg")
                    variables[f"{market}_wontons"].set("0")
            self.rm_timeline_status_var.set(
                "No RM stock records for these filters."
            )

    def _build_existing_stock_tab(self) -> None:
        ttk.Label(
            self.existing_stock_tab,
            text="Existing RM Stock",
            style="Summary.TLabel",
        ).pack(anchor=tk.W)
        ttk.Label(
            self.existing_stock_tab,
            text=(
                "Enter old/opening stock directly by M and S+ class. "
                "Average pieces/kg is used to estimate how many wontons the stock can produce."
            ),
        ).pack(anchor=tk.W, pady=(2, 10))

        self.existing_day_var = tk.StringVar()
        self.existing_month_var = tk.StringVar()
        self.existing_year_var = tk.StringVar()
        self.existing_market_var = tk.StringVar(value="DOMESTIC")
        self.existing_stock_entry_vars: dict[str, dict[str, tk.StringVar]] = {
            size_class: {
                "weight": tk.StringVar(),
                "pieces_per_kg": tk.StringVar(
                    value=DEFAULT_EXISTING_STOCK_PIECES_PER_KG[size_class]
                ),
            }
            for size_class in SIZE_CLASSES
        }

        form = ttk.LabelFrame(self.existing_stock_tab, text="Opening stock details", padding=10)
        form.pack(fill=tk.X, pady=(0, 10))
        for column in range(8):
            form.columnconfigure(column, weight=1 if column in {6} else 0)

        ttk.Label(form, text="Date").grid(row=0, column=0, sticky=tk.W)
        ttk.Combobox(
            form,
            textvariable=self.existing_day_var,
            values=[f"{value:02d}" for value in range(1, 32)],
            state="readonly",
            width=5,
        ).grid(row=0, column=1, sticky=tk.W, padx=(6, 4))
        ttk.Label(form, text="Month").grid(row=0, column=2, sticky=tk.W, padx=(8, 0))
        ttk.Combobox(
            form,
            textvariable=self.existing_month_var,
            values=[f"{value:02d}" for value in range(1, 13)],
            state="readonly",
            width=5,
        ).grid(row=0, column=3, sticky=tk.W, padx=(6, 4))
        ttk.Label(form, text="Year").grid(row=0, column=4, sticky=tk.W, padx=(8, 0))
        ttk.Combobox(
            form,
            textvariable=self.existing_year_var,
            values=[str(value) for value in range(date.today().year - 10, date.today().year + 11)],
            state="readonly",
            width=7,
        ).grid(row=0, column=5, sticky=tk.W, padx=(6, 12))
        ttk.Label(form, text="Use for").grid(row=0, column=6, sticky=tk.E)
        ttk.Combobox(
            form,
            textvariable=self.existing_market_var,
            values=("DOMESTIC", "EXPORT"),
            state="readonly",
            width=12,
        ).grid(row=0, column=7, sticky=tk.W, padx=(6, 0))

        entry_frame = ttk.Frame(form)
        entry_frame.grid(row=1, column=0, columnspan=8, sticky="ew", pady=(12, 0))
        entry_frame.columnconfigure(1, weight=1)
        entry_frame.columnconfigure(2, weight=1)
        ttk.Label(entry_frame, text="RM class", style="Summary.TLabel").grid(
            row=0, column=0, sticky=tk.W, padx=(0, 14)
        )
        ttk.Label(entry_frame, text="Existing weight (kg)", style="Summary.TLabel").grid(
            row=0, column=1, sticky=tk.W, padx=(0, 8)
        )
        ttk.Label(entry_frame, text="Average shrimp (pieces/kg)", style="Summary.TLabel").grid(
            row=0, column=2, sticky=tk.W
        )
        for row_index, size_class in enumerate(SIZE_CLASSES, start=1):
            variables = self.existing_stock_entry_vars[size_class]
            ttk.Label(entry_frame, text=size_class, font=("Segoe UI", 10, "bold")).grid(
                row=row_index, column=0, sticky=tk.W, padx=(0, 14), pady=(6, 0)
            )
            ttk.Entry(entry_frame, textvariable=variables["weight"]).grid(
                row=row_index, column=1, sticky="ew", padx=(0, 8), pady=(6, 0)
            )
            ttk.Entry(entry_frame, textvariable=variables["pieces_per_kg"]).grid(
                row=row_index, column=2, sticky="ew", pady=(6, 0)
            )

        actions = ttk.Frame(form)
        actions.grid(row=2, column=0, columnspan=8, sticky=tk.E, pady=(12, 0))
        ttk.Button(actions, text="New", command=self._new_existing_stock_form).pack(
            side=tk.LEFT
        )
        self.existing_stock_save_button = ttk.Button(
            actions,
            text="Save existing stock",
            command=self._save_existing_stock,
        )
        self.existing_stock_save_button.pack(side=tk.LEFT, padx=(8, 0))

        history = ttk.LabelFrame(self.existing_stock_tab, text="Saved existing stock", padding=8)
        history.pack(fill=tk.BOTH, expand=True)
        history.rowconfigure(0, weight=1)
        history.columnconfigure(0, weight=1)
        columns = (
            "rm_id",
            "date",
            "market",
            "m_kg",
            "m_ppkg",
            "s_plus_kg",
            "s_plus_ppkg",
            "total_kg",
            "wontons",
        )
        self.existing_stock_tree = ttk.Treeview(history, columns=columns, show="headings")
        headings = {
            "rm_id": "RM ID",
            "date": "Date",
            "market": "Use for",
            "m_kg": "M (kg)",
            "m_ppkg": "M pcs/kg",
            "s_plus_kg": "S+ (kg)",
            "s_plus_ppkg": "S+ pcs/kg",
            "total_kg": "Total (kg)",
            "wontons": "Est. wonton",
        }
        numeric = set(columns) - {"rm_id", "date", "market"}
        for column in columns:
            self.existing_stock_tree.heading(column, text=headings[column])
            self.existing_stock_tree.column(
                column,
                width=100,
                minwidth=75,
                anchor=tk.E if column in numeric else tk.W,
                stretch=column == "rm_id",
            )
        vertical = ttk.Scrollbar(history, orient=tk.VERTICAL, command=self.existing_stock_tree.yview)
        horizontal = ttk.Scrollbar(history, orient=tk.HORIZONTAL, command=self.existing_stock_tree.xview)
        self.existing_stock_tree.configure(
            yscrollcommand=vertical.set,
            xscrollcommand=horizontal.set,
        )
        self.existing_stock_tree.grid(row=0, column=0, sticky="nsew")
        vertical.grid(row=0, column=1, sticky="ns")
        horizontal.grid(row=1, column=0, sticky="ew")
        self.existing_stock_tree.bind(
            "<Double-1>", lambda _event: self._edit_selected_existing_stock()
        )
        history_actions = ttk.Frame(self.existing_stock_tab)
        history_actions.pack(fill=tk.X, pady=(8, 0))
        ttk.Button(
            history_actions,
            text="Edit selected",
            command=self._edit_selected_existing_stock,
        ).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 4))
        ttk.Button(
            history_actions,
            text="Delete selected",
            command=self._delete_selected_existing_stock,
        ).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(4, 0))
        ttk.Label(
            self.existing_stock_tab,
            textvariable=self.existing_stock_status_var,
            relief=tk.SUNKEN,
            anchor=tk.W,
            padding=(6, 3),
        ).pack(fill=tk.X, pady=(8, 0))
        self._new_existing_stock_form(set_status=False)

    def _new_existing_stock_form(self, set_status: bool = True) -> None:
        today = date.today()
        self.existing_day_var.set(f"{today.day:02d}")
        self.existing_month_var.set(f"{today.month:02d}")
        self.existing_year_var.set(str(today.year))
        self.existing_market_var.set("DOMESTIC")
        self._editing_existing_stock_id = None
        for size_class, variables in self.existing_stock_entry_vars.items():
            variables["weight"].set("")
            variables["pieces_per_kg"].set(
                DEFAULT_EXISTING_STOCK_PIECES_PER_KG[size_class]
            )
        self.existing_stock_save_button.configure(text="Save existing stock")
        if set_status:
            self.existing_stock_status_var.set("New existing-stock form ready.")

    def _selected_existing_stock_date(self) -> str:
        try:
            selected = date(
                int(self.existing_year_var.get()),
                int(self.existing_month_var.get()),
                int(self.existing_day_var.get()),
            )
        except ValueError as exc:
            raise ValueError("Choose a valid existing-stock date.") from exc
        return selected.isoformat()

    def _collect_existing_stock_entries(self) -> list[ActualAssortmentEntry]:
        entries: list[ActualAssortmentEntry] = []
        for size_class in SIZE_CLASSES:
            variables = self.existing_stock_entry_vars[size_class]
            weight_text = variables["weight"].get().strip().replace(",", "")
            pieces_text = variables["pieces_per_kg"].get().strip().replace(",", "")
            if not weight_text:
                continue
            try:
                weight = float(weight_text)
                pieces_per_kg = float(pieces_text)
            except ValueError as exc:
                raise ValueError(
                    f"{size_class} needs valid Weight and Average pieces/kg numbers."
                ) from exc
            entries.append(
                ActualAssortmentEntry(
                    size=size_class,
                    weight=weight,
                    size_class=size_class,
                    pieces_per_kg=pieces_per_kg,
                )
            )
        if not entries:
            raise ValueError("Enter existing weight for at least one RM class.")
        return entries

    def _save_existing_stock(self) -> None:
        try:
            record = upsert_actual_record(
                self.assortment_actual_file_path,
                self._selected_existing_stock_date(),
                self._collect_existing_stock_entries(),
                record_id=self._editing_existing_stock_id,
                record_type="existing",
                market_type=self.existing_market_var.get(),
            )
        except ValueError as exc:
            messagebox.showerror("Save existing stock", str(exc))
            return
        action = "Updated" if self._editing_existing_stock_id else "Saved"
        self._load_assortment_actual_history()
        self._new_existing_stock_form(set_status=False)
        self.existing_stock_status_var.set(
            f"{action} {record.rm_id} for {record.market_type.upper()} with "
            f"{self._format_optional_number(record.total_weight)} kg."
        )

    def _refresh_existing_stock_history_table(self) -> None:
        if not hasattr(self, "existing_stock_tree"):
            return
        selected = set(self.existing_stock_tree.selection())
        self.existing_stock_tree.delete(*self.existing_stock_tree.get_children())
        existing_records = [
            record
            for record in self.assortment_actual_records.values()
            if record.record_type == "existing"
        ]
        for record in sorted(
            existing_records,
            key=lambda item: (item.record_date, item.updated_at),
            reverse=True,
        ):
            entries = {entry.size_class: entry for entry in record.entries}
            values: list[str] = [record.rm_id, record.record_date, record.market_type.upper()]
            for size_class in SIZE_CLASSES:
                entry = entries.get(size_class)
                values.extend(
                    [
                        self._format_optional_number(entry.weight) if entry else "",
                        self._format_optional_number(entry.pieces_per_kg) if entry else "",
                    ]
                )
            values.extend(
                [
                    self._format_optional_number(record.total_weight),
                    self._format_optional_number(estimate_wonton_pieces(record.entries)),
                ]
            )
            self.existing_stock_tree.insert("", tk.END, iid=record.record_id, values=values)
        for record_id in selected:
            if self.existing_stock_tree.exists(record_id):
                self.existing_stock_tree.selection_add(record_id)
        if existing_records:
            self.existing_stock_status_var.set(
                f"Loaded {len(existing_records):,} saved existing-stock records."
            )

    def _edit_selected_existing_stock(self) -> None:
        selected = self.existing_stock_tree.selection()
        if not selected:
            messagebox.showwarning("No stock selected", "Select existing stock to edit.")
            return
        record = self.assortment_actual_records.get(selected[0])
        if not record or record.record_type != "existing":
            messagebox.showerror("Stock error", "The selected existing stock could not be found.")
            return
        year, month, day = record.record_date.split("-")
        self.existing_day_var.set(day)
        self.existing_month_var.set(month)
        self.existing_year_var.set(year)
        self.existing_market_var.set(record.market_type.upper())
        entries = {entry.size_class: entry for entry in record.entries}
        for size_class, variables in self.existing_stock_entry_vars.items():
            entry = entries.get(size_class)
            variables["weight"].set(
                self._format_optional_number(entry.weight) if entry else ""
            )
            variables["pieces_per_kg"].set(
                self._format_optional_number(entry.pieces_per_kg)
                if entry
                else DEFAULT_EXISTING_STOCK_PIECES_PER_KG[size_class]
            )
        self._editing_existing_stock_id = record.record_id
        self.existing_stock_save_button.configure(text="Update existing stock")
        self.existing_stock_status_var.set(f"Editing {record.rm_id} from {record.record_date}.")

    def _delete_selected_existing_stock(self) -> None:
        selected = self.existing_stock_tree.selection()
        if not selected:
            messagebox.showwarning("No stock selected", "Select existing stock to delete.")
            return
        record = self.assortment_actual_records.get(selected[0])
        if not record or record.record_type != "existing":
            messagebox.showerror("Stock error", "The selected existing stock could not be found.")
            return
        if not messagebox.askyesno(
            "Delete existing stock",
            f"Permanently delete {record.rm_id} from {record.record_date}?\n\nThis cannot be undone.",
        ):
            return
        try:
            deleted = delete_actual_record(self.assortment_actual_file_path, record.record_id)
        except ValueError as exc:
            messagebox.showerror("Delete existing stock", str(exc))
            return
        if self._editing_existing_stock_id == deleted.record_id:
            self._new_existing_stock_form(set_status=False)
        self._load_assortment_actual_history()
        self.existing_stock_status_var.set(f"Deleted {deleted.rm_id} existing stock.")

    def _build_plan_tab(self) -> None:
        controls = ttk.Frame(self.plan_tab)
        controls.pack(fill=tk.X, pady=(0, 8))
        ttk.Button(
            controls,
            text="Generate Plan",
            command=self._generate_plan,
        ).pack(side=tk.LEFT)
        ttk.Label(
            controls,
            textvariable=self.plan_summary_var,
            style="Summary.TLabel",
        ).pack(side=tk.LEFT, padx=(14, 0))

        plan_panes = ttk.PanedWindow(self.plan_tab, orient=tk.VERTICAL)
        plan_panes.pack(fill=tk.BOTH, expand=True)

        schedule_frame = ttk.LabelFrame(
            plan_panes,
            text="Generated daily production plan",
            padding=8,
        )
        schedule_frame.rowconfigure(0, weight=1)
        schedule_frame.columnconfigure(0, weight=1)
        plan_panes.add(schedule_frame, weight=3)

        plan_columns = (
            "order_no",
            "plan_date",
            "due_date",
            "type",
            "market",
            "rm_size",
            "customer",
            "group1",
            "order_cups",
            "order_wontons",
            "rm_kg",
            "produce_wontons",
            "expected_wontons",
            "rm_source",
        )
        self.plan_tree = ttk.Treeview(
            schedule_frame,
            columns=plan_columns,
            show="headings",
        )
        plan_headings = {
            "order_no": "Order No.",
            "plan_date": "Plan date",
            "due_date": "Load date",
            "type": "Type",
            "market": "Use for",
            "rm_size": "RM Size",
            "customer": "Customer",
            "group1": "Group 1",
            "order_cups": "Order (ถ้วย)",
            "order_wontons": "Order (จำนวนเกี๊ยว)",
            "rm_kg": "RM used (kg)",
            "produce_wontons": "Produce (จำนวนเกี๊ยว)",
            "expected_wontons": "Remaining (จำนวนเกี๊ยว)",
            "rm_source": "RM source",
        }
        plan_widths = {
            "order_no": 105,
            "plan_date": 95,
            "due_date": 95,
            "type": 75,
            "market": 85,
            "rm_size": 70,
            "customer": 190,
            "group1": 180,
            "order_cups": 115,
            "order_wontons": 145,
            "rm_kg": 100,
            "produce_wontons": 155,
            "expected_wontons": 115,
            "rm_source": 310,
        }
        numeric_columns = {
            "order_cups",
            "order_wontons",
            "rm_kg",
            "produce_wontons",
            "expected_wontons",
        }
        for column in plan_columns:
            self.plan_tree.heading(column, text=plan_headings[column])
            self.plan_tree.column(
                column,
                width=plan_widths[column],
                minwidth=60,
                anchor=tk.E if column in numeric_columns else tk.W,
                stretch=column in {"customer", "group1", "rm_source"},
            )
        self.plan_tree.tag_configure("late", background="#fff0e1", foreground="#9a3d00")
        plan_vertical = ttk.Scrollbar(
            schedule_frame,
            orient=tk.VERTICAL,
            command=self.plan_tree.yview,
        )
        plan_horizontal = ttk.Scrollbar(
            schedule_frame,
            orient=tk.HORIZONTAL,
            command=self.plan_tree.xview,
        )
        self.plan_tree.configure(
            yscrollcommand=plan_vertical.set,
            xscrollcommand=plan_horizontal.set,
        )
        self.plan_tree.grid(row=0, column=0, sticky="nsew")
        plan_vertical.grid(row=0, column=1, sticky="ns")
        plan_horizontal.grid(row=1, column=0, sticky="ew")

        unplanned_frame = ttk.LabelFrame(
            plan_panes,
            text="Unplanned / excluded orders and remaining demand",
            padding=8,
        )
        unplanned_frame.rowconfigure(0, weight=1)
        unplanned_frame.columnconfigure(0, weight=1)
        plan_panes.add(unplanned_frame, weight=1)
        unplanned_columns = (
            "order_no",
            "due_date",
            "type",
            "market",
            "rm_size",
            "customer",
            "group1",
            "remaining",
            "reason",
        )
        self.unplanned_tree = ttk.Treeview(
            unplanned_frame,
            columns=unplanned_columns,
            show="headings",
            height=7,
        )
        unplanned_headings = {
            "order_no": "Order No.",
            "due_date": "Load date",
            "type": "Type",
            "market": "Use for",
            "rm_size": "RM Size",
            "customer": "Customer",
            "group1": "Group 1",
            "remaining": "Remaining wontons",
            "reason": "Reason",
        }
        for column in unplanned_columns:
            self.unplanned_tree.heading(column, text=unplanned_headings[column])
            self.unplanned_tree.column(
                column,
                width=120 if column not in {"customer", "group1", "reason"} else 220,
                anchor=tk.E if column == "remaining" else tk.W,
                stretch=column in {"customer", "group1", "reason"},
            )
        unplanned_vertical = ttk.Scrollbar(
            unplanned_frame,
            orient=tk.VERTICAL,
            command=self.unplanned_tree.yview,
        )
        unplanned_horizontal = ttk.Scrollbar(
            unplanned_frame,
            orient=tk.HORIZONTAL,
            command=self.unplanned_tree.xview,
        )
        self.unplanned_tree.configure(
            yscrollcommand=unplanned_vertical.set,
            xscrollcommand=unplanned_horizontal.set,
        )
        self.unplanned_tree.grid(row=0, column=0, sticky="nsew")
        unplanned_vertical.grid(row=0, column=1, sticky="ns")
        unplanned_horizontal.grid(row=1, column=0, sticky="ew")

        ttk.Label(
            self.plan_tab,
            textvariable=self.plan_status_var,
            relief=tk.SUNKEN,
            anchor=tk.W,
            padding=(6, 3),
        ).pack(fill=tk.X, pady=(8, 0))

    def _generate_plan(self) -> None:
        if not self.saved_order_records:
            messagebox.showwarning("Generate Plan", "Extract and save Order data first.")
            return
        ranges = self._current_assortment_size_range_definitions()
        try:
            rules = load_rules(self.rule_file_path)
            result = generate_plan(
                self.saved_order_records.values(),
                self.assortment_actual_records.values(),
                ranges,
                self.capacity_settings,
                self.class_definitions.values(),
                rules,
                planning_date=date.today(),
            )
        except (ValueError, OSError) as exc:
            messagebox.showerror("Generate Plan", str(exc))
            self.plan_status_var.set(f"Could not generate plan: {exc}")
            return

        self.plan_result = result
        self.plan_tree.delete(*self.plan_tree.get_children())
        for index, row in enumerate(result.allocations):
            self.plan_tree.insert(
                "",
                tk.END,
                iid=f"plan:{index}",
                values=(
                    row.order_no,
                    row.plan_date,
                    row.due_date,
                    row.production_type,
                    row.market_type.upper(),
                    row.rm_size,
                    row.customer,
                    row.group_1,
                    self._format_optional_number(row.order_cups),
                    self._format_optional_number(row.order_wontons),
                    self._format_optional_number(row.rm_kg),
                    self._format_optional_number(row.produced_wontons),
                    self._format_optional_number(row.expected_wontons),
                    row.rm_sources,
                ),
                tags=("late",) if row.is_late else (),
            )

        self.unplanned_tree.delete(*self.unplanned_tree.get_children())
        for index, row in enumerate(
            sorted(
                result.unplanned,
                key=lambda item: (item.due_date, item.order_no, item.order_id),
            )
        ):
            self.unplanned_tree.insert(
                "",
                tk.END,
                iid=f"unplanned:{index}",
                values=(
                    row.order_no,
                    row.due_date,
                    row.production_type,
                    row.market_type.upper(),
                    row.rm_size,
                    row.customer,
                    row.group_1,
                    self._format_optional_number(row.remaining_wontons),
                    row.reason,
                ),
            )

        planned_orders = len({row.order_id for row in result.allocations})
        late_rows = sum(row.is_late for row in result.allocations)
        self.plan_summary_var.set(
            f"{planned_orders:,} orders planned  |  "
            f"{result.planned_wontons:,.0f} wontons  |  "
            f"RM {result.used_rm_kg:,.2f} kg  |  "
            f"{len(result.unplanned):,} unplanned"
        )
        self.plan_status_var.set(
            f"Generated {len(result.allocations):,} daily plan rows from {result.start_date} "
            f"through {result.end_date}. {result.skipped_past_orders:,} past orders ignored; "
            f"{late_rows:,} late rows. Month-only orders use month-end."
        )

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
            text="Class and grouping master data",
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

        group_box = ttk.LabelFrame(form, text="3. Group", padding=10)
        group_box.grid(row=1, column=0, sticky="ew", padx=(0, 8), pady=(10, 0))
        group_box.columnconfigure(0, weight=1)
        self.class_group_text = tk.Text(
            group_box,
            height=4,
            wrap=tk.WORD,
            font=("Segoe UI", 10),
            undo=True,
        )
        self.class_group_text.grid(row=0, column=0, sticky="ew")

        value_box = ttk.LabelFrame(form, text="4. Value", padding=10)
        value_box.grid(row=1, column=1, sticky="ew", pady=(10, 0))
        value_box.columnconfigure(0, weight=1)
        self.class_detail_value_text = tk.Text(
            value_box,
            height=4,
            wrap=tk.WORD,
            font=("Segoe UI", 10),
            undo=True,
        )
        self.class_detail_value_text.grid(row=0, column=0, sticky="ew")

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
        saved_frame.rowconfigure(1, weight=1)
        saved_frame.columnconfigure(0, weight=1)

        class_filters = ttk.Frame(saved_frame)
        class_filters.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 8))
        class_filters.columnconfigure(1, weight=1)
        class_filters.columnconfigure(3, weight=2)
        class_filters.columnconfigure(5, weight=1)
        ttk.Label(class_filters, text="Class:").grid(row=0, column=0, padx=(0, 5))
        self.class_filter_combo = ttk.Combobox(
            class_filters,
            textvariable=self.class_filter_var,
            state="readonly",
            values=[ALL_CLASS_FILTER],
            width=18,
        )
        self.class_filter_combo.grid(row=0, column=1, sticky="ew", padx=(0, 12))
        self.class_filter_combo.bind(
            "<<ComboboxSelected>>",
            lambda _event: self._refresh_class_table(),
        )
        ttk.Label(class_filters, text="Name contains:").grid(row=0, column=2, padx=(0, 5))
        name_search_entry = ttk.Entry(
            class_filters,
            textvariable=self.class_name_search_var,
        )
        name_search_entry.grid(row=0, column=3, sticky="ew", padx=(0, 12))
        name_search_entry.bind("<KeyRelease>", lambda _event: self._refresh_class_table())
        ttk.Label(class_filters, text="Group:").grid(row=0, column=4, padx=(0, 5))
        self.class_group_filter_combo = ttk.Combobox(
            class_filters,
            textvariable=self.class_group_filter_var,
            state="readonly",
            values=[ALL_CLASS_FILTER],
            width=18,
        )
        self.class_group_filter_combo.grid(row=0, column=5, sticky="ew", padx=(0, 12))
        self.class_group_filter_combo.bind(
            "<<ComboboxSelected>>",
            lambda _event: self._refresh_class_table(),
        )
        ttk.Button(
            class_filters,
            text="Clear filters",
            command=self._clear_class_filters,
        ).grid(row=0, column=6, padx=(0, 12))
        ttk.Label(
            class_filters,
            textvariable=self.class_filter_count_var,
            style="Summary.TLabel",
        ).grid(row=0, column=7)

        self.class_tree = ttk.Treeview(
            saved_frame,
            columns=("class", "name", "group", "value"),
            show="headings",
            selectmode="browse",
        )
        self.class_tree.heading("class", text="Class")
        self.class_tree.heading("name", text="Name")
        self.class_tree.heading("group", text="Group")
        self.class_tree.heading("value", text="Value")
        self.class_tree.column("class", width=140, minwidth=100, stretch=False)
        self.class_tree.column("name", width=260, minwidth=160)
        self.class_tree.column("group", width=280, minwidth=160)
        self.class_tree.column("value", width=320, minwidth=180)
        class_scrollbar = ttk.Scrollbar(saved_frame, orient=tk.VERTICAL, command=self.class_tree.yview)
        self.class_tree.configure(yscrollcommand=class_scrollbar.set)
        self.class_tree.grid(row=1, column=0, sticky="nsew")
        class_scrollbar.grid(row=1, column=1, sticky="ns")
        self.class_tree.bind("<Double-1>", lambda _event: self._edit_selected_class())
        ttk.Button(saved_frame, text="Edit selected", command=self._edit_selected_class).grid(
            row=2, column=0, sticky="e", pady=(8, 0)
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
        self.class_group_text.delete("1.0", tk.END)
        self.class_detail_value_text.delete("1.0", tk.END)
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
                self.class_group_text.get("1.0", "end-1c"),
                class_id=self._editing_class_id,
                value=self.class_detail_value_text.get("1.0", "end-1c"),
            )
        except ValueError as exc:
            messagebox.showerror("Save class", str(exc))
            return
        action = "Updated" if self._editing_class_id else "Saved"
        self._load_saved_class_definitions()
        self._new_class_form(set_status=False)
        self.class_status_var.set(f"{action} class {saved.class_value}.")

    def _sync_order_classes(self, records: list[OrderRecord]) -> None:
        try:
            added = add_missing_class_definitions(
                self.class_definitions_file_path,
                order_class_names(records),
            )
        except ValueError as exc:
            self.class_status_var.set(f"Could not update classes from orders: {exc}")
            return
        self._load_saved_class_definitions()
        if added:
            self.class_status_var.set(
                f"Added {added:,} new Class + Name rows from Order data. "
                f"Class master now contains {len(self.class_definitions):,} rows."
            )
        else:
            self.class_status_var.set(
                f"All Order class values already exist ({len(self.class_definitions):,} rows)."
            )

    def _load_saved_class_definitions(self) -> None:
        try:
            definitions = load_class_definitions(self.class_definitions_file_path)
        except ValueError as exc:
            self.class_status_var.set(str(exc))
            return
        self.class_definitions = {item.class_id: item for item in definitions}
        class_options = [ALL_CLASS_FILTER, *class_filter_options(definitions, "class")]
        group_options = [ALL_CLASS_FILTER, *class_filter_options(definitions, "group")]
        self.class_filter_combo.configure(values=class_options)
        self.class_group_filter_combo.configure(values=group_options)
        if self.class_filter_var.get() not in class_options:
            self.class_filter_var.set(ALL_CLASS_FILTER)
        if self.class_group_filter_var.get() not in group_options:
            self.class_group_filter_var.set(ALL_CLASS_FILTER)
        self._refresh_class_table()
        if definitions:
            self.class_status_var.set(f"Loaded {len(definitions)} saved classes.")

    def _refresh_class_table(self) -> None:
        definitions = filter_class_definitions(
            self.class_definitions.values(),
            class_filter=self.class_filter_var.get(),
            name_search=self.class_name_search_var.get(),
            group_filter=self.class_group_filter_var.get(),
        )
        self.class_tree.delete(*self.class_tree.get_children())
        for item in sorted(
            definitions,
            key=lambda value: (value.class_value.casefold(), value.name.casefold()),
        ):
            self.class_tree.insert(
                "",
                tk.END,
                iid=item.class_id,
                values=(
                    item.class_value,
                    self._format_class_name_for_display(item),
                    " ".join(item.group.split()),
                    " ".join(item.value.split()),
                ),
            )
        self.class_filter_count_var.set(
            f"Showing {len(definitions):,} of {len(self.class_definitions):,} classes"
        )

    def _clear_class_filters(self) -> None:
        self.class_filter_var.set(ALL_CLASS_FILTER)
        self.class_name_search_var.set("")
        self.class_group_filter_var.set(ALL_CLASS_FILTER)
        self._refresh_class_table()

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
        self.class_group_text.delete("1.0", tk.END)
        self.class_group_text.insert("1.0", item.group)
        self.class_detail_value_text.delete("1.0", tk.END)
        self.class_detail_value_text.insert("1.0", item.value)
        self._editing_class_id = item.class_id
        self.save_class_button.configure(text="Update class")
        self.class_status_var.set(f"Editing class {item.class_value}.")

    def _build_assortment_std_tab(self) -> None:
        ttk.Label(
            self.assortment_std_tab,
            text="Assortment STD",
            style="Summary.TLabel",
        ).pack(anchor=tk.W)
        ttk.Label(
            self.assortment_std_tab,
            text="Review the assortment master and maintain the M and S+ output-size ranges.",
        ).pack(anchor=tk.W, pady=(2, 10))

        source_frame = ttk.Frame(self.assortment_std_tab)
        source_frame.pack(fill=tk.X, pady=(0, 10))
        ttk.Label(source_frame, text="Master file:", style="Summary.TLabel").pack(side=tk.LEFT)
        ttk.Label(source_frame, text=str(self.assortment_file_path)).pack(side=tk.LEFT, padx=(6, 0))
        ttk.Button(source_frame, text="Reload master", command=self._load_assortment_data).pack(side=tk.RIGHT)
        ttk.Button(source_frame, text="Save ranges", command=self._save_assortment_size_ranges).pack(
            side=tk.RIGHT, padx=(0, 8)
        )

        table_frame = ttk.Frame(self.assortment_std_tab)
        table_frame.pack(fill=tk.BOTH, expand=True)
        table_frame.rowconfigure(0, weight=1)
        table_frame.columnconfigure(0, weight=1)

        self.assortment_canvas = tk.Canvas(
            table_frame,
            background="white",
            highlightthickness=1,
            highlightbackground="#b7b7b7",
        )
        vertical = ttk.Scrollbar(table_frame, orient=tk.VERTICAL, command=self.assortment_canvas.yview)
        horizontal = ttk.Scrollbar(table_frame, orient=tk.HORIZONTAL, command=self.assortment_canvas.xview)
        self.assortment_canvas.configure(yscrollcommand=vertical.set, xscrollcommand=horizontal.set)
        self.assortment_canvas.grid(row=0, column=0, sticky="nsew")
        vertical.grid(row=0, column=1, sticky="ns")
        horizontal.grid(row=1, column=0, sticky="ew")
        self.assortment_canvas.bind("<ButtonPress-1>", self._start_assortment_range_drag)
        self.assortment_canvas.bind("<B1-Motion>", self._drag_assortment_range)
        self.assortment_canvas.bind("<ButtonRelease-1>", self._end_assortment_range_drag)
        self.assortment_canvas.bind("<MouseWheel>", self._scroll_assortment_canvas)

        ttk.Label(
            self.assortment_std_tab,
            textvariable=self.assortment_status_var,
            relief=tk.SUNKEN,
            anchor=tk.W,
            padding=(6, 3),
        ).pack(fill=tk.X, pady=(8, 0))

    def _fill_stock_from_assortment_std(self) -> None:
        if self.assortment_table is None:
            messagebox.showerror(
                "Fill from Assortment STD",
                "Load a valid assortment master before calculating stock rows.",
            )
            return
        try:
            weight_text = self.stock_harvest_weight_var.get().strip().replace(",", "")
            predictions = predict_assortment(
                self.assortment_table,
                self.stock_harvest_size_var.get(),
                weight_text,
            )
            allocated_weight = sum(item.weight for item in predictions)
        except ValueError as exc:
            messagebox.showerror("Fill from Assortment STD", str(exc))
            return

        self._editing_actual_record_id = None
        self.assortment_actual_save_button.configure(text="Save stock")
        self._set_assortment_actual_boxes(
            [
                ActualAssortmentEntry(size=item.output_size, weight=item.weight)
                for item in predictions
            ]
        )
        requested_size = self.stock_harvest_size_var.get().strip()
        master_size = requested_size if requested_size.casefold().startswith("s.") else f"S.{requested_size}"
        resolved_size = next(
            base_size
            for base_size in self.assortment_table.base_sizes
            if base_size.casefold() == master_size.casefold()
        )
        message = (
            f"Filled {len(predictions)} size rows from {resolved_size} and "
            f"{allocated_weight:,} kg in whole kilograms. "
            "Review or edit the rows before saving."
        )
        self.assortment_actual_status_var.set(message)

    def _build_capacity_tab(self) -> None:
        self.raw_capacity_percentage_var = tk.DoubleVar(value=50)
        self.cooked_capacity_percentage_var = tk.DoubleVar(value=50)
        self.raw_capacity_percentage_text_var = tk.StringVar(value="50%")
        self.cooked_capacity_percentage_text_var = tk.StringVar(value="50%")
        self.raw_wonton_capacity_var = tk.StringVar()
        self.cooked_wonton_capacity_var = tk.StringVar()
        self.raw_wonton_scaled_var = tk.StringVar(value="Set base capacity first")
        self.cooked_wonton_scaled_var = tk.StringVar(value="Set base capacity first")

        ttk.Label(
            self.capacity_tab,
            text="Production Capacity Setup",
            style="Summary.TLabel",
        ).pack(anchor=tk.W)
        ttk.Label(
            self.capacity_tab,
            text=(
                "Set each production type independently. Each slider controls "
                "0–100% of its own maximum daily capacity."
            ),
        ).pack(anchor=tk.W, pady=(2, 12))

        settings_frame = ttk.Frame(self.capacity_tab)
        settings_frame.pack(fill=tk.X, pady=(0, 12))
        settings_frame.columnconfigure(0, weight=1)
        settings_frame.columnconfigure(1, weight=1)

        raw_frame = ttk.LabelFrame(
            settings_frame,
            text="เกี๊ยวดิบ",
            padding=12,
        )
        raw_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 6))
        raw_frame.columnconfigure(0, weight=1)
        ttk.Label(raw_frame, text="Maximum wontons per day").grid(
            row=0,
            column=0,
            sticky=tk.W,
        )
        raw_entry = ttk.Entry(
            raw_frame,
            textvariable=self.raw_wonton_capacity_var,
            font=("Segoe UI", 11),
        )
        raw_entry.grid(row=1, column=0, sticky="ew", pady=(4, 12))
        raw_percentage_row = ttk.Frame(raw_frame)
        raw_percentage_row.grid(row=2, column=0, sticky="ew")
        raw_percentage_row.columnconfigure(0, weight=1)
        ttk.Label(raw_percentage_row, text="Available capacity percentage").grid(
            row=0,
            column=0,
            sticky=tk.W,
        )
        ttk.Label(
            raw_percentage_row,
            textvariable=self.raw_capacity_percentage_text_var,
            style="Summary.TLabel",
        ).grid(row=0, column=1, sticky=tk.E)
        ttk.Scale(
            raw_frame,
            from_=0,
            to=100,
            variable=self.raw_capacity_percentage_var,
            command=self._capacity_slider_changed,
        ).grid(row=3, column=0, sticky="ew", pady=(6, 0))
        raw_scale_ends = ttk.Frame(raw_frame)
        raw_scale_ends.grid(row=4, column=0, sticky="ew")
        raw_scale_ends.columnconfigure(1, weight=1)
        ttk.Label(raw_scale_ends, text="0%").grid(row=0, column=0, sticky=tk.W)
        ttk.Label(raw_scale_ends, text="100%").grid(row=0, column=2, sticky=tk.E)
        ttk.Separator(raw_frame).grid(row=5, column=0, sticky="ew", pady=10)
        ttk.Label(raw_frame, text="Available for Plan").grid(
            row=6,
            column=0,
            sticky=tk.W,
        )
        ttk.Label(
            raw_frame,
            textvariable=self.raw_wonton_scaled_var,
            style="Summary.TLabel",
        ).grid(row=7, column=0, sticky=tk.W, pady=(3, 0))

        cooked_frame = ttk.LabelFrame(
            settings_frame,
            text="เกี๊ยวสุก",
            padding=12,
        )
        cooked_frame.grid(row=0, column=1, sticky="nsew", padx=(6, 0))
        cooked_frame.columnconfigure(0, weight=1)
        ttk.Label(cooked_frame, text="Maximum wontons per day").grid(
            row=0,
            column=0,
            sticky=tk.W,
        )
        cooked_entry = ttk.Entry(
            cooked_frame,
            textvariable=self.cooked_wonton_capacity_var,
            font=("Segoe UI", 11),
        )
        cooked_entry.grid(row=1, column=0, sticky="ew", pady=(4, 12))
        cooked_percentage_row = ttk.Frame(cooked_frame)
        cooked_percentage_row.grid(row=2, column=0, sticky="ew")
        cooked_percentage_row.columnconfigure(0, weight=1)
        ttk.Label(cooked_percentage_row, text="Available capacity percentage").grid(
            row=0,
            column=0,
            sticky=tk.W,
        )
        ttk.Label(
            cooked_percentage_row,
            textvariable=self.cooked_capacity_percentage_text_var,
            style="Summary.TLabel",
        ).grid(row=0, column=1, sticky=tk.E)
        ttk.Scale(
            cooked_frame,
            from_=0,
            to=100,
            variable=self.cooked_capacity_percentage_var,
            command=self._capacity_slider_changed,
        ).grid(row=3, column=0, sticky="ew", pady=(6, 0))
        cooked_scale_ends = ttk.Frame(cooked_frame)
        cooked_scale_ends.grid(row=4, column=0, sticky="ew")
        cooked_scale_ends.columnconfigure(1, weight=1)
        ttk.Label(cooked_scale_ends, text="0%").grid(row=0, column=0, sticky=tk.W)
        ttk.Label(cooked_scale_ends, text="100%").grid(row=0, column=2, sticky=tk.E)
        ttk.Separator(cooked_frame).grid(row=5, column=0, sticky="ew", pady=10)
        ttk.Label(cooked_frame, text="Available for Plan").grid(
            row=6,
            column=0,
            sticky=tk.W,
        )
        ttk.Label(
            cooked_frame,
            textvariable=self.cooked_wonton_scaled_var,
            style="Summary.TLabel",
        ).grid(row=7, column=0, sticky=tk.W, pady=(3, 0))

        raw_entry.bind("<KeyRelease>", lambda _event: self._update_capacity_preview())
        cooked_entry.bind("<KeyRelease>", lambda _event: self._update_capacity_preview())

        action_frame = ttk.Frame(self.capacity_tab)
        action_frame.pack(fill=tk.X)
        ttk.Button(
            action_frame,
            text="Save capacity settings",
            command=self._save_all_capacity_settings,
        ).pack(anchor=tk.E)

        ttk.Label(
            self.capacity_tab,
            textvariable=self.capacity_status_var,
            relief=tk.SUNKEN,
            anchor=tk.W,
            padding=(6, 3),
        ).pack(fill=tk.X, pady=(14, 0))

    def _capacity_slider_changed(self, _value: str) -> None:
        self._update_capacity_preview()

    def _update_capacity_preview(self) -> None:
        raw_percentage = round(self.raw_capacity_percentage_var.get())
        cooked_percentage = round(self.cooked_capacity_percentage_var.get())
        self.raw_capacity_percentage_text_var.set(f"{raw_percentage}%")
        self.cooked_capacity_percentage_text_var.set(f"{cooked_percentage}%")
        raw_base = self._preview_capacity_number(self.raw_wonton_capacity_var.get())
        cooked_base = self._preview_capacity_number(self.cooked_wonton_capacity_var.get())
        raw_wonton, cooked_wonton = capacities_at_percentage(
            CapacitySettings(
                raw_percentage=raw_percentage,
                cooked_percentage=cooked_percentage,
                raw_wonton=raw_base,
                cooked_wonton=cooked_base,
            ),
        )
        self.raw_wonton_scaled_var.set(
            "Enter a valid maximum"
            if raw_wonton is None
            else f"{self._format_optional_number(raw_wonton)} wontons/day"
        )
        self.cooked_wonton_scaled_var.set(
            "Enter a valid maximum"
            if cooked_wonton is None
            else f"{self._format_optional_number(cooked_wonton)} wontons/day"
        )

    @staticmethod
    def _preview_capacity_number(value: str) -> int | float | None:
        cleaned = value.strip().replace(",", "")
        if not cleaned:
            return None
        try:
            numeric = float(cleaned)
        except ValueError:
            return None
        if not math.isfinite(numeric) or numeric < 0:
            return None
        return int(numeric) if numeric.is_integer() else numeric

    def _load_capacity_settings(self) -> None:
        try:
            settings = load_capacity_settings(self.capacity_file_path)
        except ValueError as exc:
            self.capacity_status_var.set(str(exc))
            return
        self.capacity_settings = settings
        self.raw_capacity_percentage_var.set(settings.raw_percentage)
        self.cooked_capacity_percentage_var.set(settings.cooked_percentage)
        self.raw_wonton_capacity_var.set(self._format_optional_number(settings.raw_wonton))
        self.cooked_wonton_capacity_var.set(self._format_optional_number(settings.cooked_wonton))
        self._update_capacity_preview()
        if self.capacity_file_path.exists():
            self.capacity_status_var.set("Loaded saved capacity settings.")

    def _save_all_capacity_settings(self) -> None:
        try:
            raw_wonton = self._parse_capacity_number(
                self.raw_wonton_capacity_var.get(),
                "เกี๊ยวดิบ",
            )
            cooked_wonton = self._parse_capacity_number(
                self.cooked_wonton_capacity_var.get(),
                "เกี๊ยวสุก",
            )
            settings = CapacitySettings(
                raw_percentage=round(self.raw_capacity_percentage_var.get()),
                cooked_percentage=round(self.cooked_capacity_percentage_var.get()),
                raw_wonton=raw_wonton,
                cooked_wonton=cooked_wonton,
            )
            self.capacity_settings = save_capacity_settings(self.capacity_file_path, settings)
        except ValueError as exc:
            messagebox.showerror("Save capacity", str(exc))
            return
        self.raw_wonton_capacity_var.set(self._format_optional_number(raw_wonton))
        self.cooked_wonton_capacity_var.set(self._format_optional_number(cooked_wonton))
        self.raw_capacity_percentage_var.set(self.capacity_settings.raw_percentage)
        self.cooked_capacity_percentage_var.set(
            self.capacity_settings.cooked_percentage
        )
        self._update_capacity_preview()
        self.capacity_status_var.set(
            f"Saved maximums: ดิบ {self._format_optional_number(raw_wonton)}, "
            f"สุก {self._format_optional_number(cooked_wonton)}; "
            f"ดิบ {self.capacity_settings.raw_percentage}% / "
            f"สุก {self.capacity_settings.cooked_percentage}%."
        )

    @staticmethod
    def _parse_capacity_number(value: str, label: str) -> int | float:
        cleaned = value.strip().replace(",", "")
        if not cleaned:
            raise ValueError(f"Enter a number for {label}.")
        try:
            numeric = float(cleaned)
        except ValueError as exc:
            raise ValueError(f"{label} must be numeric.") from exc
        if not math.isfinite(numeric) or numeric < 0:
            raise ValueError(f"{label} must be zero or greater.")
        return int(numeric) if numeric.is_integer() else numeric

    def _build_assortment_actual_tab(self) -> None:
        today = date.today()
        self.actual_day_var = tk.StringVar(value=f"{today.day:02d}")
        self.actual_month_var = tk.StringVar(value=f"{today.month:02d}")
        self.actual_year_var = tk.StringVar(value=f"{today.year:04d}")
        self.actual_market_type_var = tk.StringVar(value="DOMESTIC")
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
            values=("DOMESTIC", "EXPORT"),
            state="readonly",
            width=10,
        ).grid(row=1, column=1, sticky="ew", pady=(4, 0))

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
            text="Uses STD percentages to fill the size rows below; all calculated rows remain editable.",
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
        ttk.Label(box_header, text="3. Size and weight", style="Summary.TLabel").pack(side=tk.LEFT)
        self.assortment_entry_summary_var = tk.StringVar(value="1 row | Total 0 kg")
        ttk.Label(
            box_header,
            textvariable=self.assortment_entry_summary_var,
        ).pack(side=tk.LEFT, padx=(12, 0))

        ttk.Label(
            form_panel,
            text="Size class is filled automatically from Assortment STD. Crossing ranges become Unused.",
        ).pack(anchor=tk.W, pady=(0, 6))

        entry_headings = ttk.Frame(form_panel, padding=(6, 5))
        entry_headings.pack(fill=tk.X)
        entry_headings.columnconfigure(1, weight=1)
        entry_headings.columnconfigure(3, weight=1)
        entry_headings.columnconfigure(5, weight=1)
        ttk.Label(entry_headings, text="#", width=4).grid(row=0, column=0, sticky=tk.W)
        ttk.Label(entry_headings, text="Size start").grid(row=0, column=1, sticky=tk.W)
        ttk.Label(entry_headings, text="").grid(row=0, column=2, padx=5)
        ttk.Label(entry_headings, text="Size end").grid(row=0, column=3, sticky=tk.W)
        ttk.Label(entry_headings, text="Class", width=12).grid(
            row=0, column=4, sticky=tk.W, padx=(10, 8)
        )
        ttk.Label(entry_headings, text="Weight (kg)").grid(row=0, column=5, sticky=tk.W)
        ttk.Label(entry_headings, text="", width=8).grid(row=0, column=6)

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
                "rm_id",
                "market",
                "date",
                "weight",
                "M",
                "S+",
                "unused",
                "est_wonton",
            ),
            show="headings",
            selectmode="browse",
        )
        self.assortment_actual_history_tree.heading("rm_id", text="RM ID")
        self.assortment_actual_history_tree.heading("market", text="Use for")
        self.assortment_actual_history_tree.heading("date", text="Date")
        self.assortment_actual_history_tree.heading("weight", text="Total weight")
        self.assortment_actual_history_tree.heading("M", text="M (kg)")
        self.assortment_actual_history_tree.heading("S+", text="S+ (kg)")
        self.assortment_actual_history_tree.heading("unused", text="Unused (kg)")
        self.assortment_actual_history_tree.heading("est_wonton", text="Est. wonton")
        self.assortment_actual_history_tree.column("rm_id", width=100, anchor=tk.CENTER)
        self.assortment_actual_history_tree.column("market", width=90, anchor=tk.CENTER)
        self.assortment_actual_history_tree.column("date", width=95, anchor=tk.CENTER)
        self.assortment_actual_history_tree.column("weight", width=95, anchor=tk.E)
        self.assortment_actual_history_tree.column("M", width=105, anchor=tk.E)
        self.assortment_actual_history_tree.column("S+", width=105, anchor=tk.E)
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
        size_start: str = "",
        size_end: str = "",
        weight: str = "",
    ) -> None:
        size_start_var = tk.StringVar(value=size_start)
        size_end_var = tk.StringVar(value=size_end)
        weight_var = tk.StringVar(value=weight)
        row_number_var = tk.StringVar()
        box = ttk.Frame(self.assortment_actual_list, padding=(6, 5))
        self.assortment_actual_add_row_footer.pack_forget()
        box.pack(fill=tk.X, pady=(0, 2))
        self.assortment_actual_add_row_footer.pack(fill=tk.X)
        box.columnconfigure(1, weight=1)
        box.columnconfigure(3, weight=1)
        box.columnconfigure(5, weight=1)

        ttk.Label(box, textvariable=row_number_var, width=4).grid(
            row=0, column=0, sticky=tk.W
        )
        ttk.Entry(box, textvariable=size_start_var).grid(
            row=0, column=1, sticky="ew"
        )
        ttk.Label(box, text="–").grid(row=0, column=2, padx=5)
        ttk.Entry(box, textvariable=size_end_var).grid(
            row=0, column=3, sticky="ew"
        )

        size_class_var = tk.StringVar()
        size_class_label = ttk.Label(
            box,
            textvariable=size_class_var,
            width=12,
            anchor=tk.CENTER,
            font=("Segoe UI", 9, "bold"),
        )
        size_class_label.grid(row=0, column=4, sticky="ew", padx=(10, 8))
        ttk.Entry(box, textvariable=weight_var).grid(
            row=0, column=5, sticky="ew"
        )

        ttk.Button(
            box,
            text="Remove",
            command=lambda current_box=box: self._remove_assortment_actual_box(current_box),
        ).grid(row=0, column=6, sticky=tk.E, padx=(8, 0))

        box_entry: dict[str, object] = {
            "frame": box,
            "size_start": size_start_var,
            "size_end": size_end_var,
            "size_class": size_class_var,
            "size_class_label": size_class_label,
            "weight": weight_var,
            "row_number": row_number_var,
        }
        size_start_var.trace_add(
            "write",
            lambda *_args, current=box_entry: self._update_assortment_box_size_class(current),
        )
        size_end_var.trace_add(
            "write",
            lambda *_args, current=box_entry: self._update_assortment_box_size_class(current),
        )
        weight_var.trace_add(
            "write",
            lambda *_args: self._update_assortment_entry_summary(),
        )
        self.assortment_actual_boxes.append(box_entry)
        self._update_assortment_box_size_class(box_entry)
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
            start = entry["size_start"]
            end = entry["size_end"]
            weight = entry["weight"]
            if not all(isinstance(value, tk.StringVar) for value in (start, end, weight)):
                continue
            if start.get().strip() and end.get().strip() and weight.get().strip():
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

    def _update_assortment_box_size_class(self, box_entry: dict[str, object]) -> None:
        size_start_var = box_entry.get("size_start")
        size_end_var = box_entry.get("size_end")
        size_class_var = box_entry.get("size_class")
        size_class_label = box_entry.get("size_class_label")
        if not all(
            isinstance(value, tk.StringVar)
            for value in (size_start_var, size_end_var, size_class_var)
        ) or not isinstance(size_class_label, ttk.Label):
            return
        size_start = size_start_var.get().strip()
        size_end = size_end_var.get().strip()
        ranges = self._current_assortment_size_range_definitions()
        if not size_start or not size_end or not ranges:
            size_class_var.set("")
            return
        try:
            classes = classify_size_range(size_start, size_end, ranges)
        except ValueError:
            size_class_var.set("Invalid range")
            return
        size_class_var.set(", ".join(classes))

    def _refresh_assortment_actual_size_classes(self) -> None:
        if not hasattr(self, "assortment_actual_boxes"):
            return
        for box_entry in self.assortment_actual_boxes:
            self._update_assortment_box_size_class(box_entry)

    def _new_assortment_actual_form(self, set_status: bool = True) -> None:
        today = date.today()
        self.actual_day_var.set(f"{today.day:02d}")
        self.actual_month_var.set(f"{today.month:02d}")
        self.actual_year_var.set(f"{today.year:04d}")
        self._editing_actual_record_id = None
        self.actual_market_type_var.set("DOMESTIC")
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
            for entry in entries:
                size_start, size_end = split_size_range(entry.size)
                self._add_assortment_actual_box(
                    size_start,
                    size_end,
                    self._format_weight(entry.weight),
                )
        else:
            self._add_assortment_actual_box()

    def _collect_assortment_actual_entries(self) -> list[ActualAssortmentEntry]:
        entries: list[ActualAssortmentEntry] = []
        for number, box_entry in enumerate(self.assortment_actual_boxes, start=1):
            size_start_var = box_entry["size_start"]
            size_end_var = box_entry["size_end"]
            weight_var = box_entry["weight"]
            if not all(
                isinstance(value, tk.StringVar)
                for value in (size_start_var, size_end_var, weight_var)
            ):
                continue
            size_start = size_start_var.get().strip()
            size_end = size_end_var.get().strip()
            weight_text = weight_var.get().strip().replace(",", "")
            if not size_start and not size_end and not weight_text:
                continue
            if not size_start or not size_end or not weight_text:
                raise ValueError(
                    f"Row {number} needs Size start, Size end, and Weight."
                )
            try:
                weight = float(weight_text)
            except ValueError as exc:
                raise ValueError(f"Row {number} has an invalid Weight.") from exc
            ranges = self._current_assortment_size_range_definitions()
            if ranges:
                try:
                    classify_size_range(size_start, size_end, ranges)
                except ValueError as exc:
                    raise ValueError(
                        f"Row {number} has an invalid Size range: {exc}"
                    ) from exc
            size = combine_size_range(size_start, size_end)
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
                record_id=self._editing_actual_record_id,
                record_type="actual",
                market_type=self.actual_market_type_var.get(),
            )
        except ValueError as exc:
            messagebox.showerror("Save stock", str(exc))
            return
        action = "Updated" if self._editing_actual_record_id else "Saved"
        self._load_assortment_actual_history()
        self._new_assortment_actual_form(set_status=False)
        self.assortment_actual_status_var.set(
            f"{action} stock for {record.market_type.title()} "
            f"with {len(record.entries)} entries "
            f"for {record.record_date}."
        )
        self.rm_timeline_status_var.set(
            f"{action} stock {record.rm_id} for {record.record_date}."
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
            try:
                estimated_wontons = self._format_optional_number(
                    estimate_wonton_pieces(record.entries)
                )
            except ValueError:
                estimated_wontons = "Invalid size"
            self.assortment_actual_history_tree.insert(
                "",
                tk.END,
                iid=record.record_id,
                values=(
                    record.rm_id,
                    record.market_type.upper(),
                    record.record_date,
                    self._format_weight(record.total_weight),
                    self._format_size_class_summary(class_summaries["M"]),
                    self._format_size_class_summary(class_summaries["S+"]),
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
        ranges = self._current_assortment_size_range_definitions()
        direct_totals = {size_class: 0.0 for size_class in SIZE_CLASSES}
        entries: list[tuple[str, str, float]] = []
        for entry in record.entries:
            size_class = normalize_size_class(entry.size_class)
            if size_class in direct_totals:
                direct_totals[size_class] += float(entry.weight)
                continue
            size_start, size_end = split_size_range(entry.size)
            entries.append((size_start, size_end, entry.weight))
        if ranges:
            summarized = summarize_size_class_weight_details(entries, ranges)
        else:
            summarized = {
                "M": SizeClassWeightSummary(0),
                "S+": SizeClassWeightSummary(0),
                "Unused": SizeClassWeightSummary(sum(weight for _, _, weight in entries)),
            }
        return {
            size_class: SizeClassWeightSummary(
                summarized[size_class].total + direct_totals.get(size_class, 0)
            )
            for size_class in (*SIZE_CLASSES, "Unused")
        }

    def _format_size_class_summary(self, summary: SizeClassWeightSummary) -> str:
        return self._format_weight(summary.total)

    def _edit_selected_assortment_actual(self) -> None:
        selected = self.assortment_actual_history_tree.selection()
        if not selected:
            messagebox.showwarning("No stock selected", "Select a saved stock record to edit.")
            return
        record = self.assortment_actual_records.get(selected[0])
        if not record:
            messagebox.showerror("Stock error", "The selected stock record could not be found.")
            return
        if any(entry.size_class for entry in record.entries):
            messagebox.showinfo(
                "Legacy stock record",
                "This older class-only stock record cannot be edited in the size-range form. "
                "You can delete it with Delete selected stock, then enter a replacement if needed.",
            )
            return
        year, month, day = record.record_date.split("-")
        self.actual_day_var.set(day)
        self.actual_month_var.set(month)
        self.actual_year_var.set(year)
        self.actual_market_type_var.set(record.market_type.upper())
        self.stock_harvest_size_var.set("")
        self.stock_harvest_weight_var.set("")
        self._set_assortment_actual_boxes(list(record.entries))
        self._editing_actual_record_id = record.record_id
        self.assortment_actual_save_button.configure(text="Update stock")
        self.assortment_actual_status_var.set(
            f"Editing saved stock {record.rm_id} for {record.record_date}."
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
            f"Permanently delete stock {record.rm_id} for {record.record_date}?"
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
            f"Deleted stock {deleted.rm_id} for {deleted.record_date}."
        )

    @staticmethod
    def _format_weight(weight: float) -> str:
        return f"{weight:,.2f}".rstrip("0").rstrip(".")

    @staticmethod
    def _format_class_name_for_display(item: ClassDefinition) -> str:
        if item.class_value.casefold() != "ถ้วย/unit".casefold():
            return item.name
        try:
            value = float(item.name.replace(",", ""))
        except ValueError:
            return item.name
        return ProductionPlanApp._format_optional_number(value)

    def _load_assortment_data(self) -> None:
        try:
            table = load_assortment(self.assortment_file_path)
        except (FileNotFoundError, ValueError) as exc:
            self.assortment_table = None
            self.stock_harvest_size_combo.configure(values=())
            self.assortment_canvas.delete("all")
            self.assortment_status_var.set(str(exc))
            return

        self.assortment_table = table
        self.stock_harvest_size_combo.configure(
            values=tuple(
                base_size[2:]
                if base_size.casefold().startswith("s.")
                else base_size
                for base_size in table.base_sizes
            )
        )
        range_note = (
            " Initial M/S+ ranges are placeholders; drag and save them."
            if not self.assortment_size_range_file_path.exists()
            else ""
        )
        try:
            saved_ranges = load_size_ranges(
                self.assortment_size_range_file_path,
                table.output_sizes,
            )
        except ValueError as exc:
            saved_ranges = default_size_ranges(table.output_sizes)
            range_note = f" Saved range file was ignored: {exc}"
        output_index = {size: index for index, size in enumerate(table.output_sizes)}
        self.assortment_size_ranges = {
            item.size_class: (output_index[item.start_size], output_index[item.end_size])
            for item in saved_ranges
        }
        self._show_assortment_table(table)
        if table.invalid_base_sizes:
            invalid = ", ".join(
                f"{base_size} ({total:.1%})" for base_size, total in table.invalid_base_sizes
            )
            self.assortment_status_var.set(
                f"Warning: output percentages do not total 100% for {invalid}.{range_note}"
            )
        else:
            self.assortment_status_var.set(
                f"Loaded {len(table.base_sizes)} base sizes × {len(table.output_sizes)} output ranges "
                f"from sheet {table.sheet_name}. Every base-size distribution totals 100%."
                f"{range_note}"
            )

    def _show_assortment_table(self, table: AssortmentTable) -> None:
        canvas = self.assortment_canvas
        canvas.delete("all")
        class_area_width = len(SIZE_CLASSES) * ASSORTMENT_CLASS_WIDTH
        data_start = class_area_width + ASSORTMENT_OUTPUT_WIDTH
        total_width = data_start + len(table.base_sizes) * ASSORTMENT_BASE_WIDTH
        total_height = ASSORTMENT_HEADER_HEIGHT + len(table.output_sizes) * ASSORTMENT_ROW_HEIGHT
        canvas.configure(scrollregion=(0, 0, total_width, total_height))

        headers = (*SIZE_CLASSES, "Actual output size", *table.base_sizes)
        widths = (
            *([ASSORTMENT_CLASS_WIDTH] * len(SIZE_CLASSES)),
            ASSORTMENT_OUTPUT_WIDTH,
            *([ASSORTMENT_BASE_WIDTH] * len(table.base_sizes)),
        )
        x = 0
        for header, width in zip(headers, widths):
            canvas.create_rectangle(
                x,
                0,
                x + width,
                ASSORTMENT_HEADER_HEIGHT,
                fill="#edf2f7",
                outline="#c5ccd3",
                tags="assortment_grid",
            )
            canvas.create_text(
                x + width / 2,
                ASSORTMENT_HEADER_HEIGHT / 2,
                text=header,
                font=("Segoe UI", 9, "bold"),
                tags="assortment_grid",
            )
            x += width

        for row_index, (output_size, percentages) in enumerate(
            zip(table.output_sizes, table.percentages)
        ):
            y1 = ASSORTMENT_HEADER_HEIGHT + row_index * ASSORTMENT_ROW_HEIGHT
            y2 = y1 + ASSORTMENT_ROW_HEIGHT
            canvas.create_rectangle(
                0,
                y1,
                total_width,
                y2,
                fill="#ffffff" if row_index % 2 == 0 else "#f8fafc",
                outline="#d8dde3",
                tags="assortment_grid",
            )
            canvas.create_text(
                class_area_width + ASSORTMENT_OUTPUT_WIDTH / 2,
                (y1 + y2) / 2,
                text=output_size,
                font=("Segoe UI", 9, "bold"),
                tags="assortment_grid",
            )
            for base_index, percentage in enumerate(percentages):
                if percentage == 0:
                    continue
                cell_x = data_start + base_index * ASSORTMENT_BASE_WIDTH
                canvas.create_text(
                    cell_x + ASSORTMENT_BASE_WIDTH / 2,
                    (y1 + y2) / 2,
                    text=f"{percentage:.1%}",
                    font=("Segoe UI", 9),
                    tags="assortment_grid",
                )

        x = 0
        for width in widths:
            canvas.create_line(x, 0, x, total_height, fill="#d8dde3", tags="assortment_grid")
            x += width
        canvas.create_line(total_width, 0, total_width, total_height, fill="#d8dde3")
        self._draw_assortment_range_boxes()

    def _draw_assortment_range_boxes(self) -> None:
        self.assortment_canvas.delete("assortment_range")
        if not self.assortment_table:
            return
        for class_index, size_class in enumerate(SIZE_CLASSES):
            start, end = self.assortment_size_ranges[size_class]
            x1 = class_index * ASSORTMENT_CLASS_WIDTH + 5
            x2 = (class_index + 1) * ASSORTMENT_CLASS_WIDTH - 5
            y1 = ASSORTMENT_HEADER_HEIGHT + start * ASSORTMENT_ROW_HEIGHT + 3
            y2 = ASSORTMENT_HEADER_HEIGHT + (end + 1) * ASSORTMENT_ROW_HEIGHT - 3
            fill, outline = ASSORTMENT_CLASS_COLORS[size_class]
            self.assortment_canvas.create_rectangle(
                x1,
                y1,
                x2,
                y2,
                fill=fill,
                outline=outline,
                width=2,
                tags="assortment_range",
            )
            self.assortment_canvas.create_rectangle(
                x1 + 8,
                y1 - 2,
                x2 - 8,
                y1 + 4,
                fill=outline,
                outline=outline,
                tags="assortment_range",
            )
            self.assortment_canvas.create_rectangle(
                x1 + 8,
                y2 - 4,
                x2 - 8,
                y2 + 2,
                fill=outline,
                outline=outline,
                tags="assortment_range",
            )
            start_size = self.assortment_table.output_sizes[start]
            end_size = self.assortment_table.output_sizes[end]
            label = size_class if start == end else f"{size_class}\n{start_size}\n↓\n{end_size}"
            self.assortment_canvas.create_text(
                (x1 + x2) / 2,
                (y1 + y2) / 2,
                text=label,
                fill="#17202a",
                font=("Segoe UI", 9, "bold"),
                justify=tk.CENTER,
                tags="assortment_range",
            )
        self._refresh_assortment_actual_size_classes()

    def _start_assortment_range_drag(self, event: tk.Event) -> None:
        if not self.assortment_table:
            return
        x = self.assortment_canvas.canvasx(event.x)
        y = self.assortment_canvas.canvasy(event.y)
        class_index = int(x // ASSORTMENT_CLASS_WIDTH)
        if class_index < 0 or class_index >= len(SIZE_CLASSES) or y < ASSORTMENT_HEADER_HEIGHT:
            self._assortment_range_drag = None
            return
        row = self._assortment_row_at(y)
        size_class = SIZE_CLASSES[class_index]
        start, end = self.assortment_size_ranges[size_class]
        top = ASSORTMENT_HEADER_HEIGHT + start * ASSORTMENT_ROW_HEIGHT
        bottom = ASSORTMENT_HEADER_HEIGHT + (end + 1) * ASSORTMENT_ROW_HEIGHT
        if top <= y <= bottom:
            if y - top <= 9:
                mode = "start"
            elif bottom - y <= 9:
                mode = "end"
            else:
                mode = "move"
            changed = False
        else:
            mode = "new"
            self.assortment_size_ranges[size_class] = (row, row)
            self._draw_assortment_range_boxes()
            changed = True
        self._assortment_range_drag = {
            "size_class": size_class,
            "mode": mode,
            "anchor": row,
            "start": start,
            "end": end,
        }
        self._assortment_range_drag_changed = changed

    def _drag_assortment_range(self, event: tk.Event) -> None:
        if not self.assortment_table or not self._assortment_range_drag:
            return
        y = self.assortment_canvas.canvasy(event.y)
        row = self._assortment_row_at(y)
        size_class = str(self._assortment_range_drag["size_class"])
        mode = str(self._assortment_range_drag["mode"])
        original_start = int(self._assortment_range_drag["start"])
        original_end = int(self._assortment_range_drag["end"])
        current_start, current_end = self.assortment_size_ranges[size_class]
        if mode == "start":
            updated = (min(row, current_end), current_end)
        elif mode == "end":
            updated = (current_start, max(row, current_start))
        elif mode == "new":
            anchor = int(self._assortment_range_drag["anchor"])
            updated = (min(anchor, row), max(anchor, row))
        else:
            delta = row - int(self._assortment_range_drag["anchor"])
            length = original_end - original_start
            new_start = max(
                0,
                min(original_start + delta, len(self.assortment_table.output_sizes) - length - 1),
            )
            updated = (new_start, new_start + length)
        if updated != self.assortment_size_ranges[size_class]:
            self.assortment_size_ranges[size_class] = updated
            self._assortment_range_drag_changed = True
            self._draw_assortment_range_boxes()

    def _end_assortment_range_drag(self, event: tk.Event) -> None:
        drag = self._assortment_range_drag
        self._assortment_range_drag = None
        if drag:
            size_class = str(drag["size_class"])
            start, end = self.assortment_size_ranges[size_class]
            start_size = self.assortment_table.output_sizes[start] if self.assortment_table else ""
            end_size = self.assortment_table.output_sizes[end] if self.assortment_table else ""
            suffix = " Click Save ranges to keep this change." if self._assortment_range_drag_changed else ""
            self.assortment_status_var.set(
                f"{size_class} uses actual output sizes {start_size} to {end_size}.{suffix}"
            )
            return
        self._describe_assortment_cell(event)

    def _assortment_row_at(self, canvas_y: float) -> int:
        if not self.assortment_table:
            return 0
        row = int((canvas_y - ASSORTMENT_HEADER_HEIGHT) // ASSORTMENT_ROW_HEIGHT)
        return max(0, min(row, len(self.assortment_table.output_sizes) - 1))

    def _save_assortment_size_ranges(self) -> None:
        if not self.assortment_table:
            messagebox.showwarning("Save ranges", "Load the assortment master first.")
            return
        ranges = tuple(
            AssortmentSizeRange(
                size_class,
                self.assortment_table.output_sizes[self.assortment_size_ranges[size_class][0]],
                self.assortment_table.output_sizes[self.assortment_size_ranges[size_class][1]],
            )
            for size_class in SIZE_CLASSES
        )
        try:
            save_size_ranges(
                self.assortment_size_range_file_path,
                ranges,
                self.assortment_table.output_sizes,
            )
        except ValueError as exc:
            messagebox.showerror("Save ranges", str(exc))
            return
        summary = ", ".join(
            f"{item.size_class}: {item.start_size}–{item.end_size}" for item in ranges
        )
        self._refresh_assortment_actual_history_table()
        self._refresh_rm_timeline()
        self.assortment_status_var.set(f"Saved assortment size ranges. {summary}")

    def _scroll_assortment_canvas(self, event: tk.Event) -> str:
        self.assortment_canvas.yview_scroll(int(-event.delta / 120), "units")
        return "break"

    def _describe_assortment_cell(self, event: tk.Event) -> None:
        if not self.assortment_table:
            return
        x = self.assortment_canvas.canvasx(event.x)
        y = self.assortment_canvas.canvasy(event.y)
        data_start = len(SIZE_CLASSES) * ASSORTMENT_CLASS_WIDTH + ASSORTMENT_OUTPUT_WIDTH
        if x < data_start or y < ASSORTMENT_HEADER_HEIGHT:
            return
        base_index = int((x - data_start) // ASSORTMENT_BASE_WIDTH)
        output_index = self._assortment_row_at(y)
        if base_index < 0 or base_index >= len(self.assortment_table.base_sizes):
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
                    record.order_no,
                    record.date,
                    record.month,
                    record.year,
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

        sort_column = SCHEDULE_DATE_COLUMN if column == "date" else column
        numeric = column in NUMERIC_ORDER_COLUMNS
        ascending_label = (
            "↑  Sort Oldest to Newest"
            if column == "date"
            else "↑  Sort Smallest to Largest"
            if numeric
            else "A  Z  Sort A to Z"
        )
        descending_label = (
            "↓  Sort Newest to Oldest"
            if column == "date"
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

if __name__ == "__main__":
    ProductionPlanApp().mainloop()
