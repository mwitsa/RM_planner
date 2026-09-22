from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from openpyxl import Workbook

from rm_planner.inventory.pd_actual_data import (
    PD_ACTUAL_COLUMNS,
    PIVOT_BLANK_LABEL,
    PdActualRecord,
    extract_pd_actual_records,
    list_sheets,
    load_pd_actual_records,
    pivot_weight_out_by_farm_and_size,
    save_pd_actual_records,
)

HEADER = [label for _key, label in PD_ACTUAL_COLUMNS]


def _pivot_record(farm_pond: str, size_out: str, weight_out_kg: float, transaction_date: str) -> PdActualRecord:
    fields = {key: "" for key, _label in PD_ACTUAL_COLUMNS}
    fields.update(
        farm_pond=farm_pond,
        size_out=size_out,
        weight_out_kg=weight_out_kg,
        transaction_date=transaction_date,
        actual_weight_kg=0.0,
        weight_diff_kg=0.0,
        yield_percent=0.0,
        quantity_ho_send=0.0,
        quantity_ho_from_farm=0.0,
    )
    return PdActualRecord(**fields)


class PdActualDataTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.workbook_path = Path(self.temporary_directory.name) / "pd_actual.xlsx"

        workbook = Workbook()
        summary = workbook.active
        summary.title = "summary"

        detail = workbook.create_sheet("DATA")
        detail.append(HEADER)
        row = [""] * len(HEADER)
        by_key = {key: index for index, (key, _label) in enumerate(PD_ACTUAL_COLUMNS)}
        row[by_key["farm_pond"]] = "ห้าดาว 1-B1"
        row[by_key["product"]] = "COOKED WONTON SOUP"
        row[by_key["actual_weight_kg"]] = 657.0
        row[by_key["weight_diff_kg"]] = 0.0
        row[by_key["weight_out_kg"]] = 479.74
        row[by_key["yield_percent"]] = 0.7301978691019787
        row[by_key["quantity_ho_send"]] = 1176.31
        row[by_key["quantity_ho_from_farm"]] = 1141.02
        row[by_key["transaction_date"]] = 46029.0  # 07/01/2026 as an Excel serial
        detail.append(row)
        detail.append([None] * len(HEADER))  # a blank row should be skipped

        workbook.save(self.workbook_path)

    def test_list_sheets_returns_all_sheet_names(self) -> None:
        self.assertEqual(list_sheets(self.workbook_path), ["summary", "DATA"])

    def test_extract_parses_rows_and_skips_blanks(self) -> None:
        records = extract_pd_actual_records(self.workbook_path, "DATA")

        self.assertEqual(len(records), 1)
        record = records[0]
        self.assertEqual(record.farm_pond, "ห้าดาว 1-B1")
        self.assertEqual(record.product, "COOKED WONTON SOUP")
        self.assertEqual(record.actual_weight_kg, 657.0)
        self.assertEqual(record.yield_percent, 0.7301978691019787)
        # A serial-number date cell (as pyxlsb would give for .xlsb) still
        # renders as DD/MM/YYYY when it comes through as a plain number.
        self.assertEqual(record.transaction_date, "07/01/2026")

    def test_extract_rejects_unknown_sheet(self) -> None:
        with self.assertRaisesRegex(ValueError, "Worksheet not found"):
            extract_pd_actual_records(self.workbook_path, "Missing")

    def test_pd_actual_columns_match_dataclass_fields(self) -> None:
        field_names = tuple(PdActualRecord.__slots__)
        self.assertEqual(tuple(key for key, _label in PD_ACTUAL_COLUMNS), field_names)
        self.assertEqual(len(PD_ACTUAL_COLUMNS), 60)

    def test_save_and_load_round_trip_survives_a_restart(self) -> None:
        records = extract_pd_actual_records(self.workbook_path, "DATA")
        store_path = Path(self.temporary_directory.name) / "pd_actual_data.json"

        save_pd_actual_records(store_path, records, source_file="src.xlsb", source_sheet="DATA")
        loaded, source_file, source_sheet = load_pd_actual_records(store_path)

        self.assertEqual(loaded, records)
        self.assertEqual(source_file, "src.xlsb")
        self.assertEqual(source_sheet, "DATA")

    def test_load_missing_store_returns_empty(self) -> None:
        loaded, source_file, source_sheet = load_pd_actual_records(
            Path(self.temporary_directory.name) / "never_saved.json"
        )

        self.assertEqual(loaded, [])
        self.assertEqual(source_file, "")
        self.assertEqual(source_sheet, "")


class PivotWeightOutByFarmAndSizeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.records = [
            _pivot_record("ประวิทย์ สีระสะมา(เก้าเก)-A1013", "53-58", 300.0, "12/02/2026"),
            _pivot_record("ประวิทย์ สีระสะมา(เก้าเก)-A1013", "53-58", 209.64, "12/02/2026"),
            _pivot_record("สมบัติ หัตถพณิชพร(บางกะไชย)-13", "53-58", 900.0, "12/02/2026"),
            _pivot_record("สมบัติ หัตถพณิชพร(บางกะไชย)-13", "53-58", 1006.84, "12/02/2026"),
            _pivot_record("สมบัติ หัตถพณิชพร(บางกะไชย)-13", "40-50", 120.0, "12/02/2026"),
            _pivot_record("ประวิทย์ สีระสะมา(เก้าเก)-A1013", "53-58", 5.0, "13/02/2026"),
            _pivot_record("", "", 42.0, "12/02/2026"),
        ]

    def test_groups_by_farm_then_size_with_a_transaction_date_filter(self) -> None:
        pivot = pivot_weight_out_by_farm_and_size(self.records, transaction_dates={"12/02/2026"})

        self.assertEqual(
            pivot.farm_keys,
            (PIVOT_BLANK_LABEL, "ประวิทย์ สีระสะมา(เก้าเก)-A1013", "สมบัติ หัตถพณิชพร(บางกะไชย)-13"),
        )
        self.assertAlmostEqual(
            pivot.matrix["ประวิทย์ สีระสะมา(เก้าเก)-A1013"]["53-58"], 509.64,
        )
        self.assertAlmostEqual(
            pivot.matrix["สมบัติ หัตถพณิชพร(บางกะไชย)-13"]["53-58"], 1906.84,
        )
        self.assertAlmostEqual(
            pivot.farm_totals["สมบัติ หัตถพณิชพร(บางกะไชย)-13"], 2026.84,
        )
        self.assertAlmostEqual(pivot.matrix[PIVOT_BLANK_LABEL][PIVOT_BLANK_LABEL], 42.0)
        self.assertAlmostEqual(pivot.grand_total, 509.64 + 2026.84 + 42.0)

    def test_without_a_date_filter_includes_every_record(self) -> None:
        pivot = pivot_weight_out_by_farm_and_size(self.records)

        self.assertAlmostEqual(
            pivot.farm_totals["ประวิทย์ สีระสะมา(เก้าเก)-A1013"], 509.64 + 5.0,
        )


if __name__ == "__main__":
    unittest.main()
