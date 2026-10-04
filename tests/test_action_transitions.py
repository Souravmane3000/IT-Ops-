from backend.db.connection import get_connection
from backend.db import repository as repo


def test_valid_and_invalid_transitions(temp_db):
    with get_connection() as conn:
        repo.create_run(conn, "run_test", "goal")
        repo.create_action(
            conn,
            action_id="act_001",
            run_id="run_test",
            employee_id="emp_alex",
            application_id="app_github",
        )
        repo.transition_action(conn, "act_001", "running")
        repo.transition_action(conn, "act_001", "succeeded")
        action = repo.get_action(conn, "act_001")
        assert action["status"] == "succeeded"

        try:
            repo.transition_action(conn, "act_001", "running")
            assert False, "should reject invalid transition"
        except ValueError:
            pass


def test_reject_path(temp_db):
    with get_connection() as conn:
        repo.create_run(conn, "run_rej", "goal")
        repo.create_action(
            conn,
            action_id="act_priv",
            run_id="run_rej",
            employee_id="emp_alex",
            application_id="app_admin",
            requires_approval=True,
        )
        repo.transition_action(conn, "act_priv", "running")
        repo.transition_action(conn, "act_priv", "awaiting_approval")
        repo.transition_action(
            conn, "act_priv", "rejected", approval_decision="rejected"
        )
        repo.transition_action(conn, "act_priv", "skipped")
        action = repo.get_action(conn, "act_priv")
        assert action["status"] == "skipped"
        assert action["approval_decision"] == "rejected"
