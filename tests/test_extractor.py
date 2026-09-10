from __future__ import annotations

import csv
import json
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from openpyxl import Workbook

from extractor import choose_default_sheet, export_csv, export_json, extract_orders


class ExtractorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.workbook_path = Path(self.temporary_directory.name) / "plan.xlsx"

        workbook = Workbook()
        irrelevant = workbook.active
        irrelevant.title = "Notes"
        irrelevant["A1"] = "Not an order table"

        plan = workbook.create_sheet("แผนผลิต ")
        plan["C4"] = "แผน LOAD\nDate"
        plan["J4"] = "Customer"
        plan["V4"] = "QTY"
        plan["AI4"] = "Order ถ้วย"
        plan["C5"] = datetime(2026, 8, 27)
        plan["H5"] = "  Thailand  "
        plan["J5"] = "  ลูกค้า   ทดสอบ  "
        plan["K5"] = " Group A "
        plan["L5"] = "Cooked\nWonton"
        plan["O5"] = "130g*24"
        plan["Q5"] = 8
        plan["S5"] = "M"
        plan["U5"] = " Regular "
        plan["V5"] = "1,250"
        plan["R5"] = 0.0054
        plan["AI5"] = 20000
        plan["C6"] = datetime(2026, 8, 28)  # separator/incomplete row
        plan["C7"] = "28/08/2569"
        plan["J7"] = "Customer B"
        plan["V7"] = 10.5
        plan["Q7"] = 12
        plan["S7"] = "S"
        plan["R7"] = 0.0054
        plan["AI7"] = 84
        plan["C8"] = "'10-2026"
        plan["J8"] = "Month-only customer"
        plan["V8"] = 500
        workbook.save(self.workbook_path)

    def test_extracts_normalized_records_and_reports_incomplete_rows(self) -> None:
        result = extract_orders(self.workbook_path)

        self.assertEqual(result.sheet_name, "แผนผลิต ")
        self.assertEqual(result.header_row, 4)
        self.assertEqual(len(result.records), 3)
        self.assertEqual(len(result.issues), 1)
        self.assertEqual(result.records[0].date, "27")
        self.assertEqual(result.records[0].month, "08")
        self.assertEqual(result.records[0].year, "2026")
        self.assertEqual(result.records[0].month_key, "2026-08")
        self.assertEqual(result.records[0].country, "Thailand")
        self.assertEqual(result.records[0].customer_name, "ลูกค้า ทดสอบ")
        self.assertEqual(result.records[0].group_1, "Group A")
        self.assertEqual(result.records[0].group_2, "Cooked Wonton")
        self.assertEqual(result.records[0].packaging, "130g*24")
        self.assertEqual(result.records[0].rm_size, "M")
        self.assertEqual(result.records[0].soup, "Regular")
        self.assertEqual(result.records[0].wontons_per_cup, 8)
        self.assertEqual(result.records[0].order_unit, 1250)
        self.assertEqual(result.records[0].order_cups, 20000)
        self.assertEqual(result.records[0].cups_per_unit, 16)
        self.assertEqual(result.records[0].total_wontons, 160000)
        self.assertEqual(result.records[0].ho_weight_kg, 1600)
        self.assertIsNone(result.records[0].production)
        self.assertTrue(result.records[0].record_id.endswith(":5"))
        self.assertEqual(result.records[1].date, "28")
        self.assertEqual(result.records[1].month, "08")
        self.assertEqual(result.records[1].year, "2026")
        self.assertEqual(result.records[1].order_unit, 10.5)
        self.assertEqual(result.records[1].rm_size, "S")
        self.assertEqual(result.records[1].order_cups, 84)
        self.assertEqual(result.records[1].cups_per_unit, 8)
        self.assertEqual(result.records[1].wontons_per_cup, 12)
        self.assertEqual(result.records[1].total_wontons, 1008)
        self.assertAlmostEqual(result.records[1].ho_weight_kg, 10.08)
        self.assertEqual(result.records[2].date, "")
        self.assertEqual(result.records[2].month, "10")
        self.assertEqual(result.records[2].year, "2026")
        self.assertEqual(result.records[2].month_key, "2026-10")
        self.assertIsNone(result.records[2].order_cups)
        self.assertIsNone(result.records[2].cups_per_unit)

    def test_default_sheet_uses_headers(self) -> None:
        self.assertEqual(choose_default_sheet(self.workbook_path), "แผนผลิต ")

    def test_csv_and_json_exports_preserve_data(self) -> None:
        result = extract_orders(self.workbook_path)
        csv_path = export_csv(result.records, Path(self.temporary_directory.name) / "orders.csv")
        json_path = export_json(result.records, Path(self.temporary_directory.name) / "orders.json")

        with csv_path.open(encoding="utf-8-sig", newline="") as handle:
            csv_rows = list(csv.DictReader(handle))
        with json_path.open(encoding="utf-8") as handle:
            json_rows = json.load(handle)

        self.assertEqual(csv_rows[0]["customer_name"], "ลูกค้า ทดสอบ")
        self.assertEqual(list(csv_rows[0]), [
            "date",
            "month",
            "year",
            "country",
            "customer_name",
            "group_1",
            "group_2",
            "packaging",
            "rm_size",
            "soup",
            "wontons_per_cup",
            "order_unit",
            "order_cups",
            "cups_per_unit",
            "total_wontons",
            "ho_weight_kg",
            "production",
        ])
        self.assertEqual(json_rows[0]["date"], "27")
        self.assertEqual(json_rows[0]["month"], "08")
        self.assertEqual(json_rows[0]["year"], "2026")
        self.assertEqual(json_rows[0]["rm_size"], "M")
        self.assertEqual(json_rows[0]["order_unit"], 1250)
        self.assertEqual(json_rows[0]["order_cups"], 20000)
        self.assertEqual(json_rows[0]["cups_per_unit"], 16)
        self.assertEqual(json_rows[0]["wontons_per_cup"], 8)
        self.assertEqual(json_rows[0]["total_wontons"], 160000)
        self.assertEqual(json_rows[0]["ho_weight_kg"], 1600)
        self.assertIsNone(json_rows[0]["production"])
        self.assertNotIn("record_id", json_rows[0])


if __name__ == "__main__":
    unittest.main()
