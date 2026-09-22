"""Tests for persisted Loss cost settings."""

from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from rm_planner.planning.loss_store import (
    ALL_LINE_ITEM_KEYS,
    DIRECT_LABOR_ITEM_KEYS,
    DIRECT_SINGLE_RATE_CATEGORIES,
    DIRECT_SINGLE_RATE_ITEM_KEYS,
    INDIRECT_LABOR_ITEM_KEYS,
    INDIRECT_SINGLE_RATE_CATEGORIES,
    INDIRECT_SINGLE_RATE_ITEM_KEYS,
    WORK_CENTERS_GLAENG_3_INDIRECT,
    LossSettings,
    load_loss_settings,
    save_loss_settings,
)


class LossStoreTests(unittest.TestCase):
    def test_missing_file_uses_zero_defaults(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            settings = load_loss_settings(Path(temporary_directory) / "loss.json")

        self.assertEqual(settings.freeze_in_labor_cost_per_kg, 0)
        self.assertEqual(settings.freeze_pd_cost_per_kg, 0)
        self.assertEqual(settings.line_item_costs, {key: 0 for key in ALL_LINE_ITEM_KEYS})

    def test_round_trip_normalizes_values_and_sums_total(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            path = Path(temporary_directory) / "loss.json"
            saved = save_loss_settings(
                path,
                LossSettings(
                    freeze_in_labor_cost_per_kg="1.5",
                    freeze_in_repair_cost_per_kg="2",
                    freeze_in_energy_cost_per_kg="3",
                    freeze_in_depreciation_cost_per_kg="4",
                    thaw_labor_cost_per_kg="5",
                    thaw_salary_cost_per_kg="6",
                    thaw_repair_cost_per_kg="7",
                    thaw_depreciation_cost_per_kg="8",
                    thaw_other_cost_per_kg="9",
                    yield_loss_percent="12.5",
                    # Direct labor line items are headcount (คน).
                    line_item_costs={DIRECT_LABOR_ITEM_KEYS[0]: "3"},
                ),
            )
            loaded = load_loss_settings(path)

        self.assertEqual(saved.freeze_in_labor_cost_per_kg, 1.5)
        self.assertEqual(saved.thaw_other_cost_per_kg, 9)
        self.assertEqual(saved.yield_loss_percent, 12.5)
        # The % field is not a บาท/ก.ก. cost, so it must not be summed in.
        self.assertEqual(saved.freeze_pd_cost_per_kg, 45.5)
        self.assertEqual(saved.line_item_costs[DIRECT_LABOR_ITEM_KEYS[0]], 3)
        # Every known work center line gets a default entry, even unset ones.
        self.assertEqual(saved.line_item_costs[DIRECT_LABOR_ITEM_KEYS[1]], 0)
        self.assertEqual(loaded, saved)

    def test_rejects_negative_cost(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            path = Path(temporary_directory) / "loss.json"
            with self.assertRaisesRegex(ValueError, "ค่าแรง"):
                save_loss_settings(path, LossSettings(freeze_in_labor_cost_per_kg=-1))

    def test_rejects_yield_loss_percent_out_of_range(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            path = Path(temporary_directory) / "loss.json"
            with self.assertRaisesRegex(ValueError, "Yield Loss"):
                save_loss_settings(path, LossSettings(yield_loss_percent=101))

    def test_rejects_negative_direct_labor_headcount(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            path = Path(temporary_directory) / "loss.json"
            settings = LossSettings(line_item_costs={DIRECT_LABOR_ITEM_KEYS[0]: -5})
            with self.assertRaisesRegex(ValueError, "ทางตรง"):
                save_loss_settings(path, settings)

    def test_rejects_fractional_direct_labor_headcount(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            path = Path(temporary_directory) / "loss.json"
            settings = LossSettings(line_item_costs={DIRECT_LABOR_ITEM_KEYS[0]: "2.5"})
            with self.assertRaisesRegex(ValueError, "คน"):
                save_loss_settings(path, settings)

    def test_all_nine_z_categories_have_one_column_per_work_center(self) -> None:
        self.assertEqual(len(DIRECT_SINGLE_RATE_CATEGORIES), 9)
        for category, _z_code, _label in DIRECT_SINGLE_RATE_CATEGORIES:
            self.assertEqual(len(DIRECT_SINGLE_RATE_ITEM_KEYS[category]), 17)
        self.assertEqual(len(INDIRECT_SINGLE_RATE_CATEGORIES), 9)
        for category, _z_code, _label in INDIRECT_SINGLE_RATE_CATEGORIES:
            self.assertEqual(len(INDIRECT_SINGLE_RATE_ITEM_KEYS[category]), 14)
        self.assertEqual(len(INDIRECT_LABOR_ITEM_KEYS), len(WORK_CENTERS_GLAENG_3_INDIRECT))
        # ทางตรง: Z1 + Z2-ZA (10 columns) x 17 work centers = 170.
        # ทางอ้อม: Z1 + Z2-ZA (10 columns) x 14 work centers = 140.
        self.assertEqual(len(ALL_LINE_ITEM_KEYS), 17 * 10 + 14 * 10)

    def test_z_category_round_trips_and_rejects_negative(self) -> None:
        key = DIRECT_SINGLE_RATE_ITEM_KEYS["direct_z9_salary"][0]
        with TemporaryDirectory() as temporary_directory:
            path = Path(temporary_directory) / "loss.json"
            saved = save_loss_settings(path, LossSettings(line_item_costs={key: "6.5"}))
            self.assertEqual(saved.line_item_costs[key], 6.5)

            with self.assertRaisesRegex(ValueError, "Z9"):
                save_loss_settings(path, LossSettings(line_item_costs={key: -1}))

    def test_soup_base_loss_liters_round_trips_and_rejects_negative(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            path = Path(temporary_directory) / "loss.json"
            saved = save_loss_settings(path, LossSettings(soup_base_loss_liters="25.5"))
            self.assertEqual(saved.soup_base_loss_liters, 25.5)
            # Not a บาท/ก.ก. cost, so it must not affect the Freeze PD total.
            self.assertEqual(saved.freeze_pd_cost_per_kg, 0)

            with self.assertRaisesRegex(ValueError, "ลิตร"):
                save_loss_settings(path, LossSettings(soup_base_loss_liters=-1))

    def test_indirect_labor_headcount_and_z_category_validate_like_direct(self) -> None:
        labor_key = INDIRECT_LABOR_ITEM_KEYS[0]
        rate_key = INDIRECT_SINGLE_RATE_ITEM_KEYS["indirect_z6_depreciation"][0]
        with TemporaryDirectory() as temporary_directory:
            path = Path(temporary_directory) / "loss.json"
            saved = save_loss_settings(
                path,
                LossSettings(line_item_costs={labor_key: "2", rate_key: "4.25"}),
            )

        self.assertEqual(saved.line_item_costs[labor_key], 2)
        self.assertEqual(saved.line_item_costs[rate_key], 4.25)


if __name__ == "__main__":
    unittest.main()
