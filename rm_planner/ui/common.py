"""Tkinter desktop UI for extracting production orders and planning inputs."""

from __future__ import annotations

import math
import threading
import tkinter as tk
from collections.abc import Callable, Iterable
from datetime import date
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog, ttk

from rm_planner.inventory.assortment import AssortmentTable, load_assortment, predict_assortment
from rm_planner.inventory.range_store import (
    SIZE_CLASSES,
    AssortmentSizeRange,
    default_size_ranges,
    load_size_ranges,
    normalize_size_class,
    save_size_ranges,
    SizeClassWeightSummary,
)
from rm_planner.inventory.actual_store import (
    ActualAssortmentEntry,
    ActualAssortmentRecord,
    aggregate_entries_by_size_class,
    delete_actual_record,
    load_actual_records,
    upsert_actual_record,
)
from rm_planner.planning.class_store import (
    ALL_CLASS_FILTER,
    ClassDefinition,
    add_missing_class_definitions,
    class_filter_options,
    filter_class_definitions,
    load_class_definitions,
    order_class_names,
    upsert_class_definition,
    update_class_definitions,
)
from rm_planner.planning.capacity_store import (
    CapacitySettings,
    capacities_at_percentage,
    load_capacity_settings,
    save_capacity_settings,
)
from rm_planner.orders.extractor import (
    ExtractionResult,
    OrderRecord,
    choose_default_sheet,
    extract_orders,
    list_sheets,
)
from rm_planner.master.store import (
    MasterComponentRecord,
    extract_master_data,
    load_master_data,
    save_master_data,
)
from rm_planner.inventory.upload_store import (
    AssortmentShipmentRecord,
    extract_assortment_shipments,
    load_assortment_shipments,
    save_assortment_shipments,
)
from rm_planner.inventory.size_summary import RM_SIZE_GROUPS, build_order_summary_rows, build_summary_rows
from rm_planner.orders.store import load_order_records, merge_order_records, save_order_records
from rm_planner.planning.market_labels import MARKET_DISPLAY_OPTIONS, market_display_label
from rm_planner.orders.filters import (
    ALL_FILTER,
    BLANK_FILTER,
    FILTER_SPECS,
    NUMERIC_ORDER_COLUMNS,
    PROD_SCHEDULE_DATE_COLUMN,
    SCHEDULE_DATE_COLUMN,
    cascading_filter_state,
    current_and_future_orders,
    filter_options,
    filter_orders,
    sort_orders,
)
from rm_planner.inventory.timeline import build_rm_timeline, stock_distribution_percentages
from rm_planner.inventory.wonton_weight_store import (
    WontonWeightSettings,
    load_wonton_weight_settings,
    save_wonton_weight_settings,
)


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
    "S": ("#fff0d8", "#c57617"),
    "SS": ("#dcf5df", "#338a3e"),
}
RM_STOCK_DISTRIBUTION_COLORS = {
    "M": "#4f91c3",
    "S": "#d58a2a",
    "SS": "#63a967",
    "Unused": "#91979d",
}
ORDER_COLUMN_FILTER_KEYS = {
    "order_no": "order_no",
    "prod_date": "prod_date",
    "date": "date",
    "country": "country",
    "customer": "customer",
    "code": "code",
    "product": "product",
    "group_1": "group_1",
    "group_2": "group_2",
    "packaging": "packaging",
    "rm_size": "rm_size",
    "dip": "dip",
    "soup": "soup",
    "cups": "cups",
    "pcs_per_cup": "pcs_per_cup",
    "wt_per_pcs": "wt_per_pcs",
    "wontons_per_cup": "wontons_per_cup",
    "order_unit": "order_unit",
    "stock_unit": "stock_unit",
    "order_cups": "order_cups",
    "cups_per_unit": "cups_per_unit",
    "total_wontons": "total_wontons",
    "wt_pd_kg": "wt_pd_kg",
    "ho_weight_kg": "ho_weight_kg",
    "production": "production",
}
DEFAULT_EXISTING_STOCK_PIECES_PER_KG = {
    "M": "53",
    "S": "69.25",
    "SS": "69.25",
}



# Project data stays beside the launcher, regardless of the UI module location.
PROJECT_ROOT = Path(__file__).resolve().parents[2]
