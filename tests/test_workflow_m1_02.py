import sqlite3
from pathlib import Path
from uuid import uuid4

from migrations.add_workflow_tables_v1 import migrate as migrate_workflow_tables
from migrations.rollback_workflow_tables_v1 import rollback as rollback_workflow_tables


WORKFLOW_TABLES = {
    "workflow_definition",
    "workflow_version",
    "workflow_run",
    "workflow_step_run",
}


def _list_tables(conn: sqlite3.Connection) -> set[str]:
    rows = conn.execute(
        """
        SELECT name
        FROM sqlite_master
        WHERE type = 'table'
        """
    ).fetchall()
    return {str(row[0]) for row in rows}


def _list_indexes(conn: sqlite3.Connection) -> set[str]:
    rows = conn.execute(
        """
        SELECT name
        FROM sqlite_master
        WHERE type = 'index'
        """
    ).fetchall()
    return {str(row[0]) for row in rows}


def test_workflow_tables_exist_in_metadata_created_db(test_db):
    conn = test_db.connection().connection
    table_names = _list_tables(conn)
    assert WORKFLOW_TABLES.issubset(table_names)


def test_workflow_migration_idempotent_and_rollback():
    db_path = Path(f"test_workflow_migration_{uuid4().hex}.db").resolve()

    try:
        migrate_workflow_tables(str(db_path))
        migrate_workflow_tables(str(db_path))

        conn = sqlite3.connect(str(db_path))
        try:
            table_names = _list_tables(conn)
            assert WORKFLOW_TABLES.issubset(table_names)

            index_names = _list_indexes(conn)
            assert "idx_workflow_run_trace_id" in index_names
            assert "idx_workflow_step_run_trace_id" in index_names
            assert "idx_workflow_version_workflow_id" in index_names
        finally:
            conn.close()

        rollback_workflow_tables(str(db_path))
        rollback_workflow_tables(str(db_path))

        conn = sqlite3.connect(str(db_path))
        try:
            table_names = _list_tables(conn)
            assert WORKFLOW_TABLES.isdisjoint(table_names)
        finally:
            conn.close()
    finally:
        if db_path.exists():
            db_path.unlink()
