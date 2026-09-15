from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from rm_planner.planning.chill_days_store import load_chill_days, save_chill_days


class ChillDaysStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.store_path = Path(self.temporary_directory.name) / "chill_days.json"

    def test_missing_store_defaults_to_zero_days(self) -> None:
        self.assertEqual(load_chill_days(self.store_path), 0)

    def test_round_trip_preserves_a_whole_number_of_days(self) -> None:
        self.assertEqual(save_chill_days(self.store_path, 5), 5)
        self.assertEqual(load_chill_days(self.store_path), 5)

    def test_rejects_negative_or_non_integer_values(self) -> None:
        for value in (-1, 1.5, "5", True):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    save_chill_days(self.store_path, value)


if __name__ == "__main__":
    unittest.main()
