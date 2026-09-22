from __future__ import annotations

import unittest

from rm_planner.ui.common import RM_NAVIGATION_ITEMS, rm_navigation_section


class AppRmNavigationTests(unittest.TestCase):
    def test_update_stock_is_nested_under_stock_navigation(self) -> None:
        self.assertEqual(
            RM_NAVIGATION_ITEMS,
            (
                ("timeline", "Stock"),
                ("data", "อัพโหลดข้อมูล STOCK On Hand"),
                ("pd_actual", "อัพโหลดข้อมูล STOCK แกลง 2"),
                ("pd", "PD Freeze"),
                ("pd_actual_pivot", "Pivot STOCK แกลง 2"),
                ("predict", "Assortment STD"),
            ),
        )
        self.assertEqual(rm_navigation_section("actual"), "timeline")
        self.assertEqual(rm_navigation_section("predict"), "predict")
        # The two upload pages, PD Freeze, and the STOCK แกลง 2 pivot are
        # their own top-level nav items, unlike the nested stock editor.
        self.assertEqual(rm_navigation_section("data"), "data")
        self.assertEqual(rm_navigation_section("pd_actual"), "pd_actual")
        self.assertEqual(rm_navigation_section("pd"), "pd")
        self.assertEqual(rm_navigation_section("pd_actual_pivot"), "pd_actual_pivot")


if __name__ == "__main__":
    unittest.main()
