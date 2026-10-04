#!/usr/bin/env python3
"""Reset domain DB (and optionally checkpoints) then reseed."""

from __future__ import annotations

import runpy
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.config import CHECKPOINT_DB_PATH, EVIDENCE_DIR, IT_OPS_DB_PATH


def _safe_unlink(path: Path) -> None:
    if not path.exists():
        return
    try:
        path.unlink()
        print(f"Removed {path}")
    except PermissionError:
        # Common on Windows when uvicorn holds the LangGraph checkpoint connection open.
        print(
            f"Warning: could not remove {path} (file in use). "
            "Domain seed will still proceed; restart the backend to fully clear checkpoints."
        )


def main() -> None:
    _safe_unlink(IT_OPS_DB_PATH)
    _safe_unlink(CHECKPOINT_DB_PATH)

    if EVIDENCE_DIR.exists():
        for child in EVIDENCE_DIR.iterdir():
            if child.name == ".gitkeep":
                continue
            if child.is_dir():
                shutil.rmtree(child)
            else:
                child.unlink()
        print(f"Cleared evidence under {EVIDENCE_DIR}")

    runpy.run_path(str(ROOT / "scripts" / "seed_db.py"), run_name="__main__")
    print("Reset complete.")


if __name__ == "__main__":
    main()
