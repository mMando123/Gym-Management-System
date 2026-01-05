"""Payments module frame for Gym Management System.

This module works with the existing database schema from database.py:
- payments(receipt_number, member_id, subscription_id, amount, payment_method, payment_date, notes, created_by, created_at)
- subscriptions(amount_paid, subscription_type_id, ...)
- subscription_types(price)

Some requested fields like payment_type/received_by/reference_number are not present in the
current schema; the UI derives operation type from context and stores any extra details in notes.

RTL Arabic UI.
"""

from __future__ import annotations
import html as html_lib
import os
import re
import threading
import tkinter as tk
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from tkinter import messagebox
from tkinter import ttk
from typing import Any

import ttkbootstrap as tb
from ttkbootstrap.constants import *  # noqa: F403
from ttkbootstrap.dialogs import Messagebox
from ttkbootstrap.widgets import DateEntry, Floodgauge, Meter

import config
from database import DatabaseManager
from utils import format_money, open_html_windows, print_html_windows, print_text_windows

try:
    import matplotlib

    matplotlib.use("TkAgg")
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
    from matplotlib.figure import Figure

    HAS_MATPLOTLIB = True
except Exception:
    HAS_MATPLOTLIB = False


# Local styling (to avoid circular imports)
COLORS = {
    "primary": "#2563eb",
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


def _iso_date(d: date) -> str:
    return d.isoformat()


def _fmt_money(amount: float, db: DatabaseManager | None = None) -> str:
    return format_money(amount, db=db, decimals=0)


def _generate_receipt_html(data: dict[str, Any], db: DatabaseManager | None = None) -> str:
    receipt = str(data.get("receipt_number") or "-")
    member = f"{data.get('member_code', '')} - {data.get('first_name', '')} {data.get('last_name', '')}".strip()
    phone = str(data.get("phone") or "-")
    amount = float(data.get("amount") or 0)
    method = str(data.get("payment_method") or "")
    method_ar = config.PAYMENT_METHODS.get(method, method)
    pay_date = str(data.get("payment_date") or "")
    notes = str(data.get("notes") or "").strip()
    plan_name = str(data.get("plan_name") or "").strip()
    sub_end = str(data.get("sub_end") or "").strip()

    club_name_raw = ""
    logo_path = ""
    if db is not None:
        try:
            club_name_raw = str(db.get_settings("gym.name") or "")
        except Exception:
            club_name_raw = ""
        try:
            logo_path = str(db.get_settings("gym.logo") or "")
        except Exception:
            logo_path = ""

    if not club_name_raw:
        club_name_raw = str(getattr(config, "APP_NAME", "نظام إدارة الصالة الرياضية") or "نظام إدارة الصالة الرياضية")

    logo_uri = ""
    try:
        if logo_path and os.path.exists(logo_path):
            logo_uri = Path(logo_path).resolve().as_uri()
    except Exception:
        logo_uri = ""

    club_name = club_name_raw
    system_sub = "نظام إدارة الصالة الرياضية"
    current_date = datetime.now().strftime("%d-%m-%Y")

    def esc(v: Any) -> str:
        return html_lib.escape(str(v))

    rows: list[tuple[str, str]] = []
    rows.append(("رقم الإيصال", receipt))
    rows.append(("التاريخ", pay_date))
    rows.append(("العضو", member or "-"))
    rows.append(("الهاتف", phone or "-"))
    if plan_name:
        rows.append(("الباقة", plan_name))
    if sub_end:
        rows.append(("انتهاء الاشتراك", sub_end))
    rows.append(("المبلغ", _fmt_money(amount, db=db)))
    rows.append(("طريقة الدفع", method_ar or "-"))
    if notes:
        rows.append(("ملاحظات", notes))

    logo_block = ""
    if logo_uri:
        logo_block = f"<img class=\"logo\" src=\"{logo_uri}\" alt=\"logo\">"
    else:
        logo_block = "<div class=\"logo-placeholder\">🏋️</div>"

    trs = "\n".join(
        [
            f"<tr><td class=\"k\">{esc(k)}</td><td class=\"v\">{esc(v)}</td></tr>"
            for k, v in rows
        ]
    )

    return f"""<!doctype html>
<html lang=\"ar\" dir=\"rtl\">
<head>
  <meta charset=\"utf-8\" />
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
  <title>{esc(club_name)} - إيصال {esc(receipt)}</title>
  <style>
    @page {{ size: A4; margin: 12mm; }}
    body {{ font-family: 'Cairo', 'Segoe UI', Tahoma, Arial, sans-serif; direction: rtl; color:#111827; }}
    .wrap {{ max-width: 820px; margin: 0 auto; }}
    .page {{ background: #ffffff; border: 1px solid #e5e7eb; border-radius: 14px; overflow: hidden; }}
    .header {{
      display: flex; align-items: center; justify-content: space-between;
      padding: 16px 18px; background: #f8fafc;
      border-bottom: 3px solid #2c3e50;
    }}
    .title {{ flex: 1; text-align: center; }}
    .app-name {{ margin: 0; font-size: 20px; font-weight: 800; color: #111827; }}
    .app-sub {{ margin: 4px 0 0; font-size: 13px; color: #6b7280; }}
    .report-title {{ margin: 10px 0 0; font-size: 18px; font-weight: 800; color: #2563eb; }}
    .meta {{ text-align: right; font-size: 12px; color: #374151; min-width: 220px; }}
    .meta div {{ margin: 2px 0; }}
    .logo {{ width: 64px; height: 64px; object-fit: contain; }}
    .logo-placeholder {{
      width: 64px; height: 64px; border-radius: 50%;
      background: #ffffff; border: 2px solid #e5e7eb;
      display: flex; align-items: center; justify-content: center;
      font-size: 28px;
    }}
    .content {{ padding: 16px 18px; }}
    table {{ width:100%; border-collapse:collapse; margin-top:10px; }}
    th, td {{ border:1px solid #e5e7eb; padding:10px; text-align:right; }}
    tr:nth-child(even) td {{ background:#f9fafb; }}
    td.k {{ width: 180px; font-weight:700; background:#f3f4f6; }}
    td.v {{ font-weight:600; }}
    .footer {{ margin-top:14px; color:#6b7280; font-size:12px; display:flex; justify-content:space-between; }}
    .actions {{ margin-top:12px; display:flex; gap:10px; }}
    .btn {{ border:1px solid #e5e7eb; padding:10px 12px; border-radius:10px; background:#ffffff; cursor:pointer; font-weight:700; }}
    .btn.primary {{ background:#2563eb; border-color:#2563eb; color:white; }}
    @media print {{ .actions {{ display:none; }} }}
  </style>
</head>
<body>
  <div class=\"wrap\">
    <div class=\"page\">
      <div class=\"header\">
        <div style=\"width: 64px;\">{logo_block}</div>
        <div class=\"title\">
          <h1 class=\"app-name\">{esc(club_name)}</h1>
          <p class=\"app-sub\">{esc(system_sub)}</p>
          <h2 class=\"report-title\">إيصال دفع</h2>
        </div>
        <div class=\"meta\">
          <div><strong>رقم الإيصال:</strong> {esc(receipt)}</div>
          <div><strong>تاريخ الطباعة:</strong> {esc(current_date)}</div>
        </div>
      </div>

      <div class=\"content\">
        <table>
          <tbody>
            {trs}
          </tbody>
        </table>

        <div class=\"actions\">
          <button class=\"btn primary\" onclick=\"window.print()\">طباعة</button>
          <button class=\"btn\" onclick=\"window.close()\">إغلاق</button>
        </div>

        <div class=\"footer\">
          <div>تم الإنشاء تلقائياً</div>
          <div>{esc(pay_date)}</div>
        </div>
      </div>
    </div>
  </div>
</body>
</html>"""


def _generate_daily_cash_register_html(
    db: DatabaseManager,
    today: str,
    total: float,
    by: dict[str, float],
    count: int,
    avg: float,
) -> str:
    club_name_raw = ""
    logo_path = ""
    try:
        club_name_raw = str(db.get_settings("gym.name") or "")
    except Exception:
        club_name_raw = ""
    try:
        logo_path = str(db.get_settings("gym.logo") or "")
    except Exception:
        logo_path = ""

    if not club_name_raw:
        club_name_raw = str(getattr(config, "APP_NAME", "نظام إدارة الصالة الرياضية") or "نظام إدارة الصالة الرياضية")

    logo_uri = ""
    try:
        if logo_path and os.path.exists(logo_path):
            logo_uri = Path(logo_path).resolve().as_uri()
    except Exception:
        logo_uri = ""

    def esc(v: Any) -> str:
        return html_lib.escape(str(v))

    logo_block = ""
    if logo_uri:
        logo_block = f"<img class=\"logo\" src=\"{logo_uri}\" alt=\"logo\">"
    else:
        logo_block = "<div class=\"logo-placeholder\">🏋️</div>"

    current_date = datetime.now().strftime("%d-%m-%Y")
    system_sub = "نظام إدارة الصالة الرياضية"

    rows = [
        ("إجمالي المقبوضات", _fmt_money(float(total), db=db)),
        ("نقدي", _fmt_money(float(by.get("cash", 0.0)), db=db)),
        ("بطاقة", _fmt_money(float(by.get("card", 0.0)), db=db)),
        ("تحويل", _fmt_money(float(by.get("transfer", 0.0)), db=db)),
        ("شيك", _fmt_money(float(by.get("cheque", 0.0)), db=db)),
        ("عدد العمليات", str(int(count))),
        ("متوسط العملية", _fmt_money(float(avg), db=db)),
    ]

    trs = "\n".join([f"<tr><td class=\"k\">{esc(k)}</td><td class=\"v\">{esc(v)}</td></tr>" for k, v in rows])

    return f"""<!doctype html>
<html lang=\"ar\" dir=\"rtl\">
<head>
  <meta charset=\"utf-8\" />
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
  <title>{esc(club_name_raw)} - تقرير الصندوق اليومي</title>
  <style>
    @page {{ size: A4; margin: 12mm; }}
    body {{ font-family: 'Cairo', 'Segoe UI', Tahoma, Arial, sans-serif; direction: rtl; color:#111827; }}
    .wrap {{ max-width: 820px; margin: 0 auto; }}
    .page {{ background: #ffffff; border: 1px solid #e5e7eb; border-radius: 14px; overflow: hidden; }}
    .header {{
      display: flex; align-items: center; justify-content: space-between;
      padding: 16px 18px; background: #f8fafc;
      border-bottom: 3px solid #2c3e50;
    }}
    .title {{ flex: 1; text-align: center; }}
    .app-name {{ margin: 0; font-size: 20px; font-weight: 800; color: #111827; }}
    .app-sub {{ margin: 4px 0 0; font-size: 13px; color: #6b7280; }}
    .report-title {{ margin: 10px 0 0; font-size: 18px; font-weight: 800; color: #2563eb; }}
    .meta {{ text-align: right; font-size: 12px; color: #374151; min-width: 240px; }}
    .meta div {{ margin: 2px 0; }}
    .logo {{ width: 64px; height: 64px; object-fit: contain; }}
    .logo-placeholder {{
      width: 64px; height: 64px; border-radius: 50%;
      background: #ffffff; border: 2px solid #e5e7eb;
      display: flex; align-items: center; justify-content: center;
      font-size: 28px;
    }}
    .content {{ padding: 16px 18px; }}
    table {{ width:100%; border-collapse:collapse; margin-top:10px; }}
    th, td {{ border:1px solid #e5e7eb; padding:10px; text-align:right; }}
    tr:nth-child(even) td {{ background:#f9fafb; }}
    td.k {{ width: 220px; font-weight:700; background:#f3f4f6; }}
    td.v {{ font-weight:600; }}
    .footer {{ margin-top:14px; color:#6b7280; font-size:12px; display:flex; justify-content:space-between; }}
    .actions {{ margin-top:12px; display:flex; gap:10px; }}
    .btn {{ border:1px solid #e5e7eb; padding:10px 12px; border-radius:10px; background:#ffffff; cursor:pointer; font-weight:700; }}
    .btn.primary {{ background:#2563eb; border-color:#2563eb; color:white; }}
    @media print {{ .actions {{ display:none; }} }}
  </style>
</head>
<body>
  <div class=\"wrap\">
    <div class=\"page\">
      <div class=\"header\">
        <div style=\"width: 64px;\">{logo_block}</div>
        <div class=\"title\">
          <h1 class=\"app-name\">{esc(club_name_raw)}</h1>
          <p class=\"app-sub\">{esc(system_sub)}</p>
          <h2 class=\"report-title\">تقرير الصندوق اليومي</h2>
        </div>
        <div class=\"meta\">
          <div><strong>التاريخ:</strong> {esc(today)}</div>
          <div><strong>تاريخ الطباعة:</strong> {esc(current_date)}</div>
        </div>
      </div>

      <div class=\"content\">
        <table>
          <tbody>
            {trs}
          </tbody>
        </table>

        <div class=\"actions\">
          <button class=\"btn primary\" onclick=\"window.print()\">طباعة</button>
          <button class=\"btn\" onclick=\"window.close()\">إغلاق</button>
        </div>

        <div class=\"footer\">
          <div>تم الإنشاء تلقائياً</div>
          <div>{esc(today)}</div>
        </div>
      </div>
    </div>
  </div>
</body>
</html>"""


def _month_start(d: date) -> date:
    return date(d.year, d.month, 1)


class PaymentsFrame(tb.Frame):
    """Payments and financial operations frame."""

    def __init__(self, parent: ttk.Widget, db: DatabaseManager | None, user_data: dict | None = None) -> None:
        super().__init__(parent)
        self.db = db
        self.user_data = user_data or {}

        self._main_loading: bool = False

        self.breakpoint: str = "desktop"

        self._rows: list[dict[str, Any]] = []
        self._sort_col: str | None = None
        self._sort_desc: bool = False

        self.setup_variables()
        self.create_layout()

        self.load_financial_summary()
        self.load_payments_data(filters=self._collect_filters())

        self._bind_shortcuts()

    # ------------------------------
    # Setup
    # ------------------------------

    def setup_variables(self) -> None:
        today = date.today()
        start = _month_start(today)

        self.filter_start_var = tk.StringVar(master=self, value=start.isoformat())
        self.filter_end_var = tk.StringVar(master=self, value=today.isoformat())
        self.filter_method_var = tk.StringVar(master=self, value="الكل")
        self.filter_type_var = tk.StringVar(master=self, value="الكل")
        self.filter_search_var = tk.StringVar(master=self, value="")
        self.filter_show_paid_var = tk.BooleanVar(master=self, value=True)

        # Summary vars
        self.today_total_var = tk.StringVar(master=self, value="0")
        self.today_count_var = tk.StringVar(master=self, value="0")
        self.today_cash_var = tk.StringVar(master=self, value="0")
        self.today_card_var = tk.StringVar(master=self, value="0")
        self.today_transfer_var = tk.StringVar(master=self, value="0")

        self.month_total_var = tk.StringVar(master=self, value="0")
        self.dues_total_var = tk.StringVar(master=self, value="0")
        self.dues_members_var = tk.StringVar(master=self, value="0")

        # Quick payment
        self.quick_member_search_var = tk.StringVar(master=self, value="")
        self.quick_amount_var = tk.StringVar(master=self, value="")
        self.quick_method_var = tk.StringVar(master=self, value="cash")
        self.quick_notes_var = tk.StringVar(master=self, value="")

        self._quick_saving: bool = False

        self.quick_selected_member: dict[str, Any] | None = None
        self.quick_suggest_var = tk.StringVar(master=self, value="")

        # Monthly target
        self.month_target: float = 15000.0

    def create_layout(self) -> None:
        self.configure(padding=10)

        main = ttk.Panedwindow(self, orient=tk.HORIZONTAL)
        main.pack(fill="both", expand=True)

        # Left (table + filters)
        self.left = tb.Frame(main, padding=10)
        main.add(self.left, weight=7)

        # Right (summary)
        self.right = tb.Frame(main, padding=10)
        main.add(self.right, weight=3)

        # Bottom (quick entry)
        self.bottom = tb.Labelframe(self, text="💰 تسجيل دفعة سريعة", padding=12)
        self.bottom.pack(fill="x", pady=(10, 0))

        self._build_left_panel()
        self._build_right_panel()
        self._build_bottom_panel()

        self._apply_responsive_layout()

    def _on_tree_shift_wheel(self, e) -> str:
        try:
            delta = int(-1 * (e.delta / 120))
        except Exception:
            delta = 0
        if delta:
            try:
                self.tree.xview_scroll(delta, "units")
            except Exception:
                pass
        return "break"

    def on_breakpoint_change(self, breakpoint: str) -> None:
        self.breakpoint = breakpoint
        self._apply_responsive_layout()
        try:
            self._layout_filter_controls()
        except Exception:
            pass
        self._render_payments_cards()

    # ------------------------------
    # Left panel
    # ------------------------------

    def _build_left_panel(self) -> None:
        self._create_filter_bar(self.left)
        self._create_payments_table(self.left)

    def _create_filter_bar(self, parent: ttk.Widget) -> None:
        bar = tb.Frame(parent)
        bar.pack(fill="x", pady=(0, 10))

        self.filter_controls = tb.Frame(bar)
        self.filter_controls.pack(fill="x")

        self.filter_actions = tb.Frame(bar)
        self.filter_actions.pack(fill="x", pady=(6, 0))

        self.lbl_start = tb.Label(self.filter_controls, text="من تاريخ", font=("Cairo", 10, "bold"))
        self.start_entry = DateEntry(self.filter_controls, bootstyle="info", width=12, dateformat="%Y-%m-%d")

        self.lbl_end = tb.Label(self.filter_controls, text="إلى تاريخ", font=("Cairo", 10, "bold"))
        self.end_entry = DateEntry(self.filter_controls, bootstyle="info", width=12, dateformat="%Y-%m-%d")

        # Initialize date widgets
        try:
            self.start_entry.date = datetime.strptime(self.filter_start_var.get(), config.DATE_FORMAT).date()
        except Exception:
            try:
                self.start_entry.date = _month_start(date.today())
            except Exception:
                pass

        try:
            self.end_entry.date = datetime.strptime(self.filter_end_var.get(), config.DATE_FORMAT).date()
        except Exception:
            try:
                self.end_entry.date = date.today()
            except Exception:
                pass

        self.lbl_method = tb.Label(self.filter_controls, text="طريقة الدفع", font=("Cairo", 10, "bold"))
        method_values = ["الكل", "نقدي", "بطاقة", "تحويل بنكي", "شيك"]
        self.method_combo = tb.Combobox(
            self.filter_controls,
            textvariable=self.filter_method_var,
            values=method_values,
            state="readonly",
            width=12,
            justify="right",
        )

        self.lbl_type = tb.Label(self.filter_controls, text="نوع العملية", font=("Cairo", 10, "bold"))
        type_values = ["الكل", "اشتراك", "دفعة جزئية", "استرداد", "أخرى"]
        self.type_combo = tb.Combobox(
            self.filter_controls,
            textvariable=self.filter_type_var,
            values=type_values,
            state="readonly",
            width=12,
            justify="right",
        )

        self.lbl_search = tb.Label(self.filter_controls, text="بحث", font=("Cairo", 10, "bold"))
        self.search_entry = tb.Entry(self.filter_controls, textvariable=self.filter_search_var, justify="right")
        self.btn_search = tb.Button(self.filter_controls, text="بحث", bootstyle="secondary", command=self.apply_filters)

        self.show_paid_check = tb.Checkbutton(
            self.filter_controls,
            text="إظهار المدفوعة",
            variable=self.filter_show_paid_var,
            bootstyle="secondary",
            command=self.apply_filters,
        )

        self._lbl_show_paid_spacer = tb.Label(self.filter_controls, text="", font=("Cairo", 10, "bold"))

        self.btn_apply = tb.Button(self.filter_controls, text="تطبيق", bootstyle="primary", command=self.apply_filters)
        self.btn_clear = tb.Button(self.filter_controls, text="مسح", bootstyle="secondary", command=self.clear_filters)

        tb.Button(
            self.filter_actions,
            text="⚠️ المستحقات",
            bootstyle="warning",
            command=self.show_outstanding_dues,
        ).pack(side="left")
        tb.Button(
            self.filter_actions,
            text="✅ الفواتير المدفوعة",
            bootstyle="secondary",
            command=self.show_paid_invoices,
        ).pack(side="left", padx=6)
        tb.Button(
            self.filter_actions,
            text="📋 تقرير الصندوق",
            bootstyle="info",
            command=self.show_daily_cash_register,
        ).pack(side="left", padx=6)
        tb.Button(
            self.filter_actions,
            text="➕ تسجيل دفعة",
            bootstyle="success",
            command=self.open_record_payment_dialog,
        ).pack(side="left", padx=6)

        self._main_refresh_status_var = tk.StringVar(master=self, value="")
        self._main_refresh_status_label = tb.Label(
            self.filter_actions,
            textvariable=self._main_refresh_status_var,
            font=FONTS["small"],
            anchor="e",
        )
        self._main_refresh_status_label.pack(side="right")

        self._main_refresh_spinner = ttk.Progressbar(self.filter_actions, mode="indeterminate", length=120)
        self._main_refresh_spinner.pack(side="right", padx=6)
        self._main_refresh_spinner.stop()
        self._main_refresh_spinner.pack_forget()

        self.btn_refresh_main = tb.Button(
            self.filter_actions,
            text="🔄 تحديث",
            bootstyle="primary",
            command=self.refresh_main,
        )
        self.btn_refresh_main.pack(side="right", padx=6)

        self._layout_filter_controls()

    def _set_main_loading(self, value: bool) -> None:
        self._main_loading = bool(value)
        try:
            if self._main_loading:
                self.btn_refresh_main.configure(state="disabled")
                self._main_refresh_spinner.pack(side="right", padx=6)
                self._main_refresh_spinner.start(12)
                self._main_refresh_status_var.set("جاري التحديث...")
            else:
                self._main_refresh_spinner.stop()
                self._main_refresh_spinner.pack_forget()
                self.btn_refresh_main.configure(state="normal")
        except Exception:
            pass

    def _toast_main_success(self, msg: str) -> None:
        try:
            self._main_refresh_status_var.set(msg)

            def clear() -> None:
                try:
                    self._main_refresh_status_var.set("")
                except Exception:
                    pass

            self.after(1600, clear)
        except Exception:
            pass

    def refresh_main(self) -> None:
        if self.db is None:
            return
        if self._main_loading:
            return

        filters = dict(self._collect_filters())
        sort_col = self._sort_col
        sort_desc = self._sort_desc

        self._set_main_loading(True)

        def worker() -> None:
            try:
                query = """
                    SELECT p.id,
                           p.receipt_number,
                           p.payment_date,
                           p.amount,
                           p.payment_method,
                           p.notes,
                           p.created_by,
                           m.first_name,
                           m.last_name,
                           m.phone,
                           p.subscription_id,
                           p.created_at,
                           s.invoice_status AS sub_invoice_status,
                           s.amount_paid AS sub_amount_paid,
                           st.price AS sub_total
                    FROM payments p
                    JOIN members m ON m.id = p.member_id
                    LEFT JOIN subscriptions s ON s.id = p.subscription_id
                    LEFT JOIN subscription_types st ON st.id = s.subscription_type_id
                    WHERE 1=1
                """
                params: list[Any] = []

                # Hide invalid/legacy zero-amount rows to reduce confusion in the list.
                query += " AND ABS(COALESCE(p.amount, 0)) > 0.01"

                if filters.get("start_date"):
                    query += " AND date(p.payment_date) >= date(?)"
                    params.append(filters["start_date"])
                if filters.get("end_date"):
                    query += " AND date(p.payment_date) <= date(?)"
                    params.append(filters["end_date"])
                if filters.get("payment_method") and filters["payment_method"] != "الكل":
                    query += " AND p.payment_method = ?"
                    params.append(filters["payment_method"])
                if filters.get("search"):
                    query += " AND ((m.first_name || ' ' || m.last_name) LIKE ? OR p.receipt_number LIKE ?)"
                    s = f"%{filters['search']}%"
                    params.extend([s, s])

                # Default: hide records linked to fully-paid subscriptions to reduce clutter.
                if not filters.get("show_paid"):
                    query += " AND (p.subscription_id IS NULL OR COALESCE(s.invoice_status, 'unpaid') != 'paid')"

                query += " ORDER BY datetime(p.created_at) DESC, p.id DESC LIMIT 500"

                today = date.today().isoformat()
                ms = _month_start(date.today()).isoformat()

                with self.db.get_connection() as conn:
                    payments_rows = conn.execute(query, tuple(params)).fetchall()

                    cur = conn.cursor()
                    today_total = cur.execute(
                        "SELECT COALESCE(SUM(amount), 0) AS total FROM payments WHERE date(payment_date) = date(?)",
                        (today,),
                    ).fetchone()["total"]
                    today_count = cur.execute(
                        "SELECT COUNT(*) AS c FROM payments WHERE date(payment_date) = date(?)",
                        (today,),
                    ).fetchone()["c"]

                    method_rows = cur.execute(
                        """
                        SELECT payment_method, COALESCE(SUM(amount), 0) AS total
                        FROM payments
                        WHERE date(payment_date) = date(?)
                        GROUP BY payment_method
                        """,
                        (today,),
                    ).fetchall()

                    by_method = {"cash": 0.0, "card": 0.0, "transfer": 0.0}
                    for r in method_rows:
                        k = str(r["payment_method"] or "")
                        if k in by_method:
                            by_method[k] = float(r["total"] or 0)

                    month_total = cur.execute(
                        "SELECT COALESCE(SUM(amount), 0) AS total FROM payments WHERE date(payment_date) >= date(?)",
                        (ms,),
                    ).fetchone()["total"]

                    dues_rows = cur.execute(
                        """
                        SELECT s.member_id, st.price AS total, s.amount_paid AS paid
                        FROM subscriptions s
                        JOIN subscription_types st ON st.id = s.subscription_type_id
                        WHERE s.status != 'cancelled'
                        """
                    ).fetchall()

                    month_method_rows = cur.execute(
                        """
                        SELECT payment_method, COALESCE(SUM(amount), 0) AS total
                        FROM payments
                        WHERE date(payment_date) >= date(?)
                        GROUP BY payment_method
                        """,
                        (ms,),
                    ).fetchall()

                    end = date.today()
                    start = end - timedelta(days=6)
                    chart_rows = cur.execute(
                        """
                        SELECT date(payment_date) AS d, COALESCE(SUM(amount), 0) AS total
                        FROM payments
                        WHERE date(payment_date) BETWEEN date(?) AND date(?)
                        GROUP BY date(payment_date)
                        ORDER BY date(payment_date) ASC
                        """,
                        (start.isoformat(), end.isoformat()),
                    ).fetchall()

                dues_total = 0.0
                overdue_members = set()
                for r in dues_rows:
                    total = float(r["total"] or 0)
                    paid = float(r["paid"] or 0)
                    rem = total - paid
                    if rem > 0.01:
                        dues_total += rem
                        overdue_members.add(int(r["member_id"]))

                month_method_totals = {"cash": 0.0, "card": 0.0, "transfer": 0.0}
                for r in month_method_rows:
                    k = str(r["payment_method"] or "")
                    if k in month_method_totals:
                        month_method_totals[k] = float(r["total"] or 0)

                totals_map = {str(r["d"]): float(r["total"] or 0) for r in chart_rows}
                labels: list[str] = []
                values: list[float] = []
                for i in range(7):
                    d = start + timedelta(days=i)
                    labels.append(d.strftime("%d/%m"))
                    values.append(totals_map.get(d.isoformat(), 0.0))

                prepared_rows = [dict(r) for r in payments_rows]

                def apply() -> None:
                    try:
                        self._rows = prepared_rows

                        if filters.get("operation_type") and filters["operation_type"] != "الكل":
                            op = filters["operation_type"]
                            self._rows = [r for r in self._rows if self._derive_operation_type(r) == op]

                        self._sort_col = sort_col
                        self._sort_desc = sort_desc
                        if self._sort_col:
                            self._rows = self._sorted_rows(self._rows, self._sort_col, self._sort_desc)

                        self._render_payments_table()
                        self._render_payments_cards()

                        self.today_total_var.set(_fmt_money(float(today_total), db=self.db))
                        self.today_count_var.set(str(int(today_count)))
                        self.today_cash_var.set(_fmt_money(by_method["cash"], db=self.db))
                        self.today_card_var.set(_fmt_money(by_method["card"], db=self.db))
                        self.today_transfer_var.set(_fmt_money(by_method["transfer"], db=self.db))

                        self.today_breakdown_label.configure(
                            text=f"نقدي: {self.today_cash_var.get()} | بطاقة: {self.today_card_var.get()} | تحويل: {self.today_transfer_var.get()}"
                        )
                        self.today_count_label.configure(text=f"عدد العمليات: {self.today_count_var.get()}")

                        self.month_total_var.set(_fmt_money(float(month_total), db=self.db))

                        pct = 0
                        try:
                            pct = int(min(100, max(0, (float(month_total) / self.month_target) * 100)))
                        except Exception:
                            pct = 0
                        try:
                            self.month_gauge.configure(value=pct)
                        except Exception:
                            pass

                        self.dues_total_var.set(_fmt_money(float(dues_total), db=self.db))
                        self.dues_members_var.set(f"{len(overdue_members)} أعضاء متأخرين")

                        total_sum = sum(max(0.0, v) for v in month_method_totals.values())
                        for k, m in self.method_bars.items():
                            p = 0
                            if total_sum > 0:
                                p = int((max(0.0, month_method_totals.get(k, 0.0)) / total_sum) * 100)
                            try:
                                self._set_meter_value(m, p)
                            except Exception:
                                pass

                        if HAS_MATPLOTLIB:
                            try:
                                self.ax.clear()
                                self.ax.plot(labels, values, color="#2563eb", linewidth=2)
                                self.ax.set_ylim(bottom=0)
                                self.ax.grid(True, alpha=0.3)
                                self.canvas.draw()
                            except Exception:
                                pass
                    finally:
                        self._set_main_loading(False)
                        self._toast_main_success("تم تحديث البيانات بنجاح")

                self.after(0, apply)
            except Exception as e:
                def fail() -> None:
                    self._set_main_loading(False)
                    try:
                        messagebox.showerror("خطأ", f"فشل تحديث البيانات: {e}", parent=self)
                    except Exception:
                        pass

                self.after(0, fail)

        threading.Thread(target=worker, daemon=True).start()

    def _layout_filter_controls(self) -> None:
        if not hasattr(self, "filter_controls"):
            return

        widgets = [
            self.lbl_start,
            self.start_entry,
            self.lbl_end,
            self.end_entry,
            self.lbl_method,
            self.method_combo,
            self.lbl_type,
            self.type_combo,
            self.show_paid_check,
            self.lbl_search,
            self.search_entry,
            self.btn_search,
            self.btn_apply,
            self.btn_clear,
        ]

        for w in widgets:
            try:
                w.grid_forget()
            except Exception:
                pass
            try:
                w.pack_forget()
            except Exception:
                pass

        if hasattr(self, "_search_row"):
            try:
                self._search_row.grid_forget()
            except Exception:
                pass

        if hasattr(self, "_mobile_btns_row"):
            try:
                self._mobile_btns_row.grid_forget()
            except Exception:
                pass

        for i in range(20):
            try:
                self.filter_controls.columnconfigure(i, weight=0)
            except Exception:
                pass

        if getattr(self, "breakpoint", "desktop") == "mobile":
            self.filter_controls.columnconfigure(0, weight=1)

            row = 0
            pairs = [
                (self.lbl_start, self.start_entry),
                (self.lbl_end, self.end_entry),
                (self.lbl_method, self.method_combo),
                (self.lbl_type, self.type_combo),
                (self._lbl_show_paid_spacer, self.show_paid_check),
            ]
            for lbl, field in pairs:
                lbl.grid(row=row, column=1, sticky="e", padx=(0, 6), pady=3)
                field.grid(row=row, column=0, sticky="ew", pady=3)
                row += 1

            if not hasattr(self, "_mobile_btns_row") or not self._mobile_btns_row.winfo_exists():
                self._mobile_btns_row = tb.Frame(self.filter_controls)
            btns = self._mobile_btns_row
            btns.grid(row=row, column=0, columnspan=2, sticky="ew", pady=(6, 0))
            btns.columnconfigure(0, weight=1)
            try:
                self.btn_clear.pack_forget()
                self.btn_apply.pack_forget()
                self.btn_search.pack_forget()
            except Exception:
                pass
            self.btn_search.pack(in_=btns, side="right", padx=6)
            self.btn_apply.pack(in_=btns, side="right", padx=6)
            self.btn_clear.pack(in_=btns, side="right", padx=6)
            return

        self.filter_controls.columnconfigure(0, weight=1)
        self.lbl_start.grid(row=0, column=9, sticky="e", padx=(0, 6), pady=3)
        self.start_entry.grid(row=0, column=8, sticky="w", padx=(0, 12), pady=3)
        self.lbl_end.grid(row=0, column=7, sticky="e", padx=(0, 6), pady=3)
        self.end_entry.grid(row=0, column=6, sticky="w", padx=(0, 12), pady=3)
        self.lbl_method.grid(row=0, column=5, sticky="e", padx=(0, 6), pady=3)
        self.method_combo.grid(row=0, column=4, sticky="w", padx=(0, 12), pady=3)
        self.lbl_type.grid(row=0, column=3, sticky="e", padx=(0, 6), pady=3)
        self.type_combo.grid(row=0, column=2, sticky="w", padx=(0, 12), pady=3)
        self.show_paid_check.grid(row=0, column=1, sticky="w", padx=(0, 12), pady=3)

        if not hasattr(self, "_search_row") or not self._search_row.winfo_exists():
            self._search_row = tb.Frame(self.filter_controls)

        self._search_row.grid(row=1, column=0, columnspan=10, sticky="ew", pady=3)
        self._search_row.columnconfigure(0, weight=1)

        for w in self._search_row.winfo_children():
            try:
                w.grid_forget()
            except Exception:
                pass

        self.search_entry.grid(row=0, column=0, sticky="ew", padx=(0, 12))
        self.lbl_search.grid(row=0, column=1, sticky="e", padx=(0, 6))
        self.btn_search.grid(row=0, column=2, sticky="w", padx=6)
        self.btn_apply.grid(row=0, column=3, sticky="w", padx=6)
        self.btn_clear.grid(row=0, column=4, sticky="w", padx=6)

    def _create_payments_table(self, parent: ttk.Widget) -> None:
        wrap = tb.Frame(parent)
        wrap.pack(fill="both", expand=True)
        self.table_wrap = wrap

        columns = (
            "receipt",
            "date",
            "time",
            "member",
            "op_type",
            "amount",
            "remaining",
            "method",
            "received_by",
            "notes",
        )

        self.tree = ttk.Treeview(wrap, columns=columns, show="headings", selectmode="browse")

        headers = {
            "receipt": ("رقم الإيصال", 220, "center"),
            "date": ("التاريخ", 110, "center"),
            "time": ("الوقت", 90, "center"),
            "member": ("اسم العضو", 200, "e"),
            "op_type": ("نوع العملية", 110, "center"),
            "amount": ("المبلغ", 100, "center"),
            "remaining": ("المتبقي", 100, "center"),
            "method": ("طريقة الدفع", 100, "center"),
            "received_by": ("المستلم", 90, "center"),
            "notes": ("ملاحظات", 220, "e"),
        }

        for col, (txt, w, anchor) in headers.items():
            self.tree.heading(col, text=txt, command=lambda c=col: self.sort_by_column(c))
            self.tree.column(col, width=w, minwidth=w, anchor=anchor, stretch=False)

        try:
            self.tree.column("receipt", width=220, minwidth=220, anchor="center", stretch=False)
        except Exception:
            pass

        self.tree_vsb = ttk.Scrollbar(wrap, orient="vertical", command=self.tree.yview)
        self.tree_hsb = ttk.Scrollbar(wrap, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=self.tree_vsb.set, xscrollcommand=self.tree_hsb.set)

        self.tree.pack(side="left", fill="both", expand=True)
        self.tree_vsb.pack(side="right", fill="y")
        self.tree_hsb.pack(side="bottom", fill="x")

        self.cards_canvas = tk.Canvas(wrap, highlightthickness=0)
        self.cards_vsb = ttk.Scrollbar(wrap, orient="vertical", command=self.cards_canvas.yview)
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

        self.tree.tag_configure("refund", foreground=COLORS["danger"])
        self.tree.tag_configure("large", font=("Cairo", 10, "bold"))
        self.tree.tag_configure("paid_invoice", background="#dcfce7")
        self.tree.tag_configure("unpaid_invoice", background="#fee2e2")

        self.tree.bind("<Double-1>", lambda _e: self.view_selected_receipt())
        self.tree.bind("<Return>", lambda _e: self.view_selected_receipt())
        self.tree.bind("<Shift-MouseWheel>", self._on_tree_shift_wheel, add=True)

        self.context_menu = tk.Menu(self, tearoff=0)
        self.context_menu.add_command(label="عرض الإيصال", command=self.view_selected_receipt)
        self.context_menu.add_command(label="طباعة", command=self.print_selected_receipt)
        self.context_menu.add_separator()
        self.context_menu.add_command(label="تعديل", command=self.edit_selected_payment)
        self.context_menu.add_command(label="حذف", command=self.delete_selected_payment)
        self.tree.bind("<Button-3>", self._show_context_menu)

        self._apply_responsive_layout()

    def _apply_responsive_layout(self) -> None:
        try:
            if self.breakpoint == "mobile":
                try:
                    self.tree.pack_forget()
                    self.tree_vsb.pack_forget()
                    self.tree_hsb.pack_forget()
                except Exception:
                    pass

                self.cards_canvas.pack(side="left", fill="both", expand=True)
                self.cards_vsb.pack(side="right", fill="y")
            else:
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

    # ------------------------------
    # Right panel (summary)
    # ------------------------------

    def _build_right_panel(self) -> None:
        self._create_today_card(self.right)
        self._create_month_card(self.right)
        self._create_dues_card(self.right)
        self._create_methods_breakdown(self.right)

        if HAS_MATPLOTLIB:
            self._create_optional_chart(self.right)

    def _create_today_card(self, parent: ttk.Widget) -> None:
        card = tb.Frame(parent, padding=12, bootstyle="secondary")
        card.pack(fill="x", pady=(0, 10))

        tb.Label(card, text="📅 إيرادات اليوم", font=FONTS["subheading"], anchor="e").pack(fill="x")
        tb.Label(card, textvariable=self.today_total_var, font=("Cairo", 18, "bold"), anchor="e").pack(fill="x")
        tb.Separator(card).pack(fill="x", pady=8)
        tb.Label(
            card,
            textvariable=tk.StringVar(master=self, value=""),
            font=FONTS["small"],
        )

        self.today_breakdown_label = tb.Label(
            card,
            text="",
            font=FONTS["small"],
            foreground=COLORS["text_light"],
            anchor="e",
            justify="right",
        )
        self.today_breakdown_label.pack(fill="x")

        self.today_count_label = tb.Label(
            card,
            text="",
            font=FONTS["small"],
            foreground=COLORS["text_light"],
            anchor="e",
            justify="right",
        )
        self.today_count_label.pack(fill="x", pady=(4, 0))

    def _create_month_card(self, parent: ttk.Widget) -> None:
        card = tb.Frame(parent, padding=12, bootstyle="secondary")
        card.pack(fill="x", pady=(0, 10))

        tb.Label(card, text="📊 إيرادات الشهر", font=FONTS["subheading"], anchor="e").pack(fill="x")
        tb.Label(card, textvariable=self.month_total_var, font=("Cairo", 18, "bold"), anchor="e").pack(fill="x")

        tb.Separator(card).pack(fill="x", pady=8)
        tb.Label(card, text=f"الهدف: {_fmt_money(self.month_target, db=self.db)}", font=FONTS["small"], anchor="e").pack(fill="x")

        self.month_gauge = Floodgauge(
            card,
            bootstyle="success",
            mask="{}%",
            maximum=100,
            value=0,
            length=240,
        )
        self.month_gauge.pack(fill="x", pady=(6, 0))

    def _create_dues_card(self, parent: ttk.Widget) -> None:
        card = tb.Frame(parent, padding=12, bootstyle="secondary")
        card.pack(fill="x", pady=(0, 10))

        tb.Label(card, text="⚠️ المبالغ المستحقة", font=FONTS["subheading"], anchor="e").pack(fill="x")
        tb.Label(card, textvariable=self.dues_total_var, font=("Cairo", 18, "bold"), anchor="e").pack(fill="x")

        tb.Separator(card).pack(fill="x", pady=8)
        tb.Label(card, textvariable=self.dues_members_var, font=FONTS["small"], foreground=COLORS["text_light"], anchor="e").pack(
            fill="x"
        )
        tb.Button(card, text="عرض التفاصيل", bootstyle="warning", command=self.show_outstanding_dues).pack(pady=(8, 0))

    def _create_methods_breakdown(self, parent: ttk.Widget) -> None:
        card = tb.Frame(parent, padding=12, bootstyle="secondary")
        card.pack(fill="x")

        tb.Label(card, text="تفصيل طرق الدفع", font=FONTS["subheading"], anchor="e").pack(fill="x")
        self.methods_container = tb.Frame(card)
        self.methods_container.pack(fill="x", pady=(8, 0))

        self.method_bars: dict[str, object] = {}
        for key, label in [("cash", "نقدي"), ("card", "بطاقة"), ("transfer", "تحويل")]:
            row = tb.Frame(self.methods_container)
            row.pack(fill="x", pady=4)
            tb.Label(row, text=label, font=FONTS["small"], anchor="e").pack(side="right")
            w: object | None = None
            try:
                w = Meter(row, metersize=60, amounttotal=100, amountused=0, metertype="semi", bootstyle="info")
                w.pack(side="left")  # type: ignore[attr-defined]
            except Exception:
                w = tb.Progressbar(row, maximum=100, value=0, length=90, bootstyle="info")
                w.pack(side="left", padx=(6, 0))
            self.method_bars[key] = w

    def _set_meter_value(self, widget: object, pct: int) -> None:
        try:
            widget.configure(amountused=int(pct))  # type: ignore[attr-defined]
            return
        except Exception:
            pass
        try:
            widget.configure(value=int(pct))  # type: ignore[attr-defined]
            return
        except Exception:
            pass
        try:
            widget["value"] = int(pct)  # type: ignore[index]
        except Exception:
            pass

    def _create_optional_chart(self, parent: ttk.Widget) -> None:
        card = tb.Frame(parent, padding=12, bootstyle="secondary")
        card.pack(fill="x", pady=(10, 0))
        tb.Label(card, text="📈 آخر 7 أيام", font=FONTS["subheading"], anchor="e").pack(fill="x")

        fig = Figure(figsize=(3.2, 1.6), dpi=100)
        self.ax = fig.add_subplot(111)
        self.ax.set_facecolor("#ffffff")
        self.ax.tick_params(labelsize=7)

        self.canvas = FigureCanvasTkAgg(fig, master=card)
        self.canvas.get_tk_widget().pack(fill="x")

    # ------------------------------
    # Bottom panel (quick entry)
    # ------------------------------

    def _build_bottom_panel(self) -> None:
        row = tb.Frame(self.bottom)
        row.pack(fill="x")

        # Member search
        tb.Label(row, text="بحث العضو", font=("Cairo", 10, "bold")).pack(side="right", padx=(0, 6))
        self.quick_member_entry = tb.Entry(row, textvariable=self.quick_member_search_var, justify="right", width=26)
        self.quick_member_entry.pack(side="right", padx=(0, 12), ipady=4)

        self.quick_list = tk.Listbox(self.bottom, height=5)
        self.quick_list.pack(fill="x", pady=(8, 8))
        self.quick_list.bind("<<ListboxSelect>>", lambda _e: self._on_quick_member_select())

        self.quick_member_search_var.trace_add("write", lambda *_: self._quick_search_members())

        # Amount
        tb.Label(row, text="المبلغ", font=("Cairo", 10, "bold")).pack(side="right", padx=(0, 6))
        self.quick_amount_entry = tb.Entry(row, textvariable=self.quick_amount_var, justify="right", width=12)
        self.quick_amount_entry.pack(side="right", padx=(0, 12), ipady=4)

        # Method
        tb.Label(row, text="طريقة الدفع", font=("Cairo", 10, "bold")).pack(side="right", padx=(0, 6))
        self.quick_method_combo = tb.Combobox(
            row,
            textvariable=self.quick_method_var,
            values=list(config.PAYMENT_METHODS.values()),
            state="readonly",
            width=12,
            justify="right",
        )
        self.quick_method_combo.pack(side="right", padx=(0, 12))

        # Notes
        tb.Label(row, text="ملاحظات", font=("Cairo", 10, "bold")).pack(side="right", padx=(0, 6))
        self.quick_notes_entry = tb.Entry(row, textvariable=self.quick_notes_var, justify="right")
        self.quick_notes_entry.pack(side="right", fill="x", expand=True, padx=(0, 12), ipady=4)

        # Save
        self.quick_btn_save = tb.Button(row, text="حفظ", bootstyle="success", command=self.save_quick_payment)
        self.quick_btn_save.pack(side="left", ipady=6, padx=6)
        tb.Button(row, text="تفاصيل", bootstyle="info", command=self.open_record_payment_dialog).pack(side="left", ipady=6)

        self.quick_hint = tb.Label(
            self.bottom,
            textvariable=self.quick_suggest_var,
            font=FONTS["small"],
            foreground=COLORS["text_light"],
            anchor="e",
            justify="right",
        )
        self.quick_hint.pack(fill="x")

    # ------------------------------
    # Summary queries
    # ------------------------------

    def load_financial_summary(self) -> None:
        if self.db is None:
            return

        today = date.today().isoformat()
        ms = _month_start(date.today()).isoformat()

        with self.db.get_connection() as conn:
            cur = conn.cursor()

            today_total = cur.execute(
                "SELECT COALESCE(SUM(amount), 0) AS total FROM payments WHERE date(payment_date) = date(?)",
                (today,),
            ).fetchone()["total"]
            today_count = cur.execute(
                "SELECT COUNT(*) AS c FROM payments WHERE date(payment_date) = date(?)",
                (today,),
            ).fetchone()["c"]

            method_rows = cur.execute(
                """
                SELECT payment_method, COALESCE(SUM(amount), 0) AS total
                FROM payments
                WHERE date(payment_date) = date(?)
                GROUP BY payment_method
                """,
                (today,),
            ).fetchall()

            by_method = {"cash": 0.0, "card": 0.0, "transfer": 0.0}
            for r in method_rows:
                k = str(r["payment_method"] or "")
                if k in by_method:
                    by_method[k] = float(r["total"] or 0)

            month_total = cur.execute(
                "SELECT COALESCE(SUM(amount), 0) AS total FROM payments WHERE date(payment_date) >= date(?)",
                (ms,),
            ).fetchone()["total"]

            # Outstanding dues: sum(price - amount_paid) for non-cancelled subscriptions
            dues_rows = cur.execute(
                """
                SELECT s.member_id, st.price AS total, s.amount_paid AS paid,
                       m.first_name, m.last_name, m.phone, s.end_date
                FROM subscriptions s
                JOIN subscription_types st ON st.id = s.subscription_type_id
                JOIN members m ON m.id = s.member_id
                WHERE s.status != 'cancelled'
                """
            ).fetchall()

        dues_total = 0.0
        overdue_members = set()
        for r in dues_rows:
            total = float(r["total"] or 0)
            paid = float(r["paid"] or 0)
            rem = total - paid
            if rem > 0.01:
                dues_total += rem
                overdue_members.add(int(r["member_id"]))

        self.today_total_var.set(_fmt_money(float(today_total), db=self.db))
        self.today_count_var.set(str(int(today_count)))
        self.today_cash_var.set(_fmt_money(by_method["cash"], db=self.db))
        self.today_card_var.set(_fmt_money(by_method["card"], db=self.db))
        self.today_transfer_var.set(_fmt_money(by_method["transfer"], db=self.db))

        self.today_breakdown_label.configure(
            text=f"نقدي: {self.today_cash_var.get()} | بطاقة: {self.today_card_var.get()} | تحويل: {self.today_transfer_var.get()}"
        )
        self.today_count_label.configure(text=f"عدد العمليات: {self.today_count_var.get()}")

        self.month_total_var.set(_fmt_money(float(month_total), db=self.db))

        pct = 0
        try:
            pct = int(min(100, max(0, (float(month_total) / self.month_target) * 100)))
        except Exception:
            pct = 0
        try:
            self.month_gauge.configure(value=pct)
        except Exception:
            pass

        self.dues_total_var.set(_fmt_money(float(dues_total), db=self.db))
        self.dues_members_var.set(f"{len(overdue_members)} أعضاء متأخرين")

        # Payment method breakdown this month
        try:
            with self.db.get_connection() as conn:
                rows = conn.execute(
                    """
                    SELECT payment_method, COALESCE(SUM(amount), 0) AS total
                    FROM payments
                    WHERE date(payment_date) >= date(?)
                    GROUP BY payment_method
                    """,
                    (ms,),
                ).fetchall()

            totals = {"cash": 0.0, "card": 0.0, "transfer": 0.0}
            for r in rows:
                k = str(r["payment_method"] or "")
                if k in totals:
                    totals[k] = float(r["total"] or 0)

            total_sum = sum(max(0.0, v) for v in totals.values())
            for k, m in self.method_bars.items():
                pct = 0
                if total_sum > 0:
                    pct = int((max(0.0, totals.get(k, 0.0)) / total_sum) * 100)
                try:
                    self._set_meter_value(m, pct)
                except Exception:
                    pass
        except Exception:
            pass

        # Optional chart last 7 days
        if HAS_MATPLOTLIB:
            try:
                self._update_chart_last_7_days()
            except Exception:
                pass

    def _update_chart_last_7_days(self) -> None:
        if self.db is None:
            return

        end = date.today()
        start = end - timedelta(days=6)

        with self.db.get_connection() as conn:
            rows = conn.execute(
                """
                SELECT date(payment_date) AS d, COALESCE(SUM(amount), 0) AS total
                FROM payments
                WHERE date(payment_date) BETWEEN date(?) AND date(?)
                GROUP BY date(payment_date)
                ORDER BY date(payment_date) ASC
                """,
                (start.isoformat(), end.isoformat()),
            ).fetchall()

        totals_map = {str(r["d"]): float(r["total"] or 0) for r in rows}
        labels = []
        values = []
        for i in range(7):
            d = start + timedelta(days=i)
            labels.append(d.strftime("%d/%m"))
            values.append(totals_map.get(d.isoformat(), 0.0))

        self.ax.clear()
        self.ax.plot(labels, values, color="#2563eb", linewidth=2)
        self.ax.set_ylim(bottom=0)
        self.ax.grid(True, alpha=0.3)
        self.canvas.draw()

    # ------------------------------
    # Payments table
    # ------------------------------

    def load_payments_data(self, filters: dict[str, Any] | None = None) -> None:
        if self.db is None:
            return

        if filters is None:
            filters = self._collect_filters()

        query = """
            SELECT p.id,
                   p.receipt_number,
                   p.payment_date,
                   p.amount,
                   p.payment_method,
                   p.notes,
                   p.created_by,
                   m.first_name,
                   m.last_name,
                   m.phone,
                   p.subscription_id,
                   p.created_at,
                   s.invoice_status AS sub_invoice_status,
                   s.amount_paid AS sub_amount_paid,
                   st.price AS sub_total
            FROM payments p
            JOIN members m ON m.id = p.member_id
            LEFT JOIN subscriptions s ON s.id = p.subscription_id
            LEFT JOIN subscription_types st ON st.id = s.subscription_type_id
            WHERE 1=1
        """
        params: list[Any] = []

        # Hide invalid/legacy zero-amount rows to reduce confusion in the list.
        query += " AND ABS(COALESCE(p.amount, 0)) > 0.01"

        if filters:
            if filters.get("start_date"):
                query += " AND date(p.payment_date) >= date(?)"
                params.append(filters["start_date"])
            if filters.get("end_date"):
                query += " AND date(p.payment_date) <= date(?)"
                params.append(filters["end_date"])
            if filters.get("payment_method") and filters["payment_method"] != "الكل":
                query += " AND p.payment_method = ?"
                params.append(filters["payment_method"])
            if filters.get("search"):
                query += " AND ((m.first_name || ' ' || m.last_name) LIKE ? OR p.receipt_number LIKE ?)"
                s = f"%{filters['search']}%"
                params.extend([s, s])

            # Default: hide records linked to fully-paid subscriptions to reduce clutter.
            if not filters.get("show_paid"):
                query += " AND (p.subscription_id IS NULL OR COALESCE(s.invoice_status, 'unpaid') != 'paid')"

        query += " ORDER BY datetime(p.created_at) DESC, p.id DESC LIMIT 500"

        with self.db.get_connection() as conn:
            rows = conn.execute(query, tuple(params)).fetchall()

        self._rows = [dict(r) for r in rows]

        # Operation type filter in-memory
        if filters and filters.get("operation_type") and filters["operation_type"] != "الكل":
            op = filters["operation_type"]
            self._rows = [r for r in self._rows if self._derive_operation_type(r) == op]

        if self._sort_col:
            self._rows = self._sorted_rows(self._rows, self._sort_col, self._sort_desc)

        self._render_payments_table()
        self._render_payments_cards()

    def _sorted_rows(self, rows: list[dict[str, Any]], col: str, desc: bool) -> list[dict[str, Any]]:
        def key_fn(r: dict[str, Any]):
            v = r.get(col)
            return "" if v is None else v

        return sorted(rows, key=key_fn, reverse=desc)

    def sort_by_column(self, col: str) -> None:
        if self._sort_col == col:
            self._sort_desc = not self._sort_desc
        else:
            self._sort_col = col
            self._sort_desc = False

        self.load_payments_data(filters=self._collect_filters())

    def _render_payments_table(self) -> None:
        for iid in self.tree.get_children():
            self.tree.delete(iid)

        remaining_by_payment_id: dict[int, float] = {}
        sub_rows: dict[int, list[dict[str, Any]]] = {}
        for r in self._rows:
            try:
                sid = r.get("subscription_id")
                if sid is None:
                    continue
                sid_int = int(sid)
                sub_rows.setdefault(sid_int, []).append(r)
            except Exception:
                continue

        for sid, rows in sub_rows.items():
            try:
                rows_sorted = sorted(
                    rows,
                    key=lambda x: (
                        str(x.get("payment_date") or x.get("created_at") or ""),
                        int(x.get("id") or 0),
                    ),
                )
                sub_total = float(rows_sorted[0].get("sub_total") or 0)
                paid_sum = 0.0
                for rr in rows_sorted:
                    paid_sum += float(rr.get("amount") or 0)
                    pid = int(rr.get("id") or 0)
                    remaining_by_payment_id[pid] = max(0.0, sub_total - paid_sum)
            except Exception:
                continue

        for r in self._rows:
            receipt = r.get("receipt_number") or ""

            dt_raw = str(r.get("payment_date") or r.get("created_at") or "")
            pay_date, pay_time = self._split_datetime(dt_raw)

            member = f"{r.get('first_name', '')} {r.get('last_name', '')}".strip()
            op_type = self._derive_operation_type(r)

            amount = float(r.get("amount") or 0)
            method = self._method_ar(str(r.get("payment_method") or ""))

            remaining_disp = "-"
            try:
                pid_int = int(r.get("id") or 0)
                if pid_int in remaining_by_payment_id:
                    remaining_disp = _fmt_money(float(remaining_by_payment_id[pid_int]), db=self.db)
            except Exception:
                pass

            received_by = self._received_by_display(r)
            notes = str(r.get("notes") or "")

            tags = []
            if amount < 0:
                tags.append("refund")
            if abs(amount) >= 500:
                tags.append("large")

            # Visual status based on linked subscription if available.
            try:
                sub_total = float(r.get("sub_total") or 0)
                sub_paid = float(r.get("sub_amount_paid") or 0)
                if sub_total > 0:
                    remaining = sub_total - sub_paid
                    if remaining <= 0.01:
                        tags.append("paid_invoice")
                    else:
                        tags.append("unpaid_invoice")
            except Exception:
                pass

            self.tree.insert(
                "",
                "end",
                iid=str(r.get("id")),
                values=(
                    receipt,
                    pay_date,
                    pay_time,
                    member,
                    op_type,
                    _fmt_money(amount, db=self.db),
                    remaining_disp,
                    method,
                    received_by,
                    notes,
                ),
                tags=tuple(tags),
            )

    def _render_payments_cards(self) -> None:
        if getattr(self, "breakpoint", "desktop") != "mobile":
            return
        if not hasattr(self, "cards_inner"):
            return

        for child in self.cards_inner.winfo_children():
            child.destroy()

        for r in self._rows:
            pid = str(r.get("id") or "")

            receipt = str(r.get("receipt_number") or "-")
            dt_raw = str(r.get("payment_date") or r.get("created_at") or "")
            pay_date, pay_time = self._split_datetime(dt_raw)

            member = f"{r.get('first_name', '')} {r.get('last_name', '')}".strip() or "-"
            op_type = self._derive_operation_type(r)

            amount = float(r.get("amount") or 0)
            method = self._method_ar(str(r.get("payment_method") or ""))
            notes = str(r.get("notes") or "").strip()

            card = tb.Frame(self.cards_inner, padding=10, bootstyle="secondary")
            card.pack(fill="x", pady=6)

            top = tb.Frame(card)
            top.pack(fill="x")
            tb.Label(top, text=receipt, font=("Cairo", 11, "bold"), anchor="e").pack(side="right")
            tb.Label(top, text=f"{pay_date}  {pay_time}", font=FONTS["small"], anchor="w").pack(side="left")

            tb.Label(card, text=member, font=FONTS["subheading"], anchor="e").pack(fill="x", pady=(6, 0))
            tb.Label(card, text=f"{op_type} | {method}", font=FONTS["small"], anchor="e").pack(fill="x")
            tb.Label(card, text=_fmt_money(amount, db=self.db), font=("Cairo", 14, "bold"), anchor="e").pack(fill="x", pady=(4, 0))

            if notes:
                tb.Label(card, text=notes, font=FONTS["small"], anchor="e", justify="right").pack(fill="x", pady=(6, 0))

            def open_receipt(_e=None, payment_id=pid):
                try:
                    if payment_id:
                        self.tree.selection_set(payment_id)
                except Exception:
                    pass
                self.view_selected_receipt()

            for w in (card, top):
                w.bind("<Button-1>", open_receipt)

    def _split_datetime(self, dt_str: str) -> tuple[str, str]:
        # Stored as date or datetime strings.
        try:
            if len(dt_str) >= 19:
                dt = datetime.strptime(dt_str[:19], config.DATETIME_FORMAT)
                return dt.date().isoformat(), dt.time().strftime("%H:%M")
        except Exception:
            pass

        # Try ISO date
        try:
            d = datetime.strptime(dt_str[:10], config.DATE_FORMAT).date()
            return d.isoformat(), "-"
        except Exception:
            return "-", "-"

    def _method_ar(self, method_key: str) -> str:
        return {
            "cash": "نقدي",
            "card": "بطاقة",
            "transfer": "تحويل بنكي",
            "cheque": "شيك",
        }.get(method_key, method_key or "-")

    def _received_by_display(self, r: dict[str, Any]) -> str:
        if r.get("created_by"):
            return f"#{r.get('created_by')}"
        if self.user_data.get("username"):
            return str(self.user_data.get("username"))
        return "النظام"

    def _derive_operation_type(self, r: dict[str, Any]) -> str:
        amount = float(r.get("amount") or 0)
        if amount < 0:
            return "استرداد"
        if r.get("subscription_id"):
            # If amount is less than plan price (often partial), label as partial.
            try:
                plan_total = self._subscription_total_amount(int(r["subscription_id"]))
                if amount + 1e-9 < plan_total:
                    return "دفعة جزئية"
                return "اشتراك"
            except Exception:
                return "اشتراك"
        return "أخرى"

    def _subscription_total_amount(self, subscription_id: int) -> float:
        if self.db is None:
            return 0.0

        with self.db.get_connection() as conn:
            row = conn.execute(
                """
                SELECT st.price AS total
                FROM subscriptions s
                JOIN subscription_types st ON st.id = s.subscription_type_id
                WHERE s.id = ?
                LIMIT 1
                """,
                (subscription_id,),
            ).fetchone()
            return float(row["total"] or 0) if row else 0.0

    # ------------------------------
    # Filters
    # ------------------------------

    def _collect_filters(self) -> dict[str, Any]:
        start = self._safe_date(self.start_entry)
        end = self._safe_date(self.end_entry)

        payment_method = self._method_key_from_ar(self.filter_method_var.get())

        return {
            "start_date": start,
            "end_date": end,
            "payment_method": payment_method,
            "operation_type": self.filter_type_var.get(),
            "search": self.filter_search_var.get().strip() or None,
            "show_paid": bool(self.filter_show_paid_var.get()),
        }

    def apply_filters(self) -> None:
        self.load_payments_data(filters=self._collect_filters())
        self.load_financial_summary()

    def clear_filters(self) -> None:
        self.filter_method_var.set("الكل")
        self.filter_type_var.set("الكل")
        self.filter_search_var.set("")
        self.filter_show_paid_var.set(True)
        try:
            self.start_entry.date = _month_start(date.today())
            self.end_entry.date = date.today()
        except Exception:
            pass

        self.load_payments_data(filters=self._collect_filters())
        self.load_financial_summary()

    def _safe_date(self, entry: DateEntry) -> str | None:
        try:
            d = entry.date
            if isinstance(d, date):
                return d.isoformat()
        except Exception:
            pass

        try:
            raw = entry.entry.get().strip()
            if not raw:
                return None
            txt = raw[:10]
            for fmt in (config.DATE_FORMAT, "%m/%d/%y", "%m/%d/%Y", "%d/%m/%Y"):
                try:
                    return datetime.strptime(txt, fmt).date().isoformat()
                except Exception:
                    continue
            return None
        except Exception:
            return None

    def _method_key_from_ar(self, ar: str) -> str:
        if ar == "الكل":
            return "الكل"
        mapping = {
            "نقدي": "cash",
            "بطاقة": "card",
            "تحويل بنكي": "transfer",
            "شيك": "cheque",
        }
        return mapping.get(ar, ar)

    def _method_ar_from_key(self, key: str) -> str:
        return str(config.PAYMENT_METHODS.get(key, key))

    # ------------------------------
    # Context actions
    # ------------------------------

    def _show_context_menu(self, event) -> None:
        try:
            iid = self.tree.identify_row(event.y)
            if iid:
                self.tree.selection_set(iid)
            self.context_menu.tk_popup(event.x_root, event.y_root)
        finally:
            try:
                self.context_menu.grab_release()
            except Exception:
                pass

    def _selected_payment_id(self) -> int | None:
        sel = self.tree.selection()
        if not sel:
            return None
        try:
            return int(sel[0])
        except Exception:
            return None

    def view_selected_receipt(self) -> None:
        if self.db is None:
            return

        pid = self._selected_payment_id()
        if pid is None:
            return

        data = self._get_payment_details(pid)
        if not data:
            return

        ReceiptPreviewDialog(self.winfo_toplevel(), self.db, data).wait_window()

    def print_selected_receipt(self) -> None:
        if self.db is None:
            return

        pid = self._selected_payment_id()
        if pid is None:
            return

        data = self._get_payment_details(pid)
        if not data:
            return

        try:
            html = _generate_receipt_html(data, db=self.db)
            print_html_windows(html, filename_prefix="payment_receipt")
        except Exception:
            messagebox.showwarning("تنبيه", "تعذر بدء الطباعة تلقائياً")

    def edit_selected_payment(self) -> None:
        # For safety with current schema, editing is limited to notes.
        if self.db is None:
            return

        pid = self._selected_payment_id()
        if pid is None:
            return

        data = self._get_payment_details(pid)
        if not data:
            return

        dlg = EditNotesDialog(self.winfo_toplevel(), data.get("notes", ""))
        self.wait_window(dlg)
        if dlg.result is None:
            return

        try:
            with self.db.get_connection() as conn:
                conn.execute("UPDATE payments SET notes = ? WHERE id = ?", (dlg.result, pid))
                conn.commit()
        except Exception as e:
            messagebox.showerror("خطأ", f"تعذر التعديل: {e}")
            return

        self.apply_filters()

    def delete_selected_payment(self) -> None:
        # For safety, we keep a soft approach: delete payment row AND reverse subscription amount_paid.
        if self.db is None:
            return

        pid = self._selected_payment_id()
        if pid is None:
            return

        if not messagebox.askyesno("تأكيد", "هل تريد حذف الدفعة المحددة؟"):
            return

        data = self._get_payment_details(pid)
        if not data:
            return

        try:
            with self.db.get_connection() as conn:
                # Reverse subscription paid amount if linked
                sub_id = data.get("subscription_id")
                amt = float(data.get("amount") or 0)
                if sub_id:
                    conn.execute(
                        "UPDATE subscriptions SET amount_paid = COALESCE(amount_paid, 0) - ? WHERE id = ?",
                        (amt, int(sub_id)),
                    )

                conn.execute("DELETE FROM payments WHERE id = ?", (pid,))
                conn.commit()
        except Exception as e:
            messagebox.showerror("خطأ", f"تعذر الحذف: {e}")
            return

        self.apply_filters()

    def _get_payment_details(self, payment_id: int) -> dict[str, Any] | None:
        if self.db is None:
            return None

        with self.db.get_connection() as conn:
            row = conn.execute(
                """
                SELECT p.*, m.member_code, m.first_name, m.last_name, m.phone,
                       s.start_date AS sub_start, s.end_date AS sub_end,
                       st.name_ar AS plan_name, st.price AS plan_price
                FROM payments p
                JOIN members m ON m.id = p.member_id
                LEFT JOIN subscriptions s ON s.id = p.subscription_id
                LEFT JOIN subscription_types st ON st.id = s.subscription_type_id
                WHERE p.id = ?
                LIMIT 1
                """,
                (payment_id,),
            ).fetchone()
            return dict(row) if row else None

    # ------------------------------
    # Quick payment
    # ------------------------------

    def _quick_search_members(self) -> None:
        self.quick_list.delete(0, tk.END)
        self.quick_selected_member = None
        self.quick_suggest_var.set("")

        txt = self.quick_member_search_var.get().strip()
        if not txt or self.db is None:
            return

        q = f"%{txt}%"
        try:
            with self.db.get_connection() as conn:
                rows = conn.execute(
                    """
                    SELECT m.id, m.member_code, m.first_name, m.last_name, m.phone,
                           s.id AS sub_id,
                           st.price AS total,
                           s.amount_paid AS paid,
                           s.end_date
                    FROM members m
                    LEFT JOIN subscriptions s ON s.id = (
                        SELECT id
                        FROM subscriptions
                        WHERE member_id = m.id AND status = 'active'
                        ORDER BY date(end_date) DESC, id DESC
                        LIMIT 1
                    )
                    LEFT JOIN subscription_types st ON st.id = s.subscription_type_id
                    WHERE m.member_code LIKE ? OR m.phone LIKE ? OR m.first_name LIKE ? OR m.last_name LIKE ?
                    ORDER BY m.id DESC
                    LIMIT 10
                    """,
                    (q, q, q, q),
                ).fetchall()

            self._quick_results = [dict(r) for r in rows]
            for r in self._quick_results:
                name = f"{r.get('first_name', '')} {r.get('last_name', '')}".strip()
                total = float(r.get("total") or 0)
                paid = float(r.get("paid") or 0)
                bal = max(0.0, total - paid)
                self.quick_list.insert(tk.END, f"{r.get('member_code', '')} - {name} - {r.get('phone', '')} | المتبقي: {_fmt_money(bal, db=self.db)}")
        except Exception:
            self._quick_results = []

    def _on_quick_member_select(self) -> None:
        try:
            idx = int(self.quick_list.curselection()[0])
        except Exception:
            return

        self.quick_selected_member = self._quick_results[idx]

        total = float(self.quick_selected_member.get("total") or 0)
        paid = float(self.quick_selected_member.get("paid") or 0)
        bal = max(0.0, total - paid)

        sub_status = "لا يوجد اشتراك نشط"
        if self.quick_selected_member.get("sub_id"):
            sub_status = f"اشتراك نشط ينتهي: {self.quick_selected_member.get('end_date', '-') }"

        self.quick_suggest_var.set(f"{sub_status} | المتبقي: {_fmt_money(bal, db=self.db)}")

        if bal > 0:
            self.quick_amount_var.set(f"{bal:.0f}")

    def save_quick_payment(self) -> None:
        if getattr(self, "_quick_saving", False):
            return
        self._quick_saving = True
        try:
            self.quick_btn_save.configure(state="disabled")
        except Exception:
            pass

        if self.db is None:
            messagebox.showerror("خطأ", "قاعدة البيانات غير جاهزة")
            try:
                self.quick_btn_save.configure(state="normal")
            except Exception:
                pass
            self._quick_saving = False
            return

        if self.quick_selected_member is None:
            messagebox.showwarning("تنبيه", "يرجى اختيار عضو")
            try:
                self.quick_btn_save.configure(state="normal")
            except Exception:
                pass
            self._quick_saving = False
            return

        # Prevent extra receipts when the subscription is already fully paid.
        try:
            total = float(self.quick_selected_member.get("total") or 0)
            paid = float(self.quick_selected_member.get("paid") or 0)
            bal = max(0.0, total - paid)
            if bal <= 0.01 and self.quick_selected_member.get("sub_id"):
                messagebox.showwarning("تنبيه", "هذا الاشتراك مدفوع بالكامل ولا يوجد مبلغ مستحق")
                try:
                    self.quick_btn_save.configure(state="normal")
                except Exception:
                    pass
                self._quick_saving = False
                return
        except Exception:
            pass

        try:
            amount = float(self.quick_amount_var.get() or 0)
        except Exception:
            amount = -1

        if amount <= 0:
            messagebox.showwarning("تنبيه", "يرجى إدخال مبلغ صحيح")
            try:
                self.quick_btn_save.configure(state="normal")
            except Exception:
                pass
            self._quick_saving = False
            return

        member_id = int(self.quick_selected_member["id"])
        sub_id = self.quick_selected_member.get("sub_id")

        ok, msg, pid = self._record_payment(
            member_id=member_id,
            subscription_id=int(sub_id) if sub_id else None,
            amount=amount,
            payment_method=self._method_key_from_ar(self.quick_method_var.get() or "نقدي"),
            notes=self.quick_notes_var.get().strip() or None,
        )

        if not ok:
            messagebox.showerror("خطأ", msg)
            try:
                self.quick_btn_save.configure(state="normal")
            except Exception:
                pass
            self._quick_saving = False
            return

        messagebox.showinfo("تم", "تم تسجيل الدفعة بنجاح")
        self.quick_notes_var.set("")
        self.apply_filters()

        # Open receipt preview
        if pid is not None:
            data = self._get_payment_details(pid)
            if data:
                ReceiptPreviewDialog(self.winfo_toplevel(), self.db, data).wait_window()

        try:
            self.quick_btn_save.configure(state="normal")
        except Exception:
            pass
        self._quick_saving = False

    def _record_payment(
        self,
        member_id: int,
        subscription_id: int | None,
        amount: float,
        payment_method: str,
        notes: str | None,
        payment_date: str | None = None,
    ) -> tuple[bool, str, int | None]:
        """Record a payment and update linked subscription amount_paid."""

        try:
            if float(amount) <= 0.01:
                return False, "يرجى إدخال مبلغ صحيح", None
        except Exception:
            return False, "يرجى إدخال مبلغ صحيح", None

        try:
            pay_date = payment_date or date.today().isoformat()
            now = datetime.now().strftime(config.DATETIME_FORMAT)

            with self.db.get_connection() as conn:
                cur = conn.cursor()

                if subscription_id is not None:
                    try:
                        row = cur.execute(
                            """
                            SELECT COALESCE(s.invoice_status, 'unpaid') AS invoice_status,
                                   COALESCE(s.amount_paid, 0) AS paid,
                                   COALESCE(st.price, 0) AS total
                            FROM subscriptions s
                            LEFT JOIN subscription_types st ON st.id = s.subscription_type_id
                            WHERE s.id = ?
                            LIMIT 1
                            """,
                            (int(subscription_id),),
                        ).fetchone()
                        if row is not None:
                            inv = str(row["invoice_status"] or "unpaid").strip().lower()
                            total = float(row["total"] or 0)
                            paid = float(row["paid"] or 0)
                            remaining = max(0.0, total - paid)
                            if inv == "paid" or remaining <= 0.01:
                                return False, "هذه الفاتورة مدفوعة بالكامل ولا يمكن تسجيل دفعة أخرى", None
                            if float(amount) > remaining + 0.01:
                                return (
                                    False,
                                    f"المبلغ أكبر من المتبقي ({_fmt_money(float(remaining), db=self.db)})",
                                    None,
                                )
                    except Exception:
                        pass

                receipt = self.db.generate_receipt_number()

                cur.execute(
                    """
                    INSERT INTO payments
                        (subscription_id, member_id, amount, payment_method, payment_date,
                         receipt_number, notes, created_by, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        subscription_id,
                        member_id,
                        float(amount),
                        payment_method,
                        pay_date,
                        receipt,
                        notes,
                        self.user_data.get("id"),
                        now,
                    ),
                )
                pid = int(cur.lastrowid)

                if subscription_id is not None:
                    cur.execute(
                        """
                        UPDATE subscriptions
                        SET amount_paid = COALESCE(amount_paid, 0) + ?,
                            invoice_status = CASE
                                WHEN (COALESCE(amount_paid, 0) + ?) + 1e-9 >= (
                                    SELECT COALESCE(price, 0)
                                    FROM subscription_types st
                                    WHERE st.id = subscriptions.subscription_type_id
                                ) THEN 'paid'
                                ELSE 'unpaid'
                            END,
                            paid_at = CASE
                                WHEN (COALESCE(amount_paid, 0) + ?) + 1e-9 >= (
                                    SELECT COALESCE(price, 0)
                                    FROM subscription_types st
                                    WHERE st.id = subscriptions.subscription_type_id
                                ) THEN COALESCE(paid_at, ?)
                                ELSE paid_at
                            END,
                            updated_at = ?
                        WHERE id = ?
                        """,
                        (float(amount), float(amount), float(amount), pay_date, now, int(subscription_id)),
                    )

                conn.commit()

            self.load_financial_summary()
            return True, "Payment recorded", pid
        except Exception as e:
            return False, f"فشل في تسجيل الدفعة: {e}", None

    def open_record_payment_dialog(self) -> None:
        if self.db is None:
            return

        dlg = RecordPaymentDialog(self.winfo_toplevel(), self.db, self.user_data)
        self.wait_window(dlg)
        if dlg.saved:
            self.apply_filters()

    # ------------------------------
    # Outstanding dues
    # ------------------------------

    def show_outstanding_dues(self) -> None:
        if self.db is None:
            return

        dlg = OutstandingDuesDialog(self.winfo_toplevel(), self.db, self.user_data)
        self.wait_window(dlg)
        if dlg.did_change:
            self.apply_filters()

    def show_paid_invoices(self) -> None:
        if self.db is None:
            return

        dlg = PaidInvoicesDialog(self.winfo_toplevel(), self.db)
        self.wait_window(dlg)

    # ------------------------------
    # Daily cash register
    # ------------------------------

    def show_daily_cash_register(self) -> None:
        if self.db is None:
            return

        dlg = DailyCashRegisterDialog(self.winfo_toplevel(), self.db)
        self.wait_window(dlg)

    # ------------------------------
    # Shortcuts
    # ------------------------------

    def _bind_shortcuts(self) -> None:
        top = self.winfo_toplevel()
        top.bind("<Control-n>", lambda _e: self.open_record_payment_dialog())
        top.bind("<Control-p>", lambda _e: self.print_selected_receipt())
        top.bind("<Control-f>", lambda _e: self.search_entry.focus_set())
        top.bind("<F5>", lambda _e: self.apply_filters())


class ReceiptPreviewDialog(tk.Toplevel):
    """Receipt preview for viewing/printing."""

    def __init__(self, parent: tk.Misc, db: DatabaseManager | None, data: dict[str, Any]) -> None:
        super().__init__(parent)
        self.db = db
        self.data = data
        self._html_content = _generate_receipt_html(data, db=self.db)
        self.title("الإيصال")
        self.geometry("520x560")
        self.minsize(420, 420)
        self.resizable(True, True)
        self.grab_set()

        container = tb.Frame(self, padding=14)
        container.pack(fill="both", expand=True)

        header = tb.Frame(container)
        header.pack(fill="x")

        tb.Label(header, text=config.APP_NAME, font=FONTS["subheading"], anchor="e").pack(fill="x")
        tb.Label(header, text="إيصال دفع", font=FONTS["body"], anchor="e").pack(fill="x", pady=(2, 10))

        receipt = data.get("receipt_number") or "-"
        member = f"{data.get('member_code', '')} - {data.get('first_name', '')} {data.get('last_name', '')}".strip()
        phone = data.get("phone", "")
        amount = float(data.get("amount") or 0)
        method = data.get("payment_method") or ""
        pay_date = str(data.get("payment_date") or "")
        notes = data.get("notes") or ""

        info_row = tb.Frame(container)
        info_row.pack(fill="x", pady=(0, 10))

        card_right = tb.Labelframe(info_row, text="معلومات الإيصال", padding=10)
        card_right.pack(side="right", fill="both", expand=True)

        tb.Label(card_right, text=f"رقم الإيصال: {receipt}", font=FONTS["small"], anchor="e").pack(fill="x")
        tb.Label(card_right, text=f"التاريخ: {pay_date}", font=FONTS["small"], anchor="e").pack(fill="x", pady=(2, 0))
        tb.Label(card_right, text=f"طريقة الدفع: {method}", font=FONTS["small"], anchor="e").pack(fill="x", pady=(2, 0))

        card_left = tb.Labelframe(info_row, text="المبلغ", padding=10)
        card_left.pack(side="left", fill="y")
        tb.Label(card_left, text=_fmt_money(amount, db=self.db), font=("Cairo", 18, "bold"), anchor="e").pack(fill="x")

        table_frame = tb.Frame(container)
        table_frame.pack(fill="both", expand=True)

        tree = ttk.Treeview(table_frame, columns=("field", "value"), show="headings", height=10)
        tree.heading("field", text="الحقل")
        tree.heading("value", text="القيمة")
        tree.column("field", width=160, anchor="e")
        tree.column("value", width=320, anchor="e")

        vsb = ttk.Scrollbar(table_frame, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=vsb.set)

        vsb.pack(side="left", fill="y")
        tree.pack(side="left", fill="both", expand=True)

        rows: list[tuple[str, str]] = []
        rows.append(("العضو", member or "-"))
        rows.append(("الهاتف", str(phone or "-")))
        if data.get("plan_name"):
            rows.append(("الباقة", str(data.get("plan_name") or "-")))
        if data.get("sub_end"):
            rows.append(("انتهاء الاشتراك", str(data.get("sub_end") or "-")))
        rows.append(("المبلغ", _fmt_money(amount, db=self.db)))
        rows.append(("طريقة الدفع", str(method or "-")))
        if notes:
            rows.append(("ملاحظات", str(notes)))

        for f, v in rows:
            tree.insert("", "end", values=(f, v))

        # Text used for printing (keep plain-text receipt for Windows print fallback)
        self._print_text_lines: list[str] = []
        self._print_text_lines.append("═" * 38)
        self._print_text_lines.append(str(getattr(config, "APP_NAME", "")) or "")
        self._print_text_lines.append("═" * 38)
        self._print_text_lines.append(f"رقم الإيصال: {receipt}")
        self._print_text_lines.append(f"التاريخ: {pay_date}")
        self._print_text_lines.append("-" * 38)
        self._print_text_lines.append(f"العضو: {member}")
        self._print_text_lines.append(f"الهاتف: {phone}")
        if data.get("plan_name"):
            self._print_text_lines.append(f"الباقة: {data.get('plan_name')}")
        if data.get("sub_end"):
            self._print_text_lines.append(f"انتهاء الاشتراك: {data.get('sub_end')}")
        self._print_text_lines.append("-" * 38)
        self._print_text_lines.append(f"المبلغ: {_fmt_money(amount, db=self.db)}")
        self._print_text_lines.append(f"طريقة الدفع: {method}")
        if notes:
            self._print_text_lines.append(f"ملاحظات: {notes}")
        self._print_text_lines.append("-" * 38)
        self._print_text_lines.append("شكراً لكم")
        self._print_text_lines.append("═" * 38)

        btns = tb.Frame(container)
        btns.pack(fill="x", pady=10)
        tb.Button(btns, text="🌐 فتح في المتصفح", bootstyle="secondary", command=self._open_browser).pack(side="left")
        tb.Button(btns, text="🖨️ طباعة", bootstyle="secondary", command=self._print).pack(side="left", padx=6)
        tb.Button(btns, text="إغلاق", bootstyle="secondary", command=self.destroy).pack(side="left", padx=6)

    def _print(self) -> None:
        try:
            try:
                print_html_windows(self._html_content, filename_prefix="payment_receipt")
                return
            except Exception:
                pass

            content = "\n".join(getattr(self, "_print_text_lines", [])).strip()
            print_text_windows(content, filename_prefix="payment_receipt")
        except Exception:
            messagebox.showwarning("تنبيه", "تعذر بدء الطباعة تلقائياً")

    def _open_browser(self) -> None:
        try:
            open_html_windows(self._html_content, filename_prefix="payment_receipt")
        except Exception:
            messagebox.showwarning("تنبيه", "تعذر فتح الإيصال في المتصفح")


class EditNotesDialog(tk.Toplevel):
    def __init__(self, parent: tk.Misc, notes: str) -> None:
        super().__init__(parent)
        self.title("تعديل الملاحظات")
        self.geometry("420x240")
        self.minsize(360, 220)
        self.resizable(True, True)
        self.grab_set()

        self.result: str | None = None

        container = tb.Frame(self, padding=12)
        container.pack(fill="both", expand=True)

        tb.Label(container, text="ملاحظات", font=FONTS["subheading"], anchor="e").pack(fill="x")
        self.txt = tk.Text(container, height=6, wrap="word")
        self.txt.pack(fill="both", expand=True, pady=8)
        self.txt.insert("1.0", notes or "")

        btns = tb.Frame(container)
        btns.pack(fill="x")
        tb.Button(btns, text="حفظ", bootstyle="success", command=self._save).pack(side="left", padx=6)
        tb.Button(btns, text="إلغاء", bootstyle="secondary", command=self.destroy).pack(side="left")

    def _save(self) -> None:
        self.result = self.txt.get("1.0", "end").strip()
        self.destroy()


class RecordPaymentDialog(tk.Toplevel):
    """Detailed payment dialog."""

    def __init__(self, parent: tk.Misc, db: DatabaseManager, user_data: dict[str, Any]) -> None:
        super().__init__(parent)
        self.db = db
        self.user_data = user_data
        self.saved: bool = False

        self.title("تسجيل دفعة")
        self.minsize(360, 420)
        self.resizable(True, True)
        self.grab_set()

        self.member_search_var = tk.StringVar(master=self, value="")
        self.amount_var = tk.StringVar(master=self, value="")
        self.method_var = tk.StringVar(master=self, value="cash")
        self.reference_var = tk.StringVar(master=self, value="")
        self.date_var = tk.StringVar(master=self, value=date.today().isoformat())

        self.selected_member: dict[str, Any] | None = None
        self.selected_subscription: dict[str, Any] | None = None

        self.create_widgets()
        self.member_search_var.trace_add("write", lambda *_: self._search_members())
        self._apply_geometry(parent)

    def _apply_geometry(self, parent: tk.Misc) -> None:
        try:
            self.update_idletasks()
        except Exception:
            pass

        try:
            pw = int(parent.winfo_width())
            ph = int(parent.winfo_height())
            px = int(parent.winfo_rootx())
            py = int(parent.winfo_rooty())
        except Exception:
            pw = int(self.winfo_screenwidth())
            ph = int(self.winfo_screenheight())
            px = 0
            py = 0

        w = min(760, int(pw * 0.95))
        h = min(620, int(ph * 0.90))
        w = max(360, w)
        h = max(420, h)

        x = px + max((pw - w) // 2, 0)
        y = py + max((ph - h) // 2, 0)
        try:
            self.geometry(f"{w}x{h}+{x}+{y}")
        except Exception:
            pass

    def create_widgets(self) -> None:
        container = tb.Frame(self, padding=14)
        container.pack(fill="both", expand=True)

        # Member info
        info = tb.Labelframe(container, text="معلومات العضو", padding=12)
        info.pack(fill="x")

        tb.Label(info, text="بحث بالاسم أو الهاتف", font=("Cairo", 10, "bold"), anchor="e").pack(fill="x")
        self.search_entry = tb.Entry(info, textvariable=self.member_search_var, justify="right")
        self.search_entry.pack(fill="x", pady=(6, 8), ipady=4)

        self.results = tk.Listbox(info, height=5)
        self.results.pack(fill="x")
        self.results.bind("<<ListboxSelect>>", lambda _e: self._on_select())

        self.member_label = tb.Label(info, text="-", font=FONTS["small"], foreground=COLORS["text_light"], anchor="e")
        self.member_label.pack(fill="x", pady=(8, 0))

        # History
        hist = tb.Labelframe(container, text="آخر 5 دفعات", padding=12)
        hist.pack(fill="x", pady=10)

        cols = ("receipt", "date", "amount")
        self.hist_tree = ttk.Treeview(hist, columns=cols, show="headings", height=5)
        self.hist_tree.heading("receipt", text="الإيصال")
        self.hist_tree.heading("date", text="التاريخ")
        self.hist_tree.heading("amount", text="المبلغ")
        self.hist_tree.column("receipt", width=160, anchor="center")
        self.hist_tree.column("date", width=120, anchor="center")
        self.hist_tree.column("amount", width=120, anchor="center")
        self.hist_tree.pack(fill="x")

        # Balance/payment
        pay = tb.Labelframe(container, text="الدفعة الجديدة", padding=12)
        pay.pack(fill="x")

        grid = tb.Frame(pay)
        grid.pack(fill="x")

        def row(label: str, var: tk.StringVar, i: int) -> None:
            fr = tb.Frame(grid)
            fr.grid(row=i, column=0, sticky="ew", pady=4)
            fr.columnconfigure(0, weight=1)
            tb.Label(fr, text=label, font=("Cairo", 10, "bold"), anchor="e").pack(side="right")
            tb.Entry(fr, textvariable=var, justify="right").pack(side="left", fill="x", expand=True)

        row("المبلغ المدفوع", self.amount_var, 0)

        pm = tb.Frame(grid)
        pm.grid(row=1, column=0, sticky="ew", pady=4)
        pm.columnconfigure(0, weight=1)
        tb.Label(pm, text="طريقة الدفع", font=("Cairo", 10, "bold"), anchor="e").pack(side="right")
        tb.Combobox(pm, textvariable=self.method_var, values=list(config.PAYMENT_METHODS.keys()), state="readonly", justify="right").pack(
            side="left"
        )

        row("رقم المرجع (اختياري)", self.reference_var, 2)

        dt = tb.Frame(grid)
        dt.grid(row=3, column=0, sticky="ew", pady=4)
        dt.columnconfigure(0, weight=1)
        tb.Label(dt, text="تاريخ الدفع", font=("Cairo", 10, "bold"), anchor="e").pack(side="right")
        self.date_entry = DateEntry(dt, bootstyle="info", width=12)
        self.date_entry.pack(side="left")

        notes = tb.Frame(grid)
        notes.grid(row=4, column=0, sticky="ew", pady=4)
        notes.columnconfigure(0, weight=1)
        tb.Label(notes, text="ملاحظات", font=("Cairo", 10, "bold"), anchor="e").pack(side="right")
        self.notes_entry = tb.Entry(notes, justify="right")
        self.notes_entry.pack(side="left", fill="x", expand=True)

        btns = tb.Frame(container)
        btns.pack(fill="x", pady=(10, 0))

        self.btn_save = tb.Button(btns, text="تسجيل الدفعة", bootstyle="success", command=self._save)
        self.btn_save.pack(side="left", padx=6)
        self.btn_save_print = tb.Button(btns, text="تسجيل وطباعة", bootstyle="info", command=lambda: self._save(print_after=True))
        self.btn_save_print.pack(side="left", padx=6)
        tb.Button(btns, text="إلغاء", bootstyle="secondary", command=self.destroy).pack(side="left")

    def _center(self) -> None:
        self.update_idletasks()
        w = self.winfo_width()
        h = self.winfo_height()
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        self.geometry(f"{w}x{h}+{(sw - w)//2}+{(sh - h)//2}")

    def _search_members(self) -> None:
        txt = self.member_search_var.get().strip()
        self.results.delete(0, tk.END)
        self._member_results = []
        if not txt:
            return

        q = f"%{txt}%"
        try:
            with self.db.get_connection() as conn:
                rows = conn.execute(
                    """
                    SELECT m.id, m.member_code, m.first_name, m.last_name, m.phone,
                           s.id AS sub_id,
                           st.price AS total,
                           s.amount_paid AS paid,
                           s.end_date
                    FROM members m
                    LEFT JOIN subscriptions s ON s.id = (
                        SELECT id
                        FROM subscriptions
                        WHERE member_id = m.id AND status = 'active'
                        ORDER BY date(end_date) DESC, id DESC
                        LIMIT 1
                    )
                    LEFT JOIN subscription_types st ON st.id = s.subscription_type_id
                    WHERE m.member_code LIKE ? OR m.phone LIKE ? OR m.first_name LIKE ? OR m.last_name LIKE ?
                    ORDER BY m.id DESC
                    LIMIT 20
                    """,
                    (q, q, q, q),
                ).fetchall()

            self._member_results = [dict(r) for r in rows]
            for r in self._member_results:
                name = f"{r.get('first_name', '')} {r.get('last_name', '')}".strip()
                total = float(r.get("total") or 0)
                paid = float(r.get("paid") or 0)
                bal = max(0.0, total - paid)
                self.results.insert(tk.END, f"{r.get('member_code', '')} - {name} - {r.get('phone', '')} | المتبقي: {_fmt_money(bal, db=self.db)}")
        except Exception:
            pass

    def _on_select(self) -> None:
        try:
            idx = int(self.results.curselection()[0])
        except Exception:
            return

        self.selected_member = self._member_results[idx]

        name = f"{self.selected_member.get('first_name', '')} {self.selected_member.get('last_name', '')}".strip()
        sub_status = "لا يوجد اشتراك نشط"
        if self.selected_member.get("sub_id"):
            sub_status = f"اشتراك نشط ينتهي: {self.selected_member.get('end_date', '-') }"

        total = float(self.selected_member.get("total") or 0)
        paid = float(self.selected_member.get("paid") or 0)
        remaining = max(0.0, total - paid)

        self.member_label.configure(
            text=f"الاسم: {name} | رقم العضوية: {self.selected_member.get('member_code', '')} | الهاتف: {self.selected_member.get('phone', '')}\n{sub_status}\nالمتبقي: {_fmt_money(remaining, db=self.db)}",
            foreground=COLORS["text"],
        )

        if remaining > 0:
            self.amount_var.set(f"{remaining:.0f}")

        self._load_history(int(self.selected_member["id"]))

    def _load_history(self, member_id: int) -> None:
        for i in self.hist_tree.get_children():
            self.hist_tree.delete(i)

        try:
            with self.db.get_connection() as conn:
                rows = conn.execute(
                    """
                    SELECT receipt_number, payment_date, amount
                    FROM payments
                    WHERE member_id = ?
                      AND ABS(COALESCE(amount, 0)) > 0.01
                    ORDER BY datetime(created_at) DESC, id DESC
                    LIMIT 5
                    """,
                    (member_id,),
                ).fetchall()

            for r in rows:
                dt = str(r["payment_date"] or "")
                d = dt[:10] if dt else "-"
                self.hist_tree.insert("", "end", values=(r["receipt_number"], d, _fmt_money(float(r["amount"] or 0), db=self.db)))
        except Exception:
            pass

    def _save(self, print_after: bool = False) -> None:
        if getattr(self, "_saving", False):
            return
        self._saving = True
        try:
            self.btn_save.configure(state="disabled")
            self.btn_save_print.configure(state="disabled")
        except Exception:
            pass

        if self.selected_member is None:
            messagebox.showwarning("تنبيه", "يرجى اختيار عضو")
            try:
                self.btn_save.configure(state="normal")
                self.btn_save_print.configure(state="normal")
            except Exception:
                pass
            self._saving = False
            return

        try:
            amount = float(self.amount_var.get() or 0)
        except Exception:
            amount = -1

        if amount <= 0:
            messagebox.showerror("خطأ", "يرجى إدخال مبلغ صحيح")
            try:
                self.btn_save.configure(state="normal")
                self.btn_save_print.configure(state="normal")
            except Exception:
                pass
            self._saving = False
            return

        notes = self.notes_entry.get().strip()
        if self.reference_var.get().strip():
            notes = (notes + " | " if notes else "") + f"REF={self.reference_var.get().strip()}"

        pay_date = None
        try:
            d = self.date_entry.date
            if isinstance(d, date):
                pay_date = d.isoformat()
        except Exception:
            pay_date = date.today().isoformat()

        sub_id = self.selected_member.get("sub_id")

        # Insert payment and update subscription amount_paid if linked
        try:
            receipt = self.db.generate_receipt_number()
            now = datetime.now().strftime(config.DATETIME_FORMAT)

            with self.db.get_connection() as conn:
                cur = conn.cursor()

                if sub_id:
                    try:
                        row = cur.execute(
                            """
                            SELECT COALESCE(s.invoice_status, 'unpaid') AS invoice_status,
                                   COALESCE(s.amount_paid, 0) AS paid,
                                   COALESCE(st.price, 0) AS total
                            FROM subscriptions s
                            LEFT JOIN subscription_types st ON st.id = s.subscription_type_id
                            WHERE s.id = ?
                            LIMIT 1
                            """,
                            (int(sub_id),),
                        ).fetchone()
                        if row is not None:
                            inv = str(row["invoice_status"] or "unpaid").strip().lower()
                            total = float(row["total"] or 0)
                            paid0 = float(row["paid"] or 0)
                            remaining0 = max(0.0, total - paid0)
                            if inv == "paid" or remaining0 <= 0.01:
                                Messagebox.ok(title="تنبيه", message="هذا الاشتراك مدفوع بالكامل ولا يوجد مبلغ مستحق", parent=self)
                                try:
                                    self.btn_save.configure(state="normal")
                                    self.btn_save_print.configure(state="normal")
                                except Exception:
                                    pass
                                self._saving = False
                                return
                            if float(amount) > remaining0 + 0.01:
                                Messagebox.ok(
                                    title="خطأ",
                                    message=f"المبلغ أكبر من المتبقي ({_fmt_money(float(remaining0), db=self.db)})",
                                    parent=self,
                                )
                                try:
                                    self.btn_save.configure(state="normal")
                                    self.btn_save_print.configure(state="normal")
                                except Exception:
                                    pass
                                self._saving = False
                                return
                    except Exception:
                        pass

                cur.execute(
                    """
                    INSERT INTO payments
                        (subscription_id, member_id, amount, payment_method, payment_date,
                         receipt_number, notes, created_by, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        int(sub_id) if sub_id else None,
                        int(self.selected_member["id"]),
                        float(amount),
                        self.method_var.get() or "cash",
                        pay_date,
                        receipt,
                        notes or None,
                        self.user_data.get("id"),
                        now,
                    ),
                )
                pid = int(cur.lastrowid)

                if sub_id:
                    cur.execute(
                        """
                        UPDATE subscriptions
                        SET amount_paid = COALESCE(amount_paid, 0) + ?,
                            invoice_status = CASE
                                WHEN (COALESCE(amount_paid, 0) + ?) + 1e-9 >= (
                                    SELECT COALESCE(price, 0)
                                    FROM subscription_types st
                                    WHERE st.id = subscriptions.subscription_type_id
                                ) THEN 'paid'
                                ELSE 'unpaid'
                            END,
                            paid_at = CASE
                                WHEN (COALESCE(amount_paid, 0) + ?) + 1e-9 >= (
                                    SELECT COALESCE(price, 0)
                                    FROM subscription_types st
                                    WHERE st.id = subscriptions.subscription_type_id
                                ) THEN COALESCE(paid_at, ?)
                                ELSE paid_at
                            END,
                            updated_at = ?
                        WHERE id = ?
                        """,
                        (float(amount), float(amount), float(amount), pay_date, now, int(sub_id)),
                    )

                conn.commit()

            self.saved = True
            Messagebox.ok(title="تم", message="تم تسجيل الدفعة بنجاح", parent=self)

            if print_after:
                with self.db.get_connection() as conn:
                    data = conn.execute(
                        """
                        SELECT p.*, m.member_code, m.first_name, m.last_name, m.phone,
                               s.end_date AS sub_end,
                               st.name_ar AS plan_name
                        FROM payments p
                        JOIN members m ON m.id = p.member_id
                        LEFT JOIN subscriptions s ON s.id = p.subscription_id
                        LEFT JOIN subscription_types st ON st.id = s.subscription_type_id
                        WHERE p.id = ?
                        """,
                        (pid,),
                    ).fetchone()
                if data:
                    ReceiptPreviewDialog(self, self.db, dict(data)).wait_window()

            self.destroy()
        except Exception as e:
            messagebox.showerror("خطأ", f"فشل في تسجيل الدفعة: {e}")
            try:
                self.btn_save.configure(state="normal")
                self.btn_save_print.configure(state="normal")
            except Exception:
                pass
            self._saving = False


class OutstandingDuesDialog(tk.Toplevel):
    """Dialog listing members with unpaid balances."""

    def __init__(self, parent: tk.Misc, db: DatabaseManager, user_data: dict[str, Any]) -> None:
        super().__init__(parent)
        self.db = db
        self.user_data = user_data
        self.did_change: bool = False
        self._loading: bool = False

        self.title("المبالغ المستحقة")
        self.geometry("820x520")
        self.resizable(True, True)
        self.grab_set()

        container = tb.Frame(self, padding=12)
        container.pack(fill="both", expand=True)

        cols = ("member", "phone", "due", "last_payment", "days", "action")
        self.tree = ttk.Treeview(container, columns=cols, show="headings")
        self.tree.heading("member", text="اسم العضو")
        self.tree.heading("phone", text="الهاتف")
        self.tree.heading("due", text="المبلغ المستحق")
        self.tree.heading("last_payment", text="آخر دفعة")
        self.tree.heading("days", text="أيام التأخير")
        self.tree.heading("action", text="إجراء")

        self.tree.column("member", width=240, anchor="e")
        self.tree.column("phone", width=120, anchor="center")
        self.tree.column("due", width=120, anchor="center")
        self.tree.column("last_payment", width=110, anchor="center")
        self.tree.column("days", width=100, anchor="center")
        self.tree.column("action", width=100, anchor="center")

        vsb = ttk.Scrollbar(container, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)

        self.tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

        btns = tb.Frame(container)
        btns.pack(fill="x", pady=(10, 0))
        self.btn_refresh = tb.Button(btns, text="🔄 تحديث", bootstyle="primary", command=self.refresh)
        self.btn_refresh.pack(side="left", padx=6)
        tb.Button(btns, text="تصدير CSV", bootstyle="info", command=self._export_csv).pack(side="left", padx=6)
        tb.Button(btns, text="إغلاق", bootstyle="secondary", command=self.destroy).pack(side="left")

        self._status_var = tk.StringVar(value="")
        self._status_label = tb.Label(btns, textvariable=self._status_var, font=FONTS["small"], anchor="e")
        self._status_label.pack(side="right")

        self._spinner = ttk.Progressbar(btns, mode="indeterminate", length=120)
        self._spinner.pack(side="right", padx=6)
        self._spinner.stop()
        self._spinner.pack_forget()

        self.refresh(initial=True)
        self.tree.bind("<Double-1>", lambda _e: self._record_for_selected())

    def _set_loading(self, value: bool) -> None:
        self._loading = bool(value)
        try:
            if self._loading:
                self.btn_refresh.configure(state="disabled")
                self._spinner.pack(side="right", padx=6)
                self._spinner.start(12)
                self._status_var.set("جاري التحديث...")
            else:
                self._spinner.stop()
                self._spinner.pack_forget()
                self.btn_refresh.configure(state="normal")
        except Exception:
            pass

    def _toast_success(self, msg: str) -> None:
        try:
            self._status_var.set(msg)

            def clear() -> None:
                try:
                    self._status_var.set("")
                except Exception:
                    pass

            self.after(1600, clear)
        except Exception:
            pass

    def refresh(self, initial: bool = False) -> None:
        if self._loading:
            return

        self._set_loading(True)

        def worker() -> None:
            try:
                today = date.today()
                with self.db.get_connection() as conn:
                    rows = conn.execute(
                        """
                        SELECT s.id AS subscription_id,
                               m.id AS member_id,
                               m.first_name, m.last_name, m.phone,
                               st.price AS total,
                               s.amount_paid AS paid,
                               s.end_date,
                               (
                                   SELECT MAX(date(payment_date))
                                   FROM payments p
                                   WHERE p.member_id = m.id
                               ) AS last_payment
                        FROM subscriptions s
                        JOIN members m ON m.id = s.member_id
                        JOIN subscription_types st ON st.id = s.subscription_type_id
                        WHERE s.status != 'cancelled'
                          AND COALESCE(s.invoice_status, 'unpaid') = 'unpaid'
                        ORDER BY date(s.end_date) ASC
                        """
                    ).fetchall()

                prepared: list[dict[str, Any]] = []
                for r in rows:
                    total = float(r["total"] or 0)
                    paid = float(r["paid"] or 0)
                    due = total - paid
                    if due <= 0.01:
                        continue

                    end_str = str(r["end_date"] or "")
                    days = "-"
                    try:
                        end = datetime.strptime(end_str[:10], config.DATE_FORMAT).date()
                        days = str((today - end).days) if today > end else "0"
                    except Exception:
                        days = "-"

                    d = dict(r)
                    d["due"] = due
                    d["days"] = days
                    prepared.append(d)

                def apply() -> None:
                    try:
                        for i in self.tree.get_children():
                            self.tree.delete(i)

                        self._dues_rows = prepared
                        for rr in prepared:
                            name = f"{rr.get('first_name', '')} {rr.get('last_name', '')}".strip()
                            self.tree.insert(
                                "",
                                "end",
                                iid=str(rr.get("subscription_id")),
                                values=(
                                    name,
                                    rr.get("phone"),
                                    _fmt_money(float(rr.get("due") or 0), db=self.db),
                                    rr.get("last_payment") or "-",
                                    rr.get("days") or "-",
                                    "تسجيل",
                                ),
                            )
                    finally:
                        self._set_loading(False)
                        if not initial:
                            self._toast_success("تم تحديث البيانات بنجاح")

                self.after(0, apply)
            except Exception as e:
                def fail() -> None:
                    self._set_loading(False)
                    try:
                        messagebox.showerror("خطأ", f"فشل تحديث البيانات: {e}", parent=self)
                    except Exception:
                        pass

                self.after(0, fail)

        threading.Thread(target=worker, daemon=True).start()

    def _load(self) -> None:
        for i in self.tree.get_children():
            self.tree.delete(i)

        today = date.today()

        with self.db.get_connection() as conn:
            rows = conn.execute(
                """
                SELECT s.id AS subscription_id,
                       m.id AS member_id,
                       m.first_name, m.last_name, m.phone,
                       st.price AS total,
                       s.amount_paid AS paid,
                       s.end_date,
                       (
                           SELECT MAX(date(payment_date))
                           FROM payments p
                           WHERE p.member_id = m.id
                       ) AS last_payment
                FROM subscriptions s
                JOIN members m ON m.id = s.member_id
                JOIN subscription_types st ON st.id = s.subscription_type_id
                WHERE s.status != 'cancelled'
                  AND COALESCE(s.invoice_status, 'unpaid') = 'unpaid'
                ORDER BY date(s.end_date) ASC
                """
            ).fetchall()

        self._dues_rows: list[dict[str, Any]] = []
        for r in rows:
            total = float(r["total"] or 0)
            paid = float(r["paid"] or 0)
            due = total - paid
            if due <= 0.01:
                continue

            end_str = str(r["end_date"] or "")
            days = "-"
            try:
                end = datetime.strptime(end_str[:10], config.DATE_FORMAT).date()
                days = str((today - end).days) if today > end else "0"
            except Exception:
                days = "-"

            rowd = dict(r)
            rowd["due"] = due
            self._dues_rows.append(rowd)

            name = f"{r['first_name']} {r['last_name']}".strip()
            self.tree.insert(
                "",
                "end",
                iid=str(r["subscription_id"]),
                values=(
                    name,
                    r["phone"],
                    _fmt_money(due, db=self.db),
                    r["last_payment"] or "-",
                    days,
                    "تسجيل",
                ),
            )

    def _selected(self) -> dict[str, Any] | None:
        sel = self.tree.selection()
        if not sel:
            return None
        sid = int(sel[0])
        for r in self._dues_rows:
            if int(r["subscription_id"]) == sid:
                return r
        return None

    def _record_for_selected(self) -> None:
        r = self._selected()
        if not r:
            return

        # Open record payment dialog with member pre-selected (simplified)
        dlg = RecordPaymentDialog(self, self.db, self.user_data)
        dlg.member_search_var.set(str(r.get("phone") or ""))
        dlg._search_members()
        try:
            dlg.results.selection_set(0)
            dlg._on_select()
            if dlg.selected_member is not None and r.get("subscription_id"):
                dlg.selected_member["sub_id"] = int(r["subscription_id"])
            dlg.amount_var.set(f"{float(r.get('due') or 0):.0f}")
        except Exception:
            pass

        self.wait_window(dlg)
        if dlg.saved:
            self.did_change = True
            self._load()

    def _export_csv(self) -> None:
        from tkinter import filedialog
        import csv

        path = filedialog.asksaveasfilename(title="تصدير", defaultextension=".csv", filetypes=[("CSV", "*.csv")])
        if not path:
            return

        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["اسم العضو", "الهاتف", "المبلغ المستحق", "آخر دفعة", "أيام التأخير"])
            for r in self._dues_rows:
                name = f"{r.get('first_name', '')} {r.get('last_name', '')}".strip()
                w.writerow([name, r.get("phone", ""), float(r.get("due", 0)), r.get("last_payment", "-"), "-"])

        Messagebox.ok(title="تم", message="تم التصدير", parent=self)


class PaidInvoicesDialog(tk.Toplevel):
    """Dialog listing paid invoices (paid subscriptions)."""

    def __init__(self, parent: tk.Misc, db: DatabaseManager) -> None:
        super().__init__(parent)
        self.db = db
        self._loading: bool = False

        self.title("الفواتير المدفوعة")
        self.geometry("860x520")
        self.minsize(520, 360)
        self.resizable(True, True)
        self.grab_set()

        container = tb.Frame(self, padding=12)
        container.pack(fill="both", expand=True)

        cols = ("member", "phone", "total", "paid", "paid_at", "end_date")
        self.tree = ttk.Treeview(container, columns=cols, show="headings")
        self.tree.heading("member", text="اسم العضو")
        self.tree.heading("phone", text="الهاتف")
        self.tree.heading("total", text="الإجمالي")
        self.tree.heading("paid", text="المدفوع")
        self.tree.heading("paid_at", text="تاريخ الدفع")
        self.tree.heading("end_date", text="نهاية الاشتراك")

        self.tree.column("member", width=240, anchor="e")
        self.tree.column("phone", width=120, anchor="center")
        self.tree.column("total", width=120, anchor="center")
        self.tree.column("paid", width=120, anchor="center")
        self.tree.column("paid_at", width=120, anchor="center")
        self.tree.column("end_date", width=120, anchor="center")

        vsb = ttk.Scrollbar(container, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)

        self.tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

        btns = tb.Frame(container)
        btns.pack(fill="x", pady=(10, 0))
        self.btn_refresh = tb.Button(btns, text="🔄 تحديث", bootstyle="primary", command=self.refresh)
        self.btn_refresh.pack(side="left", padx=6)
        tb.Button(btns, text="إغلاق", bootstyle="secondary", command=self.destroy).pack(side="left")

        self._status_var = tk.StringVar(value="")
        self._status_label = tb.Label(btns, textvariable=self._status_var, font=FONTS["small"], anchor="e")
        self._status_label.pack(side="right")

        self._spinner = ttk.Progressbar(btns, mode="indeterminate", length=120)
        self._spinner.pack(side="right", padx=6)
        self._spinner.stop()
        self._spinner.pack_forget()

        self.refresh(initial=True)

    def _set_loading(self, value: bool) -> None:
        self._loading = bool(value)
        try:
            if self._loading:
                self.btn_refresh.configure(state="disabled")
                self._spinner.pack(side="right", padx=6)
                self._spinner.start(12)
                self._status_var.set("جاري التحديث...")
            else:
                self._spinner.stop()
                self._spinner.pack_forget()
                self.btn_refresh.configure(state="normal")
        except Exception:
            pass

    def _toast_success(self, msg: str) -> None:
        try:
            self._status_var.set(msg)

            def clear() -> None:
                try:
                    self._status_var.set("")
                except Exception:
                    pass

            self.after(1600, clear)
        except Exception:
            pass

    def refresh(self, initial: bool = False) -> None:
        if self._loading:
            return

        self._set_loading(True)

        def worker() -> None:
            try:
                with self.db.get_connection() as conn:
                    rows = conn.execute(
                        """
                        SELECT s.id AS subscription_id,
                               m.first_name, m.last_name, m.phone,
                               st.price AS total,
                               s.amount_paid AS paid,
                               s.paid_at,
                               s.end_date
                        FROM subscriptions s
                        JOIN members m ON m.id = s.member_id
                        JOIN subscription_types st ON st.id = s.subscription_type_id
                        WHERE s.status != 'cancelled'
                          AND COALESCE(s.invoice_status, 'unpaid') = 'paid'
                        ORDER BY date(COALESCE(s.paid_at, s.end_date)) DESC, s.id DESC
                        LIMIT 500
                        """
                    ).fetchall()

                prepared = [dict(r) for r in rows]

                def apply() -> None:
                    try:
                        for i in self.tree.get_children():
                            self.tree.delete(i)

                        for r in prepared:
                            name = f"{r.get('first_name', '')} {r.get('last_name', '')}".strip()
                            self.tree.insert(
                                "",
                                "end",
                                iid=str(r.get("subscription_id")),
                                values=(
                                    name,
                                    r.get("phone"),
                                    _fmt_money(float(r.get("total") or 0), db=self.db),
                                    _fmt_money(float(r.get("paid") or 0), db=self.db),
                                    r.get("paid_at") or "-",
                                    r.get("end_date") or "-",
                                ),
                            )
                    finally:
                        self._set_loading(False)
                        if not initial:
                            self._toast_success("تم تحديث البيانات بنجاح")

                self.after(0, apply)
            except Exception as e:
                def fail() -> None:
                    self._set_loading(False)
                    try:
                        messagebox.showerror("خطأ", f"فشل تحديث البيانات: {e}", parent=self)
                    except Exception:
                        pass

                self.after(0, fail)

        threading.Thread(target=worker, daemon=True).start()

    def _load(self) -> None:
        for i in self.tree.get_children():
            self.tree.delete(i)

        with self.db.get_connection() as conn:
            rows = conn.execute(
                """
                SELECT s.id AS subscription_id,
                       m.first_name, m.last_name, m.phone,
                       st.price AS total,
                       s.amount_paid AS paid,
                       s.paid_at,
                       s.end_date
                FROM subscriptions s
                JOIN members m ON m.id = s.member_id
                JOIN subscription_types st ON st.id = s.subscription_type_id
                WHERE s.status != 'cancelled'
                  AND COALESCE(s.invoice_status, 'unpaid') = 'paid'
                ORDER BY date(COALESCE(s.paid_at, s.end_date)) DESC, s.id DESC
                LIMIT 500
                """
            ).fetchall()

        for r in rows:
            name = f"{r['first_name']} {r['last_name']}".strip()
            self.tree.insert(
                "",
                "end",
                iid=str(r["subscription_id"]),
                values=(
                    name,
                    r["phone"],
                    _fmt_money(float(r["total"] or 0), db=self.db),
                    _fmt_money(float(r["paid"] or 0), db=self.db),
                    r["paid_at"] or "-",
                    r["end_date"] or "-",
                ),
            )


class DailyCashRegisterDialog(tk.Toplevel):
    """Daily cash register summary dialog."""

    def __init__(self, parent: tk.Misc, db: DatabaseManager) -> None:
        super().__init__(parent)
        self.db = db

        self.title("📋 تقرير الصندوق اليومي")
        self.geometry("520x520")
        self.minsize(420, 420)
        self.resizable(True, True)
        self.grab_set()

        container = tb.Frame(self, padding=14)
        container.pack(fill="both", expand=True)

        today = date.today().isoformat()

        with self.db.get_connection() as conn:
            total = conn.execute(
                "SELECT COALESCE(SUM(amount), 0) AS total FROM payments WHERE date(payment_date) = date(?)",
                (today,),
            ).fetchone()["total"]

            rows = conn.execute(
                """
                SELECT payment_method, COALESCE(SUM(amount), 0) AS total, COUNT(*) AS c
                FROM payments
                WHERE date(payment_date) = date(?)
                GROUP BY payment_method
                """,
                (today,),
            ).fetchall()

            count = conn.execute(
                "SELECT COUNT(*) AS c FROM payments WHERE date(payment_date) = date(?)",
                (today,),
            ).fetchone()["c"]

        by = {"cash": 0.0, "card": 0.0, "transfer": 0.0, "cheque": 0.0}
        for r in rows:
            k = str(r["payment_method"] or "")
            if k in by:
                by[k] = float(r["total"] or 0)

        avg = 0.0
        try:
            avg = float(total) / max(1, int(count))
        except Exception:
            avg = 0.0

        tb.Label(container, text="📋 تقرير الصندوق اليومي", font=FONTS["heading"], anchor="center").pack(fill="x")
        tb.Label(container, text=today, font=FONTS["body"], anchor="center").pack(fill="x", pady=(2, 14))

        box = tk.Text(container, height=16, wrap="word")
        box.pack(fill="both", expand=True)

        lines = []
        lines.append(f"إجمالي المقبوضات: {_fmt_money(float(total), db=self.db)}")
        lines.append("-")
        lines.append("تفصيل طرق الدفع:")
        lines.append(f"  • نقدي: {_fmt_money(by['cash'], db=self.db)}")
        lines.append(f"  • بطاقة: {_fmt_money(by['card'], db=self.db)}")
        lines.append(f"  • تحويل: {_fmt_money(by['transfer'], db=self.db)}")
        lines.append(f"  • شيك: {_fmt_money(by['cheque'], db=self.db)}")
        lines.append("-")
        lines.append(f"عدد العمليات: {int(count)}")
        lines.append(f"متوسط العملية: {_fmt_money(avg, db=self.db)}")

        self._cash_report_text = "\n".join(lines)
        box.insert("1.0", self._cash_report_text)
        box.configure(state="disabled")

        btns = tb.Frame(container)
        btns.pack(fill="x", pady=10)
        tb.Button(btns, text="🌐 فتح في المتصفح", bootstyle="secondary", command=lambda: self._open_browser()).pack(side="left")
        tb.Button(btns, text="🖨️ طباعة", bootstyle="secondary", command=lambda: self._print()).pack(side="left", padx=6)
        tb.Button(btns, text="إغلاق", bootstyle="secondary", command=self.destroy).pack(side="left")

        self._cash_report_html = _generate_daily_cash_register_html(
            db=self.db,
            today=today,
            total=float(total or 0),
            by=by,
            count=int(count or 0),
            avg=float(avg or 0),
        )

    def _open_browser(self) -> None:
        try:
            open_html_windows(self._cash_report_html, filename_prefix="daily_cash")
        except Exception:
            messagebox.showwarning("تنبيه", "تعذر فتح التقرير في المتصفح")

    def _print(self) -> None:
        try:
            try:
                print_html_windows(self._cash_report_html, filename_prefix="daily_cash")
                return
            except Exception:
                pass

            content = str(getattr(self, "_cash_report_text", "") or "").strip()
            if not content:
                content = "تقرير الصندوق اليومي"
            print_text_windows(content, filename_prefix="daily_cash")
        except Exception:
            messagebox.showwarning("تنبيه", "تعذر بدء الطباعة تلقائياً")


if __name__ == "__main__":
    root = tb.Window(themename="cosmo")
    root.title("PaymentsFrame Test")
    db = DatabaseManager()
    frame = PaymentsFrame(root, db, {"id": 1, "username": "admin", "role": "admin"})
    frame.pack(fill="both", expand=True)
    root.geometry("1200x700")
    root.mainloop()
