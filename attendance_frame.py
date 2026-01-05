from __future__ import annotations

import calendar
from datetime import date, datetime
import tkinter as tk
from tkinter import messagebox
from tkinter import ttk

import ttkbootstrap as tb
from ttkbootstrap.widgets import DateEntry as TbDateEntry

from database import DatabaseManager


DateEntry = TbDateEntry
_DATEENTRY_AVAILABLE = True


class AttendanceFrame(tb.Frame):
    def __init__(self, parent: ttk.Widget, db: DatabaseManager | None, user_data: dict) -> None:
        super().__init__(parent)
        self.db = db
        self.user_data = user_data or {}

        self.breakpoint: str = "desktop"
        self._rows: list[dict] = []

        self.query_var = tk.StringVar(master=self, value="")
        self.selected_member_id: int | None = None
        self.selected_member_label = tk.StringVar(master=self, value="—")

        self.date_filter_var = tk.StringVar(master=self, value=date.today().isoformat())

        self._search_results: list[dict] = []

        self.configure(padding=12)
        self._build_ui()

        self.refresh_today()
        self.refresh_month_stats()

    def on_breakpoint_change(self, breakpoint: str) -> None:
        self.breakpoint = breakpoint
        try:
            self._apply_responsive_layout()
        except Exception:
            pass
        self._render_cards()

    def _build_ui(self) -> None:
        header = tb.Frame(self)
        header.pack(fill="x", pady=(0, 10))

        tb.Label(header, text="الحضور", font=("Cairo", 16, "bold"), anchor="e").pack(side="right")

        container = tb.Frame(self)
        container.pack(fill="both", expand=True)
        self.container = container

        left = tb.Labelframe(container, text="تسجيل حضور/انصراف", padding=12)
        left.pack(side="right", fill="y", padx=(0, 10))
        self.left = left

        right = tb.Labelframe(container, text="السجل", padding=12)
        right.pack(side="left", fill="both", expand=True)
        self.right = right

        # Left: search + actions
        tb.Label(left, text="بحث عن عضو (الاسم / رقم العضوية / الهاتف)", anchor="e").pack(fill="x")

        search_row = tb.Frame(left)
        search_row.pack(fill="x", pady=(6, 10))

        tb.Entry(search_row, textvariable=self.query_var, justify="right").pack(side="right", fill="x", expand=True)
        tb.Button(search_row, text="بحث", bootstyle="secondary", command=self.search).pack(side="left", padx=(6, 0))

        self.results_list = tk.Listbox(left, height=10)
        self.results_list.pack(fill="x")
        self.results_list.bind("<<ListboxSelect>>", self._on_select_result)

        sel_box = tb.Frame(left)
        sel_box.pack(fill="x", pady=(10, 6))
        tb.Label(sel_box, text="المحدد:", anchor="e").pack(side="right")
        tb.Label(sel_box, textvariable=self.selected_member_label, anchor="e").pack(side="right", padx=(6, 0))

        btns = tb.Frame(left)
        btns.pack(fill="x", pady=(8, 0))

        tb.Button(btns, text="تسجيل دخول", bootstyle="success", command=self.check_in_selected).pack(
            fill="x", ipady=6, pady=(0, 6)
        )
        tb.Button(btns, text="تسجيل خروج", bootstyle="warning", command=self.check_out_selected).pack(fill="x", ipady=6)

        tb.Separator(left).pack(fill="x", pady=12)

        # Monthly stats
        self.month_total_var = tk.StringVar(master=self, value="-")
        self.month_unique_var = tk.StringVar(master=self, value="-")

        stats = tb.Labelframe(left, text="إحصائيات الشهر", padding=10)
        stats.pack(fill="x")

        r1 = tb.Frame(stats)
        r1.pack(fill="x", pady=3)
        tb.Label(r1, text="إجمالي الحضور:", anchor="e").pack(side="right")
        tb.Label(r1, textvariable=self.month_total_var, anchor="e").pack(side="left")

        r2 = tb.Frame(stats)
        r2.pack(fill="x", pady=3)
        tb.Label(r2, text="عدد الأعضاء الحاضرين:", anchor="e").pack(side="right")
        tb.Label(r2, textvariable=self.month_unique_var, anchor="e").pack(side="left")

        tb.Button(left, text="تحديث", bootstyle="secondary", command=self._refresh_all).pack(fill="x", ipady=6, pady=(10, 0))

        # Right: date filter + tree
        filter_row = tb.Frame(right)
        filter_row.pack(fill="x", pady=(0, 10))

        tb.Label(filter_row, text="التاريخ:", anchor="e").pack(side="right")

        self.date_entry = None
        if _DATEENTRY_AVAILABLE and DateEntry is not None:
            try:
                self.date_entry = DateEntry(filter_row, width=12, bootstyle="secondary", dateformat="%Y-%m-%d")
                self.date_entry.pack(side="right", padx=(6, 6))
                try:
                    self.date_entry.entry.configure(textvariable=self.date_filter_var)  # type: ignore[attr-defined]
                except Exception:
                    pass
                try:
                    self.date_entry.set_date(date.today())
                except Exception:
                    pass
            except Exception:
                self.date_entry = None

        if self.date_entry is None:
            self.date_entry = tb.Entry(filter_row, textvariable=self.date_filter_var, justify="center", width=14)
            self.date_entry.pack(side="right", padx=(6, 6))

        tb.Button(filter_row, text="عرض", bootstyle="primary", command=self.refresh_by_selected_date).pack(side="right")
        tb.Button(filter_row, text="اليوم", bootstyle="secondary", command=self.refresh_today).pack(side="right", padx=(6, 0))

        table_wrap = tb.Frame(right)
        table_wrap.pack(fill="both", expand=True)
        self.table_wrap = table_wrap

        cols = ("member_code", "name", "check_in", "check_out")
        self.tree = ttk.Treeview(table_wrap, columns=cols, show="headings")
        self.tree.heading("member_code", text="رقم العضوية")
        self.tree.heading("name", text="الاسم")
        self.tree.heading("check_in", text="الدخول")
        self.tree.heading("check_out", text="الخروج")

        self.tree.column("member_code", width=110, minwidth=110, anchor="center", stretch=False)
        self.tree.column("name", width=200, minwidth=200, anchor="e", stretch=False)
        self.tree.column("check_in", width=160, minwidth=160, anchor="center", stretch=False)
        self.tree.column("check_out", width=160, minwidth=160, anchor="center", stretch=False)

        self.tree_vsb = ttk.Scrollbar(table_wrap, orient="vertical", command=self.tree.yview)
        self.tree_hsb = ttk.Scrollbar(table_wrap, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=self.tree_vsb.set, xscrollcommand=self.tree_hsb.set)

        self.tree.pack(side="left", fill="both", expand=True)
        self.tree_vsb.pack(side="right", fill="y")
        self.tree_hsb.pack(side="bottom", fill="x")

        self.cards_canvas = tk.Canvas(table_wrap, highlightthickness=0)
        self.cards_vsb = ttk.Scrollbar(table_wrap, orient="vertical", command=self.cards_canvas.yview)
        self.cards_canvas.configure(yscrollcommand=self.cards_vsb.set)

        self.cards_inner = tb.Frame(self.cards_canvas)
        self.cards_window = self.cards_canvas.create_window((0, 0), window=self.cards_inner, anchor="nw")
        self.cards_inner.bind(
            "<Configure>",
            lambda _e: self.cards_canvas.configure(scrollregion=self.cards_canvas.bbox("all")),
        )
        self.cards_canvas.bind(
            "<Configure>",
            lambda e: self.cards_canvas.itemconfigure(self.cards_window, width=e.width),
        )

        self._apply_responsive_layout()

    def _apply_responsive_layout(self) -> None:
        if not hasattr(self, "left") or not hasattr(self, "right") or not hasattr(self, "tree"):
            return

        try:
            if self.breakpoint == "mobile":
                self.left.pack_forget()
                self.right.pack_forget()

                self.left.pack(side="top", fill="x", pady=(0, 10))
                self.right.pack(side="top", fill="both", expand=True)

                try:
                    self.tree.pack_forget()
                    self.tree_vsb.pack_forget()
                    self.tree_hsb.pack_forget()
                except Exception:
                    pass
                self.cards_canvas.pack(side="left", fill="both", expand=True)
                self.cards_vsb.pack(side="right", fill="y")
            else:
                self.left.pack_forget()
                self.right.pack_forget()

                self.left.pack(side="right", fill="y", padx=(0, 10))
                self.right.pack(side="left", fill="both", expand=True)

                try:
                    self.cards_canvas.pack_forget()
                    self.cards_vsb.pack_forget()
                except Exception:
                    pass
                self.tree.pack(side="left", fill="both", expand=True)
                self.tree_vsb.pack(side="right", fill="y")
                self.tree_hsb.pack(side="bottom", fill="x")
        except Exception:
            pass

    def _refresh_all(self) -> None:
        self.refresh_today()
        self.refresh_month_stats()

    def _normalize_dt(self, dt_str: str | None) -> str:
        if not dt_str:
            return "—"
        try:
            dt = datetime.fromisoformat(str(dt_str))
            return dt.strftime("%Y-%m-%d %H:%M")
        except Exception:
            return str(dt_str)

    def _on_select_result(self, _e=None) -> None:
        try:
            idxs = self.results_list.curselection()
            if not idxs:
                return
            idx = int(idxs[0])
            row = self._search_results[idx]
            self.selected_member_id = int(row.get("id"))
            name = f"{row.get('member_code','')} - {row.get('first_name','')} {row.get('last_name','')}".strip()
            self.selected_member_label.set(name)
        except Exception:
            self.selected_member_id = None
            self.selected_member_label.set("—")

    def search(self) -> None:
        if self.db is None:
            messagebox.showerror("خطأ", "قاعدة البيانات غير جاهزة")
            return

        q = (self.query_var.get() or "").strip()
        self.results_list.delete(0, tk.END)
        self._search_results = []
        self.selected_member_id = None
        self.selected_member_label.set("—")

        if not q:
            return

        try:
            rows = self.db.search_members(q)
            self._search_results = rows
            for r in rows:
                display = f"{r.get('member_code','')} | {r.get('first_name','')} {r.get('last_name','')} | {r.get('phone','')}"
                self.results_list.insert(tk.END, display)
            if not rows:
                self.results_list.insert(tk.END, "لا توجد نتائج")
        except Exception as e:
            messagebox.showerror("خطأ", f"فشل البحث: {e}")

    def check_in_selected(self) -> None:
        if self.db is None:
            messagebox.showerror("خطأ", "قاعدة البيانات غير جاهزة")
            return
        if self.selected_member_id is None:
            messagebox.showwarning("تنبيه", "يرجى اختيار عضو أولاً")
            return

        ok, msg = self.db.check_in(int(self.selected_member_id))
        if ok:
            messagebox.showinfo("نجاح", "تم تسجيل الدخول")
        else:
            messagebox.showwarning("تنبيه", msg)
        self.refresh_today()
        self.refresh_month_stats()

    def check_out_selected(self) -> None:
        if self.db is None:
            messagebox.showerror("خطأ", "قاعدة البيانات غير جاهزة")
            return
        if self.selected_member_id is None:
            messagebox.showwarning("تنبيه", "يرجى اختيار عضو أولاً")
            return

        ok, msg = self.db.check_out(int(self.selected_member_id))
        if ok:
            messagebox.showinfo("نجاح", "تم تسجيل الخروج")
        else:
            messagebox.showwarning("تنبيه", msg)
        self.refresh_today()
        self.refresh_month_stats()

    def _get_selected_date(self) -> str:
        if hasattr(self, "date_entry") and DateEntry is not None and isinstance(self.date_entry, DateEntry):
            try:
                d = self.date_entry.date
                if isinstance(d, date):
                    return d.isoformat()
                return str(d)
            except Exception:
                pass
        return (self.date_filter_var.get() or date.today().isoformat()).strip()

    def refresh_by_selected_date(self) -> None:
        self._fill_tree_for_date(self._get_selected_date())

    def refresh_today(self) -> None:
        today = date.today().isoformat()
        if hasattr(self, "date_entry") and DateEntry is not None and isinstance(self.date_entry, DateEntry):
            try:
                self.date_entry.set_date(date.today())
            except Exception:
                pass
        else:
            self.date_filter_var.set(today)
        self._fill_tree_for_date(today)

    def _fill_tree_for_date(self, date_str: str) -> None:
        for i in self.tree.get_children():
            self.tree.delete(i)

        if self.db is None:
            return

        rows: list[dict] = []
        try:
            rows = self.db.get_attendance_by_date(date_str)
            for r in rows:
                name = f"{r.get('first_name','')} {r.get('last_name','')}".strip()
                self.tree.insert(
                    "",
                    "end",
                    values=(
                        r.get("member_code", ""),
                        name,
                        self._normalize_dt(r.get("check_in")),
                        self._normalize_dt(r.get("check_out")),
                    ),
                )
            if not rows:
                self.tree.insert("", "end", values=("—", "لا توجد بيانات", "—", "—"))
        except Exception as e:
            self.tree.insert("", "end", values=("—", f"خطأ: {e}", "—", "—"))

        self._rows = rows
        self._render_cards()

    def _render_cards(self) -> None:
        if getattr(self, "breakpoint", "desktop") != "mobile":
            return
        if not hasattr(self, "cards_inner"):
            return

        for child in self.cards_inner.winfo_children():
            child.destroy()

        rows = getattr(self, "_rows", []) or []
        for r in rows:
            name = f"{r.get('first_name','')} {r.get('last_name','')}".strip() or "-"
            code = str(r.get("member_code") or "-")
            check_in = self._normalize_dt(r.get("check_in"))
            check_out = self._normalize_dt(r.get("check_out"))

            card = tb.Frame(self.cards_inner, padding=10, bootstyle="secondary")
            card.pack(fill="x", pady=6)

            top = tb.Frame(card)
            top.pack(fill="x")
            tb.Label(top, text=code, font=("Cairo", 11, "bold"), anchor="e").pack(side="right")
            tb.Label(top, text=name, font=("Cairo", 11, "bold"), anchor="e").pack(side="right", padx=(6, 0))

            tb.Label(card, text=f"الدخول: {check_in}", anchor="e").pack(fill="x", pady=(6, 0))
            tb.Label(card, text=f"الخروج: {check_out}", anchor="e").pack(fill="x")

    def refresh_month_stats(self) -> None:
        if self.db is None:
            self.month_total_var.set("-")
            self.month_unique_var.set("-")
            return

        today = date.today()
        start = today.replace(day=1).isoformat()
        last_day = calendar.monthrange(today.year, today.month)[1]
        end = today.replace(day=last_day).isoformat()

        try:
            with self.db.get_connection() as conn:
                total = conn.execute(
                    "SELECT COUNT(*) AS c FROM attendance WHERE date(check_in) BETWEEN date(?) AND date(?)",
                    (start, end),
                ).fetchone()["c"]
                uniq = conn.execute(
                    "SELECT COUNT(DISTINCT member_id) AS c FROM attendance WHERE date(check_in) BETWEEN date(?) AND date(?)",
                    (start, end),
                ).fetchone()["c"]

            self.month_total_var.set(str(int(total)))
            self.month_unique_var.set(str(int(uniq)))
        except Exception:
            self.month_total_var.set("-")
            self.month_unique_var.set("-")
