from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from wonton_weight_store import (
    WontonWeightSettings,
    load_wonton_weight_settings,
    save_wonton_weight_settings,
)


class WontonWeightStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.store_path = Path(self.temporary_directory.name) / "wonton_weights.json"

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def test_m_weight_of_8_point_6_grams_yields_expected_wontons(self) -> None:
        settings = WontonWeightSettings(m_grams=8.6, s_plus_grams=10)

        self.assertAlmostEqual(settings.wontons_per_kg("M"), 116.2790697674)
        self.assertAlmostEqual(settings.estimate_wontons("M", 1), 116.2790697674)

    def test_round_trip_preserves_both_class_weights(self) -> None:
        saved = WontonWeightSettings(m_grams=8.6, s_plus_grams=7.5)
        save_wonton_weight_settings(self.store_path, saved)

        self.assertEqual(load_wonton_weight_settings(self.store_path), saved)

    def test_missing_store_uses_positive_compatible_defaults(self) -> None:
        settings = load_wonton_weight_settings(self.store_path)

        self.assertAlmostEqual(settings.wontons_per_kg("M"), 53)
        self.assertAlmostEqual(settings.wontons_per_kg("S+"), 69.25)

    def test_rejects_nonpositive_or_unknown_weights(self) -> None:
        with self.assertRaisesRegex(ValueError, "greater than zero"):
            WontonWeightSettings(m_grams=0, s_plus_grams=10)
        with self.assertRaisesRegex(ValueError, "not defined"):
            WontonWeightSettings().grams_for("Unused")


if __name__ == "__main__":
    unittest.main()
