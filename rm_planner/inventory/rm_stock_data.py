"""Extraction for the RM (raw material) stock workbook.

The workbook has several summary/pivot sheets (summary, Status, Sum, OS,
Aging, GROUP (2), ...) plus one raw "Data" sheet with 44 columns; only the
"Data" sheet is read here.
"""

from __future__ import annotations

from collections.abc import Collection, Iterable
from dataclasses import dataclass
from pathlib import Path

from rm_planner.inventory._workbook_io import (
    cell_float,
    cell_text,
    load_records,
    read_sheet_names,
    read_sheet_rows,
    save_records,
    validated_path,
)

STORE_VERSION = 1
PIVOT_BLANK_LABEL = "(blank)"

EXPECTED_COLUMN_COUNT = 44

# (field name, source column header) in source column order.
RM_STOCK_COLUMNS = (
    ("process", "กระบวนการ"),
    ("plant", "Plant"),
    ("storage_location", "สถานที่เก็บ"),
    ("stack_tag", "ป้ายหน้ากอง"),
    ("material_code", "รหัสอาหาร"),
    ("material_name", "ชื่อรหัสอาหาร"),
    ("order_no", "Order NO"),
    ("master", "Master"),
    ("inner", "Inner"),
    ("gross_wt", "Gross wt"),
    ("net_wt", "Net wt"),
    ("production_no", "Production No"),
    ("julian_code", "Julian Code"),
    ("eu_code", "EU code"),
    ("production_date", "วันผลิต"),
    ("expiry_date", "วันหมดอายุ"),
    ("customer_expiry_date", "วันหมดอายุลูกค้า"),
    ("lot", "LOT"),
    ("usage_remark", "หมายเหตุการใช้"),
    ("usag_name", "USAG_NAME"),
    ("qa_qc_result", "ผลเชื้อ QA,QC"),
    ("group", "Group"),
    ("group_format", "Group Format"),
    ("size_rm", "Sz.RM"),
    ("rm", "RM"),
    ("size_fg", "Sz.FG"),
    ("country", "Country"),
    ("rope_color", "สีเชือก"),
    ("gross_wt_per_unit", "Gross wt/Unit"),
    ("cost_per_gross", "Cost / Gross"),
    ("type", "Type"),
    ("action", "Action"),
    ("plan", "Plan"),
    ("remark", "Remark"),
    ("action_hold", "ActionHOLD"),
    ("action_repack", "Action Repack"),
    ("month", "Month"),
    ("aging", "Aging"),
    ("year", "Year"),
    ("grade", "Grade"),
    ("status_report", "Status_Report"),
    ("type_committed_2", "Type_committed_2"),
    ("type_group_2", "Type_Group_2"),
    ("date", "Date"),
)


@dataclass(frozen=True, slots=True)
class RmStockRecord:
    process: str
    plant: str
    storage_location: str
    stack_tag: str
    material_code: str
    material_name: str
    order_no: str
    master: str
    inner: str
    gross_wt: float
    net_wt: float
    production_no: str
    julian_code: str
    eu_code: str
    production_date: str
    expiry_date: str
    customer_expiry_date: str
    lot: str
    usage_remark: str
    usag_name: str
    qa_qc_result: str
    group: str
    group_format: str
    size_rm: str
    rm: str
    size_fg: str
    country: str
    rope_color: str
    gross_wt_per_unit: str
    cost_per_gross: str
    type: str
    action: str
    plan: str
    remark: str
    action_hold: str
    action_repack: str
    month: str
    aging: str
    year: str
    grade: str
    status_report: str
    type_committed_2: str
    type_group_2: str
    date: str


def list_sheets(workbook_path: str | Path) -> list[str]:
    return read_sheet_names(validated_path(workbook_path))


def extract_rm_stock_records(workbook_path: str | Path, sheet_name: str) -> list[RmStockRecord]:
    path = validated_path(workbook_path)
    rows = read_sheet_rows(path, sheet_name)
    if not rows:
        return []
    records: list[RmStockRecord] = []
    for row in rows[1:]:
        if len(row) < EXPECTED_COLUMN_COUNT or not any(cell_text(value) for value in row):
            continue
        records.append(RmStockRecord(
            process=cell_text(row[0]),
            plant=cell_text(row[1]),
            storage_location=cell_text(row[2]),
            stack_tag=cell_text(row[3]),
            material_code=cell_text(row[4]),
            material_name=cell_text(row[5]),
            order_no=cell_text(row[6]),
            master=cell_text(row[7]),
            inner=cell_text(row[8]),
            gross_wt=cell_float(row[9]),
            net_wt=cell_float(row[10]),
            production_no=cell_text(row[11]),
            julian_code=cell_text(row[12]),
            eu_code=cell_text(row[13]),
            production_date=cell_text(row[14]),
            expiry_date=cell_text(row[15]),
            customer_expiry_date=cell_text(row[16]),
            lot=cell_text(row[17]),
            usage_remark=cell_text(row[18]),
            usag_name=cell_text(row[19]),
            qa_qc_result=cell_text(row[20]),
            group=cell_text(row[21]),
            group_format=cell_text(row[22]),
            size_rm=cell_text(row[23]),
            rm=cell_text(row[24]),
            size_fg=cell_text(row[25]),
            country=cell_text(row[26]),
            rope_color=cell_text(row[27]),
            gross_wt_per_unit=cell_text(row[28]),
            cost_per_gross=cell_text(row[29]),
            type=cell_text(row[30]),
            action=cell_text(row[31]),
            plan=cell_text(row[32]),
            remark=cell_text(row[33]),
            action_hold=cell_text(row[34]),
            action_repack=cell_text(row[35]),
            month=cell_text(row[36]),
            aging=cell_text(row[37]),
            year=cell_text(row[38]),
            grade=cell_text(row[39]),
            status_report=cell_text(row[40]),
            type_committed_2=cell_text(row[41]),
            type_group_2=cell_text(row[42]),
            date=cell_text(row[43]),
        ))
    return records


@dataclass(frozen=True, slots=True)
class PivotTable:
    row_keys: tuple[str, ...]
    column_keys: tuple[str, ...]
    matrix: dict[str, dict[str, float]]
    row_totals: dict[str, float]
    column_totals: dict[str, float]
    grand_total: float


def pivot_gross_wt_by_remark_and_action_repack(
    records: Iterable[RmStockRecord],
    plants: Collection[str] | None = None,
    stock_type: str | None = None,
) -> PivotTable:
    """Sum of Gross wt, grouped by Remark (rows) x Action Repack (columns).

    Mirrors the reference Excel PivotTable ("PD" page): an optional Plant
    filter (one or more plants) and a single Type filter; blank Remark or
    Action Repack values are grouped under "(blank)", matching Excel.
    """

    filtered = [
        record for record in records
        if (not plants or record.plant in plants)
        and (not stock_type or record.type == stock_type)
    ]
    row_keys = sorted({record.remark or PIVOT_BLANK_LABEL for record in filtered})
    column_keys = sorted({record.action_repack or PIVOT_BLANK_LABEL for record in filtered})
    matrix = {row: {column: 0.0 for column in column_keys} for row in row_keys}
    for record in filtered:
        row = record.remark or PIVOT_BLANK_LABEL
        column = record.action_repack or PIVOT_BLANK_LABEL
        matrix[row][column] += record.gross_wt
    row_totals = {row: sum(matrix[row].values()) for row in row_keys}
    column_totals = {
        column: sum(matrix[row][column] for row in row_keys) for column in column_keys
    }
    grand_total = sum(row_totals.values())
    return PivotTable(
        row_keys=tuple(row_keys),
        column_keys=tuple(column_keys),
        matrix=matrix,
        row_totals=row_totals,
        column_totals=column_totals,
        grand_total=grand_total,
    )


def save_rm_stock_records(
    store_path: str | Path,
    records: Iterable[RmStockRecord],
    source_file: str = "",
    source_sheet: str = "",
) -> None:
    """Persist extracted RM stock rows so they're still there after a restart."""

    save_records(
        store_path, records, version=STORE_VERSION,
        source_file=source_file, source_sheet=source_sheet,
    )


def load_rm_stock_records(store_path: str | Path) -> tuple[list[RmStockRecord], str, str]:
    """Return (records, source_file, source_sheet) last saved by extraction."""

    return load_records(store_path, RmStockRecord)
