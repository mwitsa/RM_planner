"""Application assembly and shared window setup."""

from __future__ import annotations

from .common import *  # shared UI types, domain services, and display constants
from .data_view import DataViewMixin
from .master_view import MasterViewMixin
from .shipment_view import ShipmentViewMixin
from .summary_view import SummaryViewMixin
from .stock_overview import StockOverviewMixin
from .existing_stock import ExistingStockMixin
from .stock_editor import StockEditorMixin
from .plan_view import PlanViewMixin
from .class_define import ClassDefineMixin
from .capacity_view import CapacityViewMixin
from .rule_view import RuleViewMixin
from .assortment_view import AssortmentViewMixin
from .orders_view import OrdersViewMixin


class ProductionPlanApp(DataViewMixin, MasterViewMixin, ShipmentViewMixin, SummaryViewMixin, StockOverviewMixin, ExistingStockMixin, StockEditorMixin, PlanViewMixin, ClassDefineMixin, CapacityViewMixin, RuleViewMixin, AssortmentViewMixin, OrdersViewMixin, tk.Tk):
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
        self.plan_status_var = tk.StringVar(value="Load data on the Data tab first.")
        self.plan_start_date_var = tk.StringVar()
        self.plan_end_date_var = tk.StringVar()
        self.plan_columns: list[str] = []
        self.plan_tree: ttk.Treeview | None = None
        self.data_status_var = tk.StringVar(value="Load a workbook on the Order tab, then load raw data here.")
        self.raw_data_result: RawDataResult | None = None
        self.raw_data_all_rows: list[tuple[str, ...]] = []
        self.raw_data_headers: list[str] = []
        self.raw_data_filter_selections: dict[str, str | frozenset[str]] = {}
        self.raw_data_sort_column: str | None = None
        self.raw_data_sort_descending = False
        self._data_filter_popup: tk.Toplevel | None = None
        self._data_filter_outside_binding: str | None = None
        self.result: ExtractionResult | None = None
        self.saved_order_records: dict[str, OrderRecord] = {}
        self.order_records_by_id: dict[str, OrderRecord] = {}
        # The default visible window is based on the production schedule, so
        # present those orders in production-date order as well.
        self.order_sort_column: str | None = PROD_SCHEDULE_DATE_COLUMN
        self.order_sort_descending = False
        self.hide_past_orders = True
        self.assortment_table: AssortmentTable | None = None
        self.rule_file_path = PROJECT_ROOT / "Data" / "Rules" / "plan_rules.json"
        self.assortment_file_path = PROJECT_ROOT / "Data" / "RM" / "assortment.xlsx"
        self.assortment_size_range_file_path = (
            PROJECT_ROOT / "Data" / "RM" / "assortment_size_ranges.json"
        )
        self.wonton_weight_file_path = (
            PROJECT_ROOT / "Data" / "RM" / "wonton_weights.json"
        )
        self.assortment_actual_file_path = (
            PROJECT_ROOT / "Data" / "RM" / "assortment_actual.json"
        )
        self.saved_orders_file_path = (
            PROJECT_ROOT / "Data" / "Order" / "saved_orders.json"
        )
        self.class_definitions_file_path = (
            PROJECT_ROOT / "Data" / "Class" / "class_definitions.json"
        )
        self.capacity_file_path = (
            PROJECT_ROOT / "Data" / "Capacity" / "capacity.json"
        )
        self.master_workbook_file_path = (
            PROJECT_ROOT / "Data" / "Master" / "Master PCK ING.xlsx"
        )
        self.master_store_file_path = (
            PROJECT_ROOT / "Data" / "Master" / "master_pck_ing.json"
        )
        self.master_file_var = tk.StringVar(value=str(self.master_workbook_file_path))
        self.master_status_var = tk.StringVar(value="No master data loaded yet.")
        self.master_records: list[MasterComponentRecord] = []
        self.master_sort_column: str | None = None
        self.master_sort_descending = False
        self.assortment_upload_workbook_file_path = (
            PROJECT_ROOT
            / "Data"
            / "Assortment"
            / "RM Plan เกี๊ยวตะวันออก.xlsx"
        )
        self.assortment_upload_store_file_path = (
            PROJECT_ROOT / "Data" / "Assortment" / "assortment_shipments.json"
        )
        self.assortment_upload_file_var = tk.StringVar(
            value=str(self.assortment_upload_workbook_file_path)
        )
        self.assortment_upload_status_var = tk.StringVar(value="No assortment data loaded yet.")
        self.assortment_upload_field_labels: list[str] = []
        self.assortment_upload_records: list[AssortmentShipmentRecord] = []
        self.assortment_upload_columns: list[str] = []
        self.assortment_upload_tree: ttk.Treeview | None = None
        self.assortment_upload_sort_column: str | None = None
        self.assortment_upload_sort_descending = False
        self.summary_status_var = tk.StringVar(
            value="Load data on the Data and Assortment tabs first."
        )
        self.summary_tree: ttk.Treeview | None = None
        self.capacity_settings = CapacitySettings()
        self.wonton_weight_settings = WontonWeightSettings()
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
        self._load_wonton_weight_settings()
        self._load_assortment_actual_history()
        self._load_saved_orders()
        self._load_saved_class_definitions()
        self._load_capacity_settings()
        self._load_saved_master_data()
        self._load_saved_assortment_upload()
        # Use the selected workbook as the active Order/Plan source.  Saved
        # orders are loaded first only to retain manual production entries.
        self.after(0, self._start_extraction)

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

        self.data_tab = ttk.Frame(self.notebook, padding=14)
        self.notebook.add(self.data_tab, text="Data")
        self._build_data_tab()

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

        self.master_tab = ttk.Frame(self.notebook, padding=14)
        self.notebook.add(self.master_tab, text="Master")
        self._build_master_tab()

        self.assortment_upload_tab = ttk.Frame(self.notebook, padding=14)
        self.notebook.add(self.assortment_upload_tab, text="Assortment")
        self._build_assortment_upload_tab()

        self.summary_tab = ttk.Frame(self.notebook, padding=14)
        self.notebook.add(self.summary_tab, text="Summary")
        self._build_summary_tab()

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
            "prod_date",
            "date",
            "order_no",
            "country",
            "customer",
            "code",
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
            "ho_weight_kg",
        )
        self.tree = ttk.Treeview(table_frame, columns=columns, show="headings")
        self.order_headings = {
            "order_no": "Order No.",
            "prod_date": "Prod.Date",
            "date": "Load.Date",
            "country": "Country",
            "customer": "Customer",
            "code": "CODE",
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
            "ho_weight_kg": "น้ำหนัก HO (kg)",
        }
        widths = {
            "order_no": 105,
            "prod_date": 100,
            "date": 100,
            "country": 100,
            "customer": 260,
            "code": 100,
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
            "ho_weight_kg": 130,
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
                "ho_weight_kg",
            ) else tk.W
            self.tree.column(column, width=widths[column], minwidth=70, anchor=anchor)

        # Treeview has only one native header row.  Draw an aligned group bar
        # above it so related columns remain easy to scan without changing the
        # individual clickable/filterable column headings.
        self.order_group_header = tk.Canvas(
            table_frame,
            height=30,
            background="#f6f8fb",
            highlightthickness=0,
            borderwidth=0,
        )
        self.order_column_groups = (
            ("Order data", ("prod_date", "date", "order_no", "country", "customer"), "#dceeff", "#24567b"),
            ("SKU detail", ("code", "group_1", "group_2", "packaging", "rm_size", "soup"), "#e8e0fb", "#513a87"),
            ("ปริมาณผลิต", ("wontons_per_cup", "order_unit", "order_cups", "cups_per_unit", "total_wontons", "ho_weight_kg"), "#e1f3e8", "#24613c"),
        )
        self.order_column_widths = widths
        self.order_group_visibility = {
            label: tk.BooleanVar(value=True)
            for label, _members, _background, _foreground in self.order_column_groups
        }
        self._refresh_order_group_header(tuple(columns))

        vertical = ttk.Scrollbar(table_frame, orient=tk.VERTICAL, command=self.tree.yview)
        horizontal = ttk.Scrollbar(table_frame, orient=tk.HORIZONTAL, command=self.tree.xview)

        def sync_order_horizontal_scroll(first: str, last: str) -> None:
            horizontal.set(first, last)
            self.order_group_header.xview_moveto(float(first))

        self.tree.configure(yscrollcommand=vertical.set, xscrollcommand=sync_order_horizontal_scroll)
        self.order_group_header.grid(row=0, column=0, sticky="ew")
        self.tree.grid(row=1, column=0, sticky="nsew")
        vertical.grid(row=1, column=1, sticky="ns")
        horizontal.grid(row=2, column=0, sticky="ew")
        table_frame.rowconfigure(1, weight=1)
        table_frame.columnconfigure(0, weight=1)

        status = ttk.Label(
            self.order_tab,
            textvariable=self.status_var,
            relief=tk.SUNKEN,
            anchor=tk.W,
            padding=(6, 3),
        )
        status.pack(fill=tk.X, pady=(8, 0))
