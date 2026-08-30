from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from capacity_store import (
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

    def test_missing_store_uses_balanced_split_and_blank_numbers(self) -> None:
        self.assertEqual(load_capacity_settings(self.store_path), CapacitySettings())
        self.assertEqual(CapacitySettings().percentage, 50)

    def test_round_trip_preserves_percentage_and_wonton_numbers(self) -> None:
        saved = save_capacity_settings(
            self.store_path,
            CapacitySettings(percentage=75, raw_wonton=12000, cooked_wonton=9500.5),
        )

        self.assertEqual(saved.percentage, 75)
        self.assertEqual(load_capacity_settings(self.store_path), saved)
        payload = json.loads(self.store_path.read_text(encoding="utf-8"))
        self.assertEqual(payload["raw_percentage"], 75)
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
        self.assertEqual(settings.percentage, 60)
        self.assertEqual(capacities_at_percentage(settings), (60000, 32000))

    def test_calculates_complementary_raw_and_cooked_capacity_split(self) -> None:
        settings = CapacitySettings(
            percentage=100,
            raw_wonton=100000,
            cooked_wonton=80000,
        )

        self.assertEqual(capacities_at_percentage(settings, 37), (37000, 50400))
        self.assertEqual(capacities_at_percentage(settings, 0), (0, 80000))
        self.assertEqual(capacities_at_percentage(settings, 100), (100000, 0))

    def test_calculated_capacity_remains_blank_without_base_number(self) -> None:
        self.assertEqual(
            capacities_at_percentage(CapacitySettings(percentage=50), 50),
            (None, None),
        )

    def test_rejects_percentage_outside_range_and_negative_numbers(self) -> None:
        with self.assertRaises(ValueError):
            save_capacity_settings(self.store_path, CapacitySettings(percentage=101))
        with self.assertRaises(ValueError):
            save_capacity_settings(
                self.store_path,
                CapacitySettings(percentage=50, raw_wonton=-1),
            )


if __name__ == "__main__":
    unittest.main()
