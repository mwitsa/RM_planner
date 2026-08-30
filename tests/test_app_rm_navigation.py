from __future__ import annotations

import unittest

from app import RM_NAVIGATION_ITEMS, rm_navigation_section


class AppRmNavigationTests(unittest.TestCase):
    def test_update_stock_is_nested_under_stock_navigation(self) -> None:
        self.assertEqual(
            RM_NAVIGATION_ITEMS,
            (("timeline", "Stock"), ("predict", "Assortment STD")),
        )
        self.assertEqual(rm_navigation_section("actual"), "timeline")
        self.assertEqual(rm_navigation_section("predict"), "predict")


if __name__ == "__main__":
    unittest.main()
