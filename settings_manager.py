from __future__ import annotations

import json
import os
import secrets
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

import config
from database import DatabaseManager


def _now_dt_str() -> str:
    return datetime.now().strftime(config.DATETIME_FORMAT)


class SettingsManager:
    """Settings manager (DB-backed) with caching and change logging."""

    def __init__(self, db: DatabaseManager):
        self.db = db
        self._cache: dict[str, str | None] = {}
        self.ensure_schema()

    # ------------------------------
    # Schema
    # ------------------------------

    def ensure_schema(self) -> None:
        """Ensure optional tables/columns needed by advanced settings UI exist."""

        with self.db.get_connection() as conn:
            cur = conn.cursor()

            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS settings_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    key TEXT NOT NULL,
                    old_value TEXT,
                    new_value TEXT,
                    changed_by INTEGER,
                    changed_at TEXT
                )
                """
            )

            # Optional richer user schema support (non-breaking additions)
            cur.execute("PRAGMA table_info(users)")
            cols = {row[1] for row in cur.fetchall()}

            def add_col(name: str, ddl: str) -> None:
                if name in cols:
                    return
                cur.execute(f"ALTER TABLE users ADD COLUMN {ddl}")

            # Keep existing password column, add secure hash fields
            add_col("password_hash", "password_hash TEXT")
            add_col("password_salt", "password_salt TEXT")
            add_col("email", "email TEXT")
            add_col("phone", "phone TEXT")
            add_col("force_password_change", "force_password_change INTEGER DEFAULT 0")
            add_col("last_login", "last_login TEXT")
            add_col("created_by", "created_by INTEGER")

            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS permissions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    role TEXT NOT NULL,
                    page TEXT NOT NULL,
                    can_view INTEGER DEFAULT 0,
                    can_add INTEGER DEFAULT 0,
                    can_edit INTEGER DEFAULT 0,
                    can_delete INTEGER DEFAULT 0,
                    can_print INTEGER DEFAULT 0,
                    UNIQUE(role, page)
                )
                """
            )

            # Seed default permissions (role-based)
            pages = [
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

            defaults: list[tuple[str, str, int, int, int, int, int]] = []

            # Admin: everything
            for p in pages:
                defaults.append(("admin", p, 1, 1, 1, 1, 1))

            # Employee: typical day-to-day modules
            for p in ["dashboard", "members", "subscriptions", "attendance", "payments", "reports", "about"]:
                defaults.append(("employee", p, 1, 1, 1, 1, 1))
            for p in ["plans", "settings"]:
                defaults.append(("employee", p, 0, 0, 0, 0, 0))

            # Receptionist: members + subscriptions + attendance
            for p in ["dashboard", "members", "subscriptions", "attendance", "about"]:
                defaults.append(("receptionist", p, 1, 1, 1, 1, 1))
            for p in ["payments", "plans", "reports", "settings"]:
                defaults.append(("receptionist", p, 0, 0, 0, 0, 0))

            # Trainer: attendance only
            for p in ["dashboard", "attendance", "about"]:
                defaults.append(("trainer", p, 1, 1, 1, 1, 1))
            for p in ["members", "subscriptions", "payments", "plans", "reports", "settings"]:
                defaults.append(("trainer", p, 0, 0, 0, 0, 0))

            cur.executemany(
                """
                INSERT OR IGNORE INTO permissions (role, page, can_view, can_add, can_edit, can_delete, can_print)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                defaults,
            )

            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS user_sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    login_time TEXT,
                    logout_time TEXT,
                    ip_address TEXT,
                    FOREIGN KEY (user_id) REFERENCES users(id)
                )
                """
            )

            conn.commit()

    # ------------------------------
    # Key encoding (category/key over existing settings table)
    # ------------------------------

    @staticmethod
    def make_key(category: str, key: str) -> str:
        category = (category or "").strip()
        key = (key or "").strip()
        return f"{category}.{key}" if category else key

    def _get_raw(self, full_key: str, default: str | None = None) -> str | None:
        if full_key in self._cache:
            v = self._cache[full_key]
            return v if v is not None else default

        v = self.db.get_settings(full_key)
        self._cache[full_key] = v
        return v if v is not None else default

    def _set_raw(self, full_key: str, value: str, changed_by: int | None = None) -> tuple[bool, str]:
        old = self._get_raw(full_key)
        ok, msg = self.db.set_settings(full_key, value)
        if ok:
            self._cache[full_key] = value
            try:
                with self.db.get_connection() as conn:
                    conn.execute(
                        "INSERT INTO settings_log (key, old_value, new_value, changed_by, changed_at) VALUES (?, ?, ?, ?, ?)",
                        (full_key, old, value, changed_by, _now_dt_str()),
                    )
                    conn.commit()
            except Exception:
                pass
        return ok, msg

    # ------------------------------
    # Public API
    # ------------------------------

    def preload(self) -> None:
        """Load all settings into cache."""

        with self.db.get_connection() as conn:
            rows = conn.execute("SELECT key, value FROM settings").fetchall()
        for r in rows:
            self._cache[str(r["key"])] = str(r["value"]) if r["value"] is not None else None

    def get(self, category: str, key: str, default: Any = None) -> Any:
        full_key = self.make_key(category, key)
        v = self._get_raw(full_key)
        return default if v is None else v

    def set(self, category: str, key: str, value: Any, changed_by: int | None = None) -> tuple[bool, str]:
        full_key = self.make_key(category, key)
        return self._set_raw(full_key, str(value), changed_by=changed_by)

    def get_category(self, category: str) -> dict[str, str | None]:
        prefix = f"{category}."
        out: dict[str, str | None] = {}

        if not self._cache:
            self.preload()

        for k, v in self._cache.items():
            if k.startswith(prefix):
                out[k[len(prefix) :]] = v
        return out

    def reset_to_defaults(self, category: str | None = None, changed_by: int | None = None) -> None:
        defaults = self._default_settings()
        items = []
        if category:
            for (cat, key), value in defaults.items():
                if cat == category:
                    items.append((cat, key, value))
        else:
            for (cat, key), value in defaults.items():
                items.append((cat, key, value))

        for cat, key, value in items:
            self.set(cat, key, value, changed_by=changed_by)

    def export_settings(self, filepath: str) -> None:
        if not self._cache:
            self.preload()

        data: dict[str, dict[str, str | None]] = {}
        for full_key, value in self._cache.items():
            if "." in full_key:
                cat, k = full_key.split(".", 1)
            else:
                cat, k = "general", full_key
            data.setdefault(cat, {})[k] = value

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def import_settings(self, filepath: str, changed_by: int | None = None) -> None:
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)

        if not isinstance(data, dict):
            raise ValueError("Invalid settings JSON")

        for cat, pairs in data.items():
            if not isinstance(pairs, dict):
                continue
            for k, v in pairs.items():
                self.set(str(cat), str(k), "" if v is None else str(v), changed_by=changed_by)

    # ------------------------------
    # Users + permissions
    # ------------------------------

    @staticmethod
    def hash_password(password: str, salt: str | None = None) -> tuple[str, str]:
        import hashlib

        if salt is None:
            salt = secrets.token_hex(16)
        digest = hashlib.sha256((salt + password).encode("utf-8")).hexdigest()
        return digest, salt

    def create_user(
        self,
        username: str,
        password: str,
        full_name: str = "",
        email: str = "",
        phone: str = "",
        role: str = "employee",
        is_active: bool = True,
        force_password_change: bool = False,
        created_by: int | None = None,
    ) -> tuple[bool, str]:
        username = (username or "").strip()
        if not username:
            return False, "username required"

        pw_hash, pw_salt = self.hash_password(password)
        now = _now_dt_str()

        try:
            with self.db.get_connection() as conn:
                conn.execute(
                    """
                    INSERT INTO users (username, password, password_hash, password_salt, full_name, email, phone, role, is_active, force_password_change, created_at, updated_at, created_by)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        username,
                        pw_hash,
                        pw_hash,
                        pw_salt,
                        full_name.strip() or None,
                        email.strip() or None,
                        phone.strip() or None,
                        role.strip() or "employee",
                        1 if is_active else 0,
                        1 if force_password_change else 0,
                        now,
                        now,
                        created_by,
                    ),
                )
                conn.commit()
            return True, "created"
        except sqlite3.IntegrityError:
            return False, "username exists"
        except Exception as e:
            return False, str(e)

    def update_user(
        self,
        user_id: int,
        full_name: str = "",
        email: str = "",
        phone: str = "",
        role: str = "employee",
        is_active: bool = True,
        force_password_change: bool = False,
    ) -> tuple[bool, str]:
        try:
            with self.db.get_connection() as conn:
                conn.execute(
                    """
                    UPDATE users
                    SET full_name = ?, email = ?, phone = ?, role = ?, is_active = ?, force_password_change = ?, updated_at = ?
                    WHERE id = ?
                    """,
                    (
                        full_name.strip() or None,
                        email.strip() or None,
                        phone.strip() or None,
                        role.strip() or "employee",
                        1 if is_active else 0,
                        1 if force_password_change else 0,
                        _now_dt_str(),
                        user_id,
                    ),
                )
                conn.commit()
            return True, "updated"
        except Exception as e:
            return False, str(e)

    def set_user_password(self, user_id: int, new_password: str, force_change: bool = False) -> tuple[bool, str]:
        pw_hash, pw_salt = self.hash_password(new_password)
        try:
            with self.db.get_connection() as conn:
                conn.execute(
                    """
                    UPDATE users
                    SET password = ?, password_hash = ?, password_salt = ?, force_password_change = ?, updated_at = ?
                    WHERE id = ?
                    """,
                    (pw_hash, pw_hash, pw_salt, 1 if force_change else 0, _now_dt_str(), user_id),
                )
                conn.commit()
            return True, "password updated"
        except Exception as e:
            return False, str(e)

    def delete_user(self, user_id: int) -> tuple[bool, str]:
        try:
            with self.db.get_connection() as conn:
                conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
                conn.commit()
            return True, "deleted"
        except Exception as e:
            return False, str(e)

    def list_users(self) -> list[dict[str, Any]]:
        with self.db.get_connection() as conn:
            rows = conn.execute(
                """
                SELECT id, username, full_name, role, is_active, last_login, email, phone, force_password_change, created_at
                FROM users
                ORDER BY id ASC
                """
            ).fetchall()

        return [dict(r) for r in rows]

    def get_permissions_matrix(self, role: str) -> dict[str, dict[str, int]]:
        pages = ["dashboard", "members", "subscriptions", "attendance", "payments", "plans", "reports", "settings", "about"]
        with self.db.get_connection() as conn:
            rows = conn.execute(
                "SELECT page, can_view, can_add, can_edit, can_delete, can_print FROM permissions WHERE role = ?",
                (role,),
            ).fetchall()

        out: dict[str, dict[str, int]] = {p: {"view": 0, "add": 0, "edit": 0, "delete": 0, "print": 0} for p in pages}
        for r in rows:
            out[str(r["page"])] = {
                "view": int(r["can_view"]),
                "add": int(r["can_add"]),
                "edit": int(r["can_edit"]),
                "delete": int(r["can_delete"]),
                "print": int(r["can_print"]),
            }
        return out

    def set_permissions_matrix(self, role: str, matrix: dict[str, dict[str, int]]) -> None:
        with self.db.get_connection() as conn:
            for page, perms in matrix.items():
                conn.execute(
                    """
                    INSERT INTO permissions (role, page, can_view, can_add, can_edit, can_delete, can_print)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(role, page) DO UPDATE SET
                        can_view=excluded.can_view,
                        can_add=excluded.can_add,
                        can_edit=excluded.can_edit,
                        can_delete=excluded.can_delete,
                        can_print=excluded.can_print
                    """,
                    (
                        role,
                        page,
                        int(perms.get("view", 0)),
                        int(perms.get("add", 0)),
                        int(perms.get("edit", 0)),
                        int(perms.get("delete", 0)),
                        int(perms.get("print", 0)),
                    ),
                )
            conn.commit()

    # ------------------------------
    # Defaults
    # ------------------------------

    def _default_settings(self) -> dict[tuple[str, str], str]:
        return {
            ("gym", "name"): "نادي اللياقة البدنية",
            ("gym", "logo"): "",
            ("gym", "address"): "",
            ("gym", "phone"): "",
            ("gym", "email"): "",
            ("gym", "website"): "",
            ("gym", "description"): "",
            ("gym", "opening_time"): "06:00",
            ("gym", "closing_time"): "23:00",
            ("gym", "working_days"): "sat,sun,mon,tue,wed,thu",
            ("gym", "currency"): "EGP",
            ("gym", "tax_rate"): "14",
            ("gym", "tax_enabled"): "0",
            ("gym", "grace_period"): "0",
            ("system", "theme"): "cosmo",
            ("system", "language"): "ar",
            ("system", "font_size"): "medium",
            ("system", "ui_direction"): "rtl",
            ("system", "db_path"): str(config.get_database_path()),
            ("system", "images_path"): str(getattr(config, "DATA_DIR", Path.cwd())),
            ("system", "reports_path"): str(getattr(config, "DATA_DIR", Path.cwd())),
            ("system", "start_with_windows"): "0",
            ("system", "minimize_to_tray"): "1",
            ("system", "high_performance"): "0",
            ("system", "records_per_page"): "50",
            ("notifications", "days_before_expiry"): "7",
            ("notifications", "notify_on_expiry"): "1",
            ("notifications", "days_after_expiry"): "3",
            ("notifications", "debt_threshold"): "500",
            ("notifications", "daily_finance_on_exit"): "1",
            ("notifications", "warn_expenses_threshold"): "0",
            ("notifications", "warn_expenses_value"): "",
            ("notifications", "warn_expired_on_entry"): "1",
            ("notifications", "warn_duplicate_attendance"): "1",
            ("notifications", "sound_on_attendance"): "0",
            ("notifications", "in_app"): "1",
            ("notifications", "windows" ): "0",
            ("notifications", "email_enabled"): "0",
            ("notifications", "sms_enabled"): "0",
            ("notifications", "smtp_host"): "smtp.gmail.com",
            ("notifications", "smtp_port"): "587",
            ("notifications", "smtp_email"): "",
            ("notifications", "smtp_password"): "",
            ("backup", "auto_backup"): "1",
            ("backup", "backup_frequency"): "daily",
            ("backup", "backup_time"): "23:00",
            ("backup", "backup_path"): "",
            ("backup", "keep_backups"): "7",
            ("backup", "compress"): "1",
            ("backup", "encrypt"): "0",
        }
