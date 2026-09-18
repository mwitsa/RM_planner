"""Tests for persisted labour settings."""

from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from rm_planner.planning.labour_store import (
    LabourSettings,
    load_labour_settings,
    save_labour_settings,
)


class LabourStoreTests(unittest.TestCase):
    def test_missing_file_uses_zero_defaults(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            settings = load_labour_settings(Path(temporary_directory) / "labour.json")

        self.assertEqual(settings, LabourSettings())

    def test_round_trip_normalizes_values(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            path = Path(temporary_directory) / "labour.json"
            saved = save_labour_settings(
                path,
                LabourSettings(
                    raw_labour="4",
                    raw_wage="525.50",
                    cooked_labour=6,
                    cooked_wage=600,
                ),
            )
            loaded = load_labour_settings(path)

        self.assertEqual(saved, LabourSettings(4, 525.5, 6, 600.0))
        self.assertEqual(loaded, saved)

    def test_rejects_fractional_labour_count(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            path = Path(temporary_directory) / "labour.json"
            with self.assertRaisesRegex(ValueError, "Raw labour"):
                save_labour_settings(path, LabourSettings(raw_labour=1.5))


if __name__ == "__main__":
    unittest.main()
