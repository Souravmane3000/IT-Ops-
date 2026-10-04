#!/usr/bin/env python3
"""Manual test helper: start Alex run and poll until HITL/terminal."""

from __future__ import annotations

import json
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

API = "http://localhost:8000"
GOAL = (
    "Onboard Alex, who is joining as a Marketing Manager. "
    "Give Alex the applications required by the company's access policy, "
    "but ask me for approval before granting any privileged access."
)


def post_json(path: str, payload: dict) -> dict:
    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        API + path,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode())


def get_json(path: str) -> dict:
    with urllib.request.urlopen(API + path) as resp:
        return json.loads(resp.read().decode())


def main() -> None:
    created = post_json("/runs", {"goal": GOAL})
    run_id = created["run_id"]
    print(f"RUN_ID={run_id} status={created['status']}")
    Path(sys.argv[1] if len(sys.argv) > 1 else "run_id.txt").write_text(run_id, encoding="utf-8")

    for i in range(90):
        time.sleep(3)
        run = get_json(f"/runs/{run_id}")
        acts = ", ".join(
            f"{a.get('application_name')}:{a.get('status')}" for a in run.get("actions") or []
        )
        print(f"t={(i+1)*3}s status={run['status']} | {acts}")
        if run["status"] == "awaiting_approval":
            print("HITL_PAUSE")
            print(json.dumps(run, indent=2))
            return
        if run["status"] in {"complete", "failed", "blocked"}:
            print(f"TERMINAL={run['status']} err={run.get('error')}")
            print(json.dumps(run, indent=2))
            return
    print("TIMEOUT")


if __name__ == "__main__":
    main()
