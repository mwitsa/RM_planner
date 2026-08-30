from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from assortment_actual_store import (
    ActualAssortmentEntry,
    combine_size_range,
    delete_actual_record,
    estimate_wonton_pieces,
    load_actual_records,
    split_size_range,
    upsert_actual_record,
)


class ActualAssortmentStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.store_path = Path(self.temporary_directory.name) / "actual.json"

    def test_missing_history_loads_empty(self) -> None:
        self.assertEqual(load_actual_records(self.store_path), [])

    def test_splits_and_combines_size_range_for_two_input_boxes(self) -> None:
        self.assertEqual(split_size_range("51-55"), ("51", "55"))
        self.assertEqual(split_size_range("101 – 120"), ("101", "120"))
        self.assertEqual(combine_size_range("51", "55"), "51-55")

    def test_estimates_wontons_from_midpoint_pieces_per_kg(self) -> None:
        entries = (
            ActualAssortmentEntry("51-55", 100),
            ActualAssortmentEntry("61-65", 10),
        )

        self.assertEqual(estimate_wonton_pieces(entries), 5930)

    def test_size_range_requires_both_start_and_end(self) -> None:
        with self.assertRaisesRegex(ValueError, "start.*end"):
            combine_size_range("51", "")

    def test_saves_dated_entries_and_total_weight(self) -> None:
        saved = upsert_actual_record(
            self.store_path,
            "2026-08-27",
            [ActualAssortmentEntry("41-45", 120.5), ActualAssortmentEntry("46-50", 79.5)],
        )
        loaded = load_actual_records(self.store_path)
        self.assertEqual(len(loaded), 1)
        self.assertEqual(loaded[0].record_id, saved.record_id)
        self.assertEqual(loaded[0].record_date, "2026-08-27")
        self.assertEqual(loaded[0].record_type, "actual")
        self.assertEqual(loaded[0].total_weight, 200.0)
        self.assertEqual(loaded[0].rm_id, "RM-000001")

    def test_saves_and_loads_prediction_flag(self) -> None:
        saved = upsert_actual_record(
            self.store_path,
            "2026-08-27",
            [ActualAssortmentEntry("41-45", 100)],
            record_type="prediction",
        )

        self.assertEqual(saved.record_type, "prediction")
        self.assertEqual(load_actual_records(self.store_path)[0].record_type, "prediction")

    def test_saves_thai_market_label_as_internal_value(self) -> None:
        saved = upsert_actual_record(
            self.store_path,
            "2026-08-27",
            [ActualAssortmentEntry("41-45", 100)],
            market_type="ต่างประเทศ",
        )

        self.assertEqual(saved.market_type, "export")
        self.assertEqual(load_actual_records(self.store_path)[0].market_type, "export")

    def test_saves_existing_stock_with_explicit_class_and_pieces_per_kg(self) -> None:
        saved = upsert_actual_record(
            self.store_path,
            "2026-08-20",
            [
                ActualAssortmentEntry(
                    size="S",
                    weight=100,
                    size_class="S",
                    pieces_per_kg=65,
                )
            ],
            record_type="existing",
            market_type="domestic",
        )

        loaded = load_actual_records(self.store_path)[0]
        self.assertEqual(saved.record_type, "existing")
        self.assertEqual(loaded.entries[0].size_class, "S+")
        self.assertEqual(loaded.entries[0].pieces_per_kg, 65)
        self.assertEqual(estimate_wonton_pieces(loaded.entries), 6500)

    def test_existing_stock_requires_valid_size_class_and_pieces_per_kg(self) -> None:
        with self.assertRaisesRegex(ValueError, r"M or S\+"):
            upsert_actual_record(
                self.store_path,
                "2026-08-20",
                [
                    ActualAssortmentEntry(
                        size="XL",
                        weight=100,
                        size_class="XL",
                        pieces_per_kg=50,
                    )
                ],
                record_type="existing",
            )

    def test_legacy_record_without_type_loads_as_actual(self) -> None:
        self.store_path.write_text(
            json.dumps(
                {
                    "version": 1,
                    "records": [
                        {
                            "id": "legacy",
                            "date": "2026-08-27",
                            "entries": [{"size": "41-45", "weight": 100}],
                            "created_at": "2026-08-27T00:00:00+00:00",
                            "updated_at": "2026-08-27T00:00:00+00:00",
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )

        loaded = load_actual_records(self.store_path)[0]
        self.assertEqual(loaded.record_type, "actual")
        self.assertEqual(loaded.market_type, "unassigned")
        self.assertEqual(loaded.rm_id, "RM-000001")

    def test_updates_same_history_record(self) -> None:
        saved = upsert_actual_record(
            self.store_path,
            "2026-08-27",
            [ActualAssortmentEntry("41-45", 100)],
        )
        updated = upsert_actual_record(
            self.store_path,
            "2026-08-28",
            [ActualAssortmentEntry("46-50", 150)],
            saved.record_id,
        )
        loaded = load_actual_records(self.store_path)
        self.assertEqual(len(loaded), 1)
        self.assertEqual(updated.record_id, saved.record_id)
        self.assertEqual(updated.rm_id, saved.rm_id)
        self.assertEqual(updated.record_type, "actual")
        self.assertEqual(loaded[0].record_date, "2026-08-28")
        self.assertEqual(loaded[0].entries[0].size, "46-50")

    def test_update_can_manually_change_record_type(self) -> None:
        saved = upsert_actual_record(
            self.store_path,
            "2026-08-27",
            [ActualAssortmentEntry("41-45", 100)],
        )

        updated = upsert_actual_record(
            self.store_path,
            "2026-08-27",
            [ActualAssortmentEntry("41-45", 100)],
            record_id=saved.record_id,
            record_type="prediction",
        )

        self.assertEqual(updated.record_type, "prediction")
        self.assertEqual(load_actual_records(self.store_path)[0].record_type, "prediction")

    def test_deletes_only_selected_history_record(self) -> None:
        first = upsert_actual_record(
            self.store_path,
            "2026-08-27",
            [ActualAssortmentEntry("41-45", 100)],
        )
        second = upsert_actual_record(
            self.store_path,
            "2026-08-28",
            [ActualAssortmentEntry("46-50", 200)],
            record_type="prediction",
        )

        deleted = delete_actual_record(self.store_path, first.record_id)
        remaining = load_actual_records(self.store_path)

        self.assertEqual(first.rm_id, "RM-000001")
        self.assertEqual(second.rm_id, "RM-000002")
        self.assertEqual(deleted.record_id, first.record_id)
        self.assertEqual([record.record_id for record in remaining], [second.record_id])
        with self.assertRaisesRegex(ValueError, "no longer exists"):
            delete_actual_record(self.store_path, first.record_id)

    def test_rejects_invalid_date_and_weight(self) -> None:
        with self.assertRaises(ValueError):
            upsert_actual_record(
                self.store_path,
                "2026-02-30",
                [ActualAssortmentEntry("41-45", 100)],
            )
        with self.assertRaises(ValueError):
            upsert_actual_record(
                self.store_path,
                "2026-08-27",
                [ActualAssortmentEntry("41-45", 0)],
            )


if __name__ == "__main__":
    unittest.main()
