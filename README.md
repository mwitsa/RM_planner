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
| Column Q | `wontons_per_cup` | `8` |
| Column S | `rm_size` | `M` |
| Column U | `soup` | `Regular` |
| Column V | `order_unit` | `901` |
| Column AI | `order_cups` | `14416` |
| Derived: AI / V | `cups_per_unit` | `16` |
| Derived: AI × Q | `total_wontons` | `160000` |
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
worksheet whose C/J/V headers match the required structure, previews the orders,
and provides combined filters for the saved order data. The file browser can
still be used to select a different workbook manually.
Each extraction automatically appends only orders not already stored in
`Data/Order/saved_orders.json`; existing orders and their Production values are
preserved. The accumulated dataset reloads when the app starts. Double-click a
Production cell to enter the quantity produced, then click **Save orders** to
keep that manual Production change.

The **Assortment Predict** tab places three range columns—M, S, and SS—before the
actual output-size column. Drag a colored box to move its complete range, or
drag its top or bottom handle to expand or contract it vertically. Click
**Save ranges** to keep the selections in
`Data/RM/assortment_size_ranges.json` for the next app session.
The filter panel supports combined filtering by year, month, date, country,
customer, Group 1, Group 2, packaging, RM Size, soup, ถ้วย/Unit, and production
status. Filter dropdowns cascade, so each selection limits the available choices
in every other filter. The summary above the filters recalculates from the
visible orders. Click any Order-table column header to sort it; numeric columns
start largest-to-lowest, text columns start A-to-Z, and a second click reverses
the direction.

The **Class Rule** tab stores text rules in waterfall priority. Add or update a
rule, drag it up or down (or use the Move buttons), and click **Save rules**.
The rule at the top is applied first. Saved rules reload when the app starts.

The **Class Define** tab stores Class, Name, optional Group, and optional Value
fields. Group remains the numeric planning priority, while Value is additional
master-data information available for future planning rules. Each
Order extraction automatically adds missing Class + Name pairs for Country,
Customer, Group 1, Group 2, Packaging, Soup, and ถ้วย/Unit. Existing pairs and
their manually assigned Group values are preserved. Saved rows can be filtered
by Class, partial Name text, and Group, including rows whose Group is blank.

The **Capacity** tab stores a complementary production split between เกี๊ยวดิบ
and เกี๊ยวสุก plus separate maximum capacities for each type. The slider value
is the raw-wonton share and cooked receives the remainder; for example, ดิบ 60%
automatically means สุก 40%. Split and maximum-capacity settings can be saved
independently and reload when the app starts. Moving the slider previews the
available daily capacity for both types, and Plan uses those split limits. The
page is organized as maximum inputs, a colored allocation bar/slider, and the
resulting Plan capacity; one button saves the complete setup.

The **Plan** tab treats the Country class Group as the order market: Group `1`
is **Export**, Group `2` is **Domestic**, and any other/blank value is
**Unassigned**. Load-date urgency is protected first. Orders competing at the
same priority are sequenced Export before Domestic, then by the lower Group 1
value (the allergen sequence). RM is strictly separated by its **Use for** value:
Export RM can only supply Export orders and Domestic RM can only supply Domestic
orders. Unassigned orders and RM only match each other. The generated and
unplanned tables show **Use for** so this decision is visible.

The RM sidebar includes **Existing Stock** for old/opening inventory that is
already classified and does not need an assortment calculation. Choose its
availability date and Domestic/Export use, then enter weight and average shrimp
pieces/kg directly for any M, S, and SS classes. Existing stock receives an RM
ID, can be edited or deleted, appears as **Existing in (kg)** on Stock Timeline,
and is consumed by Plan only for an order with the same market and RM class.
Stock Timeline shows the latest combined stock as one summary sentence by
default. Click **Show details** to expand the dated RM-arrival table and inspect
the individual RM IDs behind that balance.

The **Assortment Predict** tab automatically loads `Data/RM/assortment.xlsx` as
read-only shrimp assortment master data. Its columns are harvested base sizes,
its rows are actual output-size ranges, and every matrix cell is the expected
output yield percentage. Each base-size column is checked to ensure its output
distribution totals 100%. Enter a harvest date, base size (for example `74`),
and weight in kilograms above the matrix to predict the actual size distribution.
The app uses column `S.74`, splits the weight by its percentages, and transfers
the size/weight rows to the **Assortment Actual** tab for review and saving.
Generated weights use whole kilograms and are allocated so their sum remains
equal to the rounded harvest weight.
Transferred rows carry a persistent amber **PREDICTION** flag, while manually
entered data carries a green **ACTUAL** flag. Saved history also displays and
preserves this Type when a record is edited. The Type dropdown allows either
classification to be selected manually before saving or while editing. A saved
history row can also be permanently deleted after confirmation. The
separate **Assortment Actual** tab is reserved
for actual harvest assortment data. It starts with one empty card containing
Size (start), Size (end), and Weight fields; use **Add another box** to record additional actual
assortment entries. Choose Date, Month, and Year before saving. Saved records
appear in the history panel on the right and can be loaded, edited, and updated.
Each completed size range is automatically classified against the current M/S/SS
ranges. Intersections show every matching class (for example `S, SS`), and a
range outside all three classifications shows `Unused`.
Saved history summarizes the weight for M, S, SS, and Unused in separate columns.
An overlapping row contributes its full weight to every matching class. The
overlap portion appears in parentheses after that class total, such as
`SS 4,244 (2,145)`.
