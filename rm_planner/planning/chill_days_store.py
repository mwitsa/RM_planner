"""Persistent Operations setting for the usable chilled-RM window."""

from __future__ import annotations

import json
from pathlib import Path


DEFAULT_CHILL_DAYS = 0


def load_chill_days(store_path: str | Path) -> int:
    """Return the configured whole number of days RM may remain chilled."""

    path = Path(store_path)
    if not path.exists():
        return DEFAULT_CHILL_DAYS
    try:
        with path.open(encoding="utf-8") as handle:
            payload = json.load(handle)
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Could not read chill-days settings: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError("Chill-days settings have an invalid structure.")
    return _validate_chill_days(payload.get("chill_days", DEFAULT_CHILL_DAYS))


def save_chill_days(store_path: str | Path, chill_days: object) -> int:
    """Validate and save the chilled-RM window."""

    normalized = _validate_chill_days(chill_days)
    path = Path(store_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = path.with_suffix(f"{path.suffix}.tmp")
    try:
        with temporary_path.open("w", encoding="utf-8") as handle:
            json.dump({"version": 1, "chill_days": normalized}, handle, indent=2)
            handle.write("\n")
        temporary_path.replace(path)
    except OSError as exc:
        raise ValueError(f"Could not save chill-days settings: {exc}") from exc
    return normalized


def _validate_chill_days(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError("Chill days must be a whole number of 0 or greater.")
    return value
