"""Extraction for the Package/Ingredient stock workbook (SAP MB52-style export).

The source file has four sheets — two Excel PivotTable summaries ("sum Ing",
"sum Package") and two raw detail sheets ("Data Ingredient", "Data package").
Only the detail sheets are read; both share the same 14-column layout:

    Material | Material description | SLoc | Plnt | Typ | Stor. Bin | Hold |
    Batch | Avail.stock | BUn | GR Number | GR Date | SLED/BBD | Stor.Unit

The workbook is commonly exported as legacy .xls, so this reads that format
(via xlrd) as well as .xlsx/.xlsm (via openpyxl).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from rm_planner.inventory._workbook_io import (
    cell_float,
    cell_text,
    choose_default_sheet,
    load_records,
    read_sheet_names,
    read_sheet_rows,
    save_records,
    validated_path,
)

STORE_VERSION = 1
EXPECTED_COLUMN_COUNT = 14


@dataclass(frozen=True, slots=True)
class StockRecord:
    material_code: str
    material_description: str
    storage_location: str
    plant: str
    stock_type: str
    storage_bin: str
    hold: str
    batch: str
    quantity: float
    unit: str
    gr_number: str
    gr_date: str
    sled_bbd: str
    storage_unit: str


def list_sheets(workbook_path: str | Path) -> list[str]:
    return read_sheet_names(validated_path(workbook_path))


def extract_stock_records(workbook_path: str | Path, sheet_name: str) -> list[StockRecord]:
    path = validated_path(workbook_path)
    rows = read_sheet_rows(path, sheet_name)
    if not rows:
        return []
    records: list[StockRecord] = []
    for row in rows[1:]:
        if len(row) < EXPECTED_COLUMN_COUNT or not any(cell_text(value) for value in row):
            continue
        records.append(StockRecord(
            material_code=cell_text(row[0]),
            material_description=cell_text(row[1]),
            storage_location=cell_text(row[2]),
            plant=cell_text(row[3]),
            stock_type=cell_text(row[4]),
            storage_bin=cell_text(row[5]),
            hold=cell_text(row[6]),
            batch=cell_text(row[7]),
            quantity=cell_float(row[8]),
            unit=cell_text(row[9]),
            gr_number=cell_text(row[10]),
            gr_date=cell_text(row[11]),
            sled_bbd=cell_text(row[12]),
            storage_unit=cell_text(row[13]),
        ))
    return records


def save_stock_records(
    store_path: str | Path,
    records: list[StockRecord],
    source_file: str = "",
    source_sheet: str = "",
) -> None:
    """Persist extracted Package/Ingredient rows so they're still there after a restart."""

    save_records(
        store_path, records, version=STORE_VERSION,
        source_file=source_file, source_sheet=source_sheet,
    )


def load_stock_records(store_path: str | Path) -> tuple[list[StockRecord], str, str]:
    """Return (records, source_file, source_sheet) last saved by extraction."""

    return load_records(store_path, StockRecord)
