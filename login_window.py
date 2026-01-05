"""Professional login window for Gym Management System."""

from __future__ import annotations

import json
import sys
import traceback
import tkinter as tk
import tkinter.font as tkfont
from pathlib import Path
from tkinter import messagebox
from tkinter import ttk
import math
from datetime import datetime

import ttkbootstrap as tb

import config
from database import DatabaseManager


_COLOR_LOG_PATH = Path(__file__).resolve().parent / "color_error.log"


class LoginWindow:
    def __init__(self) -> None:
        self.root = tb.Window(themename="darkly")

        self._install_tk_call_color_guard()

        try:
            icon_path = config.ICONS_DIR / "app.ico"
            if icon_path.exists() and icon_path.is_file():
                self.root.iconbitmap(str(icon_path))
        except Exception:
            pass

        self.db: DatabaseManager | None = None

        self.username_var = tk.StringVar(master=self.root)
        self.password_var = tk.StringVar(master=self.root)
        self.remember_var = tk.BooleanVar(master=self.root, value=False)
        self.error_var = tk.StringVar(master=self.root, value="")

        self._remember_file = Path(config.DATA_DIR) / "remember_login.json"

        self._setup_window()
        self._create_widgets()
        self._init_database()
        self._load_saved_username()

    def _install_tk_call_color_guard(self) -> None:
        """Log unknown/empty Tk colors to color_error.log for debugging."""
        try:
            tkapp = self.root.tk
            original_call = tkapp.call

            color_flags = {
                "-fill",
                "-outline",
                "-background",
                "-foreground",
                "-activebackground",
                "-activeforeground",
                "-highlightbackground",
                "-highlightcolor",
                "-selectbackground",
                "-selectforeground",
                "-insertbackground",
                "-disabledforeground",
            }

            def _log(reason: str, a: list[object]) -> None:
                try:
                    with open(_COLOR_LOG_PATH, "a", encoding="utf-8") as f:
                        f.write("\n" + "=" * 80 + "\n")
                        f.write(datetime.now().isoformat() + "\n")
                        f.write(reason + "\n")
                        f.write("Args: " + repr(a) + "\n")
                        f.write("Stack:\n" + "".join(traceback.format_stack()) + "\n")
                except Exception:
                    pass

            def guarded_call(*args):  # type: ignore[no-untyped-def]
                a = list(args)
                for i, v in enumerate(a[:-1]):
                    if v in color_flags and a[i + 1] == "":
                        _log(f"Empty color passed to Tcl option: {v}", a)
                        raise RuntimeError(f"Empty color passed to Tcl option {v}")
                try:
                    return original_call(*args)
                except tk.TclError as e:
                    if 'unknown color name ""' in str(e):
                        _log("TclError: unknown color name \"\"", a)
                        raise
                    raise

            tkapp.call = guarded_call  # type: ignore[assignment]
        except Exception:
            pass

    def _setup_window(self) -> None:
        self.root.title("نظام إدارة الصالة الرياضية - تسجيل الدخول")
        self.root.geometry("420x520")
        self.root.resizable(False, False)

        self.root.update_idletasks()
        w = self.root.winfo_width() or 420
        h = self.root.winfo_height() or 520
        x = (self.root.winfo_screenwidth() - w) // 2
        y = (self.root.winfo_screenheight() - h) // 2
        self.root.geometry(f"{w}x{h}+{x}+{y}")

        self.root.protocol("WM_DELETE_WINDOW", self.root.destroy)

    def _create_widgets(self) -> None:
        outer = tb.Frame(self.root, padding=20)
        outer.pack(fill="both", expand=True)

        tb.Label(
            outer,
            text="تسجيل الدخول",
            font=("Cairo", 18, "bold"),
            anchor="center",
            justify="center",
        ).pack(fill="x", pady=(5, 2))

        tb.Label(
            outer,
            text="نظام إدارة الصالة الرياضية",
            font=("Cairo", 10),
            anchor="center",
            justify="center",
            bootstyle="secondary",
        ).pack(fill="x", pady=(0, 20))

        form = tb.Frame(outer)
        form.pack(fill="x", pady=(0, 10))

        tb.Label(form, text="اسم المستخدم", font=("Cairo", 10, "bold"), anchor="e").pack(fill="x")
        self.username_entry = tb.Entry(form, textvariable=self.username_var, justify="right")
        self.username_entry.pack(fill="x", pady=(6, 14), ipady=5)

        tb.Label(form, text="كلمة المرور", font=("Cairo", 10, "bold"), anchor="e").pack(fill="x")
        self.password_entry = tb.Entry(form, textvariable=self.password_var, justify="right", show="•")
        self.password_entry.pack(fill="x", pady=(6, 10), ipady=5)

        remember_row = tb.Frame(form)
        remember_row.pack(fill="x", pady=(0, 10))
        tb.Checkbutton(
            remember_row,
            text="تذكرني",
            variable=self.remember_var,
            bootstyle="round-toggle",
        ).pack(side="right")

        self.error_label = tb.Label(
            form,
            textvariable=self.error_var,
            bootstyle="danger",
            anchor="e",
            justify="right",
            wraplength=340,
        )
        self.error_label.pack(fill="x", pady=(0, 12))

        tb.Button(
            form,
            text="تسجيل الدخول",
            bootstyle="primary",
            command=self.login,
        ).pack(fill="x", ipady=8)

        tb.Label(
            outer,
            text="الافتراضي: admin / admin123",
            font=("Cairo", 9),
            bootstyle="secondary",
            anchor="center",
            justify="center",
        ).pack(fill="x", pady=(18, 0))

        self.root.bind("<Return>", lambda _e: self.login())
        self.root.bind("<Escape>", lambda _e: self.root.destroy())
        self.username_entry.focus_set()

    def _init_database(self) -> None:
        try:
            self.db = DatabaseManager()
            try:
                with self.db.get_connection() as conn:
                    admin = conn.execute(
                        "SELECT id FROM users WHERE username = ? LIMIT 1",
                        (config.DEFAULT_ADMIN_USERNAME,),
                    ).fetchone()
                    if admin is None:
                        self.db.create_user(
                            config.DEFAULT_ADMIN_USERNAME,
                            config.DEFAULT_ADMIN_PASSWORD,
                            "مدير النظام",
                            role="admin",
                        )
            except Exception:
                pass
        except Exception as e:
            messagebox.showerror("خطأ", f"فشل الاتصال بقاعدة البيانات: {e}")

    def _load_saved_username(self) -> None:
        try:
            if self._remember_file.exists():
                data = json.loads(self._remember_file.read_text(encoding="utf-8") or "{}")
                username = str(data.get("username") or "").strip()
                if username:
                    self.username_var.set(username)
                    self.remember_var.set(True)
        except Exception:
            pass

    def _save_username(self) -> None:
        try:
            self._remember_file.parent.mkdir(parents=True, exist_ok=True)
            if self.remember_var.get():
                self._remember_file.write_text(
                    json.dumps({"username": self.username_var.get().strip()}, ensure_ascii=False),
                    encoding="utf-8",
                )
            elif self._remember_file.exists():
                self._remember_file.unlink(missing_ok=True)
        except Exception:
            pass

    def login(self) -> None:
        self.error_var.set("")
        username = self.username_var.get().strip()
        password = self.password_var.get().strip()

        if not username or not password:
            self.error_var.set("يرجى إدخال اسم المستخدم وكلمة المرور")
            return

        if self.db is None:
            messagebox.showerror("خطأ", "قاعدة البيانات غير متاحة")
            return

        try:
            user_data = self.db.authenticate_user(username, password)
            if user_data:
                self._save_username()

                self.root.destroy()
                from main_window import MainWindow

                MainWindow(user_data).run()
                return
            self.error_var.set("بيانات الدخول غير صحيحة")
        except Exception as e:
            messagebox.showerror("خطأ", f"حدث خطأ: {e}")

    def run(self) -> None:
        self.root.mainloop()


class ModernLoginWindow:
    """Modern professional login window with animations and custom styling."""

    COLORS = {
        'bg': '#1a1a2e',
        'card': '#16213e',
        'primary': '#e94560',
        'text': '#eaeaea',
        'text_dim': '#8b8b8b',
        'input_bg': '#0f0f1a',
        'border': '#2a2a4a',
    }

    def __init__(self):
        self.root = tk.Tk()
        try:
            icon_path = config.ICONS_DIR / "app.ico"
            if icon_path.exists() and icon_path.is_file():
                self.root.iconbitmap(str(icon_path))
        except Exception:
            pass
        self.root.title("نظام إدارة الصالة الرياضية - تسجيل الدخول")
        self.root.geometry("450x550")
        self.root.resizable(False, False)
        self.root.configure(bg=self.COLORS['bg'])
        
        # Center
        self.root.update_idletasks()
        x = (self.root.winfo_screenwidth() - 450) // 2
        y = (self.root.winfo_screenheight() - 550) // 2
        self.root.geometry(f"450x550+{x}+{y}")
        
        self.db = None
        self.username_var = tk.StringVar()
        self.password_var = tk.StringVar()
        self.remember_var = tk.BooleanVar(value=False)
        self.error_var = tk.StringVar()
        self._show_password = False
        self._failed_attempts = 0
        self._max_attempts = 5
        self._lock_seconds = 30
        self._locked = False
        self._remember_file = Path(config.DATA_DIR) / "remember_login.json"
        
        try:
            self._remember_file.parent.mkdir(parents=True, exist_ok=True)
        except Exception:
            pass
        
        self._setup_styles()
        self._create_ui()
        self._init_database()
        self._load_saved_username()

    def _setup_styles(self):
        """Configure ttk styles."""
        style = ttk.Style()
        try:
            style.theme_use('clam')
        except Exception:
            pass
        
        # Configure colors
        style.configure('.', background=self.COLORS['bg'])
        style.configure('Card.TFrame', background=self.COLORS['card'])
        style.configure(
            'Title.TLabel',
            background=self.COLORS['card'],
            foreground=self.COLORS['text'],
            font=('Segoe UI', 20, 'bold')
        )
        style.configure(
            'Subtitle.TLabel',
            background=self.COLORS['card'],
            foreground=self.COLORS['text_dim'],
            font=('Segoe UI', 10)
        )
        style.configure(
            'Field.TLabel',
            background=self.COLORS['card'],
            foreground=self.COLORS['text'],
            font=('Segoe UI', 11)
        )
        style.configure(
            'Error.TLabel',
            background=self.COLORS['card'],
            foreground='#ff6b6b',
            font=('Segoe UI', 9)
        )
        style.configure(
            'Login.TButton',
            background=self.COLORS['primary'],
            foreground=self.COLORS['text'],
            font=('Segoe UI', 12, 'bold'),
            padding=(20, 12)
        )
        style.map(
            'Login.TButton',
            background=[('active', '#c73e54'), ('pressed', '#b83549')]
        )

    def _create_ui(self):
        """Create the UI."""
        # Main container
        main = tk.Frame(self.root, bg=self.COLORS['bg'])
        main.pack(fill='both', expand=True, padx=30, pady=30)
        
        # Card
        card = tk.Frame(main, bg=self.COLORS['card'])
        card.pack(fill='both', expand=True)
        
        # Content padding
        content = tk.Frame(card, bg=self.COLORS['card'])
        content.pack(fill='both', expand=True, padx=40, pady=40)
        
        # Logo
        logo_frame = tk.Frame(content, bg=self.COLORS['card'])
        logo_frame.pack(pady=(0, 20))
        
        logo_label = tk.Label(
            logo_frame,
            text="🏋️",
            font=('Segoe UI Emoji', 48),
            bg=self.COLORS['card']
        )
        logo_label.pack()
        
        # Title
        title = tk.Label(
            content,
            text="تسجيل الدخول",
            font=('Segoe UI', 24, 'bold'),
            fg=self.COLORS['text'],
            bg=self.COLORS['card']
        )
        title.pack(pady=(0, 5))
        
        subtitle = tk.Label(
            content,
            text="نظام إدارة الصالة الرياضية",
            font=('Segoe UI', 11),
            fg=self.COLORS['text_dim'],
            bg=self.COLORS['card']
        )
        subtitle.pack(pady=(0, 30))
        
        # Username field
        self._create_field(content, "اسم المستخدم", self.username_var, False)
        
        # Password field
        self._create_field(content, "كلمة المرور", self.password_var, True)
        
        # Remember me
        remember_frame = tk.Frame(content, bg=self.COLORS['card'])
        remember_frame.pack(fill='x', pady=(5, 15))
        
        remember_cb = tk.Checkbutton(
            remember_frame,
            text="تذكرني",
            variable=self.remember_var,
            font=('Segoe UI', 10),
            fg=self.COLORS['text_dim'],
            bg=self.COLORS['card'],
            selectcolor=self.COLORS['input_bg'],
            activebackground=self.COLORS['card'],
            activeforeground=self.COLORS['text']
        )
        remember_cb.pack(side='right')
        
        # Error label
        error_label = tk.Label(
            content,
            textvariable=self.error_var,
            font=('Segoe UI', 9),
            fg='#ff6b6b',
            bg=self.COLORS['card'],
            wraplength=300
        )
        error_label.pack(pady=(0, 10))
        
        # Login button
        self.login_btn = tk.Button(
            content,
            text="تسجيل الدخول",
            font=('Segoe UI', 12, 'bold'),
            fg=self.COLORS['text'],
            bg=self.COLORS['primary'],
            activebackground='#c73e54',
            activeforeground=self.COLORS['text'],
            relief='flat',
            cursor='hand2',
            command=self._login
        )
        self.login_btn.pack(fill='x', ipady=12, pady=(10, 0))
        
        # Hover effect
        self.login_btn.bind('<Enter>', lambda e: self.login_btn.configure(bg='#c73e54'))
        self.login_btn.bind('<Leave>', lambda e: self.login_btn.configure(bg=self.COLORS['primary']))
        
        # Info
        info = tk.Label(
            content,
            text="الافتراضي: admin / admin123",
            font=('Segoe UI', 9),
            fg=self.COLORS['text_dim'],
            bg=self.COLORS['card']
        )
        info.pack(pady=(20, 0))
        
        # Bindings
        self.root.bind('<Return>', lambda e: self._login())
        self.root.bind('<Escape>', lambda e: self.root.destroy())

    def _create_field(self, parent, label_text, variable, is_password):
        """Create an input field."""
        frame = tk.Frame(parent, bg=self.COLORS['card'])
        frame.pack(fill='x', pady=(0, 15))
        
        label = tk.Label(
            frame,
            text=label_text,
            font=('Segoe UI', 11),
            fg=self.COLORS['text'],
            bg=self.COLORS['card'],
            anchor='e'
        )
        label.pack(fill='x')
        
        entry_frame = tk.Frame(
            frame,
            bg=self.COLORS['input_bg'],
            highlightbackground=self.COLORS['border'],
            highlightthickness=1,
            highlightcolor=self.COLORS['primary']
        )
        entry_frame.pack(fill='x', pady=(5, 0))
        
        entry = tk.Entry(
            entry_frame,
            textvariable=variable,
            font=('Segoe UI', 12),
            fg=self.COLORS['text'],
            bg=self.COLORS['input_bg'],
            insertbackground=self.COLORS['text'],
            relief='flat',
            justify='right',
            show='•' if is_password else ''
        )
        entry.pack(fill='x', padx=12, pady=12)
        
        if is_password:
            self.password_entry = entry
        else:
            self.username_entry = entry
            entry.focus_set()

    def _init_database(self):
        """Initialize database."""
        try:
            self.db = DatabaseManager()
            try:
                with self.db.get_connection() as conn:
                    admin = conn.execute(
                        "SELECT id FROM users WHERE username = ? LIMIT 1",
                        (config.DEFAULT_ADMIN_USERNAME,)
                    ).fetchone()
                    if admin is None:
                        self.db.create_user(
                            config.DEFAULT_ADMIN_USERNAME,
                            config.DEFAULT_ADMIN_PASSWORD,
                            "مدير النظام",
                            role="admin"
                        )
            except Exception:
                pass
        except Exception as e:
            messagebox.showerror("خطأ", f"فشل الاتصال بقاعدة البيانات: {e}")

    def _load_saved_username(self):
        """Load saved username."""
        try:
            if self._remember_file.exists():
                data = json.loads(self._remember_file.read_text(encoding='utf-8') or '{}')
                username = str(data.get('username') or '').strip()
                if username:
                    self.username_var.set(username)
                    self.remember_var.set(True)
        except Exception:
            pass

    def _save_username(self):
        """Save username."""
        try:
            if self.remember_var.get():
                self._remember_file.write_text(
                    json.dumps({'username': self.username_var.get().strip()}, ensure_ascii=False),
                    encoding='utf-8'
                )
            elif self._remember_file.exists():
                self._remember_file.unlink(missing_ok=True)
        except Exception:
            pass

    def _login(self):
        """Handle login."""
        if self._locked:
            return

        self.error_var.set('')
        username = self.username_var.get().strip()
        password = self.password_var.get().strip()

        if not username or not password:
            self.error_var.set('يرجى إدخال اسم المستخدم وكلمة المرور')
            return

        if self.db is None:
            messagebox.showerror('خطأ', 'قاعدة البيانات غير متاحة')
            return

        try:
            user_data = self.db.authenticate_user(username, password)
            if user_data:
                self._save_username()
                self.root.destroy()
                from main_window import MainWindow

                MainWindow(user_data).run()
                return

            self._failed_attempts += 1
            remaining = self._max_attempts - self._failed_attempts
            if remaining <= 0:
                self._lock_ui()
            else:
                self.error_var.set(f'بيانات الدخول غير صحيحة (متبقي {remaining} محاولات)')
        except Exception as e:
            messagebox.showerror('خطأ', f'حدث خطأ: {e}')

    def _lock_ui(self):
        """Lock after failed attempts."""
        self._locked = True
        try:
            self.login_btn.configure(state='disabled')
        except Exception:
            pass

        def tick(remaining):
            if remaining <= 0:
                self._locked = False
                self._failed_attempts = 0
                self.error_var.set('')
                try:
                    self.login_btn.configure(state='normal')
                except Exception:
                    pass
                return
            self.error_var.set(f'تم الإيقاف مؤقتاً. انتظر {remaining} ثانية')
            self.root.after(1000, lambda: tick(remaining - 1))

        tick(self._lock_seconds)

    def run(self):
        """Run the app."""
        self.root.mainloop()


if __name__ == "__main__":
    # Use the modern version
    app = ModernLoginWindow()
    # Or use the simpler version:
    # app = ModernLoginWindowSimple()
    app.run()