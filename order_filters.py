"""Composable filters for structured production orders."""

from __future__ import annotations

from collections.abc import Collection, Iterable, Mapping

from extractor import OrderRecord


ALL_FILTER = "All"
BLANK_FILTER = "(blank)"
PRODUCTION_ENTERED = "Entered"
PRODUCTION_MISSING = "Not entered"
NUMERIC_ORDER_COLUMNS = {
    "date",
    "month",
    "year",
    "wontons_per_cup",
    "order_unit",
    "order_cups",
    "cups_per_unit",
    "total_wontons",
    "production",
}
ORDER_COLUMN_ATTRIBUTES = {
    "customer": "customer_name",
}

FILTER_SPECS = (
    ("year", "Year"),
    ("month", "Month"),
    ("date", "Date"),
    ("country", "Country"),
    ("customer", "Customer"),
    ("group_1", "Group 1"),
    ("group_2", "Group 2"),
    ("packaging", "Packaging"),
    ("rm_size", "RM Size"),
    ("soup", "Soup"),
    ("cups_per_unit", "ถ้วย/Unit"),
    ("production_status", "Production status"),
)

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
    if key == "cups_per_unit":
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


def filter_value(record: OrderRecord, key: str) -> str:
    if key == "customer":
        value = record.customer_name
    elif key == "production_status":
        return PRODUCTION_ENTERED if record.production is not None else PRODUCTION_MISSING
    elif key == "cups_per_unit":
        if record.cups_per_unit is None:
            return BLANK_FILTER
        return f"{record.cups_per_unit:.2f}".rstrip("0").rstrip(".")
    elif key in {
        "year",
        "month",
        "date",
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
