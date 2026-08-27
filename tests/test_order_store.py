from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from extractor import OrderRecord
from order_store import load_order_records, save_order_records


def sample_order(production: int | float | None = None) -> OrderRecord:
    return OrderRecord(
        date="",
        month="10",
        year="2026",
        country="USA",
        customer_name="Customer",
        group_1="Group 1",
        group_2="Group 2",
        packaging="130g*24",
        soup="Regular",
        order_volume=500,
        production=production,
        record_id="แผนผลิต:10",
    )


class OrderStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.store_path = Path(self.temporary_directory.name) / "orders.json"

    def test_missing_store_loads_empty(self) -> None:
        self.assertEqual(load_order_records(self.store_path), [])

    def test_round_trip_preserves_production_and_month_only_date(self) -> None:
        save_order_records(self.store_path, [sample_order(420.5)])
        loaded = load_order_records(self.store_path)

        self.assertEqual(len(loaded), 1)
        self.assertEqual(loaded[0].date, "")
        self.assertEqual(loaded[0].month, "10")
        self.assertEqual(loaded[0].production, 420.5)
        self.assertEqual(loaded[0].record_id, "แผนผลิต:10")

    def test_rejects_negative_production(self) -> None:
        with self.assertRaises(ValueError):
            save_order_records(self.store_path, [sample_order(-1)])


if __name__ == "__main__":
    unittest.main()
