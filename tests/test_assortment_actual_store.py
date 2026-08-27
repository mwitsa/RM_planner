from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from assortment_actual_store import (
    ActualAssortmentEntry,
    load_actual_records,
    upsert_actual_record,
)


class ActualAssortmentStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.store_path = Path(self.temporary_directory.name) / "actual.json"

    def test_missing_history_loads_empty(self) -> None:
        self.assertEqual(load_actual_records(self.store_path), [])

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
        self.assertEqual(loaded[0].total_weight, 200.0)

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
        self.assertEqual(loaded[0].record_date, "2026-08-28")
        self.assertEqual(loaded[0].entries[0].size, "46-50")

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
