"""Persistent production-capacity settings."""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path


STORE_VERSION = 5


@dataclass(frozen=True, slots=True)
class CapacitySettings:
    raw_percentage: int = 50
    cooked_percentage: int = 50
    raw_wonton: int | float | None = None
    cooked_wonton: int | float | None = None
    raw_cups_per_hour: int | float | None = None
    cooked_cups_per_hour: int | float | None = None
    cooked_noodle_cups_per_hour: int | float | None = None
    work_hours_per_day: int | float = 8


def capacities_at_percentage(
    settings: CapacitySettings,
    raw_percentage: int | float | None = None,
    cooked_percentage: int | float | None = None,
) -> tuple[int | float | None, int | float | None]:
    """Return raw and cooked capacities using independent utilization values."""

    normalized = _validate_settings(settings)
    selected_raw = (
        normalized.raw_percentage
        if raw_percentage is None
        else _required_percentage(raw_percentage, "Raw")
    )
    selected_cooked = (
        normalized.cooked_percentage
        if cooked_percentage is None
        else _required_percentage(cooked_percentage, "Cooked")
    )
    raw_rate = normalized.raw_cups_per_hour
    cooked_rate = normalized.cooked_cups_per_hour
    # Keep programmatic callers and existing tests that still provide legacy
    # daily numbers working while the UI migrates to hourly inputs.
    if raw_rate is None:
        raw_rate = _per_hour(normalized.raw_wonton, normalized.work_hours_per_day)
    if cooked_rate is None:
        cooked_rate = _per_hour(normalized.cooked_wonton, normalized.work_hours_per_day)
    return (
        _scaled_number(raw_rate, normalized.work_hours_per_day * selected_raw / 100),
        _scaled_number(cooked_rate, normalized.work_hours_per_day * selected_cooked / 100),
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
    legacy_raw_percentage = payload.get(
        "raw_percentage",
        payload.get("percentage", 50),
    )
    cooked_percentage = payload.get("cooked_percentage")
    if cooked_percentage is None:
        cooked_percentage = 100 - _required_percentage(
            legacy_raw_percentage,
            "Raw",
        )
    settings = _validate_settings(
        CapacitySettings(
            raw_percentage=legacy_raw_percentage,
            cooked_percentage=cooked_percentage,
            raw_wonton=payload.get("raw_wonton"),
            cooked_wonton=payload.get("cooked_wonton"),
            raw_cups_per_hour=payload.get("raw_cups_per_hour", payload.get("raw_wonton_per_hour")),
            cooked_cups_per_hour=payload.get("cooked_cups_per_hour", payload.get("cooked_wonton_per_hour")),
            cooked_noodle_cups_per_hour=payload.get(
                "cooked_noodle_cups_per_hour", payload.get("cooked_wonton_noodle_per_hour")),
            work_hours_per_day=payload.get("work_hours_per_day", 8),
        )
    )
    # Old files stored only daily capacity. Preserve a usable calculation by
    # converting that value to an hourly rate using the configured/default day.
    return CapacitySettings(
        raw_percentage=settings.raw_percentage,
        cooked_percentage=settings.cooked_percentage,
        raw_wonton=settings.raw_wonton,
        cooked_wonton=settings.cooked_wonton,
        raw_cups_per_hour=(settings.raw_cups_per_hour if settings.raw_cups_per_hour is not None
                             else _per_hour(settings.raw_wonton, settings.work_hours_per_day)),
        cooked_cups_per_hour=(settings.cooked_cups_per_hour if settings.cooked_cups_per_hour is not None
                                else _per_hour(settings.cooked_wonton, settings.work_hours_per_day)),
        cooked_noodle_cups_per_hour=settings.cooked_noodle_cups_per_hour,
        work_hours_per_day=settings.work_hours_per_day,
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
        "raw_percentage": normalized.raw_percentage,
        "cooked_percentage": normalized.cooked_percentage,
        "raw_wonton": normalized.raw_wonton,
        "cooked_wonton": normalized.cooked_wonton,
        "raw_cups_per_hour": normalized.raw_cups_per_hour,
        "cooked_cups_per_hour": normalized.cooked_cups_per_hour,
        "cooked_noodle_cups_per_hour": normalized.cooked_noodle_cups_per_hour,
        "work_hours_per_day": normalized.work_hours_per_day,
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
    return CapacitySettings(
        raw_percentage=_required_percentage(settings.raw_percentage, "Raw"),
        cooked_percentage=_required_percentage(settings.cooked_percentage, "Cooked"),
        raw_wonton=_optional_nonnegative_number(settings.raw_wonton, "เกี๊ยวดิบ"),
        cooked_wonton=_optional_nonnegative_number(settings.cooked_wonton, "เกี๊ยวสุก"),
        raw_cups_per_hour=_optional_nonnegative_number(settings.raw_cups_per_hour, "Raw cups / hr"),
        cooked_cups_per_hour=_optional_nonnegative_number(settings.cooked_cups_per_hour, "Cooked cups / hr"),
        cooked_noodle_cups_per_hour=_optional_nonnegative_number(
            settings.cooked_noodle_cups_per_hour, "Cooked noodle cups / hr"),
        work_hours_per_day=_required_work_hours(settings.work_hours_per_day),
    )


def _required_percentage(value: object, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(
            f"{label} capacity percentage must be a number from 0 to 100."
        )
    numeric = float(value)
    if not math.isfinite(numeric) or not 0 <= numeric <= 100:
        raise ValueError(f"{label} capacity percentage must be from 0 to 100.")
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


def _per_hour(value: int | float | None, work_hours: int | float) -> int | float | None:
    return None if value is None else _scaled_number(value, 1 / work_hours)


def _required_work_hours(value: object) -> int | float:
    numeric = _optional_nonnegative_number(value, "ชั่วโมงทำงานต่อวัน")
    if numeric is None or numeric <= 0 or numeric > 24:
        raise ValueError("ชั่วโมงทำงานต่อวันต้องมากกว่า 0 และไม่เกิน 24")
    return numeric
