from __future__ import annotations

import tkinter as tk
from tkinter import ttk

import ttkbootstrap as tb


class ScrollableFrame(tb.Frame):
    def __init__(self, parent: ttk.Widget, *, bootstyle: str | None = None) -> None:
        super().__init__(parent)

        self._canvas = tk.Canvas(self, highlightthickness=0)
        self._vsb = ttk.Scrollbar(self, orient="vertical", command=self._canvas.yview)
        self._hsb = ttk.Scrollbar(self, orient="horizontal", command=self._canvas.xview)
        self._canvas.configure(yscrollcommand=self._vsb.set, xscrollcommand=self._hsb.set)

        self._vsb.pack(side="right", fill="y")
        self._hsb.pack(side="bottom", fill="x")
        self._canvas.pack(side="left", fill="both", expand=True)

        self.inner = tb.Frame(self._canvas)
        if bootstyle:
            try:
                self.inner.configure(bootstyle=bootstyle)
            except Exception:
                pass

        self._window_id = self._canvas.create_window((0, 0), window=self.inner, anchor="nw")

        self.inner.bind("<Configure>", self._on_inner_configure)
        self._canvas.bind("<Configure>", self._on_canvas_configure)

        self._bind_mousewheel(self._canvas)
        self._bind_mousewheel(self.inner)

    def _on_inner_configure(self, _e=None) -> None:
        try:
            self._canvas.configure(scrollregion=self._canvas.bbox("all"))
        except Exception:
            pass

    def _on_canvas_configure(self, e) -> None:
        try:
            self._canvas.itemconfigure(self._window_id, width=e.width)
        except Exception:
            pass

    def _bind_mousewheel(self, widget: tk.Misc) -> None:
        widget.bind("<MouseWheel>", self._on_mousewheel, add=True)
        widget.bind("<Shift-MouseWheel>", self._on_shift_mousewheel, add=True)

    def _on_mousewheel(self, e) -> str:
        try:
            delta = int(-1 * (e.delta / 120))
        except Exception:
            delta = 0
        if delta:
            self._canvas.yview_scroll(delta, "units")
        return "break"

    def _on_shift_mousewheel(self, e) -> str:
        try:
            delta = int(-1 * (e.delta / 120))
        except Exception:
            delta = 0
        if delta:
            self._canvas.xview_scroll(delta, "units")
        return "break"
