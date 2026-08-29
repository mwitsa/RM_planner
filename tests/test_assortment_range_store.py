from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from assortment_range_store import (
    AssortmentSizeRange,
    classify_size_range,
    default_size_ranges,
    load_size_ranges,
    save_size_ranges,
    summarize_size_class_weight_details,
    summarize_size_class_weights,
)


class AssortmentRangeStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.store_path = Path(self.temporary_directory.name) / "ranges.json"
        self.sizes = ("11-15", "16-20", "21-25", "26-30", "31-35", "36-40")

    def test_missing_store_returns_three_contiguous_defaults(self) -> None:
        ranges = default_size_ranges(self.sizes)

        self.assertEqual(
            ranges,
            (
                AssortmentSizeRange("M", "11-15", "16-20"),
                AssortmentSizeRange("S", "21-25", "26-30"),
                AssortmentSizeRange("SS", "31-35", "36-40"),
            ),
        )
        self.assertEqual(load_size_ranges(self.store_path, self.sizes), ranges)

    def test_round_trip_preserves_ranges(self) -> None:
        ranges = (
            AssortmentSizeRange("M", "11-15", "21-25"),
            AssortmentSizeRange("S", "26-30", "31-35"),
            AssortmentSizeRange("SS", "36-40", "36-40"),
        )

        save_size_ranges(self.store_path, ranges, self.sizes)

        self.assertEqual(load_size_ranges(self.store_path, self.sizes), ranges)

    def test_rejects_range_size_missing_from_master(self) -> None:
        payload = {
            "version": 1,
            "ranges": [
                {"size_class": "M", "start_size": "missing", "end_size": "16-20"},
                {"size_class": "S", "start_size": "21-25", "end_size": "26-30"},
                {"size_class": "SS", "start_size": "31-35", "end_size": "36-40"},
            ],
        }
        self.store_path.write_text(json.dumps(payload), encoding="utf-8")

        with self.assertRaises(ValueError):
            load_size_ranges(self.store_path, self.sizes)

    def test_classifies_every_intersecting_size_letter(self) -> None:
        ranges = (
            AssortmentSizeRange("M", "46-50", "56-60"),
            AssortmentSizeRange("S", "61-65", "66-70"),
            AssortmentSizeRange("SS", "61-65", "81-85"),
        )

        self.assertEqual(classify_size_range("51", "55", ranges), ("M",))
        self.assertEqual(classify_size_range("61", "65", ranges), ("S", "SS"))
        self.assertEqual(classify_size_range("58", "62", ranges), ("M", "S", "SS"))
        self.assertEqual(classify_size_range("86", "90", ranges), ("Unused",))

    def test_rejects_reversed_or_nonnumeric_actual_size_range(self) -> None:
        ranges = (AssortmentSizeRange("M", "46-50", "56-60"),)
        with self.assertRaises(ValueError):
            classify_size_range("60", "51", ranges)
        with self.assertRaises(ValueError):
            classify_size_range("large", "60", ranges)

    def test_summarizes_weights_into_each_intersecting_class(self) -> None:
        ranges = (
            AssortmentSizeRange("M", "46-50", "56-60"),
            AssortmentSizeRange("S", "61-65", "66-70"),
            AssortmentSizeRange("SS", "61-65", "81-85"),
        )

        totals = summarize_size_class_weights(
            (("51", "55", 486), ("61", "65", 844), ("86", "90", 10)),
            ranges,
        )

        self.assertEqual(totals, {"M": 486, "S": 844, "SS": 844, "Unused": 10})

        details = summarize_size_class_weight_details(
            (
                ("51", "55", 486),
                ("61", "65", 844),
                ("71", "75", 100),
            ),
            ranges,
        )
        self.assertEqual(details["M"].total, 486)
        self.assertEqual(details["M"].overlap, 0)
        self.assertEqual(details["S"].total, 844)
        self.assertEqual(details["S"].overlap, 844)
        self.assertEqual(details["SS"].total, 944)
        self.assertEqual(details["SS"].overlap, 844)


if __name__ == "__main__":
    unittest.main()
