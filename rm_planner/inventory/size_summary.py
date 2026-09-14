"""Compare Assortment (supply) against Order demand per day, by RM size group.

Three RM size groups are recognized, based on the shrimp count-per-kg size
buckets recorded in the Assortment upload sheet and the RM size codes used
in the Data sheet's "RM" column:

    51-75   ->  RM size M, HC
    76-100  ->  RM size S, SS
    101+    ->  RM size BK (Broken)

Assortment supply for a date is the sum of its shipment(s)' size-bucket
weights (kg) for that group. Order demand is the sum of each order's
``ho_weight_kg`` on its production date. The "ฝอยคัดทิ้ง >140" waste row is
excluded from the 101+ group since it is culled material, not usable
Broken-grade RM.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from rm_planner.inventory.upload_store import AssortmentShipmentRecord


RM_SIZE_GROUPS: tuple[tuple[str, tuple[str, ...], tuple[str, ...]], ...] = (
    ("M/HC (51-75)", ("M", "HC"), ("51-55", "56-60", "61-65", "66-70", "71-75")),
    ("S/SS (76-100)", ("S", "SS"), ("76-80", "81-85", "86-90", "91-95", "96-100")),
    ("BK (101+)", ("BK",), ("101-120", "121-130", "131-140")),
)
DATE_FIELD_LABEL = "วันที่"


@dataclass(frozen=True, slots=True)
class RmSizeSummaryRow:
    """One (date, RM size group) comparison between supply and usage."""

    record_date: str
    group_label: str
    assortment_kg: float
    data_used_kg: float

    @property
    def difference_kg(self) -> float:
        """Positive = surplus (more supply than used); negative = shortage."""

        return self.assortment_kg - self.data_used_kg


def _parse_number(value: object) -> float:
    text = str(value).strip().replace(",", "")
    if not text:
        return 0.0
    try:
        return float(text)
    except ValueError:
        return 0.0


def _rm_size_to_group() -> dict[str, str]:
    return {
        size.strip().upper(): group_label
        for group_label, rm_sizes, _buckets in RM_SIZE_GROUPS
        for size in rm_sizes
    }


def _group_to_buckets() -> dict[str, tuple[str, ...]]:
    return {group_label: buckets for group_label, _rm_sizes, buckets in RM_SIZE_GROUPS}


def summarize_assortment_supply(
    records: Iterable[AssortmentShipmentRecord],
) -> dict[tuple[str, str], float]:
    """Sum Assortment kg per (date, group_label), across every shipment that date."""

    group_buckets = _group_to_buckets()
    totals: dict[tuple[str, str], float] = {}
    for record in records:
        record_date = record.value(DATE_FIELD_LABEL).strip()
        if not record_date:
            continue
        for group_label, buckets in group_buckets.items():
            group_total = sum(_parse_number(record.value(bucket)) for bucket in buckets)
            key = (record_date, group_label)
            totals[key] = totals.get(key, 0.0) + group_total
    return totals


def summarize_data_usage(
    rows: Iterable[tuple[str, ...]],
    date_index: int,
    rm_size_index: int,
    ho_weight_index: int,
) -> dict[tuple[str, str], float]:
    """Sum น้ำหนัก HO per (date, group_label) using each row's RM size code."""

    size_to_group = _rm_size_to_group()
    max_index = max(date_index, rm_size_index, ho_weight_index)
    totals: dict[tuple[str, str], float] = {}
    for row in rows:
        if len(row) <= max_index:
            continue
        record_date = row[date_index].strip()
        rm_size = row[rm_size_index].strip().upper()
        group_label = size_to_group.get(rm_size)
        if not record_date or group_label is None:
            continue
        weight = _parse_number(row[ho_weight_index])
        key = (record_date, group_label)
        totals[key] = totals.get(key, 0.0) + weight
    return totals


def _order_production_date(order: object) -> str:
    """Return an ISO production date from an OrderRecord-like object."""

    day = str(getattr(order, "prod_date", "")).strip()
    month = str(getattr(order, "prod_month", "")).strip()
    year = str(getattr(order, "prod_year", "")).strip()
    if not day or not month or not year:
        return ""
    try:
        return f"{int(year):04d}-{int(month):02d}-{int(day):02d}"
    except ValueError:
        return ""


def summarize_order_usage(orders: Iterable[object]) -> dict[tuple[str, str], float]:
    """Sum Order WT/HO demand per production date and RM size group.

    The summary intentionally uses the Order schedule instead of raw Data
    rows.  Orders without a complete production date, recognized RM size, or
    calculated WT/HO value are not included.
    """

    size_to_group = _rm_size_to_group()
    totals: dict[tuple[str, str], float] = {}
    for order in orders:
        record_date = _order_production_date(order)
        rm_size = str(getattr(order, "rm_size", "")).strip().upper()
        group_label = size_to_group.get(rm_size)
        if not record_date or group_label is None:
            continue
        weight = getattr(order, "ho_weight_kg", None)
        if weight is None:
            continue
        key = (record_date, group_label)
        totals[key] = totals.get(key, 0.0) + _parse_number(weight)
    return totals


def build_summary_rows(
    assortment_records: Iterable[AssortmentShipmentRecord],
    data_rows: Iterable[tuple[str, ...]],
    date_index: int,
    rm_size_index: int,
    ho_weight_index: int,
) -> list[RmSizeSummaryRow]:
    """Build one row per (date, RM size group) found in either source."""

    assortment_totals = summarize_assortment_supply(assortment_records)
    data_totals = summarize_data_usage(data_rows, date_index, rm_size_index, ho_weight_index)

    all_keys = set(assortment_totals) | set(data_totals)
    rows = [
        RmSizeSummaryRow(
            record_date=record_date,
            group_label=group_label,
            assortment_kg=assortment_totals.get((record_date, group_label), 0.0),
            data_used_kg=data_totals.get((record_date, group_label), 0.0),
        )
        for record_date, group_label in all_keys
    ]
    group_order = {label: index for index, (label, _sizes, _buckets) in enumerate(RM_SIZE_GROUPS)}
    rows.sort(key=lambda row: (row.record_date, group_order.get(row.group_label, len(RM_SIZE_GROUPS))))
    return rows


def build_order_summary_rows(
    assortment_records: Iterable[AssortmentShipmentRecord],
    orders: Iterable[object],
) -> list[RmSizeSummaryRow]:
    """Build Summary rows from Assortment supply and Order WT/HO demand."""

    assortment_totals = summarize_assortment_supply(assortment_records)
    order_totals = summarize_order_usage(orders)
    all_keys = set(assortment_totals) | set(order_totals)
    rows = [
        RmSizeSummaryRow(
            record_date=record_date,
            group_label=group_label,
            assortment_kg=assortment_totals.get((record_date, group_label), 0.0),
            data_used_kg=order_totals.get((record_date, group_label), 0.0),
        )
        for record_date, group_label in all_keys
    ]
    group_order = {label: index for index, (label, _sizes, _buckets) in enumerate(RM_SIZE_GROUPS)}
    rows.sort(key=lambda row: (row.record_date, group_order.get(row.group_label, len(RM_SIZE_GROUPS))))
    return rows
