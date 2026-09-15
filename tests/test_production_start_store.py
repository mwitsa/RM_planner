from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from rm_planner.planning.production_start_store import (
    ProductionStartSettings,
    hour_from_time_label,
    load_production_start_settings,
    production_time_options,
    save_production_start_settings,
)


class ProductionStartStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.store_path = Path(self.temporary_directory.name) / "production_start_times.json"

    def test_missing_store_uses_the_current_line_start_defaults(self) -> None:
        self.assertEqual(
            load_production_start_settings(self.store_path),
            ProductionStartSettings(cooked_hour=18, raw_hour=19),
        )

    def test_saves_and_loads_both_line_start_times(self) -> None:
        settings = save_production_start_settings(
            self.store_path,
            ProductionStartSettings(cooked_hour=17, raw_hour=20),
        )

        self.assertEqual(settings, ProductionStartSettings(cooked_hour=17, raw_hour=20))
        self.assertEqual(load_production_start_settings(self.store_path), settings)

    def test_off_window_hours_are_rejected(self) -> None:
        for hour in (5, 9, 12, 15):
            with self.subTest(hour=hour):
                with self.assertRaises(ValueError):
                    save_production_start_settings(
                        self.store_path,
                        ProductionStartSettings(cooked_hour=hour, raw_hour=19),
                    )

    def test_ui_time_options_follow_the_visible_timeline_window(self) -> None:
        self.assertEqual(production_time_options()[0], "16:00")
        self.assertEqual(production_time_options()[-1], "04:00")
        self.assertEqual(hour_from_time_label("00:00"), 0)
        with self.assertRaises(ValueError):
            hour_from_time_label("18:30")


if __name__ == "__main__":
    unittest.main()
