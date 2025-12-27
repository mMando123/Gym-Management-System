"""Login window for Gym Management System (RTL Arabic UI).

This is the first window displayed when launching the application.
It authenticates admin users using DatabaseManager.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
import tkinter as tk
from tkinter import messagebox
from tkinter import ttk

import ttkbootstrap as tb
from PIL import Image, ImageTk

import config
from database import DatabaseManager


class LoginWindow:
    """Modern login window with RTL support for Arabic."""

    def __init__(self) -> None:
        self.root = tb.Window(themename="cosmo")
        self.root.withdraw()

        self.db: DatabaseManager | None = None

        self._logo_photo: ImageTk.PhotoImage | None = None
        self._show_password: bool = False
        self._failed_attempts: int = 0
        self._max_attempts: int = 5

        self.username_var = tk.StringVar()
        self.password_var = tk.StringVar()
        self.remember_var = tk.BooleanVar(value=False)

        self.error_var = tk.StringVar(value="")

        self.setup_window()
        self.create_widgets()

        self._init_database()
        self.load_saved_credentials()

        self.center_window()
        self.root.deiconify()

        self.root.bind("<Return>", lambda _e: self.login())
        self.root.bind("<Escape>", lambda _e: self.on_closing())

        self.username_entry.focus_set()

    # ------------------------------
    # Window setup
    # ------------------------------

    def setup_window(self) -> None:
        """Configure top-level window properties."""

        self.root.title("نظام إدارة الجيم - تسجيل الدخول")
        self.root.geometry("400x500")
        self.root.resizable(False, False)
        self.root.configure(background=config.THEME_COLORS["background"])
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

        icon_path = self._find_icon_path()
        if icon_path is not None:
            try:
                self.root.iconbitmap(str(icon_path))
            except Exception:
                pass

    def center_window(self) -> None:
        """Center the window on the screen."""

        self.root.update_idletasks()
        w = self.root.winfo_width()
        h = self.root.winfo_height()
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        x = (sw - w) // 2
        y = (sh - h) // 2
        self.root.geometry(f"{w}x{h}+{x}+{y}")

    # ------------------------------
    # UI creation
    # ------------------------------

    def create_widgets(self) -> None:
        """Create all UI elements with RTL alignment."""

        font_title = ("Cairo", 16, "bold")
        font_subtitle = ("Cairo", 11)
        font_label = ("Cairo", 10, "bold")
        font_entry = ("Cairo", 10)

        outer = tb.Frame(self.root, padding=20, bootstyle="secondary")
        outer.pack(fill="both", expand=True)

        header = tb.Frame(outer)
        header.pack(fill="x")

        logo_label = tb.Label(header)
        logo_label.pack(pady=(5, 10))
        self._set_logo(logo_label)

        tb.Label(
            header,
            text="نادي القوة الرياضي",
            font=font_title,
            anchor="center",
            justify="center",
        ).pack(fill="x")

        tb.Label(
            header,
            text="نظام الإدارة المتكامل",
            font=font_subtitle,
            foreground=config.THEME_COLORS["text_secondary"],
            anchor="center",
            justify="center",
        ).pack(fill="x", pady=(2, 0))

        form = tb.Labelframe(outer, text="", padding=18, bootstyle="secondary")
        form.pack(fill="x", pady=18)

        tb.Label(form, text="اسم المستخدم", font=font_label, anchor="e").pack(fill="x")
        self.username_entry = tb.Entry(
            form,
            textvariable=self.username_var,
            font=font_entry,
            justify="right",
            bootstyle="secondary",
        )
        self.username_entry.pack(fill="x", pady=(6, 12), ipady=6)

        tb.Label(form, text="كلمة المرور", font=font_label, anchor="e").pack(fill="x")

        pass_row = tb.Frame(form)
        pass_row.pack(fill="x", pady=(6, 10))

        self.password_entry = tb.Entry(
            pass_row,
            textvariable=self.password_var,
            font=font_entry,
            justify="right",
            show="*",
            bootstyle="secondary",
        )
        self.password_entry.pack(side="right", fill="x", expand=True, ipady=6)

        self.toggle_btn = tb.Button(
            pass_row,
            text="👁",
            width=3,
            command=self.toggle_password_visibility,
            bootstyle="secondary-outline",
        )
        self.toggle_btn.pack(side="left", padx=(8, 0), ipadx=2)

        self.remember_chk = tb.Checkbutton(
            form,
            text="تذكرني",
            variable=self.remember_var,
            bootstyle="secondary",
        )
        self.remember_chk.pack(anchor="e", pady=(0, 8))

        self.error_label = tb.Label(
            form,
            textvariable=self.error_var,
            font=("Cairo", 10),
            anchor="e",
            justify="right",
            bootstyle="danger",
        )
        self.error_label.pack(fill="x")
        self.clear_error()

        self.login_btn = tb.Button(
            outer,
            text="تسجيل الدخول",
            command=self.login,
            bootstyle="primary",
        )
        self.login_btn.pack(fill="x", ipady=10)

        footer = tb.Frame(outer)
        footer.pack(side="bottom", fill="x", pady=(18, 0))

        tb.Label(
            footer,
            text=f"الإصدار {config.VERSION}",
            font=("Cairo", 9),
            foreground=config.THEME_COLORS["text_secondary"],
            anchor="center",
        ).pack(fill="x")

        tb.Label(
            footer,
            text="© 2024 جميع الحقوق محفوظة",
            font=("Cairo", 9),
            foreground=config.THEME_COLORS["text_secondary"],
            anchor="center",
        ).pack(fill="x", pady=(4, 0))

    # ------------------------------
    # Logo / Icon helpers
    # ------------------------------

    def _find_logo_path(self) -> tk.PathName | None:
        candidates = [
            config.IMAGES_DIR / "logo.png",
            config.IMAGES_DIR / "logo.jpg",
            config.IMAGES_DIR / "logo.jpeg",
            config.ASSETS_DIR / "logo.png",
        ]
        for p in candidates:
            if p.exists() and p.is_file():
                return p
        return None

    def _find_icon_path(self) -> Path | None:
        candidates = [
            config.ICONS_DIR / "app.ico",
            config.ASSETS_DIR / "app.ico",
        ]
        for p in candidates:
            if p.exists() and p.is_file():
                return p
        return None

    def _set_logo(self, target_label: ttk.Label) -> None:
        logo_path = self._find_logo_path()
        if logo_path is None:
            target_label.configure(
                text="LOGO",
                font=("Cairo", 12, "bold"),
                width=12,
                anchor="center",
                foreground=config.THEME_COLORS["text_secondary"],
            )
            return

        try:
            img = Image.open(logo_path)
            img = img.convert("RGBA")
            img = img.resize((120, 120))
            self._logo_photo = ImageTk.PhotoImage(img)
            target_label.configure(image=self._logo_photo)
        except Exception:
            target_label.configure(
                text="LOGO",
                font=("Cairo", 12, "bold"),
                width=12,
                anchor="center",
                foreground=config.THEME_COLORS["text_secondary"],
            )

    # ------------------------------
    # Database init
    # ------------------------------

    def _init_database(self) -> None:
        """Initialize DatabaseManager with user-friendly error handling."""

        try:
            self.db = DatabaseManager()
        except Exception as e:
            self.db = None
            self.show_error(f"تعذر الاتصال بقاعدة البيانات: {e}")

    # ------------------------------
    # Form helpers
    # ------------------------------

    def toggle_password_visibility(self) -> None:
        """Toggle showing/hiding password characters."""

        self._show_password = not self._show_password
        if self._show_password:
            self.password_entry.configure(show="")
            self.toggle_btn.configure(text="🙈")
        else:
            self.password_entry.configure(show="*")
            self.toggle_btn.configure(text="👁")

    def validate_inputs(self) -> bool:
        """Validate username and password are present."""

        username = self._normalize_login_text(self.username_var.get(), to_lower=True)
        password = self._normalize_login_text(self.password_var.get(), to_lower=False)

        if not username:
            self.show_error("يرجى إدخال اسم المستخدم")
            self.username_entry.focus_set()
            return False

        if not password:
            self.show_error("يرجى إدخال كلمة المرور")
            self.password_entry.focus_set()
            return False

        return True

    def show_error(self, message: str) -> None:
        """Show an error message and perform a simple shake animation."""

        try:
            self.error_label.configure(bootstyle="danger")
        except Exception:
            pass
        self.error_var.set(message)
        self.error_label.pack_configure()
        self._shake_window()

    def clear_error(self) -> None:
        """Clear and hide the error message label."""

        self.error_var.set("")

    def _shake_window(self) -> None:
        try:
            x = self.root.winfo_x()
            y = self.root.winfo_y()
            offsets = [(-6, 0), (6, 0), (-4, 0), (4, 0), (-2, 0), (2, 0), (0, 0)]

            def step(i: int = 0) -> None:
                if i >= len(offsets):
                    return
                dx, dy = offsets[i]
                self.root.geometry(f"+{x + dx}+{y + dy}")
                self.root.after(25, lambda: step(i + 1))

            step()
        except Exception:
            pass

    # ------------------------------
    # Login flow
    # ------------------------------

    def login(self) -> None:
        """Validate inputs and authenticate via DatabaseManager."""

        self.clear_error()

        if self._failed_attempts >= self._max_attempts:
            self.show_error("تم قفل تسجيل الدخول مؤقتاً بسبب محاولات كثيرة")
            return

        if not self.validate_inputs():
            return

        if self.db is None:
            self.show_error("قاعدة البيانات غير جاهزة. أعد تشغيل البرنامج.")
            return

        username = self._normalize_login_text(self.username_var.get(), to_lower=True)
        password = self._normalize_login_text(self.password_var.get(), to_lower=False)

        try:
            # === الخطوة 1: التحقق من وجود المستخدم وحالته ===
            with self.db.get_connection() as conn:
                row = conn.execute(
                    "SELECT id, password, is_active FROM users WHERE username = ? COLLATE NOCASE LIMIT 1",
                    (username,),
                ).fetchone()

            # حالة 1: اسم المستخدم غير موجود
            if row is None:
                self._failed_attempts += 1
                self.show_error("اسم المستخدم غير موجود")
                self.username_entry.focus_set()
                try:
                    self.username_entry.selection_range(0, tk.END)
                    self.username_entry.icursor(tk.END)
                except Exception:
                    pass
                try:
                    logging.info("Login failed: username '%s' not found", username)
                except Exception:
                    pass
                return

            # حالة 2: الحساب معطل
            if int(row["is_active"] or 0) != 1:
                self._failed_attempts += 1
                self.show_error("الحساب معطل. تواصل مع المدير")
                try:
                    logging.info("Login failed: account '%s' is disabled", username)
                except Exception:
                    pass
                return

            # حالة 3: التحقق من كلمة المرور
            if not self.db.verify_password(password, row["password"]):
                self._failed_attempts += 1
                self.show_error("كلمة المرور غير صحيحة")
                self.password_var.set("")
                self.password_entry.focus_set()
                try:
                    logging.info("Login failed: wrong password for '%s'", username)
                except Exception:
                    pass
                return

            # === نجاح تسجيل الدخول ===
            user = self.db.get_user_by_id(int(row["id"]))
            if user is None:
                self.show_error("حدث خطأ غير متوقع")
                return

            self._failed_attempts = 0

            if self.remember_var.get():
                self.save_credentials(username)
            else:
                self._clear_saved_credentials()

            self.root.destroy()
            self._open_main_window(user)

        except Exception as e:
            self.show_error(f"حدث خطأ: {e}")
            try:
                logging.error("Login error: %s", e)
            except Exception:
                pass

    def _complete_login(self, user: dict, username: str) -> None:
        try:
            if self.remember_var.get():
                self.save_credentials(username)
            else:
                self._clear_saved_credentials()

            self.root.destroy()
        except Exception:
            pass

        try:
            self._open_main_window(user)
        except Exception:
            pass

    def _normalize_login_text(self, text: str, to_lower: bool) -> str:
        text = (text or "").strip()
        # إزالة العلامات غير المرئية الشائعة في نصوص RTL/لوحات المفاتيح
        # (قد تؤدي إلى فشل التطابق حتى لو بدا النص صحيحاً)
        text = re.sub(r"[\u200e\u200f\u202a-\u202e\u2066-\u2069\ufeff]", "", text)
        trans = str.maketrans(
            {
                "٠": "0",
                "١": "1",
                "٢": "2",
                "٣": "3",
                "٤": "4",
                "٥": "5",
                "٦": "6",
                "٧": "7",
                "٨": "8",
                "٩": "9",
            }
        )
        text = text.translate(trans)
        return text.lower() if to_lower else text

    def _open_main_window(self, user: dict) -> None:
        """Open the main window if present, otherwise show success message."""

        try:
            from main_window import MainWindow  # type: ignore

            app = MainWindow(user)
            app.run()
        except Exception:
            try:
                root = tb.Window(themename="cosmo")
                root.title(config.APP_NAME_EN)
                root.geometry("420x180")
                tb.Label(root, text="تم تسجيل الدخول بنجاح!", font=("Cairo", 14, "bold")).pack(pady=30)
                tb.Label(root, text="(لم يتم العثور على نافذة النظام الرئيسية بعد)", font=("Cairo", 10)).pack()
                tb.Button(root, text="إغلاق", bootstyle="secondary", command=root.destroy).pack(pady=20)
                root.mainloop()
            except Exception:
                pass

    # ------------------------------
    # Remember-me persistence
    # ------------------------------

    def _remember_file_path(self) -> Path:
        config.init_directories()
        return config.DATA_DIR / "remember_me.txt"

    def save_credentials(self, username: str) -> None:
        """Save remembered username locally."""

        try:
            self._remember_file_path().write_text(username.strip(), encoding="utf-8")
        except Exception:
            pass

    def _clear_saved_credentials(self) -> None:
        try:
            self._remember_file_path().unlink(missing_ok=True)
        except Exception:
            pass

    def load_saved_credentials(self) -> None:
        """Load saved username and check remember me if present."""

        try:
            p = self._remember_file_path()
            if p.exists():
                username = p.read_text(encoding="utf-8").strip()
                if username:
                    self.username_var.set(username)
                    self.remember_var.set(True)
        except Exception:
            pass

    # ------------------------------
    # Close / run
    # ------------------------------

    def on_closing(self) -> None:
        """Confirm exit before closing."""

        if messagebox.askyesno("تأكيد", "هل تريد إغلاق البرنامج؟"):
            self.root.destroy()

    def run(self) -> None:
        """Start the Tkinter main loop."""

        self.root.mainloop()


if __name__ == "__main__":
    app = LoginWindow()
    app.run()
