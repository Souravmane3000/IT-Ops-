from backend.db.connection import get_connection
from backend.db import repository as repo


def test_controlled_failure_then_retry_succeeds(temp_db):
    with get_connection() as conn:
        first = repo.grant_application(conn, "emp_alex", "app_crm")
        assert first["success"] is False
        app = repo.get_application(conn, "app_crm")
        assert app["fail_remaining"] == 0

        second = repo.grant_application(conn, "emp_alex", "app_crm")
        assert second["success"] is True
        assert second["status"] == "granted"
        perm = repo.get_permission(conn, "emp_alex", "app_crm")
        assert perm["status"] == "granted"


def test_normal_grant(temp_db):
    with get_connection() as conn:
        result = repo.grant_application(conn, "emp_alex", "app_github")
        assert result["success"] is True
        perm = repo.get_permission(conn, "emp_alex", "app_github")
        assert perm["status"] == "granted"
