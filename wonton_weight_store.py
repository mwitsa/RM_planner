"""Persistent per-class wonton weights used for RM yield estimates."""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path

from assortment_range_store import SIZE_CLASSES, normalize_size_class


STORE_VERSION = 1
DEFAULT_WONTON_WEIGHT_GRAMS = {
    "M": 1000 / 53,
    "S+": 1000 / 69.25,
}


@dataclass(frozen=True, slots=True)
class WontonWeightSettings:
    m_grams: float = DEFAULT_WONTON_WEIGHT_GRAMS["M"]
    s_plus_grams: float = DEFAULT_WONTON_WEIGHT_GRAMS["S+"]

    def __post_init__(self) -> None:
        for size_class, value in (("M", self.m_grams), ("S+", self.s_plus_grams)):
            try:
                numeric = float(value)
            except (TypeError, ValueError) as exc:
                raise ValueError(f"{size_class} wonton weight must be numeric.") from exc
            if not math.isfinite(numeric) or numeric <= 0:
                raise ValueError(
                    f"{size_class} wonton weight must be greater than zero."
                )
            object.__setattr__(
                self,
                "m_grams" if size_class == "M" else "s_plus_grams",
                numeric,
            )

    def grams_for(self, size_class: object) -> float:
        normalized = normalize_size_class(size_class)
        if normalized == "M":
            return self.m_grams
        if normalized == "S+":
            return self.s_plus_grams
        raise ValueError(f"Wonton weight is not defined for RM class {size_class}.")

    def wontons_per_kg(self, size_class: object) -> float:
        return 1000 / self.grams_for(size_class)

    def estimate_wontons(self, size_class: object, weight_kg: int | float) -> float:
        try:
            numeric_weight = float(weight_kg)
        except (TypeError, ValueError) as exc:
            raise ValueError("RM weight must be numeric.") from exc
        if not math.isfinite(numeric_weight) or numeric_weight < 0:
            raise ValueError("RM weight must be zero or greater.")
        return numeric_weight * self.wontons_per_kg(size_class)


def load_wonton_weight_settings(store_path: str | Path) -> WontonWeightSettings:
    path = Path(store_path)
    if not path.exists():
        return WontonWeightSettings()
    try:
        with path.open(encoding="utf-8") as handle:
            payload = json.load(handle)
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Could not read wonton weight settings: {exc}") from exc
    if not isinstance(payload, dict) or not isinstance(payload.get("weights_g"), dict):
        raise ValueError("Wonton weight settings have an invalid structure.")
    weights = payload["weights_g"]
    return WontonWeightSettings(
        m_grams=weights.get("M"),
        s_plus_grams=weights.get("S+"),
    )


def save_wonton_weight_settings(
    store_path: str | Path,
    settings: WontonWeightSettings,
) -> Path:
    path = Path(store_path)
    payload = {
        "version": STORE_VERSION,
        "weights_g": {
            size_class: settings.grams_for(size_class)
            for size_class in SIZE_CLASSES
        },
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = path.with_suffix(f"{path.suffix}.tmp")
    try:
        with temporary_path.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
        temporary_path.replace(path)
    except OSError as exc:
        raise ValueError(f"Could not save wonton weight settings: {exc}") from exc
    return path
