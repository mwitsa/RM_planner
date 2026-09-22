"""Extraction for the "PD เกิดจริง" (actual HO distribution/yield) workbook.

The workbook (commonly exported as .xlsb) has several sheets; only the raw
"DATA" sheet is read here, which has 60 columns covering farm/lot identity,
work-point routing, and weight/yield figures at each processing step.
"""

from __future__ import annotations

from collections.abc import Collection, Iterable
from dataclasses import dataclass
from pathlib import Path

from rm_planner.inventory._workbook_io import (
    cell_date_text,
    cell_float,
    cell_text,
    load_records,
    read_sheet_names,
    read_sheet_rows,
    save_records,
    validated_path,
)

STORE_VERSION = 1
EXPECTED_COLUMN_COUNT = 60
PIVOT_BLANK_LABEL = "(blank)"

# (field name, source column header) in source column order.
PD_ACTUAL_COLUMNS = (
    ("farm_pond", "ฟาร์ม-บ่อ"),
    ("type", "Type"),
    ("material_lot", "ล็อตวัตถุดิบ"),
    ("size", "ขนาด"),
    ("product_code", "รหัสสินค้า"),
    ("product", "สินค้า"),
    ("batch_no", "เลขที่ Batch"),
    ("production_code", "Production Code"),
    ("sku", "SKU"),
    ("eu_code", "EU Code"),
    ("julian_code", "Julian Code"),
    ("rope_color", "สีเชือก"),
    ("customer_expiry_date", "วันหมดอายุ(ลูกค้า)"),
    ("package_type", "ชนิดแพ็คเกต"),
    ("work_type", "ประเภทงานที่ทำ"),
    ("condition", "สภาพ"),
    ("receive_type", "ประเภทการรับ"),
    ("previous_work_point", "จุดงานก่อนหน้า"),
    ("previous_work_point_name", "ชื่อจุดงานก่อนหน้า"),
    ("actual_weight_kg", "น้ำหนักชั่งจริง(กก.)"),
    ("weight_diff_kg", "น้ำหนักต่าง(กก.)"),
    ("remark", "หมายเหตุ"),
    ("column1", "Column1"),
    ("transaction_date", "วันที่ทำรายการ"),
    ("product_code_2", "รหัสสินค้า2"),
    ("product_name_3", "ชื่อสินค้า3"),
    ("size_out", "ขนาด Out"),
    ("condition_out", "สภาพ Out"),
    ("distribution_type", "ประเภทการกระจาย"),
    ("next_work_point", "จุดงานถัดไป"),
    ("next_work_point_name", "ชื่อจุดงานถัดไป"),
    ("weight_out_kg", "น้ำหนัก(กก.)ออก"),
    ("yield_percent", "%Yield "),
    ("month", "Month"),
    ("week", "Week"),
    ("midpoint", "ค่ากลาง"),
    ("size_ho", "Size HO"),
    ("size_ho_pcs_per_kg_input", "ขนาดHO ตัว/กก. Input"),
    ("size_range", "ช่วง Size"),
    ("size_range_rm", "ช่วง Size RM"),
    ("std_weight_output", "STD Weight Out Put"),
    ("std_weight_input", "STD Weight InPut"),
    ("send_type", "ประเภทการส่ง"),
    ("size_ho_send", "Size HO ส่ง"),
    ("midpoint_send_peeled", "ค่ากลางส่งปอก"),
    ("size_ho_pcs_per_kg_send", "ขนาดHO ตัว/กก.ส่ง"),
    ("size_range_ho_peeled", "ช่วงSize HO ปอก"),
    ("quantity_ho_send", "ปริมาณHO ส่ง"),
    ("quantity_ho_from_farm", "ปริมาณHO จากฟาร์ม"),
    ("condition_send", "สภาพส่ง"),
    ("size_ho_farm", "Size HO ฟาร์ม"),
    ("purchase_request_no", "เลขที่ใบขอซื้อ"),
    ("receipt_no", "เลขที่รับสินค้า"),
    ("size_midpoint_output", "Sizeค่ากลาง Out put"),
    ("size_ho_output", "Size HO Out Put"),
    ("size_range_ho_output", "ช่วงSize HO Out Put"),
    ("day", "Day"),
    ("month2", "Month2"),
    ("status", "Status"),
    ("farm_type", "ประเภทฟาร์ม"),
)

# บาท/ก.ก.-style summable quantities; everything else (codes, size labels,
# reference midpoints) is kept as text, matching rm_stock_data.py's approach.
PD_ACTUAL_FLOAT_FIELDS = {
    "actual_weight_kg", "weight_diff_kg", "weight_out_kg", "yield_percent",
    "quantity_ho_send", "quantity_ho_from_farm",
}
_DATE_FIELDS = {"customer_expiry_date", "transaction_date"}


@dataclass(frozen=True, slots=True)
class PdActualRecord:
    farm_pond: str
    type: str
    material_lot: str
    size: str
    product_code: str
    product: str
    batch_no: str
    production_code: str
    sku: str
    eu_code: str
    julian_code: str
    rope_color: str
    customer_expiry_date: str
    package_type: str
    work_type: str
    condition: str
    receive_type: str
    previous_work_point: str
    previous_work_point_name: str
    actual_weight_kg: float
    weight_diff_kg: float
    remark: str
    column1: str
    transaction_date: str
    product_code_2: str
    product_name_3: str
    size_out: str
    condition_out: str
    distribution_type: str
    next_work_point: str
    next_work_point_name: str
    weight_out_kg: float
    yield_percent: float
    month: str
    week: str
    midpoint: str
    size_ho: str
    size_ho_pcs_per_kg_input: str
    size_range: str
    size_range_rm: str
    std_weight_output: str
    std_weight_input: str
    send_type: str
    size_ho_send: str
    midpoint_send_peeled: str
    size_ho_pcs_per_kg_send: str
    size_range_ho_peeled: str
    quantity_ho_send: float
    quantity_ho_from_farm: float
    condition_send: str
    size_ho_farm: str
    purchase_request_no: str
    receipt_no: str
    size_midpoint_output: str
    size_ho_output: str
    size_range_ho_output: str
    day: str
    month2: str
    status: str
    farm_type: str


def list_sheets(workbook_path: str | Path) -> list[str]:
    return read_sheet_names(validated_path(workbook_path))


def extract_pd_actual_records(workbook_path: str | Path, sheet_name: str) -> list[PdActualRecord]:
    path = validated_path(workbook_path)
    rows = read_sheet_rows(path, sheet_name)
    if not rows:
        return []
    records: list[PdActualRecord] = []
    for row in rows[1:]:
        if len(row) < EXPECTED_COLUMN_COUNT or not any(cell_text(value) for value in row):
            continue
        values = {}
        for index, (field_name, _header) in enumerate(PD_ACTUAL_COLUMNS):
            cell = row[index]
            if field_name in _DATE_FIELDS:
                values[field_name] = cell_date_text(cell)
            elif field_name in PD_ACTUAL_FLOAT_FIELDS:
                values[field_name] = cell_float(cell)
            else:
                values[field_name] = cell_text(cell)
        records.append(PdActualRecord(**values))
    return records


def save_pd_actual_records(
    store_path: str | Path,
    records: list[PdActualRecord],
    source_file: str = "",
    source_sheet: str = "",
) -> None:
    """Persist extracted PD เกิดจริง rows so they're still there after a restart."""

    save_records(
        store_path, records, version=STORE_VERSION,
        source_file=source_file, source_sheet=source_sheet,
    )


def load_pd_actual_records(store_path: str | Path) -> tuple[list[PdActualRecord], str, str]:
    """Return (records, source_file, source_sheet) last saved by extraction."""

    return load_records(store_path, PdActualRecord)


@dataclass(frozen=True, slots=True)
class FarmSizeWeightPivot:
    farm_keys: tuple[str, ...]
    size_keys_by_farm: dict[str, tuple[str, ...]]
    matrix: dict[str, dict[str, float]]
    farm_totals: dict[str, float]
    grand_total: float


def pivot_weight_out_by_farm_and_size(
    records: Iterable[PdActualRecord],
    transaction_dates: Collection[str] | None = None,
) -> FarmSizeWeightPivot:
    """Sum of น้ำหนัก(กก.)ออก, grouped by ฟาร์ม-บ่อ (rows) then ขนาด Out (sub-rows).

    Mirrors the reference Excel PivotTable ("STOCK แกลง 2" pivot): an
    optional วันที่ทำรายการ filter (one or more dates); blank farm/size
    values are grouped under "(blank)", matching Excel.
    """

    filtered = [
        record for record in records
        if not transaction_dates or record.transaction_date in transaction_dates
    ]
    matrix: dict[str, dict[str, float]] = {}
    for record in filtered:
        farm = record.farm_pond or PIVOT_BLANK_LABEL
        size = record.size_out or PIVOT_BLANK_LABEL
        matrix.setdefault(farm, {})
        matrix[farm][size] = matrix[farm].get(size, 0.0) + record.weight_out_kg
    farm_keys = tuple(sorted(matrix))
    size_keys_by_farm = {farm: tuple(sorted(matrix[farm])) for farm in farm_keys}
    farm_totals = {farm: sum(matrix[farm].values()) for farm in farm_keys}
    grand_total = sum(farm_totals.values())
    return FarmSizeWeightPivot(
        farm_keys=farm_keys,
        size_keys_by_farm=size_keys_by_farm,
        matrix=matrix,
        farm_totals=farm_totals,
        grand_total=grand_total,
    )
