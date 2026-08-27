from __future__ import annotations

import unittest

from extractor import OrderRecord
from order_filters import (
    ALL_FILTER,
    BLANK_FILTER,
    PRODUCTION_ENTERED,
    PRODUCTION_MISSING,
    filter_options,
    filter_orders,
)


def order(
    record_id: str,
    year: str,
    month: str,
    country: str,
    soup: str,
    production: int | None,
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
        soup=soup,
        order_volume=100,
        production=production,
        record_id=record_id,
    )


class OrderFilterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.records = [
            order("1", "2025", "10", "USA", "Regular", None),
            order("2", "2025", "10", "UK", "", 80),
            order("3", "2026", "01", "USA", "Regular", 100),
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


if __name__ == "__main__":
    unittest.main()
