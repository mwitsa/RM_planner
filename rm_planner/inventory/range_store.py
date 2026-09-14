"""Persistence for M/S/SS output-size ranges used by Assortment STD."""

from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


STORE_VERSION = 3
SIZE_CLASSES = ("M", "S", "SS")
LEGACY_SIZE_CLASSES = ("M", "S+")


@dataclass(frozen=True, slots=True)
class AssortmentSizeRange:
    size_class: str
    start_size: str
    end_size: str


@dataclass(frozen=True, slots=True)
class SizeClassWeightSummary:
    total: int | float


def normalize_size_class(value: object) -> str:
    """Return the current RM class, mapping legacy combined S+ stock to S."""

    normalized = str(value or "").strip().upper()
    if normalized == "S+":
        return "S"
    if normalized in {"M", "S", "SS"}:
        return normalized
    if normalized == "UNUSED":
        return "Unused"
    return normalized


def classify_size_range(
    size_start: str | int | float,
    size_end: str | int | float,
    ranges: Iterable[AssortmentSizeRange],
) -> tuple[str, ...]:
    """Return one matching M/S/SS class, or Unused when none/ambiguous."""

    actual_start = _parse_size_number(size_start)
    actual_end = _parse_size_number(size_end)
    if actual_start > actual_end:
        raise ValueError("Size (start) must not be greater than Size (end).")

    matches: list[str] = []
    for size_range in ranges:
        if size_range.size_class not in SIZE_CLASSES:
            raise ValueError(f"Invalid assortment size class: {size_range.size_class}")
        class_start, _unused = _parse_output_range(size_range.start_size)
        _unused, class_end = _parse_output_range(size_range.end_size)
        if actual_start <= class_end and actual_end >= class_start:
            matches.append(size_range.size_class)
    return (matches[0],) if len(matches) == 1 else ("Unused",)


def summarize_size_class_weights(
    entries: Iterable[tuple[str | int | float, str | int | float, int | float]],
    ranges: Iterable[AssortmentSizeRange],
) -> dict[str, int | float]:
    """Sum weights into one class per entry."""

    return {
        size_class: summary.total
        for size_class, summary in summarize_size_class_weight_details(entries, ranges).items()
    }


def summarize_size_class_weight_details(
    entries: Iterable[tuple[str | int | float, str | int | float, int | float]],
    ranges: Iterable[AssortmentSizeRange],
) -> dict[str, SizeClassWeightSummary]:
    """Return per-class totals without sharing weight between classes."""

    range_list = tuple(ranges)
    totals: dict[str, float] = {**{size_class: 0.0 for size_class in SIZE_CLASSES}, "Unused": 0.0}
    for size_start, size_end, weight in entries:
        if isinstance(weight, bool):
            raise ValueError("Assortment weight must be numeric.")
        try:
            numeric_weight = float(weight)
        except (TypeError, ValueError) as exc:
            raise ValueError("Assortment weight must be numeric.") from exc
        if not math.isfinite(numeric_weight) or numeric_weight < 0:
            raise ValueError("Assortment weight must be zero or greater.")
        try:
            classes = classify_size_range(size_start, size_end, range_list)
        except ValueError:
            classes = ("Unused",)
        for size_class in classes:
            totals[size_class] += numeric_weight
    return {
        size_class: SizeClassWeightSummary(
            total=int(total) if total.is_integer() else total,
        )
        for size_class, total in totals.items()
    }


def default_size_ranges(output_sizes: Iterable[str]) -> tuple[AssortmentSizeRange, ...]:
    sizes = tuple(output_sizes)
    if not sizes:
        raise ValueError("At least one output size is required to create size ranges.")

    ranges: list[AssortmentSizeRange] = []
    for index, size_class in enumerate(SIZE_CLASSES):
        start_index = min(index * len(sizes) // len(SIZE_CLASSES), len(sizes) - 1)
        if index == len(SIZE_CLASSES) - 1:
            end_index = len(sizes) - 1
        else:
            end_index = max(
                start_index,
                min((index + 1) * len(sizes) // len(SIZE_CLASSES) - 1, len(sizes) - 1),
            )
        ranges.append(
            AssortmentSizeRange(size_class, sizes[start_index], sizes[end_index])
        )
    return tuple(ranges)


def load_size_ranges(
    store_path: str | Path,
    output_sizes: Iterable[str],
) -> tuple[AssortmentSizeRange, ...]:
    path = Path(store_path)
    sizes = tuple(output_sizes)
    if not path.exists():
        return default_size_ranges(sizes)
    try:
        with path.open(encoding="utf-8") as handle:
            payload = json.load(handle)
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Could not read assortment size ranges: {exc}") from exc
    if not isinstance(payload, dict) or not isinstance(payload.get("ranges"), list):
        raise ValueError("Assortment size range file has an invalid structure.")

    raw_ranges: list[AssortmentSizeRange] = []
    for raw in payload["ranges"]:
        if not isinstance(raw, dict):
            raise ValueError("Assortment size range file contains an invalid range.")
        size_range = AssortmentSizeRange(
            str(raw.get("size_class", "")),
            str(raw.get("start_size", "")),
            str(raw.get("end_size", "")),
        )
        _validate_range_bounds(size_range, sizes)
        if any(item.size_class == size_range.size_class for item in raw_ranges):
            raise ValueError(f"Duplicate assortment size class: {size_range.size_class}")
        raw_ranges.append(size_range)

    parsed = {item.size_class: item for item in raw_ranges}
    # A former S+ range has no known S/SS boundary.  Split it into two adjacent
    # ranges so the user can immediately see and adjust the provisional boundary.
    if set(parsed) == set(LEGACY_SIZE_CLASSES):
        legacy_small = parsed["S+"]
        start = sizes.index(legacy_small.start_size)
        end = sizes.index(legacy_small.end_size)
        midpoint = start + (end - start) // 2
        parsed = {
            "M": parsed["M"],
            "S": AssortmentSizeRange("S", sizes[start], sizes[midpoint]),
            "SS": AssortmentSizeRange("SS", sizes[min(midpoint + 1, end)], sizes[end]),
        }
    if set(parsed) != set(SIZE_CLASSES):
        raise ValueError("Assortment size ranges must contain M, S, and SS.")
    for size_range in parsed.values():
        _validate_range(size_range, sizes)
    ordered = tuple(parsed[size_class] for size_class in SIZE_CLASSES)
    _validate_non_overlapping_ranges(ordered, sizes)
    return ordered


def save_size_ranges(
    store_path: str | Path,
    ranges: Iterable[AssortmentSizeRange],
    output_sizes: Iterable[str],
) -> Path:
    path = Path(store_path)
    sizes = tuple(output_sizes)
    range_list = tuple(ranges)
    for size_range in range_list:
        _validate_range(size_range, sizes)
    if tuple(size_range.size_class for size_range in range_list) != SIZE_CLASSES:
        raise ValueError("Assortment size ranges must be ordered M, S, and SS.")
    _validate_non_overlapping_ranges(range_list, sizes)

    payload = {
        "version": STORE_VERSION,
        "ranges": [
            {
                "size_class": size_range.size_class,
                "start_size": size_range.start_size,
                "end_size": size_range.end_size,
            }
            for size_range in range_list
        ],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = path.with_suffix(f"{path.suffix}.tmp")
    try:
        with temporary_path.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
        temporary_path.replace(path)
    except OSError as exc:
        raise ValueError(f"Could not save assortment size ranges: {exc}") from exc
    return path


def _validate_range(size_range: AssortmentSizeRange, output_sizes: tuple[str, ...]) -> None:
    if size_range.size_class not in SIZE_CLASSES:
        raise ValueError(f"Invalid assortment size class: {size_range.size_class}")
    _validate_range_bounds(size_range, output_sizes)


def _validate_range_bounds(
    size_range: AssortmentSizeRange,
    output_sizes: tuple[str, ...],
) -> None:
    try:
        start_index = output_sizes.index(size_range.start_size)
        end_index = output_sizes.index(size_range.end_size)
    except ValueError as exc:
        raise ValueError(
            f"{size_range.size_class} range references a size not found in the assortment master."
        ) from exc
    if start_index > end_index:
        raise ValueError(f"{size_range.size_class} range start must not be after its end.")


def _validate_non_overlapping_ranges(
    ranges: tuple[AssortmentSizeRange, ...],
    output_sizes: tuple[str, ...],
) -> None:
    occupied_rows: set[int] = set()
    for size_range in ranges:
        start_index = output_sizes.index(size_range.start_size)
        end_index = output_sizes.index(size_range.end_size)
        rows = set(range(start_index, end_index + 1))
        if occupied_rows.intersection(rows):
            raise ValueError("M, S, and SS assortment ranges must not overlap.")
        occupied_rows.update(rows)


def _parse_size_number(value: str | int | float) -> float:
    if isinstance(value, bool):
        raise ValueError("Size values must be numeric.")
    try:
        numeric = float(str(value).strip())
    except ValueError as exc:
        raise ValueError("Size values must be numeric.") from exc
    if not math.isfinite(numeric):
        raise ValueError("Size values must be finite numbers.")
    return numeric


def _parse_output_range(value: str) -> tuple[float, float]:
    match = re.fullmatch(
        r"\s*(-?\d+(?:\.\d+)?)\s*[-–—]\s*(-?\d+(?:\.\d+)?)\s*",
        str(value),
    )
    if not match:
        raise ValueError(f"Invalid assortment output-size range: {value}")
    start, end = float(match.group(1)), float(match.group(2))
    if start > end:
        raise ValueError(f"Invalid assortment output-size range: {value}")
    return start, end
