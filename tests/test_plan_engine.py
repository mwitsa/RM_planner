from __future__ import annotations

import unittest
from datetime import date

from assortment_actual_store import ActualAssortmentEntry, ActualAssortmentRecord
from assortment_range_store import AssortmentSizeRange
from capacity_store import CapacitySettings
from class_store import ClassDefinition
from extractor import OrderRecord
from plan_engine import generate_plan, market_type_for_order, order_due_date, priority_for_order
from wonton_weight_store import WontonWeightSettings


RANGES = (
    AssortmentSizeRange("M", "46-50", "56-60"),
    AssortmentSizeRange("S+", "61-65", "81-85"),
)


def order(
    record_id: str,
    *,
    day: str = "30",
    month: str = "08",
    year: str = "2026",
    rm_size: str = "M",
    group_2: str = "Cooked Wonton",
    country: str = "AUS",
    group_1: str = "Wonton",
    order_cups: float = 100,
    wontons_per_cup: float = 10,
    order_unit: float = 10,
    production: float | None = None,
) -> OrderRecord:
    return OrderRecord(
        date=day,
        month=month,
        year=year,
        country=country,
        customer_name=f"Customer {record_id}",
        group_1=group_1,
        group_2=group_2,
        packaging="Pack",
        rm_size=rm_size,
        soup="Regular",
        wontons_per_cup=wontons_per_cup,
        order_unit=order_unit,
        order_cups=order_cups,
        cups_per_unit=order_cups / order_unit,
        production=production,
        record_id=record_id,
    )


def stock(
    entries: tuple[tuple[str, float], ...],
    *,
    record_date: str = "2026-08-28",
    record_type: str = "actual",
    market_type: str = "unassigned",
    record_id: str = "stock-1",
    rm_id: str = "RM-000001",
    farm_name: str = "",
    lot: str = "",
) -> ActualAssortmentRecord:
    return ActualAssortmentRecord(
        record_id=record_id,
        record_date=record_date,
        entries=tuple(ActualAssortmentEntry(size, weight) for size, weight in entries),
        record_type=record_type,
        created_at="2026-08-28T00:00:00+00:00",
        updated_at="2026-08-28T00:00:00+00:00",
        rm_id=rm_id,
        market_type=market_type,
        farm_name=farm_name,
        lot=lot,
    )


def class_definition(class_value: str, name: str, group: str) -> ClassDefinition:
    return ClassDefinition(
        class_id=f"{class_value}:{name}",
        class_value=class_value,
        name=name,
        group=group,
        created_at="2026-08-28T00:00:00+00:00",
        updated_at="2026-08-28T00:00:00+00:00",
    )


def balanced_capacity(raw_wonton: float, cooked_wonton: float) -> CapacitySettings:
    """Build independent full-utilization limits for both production types."""

    return CapacitySettings(
        raw_percentage=100,
        cooked_percentage=100,
        raw_wonton=raw_wonton,
        cooked_wonton=cooked_wonton,
    )


class PlanEngineTests(unittest.TestCase):
    def test_legacy_stock_type_does_not_change_lot_priority(self) -> None:
        result = generate_plan(
            [
                order(
                    "one-order",
                    order_cups=530,
                    wontons_per_cup=1,
                    order_unit=530,
                )
            ],
            [
                stock(
                    (("51-55", 20),),
                    record_type="actual",
                    record_id="z-actual",
                    rm_id="RM-ACTUAL",
                ),
                stock(
                    (("51-55", 20),),
                    record_type="prediction",
                    record_id="a-prediction",
                    rm_id="RM-PREDICTION",
                ),
            ],
            RANGES,
            balanced_capacity(1000, 1000),
            [],
            [],
            planning_date=date(2026, 8, 28),
        )

        self.assertEqual(len(result.allocations), 1)
        self.assertEqual(result.allocations[0].rm_sources, "RM-PREDICTION: 10.00 kg")

    def test_month_only_order_is_due_on_last_day(self) -> None:
        self.assertEqual(order_due_date(order("a", day="", month="02")), date(2026, 2, 28))

    def test_configured_wonton_weight_converts_stock_kg_to_wontons(self) -> None:
        class_stock = ActualAssortmentRecord(
            record_id="class-stock",
            rm_id="RM-CLASS",
            record_date="2026-08-28",
            entries=(ActualAssortmentEntry("M", 1, size_class="M"),),
            record_type="actual",
            market_type="unassigned",
            created_at="2026-08-28T00:00:00+00:00",
            updated_at="2026-08-28T00:00:00+00:00",
        )
        result = generate_plan(
            [order("a", rm_size="M", order_cups=200, wontons_per_cup=1, order_unit=200)],
            [class_stock],
            RANGES,
            balanced_capacity(1000, 1000),
            [],
            [],
            planning_date=date(2026, 8, 28),
            wonton_weight_settings=WontonWeightSettings(m_grams=8.6),
        )

        self.assertEqual(len(result.allocations), 1)
        self.assertAlmostEqual(result.allocations[0].planned_wontons, 1000 / 8.6)
        self.assertAlmostEqual(result.allocations[0].rm_kg, 1)
        self.assertEqual(result.allocations[0].rm_size, "M")

    def test_plan_source_uses_manually_entered_farm_and_lot(self) -> None:
        result = generate_plan(
            [order("a", order_cups=100, wontons_per_cup=1, order_unit=100)],
            [
                stock(
                    (("51-55", 10),),
                    farm_name="Farm A",
                    lot="LOT-42",
                )
            ],
            RANGES,
            balanced_capacity(1000, 1000),
            [],
            [],
            planning_date=date(2026, 8, 28),
        )

        self.assertEqual(result.allocations[0].rm_sources, "Farm A / LOT-42: 1.89 kg")

    def test_order_can_split_over_multiple_capacity_days(self) -> None:
        result = generate_plan(
            [order("a", day="31", order_cups=250, wontons_per_cup=1, order_unit=250)],
            [stock((("51-55", 10),))],
            RANGES,
            balanced_capacity(100, 100),
            [],
            [],
            planning_date=date(2026, 8, 28),
        )

        self.assertEqual([row.planned_wontons for row in result.allocations], [100, 100, 50])
        self.assertEqual([row.expected_wontons for row in result.allocations], [150, 50, 0])
        self.assertEqual([row.plan_date for row in result.allocations], ["2026-08-28", "2026-08-29", "2026-08-30"])

    def test_shared_s_plus_stock_is_not_counted_twice(self) -> None:
        result = generate_plan(
            [
                order("s", rm_size="S", order_cups=650, wontons_per_cup=1, order_unit=650),
                order("ss", rm_size="SS", order_cups=650, wontons_per_cup=1, order_unit=650),
            ],
            [stock((("61-69", 10),))],
            RANGES,
            balanced_capacity(5000, 5000),
            [],
            [],
            planning_date=date(2026, 8, 28),
            wonton_weight_settings=WontonWeightSettings(s_plus_grams=1000 / 65),
        )

        self.assertAlmostEqual(result.planned_wontons, 650)
        self.assertEqual(len(result.unplanned), 1)
        self.assertEqual(result.allocations[0].rm_size, "S")
        self.assertEqual(result.unplanned[0].rm_size, "SS")
        self.assertIn("SS RM stock", result.unplanned[0].reason)
        self.assertIn("Insufficient", result.unplanned[0].reason)

    def test_s_and_ss_orders_share_s_plus_stock_without_changing_order_values(self) -> None:
        orders = [
            order("a-ss", rm_size="SS", order_cups=650, wontons_per_cup=1, order_unit=650),
            order("z-s", rm_size="S", order_cups=650, wontons_per_cup=1, order_unit=650),
        ]
        result = generate_plan(
            orders,
            [stock((("71-75", 10), ("61-65", 10)))],
            RANGES,
            balanced_capacity(5000, 5000),
            [],
            [],
            planning_date=date(2026, 8, 28),
            wonton_weight_settings=WontonWeightSettings(s_plus_grams=1000 / 65),
        )

        self.assertAlmostEqual(result.planned_wontons, 1300)
        self.assertEqual(len(result.unplanned), 0)
        self.assertEqual([record.rm_size for record in orders], ["SS", "S"])
        self.assertEqual({row.rm_size for row in result.allocations}, {"S", "SS"})
        self.assertEqual(result.allocations[0].rm_sources, "RM-000001: 10.00 kg")
        self.assertEqual(result.allocations[1].rm_sources, "RM-000001: 10.00 kg")

    def test_future_stock_is_not_consumed_before_its_saved_date(self) -> None:
        result = generate_plan(
            [order("a", day="31", order_cups=100, wontons_per_cup=1, order_unit=100)],
            [stock((("51-55", 10),), record_date="2026-08-30")],
            RANGES,
            balanced_capacity(5000, 5000),
            [],
            [],
            planning_date=date(2026, 8, 28),
        )

        self.assertEqual(result.allocations[0].plan_date, "2026-08-30")

    def test_class_rules_apply_lower_group_first(self) -> None:
        definitions = [
            class_definition("Country", "AUS", "2"),
            class_definition("Country", "USA", "1"),
        ]
        first_key, _ = priority_for_order(order("aus", country="AUS"), ["RM", "country"], definitions)
        second_key, _ = priority_for_order(order("usa", country="USA"), ["RM", "country"], definitions)
        self.assertLess(second_key, first_key)

    def test_due_date_is_protected_before_class_priority(self) -> None:
        definitions = [
            class_definition("Country", "LOWER-CLASS-PRIORITY", "2"),
            class_definition("Country", "HIGHER-CLASS-PRIORITY", "1"),
        ]
        urgent = order(
            "urgent",
            day="28",
            country="LOWER-CLASS-PRIORITY",
            order_cups=100,
            wontons_per_cup=1,
            order_unit=100,
        )
        later = order(
            "later",
            day="29",
            country="HIGHER-CLASS-PRIORITY",
            order_cups=100,
            wontons_per_cup=1,
            order_unit=100,
        )

        result = generate_plan(
            [later, urgent],
            [
                stock((("51-55", 2),), market_type="domestic", record_id="domestic-rm", rm_id="RM-DOMESTIC"),
                stock((("51-55", 2),), market_type="export", record_id="export-rm", rm_id="RM-EXPORT"),
            ],
            RANGES,
            balanced_capacity(100, 100),
            definitions,
            ["RM", "country"],
            planning_date=date(2026, 8, 28),
        )

        self.assertEqual(
            [(row.order_id, row.plan_date, row.is_late) for row in result.allocations],
            [
                ("urgent", "2026-08-28", False),
                ("later", "2026-08-29", False),
            ],
        )

    def test_country_group_maps_order_to_export_or_domestic(self) -> None:
        definitions = [
            class_definition("Country", "USA", "1"),
            class_definition("Country", "7-11", "2"),
        ]

        self.assertEqual(market_type_for_order(order("export", country="USA"), definitions), "export")
        self.assertEqual(market_type_for_order(order("domestic", country="7-11"), definitions), "domestic")
        self.assertEqual(market_type_for_order(order("unknown", country="?"), definitions), "unassigned")

    def test_export_precedes_domestic_even_when_export_group1_is_lower_priority(self) -> None:
        definitions = [
            class_definition("Country", "EXPORT", "1"),
            class_definition("Country", "DOMESTIC", "2"),
            class_definition("Group 1", "Allergen", "2"),
            class_definition("Group 1", "Non-allergen", "1"),
        ]
        export = order(
            "export",
            country="EXPORT",
            group_1="Allergen",
            order_cups=100,
            wontons_per_cup=1,
            order_unit=100,
        )
        domestic = order(
            "domestic",
            country="DOMESTIC",
            group_1="Non-allergen",
            order_cups=100,
            wontons_per_cup=1,
            order_unit=100,
        )
        result = generate_plan(
            [domestic, export],
            [
                stock((("51-55", 2),), market_type="export", record_id="export-rm", rm_id="RM-EXPORT"),
                stock((("51-55", 2),), market_type="domestic", record_id="domestic-rm", rm_id="RM-DOMESTIC"),
            ],
            RANGES,
            balanced_capacity(100, 100),
            definitions,
            ["group1"],
            planning_date=date(2026, 8, 28),
        )

        self.assertEqual(
            [(row.order_id, row.market_type, row.plan_date) for row in result.allocations],
            [
                ("export", "export", "2026-08-28"),
                ("domestic", "domestic", "2026-08-29"),
            ],
        )

    def test_export_and_domestic_rm_cannot_cross(self) -> None:
        definitions = [
            class_definition("Country", "EXPORT", "1"),
            class_definition("Country", "DOMESTIC", "2"),
        ]
        result = generate_plan(
            [
                order("export", country="EXPORT", order_cups=100, wontons_per_cup=1, order_unit=100),
                order("domestic", country="DOMESTIC", order_cups=100, wontons_per_cup=1, order_unit=100),
            ],
            [stock((("51-55", 2),), market_type="domestic")],
            RANGES,
            balanced_capacity(5000, 5000),
            definitions,
            [],
            planning_date=date(2026, 8, 28),
        )

        self.assertEqual([(row.order_id, row.market_type) for row in result.allocations], [("domestic", "domestic")])
        self.assertEqual(len(result.unplanned), 1)
        self.assertEqual(result.unplanned[0].order_id, "export")
        self.assertIn("ต่างประเทศ M RM", result.unplanned[0].reason)

    def test_legacy_existing_small_stock_is_shared_as_s_plus(self) -> None:
        definitions = [class_definition("Country", "DOMESTIC", "2")]
        existing = ActualAssortmentRecord(
            record_id="existing-1",
            rm_id="RM-OPENING",
            record_date="2026-08-20",
            entries=(
                ActualAssortmentEntry(
                    "S",
                    10,
                    size_class="S",
                    pieces_per_kg=999,
                ),
            ),
            record_type="existing",
            market_type="domestic",
            created_at="2026-08-20T00:00:00+00:00",
            updated_at="2026-08-20T00:00:00+00:00",
        )
        result = generate_plan(
            [
                order(
                    "s-order",
                    country="DOMESTIC",
                    rm_size="S",
                    order_cups=650,
                    wontons_per_cup=1,
                    order_unit=650,
                ),
                order(
                    "ss-order",
                    country="DOMESTIC",
                    rm_size="SS",
                    order_cups=650,
                    wontons_per_cup=1,
                    order_unit=650,
                ),
            ],
            [existing],
            RANGES,
            balanced_capacity(5000, 5000),
            definitions,
            [],
            planning_date=date(2026, 8, 28),
            wonton_weight_settings=WontonWeightSettings(s_plus_grams=1000 / 65),
        )

        self.assertEqual([(row.order_id, row.rm_sources) for row in result.allocations], [("s-order", "RM-OPENING: 10.00 kg")])
        self.assertEqual([row.order_id for row in result.unplanned], ["ss-order"])

    def test_existing_production_reduces_outstanding_order(self) -> None:
        result = generate_plan(
            [order("a", order_cups=100, wontons_per_cup=10, order_unit=10, production=5)],
            [stock((("51-55", 20),))],
            RANGES,
            balanced_capacity(5000, 5000),
            [],
            [],
            planning_date=date(2026, 8, 28),
        )

        self.assertAlmostEqual(result.planned_wontons, 500)
        self.assertAlmostEqual(result.allocations[0].planned_units, 5)

    def test_direct_unused_class_is_never_available_to_plan(self) -> None:
        unused = ActualAssortmentRecord(
            record_id="unused-1",
            rm_id="RM-UNUSED",
            record_date="2026-08-28",
            entries=(
                ActualAssortmentEntry("Unused", 100, size_class="Unused"),
            ),
            record_type="actual",
            market_type="unassigned",
            created_at="2026-08-28T00:00:00+00:00",
            updated_at="2026-08-28T00:00:00+00:00",
        )
        result = generate_plan(
            [order("a", order_cups=100, wontons_per_cup=1, order_unit=100)],
            [unused],
            RANGES,
            balanced_capacity(5000, 5000),
            [],
            [],
            planning_date=date(2026, 8, 28),
        )

        self.assertEqual(result.allocations, ())
        self.assertEqual(len(result.unplanned), 1)
        self.assertIn("Insufficient", result.unplanned[0].reason)

    def test_past_orders_are_ignored_and_bk_hc_are_explained(self) -> None:
        result = generate_plan(
            [
                order("past", day="27"),
                order("bk", rm_size="BK"),
                order("hc", rm_size="HC"),
            ],
            [stock((("51-55", 20),))],
            RANGES,
            balanced_capacity(5000, 5000),
            [],
            [],
            planning_date=date(2026, 8, 28),
        )

        self.assertEqual(result.skipped_past_orders, 1)
        self.assertEqual(len(result.unplanned), 2)
        self.assertTrue(all("BK/HC" in row.reason for row in result.unplanned))


if __name__ == "__main__":
    unittest.main()
