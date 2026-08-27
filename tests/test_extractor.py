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
        plan["B4"] = "แผนผลิต\nDate"
        plan["J4"] = "Customer"
        plan["V4"] = "QTY"
        plan["B5"] = datetime(2026, 8, 27)
        plan["J5"] = "  ลูกค้า   ทดสอบ  "
        plan["V5"] = "1,250"
        plan["B6"] = datetime(2026, 8, 28)  # separator/incomplete row
        plan["B7"] = "28/08/2569"
        plan["J7"] = "Customer B"
        plan["V7"] = 10.5
        workbook.save(self.workbook_path)

    def test_extracts_normalized_records_and_reports_incomplete_rows(self) -> None:
        result = extract_orders(self.workbook_path)

        self.assertEqual(result.sheet_name, "แผนผลิต ")
        self.assertEqual(result.header_row, 4)
        self.assertEqual(len(result.records), 2)
        self.assertEqual(len(result.issues), 1)
        self.assertEqual(result.records[0].production_date, "2026-08-27")
        self.assertEqual(result.records[0].production_month, "2026-08")
        self.assertEqual(result.records[0].customer_name, "ลูกค้า ทดสอบ")
        self.assertEqual(result.records[0].order_volume, 1250)
        self.assertEqual(result.records[1].production_date, "2026-08-28")
        self.assertEqual(result.records[1].order_volume, 10.5)

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
        self.assertEqual(json_rows[0]["order_volume"], 1250)


if __name__ == "__main__":
    unittest.main()
