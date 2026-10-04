"""Pytest fixtures with isolated temporary databases."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


@pytest.fixture()
def temp_db(tmp_path, monkeypatch):
    db_path = tmp_path / "it_ops.db"
    checkpoint = tmp_path / "checkpoints.db"
    monkeypatch.setenv("IT_OPS_DB_PATH", str(db_path))
    monkeypatch.setenv("CHECKPOINT_DB_PATH", str(checkpoint))

    # Reload config/db modules that cache paths
    import backend.config as config

    monkeypatch.setattr(config, "IT_OPS_DB_PATH", db_path)
    monkeypatch.setattr(config, "CHECKPOINT_DB_PATH", checkpoint)
    monkeypatch.setattr(config, "EVIDENCE_DIR", tmp_path / "evidence")
    (tmp_path / "evidence").mkdir(exist_ok=True)

    # Clear cached compiled graph between tests
    try:
        from backend.agent import graph as agent_graph

        agent_graph.get_compiled_graph.cache_clear()
    except Exception:
        pass

    from backend.db.connection import connect
    from backend.db.schema import init_schema
    from scripts.seed_db import seed

    conn = connect(db_path)
    init_schema(conn)
    seed(conn)
    conn.close()
    return db_path
