"""ملف الدوال المساعدة المشتركة لنظام إدارة نادي رياضي.

يوفر هذا الملف مجموعة وظائف عامة تستخدم عبر النظام مثل:
- تنسيق التاريخ والوقت بالعربية
- التحقق من صحة المدخلات
- تنسيق العرض (أموال/هواتف/نصوص)
- التعامل مع الملفات والمجلدات
- التصدير إلى Excel/PDF (اختياري حسب توفر المكتبات)
- دوال الأمان (تشفير كلمات المرور/توليد كلمات مرور)
- دوال واجهة المستخدم (توسيط النافذة/رسائل)
- دوال متنوعة (حالة الاشتراك/تسجيل نشاط)

ملاحظة:
- بعض الميزات اختيارية (مثل reportlab / bcrypt / pandas / openpyxl / PIL).
  إذا لم تكن مثبتة سيتم استخدام بدائل أو سيتم رفع خطأ واضح.
"""

from __future__ import annotations

import base64
import hashlib
import html
import json
import os
import re
import secrets
import shutil
import socket
import string
import subprocess
import sys
import tempfile
import threading
import time
import webbrowser
import uuid
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import Any, Iterable, Sequence

import config

# PIL (اختياري)
try:
    from PIL import Image  # type: ignore

    PIL_AVAILABLE = True
except Exception:
    Image = None  # type: ignore
    PIL_AVAILABLE = False

# Excel (اختياري)
try:
    import pandas as pd  # type: ignore

    PANDAS_AVAILABLE = True
except Exception:
    pd = None  # type: ignore
    PANDAS_AVAILABLE = False

try:
    import openpyxl  # type: ignore

    OPENPYXL_AVAILABLE = True
except Exception:
    openpyxl = None  # type: ignore
    OPENPYXL_AVAILABLE = False

# PDF (اختياري)
try:
    from reportlab.lib import colors as rl_colors  # type: ignore
    from reportlab.lib.pagesizes import A4  # type: ignore
    from reportlab.lib.styles import getSampleStyleSheet  # type: ignore
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle  # type: ignore

    REPORTLAB_AVAILABLE = True
except Exception:
    REPORTLAB_AVAILABLE = False

# bcrypt (اختياري)
try:
    import bcrypt  # type: ignore

    BCRYPT_AVAILABLE = True
except Exception:
    bcrypt = None  # type: ignore
    BCRYPT_AVAILABLE = False


# ------------------------------------------------------------
# 1) دوال التاريخ والوقت
# ------------------------------------------------------------

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


def _to_date(value: Any) -> date:
    """تحويل قيمة إلى كائن date.

    يقبل:
    - date
    - datetime
    - نص بصيغة YYYY-MM-DD

    Raises:
        ValueError إذا تعذر التحويل.

    مثال:
        >>> _to_date('2025-01-15')
    """

    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, str):
        value = value.strip()[:10]
        return datetime.strptime(value, "%Y-%m-%d").date()
    raise ValueError("Unsupported date value")


def _to_time(value: Any) -> time:
    """تحويل قيمة إلى كائن time.

    يقبل:
    - time
    - datetime
    - نص HH:MM أو HH:MM:SS
    """

    if isinstance(value, time):
        return value
    if isinstance(value, datetime):
        return value.time()
    if isinstance(value, str):
        t = value.strip()
        for fmt in ("%H:%M", "%H:%M:%S"):
            try:
                return datetime.strptime(t, fmt).time()
            except Exception:
                continue
    raise ValueError("Unsupported time value")


def get_month_name_arabic(month_number: int) -> str:
    """إرجاع اسم الشهر بالعربية.

    Args:
        month_number: رقم الشهر (1-12)

    Returns:
        اسم الشهر بالعربية.

    مثال:
        >>> get_month_name_arabic(1)
        'يناير'
    """

    return _AR_MONTHS.get(int(month_number), "")


def format_date(value: Any, format_type: str = "full") -> str:
    """تنسيق التاريخ بالعربية.

    Args:
        value: تاريخ (date/datetime/str)
        format_type: أحد القيم:
            - full: "الأحد، 15 يناير 2025"
            - short: "15 يناير 2025"
            - numeric: "2025-01-15"

    Returns:
        نص التاريخ المنسق.

    مثال:
        >>> format_date('2025-01-15', 'numeric')
        '2025-01-15'
    """

    d = _to_date(value)

    if format_type == "numeric":
        return d.strftime("%Y-%m-%d")

    day_name = _AR_WEEKDAYS.get(d.weekday(), "")
    month_name = _AR_MONTHS.get(d.month, "")

    if format_type == "short":
        return f"{d.day} {month_name} {d.year}"

    # full
    return f"{day_name}، {d.day} {month_name} {d.year}"


def format_time(value: Any, format_24: bool = False) -> str:
    """تنسيق الوقت (12/24 ساعة).

    Args:
        value: وقت (time/datetime/str)
        format_24: إذا True يعرض 24 ساعة.

    Returns:
        الوقت كنص.

    مثال:
        >>> format_time('21:30', format_24=False)
        '09:30 م'
    """

    t = _to_time(value)
    if format_24:
        return t.strftime("%H:%M")

    h = t.hour
    m = t.minute
    suffix = "ص" if h < 12 else "م"
    h12 = h % 12
    if h12 == 0:
        h12 = 12
    return f"{h12:02d}:{m:02d} {suffix}"


def get_hijri_date(gregorian_date: Any) -> str:
    """تحويل تاريخ ميلادي إلى هجري (اختياري).

    هذه الدالة تحاول استخدام مكتبة hijri-converter إن كانت مثبتة.
    إن لم تكن متاحة ستُرجع نصاً افتراضياً.

    Args:
        gregorian_date: تاريخ ميلادي.

    Returns:
        تاريخ هجري كنص.

    مثال:
        >>> get_hijri_date('2025-01-15')
    """

    d = _to_date(gregorian_date)

    try:
        from hijri_converter import Gregorian  # type: ignore

        h = Gregorian(d.year, d.month, d.day).to_hijri()
        return f"{h.day} {h.month_name()} {h.year}"
    except Exception:
        return "(التاريخ الهجري غير متاح)"


def calculate_age(birth_date: Any) -> int:
    """حساب العمر بالسنوات من تاريخ الميلاد.

    Args:
        birth_date: تاريخ الميلاد.

    Returns:
        العمر بالسنوات (int).

    مثال:
        >>> calculate_age('2000-05-01')
        24
    """

    b = _to_date(birth_date)
    today = date.today()
    years = today.year - b.year
    if (today.month, today.day) < (b.month, b.day):
        years -= 1
    return max(0, years)


def days_between(date1: Any, date2: Any) -> int:
    """حساب الفرق بالأيام بين تاريخين.

    Args:
        date1: تاريخ 1
        date2: تاريخ 2

    Returns:
        عدد الأيام (قد يكون سالباً).

    مثال:
        >>> days_between('2025-01-01', '2025-01-10')
        9
    """

    d1 = _to_date(date1)
    d2 = _to_date(date2)
    return (d2 - d1).days


def is_date_expired(value: Any) -> bool:
    """التحقق هل التاريخ منتهي (قبل اليوم).

    Args:
        value: تاريخ.

    Returns:
        True إذا كان أقل من تاريخ اليوم.

    مثال:
        >>> is_date_expired('2020-01-01')
        True
    """

    d = _to_date(value)
    return d < date.today()


# ------------------------------------------------------------
# 2) دوال التحقق من الصحة
# ------------------------------------------------------------


def validate_phone(phone: str) -> bool:
    """التحقق من رقم هاتف سعودي بصيغة (05xxxxxxxx).

    Args:
        phone: رقم الهاتف.

    Returns:
        True إذا كان صحيحاً.

    مثال:
        >>> validate_phone('0501234567')
        True
    """

    phone = (phone or "").strip()
    return bool(re.fullmatch(r"05\d{8}", phone))


def validate_email(email: str) -> bool:
    """التحقق من صحة البريد الإلكتروني.

    Args:
        email: البريد.

    Returns:
        True إذا كان البريد صالحاً.

    مثال:
        >>> validate_email('user@example.com')
        True
    """

    email = (email or "").strip()
    if not email:
        return False
    return bool(re.fullmatch(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", email))


def validate_national_id(national_id: str) -> bool:
    """التحقق من رقم الهوية (10 أرقام).

    Args:
        national_id: رقم الهوية.

    Returns:
        True إذا كان 10 أرقام.

    مثال:
        >>> validate_national_id('1234567890')
        True
    """

    v = (national_id or "").strip()
    return bool(re.fullmatch(r"\d{10}", v))


def validate_required_fields(fields_dict: dict[str, Any]) -> list[str]:
    """التحقق من الحقول المطلوبة.

    Args:
        fields_dict: قاموس {اسم_الحقل: القيمة}

    Returns:
        قائمة بأسماء الحقول الفارغة.

    مثال:
        >>> validate_required_fields({'name': '', 'phone': '050...'})
        ['name']
    """

    missing = []
    for k, v in (fields_dict or {}).items():
        if v is None:
            missing.append(str(k))
            continue
        if isinstance(v, str) and not v.strip():
            missing.append(str(k))
            continue
    return missing


def sanitize_input(text: str) -> str:
    """تنظيف المدخلات من الأحرف/الوسوم الخطرة.

    - يزيل التحكمات غير المرغوبة
    - يقوم بـ HTML escaping

    Args:
        text: النص.

    Returns:
        نص آمن نسبيًا.

    مثال:
        >>> sanitize_input('<script>alert(1)</script>')
    """

    t = (text or "")
    # إزالة المحارف التحكمية
    t = re.sub(r"[\x00-\x08\x0B\x0C\x0E-\x1F]", "", t)
    t = html.escape(t)
    return t.strip()


# ------------------------------------------------------------
# 3) دوال التنسيق والعرض
# ------------------------------------------------------------


def get_gym_currency(db: Any | None = None, default: str = "EGP") -> str:
    try:
        if db is not None and hasattr(db, "get_settings"):
            v = db.get_settings("gym.currency")
            if v is not None and str(v).strip():
                return str(v).strip()

            v = db.get_settings("currency")
            if v is not None and str(v).strip():
                return str(v).strip()
    except Exception:
        pass
    return default


def format_money(amount: Any, db: Any | None = None, decimals: int = 0, currency: str | None = None) -> str:
    cur = (currency or "").strip() or get_gym_currency(db)
    try:
        v = float(amount)
    except Exception:
        v = 0.0
    return f"{v:,.{int(decimals)}f} {cur}".strip()


def format_currency(amount: Any, currency: str = "ريال") -> str:
    """تنسيق مبلغ مالي.

    Args:
        amount: رقم/نص.
        currency: اسم العملة.

    Returns:
        نص مثل: "1,500.00 ريال"

    مثال:
        >>> format_currency(1500)
        '1,500.00 ريال'
    """

    try:
        v = float(amount)
    except Exception:
        v = 0.0
    return f"{v:,.2f} {currency}".strip()


def format_phone_display(phone: str) -> str:
    """عرض الهاتف بشكل منسق (05X XXX XXXX).

    Args:
        phone: رقم الهاتف.

    Returns:
        النص المنسق.

    مثال:
        >>> format_phone_display('0501234567')
        '050 123 4567'
    """

    p = re.sub(r"\D", "", (phone or ""))
    if len(p) == 10 and p.startswith("05"):
        return f"{p[:3]} {p[3:6]} {p[6:]}"
    return phone


def truncate_text(text: str, max_length: int = 50) -> str:
    """اختصار نص طويل وإضافة ...

    Args:
        text: النص.
        max_length: الحد الأقصى.

    Returns:
        نص مختصر.

    مثال:
        >>> truncate_text('a'*60, 10)
        'aaaaaaa...'
    """

    t = (text or "")
    if len(t) <= max_length:
        return t
    if max_length <= 3:
        return t[:max_length]
    return t[: max_length - 3] + "..."


_AR_DIGITS_MAP = str.maketrans({
    "0": "٠",
    "1": "١",
    "2": "٢",
    "3": "٣",
    "4": "٤",
    "5": "٥",
    "6": "٦",
    "7": "٧",
    "8": "٨",
    "9": "٩",
})


def format_number_arabic(number: Any) -> str:
    """تحويل الأرقام إلى عربية عند الحاجة.

    Args:
        number: رقم أو نص.

    Returns:
        نص بالأرقام العربية.

    مثال:
        >>> format_number_arabic('2025')
        '٢٠٢٥'
    """

    return str(number).translate(_AR_DIGITS_MAP)


# ------------------------------------------------------------
# 4) دوال الملفات والمجلدات
# ------------------------------------------------------------


def create_default_directories() -> None:
    """إنشاء المجلدات الافتراضية.

    ينشئ مجلدات المشروع من config.init_directories()
    بالإضافة إلى مجلدات عامة مثل exports/logs إذا لم تكن موجودة.

    مثال:
        >>> create_default_directories()
    """

    try:
        config.init_directories()
    except Exception:
        pass

    base = Path(__file__).resolve().parent
    (base / "exports").mkdir(parents=True, exist_ok=True)
    (base / "logs").mkdir(parents=True, exist_ok=True)


def get_asset_path(filename: str) -> Path:
    """الحصول على مسار ملف داخل assets.

    Args:
        filename: اسم الملف (مثلاً "icon.ico" أو "images/logo.png")

    Returns:
        Path لمسار الملف.

    مثال:
        >>> get_asset_path('icon.ico')
    """

    filename = (filename or "").lstrip("/\\")
    return Path(getattr(config, "ASSETS_DIR", Path(__file__).resolve().parent / "assets")) / filename


def generate_unique_filename(original_name: str) -> str:
    """توليد اسم فريد للملف مع الحفاظ على الامتداد.

    Args:
        original_name: الاسم الأصلي.

    Returns:
        اسم فريد.

    مثال:
        >>> generate_unique_filename('photo.jpg')
    """

    p = Path(original_name)
    ext = p.suffix.lower()
    return f"{uuid.uuid4().hex}{ext}" if ext else uuid.uuid4().hex


def save_image(image_data: Any, filename: str, folder: str = "members") -> Path:
    """حفظ صورة داخل مجلد بيانات التطبيق.

    يقبل:
    - bytes (محتوى صورة)
    - مسار ملف (str/Path) للصورة
    - كائن PIL.Image إن كانت PIL متاحة

    Args:
        image_data: البيانات.
        filename: اسم الملف المقترح.
        folder: مجلد فرعي داخل assets/images أو data/images حسب المتاح.

    Returns:
        مسار الصورة بعد الحفظ.

    Raises:
        RuntimeError إذا لم يمكن حفظ الصورة.

    مثال:
        >>> save_image('c:/temp/a.jpg', 'member1.jpg')
    """

    create_default_directories()

    # أولوية حفظ الصور داخل assets/images/<folder> إن وجد، وإلا data/<folder>
    base_images = getattr(config, "IMAGES_DIR", None)
    if isinstance(base_images, Path):
        target_dir = base_images / folder
    else:
        target_dir = Path(getattr(config, "DATA_DIR", Path(__file__).resolve().parent / "data")) / "images" / folder

    target_dir.mkdir(parents=True, exist_ok=True)

    out_name = generate_unique_filename(filename)
    out_path = target_dir / out_name

    try:
        if isinstance(image_data, (str, Path)):
            src = Path(image_data)
            if not src.exists():
                raise RuntimeError("Image file not found")
            shutil_copy2(src, out_path)
            return out_path

        if isinstance(image_data, (bytes, bytearray)):
            out_path.write_bytes(bytes(image_data))
            return out_path

        if PIL_AVAILABLE and Image is not None and hasattr(image_data, "save"):
            image_data.save(out_path)
            return out_path

        raise RuntimeError("Unsupported image_data")

    except Exception as e:
        raise RuntimeError(f"Failed to save image: {e}")


def get_file_size_formatted(filepath: str | Path) -> str:
    """إرجاع حجم ملف بشكل مقروء.

    Args:
        filepath: مسار الملف.

    Returns:
        مثل: 1.5 MB

    مثال:
        >>> get_file_size_formatted('file.zip')
    """

    p = Path(filepath)
    if not p.exists() or not p.is_file():
        return "0 B"

    size = p.stat().st_size
    units = ["B", "KB", "MB", "GB", "TB"]
    i = 0
    v = float(size)
    while v >= 1024 and i < len(units) - 1:
        v /= 1024
        i += 1
    if i == 0:
        return f"{int(v)} {units[i]}"
    return f"{v:.1f} {units[i]}"


def shutil_copy2(src: Path, dst: Path) -> None:
    """نسخ ملف مع الحفاظ على الميتاداتا (بديل بسيط لتفادي استيراد shutil في الأعلى)."""

    import shutil

    shutil.copy2(str(src), str(dst))


# ------------------------------------------------------------
# 5) دوال التقارير والتصدير
# ------------------------------------------------------------


def export_to_excel(data: Sequence[Sequence[Any]], columns: Sequence[str], filename: str) -> None:
    """تصدير بيانات إلى Excel.

    يعتمد على:
    - pandas + openpyxl (المفضل)
    - أو openpyxl فقط

    Args:
        data: صفوف البيانات.
        columns: أسماء الأعمدة.
        filename: مسار ملف xlsx.

    Example:
        >>> export_to_excel([[1,'A']], ['id','name'], 'out.xlsx')
    """

    if not filename.lower().endswith(".xlsx"):
        filename = filename + ".xlsx"

    if PANDAS_AVAILABLE and OPENPYXL_AVAILABLE:
        df = pd.DataFrame(list(data), columns=list(columns))  # type: ignore
        with pd.ExcelWriter(filename, engine="openpyxl") as writer:  # type: ignore
            df.to_excel(writer, index=False, sheet_name="Report")
        return

    if OPENPYXL_AVAILABLE:
        wb = openpyxl.Workbook()  # type: ignore
        ws = wb.active
        ws.title = "Report"
        ws.append(list(columns))
        for r in data:
            ws.append(list(r))
        wb.save(filename)
        return

    raise RuntimeError("Excel export requires pandas+openpyxl or openpyxl")


def export_to_pdf(data: Sequence[Sequence[Any]], title: str, filename: str) -> None:
    """تصدير بيانات إلى PDF باستخدام reportlab (اختياري).

    Args:
        data: البيانات.
        title: عنوان التقرير.
        filename: مسار ملف pdf.

    Example:
        >>> export_to_pdf([[1,'A']], 'My Report', 'out.pdf')
    """

    if not REPORTLAB_AVAILABLE:
        raise RuntimeError("PDF export requires reportlab")

    if not filename.lower().endswith(".pdf"):
        filename = filename + ".pdf"

    doc = SimpleDocTemplate(filename, pagesize=A4)
    styles = getSampleStyleSheet()

    elements = [Paragraph(title, styles["Title"]), Spacer(1, 12)]

    t = Table([list(r) for r in data])
    t.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), rl_colors.HexColor("#2563eb")),
                ("TEXTCOLOR", (0, 0), (-1, 0), rl_colors.white),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("GRID", (0, 0), (-1, -1), 0.5, rl_colors.grey),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [rl_colors.white, rl_colors.HexColor("#f5f5f5")]),
            ]
        )
    )

    elements.append(t)
    doc.build(elements)


def print_text_windows(text: str, filename_prefix: str = "print") -> str:
    temp_dir = os.environ.get("TEMP") or os.getcwd()
    try:
        os.makedirs(temp_dir, exist_ok=True)
    except Exception:
        pass

    fd, path = tempfile.mkstemp(prefix=f"{filename_prefix}_", suffix=".txt", dir=temp_dir, text=True)
    try:
        with os.fdopen(fd, "w", encoding="utf-8-sig", newline="\r\n") as f:
            f.write(text or "")
    except Exception:
        try:
            os.close(fd)
        except Exception:
            pass
        raise

    try:
        os.startfile(path, "print")
    except Exception:
        try:
            os.startfile(path)
        except Exception as e:
            raise RuntimeError("تعذر بدء الطباعة") from e

    return path


def open_html_windows(html_content: str, filename_prefix: str = "open") -> str:
    temp_dir = os.environ.get("TEMP") or os.getcwd()
    try:
        os.makedirs(temp_dir, exist_ok=True)
    except Exception:
        pass

    fd, path = tempfile.mkstemp(prefix=f"{filename_prefix}_", suffix=".html", dir=temp_dir, text=True)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\r\n") as f:
            f.write(html_content or "")
    except Exception:
        try:
            os.close(fd)
        except Exception:
            pass
        raise

    try:
        os.startfile(path)
    except Exception:
        try:
            webbrowser.open(f"file:///{path}")
        except Exception as e:
            raise RuntimeError("تعذر فتح الصفحة") from e

    return path


def print_html_windows(html_content: str, filename_prefix: str = "print") -> str:
    temp_dir = os.environ.get("TEMP") or os.getcwd()
    try:
        os.makedirs(temp_dir, exist_ok=True)
    except Exception:
        pass

    fd, path = tempfile.mkstemp(prefix=f"{filename_prefix}_", suffix=".html", dir=temp_dir, text=True)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\r\n") as f:
            f.write(html_content or "")
    except Exception:
        try:
            os.close(fd)
        except Exception:
            pass
        raise

    try:
        os.startfile(path, "print")
    except Exception:
        try:
            os.startfile(path)
        except Exception:
            try:
                webbrowser.open(f"file:///{path}")
            except Exception as e:
                raise RuntimeError("تعذر بدء الطباعة") from e

    return path


def generate_report_header(title: str, date_range: str | None = None) -> dict[str, str]:
    """إنشاء ترويسة تقرير.

    Args:
        title: عنوان التقرير
        date_range: فترة التقرير (اختياري)

    Returns:
        قاموس يحتوي معلومات الترويسة.

    Example:
        >>> generate_report_header('تقرير الإيرادات', '2025-01-01 إلى 2025-01-31')
    """

    return {
        "title": title,
        "generated_at": get_current_datetime(),
        "date_range": date_range or "",
        "app": getattr(config, "APP_NAME", "Gym Management System"),
        "version": getattr(config, "VERSION", "1.0.0"),
    }


def generate_barcode(data: str) -> str:
    """إنشاء باركود للعضوية وإرجاعه كنص Base64 PNG (اختياري).

    يحاول استخدام python-barcode إن كانت مثبتة.
    إذا لم تكن متاحة، سيتم إنشاء رمز مبسط عبر SHA-256.

    Args:
        data: النص المراد ترميزه.

    Returns:
        نص Base64.

    Example:
        >>> b64 = generate_barcode('GYM-2025-0001')
    """

    try:
        import io

        import barcode  # type: ignore
        from barcode.writer import ImageWriter  # type: ignore

        code128 = barcode.get("code128", data, writer=ImageWriter())
        buf = io.BytesIO()
        code128.write(buf)
        return base64.b64encode(buf.getvalue()).decode("ascii")
    except Exception:
        # بديل بسيط (ليس باركود حقيقي لكنه معرف ثابت)
        digest = hashlib.sha256(str(data).encode("utf-8")).digest()
        return base64.b64encode(digest).decode("ascii")


# ------------------------------------------------------------
# 6) دوال الأمان
# ------------------------------------------------------------


def hash_password(password: str) -> str:
    """تشفير كلمة المرور.

    - إن كانت bcrypt متاحة: تُستخدم bcrypt
    - وإلا: SHA-256 مع salt

    Args:
        password: كلمة المرور.

    Returns:
        النص المشفّر.

    Example:
        >>> hashed = hash_password('admin123')
    """

    password = password or ""

    if BCRYPT_AVAILABLE and bcrypt is not None:
        salt = bcrypt.gensalt()
        hashed = bcrypt.hashpw(password.encode("utf-8"), salt)
        return hashed.decode("utf-8")

    salt = secrets.token_hex(16)
    digest = hashlib.sha256((salt + password).encode("utf-8")).hexdigest()
    return f"sha256${salt}${digest}"


def verify_password(password: str, hashed: str) -> bool:
    """التحقق من كلمة المرور مقابل hash.

    Args:
        password: كلمة المرور المدخلة.
        hashed: القيمة المشفرة.

    Returns:
        True إذا تطابقت.

    Example:
        >>> verify_password('admin123', hash_password('admin123'))
        True
    """

    if not hashed:
        return False

    if BCRYPT_AVAILABLE and bcrypt is not None and hashed.startswith("$2"):
        try:
            return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))
        except Exception:
            return False

    if hashed.startswith("sha256$"):
        try:
            _tag, salt, digest = hashed.split("$", 2)
            check = hashlib.sha256((salt + (password or "")).encode("utf-8")).hexdigest()
            return secrets.compare_digest(check, digest)
        except Exception:
            return False

    # fallback: قد تكون قاعدة بيانات قديمة تستخدم sha256 مباشرة
    try:
        legacy = hashlib.sha256((password or "").encode("utf-8")).hexdigest()
        return secrets.compare_digest(legacy, hashed)
    except Exception:
        return False


def generate_random_password(length: int = 8) -> str:
    """توليد كلمة مرور عشوائية.

    Args:
        length: طول كلمة المرور.

    Returns:
        كلمة مرور.

    Example:
        >>> generate_random_password(10)
    """

    length = max(4, int(length))
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


def generate_member_id() -> str:
    """توليد رقم عضوية فريد بصيغة GYM-YYYY-XXXX.

    Returns:
        معرف عضوية.

    Example:
        >>> generate_member_id()
        'GYM-2025-0042'
    """

    year = date.today().year
    suffix = secrets.randbelow(10000)
    return f"GYM-{year}-{suffix:04d}"


# ------------------------------------------------------------
# 7) دوال واجهة المستخدم
# ------------------------------------------------------------


def setup_arabic_font() -> None:
    """إعداد الخط العربي للتطبيق.

    ملاحظة: Tkinter يعتمد على الخطوط المثبتة في النظام.
    هذه الدالة تحفظ مكاناً لأي إعدادات إضافية عند الحاجة.

    Example:
        >>> setup_arabic_font()
    """

    return


def center_window(window: Any, width: int, height: int) -> None:
    """توسيط نافذة على الشاشة.

    Args:
        window: نافذة Tk/Toplevel.
        width: العرض.
        height: الارتفاع.

    Example:
        >>> center_window(root, 800, 600)
    """

    try:
        window.update_idletasks()
        sw = window.winfo_screenwidth()
        sh = window.winfo_screenheight()
        x = (sw - width) // 2
        y = (sh - height) // 2
        window.geometry(f"{width}x{height}+{x}+{y}")
    except Exception:
        pass


def show_message(parent: Any, title: str, message: str, type: str = "info") -> None:
    """عرض رسالة للمستخدم.

    Args:
        parent: نافذة الأب.
        title: العنوان.
        message: النص.
        type: info/warning/error/success

    Example:
        >>> show_message(root, 'تم', 'تم الحفظ', 'success')
    """

    try:
        import tkinter.messagebox as mb

        if type == "warning":
            mb.showwarning(title, message, parent=parent)
        elif type == "error":
            mb.showerror(title, message, parent=parent)
        elif type == "success":
            mb.showinfo(title, message, parent=parent)
        else:
            mb.showinfo(title, message, parent=parent)
    except Exception:
        pass


def confirm_action(parent: Any, message: str) -> bool:
    """نافذة تأكيد (نعم/لا).

    Args:
        parent: الأب.
        message: رسالة التأكيد.

    Returns:
        True إذا وافق المستخدم.

    Example:
        >>> if confirm_action(root, 'هل أنت متأكد؟'):
        ...     pass
    """

    try:
        import tkinter.messagebox as mb

        return bool(mb.askyesno("تأكيد", message, parent=parent))
    except Exception:
        return False


# ------------------------------------------------------------
# 8) دوال متنوعة
# ------------------------------------------------------------


def get_current_datetime() -> str:
    """الوقت الحالي منسق كنص.

    Returns:
        نص بصيغة config.DATETIME_FORMAT.

    Example:
        >>> get_current_datetime()
    """

    return datetime.now().strftime(getattr(config, "DATETIME_FORMAT", "%Y-%m-%d %H:%M:%S"))


def calculate_subscription_end(start_date: Any, duration_months: int) -> str:
    """حساب تاريخ انتهاء الاشتراك.

    Args:
        start_date: تاريخ البداية.
        duration_months: مدة الاشتراك بالأشهر.

    Returns:
        تاريخ الانتهاء بصيغة YYYY-MM-DD.

    Example:
        >>> calculate_subscription_end('2025-01-01', 1)
        '2025-02-01'
    """

    d = _to_date(start_date)
    months = int(duration_months)

    # إضافة أشهر بطريقة آمنة بدون مكتبات خارجية
    y = d.year + (d.month - 1 + months) // 12
    m = (d.month - 1 + months) % 12 + 1

    # محاولة المحافظة على نفس اليوم (مع ضبط إذا تجاوز آخر يوم في الشهر)
    day = d.day
    last_day = _last_day_of_month(y, m)
    day = min(day, last_day)

    return date(y, m, day).strftime("%Y-%m-%d")


def _last_day_of_month(y: int, m: int) -> int:
    if m == 12:
        nxt = date(y + 1, 1, 1)
    else:
        nxt = date(y, m + 1, 1)
    return (nxt - timedelta(days=1)).day


def get_subscription_status(end_date: Any) -> str:
    """تحديد حالة الاشتراك بناءً على تاريخ الانتهاء.

    الحالات:
    - نشط
    - منتهي
    - ينتهي قريباً (خلال 7 أيام)

    Args:
        end_date: تاريخ الانتهاء.

    Returns:
        نص الحالة.

    Example:
        >>> get_subscription_status('2020-01-01')
        'منتهي'
    """

    d = _to_date(end_date)
    today = date.today()

    if d < today:
        return "منتهي"

    if d <= today + timedelta(days=7):
        return "ينتهي قريباً"

    return "نشط"


def log_activity(user_id: int | None, action: str, details: str) -> None:
    """تسجيل نشاط المستخدم في ملف محلي.

    هذه الدالة لا تعتمد على قاعدة البيانات حتى تعمل في كل الحالات.

    Args:
        user_id: رقم المستخدم (اختياري).
        action: نوع العملية.
        details: تفاصيل.

    Example:
        >>> log_activity(1, 'login', 'User logged in')
    """

    base = Path(__file__).resolve().parent
    logs_dir = base / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)

    path = logs_dir / "activity.log"
    ts = get_current_datetime()
    uid = "-" if user_id is None else str(user_id)

    try:
        with open(path, "a", encoding="utf-8") as f:
            f.write(f"{ts} | user={uid} | {action} | {details}\n")
    except Exception:
        pass
