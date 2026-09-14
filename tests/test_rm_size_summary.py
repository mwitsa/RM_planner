from __future__ import annotations

import unittest

from assortment_upload_store import AssortmentShipmentRecord
from rm_size_summary import (
    build_summary_rows,
    summarize_assortment_supply,
    summarize_data_usage,
)


def shipment(record_date: str, **buckets: str) -> AssortmentShipmentRecord:
    fields = [("วันที่", record_date)]
    fields.extend(buckets.items())
    return AssortmentShipmentRecord(fields=tuple(fields))


class RmSizeSummaryTests(unittest.TestCase):
    def test_summarize_assortment_supply_sums_buckets_by_group_and_date(self) -> None:
        records = [
            shipment(
                "2026-09-10",
                **{
                    "51-55": "100",
                    "56-60": "50",
                    "76-80": "30",
                    "101-120": "10",
                },
            ),
            shipment(
                "2026-09-10",
                **{
                    "51-55": "20",
                    "76-80": "5",
                },
            ),
        ]

        totals = summarize_assortment_supply(records)

        self.assertAlmostEqual(totals[("2026-09-10", "M/HC (51-75)")], 170.0)
        self.assertAlmostEqual(totals[("2026-09-10", "S/SS (76-100)")], 35.0)
        self.assertAlmostEqual(totals[("2026-09-10", "BK (101+)")], 10.0)

    def test_waste_bucket_excluded_from_broken_group(self) -> None:
        records = [
            shipment(
                "2026-09-10",
                **{"131-140": "5", "ฝอยคัดทิ้ง >140": "999"},
            ),
        ]

        totals = summarize_assortment_supply(records)

        self.assertAlmostEqual(totals[("2026-09-10", "BK (101+)")], 5.0)

    def test_summarize_data_usage_matches_rm_size_case_insensitively(self) -> None:
        rows = [
            ("2026-09-10", "m", "1000"),
            ("2026-09-10", "HC", "500"),
            ("2026-09-10", "ss", "200"),
            ("2026-09-11", "BK", "300"),
            ("2026-09-10", "Aubergine", "999"),
            ("2026-09-10", "", "111"),
        ]

        totals = summarize_data_usage(rows, date_index=0, rm_size_index=1, ho_weight_index=2)

        self.assertAlmostEqual(totals[("2026-09-10", "M/HC (51-75)")], 1500.0)
        self.assertAlmostEqual(totals[("2026-09-10", "S/SS (76-100)")], 200.0)
        self.assertAlmostEqual(totals[("2026-09-11", "BK (101+)")], 300.0)
        self.assertNotIn(("2026-09-10", "BK (101+)"), totals)

    def test_build_summary_rows_combines_both_sources_and_computes_difference(self) -> None:
        assortment_records = [shipment("2026-09-10", **{"51-55": "150"})]
        data_rows = [("2026-09-10", "M", "100")]

        rows = build_summary_rows(
            assortment_records,
            data_rows,
            date_index=0,
            rm_size_index=1,
            ho_weight_index=2,
        )

        mh_row = next(row for row in rows if row.group_label == "M/HC (51-75)")
        self.assertEqual(mh_row.record_date, "2026-09-10")
        self.assertAlmostEqual(mh_row.assortment_kg, 150.0)
        self.assertAlmostEqual(mh_row.data_used_kg, 100.0)
        self.assertAlmostEqual(mh_row.difference_kg, 50.0)

        other_rows = [row for row in rows if row.group_label != "M/HC (51-75)"]
        self.assertTrue(all(row.assortment_kg == 0.0 and row.data_used_kg == 0.0 for row in other_rows))

    def test_build_summary_rows_sorted_by_date_then_group_order(self) -> None:
        # Every shipment contributes a total for all three groups (0 where a
        # date has no supply in that group), so grouped rows stay complete
        # and comparable across dates even when a size range was empty.
        assortment_records = [
            shipment("2026-09-11", **{"101-120": "1"}),
            shipment("2026-09-10", **{"76-80": "1"}),
            shipment("2026-09-10", **{"51-55": "1"}),
        ]

        rows = build_summary_rows(
            assortment_records,
            [],
            date_index=0,
            rm_size_index=1,
            ho_weight_index=2,
        )

        ordering = [(row.record_date, row.group_label) for row in rows]
        self.assertEqual(
            ordering,
            [
                ("2026-09-10", "M/HC (51-75)"),
                ("2026-09-10", "S/SS (76-100)"),
                ("2026-09-10", "BK (101+)"),
                ("2026-09-11", "M/HC (51-75)"),
                ("2026-09-11", "S/SS (76-100)"),
                ("2026-09-11", "BK (101+)"),
            ],
        )
        by_key = {(row.record_date, row.group_label): row.assortment_kg for row in rows}
        self.assertAlmostEqual(by_key[("2026-09-10", "BK (101+)")], 0.0)
        self.assertAlmostEqual(by_key[("2026-09-11", "M/HC (51-75)")], 0.0)


if __name__ == "__main__":
    unittest.main()
