"""ClassDefineMixin behavior."""

from __future__ import annotations

from .common import *  # shared UI types and domain services


class ClassDefineMixin:
    def _build_class_define_tab(self) -> None:
        page_header = tk.Frame(self.class_define_tab, bg="#f5f7fa")
        page_header.pack(fill=tk.X, pady=(0, 12))
        tk.Label(
            page_header,
            text="Class master",
            bg="#f5f7fa",
            font=("Segoe UI", 16, "bold"),
        ).pack(anchor=tk.W)
        tk.Label(
            page_header,
            text="จัดการ Class และการจัดกลุ่มสำหรับใช้กับแผนผลิต",
            bg="#f5f7fa",
            fg="#596579",
            font=("Segoe UI", 10),
        ).pack(anchor=tk.W, pady=(2, 0))

        editor_card = tk.Frame(
            self.class_define_tab,
            bg="white",
            highlightbackground="#d9e1ea",
            highlightthickness=1,
            padx=16,
            pady=14,
        )
        editor_card.pack(fill=tk.X)
        tk.Label(
            editor_card,
            text="เพิ่มหรือแก้ไข Class",
            bg="white",
            font=("Segoe UI", 11, "bold"),
        ).pack(anchor=tk.W)
        tk.Label(
            editor_card,
            text="กรอก Class และ Name ก่อน แล้วเพิ่ม Group หรือ Value เมื่อต้องการ",
            bg="white",
            fg="#64748b",
            font=("Segoe UI", 9),
        ).pack(anchor=tk.W, pady=(2, 12))

        fields = tk.Frame(editor_card, bg="white")
        fields.pack(fill=tk.X)
        fields.columnconfigure(0, weight=1, uniform="class-field")
        fields.columnconfigure(1, weight=1, uniform="class-field")

        def field_card(row: int, column: int, label: str) -> tk.Frame:
            card = tk.Frame(
                fields,
                bg="#f8fafc",
                highlightbackground="#dce4ed",
                highlightthickness=1,
                padx=10,
                pady=8,
            )
            card.grid(
                row=row,
                column=column,
                sticky="nsew",
                padx=(0, 6) if column == 0 else (6, 0),
                pady=(0, 10) if row == 0 else 0,
            )
            card.columnconfigure(0, weight=1)
            tk.Label(
                card,
                text=label,
                bg="#f8fafc",
                fg="#334155",
                font=("Segoe UI", 9, "bold"),
            ).grid(row=0, column=0, sticky=tk.W, pady=(0, 5))
            return card

        class_box = field_card(0, 0, "Class  *")
        ttk.Entry(class_box, textvariable=self.class_value_var, font=("Segoe UI", 11)).grid(
            row=1, column=0, sticky="ew"
        )
        name_box = field_card(0, 1, "Name  *")
        ttk.Entry(name_box, textvariable=self.class_name_var, font=("Segoe UI", 11)).grid(
            row=1, column=0, sticky="ew"
        )

        group_box = field_card(1, 0, "Group")
        self.class_group_text = tk.Text(
            group_box,
            height=3,
            wrap=tk.WORD,
            font=("Segoe UI", 10),
            undo=True,
            relief=tk.SOLID,
            borderwidth=1,
            highlightthickness=0,
        )
        self.class_group_text.grid(row=1, column=0, sticky="ew")
        value_box = field_card(1, 1, "Value")
        self.class_detail_value_text = tk.Text(
            value_box,
            height=3,
            wrap=tk.WORD,
            font=("Segoe UI", 10),
            undo=True,
            relief=tk.SOLID,
            borderwidth=1,
            highlightthickness=0,
        )
        self.class_detail_value_text.grid(row=1, column=0, sticky="ew")

        actions = tk.Frame(editor_card, bg="white")
        actions.pack(fill=tk.X, pady=(14, 0))
        ttk.Button(actions, text="ล้างฟอร์ม", command=self._new_class_form).pack(side=tk.RIGHT)
        self.save_class_button = ttk.Button(
            actions,
            text="บันทึก Class",
            command=self._save_class_definition,
        )
        self.save_class_button.pack(side=tk.RIGHT, padx=(0, 8))

        saved_frame = tk.Frame(
            self.class_define_tab,
            bg="white",
            highlightbackground="#d9e1ea",
            highlightthickness=1,
            padx=12,
            pady=12,
        )
        saved_frame.pack(fill=tk.BOTH, expand=True, pady=(12, 0))
        saved_frame.rowconfigure(2, weight=1)
        saved_frame.columnconfigure(0, weight=1)

        saved_header = tk.Frame(saved_frame, bg="white")
        saved_header.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 10))
        tk.Label(saved_header, text="Saved classes", bg="white", font=("Segoe UI", 11, "bold")).pack(side=tk.LEFT)
        ttk.Label(saved_header, textvariable=self.class_filter_count_var, style="Summary.TLabel").pack(side=tk.RIGHT)

        class_filters = tk.Frame(saved_frame, bg="#f5f8fc", padx=10, pady=10)
        class_filters.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(0, 10))
        class_filters.columnconfigure(0, weight=1)
        class_filters.columnconfigure(1, weight=2)
        class_filters.columnconfigure(2, weight=1)
        ttk.Label(class_filters, text="Class").grid(row=0, column=0, sticky=tk.W)
        ttk.Label(class_filters, text="ค้นหาชื่อ").grid(row=0, column=1, sticky=tk.W, padx=(10, 0))
        ttk.Label(class_filters, text="Group").grid(row=0, column=2, sticky=tk.W, padx=(10, 0))
        self.class_filter_combo = ttk.Combobox(
            class_filters,
            textvariable=self.class_filter_var,
            state="readonly",
            values=[ALL_CLASS_FILTER],
        )
        self.class_filter_combo.grid(row=1, column=0, sticky="ew", pady=(4, 0))
        self.class_filter_combo.bind(
            "<<ComboboxSelected>>",
            lambda _event: self._refresh_class_table(),
        )
        name_search_entry = ttk.Entry(
            class_filters,
            textvariable=self.class_name_search_var,
        )
        name_search_entry.grid(row=1, column=1, sticky="ew", padx=(10, 0), pady=(4, 0))
        name_search_entry.bind("<KeyRelease>", lambda _event: self._refresh_class_table())
        self.class_group_filter_combo = ttk.Combobox(
            class_filters,
            textvariable=self.class_group_filter_var,
            state="readonly",
            values=[ALL_CLASS_FILTER],
        )
        self.class_group_filter_combo.grid(row=1, column=2, sticky="ew", padx=(10, 0), pady=(4, 0))
        self.class_group_filter_combo.bind(
            "<<ComboboxSelected>>",
            lambda _event: self._refresh_class_table(),
        )
        ttk.Button(
            class_filters,
            text="ล้างตัวกรอง",
            command=self._clear_class_filters,
        ).grid(row=1, column=3, padx=(10, 0), pady=(4, 0))

        self.class_tree = ttk.Treeview(
            saved_frame,
            columns=("class", "name", "group", "value"),
            show="headings",
            selectmode="extended",
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
        self.class_tree.grid(row=2, column=0, sticky="nsew")
        class_scrollbar.grid(row=2, column=1, sticky="ns")
        self.class_tree.bind("<Double-1>", lambda _event: self._edit_selected_class())
        ttk.Button(saved_frame, text="แก้ไขรายการที่เลือก", command=self._edit_selected_class).grid(
            row=3, column=0, sticky="e", pady=(10, 0)
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
        self.save_class_button.configure(text="บันทึก Class")
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
        if len(selected) > 1:
            self._bulk_edit_selected_classes(selected)
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
        self.save_class_button.configure(text="บันทึกการแก้ไข")
        self.class_status_var.set(f"Editing class {item.class_value}.")

    def _bulk_edit_selected_classes(self, selected: tuple[str, ...]) -> None:
        """Open a small bulk editor for the selected Class master rows."""

        dialog = tk.Toplevel(self)
        dialog.title(f"แก้ไข {len(selected):,} รายการ")
        dialog.transient(self)
        dialog.resizable(False, False)
        body = ttk.Frame(dialog, padding=16)
        body.pack(fill=tk.BOTH, expand=True)
        ttk.Label(body, text=f"แก้ไขพร้อมกัน {len(selected):,} รายการ", style="Summary.TLabel").grid(
            row=0, column=0, columnspan=2, sticky=tk.W
        )
        ttk.Label(
            body,
            text="เลือก field ที่ต้องการเปลี่ยน ช่องที่ไม่ได้เลือกจะคงค่าเดิมไว้",
        ).grid(row=1, column=0, columnspan=2, sticky=tk.W, pady=(3, 12))

        update_group = tk.BooleanVar(value=False)
        update_value = tk.BooleanVar(value=False)
        group_var = tk.StringVar()
        value_var = tk.StringVar()
        group_entry = ttk.Entry(body, textvariable=group_var, width=42, state=tk.DISABLED)
        value_entry = ttk.Entry(body, textvariable=value_var, width=42, state=tk.DISABLED)

        def sync_fields() -> None:
            group_entry.configure(state=tk.NORMAL if update_group.get() else tk.DISABLED)
            value_entry.configure(state=tk.NORMAL if update_value.get() else tk.DISABLED)

        ttk.Checkbutton(body, text="อัปเดต Group", variable=update_group, command=sync_fields).grid(
            row=2, column=0, sticky=tk.W, pady=(0, 5)
        )
        group_entry.grid(row=2, column=1, sticky=tk.EW, padx=(12, 0), pady=(0, 5))
        ttk.Checkbutton(body, text="อัปเดต Value", variable=update_value, command=sync_fields).grid(
            row=3, column=0, sticky=tk.W
        )
        value_entry.grid(row=3, column=1, sticky=tk.EW, padx=(12, 0))
        ttk.Label(
            body,
            text="หากเลือก field แล้วปล่อยว่าง ระบบจะล้างค่านั้นจากทุกรายการที่เลือก",
        ).grid(row=4, column=0, columnspan=2, sticky=tk.W, pady=(8, 0))

        actions = ttk.Frame(body)
        actions.grid(row=5, column=0, columnspan=2, sticky=tk.E, pady=(14, 0))
        ttk.Button(actions, text="ยกเลิก", command=dialog.destroy).pack(side=tk.RIGHT)

        def save_bulk_changes() -> None:
            try:
                updated = update_class_definitions(
                    self.class_definitions_file_path,
                    selected,
                    group=group_var.get() if update_group.get() else None,
                    value=value_var.get() if update_value.get() else None,
                )
            except ValueError as exc:
                messagebox.showerror("แก้ไขหลายรายการ", str(exc), parent=dialog)
                return
            dialog.destroy()
            self._load_saved_class_definitions()
            self.class_status_var.set(f"Updated {len(updated):,} classes.")

        ttk.Button(actions, text="บันทึกทั้งหมด", command=save_bulk_changes).pack(
            side=tk.RIGHT, padx=(0, 8)
        )
        dialog.grab_set()
