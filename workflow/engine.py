import json
from datetime import datetime
from typing import Any

from web.flask_app import create_app
from database.models import HFishModel, WorkflowModel, WorkflowRunModel, WorkflowWebhookModel
from utils.logger import log
from workflow.templates import get_workflow_template, list_workflow_templates

try:
    from ai.client import call_openai_chat_completion
except Exception:  # pragma: no cover
    call_openai_chat_completion = None


SUCCESS_STATUSES = {'success', 'success_with_skips'}


def workflow_catalog() -> dict:
    return {
        'categories': [
            {'id': 'trigger', 'label': '触发器'},
            {'id': 'discovery', 'label': '资产发现'},
            {'id': 'threat', 'label': '威胁采集'},
            {'id': 'ai', 'label': 'AI 分析'},
            {'id': 'defense', 'label': '防御处置'},
            {'id': 'system', 'label': '系统数据'},
            {'id': 'result', 'label': '结果输出'},
        ],
        'nodes': [
            {'kind': 'manual', 'type': 'trigger', 'label': '手动触发'},
            {'kind': 'schedule', 'type': 'trigger', 'label': '定时触发'},
            {'kind': 'webhook', 'type': 'trigger', 'label': 'Webhook 触发'},
            {'kind': 'query_hfish_logs', 'type': 'threat', 'label': '查询 HFish 日志'},
            {'kind': 'generate_ai_summary', 'type': 'ai', 'label': 'AI 摘要'},
            {'kind': 'condition', 'type': 'system', 'label': '条件分支'},
            {'kind': 'write_log', 'type': 'result', 'label': '写入系统日志'},
            {'kind': 'notify_in_app', 'type': 'result', 'label': '站内通知'},
            {'kind': 'call_internal_api', 'type': 'result', 'label': '调用内部 API'},
        ],
    }


def list_templates() -> list[dict]:
    return list_workflow_templates()


def instantiate_template(template_id: str, overrides: dict | None = None) -> dict:
    template = get_workflow_template(template_id)
    if not template:
        raise ValueError('模板不存在')

    overrides = overrides or {}
    defaults = template.get('defaults', {})
    payload = {
        **defaults,
        'name': overrides.get('name') or defaults.get('name') or template['name'],
        'description': overrides.get('description') or defaults.get('description') or template['description'],
        'category': overrides.get('category') or defaults.get('category') or template['category'],
        'status': overrides.get('status') or defaults.get('status') or 'draft',
        'trigger': overrides.get('trigger') or defaults.get('trigger') or {'type': template.get('trigger_type', 'manual')},
        'definition': overrides.get('definition') or template['definition'],
        'template_id': template['id'],
        'template_name': template['name'],
    }

    workflow_id = WorkflowModel.create(payload)
    workflow = WorkflowModel.get(workflow_id)
    if workflow and workflow.get('trigger', {}).get('type') == 'webhook':
        workflow['webhook_token'] = ensure_workflow_webhook(workflow_id)
    return workflow


def ensure_workflow_webhook(workflow_id: int) -> str:
    return WorkflowWebhookModel.ensure_token(workflow_id)


def _extract_text(value: Any) -> str:
    if value is None:
        return ''
    if isinstance(value, str):
        return value
    try:
        return json.dumps(value, ensure_ascii=False)
    except Exception:
        return str(value)


def _lookup_by_path(value: Any, path: str | None) -> Any:
    if not path:
        return value
    current = value
    for part in str(path).split('.'):
        if isinstance(current, dict):
            current = current.get(part)
        elif isinstance(current, list):
            try:
                current = current[int(part)]
            except Exception:
                return None
        else:
            return None
    return current


def _resolve_input(context: dict) -> str:
    for step in reversed(context.get('steps', [])):
        output = step.get('output') or {}
        if isinstance(output, dict):
            if 'summary' in output:
                return _extract_text(output.get('summary'))
            if 'message' in output:
                return _extract_text(output.get('message'))
            if 'logs' in output:
                return _extract_text(output.get('logs'))
        return _extract_text(output)
    return _extract_text(context.get('trigger_payload', {}))


def _resolve_condition_source(config: dict, context: dict) -> Any:
    source = config.get('source') or 'trigger_payload'
    if source == 'trigger_payload':
        return context.get('trigger_payload', {})
    if source == 'last_step_output':
        return context.get('steps', [])[-1]['output'] if context.get('steps') else {}
    if source == 'step_output_by_node_id':
        node_id = config.get('node_id')
        return context.get('step_outputs', {}).get(node_id, {})
    return {}


def _evaluate_condition(config: dict, context: dict) -> tuple[bool, Any]:
    source_value = _resolve_condition_source(config, context)
    actual = _lookup_by_path(source_value, config.get('path'))
    operator = config.get('operator') or 'eq'
    expected = config.get('expected')

    try:
        if operator == 'eq':
            result = actual == expected
        elif operator == 'neq':
            result = actual != expected
        elif operator == 'contains':
            result = expected in actual if isinstance(actual, (str, list, tuple, set)) else False
        elif operator == 'gt':
            result = actual > expected
        elif operator == 'gte':
            result = actual >= expected
        elif operator == 'lt':
            result = actual < expected
        elif operator == 'lte':
            result = actual <= expected
        elif operator == 'exists':
            result = actual is not None
        elif operator == 'empty':
            result = actual in (None, '', [], {}, ())
        else:
            result = False
    except Exception:
        result = False

    return result, actual


def _execute_node(node: dict, context: dict, cfg: dict | None = None) -> dict:
    node_type = node.get('type')
    data = node.get('data') or {}
    kind = data.get('kind') or node_type
    config = data.get('config') or {}

    if node_type == 'trigger':
        return {
            'message': f"{data.get('label', '触发器')} 已触发",
            'kind': kind,
            'trigger_payload': context.get('trigger_payload', {}),
        }

    if kind == 'condition':
        matched, actual = _evaluate_condition(config, context)
        return {
            'message': f"条件分支结果: {'true' if matched else 'false'}",
            'matched': matched,
            'actual': actual,
            'operator': config.get('operator') or 'eq',
            'expected': config.get('expected'),
            'source': config.get('source') or 'trigger_payload',
            'path': config.get('path'),
        }

    if kind == 'query_hfish_logs':
        limit = int(config.get('limit') or 20)
        service_name = config.get('service_name')
        logs = HFishModel.get_attack_logs(limit=limit, service_name=service_name)
        return {
            'message': f'已读取 {len(logs)} 条 HFish 攻击记录',
            'logs': logs,
            'count': len(logs),
        }

    if kind == 'generate_ai_summary':
        prompt = config.get('prompt') or '请对以下安全事件做简要摘要，并给出处置建议。'
        content = _resolve_input(context)
        if call_openai_chat_completion is None or not cfg:
            return {
                'summary': f'AI 模块未启用，输入内容长度 {len(content)}',
                'message': 'AI 摘要已跳过',
            }
        response = call_openai_chat_completion(
            messages=[
                {'role': 'system', 'content': prompt},
                {'role': 'user', 'content': content},
            ],
            cfg=cfg,
        )
        return {
            'summary': response.get('content') or response.get('message') or '',
            'raw': response,
            'message': 'AI 摘要已生成',
        }

    if kind == 'write_log':
        message = config.get('message') or _resolve_input(context) or '工作流执行完成'
        level = (config.get('level') or 'INFO').upper()
        log('Workflow', message, level)
        return {
            'message': message,
            'level': level,
            'logged_at': datetime.now().isoformat(),
        }

    if kind == 'notify_in_app':
        message = config.get('message') or _resolve_input(context) or '工作流执行完成'
        title = config.get('title') or data.get('label') or '工作流通知'
        return {
            'message': message,
            'title': title,
            'channel': 'in_app',
        }

    if kind == 'call_internal_api':
        endpoint = str(config.get('endpoint') or '/api/v1/overview/chain-status')
        method = str(config.get('method') or 'GET').upper()
        payload = config.get('payload') or context.get('trigger_payload') or {}
        app = create_app()
        client = app.test_client()
        request_kwargs: dict[str, Any] = {}
        if method in {'POST', 'PUT', 'PATCH', 'DELETE'}:
            request_kwargs['json'] = payload
        response = client.open(endpoint, method=method, **request_kwargs)
        try:
            response_payload: Any = response.get_json()
        except Exception:
            response_payload = response.get_data(as_text=True)
        return {
            'message': '内部 API 调用完成',
            'endpoint': endpoint,
            'method': method,
            'payload': payload,
            'status_code': response.status_code,
            'response': response_payload,
            'called': True,
        }

    return {
        'message': f'未识别的节点类型: {kind}',
        'kind': kind,
    }


def _normalize_definition(definition: dict) -> tuple[dict[str, dict], dict[str, list[dict]], list[str]]:
    nodes = definition.get('nodes', []) or []
    edges = definition.get('edges', []) or []
    node_map = {node['id']: node for node in nodes if node.get('id')}
    adjacency: dict[str, list[dict]] = {node_id: [] for node_id in node_map}
    incoming: dict[str, int] = {node_id: 0 for node_id in node_map}
    for edge in edges:
        source = edge.get('source')
        target = edge.get('target')
        if source in node_map and target in node_map:
            adjacency[source].append(edge)
            incoming[target] += 1
    start_nodes = [node_id for node_id, count in incoming.items() if count == 0]
    if not start_nodes:
        start_nodes = list(node_map.keys())[:1]
    return node_map, adjacency, start_nodes


def run_workflow(workflow: dict, trigger_type: str, trigger_payload: dict | None = None, cfg: dict | None = None) -> dict:
    trigger_payload = trigger_payload or {}
    definition = workflow.get('definition', {}) or {'nodes': [], 'edges': []}
    node_map, adjacency, start_nodes = _normalize_definition(definition)
    run_id = WorkflowRunModel.create_run(workflow['id'], trigger_type, trigger_payload, status='running')
    context = {
        'workflow': workflow,
        'trigger_type': trigger_type,
        'trigger_payload': trigger_payload,
        'steps': [],
        'step_outputs': {},
        'notifications': [],
    }

    visited: set[str] = set()
    queue: list[str] = list(start_nodes)
    skipped_branches = 0

    try:
        while queue:
            node_id = queue.pop(0)
            if node_id in visited or node_id not in node_map:
                continue
            visited.add(node_id)

            node = node_map[node_id]
            node_type = node.get('type') or 'unknown'
            data = node.get('data') or {}
            node_name = data.get('label') or node_id
            step_input = {
                'trigger_payload': trigger_payload,
                'config': data.get('config') or {},
            }
            step_id = WorkflowRunModel.add_step(
                run_id,
                node_id=node_id,
                node_type=node_type,
                node_name=node_name,
                status='running',
                input_payload=step_input,
            )
            output = _execute_node(node, context, cfg=cfg)
            WorkflowRunModel.update_step(step_id, 'success', output_payload=output)
            context['steps'].append({
                'node_id': node_id,
                'node_type': node_type,
                'node_name': node_name,
                'output': output,
            })
            context['step_outputs'][node_id] = output
            if output.get('channel') == 'in_app':
                context['notifications'].append(output)

            outgoing = adjacency.get(node_id, [])
            if (data.get('kind') or node_type) == 'condition':
                branch = 'true' if output.get('matched') else 'false'
                matched_edges = [edge for edge in outgoing if str(edge.get('branch', '')).lower() == branch]
                skipped_branches += max(len(outgoing) - len(matched_edges), 0)
                queue.extend(edge['target'] for edge in matched_edges)
            else:
                queue.extend(edge['target'] for edge in outgoing)

        status = 'success_with_skips' if skipped_branches else 'success'
        summary = context['steps'][-1]['output'].get('message') if context['steps'] else '工作流执行完成'
        if skipped_branches:
            summary = f'{summary}（跳过 {skipped_branches} 条未命中分支）'
        WorkflowRunModel.finish_run(run_id, status, summary=summary)
        WorkflowModel.mark_run_scheduled(workflow['id'])
        run = WorkflowRunModel.get_run(run_id) or {}
        steps = WorkflowRunModel.get_steps(run_id)
        run['steps'] = steps
        run['steps_count'] = len(steps)
        run['notifications'] = context['notifications']
        return run
    except Exception as exc:
        WorkflowRunModel.finish_run(run_id, 'failed', summary='工作流执行失败', error_message=str(exc))
        WorkflowModel.mark_run_scheduled(workflow['id'])
        raise


def run_workflow_by_id(workflow_id: int, trigger_type: str, trigger_payload: dict | None = None, cfg: dict | None = None) -> dict:
    workflow = WorkflowModel.get(workflow_id)
    if not workflow:
        raise ValueError('工作流不存在')
    return run_workflow(workflow, trigger_type=trigger_type, trigger_payload=trigger_payload, cfg=cfg)
