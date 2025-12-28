from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path
from typing import Any

import pandas as pd


def _connect(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def load_merged_dataframe(db_path: str) -> pd.DataFrame:
    with _connect(db_path) as conn:
        members = pd.read_sql_query("SELECT * FROM members", conn)
        subs = pd.read_sql_query(
            """
            SELECT s.*, st.name_ar AS subscription_name_ar, st.name_en AS subscription_name_en,
                   st.duration_months AS subscription_duration_months, st.price AS subscription_price
            FROM subscriptions s
            LEFT JOIN subscription_types st ON st.id = s.subscription_type_id
            """,
            conn,
        )
        payments = pd.read_sql_query(
            """
            SELECT p.*, s.start_date AS subscription_start_date, s.end_date AS subscription_end_date,
                   s.subscription_type_id AS subscription_type_id
            FROM payments p
            LEFT JOIN subscriptions s ON s.id = p.subscription_id
            """,
            conn,
        )
        attendance = pd.read_sql_query("SELECT * FROM attendance", conn)

    members = members.add_prefix("member_")
    subs = subs.add_prefix("sub_")
    payments = payments.add_prefix("pay_")
    attendance = attendance.add_prefix("att_")

    df = members

    if not subs.empty and "sub_member_id" in subs.columns and "member_id" in df.columns:
        df = df.merge(subs, how="left", left_on="member_id", right_on="sub_member_id")

    if not payments.empty and "pay_member_id" in payments.columns and "member_id" in df.columns:
        df = df.merge(payments, how="left", left_on="member_id", right_on="pay_member_id")

    if not attendance.empty and "att_member_id" in attendance.columns and "member_id" in df.columns:
        df = df.merge(attendance, how="left", left_on="member_id", right_on="att_member_id")

    for c in df.columns:
        try:
            if df[c].dtype == object:
                df[c] = df[c].astype("string")
        except Exception:
            pass

    return df


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db-path", required=True)
    args = ap.parse_args(argv)

    db_path = str(Path(args.db_path).resolve())

    try:
        import streamlit as st
    except Exception:
        raise SystemExit("streamlit غير مثبت. ثبته عبر: python -m pip install streamlit")

    st.set_page_config(page_title="التقارير الذكية", layout="wide")

    st.markdown(
        """
        <style>
        html, body, [class*='css']  { direction: rtl; text-align: right; font-family: Cairo, Arial, sans-serif; }
        </style>
        """,
        unsafe_allow_html=True,
    )

    st.title("التقارير الذكية (PyGWalker)")
    st.caption("اسحب وأسقط الحقول لإنشاء الرسوم، طبّق الفلاتر، واحفظ التحليلات.")

    if not Path(db_path).exists():
        st.error(f"ملف قاعدة البيانات غير موجود: {db_path}")
        return 1

    try:
        df = load_merged_dataframe(db_path)
    except Exception as e:
        st.error(f"فشل تحميل البيانات: {e}")
        return 1

    st.write(f"عدد الأعمدة: {len(df.columns)} | عدد الصفوف (بعد الدمج): {len(df)}")

    try:
        from pygwalker.api.streamlit import StreamlitRenderer

        renderer = StreamlitRenderer(df)
        renderer.explorer()
    except Exception as e:
        st.error(
            "تعذر تشغيل PyGWalker.\n\n"
            "إذا كنت تستخدم Python 3.13 على Windows فقد يفشل تثبيته بسبب quickjs.\n"
            "الحل العملي: استخدم Python 3.11/3.12 في بيئة منفصلة وثبّت فيها pygwalker.\n\n"
            f"تفاصيل الخطأ: {e}"
        )
        st.dataframe(df.head(50))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
