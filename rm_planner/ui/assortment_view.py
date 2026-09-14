"""AssortmentView screen behavior."""

from __future__ import annotations

from .common import *  # shared UI types, domain services, and display constants


class AssortmentViewMixin:
    def _build_assortment_std_tab(self) -> None:
        source_frame = ttk.Frame(self.assortment_std_tab)
        source_frame.pack(fill=tk.X, pady=(0, 10))
        ttk.Label(source_frame, text="Master file:", style="Summary.TLabel").pack(side=tk.LEFT)
        ttk.Label(source_frame, text=str(self.assortment_file_path)).pack(side=tk.LEFT, padx=(6, 0))
        ttk.Button(source_frame, text="Reload master", command=self._load_assortment_data).pack(side=tk.RIGHT)
        ttk.Button(source_frame, text="Save ranges", command=self._save_assortment_size_ranges).pack(
            side=tk.RIGHT, padx=(0, 8)
        )

        self.wonton_weight_vars = {
            size_class: tk.StringVar(
                value=self._format_optional_number(
                    self.wonton_weight_settings.grams_for(size_class)
                )
            )
            for size_class in SIZE_CLASSES
        }
        self.wonton_yield_preview_vars = {
            size_class: tk.StringVar()
            for size_class in SIZE_CLASSES
        }
        weight_frame = ttk.LabelFrame(
            self.assortment_std_tab,
            text="Wonton weight and estimated yield",
            padding=10,
        )
        weight_frame.pack(fill=tk.X, pady=(0, 10))
        for column, size_class in enumerate(SIZE_CLASSES):
            weight_frame.columnconfigure(column, weight=1)
            class_frame = ttk.Frame(weight_frame)
            class_frame.grid(
                row=0,
                column=column,
                sticky="ew",
                padx=(0, 20) if column == 0 else (0, 12),
            )
            ttk.Label(
                class_frame,
                text=size_class,
                style="Summary.TLabel",
            ).pack(side=tk.LEFT, padx=(0, 8))
            weight_entry = ttk.Entry(
                class_frame,
                textvariable=self.wonton_weight_vars[size_class],
                width=10,
            )
            weight_entry.pack(side=tk.LEFT)
            ttk.Label(class_frame, text="g/wonton").pack(side=tk.LEFT, padx=(5, 12))
            ttk.Label(
                class_frame,
                textvariable=self.wonton_yield_preview_vars[size_class],
                style="Summary.TLabel",
            ).pack(side=tk.LEFT)
            self.wonton_weight_vars[size_class].trace_add(
                "write",
                lambda *_args: self._update_wonton_yield_previews(),
            )
        ttk.Button(
            weight_frame,
            text="Save wonton weights",
            command=self._save_wonton_weight_settings,
        ).grid(row=0, column=len(SIZE_CLASSES), sticky=tk.E)
        self._update_wonton_yield_previews()

        table_frame = ttk.Frame(self.assortment_std_tab)
        table_frame.pack(fill=tk.BOTH, expand=True)
        table_frame.rowconfigure(0, weight=1)
        table_frame.columnconfigure(0, weight=1)

        self.assortment_canvas = tk.Canvas(
            table_frame,
            background="white",
            highlightthickness=1,
            highlightbackground="#b7b7b7",
        )
        vertical = ttk.Scrollbar(table_frame, orient=tk.VERTICAL, command=self.assortment_canvas.yview)
        horizontal = ttk.Scrollbar(table_frame, orient=tk.HORIZONTAL, command=self.assortment_canvas.xview)
        self.assortment_canvas.configure(yscrollcommand=vertical.set, xscrollcommand=horizontal.set)
        self.assortment_canvas.grid(row=0, column=0, sticky="nsew")
        vertical.grid(row=0, column=1, sticky="ns")
        horizontal.grid(row=1, column=0, sticky="ew")
        self.assortment_canvas.bind("<ButtonPress-1>", self._start_assortment_range_drag)
        self.assortment_canvas.bind("<B1-Motion>", self._drag_assortment_range)
        self.assortment_canvas.bind("<ButtonRelease-1>", self._end_assortment_range_drag)
        self.assortment_canvas.bind("<MouseWheel>", self._scroll_assortment_canvas)

        ttk.Label(
            self.assortment_std_tab,
            textvariable=self.assortment_status_var,
            relief=tk.SUNKEN,
            anchor=tk.W,
            padding=(6, 3),
        ).pack(fill=tk.X, pady=(8, 0))

    def _wonton_weight_settings_from_form(self) -> WontonWeightSettings:
        values: dict[str, float] = {}
        for size_class in SIZE_CLASSES:
            text = self.wonton_weight_vars[size_class].get().strip().replace(",", "")
            try:
                values[size_class] = float(text)
            except ValueError as exc:
                raise ValueError(
                    f"{size_class} wonton weight must be a valid number."
                ) from exc
        return WontonWeightSettings(
            m_grams=values["M"],
            s_grams=values["S"],
            ss_grams=values["SS"],
        )

    def _update_wonton_yield_previews(self) -> None:
        if not hasattr(self, "wonton_yield_preview_vars"):
            return
        try:
            settings = self._wonton_weight_settings_from_form()
        except ValueError:
            for variable in self.wonton_yield_preview_vars.values():
                variable.set("Enter a weight above 0")
            return
        for size_class in SIZE_CLASSES:
            self.wonton_yield_preview_vars[size_class].set(
                f"≈ {self._format_optional_number(settings.wontons_per_kg(size_class))} "
                "wontons/kg"
            )

    def _load_wonton_weight_settings(self) -> None:
        try:
            settings = load_wonton_weight_settings(self.wonton_weight_file_path)
        except ValueError as exc:
            self.assortment_status_var.set(str(exc))
            return
        self.wonton_weight_settings = settings
        if hasattr(self, "wonton_weight_vars"):
            for size_class in SIZE_CLASSES:
                self.wonton_weight_vars[size_class].set(
                    self._format_optional_number(settings.grams_for(size_class))
                )
            self._update_wonton_yield_previews()

    def _save_wonton_weight_settings(self) -> None:
        try:
            settings = self._wonton_weight_settings_from_form()
            save_wonton_weight_settings(self.wonton_weight_file_path, settings)
        except ValueError as exc:
            messagebox.showerror("Save wonton weights", str(exc))
            return
        self.wonton_weight_settings = settings
        self._update_wonton_yield_previews()
        self._refresh_assortment_actual_history_table()
        self._refresh_rm_timeline()
        self._plan_inputs_changed()
        summary = " | ".join(
            f"{size_class} {self._format_optional_number(settings.grams_for(size_class))} g "
            f"= {self._format_optional_number(settings.wontons_per_kg(size_class))} wontons/kg"
            for size_class in SIZE_CLASSES
        )
        self.assortment_status_var.set(f"Saved wonton weights. {summary}")

    def _fill_stock_from_assortment_std(self) -> None:
        if self.assortment_table is None:
            messagebox.showerror(
                "Fill from Assortment STD",
                "Load a valid assortment master before calculating stock rows.",
            )
            return
        try:
            weight_text = self.stock_harvest_weight_var.get().strip().replace(",", "")
            predictions = predict_assortment(
                self.assortment_table,
                self.stock_harvest_size_var.get(),
                weight_text,
            )
            allocated_weight = sum(item.weight for item in predictions)
        except ValueError as exc:
            messagebox.showerror("Fill from Assortment STD", str(exc))
            return

        self._editing_actual_record_id = None
        self.assortment_actual_save_button.configure(text="Save stock")
        class_entries = aggregate_entries_by_size_class(
            (
                ActualAssortmentEntry(size=item.output_size, weight=item.weight)
                for item in predictions
            ),
            self._current_assortment_size_range_definitions(),
        )
        self._set_assortment_actual_boxes(list(class_entries))
        requested_size = self.stock_harvest_size_var.get().strip()
        master_size = requested_size if requested_size.casefold().startswith("s.") else f"S.{requested_size}"
        resolved_size = next(
            base_size
            for base_size in self.assortment_table.base_sizes
            if base_size.casefold() == master_size.casefold()
        )
        message = (
            f"Combined {len(predictions)} assortment sizes into "
            f"{len(class_entries)} class rows from {resolved_size} and "
            f"{allocated_weight:,} kg in whole kilograms. "
            "Review or edit the rows before saving."
        )
        self.assortment_actual_status_var.set(message)

    @staticmethod
    def _format_weight(weight: float) -> str:
        return f"{weight:,.2f}".rstrip("0").rstrip(".")

    @staticmethod
    def _format_class_name_for_display(item: ClassDefinition) -> str:
        if item.class_value.casefold() != "ถ้วย/unit".casefold():
            return item.name
        try:
            value = float(item.name.replace(",", ""))
        except ValueError:
            return item.name
        return f"{value:,.2f}".rstrip("0").rstrip(".")

    def _load_assortment_data(self) -> None:
        try:
            table = load_assortment(self.assortment_file_path)
        except (FileNotFoundError, ValueError) as exc:
            self.assortment_table = None
            self.stock_harvest_size_combo.configure(values=())
            self.assortment_canvas.delete("all")
            self.assortment_status_var.set(str(exc))
            return

        self.assortment_table = table
        self.stock_harvest_size_combo.configure(
            values=tuple(
                base_size[2:]
                if base_size.casefold().startswith("s.")
                else base_size
                for base_size in table.base_sizes
            )
        )
        range_note = (
            " Initial M/S/SS ranges are placeholders; drag and save them."
            if not self.assortment_size_range_file_path.exists()
            else ""
        )
        try:
            saved_ranges = load_size_ranges(
                self.assortment_size_range_file_path,
                table.output_sizes,
            )
        except ValueError as exc:
            saved_ranges = default_size_ranges(table.output_sizes)
            range_note = f" Saved range file was ignored: {exc}"
        output_index = {size: index for index, size in enumerate(table.output_sizes)}
        self.assortment_size_ranges = {
            item.size_class: (output_index[item.start_size], output_index[item.end_size])
            for item in saved_ranges
        }
        self._show_assortment_table(table)
        if table.invalid_base_sizes:
            invalid = ", ".join(
                f"{base_size} ({total:.1%})" for base_size, total in table.invalid_base_sizes
            )
            self.assortment_status_var.set(
                f"Warning: output percentages do not total 100% for {invalid}.{range_note}"
            )
        else:
            self.assortment_status_var.set(
                f"Loaded {len(table.base_sizes)} base sizes × {len(table.output_sizes)} output ranges "
                f"from sheet {table.sheet_name}. Every base-size distribution totals 100%."
                f"{range_note}"
            )

    def _show_assortment_table(self, table: AssortmentTable) -> None:
        canvas = self.assortment_canvas
        canvas.delete("all")
        class_area_width = len(SIZE_CLASSES) * ASSORTMENT_CLASS_WIDTH
        data_start = class_area_width + ASSORTMENT_OUTPUT_WIDTH
        total_width = data_start + len(table.base_sizes) * ASSORTMENT_BASE_WIDTH
        total_height = ASSORTMENT_HEADER_HEIGHT + len(table.output_sizes) * ASSORTMENT_ROW_HEIGHT
        canvas.configure(scrollregion=(0, 0, total_width, total_height))

        headers = (*SIZE_CLASSES, "Actual output size", *table.base_sizes)
        widths = (
            *([ASSORTMENT_CLASS_WIDTH] * len(SIZE_CLASSES)),
            ASSORTMENT_OUTPUT_WIDTH,
            *([ASSORTMENT_BASE_WIDTH] * len(table.base_sizes)),
        )
        x = 0
        for header, width in zip(headers, widths):
            canvas.create_rectangle(
                x,
                0,
                x + width,
                ASSORTMENT_HEADER_HEIGHT,
                fill="#edf2f7",
                outline="#c5ccd3",
                tags="assortment_grid",
            )
            canvas.create_text(
                x + width / 2,
                ASSORTMENT_HEADER_HEIGHT / 2,
                text=header,
                font=("Segoe UI", 9, "bold"),
                tags="assortment_grid",
            )
            x += width

        for row_index, (output_size, percentages) in enumerate(
            zip(table.output_sizes, table.percentages)
        ):
            y1 = ASSORTMENT_HEADER_HEIGHT + row_index * ASSORTMENT_ROW_HEIGHT
            y2 = y1 + ASSORTMENT_ROW_HEIGHT
            canvas.create_rectangle(
                0,
                y1,
                total_width,
                y2,
                fill="#ffffff" if row_index % 2 == 0 else "#f8fafc",
                outline="#d8dde3",
                tags="assortment_grid",
            )
            canvas.create_text(
                class_area_width + ASSORTMENT_OUTPUT_WIDTH / 2,
                (y1 + y2) / 2,
                text=output_size,
                font=("Segoe UI", 9, "bold"),
                tags="assortment_grid",
            )
            for base_index, percentage in enumerate(percentages):
                if percentage == 0:
                    continue
                cell_x = data_start + base_index * ASSORTMENT_BASE_WIDTH
                canvas.create_text(
                    cell_x + ASSORTMENT_BASE_WIDTH / 2,
                    (y1 + y2) / 2,
                    text=f"{percentage:.1%}",
                    font=("Segoe UI", 9),
                    tags="assortment_grid",
                )

        x = 0
        for width in widths:
            canvas.create_line(x, 0, x, total_height, fill="#d8dde3", tags="assortment_grid")
            x += width
        canvas.create_line(total_width, 0, total_width, total_height, fill="#d8dde3")
        self._draw_assortment_range_boxes()

    def _draw_assortment_range_boxes(self) -> None:
        self.assortment_canvas.delete("assortment_range")
        if not self.assortment_table:
            return
        for class_index, size_class in enumerate(SIZE_CLASSES):
            start, end = self.assortment_size_ranges[size_class]
            x1 = class_index * ASSORTMENT_CLASS_WIDTH + 5
            x2 = (class_index + 1) * ASSORTMENT_CLASS_WIDTH - 5
            y1 = ASSORTMENT_HEADER_HEIGHT + start * ASSORTMENT_ROW_HEIGHT + 3
            y2 = ASSORTMENT_HEADER_HEIGHT + (end + 1) * ASSORTMENT_ROW_HEIGHT - 3
            fill, outline = ASSORTMENT_CLASS_COLORS[size_class]
            self.assortment_canvas.create_rectangle(
                x1,
                y1,
                x2,
                y2,
                fill=fill,
                outline=outline,
                width=2,
                tags="assortment_range",
            )
            self.assortment_canvas.create_rectangle(
                x1 + 8,
                y1 - 2,
                x2 - 8,
                y1 + 4,
                fill=outline,
                outline=outline,
                tags="assortment_range",
            )
            self.assortment_canvas.create_rectangle(
                x1 + 8,
                y2 - 4,
                x2 - 8,
                y2 + 2,
                fill=outline,
                outline=outline,
                tags="assortment_range",
            )
            start_size = self.assortment_table.output_sizes[start]
            end_size = self.assortment_table.output_sizes[end]
            label = size_class if start == end else f"{size_class}\n{start_size}\n↓\n{end_size}"
            self.assortment_canvas.create_text(
                (x1 + x2) / 2,
                (y1 + y2) / 2,
                text=label,
                fill="#17202a",
                font=("Segoe UI", 9, "bold"),
                justify=tk.CENTER,
                tags="assortment_range",
            )

    def _start_assortment_range_drag(self, event: tk.Event) -> None:
        if not self.assortment_table:
            return
        x = self.assortment_canvas.canvasx(event.x)
        y = self.assortment_canvas.canvasy(event.y)
        class_index = int(x // ASSORTMENT_CLASS_WIDTH)
        if class_index < 0 or class_index >= len(SIZE_CLASSES) or y < ASSORTMENT_HEADER_HEIGHT:
            self._assortment_range_drag = None
            return
        row = self._assortment_row_at(y)
        size_class = SIZE_CLASSES[class_index]
        start, end = self.assortment_size_ranges[size_class]
        top = ASSORTMENT_HEADER_HEIGHT + start * ASSORTMENT_ROW_HEIGHT
        bottom = ASSORTMENT_HEADER_HEIGHT + (end + 1) * ASSORTMENT_ROW_HEIGHT
        if top <= y <= bottom:
            if y - top <= 9:
                mode = "start"
            elif bottom - y <= 9:
                mode = "end"
            else:
                mode = "move"
            changed = False
        else:
            mode = "new"
            self.assortment_size_ranges[size_class] = (row, row)
            self._draw_assortment_range_boxes()
            changed = True
        self._assortment_range_drag = {
            "size_class": size_class,
            "mode": mode,
            "anchor": row,
            "start": start,
            "end": end,
        }
        self._assortment_range_drag_changed = changed

    def _drag_assortment_range(self, event: tk.Event) -> None:
        if not self.assortment_table or not self._assortment_range_drag:
            return
        y = self.assortment_canvas.canvasy(event.y)
        row = self._assortment_row_at(y)
        size_class = str(self._assortment_range_drag["size_class"])
        mode = str(self._assortment_range_drag["mode"])
        original_start = int(self._assortment_range_drag["start"])
        original_end = int(self._assortment_range_drag["end"])
        current_start, current_end = self.assortment_size_ranges[size_class]
        if mode == "start":
            updated = (min(row, current_end), current_end)
        elif mode == "end":
            updated = (current_start, max(row, current_start))
        elif mode == "new":
            anchor = int(self._assortment_range_drag["anchor"])
            updated = (min(anchor, row), max(anchor, row))
        else:
            delta = row - int(self._assortment_range_drag["anchor"])
            length = original_end - original_start
            new_start = max(
                0,
                min(original_start + delta, len(self.assortment_table.output_sizes) - length - 1),
            )
            updated = (new_start, new_start + length)
        if updated != self.assortment_size_ranges[size_class]:
            self.assortment_size_ranges[size_class] = updated
            self._assortment_range_drag_changed = True
            self._draw_assortment_range_boxes()

    def _end_assortment_range_drag(self, event: tk.Event) -> None:
        drag = self._assortment_range_drag
        self._assortment_range_drag = None
        if drag:
            size_class = str(drag["size_class"])
            start, end = self.assortment_size_ranges[size_class]
            start_size = self.assortment_table.output_sizes[start] if self.assortment_table else ""
            end_size = self.assortment_table.output_sizes[end] if self.assortment_table else ""
            suffix = " Click Save ranges to keep this change." if self._assortment_range_drag_changed else ""
            self.assortment_status_var.set(
                f"{size_class} uses actual output sizes {start_size} to {end_size}.{suffix}"
            )
            return
        self._describe_assortment_cell(event)

    def _assortment_row_at(self, canvas_y: float) -> int:
        if not self.assortment_table:
            return 0
        row = int((canvas_y - ASSORTMENT_HEADER_HEIGHT) // ASSORTMENT_ROW_HEIGHT)
        return max(0, min(row, len(self.assortment_table.output_sizes) - 1))

    def _save_assortment_size_ranges(self) -> None:
        if not self.assortment_table:
            messagebox.showwarning("Save ranges", "Load the assortment master first.")
            return
        ranges = tuple(
            AssortmentSizeRange(
                size_class,
                self.assortment_table.output_sizes[self.assortment_size_ranges[size_class][0]],
                self.assortment_table.output_sizes[self.assortment_size_ranges[size_class][1]],
            )
            for size_class in SIZE_CLASSES
        )
        try:
            save_size_ranges(
                self.assortment_size_range_file_path,
                ranges,
                self.assortment_table.output_sizes,
            )
        except ValueError as exc:
            messagebox.showerror("Save ranges", str(exc))
            return
        summary = ", ".join(
            f"{item.size_class}: {item.start_size}–{item.end_size}" for item in ranges
        )
        self._refresh_assortment_actual_history_table()
        self._refresh_rm_timeline()
        self._plan_inputs_changed()
        self.assortment_status_var.set(f"Saved assortment size ranges. {summary}")

    def _scroll_assortment_canvas(self, event: tk.Event) -> str:
        self.assortment_canvas.yview_scroll(int(-event.delta / 120), "units")
        return "break"

    def _describe_assortment_cell(self, event: tk.Event) -> None:
        if not self.assortment_table:
            return
        x = self.assortment_canvas.canvasx(event.x)
        y = self.assortment_canvas.canvasy(event.y)
        data_start = len(SIZE_CLASSES) * ASSORTMENT_CLASS_WIDTH + ASSORTMENT_OUTPUT_WIDTH
        if x < data_start or y < ASSORTMENT_HEADER_HEIGHT:
            return
        base_index = int((x - data_start) // ASSORTMENT_BASE_WIDTH)
        output_index = self._assortment_row_at(y)
        if base_index < 0 or base_index >= len(self.assortment_table.base_sizes):
            return
        base_size = self.assortment_table.base_sizes[base_index]
        output_size = self.assortment_table.output_sizes[output_index]
        percentage = self.assortment_table.percentages[output_index][base_index]
        self.assortment_status_var.set(
            f"Base harvest {base_size} → actual output {output_size}: {percentage:.4%} "
            f"(displayed as {percentage:.1%})."
        )
