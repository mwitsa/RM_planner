from __future__ import annotations

import unittest

from extractor import OrderRecord
from order_filters import (
    ALL_FILTER,
    BLANK_FILTER,
    PRODUCTION_ENTERED,
    PRODUCTION_MISSING,
    cascading_filter_state,
    filter_options,
    filter_orders,
    sort_orders,
)


def order(
    record_id: str,
    year: str,
    month: str,
    country: str,
    soup: str,
    production: int | None,
    cups_per_unit: float | None = 16,
    rm_size: str = "M",
) -> OrderRecord:
    return OrderRecord(
        date="",
        month=month,
        year=year,
        country=country,
        customer_name="Customer",
        group_1="G1",
        group_2="G2",
        packaging="Pack",
        rm_size=rm_size,
        soup=soup,
        order_unit=100,
        order_cups=1600,
        cups_per_unit=cups_per_unit,
        production=production,
        record_id=record_id,
    )


class OrderFilterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.records = [
            order("1", "2025", "10", "USA", "Regular", None, 16, "M"),
            order("2", "2025", "10", "UK", "", 80, 4.714285714285714, "S"),
            order("3", "2026", "01", "USA", "Regular", 100, None, "S"),
        ]

    def test_combines_multiple_filters(self) -> None:
        filtered = filter_orders(
            self.records,
            {"year": "2025", "country": "USA", "soup": ALL_FILTER},
        )
        self.assertEqual([record.record_id for record in filtered], ["1"])

    def test_filters_production_status(self) -> None:
        entered = filter_orders(self.records, {"production_status": PRODUCTION_ENTERED})
        missing = filter_orders(self.records, {"production_status": PRODUCTION_MISSING})
        self.assertEqual([record.record_id for record in entered], ["2", "3"])
        self.assertEqual([record.record_id for record in missing], ["1"])

    def test_options_include_blank_and_unique_values(self) -> None:
        self.assertEqual(filter_options(self.records, "country"), ["UK", "USA"])
        self.assertEqual(filter_options(self.records, "soup"), ["Regular", BLANK_FILTER])
        self.assertEqual(
            filter_options(self.records, "cups_per_unit"),
            ["4.71", "16", BLANK_FILTER],
        )

    def test_filters_cups_per_unit(self) -> None:
        filtered = filter_orders(self.records, {"cups_per_unit": "4.71"})
        blank = filter_orders(self.records, {"cups_per_unit": BLANK_FILTER})
        self.assertEqual([record.record_id for record in filtered], ["2"])
        self.assertEqual([record.record_id for record in blank], ["3"])

    def test_filters_rm_size(self) -> None:
        filtered = filter_orders(self.records, {"rm_size": "S"})
        self.assertEqual([record.record_id for record in filtered], ["2", "3"])

    def test_cascading_options_follow_other_selections(self) -> None:
        selections, options = cascading_filter_state(
            self.records,
            {"country": ALL_FILTER, "rm_size": "S", "year": ALL_FILTER},
            ("country", "rm_size", "year"),
            preferred_key="rm_size",
        )

        self.assertEqual(selections["rm_size"], "S")
        self.assertEqual(options["country"], ["UK", "USA"])
        self.assertEqual(options["year"], ["2025", "2026"])
        self.assertEqual(options["rm_size"], ["M", "S"])

    def test_cascading_filters_reset_conflict_but_keep_latest_selection(self) -> None:
        selections, options = cascading_filter_state(
            self.records,
            {"country": "UK", "rm_size": "M"},
            ("country", "rm_size"),
            preferred_key="rm_size",
        )

        self.assertEqual(selections, {"country": ALL_FILTER, "rm_size": "M"})
        self.assertEqual(options["country"], ["USA"])

    def test_sorts_numeric_columns_largest_to_lowest(self) -> None:
        self.records[0].order_unit = 100
        self.records[1].order_unit = 300
        self.records[2].order_unit = 200

        sorted_records = sort_orders(self.records, "order_unit", descending=True)

        self.assertEqual([record.record_id for record in sorted_records], ["2", "3", "1"])

    def test_sorts_derived_total_wontons_numerically(self) -> None:
        self.records[0].wontons_per_cup = 8
        self.records[1].wontons_per_cup = 12
        self.records[2].wontons_per_cup = None

        sorted_records = sort_orders(self.records, "total_wontons", descending=True)

        self.assertEqual([record.record_id for record in sorted_records], ["2", "1", "3"])

    def test_sorts_text_case_insensitively_and_keeps_blanks_last(self) -> None:
        self.records[0].customer_name = "zeta"
        self.records[1].customer_name = "Alpha"
        self.records[2].customer_name = "beta"
        self.records[0].production = None
        self.records[1].production = 80
        self.records[2].production = 100

        by_customer = sort_orders(self.records, "customer")
        by_production = sort_orders(self.records, "production", descending=True)

        self.assertEqual([record.record_id for record in by_customer], ["2", "3", "1"])
        self.assertEqual([record.record_id for record in by_production], ["3", "2", "1"])


if __name__ == "__main__":
    unittest.main()
