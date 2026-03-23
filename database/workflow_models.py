import json
import secrets
from datetime import datetime, timedelta

from database.db import get_connection


def _now_iso() -> str:
    return datetime.now().isoformat()


def _to_json(value) -> str:
    return json.dumps(value or {}, ensure_ascii=False)


def _from_json(value, default):
    if not value:
        return default
    if isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(value)
    except Exception:
        return default


def _workflow_row(row) -> dict:
    item = dict(row)
    item['definition'] = _from_json(item.pop('definition_json', None), {'nodes': [], 'edges': []})
    item['trigger'] = _from_json(item.pop('trigger_json', None), {})
    return item


def _run_row(row) -> dict:
    item = dict(row)
    item['trigger_payload'] = _from_json(item.get('trigger_payload'), {})
    return item


def _step_row(row) -> dict:
    item = dict(row)
    item['input'] = _from_json(item.pop('input_json', None), {})
    item['output'] = _from_json(item.pop('output_json', None), {})
    return item


class WorkflowModel:
    @staticmethod
    def create(payload: dict) -> int:
        now = _now_iso()
        trigger = payload.get('trigger_json', payload.get('trigger', {})) or {}
        definition = payload.get('definition_json', payload.get('definition', {'nodes': [], 'edges': []})) or {'nodes': [], 'edges': []}
        webhook_token = payload.get('webhook_token') or (secrets.token_urlsafe(18) if trigger.get('type') == 'webhook' else None)
        next_run_at = payload.get('next_run_at')
        if not next_run_at and trigger.get('type') == 'schedule' and trigger.get('enabled'):
            interval = int(trigger.get('interval_seconds') or 0)
            next_run_at = (datetime.now() + timedelta(seconds=max(interval, 0))).isoformat() if interval > 0 else now

        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            '''
            INSERT INTO workflows
            (name, description, category, status, definition_json, trigger_json, version, webhook_token, next_run_at, last_run_at, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''',
            (
                payload.get('name', '未命名工作流'),
                payload.get('description', ''),
                payload.get('category', 'system'),
                payload.get('status', 'draft'),
                _to_json(definition),
                _to_json(trigger),
                int(payload.get('version', 1) or 1),
                webhook_token,
                next_run_at,
                payload.get('last_run_at'),
                now,
                now,
            ),
        )
        workflow_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return workflow_id

    @staticmethod
    def list_all(limit: int = 100) -> list[dict]:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM workflows ORDER BY updated_at DESC LIMIT ?', (limit,))
        rows = cursor.fetchall()
        conn.close()
        return [_workflow_row(row) for row in rows]

    @staticmethod
    def get(workflow_id: int) -> dict | None:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM workflows WHERE id = ?', (workflow_id,))
        row = cursor.fetchone()
        conn.close()
        return _workflow_row(row) if row else None

    @staticmethod
    def get_by_webhook_token(token: str) -> dict | None:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM workflows WHERE webhook_token = ? AND status = ?', (token, 'active'))
        row = cursor.fetchone()
        conn.close()
        return _workflow_row(row) if row else None

    @staticmethod
    def update(workflow_id: int, payload: dict) -> dict | None:
        current = WorkflowModel.get(workflow_id)
        if not current:
            return None

        trigger = payload.get('trigger_json', payload.get('trigger', current.get('trigger', {}))) or current.get('trigger', {})
        definition = payload.get('definition_json', payload.get('definition', current.get('definition', {'nodes': [], 'edges': []}))) or current.get('definition', {'nodes': [], 'edges': []})
        status = payload.get('status', current.get('status', 'draft'))
        webhook_token = current.get('webhook_token')
        if trigger.get('type') == 'webhook' and not webhook_token:
            webhook_token = secrets.token_urlsafe(18)

        next_run_at = payload.get('next_run_at', current.get('next_run_at'))
        if status == 'active' and trigger.get('type') == 'schedule' and trigger.get('enabled') and not next_run_at:
            interval = int(trigger.get('interval_seconds') or 0)
            next_run_at = (datetime.now() + timedelta(seconds=max(interval, 0))).isoformat() if interval > 0 else _now_iso()

        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            '''
            UPDATE workflows
            SET name = ?, description = ?, category = ?, status = ?, definition_json = ?, trigger_json = ?, version = ?, webhook_token = ?, next_run_at = ?, updated_at = ?
            WHERE id = ?
            ''',
            (
                payload.get('name', current.get('name', '未命名工作流')),
                payload.get('description', current.get('description', '')),
                payload.get('category', current.get('category', 'system')),
                status,
                _to_json(definition),
                _to_json(trigger),
                int(payload.get('version', current.get('version', 1)) or 1),
                webhook_token,
                next_run_at,
                _now_iso(),
                workflow_id,
            ),
        )
        conn.commit()
        conn.close()
        return WorkflowModel.get(workflow_id)

    @staticmethod
    def publish(workflow_id: int) -> dict | None:
        workflow = WorkflowModel.get(workflow_id)
        if not workflow:
            return None
        return WorkflowModel.update(workflow_id, {'status': 'active'})

    @staticmethod
    def delete(workflow_id: int) -> bool:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('DELETE FROM workflow_run_steps WHERE run_id IN (SELECT id FROM workflow_runs WHERE workflow_id = ?)', (workflow_id,))
        cursor.execute('DELETE FROM workflow_runs WHERE workflow_id = ?', (workflow_id,))
        cursor.execute('DELETE FROM workflow_webhooks WHERE workflow_id = ?', (workflow_id,))
        cursor.execute('DELETE FROM workflows WHERE id = ?', (workflow_id,))
        deleted = cursor.rowcount > 0
        conn.commit()
        conn.close()
        return deleted

    @staticmethod
    def list_due_workflows(now_iso: str | None = None) -> list[dict]:
        now_iso = now_iso or _now_iso()
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            '''
            SELECT * FROM workflows
            WHERE status = 'active'
              AND next_run_at IS NOT NULL
              AND next_run_at <= ?
            ORDER BY next_run_at ASC, id ASC
            ''',
            (now_iso,),
        )
        rows = cursor.fetchall()
        conn.close()
        result = []
        for row in rows:
            item = _workflow_row(row)
            trigger = item.get('trigger', {})
            if trigger.get('type') == 'schedule' and trigger.get('enabled'):
                result.append(item)
        return result

    @staticmethod
    def mark_run_scheduled(workflow_id: int, next_run_at: str | None = None, last_run_at: str | None = None):
        workflow = WorkflowModel.get(workflow_id)
        if not workflow:
            return
        trigger = workflow.get('trigger', {})
        interval = int(trigger.get('interval_seconds') or 0)
        computed_next = next_run_at
        if computed_next is None and interval > 0:
            computed_next = (datetime.now() + timedelta(seconds=interval)).isoformat()
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            'UPDATE workflows SET last_run_at = ?, next_run_at = ?, updated_at = ? WHERE id = ?',
            (last_run_at or _now_iso(), computed_next, _now_iso(), workflow_id),
        )
        conn.commit()
        conn.close()

    @staticmethod
    def get_runs(workflow_id: int, limit: int = 50) -> list[dict]:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            'SELECT * FROM workflow_runs WHERE workflow_id = ? ORDER BY id DESC LIMIT ?',
            (workflow_id, limit),
        )
        rows = cursor.fetchall()
        conn.close()
        return [_run_row(row) for row in rows]


class WorkflowRunModel:
    @staticmethod
    def create_run(workflow_id: int, trigger_type: str, trigger_payload: dict | None = None, status: str = 'running') -> int:
        now = _now_iso()
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            '''
            INSERT INTO workflow_runs
            (workflow_id, trigger_type, trigger_payload, status, started_at, summary, error_message)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ''',
            (workflow_id, trigger_type, _to_json(trigger_payload or {}), status, now, '', ''),
        )
        run_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return run_id

    @staticmethod
    def finish_run(run_id: int, status: str, summary: str = '', error_message: str = ''):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            'UPDATE workflow_runs SET status = ?, ended_at = ?, summary = ?, error_message = ? WHERE id = ?',
            (status, _now_iso(), summary, error_message, run_id),
        )
        conn.commit()
        conn.close()

    @staticmethod
    def get_run(run_id: int) -> dict | None:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM workflow_runs WHERE id = ?', (run_id,))
        row = cursor.fetchone()
        conn.close()
        return _run_row(row) if row else None

    @staticmethod
    def add_step(run_id: int, node_id: str, node_type: str, node_name: str, status: str = 'running', input_payload: dict | None = None, output_payload: dict | None = None, error_message: str = '') -> int:
        now = _now_iso()
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            '''
            INSERT INTO workflow_run_steps
            (run_id, node_id, node_type, node_name, status, input_json, output_json, started_at, ended_at, error_message)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''',
            (
                run_id,
                node_id,
                node_type,
                node_name,
                status,
                _to_json(input_payload or {}),
                _to_json(output_payload or {}),
                now,
                now if status in ('success', 'failed', 'skipped') else None,
                error_message,
            ),
        )
        step_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return step_id


    @staticmethod
    def update_step(step_id: int, status: str, output_payload: dict | None = None, error_message: str = ''):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            'UPDATE workflow_run_steps SET status = ?, output_json = ?, ended_at = ?, error_message = ? WHERE id = ?',
            (status, _to_json(output_payload or {}), _now_iso(), error_message, step_id),
        )
        conn.commit()
        conn.close()

    @staticmethod
    def get_steps(run_id: int) -> list[dict]:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM workflow_run_steps WHERE run_id = ? ORDER BY id ASC', (run_id,))
        rows = cursor.fetchall()
        conn.close()
        return [_step_row(row) for row in rows]


class WorkflowWebhookModel:
    @staticmethod
    def ensure_token(workflow_id: int, enabled: bool = True) -> str:
        workflow = WorkflowModel.get(workflow_id)
        token = (workflow or {}).get('webhook_token') or secrets.token_urlsafe(18)
        secret = secrets.token_urlsafe(24)
        now = _now_iso()
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            '''
            INSERT INTO workflow_webhooks (workflow_id, token, enabled, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(workflow_id) DO UPDATE SET
                token = excluded.token,
                enabled = excluded.enabled,
                updated_at = excluded.updated_at
            ''',
            (workflow_id, token, 1 if enabled else 0, now, now),
        )
        conn.commit()
        conn.close()
        WorkflowModel.update(workflow_id, {'webhook_token': token})
        return token

    def get_by_token(token: str) -> dict | None:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM workflow_webhooks WHERE token = ? AND enabled = 1', (token,))
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None
