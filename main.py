"""Professional login window for Gym Management System."""

from __future__ import annotations

import json
import hashlib
import tkinter as tk
import tkinter.font as tkfont
from pathlib import Path
from tkinter import messagebox
import math
import sys
import traceback
from datetime import datetime

import config
from database import DatabaseManager


_COLOR_LOG_PATH = Path(__file__).resolve().parent / "color_error.log"


class SimpleLoginWindow:
    """Modern professional login window."""

    # Color Scheme
    COLORS = {
        'primary': '#6366f1',
        'primary_hover': '#4f46e5',
        'primary_light': '#e0e7ff',
        'secondary': '#10b981',
        'background': '#0f172a',
        'card_bg': '#1e293b',
        'card_border': '#334155',
        'text_primary': '#f8fafc',
        'text_secondary': '#94a3b8',
        'text_muted': '#64748b',
        'input_bg': '#0f172a',
        'input_border': '#475569',
        'input_focus': '#6366f1',
        'error': '#ef4444',
        'success': '#22c55e',
    }

    def __init__(self):
        self.root = tk.Tk()
        try:
            icon_path = config.ICONS_DIR / "app.ico"
            if icon_path.exists() and icon_path.is_file():
                self.root.iconbitmap(str(icon_path))
        except Exception:
            pass
        self._install_bgerror_handler()
        self._install_tk_call_color_guard()
        try:
            self.root.report_callback_exception = self._report_callback_exception  # type: ignore[attr-defined]
        except Exception:
            pass
        self.root.title("نظام إدارة الصالة الرياضية")
        self.root.geometry("500x650")
        self.root.resizable(False, False)
        self.root.configure(bg=self.COLORS['background'])
        
        # Center window
        self.root.update_idletasks()
        x = (self.root.winfo_screenwidth() // 2) - (500 // 2)
        y = (self.root.winfo_screenheight() // 2) - (650 // 2)
        self.root.geometry(f"500x650+{x}+{y}")
        
        # Variables
        self.db = None
        self.username_var = tk.StringVar()
        self.password_var = tk.StringVar()
        self.remember_var = tk.BooleanVar(value=False)
        self.error_var = tk.StringVar(value="")
        self._show_password = False
        self._failed_attempts = 0
        self._max_attempts = 5
        self._lock_seconds = 30
        self._locked = False
        self._remember_file = Path(config.DATA_DIR) / "remember_login.json"
        self._pulse_phase = 0
        self._animation_running = True
        self._logo_after_id = None
        self._open_main_after_id = None
        self._next_user_data = None
        
        try:
            self._remember_file.parent.mkdir(parents=True, exist_ok=True)
        except Exception:
            pass
        
        self._setup_fonts()
        self._create_widgets()
        self._init_database()
        self._load_saved_username()
        self._start_animations()

        try:
            self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        except Exception:
            pass

    def _install_bgerror_handler(self) -> None:
        try:
            self.root.tk.eval(
                """
                proc bgerror {msg} {
                    if {[string match {*application has been destroyed*} $msg]} {
                        return
                    }
                    puts stderr $msg
                    catch {puts stderr $::errorInfo}
                }
                """
            )
        except Exception:
            pass

    def _install_tk_call_color_guard(self) -> None:
        """Raise a Python error when an empty string is passed as a Tcl color value."""
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

            def _log_color_error(reason: str, a: list[object]) -> None:
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
                        _log_color_error(f"Empty color passed to Tcl option: {v}", a)
                        raise RuntimeError(f"Empty color passed to Tcl option {v}")
                try:
                    return original_call(*args)
                except tk.TclError as e:
                    if 'unknown color name ""' in str(e):
                        _log_color_error("TclError: unknown color name \"\"", a)
                        raise
                    raise

            tkapp.call = guarded_call  # type: ignore[assignment]
        except Exception:
            pass

    def _report_callback_exception(self, exc, val, tb) -> None:  # type: ignore[no-untyped-def]
        try:
            tb_text = "".join(traceback.format_exception(exc, val, tb))
            try:
                print(tb_text, file=sys.stderr)
            except Exception:
                pass
            try:
                print(tb_text)
            except Exception:
                pass
        except Exception:
            pass

    def _verify_password(self, user_row, password: str) -> bool:
        """Verify password for both legacy and salted-hash users.

        - Legacy: database.DatabaseManager.verify_password() => sha256(password)
        - New users created via SettingsManager: sha256(salt + password)
        """

        # 1) Salted-hash path (SettingsManager)
        try:
            salt = user_row["password_salt"]
            stored_hash = user_row["password_hash"]
            if salt and stored_hash:
                digest = hashlib.sha256((str(salt) + password).encode("utf-8")).hexdigest()
                if digest == str(stored_hash):
                    return True
                # SettingsManager also stores hash in `password`
                try:
                    if digest == str(user_row["password"] or ""):
                        return True
                except Exception:
                    pass
        except Exception:
            pass

        # 2) Legacy path
        try:
            return bool(self.db and self.db.verify_password(password, user_row["password"]))
        except Exception:
            return False

    def _setup_fonts(self):
        """Setup custom fonts."""
        try:
            families = set(tkfont.families())
        except Exception:
            families = set()
        
        arabic_fonts = ['Cairo', 'Tajawal', 'Segoe UI', 'Arial']
        self._font_family = next((f for f in arabic_fonts if f in families), 'Arial')
        
        self._fonts = {
            'title': (self._font_family, 22, 'bold'),
            'subtitle': (self._font_family, 11),
            'body': (self._font_family, 11),
            'input': (self._font_family, 12),
            'button': (self._font_family, 12, 'bold'),
            'small': (self._font_family, 9),
        }

    def _create_rounded_rect(self, canvas, x1, y1, x2, y2, radius, **kwargs):
        """Create rounded rectangle on canvas."""
        points = [
            x1 + radius, y1,
            x2 - radius, y1,
            x2, y1,
            x2, y1 + radius,
            x2, y2 - radius,
            x2, y2,
            x2 - radius, y2,
            x1 + radius, y2,
            x1, y2,
            x1, y2 - radius,
            x1, y1 + radius,
            x1, y1,
        ]
        return canvas.create_polygon(points, smooth=True, **kwargs)

    def _create_widgets(self):
        """Create all UI widgets."""
        # Main canvas
        self.canvas = tk.Canvas(
            self.root, width=500, height=650,
            bg=self.COLORS['background'], highlightthickness=0
        )
        self.canvas.pack(fill='both', expand=True)
        
        # Decorative circles
        self.canvas.create_oval(380, -40, 540, 120, outline=self.COLORS['primary'], width=2)
        self.canvas.create_oval(-40, 520, 100, 660, outline=self.COLORS['secondary'], width=2)
        
        # Card
        card_x, card_y = 35, 60
        card_w, card_h = 430, 530
        
        # Card shadow
        self.canvas.create_rectangle(
            card_x + 5, card_y + 5,
            card_x + card_w + 5, card_y + card_h + 5,
            fill='#000000', outline='#000000'
        )
        
        # Card background
        self._create_rounded_rect(
            self.canvas, card_x, card_y,
            card_x + card_w, card_y + card_h,
            radius=20, fill=self.COLORS['card_bg'],
            outline=self.COLORS['card_border'], width=1
        )
        
        # Logo
        center_x = card_x + card_w // 2
        self.logo_outer = self.canvas.create_oval(
            center_x - 40, card_y + 35,
            center_x + 40, card_y + 115,
            outline=self.COLORS['primary'], width=3
        )
        self.canvas.create_oval(
            center_x - 28, card_y + 47,
            center_x + 28, card_y + 103,
            fill=self.COLORS['primary'], outline=self.COLORS['primary'], width=0
        )
        self.canvas.create_text(
            center_x, card_y + 75,
            text="🏋️", font=('Segoe UI Emoji', 24)
        )
        
        # Title
        self.canvas.create_text(
            center_x, card_y + 145,
            text="نظام إدارة الصالة الرياضية",
            font=self._fonts['title'], fill=self.COLORS['text_primary']
        )
        
        # Subtitle
        self.canvas.create_text(
            center_x, card_y + 180,
            text="مرحباً بك! يرجى تسجيل الدخول للمتابعة",
            font=self._fonts['subtitle'], fill=self.COLORS['text_secondary']
        )
        
        # Form area
        form_x = card_x + 35
        form_y = card_y + 210
        form_w = card_w - 70
        
        # Username field
        self._create_input(form_x, form_y, form_w, "اسم المستخدم", "👤", self.username_var, False)
        
        # Password field
        self._create_input(form_x, form_y + 75, form_w, "كلمة المرور", "🔒", self.password_var, True)
        
        # Remember checkbox
        self._create_checkbox(form_x, form_y + 150)
        
        # Error label
        self.error_label = tk.Label(
            self.root, textvariable=self.error_var,
            font=self._fonts['small'], fg=self.COLORS['error'],
            bg=self.COLORS['card_bg'], wraplength=350
        )
        self.error_label.place(x=form_x, y=form_y + 180, width=form_w)
        
        # Login button
        self._create_login_button(form_x, form_y + 210, form_w, 50)
        
        # Info
        info_frame = tk.Frame(self.root, bg=self.COLORS['card_bg'])
        info_frame.place(x=center_x - 100, y=card_y + 470, width=200)
        
        tk.Label(
            info_frame, text="بيانات الدخول الافتراضية:",
            font=self._fonts['small'], fg=self.COLORS['text_muted'],
            bg=self.COLORS['card_bg']
        ).pack()
        
        tk.Label(
            info_frame, text="admin / admin123",
            font=(self._font_family, 10, 'bold'), fg=self.COLORS['primary'],
            bg=self.COLORS['card_bg']
        ).pack()
        
        # Footer
        self.canvas.create_text(
            250, 620, text="© 2025 Gym Management System",
            font=self._fonts['small'], fill=self.COLORS['text_muted']
        )
        
        # Bindings
        self.root.bind("<Return>", lambda e: self._login())
        self.root.bind("<Escape>", lambda e: self._on_close())

    def _cancel_all_after_callbacks(self) -> None:
        """Best-effort cancel of all scheduled after() callbacks."""
        try:
            ids = self.root.tk.call("after", "info")
            for after_id in self.root.tk.splitlist(ids):
                try:
                    self.root.after_cancel(after_id)
                except Exception:
                    pass
        except Exception:
            pass

    def _on_close(self) -> None:
        """Close window safely without leaving after() callbacks behind."""
        try:
            self._animation_running = False
        except Exception:
            pass

        self._cancel_all_after_callbacks()

        self._cancel_all_after_callbacks()

        try:
            if self.root.winfo_exists():
                self.root.destroy()
        except Exception:
            pass

    def _create_input(self, x, y, width, placeholder, icon, variable, is_password):
        """Create styled input field."""
        container = tk.Frame(
            self.root, bg=self.COLORS['input_bg'],
            highlightbackground=self.COLORS['input_border'],
            highlightthickness=2, highlightcolor=self.COLORS['input_focus']
        )
        container.place(x=x, y=y, width=width, height=48)
        
        # Icon
        tk.Label(
            container, text=icon, font=('Segoe UI Emoji', 14),
            fg=self.COLORS['text_muted'], bg=self.COLORS['input_bg']
        ).pack(side='right', padx=(0, 10), pady=10)
        
        # Entry
        entry = tk.Entry(
            container, textvariable=variable, font=self._fonts['input'],
            fg=self.COLORS['text_primary'], bg=self.COLORS['input_bg'],
            insertbackground=self.COLORS['text_primary'], relief='flat',
            justify='right', show='•' if is_password else ''
        )
        entry.pack(side='right', fill='both', expand=True, padx=(10, 5), pady=10)
        
        if is_password:
            self.password_entry = entry
            self.toggle_btn = tk.Label(
                container, text="👁", font=('Segoe UI Emoji', 12),
                fg=self.COLORS['text_muted'], bg=self.COLORS['input_bg'], cursor='hand2'
            )
            self.toggle_btn.pack(side='left', padx=(10, 0), pady=10)
            self.toggle_btn.bind('<Button-1>', lambda e: self._toggle_password())
            self.toggle_btn.bind('<Enter>', lambda e: self.toggle_btn.configure(fg=self.COLORS['primary']))
            self.toggle_btn.bind('<Leave>', lambda e: self.toggle_btn.configure(fg=self.COLORS['text_muted']))
        else:
            self.username_entry = entry
            entry.focus_set()

    def _create_checkbox(self, x, y):
        """Create remember me checkbox."""
        frame = tk.Frame(self.root, bg=self.COLORS['card_bg'])
        frame.place(x=x, y=y)
        
        self.cb_canvas = tk.Canvas(
            frame, width=20, height=20, bg=self.COLORS['card_bg'],
            highlightthickness=0, cursor='hand2'
        )
        self.cb_canvas.pack(side='right', padx=(8, 0))
        
        self.cb_border = self.cb_canvas.create_rectangle(
            2, 2, 18, 18, outline=self.COLORS['input_border'],
            fill=self.COLORS['input_bg'], width=2
        )
        self.cb_check = self.cb_canvas.create_text(
            10, 10, text="✓", font=('Arial', 11, 'bold'),
            fill=self.COLORS['primary'], state='hidden'
        )
        
        label = tk.Label(
            frame, text="تذكرني في المرة القادمة",
            font=self._fonts['body'], fg=self.COLORS['text_secondary'],
            bg=self.COLORS['card_bg'], cursor='hand2'
        )
        label.pack(side='right')
        
        def toggle(e=None):
            self.remember_var.set(not self.remember_var.get())
            if self.remember_var.get():
                self.cb_canvas.itemconfigure(self.cb_check, state='normal')
                self.cb_canvas.itemconfigure(self.cb_border, fill=self.COLORS['primary_light'])
            else:
                self.cb_canvas.itemconfigure(self.cb_check, state='hidden')
                self.cb_canvas.itemconfigure(self.cb_border, fill=self.COLORS['input_bg'])
        
        self.cb_canvas.bind('<Button-1>', toggle)
        label.bind('<Button-1>', toggle)

    def _create_login_button(self, x, y, width, height):
        """Create login button."""
        self.btn_canvas = tk.Canvas(
            self.root, width=width, height=height,
            bg=self.COLORS['card_bg'], highlightthickness=0, cursor='hand2'
        )
        self.btn_canvas.place(x=x, y=y)
        
        self.btn_bg = self._create_rounded_rect(
            self.btn_canvas, 0, 0, width, height, radius=10,
            fill=self.COLORS['primary'], outline=self.COLORS['primary'], width=0
        )
        self.btn_text = self.btn_canvas.create_text(
            width // 2, height // 2, text="تسجيل الدخول",
            font=self._fonts['button'], fill=self.COLORS['text_primary']
        )
        self.btn_loading = self.btn_canvas.create_text(
            width // 2, height // 2, text="جاري التحقق...",
            font=self._fonts['button'], fill=self.COLORS['text_primary'], state='hidden'
        )
        
        self.btn_canvas.bind('<Enter>', lambda e: self.btn_canvas.itemconfigure(
            self.btn_bg, fill=self.COLORS['primary_hover']) if not self._locked else None)
        self.btn_canvas.bind('<Leave>', lambda e: self.btn_canvas.itemconfigure(
            self.btn_bg, fill=self.COLORS['primary']) if not self._locked else None)
        self.btn_canvas.bind('<Button-1>', lambda e: self._login())

    def _start_animations(self):
        """Start logo animation."""
        self._animate_logo()

    def _animate_logo(self):
        """Animate logo pulse."""
        if not self._animation_running:
            return
        try:
            if not self.root.winfo_exists():
                self._animation_running = False
                return
        except Exception:
            self._animation_running = False
            return
        self._pulse_phase += 0.05
        scale = 1 + 0.02 * math.sin(self._pulse_phase)
        cx, cy = 250, 135
        size = 40 * scale
        try:
            self.canvas.coords(self.logo_outer, cx - size, cy - size, cx + size, cy + size)
            self._logo_after_id = self.root.after(50, self._animate_logo)
        except tk.TclError:
            self._animation_running = False
            return

    def _toggle_password(self):
        """Toggle password visibility."""
        self._show_password = not self._show_password
        self.password_entry.configure(show='' if self._show_password else '•')
        self.toggle_btn.configure(text='🙈' if self._show_password else '👁')

    def _set_busy(self, busy):
        """Set busy state."""
        if busy:
            self.btn_canvas.itemconfigure(self.btn_text, state='hidden')
            self.btn_canvas.itemconfigure(self.btn_loading, state='normal')
            self.username_entry.configure(state='disabled')
            self.password_entry.configure(state='disabled')
        else:
            self.btn_canvas.itemconfigure(self.btn_text, state='normal')
            self.btn_canvas.itemconfigure(self.btn_loading, state='hidden')
            self.username_entry.configure(state='normal')
            self.password_entry.configure(state='normal')

    def _lock_ui(self):
        """Lock UI after failed attempts."""
        self._locked = True
        self._set_busy(True)
        self.btn_canvas.itemconfigure(self.btn_bg, fill=self.COLORS['text_muted'])
        
        def tick(remaining):
            if remaining <= 0:
                self._locked = False
                self._failed_attempts = 0
                self.error_var.set("")
                self._set_busy(False)
                self.btn_canvas.itemconfigure(self.btn_bg, fill=self.COLORS['primary'])
                return
            self.error_var.set(f"⏳ انتظر {remaining} ثانية")
            self.root.after(1000, lambda: tick(remaining - 1))
        
        tick(self._lock_seconds)

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
                            "مدير النظام", role="admin"
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
                    self.cb_canvas.itemconfigure(self.cb_check, state='normal')
                    self.cb_canvas.itemconfigure(self.cb_border, fill=self.COLORS['primary_light'])
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
        
        self.error_var.set("")
        username = self.username_var.get().strip()
        password = self.password_var.get().strip()
        
        if not username or not password:
            self.error_var.set("⚠️ يرجى إدخال اسم المستخدم وكلمة المرور")
            return
        
        if self.db is None:
            messagebox.showerror("خطأ", "قاعدة البيانات غير متاحة")
            return
        
        try:
            self._set_busy(True)
            self.root.update()
            
            with self.db.get_connection() as conn:
                user = conn.execute(
                    "SELECT * FROM users WHERE username = ? COLLATE NOCASE AND is_active = 1 LIMIT 1",
                    (username,)
                ).fetchone()
                
                if user and self._verify_password(user, password):
                    self._save_username()
                    self.error_var.set("✓ تم تسجيل الدخول بنجاح!")
                    self.error_label.configure(fg=self.COLORS['success'])
                    self.root.update()
                    
                    user_data = dict(user)
                    user_data.pop("password", None)

                    self._open_main_after_id = self.root.after(500, lambda: self._finish_login(user_data))
                else:
                    self._failed_attempts += 1
                    remaining = self._max_attempts - self._failed_attempts
                    if remaining <= 0:
                        self._lock_ui()
                    else:
                        self.error_var.set(f"❌ بيانات خاطئة (متبقي {remaining} محاولات)")
                        self.error_label.configure(fg=self.COLORS['error'])
                    self._set_busy(False)
        except Exception as e:
            messagebox.showerror("خطأ", f"حدث خطأ: {e}")
            self._set_busy(False)

    def _finish_login(self, user_data):
        """Stop login UI and hand off to main window after mainloop exits."""
        self._next_user_data = user_data
        self._animation_running = False

        # Cancel pending after callbacks to avoid "invalid command name" after destroy
        self._cancel_all_after_callbacks()

        try:
            self.root.quit()
        except Exception:
            pass

    def run(self):
        """Run the application."""
        self.root.mainloop()

        user_data = self._next_user_data
        if not user_data:
            return

        try:
            self.root.destroy()
        except Exception:
            pass

        from main_window import MainWindow

        MainWindow(user_data).run()


if __name__ == "__main__":
    try:
        from simple_login import SimpleLoginWindow

        SimpleLoginWindow().run()
    except Exception:
        tb_text = traceback.format_exc()
        try:
            with open(_COLOR_LOG_PATH, "a", encoding="utf-8") as f:
                f.write("\n" + "=" * 80 + "\n")
                f.write(datetime.now().isoformat() + "\n")
                f.write(tb_text + "\n")
        except Exception:
            pass
        try:
            print(tb_text, file=sys.stderr)
        except Exception:
            pass
        try:
            print(tb_text)
        except Exception:
            pass
        raise