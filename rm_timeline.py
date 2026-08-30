"""RM arrival timeline and cumulative stock calculations."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from assortment_actual_store import (
    ActualAssortmentRecord,
    estimate_wonton_pieces,
    split_size_range,
)
from assortment_range_store import (
    AssortmentSizeRange,
    SIZE_CLASSES,
    SizeClassWeightSummary,
    normalize_size_class,
    summarize_size_class_weight_details,
)


@dataclass(frozen=True, slots=True)
class RmTimelineRow:
    record_date: str
    rm_ids: tuple[str, ...]
    actual_in_kg: float
    prediction_in_kg: float
    existing_in_kg: float
    incoming_kg: float
    cumulative_kg: float
    m_stock: SizeClassWeightSummary
    s_plus_stock: SizeClassWeightSummary
    unused_stock: SizeClassWeightSummary
    incoming_wontons: float
    cumulative_wontons: float


def build_rm_timeline(
    records: Iterable[ActualAssortmentRecord],
    ranges: Iterable[AssortmentSizeRange],
    record_type: str | None = None,
    market_type: str | None = None,
) -> tuple[RmTimelineRow, ...]:
    """Group filtered RM arrivals by date and return cumulative stock rows."""

    range_list = tuple(ranges)
    normalized_type = _normalize_filter(record_type)
    normalized_market = _normalize_filter(market_type)
    filtered = [
        record
        for record in records
        if (normalized_type is None or record.record_type == normalized_type)
        and (normalized_market is None or record.market_type == normalized_market)
    ]
    by_date: dict[str, list[ActualAssortmentRecord]] = {}
    for record in filtered:
        by_date.setdefault(record.record_date, []).append(record)

    cumulative_kg = 0.0
    cumulative_wontons = 0.0
    summary_classes = (*SIZE_CLASSES, "Unused")
    cumulative_totals = {key: 0.0 for key in summary_classes}
    cumulative_overlaps = {key: 0.0 for key in summary_classes}
    rows: list[RmTimelineRow] = []
    for record_date in sorted(by_date):
        dated_records = sorted(by_date[record_date], key=lambda item: item.rm_id)
        incoming_kg = sum(record.total_weight for record in dated_records)
        incoming_wontons = sum(
            float(estimate_wonton_pieces(record.entries)) for record in dated_records
        )
        actual_in = sum(
            record.total_weight for record in dated_records if record.record_type == "actual"
        )
        prediction_in = sum(
            record.total_weight
            for record in dated_records
            if record.record_type == "prediction"
        )
        existing_in = sum(
            record.total_weight
            for record in dated_records
            if record.record_type == "existing"
        )
        daily_summaries = _summarize_records(dated_records, range_list)
        cumulative_kg += incoming_kg
        cumulative_wontons += incoming_wontons
        for size_class, summary in daily_summaries.items():
            cumulative_totals[size_class] += float(summary.total)
            cumulative_overlaps[size_class] += float(summary.overlap)

        rows.append(
            RmTimelineRow(
                record_date=record_date,
                rm_ids=tuple(record.rm_id for record in dated_records),
                actual_in_kg=actual_in,
                prediction_in_kg=prediction_in,
                existing_in_kg=existing_in,
                incoming_kg=incoming_kg,
                cumulative_kg=cumulative_kg,
                m_stock=_summary(cumulative_totals["M"], cumulative_overlaps["M"]),
                s_plus_stock=_summary(
                    cumulative_totals["S+"], cumulative_overlaps["S+"]
                ),
                unused_stock=_summary(
                    cumulative_totals["Unused"], cumulative_overlaps["Unused"]
                ),
                incoming_wontons=incoming_wontons,
                cumulative_wontons=cumulative_wontons,
            )
        )
    return tuple(rows)


def _summarize_records(
    records: Iterable[ActualAssortmentRecord],
    ranges: tuple[AssortmentSizeRange, ...],
) -> dict[str, SizeClassWeightSummary]:
    if not ranges:
        total = sum(record.total_weight for record in records)
        return {
            "M": SizeClassWeightSummary(0, 0),
            "S+": SizeClassWeightSummary(0, 0),
            "Unused": SizeClassWeightSummary(total, 0),
        }
    entries: list[tuple[str, str, float]] = []
    direct_totals = {key: 0.0 for key in SIZE_CLASSES}
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
            summarized[size_class].overlap,
        )
        for size_class in (*SIZE_CLASSES, "Unused")
    }


def _summary(total: float, overlap: float) -> SizeClassWeightSummary:
    return SizeClassWeightSummary(
        int(total) if total.is_integer() else total,
        int(overlap) if overlap.is_integer() else overlap,
    )


def _normalize_filter(value: str | None) -> str | None:
    normalized = str(value or "").strip().casefold()
    return None if normalized in {"", "all"} else normalized
