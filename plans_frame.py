"""Plans management frame for Gym Management System.

NOTE:
The current project database schema uses `subscription_types` (from database.py) rather than a
separate `plans` table.

This module treats subscription_types as plans and stores advanced plan options (discounts,
VAT, features, access options, badges) as JSON inside `subscription_types.description`.

RTL Arabic UI.
"""

from __future__ import annotations

import json
import tkinter as tk
from datetime import date, datetime
from tkinter import messagebox
from tkinter import ttk
from typing import Any

import ttkbootstrap as tb
from ttkbootstrap.constants import *  # noqa: F403
from ttkbootstrap.dialogs import Messagebox
from ttkbootstrap.widgets import Meter

import config
from database import DatabaseManager
from scrollable_frame import ScrollableFrame
from utils import format_money


# Local styling (to avoid circular imports)
COLORS = {
    "primary": "#2563eb",
    "primary_dark": "#1e40af",
    "secondary": "#64748b",
    "success": "#059669",
    "warning": "#d97706",
    "danger": "#dc2626",
    "background": "#f1f5f9",
    "sidebar": "#1e293b",
    "sidebar_hover": "#334155",
    "sidebar_active": "#3b82f6",
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


PLAN_TYPE_COLORS = {
    "monthly": "#3498db",
    "quarterly": "#27ae60",
    "semi_annual": "#f39c12",
    "annual": "#f1c40f",
    "trial": "#95a5a6",
    "custom": "#3498db",
}


def _safe_json_load(s: str | None) -> dict[str, Any]:
    if not s:
        return {}
    try:
        data = json.loads(s)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _safe_json_dump(d: dict[str, Any]) -> str:
    try:
        return json.dumps(d, ensure_ascii=False)
    except Exception:
        return "{}"


def _fmt_money(amount: float, db: DatabaseManager | None = None) -> str:
    return format_money(amount, db=db, decimals=0)


def _plan_type_from_duration(months: int, price: float) -> str:
    if price <= 0:
        return "trial"
    if months == 1:
        return "monthly"
    if months == 3:
        return "quarterly"
    if months == 6:
        return "semi_annual"
    if months == 12:
        return "annual"
    return "custom"


class PlansFrame(tb.Frame):
    """Plans management (subscription_types) with a cards grid and details panel."""

    def __init__(self, parent: ttk.Widget, db: DatabaseManager | None, user_data: dict | None = None) -> None:
        super().__init__(parent)
        self.db = db
        self.user_data = user_data or {}

        self.selected_plan_id: int | None = None
        self.plan_cards: dict[int, ttk.Widget] = {}
        self._plans: list[dict[str, Any]] = []

        self.configure(padding=10)
        self.setup_ui()
        self.load_plans()
        self._bind_shortcuts()

    # ------------------------------
    # UI setup
    # ------------------------------

    def setup_ui(self) -> None:
        self._create_header()
        self._create_cards_area()
        self._create_details_panel()

    def _create_header(self) -> None:
        header = tb.Frame(self)
        header.pack(fill="x", pady=(0, 10))

        tb.Label(header, text="📦 إدارة الباقات والاشتراكات", font=FONTS["heading"], anchor="e").pack(side="right")

        btns = tb.Frame(header)
        btns.pack(side="left")

        tb.Button(btns, text="➕ باقة جديدة", bootstyle="success", command=self.new_plan).pack(side="left", padx=6)
        tb.Button(btns, text="📊 إحصائيات الباقات", bootstyle="info", command=self.show_plan_statistics).pack(side="left", padx=6)
        tb.Button(btns, text="⚙️ إعدادات الأسعار", bootstyle="secondary", command=self.show_price_settings).pack(side="left", padx=6)
        tb.Button(btns, text="🔄 تحديث", bootstyle="secondary", command=self.load_plans).pack(side="left")

    def _create_cards_area(self) -> None:
        # Top section (~60%)
        top = tb.Frame(self)
        top.pack(fill="both", expand=True)

        # Scrollable canvas
        self.cards_canvas = tk.Canvas(top, highlightthickness=0, background=COLORS["background"])
        self.cards_canvas.pack(side="left", fill="both", expand=True)

        vsb = ttk.Scrollbar(top, orient="vertical", command=self.cards_canvas.yview)
        vsb.pack(side="right", fill="y")
        self.cards_canvas.configure(yscrollcommand=vsb.set)

        self.cards_container = tb.Frame(self.cards_canvas)
        self.cards_window = self.cards_canvas.create_window((0, 0), window=self.cards_container, anchor="nw")

        def on_configure(_e):
            self.cards_canvas.configure(scrollregion=self.cards_canvas.bbox("all"))

        def on_canvas_resize(event):
            # Keep inner frame width aligned with canvas width
            self.cards_canvas.itemconfigure(self.cards_window, width=event.width)

        self.cards_container.bind("<Configure>", on_configure)
        self.cards_canvas.bind("<Configure>", on_canvas_resize)

        # Mouse wheel scrolling
        def on_mousewheel(event):
            try:
                self.cards_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
            except Exception:
                pass

        self.cards_canvas.bind_all("<MouseWheel>", on_mousewheel)

    def _create_details_panel(self) -> None:
        # Bottom section (~40%)
        self.details = tb.Labelframe(self, text="📋 تفاصيل الباقة", padding=12)
        self.details.pack(fill="x", pady=(10, 0))

        self.details_title = tb.Label(self.details, text="اختر باقة لعرض التفاصيل", font=FONTS["subheading"], anchor="e")
        self.details_title.pack(fill="x")

        grid = tb.Frame(self.details)
        grid.pack(fill="x", pady=(10, 0))

        self.basic_box = tb.Labelframe(grid, text="معلومات أساسية", padding=10)
        self.price_box = tb.Labelframe(grid, text="الأسعار", padding=10)
        self.stats_box = tb.Labelframe(grid, text="الإحصائيات", padding=10)

        self.basic_box.pack(side="right", fill="both", expand=True, padx=(0, 8))
        self.price_box.pack(side="right", fill="both", expand=True, padx=(0, 8))
        self.stats_box.pack(side="right", fill="both", expand=True)

        self.basic_text = tk.Text(self.basic_box, height=6, wrap="word")
        self.basic_text.pack(fill="both", expand=True)
        self.basic_text.configure(state="disabled")

        self.price_text = tk.Text(self.price_box, height=6, wrap="word")
        self.price_text.pack(fill="both", expand=True)
        self.price_text.configure(state="disabled")

        self.stats_text = tk.Text(self.stats_box, height=6, wrap="word")
        self.stats_text.pack(fill="both", expand=True)
        self.stats_text.configure(state="disabled")

        desc = tb.Frame(self.details)
        desc.pack(fill="x", pady=(10, 0))
        tb.Label(desc, text="📝 الوصف:", font=("Cairo", 10, "bold"), anchor="e").pack(side="right")
        self.desc_label = tb.Label(desc, text="-", font=FONTS["small"], anchor="e", justify="right", foreground=COLORS["text_light"])
        self.desc_label.pack(side="right", fill="x", expand=True, padx=(10, 0))

        actions = tb.Frame(self.details)
        actions.pack(fill="x", pady=(10, 0))

        self.btn_edit = tb.Button(actions, text="✏️ تعديل", bootstyle="info", command=self.edit_selected)
        self.btn_copy = tb.Button(actions, text="📋 نسخ", bootstyle="secondary", command=self.duplicate_selected)
        self.btn_delete = tb.Button(actions, text="🗑️", bootstyle="danger", command=self.delete_selected)
        self.btn_toggle = tb.Button(actions, text="تفعيل/إيقاف", bootstyle="secondary", command=self.toggle_active_selected)

        self.btn_edit.pack(side="left", padx=6)
        self.btn_copy.pack(side="left", padx=6)
        self.btn_delete.pack(side="left", padx=6)
        self.btn_toggle.pack(side="left")

        self._set_details_buttons_state(enabled=False)

    def _set_details_buttons_state(self, enabled: bool) -> None:
        state = "normal" if enabled else "disabled"
        self.btn_edit.configure(state=state)
        self.btn_copy.configure(state=state)
        self.btn_delete.configure(state=state)
        self.btn_toggle.configure(state=state)

    # ------------------------------
    # Data loading
    # ------------------------------

    def load_plans(self) -> None:
        if self.db is None:
            messagebox.showerror("خطأ", "قاعدة البيانات غير جاهزة")
            return

        try:
            self._plans = self.db.get_all_subscription_types(active_only=False)
        except Exception as e:
            messagebox.showerror("خطأ", f"تعذر تحميل الباقات: {e}")
            self._plans = []

        for w in self.cards_container.winfo_children():
            w.destroy()
        self.plan_cards.clear()

        # Cards grid (3-4 per row based on width)
        max_cols = 4
        for i in range(max_cols):
            self.cards_container.columnconfigure(i, weight=1)

        row = 0
        col = 0

        # Determine most popular plan by active subscriptions
        popular_id = self._get_most_popular_plan_id()

        for p in self._plans:
            pid = int(p["id"])
            card = self.create_plan_card(self.cards_container, p, is_popular=(pid == popular_id))
            card.grid(row=row, column=col, padx=10, pady=10, sticky="nsew")
            self.plan_cards[pid] = card

            col += 1
            if col >= max_cols:
                col = 0
                row += 1

        if self.selected_plan_id and any(int(x["id"]) == self.selected_plan_id for x in self._plans):
            self.select_plan(self.selected_plan_id)
        else:
            self.selected_plan_id = None
            self._render_details(None)

    def _get_most_popular_plan_id(self) -> int | None:
        if self.db is None:
            return None

        today = date.today().isoformat()
        try:
            with self.db.get_connection() as conn:
                row = conn.execute(
                    """
                    SELECT subscription_type_id, COUNT(*) AS c
                    FROM subscriptions
                    WHERE status = 'active' AND date(end_date) >= date(?)
                    GROUP BY subscription_type_id
                    ORDER BY c DESC
                    LIMIT 1
                    """,
                    (today,),
                ).fetchone()
            if row:
                return int(row["subscription_type_id"])
        except Exception:
            pass
        return None

    def get_plan_subscriber_count(self, plan_id: int) -> int:
        if self.db is None:
            return 0

        today = date.today().isoformat()
        try:
            with self.db.get_connection() as conn:
                row = conn.execute(
                    """
                    SELECT COUNT(*) AS c
                    FROM subscriptions
                    WHERE subscription_type_id = ?
                      AND status = 'active'
                      AND date(end_date) >= date(?)
                    """,
                    (plan_id, today),
                ).fetchone()
            return int(row["c"]) if row else 0
        except Exception:
            return 0

    def _get_plan_stats(self, plan_id: int) -> dict[str, Any]:
        if self.db is None:
            return {"total": 0, "active": 0, "expired": 0, "revenue": 0.0, "this_month": 0}

        today = date.today().isoformat()
        ms = date.today().replace(day=1).isoformat()

        try:
            with self.db.get_connection() as conn:
                cur = conn.cursor()
                total = cur.execute(
                    "SELECT COUNT(*) AS c FROM subscriptions WHERE subscription_type_id = ?",
                    (plan_id,),
                ).fetchone()["c"]

                active = cur.execute(
                    """
                    SELECT COUNT(*) AS c
                    FROM subscriptions
                    WHERE subscription_type_id = ?
                      AND status = 'active'
                      AND date(end_date) >= date(?)
                    """,
                    (plan_id, today),
                ).fetchone()["c"]

                expired = cur.execute(
                    """
                    SELECT COUNT(*) AS c
                    FROM subscriptions
                    WHERE subscription_type_id = ?
                      AND (status = 'expired' OR date(end_date) < date(?))
                    """,
                    (plan_id, today),
                ).fetchone()["c"]

                revenue = cur.execute(
                    """
                    SELECT COALESCE(SUM(p.amount), 0) AS total
                    FROM payments p
                    JOIN subscriptions s ON s.id = p.subscription_id
                    WHERE s.subscription_type_id = ?
                    """,
                    (plan_id,),
                ).fetchone()["total"]

                this_month = cur.execute(
                    """
                    SELECT COUNT(*) AS c
                    FROM subscriptions
                    WHERE subscription_type_id = ? AND date(start_date) >= date(?)
                    """,
                    (plan_id, ms),
                ).fetchone()["c"]

            return {
                "total": int(total),
                "active": int(active),
                "expired": int(expired),
                "revenue": float(revenue),
                "this_month": int(this_month),
            }
        except Exception:
            return {"total": 0, "active": 0, "expired": 0, "revenue": 0.0, "this_month": 0}

    # ------------------------------
    # Cards
    # ------------------------------

    def create_plan_card(self, parent: ttk.Widget, plan_data: dict[str, Any], is_popular: bool = False) -> ttk.Frame:
        pid = int(plan_data["id"])
        name = str(plan_data.get("name_ar") or "")
        price = float(plan_data.get("price") or 0)
        months = int(plan_data.get("duration_months") or 1)
        is_active = int(plan_data.get("is_active") or 1) == 1

        meta = _safe_json_load(plan_data.get("description"))
        plan_type = str(meta.get("plan_type") or _plan_type_from_duration(months, price))

        border = PLAN_TYPE_COLORS.get(plan_type, "#3498db")

        card = tb.Frame(parent, padding=12)
        card.configure(borderwidth=2, relief="solid")

        try:
            card.configure(highlightbackground=border, highlightcolor=border, highlightthickness=2)
        except Exception:
            pass

        if not is_active:
            card.configure(style="secondary.TFrame")

        if is_popular or bool(meta.get("is_featured")):
            badge = tb.Label(card, text="⭐ الأكثر مبيعاً" if is_popular else "⭐ باقة مميزة", bootstyle="warning")
            badge.pack(anchor="ne")

        tb.Label(card, text=f"💪 {name}", font=("Cairo", 14, "bold"), anchor="center").pack(fill="x", pady=(6, 2))
        tb.Label(card, text=_fmt_money(price, db=self.db), font=("Cairo", 22, "bold"), anchor="center").pack(fill="x", pady=(2, 2))

        tb.Label(card, text=f"مدة: {months * 30} يوم تقريباً", font=FONTS["small"], anchor="center").pack(fill="x")

        access_limit = int(meta.get("access_limit", 0) or 0)
        access_text = "الدخول: غير محدود" if access_limit == 0 else f"الدخول: {access_limit} مرة"
        tb.Label(card, text=access_text, font=FONTS["small"], foreground=COLORS["text_light"], anchor="center").pack(fill="x")

        ttk.Separator(card).pack(fill="x", pady=10)

        active_subs = self.get_plan_subscriber_count(pid)
        tb.Label(card, text=f"👥 {active_subs} مشترك حالي", font=FONTS["small"], anchor="e").pack(fill="x")

        btn_row = tb.Frame(card)
        btn_row.pack(pady=10)

        tb.Button(btn_row, text="✏️", width=3, bootstyle="info", command=lambda: self.edit_plan(pid)).pack(side="left", padx=3)
        tb.Button(btn_row, text="📋", width=3, bootstyle="secondary", command=lambda: self.duplicate_plan(pid)).pack(side="left", padx=3)
        tb.Button(btn_row, text="🗑️", width=3, bootstyle="danger", command=lambda: self.delete_plan(pid)).pack(side="left", padx=3)

        status_text = "● نشط" if is_active else "● غير نشط"
        status_style = "success" if is_active else "secondary"
        tb.Label(card, text=status_text, bootstyle=status_style, anchor="e").pack(fill="x", pady=(4, 0))

        def on_click(_e):
            self.select_plan(pid)

        # Bind click to frame and children
        card.bind("<Button-1>", on_click)
        for child in card.winfo_children():
            try:
                child.bind("<Button-1>", on_click)
            except Exception:
                pass

        return card

    # ------------------------------
    # Selection / details
    # ------------------------------

    def select_plan(self, plan_id: int) -> None:
        self.selected_plan_id = plan_id
        plan = next((p for p in self._plans if int(p["id"]) == plan_id), None)
        self._render_details(plan)

    def _render_details(self, plan: dict[str, Any] | None) -> None:
        if not plan:
            self.details_title.configure(text="اختر باقة لعرض التفاصيل")
            self.desc_label.configure(text="-")
            self._set_text(self.basic_text, "")
            self._set_text(self.price_text, "")
            self._set_text(self.stats_text, "")
            self._set_details_buttons_state(False)
            return

        self._set_details_buttons_state(True)

        meta = _safe_json_load(plan.get("description"))

        name = str(plan.get("name_ar") or "")
        self.details_title.configure(text=f"📋 تفاصيل الباقة: {name}")

        months = int(plan.get("duration_months") or 1)
        price = float(plan.get("price") or 0)
        is_active = int(plan.get("is_active") or 1) == 1

        plan_type = str(meta.get("plan_type") or _plan_type_from_duration(months, price))
        plan_type_ar = {
            "monthly": "شهري",
            "quarterly": "ربع سنوي",
            "semi_annual": "نصف سنوي",
            "annual": "سنوي",
            "trial": "تجريبي",
            "custom": "مخصص",
        }.get(plan_type, "-")

        basic = []
        basic.append(f"الاسم: {name}")
        basic.append(f"المدة: {months} شهر")
        basic.append(f"النوع: {plan_type_ar}")
        basic.append(f"الحالة: {'نشط' if is_active else 'غير نشط'}")
        basic.append(f"الدخول: {'مفتوح' if int(meta.get('access_limit', 0) or 0) == 0 else 'محدود'}")

        discount = float(meta.get("discount_percent", 0) or 0)
        vat_included = bool(meta.get("vat_included", False))
        vat_rate = float(self._get_setting("vat_rate", "15") or 15)

        after_discount = price * (1 - (discount / 100.0))
        vat_amount = after_discount * (vat_rate / 100.0)
        total_with_vat = after_discount if vat_included else after_discount + vat_amount

        pricing = []
        pricing.append(f"السعر: {_fmt_money(price, db=self.db)}")
        pricing.append(f"خصم: {discount:.0f}%")
        pricing.append(f"بعد الخصم: {_fmt_money(after_discount, db=self.db)}")
        pricing.append(f"ض.ق.م: {_fmt_money(vat_amount, db=self.db)}")
        pricing.append(f"الإجمالي: {_fmt_money(total_with_vat, db=self.db)}")

        stats = self._get_plan_stats(int(plan["id"]))
        stat_lines = []
        stat_lines.append(f"إجمالي: {stats['total']}")
        stat_lines.append(f"نشط: {stats['active']}")
        stat_lines.append(f"منتهي: {stats['expired']}")
        stat_lines.append(f"إيرادات: {_fmt_money(float(stats['revenue']), db=self.db)}")
        stat_lines.append(f"هذا الشهر: {stats['this_month']}")

        self._set_text(self.basic_text, "\n".join(basic))
        self._set_text(self.price_text, "\n".join(pricing))
        self._set_text(self.stats_text, "\n".join(stat_lines))

        desc = str(meta.get("description") or plan.get("description") or "")
        self.desc_label.configure(text=(desc if desc else "-"))

    def _set_text(self, widget: tk.Text, value: str) -> None:
        widget.configure(state="normal")
        widget.delete("1.0", "end")
        widget.insert("1.0", value)
        widget.configure(state="disabled")

    # ------------------------------
    # Actions
    # ------------------------------

    def new_plan(self) -> None:
        self.show_plan_dialog(plan_id=None)

    def edit_selected(self) -> None:
        if self.selected_plan_id is None:
            return
        self.show_plan_dialog(plan_id=self.selected_plan_id)

    def duplicate_selected(self) -> None:
        if self.selected_plan_id is None:
            return
        self.duplicate_plan(self.selected_plan_id)

    def delete_selected(self) -> None:
        if self.selected_plan_id is None:
            return
        self.delete_plan(self.selected_plan_id)

    def toggle_active_selected(self) -> None:
        if self.selected_plan_id is None or self.db is None:
            return

        plan = next((p for p in self._plans if int(p["id"]) == self.selected_plan_id), None)
        if not plan:
            return

        new_active = 0 if int(plan.get("is_active") or 1) == 1 else 1
        ok, msg = self.db.update_subscription_type(int(plan["id"]), is_active=new_active)
        if not ok:
            messagebox.showerror("خطأ", msg)
            return

        self.load_plans()

    def edit_plan(self, plan_id: int) -> None:
        self.show_plan_dialog(plan_id=plan_id)

    def duplicate_plan(self, plan_id: int) -> None:
        if self.db is None:
            return

        plan = next((p for p in self._plans if int(p["id"]) == plan_id), None)
        if not plan:
            return

        meta = _safe_json_load(plan.get("description"))
        meta["is_featured"] = False

        ok, msg, _new_id = self.db.create_subscription_type(
            name_ar=f"{plan.get('name_ar', '')} (نسخة)",
            name_en=plan.get("name_en"),
            duration_months=int(plan.get("duration_months") or 1),
            price=float(plan.get("price") or 0),
            description=_safe_json_dump(meta),
            is_active=0,
        )

        if not ok:
            messagebox.showerror("خطأ", msg)
            return

        self.load_plans()

    def delete_plan(self, plan_id: int) -> None:
        if self.db is None:
            return

        active_count = self.get_plan_subscriber_count(plan_id)
        if active_count > 0:
            messagebox.showerror("خطأ", f"لا يمكن حذف الباقة - يوجد {active_count} اشتراك نشط")
            return

        if not messagebox.askyesno("تأكيد", "هل أنت متأكد من حذف هذه الباقة؟"):
            return

        # No direct delete method in DatabaseManager; perform a safe delete via SQL.
        try:
            with self.db.get_connection() as conn:
                conn.execute("DELETE FROM subscription_types WHERE id = ?", (int(plan_id),))
                conn.commit()
        except Exception as e:
            messagebox.showerror("خطأ", f"فشل حذف الباقة: {e}")
            return

        self.selected_plan_id = None
        self.load_plans()

    # ------------------------------
    # Dialogs
    # ------------------------------

    def show_plan_dialog(self, plan_id: int | None) -> None:
        if self.db is None:
            return

        plan = None
        if plan_id is not None:
            plan = next((p for p in self._plans if int(p["id"]) == plan_id), None)

        dlg = PlanDialog(self.winfo_toplevel(), self.db, plan)
        self.wait_window(dlg)
        if dlg.saved:
            self.load_plans()
            if dlg.saved_plan_id is not None:
                self.select_plan(dlg.saved_plan_id)

    def show_plan_statistics(self) -> None:
        if self.db is None:
            return
        dlg = PlanStatisticsDialog(self.winfo_toplevel(), self.db)
        self.wait_window(dlg)

    def show_price_settings(self) -> None:
        if self.db is None:
            return
        dlg = PriceSettingsDialog(self.winfo_toplevel(), self.db)
        self.wait_window(dlg)
        # Refresh details to reflect VAT settings
        if self.selected_plan_id:
            plan = next((p for p in self._plans if int(p["id"]) == self.selected_plan_id), None)
            self._render_details(plan)

    # ------------------------------
    # Settings helpers
    # ------------------------------

    def _get_setting(self, key: str, default: str | None = None) -> str | None:
        if self.db is None:
            return default
        try:
            v = self.db.get_settings(key)
            return v if v is not None else default
        except Exception:
            return default

    def _bind_shortcuts(self) -> None:
        top = self.winfo_toplevel()
        top.bind("<Control-n>", lambda _e: self.new_plan())
        top.bind("<F5>", lambda _e: self.load_plans())
        top.bind("<Delete>", lambda _e: self.delete_selected())


class PlanDialog(tk.Toplevel):
    """Add/Edit plan dialog (stored in subscription_types + JSON meta in description)."""

    def __init__(self, parent: tk.Misc, db: DatabaseManager, plan: dict[str, Any] | None) -> None:
        super().__init__(parent)
        self.db = db
        self.plan = plan

        self.saved: bool = False
        self.saved_plan_id: int | None = None

        self.title("إضافة باقة جديدة" if plan is None else "تعديل الباقة")
        self.geometry("640x760")
        self.minsize(420, 520)
        self.resizable(True, True)
        self.grab_set()

        meta = _safe_json_load(plan.get("description")) if plan else {}

        self.var_name_ar = tk.StringVar(master=self, value=str(plan.get("name_ar") or "") if plan else "")
        self.var_name_en = tk.StringVar(master=self, value=str(plan.get("name_en") or "") if plan else "")
        self.var_plan_type = tk.StringVar(master=self, value=str(meta.get("plan_type") or "monthly"))
        self.var_duration_months = tk.IntVar(master=self, value=int(plan.get("duration_months") or 1) if plan else 1)
        self.var_price = tk.DoubleVar(master=self, value=float(plan.get("price") or 0) if plan else 0)
        self.var_discount = tk.DoubleVar(master=self, value=float(meta.get("discount_percent") or 0))
        self.var_vat_included = tk.BooleanVar(master=self, value=bool(meta.get("vat_included", False)))

        self.var_access_unlimited = tk.BooleanVar(master=self, value=int(meta.get("access_limit", 0) or 0) == 0)
        self.var_access_limit = tk.IntVar(master=self, value=int(meta.get("access_limit", 0) or 0))
        self.var_access_time = tk.StringVar(master=self, value=str(meta.get("access_time") or "all"))

        self.var_is_active = tk.BooleanVar(master=self, value=(int(plan.get("is_active") or 1) == 1) if plan else True)
        self.var_is_featured = tk.BooleanVar(master=self, value=bool(meta.get("is_featured", False)))
        self.var_show_in_registration = tk.BooleanVar(master=self, value=bool(meta.get("show_in_registration", True)))
        self.var_allow_auto_renewal = tk.BooleanVar(master=self, value=bool(meta.get("allow_auto_renewal", True)))

        self.var_description = tk.StringVar(master=self, value=str(meta.get("description") or ""))

        # Features
        feats = set(meta.get("features", []) or [])
        self.features_vars = {
            "all_equipment": tk.BooleanVar(master=self, value=("all_equipment" in feats)),
            "locker": tk.BooleanVar(master=self, value=("locker" in feats)),
            "personal_trainer": tk.BooleanVar(master=self, value=("personal_trainer" in feats)),
            "nutrition_plan": tk.BooleanVar(master=self, value=("nutrition_plan" in feats)),
            "parking": tk.BooleanVar(master=self, value=("parking" in feats)),
            "pool": tk.BooleanVar(master=self, value=("pool" in feats)),
            "sauna": tk.BooleanVar(master=self, value=("sauna" in feats)),
        }

        self._build_form()
        self._center()

        self.var_plan_type.trace_add("write", lambda *_: self._on_type_change())
        self.var_discount.trace_add("write", lambda *_: self._update_price_preview())
        self.var_price.trace_add("write", lambda *_: self._update_price_preview())
        self.var_vat_included.trace_add("write", lambda *_: self._update_price_preview())
        self.var_access_unlimited.trace_add("write", lambda *_: self._on_access_mode_change())

        self._on_type_change()
        self._update_price_preview()

        self.bind("<Escape>", lambda _e: self.destroy())

    def _build_form(self) -> None:
        outer = tb.Frame(self)
        outer.pack(fill="both", expand=True)

        scroll = ScrollableFrame(outer)
        scroll.pack(fill="both", expand=True)

        container = tb.Frame(scroll.inner, padding=14)
        container.pack(fill="both", expand=True)

        # Basic
        basic = tb.Labelframe(container, text="المعلومات الأساسية", padding=12)
        basic.pack(fill="x")

        self._row_entry(basic, "اسم الباقة *", self.var_name_ar)
        self._row_entry(basic, "اسم الباقة (إنجليزي)", self.var_name_en)

        types = [
            ("شهري", "monthly"),
            ("ربع سنوي", "quarterly"),
            ("نصف سنوي", "semi_annual"),
            ("سنوي", "annual"),
            ("تجريبي", "trial"),
            ("مخصص", "custom"),
        ]

        type_row = tb.Frame(basic)
        type_row.pack(fill="x", pady=6)
        tb.Label(type_row, text="نوع الباقة *", font=("Cairo", 10, "bold"), anchor="e").pack(side="right")
        self.type_combo = tb.Combobox(
            type_row,
            values=[t[0] for t in types],
            state="readonly",
            justify="right",
            width=18,
        )
        self.type_combo.pack(side="left")

        # Map current var_plan_type to combo
        current_label = {v: k for k, v in types}.get(self.var_plan_type.get(), "شهري")
        try:
            self.type_combo.set(current_label)
        except Exception:
            pass

        def on_type_combo(_e):
            label = self.type_combo.get().strip()
            mapping = {k: v for k, v in types}
            self.var_plan_type.set(mapping.get(label, "monthly"))

        self.type_combo.bind("<<ComboboxSelected>>", on_type_combo)

        dur_row = tb.Frame(basic)
        dur_row.pack(fill="x", pady=6)
        tb.Label(dur_row, text="المدة (بالأشهر) *", font=("Cairo", 10, "bold"), anchor="e").pack(side="right")
        self.duration_entry = tb.Entry(dur_row, textvariable=self.var_duration_months, justify="right", width=10)
        self.duration_entry.pack(side="left")

        # Pricing
        pricing = tb.Labelframe(container, text="التسعير", padding=12)
        pricing.pack(fill="x", pady=10)

        self._row_entry(pricing, "السعر الأساسي *", self.var_price)

        disc_row = tb.Frame(pricing)
        disc_row.pack(fill="x", pady=6)
        tb.Label(disc_row, text="نسبة الخصم", font=("Cairo", 10, "bold"), anchor="e").pack(side="right")
        tb.Entry(disc_row, textvariable=self.var_discount, justify="right", width=10).pack(side="right", padx=(10, 0))
        tb.Label(disc_row, text="%", font=FONTS["small"]).pack(side="right", padx=(6, 0))

        self.price_preview = tb.Label(pricing, text="", font=FONTS["small"], anchor="e", justify="right")
        self.price_preview.pack(fill="x", pady=(6, 0))

        tb.Checkbutton(pricing, text="شامل ضريبة القيمة المضافة", variable=self.var_vat_included, bootstyle="round-toggle").pack(
            anchor="e", pady=(8, 0)
        )

        # Access
        access = tb.Labelframe(container, text="خيارات الدخول", padding=12)
        access.pack(fill="x", pady=10)

        rb1 = tb.Radiobutton(access, text="غير محدود", variable=self.var_access_unlimited, value=True)
        rb2 = tb.Radiobutton(access, text="محدود", variable=self.var_access_unlimited, value=False)
        rb1.pack(anchor="e")
        rb2.pack(anchor="e")

        limit_row = tb.Frame(access)
        limit_row.pack(fill="x", pady=6)
        tb.Label(limit_row, text="عدد مرات الدخول", font=("Cairo", 10, "bold"), anchor="e").pack(side="right")
        self.limit_entry = tb.Entry(limit_row, textvariable=self.var_access_limit, justify="right", width=10)
        self.limit_entry.pack(side="left")

        time_row = tb.Frame(access)
        time_row.pack(fill="x", pady=6)
        tb.Label(time_row, text="أوقات الدخول", font=("Cairo", 10, "bold"), anchor="e").pack(side="right")
        self.time_combo = tb.Combobox(
            time_row,
            textvariable=self.var_access_time,
            values=["all", "morning", "evening"],
            state="readonly",
            justify="right",
            width=14,
        )
        self.time_combo.pack(side="left")

        # Features
        feats = tb.Labelframe(container, text="المميزات", padding=12)
        feats.pack(fill="x", pady=10)

        grid = tb.Frame(feats)
        grid.pack(fill="x")

        items = [
            ("all_equipment", "استخدام جميع الأجهزة"),
            ("locker", "خزانة شخصية"),
            ("personal_trainer", "مدرب شخصي"),
            ("nutrition_plan", "برنامج غذائي"),
            ("parking", "موقف سيارات"),
            ("pool", "حمام سباحة"),
            ("sauna", "ساونا وجاكوزي"),
        ]

        for i, (k, label) in enumerate(items):
            cb = tb.Checkbutton(grid, text=label, variable=self.features_vars[k])
            cb.grid(row=i // 2, column=i % 2, sticky="e", padx=10, pady=4)

        # Description
        desc = tb.Labelframe(container, text="الوصف", padding=12)
        desc.pack(fill="both", expand=True, pady=10)

        self.desc_text = tk.Text(desc, height=5, wrap="word")
        self.desc_text.pack(fill="both", expand=True)
        self.desc_text.insert("1.0", self.var_description.get() or "")

        # Settings
        settings = tb.Labelframe(container, text="الإعدادات", padding=12)
        settings.pack(fill="x")

        tb.Checkbutton(settings, text="نشط", variable=self.var_is_active, bootstyle="round-toggle").pack(anchor="e")
        tb.Checkbutton(settings, text="إظهار في صفحة التسجيل", variable=self.var_show_in_registration).pack(anchor="e")
        tb.Checkbutton(settings, text="السماح بالتجديد التلقائي", variable=self.var_allow_auto_renewal).pack(anchor="e")
        tb.Checkbutton(settings, text="باقة مميزة (تظهر أولاً)", variable=self.var_is_featured, bootstyle="warning-round-toggle").pack(
            anchor="e"
        )

        # Buttons (fixed bottom bar)
        btns = tb.Frame(self, padding=14)
        btns.pack(side="bottom", fill="x")

        tb.Button(btns, text="💾 حفظ الباقة", bootstyle="success", command=self._save).pack(side="left", padx=6)
        tb.Button(btns, text="❌ إلغاء", bootstyle="secondary", command=self.destroy).pack(side="left")

    def _row_entry(self, parent: ttk.Widget, label: str, var: tk.Variable) -> None:
        row = tb.Frame(parent)
        row.pack(fill="x", pady=6)
        tb.Label(row, text=label, font=("Cairo", 10, "bold"), anchor="e").pack(side="right")
        tb.Entry(row, textvariable=var, justify="right").pack(side="left", fill="x", expand=True)

    def _center(self) -> None:
        self.update_idletasks()
        w = self.winfo_width()
        h = self.winfo_height()
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        self.geometry(f"{w}x{h}+{(sw - w)//2}+{(sh - h)//2}")

    def _on_type_change(self) -> None:
        t = self.var_plan_type.get()
        if t == "monthly":
            self.var_duration_months.set(1)
        elif t == "quarterly":
            self.var_duration_months.set(3)
        elif t == "semi_annual":
            self.var_duration_months.set(6)
        elif t == "annual":
            self.var_duration_months.set(12)
        elif t == "trial":
            self.var_duration_months.set(0)
        # custom keeps whatever user entered

    def _on_access_mode_change(self) -> None:
        if self.var_access_unlimited.get():
            self.var_access_limit.set(0)
            try:
                self.limit_entry.configure(state="disabled")
            except Exception:
                pass
        else:
            try:
                self.limit_entry.configure(state="normal")
            except Exception:
                pass

    def _update_price_preview(self) -> None:
        try:
            price = float(self.var_price.get() or 0)
        except Exception:
            price = 0.0

        try:
            disc = float(self.var_discount.get() or 0)
        except Exception:
            disc = 0.0

        disc = max(0.0, min(disc, 100.0))
        after = price * (1 - disc / 100.0)

        # VAT rate from settings
        vat_rate = 15.0
        try:
            vat_rate = float(self.db.get_settings("vat_rate") or 15)
        except Exception:
            vat_rate = 15.0

        vat = after * (vat_rate / 100.0)
        total = after if self.var_vat_included.get() else after + vat

        self.price_preview.configure(text=f"بعد الخصم: {_fmt_money(after, db=self.db)} | ض.ق.م: {_fmt_money(vat, db=self.db)} | الإجمالي: {_fmt_money(total, db=self.db)}")

    def _save(self) -> None:
        name_ar = self.var_name_ar.get().strip()
        if not name_ar:
            messagebox.showerror("خطأ", "يرجى إدخال اسم الباقة")
            return

        try:
            price = float(self.var_price.get() or 0)
        except Exception:
            price = -1

        if price < 0:
            messagebox.showerror("خطأ", "يرجى إدخال سعر صحيح")
            return

        months = int(self.var_duration_months.get() or 0)
        if self.var_plan_type.get() != "trial" and months <= 0:
            messagebox.showerror("خطأ", "يرجى إدخال مدة صحيحة")
            return

        features = [k for k, v in self.features_vars.items() if bool(v.get())]

        meta = {
            "plan_type": self.var_plan_type.get(),
            "discount_percent": float(self.var_discount.get() or 0),
            "vat_included": bool(self.var_vat_included.get()),
            "access_limit": 0 if bool(self.var_access_unlimited.get()) else int(self.var_access_limit.get() or 0),
            "access_time": self.var_access_time.get(),
            "features": features,
            "description": self.desc_text.get("1.0", "end").strip(),
            "show_in_registration": bool(self.var_show_in_registration.get()),
            "allow_auto_renewal": bool(self.var_allow_auto_renewal.get()),
            "is_featured": bool(self.var_is_featured.get()),
        }

        desc_json = _safe_json_dump(meta)
        is_active = 1 if bool(self.var_is_active.get()) else 0

        try:
            if self.plan is None:
                ok, msg, new_id = self.db.create_subscription_type(
                    name_ar=name_ar,
                    name_en=self.var_name_en.get().strip() or None,
                    duration_months=max(0, months),
                    price=float(price),
                    description=desc_json,
                    is_active=is_active,
                )
                if not ok or new_id is None:
                    messagebox.showerror("خطأ", msg)
                    return
                self.saved_plan_id = int(new_id)
            else:
                pid = int(self.plan["id"])
                ok, msg = self.db.update_subscription_type(
                    pid,
                    name_ar=name_ar,
                    name_en=self.var_name_en.get().strip() or None,
                    duration_months=max(0, months),
                    price=float(price),
                    description=desc_json,
                    is_active=is_active,
                )
                if not ok:
                    messagebox.showerror("خطأ", msg)
                    return
                self.saved_plan_id = pid

            self.saved = True
            Messagebox.ok(title="نجاح", message="تم حفظ الباقة بنجاح", parent=self)
            self.destroy()
        except Exception as e:
            messagebox.showerror("خطأ", f"فشل في حفظ الباقة: {e}")


class PlanStatisticsDialog(tk.Toplevel):
    """Statistics dialog for all plans based on subscriptions and payments."""

    def __init__(self, parent: tk.Misc, db: DatabaseManager) -> None:
        super().__init__(parent)
        self.db = db

        self.title("📊 إحصائيات الباقات")
        self.geometry("760x560")
        self.resizable(True, True)
        self.grab_set()

        container = tb.Frame(self, padding=12)
        container.pack(fill="both", expand=True)

        tb.Label(container, text="📊 إحصائيات الباقات", font=FONTS["heading"], anchor="e").pack(fill="x")

        top = tb.Labelframe(container, text="توزيع الاشتراكات حسب الباقة", padding=12)
        top.pack(fill="x", pady=10)

        self.bars_container = tb.Frame(top)
        self.bars_container.pack(fill="x")

        bottom = tb.Labelframe(container, text="الإيرادات حسب الباقة", padding=12)
        bottom.pack(fill="both", expand=True)

        cols = ("name", "subs", "active", "revenue")
        self.tree = ttk.Treeview(bottom, columns=cols, show="headings")
        self.tree.heading("name", text="الباقة")
        self.tree.heading("subs", text="عدد الاشتراكات")
        self.tree.heading("active", text="النشطة")
        self.tree.heading("revenue", text="الإيرادات")

        self.tree.column("name", width=220, anchor="e")
        self.tree.column("subs", width=120, anchor="center")
        self.tree.column("active", width=120, anchor="center")
        self.tree.column("revenue", width=140, anchor="center")

        vsb = ttk.Scrollbar(bottom, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

        btns = tb.Frame(container)
        btns.pack(fill="x", pady=(10, 0))
        tb.Button(btns, text="إغلاق", bootstyle="secondary", command=self.destroy).pack(side="left")

        self._load()

    def _load(self) -> None:
        for w in self.bars_container.winfo_children():
            w.destroy()
        for i in self.tree.get_children():
            self.tree.delete(i)

        ms = date.today().replace(day=1).isoformat()

        with self.db.get_connection() as conn:
            types = conn.execute("SELECT id, name_ar FROM subscription_types ORDER BY price ASC").fetchall()

            totals = conn.execute(
                """
                SELECT subscription_type_id, COUNT(*) AS c
                FROM subscriptions
                GROUP BY subscription_type_id
                """
            ).fetchall()
            total_map = {int(r["subscription_type_id"]): int(r["c"]) for r in totals}

            active_totals = conn.execute(
                """
                SELECT subscription_type_id, COUNT(*) AS c
                FROM subscriptions
                WHERE status = 'active' AND date(end_date) >= date('now')
                GROUP BY subscription_type_id
                """
            ).fetchall()
            active_map = {int(r["subscription_type_id"]): int(r["c"]) for r in active_totals}

            rev_rows = conn.execute(
                """
                SELECT s.subscription_type_id, COALESCE(SUM(p.amount), 0) AS total
                FROM payments p
                JOIN subscriptions s ON s.id = p.subscription_id
                WHERE date(p.payment_date) >= date(?)
                GROUP BY s.subscription_type_id
                """,
                (ms,),
            ).fetchall()
            rev_map = {int(r["subscription_type_id"]): float(r["total"] or 0) for r in rev_rows}

        max_total = max(total_map.values()) if total_map else 1

        for t in types:
            pid = int(t["id"])
            name = str(t["name_ar"])
            total = int(total_map.get(pid, 0))
            active = int(active_map.get(pid, 0))
            revenue = float(rev_map.get(pid, 0.0))

            pct = int((total / max_total) * 100) if max_total else 0
            row = tb.Frame(self.bars_container)
            row.pack(fill="x", pady=4)
            tb.Label(row, text=name, font=FONTS["small"], anchor="e").pack(side="right")
            m = Meter(row, metersize=70, amounttotal=100, amountused=pct, metertype="semi", bootstyle="info")
            m.pack(side="left")

            self.tree.insert("", "end", values=(name, total, active, _fmt_money(revenue, db=self.db)))


class PriceSettingsDialog(tk.Toplevel):
    """Global price settings (stored in settings table)."""

    def __init__(self, parent: tk.Misc, db: DatabaseManager) -> None:
        super().__init__(parent)
        self.db = db

        self.title("⚙️ إعدادات الأسعار")
        self.geometry("540x620")
        self.minsize(420, 520)
        self.resizable(True, True)
        self.grab_set()

        self.var_vat_rate = tk.StringVar(master=self, value=self.db.get_settings("vat_rate") or "15")
        self.var_prices_mode = tk.StringVar(master=self, value=self.db.get_settings("prices_mode") or "inclusive")
        self.var_currency = tk.StringVar(master=self, value=self.db.get_settings("currency") or "SAR")
        self.var_currency_symbol = tk.StringVar(master=self, value=self.db.get_settings("currency_symbol") or "ر.س")

        # Automatic discounts
        self.var_early_renewal_enabled = tk.BooleanVar(master=self, value=(self.db.get_settings("discount_early_enabled") or "1") == "1")
        self.var_early_renewal_pct = tk.StringVar(master=self, value=self.db.get_settings("discount_early_pct") or "5")
        self.var_referral_enabled = tk.BooleanVar(master=self, value=(self.db.get_settings("discount_referral_enabled") or "0") == "1")
        self.var_referral_pct = tk.StringVar(master=self, value=self.db.get_settings("discount_referral_pct") or "10")

        # Fees
        self.var_registration_fee = tk.StringVar(master=self, value=self.db.get_settings("fee_registration") or "0")
        self.var_card_fee = tk.StringVar(master=self, value=self.db.get_settings("fee_card") or "0")

        self._build()
        self._center()

        self.bind("<Escape>", lambda _e: self.destroy())

    def _build(self) -> None:
        container = tb.Frame(self, padding=14)
        container.pack(fill="both", expand=True)

        tb.Label(container, text="⚙️ إعدادات الأسعار", font=FONTS["heading"], anchor="e").pack(fill="x")

        vat = tb.Labelframe(container, text="ضريبة القيمة المضافة", padding=12)
        vat.pack(fill="x", pady=10)

        row = tb.Frame(vat)
        row.pack(fill="x")
        tb.Label(row, text="نسبة الضريبة", font=("Cairo", 10, "bold"), anchor="e").pack(side="right")
        tb.Entry(row, textvariable=self.var_vat_rate, justify="right", width=10).pack(side="right", padx=(10, 0))
        tb.Label(row, text="%", font=FONTS["small"]).pack(side="right", padx=(6, 0))

        mode = tb.Labelframe(container, text="طريقة عرض الأسعار", padding=12)
        mode.pack(fill="x")

        tb.Radiobutton(mode, text="الأسعار شاملة الضريبة", variable=self.var_prices_mode, value="inclusive").pack(anchor="e")
        tb.Radiobutton(mode, text="الأسعار + الضريبة", variable=self.var_prices_mode, value="exclusive").pack(anchor="e")

        cur = tb.Labelframe(container, text="العملة", padding=12)
        cur.pack(fill="x", pady=10)

        self._row_entry(cur, "العملة", self.var_currency)
        self._row_entry(cur, "رمز العملة", self.var_currency_symbol)

        disc = tb.Labelframe(container, text="الخصومات التلقائية", padding=12)
        disc.pack(fill="x")

        r1 = tb.Frame(disc)
        r1.pack(fill="x", pady=4)
        tb.Checkbutton(r1, text="خصم التجديد المبكر", variable=self.var_early_renewal_enabled, bootstyle="secondary").pack(side="right")
        tb.Entry(r1, textvariable=self.var_early_renewal_pct, justify="right", width=8).pack(side="left")
        tb.Label(r1, text="%", font=FONTS["small"]).pack(side="left", padx=(6, 0))

        r2 = tb.Frame(disc)
        r2.pack(fill="x", pady=4)
        tb.Checkbutton(r2, text="خصم الإحالة", variable=self.var_referral_enabled, bootstyle="secondary").pack(side="right")
        tb.Entry(r2, textvariable=self.var_referral_pct, justify="right", width=8).pack(side="left")
        tb.Label(r2, text="%", font=FONTS["small"]).pack(side="left", padx=(6, 0))

        fees = tb.Labelframe(container, text="رسوم إضافية", padding=12)
        fees.pack(fill="x", pady=10)

        self._row_entry(fees, "رسوم التسجيل (مرة واحدة)", self.var_registration_fee)
        self._row_entry(fees, "رسوم إصدار البطاقة", self.var_card_fee)

        btns = tb.Frame(container)
        btns.pack(fill="x", pady=(12, 0))
        tb.Button(btns, text="💾 حفظ الإعدادات", bootstyle="success", command=self._save).pack(side="left", padx=6)
        tb.Button(btns, text="❌ إلغاء", bootstyle="secondary", command=self.destroy).pack(side="left")

    def _row_entry(self, parent: ttk.Widget, label: str, var: tk.Variable) -> None:
        row = tb.Frame(parent)
        row.pack(fill="x", pady=6)
        tb.Label(row, text=label, font=("Cairo", 10, "bold"), anchor="e").pack(side="right")
        tb.Entry(row, textvariable=var, justify="right").pack(side="left", fill="x", expand=True)

    def _center(self) -> None:
        self.update_idletasks()
        w = self.winfo_width()
        h = self.winfo_height()
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        self.geometry(f"{w}x{h}+{(sw - w)//2}+{(sh - h)//2}")

    def _save(self) -> None:
        try:
            float(self.var_vat_rate.get() or "15")
        except Exception:
            messagebox.showerror("خطأ", "نسبة الضريبة غير صحيحة")
            return

        self.db.set_settings("vat_rate", self.var_vat_rate.get().strip() or "15")
        self.db.set_settings("prices_mode", self.var_prices_mode.get().strip() or "inclusive")
        self.db.set_settings("currency", self.var_currency.get().strip() or "SAR")
        self.db.set_settings("currency_symbol", self.var_currency_symbol.get().strip() or "ر.س")

        self.db.set_settings("discount_early_enabled", "1" if self.var_early_renewal_enabled.get() else "0")
        self.db.set_settings("discount_early_pct", self.var_early_renewal_pct.get().strip() or "5")
        self.db.set_settings("discount_referral_enabled", "1" if self.var_referral_enabled.get() else "0")
        self.db.set_settings("discount_referral_pct", self.var_referral_pct.get().strip() or "10")

        self.db.set_settings("fee_registration", self.var_registration_fee.get().strip() or "0")
        self.db.set_settings("fee_card", self.var_card_fee.get().strip() or "0")

        Messagebox.ok(title="تم", message="تم حفظ الإعدادات", parent=self)
        self.destroy()


if __name__ == "__main__":
    root = tb.Window(themename="cosmo")
    root.title("PlansFrame Test")
    db = DatabaseManager()
    frame = PlansFrame(root, db, {"id": 1, "username": "admin", "role": "admin"})
    frame.pack(fill="both", expand=True)
    root.geometry("1200x700")
    root.mainloop()
