from backend.db.connection import get_connection
from backend.db import repository as repo
from backend.tools.domain import create_action_plan


def test_seed_supports_variation(temp_db):
    with get_connection() as conn:
        employees = repo.list_employees(conn)
        names = {e["name"] for e in employees}
        assert {"Alex", "Priya"} <= names
        marketing = repo.get_policies_for_role(conn, "role_marketing")
        finance = repo.get_policies_for_role(conn, "role_finance")
        assert {p["application_id"] for p in marketing} != {
            p["application_id"] for p in finance
        }


def test_create_plans_differ_by_role(temp_db):
    with get_connection() as conn:
        repo.create_run(conn, "run_alex", "Onboard Alex")
        repo.create_run(conn, "run_priya", "Onboard Priya")
    alex_plan = create_action_plan(
        run_id="run_alex", employee_id="emp_alex", role_id="role_marketing"
    )
    priya_plan = create_action_plan(
        run_id="run_priya", employee_id="emp_priya", role_id="role_finance"
    )
    assert [p["application_id"] for p in alex_plan] != [
        p["application_id"] for p in priya_plan
    ]
    assert any(p["requires_approval"] for p in alex_plan)
    assert not any(p["requires_approval"] for p in priya_plan)
