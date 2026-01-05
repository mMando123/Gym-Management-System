"""Main dashboard window for Gym Management System (RTL Arabic UI).

This window is shown after successful login.
It provides:
- Header bar with date/time/user info/notifications/logout
- RTL sidebar navigation (collapsible)
- Content area that switches between modules
- Status bar with connection/user/quick stats

Module frames (members/subscriptions/...) are optional at this stage; if not implemented yet,
placeholders will be used so navigation stays functional.
"""

from __future__ import annotations

import os
import sys
import traceback
import tkinter as tk
from tkinter import messagebox
from tkinter import ttk

import ttkbootstrap as tb
from ttkbootstrap.style import Style
from datetime import date, datetime, timedelta

import config
from database import DatabaseManager
from scrollable_frame import ScrollableFrame
from responsive_utils import ResponsiveManager, create_responsive_font
from settings_manager import SettingsManager
from utils import format_money

# Optional module frames (will fall back to placeholders if missing)
try:
    from members_frame import MembersFrame  # type: ignore
except Exception:
    MembersFrame = None  # type: ignore

try:
    from subscriptions_frame import SubscriptionsFrame  # type: ignore
except Exception:
    SubscriptionsFrame = None  # type: ignore

try:
    from payments_frame import PaymentsFrame  # type: ignore
except Exception:
    PaymentsFrame = None  # type: ignore

try:
    from attendance_frame import AttendanceFrame  # type: ignore
except Exception:
    AttendanceFrame = None  # type: ignore

try:
    from plans_frame import PlansFrame  # type: ignore
except Exception:
    PlansFrame = None  # type: ignore

try:
    from reports_frame import ReportsFrame  # type: ignore
except Exception:
    ReportsFrame = None  # type: ignore


try:
    from settings_frame import SettingsFrame  # type: ignore
except Exception:
    SettingsFrame = None  # type: ignore


LIGHT_COLORS = {
    "primary": "#2563eb",
    "primary_dark": "#1d4ed8",
    "secondary": "#64748b",
    "success": "#16a34a",
    "warning": "#d97706",
    "danger": "#dc2626",
    "background": "#f8fafc",
    "sidebar": "#ffffff",
    "sidebar_hover": "#f1f5f9",
    "sidebar_active": "#2563eb",
    "text": "#0f172a",
    "text_light": "#475569",
    "white": "#ffffff",
}

DARK_COLORS = {
    "primary": "#6366f1",
    "primary_dark": "#4f46e5",
    "secondary": "#94a3b8",
    "success": "#22c55e",
    "warning": "#f59e0b",
    "danger": "#ef4444",
    "background": "#0f172a",
    "sidebar": "#111827",
    "sidebar_hover": "#1f2937",
    "sidebar_active": "#6366f1",
    "text": "#e5e7eb",
    "text_light": "#9ca3af",
    "white": "#ffffff",
}

COLORS = dict(LIGHT_COLORS)

FONTS = {
    "heading": ("Cairo", 18, "bold"),
    "subheading": ("Cairo", 14, "bold"),
    "body": ("Cairo", 12),
    "small": ("Cairo", 10),
}


_AR_WEEKDAYS = {
    0: "الاثنين",
    1: "الثلاثاء",
    2: "الأربعاء",
    3: "الخميس",
    4: "الجمعة",
    5: "السبت",
    6: "الأحد",
}

_AR_MONTHS = {
    1: "يناير",
    2: "فبراير",
    3: "مارس",
    4: "أبريل",
    5: "مايو",
    6: "يونيو",
    7: "يوليو",
    8: "أغسطس",
    9: "سبتمبر",
    10: "أكتوبر",
    11: "نوفمبر",
    12: "ديسمبر",
}


def _arabic_date_string(d: date) -> str:
    """Format date like: الأربعاء، 15 يناير 2025"""

    wd = _AR_WEEKDAYS.get(d.weekday(), "")
    month = _AR_MONTHS.get(d.month, "")
    return f"{wd}، {d.day} {month} {d.year}"


def _arabic_time_string(dt: datetime) -> str:
    """Format time like: 10:30:45 ص"""

    hour24 = dt.hour
    am_pm = "ص" if hour24 < 12 else "م"
    hour12 = hour24 % 12
    if hour12 == 0:
        hour12 = 12
    return f"{hour12:02d}:{dt.minute:02d}:{dt.second:02d} {am_pm}"


class MainWindow:
    """Main application window."""

    def __init__(self, user_data: dict[str, object] | None = None, master: tk.Tk | None = None) -> None:
        try:
            inst = getattr(Style, "instance", None)
            if inst is not None:
                try:
                    if not inst.master.winfo_exists():
                        Style.instance = None
                except Exception:
                    Style.instance = None
        except Exception:
            pass

        self._master = master
        self._is_toplevel = master is not None
        if self._is_toplevel:
            self.root = tb.Toplevel(master)
        else:
            self.root = tb.Window(themename="cosmo")

        self._current_theme: str = "cosmo"
        self._install_bgerror_handler()
        self.user_data: dict[str, object] = user_data or {}
        self.user_role: str = str(self.user_data.get("role") or "employee")
        self.permissions: set[str] = set()
        self._logout_requested: bool = False

        # Initialize managers first
        self.db = DatabaseManager()
        self.responsive = ResponsiveManager(self.root)

        self.settings: SettingsManager | None = None
        self._header_logo_img = None

        self.current_frame: ttk.Frame | None = None

        self.sidebar_collapsed: bool = False
        self.sidebar_hidden: bool = False
        self.sidebar_auto_collapsed: bool = False
        self.mobile_menu: tb.Toplevel | None = None
        self.menu_buttons: dict[str, tb.Button] = {}
        self.notification_count: int = 0
        self.notifications_cache: list[dict] = []

        # after() task ids (initialized to avoid AttributeError on logout)
        self._after_clock = None
        self._after_date = None
        self._after_notifications = None
        self._after_status = None

        # Status bar variables
        self.status_var = tk.StringVar(value="جارٍ التحميل...")
        self.date_var = tk.StringVar(value="")
        self.time_var = tk.StringVar(value="")
        self.quick_stats_var = tk.StringVar(value="")
        self.notification_var = tk.StringVar(value="")

        try:
            self.settings = SettingsManager(self.db)
            try:
                self.settings.preload()
            except Exception:
                pass
        except Exception:
            self.settings = None

        self._apply_theme_from_settings()
        self._load_permissions()

        # Create UI
        self.create_header()
        self.create_sidebar()
        self.create_content_area()
        self.create_status_bar()

        self.switch_frame("dashboard")
        self.update_clock()
        self.update_date()
        self.check_notifications()

        self._bind_shortcuts()
        self._bind_responsive()

        try:
            self.root.bind("<<SettingsChanged>>", self._on_settings_changed)
        except Exception:
            pass

    def _is_dark_theme(self, theme_name: str) -> bool:
        t = (theme_name or "").strip().lower()
        return t in {"darkly", "cyborg", "superhero", "vapor"}

    def _apply_palette(self, theme_name: str) -> None:
        try:
            palette = DARK_COLORS if self._is_dark_theme(theme_name) else LIGHT_COLORS
            COLORS.clear()
            COLORS.update(palette)
        except Exception:
            pass

    def _apply_theme_from_settings(self) -> None:
        theme_name = "cosmo"
        try:
            if self.settings is not None:
                theme_name = str(self.settings.get("system", "theme", "cosmo") or "cosmo").strip() or "cosmo"
        except Exception:
            theme_name = "cosmo"

        if (theme_name or "").strip() == "":
            theme_name = "cosmo"

        self._apply_theme(theme_name, save=False)

    def _apply_theme(self, theme_name: str, save: bool = False) -> None:
        theme_name = (theme_name or "").strip() or "cosmo"
        self._current_theme = theme_name

        self._apply_palette(theme_name)

        try:
            tb.Style().theme_use(theme_name)
        except Exception:
            try:
                self.root.tk.call("ttk::style", "theme", "use", theme_name)
            except Exception:
                try:
                    traceback.print_exc()
                except Exception:
                    pass

        try:
            self.root.configure(background=COLORS["background"])
        except Exception:
            pass

        try:
            self.root.update_idletasks()
        except Exception:
            pass

        if save:
            changed_by = self.user_data.get("id")
            changed_by = changed_by if isinstance(changed_by, int) else None
            try:
                if self.settings is not None:
                    self.settings.set("system", "theme", theme_name, changed_by=changed_by)
            except Exception:
                pass
            try:
                if self.settings is None and self.db is not None:
                    self.db.set_settings("system.theme", theme_name)
            except Exception:
                pass

        try:
            if hasattr(self, "badge_label"):
                self.badge_label.configure(foreground=COLORS["white"], background=COLORS["danger"])
        except Exception:
            pass

        try:
            if hasattr(self, "status_text_left"):
                self.status_text_left.configure(foreground=COLORS["text_light"])
            if hasattr(self, "status_text_right"):
                self.status_text_right.configure(foreground=COLORS["text_light"])
        except Exception:
            pass

        try:
            if hasattr(self, "theme_toggle_btn"):
                self.theme_toggle_btn.configure(text=("☀" if self._is_dark_theme(theme_name) else "🌙"))
        except Exception:
            pass

    def toggle_theme(self) -> None:
        new_theme = "cosmo" if self._is_dark_theme(self._current_theme) else "darkly"
        self._apply_theme(new_theme, save=True)

    def _load_permissions(self) -> None:
        """Load allowed modules for the current user role."""
        modules = [
            "dashboard",
            "members",
            "subscriptions",
            "attendance",
            "payments",
            "plans",
            "reports",
            "settings",
            "about",
        ]

        role = str(self.user_role or "employee").strip() or "employee"

        if role.lower() == "admin":
            self.permissions.update(modules)
            return

        # Prefer SettingsManager permissions matrix (editable from Settings UI)
        try:
            if self.settings is not None:
                matrix = self.settings.get_permissions_matrix(role)
                for mod in modules:
                    perms = matrix.get(mod) or {}
                    if int(perms.get("view", 0)) == 1:
                        self.permissions.add(mod)
                return
        except Exception:
            pass

        # Fallback: DB check_permission
        try:
            for mod in modules:
                if self.db.check_permission(role, mod, "can_view"):
                    self.permissions.add(mod)
        except Exception:
            pass

        if not self.permissions:
            self.permissions.add("dashboard")

    def check_permissions(self, module: str) -> bool:
        """Check if current user can view the requested module."""
        return module in self.permissions

    # ------------------------------
    # Window setup
    # ------------------------------

    def setup_window(self) -> None:
        """Configure window properties."""

        self.root.title(str(getattr(config, "APP_NAME", "نظام إدارة الجيم")))
        self.root.geometry(f"{config.WINDOW_WIDTH}x{config.WINDOW_HEIGHT}")
        self.root.minsize(1024, 600)
        self.root.configure(background=COLORS["background"])
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

        try:
            self.root.state("zoomed")
        except Exception:
            pass

        self._center_window()

    def _install_bgerror_handler(self) -> None:
        """Ignore benign Tk background errors after the app is destroyed."""

        try:
            # Some ttk/ttkbootstrap internals can emit <<ThemeChanged>> after destroy.
            # This handler prevents noisy bgerror output for those benign cases.
            self.root.tk.eval(
                """
                proc bgerror {msg} {
                    if {[string match {*application has been destroyed*} $msg]} {
                        return
                    }
                    puts stderr $msg
                }
                """
            )
        except Exception:
            pass

    def _on_breakpoint_change(self, breakpoint: str) -> None:
        """Handle responsive breakpoint changes."""
        try:
            if not hasattr(self, "sidebar"):
                return

            # Never fully hide the sidebar; on mobile we collapse it.
            self.sidebar_hidden = False
            try:
                self.sidebar.pack(side="right", fill="y")
            except Exception:
                pass

            if breakpoint == "mobile":
                self._set_sidebar_state(True, auto=True)
            else:
                if getattr(self, "sidebar_auto_collapsed", False) and getattr(self, "sidebar_collapsed", False):
                    self._set_sidebar_state(False, auto=True)
                try:
                    self.sidebar.configure(width=self.responsive.get_sidebar_width())
                except Exception:
                    pass
        except Exception:
            pass

        try:
            if breakpoint == "tablet":
                if not self.sidebar_collapsed:
                    self._set_sidebar_state(True, auto=True)
            elif breakpoint == "desktop":
                if self.sidebar_auto_collapsed and self.sidebar_collapsed:
                    self._set_sidebar_state(False, auto=True)
        except Exception:
            pass

        try:
            if breakpoint == "mobile":
                self.hamburger_btn.pack(side="right", padx=(0, 10))
            else:
                self.hamburger_btn.pack_forget()
                self._close_mobile_menu()
        except Exception:
            pass

        self._update_fonts()

        if self.current_frame and hasattr(self.current_frame, "on_breakpoint_change"):
            try:
                self.current_frame.on_breakpoint_change(breakpoint)
            except Exception:
                pass

        if self.current_frame and hasattr(self.current_frame, "refresh"):
            self.current_frame.refresh()

    def _update_fonts(self) -> None:
        """Update fonts based on current breakpoint."""
        scale = self.responsive.get_font_scale()
        
        # Update global font definitions
        global FONTS
        FONTS = {
            "heading": create_responsive_font(("Cairo", 18, "bold"), scale),
            "subheading": create_responsive_font(("Cairo", 14, "bold"), scale),
            "body": create_responsive_font(("Cairo", 12), scale),
            "small": create_responsive_font(("Cairo", 10), scale),
        }

        try:
            if hasattr(self, "gym_name_label"):
                self.gym_name_label.configure(font=create_responsive_font(("Cairo", 16, "bold"), scale))
        except Exception:
            pass

        try:
            if hasattr(self, "gym_logo_label"):
                self.gym_logo_label.configure(font=("Segoe UI Emoji", max(14, int(18 * scale))))
        except Exception:
            pass

    def _center_window(self) -> None:
        self.root.update_idletasks()
        w = self.root.winfo_width()
        h = self.root.winfo_height()
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        x = max((sw - w) // 2, 0)
        y = max((sh - h) // 2, 0)
        self.root.geometry(f"{w}x{h}+{x}+{y}")

    def _init_database(self) -> None:
        """Initialize DatabaseManager with safe error handling."""

        try:
            self.db = DatabaseManager()
            self.status_var.set("متصل بقاعدة البيانات ✓")
        except Exception as e:
            self.db = None
            self.status_var.set("غير متصل بقاعدة البيانات ✗")
            messagebox.showerror("خطأ", f"تعذر الاتصال بقاعدة البيانات: {e}")

    def _init_settings(self) -> None:
        if self.db is None:
            self.settings = None
            return

        try:
            self.settings = SettingsManager(self.db)
            self.settings.preload()
        except Exception:
            self.settings = None

        self.apply_settings_to_ui()

    def _on_settings_changed(self, _e=None) -> None:
        try:
            if self.settings is not None:
                self.settings.preload()
        except Exception:
            pass

        self.apply_settings_to_ui()

    def apply_settings_to_ui(self) -> None:
        gym_name = "نادي القوة الرياضي"
        logo_path = ""
        theme_name = None

        scale = 1.0
        try:
            scale = float(self.responsive.get_font_scale())
        except Exception:
            scale = 1.0

        logo_size = max(24, min(48, int(36 * scale)))

        try:
            if self.settings is not None:
                gym_name = str(self.settings.get("gym", "name", gym_name) or gym_name).strip() or gym_name
                logo_path = str(self.settings.get("gym", "logo", "") or "").strip()
                theme_name = str(self.settings.get("system", "theme", "") or "").strip() or None
        except Exception:
            pass

        try:
            if self.settings is None and self.db is not None:
                v = self.db.get_settings("gym.name")
                if v is not None:
                    gym_name = str(v).strip() or gym_name
                v = self.db.get_settings("gym.logo")
                if v is not None:
                    logo_path = str(v).strip()
                v = self.db.get_settings("system.theme")
                theme_name = str(v).strip() if v is not None else theme_name
                theme_name = theme_name or None
        except Exception:
            pass

        try:
            base_title = str(getattr(config, "APP_NAME", "نظام إدارة الجيم"))
            self.root.title(f"{base_title} - {gym_name}")
        except Exception:
            pass

        try:
            if theme_name:
                self._apply_theme(theme_name, save=False)
        except Exception:
            pass

        try:
            if hasattr(self, "gym_name_label"):
                self.gym_name_label.configure(text=gym_name)
        except Exception:
            pass

        try:
            if not hasattr(self, "gym_logo_label"):
                return

            path = (logo_path or "").strip()
            if path:
                path = os.path.expanduser(path)

            if path and os.path.exists(path):
                try:
                    from PIL import Image, ImageTk

                    src = Image.open(path)
                    has_transparency = (
                        src.mode in ("RGBA", "LA")
                        or (src.mode == "P" and "transparency" in getattr(src, "info", {}))
                        or ("transparency" in getattr(src, "info", {}))
                    )

                    img = src.convert("RGBA")

                    if not has_transparency:
                        try:
                            data = list(img.getdata())
                            new_data = []
                            for r, g, b, a in data:
                                if a > 0 and r >= 245 and g >= 245 and b >= 245:
                                    new_data.append((r, g, b, 0))
                                else:
                                    new_data.append((r, g, b, a))
                            img.putdata(new_data)
                        except Exception:
                            pass

                    img = img.resize((logo_size, logo_size), Image.LANCZOS)

                    self._header_logo_img = ImageTk.PhotoImage(img)
                    self.gym_logo_label.configure(image=self._header_logo_img, text="")
                    return
                except Exception:
                    self._header_logo_img = None

            self.gym_logo_label.configure(image="", text="🏋️")
            self._header_logo_img = None
        except Exception:
            pass

    # ------------------------------
    # Layout sections
    # ------------------------------

    def create_header(self) -> None:
        """Create the top header bar."""

        self.header = tb.Frame(self.root, height=60)
        self.header.pack(side="top", fill="x")
        self.header.pack_propagate(False)

        try:
            self.header.configure(bootstyle="primary")
        except Exception:
            pass

        try:
            self.header.grid_rowconfigure(0, weight=1)
            self.header.grid_columnconfigure(0, weight=1)
            self.header.grid_columnconfigure(1, weight=1)
            self.header.grid_columnconfigure(2, weight=1)
        except Exception:
            pass

        # Right side (RTL): gym name/logo
        right = tb.Frame(self.header)
        try:
            right.configure(bootstyle="primary")
        except Exception:
            pass
        right.grid(row=0, column=2, sticky="e", padx=16)

        self.hamburger_btn = tb.Button(
            right,
            text="≡",
            command=self.toggle_mobile_menu,
            bootstyle="light",
            width=3,
        )
        if self.responsive.get_breakpoint() == "mobile":
            self.hamburger_btn.pack(side="right", padx=(0, 10))

        self.gym_logo_label = tb.Label(
            right,
            text="🏋️",
            font=("Segoe UI Emoji", 18),
            bootstyle="inverse-primary",
            anchor="center",
        )
        self.gym_logo_label.pack(side="right", padx=(0, 8))

        self.gym_name_label = tb.Label(
            right,
            text="نادي القوة الرياضي",
            font=create_responsive_font(("Cairo", 16, "bold"), self.responsive.get_font_scale()),
            bootstyle="inverse-primary",
            anchor="e",
        )
        self.gym_name_label.pack(side="right")

        self.apply_settings_to_ui()

        # Center: date & time
        center = tb.Frame(self.header)
        try:
            center.configure(bootstyle="primary")
        except Exception:
            pass
        center.grid(row=0, column=1, sticky="n", pady=6)

        tb.Label(
            center,
            textvariable=self.date_var,
            font=FONTS["small"],
            bootstyle="inverse-primary",
        ).pack()

        tb.Label(
            center,
            textvariable=self.time_var,
            font=FONTS["subheading"],
            bootstyle="inverse-primary",
        ).pack()

        # Left side: notifications + user info + logout
        left = tb.Frame(self.header)
        try:
            left.configure(bootstyle="primary")
        except Exception:
            pass
        left.grid(row=0, column=0, sticky="w", padx=16)

        self.notify_btn = tb.Button(
            left,
            text="🔔",
            command=self.show_notifications,
            bootstyle="light",
            width=3,
        )
        self.theme_toggle_btn = tb.Button(
            left,
            text=("☀" if self._is_dark_theme(self._current_theme) else "🌙"),
            command=self.toggle_theme,
            bootstyle="light",
            width=3,
        )
        self.theme_toggle_btn.pack(side="left", padx=(0, 6))
        self.notify_btn.pack(side="left", padx=(0, 6))

        self.badge_label = tb.Label(
            left,
            textvariable=self.notification_var,
            font=("Cairo", 9, "bold"),
            foreground=COLORS["white"],
            background=COLORS["danger"],
            padding=(6, 1),
        )
        self.badge_label.pack(side="left", padx=(0, 12))

        self.user_label = tb.Label(
            left,
            text=f"{self.user_data.get('username', '')} ({self.user_data.get('role', 'admin')})",
            font=FONTS["small"],
            bootstyle="inverse-primary",
        )
        self.user_label.pack(side="left", padx=(0, 12))

        self.logout_btn = tb.Button(
            left,
            text="تسجيل الخروج 🚪",
            command=self.logout,
            bootstyle="danger",
        )
        self.logout_btn.pack(side="left")

    def create_sidebar(self) -> None:
        """Create the RTL sidebar navigation on the right side."""

        self.main_row = tb.Frame(self.root)
        self.main_row.pack(side="top", fill="both", expand=True)

        self.sidebar = tb.Frame(self.main_row)
        self.sidebar.pack(side="right", fill="y")
        self.sidebar.configure(width=self.responsive.get_sidebar_width())
        self.sidebar.pack_propagate(False)

        try:
            self.sidebar.configure(bootstyle="dark")
        except Exception:
            pass

        top_row = tb.Frame(self.sidebar)
        top_row.pack(fill="x", pady=(10, 10), padx=10)

        self.toggle_btn = tb.Button(
            top_row,
            text="≡ القائمة",
            command=self.toggle_sidebar,
            bootstyle="secondary",
        )
        self.toggle_btn.pack(fill="x")

        self.menu_container = tb.Frame(self.sidebar)
        self.menu_container.pack(fill="both", expand=True, padx=10)

        items = [
            ("dashboard", "لوحة التحكم", "🏠"),
            ("members", "الأعضاء", "👥"),
            ("subscriptions", "الاشتراكات", "💳"),
            ("attendance", "الحضور", "📅"),
            ("payments", "المدفوعات", "💰"),
            ("plans", "الباقات", "🧾"),
            ("reports", "التقارير", "📊"),
            ("settings", "الإعدادات", "⚙️"),
            ("about", "حول البرنامج", "ℹ️"),
        ]

        for name, text, icon in items:
            if name in self.permissions:
                self._add_menu_item(name, text, icon)

    def create_content_area(self) -> None:
        """Create the main content area."""

        self.content = tb.Frame(self.main_row)
        self.content.pack(side="left", fill="both", expand=True)
        self.content.configure(padding=20)

        self.content_bg = tb.Frame(self.content)
        self.content_bg.pack(fill="both", expand=True)

    def create_status_bar(self) -> None:
        """Create bottom status bar."""

        self.status_bar = tb.Frame(self.root, height=30)
        self.status_bar.pack(side="bottom", fill="x")
        self.status_bar.pack_propagate(False)

        left = tb.Frame(self.status_bar)
        left.pack(side="left", padx=12)

        self.status_text_left = tb.Label(left, textvariable=self.status_var, font=FONTS["small"], foreground=COLORS["text_light"])
        self.status_text_left.pack(side="left")

        right = tb.Frame(self.status_bar)
        right.pack(side="right", padx=12)

        self.status_text_right = tb.Label(right, textvariable=self.quick_stats_var, font=FONTS["small"], foreground=COLORS["text_light"])
        self.status_text_right.pack(side="right")

    # ------------------------------
    # Sidebar helpers
    # ------------------------------

    def toggle_mobile_menu(self) -> None:
        if self.mobile_menu is not None:
            try:
                if self.mobile_menu.winfo_exists():
                    self._close_mobile_menu()
                    return
            except Exception:
                self.mobile_menu = None

        top = tb.Toplevel(self.root)
        self.mobile_menu = top
        top.title("القائمة")
        top.minsize(240, 260)
        top.resizable(True, True)
        try:
            top.grab_set()
        except Exception:
            pass

        self.root.update_idletasks()
        w = 260
        h = max(260, min(520, self.root.winfo_height() - 120))
        x = self.root.winfo_rootx() + max(self.root.winfo_width() - w, 0)
        y = self.root.winfo_rooty() + 60
        top.geometry(f"{w}x{h}+{x}+{y}")

        container = tb.Frame(top, padding=10)
        container.pack(fill="both", expand=True)

        tb.Button(container, text="✕ إغلاق", bootstyle="secondary", command=self._close_mobile_menu).pack(
            fill="x", pady=(0, 10)
        )

        def nav(name: str) -> None:
            self._close_mobile_menu()
            self.switch_frame(name)

        items = [
            ("dashboard", "لوحة التحكم", "🏠"),
            ("members", "الأعضاء", "👥"),
            ("subscriptions", "الاشتراكات", "💳"),
            ("attendance", "الحضور", "📅"),
            ("payments", "المدفوعات", "💰"),
            ("plans", "الباقات", "🧾"),
            ("reports", "التقارير", "📊"),
            ("settings", "الإعدادات", "⚙️"),
            ("about", "حول البرنامج", "ℹ️"),
        ]

        for name, text, icon in items:
            if name not in self.permissions:
                continue
            tb.Button(container, text=f"{icon}  {text}", bootstyle="secondary", command=lambda n=name: nav(n)).pack(
                fill="x", pady=3
            )

    def _close_mobile_menu(self) -> None:
        if self.mobile_menu is None:
            return
        try:
            if self.mobile_menu.winfo_exists():
                self.mobile_menu.destroy()
        except Exception:
            pass
        self.mobile_menu = None

    def _add_menu_item(self, name: str, text: str, icon: str) -> None:
        btn = self.create_menu_item(
            self.menu_container,
            text=text,
            icon=icon,
            command=lambda n=name: self.switch_frame(n),
        )
        self.menu_buttons[name] = btn

    def create_menu_item(self, parent: ttk.Widget, text: str, icon: str, command) -> tb.Button:
        """Create a consistent sidebar menu button."""

        display = f"{icon}  {text}"
        btn = tb.Button(
            parent,
            text=display,
            command=command,
            bootstyle="secondary",
            width=22,
        )
        btn.pack(fill="x", pady=4)
        btn.configure(cursor="hand2")

        def on_enter(_e):
            if getattr(btn, "_active", False):
                return
            btn.configure(bootstyle="secondary")

        def on_leave(_e):
            if getattr(btn, "_active", False):
                return
            btn.configure(bootstyle="secondary")

        btn.bind("<Enter>", on_enter)
        btn.bind("<Leave>", on_leave)
        return btn

    def toggle_sidebar(self) -> None:
        """Collapse/expand the sidebar."""

        self._set_sidebar_state(not self.sidebar_collapsed, auto=False)

    def _set_sidebar_state(self, collapsed: bool, auto: bool) -> None:
        if auto:
            self.sidebar_auto_collapsed = bool(collapsed)
        else:
            self.sidebar_auto_collapsed = False

        self.sidebar_collapsed = bool(collapsed)
        if self.sidebar_collapsed:
            self.sidebar.configure(width=60)
            self.toggle_btn.configure(text="≡")
            for name, btn in self.menu_buttons.items():
                # Keep icon only (first token)
                t = btn.cget("text")
                icon = t.split()[0] if t else ""
                btn.configure(text=icon, width=4)
        else:
            self.sidebar.configure(width=200)
            self.toggle_btn.configure(text="☰")
            mapping = {
                "dashboard": ("لوحة التحكم", "📊"),
                "members": ("الأعضاء", "👥"),
                "subscriptions": ("الاشتراكات", "💳"),
                "attendance": ("الحضور", "📅"),
                "payments": ("المدفوعات", "💰"),
                "plans": ("الباقات", "📋"),
                "settings": ("الإعدادات", "⚙️"),
                "about": ("حول البرنامج", "ℹ️"),
            }
            for name, btn in self.menu_buttons.items():
                txt, icon = mapping.get(name, (name, ""))
                btn.configure(text=f"{icon}  {txt}", width=22)

    def switch_frame(self, frame_name: str) -> None:
        if not self.check_permissions(frame_name):
            messagebox.showwarning("صلاحيات", "لا تملك صلاحية الوصول لهذه الصفحة")
            return
        
        # Check if window still exists before creating frames
        try:
            if not self.root.winfo_exists():
                return
        except Exception:
            return
            
        for child in self.content_bg.winfo_children():
            child.destroy()
        self._set_active_menu(frame_name)
        
        host = self.content_bg
        
        # Create frame based on name
        if frame_name == "dashboard":
            frame = DashboardFrame(host, self.db, self.user_data, self.switch_frame)
        elif frame_name == "members" and MembersFrame is not None:
            frame = MembersFrame(host, self.db, self.user_data)  # type: ignore
        elif frame_name == "subscriptions" and SubscriptionsFrame is not None:
            frame = SubscriptionsFrame(host, self.db, self.user_data)  # type: ignore
        elif frame_name == "attendance" and AttendanceFrame is not None:
            frame = AttendanceFrame(host, self.db, self.user_data)  # type: ignore
        elif frame_name == "payments" and PaymentsFrame is not None:
            frame = PaymentsFrame(host, self.db, self.user_data)  # type: ignore
        elif frame_name == "plans" and PlansFrame is not None:
            frame = PlansFrame(host, self.db, self.user_data)  # type: ignore
        elif frame_name == "reports" and ReportsFrame is not None:
            frame = ReportsFrame(host, self.db, self.user_data)  # type: ignore
        elif frame_name == "settings" and SettingsFrame is not None:
            frame = SettingsFrame(host, self.db, self.user_data)  # type: ignore
        elif frame_name == "about":
            frame = AboutFrame(host)
        else:
            frame = PlaceholderFrame(host, title=self._frame_title(frame_name))

        try:
            if hasattr(frame, "on_breakpoint_change"):
                frame.on_breakpoint_change(self.responsive.get_breakpoint())
        except Exception:
            pass

        frame.pack(fill="both", expand=True)
        self.current_frame = frame

    def _set_active_menu(self, frame_name: str) -> None:
        for n, btn in self.menu_buttons.items():
            active = n == frame_name
            setattr(btn, "_active", active)
            btn.configure(bootstyle="primary" if active else "secondary")

    def _add_menu_item(self, name: str, text: str, icon: str) -> None:
        """Add a menu item to the sidebar."""
        btn = self.create_menu_item(
            self.menu_container,
            text=text,
            icon=icon,
            command=lambda n=name: self.switch_frame(n),
        )
        self.menu_buttons[name] = btn

    def _frame_title(self, name: str) -> str:
        mapping = {
            "dashboard": "لوحة التحكم",
            "members": "الأعضاء",
            "subscriptions": "الاشتراكات",
            "attendance": "الحضور",
            "payments": "المدفوعات",
            "plans": "الباقات",
            "reports": "التقارير",
            "settings": "الإعدادات",
            "about": "حول البرنامج",
        }
        return mapping.get(name, name)

    # ------------------------------
    # Header updates
    # ------------------------------

    def update_clock(self) -> None:
        """Update the clock every second."""

        try:
            if not self.root.winfo_exists():
                return
        except Exception:
            return

        self.time_var.set(_arabic_time_string(datetime.now()))
        self._after_clock = self.root.after(1000, self.update_clock)

    def update_date(self) -> None:
        """Update the date (daily)."""

        try:
            if not self.root.winfo_exists():
                return
        except Exception:
            return

        today = date.today()
        self.date_var.set(_arabic_date_string(today))

        # Schedule next update around midnight
        now = datetime.now()
        next_midnight = datetime.combine(today + timedelta(days=1), datetime.min.time())
        ms = int((next_midnight - now).total_seconds() * 1000)
        ms = max(ms, 60_000)
        self._after_date = self.root.after(ms, self.update_date)

    # ------------------------------
    # Notifications
    # ------------------------------

    def check_notifications(self) -> None:
        """Check expiring subscriptions (today + next 3 days)."""

        try:
            if not self.root.winfo_exists():
                return
        except Exception:
            return

        count = 0
        items: list[dict] = []

        if self.db is not None:
            try:
                expiring = self.db.get_expiring_subscriptions(days=3)
                items = expiring
                count = len(expiring)
            except Exception:
                items = []
                count = 0

        self.notifications_cache = items
        self.notification_count = count
        self.notification_var.set(str(count) if count > 0 else "")

        # Every 5 minutes
        self._after_notifications = self.root.after(5 * 60 * 1000, self.check_notifications)

    def show_notifications(self) -> None:
        """Show a simple popup of expiring subscriptions."""

        top = tb.Toplevel(self.root)
        top.title("التنبيهات")
        top.geometry("420x320")
        top.minsize(360, 260)
        top.resizable(True, True)

        container = tb.Frame(top, padding=14)
        container.pack(fill="both", expand=True)

        tb.Label(container, text="الاشتراكات التي تنتهي قريباً", font=FONTS["subheading"], anchor="e").pack(fill="x")

        box = tb.Frame(container)
        box.pack(fill="both", expand=True, pady=10)

        cols = ("member", "end")
        tree = ttk.Treeview(box, columns=cols, show="headings")
        tree.heading("member", text="العضو")
        tree.heading("end", text="تاريخ الانتهاء")
        tree.column("member", anchor="e", width=260)
        tree.column("end", anchor="center", width=120)
        tree.pack(side="left", fill="both", expand=True)

        sc = ttk.Scrollbar(box, orient="vertical", command=tree.yview)
        sc.pack(side="right", fill="y")
        tree.configure(yscrollcommand=sc.set)

        for n in self.notifications_cache:
            member = f"{n.get('member_code', '')} - {n.get('first_name', '')} {n.get('last_name', '')}".strip()
            tree.insert("", "end", values=(member, n.get("end_date", "")))

        tb.Button(container, text="إغلاق", bootstyle="secondary", command=top.destroy).pack()

    # ------------------------------
    # Status bar updates
    # ------------------------------

    def refresh_status_bar(self) -> None:
        """Update quick stats shown in the status bar."""

        try:
            if not self.root.winfo_exists():
                return
        except Exception:
            return

        if self.db is None:
            self.quick_stats_var.set(f"المستخدم: {self.user_data.get('username', '')} | غير متصل")
            self._after_status = self.root.after(30_000, self.refresh_status_bar)
            return

        try:
            stats = self.db.get_dashboard_stats()
            active_members = stats.get("active_members", 0)
            expiring_today = 0
            try:
                expiring_today = len(self.db.get_expiring_subscriptions(days=0))
            except Exception:
                expiring_today = 0

            self.quick_stats_var.set(
                f"الأعضاء النشطين: {active_members} | اشتراكات تنتهي اليوم: {expiring_today} | المستخدم: {self.user_data.get('username', '')}"
            )
        except Exception:
            self.quick_stats_var.set(f"المستخدم: {self.user_data.get('username', '')}")

        self._after_status = self.root.after(30_000, self.refresh_status_bar)

    def _cancel_scheduled_tasks(self) -> None:
        for after_id in [
            getattr(self, "_after_clock", None),
            getattr(self, "_after_date", None),
            getattr(self, "_after_notifications", None),
            getattr(self, "_after_status", None),
        ]:
            if not after_id:
                continue
            try:
                self.root.after_cancel(after_id)
            except Exception:
                pass
        self._after_clock = None
        self._after_date = None
        self._after_notifications = None
        self._after_status = None

    # ------------------------------
    # Logout / close
    # ------------------------------

    def logout(self) -> None:
        """Confirm logout, close main window, and reopen login."""

        if not messagebox.askyesno("تأكيد", "هل تريد تسجيل الخروج؟"):
            return

        self._logout_requested = True
        self._cancel_scheduled_tasks()
        if getattr(self, "_is_toplevel", False):
            try:
                if self.root.winfo_exists():
                    self.root.destroy()
            except Exception:
                pass
            return

        try:
            self.root.quit()
        except Exception:
            pass

    def on_closing(self) -> None:
        """Confirm exit and close window."""

        if messagebox.askyesno("تأكيد", "هل تريد إغلاق البرنامج؟"):
            self._cancel_scheduled_tasks()
            try:
                self.root.destroy()
            except Exception:
                pass

    def _bind_responsive(self) -> None:
        """Wire responsive breakpoints to the window."""

        try:
            self.responsive.register_callback(self._on_breakpoint_change)
        except Exception:
            pass

        # Apply current breakpoint once at startup
        try:
            self._on_breakpoint_change(self.responsive.get_breakpoint())
        except Exception:
            pass

    def _bind_shortcuts(self) -> None:
        """Keyboard shortcuts for quick navigation."""

        self.root.bind("<Control-1>", lambda _e: self.switch_frame("dashboard"))
        self.root.bind("<Control-2>", lambda _e: self.switch_frame("members"))
        self.root.bind("<Control-3>", lambda _e: self.switch_frame("subscriptions"))
        self.root.bind("<Control-4>", lambda _e: self.switch_frame("attendance"))
        self.root.bind("<Control-5>", lambda _e: self.switch_frame("payments"))
        self.root.bind("<Control-6>", lambda _e: self.switch_frame("plans"))
        self.root.bind("<Control-7>", lambda _e: self.switch_frame("reports"))
        self.root.bind("<Control-8>", lambda _e: self.switch_frame("settings"))

    def run(self) -> None:
        if getattr(self, "_is_toplevel", False):
            try:
                self.root.wait_window()
            except Exception:
                pass
            finally:
                try:
                    self._cancel_scheduled_tasks()
                except Exception:
                    pass
            return bool(getattr(self, "_logout_requested", False))

        logged_out = False
        try:
            self.root.mainloop()
        except KeyboardInterrupt:
            pass
        finally:
            logged_out = bool(getattr(self, "_logout_requested", False))
            try:
                self._cancel_scheduled_tasks()
            except Exception:
                pass
            try:
                if self.root.winfo_exists():
                    self.root.destroy()
            except Exception:
                pass

        return bool(logged_out)


class PlaceholderFrame(tb.Frame):
    """Placeholder for modules not implemented yet."""

    def __init__(self, parent: ttk.Widget, title: str) -> None:
        super().__init__(parent)
        self.configure(padding=20)

        tb.Label(self, text=title, font=FONTS["heading"], anchor="e").pack(fill="x", pady=(0, 12))
        tb.Label(
            self,
            text="هذه الصفحة غير متاحة حالياً.",
            font=FONTS["body"],
            foreground=COLORS["text_light"],
            anchor="e",
            justify="right",
        ).pack(fill="x")


class AboutFrame(tb.Frame):
    def __init__(self, parent: ttk.Widget) -> None:
        super().__init__(parent)
        self.configure(padding=20)

        tb.Label(self, text="حول البرنامج", font=FONTS["heading"], anchor="e").pack(fill="x", pady=(0, 12))
        tb.Label(
            self,
            text=f"{config.APP_NAME_EN} - الإصدار {config.VERSION}\n\nنظام إدارة صالة رياضية مبني باستخدام Python و SQLite.",
            font=FONTS["body"],
            anchor="e",
            justify="right",
        ).pack(fill="x")


class DashboardFrame(tb.Frame):
    """Dashboard view showing real stats from the database."""

    def __init__(self, parent: ttk.Widget, db: DatabaseManager | None, user_data: dict, on_navigate) -> None:
        super().__init__(parent)
        self.db = db
        self.user_data = user_data
        self.on_navigate = on_navigate

        self.stats_vars = {
            "total_members": tk.StringVar(master=self, value="-"),
            "active_members": tk.StringVar(master=self, value="-"),
            "today_check_ins": tk.StringVar(master=self, value="-"),
            "monthly_revenue": tk.StringVar(master=self, value="-"),
        }

        self.configure(padding=10)
        self.create_widgets()
        self.refresh()

    def create_widgets(self) -> None:
        tb.Label(self, text="لوحة التحكم", font=FONTS["heading"], anchor="e").pack(fill="x", pady=(0, 12))

        cards = tb.Frame(self)
        cards.pack(fill="x")

        self._stat_card(cards, "إجمالي الأعضاء", self.stats_vars["total_members"], "👥")
        self._stat_card(cards, "الأعضاء النشطين", self.stats_vars["active_members"], "✅")
        self._stat_card(cards, "حضور اليوم", self.stats_vars["today_check_ins"], "📅")
        self._stat_card(cards, "إيرادات الشهر", self.stats_vars["monthly_revenue"], "💰")

        actions = tb.Labelframe(self, text="إجراءات سريعة", padding=14)
        actions.pack(fill="x", pady=16)

        row = tb.Frame(actions)
        row.pack(fill="x")

        tb.Button(row, text="إضافة عضو جديد", bootstyle="primary", command=lambda: self.on_navigate("members")).pack(
            side="right", padx=6, fill="x", expand=True, ipady=8
        )
        tb.Button(row, text="تسجيل اشتراك", bootstyle="success", command=lambda: self.on_navigate("subscriptions")).pack(
            side="right", padx=6, fill="x", expand=True, ipady=8
        )
        tb.Button(row, text="تسجيل حضور", bootstyle="warning", command=lambda: self.on_navigate("attendance")).pack(
            side="right", padx=6, fill="x", expand=True, ipady=8
        )
        tb.Button(row, text="تسجيل دفعة", bootstyle="secondary", command=lambda: self.on_navigate("payments")).pack(
            side="right", padx=6, fill="x", expand=True, ipady=8
        )

        bottom = tb.Frame(self)
        bottom.pack(fill="both", expand=True)

        left = tb.Labelframe(bottom, text="اشتراكات تنتهي قريباً", padding=12)
        left.pack(side="right", fill="both", expand=True, padx=(0, 8))

        self.expiring_list = tk.Listbox(left, height=8)
        self.expiring_list.pack(fill="both", expand=True)

        right = tb.Labelframe(bottom, text="آخر النشاطات", padding=12)
        right.pack(side="left", fill="both", expand=True, padx=(8, 0))

        cols = ("time", "type", "desc")
        self.activity_tree = ttk.Treeview(right, columns=cols, show="headings", height=8)
        self.activity_tree.heading("time", text="الوقت")
        self.activity_tree.heading("type", text="النوع")
        self.activity_tree.heading("desc", text="الوصف")
        self.activity_tree.column("time", width=120, anchor="center")
        self.activity_tree.column("type", width=90, anchor="center")
        self.activity_tree.column("desc", width=400, anchor="e")
        self.activity_tree.pack(fill="both", expand=True)

        tb.Button(self, text="تحديث", bootstyle="secondary", command=self.refresh).pack(anchor="w", pady=(12, 0))

    def _stat_card(self, parent: ttk.Widget, title: str, var: tk.StringVar, icon: str) -> None:
        card = tb.Frame(parent, padding=12, bootstyle="secondary")
        card.pack(side="right", padx=6, fill="x", expand=True)

        tb.Label(card, text=f"{icon}  {title}", font=FONTS["small"], anchor="e").pack(fill="x")
        tb.Label(card, textvariable=var, font=FONTS["subheading"], anchor="e").pack(fill="x", pady=(6, 0))

    def refresh(self) -> None:
        """Refresh dashboard stats and lists."""

        if self.db is None:
            self.stats_vars["total_members"].set("-")
            self.stats_vars["active_members"].set("-")
            self.stats_vars["today_check_ins"].set("-")
            self.stats_vars["monthly_revenue"].set("-")
            return

        try:
            stats = self.db.get_dashboard_stats()
            self.stats_vars["total_members"].set(str(stats.get("total_members", 0)))
            self.stats_vars["active_members"].set(str(stats.get("active_members", 0)))
            self.stats_vars["today_check_ins"].set(str(stats.get("today_check_ins", 0)))
            self.stats_vars["monthly_revenue"].set(format_money(float(stats.get("monthly_revenue", 0) or 0), db=self.db, decimals=0))
        except Exception:
            pass

        self.expiring_list.delete(0, tk.END)
        try:
            expiring = self.db.get_expiring_subscriptions(days=7)
            for s in expiring:
                name = f"{s.get('member_code', '')} - {s.get('first_name', '')} {s.get('last_name', '')}".strip()
                end = s.get("end_date", "")
                self.expiring_list.insert(tk.END, f"{name}  |  ينتهي: {end}")
        except Exception:
            self.expiring_list.insert(tk.END, "لا توجد بيانات")

        for i in self.activity_tree.get_children():
            self.activity_tree.delete(i)

        # Lightweight activity feed built from existing tables (payments, subscriptions, members)
        try:
            with self.db.get_connection() as conn:
                cur = conn.cursor()
                rows = cur.execute(
                    """
                    SELECT created_at AS ts, 'عضو جديد' AS type,
                           (first_name || ' ' || last_name || ' - ' || member_code) AS desc
                    FROM members
                    WHERE created_at IS NOT NULL

                    UNION ALL

                    SELECT created_at AS ts, 'اشتراك' AS type,
                           ('اشتراك #' || id || ' - عضو #' || member_id) AS desc
                    FROM subscriptions
                    WHERE created_at IS NOT NULL

                    UNION ALL

                    SELECT created_at AS ts, 'دفعة' AS type,
                           ('إيصال ' || COALESCE(receipt_number, '') || ' - مبلغ ' || amount) AS desc
                    FROM payments
                    WHERE created_at IS NOT NULL

                    ORDER BY ts DESC
                    LIMIT 10
                    """
                ).fetchall()

                for r in rows:
                    self.activity_tree.insert("", "end", values=(r["ts"], r["type"], r["desc"]))
        except Exception:
            self.activity_tree.insert("", "end", values=("-", "-", "لا توجد بيانات"))


if __name__ == "__main__":
    user = {"id": 1, "username": "admin", "role": "admin"}
    app = MainWindow(user)
    app.run()
