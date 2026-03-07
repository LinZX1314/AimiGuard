"""
Rollback migration: remove workflow tables created by add_workflow_tables_v1.py
"""
from __future__ import annotations

import os
import sqlite3
from pathlib import Path
from typing import Optional


def _resolve_db_path(db_path: Optional[str] = None) -> Path:
    if db_path:
        return Path(db_path)

    url = os.getenv("DATABASE_URL", "sqlite:///./aimiguard.db")
    if url.startswith("sqlite:///"):
        raw_path = url[len("sqlite:///") :]
        return Path(raw_path).resolve()

    return (Path(__file__).resolve().parents[1] / "aimiguard.db").resolve()


def rollback(db_path: Optional[str] = None) -> None:
    target = _resolve_db_path(db_path)
    target.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(str(target))
    cursor = conn.cursor()

    try:
        cursor.executescript(
            """
            DROP TABLE IF EXISTS workflow_step_run;
            DROP TABLE IF EXISTS workflow_run;
            DROP TABLE IF EXISTS workflow_version;
            DROP TABLE IF EXISTS workflow_definition;
            """
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    rollback()
