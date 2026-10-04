"""Portal data APIs — consumed by the Next.js synthetic portal UI."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from backend.db.connection import get_connection
from backend.db import repository as repo

router = APIRouter(prefix="/portal", tags=["portal"])


class GrantResponse(BaseModel):
    success: bool
    employee_id: str | None = None
    application_id: str | None = None
    status: str | None = None
    error: str | None = None
    already_granted: bool | None = None


@router.get("/employees")
def get_employees():
    with get_connection() as conn:
        return repo.list_employees(conn)


@router.get("/employees/{employee_id}")
def get_employee(employee_id: str):
    with get_connection() as conn:
        employee = repo.get_employee(conn, employee_id)
        if not employee:
            raise HTTPException(status_code=404, detail="Employee not found")
        permissions = repo.list_permissions_for_employee(conn, employee_id)
        applications = repo.list_applications(conn)
        policies = repo.get_policies_for_role(conn, employee["role_id"])
        return {
            **employee,
            "permissions": permissions,
            "applications": applications,
            "policy_applications": policies,
        }


@router.get("/applications")
def get_applications():
    with get_connection() as conn:
        return repo.list_applications(conn)


@router.get("/policies")
def get_policies():
    with get_connection() as conn:
        return repo.list_policies(conn)


@router.get("/audit")
def get_audit(limit: int = Query(default=100, ge=1, le=500)):
    with get_connection() as conn:
        return repo.list_audit(conn, limit=limit)


@router.post(
    "/employees/{employee_id}/applications/{application_id}/grant",
    response_model=GrantResponse,
)
def grant_application(
    employee_id: str,
    application_id: str,
    run_id: str | None = Query(default=None),
):
    """Authoritative grant mutation for the portal UI only."""
    with get_connection() as conn:
        result = repo.grant_application(
            conn, employee_id, application_id, run_id=run_id
        )
    if result.get("error") == "Employee not found":
        raise HTTPException(status_code=404, detail=result["error"])
    if result.get("error") == "Application not found":
        raise HTTPException(status_code=404, detail=result["error"])
    return GrantResponse(**result)
