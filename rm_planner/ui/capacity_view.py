"""CapacityViewMixin behavior."""

from __future__ import annotations

from .common import *  # shared UI types and domain services


class CapacityViewMixin:
    def _build_capacity_tab(self) -> None:
        self.work_hours_per_day_var = tk.StringVar(value="8")
        self.raw_cups_per_hour_var = tk.StringVar()
        self.cooked_cups_per_hour_var = tk.StringVar()
        self.cooked_noodle_cups_per_hour_var = tk.StringVar()
        self.raw_wonton_daily_var = tk.StringVar(value="—")
        self.cooked_wonton_daily_var = tk.StringVar(value="—")
        self.cooked_wonton_noodle_daily_var = tk.StringVar(value="—")

        page = ttk.Frame(self.capacity_tab, padding=18)
        page.pack(fill=tk.BOTH, expand=True)
        page.columnconfigure(1, weight=1)
        page.rowconfigure(0, weight=1)

        sidebar = tk.Frame(page, bg="#f5f7fa", width=210, padx=14, pady=16)
        sidebar.grid(row=0, column=0, sticky="nsw", padx=(0, 18))
        sidebar.grid_propagate(False)
        tk.Label(sidebar, text="Operations", bg="#f5f7fa", fg="#1f2937",
                 font=("Segoe UI", 13, "bold")).pack(anchor=tk.W)
        tk.Label(sidebar, text="Settings categories", bg="#f5f7fa", fg="#64748b",
                 font=("Segoe UI", 9)).pack(anchor=tk.W, pady=(2, 16))
        self.operations_capacity_button = tk.Button(
            sidebar,
            text="Capacity",
            anchor=tk.W,
            relief=tk.FLAT,
            borderwidth=0,
            padx=12,
            pady=10,
            bg="#dceeff",
            activebackground="#dceeff",
            fg="#24567b",
            activeforeground="#24567b",
            font=("Segoe UI", 10, "bold"),
        )
        self.operations_capacity_button.pack(fill=tk.X)

        content_host = ttk.Frame(page)
        content_host.grid(row=0, column=1, sticky="nsew")
        content_host.columnconfigure(0, weight=1)
        content_host.rowconfigure(0, weight=1)
        capacity_content = ttk.Frame(content_host)
        capacity_content.grid(row=0, column=0, sticky="nsew")
        ttk.Label(capacity_content, text="Capacity", font=("Segoe UI", 16, "bold")).pack(anchor=tk.W)
        ttk.Label(capacity_content, text="ตั้งค่ากำลังผลิตต่อชั่วโมงและชั่วโมงทำงานของโรงงาน").pack(
            anchor=tk.W, pady=(3, 18))

        hours_card = ttk.LabelFrame(capacity_content, text="เวลาทำงาน", padding=14)
        hours_card.pack(fill=tk.X)
        ttk.Label(hours_card, text="Working hours per day", font=("Segoe UI", 10, "bold")).pack(anchor=tk.W)
        hours_entry = ttk.Entry(hours_card, textvariable=self.work_hours_per_day_var, width=12,
                                font=("Segoe UI", 14))
        hours_entry.pack(anchor=tk.W, pady=(6, 3))
        ttk.Label(hours_card, text="ชั่วโมง/วัน  •  ใช้คูณกับ Prod Cap / hr ของทุกประเภท").pack(anchor=tk.W)

        inputs = ttk.LabelFrame(capacity_content, text="Prod Cap / hr", padding=14)
        inputs.pack(fill=tk.X, pady=(14, 0))
        for column in range(3):
            inputs.columnconfigure(column, weight=1)
        for column, (label, variable) in enumerate((
            ("Raw wonton", self.raw_cups_per_hour_var),
            ("Cooked wonton", self.cooked_cups_per_hour_var),
            ("Cooked wonton + noodle", self.cooked_noodle_cups_per_hour_var),
        )):
            field = ttk.Frame(inputs, padding=(0 if column == 0 else 8, 0, 8 if column < 2 else 0, 0))
            field.grid(row=0, column=column, sticky="ew")
            field.columnconfigure(0, weight=1)
            ttk.Label(field, text=label, font=("Segoe UI", 10, "bold")).grid(row=0, column=0, sticky=tk.W)
            entry = ttk.Entry(field, textvariable=variable, font=("Segoe UI", 14))
            entry.grid(row=1, column=0, sticky="ew", pady=(6, 0))
            ttk.Label(field, text="ถ้วย / ชั่วโมง").grid(row=2, column=0, sticky=tk.W, pady=(3, 0))
            entry.bind("<KeyRelease>", lambda _event: self._update_capacity_preview())
        hours_entry.bind("<KeyRelease>", lambda _event: self._update_capacity_preview())

        summary = ttk.LabelFrame(capacity_content, text="Calculated capacity per day", padding=14)
        summary.pack(fill=tk.X, pady=(14, 0))
        for column in range(3):
            summary.columnconfigure(column, weight=1)
        for column, (label, variable) in enumerate((
            ("Raw wonton", self.raw_wonton_daily_var),
            ("Cooked wonton", self.cooked_wonton_daily_var),
            ("Cooked wonton + noodle", self.cooked_wonton_noodle_daily_var),
        )):
            card = tk.Frame(summary, bg="#edf6fb", padx=14, pady=12)
            card.grid(row=0, column=column, sticky="ew", padx=(0 if column == 0 else 8, 8 if column < 2 else 0))
            tk.Label(card, text=label, bg="#edf6fb", anchor="w", font=("Segoe UI", 10, "bold")).pack(fill=tk.X)
            tk.Label(card, textvariable=variable, bg="#edf6fb", anchor="w", font=("Segoe UI", 17, "bold")).pack(
                fill=tk.X, pady=(5, 0))
            tk.Label(card, text="ถ้วย / วัน", bg="#edf6fb", anchor="w").pack(fill=tk.X)

        action_frame = ttk.Frame(capacity_content)
        action_frame.pack(fill=tk.X, pady=(18, 0))
        ttk.Button(
            action_frame,
            text="Save operations settings",
            command=self._save_all_capacity_settings,
        ).pack(anchor=tk.E)

        ttk.Label(
            capacity_content,
            textvariable=self.capacity_status_var,
            relief=tk.SUNKEN,
            anchor=tk.W,
            padding=(6, 3),
        ).pack(fill=tk.X, pady=(14, 0))

        self.operation_order_rule_tab = ttk.Frame(content_host)
        ttk.Label(
            self.operation_order_rule_tab,
            text="Operation order rule",
            font=("Segoe UI", 16, "bold"),
        ).pack(anchor=tk.W)
        ttk.Label(
            self.operation_order_rule_tab,
            text="กำหนดกฎและลำดับการเปลี่ยนงานของแต่ละไลน์ผลิต",
        ).pack(anchor=tk.W, pady=(3, 18))
        self._build_operation_rule_builder()

        self.class_define_tab = ttk.Frame(content_host)
        self._operations_sections = {
            "capacity": capacity_content,
            "operation_order_rule": self.operation_order_rule_tab,
            "class_define": self.class_define_tab,
        }
        self._operations_section_buttons = {
            "capacity": self.operations_capacity_button,
            "operation_order_rule": tk.Button(
                sidebar,
                text="Operation order rule",
                anchor=tk.W,
                relief=tk.FLAT,
                borderwidth=0,
                padx=12,
                pady=10,
                bg="#f5f7fa",
                activebackground="#e7edf5",
                fg="#475569",
                activeforeground="#24567b",
                font=("Segoe UI", 10),
                command=lambda: self._select_operations_section("operation_order_rule"),
            ),
            "class_define": tk.Button(
                sidebar,
                text="Class Define",
                anchor=tk.W,
                relief=tk.FLAT,
                borderwidth=0,
                padx=12,
                pady=10,
                bg="#f5f7fa",
                activebackground="#e7edf5",
                fg="#475569",
                activeforeground="#24567b",
                font=("Segoe UI", 10),
                command=lambda: self._select_operations_section("class_define"),
            ),
        }
        self.operations_capacity_button.configure(command=lambda: self._select_operations_section("capacity"))
        self._operations_section_buttons["operation_order_rule"].pack(fill=tk.X, pady=(4, 0))
        self._operations_section_buttons["class_define"].pack(fill=tk.X, pady=(4, 0))
        self._build_class_define_tab()
        self._select_operations_section("capacity")

    def _select_operations_section(self, section: str) -> None:
        """Show one Operations Settings category in the shared content area."""

        for name, frame in self._operations_sections.items():
            if name == section:
                frame.grid(row=0, column=0, sticky="nsew")
            else:
                frame.grid_remove()
            selected = name == section
            button = self._operations_section_buttons[name]
            button.configure(
                bg="#dceeff" if selected else "#f5f7fa",
                activebackground="#dceeff" if selected else "#e7edf5",
                fg="#24567b" if selected else "#475569",
                activeforeground="#24567b",
                font=("Segoe UI", 10, "bold") if selected else ("Segoe UI", 10),
            )

    def _build_operation_rule_builder(self) -> None:
        """Build a small game-like canvas for ordering Class/Group rules."""

        self.operation_rule_status_var = tk.StringVar(value="เพิ่ม Rule แล้ววางกล่องจาก Class Define")
        self.operation_rules: list[dict] = []
        self._operation_rule_selected: tuple[int, int] | None = None
        self._operation_rule_drag: dict | None = None
        try:
            self.operation_rules = load_operation_rules(self.operation_rule_file_path)
        except ValueError as exc:
            self.operation_rule_status_var.set(str(exc))

        toolbar = ttk.Frame(self.operation_order_rule_tab)
        toolbar.pack(fill=tk.X, pady=(0, 10))
        ttk.Button(toolbar, text="+ Add rule", command=self._add_operation_rule).pack(side=tk.LEFT)
        ttk.Button(toolbar, text="Remove selected box", command=self._remove_selected_operation_rule_node).pack(side=tk.LEFT, padx=8)
        order_help = ttk.Label(toolbar, text="ⓘ Order help", foreground="#24567b", cursor="hand2")
        order_help.pack(side=tk.RIGHT)
        order_help.bind("<Enter>", self._show_operation_rule_order_tip)
        order_help.bind("<Leave>", self._hide_operation_rule_order_tip)

        board = ttk.LabelFrame(self.operation_order_rule_tab, text="Workflow board", padding=1)
        board.pack(fill=tk.BOTH, expand=True)
        board.columnconfigure(0, weight=1)
        board.rowconfigure(0, weight=1)
        self.operation_rule_canvas = tk.Canvas(board, bg="#fbfcfe", highlightthickness=0, height=440)
        self.operation_rule_canvas.grid(row=0, column=0, sticky="nsew")
        vertical = ttk.Scrollbar(board, orient=tk.VERTICAL, command=self.operation_rule_canvas.yview)
        vertical.grid(row=0, column=1, sticky="ns")
        horizontal = ttk.Scrollbar(board, orient=tk.HORIZONTAL, command=self.operation_rule_canvas.xview)
        horizontal.grid(row=1, column=0, sticky="ew")
        self.operation_rule_canvas.configure(xscrollcommand=horizontal.set, yscrollcommand=vertical.set)
        self.operation_rule_canvas.bind("<Configure>", lambda _event: self._render_operation_rule_canvas())
        ttk.Label(self.operation_order_rule_tab, textvariable=self.operation_rule_status_var,
                  relief=tk.SUNKEN, anchor=tk.W, padding=(6, 3)).pack(fill=tk.X, pady=(10, 0))
        self._render_operation_rule_canvas()

    def _show_operation_rule_order_tip(self, event) -> None:
        self._hide_operation_rule_order_tip()
        tip = tk.Toplevel(self)
        tip.overrideredirect(True)
        tip.attributes("-topmost", True)
        tk.Label(
            tip,
            text="Run order\n• Each Rule: left → right\n• Then: top → bottom\n• Drag RULE to move the whole row",
            justify=tk.LEFT,
            background="#18324a",
            foreground="white",
            font=("Segoe UI", 9),
            padx=9,
            pady=7,
        ).pack()
        tip.geometry(f"+{event.x_root + 12}+{event.y_root + 14}")
        self._operation_rule_order_tip = tip

    def _hide_operation_rule_order_tip(self, _event=None) -> None:
        tip = getattr(self, "_operation_rule_order_tip", None)
        if tip is not None and tip.winfo_exists():
            tip.destroy()
        self._operation_rule_order_tip = None

    def _save_operation_rules(self) -> bool:
        try:
            save_operation_rules(self.operation_rule_file_path, self.operation_rules)
        except OSError as exc:
            messagebox.showerror("Operation order rule", str(exc), parent=self)
            return False
        self.operation_rule_status_var.set(
            f"Saved {len(self.operation_rules):,} rule(s). Order runs left → right, then top → bottom."
        )
        return True

    def _add_operation_rule(self) -> None:
        self.operation_rules.append({"nodes": []})
        self._operation_rule_selected = None
        self._save_operation_rules()
        self._render_operation_rule_canvas()

    def _add_operation_rule_node(self, rule_index: int) -> None:
        if not self.operation_rules:
            messagebox.showinfo("Operation order rule", "เพิ่ม Rule ก่อน แล้วจึงเพิ่มกล่อง Class", parent=self)
            return
        classes = sorted({item.class_value.strip() for item in self.class_definitions.values() if item.class_value.strip()})
        if not classes:
            messagebox.showinfo("Operation order rule", "ยังไม่มีข้อมูล Class Define", parent=self)
            return
        dialog = tk.Toplevel(self)
        dialog.title("Add class box")
        dialog.transient(self)
        dialog.resizable(False, False)
        body = ttk.Frame(dialog, padding=16)
        body.pack(fill=tk.BOTH, expand=True)
        class_var = tk.StringVar(value=classes[0])
        group_var = tk.StringVar()
        ttk.Label(body, text=f"Add to Rule {rule_index + 1}", style="Summary.TLabel").grid(
            row=0, column=0, columnspan=2, sticky=tk.W, pady=(0, 12)
        )
        ttk.Label(body, text="Class").grid(row=1, column=0, sticky=tk.W, pady=(0, 7))
        class_picker = ttk.Combobox(body, textvariable=class_var, values=classes, width=30, state="readonly")
        class_picker.grid(row=1, column=1, sticky="ew", padx=(12, 0), pady=(0, 7))
        ttk.Label(body, text="Group").grid(row=2, column=0, sticky=tk.W)
        group_picker = ttk.Combobox(body, textvariable=group_var, width=30, state="readonly")
        group_picker.grid(row=2, column=1, sticky="ew", padx=(12, 0))
        body.columnconfigure(1, weight=1)

        def refresh_groups(_event=None) -> None:
            groups = sorted({item.group.strip() for item in self.class_definitions.values()
                             if item.class_value.strip() == class_var.get().strip() and item.group.strip()})
            group_picker.configure(values=groups)
            group_var.set(groups[0] if groups else "")

        class_picker.bind("<<ComboboxSelected>>", refresh_groups)
        refresh_groups()

        def add_box() -> None:
            if not group_var.get():
                messagebox.showwarning("Add class box", "Class นี้ยังไม่มี Group ให้เลือก", parent=dialog)
                return
            self.operation_rules[rule_index]["nodes"].append({
                "class": class_var.get().strip(), "group": group_var.get().strip(),
            })
            self._operation_rule_selected = (rule_index, len(self.operation_rules[rule_index]["nodes"]) - 1)
            dialog.destroy()
            self._save_operation_rules()
            self._render_operation_rule_canvas()

        actions = ttk.Frame(body)
        actions.grid(row=3, column=0, columnspan=2, sticky=tk.E, pady=(16, 0))
        ttk.Button(actions, text="Cancel", command=dialog.destroy).pack(side=tk.RIGHT)
        ttk.Button(actions, text="Add box", command=add_box).pack(side=tk.RIGHT, padx=(0, 8))
        dialog.grab_set()

    def _remove_selected_operation_rule_node(self) -> None:
        if self._operation_rule_selected is None:
            messagebox.showinfo("Operation order rule", "เลือกกล่องที่ต้องการลบก่อน", parent=self)
            return
        rule_index, node_index = self._operation_rule_selected
        try:
            self.operation_rules[rule_index]["nodes"].pop(node_index)
        except (IndexError, KeyError):
            self._operation_rule_selected = None
            return
        self._operation_rule_selected = None
        self._save_operation_rules()
        self._render_operation_rule_canvas()

    def _render_operation_rule_canvas(self) -> None:
        if not hasattr(self, "operation_rule_canvas"):
            return
        canvas = self.operation_rule_canvas
        canvas.delete("all")
        row_height, first_x, node_width, node_height, gap = 130, 155, 205, 72, 76
        max_nodes = max((len(rule["nodes"]) for rule in self.operation_rules), default=0)
        width = max(canvas.winfo_width(), first_x + max(1, max_nodes) * (node_width + gap) + 70)
        height = max(canvas.winfo_height(), 70 + max(2, len(self.operation_rules)) * row_height)
        for coordinate in range(0, width + 1, 48):
            canvas.create_line(coordinate, 0, coordinate, height, fill="#edf1f5")
        for coordinate in range(0, height + 1, 48):
            canvas.create_line(0, coordinate, width, coordinate, fill="#edf1f5")
        if not self.operation_rules:
            canvas.create_text(first_x, 92, text="Add a rule to start building the workflow",
                               anchor=tk.W, fill="#64748b", font=("Segoe UI", 11))
        for rule_index, rule in enumerate(self.operation_rules):
            y = 48 + rule_index * row_height
            rule_tag = f"operation-rule:{rule_index}"
            canvas.create_rectangle(8, y + 12, 132, y + node_height - 12, fill="#f2f6fa",
                                    outline="", tags=(rule_tag,))
            canvas.create_text(18, y + node_height / 2, text=f"RULE {rule_index + 1}  ↕", anchor=tk.W,
                               fill="#1f2937", font=("Segoe UI", 13, "bold"), tags=(rule_tag,))
            canvas.tag_bind(rule_tag, "<ButtonPress-1>",
                            lambda event, r=rule_index: self._start_operation_rule_row_drag(event, r))
            canvas.tag_bind(rule_tag, "<B1-Motion>", self._move_operation_rule_row_drag)
            canvas.tag_bind(rule_tag, "<ButtonRelease-1>", self._finish_operation_rule_row_drag)
            nodes = rule["nodes"]
            for node_index, node in enumerate(nodes):
                x = first_x + node_index * (node_width + gap)
                if node_index:
                    canvas.create_line(x - gap + 9, y + node_height / 2, x - 10, y + node_height / 2,
                                       fill="#475569", width=2, arrow=tk.LAST)
                selected = self._operation_rule_selected == (rule_index, node_index)
                tag = f"operation-node:{rule_index}:{node_index}"
                canvas.create_rectangle(x, y, x + node_width, y + node_height, fill="#ffdc35",
                                        outline="#24567b" if selected else "#ffdc35",
                                        width=3 if selected else 1, tags=(tag,))
                canvas.create_text(x + node_width / 2, y + 27, text=node["class"],
                                   fill="#1f2937", font=("Segoe UI", 9), tags=(tag,))
                canvas.create_text(x + node_width / 2, y + 48, text=node["group"],
                                   fill="#1f2937", font=("Segoe UI", 11, "bold"), tags=(tag,))
                canvas.tag_bind(tag, "<ButtonPress-1>",
                                lambda event, r=rule_index, n=node_index: self._start_operation_rule_drag(event, r, n))
                canvas.tag_bind(tag, "<B1-Motion>", self._move_operation_rule_drag)
                canvas.tag_bind(tag, "<ButtonRelease-1>", self._finish_operation_rule_drag)
            add_x = first_x + len(nodes) * (node_width + gap) + 18
            add_tag = f"operation-add:{rule_index}"
            canvas.create_rectangle(add_x, y + 19, add_x + 36, y + 55, fill="#ffffff",
                                    outline="#7b8ca0", width=1, tags=(add_tag,))
            canvas.create_text(add_x + 18, y + 37, text="+", fill="#24567b",
                               font=("Segoe UI", 20, "bold"), tags=(add_tag,))
            canvas.tag_bind(add_tag, "<Button-1>",
                            lambda _event, target_rule=rule_index: self._add_operation_rule_node(target_rule))
        canvas.configure(scrollregion=(0, 0, width, height))

    def _start_operation_rule_row_drag(self, event, rule_index: int) -> None:
        self._operation_rule_row_drag = {"rule": rule_index, "y": self.operation_rule_canvas.canvasy(event.y)}

    def _move_operation_rule_row_drag(self, event) -> None:
        if not hasattr(self, "_operation_rule_row_drag") or self._operation_rule_row_drag is None:
            return
        canvas = self.operation_rule_canvas
        current_y = canvas.canvasy(event.y)
        delta_y = current_y - self._operation_rule_row_drag["y"]
        canvas.move(f"operation-rule:{self._operation_rule_row_drag['rule']}", 0, delta_y)
        self._operation_rule_row_drag["y"] = current_y

    def _finish_operation_rule_row_drag(self, event) -> None:
        drag = getattr(self, "_operation_rule_row_drag", None)
        if drag is None:
            return
        source_rule = drag["rule"]
        target_rule = min(max(0, int((self.operation_rule_canvas.canvasy(event.y) - 48) // 130)),
                          len(self.operation_rules) - 1)
        if target_rule != source_rule:
            rule = self.operation_rules.pop(source_rule)
            self.operation_rules.insert(target_rule, rule)
            self._operation_rule_selected = None
            self._save_operation_rules()
        self._operation_rule_row_drag = None
        self._render_operation_rule_canvas()

    def _start_operation_rule_drag(self, event, rule_index: int, node_index: int) -> None:
        self._operation_rule_selected = (rule_index, node_index)
        self._operation_rule_drag = {"rule": rule_index, "node": node_index, "x": event.x, "y": event.y}
        self._render_operation_rule_canvas()

    def _move_operation_rule_drag(self, event) -> None:
        if self._operation_rule_drag is None:
            return
        canvas = self.operation_rule_canvas
        delta_x, delta_y = event.x - self._operation_rule_drag["x"], event.y - self._operation_rule_drag["y"]
        tag = f"operation-node:{self._operation_rule_drag['rule']}:{self._operation_rule_drag['node']}"
        canvas.move(tag, delta_x, delta_y)
        self._operation_rule_drag["x"], self._operation_rule_drag["y"] = event.x, event.y

    def _finish_operation_rule_drag(self, event) -> None:
        if self._operation_rule_drag is None:
            return
        source_rule, source_node = self._operation_rule_drag["rule"], self._operation_rule_drag["node"]
        node = self.operation_rules[source_rule]["nodes"].pop(source_node)
        target_rule = min(max(0, int((event.y - 48) // 130)), len(self.operation_rules) - 1)
        target_nodes = self.operation_rules[target_rule]["nodes"]
        target_index = min(max(0, int((event.x - 155 + 140) // 281)), len(target_nodes))
        target_nodes.insert(target_index, node)
        self._operation_rule_selected = (target_rule, target_index)
        self._operation_rule_drag = None
        self._save_operation_rules()
        self._render_operation_rule_canvas()

    def _update_capacity_preview(self) -> None:
        work_hours = self._preview_capacity_number(self.work_hours_per_day_var.get())
        raw_rate = self._preview_capacity_number(self.raw_cups_per_hour_var.get())
        cooked_rate = self._preview_capacity_number(self.cooked_cups_per_hour_var.get())
        noodle_rate = self._preview_capacity_number(self.cooked_noodle_cups_per_hour_var.get())
        raw_base = self._daily_capacity_preview(raw_rate, work_hours)
        cooked_base = self._daily_capacity_preview(cooked_rate, work_hours)
        noodle_base = self._daily_capacity_preview(noodle_rate, work_hours)
        self.raw_wonton_daily_var.set(self._format_optional_number(raw_base) if raw_base is not None else "—")
        self.cooked_wonton_daily_var.set(self._format_optional_number(cooked_base) if cooked_base is not None else "—")
        self.cooked_wonton_noodle_daily_var.set(self._format_optional_number(noodle_base) if noodle_base is not None else "—")

    @staticmethod
    def _preview_capacity_number(value: str) -> int | float | None:
        cleaned = value.strip().replace(",", "")
        if not cleaned:
            return None
        try:
            numeric = float(cleaned)
        except ValueError:
            return None
        if not math.isfinite(numeric) or numeric < 0:
            return None
        return int(numeric) if numeric.is_integer() else numeric

    def _load_capacity_settings(self) -> None:
        try:
            settings = load_capacity_settings(self.capacity_file_path)
        except ValueError as exc:
            self.capacity_status_var.set(str(exc))
            return
        self.capacity_settings = settings
        self.capacity_settings = CapacitySettings(
            raw_percentage=100, cooked_percentage=100,
            raw_cups_per_hour=settings.raw_cups_per_hour,
            cooked_cups_per_hour=settings.cooked_cups_per_hour,
            cooked_noodle_cups_per_hour=settings.cooked_noodle_cups_per_hour,
            work_hours_per_day=settings.work_hours_per_day,
        )
        self.raw_cups_per_hour_var.set(self._format_optional_number(settings.raw_cups_per_hour))
        self.cooked_cups_per_hour_var.set(self._format_optional_number(settings.cooked_cups_per_hour))
        self.cooked_noodle_cups_per_hour_var.set(
            self._format_optional_number(settings.cooked_noodle_cups_per_hour))
        self.work_hours_per_day_var.set(self._format_optional_number(settings.work_hours_per_day))
        self._update_capacity_preview()
        if self.capacity_file_path.exists():
            self.capacity_status_var.set("Loaded saved capacity settings.")
        self._plan_inputs_changed()

    def _save_all_capacity_settings(self) -> None:
        try:
            work_hours_per_day = self._parse_work_hours(self.work_hours_per_day_var.get())
            raw_cups_per_hour = self._parse_capacity_number(
                self.raw_cups_per_hour_var.get(), "Raw cups / hr")
            cooked_cups_per_hour = self._parse_capacity_number(
                self.cooked_cups_per_hour_var.get(), "Cooked cups / hr")
            cooked_noodle_cups_per_hour = self._parse_capacity_number(
                self.cooked_noodle_cups_per_hour_var.get(), "Cooked noodle cups / hr")
            settings = CapacitySettings(
                raw_percentage=100,
                cooked_percentage=100,
                raw_wonton=None,
                cooked_wonton=None,
                raw_cups_per_hour=raw_cups_per_hour,
                cooked_cups_per_hour=cooked_cups_per_hour,
                cooked_noodle_cups_per_hour=cooked_noodle_cups_per_hour,
                work_hours_per_day=work_hours_per_day,
            )
            self.capacity_settings = save_capacity_settings(self.capacity_file_path, settings)
        except ValueError as exc:
            messagebox.showerror("Save capacity", str(exc))
            return
        self.raw_cups_per_hour_var.set(self._format_optional_number(raw_cups_per_hour))
        self.cooked_cups_per_hour_var.set(self._format_optional_number(cooked_cups_per_hour))
        self.cooked_noodle_cups_per_hour_var.set(self._format_optional_number(cooked_noodle_cups_per_hour))
        self.work_hours_per_day_var.set(self._format_optional_number(work_hours_per_day))
        self._update_capacity_preview()
        self.capacity_status_var.set(
            f"Saved hourly capacity with {self._format_optional_number(work_hours_per_day)} working hours/day."
        )
        self._plan_inputs_changed()

    @staticmethod
    def _parse_capacity_number(value: str, label: str) -> int | float:
        cleaned = value.strip().replace(",", "")
        if not cleaned:
            raise ValueError(f"Enter a number for {label}.")
        try:
            numeric = float(cleaned)
        except ValueError as exc:
            raise ValueError(f"{label} must be numeric.") from exc
        if not math.isfinite(numeric) or numeric < 0:
            raise ValueError(f"{label} must be zero or greater.")
        return int(numeric) if numeric.is_integer() else numeric

    @staticmethod
    def _parse_optional_capacity_number(value: str, label: str) -> int | float | None:
        return None if not value.strip() else CapacityViewMixin._parse_capacity_number(value, label)

    @staticmethod
    def _daily_capacity_preview(rate: int | float | None, work_hours: int | float | None) -> int | float | None:
        return None if rate is None or work_hours is None or not 0 < work_hours <= 24 else rate * work_hours

    @staticmethod
    def _parse_work_hours(value: str) -> int | float:
        hours = CapacityViewMixin._parse_capacity_number(value, "Working hours per day")
        if not 0 < hours <= 24:
            raise ValueError("Working hours per day must be more than 0 and no more than 24.")
        return hours
