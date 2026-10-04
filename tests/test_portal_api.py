from fastapi.testclient import TestClient

from backend.main import app


def test_health_and_portal(temp_db):
    client = TestClient(app)
    assert client.get("/health").json()["status"] == "ok"

    employees = client.get("/portal/employees").json()
    assert any(e["name"] == "Alex" for e in employees)
    assert any(e["name"] == "Priya" for e in employees)

    apps = client.get("/portal/applications").json()
    assert any(a["name"] == "CRM" and a["fails_on_grant"] for a in apps)

    fail = client.post("/portal/employees/emp_alex/applications/app_crm/grant")
    body = fail.json()
    assert body["success"] is False

    ok = client.post("/portal/employees/emp_alex/applications/app_github/grant")
    assert ok.json()["success"] is True
