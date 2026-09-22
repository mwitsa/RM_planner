"""Persistent Loss cost settings used to compare production plans."""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from pathlib import Path


STORE_VERSION = 4

# Display label for each scalar field's validation error, in the order shown
# on the Loss Calculation page.
_FIELD_LABELS = {
    "freeze_in_labor_cost_per_kg": "ค่าแรง (นำเข้า Freeze)",
    "freeze_in_repair_cost_per_kg": "ค่าซ่อมแซม (นำเข้า Freeze)",
    "freeze_in_energy_cost_per_kg": "ค่าพลังงาน (นำเข้า Freeze)",
    "freeze_in_depreciation_cost_per_kg": "ค่าเสื่อมราคา (นำเข้า Freeze)",
    "thaw_labor_cost_per_kg": "ค่าแรง (ทอละลาย)",
    "thaw_salary_cost_per_kg": "เงินเดือน (ทอละลาย)",
    "thaw_repair_cost_per_kg": "ค่าซ่อมแซม (ทอละลาย)",
    "thaw_depreciation_cost_per_kg": "ค่าเสื่อมราคา (ทอละลาย)",
    "thaw_other_cost_per_kg": "ค่าใช้จ่ายอื่น (ทอละลาย)",
    "yield_loss_percent": "Yield Loss",
    "soup_base_loss_liters": "ปริมาณน้ำซุปที่สูญเสีย",
}

# Groups of field names shown together under the "1. Freeze PD" card.
FREEZE_IN_FIELDS = (
    "freeze_in_labor_cost_per_kg",
    "freeze_in_repair_cost_per_kg",
    "freeze_in_energy_cost_per_kg",
    "freeze_in_depreciation_cost_per_kg",
)
THAW_FIELDS = (
    "thaw_labor_cost_per_kg",
    "thaw_salary_cost_per_kg",
    "thaw_repair_cost_per_kg",
    "thaw_depreciation_cost_per_kg",
    "thaw_other_cost_per_kg",
)
# "3. Base น้ำซุป" card fields.
SOUP_BASE_FIELDS = ("soup_base_loss_liters",)
# บาท/ก.ก. scalar cost fields that sum into freeze_pd_cost_per_kg — excludes
# fields with a different unit (see _SCALAR_FIELD_UNITS).
_COST_PER_KG_FIELDS = (*FREEZE_IN_FIELDS, *THAW_FIELDS)
_SCALAR_FIELD_NAMES = (*_COST_PER_KG_FIELDS, "yield_loss_percent", *SOUP_BASE_FIELDS)
# Scalar fields whose unit isn't บาท/ก.ก. (the default).
_SCALAR_FIELD_UNITS = {
    "yield_loss_percent": "%",
    "soup_base_loss_liters": "ลิตร",
}

# "2. ต้นทุนแรงงานไลน์ผลิตโรงงานแกลง 3" — work centers (code, name), source:
# the factory's WT/FU cost-center list. ทางตรง = direct production lines.
WORK_CENTERS_GLAENG_3 = (
    ("1197112030", "WT- Freezer  Raw"),
    ("1197112031", "WT- Pack  Raw"),
    ("1197112032", "WT Freezer PD"),
    ("1197112033", "WT-เตรียมRM"),
    ("1197112034", "WT-ผลิตห่อเกี๊ยว"),
    ("1197112035", "WT-Cook"),
    ("1197112036", "WT-ผลิตแผ่นแป้ง"),
    ("1197112037", "WT-ผลิตPremix"),
    ("1197112038", "WT-ผลิตIngredient"),
    ("1197112039", "WT-ผลิตเส้นบะหมี่"),
    ("1197112040", "WT-ผลิตน้ำซุป"),
    ("1197112041", "WT-ส่วนกลางผลิต"),
    ("1197112042", "WT-Freezer"),
    ("1197112043", "WT-Freezer น้ำซุป"),
    ("1197112044", "WT-Pack"),
    ("1197112048", "อสร.แกลงWT-ผ.ING.ซุป"),
    ("1197112050", "FU-Cook-Noodle"),
)
# ทางอ้อม = indirect / support departments.
WORK_CENTERS_GLAENG_3_INDIRECT = (
    ("1197112047", "CPF-สุขศาสตร์"),
    ("1197112070", "ส่วนกลางโรงงาน"),
    ("1197112072", "คลังพัสดุ"),
    ("1197112073", "คลัง Package"),
    ("1197112076", "วางแผนการผลิต"),
    ("1197112077", "วิศวกรรม"),
    ("1197112081", "ทีมSHE"),
    ("1197112083", "วิจัยพัฒนาผลิตภัณฑ์"),
    ("1197112085", "ระบบมาตรฐานคุณภาพ"),
    ("1197112322", "ธุรการ"),
    ("1197112412", "ทรัพยากรบุคคล"),
    ("1197112503", "จัดซื้อพัสดุ"),
    ("1197112761", "ควบคุมคุณภาพ"),
    ("1197112762", "ประกันคุณภาพ"),
)
_WORK_CENTER_NAMES = dict(WORK_CENTERS_GLAENG_3) | dict(WORK_CENTERS_GLAENG_3_INDIRECT)

# The Z-code cost chart (Z1 ค่าแรง, then Z2-ZA) applies identically to both
# ทางตรง and ทางอ้อม, just against a different work-center list each time —
# built once here and instantiated per group below instead of duplicated.
_Z2_TO_ZA_CATEGORY_DEFS = (
    ("z2_utilities", "Z2", "ค่าไฟฟ้า-น้ำประปา"),
    ("z3_repair", "Z3", "ค่าซ่อมบำรุง"),
    ("z4_consumables", "Z4", "ค่าวัสดุสิ้นเปลือง"),
    ("z5_rent", "Z5", "ค่าเช่า"),
    ("z6_depreciation", "Z6", "ค่าเสื่อม"),
    ("z7_fuel", "Z7", "ค่าเชื้อเพลิง"),
    ("z8_other_expenses", "Z8", "ค่าใช้จ่ายอื่นๆ"),
    ("z9_salary", "Z9", "เงินเดือน"),
    ("za_other_fixed", "ZA", "อื่นๆFix"),
)


def _build_z_cost_group(prefix: str, group_label: str, work_centers: tuple[tuple[str, str], ...]):
    """Build the Z1 (ค่าแรง, คน) + Z2-ZA (บาท/ถ้วย) line items for one group."""

    labor_item_keys = tuple(f"{prefix}_labor:{code}" for code, _name in work_centers)
    single_rate_categories = tuple(
        (f"{prefix}_{suffix}", z_code, label) for suffix, z_code, label in _Z2_TO_ZA_CATEGORY_DEFS
    )
    single_rate_item_keys = {
        category: tuple(f"{category}:{code}" for code, _name in work_centers)
        for category, _z_code, _label in single_rate_categories
    }
    category_labels = {
        f"{prefix}_labor": f"{group_label} - Z1 ค่าแรง (คน)",
        **{
            category: f"{group_label} - {z_code} {label}"
            for category, z_code, label in single_rate_categories
        },
    }
    unit_by_category = {
        f"{prefix}_labor": "คน",
        **{category: "บาท/ถ้วย" for category, _z_code, _label in single_rate_categories},
    }
    all_keys = (
        *labor_item_keys,
        *(key for keys in single_rate_item_keys.values() for key in keys),
    )
    return {
        "labor_item_keys": labor_item_keys,
        "single_rate_categories": single_rate_categories,
        "single_rate_item_keys": single_rate_item_keys,
        "category_labels": category_labels,
        "unit_by_category": unit_by_category,
        "all_keys": all_keys,
    }


_DIRECT = _build_z_cost_group("direct", "ทางตรง", WORK_CENTERS_GLAENG_3)
_INDIRECT = _build_z_cost_group("indirect", "ทางอ้อม", WORK_CENTERS_GLAENG_3_INDIRECT)

DIRECT_LABOR_ITEM_KEYS = _DIRECT["labor_item_keys"]
DIRECT_SINGLE_RATE_CATEGORIES = _DIRECT["single_rate_categories"]
DIRECT_SINGLE_RATE_ITEM_KEYS = _DIRECT["single_rate_item_keys"]

INDIRECT_LABOR_ITEM_KEYS = _INDIRECT["labor_item_keys"]
INDIRECT_SINGLE_RATE_CATEGORIES = _INDIRECT["single_rate_categories"]
INDIRECT_SINGLE_RATE_ITEM_KEYS = _INDIRECT["single_rate_item_keys"]

_LINE_ITEM_CATEGORY_LABELS = {**_DIRECT["category_labels"], **_INDIRECT["category_labels"]}
_LINE_ITEM_UNIT_BY_CATEGORY = {**_DIRECT["unit_by_category"], **_INDIRECT["unit_by_category"]}
ALL_LINE_ITEM_KEYS = (*_DIRECT["all_keys"], *_INDIRECT["all_keys"])


def _line_item_label(key: str) -> str:
    category, code = key.split(":", 1)
    category_label = _LINE_ITEM_CATEGORY_LABELS.get(category, category)
    return f"{category_label} - {_WORK_CENTER_NAMES.get(code, code)}"


@dataclass(frozen=True, slots=True)
class LossSettings:
    # 1. Freeze PD — ต้นทุนการนำเข้า Freeze
    freeze_in_labor_cost_per_kg: float = 0.0
    freeze_in_repair_cost_per_kg: float = 0.0
    freeze_in_energy_cost_per_kg: float = 0.0
    freeze_in_depreciation_cost_per_kg: float = 0.0
    # 1. Freeze PD — ต้นทุนการทอละลาย
    thaw_labor_cost_per_kg: float = 0.0
    thaw_salary_cost_per_kg: float = 0.0
    thaw_repair_cost_per_kg: float = 0.0
    thaw_depreciation_cost_per_kg: float = 0.0
    thaw_other_cost_per_kg: float = 0.0
    # 1. Freeze PD — ต้นทุน Yield Loss
    yield_loss_percent: float = 0.0
    # 3. Base น้ำซุป — 1. ปริมาณน้ำซุปที่สูญเสีย
    soup_base_loss_liters: float = 0.0
    # 2. ต้นทุนแรงงานไลน์ผลิตโรงงานแกลง 3 — one entry per "<category>:<code>"
    # line item (see ALL_LINE_ITEM_KEYS); unit depends on the category, see
    # _LINE_ITEM_UNIT_BY_CATEGORY (direct_labor is headcount, คน).
    line_item_costs: dict[str, float] = field(default_factory=dict)

    @property
    def freeze_pd_cost_per_kg(self) -> float:
        """Total Freeze PD cost per kg: sum of every entered บาท/ก.ก. component."""

        return sum(getattr(self, name) for name in _COST_PER_KG_FIELDS)


def _nonnegative_number(value: object, label: str, unit: str) -> float:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        raise ValueError(f"{label} ({unit}) must be a number of 0 or greater.") from None
    if not math.isfinite(numeric) or numeric < 0:
        raise ValueError(f"{label} ({unit}) must be a number of 0 or greater.")
    return numeric


def _cost_per_kg(value: object, label: str) -> float:
    return _nonnegative_number(value, label, "บาท/ก.ก.")


def _percent(value: object, label: str) -> float:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        raise ValueError(f"{label} (%) must be a number between 0 and 100.") from None
    if not math.isfinite(numeric) or not 0 <= numeric <= 100:
        raise ValueError(f"{label} (%) must be a number between 0 and 100.")
    return numeric


def _headcount(value: object, label: str) -> int:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        raise ValueError(f"{label} (คน) must be a whole number of 0 or greater.") from None
    if not math.isfinite(numeric) or numeric < 0 or not numeric.is_integer():
        raise ValueError(f"{label} (คน) must be a whole number of 0 or greater.")
    return int(numeric)


def _validate_line_item(key: str, value: object) -> float:
    category = key.split(":", 1)[0]
    label = _line_item_label(key)
    unit = _LINE_ITEM_UNIT_BY_CATEGORY.get(category, "บาท/ก.ก.")
    if unit == "คน":
        return _headcount(value, label)
    return _nonnegative_number(value, label, unit)


def _validate_scalar(name: str, value: object) -> float:
    label = _FIELD_LABELS[name]
    unit = _SCALAR_FIELD_UNITS.get(name)
    if unit == "%":
        return _percent(value, label)
    if unit is not None:
        return _nonnegative_number(value, label, unit)
    return _cost_per_kg(value, label)


def _validate(settings: LossSettings) -> LossSettings:
    scalars = {
        name: _validate_scalar(name, getattr(settings, name))
        for name in _SCALAR_FIELD_NAMES
    }
    line_items = {
        key: _validate_line_item(key, settings.line_item_costs.get(key, 0))
        for key in ALL_LINE_ITEM_KEYS
    }
    return LossSettings(**scalars, line_item_costs=line_items)


def load_loss_settings(store_path: str | Path) -> LossSettings:
    path = Path(store_path)
    if not path.exists():
        return _validate(LossSettings())
    try:
        with path.open(encoding="utf-8") as handle:
            payload = json.load(handle)
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Could not read loss settings: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError("Loss settings have an invalid structure.")
    raw_line_items = payload.get("line_item_costs", {})
    if not isinstance(raw_line_items, dict):
        raise ValueError("Loss settings have an invalid line item structure.")
    return _validate(LossSettings(
        **{name: payload.get(name, 0) for name in _SCALAR_FIELD_NAMES},
        line_item_costs=raw_line_items,
    ))


def save_loss_settings(store_path: str | Path, settings: LossSettings) -> LossSettings:
    path = Path(store_path)
    normalized = _validate(settings)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "version": STORE_VERSION,
        **{name: getattr(normalized, name) for name in _SCALAR_FIELD_NAMES},
        "line_item_costs": normalized.line_item_costs,
    }
    temporary_path = path.with_suffix(f"{path.suffix}.tmp")
    try:
        with temporary_path.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
        temporary_path.replace(path)
    except OSError as exc:
        raise ValueError(f"Could not save loss settings: {exc}") from exc
    return normalized
