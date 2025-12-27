"""Comprehensive reporting module for Gym Management System.

This module provides a multi-report UI with charts, tables, and export capabilities.

It is designed to work with the current database schema from database.py:
- members
- subscriptions (with subscription_types)
- payments
- attendance
- expenses

PDF export uses reportlab if installed (optional).
"""

from __future__ import annotations

import csv
import html as html_lib
import os
import tkinter as tk
from datetime import date, datetime, timedelta
from pathlib import Path
from tkinter import filedialog, messagebox
from tkinter import ttk
from typing import Any

import ttkbootstrap as tb
from ttkbootstrap.constants import *  # noqa: F403
from ttkbootstrap.widgets import DateEntry, Meter

import config
from database import DatabaseManager
from utils import format_money, print_html_windows, print_text_windows

# Local styling fallback (some modules store COLORS/FONTS locally)
COLORS = {
    "primary": "#2563eb",
    "primary_dark": "#1e40af",
    "secondary": "#64748b",
    "success": "#059669",
    "warning": "#d97706",
    "danger": "#dc2626",
    "background": "#f1f5f9",
    "text": "#1e293b",
    "text_light": "#64748b",
    "white": "#ffffff",
}

FONTS = {
    "heading": ("Cairo", 18, "bold"),
    "subheading": ("Cairo", 14, "bold"),
    "body": ("Cairo", 12),
    "small": ("Cairo", 10),
}


# Matplotlib (required in prompt, but still guarded for friendliness)
try:
    import matplotlib.pyplot as plt
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
    from matplotlib.figure import Figure

    MATPLOTLIB_AVAILABLE = True
except Exception:
    plt = None  # type: ignore
    FigureCanvasTkAgg = None  # type: ignore
    Figure = None  # type: ignore
    MATPLOTLIB_AVAILABLE = False

# pandas / openpyxl (required in prompt, but guarded)
try:
    import pandas as pd

    PANDAS_AVAILABLE = True
except Exception:
    pd = None  # type: ignore
    PANDAS_AVAILABLE = False

try:
    import openpyxl  # type: ignore

    OPENPYXL_AVAILABLE = True
except Exception:
    openpyxl = None  # type: ignore
    OPENPYXL_AVAILABLE = False

# reportlab (optional)
try:
    from reportlab.lib import colors as rl_colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import SimpleDocTemplate, Spacer, Table, TableStyle, Paragraph

    REPORTLAB_AVAILABLE = True
except Exception:
    REPORTLAB_AVAILABLE = False


REPORT_CATEGORIES: dict[str, dict[str, Any]] = {
    "members": {
        "title": "👥 تقارير الأعضاء",
        "reports": {
            "total_members": "إجمالي الأعضاء",
            "new_members": "الأعضاء الجدد",
            "expired_members": "الاشتراكات المنتهية",
            "expiring_soon": "تنتهي قريباً",
            "members_by_gender": "حسب الجنس",
            "inactive_members": "الأعضاء غير النشطين",
        },
    },
    "financial": {
        "title": "💰 التقارير المالية",
        "reports": {
            "revenue": "الإيرادات",
            "daily_revenue": "الإيرادات اليومية",
            "monthly_revenue": "الإيرادات الشهرية",
            "revenue_by_plan": "الإيرادات حسب الباقة",
            "payment_methods": "طرق الدفع",
        },
    },
    "attendance": {
        "title": "📅 تقارير الحضور",
        "reports": {
            "daily_attendance": "الحضور اليومي",
            "monthly_attendance": "الحضور الشهري",
            "peak_hours": "أوقات الذروة",
        },
    },
    "plans": {
        "title": "📦 تقارير الباقات",
        "reports": {
            "plan_distribution": "توزيع الباقات",
            "plan_performance": "أداء الباقات",
        },
    },
    "custom": {
        "title": "📈 تقارير مخصصة",
        "reports": {
            "custom_query": "استعلام مخصص",
        },
    },
}


def _fmt_money(amount: float, db: DatabaseManager | None = None) -> str:
    return format_money(amount, db=db, decimals=0)


class ReportsFrame(tb.Frame):
    """Reporting module with charts, tables, and exports."""

    def __init__(self, parent: ttk.Widget, db: DatabaseManager | None, user_data: dict | None = None) -> None:
        super().__init__(parent)
        self.db = db
        self.user_data = user_data or {}

        self.current_report_type: str | None = None
        self.current_report_title: str = ""
        self.current_data: list[list[Any]] = []
        self.current_columns: list[str] = []
        self.current_summary: str = ""
        self.current_report_meta: dict[str, Any] = {}
        self.charts: list[Any] = []

        self.configure(padding=10)

        self.setup_ui()
        self._bind_shortcuts()

        # Default report
        self.display_report("total_members")

        self._member_report_types: set[str] = {
            "total_members",
            "new_members",
            "expired_members",
            "expiring_soon",
            "members_by_gender",
            "inactive_members",
        }

        self._financial_report_types: set[str] = {
            "revenue",
            "daily_revenue",
            "monthly_revenue",
            "revenue_by_plan",
            "payment_methods",
        }

        self._other_unified_report_types: set[str] = {
            "daily_attendance",
            "monthly_attendance",
            "peak_hours",
            "plan_distribution",
            "plan_performance",
            "custom_query",
        }

    # ------------------------------
    # UI
    # ------------------------------

    def setup_ui(self) -> None:
        self.create_header()
        self.create_main_content()
        self.create_date_selector()

    def create_header(self) -> None:
        header = tb.Frame(self)
        header.pack(fill="x", pady=(0, 10))

        tb.Label(header, text="📊 التقارير والإحصائيات", font=FONTS["heading"], anchor="e").pack(side="right")

        btns = tb.Frame(header)
        btns.pack(side="left")

        tb.Button(btns, text="🔄", bootstyle="secondary", command=self.refresh_report).pack(side="left", padx=6)
        tb.Button(btns, text="📥 تصدير", bootstyle="info", command=self.show_export_dialog).pack(side="left", padx=6)
        self.btn_print = tb.Button(btns, text="🖨️ طباعة", bootstyle="secondary", command=self.print_report)
        self.btn_print.pack(side="left")

    def create_main_content(self) -> None:
        main = tb.Frame(self)
        main.pack(fill="both", expand=True)

        # Left panel: tree
        left = tb.Frame(main, width=260)
        left.pack(side="right", fill="y", padx=(0, 10))
        left.pack_propagate(False)

        tb.Label(left, text="📁 أنواع التقارير", font=FONTS["subheading"], anchor="e").pack(anchor="e", pady=6)

        self.categories_tree = ttk.Treeview(left, show="tree")
        self.categories_tree.pack(fill="both", expand=True)

        for cat_id, cat_info in REPORT_CATEGORIES.items():
            cat_node = self.categories_tree.insert("", "end", iid=cat_id, text=cat_info["title"], open=True)
            for report_id, report_name in cat_info["reports"].items():
                self.categories_tree.insert(cat_node, "end", iid=report_id, text=report_name)

        self.categories_tree.bind("<<TreeviewSelect>>", self.on_report_select)

        # Right panel: content
        self.report_content_frame = tb.Frame(main)
        self.report_content_frame.pack(side="left", fill="both", expand=True)

        # Sections inside content
        self.chart_frame = tb.Labelframe(self.report_content_frame, text="📈 الرسم البياني", padding=10)
        self.chart_frame.pack(fill="both", expand=True)

        self.table_frame = tb.Labelframe(self.report_content_frame, text="📋 بيانات التقرير", padding=10)
        self.table_frame.pack(fill="both", expand=True, pady=10)

        self.summary_frame = tb.Labelframe(self.report_content_frame, text="📌 ملخص التقرير", padding=10)
        self.summary_frame.pack(fill="x")

        self.summary_label = tb.Label(self.summary_frame, text="-", font=FONTS["small"], anchor="e", justify="right")
        self.summary_label.pack(fill="x")

    def create_date_selector(self) -> None:
        bar = tb.Frame(self)
        bar.pack(fill="x", pady=(10, 0))

        tb.Label(bar, text="📅 الفترة:", font=("Cairo", 10, "bold"), anchor="e").pack(side="right", padx=(0, 8))

        tb.Label(bar, text="من:", font=FONTS["small"], anchor="e").pack(side="right")
        self.start_date_entry = DateEntry(bar, bootstyle="info", width=12)
        self.start_date_entry.pack(side="right", padx=(6, 14))

        tb.Label(bar, text="إلى:", font=FONTS["small"], anchor="e").pack(side="right")
        self.end_date_entry = DateEntry(bar, bootstyle="info", width=12)
        self.end_date_entry.pack(side="right", padx=(6, 14))

        quick = tb.Frame(bar)
        quick.pack(side="right")

        for label, kind in [
            ("اليوم", "today"),
            ("أمس", "yesterday"),
            ("هذا الأسبوع", "week"),
            ("الأسبوع الماضي", "last_week"),
            ("هذا الشهر", "month"),
            ("الشهر الماضي", "last_month"),
            ("هذه السنة", "year"),
        ]:
            tb.Button(quick, text=label, bootstyle="secondary", command=lambda k=kind: self.set_quick_date_range(k)).pack(
                side="left", padx=2
            )

        tb.Frame(bar).pack(side="right", fill="x", expand=True)

        tb.Button(bar, text="🔍 عرض التقرير", bootstyle="success", command=self.refresh_report).pack(side="left", padx=10)

        # Default range: this month
        self.set_quick_date_range("month")

    # ------------------------------
    # Events
    # ------------------------------

    def on_report_select(self, _event) -> None:
        selection = self.categories_tree.selection()
        if not selection:
            return

        report_id = selection[0]
        if report_id in REPORT_CATEGORIES:
            return

        self.display_report(report_id)

    def refresh_report(self) -> None:
        if self.current_report_type:
            self.display_report(self.current_report_type)

    def set_quick_date_range(self, kind: str) -> None:
        today = date.today()

        if kind == "today":
            start = end = today
        elif kind == "yesterday":
            start = end = today - timedelta(days=1)
        elif kind == "week":
            start = today - timedelta(days=today.weekday())
            end = today
        elif kind == "last_week":
            end = today - timedelta(days=today.weekday() + 1)
            start = end - timedelta(days=6)
        elif kind == "month":
            start = today.replace(day=1)
            end = today
        elif kind == "last_month":
            first_this = today.replace(day=1)
            end = first_this - timedelta(days=1)
            start = end.replace(day=1)
        elif kind == "year":
            start = date(today.year, 1, 1)
            end = today
        else:
            start = today.replace(day=1)
            end = today

        try:
            self.start_date_entry.date = start
            self.end_date_entry.date = end
        except Exception:
            pass

    def _get_date_range(self) -> tuple[str, str]:
        try:
            sd = self.start_date_entry.date
            ed = self.end_date_entry.date
            if isinstance(sd, date) and isinstance(ed, date):
                return sd.isoformat(), ed.isoformat()
        except Exception:
            pass

        # Fallback to entry strings
        start = self.start_date_entry.entry.get().strip()[:10]
        end = self.end_date_entry.entry.get().strip()[:10]
        return start, end

    # ------------------------------
    # Report dispatch
    # ------------------------------

    def display_report(self, report_type: str) -> None:
        self.current_report_type = report_type
        self.current_report_meta = {}

        # Clear previous
        for w in self.chart_frame.winfo_children():
            w.destroy()
        for w in self.table_frame.winfo_children():
            w.destroy()
        self.charts.clear()

        start_date, end_date = self._get_date_range()

        dispatch = {
            "total_members": self.display_total_members_report,
            "new_members": self.display_new_members_report,
            "expired_members": self.display_expired_members_report,
            "expiring_soon": self.display_expiring_soon_report,
            "members_by_gender": self.display_members_by_gender_report,
            "inactive_members": self.display_inactive_members_report,
            "revenue": self.display_revenue_report,
            "daily_revenue": self.display_daily_revenue_report,
            "monthly_revenue": self.display_monthly_revenue_report,
            "revenue_by_plan": self.display_revenue_by_plan_report,
            "payment_methods": self.display_payment_methods_report,
            "daily_attendance": self.display_daily_attendance_report,
            "monthly_attendance": self.display_monthly_attendance_report,
            "peak_hours": self.display_peak_hours_report,
            "plan_distribution": self.display_plan_distribution_report,
            "plan_performance": self.display_plan_performance_report,
            "custom_query": self.display_custom_query,
        }

        fn = dispatch.get(report_type)
        if fn is None:
            self._set_summary("التقرير غير متاح حالياً")
            tb.Label(self.chart_frame, text="التقرير غير متاح حالياً", font=FONTS["subheading"]).pack(pady=40)
            return

        fn(start_date, end_date)

    # ------------------------------
    # Report implementations
    # ------------------------------

    def display_total_members_report(self, start_date: str, end_date: str) -> None:
        self.current_report_title = "تقرير إجمالي الأعضاء"

        if self.db is None:
            self._no_db()
            return

        with self.db.get_connection() as conn:
            cur = conn.cursor()
            total = cur.execute("SELECT COUNT(*) AS c FROM members").fetchone()["c"]
            active = cur.execute("SELECT COUNT(*) AS c FROM members WHERE status = 'active'").fetchone()["c"]
            inactive = cur.execute("SELECT COUNT(*) AS c FROM members WHERE status = 'inactive'").fetchone()["c"]
            frozen = cur.execute("SELECT COUNT(*) AS c FROM members WHERE status = 'frozen'").fetchone()["c"]

            new_in_range = cur.execute(
                """
                SELECT COUNT(*) AS c
                FROM members
                WHERE date(join_date) BETWEEN date(?) AND date(?)
                """,
                (start_date, end_date),
            ).fetchone()["c"]

            # Growth series by day (based on join_date)
            growth = cur.execute(
                """
                SELECT date(join_date) AS d, COUNT(*) AS c
                FROM members
                WHERE date(join_date) BETWEEN date(?) AND date(?)
                GROUP BY date(join_date)
                ORDER BY date(join_date) ASC
                """,
                (start_date, end_date),
            ).fetchall()

            # Table details
            rows = cur.execute(
                """
                SELECT m.member_code,
                       (m.first_name || ' ' || m.last_name) AS name,
                       m.phone,
                       m.status,
                       m.join_date
                FROM members m
                WHERE date(m.join_date) BETWEEN date(?) AND date(?)
                ORDER BY date(m.join_date) DESC
                LIMIT 500
                """,
                (start_date, end_date),
            ).fetchall()

        # Chart
        if MATPLOTLIB_AVAILABLE:
            data = [(r["d"], int(r["c"])) for r in growth]
            self.create_line_chart(self.chart_frame, data, "نمو الأعضاء خلال الفترة", "التاريخ", "عدد المسجلين")
        else:
            tb.Label(self.chart_frame, text="matplotlib غير متاح لعرض الرسوم البيانية", font=FONTS["small"]).pack(pady=30)

        # Table
        columns = ["#", "الاسم", "الهاتف", "الحالة", "تاريخ التسجيل"]
        data_table = []
        for i, r in enumerate(rows, start=1):
            status_ar = {"active": "نشط", "inactive": "غير نشط", "frozen": "مجمد"}.get(str(r["status"]), str(r["status"]))
            data_table.append([i, r["name"], r["phone"], status_ar, r["join_date"]])

        self.current_columns = columns
        self.current_data = data_table
        self.current_report_meta = {
            "start_date": start_date,
            "end_date": end_date,
            "stats": {
                "total": int(total or 0),
                "active": int(active or 0),
                "inactive": int((inactive or 0) + (frozen or 0)),
                "new_members": int(new_in_range or 0),
                "deleted": 0,
            },
            "stats_items": [
                {"label": "إجمالي", "value": int(total or 0), "variant": "secondary"},
                {"label": "نشط", "value": int(active or 0), "variant": "success"},
                {"label": "غير نشط", "value": int(inactive or 0), "variant": "danger"},
                {"label": "مجمد", "value": int(frozen or 0), "variant": "info"},
                {"label": "جدد في الفترة", "value": int(new_in_range or 0), "variant": "primary"},
            ],
        }

        self.create_data_table(self.table_frame, data_table, columns)

        self._set_summary(
            f"الفترة: {start_date} إلى {end_date} | إجمالي: {int(total)} | نشط: {int(active)} | غير نشط: {int(inactive)} | مجمد: {int(frozen)} | جدد في الفترة: {int(new_in_range)}"
        )

    def display_new_members_report(self, start_date: str, end_date: str) -> None:
        self.current_report_title = "تقرير الأعضاء الجدد"

        if self.db is None:
            self._no_db()
            return

        with self.db.get_connection() as conn:
            rows = conn.execute(
                """
                SELECT m.member_code,
                       (m.first_name || ' ' || m.last_name) AS name,
                       m.phone,
                       m.gender,
                       m.join_date
                FROM members m
                WHERE date(m.join_date) BETWEEN date(?) AND date(?)
                ORDER BY date(m.join_date) DESC
                LIMIT 1000
                """,
                (start_date, end_date),
            ).fetchall()

        columns = ["رقم العضوية", "الاسم", "الهاتف", "الجنس", "تاريخ التسجيل"]

        data_table: list[list[Any]] = []
        for r in rows:
            gender_ar = {"male": "ذكر", "female": "أنثى"}.get(str(r["gender"]), "-")
            data_table.append([r["member_code"], r["name"], r["phone"], gender_ar, r["join_date"]])

        self.current_columns = columns
        self.current_data = data_table
        self.create_data_table(self.table_frame, data_table, columns)

        self.current_report_meta = {
            "start_date": start_date,
            "end_date": end_date,
            "stats_items": [
                {"label": "أعضاء جدد", "value": len(data_table), "variant": "primary"},
            ],
        }

        # Chart: count by day
        if MATPLOTLIB_AVAILABLE:
            with self.db.get_connection() as conn:
                series = conn.execute(
                    """
                    SELECT date(join_date) AS d, COUNT(*) AS c
                    FROM members
                    WHERE date(join_date) BETWEEN date(?) AND date(?)
                    GROUP BY date(join_date)
                    ORDER BY date(join_date) ASC
                    """,
                    (start_date, end_date),
                ).fetchall()
            self.create_bar_chart(
                self.chart_frame,
                [(r["d"], int(r["c"])) for r in series],
                "الأعضاء الجدد حسب اليوم",
                "اليوم",
                "العدد",
            )
        else:
            tb.Label(self.chart_frame, text="matplotlib غير متاح", font=FONTS["small"]).pack(pady=30)

        self._set_summary(f"الفترة: {start_date} إلى {end_date} | عدد الأعضاء الجدد: {len(data_table)}")

    def display_inactive_members_report(self, start_date: str, end_date: str) -> None:
        self.current_report_title = "تقرير الأعضاء غير النشطين"

        if self.db is None:
            self._no_db()
            return

        with self.db.get_connection() as conn:
            rows = conn.execute(
                """
                SELECT member_code,
                       (first_name || ' ' || last_name) AS name,
                       phone,
                       status,
                       join_date
                FROM members
                WHERE status != 'active'
                ORDER BY date(join_date) DESC
                LIMIT 1000
                """
            ).fetchall()

        columns = ["رقم العضوية", "الاسم", "الهاتف", "الحالة", "تاريخ التسجيل"]
        data_table: list[list[Any]] = []
        for r in rows:
            status_ar = {"inactive": "غير نشط", "frozen": "مجمد"}.get(str(r["status"]), str(r["status"]))
            data_table.append([r["member_code"], r["name"], r["phone"], status_ar, r["join_date"]])

        self.current_columns = columns
        self.current_data = data_table
        self.create_data_table(self.table_frame, data_table, columns)

        inactive_count = 0
        frozen_count = 0
        try:
            for r in rows:
                s = str(r["status"])
                if s == "inactive":
                    inactive_count += 1
                elif s == "frozen":
                    frozen_count += 1
        except Exception:
            pass

        self.current_report_meta = {
            "start_date": start_date,
            "end_date": end_date,
            "stats_items": [
                {"label": "إجمالي", "value": len(data_table), "variant": "secondary"},
                {"label": "غير نشط", "value": inactive_count, "variant": "danger"},
                {"label": "مجمد", "value": frozen_count, "variant": "info"},
            ],
        }

        if MATPLOTLIB_AVAILABLE:
            counts = {}
            for r in rows:
                counts[str(r["status"])] = counts.get(str(r["status"]), 0) + 1
            mapped = []
            for k, v in counts.items():
                mapped.append(({"inactive": "غير نشط", "frozen": "مجمد"}.get(k, k), v))
            self.create_pie_chart(self.chart_frame, mapped, "توزيع حالات الأعضاء غير النشطين")
        else:
            tb.Label(self.chart_frame, text="matplotlib غير متاح", font=FONTS["small"]).pack(pady=30)

        self._set_summary(f"عدد الأعضاء غير النشطين: {len(data_table)}")

    def display_members_by_gender_report(self, start_date: str, end_date: str) -> None:
        self.current_report_title = "تقرير الأعضاء حسب الجنس"

        if self.db is None:
            self._no_db()
            return

        with self.db.get_connection() as conn:
            rows = conn.execute(
                """
                SELECT gender, COUNT(*) AS c
                FROM members
                GROUP BY gender
                """
            ).fetchall()

        data = []
        for r in rows:
            g = str(r["gender"] or "")
            label = {"male": "ذكر", "female": "أنثى"}.get(g, "غير محدد")
            data.append([label, int(r["c"])])

        self.current_columns = ["الجنس", "العدد"]
        self.current_data = data
        self.create_data_table(self.table_frame, data, self.current_columns)

        male = 0
        female = 0
        unknown = 0
        total = 0
        for label, c in data:
            n = int(c or 0)
            total += n
            if label == "ذكر":
                male = n
            elif label == "أنثى":
                female = n
            else:
                unknown += n

        self.current_report_meta = {
            "start_date": "",
            "end_date": "",
            "stats_items": [
                {"label": "إجمالي", "value": total, "variant": "secondary"},
                {"label": "ذكور", "value": male, "variant": "primary"},
                {"label": "إناث", "value": female, "variant": "info"},
                {"label": "غير محدد", "value": unknown, "variant": "warning"},
            ],
        }

        if MATPLOTLIB_AVAILABLE:
            self.create_pie_chart(self.chart_frame, [(r[0], r[1]) for r in data], "توزيع الأعضاء حسب الجنس")
        else:
            tb.Label(self.chart_frame, text="matplotlib غير متاح", font=FONTS["small"]).pack(pady=30)

        self._set_summary("توزيع الأعضاء حسب الجنس")

    def display_expiring_soon_report(self, start_date: str, end_date: str) -> None:
        self.current_report_title = "تقرير الاشتراكات التي تنتهي قريباً"

        if self.db is None:
            self._no_db()
            return

        # Here, start/end are used as report range. We also provide a quick expiring window (next 7 days) chart.
        with self.db.get_connection() as conn:
            rows = conn.execute(
                """
                SELECT s.id AS subscription_id,
                       m.member_code,
                       (m.first_name || ' ' || m.last_name) AS name,
                       m.phone,
                       st.name_ar AS plan_name,
                       s.end_date,
                       s.status
                FROM subscriptions s
                JOIN members m ON m.id = s.member_id
                JOIN subscription_types st ON st.id = s.subscription_type_id
                WHERE s.status = 'active'
                  AND date(s.end_date) BETWEEN date(?) AND date(?)
                ORDER BY date(s.end_date) ASC
                """,
                (start_date, end_date),
            ).fetchall()

        columns = ["رقم الاشتراك", "رقم العضوية", "الاسم", "الهاتف", "الباقة", "تاريخ الانتهاء"]
        data_table: list[list[Any]] = []
        for r in rows:
            data_table.append([r["subscription_id"], r["member_code"], r["name"], r["phone"], r["plan_name"], r["end_date"]])

        self.current_columns = columns
        self.current_data = data_table
        self.create_data_table(self.table_frame, data_table, columns)

        self.current_report_meta = {
            "start_date": start_date,
            "end_date": end_date,
            "stats_items": [
                {"label": "عدد الاشتراكات", "value": len(data_table), "variant": "primary"},
            ],
        }

        if MATPLOTLIB_AVAILABLE:
            # Count expiring by day
            counts = {}
            for r in rows:
                d = str(r["end_date"])
                counts[d] = counts.get(d, 0) + 1
            series = sorted(counts.items(), key=lambda x: x[0])
            self.create_bar_chart(self.chart_frame, [(d, c) for d, c in series], "الاشتراكات حسب تاريخ الانتهاء", "التاريخ", "العدد")
        else:
            tb.Label(self.chart_frame, text="matplotlib غير متاح", font=FONTS["small"]).pack(pady=30)

        self._set_summary(f"الفترة: {start_date} إلى {end_date} | عدد الاشتراكات: {len(data_table)}")

    def display_expired_members_report(self, start_date: str, end_date: str) -> None:
        self.current_report_title = "تقرير الاشتراكات المنتهية"

        if self.db is None:
            self._no_db()
            return

        with self.db.get_connection() as conn:
            rows = conn.execute(
                """
                SELECT s.id AS subscription_id,
                       m.member_code,
                       (m.first_name || ' ' || m.last_name) AS name,
                       m.phone,
                       st.name_ar AS plan_name,
                       s.end_date
                FROM subscriptions s
                JOIN members m ON m.id = s.member_id
                JOIN subscription_types st ON st.id = s.subscription_type_id
                WHERE date(s.end_date) < date('now')
                ORDER BY date(s.end_date) DESC
                LIMIT 1000
                """
            ).fetchall()

        columns = ["رقم الاشتراك", "رقم العضوية", "الاسم", "الهاتف", "الباقة", "تاريخ الانتهاء"]
        data_table = [[r["subscription_id"], r["member_code"], r["name"], r["phone"], r["plan_name"], r["end_date"]] for r in rows]

        self.current_columns = columns
        self.current_data = data_table
        self.create_data_table(self.table_frame, data_table, columns)

        self.current_report_meta = {
            "start_date": "",
            "end_date": "",
            "stats_items": [
                {"label": "اشتراكات منتهية", "value": len(data_table), "variant": "danger"},
            ],
        }

        if MATPLOTLIB_AVAILABLE:
            # Expired by plan
            with self.db.get_connection() as conn:
                dist = conn.execute(
                    """
                    SELECT st.name_ar AS plan, COUNT(*) AS c
                    FROM subscriptions s
                    JOIN subscription_types st ON st.id = s.subscription_type_id
                    WHERE date(s.end_date) < date('now')
                    GROUP BY st.id
                    ORDER BY c DESC
                    """
                ).fetchall()
            self.create_horizontal_bar_chart(self.chart_frame, [(r["plan"], int(r["c"])) for r in dist], "الاشتراكات المنتهية حسب الباقة")
        else:
            tb.Label(self.chart_frame, text="matplotlib غير متاح", font=FONTS["small"]).pack(pady=30)

        self._set_summary(f"عدد الاشتراكات المنتهية: {len(data_table)}")

    def display_revenue_report(self, start_date: str, end_date: str) -> None:
        self.current_report_title = "تقرير الإيرادات"

        if self.db is None:
            self._no_db()
            return

        with self.db.get_connection() as conn:
            rows = conn.execute(
                """
                SELECT date(payment_date) AS d, COALESCE(SUM(amount), 0) AS total, COUNT(*) AS c
                FROM payments
                WHERE date(payment_date) BETWEEN date(?) AND date(?)
                GROUP BY date(payment_date)
                ORDER BY date(payment_date) ASC
                """,
                (start_date, end_date),
            ).fetchall()

            total = conn.execute(
                """
                SELECT COALESCE(SUM(amount), 0) AS total
                FROM payments
                WHERE date(payment_date) BETWEEN date(?) AND date(?)
                """,
                (start_date, end_date),
            ).fetchone()["total"]

            methods = conn.execute(
                """
                SELECT payment_method, COALESCE(SUM(amount), 0) AS total
                FROM payments
                WHERE date(payment_date) BETWEEN date(?) AND date(?)
                GROUP BY payment_method
                ORDER BY total DESC
                """,
                (start_date, end_date),
            ).fetchall()

            # Details table
            details = conn.execute(
                """
                SELECT p.receipt_number,
                       date(p.payment_date) AS d,
                       time(p.payment_date) AS t,
                       (m.first_name || ' ' || m.last_name) AS member,
                       st.name_ar AS plan,
                       p.amount,
                       p.payment_method
                FROM payments p
                JOIN members m ON m.id = p.member_id
                LEFT JOIN subscriptions s ON s.id = p.subscription_id
                LEFT JOIN subscription_types st ON st.id = s.subscription_type_id
                WHERE date(p.payment_date) BETWEEN date(?) AND date(?)
                ORDER BY datetime(p.payment_date) DESC
                LIMIT 1000
                """,
                (start_date, end_date),
            ).fetchall()

        # Chart
        if MATPLOTLIB_AVAILABLE:
            self.create_bar_chart(self.chart_frame, [(r["d"], float(r["total"])) for r in rows], "الإيرادات اليومية", "اليوم", "الإيراد")
        else:
            tb.Label(self.chart_frame, text="matplotlib غير متاح", font=FONTS["small"]).pack(pady=30)

        total_amount = float(total or 0)
        tx_count = int(len(details))
        avg_amount = (total_amount / tx_count) if tx_count else 0.0

        self.current_report_meta = {
            "start_date": start_date,
            "end_date": end_date,
            "stats_items": [
                {"label": "إجمالي الإيرادات", "value": _fmt_money(total_amount, db=self.db), "variant": "success"},
                {"label": "عدد العمليات", "value": tx_count, "variant": "secondary"},
                {"label": "متوسط العملية", "value": _fmt_money(avg_amount, db=self.db), "variant": "primary"},
            ],
        }

        # Table (per requested format)
        columns = ["التاريخ", "الوصف", "طريقة الدفع", "المبلغ"]
        data_table: list[list[Any]] = []
        for r in details:
            method_ar = config.PAYMENT_METHODS.get(str(r["payment_method"]), str(r["payment_method"]))
            d = str(r["d"] or "")
            plan = str(r["plan"] or "").strip()
            member = str(r["member"] or "").strip()
            desc = (f"اشتراك: {plan} - {member}" if plan else f"عملية مالية - {member}")
            data_table.append([d, desc, method_ar, _fmt_money(float(r["amount"] or 0), db=self.db)])

        self.current_columns = columns
        self.current_data = data_table
        self.create_data_table(self.table_frame, data_table, columns)

        methods_summary = " | ".join([f"{config.PAYMENT_METHODS.get(str(m['payment_method']), m['payment_method'])}: {_fmt_money(float(m['total']), db=self.db)}" for m in methods])
        self._set_summary(f"الفترة: {start_date} إلى {end_date} | إجمالي الإيرادات: {_fmt_money(float(total), db=self.db)} | {methods_summary}")

    def display_daily_revenue_report(self, start_date: str, end_date: str) -> None:
        self.current_report_title = "تقرير الإيرادات اليومية"

        if self.db is None:
            self._no_db()
            return

        with self.db.get_connection() as conn:
            details = conn.execute(
                """
                SELECT date(p.payment_date) AS d,
                       time(p.payment_date) AS t,
                       (m.first_name || ' ' || m.last_name) AS member,
                       CASE WHEN p.subscription_id IS NOT NULL THEN 'اشتراك' ELSE 'عملية مالية' END AS op_type,
                       p.amount,
                       p.payment_method
                FROM payments p
                JOIN members m ON m.id = p.member_id
                WHERE date(p.payment_date) BETWEEN date(?) AND date(?)
                ORDER BY datetime(p.payment_date) DESC
                LIMIT 1000
                """,
                (start_date, end_date),
            ).fetchall()

            methods = conn.execute(
                """
                SELECT payment_method, COALESCE(SUM(amount), 0) AS total
                FROM payments
                WHERE date(payment_date) BETWEEN date(?) AND date(?)
                GROUP BY payment_method
                ORDER BY total DESC
                """,
                (start_date, end_date),
            ).fetchall()

        total_amount = 0.0
        max_amount = 0.0
        for r in details:
            a = float(r["amount"] or 0)
            total_amount += a
            if a > max_amount:
                max_amount = a

        tx_count = int(len(details))

        self.current_report_meta = {
            "start_date": start_date,
            "end_date": end_date,
            "stats_items": [
                {"label": "إيرادات اليوم", "value": _fmt_money(total_amount, db=self.db), "variant": "success"},
                {"label": "عدد العمليات", "value": tx_count, "variant": "secondary"},
                {"label": "أعلى عملية", "value": _fmt_money(max_amount, db=self.db), "variant": "primary"},
            ],
        }

        if MATPLOTLIB_AVAILABLE:
            pie_data = [(config.PAYMENT_METHODS.get(str(r["payment_method"]), str(r["payment_method"])), float(r["total"])) for r in methods]
            self.create_pie_chart(self.chart_frame, pie_data, "توزيع الإيرادات حسب طريقة الدفع")
        else:
            tb.Label(self.chart_frame, text="matplotlib غير متاح", font=FONTS["small"]).pack(pady=30)

        columns = ["الوقت", "اسم العضو", "نوع العملية", "طريقة الدفع", "المبلغ"]
        data_table: list[list[Any]] = []
        for r in details:
            t = str(r["t"] or "").strip() or "-"
            member = str(r["member"] or "-")
            op_type = str(r["op_type"] or "-")
            method_ar = config.PAYMENT_METHODS.get(str(r["payment_method"]), str(r["payment_method"]))
            data_table.append([t, member, op_type, method_ar, _fmt_money(float(r["amount"] or 0), db=self.db)])

        self.current_columns = columns
        self.current_data = data_table
        self.create_data_table(self.table_frame, data_table, columns)

        self._set_summary(f"الفترة: {start_date} إلى {end_date} | عدد العمليات: {tx_count} | إجمالي: {_fmt_money(total_amount, db=self.db)}")

    def display_monthly_revenue_report(self, start_date: str, end_date: str) -> None:
        month_names = {
            "01": "يناير",
            "02": "فبراير",
            "03": "مارس",
            "04": "أبريل",
            "05": "مايو",
            "06": "يونيو",
            "07": "يوليو",
            "08": "أغسطس",
            "09": "سبتمبر",
            "10": "أكتوبر",
            "11": "نوفمبر",
            "12": "ديسمبر",
        }

        ym = str(start_date or end_date or "")[:7]
        mm = ym[5:7] if len(ym) == 7 else ""
        yy = ym[0:4] if len(ym) >= 4 else ""
        month_label = month_names.get(mm, mm)
        self.current_report_title = f"تقرير الإيرادات الشهرية - {month_label}/{yy}" if month_label and yy else "تقرير الإيرادات الشهرية"

        if self.db is None:
            self._no_db()
            return

        with self.db.get_connection() as conn:
            rows = conn.execute(
                """
                SELECT date(payment_date) AS d,
                       COUNT(*) AS c,
                       COALESCE(SUM(amount), 0) AS total
                FROM payments
                WHERE date(payment_date) BETWEEN date(?) AND date(?)
                GROUP BY date(payment_date)
                ORDER BY date(payment_date) ASC
                """,
                (start_date, end_date),
            ).fetchall()

        table = [[str(r["d"]), int(r["c"]), float(r["total"]) ] for r in rows]

        total_month = sum(float(r[2] or 0) for r in table)
        top_day = max(table, key=lambda x: float(x[2] or 0)) if table else ["-", 0, 0]

        prev_total = 0.0
        try:
            d0 = datetime.strptime(str(start_date)[:10], "%Y-%m-%d").date()
            first = d0.replace(day=1)
            prev_last = first - timedelta(days=1)
            prev_first = prev_last.replace(day=1)
            with self.db.get_connection() as conn:
                prev_total = float(
                    conn.execute(
                        """
                        SELECT COALESCE(SUM(amount), 0) AS total
                        FROM payments
                        WHERE date(payment_date) BETWEEN date(?) AND date(?)
                        """,
                        (prev_first.strftime("%Y-%m-%d"), prev_last.strftime("%Y-%m-%d")),
                    ).fetchone()["total"]
                    or 0
                )
        except Exception:
            prev_total = 0.0

        pct = 0.0
        if prev_total:
            pct = ((total_month - prev_total) / prev_total) * 100.0
        arrow = "↑" if pct > 0 else ("↓" if pct < 0 else "-")
        pct_variant = "success" if pct > 0 else ("danger" if pct < 0 else "secondary")
        pct_label = f"{arrow} {abs(pct):.1f}%" if prev_total else "-"

        self.current_report_meta = {
            "start_date": start_date,
            "end_date": end_date,
            "stats_items": [
                {"label": "إجمالي الشهر", "value": _fmt_money(total_month, db=self.db), "variant": "success"},
                {"label": "مقارنة بالشهر السابق", "value": pct_label, "variant": pct_variant},
                {"label": "أعلى يوم إيراداً", "value": f"{self._format_date_dmy(str(top_day[0]))} - {_fmt_money(float(top_day[2] or 0), db=self.db)}", "variant": "primary"},
            ],
        }

        if MATPLOTLIB_AVAILABLE:
            self.create_bar_chart(self.chart_frame, [(self._format_date_dmy(str(d)), float(t)) for d, _c, t in table], "إجمالي الإيراد حسب اليوم", "اليوم", "الإيراد")
        else:
            tb.Label(self.chart_frame, text="matplotlib غير متاح", font=FONTS["small"]).pack(pady=30)

        columns = ["اليوم/التاريخ", "عدد العمليات", "إجمالي اليوم"]
        data_table = [[self._format_date_dmy(str(d)), int(c), _fmt_money(float(t), db=self.db)] for d, c, t in table]

        self.current_columns = columns
        self.current_data = data_table
        self.create_data_table(self.table_frame, data_table, columns)

        self._set_summary(f"الفترة: {start_date} إلى {end_date} | إجمالي الشهر: {_fmt_money(total_month, db=self.db)}")

    def display_revenue_by_plan_report(self, start_date: str, end_date: str) -> None:
        self.current_report_title = "تقرير الإيرادات حسب الباقة"

        if self.db is None:
            self._no_db()
            return

        with self.db.get_connection() as conn:
            rows = conn.execute(
                """
                SELECT st.name_ar AS plan, COALESCE(SUM(p.amount), 0) AS total
                FROM payments p
                JOIN subscriptions s ON s.id = p.subscription_id
                JOIN subscription_types st ON st.id = s.subscription_type_id
                WHERE date(p.payment_date) BETWEEN date(?) AND date(?)
                GROUP BY st.id
                ORDER BY total DESC
                """,
                (start_date, end_date),
            ).fetchall()

        data = [(r["plan"], float(r["total"])) for r in rows]

        if MATPLOTLIB_AVAILABLE:
            self.create_pie_chart(self.chart_frame, data, "الإيرادات حسب الباقة")
        else:
            tb.Label(self.chart_frame, text="matplotlib غير متاح", font=FONTS["small"]).pack(pady=30)

        total_amount = sum(float(v) for _p, v in data)
        top_plan = max(data, key=lambda x: float(x[1] or 0))[0] if data else "-"
        plans_count = len(data)
        avg = (total_amount / plans_count) if plans_count else 0.0

        self.current_report_meta = {
            "start_date": start_date,
            "end_date": end_date,
            "stats_items": [
                {"label": "إجمالي الإيرادات", "value": _fmt_money(total_amount, db=self.db), "variant": "success"},
                {"label": "عدد الباقات", "value": plans_count, "variant": "secondary"},
                {"label": "أعلى باقة", "value": str(top_plan), "variant": "primary"},
                {"label": "متوسط الإيراد/باقة", "value": _fmt_money(avg, db=self.db), "variant": "info"},
            ],
        }

        columns = ["اسم الباقة", "الإيراد", "النسبة %"]
        table: list[list[Any]] = []
        for p, v in data:
            pct = (float(v) / total_amount * 100.0) if total_amount else 0.0
            table.append([p, _fmt_money(float(v), db=self.db), f"{pct:.0f}%"])
        self.current_columns = columns
        self.current_data = table
        self.create_data_table(self.table_frame, table, columns)

        self._set_summary(f"الفترة: {start_date} إلى {end_date} | عدد الباقات: {plans_count}")

    def display_payment_methods_report(self, start_date: str, end_date: str) -> None:
        self.current_report_title = "تقرير طرق الدفع"

        if self.db is None:
            self._no_db()
            return

        with self.db.get_connection() as conn:
            rows = conn.execute(
                """
                SELECT payment_method, COALESCE(SUM(amount), 0) AS total
                FROM payments
                WHERE date(payment_date) BETWEEN date(?) AND date(?)
                GROUP BY payment_method
                ORDER BY total DESC
                """,
                (start_date, end_date),
            ).fetchall()

        data = [(config.PAYMENT_METHODS.get(str(r["payment_method"]), str(r["payment_method"])), float(r["total"])) for r in rows]

        if MATPLOTLIB_AVAILABLE:
            self.create_pie_chart(self.chart_frame, data, "توزيع طرق الدفع")
        else:
            tb.Label(self.chart_frame, text="matplotlib غير متاح", font=FONTS["small"]).pack(pady=30)

        columns = ["طريقة الدفع", "الإجمالي"]
        table = [[k, v] for k, v in data]
        self.current_columns = columns
        self.current_data = table
        self.create_data_table(self.table_frame, table, columns)

        total_amount = sum(float(v) for _k, v in data)
        top_method = max(data, key=lambda x: float(x[1] or 0))[0] if data else "-"
        self.current_report_meta = {
            "start_date": start_date,
            "end_date": end_date,
            "stats_items": [
                {"label": "إجمالي الإيرادات", "value": _fmt_money(total_amount, db=self.db), "variant": "success"},
                {"label": "عدد الطرق", "value": len(table), "variant": "secondary"},
                {"label": "الأعلى", "value": str(top_method), "variant": "primary"},
            ],
        }

        self._set_summary(f"الفترة: {start_date} إلى {end_date} | عدد الطرق: {len(table)}")

    def display_daily_attendance_report(self, start_date: str, end_date: str) -> None:
        title_date = self._format_date_dmy(start_date) if start_date == end_date else ""
        self.current_report_title = f"تقرير الحضور اليومي - {title_date}" if title_date else "تقرير الحضور اليومي"

        if self.db is None:
            self._no_db()
            return

        # Attendance uses check_in/check_out stored as datetime strings.
        with self.db.get_connection() as conn:
            expected = conn.execute("SELECT COUNT(*) AS c FROM members WHERE status='active'").fetchone()["c"]
            rows = conn.execute(
                """
                SELECT date(a.check_in) AS d, COUNT(*) AS c
                FROM attendance a
                WHERE date(a.check_in) BETWEEN date(?) AND date(?)
                GROUP BY date(a.check_in)
                ORDER BY date(a.check_in) ASC
                """,
                (start_date, end_date),
            ).fetchall()

            details = conn.execute(
                """
                SELECT date(a.check_in) AS d,
                       a.member_id AS member_id,
                       time(a.check_in) AS in_time,
                       time(a.check_out) AS out_time,
                       (m.first_name || ' ' || m.last_name) AS member
                FROM attendance a
                JOIN members m ON m.id = a.member_id
                WHERE date(a.check_in) BETWEEN date(?) AND date(?)
                ORDER BY datetime(a.check_in) DESC
                LIMIT 1000
                """,
                (start_date, end_date),
            ).fetchall()

        data = [(r["d"], int(r["c"])) for r in rows]

        if MATPLOTLIB_AVAILABLE:
            self.create_line_chart(self.chart_frame, data, "الحضور اليومي", "اليوم", "عدد الزيارات")
        else:
            tb.Label(self.chart_frame, text="matplotlib غير متاح", font=FONTS["small"]).pack(pady=30)

        present = len({int(r["member_id"]) for r in details}) if details else 0
        absent = max(int(expected or 0) - int(present), 0)
        pct = (present / expected * 100.0) if expected else 0.0

        self.current_report_meta = {
            "start_date": start_date,
            "end_date": end_date,
            "stats_items": [
                {"label": "إجمالي الحضور", "value": present, "variant": "success"},
                {"label": "الغياب", "value": absent, "variant": "danger"},
                {"label": "نسبة الحضور", "value": f"{pct:.0f}%", "variant": "primary"},
                {"label": "المتوقع", "value": int(expected or 0), "variant": "secondary"},
            ],
            "total_row": ["الإجمالي", "-", "-", "-", "-"],
        }

        def _duration_hhmm(in_t: str, out_t: str) -> str:
            try:
                a = datetime.strptime(in_t[:8], "%H:%M:%S")
                b = datetime.strptime(out_t[:8], "%H:%M:%S")
                delta = b - a
                mins = int(delta.total_seconds() // 60)
                if mins < 0:
                    return "-"
                h = mins // 60
                m = mins % 60
                return f"{h}:{m:02d}"
            except Exception:
                return "-"

        columns = ["اسم العضو", "وقت الدخول", "وقت الخروج", "المدة", "الحالة"]
        table: list[list[Any]] = []
        for r in details:
            in_time = str(r["in_time"] or "-")
            out_time = str(r["out_time"] or "-")
            dur = _duration_hhmm(in_time, out_time) if in_time != "-" and out_time != "-" else "-"
            table.append([r["member"], in_time, out_time, dur, "✅"])
        self.current_columns = columns
        self.current_data = table
        self.create_data_table(self.table_frame, table, columns)

        self._set_summary(f"الفترة: {start_date} إلى {end_date} | الحضور: {present} | الغياب: {absent} | النسبة: {pct:.0f}%")

    def display_monthly_attendance_report(self, start_date: str, end_date: str) -> None:
        month_names = {
            "01": "يناير",
            "02": "فبراير",
            "03": "مارس",
            "04": "أبريل",
            "05": "مايو",
            "06": "يونيو",
            "07": "يوليو",
            "08": "أغسطس",
            "09": "سبتمبر",
            "10": "أكتوبر",
            "11": "نوفمبر",
            "12": "ديسمبر",
        }
        ym = str(start_date or end_date or "")[:7]
        mm = ym[5:7] if len(ym) == 7 else ""
        yy = ym[0:4] if len(ym) >= 4 else ""
        month_label = month_names.get(mm, mm)
        self.current_report_title = f"تقرير الحضور الشهري - {month_label}/{yy}" if month_label and yy else "تقرير الحضور الشهري"

        if self.db is None:
            self._no_db()
            return

        with self.db.get_connection() as conn:
            expected = conn.execute("SELECT COUNT(*) AS c FROM members WHERE status='active'").fetchone()["c"]
            rows = conn.execute(
                """
                SELECT date(check_in) AS d, COUNT(*) AS c
                FROM attendance
                WHERE date(check_in) BETWEEN date(?) AND date(?)
                GROUP BY date(check_in)
                ORDER BY date(check_in) ASC
                """,
                (start_date, end_date),
            ).fetchall()

        table = [[str(r["d"]), int(r["c"])] for r in rows]
        total_visits = sum(int(c) for _d, c in table)
        days_count = len(table)
        avg = (total_visits / days_count) if days_count else 0.0

        max_day = max(table, key=lambda x: int(x[1] or 0)) if table else ["-", 0]
        peak_days = len([1 for _d, c in table if int(c) == int(max_day[1])]) if table else 0

        self.current_report_meta = {
            "start_date": start_date,
            "end_date": end_date,
            "stats_items": [
                {"label": "أيام الذروة", "value": peak_days, "variant": "warning"},
                {"label": "متوسط الحضور اليومي", "value": f"{avg:.1f}", "variant": "secondary"},
                {"label": "أعلى يوم حضوراً", "value": f"{self._format_date_dmy(str(max_day[0]))} - {int(max_day[1])}", "variant": "primary"},
            ],
            "total_row": ["الإجمالي", str(int(total_visits)), "-"],
        }

        if MATPLOTLIB_AVAILABLE:
            self.create_bar_chart(self.chart_frame, [(self._format_date_dmy(str(d)), int(c)) for d, c in table], "عدد الحضور حسب اليوم", "اليوم", "عدد الحضور")
        else:
            tb.Label(self.chart_frame, text="matplotlib غير متاح", font=FONTS["small"]).pack(pady=30)

        columns = ["التاريخ", "عدد الحضور", "نسبة الإشغال %"]
        data_table: list[list[Any]] = []
        for d, c in table:
            occ = (int(c) / expected * 100.0) if expected else 0.0
            data_table.append([self._format_date_dmy(str(d)), int(c), f"{occ:.0f}%"])

        self.current_columns = columns
        self.current_data = data_table
        self.create_data_table(self.table_frame, data_table, columns)

        self._set_summary(f"الفترة: {start_date} إلى {end_date} | إجمالي الحضور: {total_visits}")

    def display_peak_hours_report(self, start_date: str, end_date: str) -> None:
        self.current_report_title = "تقرير أوقات الذروة"

        if self.db is None:
            self._no_db()
            return

        with self.db.get_connection() as conn:
            rows = conn.execute(
                """
                SELECT strftime('%H', check_in) AS hour, COUNT(*) AS c
                FROM attendance
                WHERE date(check_in) BETWEEN date(?) AND date(?)
                GROUP BY strftime('%H', check_in)
                ORDER BY hour ASC
                """,
                (start_date, end_date),
            ).fetchall()

        data = [(f"{int(r['hour']):02d}:00", int(r["c"])) for r in rows]

        total_visits = sum(int(c) for _h, c in data)
        avg = (total_visits / len(data)) if data else 0.0
        peak = max(data, key=lambda x: x[1])[0] if data else "-"
        low = min(data, key=lambda x: x[1])[0] if data else "-"

        self.current_report_meta = {
            "start_date": start_date,
            "end_date": end_date,
            "stats_items": [
                {"label": "أعلى ساعة ازدحاماً", "value": peak, "variant": "danger"},
                {"label": "أقل ساعة", "value": low, "variant": "secondary"},
                {"label": "متوسط الحضور بالساعة", "value": f"{avg:.1f}", "variant": "primary"},
            ],
        }

        if MATPLOTLIB_AVAILABLE:
            self.create_bar_chart(self.chart_frame, data, "أوقات الذروة", "الساعة", "عدد الزيارات")
        else:
            tb.Label(self.chart_frame, text="matplotlib غير متاح", font=FONTS["small"]).pack(pady=30)

        max_count = max((c for _h, c in data), default=0)

        def _bucket(v: int) -> str:
            if max_count <= 0:
                return "-"
            r = float(v) / float(max_count)
            if r >= 0.75:
                return "مرتفع"
            if r >= 0.40:
                return "متوسط"
            return "منخفض"

        columns = ["الفترة الزمنية", "عدد الزيارات", "النسبة %", "مؤشر الازدحام"]
        table: list[list[Any]] = []
        for h, c in data:
            try:
                hh = int(str(h)[:2])
                h2 = f"{(hh + 1) % 24:02d}:00"
                period = f"{h} - {h2}"
            except Exception:
                period = str(h)
            pct = (int(c) / total_visits * 100.0) if total_visits else 0.0
            table.append([period, int(c), f"{pct:.0f}%", _bucket(int(c))])
        self.current_columns = columns
        self.current_data = table
        self.create_data_table(self.table_frame, table, columns)

        self._set_summary(f"الفترة: {start_date} إلى {end_date} | إجمالي الزيارات: {total_visits} | أعلى ساعة: {peak}")

    def display_plan_distribution_report(self, start_date: str, end_date: str) -> None:
        self.current_report_title = "تقرير توزيع الباقات"

        if self.db is None:
            self._no_db()
            return

        with self.db.get_connection() as conn:
            rows = conn.execute(
                """
                SELECT st.name_ar AS plan,
                       st.is_active AS is_active,
                       COUNT(*) AS c
                FROM subscriptions s
                JOIN subscription_types st ON st.id = s.subscription_type_id
                WHERE date(s.start_date) BETWEEN date(?) AND date(?)
                GROUP BY st.id
                ORDER BY c DESC
                """,
                (start_date, end_date),
            ).fetchall()

        data = [(r["plan"], int(r["c"]), int(r["is_active"] or 0)) for r in rows]

        if MATPLOTLIB_AVAILABLE:
            self.create_pie_chart(self.chart_frame, [(p, c) for p, c, _a in data], "توزيع الاشتراكات حسب الباقة")
        else:
            tb.Label(self.chart_frame, text="matplotlib غير متاح", font=FONTS["small"]).pack(pady=30)

        total_subs = sum(int(c) for _p, c, _a in data)
        most = max(data, key=lambda x: int(x[1] or 0))[0] if data else "-"
        least = min(data, key=lambda x: int(x[1] or 0))[0] if data else "-"

        self.current_report_meta = {
            "start_date": start_date,
            "end_date": end_date,
            "stats_items": [
                {"label": "إجمالي الاشتراكات", "value": total_subs, "variant": "secondary"},
                {"label": "أكثر باقة", "value": str(most), "variant": "primary"},
                {"label": "أقل باقة", "value": str(least), "variant": "warning"},
            ],
        }

        columns = ["اسم الباقة", "عدد المشتركين", "النسبة %", "الحالة"]
        table: list[list[Any]] = []
        for p, c, a in data:
            pct = (int(c) / total_subs * 100.0) if total_subs else 0.0
            st = "نشطة" if int(a) == 1 else "غير نشطة"
            table.append([p, int(c), f"{pct:.0f}%", st])
        self.current_columns = columns
        self.current_data = table
        self.create_data_table(self.table_frame, table, columns)

        self._set_summary(f"الفترة: {start_date} إلى {end_date} | إجمالي الاشتراكات: {total_subs}")

    def display_plan_performance_report(self, start_date: str, end_date: str) -> None:
        self.current_report_title = "تقرير أداء الباقات"

        if self.db is None:
            self._no_db()
            return

        with self.db.get_connection() as conn:
            rows = conn.execute(
                """
                SELECT st.name_ar AS plan,
                       COUNT(s.id) AS new_subs,
                       SUM(
                           CASE
                               WHEN s.id IS NOT NULL AND EXISTS(
                                   SELECT 1
                                   FROM subscriptions s2
                                   WHERE s2.member_id = s.member_id
                                     AND s2.subscription_type_id = st.id
                                     AND date(s2.end_date) < date(s.start_date)
                               ) THEN 1
                               ELSE 0
                           END
                       ) AS renewals,
                       SUM(CASE WHEN s.status = 'cancelled' THEN 1 ELSE 0 END) AS cancelled,
                       COALESCE(SUM(p.amount), 0) AS revenue
                FROM subscription_types st
                LEFT JOIN subscriptions s ON s.subscription_type_id = st.id
                    AND date(s.start_date) BETWEEN date(?) AND date(?)
                LEFT JOIN payments p ON p.subscription_id = s.id
                    AND date(p.payment_date) BETWEEN date(?) AND date(?)
                GROUP BY st.id
                ORDER BY revenue DESC
                """,
                (start_date, end_date, start_date, end_date),
            ).fetchall()

        raw_table = [[r["plan"], int(r["new_subs"] or 0), int(r["renewals"] or 0), int(r["cancelled"] or 0), float(r["revenue"] or 0)] for r in rows]
        columns = ["اسم الباقة", "الاشتراكات الجديدة", "التجديدات", "الإلغاءات", "الإيرادات"]

        table: list[list[Any]] = []
        for p, n, rr, cc, rv in raw_table:
            table.append([p, int(n), int(rr), int(cc), _fmt_money(float(rv), db=self.db)])

        self.current_columns = columns
        self.current_data = table
        self.create_data_table(self.table_frame, table, columns)

        total_revenue = sum(float(rv) for _p, _n, _rr, _cc, rv in raw_table)
        top_plan = max(raw_table, key=lambda x: float(x[4] or 0))[0] if raw_table else "-"
        total_new = sum(int(n) for _p, n, _rr, _cc, _rv in raw_table)
        total_ren = sum(int(rr) for _p, _n, rr, _cc, _rv in raw_table)
        renewal_rate = (total_ren / total_new * 100.0) if total_new else 0.0

        self.current_report_meta = {
            "start_date": start_date,
            "end_date": end_date,
            "stats_items": [
                {"label": "إجمالي الإيرادات", "value": _fmt_money(total_revenue, db=self.db), "variant": "success"},
                {"label": "أعلى باقة أداءً", "value": str(top_plan), "variant": "primary"},
                {"label": "معدل التجديد", "value": f"{renewal_rate:.0f}%", "variant": "secondary"},
            ],
        }

        if MATPLOTLIB_AVAILABLE:
            self.create_horizontal_bar_chart(self.chart_frame, [(r[0], float(r[4])) for r in raw_table], "إيرادات الباقات")
        else:
            tb.Label(self.chart_frame, text="matplotlib غير متاح", font=FONTS["small"]).pack(pady=30)

        self._set_summary(f"الفترة: {start_date} إلى {end_date} | عدد الباقات: {len(table)}")

    def display_custom_query(self, start_date: str, end_date: str) -> None:
        self.current_report_title = "استعلام مخصص"

        tb.Label(self.chart_frame, text="أدخل استعلام SQL مخصص (SELECT فقط)", font=FONTS["subheading"], anchor="e").pack(
            fill="x", pady=(0, 8)
        )

        box = tk.Text(self.chart_frame, height=8, wrap="word")
        box.pack(fill="x")
        box.insert(
            "1.0",
            "SELECT member_code, first_name, last_name, phone FROM members LIMIT 50;",
        )

        def run_query() -> None:
            if self.db is None:
                return
            q = box.get("1.0", "end").strip()
            if not q.lower().startswith("select"):
                messagebox.showwarning("تنبيه", "يسمح فقط باستعلامات SELECT")
                return

            try:
                with self.db.get_connection() as conn:
                    cur = conn.cursor()
                    res = cur.execute(q).fetchall()
                    cols = [d[0] for d in cur.description] if cur.description else []
            except Exception as e:
                messagebox.showerror("خطأ", f"فشل الاستعلام: {e}")
                return

            data = [list(r) for r in res]
            self.current_columns = cols
            self.current_data = data
            self.create_data_table(self.table_frame, data, cols)
            short = q.strip().splitlines()[0] if q.strip() else ""
            short = (short[:60] + "...") if len(short) > 60 else short
            if short:
                self.current_report_title = f"تقرير استعلام مخصص - {short}"
            else:
                self.current_report_title = "تقرير استعلام مخصص"

            executed_at = datetime.now().strftime("%d-%m-%Y %H:%M")
            self.current_report_meta = {
                "start_date": start_date,
                "end_date": end_date,
                "criteria_lines": [
                    f"SQL: {q}",
                    f"تاريخ التنفيذ: {executed_at}",
                    (f"الفترة: {start_date} إلى {end_date}" if start_date and end_date else ""),
                ],
                "stats_items": [
                    {"label": "عدد النتائج", "value": len(data), "variant": "primary"},
                    {"label": "تاريخ التنفيذ", "value": executed_at, "variant": "secondary"},
                ],
            }

            self._set_summary(f"نتائج: {len(data)} صف")

        tb.Button(self.chart_frame, text="تشغيل", bootstyle="success", command=run_query).pack(anchor="w", pady=8)

    # ------------------------------
    # Chart helpers
    # ------------------------------

    def create_line_chart(self, parent: ttk.Widget, data: list[tuple[Any, Any]], title: str, x_label: str, y_label: str):
        fig = Figure(figsize=(8, 3.6), dpi=100)
        ax = fig.add_subplot(111)
        x = [r[0] for r in data]
        y = [r[1] for r in data]
        ax.plot(x, y, marker="o", linewidth=2, markersize=5, color=COLORS["primary"])
        ax.set_title(title)
        ax.set_xlabel(x_label)
        ax.set_ylabel(y_label)
        ax.grid(True, alpha=0.3)
        fig.tight_layout()

        canvas = FigureCanvasTkAgg(fig, parent)
        canvas.draw()
        canvas.get_tk_widget().pack(fill="both", expand=True)
        self.charts.append(canvas)
        return canvas

    def create_bar_chart(self, parent: ttk.Widget, data: list[tuple[Any, Any]], title: str, x_label: str, y_label: str):
        fig = Figure(figsize=(8, 3.6), dpi=100)
        ax = fig.add_subplot(111)
        labels = [r[0] for r in data]
        values = [float(r[1]) for r in data]
        ax.bar(labels, values, color="#3498db")
        ax.set_title(title)
        ax.set_xlabel(x_label)
        ax.set_ylabel(y_label)
        ax.grid(True, alpha=0.2, axis="y")
        if plt is not None:
            plt.setp(ax.xaxis.get_majorticklabels(), rotation=45, ha="right")
        fig.tight_layout()

        canvas = FigureCanvasTkAgg(fig, parent)
        canvas.draw()
        canvas.get_tk_widget().pack(fill="both", expand=True)
        self.charts.append(canvas)
        return canvas

    def create_pie_chart(self, parent: ttk.Widget, data: list[tuple[Any, Any]], title: str):
        fig = Figure(figsize=(7, 3.6), dpi=100)
        ax = fig.add_subplot(111)
        labels = [r[0] for r in data]
        values = [float(r[1]) for r in data]
        ax.pie(values, labels=labels, autopct="%1.1f%%", startangle=90)
        ax.set_title(title)
        fig.tight_layout()

        canvas = FigureCanvasTkAgg(fig, parent)
        canvas.draw()
        canvas.get_tk_widget().pack(fill="both", expand=True)
        self.charts.append(canvas)
        return canvas

    def create_horizontal_bar_chart(self, parent: ttk.Widget, data: list[tuple[Any, Any]], title: str):
        fig = Figure(figsize=(8, 3.6), dpi=100)
        ax = fig.add_subplot(111)
        labels = [r[0] for r in data]
        values = [float(r[1]) for r in data]
        y_pos = list(range(len(labels)))
        ax.barh(y_pos, values, color="#3498db")
        ax.set_yticks(y_pos)
        ax.set_yticklabels(labels)
        ax.invert_yaxis()
        ax.set_title(title)
        ax.grid(True, alpha=0.2, axis="x")
        fig.tight_layout()

        canvas = FigureCanvasTkAgg(fig, parent)
        canvas.draw()
        canvas.get_tk_widget().pack(fill="both", expand=True)
        self.charts.append(canvas)
        return canvas

    # ------------------------------
    # Table helper
    # ------------------------------

    def create_data_table(self, parent: ttk.Widget, data: list[list[Any]], columns: list[str]) -> ttk.Treeview:
        frame = tb.Frame(parent)
        frame.pack(fill="both", expand=True)

        tree = ttk.Treeview(frame, columns=columns, show="headings")

        for col in columns:
            tree.heading(col, text=col)
            tree.column(col, width=120, anchor="center")

        ysb = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
        xsb = ttk.Scrollbar(frame, orient="horizontal", command=tree.xview)
        tree.configure(yscrollcommand=ysb.set, xscrollcommand=xsb.set)

        tree.pack(side="left", fill="both", expand=True)
        ysb.pack(side="right", fill="y")
        xsb.pack(side="bottom", fill="x")

        for row in data:
            tree.insert("", "end", values=row)

        return tree

    # ------------------------------
    # Export
    # ------------------------------

    def show_export_dialog(self) -> None:
        if not self.current_columns:
            messagebox.showwarning("تنبيه", "لا يوجد تقرير لتصديره")
            return

        dlg = ExportDialog(self.winfo_toplevel())
        self.wait_window(dlg)
        if dlg.result is None:
            return

        fmt = dlg.result
        if fmt == "excel":
            self.export_to_excel(self.current_data, self.current_columns)
        elif fmt == "csv":
            self.export_to_csv(self.current_data, self.current_columns)
        elif fmt == "pdf":
            self.export_to_pdf(self.current_report_title, self.current_data, self.current_columns, summary=self.current_summary)

    def export_to_csv(self, data: list[list[Any]], columns: list[str], filename: str | None = None) -> bool:
        if filename is None:
            filename = filedialog.asksaveasfilename(
                defaultextension=".csv",
                filetypes=[("CSV files", "*.csv")],
                title="حفظ التقرير كملف CSV",
            )
        if not filename:
            return False

        try:
            with open(filename, "w", newline="", encoding="utf-8-sig") as f:
                writer = csv.writer(f)
                writer.writerow(columns)
                writer.writerows(data)

            messagebox.showinfo("نجاح", f"تم تصدير التقرير إلى:\n{filename}")
            return True
        except Exception as e:
            messagebox.showerror("خطأ", f"فشل في تصدير التقرير:\n{e}")
            return False

    def export_to_excel(self, data: list[list[Any]], columns: list[str], filename: str | None = None) -> bool:
        if filename is None:
            filename = filedialog.asksaveasfilename(
                defaultextension=".xlsx",
                filetypes=[("Excel files", "*.xlsx")],
                title="حفظ التقرير كملف Excel",
            )
        if not filename:
            return False

        try:
            if PANDAS_AVAILABLE and OPENPYXL_AVAILABLE:
                df = pd.DataFrame(data, columns=columns)  # type: ignore
                with pd.ExcelWriter(filename, engine="openpyxl") as writer:  # type: ignore
                    df.to_excel(writer, index=False, sheet_name="التقرير")
            elif OPENPYXL_AVAILABLE:
                wb = openpyxl.Workbook()  # type: ignore
                ws = wb.active
                ws.title = "التقرير"
                ws.append(columns)
                for row in data:
                    ws.append(list(row))
                wb.save(filename)
            else:
                messagebox.showwarning("تنبيه", "openpyxl غير مثبت. استخدم CSV")
                return False

            messagebox.showinfo("نجاح", f"تم تصدير التقرير إلى:\n{filename}")
            try:
                if messagebox.askyesno("فتح الملف", "هل تريد فتح الملف الآن؟"):
                    os.startfile(filename)
            except Exception:
                pass

            return True
        except Exception as e:
            messagebox.showerror("خطأ", f"فشل في تصدير التقرير:\n{e}")
            return False

    def export_to_pdf(
        self,
        report_title: str,
        data: list[list[Any]],
        columns: list[str],
        summary: str | None = None,
        filename: str | None = None,
    ) -> bool:
        if not REPORTLAB_AVAILABLE:
            if filename is None:
                filename = filedialog.asksaveasfilename(
                    defaultextension=".txt",
                    filetypes=[("Text files", "*.txt")],
                    title="حفظ التقرير كملف نصي (بديل عن PDF)",
                )
            if not filename:
                return False

            if filename.lower().endswith(".pdf"):
                filename = filename[:-4] + ".txt"
            if not filename.lower().endswith(".txt"):
                filename = filename + ".txt"

            try:
                lines: list[str] = []
                lines.append(str(getattr(config, "APP_NAME", "")) or "")
                lines.append(report_title or "")
                lines.append(f"تاريخ التقرير: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
                if (summary or "").strip():
                    lines.append("")
                    lines.append((summary or "").strip())
                lines.append("")
                lines.append("\t".join([str(c) for c in columns]))
                for r in data:
                    lines.append("\t".join([str(x) for x in r]))

                with open(filename, "w", encoding="utf-8-sig", newline="\r\n") as f:
                    f.write("\n".join(lines))

                messagebox.showinfo("نجاح", f"تم حفظ التقرير كملف نصي (بديل عن PDF):\n{filename}")
                try:
                    if messagebox.askyesno("فتح الملف", "هل تريد فتح الملف الآن؟"):
                        os.startfile(filename)
                except Exception:
                    pass

                return True
            except Exception as e:
                messagebox.showerror("خطأ", f"فشل في حفظ التقرير:\n{e}")
                return False

        if filename is None:
            filename = filedialog.asksaveasfilename(
                defaultextension=".pdf",
                filetypes=[("PDF files", "*.pdf")],
                title="حفظ التقرير كملف PDF",
            )
        if not filename:
            return False

        try:
            doc = SimpleDocTemplate(filename, pagesize=landscape(A4), rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
            styles = getSampleStyleSheet()

            elements = []
            elements.append(Paragraph(report_title, styles["Title"]))
            elements.append(Spacer(1, 10))
            elements.append(Paragraph(f"تاريخ التقرير: {datetime.now().strftime('%Y-%m-%d %H:%M')}", styles["Normal"]))
            elements.append(Spacer(1, 10))
            if summary:
                elements.append(Paragraph(summary, styles["Normal"]))
                elements.append(Spacer(1, 12))

            table_data = [columns] + data
            t = Table(table_data)
            t.setStyle(
                TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, 0), rl_colors.HexColor("#3498db")),
                        ("TEXTCOLOR", (0, 0), (-1, 0), rl_colors.white),
                        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                        ("GRID", (0, 0), (-1, -1), 0.5, rl_colors.grey),
                        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [rl_colors.white, rl_colors.HexColor("#f5f5f5")]),
                    ]
                )
            )
            elements.append(t)
            doc.build(elements)

            messagebox.showinfo("نجاح", f"تم تصدير التقرير إلى:\n{filename}")
            try:
                if messagebox.askyesno("فتح الملف", "هل تريد فتح الملف الآن؟"):
                    os.startfile(filename)
            except Exception:
                pass

            return True
        except Exception as e:
            messagebox.showerror("خطأ", f"فشل في تصدير PDF:\n{e}")
            return False

    def print_report(self) -> None:
        # Print via PDF export if available, otherwise fallback to Windows text printing.
        if not self.current_columns:
            return

        if (
            self.current_report_type in self._member_report_types
            or self.current_report_type in self._financial_report_types
            or self.current_report_type in self._other_unified_report_types
        ):
            try:
                html_doc = self._generate_members_report_print_html()
                if self.current_report_type in self._member_report_types:
                    grp = "members"
                elif self.current_report_type in self._financial_report_types:
                    grp = "financial"
                else:
                    grp = "reports"
                prefix = f"{grp}_{self.current_report_type or 'report'}"
                print_html_windows(html_doc, filename_prefix=prefix)
                return
            except Exception:
                messagebox.showwarning("تنبيه", "تعذر بدء الطباعة تلقائياً")
                return

        if REPORTLAB_AVAILABLE:
            temp_dir = os.environ.get("TEMP") or os.getcwd()
            temp_pdf = os.path.join(temp_dir, "temp_report.pdf")
            ok = self.export_to_pdf(
                self.current_report_title,
                self.current_data,
                self.current_columns,
                summary=self.current_summary,
                filename=temp_pdf,
            )
            if not ok:
                return

            try:
                os.startfile(temp_pdf, "print")
            except Exception:
                messagebox.showwarning("تنبيه", "تعذر بدء الطباعة تلقائياً")
            return

        try:
            lines: list[str] = []
            lines.append(str(getattr(config, "APP_NAME", "")) or "")
            lines.append(self.current_report_title or "")
            lines.append(f"التاريخ: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
            if (self.current_summary or "").strip():
                lines.append("-")
                lines.append(self.current_summary.strip())
            lines.append("-")
            lines.append("\t".join([str(c) for c in self.current_columns]))
            for r in self.current_data:
                lines.append("\t".join([str(x) for x in r]))
            print_text_windows("\n".join(lines), filename_prefix="report")
        except Exception:
            messagebox.showwarning("تنبيه", "تعذر بدء الطباعة تلقائياً")

    def _format_date_dmy(self, value: str) -> str:
        try:
            d = datetime.strptime(str(value)[:10], "%Y-%m-%d").date()
            return d.strftime("%d-%m-%Y")
        except Exception:
            return str(value)

    def _get_club_settings(self) -> dict[str, str]:
        club_name = ""
        logo_path = ""
        if self.db is not None:
            try:
                club_name = str(self.db.get_settings("gym.name") or "")
            except Exception:
                club_name = ""
            try:
                logo_path = str(self.db.get_settings("gym.logo") or "")
            except Exception:
                logo_path = ""

        if not club_name:
            club_name = str(getattr(config, "APP_NAME", "نظام إدارة الصالة الرياضية"))

        logo_uri = ""
        try:
            if logo_path and os.path.exists(logo_path):
                logo_uri = Path(logo_path).resolve().as_uri()
        except Exception:
            logo_uri = ""

        return {"club_name": club_name, "logo_uri": logo_uri}

    def _generate_members_report_print_html(self) -> str:
        settings = self._get_club_settings()
        club_name = html_lib.escape(settings.get("club_name") or "")
        logo_uri = settings.get("logo_uri") or ""

        system_name = html_lib.escape(str(getattr(config, "APP_NAME", "نظام إدارة النادي")) or "نظام إدارة النادي")

        user_name = str(self.user_data.get("username") or self.user_data.get("name") or self.user_data.get("full_name") or "-")
        user_name = html_lib.escape(user_name)

        meta = self.current_report_meta or {}
        start_date = str(meta.get("start_date") or "").strip()
        end_date = str(meta.get("end_date") or "").strip()
        current_date = datetime.now().strftime("%d-%m-%Y")
        start_dmy = self._format_date_dmy(start_date) if start_date else ""
        end_dmy = self._format_date_dmy(end_date) if end_date else ""

        stats_items = list(meta.get("stats_items") or [])

        criteria_lines = meta.get("criteria_lines")
        criteria_html = ""
        if criteria_lines:
            items = criteria_lines
            if isinstance(items, str):
                items = [items]
            try:
                items = list(items)
            except Exception:
                items = [str(criteria_lines)]

            lis: list[str] = []
            for it in items:
                txt = html_lib.escape(str(it))
                if txt.strip():
                    lis.append(f"<div class=\"criteria-item\">{txt}</div>")
            if lis:
                criteria_html = f"""
                    <div class=\"criteria\">
                        <div class=\"criteria-title\">🔎 معايير البحث</div>
                        <div class=\"criteria-body\">{''.join(lis)}</div>
                    </div>
                """

        raw_columns = list(self.current_columns or [])
        raw_rows = list(self.current_data or [])

        total_row = meta.get("total_row")
        has_total_row = isinstance(total_row, list) and len(list(total_row)) == len(raw_columns)

        add_index = True
        if raw_columns and str(raw_columns[0]).strip() == "#":
            add_index = False

        columns = (["#"] + raw_columns) if add_index else raw_columns
        rows: list[list[Any]] = []
        if add_index:
            for i, r in enumerate(raw_rows, start=1):
                rows.append([i] + list(r))
        else:
            rows = [list(r) for r in raw_rows]

        if has_total_row:
            if add_index:
                rows.append([""] + list(total_row))
            else:
                rows.append(list(total_row))

        def _variant_class(v: str) -> str:
            vv = (v or "").strip().lower()
            if vv in ("success", "green"):
                return "success"
            if vv in ("danger", "red", "error"):
                return "danger"
            if vv in ("warning", "orange"):
                return "warning"
            if vv in ("info", "blue"):
                return "info"
            if vv in ("primary", "purple"):
                return "primary"
            return "secondary"

        stats_html = ""
        if stats_items:
            cards: list[str] = []
            for it in stats_items:
                label = html_lib.escape(str(it.get("label") or ""))
                value = html_lib.escape(str(it.get("value") if it.get("value") is not None else ""))
                cls = _variant_class(str(it.get("variant") or "secondary"))
                cards.append(
                    f"<div class=\"stat {cls}\"><div class=\"value\">{value}</div><div class=\"label\">{label}</div></div>"
                )
            stats_html = f"""
                <div class=\"stats-title\">📊 الإحصائيات السريعة</div>
                <div class=\"stats\">{''.join(cards)}</div>
            """

        logo_block = ""
        if logo_uri:
            logo_block = f"<img class=\"logo\" src=\"{logo_uri}\" alt=\"logo\">"
        else:
            logo_block = "<div class=\"logo-placeholder\">🏋️</div>"

        # Build table
        ths: list[str] = []
        for i, c in enumerate(columns):
            name = html_lib.escape(str(c))
            style = ""
            if i == 0:
                style = " style=\"width:52px\""
            ths.append(f"<th{style}>{name}</th>")

        def _is_phone_col(col_name: str) -> bool:
            return "الهاتف" in col_name or "phone" in col_name.lower()

        def _is_status_col(col_name: str) -> bool:
            return "الحالة" in col_name or "status" in col_name.lower()

        trows: list[str] = []
        for ridx, r in enumerate(rows):
            is_total = has_total_row and ridx == (len(rows) - 1)
            tds: list[str] = []
            for i, val in enumerate(r):
                col_name = str(columns[i]) if i < len(columns) else ""
                cell = str(val) if val is not None else ""
                cell_esc = html_lib.escape(cell)

                if _is_status_col(col_name):
                    s = cell.strip()
                    cls = "status-neutral"
                    if s in ("نشط", "active"):
                        cls = "status-active"
                    elif s in ("غير نشط", "inactive"):
                        cls = "status-inactive"
                    elif s in ("مجمد", "frozen"):
                        cls = "status-frozen"
                    elif s in ("✅", "حاضر"):
                        cls = "status-active"
                    cell_esc = f"<span class=\"badge {cls}\">{html_lib.escape(s)}</span>"
                    tds.append(f"<td>{cell_esc}</td>")
                    continue

                if _is_phone_col(col_name):
                    tds.append(f"<td dir=\"ltr\" class=\"cell-phone\">{cell_esc}</td>")
                    continue

                tds.append(f"<td>{cell_esc}</td>")

            row_cls = " class=\"total-row\"" if is_total else ""
            trows.append(f"<tr{row_cls}>{''.join(tds)}</tr>")

        range_html = ""
        if start_dmy and end_dmy:
            range_html = f"<div><strong>الفترة:</strong> من {html_lib.escape(start_dmy)} إلى {html_lib.escape(end_dmy)}</div>"

        report_title = html_lib.escape(self.current_report_title or "تقرير")

        html_doc = f"""
        <!DOCTYPE html>
        <html dir=\"rtl\" lang=\"ar\">
        <head>
            <meta charset=\"UTF-8\">
            <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">
            <style>
                @page {{ size: A4; margin: 12mm; }}
                * {{ box-sizing: border-box; }}
                body {{
                    font-family: 'Cairo', 'Tajawal', Arial, sans-serif;
                    direction: rtl;
                    color: #1f2937;
                    -webkit-print-color-adjust: exact;
                    print-color-adjust: exact;
                }}
                .page {{
                    border: 2px solid #e5e7eb;
                    border-radius: 10px;
                    padding: 16px;
                }}
                .header {{
                    display: flex;
                    align-items: center;
                    justify-content: space-between;
                    gap: 12px;
                    padding-bottom: 10px;
                    border-bottom: 3px solid #2c3e50;
                }}
                .title {{ flex: 1; text-align: center; }}
                .logo {{ width: 64px; height: 64px; object-fit: contain; }}
                .logo-placeholder {{
                    width: 64px; height: 64px; border-radius: 50%;
                    background: #ffffff; border: 2px solid #e5e7eb;
                    display: flex; align-items: center; justify-content: center;
                    font-size: 28px;
                }}
                .app-name {{ margin: 0; font-size: 20px; font-weight: 800; color: #111827; }}
                .app-sub {{ margin: 4px 0 0 0; font-size: 12px; color: #6b7280; }}
                .report-title {{
                    margin: 14px 0 12px 0;
                    padding: 10px 14px;
                    border-radius: 10px;
                    text-align: center;
                    font-size: 18px;
                    font-weight: 800;
                    color: #fff;
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                }}
                .info {{
                    background: #f8fafc;
                    border: 1px solid #e5e7eb;
                    border-radius: 10px;
                    padding: 12px;
                    font-size: 12px;
                    display: flex;
                    justify-content: space-between;
                    gap: 10px;
                    flex-wrap: wrap;
                }}
                .criteria {{
                    margin-top: 10px;
                    border: 1px dashed #cbd5e1;
                    border-radius: 10px;
                    padding: 10px;
                    background: #f8fafc;
                }}
                .criteria-title {{
                    font-weight: 800;
                    color: #0f172a;
                    margin-bottom: 6px;
                }}
                .criteria-item {{
                    font-size: 12px;
                    color: #334155;
                    padding: 2px 0;
                    word-break: break-word;
                }}
                .stats-title {{ margin-top: 12px; font-size: 13px; color: #374151; font-weight: 800; }}
                .stats {{
                    margin-top: 8px;
                    display: grid;
                    grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
                    gap: 10px;
                }}
                .stat {{
                    background: #fff;
                    border: 2px solid #e5e7eb;
                    border-radius: 10px;
                    padding: 12px;
                    text-align: center;
                }}
                .stat .value {{ font-size: 22px; font-weight: 900; color: #111827; }}
                .stat .label {{ font-size: 12px; margin-top: 4px; color: #6b7280; }}
                .stat.success {{ border-color: #22c55e; }}
                .stat.danger {{ border-color: #ef4444; }}
                .stat.warning {{ border-color: #f59e0b; }}
                .stat.info {{ border-color: #3b82f6; }}
                .stat.primary {{ border-color: #8b5cf6; }}
                .stat.secondary {{ border-color: #64748b; }}
                table {{ width: 100%; border-collapse: collapse; margin-top: 14px; border: 1px solid #e5e7eb; }}
                thead th {{
                    background: linear-gradient(135deg, #2c3e50 0%, #34495e 100%);
                    color: #fff;
                    padding: 10px;
                    font-size: 12px;
                    text-align: center;
                    border: 1px solid rgba(255,255,255,0.12);
                }}
                tbody td {{ padding: 9px; font-size: 12px; text-align: center; border: 1px solid #e5e7eb; }}
                tbody tr:nth-child(even) {{ background: #f8fafc; }}
                .cell-phone {{ font-family: Consolas, Monaco, monospace; letter-spacing: 0.5px; }}
                .badge {{ display: inline-block; padding: 3px 10px; border-radius: 999px; font-size: 11px; font-weight: 700; }}
                .status-active {{ background: #dcfce7; color: #166534; }}
                .status-inactive {{ background: #fee2e2; color: #7f1d1d; }}
                .status-frozen {{ background: #e0f2fe; color: #075985; }}
                .status-neutral {{ background: #e5e7eb; color: #374151; }}
                .footer {{
                    margin-top: 16px;
                    padding-top: 10px;
                    border-top: 1px solid #e5e7eb;
                    display: flex;
                    justify-content: space-between;
                    color: #64748b;
                    font-size: 12px;
                }}
                .total-row td {{
                    background: #fef3c7 !important;
                    font-weight: 800;
                }}
            </style>
        </head>
        <body>
            <div class=\"page\">
                <div class=\"header\">
                    <div style=\"width: 64px;\">{logo_block}</div>
                    <div class=\"title\">
                        <h1 class=\"app-name\">{club_name}</h1>
                        <p class=\"app-sub\">نظام إدارة الصالة الرياضية</p>
                    </div>
                    <div style=\"width: 64px;\"></div>
                </div>
                <div class=\"report-title\">📋 {report_title}</div>
                <div class=\"info\">
                    <div><strong>التاريخ:</strong> {current_date}</div>
                    {range_html}
                </div>
                {criteria_html}
                {stats_html}
                <table>
                    <thead><tr>{''.join(ths)}</tr></thead>
                    <tbody>{''.join(trows)}</tbody>
                </table>
                <div class=\"footer\">
                    <span>طُبع بواسطة: {user_name}</span>
                    <span>الصفحة: 1 من 1</span>
                    <span>تم الإنشاء بواسطة {system_name}</span>
                </div>
            </div>
            <script>
                window.addEventListener('load', function () {{
                    try {{ window.print(); }} catch (e) {{}}
                }});
            </script>
        </body>
        </html>
        """

        return html_doc

    def _generate_total_members_print_html(self) -> str:
        meta = self.current_report_meta or {}
        stats = dict(meta.get("stats") or {})
        start_date = str(meta.get("start_date") or "")
        end_date = str(meta.get("end_date") or "")

        s_total = int(stats.get("total") or 0)
        s_active = int(stats.get("active") or 0)
        s_inactive = int(stats.get("inactive") or 0)
        s_new = int(stats.get("new_members") or 0)
        s_deleted = int(stats.get("deleted") or 0)

        settings = self._get_club_settings()
        club_name = html_lib.escape(settings.get("club_name") or "")
        logo_uri = settings.get("logo_uri") or ""

        user_name = str(self.user_data.get("username") or self.user_data.get("name") or self.user_data.get("full_name") or "-")
        user_name = html_lib.escape(user_name)

        current_date = datetime.now().strftime("%d-%m-%Y")
        start_dmy = self._format_date_dmy(start_date)
        end_dmy = self._format_date_dmy(end_date)

        table_rows: list[str] = []
        for r in self.current_data:
            idx = html_lib.escape(str(r[0]) if len(r) > 0 else "")
            name = html_lib.escape(str(r[1]) if len(r) > 1 else "")
            phone = html_lib.escape(str(r[2]) if len(r) > 2 else "")
            status = str(r[3]) if len(r) > 3 else ""
            join_date = html_lib.escape(self._format_date_dmy(str(r[4]) if len(r) > 4 else ""))

            status_class = "status-inactive"
            if str(status).strip() == "نشط":
                status_class = "status-active"
            elif str(status).strip() == "مجمد":
                status_class = "status-frozen"

            status_html = f"<span class=\"badge {status_class}\">{html_lib.escape(str(status))}</span>"
            table_rows.append(
                """
                <tr>
                    <td class=\"col-idx\">{idx}</td>
                    <td class=\"col-name\">{name}</td>
                    <td class=\"col-phone\">{phone}</td>
                    <td class=\"col-status\">{status_html}</td>
                    <td class=\"col-date\">{join_date}</td>
                </tr>
                """.format(idx=idx, name=name, phone=phone, status_html=status_html, join_date=join_date)
            )

        logo_block = ""
        if logo_uri:
            logo_block = f"<img class=\"logo\" src=\"{logo_uri}\" alt=\"logo\">"

        html_doc = f"""
        <!DOCTYPE html>
        <html dir=\"rtl\" lang=\"ar\">
        <head>
            <meta charset=\"UTF-8\">
            <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">
            <style>
                @page {{ size: A4; margin: 12mm; }}

                * {{ box-sizing: border-box; }}

                body {{
                    font-family: 'Cairo', 'Tajawal', Arial, sans-serif;
                    direction: rtl;
                    color: #1f2937;
                    -webkit-print-color-adjust: exact;
                    print-color-adjust: exact;
                }}

                .page {{
                    border: 2px solid #e5e7eb;
                    border-radius: 10px;
                    padding: 16px;
                }}

                .header {{
                    display: flex;
                    align-items: center;
                    justify-content: space-between;
                    gap: 12px;
                    padding-bottom: 10px;
                    border-bottom: 3px solid #2c3e50;
                }}

                .header .title {{
                    flex: 1;
                    text-align: center;
                }}

                .logo {{
                    width: 64px;
                    height: 64px;
                    object-fit: contain;
                }}

                .app-name {{
                    margin: 0;
                    font-size: 20px;
                    font-weight: 800;
                    color: #111827;
                }}

                .app-sub {{
                    margin: 4px 0 0 0;
                    font-size: 12px;
                    color: #6b7280;
                }}

                .report-title {{
                    margin: 14px 0 12px 0;
                    padding: 10px 14px;
                    border-radius: 10px;
                    text-align: center;
                    font-size: 18px;
                    font-weight: 800;
                    color: #fff;
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                }}

                .info {{
                    background: #f8fafc;
                    border: 1px solid #e5e7eb;
                    border-radius: 10px;
                    padding: 12px;
                    font-size: 12px;
                    display: flex;
                    justify-content: space-between;
                    gap: 10px;
                    flex-wrap: wrap;
                }}

                .stats {{
                    margin-top: 12px;
                    display: grid;
                    grid-template-columns: repeat(5, 1fr);
                    gap: 10px;
                }}

                .stat {{
                    background: #fff;
                    border: 2px solid #e5e7eb;
                    border-radius: 10px;
                    padding: 12px;
                    text-align: center;
                }}

                .stat .value {{
                    font-size: 22px;
                    font-weight: 900;
                    color: #111827;
                }}

                .stat .label {{
                    font-size: 12px;
                    margin-top: 4px;
                    color: #6b7280;
                }}

                .stat.active {{ border-color: #22c55e; }}
                .stat.inactive {{ border-color: #ef4444; }}
                .stat.new {{ border-color: #3b82f6; }}

                table {{
                    width: 100%;
                    border-collapse: collapse;
                    margin-top: 14px;
                    border: 1px solid #e5e7eb;
                    border-radius: 10px;
                    overflow: hidden;
                }}

                thead th {{
                    background: linear-gradient(135deg, #2c3e50 0%, #34495e 100%);
                    color: #fff;
                    padding: 10px;
                    font-size: 12px;
                    text-align: center;
                    border: 1px solid rgba(255,255,255,0.12);
                }}

                tbody td {{
                    padding: 9px;
                    font-size: 12px;
                    text-align: center;
                    border: 1px solid #e5e7eb;
                }}

                tbody tr:nth-child(even) {{ background: #f8fafc; }}

                .col-idx {{ width: 52px; font-weight: 700; }}
                .col-phone {{ width: 160px; }}
                .col-status {{ width: 120px; }}
                .col-date {{ width: 150px; }}
                .col-name {{ text-align: right; }}

                .badge {{
                    display: inline-block;
                    padding: 3px 10px;
                    border-radius: 999px;
                    font-size: 11px;
                    font-weight: 700;
                }}

                .status-active {{ background: #dcfce7; color: #166534; }}
                .status-inactive {{ background: #fee2e2; color: #7f1d1d; }}
                .status-frozen {{ background: #e0f2fe; color: #075985; }}

                .footer {{
                    margin-top: 14px;
                    padding-top: 10px;
                    border-top: 2px solid #e5e7eb;
                    display: flex;
                    justify-content: space-between;
                    gap: 10px;
                    font-size: 11px;
                    color: #6b7280;
                }}

                @media print {{
                    .page {{ border-color: #d1d5db; }}
                }}
            </style>
        </head>
        <body>
            <div class=\"page\">
                <div class=\"header\">
                    <div style=\"width: 64px;\">{logo_block}</div>
                    <div class=\"title\">
                        <h1 class=\"app-name\">{club_name}</h1>
                        <p class=\"app-sub\">نظام إدارة الصالة الرياضية</p>
                    </div>
                    <div style=\"width: 64px;\"></div>
                </div>

                <div class=\"report-title\">📋 تقرير إجمالي الأعضاء</div>

                <div class=\"info\">
                    <div><strong>التاريخ:</strong> {current_date}</div>
                    <div><strong>الفترة:</strong> من {start_dmy} إلى {end_dmy}</div>
                </div>

                <div class=\"stats\">
                    <div class=\"stat\">
                        <div class=\"value\">{s_total}</div>
                        <div class=\"label\">إجمالي</div>
                    </div>
                    <div class=\"stat active\">
                        <div class=\"value\">{s_active}</div>
                        <div class=\"label\">نشط</div>
                    </div>
                    <div class=\"stat inactive\">
                        <div class=\"value\">{s_inactive}</div>
                        <div class=\"label\">غير نشط</div>
                    </div>
                    <div class=\"stat new\">
                        <div class=\"value\">{s_new}</div>
                        <div class=\"label\">جدد</div>
                    </div>
                    <div class=\"stat\">
                        <div class=\"value\">{s_deleted}</div>
                        <div class=\"label\">محذوف</div>
                    </div>
                </div>

                <table>
                    <thead>
                        <tr>
                            <th style=\"width:52px\">#</th>
                            <th>الاسم</th>
                            <th style=\"width:160px\">الهاتف</th>
                            <th style=\"width:120px\">الحالة</th>
                            <th style=\"width:150px\">تاريخ التسجيل</th>
                        </tr>
                    </thead>
                    <tbody>
                        {"".join(table_rows)}
                    </tbody>
                </table>

                <div class=\"footer\">
                    <span>طُبع بواسطة: {user_name}</span>
                    <span>الصفحة: 1 من 1</span>
                    <span>{club_name} - نظام إدارة النادي</span>
                </div>
            </div>

            <script>
                window.addEventListener('load', function () {{
                    try {{ window.print(); }} catch (e) {{}}
                }});
            </script>
        </body>
        </html>
        """
        return html_doc

    # ------------------------------
    # Helpers
    # ------------------------------

    def _set_summary(self, text: str) -> None:
        self.current_summary = text
        self.summary_label.configure(text=text)

    def _no_db(self) -> None:
        self._set_summary("قاعدة البيانات غير جاهزة")
        tb.Label(self.chart_frame, text="قاعدة البيانات غير جاهزة", font=FONTS["subheading"]).pack(pady=30)

    def _bind_shortcuts(self) -> None:
        top = self.winfo_toplevel()
        top.bind("<F5>", lambda _e: self.refresh_report())
        top.bind("<Control-e>", lambda _e: self.export_to_excel(self.current_data, self.current_columns) if self.current_columns else None)
        top.bind("<Control-s>", lambda _e: self.export_to_pdf(self.current_report_title, self.current_data, self.current_columns, summary=self.current_summary) if self.current_columns else None)
        top.bind("<Control-p>", lambda _e: self.print_report())


class ExportDialog(tk.Toplevel):
    """Small dialog to choose export format."""

    def __init__(self, parent: tk.Misc) -> None:
        super().__init__(parent)
        self.title("📥 تصدير التقرير")
        self.geometry("460x240")
        self.minsize(360, 220)
        self.resizable(True, True)
        self.grab_set()

        self.result: str | None = None

        container = tb.Frame(self, padding=14)
        container.pack(fill="both", expand=True)

        tb.Label(container, text="اختر صيغة التصدير:", font=FONTS["subheading"], anchor="e").pack(fill="x", pady=(0, 10))

        row = tb.Frame(container)
        row.pack(fill="x", pady=6)

        tb.Button(row, text="📗 Excel\n.xlsx", bootstyle="info", command=lambda: self._choose("excel")).pack(
            side="left", fill="both", expand=True, padx=6, ipady=10
        )
        tb.Button(row, text="📄 PDF\n.pdf", bootstyle="secondary", command=lambda: self._choose("pdf")).pack(
            side="left", fill="both", expand=True, padx=6, ipady=10
        )
        tb.Button(row, text="📋 CSV\n.csv", bootstyle="secondary", command=lambda: self._choose("csv")).pack(
            side="left", fill="both", expand=True, padx=6, ipady=10
        )

        tb.Button(container, text="إلغاء", bootstyle="secondary", command=self.destroy).pack(side="left", pady=(12, 0))

    def _choose(self, fmt: str) -> None:
        self.result = fmt
        self.destroy()


if __name__ == "__main__":
    root = tb.Window(themename="cosmo")
    root.title("ReportsFrame Test")
    db = DatabaseManager()
    frame = ReportsFrame(root, db, {"username": "admin"})
    frame.pack(fill="both", expand=True)
    root.geometry("1200x700")
    root.mainloop()
