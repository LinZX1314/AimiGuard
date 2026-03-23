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


def _manual_hfish_triage_template() -> dict:
    return {
        'id': 'hfish-triage-route',
        'name': 'HFish 告警分诊',
        'description': '手动读取 HFish 日志，按日志数量判断是否需要生成 AI 摘要与通知。',
        'category': 'threat',
        'trigger_type': 'manual',
        'tags': ['HFish', '条件分支', 'AI'],
        'definition': {
            'nodes': [
                {
                    'id': 'trigger-1',
                    'type': 'trigger',
                    'position': {'x': 0, 'y': 0},
                    'data': {'kind': 'manual', 'label': '手动触发'},
                },
                {
                    'id': 'query-1',
                    'type': 'threat',
                    'position': {'x': 280, 'y': 0},
                    'data': {'kind': 'query_hfish_logs', 'label': '查询 HFish 日志', 'config': {'limit': 20}},
                },
                {
                    'id': 'condition-1',
                    'type': 'condition',
                    'position': {'x': 560, 'y': 0},
                    'data': {
                        'kind': 'condition',
                        'label': '是否存在攻击日志',
                        'config': {
                            'source': 'last_step_output',
                            'path': 'count',
                            'operator': 'gt',
                            'expected': 0,
                        },
                    },
                },
                {
                    'id': 'ai-1',
                    'type': 'ai',
                    'position': {'x': 860, 'y': -110},
                    'data': {'kind': 'generate_ai_summary', 'label': '生成 AI 摘要'},
                },
                {
                    'id': 'notify-1',
                    'type': 'result',
                    'position': {'x': 1140, 'y': -110},
                    'data': {'kind': 'notify_in_app', 'label': '站内通知', 'config': {'title': 'HFish 分诊结果'}},
                },
                {
                    'id': 'log-1',
                    'type': 'result',
                    'position': {'x': 860, 'y': 120},
                    'data': {'kind': 'write_log', 'label': '写入日志', 'config': {'message': '当前未发现攻击日志', 'level': 'INFO'}},
                },
            ],
            'edges': [
                {'id': 'e1', 'source': 'trigger-1', 'target': 'query-1'},
                {'id': 'e2', 'source': 'query-1', 'target': 'condition-1'},
                {'id': 'e3', 'source': 'condition-1', 'target': 'ai-1', 'branch': 'true'},
                {'id': 'e4', 'source': 'ai-1', 'target': 'notify-1'},
                {'id': 'e5', 'source': 'condition-1', 'target': 'log-1', 'branch': 'false'},
            ],
        },
        'defaults': {
            'name': 'HFish 告警分诊工作流',
            'description': '自动判断当前是否有攻击日志，并决定是否走 AI 摘要和通知。',
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


def _scheduled_daily_digest_template() -> dict:
    return {
        'id': 'scheduled-daily-digest',
        'name': '定时安全日报',
        'description': '定时汇总 HFish 日志，生成 AI 摘要并写入日志与站内通知。',
        'category': 'threat',
        'trigger_type': 'schedule',
        'tags': ['定时', '日报', 'AI'],
        'definition': {
            'nodes': [
                {
                    'id': 'trigger-1',
                    'type': 'trigger',
                    'position': {'x': 0, 'y': 0},
                    'data': {'kind': 'schedule', 'label': '定时触发', 'config': {'interval_seconds': 86400}},
                },
                {
                    'id': 'query-1',
                    'type': 'threat',
                    'position': {'x': 260, 'y': 0},
                    'data': {'kind': 'query_hfish_logs', 'label': '查询 HFish 日志', 'config': {'limit': 30}},
                },
                {
                    'id': 'ai-1',
                    'type': 'ai',
                    'position': {'x': 520, 'y': 0},
                    'data': {'kind': 'generate_ai_summary', 'label': '生成日报摘要'},
                },
                {
                    'id': 'log-1',
                    'type': 'result',
                    'position': {'x': 780, 'y': -110},
                    'data': {'kind': 'write_log', 'label': '写入系统日志', 'config': {'level': 'INFO'}},
                },
                {
                    'id': 'notify-1',
                    'type': 'result',
                    'position': {'x': 780, 'y': 110},
                    'data': {'kind': 'notify_in_app', 'label': '推送日报通知', 'config': {'title': '每日报告已生成'}},
                },
            ],
            'edges': [
                {'id': 'e1', 'source': 'trigger-1', 'target': 'query-1'},
                {'id': 'e2', 'source': 'query-1', 'target': 'ai-1'},
                {'id': 'e3', 'source': 'ai-1', 'target': 'log-1'},
                {'id': 'e4', 'source': 'ai-1', 'target': 'notify-1'},
            ],
        },
        'defaults': {
            'name': '定时安全日报工作流',
            'description': '每天自动汇总 HFish 日志并输出安全摘要。',
            'category': 'threat',
            'status': 'draft',
            'trigger': {'type': 'schedule', 'enabled': True, 'interval_seconds': 86400},
        },
    }


def _webhook_alert_intake_template() -> dict:
    return {
        'id': 'webhook-alert-intake',
        'name': 'Webhook 外部告警接入',
        'description': '接收第三方告警 Webhook，按严重级别分流到站内通知或日志。',
        'category': 'integration',
        'trigger_type': 'webhook',
        'tags': ['Webhook', '外部集成', '告警'],
        'definition': {
            'nodes': [
                {
                    'id': 'trigger-1',
                    'type': 'trigger',
                    'position': {'x': 0, 'y': 0},
                    'data': {'kind': 'webhook', 'label': 'Webhook 触发'},
                },
                {
                    'id': 'condition-1',
                    'type': 'condition',
                    'position': {'x': 300, 'y': 0},
                    'data': {
                        'kind': 'condition',
                        'label': '判断告警级别',
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
                    'position': {'x': 620, 'y': -110},
                    'data': {'kind': 'notify_in_app', 'label': '推送高危告警', 'config': {'title': '外部高危告警'}},
                },
                {
                    'id': 'log-1',
                    'type': 'result',
                    'position': {'x': 620, 'y': 110},
                    'data': {'kind': 'write_log', 'label': '记录普通告警', 'config': {'level': 'INFO'}},
                },
            ],
            'edges': [
                {'id': 'e1', 'source': 'trigger-1', 'target': 'condition-1'},
                {'id': 'e2', 'source': 'condition-1', 'target': 'notify-1', 'branch': 'true'},
                {'id': 'e3', 'source': 'condition-1', 'target': 'log-1', 'branch': 'false'},
            ],
        },
        'defaults': {
            'name': 'Webhook 外部告警接入工作流',
            'description': '接收第三方告警并根据严重级别自动处理。',
            'category': 'integration',
            'status': 'draft',
            'trigger': {'type': 'webhook', 'enabled': True},
        },
    }


def _webhook_internal_api_template() -> dict:
    return {
        'id': 'webhook-api-bridge',
        'name': 'Webhook 到内部 API 桥接',
        'description': '接收 Webhook 后调用内部 API，并将结果记录到日志与通知。',
        'category': 'integration',
        'trigger_type': 'webhook',
        'tags': ['Webhook', 'API', '桥接'],
        'definition': {
            'nodes': [
                {
                    'id': 'trigger-1',
                    'type': 'trigger',
                    'position': {'x': 0, 'y': 0},
                    'data': {'kind': 'webhook', 'label': 'Webhook 触发'},
                },
                {
                    'id': 'api-1',
                    'type': 'result',
                    'position': {'x': 280, 'y': 0},
                    'data': {
                        'kind': 'call_internal_api',
                        'label': '调用内部 API',
                        'config': {'endpoint': '/api/v1/overview/chain-status', 'method': 'GET'},
                    },
                },
                {
                    'id': 'log-1',
                    'type': 'result',
                    'position': {'x': 560, 'y': -110},
                    'data': {'kind': 'write_log', 'label': '记录桥接结果', 'config': {'level': 'INFO'}},
                },
                {
                    'id': 'notify-1',
                    'type': 'result',
                    'position': {'x': 560, 'y': 110},
                    'data': {'kind': 'notify_in_app', 'label': '发送桥接通知', 'config': {'title': 'Webhook 桥接完成'}},
                },
            ],
            'edges': [
                {'id': 'e1', 'source': 'trigger-1', 'target': 'api-1'},
                {'id': 'e2', 'source': 'api-1', 'target': 'log-1'},
                {'id': 'e3', 'source': 'api-1', 'target': 'notify-1'},
            ],
        },
        'defaults': {
            'name': 'Webhook 内部 API 桥接工作流',
            'description': '把外部 Webhook 事件桥接到平台内部 API。',
            'category': 'integration',
            'status': 'draft',
            'trigger': {'type': 'webhook', 'enabled': True},
        },
    }


WORKFLOW_TEMPLATES = [
    _manual_hfish_summary_template(),
    _manual_hfish_triage_template(),
    _scheduled_severity_template(),
    _scheduled_daily_digest_template(),
    _webhook_alert_intake_template(),
    _webhook_internal_api_template(),
]


def list_workflow_templates() -> list[dict]:
    return [deepcopy(item) for item in WORKFLOW_TEMPLATES]


def get_workflow_template(template_id: str) -> dict | None:
    for item in WORKFLOW_TEMPLATES:
        if item['id'] == template_id:
            return deepcopy(item)
    return None
