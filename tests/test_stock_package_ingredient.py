from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from openpyxl import Workbook

from rm_planner.inventory.stock_package_ingredient import (
    StockRecord,
    choose_default_sheet,
    extract_stock_records,
    list_sheets,
    load_stock_records,
    save_stock_records,
)

HEADER = (
    "Material", "Material description", "SLoc", "Plnt", "Typ", "Stor. Bin",
    "Hold", "Batch", "Avail.stock", "BUn", "GR Number", "GR Date", "SLED/BBD",
    "Stor.Unit",
)


class StockPackageIngredientTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.workbook_path = Path(self.temporary_directory.name) / "stock.xlsx"

        workbook = Workbook()
        summary = workbook.active
        summary.title = "sum Package"
        summary["A1"] = "Sum of Avail.stock"

        detail = workbook.create_sheet("Data package")
        detail.append(HEADER)
        detail.append([
            12004870, "TAPE-OPP-1003 (2INX90M-0.045-CLEAR)", 9501, 4912, 280,
            "299-99-99", "", "260911T20B", 1104, "RO", 5000655025,
            "11.09.2026", "11.09.2027", 5800007010,
        ])
        detail.append([None] * 14)  # a blank row should be skipped

        workbook.save(self.workbook_path)

    def test_list_sheets_returns_all_sheet_names(self) -> None:
        self.assertEqual(
            list_sheets(self.workbook_path), ["sum Package", "Data package"]
        )

    def test_choose_default_sheet_prefers_data_sheet_over_pivot_summary(self) -> None:
        # "sum Package" also matches "package", but the detail sheet must win.
        self.assertEqual(
            choose_default_sheet(["sum Package", "Data package"], "package"),
            "Data package",
        )

    def test_choose_default_sheet_falls_back_to_plain_match(self) -> None:
        self.assertEqual(choose_default_sheet(["Other", "Ingredient"], "ing"), "Ingredient")

    def test_choose_default_sheet_falls_back_to_first_sheet(self) -> None:
        self.assertEqual(choose_default_sheet(["A", "B"], "nomatch"), "A")
        self.assertEqual(choose_default_sheet([], "nomatch"), "")

    def test_extract_stock_records_parses_rows_and_skips_blanks(self) -> None:
        records = extract_stock_records(self.workbook_path, "Data package")

        self.assertEqual(
            records,
            [StockRecord(
                material_code="12004870",
                material_description="TAPE-OPP-1003 (2INX90M-0.045-CLEAR)",
                storage_location="9501",
                plant="4912",
                stock_type="280",
                storage_bin="299-99-99",
                hold="",
                batch="260911T20B",
                quantity=1104.0,
                unit="RO",
                gr_number="5000655025",
                gr_date="11.09.2026",
                sled_bbd="11.09.2027",
                storage_unit="5800007010",
            )],
        )

    def test_extract_stock_records_rejects_unknown_sheet(self) -> None:
        with self.assertRaisesRegex(ValueError, "Worksheet not found"):
            extract_stock_records(self.workbook_path, "Missing")

    def test_save_and_load_round_trip_survives_a_restart(self) -> None:
        records = extract_stock_records(self.workbook_path, "Data package")
        store_path = Path(self.temporary_directory.name) / "package.json"

        save_stock_records(store_path, records, source_file="src.xlsx", source_sheet="Data package")
        loaded, source_file, source_sheet = load_stock_records(store_path)

        self.assertEqual(loaded, records)
        self.assertEqual(source_file, "src.xlsx")
        self.assertEqual(source_sheet, "Data package")

    def test_load_missing_store_returns_empty(self) -> None:
        loaded, source_file, source_sheet = load_stock_records(
            Path(self.temporary_directory.name) / "never_saved.json"
        )

        self.assertEqual(loaded, [])
        self.assertEqual(source_file, "")
        self.assertEqual(source_sheet, "")


if __name__ == "__main__":
    unittest.main()
