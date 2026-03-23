import os
import tempfile
import unittest
from datetime import datetime, timedelta
from unittest.mock import patch

import database.db as db_module
from database.models import WorkflowModel
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
        self.assertGreaterEqual(len(templates), 1)
        template_id = templates[0]['id']

        instantiate_response = self.client.post(
            f'/api/v1/workflows/templates/{template_id}/instantiate',
            json={'name': '从模板创建'},
            headers=self.auth_headers(),
        )
        self.assertEqual(instantiate_response.status_code, 200)
        workflow = instantiate_response.get_json()['data']
        self.assertEqual(workflow['name'], '从模板创建')
        self.assertGreater(len(workflow['definition']['nodes']), 0)

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

    def test_scheduler_executes_due_workflow_once(self):
        from web.api import runtime as runtime_module

        workflow_id = WorkflowModel.create({
            'name': '定时调度执行',
            'description': '',
            'category': 'system',
            'status': 'active',
            'trigger_json': {'type': 'schedule', 'enabled': True, 'interval_seconds': 60},
            'definition_json': self.workflow_payload(trigger_type='schedule')['definition'],
            'next_run_at': (datetime.now() - timedelta(seconds=5)).isoformat(),
        })

        with patch('database.models.HFishModel.get_attack_logs', return_value=[]):
            executed = runtime_module.run_workflow_scheduler_once(datetime.now().isoformat())

        self.assertEqual(executed, 1)
        runs = WorkflowModel.get_runs(workflow_id)
        self.assertEqual(len(runs), 1)
        self.assertEqual(runs[0]['trigger_type'], 'schedule')


if __name__ == '__main__':
    unittest.main()
