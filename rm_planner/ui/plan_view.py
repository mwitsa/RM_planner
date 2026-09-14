"""PlanViewMixin behavior."""

from __future__ import annotations

from .common import *  # shared UI types and domain services


class PlanViewMixin:
    def _build_plan_tab(self) -> None:
        controls = ttk.Frame(self.plan_tab)
        controls.pack(fill=tk.X, pady=(0, 8))
        ttk.Label(controls, text="วันที่เริ่มต้น:").pack(side=tk.LEFT)
        self.plan_start_date_combo = ttk.Combobox(
            controls,
            textvariable=self.plan_start_date_var,
            state="readonly",
            width=14,
        )
        self.plan_start_date_combo.pack(side=tk.LEFT, padx=(4, 16))
        ttk.Label(controls, text="วันที่สิ้นสุด:").pack(side=tk.LEFT)
        self.plan_end_date_combo = ttk.Combobox(
            controls,
            textvariable=self.plan_end_date_var,
            state="readonly",
            width=14,
        )
        self.plan_end_date_combo.pack(side=tk.LEFT, padx=(4, 16))
        self.plan_start_date_combo.bind(
            "<<ComboboxSelected>>", lambda _event: self._refresh_plan_table()
        )
        self.plan_end_date_combo.bind(
            "<<ComboboxSelected>>", lambda _event: self._refresh_plan_table()
        )

        self.plan_table_frame = ttk.Frame(self.plan_tab)
        self.plan_table_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(
            self.plan_tab,
            textvariable=self.plan_status_var,
            relief=tk.SUNKEN,
            anchor=tk.W,
            padding=(6, 3),
        ).pack(fill=tk.X, pady=(8, 0))

    def _refresh_plan_date_options(self) -> None:
        """Repopulate the Plan tab's date pickers from the Data tab's loaded rows."""

        if not hasattr(self, "plan_start_date_combo"):
            return
        dates = sorted({row[0] for row in self.raw_data_all_rows if row and row[0]})
        self.plan_start_date_combo.configure(values=dates)
        self.plan_end_date_combo.configure(values=dates)
        if dates:
            if self.plan_start_date_var.get() not in dates:
                self.plan_start_date_var.set(dates[0])
            if self.plan_end_date_var.get() not in dates:
                self.plan_end_date_var.set(dates[-1])
        else:
            self.plan_start_date_var.set("")
            self.plan_end_date_var.set("")
        self._rebuild_plan_tree()
        self._refresh_plan_table()

    def _rebuild_plan_tree(self) -> None:
        for child in self.plan_table_frame.winfo_children():
            child.destroy()
        columns = list(self.raw_data_columns)
        self.plan_columns = columns
        if not columns:
            self.plan_tree = None
            return
        tree = ttk.Treeview(self.plan_table_frame, columns=columns, show="headings")
        for column, header in zip(columns, self.raw_data_headers):
            tree.heading(column, text=header)
            tree.column(column, width=110, minwidth=60, anchor=tk.W)
        vertical = ttk.Scrollbar(self.plan_table_frame, orient=tk.VERTICAL, command=tree.yview)
        horizontal = ttk.Scrollbar(self.plan_table_frame, orient=tk.HORIZONTAL, command=tree.xview)
        tree.configure(yscrollcommand=vertical.set, xscrollcommand=horizontal.set)
        tree.grid(row=0, column=0, sticky="nsew")
        vertical.grid(row=0, column=1, sticky="ns")
        horizontal.grid(row=1, column=0, sticky="ew")
        self.plan_table_frame.rowconfigure(0, weight=1)
        self.plan_table_frame.columnconfigure(0, weight=1)
        self.plan_tree = tree

    def _refresh_plan_table(self) -> None:
        if self.plan_tree is None:
            if not self.raw_data_all_rows:
                self.plan_status_var.set("Load data on the Data tab first.")
            self._refresh_summary_table()
            return
        self.plan_tree.delete(*self.plan_tree.get_children())
        start = self.plan_start_date_var.get()
        end = self.plan_end_date_var.get()
        if not start or not end:
            self.plan_status_var.set("Select a start and end date.")
            self._refresh_summary_table()
            return
        if start > end:
            start, end = end, start
        matching = [
            row for row in self.raw_data_all_rows if row and start <= row[0] <= end
        ]
        for index, row in enumerate(matching):
            self.plan_tree.insert("", tk.END, iid=str(index), values=row)
        self.plan_status_var.set(
            f"Showing {len(matching):,} of {len(self.raw_data_all_rows):,} rows "
            f"from {start} to {end}."
        )
        self._refresh_summary_table()
