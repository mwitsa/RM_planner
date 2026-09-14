from __future__ import annotations

import json
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from rm_planner.planning.class_store import (
    BLANK_CLASS_FILTER,
    add_missing_class_definitions,
    class_filter_options,
    filter_class_definitions,
    load_class_definitions,
    order_class_names,
    upsert_class_definition,
)
from rm_planner.orders.extractor import OrderRecord


class ClassStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.store_path = Path(self.temporary_directory.name) / "classes.json"

    def test_missing_store_loads_empty(self) -> None:
        self.assertEqual(load_class_definitions(self.store_path), [])

    def test_saves_and_updates_class(self) -> None:
        saved = upsert_class_definition(
            self.store_path,
            "Country",
            "USA",
            "Export",
            value="Initial value",
        )
        updated = upsert_class_definition(
            self.store_path,
            "Country",
            "USA",
            "North America",
            class_id=saved.class_id,
            value="Updated value",
        )
        loaded = load_class_definitions(self.store_path)
        self.assertEqual(len(loaded), 1)
        self.assertEqual(updated.class_id, saved.class_id)
        self.assertEqual(loaded[0].name, "USA")
        self.assertEqual(loaded[0].group, "North America")
        self.assertEqual(loaded[0].value, "Updated value")

    def test_allows_many_names_per_class_but_rejects_duplicate_pair(self) -> None:
        upsert_class_definition(self.store_path, "Country", "USA")
        upsert_class_definition(self.store_path, "Country", "UK")
        with self.assertRaises(ValueError):
            upsert_class_definition(self.store_path, "country", "usa")
        self.assertEqual(len(load_class_definitions(self.store_path)), 2)

    def test_requires_class_and_name_but_group_may_be_blank(self) -> None:
        with self.assertRaises(ValueError):
            upsert_class_definition(self.store_path, "Country", "")
        saved = upsert_class_definition(self.store_path, "Country", "USA", "")
        self.assertEqual(saved.group, "")

    def test_adds_only_missing_class_name_pairs(self) -> None:
        upsert_class_definition(self.store_path, "Country", "USA", "North America")

        added = add_missing_class_definitions(
            self.store_path,
            [
                ("Country", "USA"),
                ("Country", "UK"),
                ("Soup", "Regular"),
                ("Soup", "regular"),
                ("Soup", ""),
            ],
        )

        loaded = load_class_definitions(self.store_path)
        self.assertEqual(added, 2)
        self.assertEqual(len(loaded), 3)
        self.assertEqual(
            {(item.class_value, item.name, item.group) for item in loaded},
            {
                ("Country", "USA", "North America"),
                ("Country", "UK", ""),
                ("Soup", "Regular", ""),
            },
        )

    def test_reads_legacy_define_as_group(self) -> None:
        payload = {
            "version": 1,
            "classes": [{
                "id": "legacy-1",
                "class": "Country",
                "name": "USA",
                "define": "North America",
                "created_at": "2026-01-01T00:00:00+00:00",
                "updated_at": "2026-01-01T00:00:00+00:00",
            }],
        }
        self.store_path.write_text(json.dumps(payload), encoding="utf-8")

        loaded = load_class_definitions(self.store_path)

        self.assertEqual(loaded[0].group, "North America")
        self.assertEqual(loaded[0].value, "")

    def test_builds_class_names_from_order_fields(self) -> None:
        record = OrderRecord(
            date="01",
            month="10",
            year="2026",
            country="USA",
            customer_name="Customer A",
            group_1="G1",
            group_2="G2",
            packaging="Pack",
            soup="Regular",
            order_unit=100,
            order_cups=1600,
            cups_per_unit=16,
            record_id="1",
        )

        duplicate_case = replace(record, record_id="2", country="usa")
        pairs = order_class_names([record, duplicate_case])

        self.assertEqual(
            pairs,
            (
                ("Country", "USA"),
                ("Customer", "Customer A"),
                ("Group 1", "G1"),
                ("Group 2", "G2"),
                ("Packaging", "Pack"),
                ("Soup", "Regular"),
                ("ถ้วย/Unit", "16"),
            ),
        )

    def test_filters_classes_by_class_name_search_and_group(self) -> None:
        upsert_class_definition(self.store_path, "Country", "USA", "North America")
        upsert_class_definition(self.store_path, "Country", "UK", "Europe")
        upsert_class_definition(self.store_path, "Soup", "Regular", "")
        definitions = load_class_definitions(self.store_path)

        filtered = filter_class_definitions(
            definitions,
            class_filter="Country",
            name_search="us",
            group_filter="North America",
        )
        blank_group = filter_class_definitions(
            definitions,
            group_filter=BLANK_CLASS_FILTER,
        )

        self.assertEqual([item.name for item in filtered], ["USA"])
        self.assertEqual([item.name for item in blank_group], ["Regular"])
        self.assertEqual(class_filter_options(definitions, "class"), ["Country", "Soup"])
        self.assertEqual(
            class_filter_options(definitions, "group"),
            ["Europe", "North America", BLANK_CLASS_FILTER],
        )


if __name__ == "__main__":
    unittest.main()
