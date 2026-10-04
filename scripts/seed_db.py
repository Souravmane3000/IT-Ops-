#!/usr/bin/env python3
"""Deterministic seed for the IT Ops domain database."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.db.connection import connect, get_db_path
from backend.db.schema import init_schema


def seed(conn) -> None:
    # Clear domain tables (preserve schema)
    for table in (
        "audit_log",
        "actions",
        "runs",
        "permissions",
        "access_policies",
        "applications",
        "employees",
        "roles",
    ):
        conn.execute(f"DELETE FROM {table}")

    roles = [
        ("role_marketing", "Marketing Manager"),
        ("role_finance", "Finance Analyst"),
    ]
    conn.executemany("INSERT INTO roles (id, name) VALUES (?, ?)", roles)

    employees = [
        ("emp_alex", "Alex", "role_marketing"),
        ("emp_priya", "Priya", "role_finance"),
    ]
    conn.executemany(
        "INSERT INTO employees (id, name, role_id) VALUES (?, ?, ?)", employees
    )

    # Architecture §8.3 illustrative applications for the primary demo path.
    # fail_remaining=1 enables one-shot controlled failure then safe retry.
    applications = [
        ("app_github", "GitHub", 0, 0, 0),
        ("app_slack", "Slack", 0, 0, 0),
        ("app_crm", "CRM", 0, 1, 1),
        ("app_admin", "Admin Console", 1, 0, 0),
    ]
    conn.executemany(
        """
        INSERT INTO applications (id, name, privileged, fails_on_grant, fail_remaining)
        VALUES (?, ?, ?, ?, ?)
        """,
        applications,
    )

    # Marketing: full primary demo set (permitted + failure + privileged)
    marketing_apps = ["app_github", "app_slack", "app_crm", "app_admin"]
    # Finance: minimal distinct set (adaptability without invented privileged workflow)
    finance_apps = ["app_github", "app_slack"]

    policy_rows = []
    for i, app_id in enumerate(marketing_apps, start=1):
        policy_rows.append((f"pol_mkt_{i}", "role_marketing", app_id, 1))
    for i, app_id in enumerate(finance_apps, start=1):
        policy_rows.append((f"pol_fin_{i}", "role_finance", app_id, 1))

    conn.executemany(
        """
        INSERT INTO access_policies (id, role_id, application_id, required)
        VALUES (?, ?, ?, ?)
        """,
        policy_rows,
    )
    conn.commit()


def main() -> None:
    db_path = get_db_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = connect(db_path)
    try:
        init_schema(conn)
        seed(conn)
        print(f"Seeded domain database at {db_path}")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
