import os
import tempfile
import unittest
from datetime import datetime, timedelta
from unittest.mock import patch
import hashlib
import hmac
import json
import time

import database.db as db_module
from database.models import WorkflowModel, WorkflowWebhookModel
from web.api.helpers import _make_token
from web.flask_app import create_app


class WorkflowApiTestCase(unittest.TestCase):
    def setUp(self):
        self.temp_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        self.temp_db.close()
        self.original_db_file = db_module.DB_FILE
        db_module.DB_FILE = self.temp_db.name
        self.app = create_app()
        self.client = self.app.test_client()
        self.token = _make_token({
            'sub': 'admin',
            'username': 'admin',
            'role': 'admin',
            'permissions': ['*'],
        })

    def tearDown(self):
        db_module.DB_FILE = self.original_db_file
        if os.path.exists(self.temp_db.name):
            os.remove(self.temp_db.name)

    def auth_headers(self):
        return {'Authorization': f'Bearer {self.token}'}

    def workflow_payload(self, trigger_type='manual'):
        return {
            'name': '攻击日志摘要流',
            'description': '测试工作流',
            'category': 'ai',
            'status': 'draft',
            'trigger': {
                'type': trigger_type,
                'enabled': True,
                'interval_seconds': 60,
            },
            'definition': {
                'nodes': [
                    {
                        'id': 'trigger-1',
                        'type': 'trigger',
                        'position': {'x': 0, 'y': 0},
                        'data': {'kind': trigger_type, 'label': '触发器'},
                    },
                    {
                        'id': 'query-1',
                        'type': 'threat',
                        'position': {'x': 320, 'y': 0},
                        'data': {'kind': 'query_hfish_logs', 'label': '读取HFish日志', 'config': {'limit': 5}},
                    },
                    {
                        'id': 'notify-1',
                        'type': 'result',
                        'position': {'x': 640, 'y': 0},
                        'data': {'kind': 'notify_in_app', 'label': '站内通知', 'config': {'title': '工作流完成'}},
                    },
                    {
                        'id': 'log-1',
                        'type': 'result',
                        'position': {'x': 960, 'y': 0},
                        'data': {'kind': 'write_log', 'label': '写入日志', 'config': {'level': 'INFO'}},
                    },
                ],
                'edges': [
                    {'id': 'e1', 'source': 'trigger-1', 'target': 'query-1'},
                    {'id': 'e2', 'source': 'query-1', 'target': 'notify-1'},
                    {'id': 'e3', 'source': 'notify-1', 'target': 'log-1'},
                ],
            },
        }

    def conditional_workflow_payload(self):
        return {
            'name': '条件分支工作流',
            'description': '测试条件分支',
            'category': 'system',
            'status': 'active',
            'trigger': {
                'type': 'manual',
                'enabled': True,
            },
            'definition': {
                'nodes': [
                    {
                        'id': 'trigger-1',
                        'type': 'trigger',
                        'position': {'x': 0, 'y': 0},
                        'data': {'kind': 'manual', 'label': '触发器'},
                    },
                    {
                        'id': 'condition-1',
                        'type': 'condition',
                        'position': {'x': 300, 'y': 0},
                        'data': {
                            'kind': 'condition',
                            'label': '高危判断',
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
                        'position': {'x': 620, 'y': -120},
                        'data': {'kind': 'notify_in_app', 'label': '高危通知', 'config': {'title': '高危告警'}},
                    },
                    {
                        'id': 'log-1',
                        'type': 'result',
                        'position': {'x': 620, 'y': 120},
                        'data': {'kind': 'write_log', 'label': '普通日志', 'config': {'message': '普通事件', 'level': 'INFO'}},
                    },
                ],
                'edges': [
                    {'id': 'e1', 'source': 'trigger-1', 'target': 'condition-1'},
                    {'id': 'e2', 'source': 'condition-1', 'target': 'notify-1', 'branch': 'true'},
                    {'id': 'e3', 'source': 'condition-1', 'target': 'log-1', 'branch': 'false'},
                ],
            },
        }

    def test_catalog_endpoint_returns_workflow_categories(self):
        response = self.client.get('/api/v1/workflows/catalog', headers=self.auth_headers())
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload['code'], 0)
        category_ids = {item['id'] for item in payload['data']['categories']}
        self.assertIn('trigger', category_ids)
        self.assertIn('result', category_ids)

    def test_template_endpoints_list_and_instantiate_workflow(self):
        list_response = self.client.get('/api/v1/workflows/templates', headers=self.auth_headers())
        self.assertEqual(list_response.status_code, 200)
        templates = list_response.get_json()['data']
        self.assertGreaterEqual(len(templates), 6)
        template_ids = {template['id'] for template in templates}
        self.assertIn('hfish-ai-summary', template_ids)
        self.assertIn('hfish-triage-route', template_ids)
        self.assertIn('scheduled-daily-digest', template_ids)
        self.assertIn('webhook-alert-intake', template_ids)
        template_id = 'webhook-alert-intake'

        instantiate_response = self.client.post(
            f'/api/v1/workflows/templates/{template_id}/instantiate',
            json={'name': '从模板创建'},
            headers=self.auth_headers(),
        )
        self.assertEqual(instantiate_response.status_code, 200)
        workflow = instantiate_response.get_json()['data']
        self.assertEqual(workflow['name'], '从模板创建')
        self.assertGreater(len(workflow['definition']['nodes']), 0)
        self.assertEqual(workflow['trigger']['type'], 'webhook')
        self.assertTrue(workflow.get('webhook_secret'))

    def test_create_publish_and_run_workflow_records_run_history(self):
        create_response = self.client.post(
            '/api/v1/workflows',
            json=self.workflow_payload(),
            headers=self.auth_headers(),
        )
        self.assertEqual(create_response.status_code, 200)
        workflow = create_response.get_json()['data']

        publish_response = self.client.post(
            f"/api/v1/workflows/{workflow['id']}/publish",
            headers=self.auth_headers(),
        )
        self.assertEqual(publish_response.status_code, 200)

        with patch('database.models.HFishModel.get_attack_logs', return_value=[{'attack_ip': '1.1.1.1'}]):
            run_response = self.client.post(
                f"/api/v1/workflows/{workflow['id']}/run",
                json={'payload': {'source': 'manual-test'}},
                headers=self.auth_headers(),
            )

        self.assertEqual(run_response.status_code, 200)
        run_payload = run_response.get_json()['data']
        self.assertEqual(run_payload['status'], 'success')
        self.assertGreater(run_payload['steps_count'], 0)

        runs_response = self.client.get(
            f"/api/v1/workflows/{workflow['id']}/runs",
            headers=self.auth_headers(),
        )
        self.assertEqual(runs_response.status_code, 200)
        runs = runs_response.get_json()['data']
        self.assertEqual(len(runs), 1)
        self.assertEqual(runs[0]['trigger_type'], 'manual')

    def test_condition_workflow_routes_only_matching_branch(self):
        workflow_id = WorkflowModel.create(self.conditional_workflow_payload())
        workflow = WorkflowModel.publish(workflow_id)
        self.assertIsNotNone(workflow)

        run_response = self.client.post(
            f'/api/v1/workflows/{workflow_id}/run',
            json={'payload': {'severity': 'high'}},
            headers=self.auth_headers(),
        )
        self.assertEqual(run_response.status_code, 200)
        run_payload = run_response.get_json()['data']
        step_names = [step['node_name'] for step in run_payload['steps']]
        self.assertIn('高危通知', step_names)
        self.assertNotIn('普通日志', step_names)
        self.assertEqual(run_payload['status'], 'success_with_skips')

    def test_run_detail_endpoint_returns_steps(self):
        create_response = self.client.post(
            '/api/v1/workflows',
            json=self.workflow_payload(),
            headers=self.auth_headers(),
        )
        workflow = create_response.get_json()['data']
        self.client.post(f"/api/v1/workflows/{workflow['id']}/publish", headers=self.auth_headers())

        with patch('database.models.HFishModel.get_attack_logs', return_value=[]):
            run_response = self.client.post(
                f"/api/v1/workflows/{workflow['id']}/run",
                json={'payload': {'source': 'detail'}},
                headers=self.auth_headers(),
            )

        run_id = run_response.get_json()['data']['id']
        detail_response = self.client.get(f'/api/v1/workflows/runs/{run_id}', headers=self.auth_headers())
        self.assertEqual(detail_response.status_code, 200)
        detail = detail_response.get_json()['data']
        self.assertGreater(len(detail['steps']), 0)
        self.assertIn('input', detail['steps'][0])
        self.assertIn('output', detail['steps'][0])

    def test_webhook_endpoint_executes_matching_workflow(self):
        create_response = self.client.post(
            '/api/v1/workflows',
            json=self.workflow_payload(trigger_type='webhook'),
            headers=self.auth_headers(),
        )
        workflow = create_response.get_json()['data']

        self.client.post(
            f"/api/v1/workflows/{workflow['id']}/publish",
            headers=self.auth_headers(),
        )

        with patch('database.models.HFishModel.get_attack_logs', return_value=[]):
            webhook_response = self.client.post(
                f"/api/v1/workflows/webhook/{workflow['webhook_token']}",
                json={'event': 'external-alert'},
            )

        self.assertEqual(webhook_response.status_code, 200)
        data = webhook_response.get_json()['data']
        self.assertEqual(data['trigger_type'], 'webhook')
        self.assertEqual(data['status'], 'success')

    def test_webhook_returns_secret_and_accepts_signed_request(self):
        create_response = self.client.post(
            '/api/v1/workflows',
            json=self.workflow_payload(trigger_type='webhook'),
            headers=self.auth_headers(),
        )
        self.assertEqual(create_response.status_code, 200)
        workflow = create_response.get_json()['data']
        self.assertTrue(workflow.get('webhook_token'))
        self.assertTrue(workflow.get('webhook_secret'))
        self.assertIn('X-Workflow-Timestamp', workflow.get('webhook_signature_hint', ''))

        stored_webhook = WorkflowWebhookModel.get_by_workflow_id(workflow['id'])
        self.assertIsNotNone(stored_webhook)
        self.assertEqual(stored_webhook['secret'], workflow['webhook_secret'])

        self.client.post(
            f"/api/v1/workflows/{workflow['id']}/publish",
            headers=self.auth_headers(),
        )

        payload = {'event': 'signed-alert', 'severity': 'high'}
        timestamp = str(int(time.time()))
        canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True)
        signature = hmac.new(
            workflow['webhook_secret'].encode('utf-8'),
            f'{timestamp}.{canonical}'.encode('utf-8'),
            hashlib.sha256,
        ).hexdigest()

        with patch('database.models.HFishModel.get_attack_logs', return_value=[]):
            response = self.client.post(
                f"/api/v1/workflows/webhook/{workflow['webhook_token']}",
                json=payload,
                headers={
                    'X-Workflow-Timestamp': timestamp,
                    'X-Workflow-Signature': signature,
                },
            )

        self.assertEqual(response.status_code, 200)
        data = response.get_json()['data']
        self.assertEqual(data['trigger_type'], 'webhook')

    def test_webhook_rejects_invalid_signature(self):
        create_response = self.client.post(
            '/api/v1/workflows',
            json=self.workflow_payload(trigger_type='webhook'),
            headers=self.auth_headers(),
        )
        workflow = create_response.get_json()['data']
        self.client.post(
            f"/api/v1/workflows/{workflow['id']}/publish",
            headers=self.auth_headers(),
        )

        response = self.client.post(
            f"/api/v1/workflows/webhook/{workflow['webhook_token']}",
            json={'event': 'invalid-signed-alert'},
            headers={
                'X-Workflow-Timestamp': str(int(time.time())),
                'X-Workflow-Signature': 'bad-signature',
            },
        )
        self.assertEqual(response.status_code, 401)

    def test_due_schedule_query_only_returns_ready_workflows(self):
        past = (datetime.now() - timedelta(minutes=1)).isoformat()
        future = (datetime.now() + timedelta(minutes=10)).isoformat()

        due_id = WorkflowModel.create({
            'name': '定时工作流-到期',
            'description': '',
            'category': 'system',
            'status': 'active',
            'trigger_json': {'type': 'schedule', 'enabled': True, 'interval_seconds': 60},
            'definition_json': {'nodes': [], 'edges': []},
            'next_run_at': past,
        })
        WorkflowModel.create({
            'name': '定时工作流-未到期',
            'description': '',
            'category': 'system',
            'status': 'active',
            'trigger_json': {'type': 'schedule', 'enabled': True, 'interval_seconds': 60},
            'definition_json': {'nodes': [], 'edges': []},
            'next_run_at': future,
        })

        due_workflows = WorkflowModel.list_due_workflows(datetime.now().isoformat())
        due_ids = {item['id'] for item in due_workflows}
        self.assertIn(due_id, due_ids)
        self.assertEqual(len(due_ids), 1)

    def test_manual_hfish_sync_endpoint_returns_runtime_error_code(self):
        with patch('web.api.defense.run_hfish_sync', return_value={
            'success': False,
            'error_code': 'not_found',
            'error': '接口不存在(404): https://127.0.0.1:4433/api/v1/attack/detail?api_key=k',
        }):
            response = self.client.post('/api/v1/defense/hfish/sync', headers=self.auth_headers())

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload['code'], 0)
        self.assertFalse(payload['data']['success'])
        self.assertEqual(payload['data']['error_code'], 'not_found')
        self.assertIn('404', payload['data']['error'])


    def test_run_hfish_sync_returns_not_found_error_before_reading_timestamp(self):
        from web.api import runtime as runtime_module
        from database.models import HFishModel

        with patch.object(runtime_module, '_load_cfg', return_value={
            'hfish': {'host_port': '127.0.0.1:4433', 'api_key': 'k', 'api_base_url': 'https://127.0.0.1:4433'}
        }), \
             patch.object(HFishModel, 'get_last_timestamp', side_effect=AssertionError('should not read timestamp when probe failed')), \
             patch.object(HFishModel, 'save_logs') as mock_save, \
             patch('hfish_ai_ban.analyze_and_ban_attack_ips') as mock_ai, \
             patch.dict('sys.modules', {
                 'attack_log_sync': __import__('types').SimpleNamespace(
                     get_attack_logs=lambda *args, **kwargs: {'success': False, 'error_code': 'not_found', 'error': '接口不存在(404)'}
                 )
             }, clear=False):
            result = runtime_module.run_hfish_sync()

        self.assertFalse(result['success'])
        self.assertEqual(result['error_code'], 'not_found')
        self.assertIn('404', result['error'])
        mock_save.assert_not_called()
        mock_ai.assert_not_called()

    def test_hfish_model_get_last_timestamp_returns_latest_timestamp(self):
        from database.models import HFishModel

        HFishModel.save_logs([
            {
                'attack_ip': '1.1.1.1',
                'attack_port': 22,
                'protocol_type': 'tcp',
                'service_name': 'ssh',
                'attack_detail': 'first',
                'create_time_str': '2026-03-25 09:00:00',
                'create_time_timestamp': 100,
            },
            {
                'attack_ip': '2.2.2.2',
                'attack_port': 80,
                'protocol_type': 'tcp',
                'service_name': 'http',
                'attack_detail': 'second',
                'create_time_str': '2026-03-25 09:05:00',
                'create_time_timestamp': 200,
            },
        ])

        self.assertEqual(HFishModel.get_last_timestamp(), 200)


    def test_run_hfish_sync_returns_connection_error_before_reading_timestamp(self):
        from web.api import runtime as runtime_module
        from database.models import HFishModel

        with patch.object(runtime_module, '_load_cfg', return_value={
            'hfish': {'host_port': '127.0.0.1:4433', 'api_key': 'k', 'api_base_url': 'https://127.0.0.1:4433'}
        }), \
             patch.object(HFishModel, 'get_last_timestamp', side_effect=AssertionError('should not read timestamp when probe failed')), \
             patch.object(HFishModel, 'save_logs') as mock_save, \
             patch('hfish_ai_ban.analyze_and_ban_attack_ips') as mock_ai, \
             patch.dict('sys.modules', {
                 'attack_log_sync': __import__('types').SimpleNamespace(
                     get_attack_logs=lambda *args, **kwargs: {'success': False, 'error_code': 'connection_refused', 'error': '连接被拒绝，目标主机未响应（请确认 HFish 服务已启动）'}
                 )
             }, clear=False):
            result = runtime_module.run_hfish_sync()

        self.assertFalse(result['success'])
        self.assertEqual(result['error_code'], 'connection_refused')
        self.assertIn('连接被拒绝', result['error'])
        mock_save.assert_not_called()
        mock_ai.assert_not_called()

    def test_run_hfish_sync_falls_back_to_zero_when_timestamp_method_missing(self):
        from web.api import runtime as runtime_module
        from database.models import HFishModel

        sample_logs = [{'attack_ip': '1.1.1.1', 'create_time_str': '2026-03-25 09:00:00'}]
        original_get_last_timestamp = getattr(HFishModel, 'get_last_timestamp', None)
        had_get_last_timestamp = hasattr(HFishModel, 'get_last_timestamp')
        if had_get_last_timestamp:
            delattr(HFishModel, 'get_last_timestamp')

        try:
            with patch.object(runtime_module, '_load_cfg', return_value={
                'hfish': {'host_port': '127.0.0.1:4433', 'api_key': 'k', 'api_base_url': 'https://127.0.0.1:4433'}
            }), \
                 patch.object(HFishModel, 'save_logs', return_value=1) as mock_save, \
                 patch('hfish_ai_ban.analyze_and_ban_attack_ips', return_value={'analyzed': 0, 'ban_count': 0}) as mock_ai, \
                 patch.dict('sys.modules', {
                     'attack_log_sync': __import__('types').SimpleNamespace(
                         get_attack_logs=lambda *args, **kwargs: sample_logs
                     )
                 }, clear=False):
                result = runtime_module.run_hfish_sync()
        finally:
            if had_get_last_timestamp:
                setattr(HFishModel, 'get_last_timestamp', original_get_last_timestamp)

        self.assertTrue(result['success'])
        self.assertEqual(result['total'], 1)
        self.assertEqual(result['new'], 1)
        mock_save.assert_called_once_with(sample_logs)
        mock_ai.assert_called_once_with(sample_logs, {
            'hfish': {'host_port': '127.0.0.1:4433', 'api_key': 'k', 'api_base_url': 'https://127.0.0.1:4433'}
        })

