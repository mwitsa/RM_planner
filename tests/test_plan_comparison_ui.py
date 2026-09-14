"""Tk integration checks using isolated data and no real application loaders."""
from contextlib import ExitStack
from pathlib import Path
from tempfile import TemporaryDirectory
import tkinter as tk
import unittest
from unittest.mock import patch

from rm_planner.ui.core import ProductionPlanApp
from rm_planner.planning.alternatives import compare
import test_alternatives


class ComparisonUiTests(unittest.TestCase):
    def test_cards_profile_and_approval_windows(self):
        with ExitStack() as stack:
            directory = stack.enter_context(TemporaryDirectory())
            stack.enter_context(patch('rm_planner.ui.plan_view.PROJECT_ROOT', Path(directory)))
            for name in ('_load_default_workbook', '_load_saved_rules', '_load_assortment_data',
                         '_load_wonton_weight_settings', '_load_assortment_actual_history', '_load_saved_orders',
                         '_load_saved_class_definitions', '_load_capacity_settings', '_load_saved_master_data',
                         '_load_saved_assortment_upload'):
                stack.enter_context(patch.object(ProductionPlanApp, name))
            try:
                app = ProductionPlanApp()
            except tk.TclError as exc:
                if 'init.tcl' in str(exc) or 'display' in str(exc):
                    self.skipTest(str(exc))
                raise
            try:
                app.withdraw()
                context = test_alternatives.AlternativeTests().context()
                app._proposal_context = lambda: context
                app._show_proposals(context, compare(context))
                app.update_idletasks()
                self.assertEqual(len(app._proposal_cards.winfo_children()), 4)
                app._select_proposal(2)
                self.assertEqual(len(app._proposal_tables['daily'].get_children()), 7)
                tree = app._proposal_tables['jobs']
                tree.selection_set(tree.get_children()[0])
                app._proposal_job_dialog()
                app._proposal_settings_dialog()
                app._approve_proposal()
                app.update_idletasks()
                self.assertEqual(len([w for w in app.winfo_children() if isinstance(w,tk.Toplevel)]),3)
                approval = next(w for w in app.winfo_children() if isinstance(w,tk.Toplevel) and w.title().startswith('ยืนยัน '))
                for w in approval.winfo_children():
                    if isinstance(w,tk.ttk.Checkbutton): w.invoke()
                    if isinstance(w,tk.ttk.Entry): w.insert(0,'Test reviewer')
                with patch('rm_planner.ui.plan_view.messagebox.showinfo'):
                    next(w for w in approval.winfo_children() if isinstance(w,tk.ttk.Button)).invoke()
                self.assertEqual(len(list((Path(directory)/'Data'/'Planning'/'approved').glob('*.json'))),1)
                app._proposal_history()
                app.update_idletasks()
            finally:
                app.destroy()
