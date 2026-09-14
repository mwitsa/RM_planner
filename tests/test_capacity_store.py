from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from rm_planner.planning.capacity_store import (
    CapacitySettings,
    capacities_at_percentage,
    load_capacity_settings,
    save_capacity_settings,
)


class CapacityStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.store_path = Path(self.temporary_directory.name) / "capacity.json"

    def test_missing_store_uses_independent_half_capacity_and_blank_numbers(self) -> None:
        self.assertEqual(load_capacity_settings(self.store_path), CapacitySettings())
        self.assertEqual(CapacitySettings().raw_percentage, 50)
        self.assertEqual(CapacitySettings().cooked_percentage, 50)

    def test_round_trip_preserves_percentage_and_wonton_numbers(self) -> None:
        saved = save_capacity_settings(
            self.store_path,
            CapacitySettings(
                raw_percentage=75,
                cooked_percentage=35,
                raw_wonton=12000,
                cooked_wonton=9500.5,
                raw_wonton_per_hour=1500,
                cooked_wonton_per_hour=1200,
                cooked_wonton_noodle_per_hour=900,
            ),
        )

        self.assertEqual(saved.raw_percentage, 75)
        self.assertEqual(saved.cooked_percentage, 35)
        self.assertEqual(load_capacity_settings(self.store_path), saved)
        payload = json.loads(self.store_path.read_text(encoding="utf-8"))
        self.assertEqual(payload["raw_percentage"], 75)
        self.assertEqual(payload["cooked_percentage"], 35)
        self.assertEqual(payload["cooked_wonton_noodle_per_hour"], 900)
        self.assertNotIn("percentage", payload)

    def test_reads_legacy_percentage_as_raw_share(self) -> None:
        self.store_path.write_text(
            json.dumps(
                {
                    "version": 1,
                    "percentage": 60,
                    "raw_wonton": 100000,
                    "cooked_wonton": 80000,
                }
            ),
            encoding="utf-8",
        )

        settings = load_capacity_settings(self.store_path)
        self.assertEqual(settings.raw_percentage, 60)
        self.assertEqual(settings.cooked_percentage, 40)
        self.assertEqual(capacities_at_percentage(settings), (60000, 32000))

    def test_reads_previous_raw_share_and_preserves_complementary_cooked_value(self) -> None:
        self.store_path.write_text(
            json.dumps(
                {
                    "version": 2,
                    "raw_percentage": 35,
                    "raw_wonton": 100000,
                    "cooked_wonton": 80000,
                }
            ),
            encoding="utf-8",
        )

        settings = load_capacity_settings(self.store_path)

        self.assertEqual(settings.raw_percentage, 35)
        self.assertEqual(settings.cooked_percentage, 65)
        self.assertEqual(capacities_at_percentage(settings), (35000, 52000))

    def test_calculates_independent_raw_and_cooked_capacity_percentages(self) -> None:
        settings = CapacitySettings(
            raw_percentage=100,
            cooked_percentage=100,
            raw_wonton=100000,
            cooked_wonton=80000,
        )

        self.assertEqual(capacities_at_percentage(settings, 37, 80), (37000, 64000))
        self.assertEqual(capacities_at_percentage(settings, 0, 100), (0, 80000))
        self.assertEqual(capacities_at_percentage(settings, 100, 0), (100000, 0))

    def test_calculated_capacity_remains_blank_without_base_number(self) -> None:
        self.assertEqual(
            capacities_at_percentage(CapacitySettings(), 50, 50),
            (None, None),
        )

    def test_rejects_percentage_outside_range_and_negative_numbers(self) -> None:
        with self.assertRaises(ValueError):
            save_capacity_settings(
                self.store_path,
                CapacitySettings(raw_percentage=101),
            )
        with self.assertRaises(ValueError):
            save_capacity_settings(
                self.store_path,
                CapacitySettings(cooked_percentage=-1),
            )
        with self.assertRaises(ValueError):
            save_capacity_settings(
                self.store_path,
                CapacitySettings(raw_wonton=-1),
            )


if __name__ == "__main__":
    unittest.main()
