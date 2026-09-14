"""SummaryView screen behavior."""

from __future__ import annotations

from .common import *  # shared UI types, domain services, and display constants


class SummaryViewMixin:
    def _build_summary_tab(self) -> None:
        ttk.Label(
            self.summary_tab,
            text=(
                "เทียบปริมาณกุ้งต่อวัน: Assortment (จับได้) เทียบกับ Order (ใช้จริง, "
                "น้ำหนัก HO) แยกตามไซซ์ RM — 51-75=M/HC, 76-100=S/SS, 101+=BK"
            ),
            wraplength=900,
            justify=tk.LEFT,
        ).pack(fill=tk.X, pady=(0, 8), anchor=tk.W)

        table_frame = ttk.Frame(self.summary_tab)
        table_frame.pack(fill=tk.BOTH, expand=True)
        summary_columns = ("date", "group", "assortment_kg", "order_used_kg", "difference_kg")
        self.summary_columns = summary_columns
        self.summary_headings = {
            "date": "วันที่",
            "group": "ไซซ์ RM",
            "assortment_kg": "Assortment (กก.)",
            "order_used_kg": "Order WT/HO (กก.)",
            "difference_kg": "ขาด/เหลือ (กก.)",
        }
        tree = ttk.Treeview(table_frame, columns=summary_columns, show="headings")
        widths = {
            "date": 100,
            "group": 150,
            "assortment_kg": 140,
            "order_used_kg": 140,
            "difference_kg": 140,
        }
        for column in summary_columns:
            tree.heading(column, text=self.summary_headings[column])
            numeric = column != "date" and column != "group"
            tree.column(column, width=widths[column], minwidth=80, anchor=tk.E if numeric else tk.W)
        tree.tag_configure("shortage", foreground="#b00020")
        vertical = ttk.Scrollbar(table_frame, orient=tk.VERTICAL, command=tree.yview)
        horizontal = ttk.Scrollbar(table_frame, orient=tk.HORIZONTAL, command=tree.xview)
        tree.configure(yscrollcommand=vertical.set, xscrollcommand=horizontal.set)
        tree.grid(row=0, column=0, sticky="nsew")
        vertical.grid(row=0, column=1, sticky="ns")
        horizontal.grid(row=1, column=0, sticky="ew")
        table_frame.rowconfigure(0, weight=1)
        table_frame.columnconfigure(0, weight=1)
        self.summary_tree = tree

        ttk.Label(
            self.summary_tab,
            textvariable=self.summary_status_var,
            relief=tk.SUNKEN,
            anchor=tk.W,
            padding=(6, 3),
        ).pack(fill=tk.X, pady=(8, 0))

    def _refresh_summary_table(self) -> None:
        if self.summary_tree is None:
            return
        self.summary_tree.delete(*self.summary_tree.get_children())
        records = self.result.records if self.result is not None else list(self.saved_order_records.values())
        missing_sources = [
            name
            for name, loaded in (("Order", bool(records)), ("Assortment", bool(self.assortment_upload_records)))
            if not loaded
        ]
        if missing_sources:
            tab_word = "tab" if len(missing_sources) == 1 else "tabs"
            self.summary_status_var.set(
                f"Load data on the {' and '.join(missing_sources)} {tab_word} first."
            )
            return
        rows = build_order_summary_rows(self.assortment_upload_records, records)
        plan_start = self.plan_start_date_var.get()
        plan_end = self.plan_end_date_var.get()
        date_range_note = ""
        if plan_start and plan_end:
            if plan_start > plan_end:
                plan_start, plan_end = plan_end, plan_start
            rows = [row for row in rows if plan_start <= row.record_date <= plan_end]
            date_range_note = f" from {plan_start} to {plan_end} (per Plan tab)"
        for index, row in enumerate(rows):
            difference = row.difference_kg
            self.summary_tree.insert(
                "",
                tk.END,
                iid=str(index),
                values=(
                    row.record_date,
                    row.group_label,
                    f"{row.assortment_kg:,.0f}",
                    f"{row.data_used_kg:,.0f}",
                    f"{difference:,.0f}",
                ),
                tags=("shortage",) if difference < 0 else (),
            )
        dates = {row.record_date for row in rows}
        self.summary_status_var.set(
            f"Showing {len(rows):,} rows across {len(dates):,} dates and "
            f"{len(RM_SIZE_GROUPS)} RM size groups{date_range_note}."
        )
