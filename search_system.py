"""Global search system for Gym Management System.

Provides a Spotlight-style floating search dialog that searches across:
- members
- subscriptions
- payments
- attendance

Works with the existing database schema from database.py.
"""

from __future__ import annotations

import re
import threading
import tkinter as tk
from tkinter import ttk

import ttkbootstrap as tb

import config
from database import DatabaseManager
from utils import format_money


def _get_colors() -> dict[str, str]:
    """Return colors dict from config if present, otherwise fallback to THEME_COLORS."""

    colors = getattr(config, "COLORS", None)
    if isinstance(colors, dict):
        return colors

    theme = getattr(config, "THEME_COLORS", {})
    return {
        "primary": theme.get("primary", "#2563eb"),
        "background": theme.get("background", "#f8fafc"),
        "text": theme.get("text_primary", "#1e293b"),
        "text_light": theme.get("text_secondary", "#64748b"),
        "danger": theme.get("danger", "#dc2626"),
    }


def _get_fonts() -> dict[str, tuple]:
    fonts = getattr(config, "FONTS", None)
    if isinstance(fonts, dict):
        return fonts

    return {
        "heading": ("Cairo", 14, "bold"),
        "body": ("Cairo", 11),
        "small": ("Cairo", 10),
    }


COLORS = _get_colors()
FONTS = _get_fonts()


class GlobalSearchDialog(tb.Toplevel):
    """Floating unified search dialog.

    Args:
        parent: main window
        db_manager: DatabaseManager instance
        callback_dict: mapping of open callbacks
            {
                'open_member': func(member_id),
                'open_subscription': func(sub_id),
                'open_payment': func(payment_id),
                'open_attendance': func(attendance_id)
            }
    """

    def __init__(self, parent: tk.Misc, db_manager: DatabaseManager, callback_dict: dict[str, object] | None = None) -> None:
        super().__init__(parent)

        self.db = db_manager
        self.callbacks = callback_dict or {}

        self.search_results: dict[str, list[dict]] = {}
        self.all_results: list[dict] = []
        self.selected_index: int = 0

        self._search_timer: str | None = None
        self._search_thread: threading.Thread | None = None
        self._search_seq: int = 0

        self.setup_window()
        self.setup_ui()
        self.bind_events()

    # ------------------------------
    # Window / UI
    # ------------------------------

    def setup_window(self) -> None:
        self.title("")
        self.geometry("700x500")
        self.minsize(520, 360)
        self.resizable(True, True)

        self.update_idletasks()
        x = (self.winfo_screenwidth() - 700) // 2
        y = (self.winfo_screenheight() - 500) // 3
        self.geometry(f"+{x}+{y}")

        # Border style
        self.configure(borderwidth=2, relief="solid")

        self.grab_set()

    def setup_ui(self) -> None:
        main = tb.Frame(self, padding=15)
        main.pack(fill="both", expand=True)

        header = tb.Frame(main)
        header.pack(fill="x", pady=(0, 12))

        tb.Label(header, text="🔍", font=("Segoe UI Emoji", 18)).pack(side="right", padx=(0, 10))

        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", lambda *_: self.on_search_changed())

        self.search_entry = tb.Entry(header, textvariable=self.search_var, font=("Cairo", 14), justify="right")
        self.search_entry.pack(side="right", fill="x", expand=True)
        self.search_entry.focus_set()

        tb.Button(header, text="✕", width=3, bootstyle="secondary-link", command=self.destroy).pack(side="left")

        # Results scrollable area
        body = tb.Frame(main)
        body.pack(fill="both", expand=True)

        self.results_canvas = tk.Canvas(body, highlightthickness=0)
        self.results_canvas.pack(side="right", fill="both", expand=True)

        scrollbar = ttk.Scrollbar(body, orient="vertical", command=self.results_canvas.yview)
        scrollbar.pack(side="left", fill="y")
        self.results_canvas.configure(yscrollcommand=scrollbar.set)

        self.results_frame = tb.Frame(self.results_canvas)
        self.canvas_window = self.results_canvas.create_window((0, 0), window=self.results_frame, anchor="ne")

        def on_frame_configure(_e):
            self.results_canvas.configure(scrollregion=self.results_canvas.bbox("all"))

        def on_canvas_configure(event):
            self.results_canvas.itemconfigure(self.canvas_window, width=event.width)

        self.results_frame.bind("<Configure>", on_frame_configure)
        self.results_canvas.bind("<Configure>", on_canvas_configure)

        footer = tb.Label(
            main,
            text="Enter للفتح  •  ↑↓ للتنقل  •  Esc للإغلاق",
            font=FONTS["small"],
            foreground=COLORS["text_light"],
            anchor="center",
        )
        footer.pack(side="bottom", pady=(10, 0))

    def bind_events(self) -> None:
        self.bind("<Escape>", lambda _e: self.destroy())
        self.bind("<Return>", lambda _e: self.on_enter_pressed())
        self.bind("<Up>", lambda _e: self.navigate_up())
        self.bind("<Down>", lambda _e: self.navigate_down())
        self.search_entry.bind("<Down>", lambda _e: self.navigate_down())

    # ------------------------------
    # Search logic
    # ------------------------------

    def on_search_changed(self) -> None:
        query = self.search_var.get().strip()

        if len(query) < 2:
            self.clear_results()
            return

        if self._search_timer is not None:
            try:
                self.after_cancel(self._search_timer)
            except Exception:
                pass

        self._search_timer = self.after(300, lambda q=query: self.perform_search_async(q))

    def perform_search_async(self, query: str) -> None:
        self.clear_results()
        self._search_seq += 1
        seq = self._search_seq

        def worker() -> None:
            results = {
                "member": self.search_members(query),
                "subscription": self.search_subscriptions(query),
                "payment": self.search_payments(query),
                "attendance": self.search_attendance(query),
            }

            self.after(0, lambda: self._render_search_results(seq, results))

        self._search_thread = threading.Thread(target=worker, daemon=True)
        self._search_thread.start()

    def _render_search_results(self, seq: int, results: dict[str, list[dict]]) -> None:
        if seq != self._search_seq:
            return

        self.search_results = results
        self.all_results = []
        self.selected_index = 0

        any_found = False

        if results.get("member"):
            any_found = True
            self.add_result_section("👤 الأعضاء", results["member"], "member")

        if results.get("subscription"):
            any_found = True
            self.add_result_section("💳 الاشتراكات", results["subscription"], "subscription")

        if results.get("payment"):
            any_found = True
            self.add_result_section("💰 المدفوعات", results["payment"], "payment")

        if results.get("attendance"):
            any_found = True
            self.add_result_section("📅 الحضور", results["attendance"], "attendance")

        if not any_found:
            tb.Label(self.results_frame, text="😕 لا توجد نتائج", font=("Cairo", 14), foreground=COLORS["text_light"]).pack(
                pady=60
            )

        self.highlight_selected()

    def search_members(self, query: str) -> list[dict]:
        pattern = f"%{query}%"

        with self.db.get_connection() as conn:
            rows = conn.execute(
                """
                SELECT m.id,
                       m.member_code,
                       (m.first_name || ' ' || m.last_name) AS name,
                       m.phone,
                       m.email,
                       m.status,
                       (
                         SELECT s.end_date
                         FROM subscriptions s
                         WHERE s.member_id = m.id
                         ORDER BY date(s.end_date) DESC
                         LIMIT 1
                       ) AS last_end_date
                FROM members m
                WHERE (m.first_name || ' ' || m.last_name) LIKE ?
                   OR m.member_code LIKE ?
                   OR m.phone LIKE ?
                   OR COALESCE(m.email, '') LIKE ?
                   OR COALESCE(m.national_id, '') LIKE ?
                ORDER BY m.first_name ASC
                LIMIT 10
                """,
                (pattern, pattern, pattern, pattern, pattern),
            ).fetchall()

        out = []
        for r in rows:
            status_ar = {"active": "نشط", "inactive": "غير نشط", "frozen": "مجمد"}.get(str(r["status"]), "-")
            out.append(
                {
                    "id": int(r["id"]),
                    "text": f"{r['name']} - {r['phone']} - {status_ar}",
                }
            )
        return out

    def search_subscriptions(self, query: str) -> list[dict]:
        pattern = f"%{query}%"

        with self.db.get_connection() as conn:
            rows = conn.execute(
                """
                SELECT s.id,
                       st.name_ar AS plan_name,
                       (m.first_name || ' ' || m.last_name) AS member_name,
                       s.end_date,
                       s.status
                FROM subscriptions s
                JOIN members m ON m.id = s.member_id
                JOIN subscription_types st ON st.id = s.subscription_type_id
                WHERE (m.first_name || ' ' || m.last_name) LIKE ?
                   OR st.name_ar LIKE ?
                   OR m.member_code LIKE ?
                ORDER BY date(s.end_date) DESC
                LIMIT 10
                """,
                (pattern, pattern, pattern),
            ).fetchall()

        out = []
        for r in rows:
            status_ar = {"active": "نشط", "expired": "منتهي", "frozen": "مجمد", "cancelled": "ملغي"}.get(str(r["status"]), "-")
            out.append({"id": int(r["id"]), "text": f"{r['plan_name']} - {r['member_name']} - ينتهي: {r['end_date']} ({status_ar})"})
        return out

    def search_payments(self, query: str) -> list[dict]:
        pattern = f"%{query}%"

        with self.db.get_connection() as conn:
            rows = conn.execute(
                """
                SELECT p.id,
                       p.amount,
                       p.payment_date,
                       p.payment_method,
                       p.receipt_number,
                       (m.first_name || ' ' || m.last_name) AS member_name
                FROM payments p
                JOIN members m ON m.id = p.member_id
                WHERE (m.first_name || ' ' || m.last_name) LIKE ?
                   OR COALESCE(p.receipt_number, '') LIKE ?
                   OR CAST(p.amount AS TEXT) LIKE ?
                ORDER BY date(p.payment_date) DESC, p.id DESC
                LIMIT 10
                """,
                (pattern, pattern, pattern),
            ).fetchall()

        out = []
        for r in rows:
            method_ar = config.PAYMENT_METHODS.get(str(r["payment_method"]), str(r["payment_method"]))
            out.append(
                {
                    "id": int(r["id"]),
                    "text": f"{format_money(float(r['amount'] or 0), db=self.db, decimals=0)} - {r['member_name']} - {r['payment_date']} - {method_ar}",
                }
            )
        return out

    def search_attendance(self, query: str) -> list[dict]:
        pattern = f"%{query}%"

        with self.db.get_connection() as conn:
            rows = conn.execute(
                """
                SELECT a.id,
                       (m.first_name || ' ' || m.last_name) AS member_name,
                       a.check_in,
                       a.check_out
                FROM attendance a
                JOIN members m ON m.id = a.member_id
                WHERE (m.first_name || ' ' || m.last_name) LIKE ?
                   OR m.member_code LIKE ?
                   OR m.phone LIKE ?
                ORDER BY datetime(a.check_in) DESC
                LIMIT 10
                """,
                (pattern, pattern, pattern),
            ).fetchall()

        out = []
        for r in rows:
            out.append({"id": int(r["id"]), "text": f"{r['member_name']} - دخول: {r['check_in']} - خروج: {r['check_out'] or '-'}"})
        return out

    # ------------------------------
    # Results rendering
    # ------------------------------

    def add_result_section(self, title: str, results: list[dict], result_type: str) -> None:
        tb.Label(
            self.results_frame,
            text=f"{title} ({len(results)} نتائج)",
            font=("Cairo", 12, "bold"),
            anchor="e",
        ).pack(fill="x", pady=(10, 5), anchor="e")

        for r in results:
            item_frame = self.create_result_item(r, result_type, len(self.all_results))
            item_frame.pack(fill="x", pady=2)
            self.all_results.append({"frame": item_frame, "data": r, "type": result_type})

    def create_result_item(self, data: dict, result_type: str, index: int) -> ttk.Frame:
        frame = tb.Frame(self.results_frame, padding=10, bootstyle="secondary")

        icon = "📋"
        if result_type == "member":
            icon = "👤"
        elif result_type == "subscription":
            icon = "📄"
        elif result_type == "payment":
            icon = "🧾"
        elif result_type == "attendance":
            icon = "📅"

        label = tb.Label(frame, text=f"{icon}  {data.get('text', '')}", font=FONTS["body"], anchor="e", justify="right")
        label.pack(fill="x")

        def on_click(_e, i=index):
            self.select_and_open(i)

        def on_enter(_e):
            try:
                frame.configure(bootstyle="info")
            except Exception:
                pass

        def on_leave(_e):
            if index == self.selected_index:
                return
            try:
                frame.configure(bootstyle="secondary")
            except Exception:
                pass

        for w in (frame, label):
            w.bind("<Button-1>", on_click)
            w.bind("<Enter>", on_enter)
            w.bind("<Leave>", on_leave)

        return frame

    def clear_results(self) -> None:
        for w in self.results_frame.winfo_children():
            w.destroy()
        self.all_results = []
        self.selected_index = 0

    # ------------------------------
    # Navigation
    # ------------------------------

    def select_and_open(self, index: int) -> None:
        self.selected_index = index
        self.open_selected()

    def navigate_up(self) -> None:
        if self.selected_index > 0:
            self.selected_index -= 1
            self.highlight_selected()

    def navigate_down(self) -> None:
        if self.selected_index < len(self.all_results) - 1:
            self.selected_index += 1
            self.highlight_selected()

    def highlight_selected(self) -> None:
        for i, item in enumerate(self.all_results):
            try:
                item["frame"].configure(bootstyle="primary" if i == self.selected_index else "secondary")
            except Exception:
                pass

        # Ensure visibility
        try:
            if self.all_results:
                frame = self.all_results[self.selected_index]["frame"]
                self.results_canvas.update_idletasks()
                y = frame.winfo_y()
                h = frame.winfo_height()
                canvas_h = self.results_canvas.winfo_height()

                # Scroll if out of view
                current = self.results_canvas.canvasy(0)
                if y < current:
                    self.results_canvas.yview_moveto(max(0, y) / max(1, self.results_frame.winfo_height()))
                elif y + h > current + canvas_h:
                    self.results_canvas.yview_moveto(max(0, y + h - canvas_h) / max(1, self.results_frame.winfo_height()))
        except Exception:
            pass

    def on_enter_pressed(self) -> None:
        self.open_selected()

    def open_selected(self) -> None:
        if not self.all_results:
            return

        selected = self.all_results[self.selected_index]
        typ = str(selected.get("type"))
        data = selected.get("data") or {}
        record_id = int(data.get("id"))

        self.destroy()

        if typ == "member" and callable(self.callbacks.get("open_member")):
            self.callbacks["open_member"](record_id)
        elif typ == "subscription" and callable(self.callbacks.get("open_subscription")):
            self.callbacks["open_subscription"](record_id)
        elif typ == "payment" and callable(self.callbacks.get("open_payment")):
            self.callbacks["open_payment"](record_id)
        elif typ == "attendance" and callable(self.callbacks.get("open_attendance")):
            self.callbacks["open_attendance"](record_id)


if __name__ == "__main__":
    root = tb.Window(themename="cosmo")
    root.withdraw()

    db = DatabaseManager()

    def _open(_id):
        print("Open:", _id)

    dlg = GlobalSearchDialog(
        root,
        db,
        {
            "open_member": _open,
            "open_subscription": _open,
            "open_payment": _open,
            "open_attendance": _open,
        },
    )
    dlg.mainloop()
