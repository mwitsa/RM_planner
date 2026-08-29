from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from extractor import OrderRecord
from order_store import load_order_records, merge_order_records, save_order_records


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
        rm_size="M",
        soup="Regular",
        order_unit=500,
        order_cups=8000,
        cups_per_unit=16,
        wontons_per_cup=8,
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
        self.assertEqual(loaded[0].order_unit, 500)
        self.assertEqual(loaded[0].order_cups, 8000)
        self.assertEqual(loaded[0].cups_per_unit, 16)
        self.assertEqual(loaded[0].wontons_per_cup, 8)
        self.assertEqual(loaded[0].total_wontons, 64000)
        self.assertEqual(loaded[0].production, 420.5)
        self.assertEqual(loaded[0].record_id, "แผนผลิต:10")
        self.assertEqual(loaded[0].order_no, "ORD-000001")

    def test_rejects_negative_production(self) -> None:
        with self.assertRaises(ValueError):
            save_order_records(self.store_path, [sample_order(-1)])

    def test_incremental_merge_adds_only_new_record_ids(self) -> None:
        existing = sample_order(420)
        save_order_records(self.store_path, [existing])
        duplicate = sample_order(None)
        new_order = sample_order(None)
        new_order.record_id = "แผนผลิต:11"
        new_order.customer_name = "New Customer"

        merged, added = merge_order_records(
            self.store_path,
            [duplicate, new_order],
        )
        merged_again, added_again = merge_order_records(
            self.store_path,
            [duplicate, new_order],
        )

        self.assertEqual(added, 1)
        self.assertEqual(added_again, 0)
        self.assertEqual(len(merged), 2)
        self.assertEqual(len(merged_again), 2)
        self.assertEqual(merged[0].production, 420)
        self.assertEqual(merged[1].customer_name, "New Customer")
        self.assertEqual(
            [record.order_no for record in merged],
            ["ORD-000001", "ORD-000002"],
        )
        self.assertEqual(
            [record.order_no for record in merged_again],
            ["ORD-000001", "ORD-000002"],
        )

    def test_incremental_merge_compares_content_when_source_row_is_reused(self) -> None:
        existing = sample_order(420)
        save_order_records(self.store_path, [existing])
        changed_row = sample_order(None)
        changed_row.customer_name = "Replacement Order"

        merged, added = merge_order_records(self.store_path, [changed_row])

        self.assertEqual(added, 1)
        self.assertEqual(len(merged), 2)
        self.assertEqual(merged[0].record_id, "แผนผลิต:10")
        self.assertNotEqual(merged[1].record_id, "แผนผลิต:10")
        self.assertEqual(merged[1].customer_name, "Replacement Order")

    def test_incremental_merge_ignores_existing_content_from_a_different_row(self) -> None:
        existing = sample_order(420)
        save_order_records(self.store_path, [existing])
        duplicate_content = sample_order(None)
        duplicate_content.record_id = "แผนผลิต:999"

        merged, added = merge_order_records(self.store_path, [duplicate_content])

        self.assertEqual(added, 0)
        self.assertEqual(len(merged), 1)
        self.assertEqual(merged[0].production, 420)

    def test_incremental_merge_backfills_rm_size_without_duplicating(self) -> None:
        existing = sample_order(420)
        existing.rm_size = ""
        save_order_records(self.store_path, [existing])
        incoming = sample_order(None)

        merged, added = merge_order_records(self.store_path, [incoming])
        reloaded = load_order_records(self.store_path)

        self.assertEqual(added, 0)
        self.assertEqual(len(merged), 1)
        self.assertEqual(reloaded[0].rm_size, "M")
        self.assertEqual(reloaded[0].production, 420)

    def test_incremental_merge_backfills_wontons_per_cup_without_duplicating(self) -> None:
        existing = sample_order(420)
        existing.wontons_per_cup = None
        save_order_records(self.store_path, [existing])
        incoming = sample_order(None)

        merged, added = merge_order_records(self.store_path, [incoming])
        reloaded = load_order_records(self.store_path)

        self.assertEqual(added, 0)
        self.assertEqual(len(merged), 1)
        self.assertEqual(reloaded[0].wontons_per_cup, 8)
        self.assertEqual(reloaded[0].total_wontons, 64000)
        self.assertEqual(reloaded[0].production, 420)

    def test_loads_old_order_volume_store(self) -> None:
        payload = {
            "version": 1,
            "records": [{
                "record_id": "old:1",
                "date": "01",
                "month": "10",
                "year": "2026",
                "country": "USA",
                "customer_name": "Customer",
                "group_1": "G1",
                "group_2": "G2",
                "packaging": "Pack",
                "soup": "Regular",
                "order_volume": 100,
                "production": None,
            }],
        }
        self.store_path.write_text(json.dumps(payload), encoding="utf-8")

        loaded = load_order_records(self.store_path)

        self.assertEqual(loaded[0].order_unit, 100)
        self.assertEqual(loaded[0].rm_size, "")
        self.assertIsNone(loaded[0].order_cups)
        self.assertIsNone(loaded[0].cups_per_unit)
        self.assertIsNone(loaded[0].wontons_per_cup)
        self.assertIsNone(loaded[0].total_wontons)
        self.assertEqual(loaded[0].order_no, "ORD-000001")

    def test_preserves_existing_order_number_when_adding_new_orders(self) -> None:
        existing = sample_order()
        existing.order_no = "ORD-000125"
        save_order_records(self.store_path, [existing])
        incoming = sample_order()
        incoming.record_id = "แผนผลิต:11"
        incoming.customer_name = "New Customer"

        merged, added = merge_order_records(self.store_path, [incoming])

        self.assertEqual(added, 1)
        self.assertEqual(
            [record.order_no for record in merged],
            ["ORD-000125", "ORD-000126"],
        )


if __name__ == "__main__":
    unittest.main()
