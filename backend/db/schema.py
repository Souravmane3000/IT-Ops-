"""Domain database schema for it_ops.db."""

from __future__ import annotations

import sqlite3


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS roles (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS employees (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    role_id TEXT NOT NULL REFERENCES roles(id)
);

CREATE TABLE IF NOT EXISTS applications (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    privileged INTEGER NOT NULL DEFAULT 0,
    fails_on_grant INTEGER NOT NULL DEFAULT 0,
    fail_remaining INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS access_policies (
    id TEXT PRIMARY KEY,
    role_id TEXT NOT NULL REFERENCES roles(id),
    application_id TEXT NOT NULL REFERENCES applications(id),
    required INTEGER NOT NULL DEFAULT 1,
    UNIQUE(role_id, application_id)
);

CREATE TABLE IF NOT EXISTS permissions (
    id TEXT PRIMARY KEY,
    employee_id TEXT NOT NULL REFERENCES employees(id),
    application_id TEXT NOT NULL REFERENCES applications(id),
    status TEXT NOT NULL CHECK(status IN ('granted', 'revoked')),
    UNIQUE(employee_id, application_id)
);

CREATE TABLE IF NOT EXISTS runs (
    id TEXT PRIMARY KEY,
    goal TEXT NOT NULL,
    status TEXT NOT NULL,
    employee_id TEXT REFERENCES employees(id),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    completed_at TEXT,
    error TEXT
);

CREATE TABLE IF NOT EXISTS actions (
    id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL REFERENCES runs(id),
    employee_id TEXT NOT NULL REFERENCES employees(id),
    application_id TEXT NOT NULL REFERENCES applications(id),
    action_type TEXT NOT NULL,
    status TEXT NOT NULL,
    requires_approval INTEGER NOT NULL DEFAULT 0,
    approval_decision TEXT,
    recovery_attempts INTEGER NOT NULL DEFAULT 0,
    error TEXT,
    started_at TEXT,
    completed_at TEXT,
    details TEXT
);

CREATE TABLE IF NOT EXISTS audit_log (
    id TEXT PRIMARY KEY,
    run_id TEXT,
    employee_id TEXT,
    action TEXT NOT NULL,
    status TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    details TEXT
);
"""


def init_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA_SQL)
    conn.commit()
