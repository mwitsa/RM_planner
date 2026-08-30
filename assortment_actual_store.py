"""Persistent storage for dated actual shrimp assortment records."""

from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass, replace
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Iterable
from uuid import uuid4

from assortment_range_store import SIZE_CLASSES, normalize_size_class
from market_labels import market_internal_value


STORE_VERSION = 5
RECORD_TYPES = {"actual", "prediction", "existing"}
RM_ID_PREFIX = "RM-"
RM_ID_WIDTH = 6
RM_ID_PATTERN = re.compile(r"^RM-(\d+)$", re.IGNORECASE)


@dataclass(frozen=True, slots=True)
class ActualAssortmentEntry:
    size: str
    weight: float
    size_class: str = ""
    pieces_per_kg: float | None = None


@dataclass(frozen=True, slots=True)
class ActualAssortmentRecord:
    record_id: str
    record_date: str
    entries: tuple[ActualAssortmentEntry, ...]
    record_type: str
    created_at: str
    updated_at: str
    market_type: str = "unassigned"
    rm_id: str = ""

    @property
    def total_weight(self) -> float:
        return sum(entry.weight for entry in self.entries)


def split_size_range(size: str) -> tuple[str, str]:
    """Split a stored size such as 51-55 into start and end UI values."""

    normalized = str(size).strip()
    parts = re.split(r"\s*[-–—]\s*", normalized, maxsplit=1)
    if len(parts) == 2:
        return parts[0].strip(), parts[1].strip()
    return normalized, ""


def combine_size_range(size_start: str, size_end: str) -> str:
    """Combine the two size inputs into the existing stored range format."""

    start = str(size_start).strip()
    end = str(size_end).strip()
    if not start or not end:
        raise ValueError("Both Size (start) and Size (end) are required.")
    return f"{start}-{end}"


def estimate_wonton_pieces(entries: Iterable[ActualAssortmentEntry]) -> int | float:
    """Estimate one-shrimp wontons from physical RM size ranges and kg weights."""

    total = 0.0
    for entry in entries:
        try:
            weight = float(entry.weight)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"Cannot estimate wontons for RM size {entry.size}.") from exc
        if entry.pieces_per_kg is not None:
            try:
                pieces_per_kg = float(entry.pieces_per_kg)
            except (TypeError, ValueError) as exc:
                raise ValueError(f"Cannot estimate wontons for RM size {entry.size}.") from exc
            if (
                not all(math.isfinite(value) for value in (pieces_per_kg, weight))
                or pieces_per_kg <= 0
                or weight < 0
            ):
                raise ValueError(f"Cannot estimate wontons for RM size {entry.size}.")
            total += weight * pieces_per_kg
            continue
        size_start, size_end = split_size_range(entry.size)
        try:
            start = float(size_start)
            end = float(size_end)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"Cannot estimate wontons for RM size {entry.size}.") from exc
        if (
            not all(math.isfinite(value) for value in (start, end, weight))
            or start <= 0
            or end <= 0
            or start > end
            or weight < 0
        ):
            raise ValueError(f"Cannot estimate wontons for RM size {entry.size}.")
        total += weight * ((start + end) / 2)
    return int(total) if total.is_integer() else total


def load_actual_records(store_path: str | Path) -> list[ActualAssortmentRecord]:
    path = Path(store_path)
    if not path.exists():
        return []
    try:
        with path.open(encoding="utf-8") as handle:
            payload = json.load(handle)
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Could not read actual assortment history: {exc}") from exc

    if not isinstance(payload, dict) or not isinstance(payload.get("records"), list):
        raise ValueError("Actual assortment history has an invalid structure.")

    records: list[ActualAssortmentRecord] = []
    seen_ids: set[str] = set()
    for raw_record in payload["records"]:
        if not isinstance(raw_record, dict):
            raise ValueError("Actual assortment history contains an invalid record.")
        record_id = raw_record.get("id")
        record_date = raw_record.get("date")
        raw_entries = raw_record.get("entries")
        record_type = _normalize_record_type(raw_record.get("record_type", "actual"))
        market_type = _normalize_market_type(raw_record.get("market_type", "unassigned"))
        rm_id = raw_record.get("rm_id", "")
        created_at = raw_record.get("created_at")
        updated_at = raw_record.get("updated_at")
        if not all(
            isinstance(value, str)
            for value in (record_id, record_date, created_at, updated_at, rm_id)
        ):
            raise ValueError("Actual assortment history contains invalid record metadata.")
        if record_id in seen_ids:
            raise ValueError("Actual assortment history contains duplicate record IDs.")
        seen_ids.add(record_id)
        _validate_date(record_date)
        if not isinstance(raw_entries, list) or not raw_entries:
            raise ValueError("Every saved actual assortment record must contain at least one entry.")
        entries = tuple(_entry_from_json(entry) for entry in raw_entries)
        records.append(
            ActualAssortmentRecord(
                record_id=record_id,
                record_date=record_date,
                entries=entries,
                record_type=record_type,
                created_at=created_at,
                updated_at=updated_at,
                market_type=market_type,
                rm_id=rm_id.strip().upper(),
            )
        )
    return _assign_missing_rm_ids(records)


def upsert_actual_record(
    store_path: str | Path,
    record_date: str,
    entries: Iterable[ActualAssortmentEntry],
    record_id: str | None = None,
    record_type: str | None = None,
    market_type: str | None = None,
) -> ActualAssortmentRecord:
    """Create a new history record or update an existing record by ID."""

    path = Path(store_path)
    _validate_date(record_date)
    normalized_entries = tuple(_validate_entry(entry) for entry in entries)
    if not normalized_entries:
        raise ValueError("Add at least one Size and Weight entry before saving.")

    records = load_actual_records(path)
    now = datetime.now(timezone.utc).isoformat()
    if record_id is None:
        saved_record_type = _normalize_record_type(record_type or "actual")
        saved_market_type = _normalize_market_type(market_type or "unassigned")
        saved_record = ActualAssortmentRecord(
            record_id=str(uuid4()),
            record_date=record_date,
            entries=normalized_entries,
            record_type=saved_record_type,
            created_at=now,
            updated_at=now,
            market_type=saved_market_type,
            rm_id=_next_rm_id(records),
        )
        records.append(saved_record)
    else:
        saved_record = None
        for index, existing in enumerate(records):
            if existing.record_id == record_id:
                saved_record_type = (
                    existing.record_type
                    if record_type is None
                    else _normalize_record_type(record_type)
                )
                saved_market_type = (
                    existing.market_type
                    if market_type is None
                    else _normalize_market_type(market_type)
                )
                saved_record = ActualAssortmentRecord(
                    record_id=record_id,
                    record_date=record_date,
                    entries=normalized_entries,
                    record_type=saved_record_type,
                    created_at=existing.created_at,
                    updated_at=now,
                    market_type=saved_market_type,
                    rm_id=existing.rm_id,
                )
                records[index] = saved_record
                break
        if saved_record is None:
            raise ValueError("The selected actual assortment history record no longer exists.")

    _write_records(path, records)
    return saved_record


def delete_actual_record(
    store_path: str | Path,
    record_id: str,
) -> ActualAssortmentRecord:
    """Permanently remove one saved assortment-history record by ID."""

    path = Path(store_path)
    records = load_actual_records(path)
    for index, record in enumerate(records):
        if record.record_id == record_id:
            deleted = records.pop(index)
            _write_records(path, records)
            return deleted
    raise ValueError("The selected actual assortment history record no longer exists.")


def _validate_date(value: str) -> None:
    try:
        date.fromisoformat(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Invalid actual assortment date: {value}") from exc


def _normalize_record_type(value: object) -> str:
    record_type = str(value).strip().casefold()
    if record_type not in RECORD_TYPES:
        raise ValueError("RM record type must be actual, prediction, or existing.")
    return record_type


def _normalize_market_type(value: object) -> str:
    return market_internal_value(value, allow_unassigned=True)


def _validate_entry(entry: ActualAssortmentEntry) -> ActualAssortmentEntry:
    size = entry.size.strip()
    size_class = normalize_size_class(entry.size_class)
    try:
        weight = float(entry.weight)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Invalid weight for size {size or '(blank)' }.") from exc
    if not size:
        raise ValueError("Every actual assortment entry must have a Size.")
    if weight <= 0:
        raise ValueError(f"Weight for size {size} must be greater than zero.")
    pieces_per_kg = entry.pieces_per_kg
    if size_class or pieces_per_kg is not None:
        if size_class not in SIZE_CLASSES:
            raise ValueError("Existing stock Size class must be M or S+.")
        try:
            pieces_per_kg = float(pieces_per_kg)
        except (TypeError, ValueError) as exc:
            raise ValueError(
                f"Existing {size_class} stock needs a valid average pieces/kg value."
            ) from exc
        if not math.isfinite(pieces_per_kg) or pieces_per_kg <= 0:
            raise ValueError(
                f"Existing {size_class} stock pieces/kg must be greater than zero."
            )
    return ActualAssortmentEntry(
        size=size,
        weight=weight,
        size_class=size_class,
        pieces_per_kg=pieces_per_kg,
    )


def _entry_from_json(raw_entry: object) -> ActualAssortmentEntry:
    if not isinstance(raw_entry, dict):
        raise ValueError("Actual assortment history contains an invalid Size/Weight entry.")
    return _validate_entry(
        ActualAssortmentEntry(
            size=str(raw_entry.get("size", "")),
            weight=raw_entry.get("weight", 0),
            size_class=str(raw_entry.get("size_class", "")),
            pieces_per_kg=raw_entry.get("pieces_per_kg"),
        )
    )


def _write_records(path: Path, records: list[ActualAssortmentRecord]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    records = _assign_missing_rm_ids(records)
    payload = {
        "version": STORE_VERSION,
        "records": [
            {
                "id": record.record_id,
                "rm_id": record.rm_id,
                "date": record.record_date,
                "record_type": record.record_type,
                "market_type": record.market_type,
                "entries": [
                    {
                        "size": entry.size,
                        "weight": entry.weight,
                        **(
                            {
                                "size_class": entry.size_class,
                                "pieces_per_kg": entry.pieces_per_kg,
                            }
                            if entry.size_class
                            else {}
                        ),
                    }
                    for entry in record.entries
                ],
                "created_at": record.created_at,
                "updated_at": record.updated_at,
            }
            for record in records
        ],
    }
    temporary_path = path.with_suffix(f"{path.suffix}.tmp")
    try:
        with temporary_path.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
        temporary_path.replace(path)
    except OSError as exc:
        raise ValueError(f"Could not save actual assortment history: {exc}") from exc


def _assign_missing_rm_ids(
    records: list[ActualAssortmentRecord],
) -> list[ActualAssortmentRecord]:
    seen: set[str] = set()
    highest = 0
    for record in records:
        rm_id = record.rm_id.strip().upper()
        if not rm_id:
            continue
        if rm_id in seen:
            raise ValueError(f"Actual assortment history contains duplicate RM ID: {rm_id}")
        seen.add(rm_id)
        match = RM_ID_PATTERN.fullmatch(rm_id)
        if match:
            highest = max(highest, int(match.group(1)))

    assigned_records: list[ActualAssortmentRecord] = []
    next_number = highest + 1
    for record in records:
        rm_id = record.rm_id.strip().upper()
        if not rm_id:
            while True:
                rm_id = f"{RM_ID_PREFIX}{next_number:0{RM_ID_WIDTH}d}"
                next_number += 1
                if rm_id not in seen:
                    break
        seen.add(rm_id)
        assigned_records.append(replace(record, rm_id=rm_id))
    return assigned_records


def _next_rm_id(records: list[ActualAssortmentRecord]) -> str:
    highest = 0
    existing = {record.rm_id.strip().upper() for record in records if record.rm_id.strip()}
    for rm_id in existing:
        match = RM_ID_PATTERN.fullmatch(rm_id)
        if match:
            highest = max(highest, int(match.group(1)))
    next_number = highest + 1
    while True:
        candidate = f"{RM_ID_PREFIX}{next_number:0{RM_ID_WIDTH}d}"
        if candidate not in existing:
            return candidate
        next_number += 1
