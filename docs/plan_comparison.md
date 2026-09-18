# Plan comparison

## Freeze top-up policy (current)

- Only the balanced proposal may use frozen stock. Baseline and reduced-RM
  proposals allocate fresh RM only.
- Saved existing-stock records and arrivals before the selected start date are
  opening frozen stock. Chilled arrivals become frozen on their configured
  freeze day.
- Allocate fresh RM first, then frozen stock only for the unmet requirement,
  matching market and size and respecting the arrival date. Allocations decrement
  the same lot balances, so stock cannot be spent twice.
- Replanned orders remain whole. Balanced search retains its existing cost and
  residual reduction criteria; frozen stock enables otherwise infeasible top-ups.
- Opening/existing stock is excluded from the card's timeframe residual.
  Blue diagonal sections show the fraction supplied by Freeze; red shows the
  remaining shortage. Production tooltips report fresh, Freeze and shortage kg.
  The stock rail uses the engine's recorded lot allocations.

The older workflow notes below describe the original implementation; where they
conflict with this policy or current code, the current policy takes precedence.

Plan now compares the imported Order production schedule with three bounded
pull-forward policies. Data remains the raw workbook view. Default lookahead is
7 days, with changes targeted at the first 3 days (both configurable, up to 31).
Work can be pulled from later days in the lookahead; quantities are subtracted
from the original day. The original Order workbook is never changed by approval.

## Staff workflow

1. Load Order, Stock, Class Define market mapping and Capacity. Choose a planning
   start date, then calculate. Orders need a full original production date.
2. Select an order row and set earliest permitted production date, readiness date,
   maximum **additional wontons**, reviewer, egg group and soup sequence rank.
   Lock work already started or otherwise fixed. Market mapping remains in Class
   Define. Identical egg-group labels mean compatible work; missing data is not
   assumed safe. Soup rank is ascending, with equal SKUs grouped within rank.
3. Enter shift hours, changeover minutes, hourly stop cost, freezing cost/kg and
   the assumed percentage of residual sent to freezing at the adjustment boundary.
   Blank costs or percentage mean unknown, not zero. A zero can be explicit.
4. Compare baseline, minimal disruption (confirmed materials only), reduced
   residual and cost-balanced policies. Inspect the full daily impact and issues.
5. Confirm remaining stock, shared materials for the complete bundle, locks and
   future impact. Save the selected plan with a reviewer. View saved versions via
   "แผนที่ยืนยันแล้ว". Approval does not reserve inventory or count production.

## Calculation boundaries

- Uses outstanding wontons after recorded production, original production dates,
  dated RM Stock records and configured wonton yields. Does **not** mix HO weights
  or Assortment shipment raw weights with usable RM kg. S and SS retain their order
  labels and consume one S+ stock pool. M uses M. Unsupported classes block a plan.
- RAW and COOKED capacities are independent. Production time is quantity divided
  by available daily capacity times configured shift hours. Changeover time is
  added for each consecutive different SKU (group, packaging, soup, RM identity).
- Markets and egg groups must match within each line/day. RM is partitioned by
  market and size, arrives on its saved date and carries forward. Unused stock is
  included in residual, but cannot be consumed. Recorded predictions require review.
- All lookahead days are checked for capacity and known RM deficits. Future
  shipments not present in Stock are not inferred. Baselines with hard violations
  are displayed but must be corrected before this limited pull-forward search.
- Search examines up to 60 orders/day, largest RM quantity first, using bounded
  quantity fitting. It is not proof of global optimality; alternatives can coincide.
- Cards compare residual **at the end of the adjustment window** and costs for that
  window. Today's residual is separate. Freeze cost is charged once at the boundary;
  this is a cost scenario, not an actual disposal or a shelf-life simulation.
- No automated BOM check, expiry, overtime, FG holding cost, monthly optimizer,
  or automatic adoption of an approved snapshot as the next baseline. Shared
  material confirmation supplements order readiness; it is not a stock ledger.
- Stock records previously represented arrivals before plan usage: staff must
  reconcile remaining physical stock before approving. The calculator does not
  silently subtract unknown historical usage.

## Code map

- `rm_planner/planning/alternatives.py`: adaptation, evaluation, three search policies.
- `rm_planner/planning/proposal_store.py`: preferences and versioned approval files.
- `rm_planner/ui/plan_view.py`: controls, cards, tables, review dialogs, history.
- `Data/Planning/preferences.json`: costs, readiness and locks (created on save).
- `Data/Planning/approved/`: immutable approval snapshots (created on approval).
- `tests/test_alternatives.py`: quantity, timing, readiness, material and cost checks.
- `tests/test_plan_comparison_ui.py`: isolated Tk startup/cards/dialog checks.

Run `python -m unittest discover -s tests -q`. Tk integration test skips only when
the runtime cannot initialize Tcl/display; rerun it with a desktop-capable runtime.
