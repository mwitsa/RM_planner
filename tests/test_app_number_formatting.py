from __future__ import annotations

import unittest

from app import ProductionPlanApp
from rm_planner.planning.class_store import ClassDefinition


class AppNumberFormattingTests(unittest.TestCase):
    def test_optional_numbers_have_at_most_two_decimal_places(self) -> None:
        self.assertEqual(ProductionPlanApp._format_optional_number(277.777778), "277.78")
        self.assertEqual(ProductionPlanApp._format_optional_number(5000.0), "5,000")
        self.assertEqual(ProductionPlanApp._format_optional_number(5075.6), "5,075.6")

    def test_weights_have_at_most_two_decimal_places(self) -> None:
        self.assertEqual(ProductionPlanApp._format_weight(588.235294), "588.24")

    def test_cups_per_unit_class_name_is_rounded_for_display_only(self) -> None:
        definition = ClassDefinition(
            class_id="ratio",
            class_value="ถ้วย/Unit",
            name="4.714286",
            group="",
            created_at="2026-08-28T00:00:00+00:00",
            updated_at="2026-08-28T00:00:00+00:00",
        )

        self.assertEqual(
            ProductionPlanApp._format_class_name_for_display(definition),
            "4.71",
        )


if __name__ == "__main__":
    unittest.main()
