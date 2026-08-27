# RM Planner — production plan extractor

This first project step converts the selected worksheet in
`Data/Order/แผน.xlsx` into a stable order dataset through a small Windows
desktop UI.

## Data mapping

| Excel source | Structured field | Example |
| --- | --- | --- |
| Column C | `date`, `month`, and `year` | `04`, `01`, `2024` |
| Column H | `country` | `USA` |
| Column J | `customer_name` | `Bellisio` |
| Column K | `group_1` | `Wonton` |
| Column L | `group_2` | `Cooked Wonton` |
| Column O | `packaging` | `130g*24` |
| Column U | `soup` | `Regular` |
| Column V | `order_volume` | `901` |
| App input | `production` | Actual quantity produced |

For example, the Excel date `2024-01-04` becomes date `04`, month `01`, and
year `2024`. Completely blank rows are ignored. Rows that have some source data
but are not complete orders are counted as skipped issues.

Column C can also contain a month-only value such as `'10-2026`. This means the
order has no specific production day, so it is retained with a blank `date`,
`month` = `10`, and `year` = `2026`.

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

The **Order** tab automatically finds `Data/Order/แผน.xlsx`, suggests the
worksheet whose B/J/V headers match the required structure, previews the orders,
filters the preview by production month, and exports either CSV or JSON. The
file browser can still be used to select a different workbook manually.
Double-click a Production cell to enter the quantity produced, then click
**Save orders**. Saved orders and production quantities reload from
`Data/Order/saved_orders.json` and are restored after re-extraction.
The filter panel supports combined filtering by period, year, month, date,
country, customer, Group 1, Group 2, packaging, soup, and production status.

The **Plan Rule** tab stores text rules in waterfall priority. Add or update a
rule, drag it up or down (or use the Move buttons), and click **Save rules**.
The rule at the top is applied first. Saved rules reload when the app starts.

The **Class Define** tab stores classification master data with required Class,
Name, and Define fields. Saved classes reload on startup and can be selected for
editing and updating.

The **Assortment STD** tab automatically loads `Data/RM/assortment.xlsx` as
read-only shrimp assortment master data. Its columns are harvested base sizes,
its rows are actual output-size ranges, and every matrix cell is the expected
output yield percentage. Each base-size column is checked to ensure its output
distribution totals 100%. The separate **Assortment Actual** tab is reserved
for actual harvest assortment data. It starts with one empty card containing
Size and Weight fields; use **Add another box** to record additional actual
assortment entries. Choose Date, Month, and Year before saving. Saved records
appear in the history panel on the right and can be loaded, edited, and updated.

CSV is encoded as UTF-8 with BOM so Thai customer names display correctly in
Excel. JSON is UTF-8 and preserves Thai characters directly.
