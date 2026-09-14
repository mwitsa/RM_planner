"""Composable filters for structured production orders."""

from __future__ import annotations

from calendar import monthrange
from collections.abc import Collection, Iterable, Mapping
from datetime import date

from rm_planner.orders.extractor import OrderRecord


ALL_FILTER = "All"
SCHEDULE_DATE_COLUMN = "schedule_date"
PROD_SCHEDULE_DATE_COLUMN = "prod_schedule_date"
BLANK_FILTER = "(blank)"
PRODUCTION_ENTERED = "Entered"
PRODUCTION_MISSING = "Not entered"
NUMERIC_ORDER_COLUMNS = {
    "date",
    "prod_date",
    "wontons_per_cup",
    "order_unit",
    "order_cups",
    "cups_per_unit",
    "total_wontons",
    "ho_weight_kg",
    "production",
    "cups",
    "pcs_per_cup",
    "wt_per_pcs",
}
ORDER_COLUMN_ATTRIBUTES = {
    "customer": "customer_name",
}

FILTER_SPECS = (
    ("order_no", "Order No."),
    ("prod_date", "Prod.Date"),
    ("date", "Load.Date"),
    ("country", "Country"),
    ("customer", "Customer"),
    ("code", "CODE"),
    ("group_1", "Group 1"),
    ("group_2", "Group 2"),
    ("packaging", "Packaging"),
    ("rm_size", "RM Size"),
    ("dip", "Dip"),
    ("soup", "Soup"),
    ("cups", "cups"),
    ("pcs_per_cup", "Pcs./Cup"),
    ("wt_per_pcs", "WT/Pcs"),
    ("wontons_per_cup", "ลูกเกี๊ยว/ถ้วย"),
    ("order_unit", "Order (unit)"),
    ("order_cups", "Order (ถ้วย)"),
    ("cups_per_unit", "ถ้วย/Unit"),
    ("total_wontons", "จำนวนเกี๊ยว"),
    ("ho_weight_kg", "น้ำหนัก HO (kg)"),
    ("production", "Production"),
)

NUMERIC_FILTER_KEYS = {
    "wontons_per_cup",
    "order_unit",
    "order_cups",
    "cups_per_unit",
    "total_wontons",
    "ho_weight_kg",
    "production",
    "cups",
    "pcs_per_cup",
    "wt_per_pcs",
}

FilterSelection = str | frozenset[str]


def _matches_selection(value: str, selected: str | Collection[str]) -> bool:
    if selected == ALL_FILTER:
        return True
    if isinstance(selected, str):
        return value == selected
    return value in selected


def _normalize_selection(
    selected: str | Collection[str],
    available: Collection[str],
) -> FilterSelection:
    if selected == ALL_FILTER:
        return ALL_FILTER
    if isinstance(selected, str):
        return selected if selected in available else ALL_FILTER
    retained = frozenset(value for value in selected if value in available)
    if not retained or retained == frozenset(available):
        return ALL_FILTER
    return retained


def filter_orders(
    records: Iterable[OrderRecord],
    selections: Mapping[str, str | Collection[str]],
) -> list[OrderRecord]:
    """Apply single- or multi-value selections using AND logic between columns."""

    return [
        record
        for record in records
        if all(
            _matches_selection(filter_value(record, key), selected)
            for key, selected in selections.items()
        )
    ]


def filter_options(records: Iterable[OrderRecord], key: str) -> list[str]:
    """Return sorted unique display values for one filter."""

    if key == "production_status":
        return [PRODUCTION_ENTERED, PRODUCTION_MISSING]
    values = {filter_value(record, key) for record in records}
    if key in NUMERIC_FILTER_KEYS:
        return sorted(
            values,
            key=lambda value: (
                value == BLANK_FILTER,
                float("inf") if value == BLANK_FILTER else float(value),
            ),
        )
    return sorted(values, key=lambda value: (value == BLANK_FILTER, value.casefold()))


def cascading_filter_state(
    records: Iterable[OrderRecord],
    selections: Mapping[str, str | Collection[str]],
    keys: Iterable[str],
    preferred_key: str | None = None,
) -> tuple[dict[str, FilterSelection], dict[str, list[str]]]:
    """Normalize selections and calculate each filter's context-aware options."""

    record_list = list(records)
    filter_keys = tuple(keys)
    current = {key: selections.get(key, ALL_FILTER) for key in filter_keys}
    evaluation_order = tuple(key for key in filter_keys if key != preferred_key)
    if preferred_key in filter_keys:
        evaluation_order = (*evaluation_order, preferred_key)

    for _ in range(len(filter_keys) + 1):
        changed = False
        for key in evaluation_order:
            candidates = filter_orders(
                record_list,
                {other: current[other] for other in filter_keys if other != key},
            )
            available = filter_options(candidates, key)
            normalized = _normalize_selection(current[key], available)
            if current[key] != normalized:
                current[key] = normalized
                changed = True
        if not changed:
            break

    options: dict[str, list[str]] = {}
    for key in filter_keys:
        candidates = filter_orders(
            record_list,
            {other: current[other] for other in filter_keys if other != key},
        )
        options[key] = filter_options(candidates, key)
    return current, options


def sort_orders(
    records: Iterable[OrderRecord],
    column: str | None,
    descending: bool = False,
) -> list[OrderRecord]:
    """Sort one displayed Order column while keeping blank values last."""

    record_list = list(records)
    if column is None:
        return record_list
    if column in _SCHEDULE_COLUMNS:
        effective_date_fn, day_field = _SCHEDULE_COLUMNS[column]
        dated: list[tuple[date, bool, OrderRecord]] = []
        undated: list[OrderRecord] = []
        for record in record_list:
            effective_date = effective_date_fn(record)
            if effective_date is None:
                undated.append(record)
            else:
                month_only = not str(getattr(record, day_field)).strip()
                dated.append((effective_date, month_only, record))
        # Preserve explicit month-end dates before month-only rows even when the
        # primary date direction is reversed.
        dated.sort(key=lambda item: item[1])
        dated.sort(key=lambda item: item[0], reverse=descending)
        return [record for _value, _month_only, record in dated] + undated
    attribute = ORDER_COLUMN_ATTRIBUTES.get(column, column)
    if not hasattr(OrderRecord, attribute) and attribute not in OrderRecord.__slots__:
        raise ValueError(f"Unknown order sort column: {column}")

    populated: list[tuple[object, OrderRecord]] = []
    blanks: list[OrderRecord] = []
    for record in record_list:
        value = getattr(record, attribute)
        if value is None or (isinstance(value, str) and not value.strip()):
            blanks.append(record)
            continue
        if column in NUMERIC_ORDER_COLUMNS:
            sort_value: object = float(value)
        else:
            sort_value = str(value).casefold()
        populated.append((sort_value, record))
    populated.sort(key=lambda item: item[0], reverse=descending)
    return [record for _value, record in populated] + blanks


def order_effective_date(record: OrderRecord) -> date | None:
    """Return an exact order date, or month-end for a month-only order."""

    return _effective_date(record.year, record.month, record.date)


def prod_effective_date(record: OrderRecord) -> date | None:
    """Return an exact production date, or month-end for a month-only order."""

    return _effective_date(record.prod_year, record.prod_month, record.prod_date)


def _effective_date(year: str, month: str, day: str) -> date | None:
    try:
        year_number = int(str(year).strip())
        month_number = int(str(month).strip())
        day_text = str(day).strip()
        day_number = int(day_text) if day_text else monthrange(year_number, month_number)[1]
        return date(year_number, month_number, day_number)
    except (TypeError, ValueError):
        return None


_SCHEDULE_COLUMNS = {
    SCHEDULE_DATE_COLUMN: (order_effective_date, "date"),
    PROD_SCHEDULE_DATE_COLUMN: (prod_effective_date, "prod_date"),
}


def current_and_future_orders(
    records: Iterable[OrderRecord],
    today: date,
) -> list[OrderRecord]:
    """Hide orders with a production date before today.

    Rows without a usable production date stay visible so incomplete source data
    is not silently hidden from the order screen.
    """

    return [
        record
        for record in records
        if (effective_date := prod_effective_date(record)) is None
        or effective_date >= today
    ]


def filter_value(record: OrderRecord, key: str) -> str:
    if key == "customer":
        value = record.customer_name
    elif key == "production_status":
        return PRODUCTION_ENTERED if record.production is not None else PRODUCTION_MISSING
    elif key in NUMERIC_FILTER_KEYS:
        value = getattr(record, key)
        if value is None:
            return BLANK_FILTER
        return f"{value:.2f}".rstrip("0").rstrip(".")
    elif key == "date":
        value = record.load_date_display
    elif key == "prod_date":
        value = record.prod_date_display
    elif key in {
        "order_no",
        "country",
        "group_1",
        "group_2",
        "packaging",
        "rm_size",
        "soup",
    }:
        value = getattr(record, key)
    else:
        raise ValueError(f"Unknown order filter: {key}")
    return str(value).strip() or BLANK_FILTER
