"""Persistent production-capacity settings."""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path


STORE_VERSION = 2


@dataclass(frozen=True, slots=True)
class CapacitySettings:
    percentage: int = 50
    raw_wonton: int | float | None = None
    cooked_wonton: int | float | None = None


def capacities_at_percentage(
    settings: CapacitySettings,
    percentage: int | float | None = None,
) -> tuple[int | float | None, int | float | None]:
    """Return capacities using a complementary raw/cooked production split.

    ``percentage`` is the share assigned to raw wontons. Cooked wontons receive
    the remaining share, so the two production shares always total 100%.
    """

    normalized = _validate_settings(settings)
    selected_percentage = normalized.percentage if percentage is None else _required_percentage(percentage)
    raw_multiplier = selected_percentage / 100
    cooked_multiplier = (100 - selected_percentage) / 100
    return (
        _scaled_number(normalized.raw_wonton, raw_multiplier),
        _scaled_number(normalized.cooked_wonton, cooked_multiplier),
    )


def load_capacity_settings(store_path: str | Path) -> CapacitySettings:
    path = Path(store_path)
    if not path.exists():
        return CapacitySettings()
    try:
        with path.open(encoding="utf-8") as handle:
            payload = json.load(handle)
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Could not read capacity settings: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError("Capacity settings have an invalid structure.")
    return _validate_settings(
        CapacitySettings(
            percentage=payload.get("raw_percentage", payload.get("percentage", 50)),
            raw_wonton=payload.get("raw_wonton"),
            cooked_wonton=payload.get("cooked_wonton"),
        )
    )


def save_capacity_settings(
    store_path: str | Path,
    settings: CapacitySettings,
) -> CapacitySettings:
    path = Path(store_path)
    normalized = _validate_settings(settings)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "version": STORE_VERSION,
        "raw_percentage": normalized.percentage,
        "raw_wonton": normalized.raw_wonton,
        "cooked_wonton": normalized.cooked_wonton,
    }
    temporary_path = path.with_suffix(f"{path.suffix}.tmp")
    try:
        with temporary_path.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
        temporary_path.replace(path)
    except OSError as exc:
        raise ValueError(f"Could not save capacity settings: {exc}") from exc
    return normalized


def _validate_settings(settings: CapacitySettings) -> CapacitySettings:
    percentage = _required_percentage(settings.percentage)
    return CapacitySettings(
        percentage=percentage,
        raw_wonton=_optional_nonnegative_number(settings.raw_wonton, "เกี๊ยวดิบ"),
        cooked_wonton=_optional_nonnegative_number(settings.cooked_wonton, "เกี๊ยวสุก"),
    )


def _required_percentage(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("Raw capacity share must be a number from 0 to 100.")
    numeric = float(value)
    if not math.isfinite(numeric) or not 0 <= numeric <= 100:
        raise ValueError("Raw capacity share must be from 0 to 100.")
    return int(round(numeric))


def _optional_nonnegative_number(value: object, label: str) -> int | float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{label} capacity must be numeric or blank.")
    numeric = float(value)
    if not math.isfinite(numeric) or numeric < 0:
        raise ValueError(f"{label} capacity must be zero or greater.")
    return int(numeric) if numeric.is_integer() else numeric


def _scaled_number(
    value: int | float | None,
    multiplier: float,
) -> int | float | None:
    if value is None:
        return None
    result = value * multiplier
    return int(result) if float(result).is_integer() else result
