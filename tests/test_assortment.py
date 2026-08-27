from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from openpyxl import Workbook

from assortment import load_assortment


class AssortmentTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.workbook_path = Path(self.temporary_directory.name) / "assortment.xlsx"

        workbook = Workbook()
        sheet = workbook.active
        sheet.title = "Assortment"
        sheet.append(["Actual output", "S.43", "S.66"])
        sheet.append(["31-35", 0.4, "20%"])
        sheet.append(["36-40", 0.6, 0.8])
        workbook.save(self.workbook_path)

    def test_loads_assortment_matrix_and_totals(self) -> None:
        table = load_assortment(self.workbook_path)

        self.assertEqual(table.sheet_name, "Assortment")
        self.assertEqual(table.base_sizes, ("S.43", "S.66"))
        self.assertEqual(table.output_sizes, ("31-35", "36-40"))
        self.assertEqual(table.percentages, ((0.4, 0.2), (0.6, 0.8)))
        self.assertEqual(table.column_totals, (1.0, 1.0))
        self.assertEqual(table.invalid_base_sizes, ())

    def test_reports_distribution_that_does_not_total_100_percent(self) -> None:
        workbook = Workbook()
        sheet = workbook.active
        sheet.append(["Actual output", "S.43"])
        sheet.append(["31-35", 0.4])
        workbook.save(self.workbook_path)

        table = load_assortment(self.workbook_path)
        self.assertEqual(table.invalid_base_sizes, (("S.43", 0.4),))

    def test_rejects_percentage_over_100_percent(self) -> None:
        workbook = Workbook()
        sheet = workbook.active
        sheet.append(["Actual output", "S.43"])
        sheet.append(["31-35", 1.1])
        workbook.save(self.workbook_path)

        with self.assertRaises(ValueError):
            load_assortment(self.workbook_path)


if __name__ == "__main__":
    unittest.main()
