"""Persistent Operations settings for production-line start times."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


PRODUCTION_WINDOW_START_HOUR = 16
PRODUCTION_WINDOW_END_HOUR = 8
DEFAULT_COOKED_START_HOUR = 18
DEFAULT_RAW_START_HOUR = 19


@dataclass(frozen=True, slots=True)
class ProductionStartSettings:
    """Clock hours at which each production line begins its daily work."""

    cooked_hour: int = DEFAULT_COOKED_START_HOUR
    raw_hour: int = DEFAULT_RAW_START_HOUR


def production_time_options() -> tuple[str, ...]:
    """Return valid hourly choices in the displayed 16:00–08:00 order."""

    return tuple(
        f"{hour:02d}:00"
        for hour in (*range(PRODUCTION_WINDOW_START_HOUR, 24), *range(PRODUCTION_WINDOW_END_HOUR + 1))
    )


def load_production_start_settings(store_path: str | Path) -> ProductionStartSettings:
    """Load the saved line start times, or their current 18:00/19:00 defaults."""

    path = Path(store_path)
    if not path.exists():
        return ProductionStartSettings()
    try:
        with path.open(encoding="utf-8") as handle:
            payload = json.load(handle)
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Could not read production-start settings: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError("Production-start settings have an invalid structure.")
    return _validate_settings(
        ProductionStartSettings(
            cooked_hour=payload.get("cooked_hour", DEFAULT_COOKED_START_HOUR),
            raw_hour=payload.get("raw_hour", DEFAULT_RAW_START_HOUR),
        )
    )


def save_production_start_settings(
    store_path: str | Path,
    settings: ProductionStartSettings,
) -> ProductionStartSettings:
    """Validate and save daily Cooked and Raw production start times."""

    normalized = _validate_settings(settings)
    path = Path(store_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = path.with_suffix(f"{path.suffix}.tmp")
    try:
        with temporary_path.open("w", encoding="utf-8") as handle:
            json.dump(
                {
                    "version": 1,
                    "cooked_hour": normalized.cooked_hour,
                    "raw_hour": normalized.raw_hour,
                },
                handle,
                indent=2,
            )
            handle.write("\n")
        temporary_path.replace(path)
    except OSError as exc:
        raise ValueError(f"Could not save production-start settings: {exc}") from exc
    return normalized


def hour_from_time_label(value: object) -> int:
    """Parse one of the fixed hourly UI values such as ``18:00``."""

    label = str(value or "").strip()
    try:
        hour_text, minute_text = label.split(":", 1)
        hour = int(hour_text)
    except (TypeError, ValueError) as exc:
        raise ValueError("Choose a production start time in HH:00 format.") from exc
    if minute_text != "00":
        raise ValueError("Production start time must be set by the hour (HH:00).")
    return _validate_hour(hour)


def _validate_settings(settings: ProductionStartSettings) -> ProductionStartSettings:
    if not isinstance(settings, ProductionStartSettings):
        raise ValueError("Production-start settings have an invalid structure.")
    return ProductionStartSettings(
        cooked_hour=_validate_hour(settings.cooked_hour),
        raw_hour=_validate_hour(settings.raw_hour),
    )


def _validate_hour(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError("Production start hour must be a whole hour.")
    if not 0 <= value <= 23:
        raise ValueError("Production start hour must be between 00:00 and 23:00.")
    if PRODUCTION_WINDOW_END_HOUR < value < PRODUCTION_WINDOW_START_HOUR:
        raise ValueError("Production start time must be within the 16:00–08:00 production window.")
    return value
