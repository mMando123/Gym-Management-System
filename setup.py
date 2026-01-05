from __future__ import annotations

from pathlib import Path

from setuptools import find_packages, setup


BASE_DIR = Path(__file__).resolve().parent


def read_requirements() -> list[str]:
    req = BASE_DIR / "requirements.txt"
    if not req.exists():
        return []
    lines: list[str] = []
    for line in req.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        lines.append(line)
    return lines


setup(
    name="gym_management_system",
    version="1.0.0",
    description="نظام متكامل لإدارة النوادي الرياضية",
    long_description=(BASE_DIR / "README.md").read_text(encoding="utf-8") if (BASE_DIR / "README.md").exists() else "",
    long_description_content_type="text/markdown",
    author="[اسم المطور]",
    python_requires=">=3.8",
    # المشروع الحالي يعمل كوحدات (modules) في الجذر.
    # إذا قمت لاحقاً بإضافة مجلدات packages مثل views/models فسيتم اكتشافها تلقائياً.
    packages=find_packages(exclude=("tests", "tests.*")),
    py_modules=[
        "main",
        "config",
        "database",
        "utils",
        "login_window",
        "main_window",
        "members_frame",
        "subscriptions_frame",
        "payments_frame",
        "plans_frame",
        "reports_frame",
        "search_system",
        "notifications_system",
        "settings_manager",
        "settings_frame",
    ],
    include_package_data=True,
    install_requires=read_requirements(),
    entry_points={
        "console_scripts": [
            "gym_management=main:main",
        ]
    },
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: End Users/Desktop",
        "Topic :: Office/Business :: Financial :: Accounting",
        "Topic :: Office/Business :: Scheduling",
        "Topic :: Database",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Operating System :: Microsoft :: Windows",
        "License :: OSI Approved :: MIT License",
        "Natural Language :: Arabic",
    ],
    keywords="gym, management, ttkbootstrap, tkinter, sqlite, arabic, rtl",
)
