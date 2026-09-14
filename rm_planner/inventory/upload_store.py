"""Extraction and local persistence for the transposed per-shipment assortment sheet.

The source sheet lists each farm shipment as its own two-column block (a label
column repeating "วันที่", "ฟาร์ม", ... down the rows, and a value column next
to it), for example:

    วันที่   2026-09-10   วันที่   2026-09-11   ...
    ฟาร์ม   ณรรฐพงษ์ฟาร์ม  ฟาร์ม   สิริชัย       ...
    ...
    SUM     6000          SUM     5500          ...

Everything from the "วันที่" row down to and including the "SUM" row is read,
one shipment per column-pair; nothing below "SUM" (catch method, salinity,
remark, defect %) is read.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any, Iterable

from openpyxl import load_workbook


STORE_VERSION = 1
DATE_LABEL = "วันที่"
STOP_LABEL = "SUM"
MAX_FIELD_ROWS = 200
SUPPORTED_EXTENSIONS = {".xlsx", ".xlsm"}


@dataclass(frozen=True, slots=True)
class AssortmentShipmentRecord:
    """One farm/date shipment, as (row label, display value) pairs in sheet order."""

    fields: tuple[tuple[str, str], ...]

    def value(self, label: str) -> str:
        for field_label, field_value in self.fields:
            if field_label == label:
                return field_value
        return ""


def extract_assortment_shipments(
    workbook_path: str | Path,
    sheet_name: str | None = None,
) -> tuple[str, list[str], list[AssortmentShipmentRecord]]:
    """Return (sheet_name, field_labels, shipment records)."""

    path = _validated_path(workbook_path)
    workbook = load_workbook(path, read_only=True, data_only=True)
    try:
        selected_sheet = sheet_name or _choose_default_sheet(workbook)
        if selected_sheet not in workbook.sheetnames:
            raise ValueError(f"Worksheet not found: {selected_sheet}")

        worksheet = workbook[selected_sheet]
        header_row = _find_date_row(worksheet)
        if header_row is None:
            raise ValueError(
                f"Could not find a '{DATE_LABEL}' row in worksheet '{selected_sheet}'."
            )

        field_labels: list[str] = []
        row = header_row
        while True:
            label = _clean_text(worksheet.cell(row, 1).value)
            if not label:
                break
            field_labels.append(label)
            if label == STOP_LABEL:
                break
            row += 1
            if row - header_row > MAX_FIELD_ROWS:
                raise ValueError(
                    f"Could not find a '{STOP_LABEL}' row below '{DATE_LABEL}' "
                    f"in worksheet '{selected_sheet}'."
                )

        value_columns: list[int] = []
        column = 1
        max_column = worksheet.max_column
        while column <= max_column:
            label_value = _clean_text(worksheet.cell(header_row, column).value)
            if label_value == DATE_LABEL:
                value_columns.append(column + 1)
                column += 2
            else:
                column += 1

        records: list[AssortmentShipmentRecord] = []
        for value_column in value_columns:
            values = [
                _format_field_value(worksheet.cell(header_row + offset, value_column).value)
                for offset in range(len(field_labels))
            ]
            records.append(AssortmentShipmentRecord(fields=tuple(zip(field_labels, values))))

        return selected_sheet, field_labels, records
    finally:
        workbook.close()


def save_assortment_shipments(
    store_path: str | Path,
    sheet_name: str,
    field_labels: Iterable[str],
    records: Iterable[AssortmentShipmentRecord],
) -> Path:
    path = Path(store_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "version": STORE_VERSION,
        "sheet_name": sheet_name,
        "field_labels": list(field_labels),
        "records": [
            {"values": [value for _label, value in record.fields]} for record in records
        ],
    }
    temporary_path = path.with_suffix(f"{path.suffix}.tmp")
    try:
        with temporary_path.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
        temporary_path.replace(path)
    except OSError as exc:
        raise ValueError(f"Could not save assortment shipment data: {exc}") from exc
    return path


def load_assortment_shipments(
    store_path: str | Path,
) -> tuple[str, list[str], list[AssortmentShipmentRecord]]:
    path = Path(store_path)
    if not path.exists():
        return "", [], []
    try:
        with path.open(encoding="utf-8") as handle:
            payload = json.load(handle)
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Could not read saved assortment shipment data: {exc}") from exc
    if not isinstance(payload, dict) or not isinstance(payload.get("records"), list):
        raise ValueError("Saved assortment shipment data has an invalid structure.")

    field_labels = [str(label) for label in payload.get("field_labels", [])]
    records: list[AssortmentShipmentRecord] = []
    for raw in payload["records"]:
        if not isinstance(raw, dict) or not isinstance(raw.get("values"), list):
            raise ValueError("Saved assortment shipment data contains an invalid record.")
        values = [str(value) for value in raw["values"]]
        if len(values) != len(field_labels):
            raise ValueError("Saved assortment shipment data column count does not match.")
        records.append(AssortmentShipmentRecord(fields=tuple(zip(field_labels, values))))
    return str(payload.get("sheet_name", "")), field_labels, records


def _choose_default_sheet(workbook: Any) -> str:
    for worksheet in workbook.worksheets:
        if _find_date_row(worksheet) is not None:
            return worksheet.title
    raise ValueError(
        f"Could not find a worksheet with a '{DATE_LABEL}' row to identify the "
        "shipment table."
    )


def _find_date_row(worksheet: Any, scan_rows: int = 30) -> int | None:
    for row_number in range(1, min(worksheet.max_row, scan_rows) + 1):
        if _clean_text(worksheet.cell(row_number, 1).value) == DATE_LABEL:
            return row_number
    return None


def _validated_path(workbook_path: str | Path) -> Path:
    path = Path(workbook_path).expanduser().resolve()
    if not path.is_file():
        raise FileNotFoundError(f"Workbook not found: {path}")
    if path.suffix.lower() not in SUPPORTED_EXTENSIONS:
        raise ValueError("Please select an .xlsx or .xlsm workbook.")
    return path


def _clean_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _format_field_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, bool):
        return str(value)
    if isinstance(value, (int, float)):
        return str(int(round(value)))
    return str(value).strip()
