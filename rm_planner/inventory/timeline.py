"""RM arrival timeline and cumulative stock calculations."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Iterable

from rm_planner.inventory.actual_store import (
    ActualAssortmentRecord,
    STOCK_SIZE_CLASSES,
    split_size_range,
)
from rm_planner.inventory.range_store import (
    AssortmentSizeRange,
    SIZE_CLASSES,
    SizeClassWeightSummary,
    normalize_size_class,
    summarize_size_class_weight_details,
)
from rm_planner.inventory.wonton_weight_store import WontonWeightSettings


@dataclass(frozen=True, slots=True)
class RmTimelineRow:
    record_date: str
    source_labels: tuple[str, ...]
    incoming_kg: float
    cumulative_kg: float
    m_stock: SizeClassWeightSummary
    s_stock: SizeClassWeightSummary
    ss_stock: SizeClassWeightSummary
    hc_stock: SizeClassWeightSummary
    bk_stock: SizeClassWeightSummary
    m_wontons: float
    s_wontons: float
    ss_wontons: float
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
    filtered = []
    for record in records:
        entries = tuple(
            entry for entry in record.entries
            if normalized_market is None or (entry.market_type or record.market_type) == normalized_market
        )
        if entries:
            filtered.append(replace(record, entries=entries))
    by_date: dict[str, list[ActualAssortmentRecord]] = {}
    for record in filtered:
        by_date.setdefault(record.record_date, []).append(record)

    cumulative_kg = 0.0
    cumulative_wontons = 0.0
    summary_classes = STOCK_SIZE_CLASSES
    cumulative_totals = {key: 0.0 for key in summary_classes}
    cumulative_class_wontons = {key: 0.0 for key in summary_classes}
    rows: list[RmTimelineRow] = []
    for record_date in sorted(by_date):
        dated_records = sorted(
            by_date[record_date],
            key=lambda item: (item.source_label.casefold(), item.record_id),
        )
        incoming_kg = sum(record.total_weight for record in dated_records)
        daily_summaries = _summarize_records(dated_records, range_list)
        daily_class_wontons = {
            size_class: (
                weight_settings.estimate_wontons(size_class, daily_summaries[size_class].total)
                if size_class in SIZE_CLASSES else 0.0
            )
            for size_class in summary_classes
        }
        incoming_wontons = sum(daily_class_wontons.values())
        cumulative_kg += incoming_kg
        cumulative_wontons += incoming_wontons
        for size_class, summary in daily_summaries.items():
            cumulative_totals[size_class] += float(summary.total)
            cumulative_class_wontons[size_class] += daily_class_wontons[size_class]

        rows.append(
            RmTimelineRow(
                record_date=record_date,
                source_labels=tuple(record.source_label for record in dated_records),
                incoming_kg=incoming_kg,
                cumulative_kg=cumulative_kg,
                m_stock=_summary(cumulative_totals["M"]),
                s_stock=_summary(cumulative_totals["S"]),
                ss_stock=_summary(cumulative_totals["SS"]),
                hc_stock=_summary(cumulative_totals["HC"]),
                bk_stock=_summary(cumulative_totals["BK"]),
                m_wontons=_number(cumulative_class_wontons["M"]),
                s_wontons=_number(cumulative_class_wontons["S"]),
                ss_wontons=_number(cumulative_class_wontons["SS"]),
                unused_stock=_summary(cumulative_totals["Unused"]),
                incoming_wontons=incoming_wontons,
                cumulative_wontons=cumulative_wontons,
            )
        )
    return tuple(rows)


def stock_distribution_percentages(*stock_weights: int | float) -> tuple[float, ...]:
    """Return percentage shares for the supplied stock-class weights."""

    weights = tuple(float(value) for value in stock_weights)
    if any(value < 0 for value in weights):
        raise ValueError("Stock distribution weights cannot be negative.")
    total = sum(weights)
    if total == 0:
        return tuple(0.0 for _ in weights)
    return tuple(value / total * 100 for value in weights)


def _summarize_records(
    records: Iterable[ActualAssortmentRecord],
    ranges: tuple[AssortmentSizeRange, ...],
) -> dict[str, SizeClassWeightSummary]:
    entries: list[tuple[str, str, float]] = []
    direct_totals = {key: 0.0 for key in STOCK_SIZE_CLASSES}
    for record in records:
        for entry in record.entries:
            size_class = normalize_size_class(entry.size_class)
            if size_class in direct_totals:
                direct_totals[size_class] += float(entry.weight)
                continue
            start, end = split_size_range(entry.size)
            entries.append((start, end, entry.weight))
    summarized = (
        summarize_size_class_weight_details(entries, ranges)
        if ranges else {"Unused": SizeClassWeightSummary(sum(weight for _, _, weight in entries))}
    )
    return {
        size_class: SizeClassWeightSummary(
            summarized.get(size_class, SizeClassWeightSummary(0)).total + direct_totals[size_class],
        )
        for size_class in STOCK_SIZE_CLASSES
    }


def _summary(total: float) -> SizeClassWeightSummary:
    return SizeClassWeightSummary(_number(total))


def _number(total: float) -> int | float:
    return int(total) if total.is_integer() else total


def _normalize_filter(value: str | None) -> str | None:
    normalized = str(value or "").strip().casefold()
    return None if normalized in {"", "all"} else normalized
