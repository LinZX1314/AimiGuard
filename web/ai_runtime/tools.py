import json
from datetime import datetime
from typing import Callable

from database.models import ScannerModel
from utils.logger import log as unified_log


class OpenAIToolRegistry:
    def __init__(self):
        self._definitions: dict[str, dict] = {}
        self._handlers: dict[str, Callable] = {}

    def register_function(self, *, name: str, description: str, parameters: dict):
        definition = {
            'type': 'function',
            'function': {
                'name': name,
                'description': description,
                'parameters': parameters,
            },
        }

        def decorator(func):
            self._definitions[name] = definition
            self._handlers[name] = func
            return func

        return decorator

    def get_definitions(self) -> list[dict]:
        return list(self._definitions.values())

    def execute_tool_calls(self, tool_calls: list[dict] | None) -> list[dict]:
        results: list[dict] = []
        for tool_call in tool_calls or []:
            name = tool_call.get('name', '')
            handler = self._handlers.get(name)
            arguments = tool_call.get('arguments')
            if not isinstance(arguments, dict):
                arguments = {}

            if handler is None:
                content = {'ok': False, 'error': f'未知工具: {name}'}
            else:
                try:
                    content = handler(arguments)
                except Exception as exc:
                    content = {'ok': False, 'error': str(exc)}

            if not isinstance(content, str):
                try:
                    content = json.dumps(content, ensure_ascii=False)
                except Exception:
                    content = str(content)

            results.append({
                'role': 'tool',
                'tool_call_id': tool_call.get('id', ''),
                'name': name,
                'content': content,
            })
        return results


def _save_scan_hosts(scan_id: int, hosts: list[dict], scan_time: str):
    count = 0
    for host in hosts:
        try:
            open_ports_str = ','.join(map(str, host.get('open_ports', []) or []))
            services_list = []
            for svc in host.get('services', []) or []:
                svc_str = f"{svc.get('port', '')}/{svc.get('service', '')}"
                if svc.get('product'):
                    svc_str += f" {svc['product']}"
                if svc.get('version'):
                    svc_str += f" {svc['version']}"
                services_list.append(svc_str)
            services_str = '; '.join(services_list)
            ScannerModel.save_host(scan_id, host, scan_time, open_ports_str, services_str)
            ScannerModel.upsert_asset(scan_id, host, scan_time)
            count += 1
        except Exception:
            pass

    if count > 0:
        ScannerModel.increment_hosts_count(scan_id, count)


tool_registry = OpenAIToolRegistry()


@tool_registry.register_function(
    name='nmap_scan',
    description='执行 Nmap 网络扫描，返回主机与端口信息',
    parameters={
        'type': 'object',
        'properties': {
            'target': {'type': 'string', 'description': '目标 IP、域名或网段'},
            'arguments': {'type': 'string', 'description': 'nmap 参数'},
        },
        'required': ['target'],
    },
)
def _exec_nmap_scan(args: dict):
    from plugin.network_scan import scan_hosts, parse_scan_results

    target = str(args.get('target') or '').strip()
    raw_arguments = args.get('arguments', '-sV -O -T4')
    nmap_arguments = str(raw_arguments).strip() or '-sV -O -T4'

    if not target:
        return {'ok': False, 'error': '缺少 target 参数'}

    nm = scan_hosts(target, nmap_arguments)
    if not nm:
        return {'ok': False, 'error': 'Nmap 执行失败'}

    hosts = parse_scan_results(nm)
    scan_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    scan_id = ScannerModel.create_scan([target], nmap_arguments, scan_time)

    try:
        _save_scan_hosts(scan_id, hosts, scan_time)
    except Exception as exc:
        unified_log('AIChat', f'nmap 结果写库失败: {exc}', 'WARN')

    return {
        'ok': True,
        'scan_id': scan_id,
        'target': target,
        'arguments': nmap_arguments,
        'host_count': len(hosts),
        'hosts': hosts[:15],
    }


def get_tool_definitions() -> list[dict]:
    return tool_registry.get_definitions()


def execute_tool_calls(tool_calls: list[dict] | None) -> list[dict]:
    return tool_registry.execute_tool_calls(tool_calls)
