#!/usr/bin/env python3
"""Start Priya variation run and poll to terminal status."""

from __future__ import annotations

import json
import time
import urllib.request

API = "http://127.0.0.1:8000"
GOAL = (
    "Onboard Priya as a Finance Analyst and give her the applications "
    "required by policy."
)


def main() -> None:
    req = urllib.request.Request(
        API + "/runs",
        data=json.dumps({"goal": GOAL}).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req) as resp:
        created = json.loads(resp.read().decode())
    print("CREATED", created)
    rid = created["run_id"]
    run: dict = {}
    for i in range(60):
        time.sleep(2)
        with urllib.request.urlopen(API + f"/runs/{rid}") as resp:
            run = json.loads(resp.read().decode())
        acts = ", ".join(
            f"{a.get('application_name')}:{a.get('status')}"
            for a in run.get("actions") or []
        )
        print(
            f"t={(i + 1) * 2}s status={run['status']} | {acts} err={run.get('error')}"
        )
        if run["status"] in {"complete", "failed", "blocked", "awaiting_approval"}:
            break
    emp = (run.get("employee") or {}).get("name")
    print("FINAL", run.get("status"), "employee", emp)


if __name__ == "__main__":
    main()
