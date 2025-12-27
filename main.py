"""نقطة تشغيل نظام إدارة النادي الرياضي.

هذا الملف هو نقطة الانطلاق الرئيسية لتطبيق سطح المكتب المبني باستخدام:
- Python
- Tkinter / ttk
- ttkbootstrap

يتولى:
- تجهيز المجلدات الافتراضية
- تجهيز قاعدة البيانات
- إنشاء مستخدم admin افتراضي عند أول تشغيل
- تشغيل نافذة تسجيل الدخول ثم النافذة الرئيسية
- تسجيل الأخطاء في logs/error.log
"""

from __future__ import annotations

import logging
import os
import sys
import traceback
from pathlib import Path

import ttkbootstrap as tb
from tkinter import messagebox

import config
from database import DatabaseManager


# ------------------------------------------------------------
# استيرادات مرنة حسب هيكل المشروع (views/utils) أو الملفات الحالية
# ------------------------------------------------------------

try:
    # الهيكل المطلوب في السؤال
    from views.login_window import LoginWindow as _LoginWindow  # type: ignore
    from views.main_window import MainWindow as _MainWindow  # type: ignore
except Exception:
    # الهيكل الحالي في المشروع
    from login_window import LoginWindow as _LoginWindow  # type: ignore
    from main_window import MainWindow as _MainWindow  # type: ignore

try:
    from utils import setup_arabic_font as _setup_arabic_font  # type: ignore
    from utils import create_default_directories as _create_default_directories  # type: ignore
except Exception:

    def _setup_arabic_font() -> None:
        """إعداد افتراضي للخط العربي.

        ملاحظة: في هذا المشروع يتم استخدام خط Cairo في أغلب الواجهات.
        إذا كان الخط غير متوفر على الجهاز، سيستخدم Tk خطاً افتراضياً.
        """

        return

    def _create_default_directories() -> None:
        """إنشاء المجلدات الافتراضية المطلوبة للتطبيق."""

        create_default_directories()


# ------------------------------------------------------------
# إعداد السجلات (Logs)
# ------------------------------------------------------------


def setup_logging() -> Path:
    """تهيئة نظام تسجيل الأخطاء في ملف logs/error.log."""

    logs_dir = Path(__file__).resolve().parent / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)

    log_path = logs_dir / "error.log"

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
        handlers=[
            logging.FileHandler(log_path, encoding="utf-8"),
        ],
    )

    return log_path


# ------------------------------------------------------------
# إعداد المجلدات
# ------------------------------------------------------------


def create_default_directories() -> None:
    """إنشاء المجلدات الأساسية المطلوبة.

    حسب المتطلبات:
    - database
    - assets
    - backups
    - exports
    - logs

    ملاحظة: المشروع الحالي يستخدم data/ كحاوية لملفات التطبيق.
    لذلك نقوم بإنشاء المجلدات المطلوبة دون كسر الهيكل الحالي.
    """

    base = Path(__file__).resolve().parent

    # مجلدات مطلوبة صراحةً
    (base / "database").mkdir(parents=True, exist_ok=True)
    (base / "assets").mkdir(parents=True, exist_ok=True)
    (base / "backups").mkdir(parents=True, exist_ok=True)
    (base / "exports").mkdir(parents=True, exist_ok=True)
    (base / "logs").mkdir(parents=True, exist_ok=True)

    # مجلدات المشروع الحالية (من config.py)
    try:
        config.init_directories()
    except Exception:
        pass


# ------------------------------------------------------------
# تهيئة التطبيق
# ------------------------------------------------------------


def setup_application() -> None:
    """تهيئة أولية للتطبيق.

    - إنشاء المجلدات
    - إعداد الخط العربي
    - تطبيق سمة ttkbootstrap (قدر الإمكان)
    """

    _create_default_directories()
    _setup_arabic_font()

    # ملاحظة مهمة: لا ننشئ tb.Style() هنا لأن ذلك قد ينشئ Tk root ضمني
    # قبل إنشاء نافذة التطبيق، مما يؤدي لاحقاً إلى أخطاء ttkbootstrap
    # مثل: "application has been destroyed".


def check_first_run() -> bool:
    """التحقق من أول تشغيل للتطبيق.

    يعتمد على وجود ملف قاعدة البيانات.

    Returns:
        True إذا كانت هذه أول مرة يتم فيها تشغيل البرنامج.
    """

    try:
        db_path = config.get_database_path()
        return not db_path.exists()
    except Exception:
        # في حال تعذر تحديد المسار نعتبرها ليست أول مرة لتفادي إنشاءات خاطئة
        return False


def create_default_admin(db: DatabaseManager) -> None:
    """إنشاء مستخدم admin افتراضي إذا لم يكن موجوداً.

    - username: admin
    - password: admin123

    ملاحظة: DatabaseManager في المشروع ينشئ admin افتراضياً أثناء init_default_data.
    هنا نقوم بتأكيد وجوده لتوافق المتطلبات.
    """

    try:
        with db.get_connection() as conn:
            row = conn.execute("SELECT id FROM users WHERE username = ? LIMIT 1", (config.DEFAULT_ADMIN_USERNAME,)).fetchone()
            if row is not None:
                return

        # إن لم يكن موجوداً: استخدم دالة create_user في DB
        db.create_user(config.DEFAULT_ADMIN_USERNAME, config.DEFAULT_ADMIN_PASSWORD, "مدير النظام", role="admin")
    except Exception:
        # لا نوقف التطبيق إذا فشل الإنشاء
        logging.exception("Failed to create default admin")


def _find_app_icon() -> Path | None:
    """البحث عن أيقونة التطبيق في assets/icon.ico إن وجدت."""

    base = Path(__file__).resolve().parent
    candidates = [
        base / "assets" / "icon.ico",
        base / "assets" / "icons" / "app.ico",
        base / "assets" / "app.ico",
    ]
    for p in candidates:
        if p.exists() and p.is_file():
            return p
    return None


class LoginWindowWithCallback(_LoginWindow):
    """تغليف نافذة تسجيل الدخول لتمرير المستخدم الناجح إلى main.py.

    LoginWindow الحالية تفتح MainWindow من داخلها.
    هذا التغليف يجعل التدفق كما في المتطلبات:
    - LoginWindow تُرجع بيانات المستخدم
    - main.py يفتح MainWindow
    """

    def __init__(self) -> None:
        super().__init__()
        self.logged_user: dict | None = None

    def _open_main_window(self, user: dict) -> None:  # type: ignore[override]
        self.logged_user = user


def main() -> None:
    """الدالة الرئيسية لتشغيل التطبيق."""

    log_path = setup_logging()

    try:
        setup_application()

        # تجهيز قاعدة البيانات (إنشاء الجداول إن لم تكن موجودة)
        first_run = check_first_run()

        try:
            db = DatabaseManager()
        except Exception as e:
            logging.exception("Database initialization failed")
            messagebox.showerror(
                "خطأ",
                f"فشل الاتصال بقاعدة البيانات.\n\n{e}\n\nتم تسجيل التفاصيل في:\n{log_path}",
            )
            return

        if first_run:
            create_default_admin(db)
        else:
            # لضمان وجود المستخدم الافتراضي حتى لو كانت قاعدة البيانات موجودة
            create_default_admin(db)

        # تجاوز صفحة تسجيل الدخول وفتح الشاشة الرئيسية مباشرةً
        # مع تمرير بيانات مستخدم admin الافتراضي
        try:
            with db.get_connection() as conn:
                row = conn.execute(
                    "SELECT * FROM users WHERE username = ? COLLATE NOCASE LIMIT 1",
                    (config.DEFAULT_ADMIN_USERNAME,),
                ).fetchone()

            if row is None:
                messagebox.showerror(
                    "خطأ",
                    "تعذر العثور على مستخدم المدير الافتراضي (admin).",
                )
                return

            # إذا كان الحساب معطلاً نحاول تفعيله تلقائياً لتفادي تعطّل النظام
            if int(row["is_active"] or 0) != 1:
                try:
                    db.update_user(int(row["id"]), is_active=1)
                    with db.get_connection() as conn:
                        row = conn.execute(
                            "SELECT * FROM users WHERE id = ? LIMIT 1",
                            (int(row["id"]),),
                        ).fetchone()
                except Exception:
                    messagebox.showerror(
                        "خطأ",
                        "حساب المدير معطل. يرجى تفعيله ثم إعادة تشغيل البرنامج.",
                    )
                    return

            admin_user = dict(row)
            admin_user.pop("password", None)
        except Exception as e:
            logging.exception("Failed to load default admin")
            messagebox.showerror(
                "خطأ",
                f"فشل تحميل بيانات المدير الافتراضي.\n\n{e}\n\nتم تسجيل التفاصيل في:\n{log_path}",
            )
            return

        # فتح النافذة الرئيسية وتمرير بيانات المستخدم
        try:
            app = _MainWindow(admin_user)

            # محاولة تطبيق الأيقونة على النافذة الرئيسية أيضاً
            try:
                icon = _find_app_icon()
                if icon is not None and hasattr(app, "root"):
                    app.root.iconbitmap(str(icon))
            except Exception:
                pass

            app.run()
        except Exception as e:
            logging.exception("Failed to open main window")
            messagebox.showerror(
                "خطأ",
                f"حدث خطأ أثناء تشغيل النافذة الرئيسية.\n\n{e}\n\nتم تسجيل التفاصيل في:\n{log_path}",
            )

    except Exception as e:
        # try/except شامل مع تسجيل stacktrace
        logging.exception("Unhandled exception")
        try:
            msg = f"حدث خطأ غير متوقع.\n\n{e}\n\nتم تسجيل التفاصيل في:\n{log_path}"
            messagebox.showerror("خطأ", msg)
        except Exception:
            pass


if __name__ == "__main__":
    main()
