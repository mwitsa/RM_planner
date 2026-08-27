from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from rule_store import load_rules, save_rules


class RuleStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.rule_path = Path(self.temporary_directory.name) / "plan_rules.json"

    def test_missing_file_loads_as_empty_rules(self) -> None:
        self.assertEqual(load_rules(self.rule_path), [])

    def test_rules_round_trip_in_waterfall_order(self) -> None:
        save_rules(self.rule_path, ["First rule", "กฎข้อที่สอง", "Third rule"])

        self.assertEqual(
            load_rules(self.rule_path),
            ["First rule", "กฎข้อที่สอง", "Third rule"],
        )
        with self.rule_path.open(encoding="utf-8") as handle:
            payload = json.load(handle)
        self.assertEqual([entry["priority"] for entry in payload["rules"]], [1, 2, 3])

    def test_blank_rules_are_not_saved(self) -> None:
        save_rules(self.rule_path, ["  Keep me  ", "  ", "\n"])
        self.assertEqual(load_rules(self.rule_path), ["Keep me"])

    def test_invalid_file_is_reported(self) -> None:
        self.rule_path.write_text("not json", encoding="utf-8")
        with self.assertRaises(ValueError):
            load_rules(self.rule_path)


if __name__ == "__main__":
    unittest.main()
