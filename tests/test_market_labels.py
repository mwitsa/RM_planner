from __future__ import annotations

import unittest

from rm_planner.planning.market_labels import market_display_label, market_internal_value


class MarketLabelTests(unittest.TestCase):
    def test_displays_thai_market_labels_for_internal_values(self) -> None:
        self.assertEqual(market_display_label("domestic"), "ในประเทศ")
        self.assertEqual(market_display_label("export"), "ต่างประเทศ")

    def test_normalizes_thai_and_legacy_english_values_for_storage(self) -> None:
        self.assertEqual(market_internal_value("ในประเทศ"), "domestic")
        self.assertEqual(market_internal_value("ต่างประเทศ"), "export")
        self.assertEqual(market_internal_value("DOMESTIC"), "domestic")
        self.assertEqual(market_internal_value("EXPORT"), "export")

    def test_rejects_unknown_market_labels(self) -> None:
        with self.assertRaisesRegex(ValueError, "ในประเทศ or ต่างประเทศ"):
            market_internal_value("unknown")


if __name__ == "__main__":
    unittest.main()
