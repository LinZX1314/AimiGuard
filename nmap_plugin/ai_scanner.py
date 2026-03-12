import os
import json
import sys
from datetime import datetime

# 确保可以导入项目中的模块
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.append(BASE_DIR)

try:
    from network_scan import scan_hosts, parse_scan_results
except ImportError:
    # 针对在其他目录下运行时的路径调整
    sys.path.append(os.path.join(BASE_DIR, "nmap_plugin"))
    from network_scan import scan_hosts, parse_scan_results

from database.models import ScannerModel, NmapModel
from openai import OpenAI
from utils.logger import log


class AIScanner:
    def __init__(self, config_path=None):
        if config_path is None:
            config_path = os.path.join(BASE_DIR, "config.json")

        with open(config_path, "r", encoding="utf-8") as f:
            self.config = json.load(f)

        self.ai_config = self.config.get("ai", {})
        self.api_url = self.ai_config.get("api_url")
        self.api_key = self.ai_config.get("api_key")
        self.model = self.ai_config.get("model")
        self.timeout = self.ai_config.get("timeout", 160)

        # 初始化 OpenAI 客户端
        self.client = OpenAI(
            api_key=self.api_key,
            base_url=self.api_url,
            timeout=self.timeout
        )

    def get_tools_definition(self):
        """定义 AI 可调用的网络工具"""
        return [
            {
                "type": "function",
                "function": {
                    "name": "nmap_scan",
                    "description": "执行 Nmap 扫描以发现主机、端口、服务和操作系统信息。",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "target": {
                                "type": "string",
                                "description": "要扫描的目标 IP、域名或网段"
                            },
                            "arguments": {
                                "type": "string",
                                "description": "Nmap 参数，如 -sV -T4 -O"
                            }
                        },
                        "required": ["target"]
                    }
                }
            }
        ]

    def chat_and_scan_stream(self, user_input, history=None):
        """
        使用 OpenAI 库的流式 + 函数调用
        """
        messages = [
            {"role": "system", "content": "你是一个专业的网络安全助手，拥有实时的 Nmap 扫描能力。请直接回复用户，如果需要扫描，请调用工具。"}
        ]
        if history:
            messages.extend(history)
        messages.append({"role": "user", "content": user_input})

        # 第一步：发起对话
        try:
            log("AI", f"发起请求: {self.model}")

            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                tools=self.get_tools_definition(),
                stream=True
            )

            # 收集完整回复和工具调用
            content_buffer = ""
            tool_calls = []

            for chunk in response:
                choice = chunk.choices[0]
                delta = choice.delta

                # 处理文字流
                if delta.content:
                    content_buffer += delta.content
                    yield {"type": "text", "content": delta.content}

                # 处理工具调用
                if delta.tool_calls:
                    for tc in delta.tool_calls:
                        # 收集工具调用
                        tool_calls.append({
                            "id": tc.id,
                            "name": tc.function.name,
                            "arguments": tc.function.arguments
                        })
                        yield {"type": "status", "content": "AI 正在构造扫描指令..."}

            # 第二步：如果有工具调用，执行工具
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

                    # 执行扫描
                    nm = scan_hosts(target, nmap_args)
                    if not nm:
                        yield {"type": "error", "content": "Nmap 执行失败，请检查系统环境。"}
                        return

                    hosts_data = parse_scan_results(nm)

                    # 保存入库
                    scan_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    scan_id = ScannerModel.create_scan([target], nmap_args, scan_time)
                    save_to_db(scan_id, hosts_data)

                    yield {"type": "scan", "scan_id": scan_id}
                    yield {"type": "status", "content": "扫描完成，分析中..."}

                    # 第三步：将结果发回 AI 继续对话
                    messages.append({
                        "role": "assistant",
                        "content": content_buffer if content_buffer else "",
                        "tool_calls": [
                            {
                                "id": tc["id"],
                                "type": "function",
                                "function": {
                                    "name": tc["name"],
                                    "arguments": tc["arguments"]
                                }
                            }
                            for tc in tool_calls
                        ]
                    })
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call["id"],
                        "name": func_name,
                        "content": json.dumps(hosts_data[:15], ensure_ascii=False)
                    })

                    log("AI", "发起结果解读请求...")
                    final_response = self.client.chat.completions.create(
                        model=self.model,
                        messages=messages,
                        stream=True
                    )

                    for chunk in final_response:
                        if chunk.choices[0].delta.content:
                            yield {"type": "text", "content": chunk.choices[0].delta.content}

        except Exception as e:
            import traceback
            traceback.print_exc()
            yield {"type": "error", "content": f"AI 引擎内部错误: {str(e)}"}


def save_to_db(scan_id, hosts_data):
    """保存扫描结果到数据库"""
    for host_info in hosts_data:
        host = host_info.get("host")
        if not host:
            continue

        NmapModel.create_nmap(
            scan_id=scan_id,
            host=host,
            state=host_info.get("state", "unknown"),
            protocol=host_info.get("protocol", "tcp"),
            port=host_info.get("port", ""),
            service=host_info.get("service", ""),
            version=host_info.get("version", ""),
            os_match=host_info.get("os_match", "")
        )

