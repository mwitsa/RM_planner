"""RuleViewMixin behavior."""

from __future__ import annotations

from .common import *  # shared UI types and domain services


class RuleViewMixin:
    def _build_plan_rule_tab(self) -> None:
        ttk.Label(
            self.plan_rule_tab,
            text="Waterfall priority: rules are applied from top to bottom.",
            style="Summary.TLabel",
        ).pack(anchor=tk.W, pady=(0, 10))

        editor = ttk.LabelFrame(self.plan_rule_tab, text="Rule text", padding=12)
        editor.pack(fill=tk.X)
        editor.columnconfigure(0, weight=1)

        self.rule_text = tk.Text(editor, height=4, wrap=tk.WORD, font=("Segoe UI", 10), undo=True)
        self.rule_text.grid(row=0, column=0, columnspan=6, sticky="ew")

        ttk.Button(editor, text="Add rule", command=self._add_rule).grid(row=1, column=0, sticky=tk.W, pady=(10, 0))
        ttk.Button(editor, text="Update selected", command=self._update_rule).grid(
            row=1, column=1, sticky=tk.W, padx=(8, 0), pady=(10, 0)
        )
        ttk.Button(editor, text="Delete", command=self._delete_rule).grid(
            row=1, column=2, sticky=tk.W, padx=(8, 0), pady=(10, 0)
        )
        ttk.Button(editor, text="Move up", command=lambda: self._move_rule(-1)).grid(
            row=1, column=3, sticky=tk.W, padx=(24, 0), pady=(10, 0)
        )
        ttk.Button(editor, text="Move down", command=lambda: self._move_rule(1)).grid(
            row=1, column=4, sticky=tk.W, padx=(8, 0), pady=(10, 0)
        )
        ttk.Button(editor, text="Save rules", command=self._save_rules).grid(
            row=1, column=5, sticky=tk.E, padx=(24, 0), pady=(10, 0)
        )

        list_frame = ttk.Frame(self.plan_rule_tab)
        list_frame.pack(fill=tk.BOTH, expand=True, pady=(12, 0))
        list_frame.rowconfigure(0, weight=1)
        list_frame.columnconfigure(0, weight=1)

        self.rules_tree = ttk.Treeview(
            list_frame,
            columns=("priority", "rule"),
            show="headings",
            selectmode="browse",
        )
        self.rules_tree.heading("priority", text="Apply order")
        self.rules_tree.heading("rule", text="Rule")
        self.rules_tree.column("priority", width=100, minwidth=90, anchor=tk.CENTER, stretch=False)
        self.rules_tree.column("rule", width=850, minwidth=300, anchor=tk.W)
        rule_scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.rules_tree.yview)
        self.rules_tree.configure(yscrollcommand=rule_scrollbar.set)
        self.rules_tree.grid(row=0, column=0, sticky="nsew")
        rule_scrollbar.grid(row=0, column=1, sticky="ns")

        self.rules_tree.bind("<<TreeviewSelect>>", self._select_rule)
        self.rules_tree.bind("<ButtonPress-1>", self._start_rule_drag, add="+")
        self.rules_tree.bind("<B1-Motion>", self._drag_rule)
        self.rules_tree.bind("<ButtonRelease-1>", self._finish_rule_drag)

        ttk.Label(
            self.plan_rule_tab,
            textvariable=self.rule_status_var,
            relief=tk.SUNKEN,
            anchor=tk.W,
            padding=(6, 3),
        ).pack(fill=tk.X, pady=(8, 0))

    def _editor_rule_text(self) -> str:
        return self.rule_text.get("1.0", "end-1c").strip()

    def _insert_rule(self, text: str) -> str:
        item = self.rules_tree.insert("", tk.END, values=("", " ".join(text.split())))
        self._rule_text_by_item[item] = text
        self._renumber_rules()
        return item

    def _add_rule(self) -> None:
        text = self._editor_rule_text()
        if not text:
            messagebox.showwarning("Empty rule", "Enter the rule text first.")
            return
        item = self._insert_rule(text)
        self.rules_tree.selection_set(item)
        self.rules_tree.focus(item)
        self.rules_tree.see(item)
        self.rule_text.delete("1.0", tk.END)
        self.rule_status_var.set("Rule added. Click Save rules to keep this waterfall order.")

    def _update_rule(self) -> None:
        selected = self.rules_tree.selection()
        if not selected:
            messagebox.showwarning("No rule selected", "Select a rule to update.")
            return
        text = self._editor_rule_text()
        if not text:
            messagebox.showwarning("Empty rule", "Enter the updated rule text first.")
            return
        item = selected[0]
        self._rule_text_by_item[item] = text
        self._renumber_rules()
        self.rule_status_var.set("Rule updated. Click Save rules to keep the change.")

    def _delete_rule(self) -> None:
        selected = self.rules_tree.selection()
        if not selected:
            messagebox.showwarning("No rule selected", "Select a rule to delete.")
            return
        item = selected[0]
        self.rules_tree.delete(item)
        self._rule_text_by_item.pop(item, None)
        self.rule_text.delete("1.0", tk.END)
        self._renumber_rules()
        self.rule_status_var.set("Rule removed. Click Save rules to keep the change.")

    def _move_rule(self, direction: int) -> None:
        selected = self.rules_tree.selection()
        if not selected:
            messagebox.showwarning("No rule selected", "Select a rule to move.")
            return
        item = selected[0]
        current_index = self.rules_tree.index(item)
        destination = current_index + direction
        if destination < 0 or destination >= len(self.rules_tree.get_children()):
            return
        self.rules_tree.move(item, "", destination)
        self._renumber_rules()
        self.rules_tree.see(item)
        self.rule_status_var.set("Rule order changed. Click Save rules to keep the waterfall order.")

    def _select_rule(self, _event: tk.Event | None = None) -> None:
        selected = self.rules_tree.selection()
        if not selected:
            return
        text = self._rule_text_by_item.get(selected[0], "")
        self.rule_text.delete("1.0", tk.END)
        self.rule_text.insert("1.0", text)

    def _start_rule_drag(self, event: tk.Event) -> None:
        item = self.rules_tree.identify_row(event.y)
        self._drag_rule_item = item or None
        self._rule_drag_changed = False
        if item:
            self.rules_tree.selection_set(item)
            self.rules_tree.focus(item)

    def _drag_rule(self, event: tk.Event) -> str:
        if not self._drag_rule_item:
            return "break"
        target = self.rules_tree.identify_row(event.y)
        if target and target != self._drag_rule_item:
            self.rules_tree.move(self._drag_rule_item, "", self.rules_tree.index(target))
            self._renumber_rules()
            self._rule_drag_changed = True
        return "break"

    def _finish_rule_drag(self, _event: tk.Event) -> None:
        if self._rule_drag_changed:
            self.rule_status_var.set("Rule order changed. Click Save rules to keep the waterfall order.")
        self._drag_rule_item = None
        self._rule_drag_changed = False

    def _renumber_rules(self) -> None:
        for priority, item in enumerate(self.rules_tree.get_children(), start=1):
            text = self._rule_text_by_item[item]
            self.rules_tree.item(item, values=(priority, " ".join(text.split())))

    def _load_saved_rules(self) -> None:
        try:
            rules = load_rules(self.rule_file_path)
        except ValueError as exc:
            self.rule_status_var.set(str(exc))
            messagebox.showerror("Rule file error", str(exc))
            return
        for text in rules:
            self._insert_rule(text)
        if rules:
            self.rule_status_var.set(f"Loaded {len(rules)} saved rules. Top rule applies first.")

    def _save_rules(self) -> None:
        ordered_rules = [self._rule_text_by_item[item] for item in self.rules_tree.get_children()]
        try:
            save_rules(self.rule_file_path, ordered_rules)
        except ValueError as exc:
            messagebox.showerror("Save error", str(exc))
            return
        self.rule_status_var.set(f"Saved {len(ordered_rules)} rules in waterfall order.")
