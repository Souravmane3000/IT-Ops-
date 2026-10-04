from backend.tools.domain import create_action_plan, find_employee, get_access_policy


def test_marketing_and_finance_policies_differ(temp_db):
    marketing = get_access_policy("role_marketing")
    finance = get_access_policy("role_finance")
    assert len(marketing) >= 3
    assert len(finance) >= 1
    m_apps = {p["application_id"] for p in marketing}
    f_apps = {p["application_id"] for p in finance}
    assert m_apps != f_apps
    assert any(p["privileged"] for p in marketing)


def test_action_plan_persists(temp_db):
    from backend.db.connection import get_connection
    from backend.db import repository as repo

    with get_connection() as conn:
        repo.create_run(conn, "run_plan2", "Onboard Alex")
    alex = find_employee("Alex")
    assert alex is not None
    plan = create_action_plan(
        run_id="run_plan2",
        employee_id=alex["id"],
        role_id=alex["role_id"],
    )
    assert len(plan) == 4
    assert any(p["requires_approval"] for p in plan)
    assert any(p["application_id"] == "app_crm" for p in plan)
