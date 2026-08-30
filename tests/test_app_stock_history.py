from __future__ import annotations

import unittest

from app import ProductionPlanApp
from assortment_actual_store import ActualAssortmentEntry, ActualAssortmentRecord
from assortment_range_store import AssortmentSizeRange


def stock(
    record_id: str,
    record_type: str,
    entries: tuple[ActualAssortmentEntry, ...],
) -> ActualAssortmentRecord:
    return ActualAssortmentRecord(
        record_id=record_id,
        rm_id=record_id,
        record_date="2026-08-30",
        entries=entries,
        record_type=record_type,
        market_type="domestic",
        created_at="2026-08-30T00:00:00+00:00",
        updated_at=f"2026-08-30T00:00:0{record_id[-1]}+00:00",
    )


class AppStockHistoryTests(unittest.TestCase):
    def test_saved_stock_includes_legacy_class_only_records(self) -> None:
        current = stock("RM-000001", "actual", (ActualAssortmentEntry("51-55", 10),))
        legacy = stock(
            "RM-000002",
            "existing",
            (ActualAssortmentEntry("SS", 500, size_class="S+", pieces_per_kg=73),),
        )

        records = ProductionPlanApp._sorted_saved_stock_records((current, legacy))

        self.assertEqual({record.rm_id for record in records}, {"RM-000001", "RM-000002"})

    def test_legacy_class_only_stock_has_saved_stock_summaries(self) -> None:
        legacy = stock(
            "RM-000002",
            "existing",
            (
                ActualAssortmentEntry("M", 5000, size_class="M", pieces_per_kg=53),
                ActualAssortmentEntry("SS", 500, size_class="S+", pieces_per_kg=73),
            ),
        )
        app = object.__new__(ProductionPlanApp)
        app._current_assortment_size_range_definitions = lambda: (
            AssortmentSizeRange("M", "46-50", "56-60"),
            AssortmentSizeRange("S+", "61-65", "81-85"),
        )

        summaries = app._assortment_record_class_summaries(legacy)

        self.assertEqual(summaries["M"].total, 5000)
        self.assertEqual(summaries["S+"].total, 500)
        self.assertEqual(summaries["Unused"].total, 0)


if __name__ == "__main__":
    unittest.main()
