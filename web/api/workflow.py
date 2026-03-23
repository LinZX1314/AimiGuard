from flask import Blueprint, request
import hashlib
import hmac
import time
import json

from database.models import WorkflowModel, WorkflowRunModel
from workflow.engine import ensure_workflow_webhook, instantiate_template, list_templates, run_workflow_by_id, workflow_catalog
from .helpers import require_auth, ok, err, _body, _load_cfg


workflow_bp = Blueprint('workflow', __name__, url_prefix='/api/v1/workflows')



@workflow_bp.route('/catalog', methods=['GET'])
@require_auth
def workflow_catalog_view():
    return ok(workflow_catalog())


@workflow_bp.route('/templates', methods=['GET'])
@require_auth
def workflow_templates_list():
    return ok(list_templates())


@workflow_bp.route('/templates/<template_id>/instantiate', methods=['POST'])
@require_auth
def workflow_templates_instantiate(template_id: str):
    try:
        workflow = instantiate_template(template_id, _body())
    except ValueError as exc:
        return err(str(exc), 404)
    trigger = workflow.get('trigger', {}) if workflow else {}
    if workflow and trigger.get('type') == 'webhook':
        workflow['webhook_token'] = ensure_workflow_webhook(workflow['id'])
        workflow['webhook_signature_hint'] = 'X-Workflow-Timestamp + X-Workflow-Signature (HMAC-SHA256)'
    return ok(workflow)


@workflow_bp.route('', methods=['GET'])
@require_auth
def workflow_list():
    return ok(WorkflowModel.list_all())


@workflow_bp.route('', methods=['POST'])
@require_auth
def workflow_create():
    body = _body()
    workflow_id = WorkflowModel.create(body)
    workflow = WorkflowModel.get(workflow_id)
    trigger = workflow.get('trigger', {}) if workflow else {}
    if workflow and trigger.get('type') == 'webhook':
        token = ensure_workflow_webhook(workflow_id)
        workflow = WorkflowModel.get(workflow_id)
        workflow['webhook_token'] = token
        workflow['webhook_signature_hint'] = 'X-Workflow-Timestamp + X-Workflow-Signature (HMAC-SHA256)'
    return ok(workflow)


@workflow_bp.route('/<int:workflow_id>', methods=['GET'])
@require_auth
def workflow_detail(workflow_id: int):
    workflow = WorkflowModel.get(workflow_id)
    if not workflow:
        return err('工作流不存在', 404)
    return ok(workflow)


@workflow_bp.route('/<int:workflow_id>', methods=['PUT'])
@require_auth
def workflow_update(workflow_id: int):
    workflow = WorkflowModel.update(workflow_id, _body())
    if not workflow:
        return err('工作流不存在', 404)
    trigger = workflow.get('trigger', {})
    if trigger.get('type') == 'webhook':
        workflow['webhook_token'] = ensure_workflow_webhook(workflow_id)
        workflow['webhook_signature_hint'] = 'X-Workflow-Timestamp + X-Workflow-Signature (HMAC-SHA256)'
    return ok(workflow)


@workflow_bp.route('/<int:workflow_id>', methods=['DELETE'])
@require_auth
def workflow_delete(workflow_id: int):
    if not WorkflowModel.delete(workflow_id):
        return err('工作流不存在', 404)
    return ok({'deleted': True})


@workflow_bp.route('/<int:workflow_id>/publish', methods=['POST'])
@require_auth
def workflow_publish(workflow_id: int):
    workflow = WorkflowModel.publish(workflow_id)
    if not workflow:
        return err('工作流不存在', 404)
    if workflow.get('trigger', {}).get('type') == 'webhook':
        workflow['webhook_token'] = ensure_workflow_webhook(workflow_id)
        workflow['webhook_signature_hint'] = 'X-Workflow-Timestamp + X-Workflow-Signature (HMAC-SHA256)'
    return ok(workflow)


@workflow_bp.route('/<int:workflow_id>/run', methods=['POST'])
@require_auth
def workflow_run(workflow_id: int):
    body = _body()
    cfg = _load_cfg()
    try:
        result = run_workflow_by_id(
            workflow_id,
            trigger_type='manual',
            trigger_payload=body.get('payload') or body,
            cfg=cfg,
        )
    except ValueError as exc:
        return err(str(exc), 404)
    except Exception as exc:
        return err(f'工作流执行失败: {exc}', 500)
    return ok(result)


@workflow_bp.route('/webhook/<token>', methods=['POST'])
def workflow_webhook(token: str):
    workflow = WorkflowModel.get_by_webhook_token(token)
    if not workflow:
        return err('Webhook 不存在或已禁用', 404)

    body = _body()
    timestamp = str(request.headers.get('X-Workflow-Timestamp', '')).strip()
    signature = str(request.headers.get('X-Workflow-Signature', '')).strip()
    secret = token

    if timestamp and signature:
        try:
            ts_int = int(timestamp)
        except ValueError:
            return err('Webhook 时间戳无效', 400)
        if abs(int(time.time()) - ts_int) > 300:
            return err('Webhook 请求已过期', 401)
        canonical = json.dumps(body, ensure_ascii=False, sort_keys=True)
        expected = hmac.new(secret.encode('utf-8'), f'{timestamp}.{canonical}'.encode('utf-8'), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(signature, expected):
            return err('Webhook 签名校验失败', 401)

    try:
        result = run_workflow_by_id(
            workflow['id'],
            trigger_type='webhook',
            trigger_payload=body,
            cfg=_load_cfg(),
        )
    except Exception as exc:
        return err(f'Webhook 工作流执行失败: {exc}', 500)
    return ok(result)


@workflow_bp.route('/<int:workflow_id>/runs', methods=['GET'])
@require_auth
def workflow_runs(workflow_id: int):
    return ok(WorkflowModel.get_runs(workflow_id))


@workflow_bp.route('/runs/<int:run_id>', methods=['GET'])
@require_auth
def workflow_run_detail(run_id: int):
    run = WorkflowRunModel.get_run(run_id)
    if not run:
        return err('运行记录不存在', 404)
    run['steps'] = WorkflowRunModel.get_steps(run_id)
    run['steps_count'] = len(run['steps'])
    return ok(run)


@workflow_bp.route('/runs/<int:run_id>/steps', methods=['GET'])
@require_auth
def workflow_run_steps(run_id: int):
    return ok(WorkflowRunModel.get_steps(run_id))
