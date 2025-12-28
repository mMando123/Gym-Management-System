from __future__ import annotations

import os
import subprocess
import sys
import time
import webbrowser
from pathlib import Path
from tkinter import messagebox
from tkinter import ttk
from typing import Any

import ttkbootstrap as tb

from database import DatabaseManager


class SmartReportsFrame(tb.Frame):
    def __init__(self, parent: ttk.Widget, db: DatabaseManager | None, user_data: dict | None = None) -> None:
        super().__init__(parent)
        self.db = db
        self.user_data = user_data or {}

        self._proc: subprocess.Popen | None = None
        self._log_fp = None
        self._url: str | None = None

        self._build_ui()

    def _build_ui(self) -> None:
        self.configure(padding=10)

        header = tb.Frame(self)
        header.pack(fill="x", pady=(0, 10))

        tb.Label(header, text="التقارير الذكية (PyGWalker)", font=("Cairo", 18, "bold"), anchor="e").pack(side="right")

        body = tb.Frame(self)
        body.pack(fill="both", expand=True)

        note = (
            "هذه الصفحة تفتح لوحة تفاعلية في المتصفح باستخدام Streamlit + PyGWalker.\n"
            "ملاحظة مهمة: تثبيت PyGWalker على Python 3.13 في Windows قد يفشل بسبب quickjs، "
            "والحل العملي هو استخدام Python 3.11/3.12 في بيئة منفصلة."
        )
        tb.Label(body, text=note, font=("Cairo", 10), justify="right", anchor="e").pack(fill="x", pady=(0, 12))

        form = tb.Labelframe(body, text="إعداد التشغيل", padding=10)
        form.pack(fill="x", pady=(0, 12))

        row1 = tb.Frame(form)
        row1.pack(fill="x", pady=4)
        tb.Label(row1, text="مسار Python (بيئة PyGWalker):", font=("Cairo", 10), anchor="e").pack(side="right")
        self.python_entry = tb.Entry(row1)
        self.python_entry.pack(side="right", fill="x", expand=True, padx=(8, 0))
        self.python_entry.insert(0, sys.executable)

        row2 = tb.Frame(form)
        row2.pack(fill="x", pady=4)
        tb.Label(row2, text="منفذ Streamlit:", font=("Cairo", 10), anchor="e").pack(side="right")
        self.port_entry = tb.Entry(row2, width=10)
        self.port_entry.pack(side="right", padx=(8, 0))
        self.port_entry.insert(0, "8501")

        btns = tb.Frame(body)
        btns.pack(fill="x", pady=(0, 12))

        tb.Button(btns, text="تشغيل وفتح", bootstyle="success", command=self.start).pack(side="right")
        tb.Button(btns, text="فتح في المتصفح", bootstyle="info", command=self.open_browser).pack(side="right", padx=6)
        tb.Button(btns, text="إيقاف", bootstyle="danger", command=self.stop).pack(side="right")

        self.status_var = tb.StringVar(value="الحالة: متوقف")
        tb.Label(body, textvariable=self.status_var, font=("Cairo", 10), anchor="e").pack(fill="x")

        self.bind("<Destroy>", lambda _e=None: self.stop())

    def _streamlit_script_path(self) -> str:
        return str(Path(__file__).resolve().parent / "smart_reports_streamlit.py")

    def start(self) -> None:
        if self._proc is not None and self._proc.poll() is None:
            self.open_browser()
            return

        if self.db is None:
            messagebox.showwarning("تنبيه", "قاعدة البيانات غير متاحة")
            return

        py = self.python_entry.get().strip() or sys.executable
        try:
            port = int(self.port_entry.get().strip() or "8501")
        except Exception:
            port = 8501

        db_path = str(getattr(self.db, "db_path", "") or "")
        if not db_path:
            try:
                import config

                db_path = str(config.get_database_path())
            except Exception:
                db_path = ""

        if not db_path:
            messagebox.showwarning("تنبيه", "تعذر تحديد مسار قاعدة البيانات")
            return

        script = self._streamlit_script_path()
        if not Path(script).exists():
            messagebox.showerror("خطأ", "ملف التقارير الذكية غير موجود")
            return

        log_path = Path(os.getenv("TEMP") or os.getcwd()) / "smart_reports_streamlit.log"
        try:
            self._log_fp = open(log_path, "w", encoding="utf-8")
        except Exception:
            self._log_fp = None

        cmd = [
            py,
            "-m",
            "streamlit",
            "run",
            script,
            "--server.port",
            str(port),
            "--server.headless",
            "true",
            "--",
            "--db-path",
            db_path,
        ]

        try:
            self._proc = subprocess.Popen(
                cmd,
                stdout=self._log_fp or subprocess.DEVNULL,
                stderr=self._log_fp or subprocess.DEVNULL,
                cwd=str(Path(__file__).resolve().parent),
            )
        except Exception as e:
            self._proc = None
            messagebox.showerror("خطأ", f"فشل تشغيل Streamlit: {e}")
            return

        self._url = f"http://localhost:{port}"
        self.status_var.set(f"الحالة: يعمل على {self._url}")

        self.after(450, self.open_browser)

        def _check_startup() -> None:
            if self._proc is None:
                return
            rc = self._proc.poll()
            if rc is None:
                return
            self.status_var.set("الحالة: توقف")
            msg = "فشل تشغيل التقارير الذكية. تحقق من تثبيت streamlit و pygwalker في نفس Python."\
                  f"\nسجل التشغيل: {log_path}"
            messagebox.showerror("خطأ", msg)

        self.after(900, _check_startup)

    def open_browser(self) -> None:
        if not self._url:
            return
        try:
            webbrowser.open(self._url)
        except Exception:
            pass

    def stop(self) -> None:
        if self._proc is None:
            self.status_var.set("الحالة: متوقف")
            return

        try:
            if self._proc.poll() is None:
                self._proc.terminate()
                t0 = time.time()
                while self._proc.poll() is None and (time.time() - t0) < 2.0:
                    time.sleep(0.05)
                if self._proc.poll() is None:
                    self._proc.kill()
        except Exception:
            pass

        self._proc = None
        self._url = None

        try:
            if self._log_fp is not None:
                self._log_fp.close()
        except Exception:
            pass
        self._log_fp = None

        self.status_var.set("الحالة: متوقف")
