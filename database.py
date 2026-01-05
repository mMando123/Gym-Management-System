"""SQLite database layer for Gym Management System.

This module provides a single entry point (DatabaseManager) for all database operations.
It is designed to work with the project's config.py file.

Key features:
- Uses parameterized queries to prevent SQL injection
- Uses sqlite3.Row so SELECT queries can return dictionaries
- Enables foreign key constraints
- Stores dates in ISO formats
"""

from __future__ import annotations

import hashlib
import sqlite3
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Optional

import config


def _now_dt_str() -> str:
    """Return current datetime as a string."""

    return datetime.now().strftime(config.DATETIME_FORMAT)


def _today_str() -> str:
    """Return today's date as ISO string (YYYY-MM-DD)."""

    return date.today().isoformat()


def _add_months(start: date, months: int) -> date:
    """Add months to a date while keeping a valid day-of-month."""

    month = start.month - 1 + months
    year = start.year + month // 12
    month = month % 12 + 1

    # Clamp day to last day of target month.
    # Works without external dependencies.
    if month == 12:
        next_month = date(year + 1, 1, 1)
    else:
        next_month = date(year, month + 1, 1)
    last_day = (next_month - timedelta(days=1)).day

    day = min(start.day, last_day)
    return date(year, month, day)


def _row_to_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
    """Convert sqlite3.Row to a plain dict."""

    if row is None:
        return None
    return dict(row)


class DatabaseManager:
    """Database manager handling all SQLite operations."""

    def __init__(self) -> None:
        """Initialize database, create tables, and insert default data."""

        config.init_directories()
        self.db_path: Path = config.get_database_path()
        self.create_tables()
        self.init_default_data()

    # ------------------------------
    # Connection Methods
    # ------------------------------

    def get_connection(self) -> sqlite3.Connection:
        """Create and return a configured database connection."""

        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row

        # Ensure foreign key constraints are enforced.
        conn.execute("PRAGMA foreign_keys = ON;")
        return conn

    def close_connection(self, conn: sqlite3.Connection) -> None:
        """Close a database connection."""

        try:
            conn.close()
        except Exception:
            # Close failures are non-fatal.
            pass

    def create_tables(self) -> None:
        """Create all tables and indexes if they do not already exist."""

        with self.get_connection() as conn:
            cur = conn.cursor()

            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT UNIQUE NOT NULL,
                    password TEXT NOT NULL,
                    full_name TEXT,
                    role TEXT DEFAULT 'admin',
                    is_active INTEGER DEFAULT 1,
                    created_at TEXT,
                    updated_at TEXT
                )
                """
            )

            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS members (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    member_code TEXT UNIQUE NOT NULL,
                    first_name TEXT NOT NULL,
                    last_name TEXT NOT NULL,
                    phone TEXT NOT NULL,
                    email TEXT,
                    gender TEXT,
                    date_of_birth TEXT,
                    national_id TEXT,
                    address TEXT,
                    emergency_contact TEXT,
                    emergency_phone TEXT,
                    photo_path TEXT,
                    notes TEXT,
                    status TEXT DEFAULT 'active',
                    join_date TEXT,
                    created_at TEXT,
                    updated_at TEXT
                )
                """
            )

            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS subscription_types (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name_ar TEXT NOT NULL,
                    name_en TEXT,
                    duration_months INTEGER NOT NULL,
                    price REAL NOT NULL,
                    description TEXT,
                    is_active INTEGER DEFAULT 1,
                    created_at TEXT
                )
                """
            )

            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS subscriptions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    member_id INTEGER NOT NULL,
                    subscription_type_id INTEGER NOT NULL,
                    start_date TEXT NOT NULL,
                    end_date TEXT NOT NULL,
                    amount_paid REAL NOT NULL,
                    payment_method TEXT,
                    status TEXT DEFAULT 'active',
                    invoice_status TEXT DEFAULT 'unpaid',
                    paid_at TEXT,
                    notes TEXT,
                    created_by INTEGER,
                    created_at TEXT,
                    updated_at TEXT,
                    FOREIGN KEY (member_id) REFERENCES members(id),
                    FOREIGN KEY (subscription_type_id) REFERENCES subscription_types(id),
                    FOREIGN KEY (created_by) REFERENCES users(id)
                )
                """
            )

            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS payments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    subscription_id INTEGER,
                    member_id INTEGER NOT NULL,
                    amount REAL NOT NULL,
                    payment_method TEXT,
                    payment_date TEXT,
                    receipt_number TEXT UNIQUE,
                    notes TEXT,
                    created_by INTEGER,
                    created_at TEXT,
                    FOREIGN KEY (subscription_id) REFERENCES subscriptions(id),
                    FOREIGN KEY (member_id) REFERENCES members(id)
                )
                """
            )

            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS attendance (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    member_id INTEGER NOT NULL,
                    check_in TEXT NOT NULL,
                    check_out TEXT,
                    notes TEXT,
                    FOREIGN KEY (member_id) REFERENCES members(id)
                )
                """
            )

            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS expenses (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    category TEXT NOT NULL,
                    description TEXT,
                    amount REAL NOT NULL,
                    expense_date TEXT,
                    created_by INTEGER,
                    created_at TEXT,
                    FOREIGN KEY (created_by) REFERENCES users(id)
                )
                """
            )

            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS settings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    key TEXT UNIQUE NOT NULL,
                    value TEXT,
                    updated_at TEXT
                )
                """
            )

            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS role_permissions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    role TEXT NOT NULL,
                    module TEXT NOT NULL,
                    can_view INTEGER DEFAULT 0,
                    can_edit INTEGER DEFAULT 0,
                    UNIQUE(role, module)
                )
                """
            )

            try:
                cols = {r["name"] for r in cur.execute("PRAGMA table_info(subscriptions)").fetchall()}
                if "invoice_status" not in cols:
                    cur.execute("ALTER TABLE subscriptions ADD COLUMN invoice_status TEXT DEFAULT 'unpaid'")
                if "paid_at" not in cols:
                    cur.execute("ALTER TABLE subscriptions ADD COLUMN paid_at TEXT")
            except Exception:
                pass

            # Indexes (frequently searched columns)
            cur.execute("CREATE INDEX IF NOT EXISTS idx_members_member_code ON members(member_code);")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_members_phone ON members(phone);")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_members_status ON members(status);")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_subscriptions_member_id ON subscriptions(member_id);")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_subscriptions_status ON subscriptions(status);")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_subscriptions_end_date ON subscriptions(end_date);")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_subscriptions_invoice_status ON subscriptions(invoice_status);")
            try:
                cur.execute(
                    """
                    CREATE UNIQUE INDEX IF NOT EXISTS idx_subscriptions_unique_period
                    ON subscriptions(member_id, subscription_type_id, start_date, end_date)
                    WHERE status != 'cancelled'
                    """
                )
            except Exception:
                pass
            cur.execute("CREATE INDEX IF NOT EXISTS idx_payments_member_id ON payments(member_id);")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_payments_payment_date ON payments(payment_date);")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_payments_receipt_number ON payments(receipt_number);")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_attendance_member_id ON attendance(member_id);")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_attendance_check_in ON attendance(check_in);")

            # Default role permissions
            default_perms = [
                # admin: full access
                ("admin", "dashboard", 1, 1),
                ("admin", "members", 1, 1),
                ("admin", "subscriptions", 1, 1),
                ("admin", "attendance", 1, 1),
                ("admin", "payments", 1, 1),
                ("admin", "plans", 1, 1),
                ("admin", "reports", 1, 1),
                ("admin", "settings", 1, 1),
                ("admin", "about", 1, 0),
                # employee: can view most but not settings
                ("employee", "dashboard", 1, 0),
                ("employee", "members", 1, 1),
                ("employee", "subscriptions", 1, 1),
                ("employee", "attendance", 1, 1),
                ("employee", "payments", 1, 1),
                ("employee", "plans", 0, 0),
                ("employee", "reports", 1, 0),
                ("employee", "settings", 0, 0),
                ("employee", "about", 1, 0),
                # receptionist: members, subscriptions, attendance
                ("receptionist", "dashboard", 1, 0),
                ("receptionist", "members", 1, 1),
                ("receptionist", "subscriptions", 1, 1),
                ("receptionist", "attendance", 1, 1),
                ("receptionist", "payments", 0, 0),
                ("receptionist", "plans", 0, 0),
                ("receptionist", "reports", 0, 0),
                ("receptionist", "settings", 0, 0),
                ("receptionist", "about", 1, 0),
                # trainer: attendance only
                ("trainer", "dashboard", 1, 0),
                ("trainer", "members", 0, 0),
                ("trainer", "subscriptions", 0, 0),
                ("trainer", "attendance", 1, 1),
                ("trainer", "payments", 0, 0),
                ("trainer", "plans", 0, 0),
                ("trainer", "reports", 0, 0),
                ("trainer", "settings", 0, 0),
                ("trainer", "about", 1, 0),
            ]
            cur.executemany(
                """
                INSERT OR IGNORE INTO role_permissions (role, module, can_view, can_edit)
                VALUES (?, ?, ?, ?)
                """,
                default_perms,
            )

            try:
                cur.execute(
                    """
                    UPDATE subscriptions
                    SET invoice_status = CASE
                        WHEN COALESCE(amount_paid, 0) + 1e-9 >= (
                            SELECT COALESCE(price, 0)
                            FROM subscription_types st
                            WHERE st.id = subscriptions.subscription_type_id
                        ) THEN 'paid'
                        ELSE 'unpaid'
                    END
                    WHERE invoice_status IS NULL OR invoice_status = ''
                    """
                )
                cur.execute(
                    """
                    UPDATE subscriptions
                    SET paid_at = (
                        SELECT MAX(p.payment_date)
                        FROM payments p
                        WHERE p.subscription_id = subscriptions.id
                    )
                    WHERE invoice_status = 'paid' AND (paid_at IS NULL OR paid_at = '')
                    """
                )
            except Exception:
                pass

            conn.commit()

    def init_default_data(self) -> None:
        """Insert default admin user and subscription types if missing."""

        with self.get_connection() as conn:
            cur = conn.cursor()

            # Default admin
            cur.execute("SELECT id FROM users WHERE username = ? LIMIT 1", (config.DEFAULT_ADMIN_USERNAME,))
            admin = cur.fetchone()
            if admin is None:
                now = _now_dt_str()
                cur.execute(
                    """
                    INSERT INTO users (username, password, full_name, role, is_active, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        config.DEFAULT_ADMIN_USERNAME,
                        self.hash_password(config.DEFAULT_ADMIN_PASSWORD),
                        "Administrator",
                        "admin",
                        1,
                        now,
                        now,
                    ),
                )

            # Default subscription types
            cur.execute("SELECT COUNT(*) AS cnt FROM subscription_types")
            cnt_row = cur.fetchone()
            existing_count = int(cnt_row["cnt"]) if cnt_row else 0
            if existing_count == 0:
                now = _now_dt_str()
                for st in config.SUBSCRIPTION_TYPES:
                    cur.execute(
                        """
                        INSERT INTO subscription_types
                            (name_ar, name_en, duration_months, price, description, is_active, created_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            str(st.get("name_ar")),
                            str(st.get("name_en")),
                            int(st.get("duration_months")),
                            float(st.get("price")),
                            None,
                            1,
                            now,
                        ),
                    )

            conn.commit()

    # ------------------------------
    # User Methods
    # ------------------------------

    def hash_password(self, password: str) -> str:
        """Hash a password with SHA256."""

        return hashlib.sha256(password.encode("utf-8")).hexdigest()

    def verify_password(self, password: str, hashed: str) -> bool:
        """Verify a password against a SHA256 hash."""

        return self.hash_password(password) == (hashed or "")

    def check_permission(self, role: str, module: str, permission: str = "can_view") -> bool:
        """Check if a role has permission for a module/page.

        Prefers the SettingsManager schema: permissions(role,page,can_*)
        Falls back to role_permissions(role,module,can_view/can_edit) if present.
        """

        role = str(role or "").strip() or "employee"
        module = str(module or "").strip()

        if role.lower() == "admin":
            return True

        # 1) Preferred table: permissions
        try:
            with self.get_connection() as conn:
                cur = conn.cursor()
                row = cur.execute(
                    """
                    SELECT can_view, can_add, can_edit, can_delete, can_print
                    FROM permissions
                    WHERE role = ? AND page = ?
                    LIMIT 1
                    """,
                    (role, module),
                ).fetchone()
                if row:
                    col = str(permission or "can_view")
                    if col not in {"can_view", "can_add", "can_edit", "can_delete", "can_print"}:
                        col = "can_view"
                    try:
                        return bool(row[col])
                    except Exception:
                        return bool(row["can_view"])
        except Exception:
            pass

        # 2) Fallback table: role_permissions
        try:
            with self.get_connection() as conn:
                cur = conn.cursor()
                row = cur.execute(
                    """
                    SELECT can_view, can_edit FROM role_permissions
                    WHERE role = ? AND module = ? LIMIT 1
                    """,
                    (role, module),
                ).fetchone()
                if not row:
                    return False
                if permission == "can_edit":
                    return bool(row["can_edit"])
                return bool(row["can_view"])
        except Exception:
            return False

    def authenticate_user(self, username: str, password: str) -> dict[str, Any] | None:
        """Authenticate user. Returns a user dict on success, otherwise None."""

        with self.get_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT * FROM users
                WHERE username = ? COLLATE NOCASE AND is_active = 1
                LIMIT 1
                """,
                (username,),
            )
            row = cur.fetchone()
            if row is None:
                return None

            try:
                salt = row["password_salt"]
            except Exception:
                salt = None

            if salt:
                try:
                    import hashlib

                    digest = hashlib.sha256((str(salt) + password).encode("utf-8")).hexdigest()
                    try:
                        stored = row["password_hash"]
                    except Exception:
                        stored = row["password"]
                    if digest != (stored or ""):
                        return None
                except Exception:
                    return None
            else:
                if not self.verify_password(password, row["password"]):
                    return None
            user = dict(row)
            user.pop("password", None)
            return user

    def create_user(self, username: str, password: str, full_name: str | None, role: str = "admin") -> tuple[bool, str, Optional[int]]:
        """Create a new user.

        Returns: (success, message, user_id)
        """

        try:
            with self.get_connection() as conn:
                cur = conn.cursor()
                now = _now_dt_str()
                cur.execute(
                    """
                    INSERT INTO users (username, password, full_name, role, is_active, created_at, updated_at)
                    VALUES (?, ?, ?, ?, 1, ?, ?)
                    """,
                    (username, self.hash_password(password), full_name, role, now, now),
                )
                conn.commit()
                return True, "User created successfully", int(cur.lastrowid)
        except sqlite3.IntegrityError:
            return False, "Username already exists", None
        except Exception as e:
            return False, f"Error creating user: {e}", None

    def get_user_by_id(self, user_id: int) -> dict[str, Any] | None:
        """Return a user dict by ID (without password)."""

        with self.get_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT * FROM users WHERE id = ? LIMIT 1", (user_id,))
            row = cur.fetchone()
            if row is None:
                return None
            user = dict(row)
            user.pop("password", None)
            return user

    def update_user(self, user_id: int, **kwargs: Any) -> tuple[bool, str]:
        """Update user fields.

        Allowed keys: username, password, full_name, role, is_active
        """

        allowed = {"username", "password", "full_name", "role", "is_active"}
        updates: dict[str, Any] = {k: v for k, v in kwargs.items() if k in allowed}
        if not updates:
            return False, "No valid fields to update"

        if "password" in updates and updates["password"] is not None:
            updates["password"] = self.hash_password(str(updates["password"]))

        updates["updated_at"] = _now_dt_str()

        set_clause = ", ".join([f"{k} = ?" for k in updates.keys()])
        params = list(updates.values()) + [user_id]

        try:
            with self.get_connection() as conn:
                conn.execute(f"UPDATE users SET {set_clause} WHERE id = ?", params)
                conn.commit()
                return True, "User updated successfully"
        except sqlite3.IntegrityError:
            return False, "Username already exists"
        except Exception as e:
            return False, f"Error updating user: {e}"

    # ------------------------------
    # Member Methods
    # ------------------------------

    def generate_member_code(self) -> str:
        """Generate the next sequential member code (e.g., MEM-0001)."""

        with self.get_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT member_code
                FROM members
                WHERE member_code LIKE 'MEM-%'
                ORDER BY id DESC
                LIMIT 1
                """
            )
            row = cur.fetchone()

        if row is None or not row["member_code"]:
            next_num = 1
        else:
            try:
                next_num = int(str(row["member_code"]).split("-")[-1]) + 1
            except Exception:
                next_num = 1

        return f"MEM-{next_num:04d}"

    def create_member(self, **kwargs: Any) -> tuple[bool, str, Optional[int]]:
        """Create a new member.

        Returns: (success, message, member_id)
        """

        required = {"first_name", "last_name", "phone"}
        missing = [k for k in required if not kwargs.get(k)]
        if missing:
            return False, f"Missing required fields: {', '.join(missing)}", None

        member_code = kwargs.get("member_code") or self.generate_member_code()
        now = _now_dt_str()
        join_date = kwargs.get("join_date") or _today_str()

        fields = {
            "member_code": member_code,
            "first_name": kwargs.get("first_name"),
            "last_name": kwargs.get("last_name"),
            "phone": kwargs.get("phone"),
            "email": kwargs.get("email"),
            "gender": kwargs.get("gender"),
            "date_of_birth": kwargs.get("date_of_birth"),
            "national_id": kwargs.get("national_id"),
            "address": kwargs.get("address"),
            "emergency_contact": kwargs.get("emergency_contact"),
            "emergency_phone": kwargs.get("emergency_phone"),
            "photo_path": kwargs.get("photo_path"),
            "notes": kwargs.get("notes"),
            "status": kwargs.get("status") or "active",
            "join_date": join_date,
            "created_at": now,
            "updated_at": now,
        }

        try:
            with self.get_connection() as conn:
                cur = conn.cursor()
                cols = ", ".join(fields.keys())
                placeholders = ", ".join(["?"] * len(fields))
                cur.execute(
                    f"INSERT INTO members ({cols}) VALUES ({placeholders})",
                    tuple(fields.values()),
                )
                conn.commit()
                return True, "Member created successfully", int(cur.lastrowid)
        except sqlite3.IntegrityError as e:
            return False, f"Member already exists or duplicate data: {e}", None
        except Exception as e:
            return False, f"Error creating member: {e}", None

    def get_member_by_id(self, member_id: int) -> dict[str, Any] | None:
        """Return member dict by ID including current active subscription (if any)."""

        with self.get_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT * FROM members WHERE id = ? LIMIT 1", (member_id,))
            member = cur.fetchone()
            if member is None:
                return None

            cur.execute(
                """
                SELECT s.*, st.name_ar AS type_name_ar, st.name_en AS type_name_en,
                       st.duration_months, st.price
                FROM subscriptions s
                JOIN subscription_types st ON st.id = s.subscription_type_id
                WHERE s.member_id = ? AND s.status = 'active'
                ORDER BY s.end_date DESC, s.id DESC
                LIMIT 1
                """,
                (member_id,),
            )
            active_sub = cur.fetchone()

        data = dict(member)
        data["active_subscription"] = _row_to_dict(active_sub)
        return data

    def get_member_by_code(self, member_code: str) -> dict[str, Any] | None:
        """Return member dict by code."""

        with self.get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM members WHERE member_code = ? LIMIT 1",
                (member_code,),
            ).fetchone()
            return _row_to_dict(row)

    def get_member_by_phone(self, phone: str) -> dict[str, Any] | None:
        """Return member dict by phone."""

        with self.get_connection() as conn:
            row = conn.execute("SELECT * FROM members WHERE phone = ? LIMIT 1", (phone,)).fetchone()
            return _row_to_dict(row)

    def get_all_members(self, status: str | None = None) -> list[dict[str, Any]]:
        """Return all members. Optionally filter by status."""

        with self.get_connection() as conn:
            cur = conn.cursor()
            if status:
                cur.execute("SELECT * FROM members WHERE status = ? ORDER BY id DESC", (status,))
            else:
                cur.execute("SELECT * FROM members ORDER BY id DESC")
            return [dict(r) for r in cur.fetchall()]

    def update_member(self, member_id: int, **kwargs: Any) -> tuple[bool, str]:
        """Update member fields."""

        allowed = {
            "member_code",
            "first_name",
            "last_name",
            "phone",
            "email",
            "gender",
            "date_of_birth",
            "national_id",
            "address",
            "emergency_contact",
            "emergency_phone",
            "photo_path",
            "notes",
            "status",
            "join_date",
        }
        updates = {k: v for k, v in kwargs.items() if k in allowed}
        if not updates:
            return False, "No valid fields to update"

        updates["updated_at"] = _now_dt_str()
        set_clause = ", ".join([f"{k} = ?" for k in updates.keys()])
        params = list(updates.values()) + [member_id]

        try:
            with self.get_connection() as conn:
                conn.execute(f"UPDATE members SET {set_clause} WHERE id = ?", params)
                conn.commit()
                return True, "Member updated successfully"
        except sqlite3.IntegrityError as e:
            return False, f"Update failed due to duplicate data: {e}"
        except Exception as e:
            return False, f"Error updating member: {e}"

    def delete_member(self, member_id: int) -> tuple[bool, str]:
        """Soft delete member by setting status to inactive."""

        return self.update_member(member_id, status="inactive")

    def activate_member(self, member_id: int) -> tuple[bool, str]:
        """Re-activate a soft-deleted member by setting status to active."""

        return self.update_member(member_id, status="active")

    def activate_all_inactive_members(self) -> tuple[bool, str, int]:
        """Re-activate all inactive members in one operation."""

        now = _now_dt_str()
        try:
            with self.get_connection() as conn:
                cur = conn.cursor()
                cur.execute(
                    "UPDATE members SET status = 'active', updated_at = ? WHERE status = 'inactive'",
                    (now,),
                )
                affected = int(cur.rowcount or 0)
                conn.commit()
            return True, "Members activated successfully", affected
        except Exception as e:
            return False, f"Error activating members: {e}", 0

    def search_members(self, query: str) -> list[dict[str, Any]]:
        """Search members by name, phone, or member code."""

        q = f"%{query.strip()}%"
        with self.get_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT * FROM members
                WHERE member_code LIKE ?
                   OR phone LIKE ?
                   OR first_name LIKE ?
                   OR last_name LIKE ?
                   OR (first_name || ' ' || last_name) LIKE ?
                ORDER BY id DESC
                """,
                (q, q, q, q, q),
            )
            return [dict(r) for r in cur.fetchall()]

    # ------------------------------
    # Subscription Type Methods
    # ------------------------------

    def get_all_subscription_types(self, active_only: bool = True) -> list[dict[str, Any]]:
        """Return all subscription types."""

        with self.get_connection() as conn:
            cur = conn.cursor()
            if active_only:
                cur.execute("SELECT * FROM subscription_types WHERE is_active = 1 ORDER BY id ASC")
            else:
                cur.execute("SELECT * FROM subscription_types ORDER BY id ASC")
            return [dict(r) for r in cur.fetchall()]

    def get_subscription_type_by_id(self, type_id: int) -> dict[str, Any] | None:
        """Return subscription type dict by ID."""

        with self.get_connection() as conn:
            row = conn.execute("SELECT * FROM subscription_types WHERE id = ? LIMIT 1", (type_id,)).fetchone()
            return _row_to_dict(row)

    def create_subscription_type(self, **kwargs: Any) -> tuple[bool, str, Optional[int]]:
        """Create a new subscription type."""

        required = {"name_ar", "duration_months", "price"}
        missing = [k for k in required if kwargs.get(k) in (None, "")]
        if missing:
            return False, f"Missing required fields: {', '.join(missing)}", None

        fields = {
            "name_ar": kwargs.get("name_ar"),
            "name_en": kwargs.get("name_en"),
            "duration_months": int(kwargs.get("duration_months")),
            "price": float(kwargs.get("price")),
            "description": kwargs.get("description"),
            "is_active": int(kwargs.get("is_active", 1)),
            "created_at": _now_dt_str(),
        }

        try:
            with self.get_connection() as conn:
                cur = conn.cursor()
                cols = ", ".join(fields.keys())
                placeholders = ", ".join(["?"] * len(fields))
                cur.execute(
                    f"INSERT INTO subscription_types ({cols}) VALUES ({placeholders})",
                    tuple(fields.values()),
                )
                conn.commit()
                return True, "Subscription type created successfully", int(cur.lastrowid)
        except Exception as e:
            return False, f"Error creating subscription type: {e}", None

    def update_subscription_type(self, type_id: int, **kwargs: Any) -> tuple[bool, str]:
        """Update subscription type fields."""

        allowed = {"name_ar", "name_en", "duration_months", "price", "description", "is_active"}
        updates = {k: v for k, v in kwargs.items() if k in allowed}
        if not updates:
            return False, "No valid fields to update"

        set_clause = ", ".join([f"{k} = ?" for k in updates.keys()])
        params = list(updates.values()) + [type_id]

        try:
            with self.get_connection() as conn:
                conn.execute(f"UPDATE subscription_types SET {set_clause} WHERE id = ?", params)
                conn.commit()
                return True, "Subscription type updated successfully"
        except Exception as e:
            return False, f"Error updating subscription type: {e}"

    # ------------------------------
    # Subscription Methods
    # ------------------------------

    def create_subscription(
        self,
        member_id: int,
        subscription_type_id: int,
        amount_paid: float,
        payment_method: str,
        start_date: str | None = None,
        created_by: int | None = None,
    ) -> tuple[bool, str, Optional[int]]:
        """Create a new subscription for a member.

        - Computes end_date using the subscription type duration.
        - Inserts an initial payment record.

        Returns: (success, message, subscription_id)
        """

        try:
            with self.get_connection() as conn:
                cur = conn.cursor()

                st = cur.execute(
                    "SELECT * FROM subscription_types WHERE id = ? AND is_active = 1 LIMIT 1",
                    (subscription_type_id,),
                ).fetchone()
                if st is None:
                    return False, "Invalid subscription type", None

                start = datetime.strptime(start_date, config.DATE_FORMAT).date() if start_date else date.today()
                end = _add_months(start, int(st["duration_months"]))

                try:
                    has_unpaid = cur.execute(
                        """
                        SELECT 1
                        FROM subscriptions
                        WHERE member_id = ?
                          AND status != 'cancelled'
                          AND (invoice_status = 'unpaid' OR invoice_status IS NULL OR invoice_status = '')
                        LIMIT 1
                        """,
                        (member_id,),
                    ).fetchone()
                    if has_unpaid is not None:
                        return False, "يوجد فاتورة غير مدفوعة لهذا العضو", None
                except Exception:
                    pass

                # Prevent duplicate/overlapping invoices for the same period.
                # Allows renewal only when the new period does not overlap (e.g., next day after end_date).
                try:
                    overlap = cur.execute(
                        """
                        SELECT 1
                        FROM subscriptions
                        WHERE member_id = ?
                          AND status != 'cancelled'
                          AND NOT (date(end_date) < date(?) OR date(start_date) > date(?))
                        LIMIT 1
                        """,
                        (member_id, start.isoformat(), end.isoformat()),
                    ).fetchone()
                    if overlap is not None:
                        return False, "يوجد اشتراك مسجل لهذا العضو لنفس الفترة", None
                except Exception:
                    pass

                now = _now_dt_str()

                total_price = float(st["price"] or 0)
                inv_status = "paid" if float(amount_paid) + 1e-9 >= total_price and total_price > 0 else "unpaid"
                paid_at = start.isoformat() if inv_status == "paid" else None

                # Optionally close any previous active subscription.
                cur.execute(
                    """
                    UPDATE subscriptions
                    SET status = 'expired', updated_at = ?
                    WHERE member_id = ? AND status = 'active' AND end_date < ?
                    """,
                    (now, member_id, _today_str()),
                )

                cur.execute(
                    """
                    INSERT INTO subscriptions
                        (member_id, subscription_type_id, start_date, end_date, amount_paid,
                         payment_method, status, invoice_status, paid_at, notes, created_by, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, 'active', ?, ?, NULL, ?, ?, ?)
                    """,
                    (
                        member_id,
                        subscription_type_id,
                        start.isoformat(),
                        end.isoformat(),
                        float(amount_paid),
                        payment_method,
                        inv_status,
                        paid_at,
                        created_by,
                        now,
                        now,
                    ),
                )
                subscription_id = int(cur.lastrowid)

                # Create initial payment record only when there is an actual payment.
                try:
                    if float(amount_paid) > 0.01:
                        receipt = self.generate_receipt_number()
                        cur.execute(
                            """
                            INSERT INTO payments
                                (subscription_id, member_id, amount, payment_method, payment_date,
                                 receipt_number, notes, created_by, created_at)
                            VALUES (?, ?, ?, ?, ?, ?, NULL, ?, ?)
                            """,
                            (
                                subscription_id,
                                member_id,
                                float(amount_paid),
                                payment_method,
                                start.isoformat(),
                                receipt,
                                created_by,
                                now,
                            ),
                        )
                except Exception:
                    pass

                conn.commit()
                return True, "Subscription created successfully", subscription_id
        except Exception as e:
            return False, f"Error creating subscription: {e}", None

    def get_subscription_by_id(self, subscription_id: int) -> dict[str, Any] | None:
        """Return subscription with member and type info."""

        with self.get_connection() as conn:
            row = conn.execute(
                """
                SELECT s.*,
                       m.member_code, m.first_name, m.last_name, m.phone,
                       st.name_ar AS type_name_ar, st.name_en AS type_name_en,
                       st.duration_months, st.price
                FROM subscriptions s
                JOIN members m ON m.id = s.member_id
                JOIN subscription_types st ON st.id = s.subscription_type_id
                WHERE s.id = ?
                LIMIT 1
                """,
                (subscription_id,),
            ).fetchone()
            return _row_to_dict(row)

    def get_member_subscriptions(self, member_id: int) -> list[dict[str, Any]]:
        """Return all subscriptions for a member."""

        with self.get_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT s.*, st.name_ar AS type_name_ar, st.name_en AS type_name_en
                FROM subscriptions s
                JOIN subscription_types st ON st.id = s.subscription_type_id
                WHERE s.member_id = ?
                ORDER BY s.start_date DESC, s.id DESC
                """,
                (member_id,),
            )
            return [dict(r) for r in cur.fetchall()]

    def get_active_subscription(self, member_id: int) -> dict[str, Any] | None:
        """Return current active subscription for a member."""

        with self.get_connection() as conn:
            row = conn.execute(
                """
                SELECT s.*, st.name_ar AS type_name_ar, st.name_en AS type_name_en,
                       st.duration_months, st.price
                FROM subscriptions s
                JOIN subscription_types st ON st.id = s.subscription_type_id
                WHERE s.member_id = ? AND s.status = 'active'
                ORDER BY s.end_date DESC, s.id DESC
                LIMIT 1
                """,
                (member_id,),
            ).fetchone()
            return _row_to_dict(row)

    def get_expiring_subscriptions(self, days: int = 7) -> list[dict[str, Any]]:
        """Return active subscriptions expiring within X days."""

        today = date.today()
        end = today + timedelta(days=int(days))

        with self.get_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT s.*, m.member_code, m.first_name, m.last_name, m.phone,
                       st.name_ar AS type_name_ar, st.name_en AS type_name_en
                FROM subscriptions s
                JOIN members m ON m.id = s.member_id
                JOIN subscription_types st ON st.id = s.subscription_type_id
                WHERE s.status = 'active'
                  AND date(s.end_date) BETWEEN date(?) AND date(?)
                ORDER BY s.end_date ASC
                """,
                (today.isoformat(), end.isoformat()),
            )
            return [dict(r) for r in cur.fetchall()]

    def get_expired_subscriptions(self) -> list[dict[str, Any]]:
        """Return subscriptions that are expired but still marked active."""

        with self.get_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT s.*, m.member_code, m.first_name, m.last_name, m.phone
                FROM subscriptions s
                JOIN members m ON m.id = s.member_id
                WHERE s.status = 'active' AND date(s.end_date) < date(?)
                ORDER BY s.end_date ASC
                """,
                (_today_str(),),
            )
            return [dict(r) for r in cur.fetchall()]

    def update_subscription_status(self, subscription_id: int, status: str) -> tuple[bool, str]:
        """Update subscription status."""

        try:
            with self.get_connection() as conn:
                conn.execute(
                    "UPDATE subscriptions SET status = ?, updated_at = ? WHERE id = ?",
                    (status, _now_dt_str(), subscription_id),
                )
                conn.commit()
                return True, "Subscription status updated successfully"
        except Exception as e:
            return False, f"Error updating subscription status: {e}"

    def freeze_subscription(self, subscription_id: int, freeze_days: int) -> tuple[bool, str]:
        """Freeze a subscription and extend end_date by freeze_days."""

        try:
            with self.get_connection() as conn:
                cur = conn.cursor()
                row = cur.execute(
                    "SELECT end_date FROM subscriptions WHERE id = ? LIMIT 1",
                    (subscription_id,),
                ).fetchone()
                if row is None:
                    return False, "Subscription not found"

                end = datetime.strptime(row["end_date"], config.DATE_FORMAT).date()
                new_end = end + timedelta(days=int(freeze_days))

                cur.execute(
                    """
                    UPDATE subscriptions
                    SET status = 'frozen', end_date = ?, updated_at = ?
                    WHERE id = ?
                    """,
                    (new_end.isoformat(), _now_dt_str(), subscription_id),
                )
                conn.commit()
                return True, "Subscription frozen successfully"
        except Exception as e:
            return False, f"Error freezing subscription: {e}"

    def cancel_subscription(self, subscription_id: int) -> tuple[bool, str]:
        """Cancel a subscription."""

        return self.update_subscription_status(subscription_id, "cancelled")

    # ------------------------------
    # Payment Methods
    # ------------------------------

    def generate_receipt_number(self) -> str:
        """Generate a unique receipt number."""

        today = date.today().strftime("%Y%m%d")
        prefix = f"RCPT-{today}-"

        with self.get_connection() as conn:
            row = conn.execute(
                """
                SELECT receipt_number
                FROM payments
                WHERE receipt_number LIKE ?
                ORDER BY id DESC
                LIMIT 1
                """,
                (f"{prefix}%",),
            ).fetchone()

        if row is None or not row["receipt_number"]:
            seq = 1
        else:
            try:
                seq = int(str(row["receipt_number"]).split("-")[-1]) + 1
            except Exception:
                seq = 1

        return f"{prefix}{seq:04d}"

    def create_payment(self, **kwargs: Any) -> tuple[bool, str, Optional[int]]:
        """Create a payment record."""

        required = {"member_id", "amount"}
        missing = [k for k in required if kwargs.get(k) in (None, "")]
        if missing:
            return False, f"Missing required fields: {', '.join(missing)}", None

        receipt = kwargs.get("receipt_number") or self.generate_receipt_number()
        payment_date = kwargs.get("payment_date") or _today_str()

        fields = {
            "subscription_id": kwargs.get("subscription_id"),
            "member_id": int(kwargs.get("member_id")),
            "amount": float(kwargs.get("amount")),
            "payment_method": kwargs.get("payment_method"),
            "payment_date": payment_date,
            "receipt_number": receipt,
            "notes": kwargs.get("notes"),
            "created_by": kwargs.get("created_by"),
            "created_at": _now_dt_str(),
        }

        try:
            with self.get_connection() as conn:
                cur = conn.cursor()
                cols = ", ".join(fields.keys())
                placeholders = ", ".join(["?"] * len(fields))
                cur.execute(
                    f"INSERT INTO payments ({cols}) VALUES ({placeholders})",
                    tuple(fields.values()),
                )
                conn.commit()
                return True, "Payment created successfully", int(cur.lastrowid)
        except sqlite3.IntegrityError:
            return False, "Receipt number already exists", None
        except Exception as e:
            return False, f"Error creating payment: {e}", None

    def get_member_payments(self, member_id: int) -> list[dict[str, Any]]:
        """Return all payments for a member."""

        with self.get_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT p.*, s.start_date, s.end_date
                FROM payments p
                LEFT JOIN subscriptions s ON s.id = p.subscription_id
                WHERE p.member_id = ?
                ORDER BY p.payment_date DESC, p.id DESC
                """,
                (member_id,),
            )
            return [dict(r) for r in cur.fetchall()]

    def get_payments_by_date_range(self, start_date: str, end_date: str) -> list[dict[str, Any]]:
        """Return payments within a date range."""

        with self.get_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT p.*, m.member_code, m.first_name, m.last_name
                FROM payments p
                JOIN members m ON m.id = p.member_id
                WHERE date(p.payment_date) BETWEEN date(?) AND date(?)
                ORDER BY p.payment_date ASC, p.id ASC
                """,
                (start_date, end_date),
            )
            return [dict(r) for r in cur.fetchall()]

    # ------------------------------
    # Attendance Methods
    # ------------------------------

    def check_in(self, member_id: int) -> tuple[bool, str]:
        """Record member check-in. Prevents double check-in if open session exists."""

        try:
            with self.get_connection() as conn:
                cur = conn.cursor()
                open_row = cur.execute(
                    """
                    SELECT id FROM attendance
                    WHERE member_id = ? AND check_out IS NULL
                    ORDER BY id DESC
                    LIMIT 1
                    """,
                    (member_id,),
                ).fetchone()
                if open_row is not None:
                    return False, "Member is already checked in"

                cur.execute(
                    "INSERT INTO attendance (member_id, check_in, check_out, notes) VALUES (?, ?, NULL, NULL)",
                    (member_id, _now_dt_str()),
                )
                conn.commit()
                return True, "Check-in recorded"
        except Exception as e:
            return False, f"Error recording check-in: {e}"

    def check_out(self, member_id: int) -> tuple[bool, str]:
        """Record member check-out for the latest open attendance record."""

        try:
            with self.get_connection() as conn:
                cur = conn.cursor()
                row = cur.execute(
                    """
                    SELECT id FROM attendance
                    WHERE member_id = ? AND check_out IS NULL
                    ORDER BY id DESC
                    LIMIT 1
                    """,
                    (member_id,),
                ).fetchone()
                if row is None:
                    return False, "No open check-in record found"

                cur.execute(
                    "UPDATE attendance SET check_out = ? WHERE id = ?",
                    (_now_dt_str(), int(row["id"])),
                )
                conn.commit()
                return True, "Check-out recorded"
        except Exception as e:
            return False, f"Error recording check-out: {e}"

    def get_member_attendance(self, member_id: int, limit: int = 30) -> list[dict[str, Any]]:
        """Return recent attendance records for a member."""

        with self.get_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT * FROM attendance
                WHERE member_id = ?
                ORDER BY id DESC
                LIMIT ?
                """,
                (member_id, int(limit)),
            )
            return [dict(r) for r in cur.fetchall()]

    def get_today_attendance(self) -> list[dict[str, Any]]:
        """Return today's attendance records."""

        today = _today_str()
        with self.get_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT a.*, m.member_code, m.first_name, m.last_name
                FROM attendance a
                JOIN members m ON m.id = a.member_id
                WHERE date(a.check_in) = date(?)
                ORDER BY a.check_in DESC
                """,
                (today,),
            )
            return [dict(r) for r in cur.fetchall()]

    def get_attendance_by_date(self, date_str: str) -> list[dict[str, Any]]:
        """Return attendance records for a specific date."""

        with self.get_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT a.*, m.member_code, m.first_name, m.last_name
                FROM attendance a
                JOIN members m ON m.id = a.member_id
                WHERE date(a.check_in) = date(?)
                ORDER BY a.check_in DESC
                """,
                (date_str,),
            )
            return [dict(r) for r in cur.fetchall()]

    # ------------------------------
    # Statistics Methods
    # ------------------------------

    def get_monthly_revenue(self, year: int | None = None, month: int | None = None) -> float:
        """Return total revenue for a month."""

        dt = date.today()
        y = year or dt.year
        m = month or dt.month

        start = date(int(y), int(m), 1)
        if m == 12:
            end = date(int(y) + 1, 1, 1) - timedelta(days=1)
        else:
            end = date(int(y), int(m) + 1, 1) - timedelta(days=1)

        with self.get_connection() as conn:
            row = conn.execute(
                """
                SELECT COALESCE(SUM(amount), 0) AS total
                FROM payments
                WHERE date(payment_date) BETWEEN date(?) AND date(?)
                """,
                (start.isoformat(), end.isoformat()),
            ).fetchone()
            return float(row["total"]) if row else 0.0

    def get_revenue_by_date_range(self, start_date: str, end_date: str) -> list[dict[str, Any]]:
        """Return revenue breakdown by day in a date range."""

        with self.get_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT payment_date AS date, COALESCE(SUM(amount), 0) AS total
                FROM payments
                WHERE date(payment_date) BETWEEN date(?) AND date(?)
                GROUP BY payment_date
                ORDER BY payment_date ASC
                """,
                (start_date, end_date),
            )
            return [dict(r) for r in cur.fetchall()]

    def get_subscription_type_stats(self) -> list[dict[str, Any]]:
        """Return statistics per subscription type."""

        with self.get_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT st.id,
                       st.name_ar,
                       st.name_en,
                       COUNT(s.id) AS subscriptions_count,
                       COALESCE(SUM(s.amount_paid), 0) AS revenue
                FROM subscription_types st
                LEFT JOIN subscriptions s ON s.subscription_type_id = st.id
                GROUP BY st.id
                ORDER BY revenue DESC
                """
            )
            return [dict(r) for r in cur.fetchall()]

    def get_dashboard_stats(self) -> dict[str, Any]:
        """Return key dashboard statistics."""

        self.check_and_update_expired_subscriptions()

        today = _today_str()
        dt = date.today()
        month_start = date(dt.year, dt.month, 1).isoformat()

        with self.get_connection() as conn:
            cur = conn.cursor()

            total_members = cur.execute("SELECT COUNT(*) AS c FROM members").fetchone()["c"]
            active_members = cur.execute("SELECT COUNT(*) AS c FROM members WHERE status = 'active'").fetchone()["c"]

            expiring_soon = cur.execute(
                """
                SELECT COUNT(*) AS c
                FROM subscriptions
                WHERE status = 'active'
                  AND date(end_date) BETWEEN date(?) AND date(?)
                """,
                (today, (date.today() + timedelta(days=7)).isoformat()),
            ).fetchone()["c"]

            expired_subscriptions = cur.execute(
                """
                SELECT COUNT(*) AS c
                FROM subscriptions
                WHERE status = 'expired'
                """
            ).fetchone()["c"]

            today_check_ins = cur.execute(
                """
                SELECT COUNT(*) AS c
                FROM attendance
                WHERE date(check_in) = date(?)
                """,
                (today,),
            ).fetchone()["c"]

            monthly_revenue = cur.execute(
                """
                SELECT COALESCE(SUM(amount), 0) AS total
                FROM payments
                WHERE date(payment_date) >= date(?)
                """,
                (month_start,),
            ).fetchone()["total"]

            new_members_this_month = cur.execute(
                """
                SELECT COUNT(*) AS c
                FROM members
                WHERE date(join_date) >= date(?)
                """,
                (month_start,),
            ).fetchone()["c"]

        return {
            "total_members": int(total_members),
            "active_members": int(active_members),
            "expiring_soon": int(expiring_soon),
            "expired_subscriptions": int(expired_subscriptions),
            "today_check_ins": int(today_check_ins),
            "monthly_revenue": float(monthly_revenue),
            "new_members_this_month": int(new_members_this_month),
        }

    # ------------------------------
    # Utility Methods
    # ------------------------------

    def check_and_update_expired_subscriptions(self) -> tuple[bool, str]:
        """Mark subscriptions as expired if end_date < today and status is active."""

        try:
            with self.get_connection() as conn:
                cur = conn.cursor()
                cur.execute(
                    """
                    UPDATE subscriptions
                    SET status = 'expired', updated_at = ?
                    WHERE status = 'active' AND date(end_date) < date(?)
                    """,
                    (_now_dt_str(), _today_str()),
                )
                conn.commit()
                return True, "Expired subscriptions updated"
        except Exception as e:
            return False, f"Error updating expired subscriptions: {e}"

    def backup_database(self) -> tuple[bool, str, Optional[Path]]:
        """Create a database backup in BACKUPS_DIR.

        Returns: (success, message, backup_path)
        """

        try:
            config.init_directories()
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = config.BACKUPS_DIR / f"gym_database_{ts}.db"

            # Use SQLite backup API for consistency.
            with self.get_connection() as src:
                dest = sqlite3.connect(str(backup_path))
                try:
                    src.backup(dest)
                    dest.commit()
                finally:
                    dest.close()

            # Apply retention (simple: keep only newest MAX_BACKUPS)
            backups = sorted(config.BACKUPS_DIR.glob("gym_database_*.db"), key=lambda p: p.stat().st_mtime, reverse=True)
            for old in backups[config.MAX_BACKUPS :]:
                try:
                    old.unlink(missing_ok=True)
                except Exception:
                    pass

            # Apply retention days
            cutoff = datetime.now() - timedelta(days=int(config.BACKUP_RETENTION_DAYS))
            for b in backups:
                try:
                    if datetime.fromtimestamp(b.stat().st_mtime) < cutoff:
                        b.unlink(missing_ok=True)
                except Exception:
                    pass

            return True, "Backup created successfully", backup_path
        except Exception as e:
            return False, f"Error creating backup: {e}", None

    def get_settings(self, key: str) -> str | None:
        """Return a setting value by key."""

        with self.get_connection() as conn:
            row = conn.execute("SELECT value FROM settings WHERE key = ? LIMIT 1", (key,)).fetchone()
            return str(row["value"]) if row and row["value"] is not None else None

    def set_settings(self, key: str, value: str) -> tuple[bool, str]:
        """Set a setting value (insert or update)."""

        try:
            now = _now_dt_str()
            with self.get_connection() as conn:
                conn.execute(
                    """
                    INSERT INTO settings (key, value, updated_at)
                    VALUES (?, ?, ?)
                    ON CONFLICT(key) DO UPDATE SET
                        value = excluded.value,
                        updated_at = excluded.updated_at
                    """,
                    (key, value, now),
                )
                conn.commit()
                return True, "Setting saved"
        except Exception as e:
            return False, f"Error saving setting: {e}"

    def get_app_data_counts(self) -> dict[str, int]:
        if not self.db_path.exists():
            return {"members": 0, "subscriptions": 0, "payments": 0, "attendance": 0, "expenses": 0}

        with self.get_connection() as conn:
            cur = conn.cursor()

            def count_table(name: str) -> int:
                try:
                    row = cur.execute(f"SELECT COUNT(*) AS c FROM {name}").fetchone()
                    return int(row["c"]) if row and row["c"] is not None else 0
                except Exception:
                    return 0

            return {
                "members": count_table("members"),
                "subscriptions": count_table("subscriptions"),
                "payments": count_table("payments"),
                "attendance": count_table("attendance"),
                "expenses": count_table("expenses"),
            }

    def wipe_all_app_data(self) -> tuple[bool, str]:
        if not self.db_path.exists():
            return False, "Database not found"

        tables = ["payments", "attendance", "subscriptions", "expenses", "members"]
        try:
            with self.get_connection() as conn:
                cur = conn.cursor()
                cur.execute("PRAGMA foreign_keys = OFF;")

                for t in tables:
                    try:
                        cur.execute(f"DELETE FROM {t}")
                    except Exception:
                        pass

                try:
                    seqs = ",".join(["?"] * len(tables))
                    cur.execute(f"DELETE FROM sqlite_sequence WHERE name IN ({seqs})", tuple(tables))
                except Exception:
                    pass

                cur.execute("PRAGMA foreign_keys = ON;")
                conn.commit()

            return True, "All data deleted"
        except Exception as e:
            return False, f"Error deleting data: {e}"


if __name__ == "__main__":
    db = DatabaseManager()
    print("Database initialized successfully!")
    stats = db.get_dashboard_stats()
    print(f"Stats: {stats}")
