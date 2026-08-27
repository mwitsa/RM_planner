"""Local persistence for extracted orders and editable production quantities."""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Iterable

from extractor import ORDER_EXPORT_FIELDS, OrderRecord


STORE_VERSION = 1


def save_order_records(store_path: str | Path, records: Iterable[OrderRecord]) -> Path:
    path = Path(store_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    record_list = list(records)
    for record in record_list:
        _validate_production(record.production)
        if not record.record_id:
            raise ValueError("Every saved order must have an internal record ID.")
    payload = {
        "version": STORE_VERSION,
        "records": [
            {
                "record_id": record.record_id,
                **{field: getattr(record, field) for field in ORDER_EXPORT_FIELDS},
            }
            for record in record_list
        ],
    }
    temporary_path = path.with_suffix(f"{path.suffix}.tmp")
    try:
        with temporary_path.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
        temporary_path.replace(path)
    except OSError as exc:
        raise ValueError(f"Could not save orders: {exc}") from exc
    return path


def load_order_records(store_path: str | Path) -> list[OrderRecord]:
    path = Path(store_path)
    if not path.exists():
        return []
    try:
        with path.open(encoding="utf-8") as handle:
            payload = json.load(handle)
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Could not read saved orders: {exc}") from exc
    if not isinstance(payload, dict) or not isinstance(payload.get("records"), list):
        raise ValueError("Saved orders file has an invalid structure.")

    records: list[OrderRecord] = []
    seen_ids: set[str] = set()
    for raw in payload["records"]:
        if not isinstance(raw, dict):
            raise ValueError("Saved orders file contains an invalid order.")
        record_id = raw.get("record_id")
        if not isinstance(record_id, str) or not record_id or record_id in seen_ids:
            raise ValueError("Saved orders contain an invalid or duplicate record ID.")
        seen_ids.add(record_id)
        production = raw.get("production")
        _validate_production(production)
        try:
            records.append(
                OrderRecord(
                    date=str(raw["date"]),
                    month=str(raw["month"]),
                    year=str(raw["year"]),
                    country=str(raw["country"]),
                    customer_name=str(raw["customer_name"]),
                    group_1=str(raw["group_1"]),
                    group_2=str(raw["group_2"]),
                    packaging=str(raw["packaging"]),
                    soup=str(raw["soup"]),
                    order_volume=_required_number(raw.get("order_volume"), "order volume"),
                    production=production,
                    record_id=record_id,
                )
            )
        except KeyError as exc:
            raise ValueError(f"Saved order is missing field: {exc.args[0]}") from exc
    return records


def _required_number(value: object, label: str) -> int | float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"Saved {label} must be numeric.")
    numeric = float(value)
    if not math.isfinite(numeric):
        raise ValueError(f"Saved {label} must be finite.")
    return int(numeric) if numeric.is_integer() else numeric


def _validate_production(value: object) -> None:
    if value is None:
        return
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("Production must be numeric or blank.")
    numeric = float(value)
    if not math.isfinite(numeric) or numeric < 0:
        raise ValueError("Production must be a finite number greater than or equal to zero.")
