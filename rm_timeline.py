"""RM arrival timeline and cumulative stock calculations."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from assortment_actual_store import (
    ActualAssortmentRecord,
    split_size_range,
)
from assortment_range_store import (
    AssortmentSizeRange,
    SIZE_CLASSES,
    SizeClassWeightSummary,
    normalize_size_class,
    summarize_size_class_weight_details,
)
from wonton_weight_store import WontonWeightSettings


@dataclass(frozen=True, slots=True)
class RmTimelineRow:
    record_date: str
    rm_ids: tuple[str, ...]
    incoming_kg: float
    cumulative_kg: float
    m_stock: SizeClassWeightSummary
    s_plus_stock: SizeClassWeightSummary
    m_wontons: float
    s_plus_wontons: float
    unused_stock: SizeClassWeightSummary
    incoming_wontons: float
    cumulative_wontons: float


def build_rm_timeline(
    records: Iterable[ActualAssortmentRecord],
    ranges: Iterable[AssortmentSizeRange],
    market_type: str | None = None,
    wonton_weight_settings: WontonWeightSettings | None = None,
) -> tuple[RmTimelineRow, ...]:
    """Group filtered RM arrivals by date and return cumulative stock rows."""

    range_list = tuple(ranges)
    weight_settings = wonton_weight_settings or WontonWeightSettings()
    normalized_market = _normalize_filter(market_type)
    filtered = [
        record
        for record in records
        if normalized_market is None or record.market_type == normalized_market
    ]
    by_date: dict[str, list[ActualAssortmentRecord]] = {}
    for record in filtered:
        by_date.setdefault(record.record_date, []).append(record)

    cumulative_kg = 0.0
    cumulative_wontons = 0.0
    summary_classes = (*SIZE_CLASSES, "Unused")
    cumulative_totals = {key: 0.0 for key in summary_classes}
    cumulative_class_wontons = {key: 0.0 for key in summary_classes}
    rows: list[RmTimelineRow] = []
    for record_date in sorted(by_date):
        dated_records = sorted(by_date[record_date], key=lambda item: item.rm_id)
        incoming_kg = sum(record.total_weight for record in dated_records)
        daily_summaries = _summarize_records(dated_records, range_list)
        daily_class_wontons = {
            size_class: weight_settings.estimate_wontons(
                size_class,
                daily_summaries[size_class].total,
            )
            for size_class in SIZE_CLASSES
        }
        daily_class_wontons["Unused"] = 0.0
        incoming_wontons = sum(daily_class_wontons.values())
        cumulative_kg += incoming_kg
        cumulative_wontons += incoming_wontons
        for size_class, summary in daily_summaries.items():
            cumulative_totals[size_class] += float(summary.total)
            cumulative_class_wontons[size_class] += daily_class_wontons[size_class]

        rows.append(
            RmTimelineRow(
                record_date=record_date,
                rm_ids=tuple(record.rm_id for record in dated_records),
                incoming_kg=incoming_kg,
                cumulative_kg=cumulative_kg,
                m_stock=_summary(cumulative_totals["M"]),
                s_plus_stock=_summary(cumulative_totals["S+"]),
                m_wontons=_number(cumulative_class_wontons["M"]),
                s_plus_wontons=_number(cumulative_class_wontons["S+"]),
                unused_stock=_summary(cumulative_totals["Unused"]),
                incoming_wontons=incoming_wontons,
                cumulative_wontons=cumulative_wontons,
            )
        )
    return tuple(rows)


def stock_distribution_percentages(
    m_stock: int | float,
    s_plus_stock: int | float,
    unused_stock: int | float,
) -> tuple[float, float, float]:
    """Return the M, S+, and Unused shares of total stock."""

    weights = tuple(float(value) for value in (m_stock, s_plus_stock, unused_stock))
    if any(value < 0 for value in weights):
        raise ValueError("Stock distribution weights cannot be negative.")
    total = sum(weights)
    if total == 0:
        return (0.0, 0.0, 0.0)
    return tuple(value / total * 100 for value in weights)


def _summarize_records(
    records: Iterable[ActualAssortmentRecord],
    ranges: tuple[AssortmentSizeRange, ...],
) -> dict[str, SizeClassWeightSummary]:
    if not ranges:
        total = sum(record.total_weight for record in records)
        return {
            "M": SizeClassWeightSummary(0),
            "S+": SizeClassWeightSummary(0),
            "Unused": SizeClassWeightSummary(total),
        }
    entries: list[tuple[str, str, float]] = []
    direct_totals = {key: 0.0 for key in (*SIZE_CLASSES, "Unused")}
    for record in records:
        for entry in record.entries:
            size_class = normalize_size_class(entry.size_class)
            if size_class in direct_totals:
                direct_totals[size_class] += float(entry.weight)
                continue
            start, end = split_size_range(entry.size)
            entries.append((start, end, entry.weight))
    summarized = summarize_size_class_weight_details(entries, ranges)
    return {
        size_class: SizeClassWeightSummary(
            summarized[size_class].total + direct_totals.get(size_class, 0),
        )
        for size_class in (*SIZE_CLASSES, "Unused")
    }


def _summary(total: float) -> SizeClassWeightSummary:
    return SizeClassWeightSummary(_number(total))


def _number(total: float) -> int | float:
    return int(total) if total.is_integer() else total


def _normalize_filter(value: str | None) -> str | None:
    normalized = str(value or "").strip().casefold()
    return None if normalized in {"", "all"} else normalized
