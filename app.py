"""Tkinter desktop UI for extracting production orders from แผน.xlsx."""

from __future__ import annotations

import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from extractor import (
    ExtractionResult,
    choose_default_sheet,
    export_csv,
    export_json,
    extract_orders,
    list_sheets,
)


class ProductionPlanApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Production Plan Extractor / โปรแกรมดึงข้อมูลแผนผลิต")
        self.geometry("1180x720")
        self.minsize(900, 560)

        self.file_var = tk.StringVar()
        self.sheet_var = tk.StringVar()
        self.month_var = tk.StringVar(value="All months / ทุกเดือน")
        self.summary_var = tk.StringVar(value="Select a workbook to begin.")
        self.status_var = tk.StringVar(value="Ready")
        self.result: ExtractionResult | None = None

        self._configure_style()
        self._build_ui()
        self._load_default_workbook()

    def _configure_style(self) -> None:
        style = ttk.Style(self)
        if "vista" in style.theme_names():
            style.theme_use("vista")
        style.configure("Title.TLabel", font=("Segoe UI", 18, "bold"))
        style.configure("Summary.TLabel", font=("Segoe UI", 10, "bold"))
        style.configure("Treeview", rowheight=25, font=("Segoe UI", 9))
        style.configure("Treeview.Heading", font=("Segoe UI", 9, "bold"))

    def _build_ui(self) -> None:
        container = ttk.Frame(self, padding=18)
        container.pack(fill=tk.BOTH, expand=True)

        ttk.Label(container, text="Production Plan Data Extractor", style="Title.TLabel").pack(anchor=tk.W)
        ttk.Label(
            container,
            text="Column B → production date/month   |   Column J → customer   |   Column V → order volume",
        ).pack(anchor=tk.W, pady=(2, 16))

        source = ttk.LabelFrame(container, text="Source workbook", padding=12)
        source.pack(fill=tk.X)
        source.columnconfigure(1, weight=1)

        ttk.Label(source, text="Excel file:").grid(row=0, column=0, sticky=tk.W, padx=(0, 8))
        ttk.Entry(source, textvariable=self.file_var).grid(row=0, column=1, sticky=tk.EW)
        ttk.Button(source, text="Browse…", command=self._browse).grid(row=0, column=2, padx=(8, 0))

        ttk.Label(source, text="Worksheet:").grid(row=1, column=0, sticky=tk.W, padx=(0, 8), pady=(10, 0))
        self.sheet_combo = ttk.Combobox(source, textvariable=self.sheet_var, state="readonly", width=35)
        self.sheet_combo.grid(row=1, column=1, sticky=tk.W, pady=(10, 0))
        self.extract_button = ttk.Button(source, text="Extract data", command=self._start_extraction)
        self.extract_button.grid(row=1, column=2, padx=(8, 0), pady=(10, 0))

        controls = ttk.Frame(container)
        controls.pack(fill=tk.X, pady=(14, 8))
        ttk.Label(controls, textvariable=self.summary_var, style="Summary.TLabel").pack(side=tk.LEFT)
        ttk.Button(controls, text="Export JSON", command=self._export_json, state=tk.DISABLED).pack(
            side=tk.RIGHT, padx=(8, 0)
        )
        ttk.Button(controls, text="Export CSV", command=self._export_csv, state=tk.DISABLED).pack(side=tk.RIGHT)
        self.export_buttons = controls.winfo_children()[-2:]

        filter_frame = ttk.Frame(container)
        filter_frame.pack(fill=tk.X, pady=(0, 8))
        ttk.Label(filter_frame, text="Preview month:").pack(side=tk.LEFT)
        self.month_combo = ttk.Combobox(
            filter_frame,
            textvariable=self.month_var,
            state="readonly",
            width=22,
            values=["All months / ทุกเดือน"],
        )
        self.month_combo.pack(side=tk.LEFT, padx=(8, 0))
        self.month_combo.bind("<<ComboboxSelected>>", lambda _event: self._refresh_preview())

        table_frame = ttk.Frame(container)
        table_frame.pack(fill=tk.BOTH, expand=True)
        columns = ("date", "month", "customer", "volume", "sheet", "row")
        self.tree = ttk.Treeview(table_frame, columns=columns, show="headings")
        headings = {
            "date": "Production date",
            "month": "Production month",
            "customer": "Customer",
            "volume": "Order volume",
            "sheet": "Source sheet",
            "row": "Source row",
        }
        widths = {"date": 120, "month": 120, "customer": 440, "volume": 120, "sheet": 140, "row": 90}
        for column in columns:
            self.tree.heading(column, text=headings[column])
            anchor = tk.E if column in ("volume", "row") else tk.W
            self.tree.column(column, width=widths[column], minwidth=70, anchor=anchor)

        vertical = ttk.Scrollbar(table_frame, orient=tk.VERTICAL, command=self.tree.yview)
        horizontal = ttk.Scrollbar(table_frame, orient=tk.HORIZONTAL, command=self.tree.xview)
        self.tree.configure(yscrollcommand=vertical.set, xscrollcommand=horizontal.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        vertical.grid(row=0, column=1, sticky="ns")
        horizontal.grid(row=1, column=0, sticky="ew")
        table_frame.rowconfigure(0, weight=1)
        table_frame.columnconfigure(0, weight=1)

        status = ttk.Label(container, textvariable=self.status_var, relief=tk.SUNKEN, anchor=tk.W, padding=(6, 3))
        status.pack(fill=tk.X, pady=(8, 0))

    def _load_default_workbook(self) -> None:
        candidate = Path(__file__).resolve().parent / "แผน.xlsx"
        if candidate.is_file():
            self.file_var.set(str(candidate))
            self._load_sheets()

    def _browse(self) -> None:
        selected = filedialog.askopenfilename(
            title="Select production plan workbook",
            filetypes=[("Excel workbook", "*.xlsx *.xlsm"), ("All files", "*.*")],
        )
        if selected:
            self.file_var.set(selected)
            self._load_sheets()

    def _load_sheets(self) -> None:
        try:
            workbook_path = self.file_var.get().strip()
            sheets = list_sheets(workbook_path)
            default_sheet = choose_default_sheet(workbook_path)
            self.sheet_combo.configure(values=sheets)
            self.sheet_var.set(default_sheet)
            self.status_var.set(f"Loaded {len(sheets)} worksheets. Suggested: {default_sheet.strip()}")
        except Exception as exc:
            self.sheet_combo.configure(values=[])
            self.sheet_var.set("")
            self.status_var.set("Could not read workbook.")
            messagebox.showerror("Workbook error", str(exc))

    def _start_extraction(self) -> None:
        if not self.file_var.get().strip() or not self.sheet_var.get():
            messagebox.showwarning("Missing source", "Please select an Excel file and worksheet.")
            return
        self.extract_button.configure(state=tk.DISABLED)
        self.status_var.set("Extracting data…")
        threading.Thread(target=self._extract_worker, daemon=True).start()

    def _extract_worker(self) -> None:
        try:
            result = extract_orders(self.file_var.get().strip(), self.sheet_var.get())
            self.after(0, self._show_result, result)
        except Exception as exc:
            self.after(0, self._show_error, exc)

    def _show_result(self, result: ExtractionResult) -> None:
        self.result = result
        months = sorted({record.production_month for record in result.records})
        customers = {record.customer_name for record in result.records}
        total_volume = sum(record.order_volume for record in result.records)
        self.month_combo.configure(values=["All months / ทุกเดือน", *months])
        self.month_var.set("All months / ทุกเดือน")
        self.summary_var.set(
            f"{len(result.records):,} orders  |  {len(customers):,} customers  |  "
            f"{len(months):,} months  |  volume {total_volume:,.2f}"
        )
        for button in self.export_buttons:
            button.configure(state=tk.NORMAL)
        self.extract_button.configure(state=tk.NORMAL)
        self.status_var.set(
            f"Complete. Header row {result.header_row}; {len(result.issues):,} incomplete/non-order rows skipped."
        )
        self._refresh_preview()

    def _show_error(self, exc: Exception) -> None:
        self.extract_button.configure(state=tk.NORMAL)
        self.status_var.set("Extraction failed.")
        messagebox.showerror("Extraction error", str(exc))

    def _refresh_preview(self) -> None:
        self.tree.delete(*self.tree.get_children())
        if not self.result:
            return
        selected_month = self.month_var.get()
        records = self.result.records
        if selected_month != "All months / ทุกเดือน":
            records = [record for record in records if record.production_month == selected_month]
        for record in records:
            self.tree.insert(
                "",
                tk.END,
                values=(
                    record.production_date,
                    record.production_month,
                    record.customer_name,
                    f"{record.order_volume:,.6f}".rstrip("0").rstrip("."),
                    record.source_sheet,
                    record.source_row,
                ),
            )

    def _export_csv(self) -> None:
        if not self.result:
            return
        destination = filedialog.asksaveasfilename(
            title="Export structured orders as CSV",
            defaultextension=".csv",
            initialfile="production_orders.csv",
            filetypes=[("CSV file", "*.csv")],
        )
        if destination:
            export_csv(self.result.records, destination)
            self.status_var.set(f"CSV exported: {destination}")
            messagebox.showinfo("Export complete", f"Saved {len(self.result.records):,} orders.")

    def _export_json(self) -> None:
        if not self.result:
            return
        destination = filedialog.asksaveasfilename(
            title="Export structured orders as JSON",
            defaultextension=".json",
            initialfile="production_orders.json",
            filetypes=[("JSON file", "*.json")],
        )
        if destination:
            export_json(self.result.records, destination)
            self.status_var.set(f"JSON exported: {destination}")
            messagebox.showinfo("Export complete", f"Saved {len(self.result.records):,} orders.")


if __name__ == "__main__":
    ProductionPlanApp().mainloop()
