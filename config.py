"""Application configuration for Gym Management System.

This module centralizes:
- Application UI settings
- Filesystem paths
- Database configuration
- Lookup tables (subscription types, statuses, etc.)

All paths are based on the application root directory and are created on demand.
"""

from __future__ import annotations

from pathlib import Path

# ------------------------------
# Application Settings
# ------------------------------

APP_NAME: str = "نظام إدارة الصالة الرياضية"
APP_NAME_EN: str = "Gym Management System"
VERSION: str = "1.0.0"

WINDOW_WIDTH: int = 1200
WINDOW_HEIGHT: int = 700
MIN_WINDOW_WIDTH: int = 1000
MIN_WINDOW_HEIGHT: int = 600

# ------------------------------
# Paths Configuration
# ------------------------------

# Application root directory (the directory containing this file).
BASE_DIR: Path = Path(__file__).resolve().parent

# Data directory (for database and backups).
DATA_DIR: Path = BASE_DIR / "data"

# Assets directories (for images, icons, styles).
ASSETS_DIR: Path = BASE_DIR / "assets"
IMAGES_DIR: Path = ASSETS_DIR / "images"
ICONS_DIR: Path = ASSETS_DIR / "icons"
STYLES_DIR: Path = ASSETS_DIR / "styles"

# Backup directory (under data to keep app-generated data in one place).
BACKUPS_DIR: Path = DATA_DIR / "backups"

# ------------------------------
# Database Settings (SQLite)
# ------------------------------

DATABASE_NAME: str = "gym_database.db"
DATABASE_PATH: Path = DATA_DIR / DATABASE_NAME

# ------------------------------
# Subscription Types
# ------------------------------

SUBSCRIPTION_TYPES: list[dict[str, object]] = [
    {
        "id": "monthly",
        "name_ar": "شهري",
        "name_en": "Monthly",
        "duration_months": 1,
        "price": 200,
    },
    {
        "id": "quarterly",
        "name_ar": "ربع سنوي",
        "name_en": "Quarterly",
        "duration_months": 3,
        "price": 500,
    },
    {
        "id": "semi_annual",
        "name_ar": "نصف سنوي",
        "name_en": "Semi-Annual",
        "duration_months": 6,
        "price": 900,
    },
    {
        "id": "annual",
        "name_ar": "سنوي",
        "name_en": "Annual",
        "duration_months": 12,
        "price": 1500,
    },
]

# ------------------------------
# Theme Colors
# ------------------------------

THEME_COLORS: dict[str, str] = {
    "primary": "#2563eb",
    "secondary": "#64748b",
    "success": "#22c55e",
    "danger": "#ef4444",
    "warning": "#f59e0b",
    "background": "#f8fafc",
    "sidebar": "#1e293b",
    "text_primary": "#1e293b",
    "text_secondary": "#64748b",
}

# ------------------------------
# Payment Methods
# ------------------------------

PAYMENT_METHODS: dict[str, str] = {
    "cash": "نقدي",
    "card": "بطاقة",
    "transfer": "تحويل بنكي",
    "cheque": "شيك",
}

# ------------------------------
# Member Status
# ------------------------------

MEMBER_STATUS: dict[str, str] = {
    "active": "نشط",
    "inactive": "غير نشط",
    "frozen": "مجمد",
}

# ------------------------------
# Subscription Status
# ------------------------------

SUBSCRIPTION_STATUS: dict[str, str] = {
    "active": "نشط",
    "expired": "منتهي",
    "frozen": "مجمد",
    "cancelled": "ملغي",
}

# ------------------------------
# Gender Options
# ------------------------------

GENDER_OPTIONS: dict[str, str] = {
    "male": "ذكر",
    "female": "أنثى",
}

# ------------------------------
# Date Format
# ------------------------------

DATE_FORMAT: str = "%Y-%m-%d"
DATETIME_FORMAT: str = "%Y-%m-%d %H:%M:%S"
DISPLAY_DATE_FORMAT: str = "%d/%m/%Y"

# ------------------------------
# Backup Settings
# ------------------------------

AUTO_BACKUP: bool = True
BACKUP_RETENTION_DAYS: int = 30
MAX_BACKUPS: int = 10

# ------------------------------
# Default Admin User
# ------------------------------

DEFAULT_ADMIN_USERNAME: str = "admin"
DEFAULT_ADMIN_PASSWORD: str = "admin123"


def init_directories() -> None:
    """Create all necessary application directories.

    This function is safe to call multiple times.
    """

    # Core data directories
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    BACKUPS_DIR.mkdir(parents=True, exist_ok=True)

    # Asset directories
    ASSETS_DIR.mkdir(parents=True, exist_ok=True)
    IMAGES_DIR.mkdir(parents=True, exist_ok=True)
    ICONS_DIR.mkdir(parents=True, exist_ok=True)
    STYLES_DIR.mkdir(parents=True, exist_ok=True)


def get_database_path() -> Path:
    """Return the full path to the SQLite database file.

    Ensures that the data directory exists before returning the path.
    """

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    return DATABASE_PATH
