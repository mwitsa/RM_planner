"""Persistent labour settings for raw and cooked production lines."""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path


STORE_VERSION = 1


@dataclass(frozen=True, slots=True)
class LabourSettings:
    raw_labour: int = 0
    raw_wage: float = 0.0
    cooked_labour: int = 0
    cooked_wage: float = 0.0


def _labour_count(value: object, name: str) -> int:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        raise ValueError(f"{name} must be a whole number of 0 or greater.") from None
    if not math.isfinite(numeric) or numeric < 0 or not numeric.is_integer():
        raise ValueError(f"{name} must be a whole number of 0 or greater.")
    return int(numeric)


def _wage(value: object, name: str) -> float:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        raise ValueError(f"{name} must be a number of 0 or greater.") from None
    if not math.isfinite(numeric) or numeric < 0:
        raise ValueError(f"{name} must be a number of 0 or greater.")
    return numeric


def _validate(settings: LabourSettings) -> LabourSettings:
    return LabourSettings(
        raw_labour=_labour_count(settings.raw_labour, "Raw labour"),
        raw_wage=_wage(settings.raw_wage, "Raw wage"),
        cooked_labour=_labour_count(settings.cooked_labour, "Cooked labour"),
        cooked_wage=_wage(settings.cooked_wage, "Cooked wage"),
    )


def load_labour_settings(store_path: str | Path) -> LabourSettings:
    path = Path(store_path)
    if not path.exists():
        return LabourSettings()
    try:
        with path.open(encoding="utf-8") as handle:
            payload = json.load(handle)
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Could not read labour settings: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError("Labour settings have an invalid structure.")
    return _validate(LabourSettings(
        raw_labour=payload.get("raw_labour", 0),
        raw_wage=payload.get("raw_wage", 0),
        cooked_labour=payload.get("cooked_labour", 0),
        cooked_wage=payload.get("cooked_wage", 0),
    ))


def save_labour_settings(store_path: str | Path, settings: LabourSettings) -> LabourSettings:
    path = Path(store_path)
    normalized = _validate(settings)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"version": STORE_VERSION, **{
        "raw_labour": normalized.raw_labour,
        "raw_wage": normalized.raw_wage,
        "cooked_labour": normalized.cooked_labour,
        "cooked_wage": normalized.cooked_wage,
    }}
    temporary_path = path.with_suffix(f"{path.suffix}.tmp")
    try:
        with temporary_path.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
        temporary_path.replace(path)
    except OSError as exc:
        raise ValueError(f"Could not save labour settings: {exc}") from exc
    return normalized
