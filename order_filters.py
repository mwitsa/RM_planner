"""Composable filters for structured production orders."""

from __future__ import annotations

from collections.abc import Iterable, Mapping

from extractor import OrderRecord


ALL_FILTER = "All"
BLANK_FILTER = "(blank)"
PRODUCTION_ENTERED = "Entered"
PRODUCTION_MISSING = "Not entered"

FILTER_SPECS = (
    ("period", "Period"),
    ("year", "Year"),
    ("month", "Month"),
    ("date", "Date"),
    ("country", "Country"),
    ("customer", "Customer"),
    ("group_1", "Group 1"),
    ("group_2", "Group 2"),
    ("packaging", "Packaging"),
    ("soup", "Soup"),
    ("production_status", "Production status"),
)


def filter_orders(
    records: Iterable[OrderRecord],
    selections: Mapping[str, str],
) -> list[OrderRecord]:
    """Apply every non-All selection using AND logic."""

    return [
        record
        for record in records
        if all(
            selected == ALL_FILTER or filter_value(record, key) == selected
            for key, selected in selections.items()
        )
    ]


def filter_options(records: Iterable[OrderRecord], key: str) -> list[str]:
    """Return sorted unique display values for one filter."""

    if key == "production_status":
        return [PRODUCTION_ENTERED, PRODUCTION_MISSING]
    values = {filter_value(record, key) for record in records}
    return sorted(values, key=lambda value: (value == BLANK_FILTER, value.casefold()))


def filter_value(record: OrderRecord, key: str) -> str:
    if key == "period":
        value = record.month_key
    elif key == "customer":
        value = record.customer_name
    elif key == "production_status":
        return PRODUCTION_ENTERED if record.production is not None else PRODUCTION_MISSING
    elif key in {
        "year",
        "month",
        "date",
        "country",
        "group_1",
        "group_2",
        "packaging",
        "soup",
    }:
        value = getattr(record, key)
    else:
        raise ValueError(f"Unknown order filter: {key}")
    return str(value).strip() or BLANK_FILTER
