from copy import deepcopy


def _manual_hfish_summary_template() -> dict:
    return {
        'id': 'hfish-ai-summary',
        'name': 'HFish 攻击摘要',
        'description': '手动触发读取 HFish 攻击日志，生成 AI 摘要后发送站内通知。',
        'category': 'threat',
        'trigger_type': 'manual',
        'tags': ['HFish', 'AI', '通知'],
        'definition': {
            'nodes': [
                {
                    'id': 'trigger-1',
                    'type': 'trigger',
                    'position': {'x': 0, 'y': 0},
                    'data': {'kind': 'manual', 'label': '手动触发', 'description': '点击立即运行时触发'},
                },
                {
                    'id': 'query-1',
                    'type': 'threat',
                    'position': {'x': 280, 'y': 0},
                    'data': {'kind': 'query_hfish_logs', 'label': '查询 HFish 日志', 'config': {'limit': 10}},
                },
                {
                    'id': 'ai-1',
                    'type': 'ai',
                    'position': {'x': 560, 'y': 0},
                    'data': {'kind': 'generate_ai_summary', 'label': 'AI 生成摘要'},
                },
                {
                    'id': 'notify-1',
                    'type': 'result',
                    'position': {'x': 840, 'y': 0},
                    'data': {'kind': 'notify_in_app', 'label': '站内通知', 'config': {'title': 'HFish 攻击摘要'}},
                },
            ],
            'edges': [
                {'id': 'e1', 'source': 'trigger-1', 'target': 'query-1'},
                {'id': 'e2', 'source': 'query-1', 'target': 'ai-1'},
                {'id': 'e3', 'source': 'ai-1', 'target': 'notify-1'},
            ],
        },
        'defaults': {
            'name': 'HFish 攻击摘要工作流',
            'description': '读取攻击日志，生成 AI 摘要并推送站内通知。',
            'category': 'threat',
            'status': 'draft',
            'trigger': {'type': 'manual', 'enabled': True},
        },
    }


def _scheduled_severity_template() -> dict:
    return {
        'id': 'scheduled-severity-route',
        'name': '定时高危分流',
        'description': '定时触发，根据 payload 中的 severity 做条件分支处理。',
        'category': 'system',
        'trigger_type': 'schedule',
        'tags': ['定时', '条件分支', '通知'],
        'definition': {
            'nodes': [
                {
                    'id': 'trigger-1',
                    'type': 'trigger',
                    'position': {'x': 0, 'y': 0},
                    'data': {'kind': 'schedule', 'label': '定时触发', 'config': {'interval_seconds': 300}},
                },
                {
                    'id': 'condition-1',
                    'type': 'condition',
                    'position': {'x': 320, 'y': 0},
                    'data': {
                        'kind': 'condition',
                        'label': '判断 severity',
                        'config': {
                            'source': 'trigger_payload',
                            'path': 'severity',
                            'operator': 'eq',
                            'expected': 'high',
                        },
                    },
                },
                {
                    'id': 'notify-1',
                    'type': 'result',
                    'position': {'x': 640, 'y': -120},
                    'data': {'kind': 'notify_in_app', 'label': '高危通知', 'config': {'title': '高危告警'}},
                },
                {
                    'id': 'log-1',
                    'type': 'result',
                    'position': {'x': 640, 'y': 120},
                    'data': {'kind': 'write_log', 'label': '普通日志', 'config': {'message': '普通事件', 'level': 'INFO'}},
                },
            ],
            'edges': [
                {'id': 'e1', 'source': 'trigger-1', 'target': 'condition-1'},
                {'id': 'e2', 'source': 'condition-1', 'target': 'notify-1', 'branch': 'true'},
                {'id': 'e3', 'source': 'condition-1', 'target': 'log-1', 'branch': 'false'},
            ],
        },
        'defaults': {
            'name': '定时高危分流工作流',
            'description': '定时读取触发 payload，并依据 severity 分流。',
            'category': 'system',
            'status': 'draft',
            'trigger': {'type': 'schedule', 'enabled': True, 'interval_seconds': 300},
        },
    }


WORKFLOW_TEMPLATES = [
    _manual_hfish_summary_template(),
    _scheduled_severity_template(),
]


def list_workflow_templates() -> list[dict]:
    return [deepcopy(item) for item in WORKFLOW_TEMPLATES]


def get_workflow_template(template_id: str) -> dict | None:
    for item in WORKFLOW_TEMPLATES:
        if item['id'] == template_id:
            return deepcopy(item)
    return None
