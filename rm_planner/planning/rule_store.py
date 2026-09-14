"""Persistent storage for ordered production-planning rules."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable


RULE_FILE_VERSION = 1


def load_rules(rule_path: str | Path) -> list[str]:
    """Load rule text in application order; a missing file means no rules."""

    path = Path(rule_path)
    if not path.exists():
        return []
    try:
        with path.open(encoding="utf-8") as handle:
            payload = json.load(handle)
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Could not read saved rules: {exc}") from exc

    if not isinstance(payload, dict) or not isinstance(payload.get("rules"), list):
        raise ValueError("Saved rule file has an invalid structure.")

    rules: list[str] = []
    for entry in payload["rules"]:
        if not isinstance(entry, dict) or not isinstance(entry.get("text"), str):
            raise ValueError("Saved rule file contains an invalid rule.")
        text = entry["text"].strip()
        if text:
            rules.append(text)
    return rules


def save_rules(rule_path: str | Path, rules: Iterable[str]) -> Path:
    """Atomically save rule text in top-to-bottom waterfall order."""

    path = Path(rule_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    normalized = [text.strip() for text in rules if text.strip()]
    payload = {
        "version": RULE_FILE_VERSION,
        "rules": [
            {"priority": priority, "text": text}
            for priority, text in enumerate(normalized, start=1)
        ],
    }
    temporary_path = path.with_suffix(f"{path.suffix}.tmp")
    try:
        with temporary_path.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
        temporary_path.replace(path)
    except OSError as exc:
        raise ValueError(f"Could not save rules: {exc}") from exc
    return path
