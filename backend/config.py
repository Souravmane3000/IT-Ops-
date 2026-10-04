"""Environment configuration for the IT Ops backend."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parent.parent
load_dotenv(ROOT_DIR / ".env")


def _path_from_env(key: str, default: str) -> Path:
    raw = os.getenv(key, default)
    path = Path(raw)
    if not path.is_absolute():
        path = ROOT_DIR / path
    return path


OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

IT_OPS_DB_PATH = _path_from_env("IT_OPS_DB_PATH", "./data/it_ops.db")
CHECKPOINT_DB_PATH = _path_from_env("CHECKPOINT_DB_PATH", "./data/checkpoints.db")

PLAYWRIGHT_BASE_URL = os.getenv("PLAYWRIGHT_BASE_URL", "http://localhost:3000")
PLAYWRIGHT_HEADLESS = os.getenv("PLAYWRIGHT_HEADLESS", "false").lower() in {
    "1",
    "true",
    "yes",
}

CORS_ORIGINS = [
    origin.strip()
    for origin in os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",")
    if origin.strip()
]

EVIDENCE_DIR = ROOT_DIR / "evidence"
MAX_RECOVERY_ATTEMPTS = 1
