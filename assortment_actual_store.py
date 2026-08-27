"""Persistent storage for dated actual shrimp assortment records."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Iterable
from uuid import uuid4


STORE_VERSION = 1


@dataclass(frozen=True, slots=True)
class ActualAssortmentEntry:
    size: str
    weight: float


@dataclass(frozen=True, slots=True)
class ActualAssortmentRecord:
    record_id: str
    record_date: str
    entries: tuple[ActualAssortmentEntry, ...]
    created_at: str
    updated_at: str

    @property
    def total_weight(self) -> float:
        return sum(entry.weight for entry in self.entries)


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
        created_at = raw_record.get("created_at")
        updated_at = raw_record.get("updated_at")
        if not all(isinstance(value, str) for value in (record_id, record_date, created_at, updated_at)):
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
                created_at=created_at,
                updated_at=updated_at,
            )
        )
    return records


def upsert_actual_record(
    store_path: str | Path,
    record_date: str,
    entries: Iterable[ActualAssortmentEntry],
    record_id: str | None = None,
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
        saved_record = ActualAssortmentRecord(
            record_id=str(uuid4()),
            record_date=record_date,
            entries=normalized_entries,
            created_at=now,
            updated_at=now,
        )
        records.append(saved_record)
    else:
        saved_record = None
        for index, existing in enumerate(records):
            if existing.record_id == record_id:
                saved_record = ActualAssortmentRecord(
                    record_id=record_id,
                    record_date=record_date,
                    entries=normalized_entries,
                    created_at=existing.created_at,
                    updated_at=now,
                )
                records[index] = saved_record
                break
        if saved_record is None:
            raise ValueError("The selected actual assortment history record no longer exists.")

    _write_records(path, records)
    return saved_record


def _validate_date(value: str) -> None:
    try:
        date.fromisoformat(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Invalid actual assortment date: {value}") from exc


def _validate_entry(entry: ActualAssortmentEntry) -> ActualAssortmentEntry:
    size = entry.size.strip()
    try:
        weight = float(entry.weight)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Invalid weight for size {size or '(blank)' }.") from exc
    if not size:
        raise ValueError("Every actual assortment entry must have a Size.")
    if weight <= 0:
        raise ValueError(f"Weight for size {size} must be greater than zero.")
    return ActualAssortmentEntry(size=size, weight=weight)


def _entry_from_json(raw_entry: object) -> ActualAssortmentEntry:
    if not isinstance(raw_entry, dict):
        raise ValueError("Actual assortment history contains an invalid Size/Weight entry.")
    return _validate_entry(
        ActualAssortmentEntry(
            size=str(raw_entry.get("size", "")),
            weight=raw_entry.get("weight", 0),
        )
    )


def _write_records(path: Path, records: list[ActualAssortmentRecord]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "version": STORE_VERSION,
        "records": [
            {
                "id": record.record_id,
                "date": record.record_date,
                "entries": [
                    {"size": entry.size, "weight": entry.weight}
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
