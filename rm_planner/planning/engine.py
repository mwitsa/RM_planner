"""Deterministic production-plan generation from prepared application data.

The engine is deliberately independent of Tkinter.  It treats every assortment
entry as one physical inventory lot, even when that lot is eligible for more
than one M/S/SS class.
"""

from __future__ import annotations

import calendar
import math
import re
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Iterable

from rm_planner.inventory.actual_store import ActualAssortmentRecord, split_size_range
from rm_planner.inventory.range_store import (
    AssortmentSizeRange,
    classify_size_range,
    normalize_size_class,
)
from rm_planner.planning.capacity_store import CapacitySettings, capacities_at_percentage
from rm_planner.planning.class_store import ClassDefinition
from rm_planner.orders.extractor import OrderRecord
from rm_planner.planning.market_labels import market_display_label
from rm_planner.inventory.wonton_weight_store import WontonWeightSettings


SUPPORTED_RM_SIZES = {"M", "S", "SS"}
SKIPPED_RM_SIZES = {"BK", "HC"}
SUPPORTED_MARKETS = {"export", "domestic", "unassigned"}
MISSING_PRIORITY = 1_000_000
EPSILON = 1e-7


@dataclass(frozen=True, slots=True)
class PlanAllocation:
    plan_date: str
    due_date: str
    order_no: str
    order_id: str
    customer: str
    group_1: str
    production_type: str
    market_type: str
    rm_size: str
    priority: str
    order_cups: float
    order_wontons: float
    planned_units: float
    planned_cups: float
    planned_wontons: float
    rm_kg: float
    expected_wontons: float
    rm_sources: str
    is_late: bool

    @property
    def produced_wontons(self) -> float:
        """Wontons produced from the physical RM consumed by this plan row."""

        return self.planned_wontons


@dataclass(frozen=True, slots=True)
class UnplannedOrder:
    order_no: str
    order_id: str
    due_date: str
    customer: str
    group_1: str
    production_type: str
    market_type: str
    rm_size: str
    remaining_wontons: float
    reason: str


@dataclass(frozen=True, slots=True)
class PlanResult:
    allocations: tuple[PlanAllocation, ...]
    unplanned: tuple[UnplannedOrder, ...]
    eligible_orders: int
    skipped_past_orders: int
    planned_wontons: float
    used_rm_kg: float
    start_date: str
    end_date: str


@dataclass(slots=True)
class _InventoryLot:
    available_date: date
    market_type: str
    stock_source: str
    record_id: str
    size_range: str
    wontons_per_kg: float
    eligible_classes: tuple[str, ...]
    remaining_kg: float

    @property
    def source_label(self) -> str:
        return self.stock_source or self.record_id


@dataclass(slots=True)
class _PendingOrder:
    record: OrderRecord
    due_date: date
    production_type: str
    market_type: str
    priority_key: tuple[object, ...]
    priority_label: str
    remaining_wontons: float
    original_outstanding_wontons: float
    outstanding_units: float
    outstanding_cups: float


def generate_plan(
    orders: Iterable[OrderRecord],
    assortment_records: Iterable[ActualAssortmentRecord],
    size_ranges: Iterable[AssortmentSizeRange],
    capacity_settings: CapacitySettings,
    class_definitions: Iterable[ClassDefinition],
    class_rules: Iterable[str],
    planning_date: date | None = None,
    wonton_weight_settings: WontonWeightSettings | None = None,
) -> PlanResult:
    """Generate a finite daily plan through the latest eligible order due date.

    Assumptions for the first planning model:
    - each M/S/SS class uses its configured wonton weight to convert RM kg;
    - blank order days are due on the final day of their month;
    - assortment lots become available on their saved date and carry forward;
    - orders may split across days and inventory lots.
    """

    start_date = planning_date or date.today()
    weight_settings = wonton_weight_settings or WontonWeightSettings()
    ranges = tuple(size_ranges)
    if not ranges:
        raise ValueError("Define and save the M/S/SS assortment ranges first.")

    raw_capacity, cooked_capacity = capacities_at_percentage(capacity_settings)
    if raw_capacity is None or cooked_capacity is None:
        raise ValueError("Set both raw and cooked daily capacity numbers first.")
    daily_capacity = {
        "RAW": float(raw_capacity),
        "COOKED": float(cooked_capacity),
    }
    if not any(value > 0 for value in daily_capacity.values()):
        raise ValueError("At least one available daily capacity must be greater than zero.")

    definitions = tuple(class_definitions)
    rules = tuple(rule.strip() for rule in class_rules if rule.strip())
    pending: list[_PendingOrder] = []
    unplanned: list[UnplannedOrder] = []
    skipped_past = 0

    for record in orders:
        due_date = order_due_date(record)
        if due_date < start_date:
            skipped_past += 1
            continue
        production_type = production_type_for_order(record)
        market_type = market_type_for_order(record, definitions)
        outstanding = outstanding_order_quantities(record)
        rm_size = normalize_size_class(record.rm_size)
        if rm_size in SKIPPED_RM_SIZES:
            unplanned.append(
                _unplanned(
                    record,
                    due_date,
                    production_type,
                    market_type,
                    outstanding[2],
                    "BK/HC excluded from this planning version.",
                )
            )
            continue
        if rm_size not in SUPPORTED_RM_SIZES:
            unplanned.append(
                _unplanned(
                    record,
                    due_date,
                    production_type,
                    market_type,
                    outstanding[2],
                    f"Unsupported RM size: {rm_size or '(blank)' }.",
                )
            )
            continue
        if production_type not in daily_capacity:
            unplanned.append(
                _unplanned(
                    record,
                    due_date,
                    production_type,
                    market_type,
                    outstanding[2],
                    "Group 2 is not Raw Wonton or Cooked Wonton.",
                )
            )
            continue
        if outstanding[2] <= EPSILON:
            continue
        priority_key, priority_label = priority_for_order(record, rules, definitions)
        pending.append(
            _PendingOrder(
                record=record,
                due_date=due_date,
                production_type=production_type,
                market_type=market_type,
                priority_key=(
                    due_date,
                    _market_priority(market_type),
                    _group_priority(record, "Group 1", definitions),
                    *priority_key,
                    record.record_id,
                ),
                priority_label=(
                    f"Load {due_date.isoformat()} > {market_display_label(market_type)} > "
                    f"Group 1 > {priority_label}"
                ),
                remaining_wontons=outstanding[2],
                original_outstanding_wontons=outstanding[2],
                outstanding_units=outstanding[0],
                outstanding_cups=outstanding[1],
            )
        )

    eligible_orders = len(pending)
    if not pending:
        return PlanResult(
            allocations=(),
            unplanned=tuple(unplanned),
            eligible_orders=0,
            skipped_past_orders=skipped_past,
            planned_wontons=0,
            used_rm_kg=0,
            start_date=start_date.isoformat(),
            end_date=start_date.isoformat(),
        )

    lots = _inventory_lots(assortment_records, ranges, weight_settings)
    horizon_end = max(item.due_date for item in pending)
    allocations: list[PlanAllocation] = []
    pending.sort(key=lambda item: item.priority_key)

    current_day = start_date
    while current_day <= horizon_end and any(item.remaining_wontons > EPSILON for item in pending):
        capacity_left = dict(daily_capacity)
        for item in pending:
            if item.remaining_wontons <= EPSILON:
                continue
            available_capacity = capacity_left[item.production_type]
            if available_capacity <= EPSILON:
                continue
            compatible = _compatible_lots(
                lots,
                normalize_size_class(item.record.rm_size),
                item.market_type,
                current_day,
            )
            material_wontons = sum(
                lot.remaining_kg * lot.wontons_per_kg for lot in compatible
            )
            planned_wontons = min(
                item.remaining_wontons,
                available_capacity,
                material_wontons,
            )
            if planned_wontons <= EPSILON:
                continue
            used_kg, sources = _consume_material(compatible, planned_wontons)
            item.remaining_wontons -= planned_wontons
            capacity_left[item.production_type] -= planned_wontons
            fraction = planned_wontons / item.original_outstanding_wontons
            allocations.append(
                PlanAllocation(
                    plan_date=current_day.isoformat(),
                    due_date=item.due_date.isoformat(),
                    order_no=item.record.order_no,
                    order_id=item.record.record_id,
                    customer=item.record.customer_name,
                    group_1=item.record.group_1,
                    production_type=item.production_type,
                    market_type=item.market_type,
                    rm_size=item.record.rm_size,
                    priority=item.priority_label,
                    order_cups=float(item.record.order_cups or 0),
                    order_wontons=float(item.record.total_wontons or 0),
                    planned_units=item.outstanding_units * fraction,
                    planned_cups=item.outstanding_cups * fraction,
                    planned_wontons=planned_wontons,
                    rm_kg=used_kg,
                    expected_wontons=max(item.remaining_wontons, 0),
                    rm_sources=", ".join(sources),
                    is_late=current_day > item.due_date,
                )
            )
        current_day += timedelta(days=1)

    for item in pending:
        if item.remaining_wontons <= EPSILON:
            continue
        future_compatible = [
            lot
            for lot in lots
            if normalize_size_class(item.record.rm_size) in lot.eligible_classes
            and lot.market_type == item.market_type
            and lot.remaining_kg > EPSILON
        ]
        if not future_compatible:
            reason = (
                f"Insufficient {market_display_label(item.market_type)} "
                f"{item.record.rm_size or '(blank)'} RM stock."
            )
        else:
            reason = "Daily capacity exhausted before the latest order load date."
        unplanned.append(
            _unplanned(
                item.record,
                item.due_date,
                item.production_type,
                item.market_type,
                item.remaining_wontons,
                reason,
            )
        )

    return PlanResult(
        allocations=tuple(allocations),
        unplanned=tuple(unplanned),
        eligible_orders=eligible_orders,
        skipped_past_orders=skipped_past,
        planned_wontons=sum(item.planned_wontons for item in allocations),
        used_rm_kg=sum(item.rm_kg for item in allocations),
        start_date=start_date.isoformat(),
        end_date=horizon_end.isoformat(),
    )


def order_due_date(record: OrderRecord) -> date:
    year = int(record.year)
    month = int(record.month)
    day_text = record.date.strip()
    day = int(day_text) if day_text else calendar.monthrange(year, month)[1]
    return date(year, month, day)


def production_type_for_order(record: OrderRecord) -> str:
    value = record.group_2.strip().casefold()
    if "raw" in value:
        return "RAW"
    if "cooked" in value:
        return "COOKED"
    return "UNKNOWN"


def market_type_for_order(
    record: OrderRecord,
    definitions: Iterable[ClassDefinition],
) -> str:
    """Map the Country master-data group to the order's RM market.

    Country group 1 is ต่างประเทศ and group 2 is ในประเทศ. Any missing or other
    value remains unassigned and can only consume unassigned RM.
    """

    group = _group_priority(record, "Country", definitions)
    if group == 1:
        return "export"
    if group == 2:
        return "domestic"
    return "unassigned"


def outstanding_order_quantities(record: OrderRecord) -> tuple[float, float, float]:
    """Return outstanding units, cups, and wontons after manual production."""

    produced_units = max(float(record.production or 0), 0)
    outstanding_units = max(float(record.order_unit) - produced_units, 0)
    if float(record.order_unit) <= EPSILON:
        return 0, 0, 0
    fraction = outstanding_units / float(record.order_unit)
    cups = float(record.order_cups or 0) * fraction
    wontons = float(record.total_wontons or 0) * fraction
    return outstanding_units, cups, wontons


def priority_for_order(
    record: OrderRecord,
    rules: Iterable[str],
    definitions: Iterable[ClassDefinition],
) -> tuple[tuple[int, ...], str]:
    """Return lexicographic numeric priority and a readable explanation."""

    lookup = {
        (item.class_value.casefold(), item.name.casefold()): _numeric_group(item.group)
        for item in definitions
    }
    groups: list[int] = []
    labels: list[str] = []
    for raw_rule in rules:
        field = _rule_field(raw_rule)
        if field == "rm":
            labels.append("RM available")
            continue
        if field is None:
            continue
        class_name, value = _order_class_value(record, field)
        group = lookup.get((class_name.casefold(), value.casefold()), MISSING_PRIORITY)
        groups.append(group)
        group_label = "unassigned" if group == MISSING_PRIORITY else f"G{group}"
        labels.append(f"{class_name} {group_label}")
    if not groups:
        groups.append(MISSING_PRIORITY)
    return tuple(groups), " > ".join(labels) if labels else "Due date"


def _inventory_lots(
    records: Iterable[ActualAssortmentRecord],
    ranges: tuple[AssortmentSizeRange, ...],
    wonton_weight_settings: WontonWeightSettings,
) -> list[_InventoryLot]:
    lots: list[_InventoryLot] = []
    for record in records:
        available_date = date.fromisoformat(record.record_date)
        for entry in record.entries:
            if entry.size_class:
                classes = tuple(
                    size_class
                    for size_class in (normalize_size_class(entry.size_class),)
                    if size_class in SUPPORTED_RM_SIZES
                )
            else:
                start, end = split_size_range(entry.size)
                classes = tuple(
                    value
                    for value in classify_size_range(start, end, ranges)
                    if value in SUPPORTED_RM_SIZES
                )
            if not classes:
                continue
            wontons_per_kg = wonton_weight_settings.wontons_per_kg(classes[0])
            lots.append(
                _InventoryLot(
                    available_date=available_date,
                    market_type=_normalize_market_type(record.market_type),
                    stock_source=record.source_label,
                    record_id=record.record_id,
                    size_range=entry.size,
                    wontons_per_kg=wontons_per_kg,
                    eligible_classes=classes,
                    remaining_kg=float(entry.weight),
                )
            )
    return lots


def _compatible_lots(
    lots: Iterable[_InventoryLot],
    rm_size: str,
    market_type: str,
    current_day: date,
) -> list[_InventoryLot]:
    target = normalize_size_class(rm_size)
    target_market = _normalize_market_type(market_type)
    return sorted(
        (
            lot
            for lot in lots
            if target in lot.eligible_classes
            and lot.market_type == target_market
            and lot.available_date <= current_day
            and lot.remaining_kg > EPSILON
        ),
        key=lambda lot: (
            len(lot.eligible_classes),
            lot.available_date,
            -lot.wontons_per_kg,
            lot.record_id,
            lot.size_range,
        ),
    )


def _consume_material(
    lots: Iterable[_InventoryLot],
    required_wontons: float,
) -> tuple[float, list[str]]:
    wontons_left = required_wontons
    total_kg = 0.0
    source_amounts: dict[str, float] = {}
    for lot in lots:
        if wontons_left <= EPSILON:
            break
        available_wontons = lot.remaining_kg * lot.wontons_per_kg
        used_wontons = min(wontons_left, available_wontons)
        used_kg = used_wontons / lot.wontons_per_kg
        lot.remaining_kg = max(lot.remaining_kg - used_kg, 0)
        wontons_left -= used_wontons
        total_kg += used_kg
        source_amounts[lot.source_label] = source_amounts.get(lot.source_label, 0) + used_kg
    sources = [
        f"{source_id}: {used_kg:,.2f} kg"
        for source_id, used_kg in source_amounts.items()
    ]
    return total_kg, sources


def _unplanned(
    record: OrderRecord,
    due_date: date,
    production_type: str,
    market_type: str,
    remaining_wontons: float,
    reason: str,
) -> UnplannedOrder:
    return UnplannedOrder(
        order_no=record.order_no,
        order_id=record.record_id,
        due_date=due_date.isoformat(),
        customer=record.customer_name,
        group_1=record.group_1,
        production_type=production_type,
        market_type=_normalize_market_type(market_type),
        rm_size=record.rm_size,
        remaining_wontons=remaining_wontons,
        reason=reason,
    )


def _numeric_group(value: str) -> int:
    try:
        numeric = float(value.strip())
    except ValueError:
        return MISSING_PRIORITY
    if not math.isfinite(numeric) or numeric < 0:
        return MISSING_PRIORITY
    return int(numeric)


def _group_priority(
    record: OrderRecord,
    class_name: str,
    definitions: Iterable[ClassDefinition],
) -> int:
    name_by_class = {
        "Country": record.country,
        "Group 1": record.group_1,
    }
    target_name = name_by_class[class_name].strip().casefold()
    for item in definitions:
        if (
            item.class_value.strip().casefold() == class_name.casefold()
            and item.name.strip().casefold() == target_name
        ):
            return _numeric_group(item.group)
    return MISSING_PRIORITY


def _market_priority(market_type: str) -> int:
    return {
        "export": 0,
        "domestic": 1,
        "unassigned": 2,
    }[_normalize_market_type(market_type)]


def _normalize_market_type(value: str) -> str:
    market_type = value.strip().casefold()
    return market_type if market_type in SUPPORTED_MARKETS else "unassigned"


def _rule_field(value: str) -> str | None:
    normalized = re.sub(r"[^a-z0-9ก-๙]+", "", value.casefold())
    aliases = {
        "rm": "rm",
        "rmsize": "rm",
        "country": "country",
        "customer": "customer",
        "group1": "group1",
        "group2": "group2",
        "packaging": "packaging",
        "soup": "soup",
        "ถ้วยunit": "cups_per_unit",
        "cupsunit": "cups_per_unit",
        "cupsperunit": "cups_per_unit",
    }
    return aliases.get(normalized)


def _order_class_value(record: OrderRecord, field: str) -> tuple[str, str]:
    if field == "country":
        return "Country", record.country
    if field == "customer":
        return "Customer", record.customer_name
    if field == "group1":
        return "Group 1", record.group_1
    if field == "group2":
        return "Group 2", record.group_2
    if field == "packaging":
        return "Packaging", record.packaging
    if field == "soup":
        return "Soup", record.soup
    if field == "cups_per_unit":
        ratio = "" if record.cups_per_unit is None else f"{record.cups_per_unit:.6f}".rstrip("0").rstrip(".")
        return "ถ้วย/Unit", ratio
    raise ValueError(f"Unknown priority field: {field}")
