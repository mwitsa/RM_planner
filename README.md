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

The **Assortment STD** page places two range columns—M and S+—before the
actual output-size column. Drag a colored box to move its complete range, or
drag its top or bottom handle to expand or contract it vertically. Click
**Save ranges** to keep the selections in
`Data/RM/assortment_size_ranges.json` for the next app session.
The Order table uses compact Excel-style filters directly in its column
headers, so no separate filter panel takes up space. Click a header to sort,
search its available values, select one or several values with checkboxes, or
clear its filter. The menu includes Excel-style **Select All**, **OK**, and
**Cancel** controls. Every visible Order column is filterable, including order
number, all quantity columns, and Production. Filters cascade, so each selection
limits the available choices in every other header. A dot marks filtered
columns, an arrow marks the active sort direction, and the summary recalculates
from the visible orders.

Orders are shown oldest-to-newest by their complete year, month, and date, with
today first. Past orders are hidden by default; use **Show past orders** to
include them and **Hide past orders** to return to the current view. Orders that
only specify a month use the final day of that month for chronological sorting
and the past-order check, but they appear after every explicitly dated order in
that month (including orders dated on the final day).

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

The **Capacity** tab stores separate maximum capacities and independent 0–100%
utilization settings for เกี๊ยวดิบ and เกี๊ยวสุก. Changing one slider does not
change the other. Each plain settings panel previews the daily capacity that
Plan will use. One button saves both maximums and percentages, which reload when
the app starts. Existing complementary-split settings are migrated while
preserving their previous raw and cooked available capacities.

The **Plan** tab treats the Country class Group as the order market: Group `1`
is **Export**, Group `2` is **Domestic**, and any other/blank value is
**Unassigned**. Load-date urgency is protected first. Orders competing at the
same priority are sequenced Export before Domestic, then by the lower Group 1
value (the allergen sequence). RM is strictly separated by its **Use for** value:
Export RM can only supply Export orders and Domestic RM can only supply Domestic
orders. Unassigned orders and RM only match each other. The generated and
unplanned tables show **Use for** so this decision is visible.

**Stock** shows a plain overview for total weight, unused weight, estimated
wontons, and the latest availability date. M and S+ have separate stock sections.
Click **Show details** to expand the dated
RM-arrival table and inspect the individual RM IDs behind the balances. Legacy
existing-stock records remain readable in Stock and Plan, but the unused
Existing Stock entry page is no longer shown.

The **Assortment STD** page automatically loads `Data/RM/assortment.xlsx` as
read-only shrimp assortment master data. Its columns are harvested base sizes,
its rows are actual output-size ranges, and every matrix cell is the expected
output yield percentage. Each base-size column is checked to ensure its output
distribution totals 100%. Enter a harvest date, base size (for example `74`),
and weight in kilograms above the matrix to predict the actual size distribution.
The app uses column `S.74`, splits the weight by its percentages, and transfers
the size/weight rows to **Update Stock** for review and saving.
Generated weights use whole kilograms and are allocated so their sum remains
equal to the rounded harvest weight.
Transferred rows carry a persistent **PREDICTION** type, while manually entered
data carries an **ACTUAL** type. Saved stock also displays and preserves this
Type when a record is edited. The Type dropdown allows either
classification to be selected manually before saving or while editing. A saved
history row can also be permanently deleted after confirmation. The
separate **Update Stock** page is used for actual harvest assortment data. Stock
details and actions are grouped at the top, while each size and weight entry uses
one compact row. Use **Add row** for additional entries. The page shows completed
row count and total weight while entering data. Saved stock appears in the panel
on the right and can be loaded, edited, and updated.
Each completed size range is automatically classified against the current M/S+
ranges. A range crossing both classes or outside both classifications shows
`Unused`.
Saved stock summarizes the weight for M, S+, and Unused in separate columns.
