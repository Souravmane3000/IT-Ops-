"""Run lifecycle APIs + SSE + HITL resume."""

from __future__ import annotations

import asyncio
import json
import uuid
from concurrent.futures import ThreadPoolExecutor

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sse_starlette.sse import EventSourceResponse

from backend.agent.graph import resume_run, start_run
import backend.config as config
from backend.db.connection import get_connection
from backend.db import repository as repo
from backend.evidence.writer import list_evidence_files, read_result_json
from backend.events.publisher import ExecutionEvent, get_event_publisher

router = APIRouter(tags=["runs"])
_executor = ThreadPoolExecutor(max_workers=2)


class CreateRunRequest(BaseModel):
    goal: str = Field(min_length=1)


class CreateRunResponse(BaseModel):
    run_id: str
    status: str


def _new_run_id() -> str:
    return f"run_{uuid.uuid4().hex}"


def _run_graph_start(run_id: str, goal: str) -> None:
    try:
        start_run(run_id, goal)
    except Exception as exc:  # noqa: BLE001
        # interrupt() raises GraphInterrupt which may surface here depending on version
        from langgraph.errors import GraphInterrupt

        if isinstance(exc, GraphInterrupt):
            return
        # Some versions raise differently — check message
        if "Interrupt" in type(exc).__name__:
            return
        with get_connection() as conn:
            repo.update_run(
                conn, run_id, status="failed", error=str(exc), completed=True
            )
        get_event_publisher().publish_simple(
            run_id, "run_failed", str(exc), status="error"
        )


def _run_graph_resume(run_id: str, decision: str) -> None:
    try:
        resume_run(run_id, decision)
    except Exception as exc:  # noqa: BLE001
        if "Interrupt" in type(exc).__name__:
            return
        try:
            from langgraph.errors import GraphInterrupt

            if isinstance(exc, GraphInterrupt):
                return
        except Exception:  # noqa: BLE001
            pass
        with get_connection() as conn:
            repo.update_run(
                conn, run_id, status="failed", error=str(exc), completed=True
            )
        get_event_publisher().publish_simple(
            run_id, "run_failed", str(exc), status="error"
        )


@router.post("/runs", response_model=CreateRunResponse)
async def create_run(body: CreateRunRequest, request: Request):
    goal = body.goal.strip()
    if not goal:
        raise HTTPException(status_code=400, detail="Goal is required")

    run_id = _new_run_id()
    with get_connection() as conn:
        repo.create_run(conn, run_id, goal)

    loop = asyncio.get_running_loop()
    get_event_publisher().set_loop(loop)
    loop.run_in_executor(_executor, _run_graph_start, run_id, goal)

    return CreateRunResponse(run_id=run_id, status="running")


@router.get("/runs/{run_id}")
def get_run(run_id: str):
    with get_connection() as conn:
        run = repo.get_run(conn, run_id)
        if not run:
            raise HTTPException(status_code=404, detail="Run not found")
        actions = repo.list_actions_for_run(conn, run_id)
        employee = (
            repo.get_employee(conn, run["employee_id"]) if run["employee_id"] else None
        )
    awaiting = next(
        (a for a in actions if a["status"] == "awaiting_approval"),
        None,
    )
    return {
        **run,
        "employee": employee,
        "actions": actions,
        "awaiting_approval": awaiting,
    }


@router.get("/runs/{run_id}/events")
async def run_events(run_id: str, request: Request):
    with get_connection() as conn:
        run = repo.get_run(conn, run_id)
        if not run:
            raise HTTPException(status_code=404, detail="Run not found")

    publisher = get_event_publisher()
    publisher.set_loop(asyncio.get_running_loop())
    queue = await publisher.subscribe(run_id)

    async def event_generator():
        try:
            while True:
                if await request.is_disconnected():
                    break
                try:
                    event: ExecutionEvent = await asyncio.wait_for(queue.get(), timeout=15.0)
                    yield {
                        "event": event.event_type,
                        "data": event.to_dict() if hasattr(event, "to_dict") else event,
                    }
                    # sse-starlette expects data as str or dict — convert
                except asyncio.TimeoutError:
                    yield {"event": "ping", "data": {"run_id": run_id}}
                    with get_connection() as conn:
                        current = repo.get_run(conn, run_id)
                    if current and current["status"] in {
                        "complete",
                        "failed",
                        "blocked",
                    }:
                        # final drain
                        while not queue.empty():
                            event = queue.get_nowait()
                            yield {"event": event.event_type, "data": event.to_dict()}
                        break
        finally:
            await publisher.unsubscribe(run_id, queue)

    async def adapted():
        async for item in event_generator():
            data = item["data"]
            if isinstance(data, dict):
                yield {"event": item["event"], "data": json.dumps(data)}
            else:
                yield item

    return EventSourceResponse(adapted())


@router.post("/runs/{run_id}/approve")
async def approve_run(run_id: str):
    with get_connection() as conn:
        run = repo.get_run(conn, run_id)
        if not run:
            raise HTTPException(status_code=404, detail="Run not found")
        actions = repo.list_actions_for_run(conn, run_id)
        awaiting = [a for a in actions if a["status"] == "awaiting_approval"]
        if not awaiting and run["status"] != "awaiting_approval":
            raise HTTPException(status_code=409, detail="Run is not awaiting approval")

    loop = asyncio.get_running_loop()
    get_event_publisher().set_loop(loop)
    loop.run_in_executor(_executor, _run_graph_resume, run_id, "approved")
    return {"status": "resuming", "decision": "approved"}


@router.post("/runs/{run_id}/reject")
async def reject_run(run_id: str):
    with get_connection() as conn:
        run = repo.get_run(conn, run_id)
        if not run:
            raise HTTPException(status_code=404, detail="Run not found")
        actions = repo.list_actions_for_run(conn, run_id)
        awaiting = [a for a in actions if a["status"] == "awaiting_approval"]
        if not awaiting and run["status"] != "awaiting_approval":
            raise HTTPException(status_code=409, detail="Run is not awaiting approval")

    loop = asyncio.get_running_loop()
    get_event_publisher().set_loop(loop)
    loop.run_in_executor(_executor, _run_graph_resume, run_id, "rejected")
    return {"status": "resuming", "decision": "rejected"}


@router.get("/runs/{run_id}/evidence")
def get_evidence(run_id: str):
    with get_connection() as conn:
        run = repo.get_run(conn, run_id)
        if not run:
            raise HTTPException(status_code=404, detail="Run not found")
    files = list_evidence_files(run_id)
    result = read_result_json(run_id)
    return {"run_id": run_id, "files": files, "result": result}


@router.get("/runs/{run_id}/evidence/{filename}")
def get_evidence_file(run_id: str, filename: str):
    path = config.EVIDENCE_DIR / run_id / filename
    if not path.exists() or not path.is_file():
        raise HTTPException(status_code=404, detail="Evidence file not found")
    # Prevent path traversal
    if path.resolve().parent != (config.EVIDENCE_DIR / run_id).resolve():
        raise HTTPException(status_code=400, detail="Invalid path")
    media = "application/json" if filename.endswith(".json") else "image/png"
    return FileResponse(path, media_type=media)
