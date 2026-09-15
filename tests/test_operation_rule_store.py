from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from rm_planner.planning.operation_rule_store import load_operation_rules, save_operation_rules


class OperationRuleStoreTests(unittest.TestCase):
    def test_rules_round_trip_in_visual_order(self) -> None:
        rules = [
            {"nodes": [{"class": "Country", "group": "E"}, {"class": "Country", "group": "D"}]},
            {"nodes": [{"class": "Group 1", "group": "NE"}]},
        ]
        with TemporaryDirectory() as temporary:
            path = Path(temporary) / "rules.json"
            save_operation_rules(path, rules)
            self.assertEqual(load_operation_rules(path), rules)


if __name__ == "__main__":
    unittest.main()
