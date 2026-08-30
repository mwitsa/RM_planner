"""User-facing labels for internal RM market values."""

from __future__ import annotations


MARKET_DISPLAY_LABELS = {
    "domestic": "ในประเทศ",
    "export": "ต่างประเทศ",
    "unassigned": "UNASSIGNED",
}
MARKET_DISPLAY_OPTIONS = (
    MARKET_DISPLAY_LABELS["domestic"],
    MARKET_DISPLAY_LABELS["export"],
)


def market_display_label(value: object) -> str:
    """Return the Thai UI label while accepting an internal or display value."""

    normalized = str(value or "").strip()
    internal = market_internal_value(normalized, allow_unassigned=True)
    return MARKET_DISPLAY_LABELS[internal]


def market_internal_value(value: object, *, allow_unassigned: bool = False) -> str:
    """Normalize Thai UI labels and legacy English values for persistence."""

    normalized = str(value or "").strip()
    casefolded = normalized.casefold()
    aliases = {
        "domestic": "domestic",
        "export": "export",
        "unassigned": "unassigned",
        MARKET_DISPLAY_LABELS["domestic"].casefold(): "domestic",
        MARKET_DISPLAY_LABELS["export"].casefold(): "export",
    }
    internal = aliases.get(casefolded)
    allowed = {"domestic", "export"}
    if allow_unassigned:
        allowed.add("unassigned")
    if internal not in allowed:
        choices = "ในประเทศ or ต่างประเทศ"
        raise ValueError(f"RM usage must be {choices}.")
    return internal
