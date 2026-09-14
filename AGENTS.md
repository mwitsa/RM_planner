# RM Planner code map

The implementation lives in `rm_planner/`. The root `app.py` only launches the
Tkinter app. Import application code directly from its `rm_planner` package.

- `rm_planner/ui/core.py` assembles the app and creates shared state and tabs.
- `rm_planner/ui/common.py` holds UI imports, display constants, and the
  project-root path used for `Data/`.
- `rm_planner/ui/*_view.py`, `class_define.py`, `existing_stock.py`, and
  `stock_editor.py` contain screen-specific methods. Search for a method name
  there before opening `core.py`.
- `rm_planner/orders/` handles order extraction, filtering, and persistence.
- `rm_planner/inventory/` handles assortment, stock records, sizes, and timeline.
- `rm_planner/planning/` handles capacity, classes, market labels, rules, and
  plan calculations.
- Plan comparison: `planning/alternatives.py` (engine), `planning/proposal_store.py`
  (saved reviews), `ui/plan_view.py` (screen). Read `docs/plan_comparison.md` for
  the 7-day / 3-day workflow and calculation boundaries before changing it.
- `rm_planner/master/` handles master workbook data.

Keep app data files in `Data/`, including `Data/Rules/plan_rules.json`. Run tests
with `python -m unittest discover -s tests -q` (or an available Python
executable). The `run_app.bat` launcher and `python app.py` remain the app entry
points.
