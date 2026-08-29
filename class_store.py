"""Persistent master data for user-defined production classes."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable
from uuid import uuid4

from extractor import OrderRecord


STORE_VERSION = 2
ALL_CLASS_FILTER = "All"
BLANK_CLASS_FILTER = "(blank)"
ORDER_CLASS_FIELDS = (
    ("Country", "country"),
    ("Customer", "customer_name"),
    ("Group 1", "group_1"),
    ("Group 2", "group_2"),
    ("Packaging", "packaging"),
    ("Soup", "soup"),
)


@dataclass(frozen=True, slots=True)
class ClassDefinition:
    class_id: str
    class_value: str
    name: str
    group: str
    created_at: str
    updated_at: str


def load_class_definitions(store_path: str | Path) -> list[ClassDefinition]:
    path = Path(store_path)
    if not path.exists():
        return []
    try:
        with path.open(encoding="utf-8") as handle:
            payload = json.load(handle)
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Could not read saved classes: {exc}") from exc
    if not isinstance(payload, dict) or not isinstance(payload.get("classes"), list):
        raise ValueError("Saved class file has an invalid structure.")

    definitions: list[ClassDefinition] = []
    seen_ids: set[str] = set()
    seen_class_names: set[tuple[str, str]] = set()
    for raw in payload["classes"]:
        if not isinstance(raw, dict):
            raise ValueError("Saved class file contains an invalid class.")
        group = raw.get("group", raw.get("define", ""))
        values = (
            raw.get("id"),
            raw.get("class"),
            raw.get("name"),
            group,
            raw.get("created_at"),
            raw.get("updated_at"),
        )
        if not all(isinstance(value, str) for value in values):
            raise ValueError("Saved class file contains invalid class fields.")
        class_id, class_value, name, group, created_at, updated_at = values
        normalized_key = (class_value.strip().casefold(), name.strip().casefold())
        if (
            not class_id
            or class_id in seen_ids
            or not normalized_key[0]
            or not normalized_key[1]
            or normalized_key in seen_class_names
        ):
            raise ValueError("Saved classes contain a blank or duplicate Class + Name pair.")
        seen_ids.add(class_id)
        seen_class_names.add(normalized_key)
        definitions.append(
            ClassDefinition(
                class_id=class_id,
                class_value=class_value.strip(),
                name=name.strip(),
                group=group.strip(),
                created_at=created_at,
                updated_at=updated_at,
            )
        )
    return definitions


def upsert_class_definition(
    store_path: str | Path,
    class_value: str,
    name: str,
    group: str = "",
    class_id: str | None = None,
) -> ClassDefinition:
    path = Path(store_path)
    class_value = class_value.strip()
    name = name.strip()
    group = group.strip()
    if not class_value or not name:
        raise ValueError("Class and Name are required.")

    definitions = load_class_definitions(path)
    normalized_key = (class_value.casefold(), name.casefold())
    for existing in definitions:
        existing_key = (existing.class_value.casefold(), existing.name.casefold())
        if existing_key == normalized_key and existing.class_id != class_id:
            raise ValueError(f"Class and Name already exist: {class_value} / {name}")

    now = datetime.now(timezone.utc).isoformat()
    if class_id is None:
        saved = ClassDefinition(
            class_id=str(uuid4()),
            class_value=class_value,
            name=name,
            group=group,
            created_at=now,
            updated_at=now,
        )
        definitions.append(saved)
    else:
        saved = None
        for index, existing in enumerate(definitions):
            if existing.class_id == class_id:
                saved = ClassDefinition(
                    class_id=class_id,
                    class_value=class_value,
                    name=name,
                    group=group,
                    created_at=existing.created_at,
                    updated_at=now,
                )
                definitions[index] = saved
                break
        if saved is None:
            raise ValueError("The selected saved class no longer exists.")

    _write_definitions(path, definitions)
    return saved


def add_missing_class_definitions(
    store_path: str | Path,
    class_names: Iterable[tuple[str, str]],
) -> int:
    """Add missing Class + Name pairs with a blank Group in one atomic write."""

    path = Path(store_path)
    definitions = load_class_definitions(path)
    existing_keys = {
        (item.class_value.casefold(), item.name.casefold()) for item in definitions
    }
    now = datetime.now(timezone.utc).isoformat()
    added = 0
    for raw_class, raw_name in class_names:
        class_value = raw_class.strip()
        name = raw_name.strip()
        if not class_value or not name:
            continue
        key = (class_value.casefold(), name.casefold())
        if key in existing_keys:
            continue
        definitions.append(
            ClassDefinition(
                class_id=str(uuid4()),
                class_value=class_value,
                name=name,
                group="",
                created_at=now,
                updated_at=now,
            )
        )
        existing_keys.add(key)
        added += 1

    if added:
        _write_definitions(path, definitions)
    return added


def order_class_names(records: Iterable[OrderRecord]) -> tuple[tuple[str, str], ...]:
    """Return unique Class + Name pairs represented by extracted orders."""

    record_list = tuple(records)
    pairs: list[tuple[str, str]] = []
    for class_value, attribute in ORDER_CLASS_FIELDS:
        names_by_key: dict[str, str] = {}
        for record in record_list:
            name = str(getattr(record, attribute)).strip()
            if name:
                names_by_key.setdefault(name.casefold(), name)
        pairs.extend(
            (class_value, name)
            for name in sorted(names_by_key.values(), key=str.casefold)
        )

    ratios = {
        f"{record.cups_per_unit:.6f}".rstrip("0").rstrip(".")
        for record in record_list
        if record.cups_per_unit is not None
    }
    pairs.extend(("ถ้วย/Unit", ratio) for ratio in sorted(ratios, key=float))
    return tuple(pairs)


def filter_class_definitions(
    definitions: Iterable[ClassDefinition],
    class_filter: str = ALL_CLASS_FILTER,
    name_search: str = "",
    group_filter: str = ALL_CLASS_FILTER,
) -> list[ClassDefinition]:
    """Filter class master rows by Class, partial Name, and Group."""

    normalized_search = name_search.strip().casefold()
    return [
        item
        for item in definitions
        if (
            (class_filter == ALL_CLASS_FILTER or item.class_value == class_filter)
            and (not normalized_search or normalized_search in item.name.casefold())
            and (
                group_filter == ALL_CLASS_FILTER
                or (group_filter == BLANK_CLASS_FILTER and not item.group)
                or item.group == group_filter
            )
        )
    ]


def class_filter_options(
    definitions: Iterable[ClassDefinition],
    field: str,
) -> list[str]:
    """Return sorted options for the Class or Group dropdown."""

    if field == "class":
        values = {item.class_value for item in definitions}
    elif field == "group":
        values = {item.group or BLANK_CLASS_FILTER for item in definitions}
    else:
        raise ValueError(f"Unknown class filter field: {field}")
    return sorted(
        values,
        key=lambda value: (value == BLANK_CLASS_FILTER, value.casefold()),
    )


def _write_definitions(path: Path, definitions: list[ClassDefinition]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "version": STORE_VERSION,
        "classes": [
            {
                "id": item.class_id,
                "class": item.class_value,
                "name": item.name,
                "group": item.group,
                "created_at": item.created_at,
                "updated_at": item.updated_at,
            }
            for item in definitions
        ],
    }
    temporary_path = path.with_suffix(f"{path.suffix}.tmp")
    try:
        with temporary_path.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
        temporary_path.replace(path)
    except OSError as exc:
        raise ValueError(f"Could not save class definitions: {exc}") from exc
