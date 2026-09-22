from __future__ import annotations

import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from openpyxl import Workbook

from rm_planner.inventory.rm_stock_data import (
    RM_STOCK_COLUMNS,
    RmStockRecord,
    extract_rm_stock_records,
    list_sheets,
    load_rm_stock_records,
    pivot_gross_wt_by_remark_and_action_repack,
    save_rm_stock_records,
)

HEADER = [label for _key, label in RM_STOCK_COLUMNS]


def sample_record(**overrides: object) -> RmStockRecord:
    fields = {key: "" for key, _label in RM_STOCK_COLUMNS}
    fields["gross_wt"] = 0.0
    fields["net_wt"] = 0.0
    fields.update(overrides)
    return RmStockRecord(**fields)


class RmStockDataTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.workbook_path = Path(self.temporary_directory.name) / "rm_stock.xlsx"

        workbook = Workbook()
        summary = workbook.active
        summary.title = "summary"
        summary["A1"] = "Sum of stock"

        detail = workbook.create_sheet("Data")
        detail.append(HEADER)
        row = ["43", "Plant 2", "3G34-07-1", "20004557", "08240N402050K01150",
               "VA HL EZ IQF FOR 13/15 2x5KG", "MRYPR2567/0187", "1", "", 10, 10,
               "26031820010652", "COMXXXI60318200101RPHLEZLOCL60318", "RX/GRAE",
               "21/12/2024", "21/06/2026", "", "0000", "90", "ผ่าน", "", "B.HL",
               "2 HL", "20/23(23)", "21-25", "13/15", "Local", "XXXI", "5", 227.48,
               "No Order", "เบิกทำWT/Mince", "", "", "เบิกทำWT/Mince", "", 603,
               ">3 Yr", 2566, "Co Product", "No Order", "Uncommitted", "No Order",
               datetime(2026, 9, 13)]
        self.assertEqual(len(row), len(HEADER))
        detail.append(row)
        detail.append([None] * len(HEADER))  # a blank row should be skipped

        workbook.save(self.workbook_path)

    def test_list_sheets_returns_all_sheet_names(self) -> None:
        self.assertEqual(list_sheets(self.workbook_path), ["summary", "Data"])

    def test_extract_rm_stock_records_parses_rows_and_skips_blanks(self) -> None:
        records = extract_rm_stock_records(self.workbook_path, "Data")

        self.assertEqual(len(records), 1)
        record = records[0]
        self.assertEqual(record.material_code, "08240N402050K01150")
        self.assertEqual(record.material_name, "VA HL EZ IQF FOR 13/15 2x5KG")
        self.assertEqual(record.gross_wt, 10.0)
        self.assertEqual(record.net_wt, 10.0)
        # A datetime cell renders as text, DD/MM/YYYY, matching the plain
        # text date columns already in this sheet (e.g. production_date).
        self.assertEqual(record.date, "13/09/2026")
        self.assertEqual(record.production_date, "21/12/2024")

    def test_save_and_load_round_trip_survives_a_restart(self) -> None:
        records = extract_rm_stock_records(self.workbook_path, "Data")
        with tempfile.TemporaryDirectory() as store_directory:
            store_path = Path(store_directory) / "rm_stock_data.json"
            save_rm_stock_records(
                store_path, records, source_file="src.xlsx", source_sheet="Data",
            )
            loaded, source_file, source_sheet = load_rm_stock_records(store_path)

        self.assertEqual(loaded, records)
        self.assertEqual(source_file, "src.xlsx")
        self.assertEqual(source_sheet, "Data")

    def test_load_missing_store_returns_empty(self) -> None:
        loaded, source_file, source_sheet = load_rm_stock_records(
            Path(self.temporary_directory.name) / "never_saved.json"
        )

        self.assertEqual(loaded, [])
        self.assertEqual(source_file, "")
        self.assertEqual(source_sheet, "")

    def test_extract_rm_stock_records_rejects_unknown_sheet(self) -> None:
        with self.assertRaisesRegex(ValueError, "Worksheet not found"):
            extract_rm_stock_records(self.workbook_path, "Missing")

    def test_rm_stock_columns_match_dataclass_fields(self) -> None:
        field_names = tuple(RmStockRecord.__slots__)
        self.assertEqual(tuple(key for key, _label in RM_STOCK_COLUMNS), field_names)


class RmStockPivotTests(unittest.TestCase):
    def test_pivot_matches_reference_grouping_and_totals(self) -> None:
        # Mirrors the reference Excel PivotTable: Plant filter across two
        # plants, Type = "RM For Wonton", rows = Remark, columns = Action
        # Repack, values = sum of Gross wt.
        records = [
            sample_record(plant="Plant 2", type="RM For Wonton", remark="WT",
                           action_repack="Waiting for reprocess", gross_wt=300.0),
            sample_record(plant="Plant 3", type="RM For Wonton", remark="WT",
                           action_repack="Waiting for reprocess", gross_wt=178.5),
            sample_record(plant="Plant 2", type="RM For Wonton", remark="PD For",
                           action_repack="No Prod. Plan", gross_wt=47841.0),
            # A different Type must be excluded by the filter.
            sample_record(plant="Plant 2", type="Committed", remark="WT",
                           action_repack="Waiting for reprocess", gross_wt=999.0),
        ]

        pivot = pivot_gross_wt_by_remark_and_action_repack(records, stock_type="RM For Wonton")

        self.assertEqual(pivot.row_keys, ("PD For", "WT"))
        self.assertEqual(pivot.column_keys, ("No Prod. Plan", "Waiting for reprocess"))
        self.assertEqual(pivot.matrix["WT"]["Waiting for reprocess"], 478.5)
        self.assertEqual(pivot.matrix["WT"]["No Prod. Plan"], 0.0)
        self.assertEqual(pivot.matrix["PD For"]["No Prod. Plan"], 47841.0)
        self.assertEqual(pivot.row_totals["WT"], 478.5)
        self.assertEqual(pivot.row_totals["PD For"], 47841.0)
        self.assertEqual(pivot.column_totals["Waiting for reprocess"], 478.5)
        self.assertEqual(pivot.grand_total, 48319.5)

    def test_pivot_filters_by_plant(self) -> None:
        records = [
            sample_record(plant="Plant 2", type="RM For Wonton", remark="WT",
                           action_repack="Waiting for reprocess", gross_wt=300.0),
            sample_record(plant="Plant 3", type="RM For Wonton", remark="WT",
                           action_repack="Waiting for reprocess", gross_wt=178.5),
        ]

        pivot = pivot_gross_wt_by_remark_and_action_repack(records, plants={"Plant 2"})

        self.assertEqual(pivot.grand_total, 300.0)

    def test_pivot_groups_blank_remark_and_action_repack(self) -> None:
        records = [sample_record(gross_wt=5.0)]

        pivot = pivot_gross_wt_by_remark_and_action_repack(records)

        self.assertEqual(pivot.row_keys, ("(blank)",))
        self.assertEqual(pivot.column_keys, ("(blank)",))
        self.assertEqual(pivot.matrix["(blank)"]["(blank)"], 5.0)


if __name__ == "__main__":
    unittest.main()
