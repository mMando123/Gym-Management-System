"""Notifications system for Gym Management System.

Provides:
- NotificationManager: background checks (expiring subscriptions, pending payments)
- NotificationCenter: UI to view notifications

Uses ttkbootstrap ToastNotification if available.

NOTE: This module is designed around the existing database schema from database.py.
"""

from __future__ import annotations

import threading
import time
from datetime import date, datetime
from typing import Any

import ttkbootstrap as tb
from tkinter import ttk

from database import DatabaseManager
from utils import format_money


try:
    from ttkbootstrap.toast import ToastNotification  # type: ignore

    HAS_TOAST = True
except Exception:
    ToastNotification = None  # type: ignore
    HAS_TOAST = False


class NotificationManager:
    """Manages system notifications and runs background checks."""

    def __init__(self, parent: Any, db_manager: DatabaseManager):
        self.parent = parent
        self.db = db_manager

        self.notifications_queue: list[dict[str, Any]] = []
        self.notification_history: list[dict[str, Any]] = []

        self.is_running: bool = True

        self.start_background_checker()

    def start_background_checker(self) -> None:
        self.checker_thread = threading.Thread(target=self._check_loop, daemon=True)
        self.checker_thread.start()

    def _check_loop(self) -> None:
        while self.is_running:
            try:
                self.check_expiring_subscriptions()
                self.check_pending_payments()
            except Exception:
                pass

            time.sleep(300)

    def check_expiring_subscriptions(self) -> None:
        """Check subscriptions expiring within 3 days."""

        try:
            expiring = self.db.get_expiring_subscriptions(days=3)
        except Exception:
            expiring = []

        for s in expiring:
            title = "⚠️ اشتراك ينتهي قريباً"
            msg = f"اشتراك {s.get('first_name','')} {s.get('last_name','')} ({s.get('type_name_ar','')}) ينتهي في {s.get('end_date','')}"
            self.add_notification(
                title=title,
                message=msg,
                type="warning",
                action_type="open_subscription",
                action_data={"subscription_id": s.get("id")},
            )

    def check_pending_payments(self) -> None:
        """Check members with remaining balances on active subscriptions."""

        try:
            with self.db.get_connection() as conn:
                rows = conn.execute(
                    """
                    SELECT s.id AS subscription_id,
                           m.first_name, m.last_name, m.phone,
                           st.price AS total,
                           s.amount_paid AS paid
                    FROM subscriptions s
                    JOIN members m ON m.id = s.member_id
                    JOIN subscription_types st ON st.id = s.subscription_type_id
                    WHERE s.status = 'active'
                    """
                ).fetchall()
        except Exception:
            rows = []

        for r in rows:
            total = float(r["total"] or 0)
            paid = float(r["paid"] or 0)
            remaining = total - paid
            if remaining <= 0.01:
                continue

            title = "💰 دفعة معلقة"
            msg = f"العضو {r['first_name']} {r['last_name']} عليه مبلغ متبقي: {format_money(remaining, db=self.db, decimals=0)}"
            self.add_notification(
                title=title,
                message=msg,
                type="danger",
                action_type="open_payment",
                action_data={"subscription_id": r.get("subscription_id")},
            )

    def add_notification(
        self,
        title: str,
        message: str,
        type: str = "info",
        action_type: str | None = None,
        action_data: dict[str, Any] | None = None,
    ) -> None:
        notif = {
            "id": len(self.notification_history) + 1,
            "title": title,
            "message": message,
            "type": type,
            "action_type": action_type,
            "action_data": action_data,
            "timestamp": datetime.now(),
            "read": False,
        }

        self.notifications_queue.append(notif)
        self.notification_history.append(notif)

        try:
            self.parent.after(0, lambda n=notif: self.show_toast(n))
        except Exception:
            # Parent may not support after()
            self.show_toast(notif)

    def show_toast(self, notification: dict[str, Any]) -> None:
        """Display toast notification if available."""

        if not HAS_TOAST:
            return

        bootstyle_map = {
            "info": "info",
            "warning": "warning",
            "danger": "danger",
            "success": "success",
        }

        toast = ToastNotification(
            title=notification["title"],
            message=notification["message"],
            duration=5000,
            bootstyle=bootstyle_map.get(notification["type"], "info"),
            position=(50, 50, "se"),
        )
        toast.show_toast()

    def get_unread_count(self) -> int:
        return len([n for n in self.notification_history if not n.get("read")])

    def mark_all_read(self) -> None:
        for n in self.notification_history:
            n["read"] = True

    def get_all_notifications(self) -> list[dict[str, Any]]:
        return sorted(self.notification_history, key=lambda x: x.get("timestamp"), reverse=True)

    def stop(self) -> None:
        self.is_running = False


class NotificationCenter(tb.Toplevel):
    """A panel showing all notifications with actions."""

    def __init__(self, parent: Any, notification_manager: NotificationManager, action_callbacks: dict[str, Any] | None = None):
        super().__init__(parent)
        self.nm = notification_manager
        self.callbacks = action_callbacks or {}

        self.title("مركز الإشعارات")
        self.geometry("420x640")

        self.setup_ui()
        self.load_notifications()

    def setup_ui(self) -> None:
        header = tb.Frame(self, padding=12)
        header.pack(fill="x")

        tb.Label(header, text="🔔 الإشعارات", font=("Cairo", 16, "bold")).pack(side="right")
        tb.Button(header, text="تحديد الكل كمقروء", bootstyle="secondary-link", command=self.mark_all_read).pack(side="left")

        self.list_frame = tb.Frame(self, padding=10)
        self.list_frame.pack(fill="both", expand=True)

        self.canvas = tb.Canvas(self.list_frame, highlightthickness=0)
        self.canvas.pack(side="left", fill="both", expand=True)

        sb = ttk.Scrollbar(self.list_frame, orient="vertical", command=self.canvas.yview)
        sb.pack(side="right", fill="y")
        self.canvas.configure(yscrollcommand=sb.set)

        self.inner = tb.Frame(self.canvas)
        self.canvas_window = self.canvas.create_window((0, 0), window=self.inner, anchor="nw")

        self.inner.bind("<Configure>", lambda _e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.bind("<Configure>", lambda e: self.canvas.itemconfigure(self.canvas_window, width=e.width))

    def load_notifications(self) -> None:
        for w in self.inner.winfo_children():
            w.destroy()

        notifications = self.nm.get_all_notifications()
        if not notifications:
            tb.Label(self.inner, text="لا توجد إشعارات", font=("Cairo", 14), foreground="gray").pack(pady=50)
            return

        for notif in notifications:
            self.create_notification_card(notif)

    def create_notification_card(self, notification: dict[str, Any]) -> None:
        style = "secondary" if notification.get("read") else "primary"

        card = tb.Frame(self.inner, padding=10, bootstyle=style)
        card.pack(fill="x", pady=6)

        tb.Label(card, text=str(notification.get("title", "")), font=("Cairo", 12, "bold"), anchor="e").pack(fill="x")
        tb.Label(
            card,
            text=str(notification.get("message", "")),
            font=("Cairo", 10),
            anchor="e",
            justify="right",
            wraplength=360,
        ).pack(fill="x", pady=(4, 0))

        ts = notification.get("timestamp")
        ts_str = ts.strftime("%Y-%m-%d %H:%M") if isinstance(ts, datetime) else ""
        tb.Label(card, text=ts_str, font=("Cairo", 9), foreground="gray").pack(anchor="e", pady=(6, 0))

        if notification.get("action_type"):
            tb.Button(card, text="اتخاذ إجراء", bootstyle="info-outline", command=lambda n=notification: self.execute_action(n)).pack(
                anchor="w", pady=(6, 0)
            )

    def execute_action(self, notification: dict[str, Any]) -> None:
        action_type = notification.get("action_type")
        action_data = notification.get("action_data")

        if action_type in self.callbacks and callable(self.callbacks[action_type]):
            self.callbacks[action_type](action_data)

    def mark_all_read(self) -> None:
        self.nm.mark_all_read()
        self.load_notifications()


if __name__ == "__main__":
    root = tb.Window(themename="cosmo")
    db = DatabaseManager()
    nm = NotificationManager(root, db)

    def _open_payment(data):
        print("Open payment:", data)

    def _open_sub(data):
        print("Open subscription:", data)

    NotificationCenter(root, nm, {"open_payment": _open_payment, "open_subscription": _open_sub})
    root.mainloop()
