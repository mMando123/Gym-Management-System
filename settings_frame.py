from __future__ import annotations

import json
import os
import platform
import shutil
import sys
import zipfile
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox
import tkinter as tk
from tkinter import ttk

import ttkbootstrap as tb
from ttkbootstrap.constants import *  # noqa: F403

try:
    from ttkbootstrap.toast import ToastNotification  # type: ignore

    HAS_TOAST = True
except Exception:
    ToastNotification = None  # type: ignore
    HAS_TOAST = False

import config
from database import DatabaseManager
from settings_manager import SettingsManager


def _safe_get_dict(module_attr, fallback: dict):
    if isinstance(module_attr, dict):
        return module_attr
    return fallback


COLORS = _safe_get_dict(getattr(config, "COLORS", None), {
    "primary": "#2563eb",
    "secondary": "#64748b",
    "success": "#059669",
    "warning": "#d97706",
    "danger": "#dc2626",
    "background": "#f8fafc",
    "text": "#1e293b",
    "text_light": "#64748b",
    "white": "#ffffff",
})

FONTS = _safe_get_dict(getattr(config, "FONTS", None), {
    "heading": ("Cairo", 18, "bold"),
    "subheading": ("Cairo", 14, "bold"),
    "body": ("Cairo", 12),
    "small": ("Cairo", 10),
})


class SettingsFrame(tb.Frame):
    def __init__(self, parent: ttk.Widget, db: DatabaseManager | None, user_data: dict | None = None):
        super().__init__(parent)
        self.db = db
        self.user_data = user_data or {}
        self.settings = SettingsManager(db) if db else None
        if self.settings:
            try:
                self.settings.preload()
            except Exception:
                pass

        self.configure(padding=10)
        self._build()

    def _build(self) -> None:
        header = tb.Frame(self)
        header.pack(fill="x", pady=(0, 10))

        tb.Label(header, text="⚙️ الإعدادات", font=FONTS["heading"], anchor="e").pack(side="right")

        actions = tb.Frame(header)
        actions.pack(side="left")

        tb.Button(actions, text="🔄 تحديث", bootstyle="secondary", command=self.reload_all).pack(side="left", padx=6)
        tb.Button(actions, text="📤 تصدير الإعدادات", bootstyle="info", command=self.export_settings).pack(side="left", padx=6)
        tb.Button(actions, text="📥 استيراد الإعدادات", bootstyle="info", command=self.import_settings).pack(side="left")

        self.notebook = tb.Notebook(self, bootstyle="primary")
        self.notebook.pack(fill="both", expand=True)

        self.tab_gym = GymSettingsTab(self.notebook, self.db, self.settings, self.user_data)
        self.notebook.add(self.tab_gym, text="إعدادات النادي")

        self.tab_system = SystemSettingsTab(self.notebook, self.db, self.settings, self.user_data)
        self.notebook.add(self.tab_system, text="إعدادات النظام")

        if self._is_admin():
            self.tab_users = UsersManagementTab(self.notebook, self.db, self.settings, self.user_data)
            self.notebook.add(self.tab_users, text="إدارة المستخدمين")
        else:
            self.tab_users = None

        self.tab_notifications = NotificationsTab(self.notebook, self.db, self.settings, self.user_data)
        self.notebook.add(self.tab_notifications, text="الإشعارات")

        self.tab_backup = BackupTab(self.notebook, self.db, self.settings, self.user_data)
        self.notebook.add(self.tab_backup, text="النسخ الاحتياطي")

        self.tab_about = AboutTab(self.notebook, self.db, self.settings, self.user_data)
        self.notebook.add(self.tab_about, text="حول")

    def _is_admin(self) -> bool:
        role = str(self.user_data.get("role") or "").lower()
        username = str(self.user_data.get("username") or "").lower()
        return role in {"admin", "manager", "system_admin"} or username == "admin"

    def reload_all(self) -> None:
        if self.settings:
            try:
                self.settings.preload()
            except Exception:
                pass

        for tab in [self.tab_gym, self.tab_system, self.tab_notifications, self.tab_backup, self.tab_about, self.tab_users]:
            if tab is None:
                continue
            try:
                tab.load()
            except Exception:
                pass

    def export_settings(self) -> None:
        if not self.settings:
            messagebox.showwarning("تنبيه", "قاعدة البيانات غير جاهزة")
            return

        path = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON", "*.json")],
            title="تصدير الإعدادات",
        )
        if not path:
            return
        try:
            self.settings.export_settings(path)
            messagebox.showinfo("تم", f"تم تصدير الإعدادات إلى:\n{path}")
        except Exception as e:
            messagebox.showerror("خطأ", f"فشل التصدير:\n{e}")

    def import_settings(self) -> None:
        if not self.settings:
            messagebox.showwarning("تنبيه", "قاعدة البيانات غير جاهزة")
            return

        path = filedialog.askopenfilename(
            filetypes=[("JSON", "*.json"), ("All files", "*.*")],
            title="استيراد الإعدادات",
        )
        if not path:
            return

        if not messagebox.askyesno("تأكيد", "سيتم استيراد إعدادات جديدة وقد تؤثر على النظام. هل تريد المتابعة؟"):
            return

        try:
            changed_by = self.user_data.get("id")
            self.settings.import_settings(path, changed_by=changed_by if isinstance(changed_by, int) else None)
            self.reload_all()
            messagebox.showinfo("تم", "تم استيراد الإعدادات")
        except Exception as e:
            messagebox.showerror("خطأ", f"فشل الاستيراد:\n{e}")


class BaseSettingsTab(tb.Frame):
    def __init__(self, parent: ttk.Widget, db: DatabaseManager | None, settings: SettingsManager | None, user_data: dict):
        super().__init__(parent)
        self.db = db
        self.settings = settings
        self.user_data = user_data

    def _notify_saved(self, msg: str) -> None:
        try:
            top = self.winfo_toplevel()
            top.event_generate("<<SettingsChanged>>", when="tail")
        except Exception:
            pass

        if HAS_TOAST and ToastNotification is not None:
            try:
                toast = ToastNotification(
                    title="تم",
                    message=msg,
                    duration=2500,
                    bootstyle="success",
                    position=(30, 30, "se"),
                )
                toast.show_toast()
                return
            except Exception:
                pass

        messagebox.showinfo("تم", msg)

    def load(self) -> None:
        return


class GymSettingsTab(BaseSettingsTab):
    def __init__(self, parent: ttk.Widget, db: DatabaseManager | None, settings: SettingsManager | None, user_data: dict):
        super().__init__(parent, db, settings, user_data)

        self.var_name = tk.StringVar(master=self)
        self.var_address = tk.StringVar(master=self)
        self.var_phone = tk.StringVar(master=self)
        self.var_email = tk.StringVar(master=self)
        self.var_website = tk.StringVar(master=self)
        self.var_opening = tk.StringVar(master=self)
        self.var_closing = tk.StringVar(master=self)
        self.var_currency = tk.StringVar(master=self)
        self.var_tax_rate = tk.StringVar(master=self)
        self.var_tax_enabled = tk.BooleanVar(master=self)
        self.var_grace = tk.StringVar(master=self)
        self.var_logo = tk.StringVar(master=self)

        self.day_vars = {
            "sat": tk.BooleanVar(master=self),
            "sun": tk.BooleanVar(master=self),
            "mon": tk.BooleanVar(master=self),
            "tue": tk.BooleanVar(master=self),
            "wed": tk.BooleanVar(master=self),
            "thu": tk.BooleanVar(master=self),
            "fri": tk.BooleanVar(master=self),
        }

        self._logo_img = None

        self._build()
        self.load()

    def _build(self) -> None:
        container = tb.Frame(self, padding=12)
        container.pack(fill="both", expand=True)

        tb.Label(container, text="⚙️ إعدادات النادي", font=FONTS["subheading"], anchor="e").pack(fill="x")

        top = tb.Frame(container)
        top.pack(fill="x", pady=10)

        logo_box = tb.Labelframe(top, text="شعار النادي", padding=10)
        logo_box.pack(side="right", padx=(0, 10))

        self.logo_label = tb.Label(logo_box, text="(150x150)", width=18, anchor="center")
        self.logo_label.pack(pady=(0, 8))

        tb.Button(logo_box, text="تغيير الشعار", bootstyle="secondary", command=self.change_logo).pack(fill="x")

        form = tb.Labelframe(top, text="بيانات النادي", padding=10)
        form.pack(side="left", fill="both", expand=True)

        self._row_entry(form, "اسم النادي", self.var_name)
        self._row_entry(form, "العنوان", self.var_address)
        self._row_entry(form, "الهاتف", self.var_phone)
        self._row_entry(form, "البريد", self.var_email)
        self._row_entry(form, "الموقع", self.var_website)

        extra = tb.Labelframe(container, text="معلومات إضافية", padding=10)
        extra.pack(fill="both", expand=False)

        tb.Label(extra, text="وصف النادي", font=("Cairo", 10, "bold"), anchor="e").pack(anchor="e")
        self.txt_description = tk.Text(extra, height=5, wrap="word")
        self.txt_description.pack(fill="x", pady=(6, 0))

        hours = tb.Labelframe(container, text="أوقات العمل", padding=10)
        hours.pack(fill="x", pady=10)

        row = tb.Frame(hours)
        row.pack(fill="x")

        tb.Label(row, text="من الساعة", font=("Cairo", 10, "bold"), anchor="e").pack(side="right")
        self.cmb_open = ttk.Combobox(row, textvariable=self.var_opening, values=self._time_values(), width=10, state="readonly", justify="right")
        self.cmb_open.pack(side="right", padx=(10, 18))

        tb.Label(row, text="إلى الساعة", font=("Cairo", 10, "bold"), anchor="e").pack(side="right")
        self.cmb_close = ttk.Combobox(row, textvariable=self.var_closing, values=self._time_values(), width=10, state="readonly", justify="right")
        self.cmb_close.pack(side="right", padx=(10, 0))

        days = tb.Frame(hours)
        days.pack(fill="x", pady=(10, 0))

        tb.Label(days, text="أيام العمل", font=("Cairo", 10, "bold"), anchor="e").pack(side="right")

        days_map = [
            ("السبت", "sat"),
            ("الأحد", "sun"),
            ("الإثنين", "mon"),
            ("الثلاثاء", "tue"),
            ("الأربعاء", "wed"),
            ("الخميس", "thu"),
            ("الجمعة", "fri"),
        ]

        for label, k in days_map:
            tb.Checkbutton(days, text=label, variable=self.day_vars[k]).pack(side="right", padx=4)

        subs = tb.Labelframe(container, text="إعدادات الاشتراكات", padding=10)
        subs.pack(fill="x")

        row2 = tb.Frame(subs)
        row2.pack(fill="x", pady=4)

        tb.Label(row2, text="العملة الافتراضية", font=("Cairo", 10, "bold"), anchor="e").pack(side="right")
        self.cmb_currency = ttk.Combobox(
            row2,
            textvariable=self.var_currency,
            values=["EGP", "SAR", "AED", "USD", "EUR"],
            width=12,
            state="readonly",
            justify="right",
        )
        self.cmb_currency.pack(side="right", padx=(10, 0))

        row3 = tb.Frame(subs)
        row3.pack(fill="x", pady=4)

        tb.Label(row3, text="ضريبة القيمة المضافة", font=("Cairo", 10, "bold"), anchor="e").pack(side="right")
        tb.Entry(row3, textvariable=self.var_tax_rate, width=8, justify="right").pack(side="right", padx=(10, 0))
        tb.Label(row3, text="%", font=FONTS["small"]).pack(side="right", padx=(6, 12))
        tb.Checkbutton(row3, text="تفعيل الضريبة", variable=self.var_tax_enabled).pack(side="right")

        row4 = tb.Frame(subs)
        row4.pack(fill="x", pady=4)

        tb.Label(row4, text="فترة السماح للتجديد", font=("Cairo", 10, "bold"), anchor="e").pack(side="right")
        tb.Entry(row4, textvariable=self.var_grace, width=8, justify="right").pack(side="right", padx=(10, 0))
        tb.Label(row4, text="يوم", font=FONTS["small"]).pack(side="right")

        btns = tb.Frame(container)
        btns.pack(fill="x", pady=(12, 0))

        tb.Button(btns, text="💾 حفظ إعدادات النادي", bootstyle="success", command=self.save).pack(side="left")

    def _row_entry(self, parent: ttk.Widget, label: str, var: tk.StringVar) -> None:
        row = tb.Frame(parent)
        row.pack(fill="x", pady=6)
        tb.Label(row, text=label, font=("Cairo", 10, "bold"), anchor="e").pack(side="right")
        tb.Entry(row, textvariable=var, justify="right").pack(side="left", fill="x", expand=True)

    def _time_values(self) -> list[str]:
        vals = []
        for h in range(0, 24):
            vals.append(f"{h:02d}:00")
            vals.append(f"{h:02d}:30")
        return vals

    def load(self) -> None:
        if not self.settings:
            return

        self.var_name.set(self.settings.get("gym", "name", ""))
        self.var_logo.set(self.settings.get("gym", "logo", ""))
        self.var_address.set(self.settings.get("gym", "address", ""))
        self.var_phone.set(self.settings.get("gym", "phone", ""))
        self.var_email.set(self.settings.get("gym", "email", ""))
        self.var_website.set(self.settings.get("gym", "website", ""))
        self.var_opening.set(self.settings.get("gym", "opening_time", "06:00"))
        self.var_closing.set(self.settings.get("gym", "closing_time", "23:00"))
        self.var_currency.set(self.settings.get("gym", "currency", "EGP"))
        self.var_tax_rate.set(self.settings.get("gym", "tax_rate", "14"))
        self.var_tax_enabled.set(str(self.settings.get("gym", "tax_enabled", "0")) == "1")
        self.var_grace.set(self.settings.get("gym", "grace_period", "0"))

        desc = self.settings.get("gym", "description", "")
        self.txt_description.delete("1.0", "end")
        self.txt_description.insert("1.0", desc)

        days_raw = str(self.settings.get("gym", "working_days", "sat,sun,mon,tue,wed,thu"))
        selected = {d.strip() for d in days_raw.split(",") if d.strip()}
        for k, v in self.day_vars.items():
            v.set(k in selected)

        self._refresh_logo_preview()

    def _refresh_logo_preview(self) -> None:
        path = (self.var_logo.get() or "").strip()
        if not path:
            self.logo_label.configure(text="(150x150)", image="")
            self._logo_img = None
            return

        try:
            from PIL import Image, ImageTk

            img = Image.open(path)
            img = img.resize((150, 150))
            self._logo_img = ImageTk.PhotoImage(img)
            self.logo_label.configure(image=self._logo_img, text="")
        except Exception:
            self._logo_img = None
            self.logo_label.configure(text="(150x150)", image="")

    def change_logo(self) -> None:
        path = filedialog.askopenfilename(
            title="اختيار شعار النادي",
            filetypes=[("Images", "*.png;*.jpg;*.jpeg"), ("All files", "*.*")],
        )
        if not path:
            return

        self.var_logo.set(path)
        self._refresh_logo_preview()

    def save(self) -> None:
        if not self.settings:
            messagebox.showwarning("تنبيه", "قاعدة البيانات غير جاهزة")
            return

        if not (self.var_name.get() or "").strip():
            messagebox.showerror("خطأ", "اسم النادي مطلوب")
            return

        try:
            float(self.var_tax_rate.get() or "0")
        except Exception:
            messagebox.showerror("خطأ", "نسبة الضريبة غير صحيحة")
            return

        try:
            int(self.var_grace.get() or "0")
        except Exception:
            messagebox.showerror("خطأ", "فترة السماح غير صحيحة")
            return

        changed_by = self.user_data.get("id")
        changed_by = changed_by if isinstance(changed_by, int) else None

        days_selected = [k for k, v in self.day_vars.items() if v.get()]

        self.settings.set("gym", "name", self.var_name.get().strip(), changed_by=changed_by)
        self.settings.set("gym", "logo", self.var_logo.get().strip(), changed_by=changed_by)
        self.settings.set("gym", "address", self.var_address.get().strip(), changed_by=changed_by)
        self.settings.set("gym", "phone", self.var_phone.get().strip(), changed_by=changed_by)
        self.settings.set("gym", "email", self.var_email.get().strip(), changed_by=changed_by)
        self.settings.set("gym", "website", self.var_website.get().strip(), changed_by=changed_by)
        self.settings.set("gym", "description", self.txt_description.get("1.0", "end").strip(), changed_by=changed_by)
        self.settings.set("gym", "opening_time", self.var_opening.get().strip() or "06:00", changed_by=changed_by)
        self.settings.set("gym", "closing_time", self.var_closing.get().strip() or "23:00", changed_by=changed_by)
        self.settings.set("gym", "working_days", ",".join(days_selected), changed_by=changed_by)
        self.settings.set("gym", "currency", self.var_currency.get().strip() or "EGP", changed_by=changed_by)
        self.settings.set("gym", "tax_rate", self.var_tax_rate.get().strip() or "0", changed_by=changed_by)
        self.settings.set("gym", "tax_enabled", "1" if self.var_tax_enabled.get() else "0", changed_by=changed_by)
        self.settings.set("gym", "grace_period", self.var_grace.get().strip() or "0", changed_by=changed_by)

        self._notify_saved("تم حفظ إعدادات النادي")


class SystemSettingsTab(BaseSettingsTab):
    def __init__(self, parent: ttk.Widget, db: DatabaseManager | None, settings: SettingsManager | None, user_data: dict):
        super().__init__(parent, db, settings, user_data)

        self.var_theme = tk.StringVar(master=self)
        self.var_language = tk.StringVar(master=self)
        self.var_font_size = tk.StringVar(master=self)
        self.var_direction = tk.StringVar(master=self)

        self.var_db_path = tk.StringVar(master=self)
        self.var_images_path = tk.StringVar(master=self)
        self.var_reports_path = tk.StringVar(master=self)

        self.var_startup = tk.BooleanVar(master=self)
        self.var_minimize_tray = tk.BooleanVar(master=self)
        self.var_high_perf = tk.BooleanVar(master=self)
        self.var_records = tk.StringVar(master=self)

        self._build()
        self.load()

    def _build(self) -> None:
        container = tb.Frame(self, padding=12)
        container.pack(fill="both", expand=True)

        tb.Label(container, text="🖥️ إعدادات النظام", font=FONTS["subheading"], anchor="e").pack(fill="x")

        ui = tb.Labelframe(container, text="المظهر والواجهة", padding=10)
        ui.pack(fill="x", pady=10)

        row1 = tb.Frame(ui)
        row1.pack(fill="x", pady=6)
        tb.Label(row1, text="سمة التطبيق", font=("Cairo", 10, "bold"), anchor="e").pack(side="right")
        self.cmb_theme = ttk.Combobox(
            row1,
            textvariable=self.var_theme,
            values=["darkly", "cyborg", "vapor", "cosmo", "flatly", "journal", "superhero", "minty"],
            width=16,
            state="readonly",
            justify="right",
        )
        self.cmb_theme.pack(side="right", padx=(10, 0))
        tb.Button(row1, text="معاينة", bootstyle="secondary", command=self.preview_theme).pack(side="left")

        row2 = tb.Frame(ui)
        row2.pack(fill="x", pady=6)
        tb.Label(row2, text="اللغة", font=("Cairo", 10, "bold"), anchor="e").pack(side="right")
        ttk.Combobox(row2, textvariable=self.var_language, values=["ar", "en"], width=10, state="readonly", justify="right").pack(
            side="right", padx=(10, 0)
        )

        row3 = tb.Frame(ui)
        row3.pack(fill="x", pady=6)
        tb.Label(row3, text="حجم الخط", font=("Cairo", 10, "bold"), anchor="e").pack(side="right")
        ttk.Combobox(row3, textvariable=self.var_font_size, values=["small", "medium", "large"], width=12, state="readonly", justify="right").pack(
            side="right", padx=(10, 0)
        )

        row4 = tb.Frame(ui)
        row4.pack(fill="x", pady=6)
        tb.Label(row4, text="اتجاه الواجهة", font=("Cairo", 10, "bold"), anchor="e").pack(side="right")
        tb.Radiobutton(row4, text="RTL (يمين لليسار)", variable=self.var_direction, value="rtl").pack(side="right", padx=10)
        tb.Radiobutton(row4, text="LTR (يسار لليمين)", variable=self.var_direction, value="ltr").pack(side="right")

        paths = tb.Labelframe(container, text="إعدادات البيانات", padding=10)
        paths.pack(fill="x")

        self._path_row(paths, "مسار قاعدة البيانات", self.var_db_path, "system", "db_path")
        self._path_row(paths, "مسار حفظ الصور", self.var_images_path, "system", "images_path")
        self._path_row(paths, "مسار التقارير", self.var_reports_path, "system", "reports_path")

        perf = tb.Labelframe(container, text="الأداء", padding=10)
        perf.pack(fill="x", pady=10)

        tb.Checkbutton(perf, text="تشغيل البرنامج مع بدء Windows", variable=self.var_startup, command=self._on_startup_toggle).pack(
            anchor="e", pady=2
        )
        tb.Checkbutton(perf, text="تصغير إلى شريط المهام عند الإغلاق", variable=self.var_minimize_tray).pack(anchor="e", pady=2)
        tb.Checkbutton(perf, text="تفعيل وضع الأداء العالي", variable=self.var_high_perf).pack(anchor="e", pady=2)

        row5 = tb.Frame(perf)
        row5.pack(fill="x", pady=6)
        tb.Label(row5, text="عدد السجلات في الصفحة", font=("Cairo", 10, "bold"), anchor="e").pack(side="right")
        ttk.Combobox(row5, textvariable=self.var_records, values=["25", "50", "100", "200"], width=10, state="readonly", justify="right").pack(
            side="right", padx=(10, 0)
        )

        note = tb.Label(
            container,
            text="بعض إعدادات النظام تتطلب إعادة تشغيل التطبيق لتطبيقها بالكامل.",
            font=FONTS["small"],
            foreground=COLORS["text_light"],
            anchor="e",
        )
        note.pack(fill="x")

        btns = tb.Frame(container)
        btns.pack(fill="x", pady=(12, 0))
        tb.Button(btns, text="💾 حفظ إعدادات النظام", bootstyle="success", command=self.save).pack(side="left")

    def _path_row(self, parent: ttk.Widget, label: str, var: tk.StringVar, category: str, key: str) -> None:
        row = tb.Frame(parent)
        row.pack(fill="x", pady=6)
        tb.Label(row, text=label, font=("Cairo", 10, "bold"), anchor="e").pack(side="right")
        tb.Entry(row, textvariable=var, justify="right").pack(side="right", fill="x", expand=True, padx=(10, 10))
        tb.Button(row, text="📁", bootstyle="secondary", command=lambda: self.browse_folder(var)).pack(side="left")

    def browse_folder(self, var: tk.StringVar) -> None:
        path = filedialog.askdirectory(title="اختيار مجلد")
        if not path:
            return
        var.set(path)

    def preview_theme(self) -> None:
        self.change_theme(self.var_theme.get().strip())

    def change_theme(self, theme_name: str) -> None:
        theme_name = (theme_name or "").strip()
        if not theme_name:
            return

        try:
            master = None
            try:
                master = self.winfo_toplevel()
            except Exception:
                master = None

            if master is not None:
                style = tb.Style(master=master)
            else:
                style = tb.Style()
            style.theme_use(theme_name)
        except Exception:
            messagebox.showwarning("تنبيه", "تعذر تغيير السمة مباشرة")

    def _on_startup_toggle(self) -> None:
        self.toggle_startup(self.var_startup.get())

    def toggle_startup(self, enabled: bool) -> None:
        messagebox.showinfo(
            "تنبيه",
            "تم حفظ خيار (التشغيل مع Windows) داخل الإعدادات.\nتفعيل/إلغاء التشغيل التلقائي على Windows قد يتطلب إعداداً إضافياً حسب بيئة الجهاز.",
        )

    def load(self) -> None:
        if not self.settings:
            return

        self.var_theme.set(self.settings.get("system", "theme", "darkly"))
        self.var_language.set(self.settings.get("system", "language", "ar"))
        self.var_font_size.set(self.settings.get("system", "font_size", "medium"))
        self.var_direction.set(self.settings.get("system", "ui_direction", "rtl"))

        self.var_db_path.set(self.settings.get("system", "db_path", ""))
        self.var_images_path.set(self.settings.get("system", "images_path", ""))
        self.var_reports_path.set(self.settings.get("system", "reports_path", ""))

        self.var_startup.set(str(self.settings.get("system", "start_with_windows", "0")) == "1")
        self.var_minimize_tray.set(str(self.settings.get("system", "minimize_to_tray", "1")) == "1")
        self.var_high_perf.set(str(self.settings.get("system", "high_performance", "0")) == "1")
        self.var_records.set(self.settings.get("system", "records_per_page", "50"))

    def save(self) -> None:
        if not self.settings:
            messagebox.showwarning("تنبيه", "قاعدة البيانات غير جاهزة")
            return

        changed_by = self.user_data.get("id")
        changed_by = changed_by if isinstance(changed_by, int) else None

        self.settings.set("system", "theme", self.var_theme.get().strip() or "darkly", changed_by=changed_by)
        self.settings.set("system", "language", self.var_language.get().strip() or "ar", changed_by=changed_by)
        self.settings.set("system", "font_size", self.var_font_size.get().strip() or "medium", changed_by=changed_by)
        self.settings.set("system", "ui_direction", self.var_direction.get().strip() or "rtl", changed_by=changed_by)

        self.settings.set("system", "db_path", self.var_db_path.get().strip(), changed_by=changed_by)
        self.settings.set("system", "images_path", self.var_images_path.get().strip(), changed_by=changed_by)
        self.settings.set("system", "reports_path", self.var_reports_path.get().strip(), changed_by=changed_by)

        self.settings.set("system", "start_with_windows", "1" if self.var_startup.get() else "0", changed_by=changed_by)
        self.settings.set("system", "minimize_to_tray", "1" if self.var_minimize_tray.get() else "0", changed_by=changed_by)
        self.settings.set("system", "high_performance", "1" if self.var_high_perf.get() else "0", changed_by=changed_by)
        self.settings.set("system", "records_per_page", self.var_records.get().strip() or "50", changed_by=changed_by)

        self._notify_saved("تم حفظ إعدادات النظام")


class UsersManagementTab(BaseSettingsTab):
    def __init__(self, parent: ttk.Widget, db: DatabaseManager | None, settings: SettingsManager | None, user_data: dict):
        super().__init__(parent, db, settings, user_data)

        self.var_role = tk.StringVar(master=self, value="employee")
        self._matrix: dict[str, dict[str, int]] = {}

        self._build()
        self.load()

    def _build(self) -> None:
        container = tb.Frame(self, padding=12)
        container.pack(fill="both", expand=True)

        tb.Label(container, text="👥 إدارة المستخدمين والصلاحيات", font=FONTS["subheading"], anchor="e").pack(fill="x")

        toolbar = tb.Frame(container)
        toolbar.pack(fill="x", pady=(10, 6))

        tb.Button(toolbar, text="➕ إضافة مستخدم", bootstyle="success", command=self.add_user).pack(side="right", padx=6)
        tb.Button(toolbar, text="✏️ تعديل", bootstyle="info", command=self.edit_user).pack(side="right", padx=6)
        tb.Button(toolbar, text="🗑️ حذف", bootstyle="danger", command=self.delete_user).pack(side="right", padx=6)
        tb.Button(toolbar, text="🔄 تحديث", bootstyle="secondary", command=self.load).pack(side="left")

        table_frame = tb.Labelframe(container, text="المستخدمون", padding=10)
        table_frame.pack(fill="both", expand=True)

        cols = ("id", "username", "full_name", "role", "status", "last_login")
        self.tree = ttk.Treeview(table_frame, columns=cols, show="headings", height=10)

        headings = {
            "id": "#",
            "username": "اسم المستخدم",
            "full_name": "الاسم الكامل",
            "role": "الدور",
            "status": "الحالة",
            "last_login": "آخر دخول",
        }

        for c in cols:
            self.tree.heading(c, text=headings[c])
            self.tree.column(c, width=120, anchor="center")

        ysb = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=ysb.set)

        self.tree.pack(side="left", fill="both", expand=True)
        ysb.pack(side="right", fill="y")

        perms = tb.Labelframe(container, text="الصلاحيات حسب الدور", padding=10)
        perms.pack(fill="x", pady=10)

        row = tb.Frame(perms)
        row.pack(fill="x")
        tb.Label(row, text="الدور", font=("Cairo", 10, "bold"), anchor="e").pack(side="right")
        self.cmb_role = ttk.Combobox(
            row,
            textvariable=self.var_role,
            values=["admin", "manager", "employee", "trainer", "accountant", "reception"],
            state="readonly",
            width=16,
            justify="right",
        )
        self.cmb_role.pack(side="right", padx=(10, 0))
        self.cmb_role.bind("<<ComboboxSelected>>", lambda _e: self.load_permissions())

        self.perms_grid = tb.Frame(perms)
        self.perms_grid.pack(fill="x", pady=(10, 0))

        self._build_permissions_grid()

        btns = tb.Frame(container)
        btns.pack(fill="x", pady=(0, 0))
        tb.Button(btns, text="💾 حفظ الصلاحيات", bootstyle="success", command=self.save_permissions).pack(side="left")

    def _build_permissions_grid(self) -> None:
        for w in self.perms_grid.winfo_children():
            w.destroy()

        header = ["الصفحة", "عرض", "إضافة", "تعديل", "حذف", "طباعة"]
        for j, t in enumerate(header):
            tb.Label(self.perms_grid, text=t, font=("Cairo", 10, "bold")).grid(row=0, column=j, padx=6, pady=4, sticky="nsew")

        self._perm_vars: dict[str, dict[str, tk.IntVar]] = {}
        pages = [
            ("members", "الأعضاء"),
            ("subscriptions", "الاشتراكات"),
            ("payments", "المالية"),
            ("reports", "التقارير"),
            ("settings", "الإعدادات"),
        ]

        for i, (page_key, page_label) in enumerate(pages, start=1):
            tb.Label(self.perms_grid, text=page_label, font=FONTS["small"], anchor="e").grid(row=i, column=0, padx=6, pady=2, sticky="nsew")

            self._perm_vars[page_key] = {
                "view": tk.IntVar(master=self, value=0),
                "add": tk.IntVar(master=self, value=0),
                "edit": tk.IntVar(master=self, value=0),
                "delete": tk.IntVar(master=self, value=0),
                "print": tk.IntVar(master=self, value=0),
            }

            for j, key in enumerate(["view", "add", "edit", "delete", "print"], start=1):
                ttk.Checkbutton(self.perms_grid, variable=self._perm_vars[page_key][key]).grid(row=i, column=j, padx=8, pady=2)

        for col in range(6):
            self.perms_grid.grid_columnconfigure(col, weight=1)

    def load(self) -> None:
        if not self.settings:
            return

        self._load_users()
        self.load_permissions()

    def _load_users(self) -> None:
        for i in self.tree.get_children():
            self.tree.delete(i)

        if not self.settings:
            return

        users = self.settings.list_users()
        for idx, u in enumerate(users, start=1):
            role = str(u.get("role") or "")
            is_active = int(u.get("is_active") or 0)
            status = "🟢نشط" if is_active == 1 else "🔴معطل"
            self.tree.insert("", "end", values=(idx, u.get("username"), u.get("full_name") or "", role, status, u.get("last_login") or ""), tags=(str(u.get("id")),))

    def _selected_user_id(self) -> int | None:
        sel = self.tree.selection()
        if not sel:
            return None
        tags = self.tree.item(sel[0]).get("tags")
        if not tags:
            return None
        try:
            return int(tags[0])
        except Exception:
            return None

    def add_user(self) -> None:
        if not self.settings:
            return

        dlg = UserDialog(self.winfo_toplevel(), title="👤 إضافة مستخدم جديد")
        self.wait_window(dlg)
        if dlg.result is None:
            return

        changed_by = self.user_data.get("id")
        created_by = changed_by if isinstance(changed_by, int) else None

        ok, msg = self.settings.create_user(created_by=created_by, **dlg.result)
        if ok:
            self._load_users()
            messagebox.showinfo("تم", "تم إضافة المستخدم")
        else:
            messagebox.showerror("خطأ", f"فشل إضافة المستخدم:\n{msg}")

    def edit_user(self) -> None:
        if not self.settings:
            return

        user_id = self._selected_user_id()
        if user_id is None:
            messagebox.showwarning("تنبيه", "اختر مستخدمًا")
            return

        users = self.settings.list_users()
        current = next((u for u in users if int(u.get("id")) == user_id), None)
        if not current:
            messagebox.showerror("خطأ", "لم يتم العثور على المستخدم")
            return

        dlg = UserDialog(self.winfo_toplevel(), title="✏️ تعديل المستخدم", initial=current, edit_mode=True)
        self.wait_window(dlg)
        if dlg.result is None:
            return

        ok, msg = self.settings.update_user(user_id=user_id, **dlg.result)
        if not ok:
            messagebox.showerror("خطأ", f"فشل التعديل:\n{msg}")
            return

        if dlg.password_change:
            ok2, msg2 = self.settings.set_user_password(user_id, dlg.password_change, force_change=dlg.force_password_change)
            if not ok2:
                messagebox.showwarning("تنبيه", f"تم تعديل البيانات ولكن فشل تحديث كلمة المرور:\n{msg2}")

        self._load_users()
        messagebox.showinfo("تم", "تم تعديل المستخدم")

    def delete_user(self) -> None:
        if not self.settings:
            return

        user_id = self._selected_user_id()
        if user_id is None:
            messagebox.showwarning("تنبيه", "اختر مستخدمًا")
            return

        if not messagebox.askyesno("تأكيد", "هل تريد حذف المستخدم؟"):
            return

        ok, msg = self.settings.delete_user(user_id)
        if ok:
            self._load_users()
            messagebox.showinfo("تم", "تم حذف المستخدم")
        else:
            messagebox.showerror("خطأ", f"فشل الحذف:\n{msg}")

    def load_permissions(self) -> None:
        if not self.settings:
            return

        role = self.var_role.get().strip() or "employee"
        matrix = self.settings.get_permissions_matrix(role)

        for page, perms in matrix.items():
            if page not in self._perm_vars:
                continue
            self._perm_vars[page]["view"].set(int(perms.get("view", 0)))
            self._perm_vars[page]["add"].set(int(perms.get("add", 0)))
            self._perm_vars[page]["edit"].set(int(perms.get("edit", 0)))
            self._perm_vars[page]["delete"].set(int(perms.get("delete", 0)))
            self._perm_vars[page]["print"].set(int(perms.get("print", 0)))

    def save_permissions(self) -> None:
        if not self.settings:
            return

        role = self.var_role.get().strip() or "employee"
        matrix: dict[str, dict[str, int]] = {}

        for page, vars_ in self._perm_vars.items():
            matrix[page] = {
                "view": int(vars_["view"].get()),
                "add": int(vars_["add"].get()),
                "edit": int(vars_["edit"].get()),
                "delete": int(vars_["delete"].get()),
                "print": int(vars_["print"].get()),
            }

        self.settings.set_permissions_matrix(role, matrix)
        messagebox.showinfo("تم", "تم حفظ الصلاحيات")


class UserDialog(tb.Toplevel):
    def __init__(self, parent: tk.Misc, title: str, initial: dict | None = None, edit_mode: bool = False):
        super().__init__(parent)
        self.title(title)
        self.geometry("520x520")
        self.minsize(420, 420)
        self.resizable(True, True)
        self.grab_set()

        self.result: dict | None = None
        self.password_change: str | None = None
        self.force_password_change = False

        initial = initial or {}

        self.var_username = tk.StringVar(master=self, value=str(initial.get("username") or ""))
        self.var_full_name = tk.StringVar(master=self, value=str(initial.get("full_name") or ""))
        self.var_email = tk.StringVar(master=self, value=str(initial.get("email") or ""))
        self.var_phone = tk.StringVar(master=self, value=str(initial.get("phone") or ""))
        self.var_role = tk.StringVar(master=self, value=str(initial.get("role") or "employee"))
        self.var_active = tk.BooleanVar(master=self, value=int(initial.get("is_active") or 1) == 1)
        self.var_force = tk.BooleanVar(master=self, value=int(initial.get("force_password_change") or 0) == 1)

        self.var_password = tk.StringVar(master=self)
        self.var_password2 = tk.StringVar(master=self)
        self._show_pw = tk.BooleanVar(master=self, value=False)

        self._build(edit_mode)
        self._center()

        self.bind("<Escape>", lambda _e: self.destroy())

    def _build(self, edit_mode: bool) -> None:
        container = tb.Frame(self, padding=14)
        container.pack(fill="both", expand=True)

        def row_entry(label: str, var: tk.StringVar, show: str | None = None, state: str = "normal"):
            row = tb.Frame(container)
            row.pack(fill="x", pady=6)
            tb.Label(row, text=label, font=("Cairo", 10, "bold"), anchor="e").pack(side="right")
            ent = tb.Entry(row, textvariable=var, justify="right", show=show)
            ent.configure(state=state)
            ent.pack(side="left", fill="x", expand=True)
            return ent

        row_entry("اسم المستخدم", self.var_username, state="disabled" if edit_mode else "normal")

        pw_row = tb.Frame(container)
        pw_row.pack(fill="x", pady=6)
        tb.Label(pw_row, text="كلمة المرور", font=("Cairo", 10, "bold"), anchor="e").pack(side="right")
        self.ent_pw = tb.Entry(pw_row, textvariable=self.var_password, justify="right", show="*")
        self.ent_pw.pack(side="left", fill="x", expand=True)
        tb.Checkbutton(pw_row, text="👁️", variable=self._show_pw, command=self._toggle_pw).pack(side="left", padx=6)

        row_entry("تأكيد كلمة المرور", self.var_password2, show="*")

        row_entry("الاسم الكامل", self.var_full_name)
        row_entry("البريد الإلكتروني", self.var_email)
        row_entry("رقم الهاتف", self.var_phone)

        role_box = tb.Labelframe(container, text="الدور", padding=10)
        role_box.pack(fill="x", pady=10)

        ttk.Combobox(
            role_box,
            textvariable=self.var_role,
            values=["admin", "manager", "reception", "trainer", "accountant", "employee"],
            state="readonly",
            justify="right",
        ).pack(fill="x")

        tb.Checkbutton(container, text="الحساب نشط", variable=self.var_active).pack(anchor="e", pady=6)
        tb.Checkbutton(container, text="إجبار تغيير كلمة المرور عند أول دخول", variable=self.var_force).pack(anchor="e")

        btns = tb.Frame(container)
        btns.pack(fill="x", pady=(14, 0))
        tb.Button(btns, text="إلغاء", bootstyle="secondary", command=self.destroy).pack(side="left")
        tb.Button(btns, text="💾 حفظ", bootstyle="success", command=lambda: self._save(edit_mode)).pack(side="left", padx=6)

        hint = tb.Label(
            container,
            text="في وضع التعديل: اترك كلمة المرور فارغة إذا لا تريد تغييرها.",
            font=FONTS["small"],
            foreground=COLORS["text_light"],
            anchor="e",
        )
        hint.pack(fill="x", pady=(10, 0))

    def _toggle_pw(self) -> None:
        show = "" if self._show_pw.get() else "*"
        try:
            self.ent_pw.configure(show=show)
        except Exception:
            pass

    def _center(self) -> None:
        self.update_idletasks()
        w = self.winfo_width()
        h = self.winfo_height()
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        self.geometry(f"{w}x{h}+{(sw - w)//2}+{(sh - h)//2}")

    def _save(self, edit_mode: bool) -> None:
        username = (self.var_username.get() or "").strip()
        password = self.var_password.get() or ""
        password2 = self.var_password2.get() or ""

        if not edit_mode and not username:
            messagebox.showerror("خطأ", "اسم المستخدم مطلوب")
            return

        if password or password2:
            if password != password2:
                messagebox.showerror("خطأ", "كلمتا المرور غير متطابقتين")
                return
            if len(password) < 4:
                messagebox.showerror("خطأ", "كلمة المرور قصيرة")
                return

        self.result = {
            "username": username,
            "password": password if not edit_mode else "",
            "full_name": self.var_full_name.get().strip(),
            "email": self.var_email.get().strip(),
            "phone": self.var_phone.get().strip(),
            "role": self.var_role.get().strip() or "employee",
            "is_active": bool(self.var_active.get()),
            "force_password_change": bool(self.var_force.get()),
        }

        if edit_mode and password:
            self.password_change = password
            self.force_password_change = bool(self.var_force.get())

        if edit_mode:
            self.result.pop("username", None)
            self.result.pop("password", None)

        self.destroy()


class NotificationsTab(BaseSettingsTab):
    def __init__(self, parent: ttk.Widget, db: DatabaseManager | None, settings: SettingsManager | None, user_data: dict):
        super().__init__(parent, db, settings, user_data)

        self.var_before_enabled = tk.BooleanVar(master=self)
        self.var_days_before = tk.StringVar(master=self)
        self.var_on_expiry = tk.BooleanVar(master=self)
        self.var_after_enabled = tk.BooleanVar(master=self)
        self.var_days_after = tk.StringVar(master=self)

        self.var_debt_threshold = tk.StringVar(master=self)
        self.var_daily_finance = tk.BooleanVar(master=self)
        self.var_warn_expenses = tk.BooleanVar(master=self)
        self.var_expenses_value = tk.StringVar(master=self)

        self.var_warn_expired_entry = tk.BooleanVar(master=self)
        self.var_warn_duplicate_att = tk.BooleanVar(master=self)
        self.var_sound_att = tk.BooleanVar(master=self)

        self.var_in_app = tk.BooleanVar(master=self)
        self.var_windows = tk.BooleanVar(master=self)
        self.var_email_enabled = tk.BooleanVar(master=self)
        self.var_sms_enabled = tk.BooleanVar(master=self)

        self.var_smtp_host = tk.StringVar(master=self)
        self.var_smtp_port = tk.StringVar(master=self)
        self.var_smtp_email = tk.StringVar(master=self)
        self.var_smtp_password = tk.StringVar(master=self)

        self._build()
        self.load()

    def _build(self) -> None:
        container = tb.Frame(self, padding=12)
        container.pack(fill="both", expand=True)

        tb.Label(container, text="🔔 إعدادات الإشعارات والتنبيهات", font=FONTS["subheading"], anchor="e").pack(fill="x")

        subs = tb.Labelframe(container, text="تنبيهات الاشتراكات", padding=10)
        subs.pack(fill="x", pady=10)

        row1 = tb.Frame(subs)
        row1.pack(fill="x", pady=4)
        tb.Checkbutton(row1, text="تنبيه قبل انتهاء الاشتراك بـ", variable=self.var_before_enabled).pack(side="right")
        tb.Entry(row1, textvariable=self.var_days_before, width=6, justify="right").pack(side="right", padx=10)
        tb.Label(row1, text="أيام", font=FONTS["small"]).pack(side="right")

        tb.Checkbutton(subs, text="تنبيه يوم انتهاء الاشتراك", variable=self.var_on_expiry).pack(anchor="e", pady=4)

        row2 = tb.Frame(subs)
        row2.pack(fill="x", pady=4)
        tb.Checkbutton(row2, text="تنبيه بعد انتهاء الاشتراك بـ", variable=self.var_after_enabled).pack(side="right")
        tb.Entry(row2, textvariable=self.var_days_after, width=6, justify="right").pack(side="right", padx=10)
        tb.Label(row2, text="أيام", font=FONTS["small"]).pack(side="right")

        fin = tb.Labelframe(container, text="تنبيهات المالية", padding=10)
        fin.pack(fill="x")

        row3 = tb.Frame(fin)
        row3.pack(fill="x", pady=4)
        self.var_debt_enabled = tk.BooleanVar(master=self)
        tb.Checkbutton(row3, text="تنبيه عند وجود مديونية تتجاوز", variable=self.var_debt_enabled).pack(side="right")
        tb.Entry(row3, textvariable=self.var_debt_threshold, width=10, justify="right").pack(side="right", padx=10)
        tb.Label(row3, text="جنيه", font=FONTS["small"]).pack(side="right")

        tb.Checkbutton(fin, text="تقرير مالي يومي عند إغلاق البرنامج", variable=self.var_daily_finance).pack(anchor="e", pady=4)

        row4 = tb.Frame(fin)
        row4.pack(fill="x", pady=4)
        tb.Checkbutton(row4, text="تنبيه عند تجاوز المصروفات للحد", variable=self.var_warn_expenses).pack(side="right")
        tb.Entry(row4, textvariable=self.var_expenses_value, width=10, justify="right").pack(side="right", padx=10)
        tb.Label(row4, text="جنيه", font=FONTS["small"]).pack(side="right")

        att = tb.Labelframe(container, text="تنبيهات الحضور", padding=10)
        att.pack(fill="x", pady=10)

        tb.Checkbutton(att, text="تنبيه عند محاولة دخول عضو منتهي الاشتراك", variable=self.var_warn_expired_entry).pack(anchor="e", pady=4)
        tb.Checkbutton(att, text="تنبيه عند تكرار الحضور في نفس اليوم", variable=self.var_warn_duplicate_att).pack(anchor="e", pady=4)
        tb.Checkbutton(att, text="صوت عند تسجيل الحضور", variable=self.var_sound_att).pack(anchor="e", pady=4)

        method = tb.Labelframe(container, text="طريقة التنبيه", padding=10)
        method.pack(fill="x")

        tb.Checkbutton(method, text="إشعارات داخل التطبيق", variable=self.var_in_app).pack(anchor="e", pady=2)
        tb.Checkbutton(method, text="إشعارات Windows", variable=self.var_windows).pack(anchor="e", pady=2)
        tb.Checkbutton(method, text="إرسال بريد إلكتروني (يتطلب إعداد SMTP)", variable=self.var_email_enabled).pack(anchor="e", pady=2)
        tb.Checkbutton(method, text="إرسال رسائل SMS (يتطلب ربط API)", variable=self.var_sms_enabled).pack(anchor="e", pady=2)

        smtp = tb.Labelframe(container, text="إعدادات البريد", padding=10)
        smtp.pack(fill="x", pady=10)

        row5 = tb.Frame(smtp)
        row5.pack(fill="x", pady=4)
        tb.Label(row5, text="خادم SMTP", font=("Cairo", 10, "bold"), anchor="e").pack(side="right")
        tb.Entry(row5, textvariable=self.var_smtp_host, justify="right").pack(side="left", fill="x", expand=True)

        row6 = tb.Frame(smtp)
        row6.pack(fill="x", pady=4)
        tb.Label(row6, text="المنفذ", font=("Cairo", 10, "bold"), anchor="e").pack(side="right")
        tb.Entry(row6, textvariable=self.var_smtp_port, width=8, justify="right").pack(side="right", padx=(10, 0))
        tb.Label(row6, text="البريد", font=("Cairo", 10, "bold"), anchor="e").pack(side="right", padx=(18, 0))
        tb.Entry(row6, textvariable=self.var_smtp_email, justify="right").pack(side="left", fill="x", expand=True)

        row7 = tb.Frame(smtp)
        row7.pack(fill="x", pady=4)
        tb.Label(row7, text="كلمة المرور", font=("Cairo", 10, "bold"), anchor="e").pack(side="right")
        tb.Entry(row7, textvariable=self.var_smtp_password, justify="right", show="*").pack(side="left", fill="x", expand=True)
        tb.Button(row7, text="اختبار الاتصال", bootstyle="secondary", command=self.test_smtp).pack(side="left", padx=8)

        btns = tb.Frame(container)
        btns.pack(fill="x", pady=(12, 0))
        tb.Button(btns, text="💾 حفظ إعدادات الإشعارات", bootstyle="success", command=self.save).pack(side="left")

    def load(self) -> None:
        if not self.settings:
            return

        self.var_before_enabled.set(True)
        self.var_days_before.set(self.settings.get("notifications", "days_before_expiry", "7"))
        self.var_on_expiry.set(str(self.settings.get("notifications", "notify_on_expiry", "1")) == "1")
        self.var_after_enabled.set(True)
        self.var_days_after.set(self.settings.get("notifications", "days_after_expiry", "3"))

        self.var_debt_enabled.set(str(self.settings.get("notifications", "debt_enabled", "1")) == "1")
        self.var_debt_threshold.set(self.settings.get("notifications", "debt_threshold", "500"))
        self.var_daily_finance.set(str(self.settings.get("notifications", "daily_finance_on_exit", "1")) == "1")
        self.var_warn_expenses.set(str(self.settings.get("notifications", "warn_expenses_threshold", "0")) == "1")
        self.var_expenses_value.set(self.settings.get("notifications", "warn_expenses_value", ""))

        self.var_warn_expired_entry.set(str(self.settings.get("notifications", "warn_expired_on_entry", "1")) == "1")
        self.var_warn_duplicate_att.set(str(self.settings.get("notifications", "warn_duplicate_attendance", "1")) == "1")
        self.var_sound_att.set(str(self.settings.get("notifications", "sound_on_attendance", "0")) == "1")

        self.var_in_app.set(str(self.settings.get("notifications", "in_app", "1")) == "1")
        self.var_windows.set(str(self.settings.get("notifications", "windows", "0")) == "1")
        self.var_email_enabled.set(str(self.settings.get("notifications", "email_enabled", "0")) == "1")
        self.var_sms_enabled.set(str(self.settings.get("notifications", "sms_enabled", "0")) == "1")

        self.var_smtp_host.set(self.settings.get("notifications", "smtp_host", "smtp.gmail.com"))
        self.var_smtp_port.set(self.settings.get("notifications", "smtp_port", "587"))
        self.var_smtp_email.set(self.settings.get("notifications", "smtp_email", ""))
        self.var_smtp_password.set(self.settings.get("notifications", "smtp_password", ""))

    def save(self) -> None:
        if not self.settings:
            messagebox.showwarning("تنبيه", "قاعدة البيانات غير جاهزة")
            return

        changed_by = self.user_data.get("id")
        changed_by = changed_by if isinstance(changed_by, int) else None

        self.settings.set("notifications", "days_before_expiry", self.var_days_before.get().strip() or "7", changed_by=changed_by)
        self.settings.set("notifications", "notify_on_expiry", "1" if self.var_on_expiry.get() else "0", changed_by=changed_by)
        self.settings.set("notifications", "days_after_expiry", self.var_days_after.get().strip() or "3", changed_by=changed_by)

        self.settings.set("notifications", "debt_enabled", "1" if self.var_debt_enabled.get() else "0", changed_by=changed_by)
        self.settings.set("notifications", "debt_threshold", self.var_debt_threshold.get().strip() or "500", changed_by=changed_by)
        self.settings.set("notifications", "daily_finance_on_exit", "1" if self.var_daily_finance.get() else "0", changed_by=changed_by)
        self.settings.set("notifications", "warn_expenses_threshold", "1" if self.var_warn_expenses.get() else "0", changed_by=changed_by)
        self.settings.set("notifications", "warn_expenses_value", self.var_expenses_value.get().strip(), changed_by=changed_by)

        self.settings.set("notifications", "warn_expired_on_entry", "1" if self.var_warn_expired_entry.get() else "0", changed_by=changed_by)
        self.settings.set("notifications", "warn_duplicate_attendance", "1" if self.var_warn_duplicate_att.get() else "0", changed_by=changed_by)
        self.settings.set("notifications", "sound_on_attendance", "1" if self.var_sound_att.get() else "0", changed_by=changed_by)

        self.settings.set("notifications", "in_app", "1" if self.var_in_app.get() else "0", changed_by=changed_by)
        self.settings.set("notifications", "windows", "1" if self.var_windows.get() else "0", changed_by=changed_by)
        self.settings.set("notifications", "email_enabled", "1" if self.var_email_enabled.get() else "0", changed_by=changed_by)
        self.settings.set("notifications", "sms_enabled", "1" if self.var_sms_enabled.get() else "0", changed_by=changed_by)

        self.settings.set("notifications", "smtp_host", self.var_smtp_host.get().strip(), changed_by=changed_by)
        self.settings.set("notifications", "smtp_port", self.var_smtp_port.get().strip() or "587", changed_by=changed_by)
        self.settings.set("notifications", "smtp_email", self.var_smtp_email.get().strip(), changed_by=changed_by)
        self.settings.set("notifications", "smtp_password", self.var_smtp_password.get(), changed_by=changed_by)

        messagebox.showinfo("تم", "تم حفظ إعدادات الإشعارات")

    def test_smtp(self) -> None:
        host = (self.var_smtp_host.get() or "").strip()
        port = int(self.var_smtp_port.get() or "587")

        try:
            import smtplib

            with smtplib.SMTP(host, port, timeout=8) as s:
                s.noop()
            messagebox.showinfo("تم", "تم الاتصال بخادم SMTP بنجاح")
        except Exception as e:
            messagebox.showerror("خطأ", f"فشل الاتصال:\n{e}")


class BackupTab(BaseSettingsTab):
    def __init__(self, parent: ttk.Widget, db: DatabaseManager | None, settings: SettingsManager | None, user_data: dict):
        super().__init__(parent, db, settings, user_data)

        self.var_compress = tk.BooleanVar(master=self, value=True)
        self.var_encrypt = tk.BooleanVar(master=self, value=False)

        self.var_auto = tk.BooleanVar(master=self)
        self.var_freq = tk.StringVar(master=self)
        self.var_time = tk.StringVar(master=self)
        self.var_path = tk.StringVar(master=self)
        self.var_keep = tk.StringVar(master=self)

        self._build()
        self.load()

    def _build(self) -> None:
        container = tb.Frame(self, padding=12)
        container.pack(fill="both", expand=True)

        tb.Label(container, text="💾 النسخ الاحتياطي واستعادة البيانات", font=FONTS["subheading"], anchor="e").pack(fill="x")

        manual = tb.Labelframe(container, text="النسخ الاحتياطي اليدوي", padding=10)
        manual.pack(fill="x", pady=10)

        tb.Label(manual, text="سيتم حفظ: قاعدة البيانات + الصور + الإعدادات", font=FONTS["small"], anchor="e").pack(fill="x")

        opts = tb.Frame(manual)
        opts.pack(fill="x", pady=8)
        tb.Checkbutton(opts, text="ضغط الملفات (ZIP)", variable=self.var_compress).pack(side="right", padx=6)
        tb.Checkbutton(opts, text="تشفير النسخة الاحتياطية", variable=self.var_encrypt).pack(side="right", padx=6)

        tb.Button(manual, text="📦 إنشاء نسخة احتياطية", bootstyle="success", command=self.create_backup).pack(anchor="w")

        auto = tb.Labelframe(container, text="النسخ الاحتياطي التلقائي", padding=10)
        auto.pack(fill="x")

        tb.Checkbutton(auto, text="تفعيل النسخ الاحتياطي التلقائي", variable=self.var_auto).pack(anchor="e", pady=4)

        row = tb.Frame(auto)
        row.pack(fill="x", pady=4)
        tb.Label(row, text="التكرار", font=("Cairo", 10, "bold"), anchor="e").pack(side="right")
        ttk.Combobox(row, textvariable=self.var_freq, values=["daily", "weekly", "monthly"], state="readonly", width=14, justify="right").pack(
            side="right", padx=(10, 0)
        )
        tb.Label(row, text="الوقت", font=("Cairo", 10, "bold"), anchor="e").pack(side="right", padx=(18, 0))
        ttk.Combobox(row, textvariable=self.var_time, values=self._time_values(), state="readonly", width=10, justify="right").pack(
            side="right", padx=(10, 0)
        )

        row2 = tb.Frame(auto)
        row2.pack(fill="x", pady=4)
        tb.Label(row2, text="مسار الحفظ", font=("Cairo", 10, "bold"), anchor="e").pack(side="right")
        tb.Entry(row2, textvariable=self.var_path, justify="right").pack(side="right", fill="x", expand=True, padx=(10, 10))
        tb.Button(row2, text="📁", bootstyle="secondary", command=self.browse_backup_path).pack(side="left")

        row3 = tb.Frame(auto)
        row3.pack(fill="x", pady=4)
        tb.Label(row3, text="الاحتفاظ بآخر", font=("Cairo", 10, "bold"), anchor="e").pack(side="right")
        tb.Entry(row3, textvariable=self.var_keep, width=8, justify="right").pack(side="right", padx=(10, 0))
        tb.Label(row3, text="نسخ احتياطية", font=FONTS["small"]).pack(side="right")

        tb.Button(auto, text="💾 حفظ إعدادات النسخ الاحتياطي", bootstyle="success", command=self.save).pack(anchor="w", pady=(8, 0))

        prev = tb.Labelframe(container, text="استعادة من ملف", padding=10)
        prev.pack(fill="x", pady=10)

        tb.Button(prev, text="📁 اختر ملف النسخة الاحتياطية...", bootstyle="info", command=self.restore_backup).pack(anchor="w")
        tb.Label(prev, text="⚠️ تحذير: استعادة نسخة احتياطية ستحذف جميع البيانات الحالية", foreground=COLORS["danger"], anchor="e").pack(
            fill="x", pady=(10, 0)
        )

    def _time_values(self) -> list[str]:
        return [f"{h:02d}:00" for h in range(0, 24)]

    def load(self) -> None:
        if not self.settings:
            return

        self.var_auto.set(str(self.settings.get("backup", "auto_backup", "1")) == "1")
        self.var_freq.set(self.settings.get("backup", "backup_frequency", "daily"))
        self.var_time.set(self.settings.get("backup", "backup_time", "23:00"))
        self.var_path.set(self.settings.get("backup", "backup_path", ""))
        self.var_keep.set(self.settings.get("backup", "keep_backups", "7"))

        self.var_compress.set(str(self.settings.get("backup", "compress", "1")) == "1")
        self.var_encrypt.set(str(self.settings.get("backup", "encrypt", "0")) == "1")

    def browse_backup_path(self) -> None:
        path = filedialog.askdirectory(title="اختيار مجلد النسخ الاحتياطي")
        if not path:
            return
        self.var_path.set(path)

    def save(self) -> None:
        if not self.settings:
            return

        try:
            int(self.var_keep.get() or "7")
        except Exception:
            messagebox.showerror("خطأ", "عدد النسخ غير صحيح")
            return

        changed_by = self.user_data.get("id")
        changed_by = changed_by if isinstance(changed_by, int) else None

        self.settings.set("backup", "auto_backup", "1" if self.var_auto.get() else "0", changed_by=changed_by)
        self.settings.set("backup", "backup_frequency", self.var_freq.get().strip() or "daily", changed_by=changed_by)
        self.settings.set("backup", "backup_time", self.var_time.get().strip() or "23:00", changed_by=changed_by)
        self.settings.set("backup", "backup_path", self.var_path.get().strip(), changed_by=changed_by)
        self.settings.set("backup", "keep_backups", self.var_keep.get().strip() or "7", changed_by=changed_by)

        self.settings.set("backup", "compress", "1" if self.var_compress.get() else "0", changed_by=changed_by)
        self.settings.set("backup", "encrypt", "1" if self.var_encrypt.get() else "0", changed_by=changed_by)

        messagebox.showinfo("تم", "تم حفظ إعدادات النسخ الاحتياطي")

    def create_backup(self) -> None:
        if not self.db or not self.settings:
            messagebox.showwarning("تنبيه", "قاعدة البيانات غير جاهزة")
            return

        if self.var_encrypt.get():
            messagebox.showwarning("تنبيه", "التشفير غير مُفعّل حالياً وسيتم إنشاء نسخة بدون تشفير")

        base_dir = (self.var_path.get() or "").strip()
        if not base_dir:
            base_dir = str(getattr(config, "BACKUPS_DIR", Path.cwd()))

        os.makedirs(base_dir, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        name = f"gym_backup_{timestamp}"
        work_dir = Path(base_dir) / name

        try:
            if work_dir.exists():
                shutil.rmtree(work_dir)
            work_dir.mkdir(parents=True, exist_ok=True)

            ok, msg, backup_db_path = self.db.backup_database()
            if not ok or backup_db_path is None:
                raise RuntimeError(msg)

            shutil.copy2(str(backup_db_path), str(work_dir / "database.sqlite3"))

            images_path = self.settings.get("system", "images_path", "")
            if images_path and Path(images_path).exists():
                shutil.copytree(images_path, work_dir / "images", dirs_exist_ok=True)

            settings_path = work_dir / "settings.json"
            self.settings.export_settings(str(settings_path))

            if self.var_compress.get():
                zip_path = Path(base_dir) / f"{name}.zip"
                with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as z:
                    for p in work_dir.rglob("*"):
                        z.write(p, arcname=str(p.relative_to(work_dir)))
                shutil.rmtree(work_dir)
                messagebox.showinfo("تم", f"تم إنشاء النسخة الاحتياطية:\n{zip_path}")
            else:
                messagebox.showinfo("تم", f"تم إنشاء النسخة الاحتياطية:\n{work_dir}")

            self.cleanup_old_backups()

        except Exception as e:
            try:
                if work_dir.exists():
                    shutil.rmtree(work_dir)
            except Exception:
                pass
            messagebox.showerror("خطأ", f"فشل إنشاء النسخة الاحتياطية:\n{e}")

    def restore_backup(self) -> None:
        if not self.db:
            messagebox.showwarning("تنبيه", "قاعدة البيانات غير جاهزة")
            return

        path = filedialog.askopenfilename(
            title="اختيار ملف النسخة الاحتياطية",
            filetypes=[("Backup", "*.zip;*.sqlite3"), ("All files", "*.*")],
        )
        if not path:
            return

        if not messagebox.askyesno("تأكيد", "استعادة نسخة احتياطية ستستبدل البيانات الحالية. هل تريد المتابعة؟"):
            return

        try:
            p = Path(path)
            if p.suffix.lower() == ".zip":
                temp_dir = Path(os.environ.get("TEMP") or os.getcwd()) / f"restore_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                if temp_dir.exists():
                    shutil.rmtree(temp_dir)
                temp_dir.mkdir(parents=True, exist_ok=True)

                with zipfile.ZipFile(p, "r") as z:
                    z.extractall(temp_dir)

                db_file = temp_dir / "database.sqlite3"
                if not db_file.exists():
                    raise RuntimeError("ملف قاعدة البيانات غير موجود داخل النسخة")

                shutil.copy2(str(db_file), str(self.db.db_path))

                shutil.rmtree(temp_dir)
            else:
                shutil.copy2(str(p), str(self.db.db_path))

            messagebox.showinfo("تم", "تمت الاستعادة. يرجى إعادة تشغيل التطبيق.")

        except Exception as e:
            messagebox.showerror("خطأ", f"فشل الاستعادة:\n{e}")

    def cleanup_old_backups(self) -> None:
        try:
            keep = int(self.var_keep.get() or "7")
        except Exception:
            keep = 7

        base_dir = (self.var_path.get() or "").strip()
        if not base_dir:
            base_dir = str(getattr(config, "BACKUPS_DIR", Path.cwd()))

        try:
            p = Path(base_dir)
            if not p.exists():
                return

            zips = sorted([x for x in p.glob("gym_backup_*.zip")], key=lambda x: x.stat().st_mtime, reverse=True)
            for old in zips[keep:]:
                try:
                    old.unlink()
                except Exception:
                    pass
        except Exception:
            pass


class AboutTab(BaseSettingsTab):
    def __init__(self, parent: ttk.Widget, db: DatabaseManager | None, settings: SettingsManager | None, user_data: dict):
        super().__init__(parent, db, settings, user_data)
        self._build()
        self.load()

    def _build(self) -> None:
        container = tb.Frame(self, padding=12)
        container.pack(fill="both", expand=True)

        tb.Label(container, text="ℹ️ حول البرنامج", font=FONTS["subheading"], anchor="e").pack(fill="x")

        box = tb.Frame(container)
        box.pack(fill="x", pady=12)

        logo = tb.Label(box, text="🏋️", font=("Segoe UI Emoji", 42), anchor="center")
        logo.pack()

        tb.Label(box, text=str(getattr(config, "APP_NAME", "Gym Management System")), font=("Cairo", 16, "bold"), anchor="center").pack(
            pady=(6, 0)
        )
        tb.Label(box, text=f"الإصدار: {getattr(config, 'VERSION', '1.0.0')}", font=FONTS["body"], anchor="center").pack()

        info = tb.Labelframe(container, text="معلومات النظام", padding=10)
        info.pack(fill="x", pady=10)

        ttk.Label(info, text=f"Python Version: {sys.version.split()[0]}", anchor="e").pack(fill="x")
        ttk.Label(info, text=f"ttkbootstrap: {getattr(tb, '__version__', '-')}", anchor="e").pack(fill="x")
        ttk.Label(info, text=f"SQLite: {sqlite3_version()}", anchor="e").pack(fill="x")
        ttk.Label(info, text=f"نظام التشغيل: {platform.platform()}", anchor="e").pack(fill="x")

        db_stats = tb.Labelframe(container, text="إحصائيات قاعدة البيانات", padding=10)
        db_stats.pack(fill="x")

        self.lbl_members = ttk.Label(db_stats, text="عدد الأعضاء: -", anchor="e")
        self.lbl_subs = ttk.Label(db_stats, text="عدد الاشتراكات: -", anchor="e")
        self.lbl_size = ttk.Label(db_stats, text="حجم قاعدة البيانات: -", anchor="e")

        self.lbl_members.pack(fill="x")
        self.lbl_subs.pack(fill="x")
        self.lbl_size.pack(fill="x")

        dev = tb.Labelframe(container, text="التطوير", padding=10)
        dev.pack(fill="x", pady=10)

        ttk.Label(dev, text="تم التطوير بواسطة: (يمكن تخصيصه)", anchor="e").pack(fill="x")
        ttk.Label(dev, text="البريد: developer@email.com", anchor="e").pack(fill="x")
        ttk.Label(dev, text="الموقع: www.example.com", anchor="e").pack(fill="x")

    def load(self) -> None:
        if not self.db:
            return

        try:
            with self.db.get_connection() as conn:
                members = conn.execute("SELECT COUNT(*) AS c FROM members").fetchone()["c"]
                subs = conn.execute("SELECT COUNT(*) AS c FROM subscriptions").fetchone()["c"]

            self.lbl_members.configure(text=f"عدد الأعضاء: {int(members)}")
            self.lbl_subs.configure(text=f"عدد الاشتراكات: {int(subs)}")

            try:
                size = Path(self.db.db_path).stat().st_size
                self.lbl_size.configure(text=f"حجم قاعدة البيانات: {size/1024/1024:.1f} MB")
            except Exception:
                pass
        except Exception:
            pass


def sqlite3_version() -> str:
    try:
        import sqlite3

        return sqlite3.sqlite_version
    except Exception:
        return "-"


if __name__ == "__main__":
    root = tb.Window(themename="cosmo")
    root.title("SettingsFrame Test")
    db = DatabaseManager()
    frame = SettingsFrame(root, db, {"username": "admin", "role": "admin", "id": 1})
    frame.pack(fill="both", expand=True)
    root.geometry("1200x720")
    root.mainloop()
