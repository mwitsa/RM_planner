"""Local persistence for extracted orders and editable production quantities."""

from __future__ import annotations

import json
import math
import re
from collections import Counter
from dataclasses import replace
from hashlib import sha256
from pathlib import Path
from typing import Iterable

from rm_planner.orders.extractor import ORDER_EXPORT_FIELDS, OrderRecord


STORE_VERSION = 8
ORDER_NUMBER_PREFIX = "ORD-"
ORDER_NUMBER_WIDTH = 6
ORDER_NUMBER_PATTERN = re.compile(r"^ORD-(\d+)$", re.IGNORECASE)


def save_order_records(store_path: str | Path, records: Iterable[OrderRecord]) -> Path:
    path = Path(store_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    record_list = list(records)
    _assign_missing_order_numbers(record_list)
    for record in record_list:
        _validate_production(record.production)
        if not record.record_id:
            raise ValueError("Every saved order must have an internal record ID.")
    payload = {
        "version": STORE_VERSION,
        "records": [
            {
                "record_id": record.record_id,
                "order_no": record.order_no,
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
        order_no = raw.get("order_no", "")
        if not isinstance(order_no, str):
            raise ValueError("Saved order number must be text.")
        production = raw.get("production")
        _validate_production(production)
        try:
            order_unit = _required_number(
                raw.get("order_unit", raw.get("order_volume")),
                "order quantity in units",
            )
            order_cups = _optional_number(raw.get("order_cups"), "order quantity in cups")
            cups_per_unit = _optional_number(raw.get("cups_per_unit"), "cups per unit")
            wontons_per_cup = _optional_number(
                raw.get("wontons_per_cup"),
                "ลูกเกี๊ยว per cup",
            )
            cups = _optional_number(raw.get("cups"), "cups")
            pcs_per_cup = _optional_number(
                raw.get("pcs_per_cup", wontons_per_cup), "Pcs./Cup"
            )
            wt_per_pcs = _optional_number(raw.get("wt_per_pcs"), "WT/Pcs")
            ho_weight_kg = _optional_number(
                raw.get("ho_weight_kg"),
                "น้ำหนัก HO (kg)",
            )
            if cups_per_unit is None and order_cups is not None and order_unit != 0:
                cups_per_unit = order_cups / order_unit
            records.append(
                OrderRecord(
                    date=str(raw["date"]),
                    month=str(raw["month"]),
                    year=str(raw["year"]),
                    prod_date=str(raw.get("prod_date", "")),
                    prod_month=str(raw.get("prod_month", "")),
                    prod_year=str(raw.get("prod_year", "")),
                    country=str(raw["country"]),
                    customer_name=str(raw["customer_name"]),
                    code=str(raw.get("code", "")),
                    group_1=str(raw["group_1"]),
                    group_2=str(raw["group_2"]),
                    packaging=str(raw["packaging"]),
                    rm_size=str(raw.get("rm_size", "")),
                    soup=str(raw["soup"]),
                    cups=cups,
                    pcs_per_cup=pcs_per_cup,
                    wt_per_pcs=wt_per_pcs,
                    wontons_per_cup=wontons_per_cup,
                    order_unit=order_unit,
                    order_cups=order_cups,
                    cups_per_unit=cups_per_unit,
                    ho_weight_kg=ho_weight_kg,
                    production=production,
                    record_id=record_id,
                    order_no=order_no.strip().upper(),
                )
            )
        except KeyError as exc:
            raise ValueError(f"Saved order is missing field: {exc.args[0]}") from exc
    _assign_missing_order_numbers(records)
    return records


def merge_order_records(
    store_path: str | Path,
    incoming_records: Iterable[OrderRecord],
) -> tuple[list[OrderRecord], int]:
    """Append records whose internal IDs are not already saved."""

    path = Path(store_path)
    incoming_list = list(incoming_records)
    merged = load_order_records(path)
    upgraded = _backfill_new_source_fields(merged, incoming_list)
    known_ids = {record.record_id for record in merged}
    existing_counts = Counter(_order_identity(record) for record in merged)
    incoming_counts: Counter[tuple[object, ...]] = Counter()
    added = 0
    for record in incoming_list:
        _validate_production(record.production)
        if not record.record_id:
            raise ValueError("Every imported order must have an internal record ID.")
        identity = _order_identity(record)
        incoming_counts[identity] += 1
        occurrence = incoming_counts[identity]
        if occurrence <= existing_counts[identity]:
            continue
        saved_record = replace(record, order_no="")
        if record.record_id in known_ids:
            saved_record = replace(
                saved_record,
                record_id=_unique_record_id(identity, occurrence, known_ids),
            )
        merged.append(saved_record)
        known_ids.add(saved_record.record_id)
        added += 1
    numbered = _assign_missing_order_numbers(merged)
    if added or upgraded or numbered:
        save_order_records(path, merged)
    return merged, added


def _order_identity(record: OrderRecord) -> tuple[object, ...]:
    """Content identity used for incremental imports; production is user-entered."""

    return (
        record.date,
        record.month,
        record.year,
        record.country.casefold(),
        record.customer_name.casefold(),
        record.group_1.casefold(),
        record.group_2.casefold(),
        record.packaging.casefold(),
        record.rm_size.casefold(),
        record.soup.casefold(),
        record.wontons_per_cup,
        record.order_unit,
        record.order_cups,
    )


def _backfill_new_source_fields(
    existing_records: list[OrderRecord],
    incoming_records: list[OrderRecord],
) -> int:
    """Upgrade older saved rows using matching stable source IDs."""

    incoming_by_id = {record.record_id: record for record in incoming_records}
    upgraded = 0
    for existing in existing_records:
        incoming = incoming_by_id.get(existing.record_id)
        if incoming is None or _order_identity_without_backfills(
            existing
        ) != _order_identity_without_backfills(incoming):
            continue
        changed = False
        if not existing.rm_size and incoming.rm_size:
            existing.rm_size = incoming.rm_size
            changed = True
        elif (
            existing.rm_size.strip().upper() == "S+"
            and incoming.rm_size.strip().upper() in {"S", "SS"}
        ):
            existing.rm_size = incoming.rm_size
            changed = True
        if not existing.code and incoming.code:
            existing.code = incoming.code
            changed = True
        if existing.wontons_per_cup is None and incoming.wontons_per_cup is not None:
            existing.wontons_per_cup = incoming.wontons_per_cup
            changed = True
        if existing.cups is None and incoming.cups is not None:
            existing.cups = incoming.cups
            changed = True
        if existing.pcs_per_cup is None and incoming.pcs_per_cup is not None:
            existing.pcs_per_cup = incoming.pcs_per_cup
            changed = True
        if existing.wt_per_pcs is None and incoming.wt_per_pcs is not None:
            existing.wt_per_pcs = incoming.wt_per_pcs
            changed = True
        if incoming.ho_weight_kg is not None and (
            existing.ho_weight_kg != incoming.ho_weight_kg
        ):
            existing.ho_weight_kg = incoming.ho_weight_kg
            changed = True
        if not existing.prod_date and not existing.prod_month and not existing.prod_year and (
            incoming.prod_date or incoming.prod_month or incoming.prod_year
        ):
            existing.prod_date = incoming.prod_date
            existing.prod_month = incoming.prod_month
            existing.prod_year = incoming.prod_year
            changed = True
        if changed:
            upgraded += 1
    return upgraded


def _order_identity_without_backfills(record: OrderRecord) -> tuple[object, ...]:
    identity = _order_identity(record)
    return (*identity[:8], identity[9], *identity[11:])


def _unique_record_id(
    identity: tuple[object, ...],
    occurrence: int,
    known_ids: set[str],
) -> str:
    digest = sha256(repr(identity).encode("utf-8")).hexdigest()[:20]
    candidate_number = occurrence
    while True:
        candidate = f"order:{digest}:{candidate_number}"
        if candidate not in known_ids:
            return candidate
        candidate_number += 1


def _required_number(value: object, label: str) -> int | float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"Saved {label} must be numeric.")
    numeric = float(value)
    if not math.isfinite(numeric):
        raise ValueError(f"Saved {label} must be finite.")
    return int(numeric) if numeric.is_integer() else numeric


def _optional_number(value: object, label: str) -> int | float | None:
    if value is None:
        return None
    return _required_number(value, label)


def _validate_production(value: object) -> None:
    if value is None:
        return
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("Production must be numeric or blank.")
    numeric = float(value)
    if not math.isfinite(numeric) or numeric < 0:
        raise ValueError("Production must be a finite number greater than or equal to zero.")


def _assign_missing_order_numbers(records: list[OrderRecord]) -> int:
    """Assign stable human-readable numbers without changing existing numbers."""

    seen: set[str] = set()
    highest_number = 0
    for record in records:
        order_no = record.order_no.strip().upper()
        if not order_no:
            continue
        if order_no in seen:
            raise ValueError(f"Saved orders contain duplicate Order No.: {order_no}")
        seen.add(order_no)
        match = ORDER_NUMBER_PATTERN.fullmatch(order_no)
        if match:
            highest_number = max(highest_number, int(match.group(1)))
        record.order_no = order_no

    assigned = 0
    next_number = highest_number + 1
    for record in records:
        if record.order_no.strip():
            continue
        while True:
            candidate = f"{ORDER_NUMBER_PREFIX}{next_number:0{ORDER_NUMBER_WIDTH}d}"
            next_number += 1
            if candidate not in seen:
                break
        record.order_no = candidate
        seen.add(candidate)
        assigned += 1
    return assigned
