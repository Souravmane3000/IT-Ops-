#!/usr/bin/env python3
"""Approve/reject a run and poll to completion."""

from __future__ import annotations

import json
import sys
import time
import urllib.request
from pathlib import Path

API = "http://localhost:8000"


def req(method: str, path: str, payload: dict | None = None) -> dict:
    data = None if payload is None else json.dumps(payload).encode()
    request = urllib.request.Request(
        API + path,
        data=data,
        headers={"Content-Type": "application/json"} if payload is not None else {},
        method=method,
    )
    with urllib.request.urlopen(request) as resp:
        return json.loads(resp.read().decode())


def main() -> None:
    run_id = sys.argv[1] if len(sys.argv) > 1 else Path("run_id.txt").read_text(encoding="utf-8").strip()
    decision = sys.argv[2] if len(sys.argv) > 2 else "approve"
    path = f"/runs/{run_id}/approve" if decision == "approve" else f"/runs/{run_id}/reject"
    print(req("POST", path))
    for i in range(80):
        time.sleep(3)
        run = req("GET", f"/runs/{run_id}")
        acts = ", ".join(
            f"{a.get('application_name')}:{a.get('status')}" for a in run.get("actions") or []
        )
        print(f"t={(i+1)*3}s status={run['status']} | {acts}")
        if run["status"] in {"complete", "failed", "blocked"}:
            evidence = req("GET", f"/runs/{run_id}/evidence")
            print("TERMINAL", run["status"], run.get("error"))
            print("EVIDENCE_FILES", [f["name"] for f in evidence.get("files") or []])
            print("RESULT", json.dumps(evidence.get("result"), indent=2))
            return
    print("TIMEOUT")


if __name__ == "__main__":
    main()
