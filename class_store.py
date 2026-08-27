"""Persistent master data for user-defined production classes."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4


STORE_VERSION = 1


@dataclass(frozen=True, slots=True)
class ClassDefinition:
    class_id: str
    class_value: str
    name: str
    definition: str
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
    seen_classes: set[str] = set()
    for raw in payload["classes"]:
        if not isinstance(raw, dict):
            raise ValueError("Saved class file contains an invalid class.")
        values = (
            raw.get("id"),
            raw.get("class"),
            raw.get("name"),
            raw.get("define"),
            raw.get("created_at"),
            raw.get("updated_at"),
        )
        if not all(isinstance(value, str) for value in values):
            raise ValueError("Saved class file contains invalid class fields.")
        class_id, class_value, name, definition, created_at, updated_at = values
        normalized_key = class_value.strip().casefold()
        if not class_id or class_id in seen_ids or not normalized_key or normalized_key in seen_classes:
            raise ValueError("Saved classes contain a blank or duplicate Class value.")
        if not name.strip() or not definition.strip():
            raise ValueError("Every saved class must have Class, Name, and Define values.")
        seen_ids.add(class_id)
        seen_classes.add(normalized_key)
        definitions.append(
            ClassDefinition(
                class_id=class_id,
                class_value=class_value.strip(),
                name=name.strip(),
                definition=definition.strip(),
                created_at=created_at,
                updated_at=updated_at,
            )
        )
    return definitions


def upsert_class_definition(
    store_path: str | Path,
    class_value: str,
    name: str,
    definition: str,
    class_id: str | None = None,
) -> ClassDefinition:
    path = Path(store_path)
    class_value = class_value.strip()
    name = name.strip()
    definition = definition.strip()
    if not class_value or not name or not definition:
        raise ValueError("Class, Name, and Define are all required.")

    definitions = load_class_definitions(path)
    normalized_key = class_value.casefold()
    for existing in definitions:
        if existing.class_value.casefold() == normalized_key and existing.class_id != class_id:
            raise ValueError(f"Class already exists: {class_value}")

    now = datetime.now(timezone.utc).isoformat()
    if class_id is None:
        saved = ClassDefinition(
            class_id=str(uuid4()),
            class_value=class_value,
            name=name,
            definition=definition,
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
                    definition=definition,
                    created_at=existing.created_at,
                    updated_at=now,
                )
                definitions[index] = saved
                break
        if saved is None:
            raise ValueError("The selected saved class no longer exists.")

    _write_definitions(path, definitions)
    return saved


def _write_definitions(path: Path, definitions: list[ClassDefinition]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "version": STORE_VERSION,
        "classes": [
            {
                "id": item.class_id,
                "class": item.class_value,
                "name": item.name,
                "define": item.definition,
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
