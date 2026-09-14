"""ExistingStockMixin behavior."""

from __future__ import annotations

from .common import *  # shared UI types and domain services


class ExistingStockMixin:
    def _build_existing_stock_tab(self) -> None:
        ttk.Label(
            self.existing_stock_tab,
            text="Existing RM Stock",
            style="Summary.TLabel",
        ).pack(anchor=tk.W)
        ttk.Label(
            self.existing_stock_tab,
            text=(
                "Enter old/opening stock directly by M, S, and SS class. "
                "Average pieces/kg is used to estimate how many wontons the stock can produce."
            ),
        ).pack(anchor=tk.W, pady=(2, 10))

        self.existing_day_var = tk.StringVar()
        self.existing_month_var = tk.StringVar()
        self.existing_year_var = tk.StringVar()
        self.existing_market_var = tk.StringVar(value=market_display_label("domestic"))
        self.existing_stock_entry_vars: dict[str, dict[str, tk.StringVar]] = {
            size_class: {
                "weight": tk.StringVar(),
                "pieces_per_kg": tk.StringVar(
                    value=DEFAULT_EXISTING_STOCK_PIECES_PER_KG[size_class]
                ),
            }
            for size_class in SIZE_CLASSES
        }

        form = ttk.LabelFrame(self.existing_stock_tab, text="Opening stock details", padding=10)
        form.pack(fill=tk.X, pady=(0, 10))
        for column in range(8):
            form.columnconfigure(column, weight=1 if column in {6} else 0)

        ttk.Label(form, text="Date").grid(row=0, column=0, sticky=tk.W)
        ttk.Combobox(
            form,
            textvariable=self.existing_day_var,
            values=[f"{value:02d}" for value in range(1, 32)],
            state="readonly",
            width=5,
        ).grid(row=0, column=1, sticky=tk.W, padx=(6, 4))
        ttk.Label(form, text="Month").grid(row=0, column=2, sticky=tk.W, padx=(8, 0))
        ttk.Combobox(
            form,
            textvariable=self.existing_month_var,
            values=[f"{value:02d}" for value in range(1, 13)],
            state="readonly",
            width=5,
        ).grid(row=0, column=3, sticky=tk.W, padx=(6, 4))
        ttk.Label(form, text="Year").grid(row=0, column=4, sticky=tk.W, padx=(8, 0))
        ttk.Combobox(
            form,
            textvariable=self.existing_year_var,
            values=[str(value) for value in range(date.today().year - 10, date.today().year + 11)],
            state="readonly",
            width=7,
        ).grid(row=0, column=5, sticky=tk.W, padx=(6, 12))
        ttk.Label(form, text="Use for").grid(row=0, column=6, sticky=tk.E)
        ttk.Combobox(
            form,
            textvariable=self.existing_market_var,
            values=MARKET_DISPLAY_OPTIONS,
            state="readonly",
            width=12,
        ).grid(row=0, column=7, sticky=tk.W, padx=(6, 0))

        entry_frame = ttk.Frame(form)
        entry_frame.grid(row=1, column=0, columnspan=8, sticky="ew", pady=(12, 0))
        entry_frame.columnconfigure(1, weight=1)
        entry_frame.columnconfigure(2, weight=1)
        ttk.Label(entry_frame, text="RM class", style="Summary.TLabel").grid(
            row=0, column=0, sticky=tk.W, padx=(0, 14)
        )
        ttk.Label(entry_frame, text="Existing weight (kg)", style="Summary.TLabel").grid(
            row=0, column=1, sticky=tk.W, padx=(0, 8)
        )
        ttk.Label(entry_frame, text="Average shrimp (pieces/kg)", style="Summary.TLabel").grid(
            row=0, column=2, sticky=tk.W
        )
        for row_index, size_class in enumerate(SIZE_CLASSES, start=1):
            variables = self.existing_stock_entry_vars[size_class]
            ttk.Label(entry_frame, text=size_class, font=("Segoe UI", 10, "bold")).grid(
                row=row_index, column=0, sticky=tk.W, padx=(0, 14), pady=(6, 0)
            )
            ttk.Entry(entry_frame, textvariable=variables["weight"]).grid(
                row=row_index, column=1, sticky="ew", padx=(0, 8), pady=(6, 0)
            )
            ttk.Entry(entry_frame, textvariable=variables["pieces_per_kg"]).grid(
                row=row_index, column=2, sticky="ew", pady=(6, 0)
            )

        actions = ttk.Frame(form)
        actions.grid(row=2, column=0, columnspan=8, sticky=tk.E, pady=(12, 0))
        ttk.Button(actions, text="New", command=self._new_existing_stock_form).pack(
            side=tk.LEFT
        )
        self.existing_stock_save_button = ttk.Button(
            actions,
            text="Save existing stock",
            command=self._save_existing_stock,
        )
        self.existing_stock_save_button.pack(side=tk.LEFT, padx=(8, 0))

        history = ttk.LabelFrame(self.existing_stock_tab, text="Saved existing stock", padding=8)
        history.pack(fill=tk.BOTH, expand=True)
        history.rowconfigure(0, weight=1)
        history.columnconfigure(0, weight=1)
        columns = (
            "rm_id",
            "date",
            "market",
            "m_kg",
            "m_ppkg",
            "s_kg",
            "s_ppkg",
            "ss_kg",
            "ss_ppkg",
            "total_kg",
            "wontons",
        )
        self.existing_stock_tree = ttk.Treeview(history, columns=columns, show="headings")
        headings = {
            "rm_id": "RM ID",
            "date": "Date",
            "market": "Use for",
            "m_kg": "M (kg)",
            "m_ppkg": "M pcs/kg",
            "s_kg": "S (kg)",
            "s_ppkg": "S pcs/kg",
            "ss_kg": "SS (kg)",
            "ss_ppkg": "SS pcs/kg",
            "total_kg": "Total (kg)",
            "wontons": "Est. wonton",
        }
        numeric = set(columns) - {"rm_id", "date", "market"}
        for column in columns:
            self.existing_stock_tree.heading(column, text=headings[column])
            self.existing_stock_tree.column(
                column,
                width=100,
                minwidth=75,
                anchor=tk.E if column in numeric else tk.W,
                stretch=column == "rm_id",
            )
        vertical = ttk.Scrollbar(history, orient=tk.VERTICAL, command=self.existing_stock_tree.yview)
        horizontal = ttk.Scrollbar(history, orient=tk.HORIZONTAL, command=self.existing_stock_tree.xview)
        self.existing_stock_tree.configure(
            yscrollcommand=vertical.set,
            xscrollcommand=horizontal.set,
        )
        self.existing_stock_tree.grid(row=0, column=0, sticky="nsew")
        vertical.grid(row=0, column=1, sticky="ns")
        horizontal.grid(row=1, column=0, sticky="ew")
        self.existing_stock_tree.bind(
            "<Double-1>", lambda _event: self._edit_selected_existing_stock()
        )
        history_actions = ttk.Frame(self.existing_stock_tab)
        history_actions.pack(fill=tk.X, pady=(8, 0))
        ttk.Button(
            history_actions,
            text="Edit selected",
            command=self._edit_selected_existing_stock,
        ).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 4))
        ttk.Button(
            history_actions,
            text="Delete selected",
            command=self._delete_selected_existing_stock,
        ).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(4, 0))
        ttk.Label(
            self.existing_stock_tab,
            textvariable=self.existing_stock_status_var,
            relief=tk.SUNKEN,
            anchor=tk.W,
            padding=(6, 3),
        ).pack(fill=tk.X, pady=(8, 0))
        self._new_existing_stock_form(set_status=False)

    def _new_existing_stock_form(self, set_status: bool = True) -> None:
        today = date.today()
        self.existing_day_var.set(f"{today.day:02d}")
        self.existing_month_var.set(f"{today.month:02d}")
        self.existing_year_var.set(str(today.year))
        self.existing_market_var.set(market_display_label("domestic"))
        self._editing_existing_stock_id = None
        for size_class, variables in self.existing_stock_entry_vars.items():
            variables["weight"].set("")
            variables["pieces_per_kg"].set(
                DEFAULT_EXISTING_STOCK_PIECES_PER_KG[size_class]
            )
        self.existing_stock_save_button.configure(text="Save existing stock")
        if set_status:
            self.existing_stock_status_var.set("New existing-stock form ready.")

    def _selected_existing_stock_date(self) -> str:
        try:
            selected = date(
                int(self.existing_year_var.get()),
                int(self.existing_month_var.get()),
                int(self.existing_day_var.get()),
            )
        except ValueError as exc:
            raise ValueError("Choose a valid existing-stock date.") from exc
        return selected.isoformat()

    def _collect_existing_stock_entries(self) -> list[ActualAssortmentEntry]:
        entries: list[ActualAssortmentEntry] = []
        for size_class in SIZE_CLASSES:
            variables = self.existing_stock_entry_vars[size_class]
            weight_text = variables["weight"].get().strip().replace(",", "")
            pieces_text = variables["pieces_per_kg"].get().strip().replace(",", "")
            if not weight_text:
                continue
            try:
                weight = float(weight_text)
                pieces_per_kg = float(pieces_text)
            except ValueError as exc:
                raise ValueError(
                    f"{size_class} needs valid Weight and Average pieces/kg numbers."
                ) from exc
            entries.append(
                ActualAssortmentEntry(
                    size=size_class,
                    weight=weight,
                    size_class=size_class,
                    pieces_per_kg=pieces_per_kg,
                )
            )
        if not entries:
            raise ValueError("Enter existing weight for at least one RM class.")
        return entries

    def _save_existing_stock(self) -> None:
        try:
            record = upsert_actual_record(
                self.assortment_actual_file_path,
                self._selected_existing_stock_date(),
                self._collect_existing_stock_entries(),
                record_id=self._editing_existing_stock_id,
                record_type="existing",
                market_type=self.existing_market_var.get(),
            )
        except ValueError as exc:
            messagebox.showerror("Save existing stock", str(exc))
            return
        action = "Updated" if self._editing_existing_stock_id else "Saved"
        self._load_assortment_actual_history()
        self._new_existing_stock_form(set_status=False)
        self.existing_stock_status_var.set(
            f"{action} {record.rm_id} for {market_display_label(record.market_type)} with "
            f"{self._format_optional_number(record.total_weight)} kg."
        )

    def _refresh_existing_stock_history_table(self) -> None:
        if not hasattr(self, "existing_stock_tree"):
            return
        selected = set(self.existing_stock_tree.selection())
        self.existing_stock_tree.delete(*self.existing_stock_tree.get_children())
        existing_records = [
            record
            for record in self.assortment_actual_records.values()
            if record.record_type == "existing"
        ]
        for record in sorted(
            existing_records,
            key=lambda item: (item.record_date, item.updated_at),
            reverse=True,
        ):
            entries = {entry.size_class: entry for entry in record.entries}
            class_summaries = self._assortment_record_class_summaries(record)
            values: list[str] = [
                record.rm_id,
                record.record_date,
                market_display_label(record.market_type),
            ]
            for size_class in SIZE_CLASSES:
                entry = entries.get(size_class)
                values.extend(
                    [
                        self._format_optional_number(entry.weight) if entry else "",
                        self._format_optional_number(entry.pieces_per_kg) if entry else "",
                    ]
                )
            values.extend(
                [
                    self._format_optional_number(record.total_weight),
                    self._format_optional_number(
                        self._estimate_wontons_from_class_summaries(class_summaries)
                    ),
                ]
            )
            self.existing_stock_tree.insert("", tk.END, iid=record.record_id, values=values)
        for record_id in selected:
            if self.existing_stock_tree.exists(record_id):
                self.existing_stock_tree.selection_add(record_id)
        if existing_records:
            self.existing_stock_status_var.set(
                f"Loaded {len(existing_records):,} saved existing-stock records."
            )

    def _edit_selected_existing_stock(self) -> None:
        selected = self.existing_stock_tree.selection()
        if not selected:
            messagebox.showwarning("No stock selected", "Select existing stock to edit.")
            return
        record = self.assortment_actual_records.get(selected[0])
        if not record or record.record_type != "existing":
            messagebox.showerror("Stock error", "The selected existing stock could not be found.")
            return
        year, month, day = record.record_date.split("-")
        self.existing_day_var.set(day)
        self.existing_month_var.set(month)
        self.existing_year_var.set(year)
        self.existing_market_var.set(market_display_label(record.market_type))
        entries = {entry.size_class: entry for entry in record.entries}
        for size_class, variables in self.existing_stock_entry_vars.items():
            entry = entries.get(size_class)
            variables["weight"].set(
                self._format_optional_number(entry.weight) if entry else ""
            )
            variables["pieces_per_kg"].set(
                self._format_optional_number(entry.pieces_per_kg)
                if entry
                else DEFAULT_EXISTING_STOCK_PIECES_PER_KG[size_class]
            )
        self._editing_existing_stock_id = record.record_id
        self.existing_stock_save_button.configure(text="Update existing stock")
        self.existing_stock_status_var.set(f"Editing {record.rm_id} from {record.record_date}.")

    def _delete_selected_existing_stock(self) -> None:
        selected = self.existing_stock_tree.selection()
        if not selected:
            messagebox.showwarning("No stock selected", "Select existing stock to delete.")
            return
        record = self.assortment_actual_records.get(selected[0])
        if not record or record.record_type != "existing":
            messagebox.showerror("Stock error", "The selected existing stock could not be found.")
            return
        if not messagebox.askyesno(
            "Delete existing stock",
            f"Permanently delete {record.rm_id} from {record.record_date}?\n\nThis cannot be undone.",
        ):
            return
        try:
            deleted = delete_actual_record(self.assortment_actual_file_path, record.record_id)
        except ValueError as exc:
            messagebox.showerror("Delete existing stock", str(exc))
            return
        if self._editing_existing_stock_id == deleted.record_id:
            self._new_existing_stock_form(set_status=False)
        self._load_assortment_actual_history()
        self.existing_stock_status_var.set(f"Deleted {deleted.rm_id} existing stock.")
