"""
Migration: add workflow tables for visual workflow orchestration (M1-02).

Creates:
- workflow_definition
- workflow_version
- workflow_run
- workflow_step_run
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

    # Fallback for non-sqlite URLs in local/dev execution.
    return (Path(__file__).resolve().parents[1] / "aimiguard.db").resolve()


def migrate(db_path: Optional[str] = None) -> None:
    target = _resolve_db_path(db_path)
    target.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(str(target))
    conn.execute("PRAGMA foreign_keys = ON")
    cursor = conn.cursor()

    try:
        cursor.executescript(
            """
            CREATE TABLE IF NOT EXISTS workflow_definition (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                workflow_key TEXT NOT NULL UNIQUE,
                name TEXT NOT NULL,
                description TEXT,
                definition_state TEXT NOT NULL DEFAULT 'DRAFT'
                    CHECK(definition_state IN ('DRAFT','VALIDATED','PUBLISHED','ARCHIVED')),
                latest_version INTEGER NOT NULL DEFAULT 1,
                published_version INTEGER,
                created_by TEXT,
                updated_by TEXT,
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                updated_at TEXT NOT NULL DEFAULT (datetime('now'))
            );

            CREATE INDEX IF NOT EXISTS idx_workflow_definition_state
                ON workflow_definition(definition_state);
            CREATE INDEX IF NOT EXISTS idx_workflow_definition_created_at
                ON workflow_definition(created_at);

            CREATE TABLE IF NOT EXISTS workflow_version (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                workflow_id INTEGER NOT NULL,
                version INTEGER NOT NULL,
                definition_state TEXT NOT NULL DEFAULT 'DRAFT'
                    CHECK(definition_state IN ('DRAFT','VALIDATED','PUBLISHED','ARCHIVED')),
                dsl_json TEXT NOT NULL,
                change_note TEXT,
                created_by TEXT,
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                updated_at TEXT NOT NULL DEFAULT (datetime('now')),
                FOREIGN KEY (workflow_id) REFERENCES workflow_definition(id) ON DELETE CASCADE,
                UNIQUE (workflow_id, version)
            );

            CREATE INDEX IF NOT EXISTS idx_workflow_version_workflow_id
                ON workflow_version(workflow_id);
            CREATE INDEX IF NOT EXISTS idx_workflow_version_version
                ON workflow_version(version);
            CREATE INDEX IF NOT EXISTS idx_workflow_version_state
                ON workflow_version(definition_state);
            CREATE INDEX IF NOT EXISTS idx_workflow_version_created_at
                ON workflow_version(created_at);

            CREATE TABLE IF NOT EXISTS workflow_run (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                workflow_id INTEGER NOT NULL,
                workflow_version_id INTEGER NOT NULL,
                run_state TEXT NOT NULL DEFAULT 'QUEUED'
                    CHECK(run_state IN ('QUEUED','RUNNING','RETRYING','SUCCESS','FAILED','MANUAL_REQUIRED','CANCELLED')),
                trigger_source TEXT,
                trigger_ref TEXT,
                input_payload TEXT,
                output_payload TEXT,
                context_json TEXT,
                trace_id TEXT NOT NULL,
                started_at TEXT,
                ended_at TEXT,
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                updated_at TEXT NOT NULL DEFAULT (datetime('now')),
                FOREIGN KEY (workflow_id) REFERENCES workflow_definition(id) ON DELETE CASCADE,
                FOREIGN KEY (workflow_version_id) REFERENCES workflow_version(id) ON DELETE RESTRICT
            );

            CREATE INDEX IF NOT EXISTS idx_workflow_run_workflow_id
                ON workflow_run(workflow_id);
            CREATE INDEX IF NOT EXISTS idx_workflow_run_workflow_version_id
                ON workflow_run(workflow_version_id);
            CREATE INDEX IF NOT EXISTS idx_workflow_run_state
                ON workflow_run(run_state);
            CREATE INDEX IF NOT EXISTS idx_workflow_run_created_at
                ON workflow_run(created_at);
            CREATE INDEX IF NOT EXISTS idx_workflow_run_trace_id
                ON workflow_run(trace_id);

            CREATE TABLE IF NOT EXISTS workflow_step_run (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                workflow_run_id INTEGER NOT NULL,
                workflow_id INTEGER NOT NULL,
                workflow_version_id INTEGER NOT NULL,
                node_id TEXT NOT NULL,
                node_type TEXT NOT NULL,
                step_state TEXT NOT NULL DEFAULT 'QUEUED'
                    CHECK(step_state IN ('QUEUED','RUNNING','RETRYING','SUCCESS','FAILED','MANUAL_REQUIRED','CANCELLED')),
                attempt INTEGER NOT NULL DEFAULT 1,
                input_payload TEXT,
                output_payload TEXT,
                error_message TEXT,
                trace_id TEXT NOT NULL,
                started_at TEXT,
                ended_at TEXT,
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                updated_at TEXT NOT NULL DEFAULT (datetime('now')),
                FOREIGN KEY (workflow_run_id) REFERENCES workflow_run(id) ON DELETE CASCADE,
                FOREIGN KEY (workflow_id) REFERENCES workflow_definition(id) ON DELETE CASCADE,
                FOREIGN KEY (workflow_version_id) REFERENCES workflow_version(id) ON DELETE RESTRICT,
                UNIQUE (workflow_run_id, node_id, attempt)
            );

            CREATE INDEX IF NOT EXISTS idx_workflow_step_run_run_id
                ON workflow_step_run(workflow_run_id);
            CREATE INDEX IF NOT EXISTS idx_workflow_step_run_workflow_id
                ON workflow_step_run(workflow_id);
            CREATE INDEX IF NOT EXISTS idx_workflow_step_run_workflow_version_id
                ON workflow_step_run(workflow_version_id);
            CREATE INDEX IF NOT EXISTS idx_workflow_step_run_state
                ON workflow_step_run(step_state);
            CREATE INDEX IF NOT EXISTS idx_workflow_step_run_created_at
                ON workflow_step_run(created_at);
            CREATE INDEX IF NOT EXISTS idx_workflow_step_run_trace_id
                ON workflow_step_run(trace_id);
            """
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    migrate()
