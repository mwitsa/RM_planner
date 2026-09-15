"""Persistence for the visual operation-order workflow."""

from __future__ import annotations

import json
from pathlib import Path


def load_operation_rules(path: str | Path) -> list[dict]:
    path = Path(path)
    if not path.exists():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"เปิด Operation order rule ไม่ได้: {exc}") from exc
    rules = payload.get("rules") if isinstance(payload, dict) else None
    if not isinstance(rules, list):
        raise ValueError("ไฟล์ Operation order rule ไม่ถูกต้อง")
    normalized = []
    for rule in rules:
        nodes = rule.get("nodes") if isinstance(rule, dict) else None
        if not isinstance(nodes, list):
            raise ValueError("ข้อมูล Rule ไม่ถูกต้อง")
        normalized_nodes = []
        for node in nodes:
            if not isinstance(node, dict) or not all(isinstance(node.get(key), str) for key in ("class", "group")):
                raise ValueError("ข้อมูลกล่อง Rule ไม่ถูกต้อง")
            normalized_nodes.append({"class": node["class"].strip(), "group": node["group"].strip()})
        normalized.append({"nodes": normalized_nodes})
    return normalized


def save_operation_rules(path: str | Path, rules: list[dict]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"version": 1, "rules": rules}
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    temporary.replace(path)
