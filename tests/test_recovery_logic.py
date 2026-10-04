from backend.config import MAX_RECOVERY_ATTEMPTS
from backend.db.connection import get_connection
from backend.db import repository as repo
from backend.tools.domain import check_permission


def test_permission_check_and_recovery_bound(temp_db):
    assert MAX_RECOVERY_ATTEMPTS == 1
    with get_connection() as conn:
        repo.grant_application(conn, "emp_alex", "app_github")
    assert check_permission("emp_alex", "app_github")["granted"] is True
    assert check_permission("emp_alex", "app_slack")["granted"] is False
