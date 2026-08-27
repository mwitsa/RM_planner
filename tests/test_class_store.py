from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from class_store import load_class_definitions, upsert_class_definition


class ClassStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.store_path = Path(self.temporary_directory.name) / "classes.json"

    def test_missing_store_loads_empty(self) -> None:
        self.assertEqual(load_class_definitions(self.store_path), [])

    def test_saves_and_updates_class(self) -> None:
        saved = upsert_class_definition(
            self.store_path, "A", "Premium", "Priority production class"
        )
        updated = upsert_class_definition(
            self.store_path,
            "A",
            "Premium export",
            "Updated definition",
            saved.class_id,
        )
        loaded = load_class_definitions(self.store_path)
        self.assertEqual(len(loaded), 1)
        self.assertEqual(updated.class_id, saved.class_id)
        self.assertEqual(loaded[0].name, "Premium export")

    def test_rejects_duplicate_class(self) -> None:
        upsert_class_definition(self.store_path, "A", "First", "Definition")
        with self.assertRaises(ValueError):
            upsert_class_definition(self.store_path, "a", "Duplicate", "Definition")

    def test_requires_all_three_fields(self) -> None:
        with self.assertRaises(ValueError):
            upsert_class_definition(self.store_path, "A", "", "Definition")


if __name__ == "__main__":
    unittest.main()
