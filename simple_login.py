"""Professional login window for Gym Management System."""

from __future__ import annotations

import json
import tkinter as tk
import tkinter.font as tkfont
from pathlib import Path
from tkinter import messagebox
import math

import ttkbootstrap as tb

import config
from database import DatabaseManager


class SimpleLoginWindow:
    """Modern professional login window."""

    # Color Scheme
    LIGHT_COLORS = {
        'primary': '#2563eb',
        'primary_hover': '#1e40af',
        'primary_light': '#eff6ff',
        'secondary': '#10b981',
        'background': '#f3f4f6',
        'card_bg': '#ffffff',
        'card_border': '#e5e7eb',
        'shadow': '#cbd5e1',
        'text_primary': '#111827',
        'text_secondary': '#374151',
        'text_muted': '#6b7280',
        'input_bg': '#ffffff',
        'input_border': '#d1d5db',
        'input_focus': '#2563eb',
        'error': '#dc2626',
        'success': '#16a34a',
    }

    DARK_COLORS = {
        'primary': '#6366f1',
        'primary_hover': '#4f46e5',
        'primary_light': '#e0e7ff',
        'secondary': '#10b981',
        'background': '#0f172a',
        'card_bg': '#1e293b',
        'card_border': '#334155',
        'shadow': '#000000',
        'text_primary': '#f8fafc',
        'text_secondary': '#94a3b8',
        'text_muted': '#64748b',
        'input_bg': '#0f172a',
        'input_border': '#475569',
        'input_focus': '#6366f1',
        'error': '#ef4444',
        'success': '#22c55e',
    }

    def __init__(self, root: tb.Window | None = None):
        self.root = root if root is not None else tb.Window(themename="cosmo")
        self._install_tk_call_color_guard()
        self._current_theme = "cosmo"
        self.COLORS = dict(self.LIGHT_COLORS)
        self.root.title("نظام إدارة الصالة الرياضية")
        self._base_w = 620
        self._base_h = 760
        self.root.geometry("1100x800")
        try:
            self.root.minsize(self._base_w, self._base_h)
        except Exception:
            pass

        self.root.resizable(True, True)
        self.root.configure(bg=self.COLORS['background'])
        try:
            self.root.state("zoomed")
        except Exception:
            pass

        self.outer = tk.Frame(self.root, bg=self.COLORS['background'])
        self.outer.pack(fill='both', expand=True)

        self.container = tk.Frame(self.outer, bg=self.COLORS['background'], width=self._base_w, height=self._base_h)
        try:
            self.container.pack_propagate(False)
        except Exception:
            pass
        self.container.place(relx=0.5, rely=0.5, anchor='center')

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
        self._init_database()
        self._apply_theme_from_settings()
        self._create_widgets()
        self._load_saved_username()
        self._start_animations()

        try:
            self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        except Exception:
            pass

    def _is_dark_theme(self, theme_name: str) -> bool:
        t = (theme_name or "").strip().lower()
        return t in {"darkly", "cyborg", "superhero", "vapor"}

    def _apply_theme_from_settings(self) -> None:
        theme_name = "cosmo"
        try:
            if self.db is not None:
                v = self.db.get_settings("system.theme")
                theme_name = str(v).strip() if v is not None else theme_name
        except Exception:
            theme_name = "cosmo"

        if (theme_name or "").strip() == "":
            theme_name = "cosmo"

        self._apply_theme(theme_name, save=False, rebuild=False)

    def _apply_theme(self, theme_name: str, save: bool = False, rebuild: bool = True) -> None:
        theme_name = (theme_name or "").strip() or "cosmo"
        self._current_theme = theme_name

        try:
            self.COLORS = dict(self.DARK_COLORS if self._is_dark_theme(theme_name) else self.LIGHT_COLORS)
        except Exception:
            self.COLORS = dict(self.LIGHT_COLORS)

        try:
            tb.Style().theme_use(theme_name)
        except Exception:
            try:
                self.root.tk.call("ttk::style", "theme", "use", theme_name)
            except Exception:
                pass

        try:
            self.root.configure(bg=self.COLORS['background'])
        except Exception:
            pass

        try:
            if hasattr(self, "outer"):
                self.outer.configure(bg=self.COLORS['background'])
            if hasattr(self, "container"):
                self.container.configure(bg=self.COLORS['background'])
        except Exception:
            pass

        if save:
            try:
                if self.db is not None:
                    self.db.set_settings("system.theme", theme_name)
            except Exception:
                pass

        if not rebuild:
            return

        try:
            self._cancel_all_after_callbacks()
        except Exception:
            pass

        try:
            for w in list(self.container.winfo_children()):
                try:
                    w.destroy()
                except Exception:
                    pass
        except Exception:
            pass

        try:
            self._create_widgets()
        except Exception:
            pass

        try:
            self._animation_running = True
            self._start_animations()
        except Exception:
            pass

    def toggle_theme(self) -> None:
        new_theme = "cosmo" if self._is_dark_theme(self._current_theme) else "darkly"
        self._apply_theme(new_theme, save=True, rebuild=True)

    def _on_close(self):
        self._next_user_data = None
        self._cancel_all_after_callbacks()
        try:
            self.root.quit()
        except Exception:
            pass

    def _install_tk_call_color_guard(self):
        """Install guard to catch and log unknown color name errors."""
        # No-op: previous Tcl-level guards caused "application has been destroyed" issues.
        return

    def _setup_fonts(self):
        """Setup custom fonts."""
        try:
            families = set(tkfont.families())
        except Exception:
            families = set()

        arabic_fonts = ['Cairo', 'Tajawal', 'Segoe UI', 'Arial']
        self._font_family = next((f for f in arabic_fonts if f in families), 'Arial')

        self._fonts = {
            'title': (self._font_family, 20, 'bold'),
            'subtitle': (self._font_family, 12),
            'body': (self._font_family, 12),
            'input': (self._font_family, 13),
            'button': (self._font_family, 13, 'bold'),
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
            self.container, width=620, height=760,
            bg=self.COLORS['background'], highlightthickness=0
        )
        self.canvas.pack(fill='both', expand=True)

        self.theme_toggle_btn = tb.Button(
            self.container,
            text=("☀" if self._is_dark_theme(self._current_theme) else "🌙"),
            command=self.toggle_theme,
            bootstyle="secondary",
            width=3,
        )
        self.theme_toggle_btn.place(x=10, y=10)

        # Decorative circles
        self.canvas.create_oval(470, -50, 680, 160, outline=self.COLORS['primary'], width=2)
        self.canvas.create_oval(-50, 620, 120, 790, outline=self.COLORS['secondary'], width=2)

        # Card
        card_x, card_y = 40, 70
        card_w, card_h = 540, 620

        # Card shadow
        self.canvas.create_rectangle(
            card_x + 5, card_y + 5,
            card_x + card_w + 5, card_y + card_h + 5,
            fill=self.COLORS.get('shadow', '#000000'), outline=self.COLORS['background'], width=0
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
        form_x = card_x + 50
        form_y = card_y + 245
        form_w = card_w - 100

        # Username field
        self._create_input(form_x, form_y, form_w, "اسم المستخدم", "👤", self.username_var, False)

        # Password field
        self._create_input(form_x, form_y + 90, form_w, "كلمة المرور", "🔒", self.password_var, True)

        # Remember checkbox
        self._create_checkbox(form_x, form_y + 180)

        # Error label
        self.error_label = tk.Label(
            self.container, textvariable=self.error_var,
            font=self._fonts['small'], fg=self.COLORS['error'],
            bg=self.COLORS['card_bg'], wraplength=460
        )
        self.error_label.place(x=form_x, y=form_y + 220, width=form_w)

        # Login button
        self._create_login_button(form_x, form_y + 260, form_w, 58)

        # Footer
        self.canvas.create_text(
            310, 735, text="© 2025 Gym Management System",
            font=self._fonts['small'], fill=self.COLORS['text_muted']
        )

        # Bindings
        self.root.bind("<Return>", lambda e: self._login())
        self.root.bind("<Escape>", lambda e: self._on_close())

    def _create_input(self, x, y, width, placeholder, icon, variable, is_password):
        """Create styled input field."""
        container = tk.Frame(
            self.container, bg=self.COLORS['input_bg'],
            highlightbackground=self.COLORS['input_border'],
            highlightthickness=2, highlightcolor=self.COLORS['input_focus']
        )
        container.place(x=x, y=y, width=width, height=56)

        # Icon
        tk.Label(
            container, text=icon, font=('Segoe UI Emoji', 14),
            fg=self.COLORS['text_muted'], bg=self.COLORS['input_bg']
        ).pack(side='right', padx=(0, 12), pady=12)

        # Entry
        entry = tk.Entry(
            container, textvariable=variable, font=self._fonts['input'],
            fg=self.COLORS['text_primary'], bg=self.COLORS['input_bg'],
            insertbackground=self.COLORS['text_primary'], relief='flat',
            justify='right', show='•' if is_password else ''
        )
        entry.pack(side='right', fill='both', expand=True, padx=(12, 6), pady=12)

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
        frame = tk.Frame(self.container, bg=self.COLORS['card_bg'])
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
            self.container, width=width, height=height,
            bg=self.COLORS['card_bg'], highlightthickness=0, cursor='hand2'
        )
        self.btn_canvas.place(x=x, y=y)

        self.btn_bg = self._create_rounded_rect(
            self.btn_canvas, 0, 0, width, height, radius=10,
            fill=self.COLORS['primary'], outline=self.COLORS['primary'], width=0
        )
        self.btn_text = self.btn_canvas.create_text(
            width // 2, height // 2, text="تسجيل الدخول",
            font=self._fonts['button'], fill='#ffffff'
        )
        self.btn_loading = self.btn_canvas.create_text(
            width // 2, height // 2, text="جاري التحقق...",
            font=self._fonts['button'], fill='#ffffff', state='hidden'
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
        self._pulse_phase += 0.05
        scale = 1 + 0.02 * math.sin(self._pulse_phase)
        cx, cy = 310, 145
        size = 40 * scale
        self.canvas.coords(self.logo_outer, cx - size, cy - size, cx + size, cy + size)
        self._logo_after_id = self.root.after(50, self._animate_logo)

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

            user_data = self.db.authenticate_user(username, password)
            if user_data:
                self._save_username()
                self.error_var.set("✓ تم تسجيل الدخول بنجاح!")
                self.error_label.configure(fg=self.COLORS['success'])
                self.root.update()

                self._open_main_after_id = self.root.after(500, lambda: self._open_main(user_data))
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

    def _cancel_all_after_callbacks(self):
        """Cancel all scheduled after callbacks."""
        self._animation_running = False
        if self._logo_after_id:
            try:
                self.root.after_cancel(self._logo_after_id)
            except Exception:
                pass
            self._logo_after_id = None
        if self._open_main_after_id:
            try:
                self.root.after_cancel(self._open_main_after_id)
            except Exception:
                pass
            self._open_main_after_id = None

    def _open_main(self, user_data):
        """Open main window."""
        self._cancel_all_after_callbacks()
        try:
            self.root.withdraw()
        except Exception:
            pass

        from main_window import MainWindow

        logged_out = False
        try:
            logged_out = bool(MainWindow(user_data, master=self.root).run())
        except Exception:
            logged_out = False

        if logged_out:
            try:
                try:
                    self.password_var.set("")
                except Exception:
                    pass

                try:
                    self.error_var.set("")
                except Exception:
                    pass

                try:
                    self.error_label.configure(fg=self.COLORS['error'])
                except Exception:
                    pass

                try:
                    self._set_busy(False)
                except Exception:
                    pass

                self._animation_running = True
                self._start_animations()
                self.root.deiconify()
            except Exception:
                pass
        else:
            try:
                self.root.quit()
            except Exception:
                pass

    def run(self):
        """Run the application."""
        self.root.mainloop()


if __name__ == "__main__":
    app = SimpleLoginWindow()
    app.run()