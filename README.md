# RM Planner — production plan extractor

This first project step converts the selected worksheet in `แผน.xlsx` into a
stable order dataset through a small Windows desktop UI.

## Data mapping

| Excel source | Structured field | Example |
| --- | --- | --- |
| Column B | `production_date` and derived `production_month` | `2024-01-03`, `2024-01` |
| Column J | `customer_name` | `Bellisio` |
| Column V | `order_volume` | `901` |

Every output row also includes `source_sheet` and `source_row` so it can be
traced back to Excel. Completely blank rows are ignored. Rows that have some
source data but are not complete orders are counted as skipped issues.

## Run the app

1. Install Python 3.10 or later from the official Windows installer (including
   its standard Tcl/Tk desktop UI component).
2. Install the dependency:

   ```powershell
   python -m pip install -r requirements.txt
   ```

3. Double-click `run_app.bat`, or run:

   ```powershell
   python app.py
   ```

The app automatically finds `แผน.xlsx` when it is beside `app.py`, suggests
the worksheet whose B/J/V headers match the required structure, previews the
orders, filters the preview by production month, and exports either CSV or JSON.

CSV is encoded as UTF-8 with BOM so Thai customer names display correctly in
Excel. JSON is UTF-8 and preserves Thai characters directly.
