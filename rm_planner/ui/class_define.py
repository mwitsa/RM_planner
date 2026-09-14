"""ClassDefineMixin behavior."""

from __future__ import annotations

from .common import *  # shared UI types and domain services


class ClassDefineMixin:
    def _build_class_define_tab(self) -> None:
        ttk.Label(
            self.class_define_tab,
            text="Class and grouping master data",
            style="Summary.TLabel",
        ).pack(anchor=tk.W, pady=(0, 10))

        form = ttk.LabelFrame(self.class_define_tab, text="Class details", padding=12)
        form.pack(fill=tk.X)
        form.columnconfigure(0, weight=1)
        form.columnconfigure(1, weight=2)

        class_box = ttk.LabelFrame(form, text="1. Class", padding=10)
        class_box.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        class_box.columnconfigure(0, weight=1)
        ttk.Entry(class_box, textvariable=self.class_value_var).grid(row=0, column=0, sticky="ew")

        name_box = ttk.LabelFrame(form, text="2. Name", padding=10)
        name_box.grid(row=0, column=1, sticky="ew")
        name_box.columnconfigure(0, weight=1)
        ttk.Entry(name_box, textvariable=self.class_name_var).grid(row=0, column=0, sticky="ew")

        group_box = ttk.LabelFrame(form, text="3. Group", padding=10)
        group_box.grid(row=1, column=0, sticky="ew", padx=(0, 8), pady=(10, 0))
        group_box.columnconfigure(0, weight=1)
        self.class_group_text = tk.Text(
            group_box,
            height=4,
            wrap=tk.WORD,
            font=("Segoe UI", 10),
            undo=True,
        )
        self.class_group_text.grid(row=0, column=0, sticky="ew")

        value_box = ttk.LabelFrame(form, text="4. Value", padding=10)
        value_box.grid(row=1, column=1, sticky="ew", pady=(10, 0))
        value_box.columnconfigure(0, weight=1)
        self.class_detail_value_text = tk.Text(
            value_box,
            height=4,
            wrap=tk.WORD,
            font=("Segoe UI", 10),
            undo=True,
        )
        self.class_detail_value_text.grid(row=0, column=0, sticky="ew")

        actions = ttk.Frame(form)
        actions.grid(row=2, column=0, columnspan=2, sticky="e", pady=(10, 0))
        ttk.Button(actions, text="New", command=self._new_class_form).pack(side=tk.LEFT)
        self.save_class_button = ttk.Button(
            actions,
            text="Save class",
            command=self._save_class_definition,
        )
        self.save_class_button.pack(side=tk.LEFT, padx=(8, 0))

        saved_frame = ttk.LabelFrame(self.class_define_tab, text="Saved classes", padding=10)
        saved_frame.pack(fill=tk.BOTH, expand=True, pady=(12, 0))
        saved_frame.rowconfigure(1, weight=1)
        saved_frame.columnconfigure(0, weight=1)

        class_filters = ttk.Frame(saved_frame)
        class_filters.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 8))
        class_filters.columnconfigure(1, weight=1)
        class_filters.columnconfigure(3, weight=2)
        class_filters.columnconfigure(5, weight=1)
        ttk.Label(class_filters, text="Class:").grid(row=0, column=0, padx=(0, 5))
        self.class_filter_combo = ttk.Combobox(
            class_filters,
            textvariable=self.class_filter_var,
            state="readonly",
            values=[ALL_CLASS_FILTER],
            width=18,
        )
        self.class_filter_combo.grid(row=0, column=1, sticky="ew", padx=(0, 12))
        self.class_filter_combo.bind(
            "<<ComboboxSelected>>",
            lambda _event: self._refresh_class_table(),
        )
        ttk.Label(class_filters, text="Name contains:").grid(row=0, column=2, padx=(0, 5))
        name_search_entry = ttk.Entry(
            class_filters,
            textvariable=self.class_name_search_var,
        )
        name_search_entry.grid(row=0, column=3, sticky="ew", padx=(0, 12))
        name_search_entry.bind("<KeyRelease>", lambda _event: self._refresh_class_table())
        ttk.Label(class_filters, text="Group:").grid(row=0, column=4, padx=(0, 5))
        self.class_group_filter_combo = ttk.Combobox(
            class_filters,
            textvariable=self.class_group_filter_var,
            state="readonly",
            values=[ALL_CLASS_FILTER],
            width=18,
        )
        self.class_group_filter_combo.grid(row=0, column=5, sticky="ew", padx=(0, 12))
        self.class_group_filter_combo.bind(
            "<<ComboboxSelected>>",
            lambda _event: self._refresh_class_table(),
        )
        ttk.Button(
            class_filters,
            text="Clear filters",
            command=self._clear_class_filters,
        ).grid(row=0, column=6, padx=(0, 12))
        ttk.Label(
            class_filters,
            textvariable=self.class_filter_count_var,
            style="Summary.TLabel",
        ).grid(row=0, column=7)

        self.class_tree = ttk.Treeview(
            saved_frame,
            columns=("class", "name", "group", "value"),
            show="headings",
            selectmode="browse",
        )
        self.class_tree.heading("class", text="Class")
        self.class_tree.heading("name", text="Name")
        self.class_tree.heading("group", text="Group")
        self.class_tree.heading("value", text="Value")
        self.class_tree.column("class", width=140, minwidth=100, stretch=False)
        self.class_tree.column("name", width=260, minwidth=160)
        self.class_tree.column("group", width=280, minwidth=160)
        self.class_tree.column("value", width=320, minwidth=180)
        class_scrollbar = ttk.Scrollbar(saved_frame, orient=tk.VERTICAL, command=self.class_tree.yview)
        self.class_tree.configure(yscrollcommand=class_scrollbar.set)
        self.class_tree.grid(row=1, column=0, sticky="nsew")
        class_scrollbar.grid(row=1, column=1, sticky="ns")
        self.class_tree.bind("<Double-1>", lambda _event: self._edit_selected_class())
        ttk.Button(saved_frame, text="Edit selected", command=self._edit_selected_class).grid(
            row=2, column=0, sticky="e", pady=(8, 0)
        )

        ttk.Label(
            self.class_define_tab,
            textvariable=self.class_status_var,
            relief=tk.SUNKEN,
            anchor=tk.W,
            padding=(6, 3),
        ).pack(fill=tk.X, pady=(8, 0))

    def _new_class_form(self, set_status: bool = True) -> None:
        self.class_value_var.set("")
        self.class_name_var.set("")
        self.class_group_text.delete("1.0", tk.END)
        self.class_detail_value_text.delete("1.0", tk.END)
        self._editing_class_id = None
        self.save_class_button.configure(text="Save class")
        if set_status:
            self.class_status_var.set("New class form ready.")

    def _save_class_definition(self) -> None:
        try:
            saved = upsert_class_definition(
                self.class_definitions_file_path,
                self.class_value_var.get(),
                self.class_name_var.get(),
                self.class_group_text.get("1.0", "end-1c"),
                class_id=self._editing_class_id,
                value=self.class_detail_value_text.get("1.0", "end-1c"),
            )
        except ValueError as exc:
            messagebox.showerror("Save class", str(exc))
            return
        action = "Updated" if self._editing_class_id else "Saved"
        self._load_saved_class_definitions()
        self._new_class_form(set_status=False)
        self.class_status_var.set(f"{action} class {saved.class_value}.")

    def _sync_order_classes(self, records: list[OrderRecord]) -> None:
        try:
            added = add_missing_class_definitions(
                self.class_definitions_file_path,
                order_class_names(records),
            )
        except ValueError as exc:
            self.class_status_var.set(f"Could not update classes from orders: {exc}")
            return
        self._load_saved_class_definitions()
        if added:
            self.class_status_var.set(
                f"Added {added:,} new Class + Name rows from Order data. "
                f"Class master now contains {len(self.class_definitions):,} rows."
            )
        else:
            self.class_status_var.set(
                f"All Order class values already exist ({len(self.class_definitions):,} rows)."
            )

    def _load_saved_class_definitions(self) -> None:
        try:
            definitions = load_class_definitions(self.class_definitions_file_path)
        except ValueError as exc:
            self.class_status_var.set(str(exc))
            return
        self.class_definitions = {item.class_id: item for item in definitions}
        class_options = [ALL_CLASS_FILTER, *class_filter_options(definitions, "class")]
        group_options = [ALL_CLASS_FILTER, *class_filter_options(definitions, "group")]
        self.class_filter_combo.configure(values=class_options)
        self.class_group_filter_combo.configure(values=group_options)
        if self.class_filter_var.get() not in class_options:
            self.class_filter_var.set(ALL_CLASS_FILTER)
        if self.class_group_filter_var.get() not in group_options:
            self.class_group_filter_var.set(ALL_CLASS_FILTER)
        self._refresh_class_table()
        if definitions:
            self.class_status_var.set(f"Loaded {len(definitions)} saved classes.")

    def _refresh_class_table(self) -> None:
        definitions = filter_class_definitions(
            self.class_definitions.values(),
            class_filter=self.class_filter_var.get(),
            name_search=self.class_name_search_var.get(),
            group_filter=self.class_group_filter_var.get(),
        )
        self.class_tree.delete(*self.class_tree.get_children())
        for item in sorted(
            definitions,
            key=lambda value: (value.class_value.casefold(), value.name.casefold()),
        ):
            self.class_tree.insert(
                "",
                tk.END,
                iid=item.class_id,
                values=(
                    item.class_value,
                    self._format_class_name_for_display(item),
                    " ".join(item.group.split()),
                    " ".join(item.value.split()),
                ),
            )
        self.class_filter_count_var.set(
            f"Showing {len(definitions):,} of {len(self.class_definitions):,} classes"
        )

    def _clear_class_filters(self) -> None:
        self.class_filter_var.set(ALL_CLASS_FILTER)
        self.class_name_search_var.set("")
        self.class_group_filter_var.set(ALL_CLASS_FILTER)
        self._refresh_class_table()

    def _edit_selected_class(self) -> None:
        selected = self.class_tree.selection()
        if not selected:
            messagebox.showwarning("No class selected", "Select a saved class to edit.")
            return
        item = self.class_definitions.get(selected[0])
        if not item:
            messagebox.showerror("Class error", "The selected class could not be found.")
            return
        self.class_value_var.set(item.class_value)
        self.class_name_var.set(item.name)
        self.class_group_text.delete("1.0", tk.END)
        self.class_group_text.insert("1.0", item.group)
        self.class_detail_value_text.delete("1.0", tk.END)
        self.class_detail_value_text.insert("1.0", item.value)
        self._editing_class_id = item.class_id
        self.save_class_button.configure(text="Update class")
        self.class_status_var.set(f"Editing class {item.class_value}.")
