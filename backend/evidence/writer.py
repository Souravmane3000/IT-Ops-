"""Local evidence directory writer."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import backend.config as config


def evidence_dir_for_run(run_id: str) -> Path:
    path = config.EVIDENCE_DIR / run_id
    path.mkdir(parents=True, exist_ok=True)
    return path


def screenshot_path(run_id: str, name: str) -> Path:
    directory = evidence_dir_for_run(run_id)
    if not name.endswith(".png"):
        name = f"{name}.png"
    return directory / name


def write_result_json(run_id: str, payload: dict[str, Any]) -> Path:
    path = evidence_dir_for_run(run_id) / "result.json"
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path


def list_evidence_files(run_id: str) -> list[dict[str, str]]:
    directory = config.EVIDENCE_DIR / run_id
    if not directory.exists():
        return []
    files = []
    for path in sorted(directory.iterdir()):
        if path.is_file():
            files.append({"name": path.name, "path": str(path)})
    return files


def read_result_json(run_id: str) -> dict[str, Any] | None:
    path = config.EVIDENCE_DIR / run_id / "result.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))
