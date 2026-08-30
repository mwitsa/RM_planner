from __future__ import annotations

import unittest

from assortment_actual_store import ActualAssortmentEntry, ActualAssortmentRecord
from assortment_range_store import AssortmentSizeRange
from rm_timeline import build_rm_timeline, stock_distribution_percentages


RANGES = (
    AssortmentSizeRange("M", "46-50", "56-60"),
    AssortmentSizeRange("S+", "61-65", "81-85"),
)


def record(
    rm_id: str,
    record_date: str,
    record_type: str,
    market_type: str,
    entries: tuple[tuple[str, float], ...],
) -> ActualAssortmentRecord:
    return ActualAssortmentRecord(
        record_id=rm_id,
        rm_id=rm_id,
        record_date=record_date,
        entries=tuple(ActualAssortmentEntry(size, kg) for size, kg in entries),
        record_type=record_type,
        market_type=market_type,
        created_at="2026-08-29T00:00:00+00:00",
        updated_at="2026-08-29T00:00:00+00:00",
    )


class RmTimelineTests(unittest.TestCase):
    def test_stock_distribution_percentages_follow_each_weight_share(self) -> None:
        self.assertEqual(stock_distribution_percentages(20, 60, 20), (20, 60, 20))
        self.assertEqual(stock_distribution_percentages(0, 0, 0), (0, 0, 0))
        with self.assertRaisesRegex(ValueError, "cannot be negative"):
            stock_distribution_percentages(20, -1, 20)

    def test_groups_same_day_and_builds_cumulative_stock(self) -> None:
        rows = build_rm_timeline(
            [
                record("RM-000001", "2026-08-28", "actual", "domestic", (("51-55", 10),)),
                record("RM-000002", "2026-08-28", "prediction", "export", (("61-65", 20),)),
                record("RM-000003", "2026-08-29", "actual", "domestic", (("71-75", 30),)),
            ],
            RANGES,
        )

        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0].rm_ids, ("RM-000001", "RM-000002"))
        self.assertEqual(rows[0].incoming_kg, 30)
        self.assertEqual(rows[0].cumulative_kg, 30)
        self.assertEqual(rows[1].cumulative_kg, 60)
        self.assertEqual(rows[0].s_plus_stock.total, 20)
        self.assertEqual(rows[1].s_plus_stock.total, 50)
        self.assertEqual(rows[0].m_wontons, 530)
        self.assertEqual(rows[0].s_plus_wontons, 1260)
        self.assertEqual(rows[1].s_plus_wontons, 3450)
        self.assertEqual(rows[0].cumulative_wontons, 1790)
        self.assertEqual(rows[1].cumulative_wontons, 3980)

    def test_filters_market_before_calculating_cumulative_stock(self) -> None:
        rows = build_rm_timeline(
            [
                record("RM-000001", "2026-08-28", "actual", "domestic", (("51-55", 10),)),
                record("RM-000002", "2026-08-29", "prediction", "domestic", (("51-55", 20),)),
                record("RM-000003", "2026-08-30", "actual", "export", (("51-55", 30),)),
            ],
            RANGES,
            market_type="domestic",
        )

        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0].rm_ids, ("RM-000001",))
        self.assertEqual(rows[1].rm_ids, ("RM-000002",))
        self.assertEqual(rows[1].cumulative_kg, 30)

    def test_existing_stock_adds_direct_class(self) -> None:
        existing = ActualAssortmentRecord(
            record_id="existing-1",
            rm_id="RM-OPENING",
            record_date="2026-08-20",
            entries=(
                ActualAssortmentEntry(
                    "S",
                    100,
                    size_class="S",
                    pieces_per_kg=65,
                ),
            ),
            record_type="existing",
            market_type="domestic",
            created_at="2026-08-20T00:00:00+00:00",
            updated_at="2026-08-20T00:00:00+00:00",
        )

        rows = build_rm_timeline(
            [existing],
            RANGES,
            market_type="domestic",
        )

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].incoming_kg, 100)
        self.assertEqual(rows[0].s_plus_stock.total, 100)
        self.assertEqual(rows[0].s_plus_wontons, 6500)
        self.assertEqual(rows[0].cumulative_wontons, 6500)


if __name__ == "__main__":
    unittest.main()
