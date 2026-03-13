import os
import json
import sys
from datetime import datetime

from openai import OpenAI

# 确保可以导入项目中的模块
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if BASE_DIR not in sys.path:
    sys.path.append(BASE_DIR)

try:
    from network_scan import scan_hosts, parse_scan_results
except ImportError:
    # 针对在其他目录下运行时的路径调整
    sys.path.append(os.path.join(BASE_DIR, "plugin", "nmap_plugin"))
    from network_scan import scan_hosts, parse_scan_results

from database.models import ScannerModel
from utils.logger import log


class AIScanner:
    def __init__(self, config_path=None):
        if config_path is None:
            config_path = os.path.join(BASE_DIR, "config.json")

        with open(config_path, "r", encoding="utf-8") as f:
            self.config = json.load(f)

        self.ai_config = self.config.get("ai", {})
        self.analysis_map = self.ai_config.get("analysis_map", {})
        self.api_url = self.ai_config.get("api_url")
        self.api_key = self.ai_config.get("api_key")
        self.model = self.ai_config.get("model")
        self.timeout = self.ai_config.get("timeout", 160)

        self.client = OpenAI(api_key=self.api_key, base_url=self.api_url)

    def _get_prompt(self, key, default=""):
        """统一从 ai.analysis_map 获取提示词，并兼容旧字段。"""
        value = self.analysis_map.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()

        # 兼容历史字段：chat_system_prompt 作为通用系统提示词
        legacy = self.ai_config.get("system_prompt")
        if isinstance(legacy, str) and legacy.strip():
            return legacy.strip()

        return default

    def get_tools_definition(self):
        return [
            {
                "type": "function",
                "function": {
                    "name": "nmap_scan",
                    "description": "执行一次 Nmap 网络扫描",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "target": {
                                "type": "string",
                                "description": "要扫描的目标 IP、域名或网段",
                            },
                            "arguments": {
                                "type": "string",
                                "description": "Nmap 参数，如 -sV -T4 -O",
                            },
                        },
                        "required": ["target"],
                    },
                },
            }
        ]

    def chat_and_scan_stream(self, user_input, history=None):
        """
        使用 OpenAI 库的流式 + 函数调用
        """
        system_prompt = self._get_prompt(
            "nmap_scan_system_prompt",
            "你是一个专业的网络安全助手，拥有实时的 Nmap 扫描能力。请直接回复用户，如果需要扫描，请调用工具。",
        )

        messages = [
            {
                "role": "system",
                "content": system_prompt,
            }
        ]
        if history:
            messages.extend(history)
        messages.append({"role": "user", "content": user_input})

        try:
            log("AI", f"发起请求: {self.model}")

            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                tools=self.get_tools_definition(),
                stream=True,
            )

            content_buffer = ""
            # 按 index 累积工具调用分片，key=index, value={id, name, arguments_buf}
            tool_calls_buf: dict[int, dict] = {}
            _status_yielded = False

            for chunk in response:
                choice = chunk.choices[0]
                delta = choice.delta

                if delta.content:
                    content_buffer += delta.content
                    yield {"type": "text", "content": delta.content}

                if delta.tool_calls:
                    if not _status_yielded:
                        yield {"type": "status", "content": "AI 正在构造扫描指令..."}
                        _status_yielded = True
                    for tc in delta.tool_calls:
                        idx = tc.index if tc.index is not None else 0
                        if idx not in tool_calls_buf:
                            tool_calls_buf[idx] = {
                                "id": tc.id or "",
                                "name": tc.function.name or "",
                                "arguments": "",
                            }
                        else:
                            # 后续分片可能补充 id/name
                            if tc.id:
                                tool_calls_buf[idx]["id"] = tc.id
                            if tc.function.name:
                                tool_calls_buf[idx]["name"] = tc.function.name
                        if tc.function.arguments:
                            tool_calls_buf[idx]["arguments"] += tc.function.arguments

            # 还原有序工具列表
            tool_calls = [tool_calls_buf[k] for k in sorted(tool_calls_buf.keys())]

            if tool_calls:
                tool_call = tool_calls[0]
                func_name = tool_call["name"]

                if func_name == "nmap_scan":
                    raw_args = tool_call.get("arguments", "{}")
                    log("AI", f"准备执行工具: {func_name}, 参数: {raw_args}")

                    try:
                        args = json.loads(raw_args)
                    except json.JSONDecodeError:
                        yield {"type": "error", "content": "AI 生成的扫描参数格式错误"}
                        return

                    target = args.get("target")
                    nmap_args = args.get("arguments", "-sV -T4")

                    yield {"type": "status", "content": f"正在启动 Nmap 扫描目标: {target}..."}

                    nm = scan_hosts(target, nmap_args)
                    if not nm:
                        yield {"type": "error", "content": "Nmap 执行失败，请检查系统环境。"}
                        return

                    hosts_data = parse_scan_results(nm)

                    scan_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    scan_id = ScannerModel.create_scan([target], nmap_args, scan_time)
                    save_to_db(scan_id, hosts_data)

                    yield {"type": "scan", "scan_id": scan_id}
                    yield {"type": "status", "content": "扫描完成，分析中..."}

                    messages.append(
                        {
                            "role": "assistant",
                            "content": content_buffer if content_buffer else "",
                            "tool_calls": [
                                {
                                    "id": tc["id"],
                                    "type": "function",
                                    "function": {
                                        "name": tc["name"],
                                        "arguments": tc["arguments"],
                                    },
                                }
                                for tc in tool_calls
                            ],
                        }
                    )
                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": tool_call["id"],
                            "name": func_name,
                            "content": json.dumps(hosts_data[:15], ensure_ascii=False),
                        }
                    )

                    log("AI", "发起结果解读请求...")
                    final_response = self.client.chat.completions.create(
                        model=self.model,
                        messages=messages,
                        stream=True,
                    )

                    for chunk in final_response:
                        if chunk.choices[0].delta.content:
                            yield {"type": "text", "content": chunk.choices[0].delta.content}

        except Exception as e:
            import traceback

            traceback.print_exc()
            yield {"type": "error", "content": f"AI 引擎内部错误: {str(e)}"}


def save_to_db(scan_id, hosts_data):
    """保存扫描结果到数据库（与 network_scan.save_to_db 逻辑一致）"""
    if not hosts_data:
        return
    scan_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    count = 0
    for host in hosts_data:
        try:
            open_ports_str = ','.join(map(str, host.get('open_ports') or []))
            services_list = []
            for svc in host.get('services') or []:
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
