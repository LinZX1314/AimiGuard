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
            tool_calls_dict = {}  # 用字典按 index 合并

            for chunk in response:
                choice = chunk.choices[0]
                delta = choice.delta

                # 处理文字流
                if delta.content:
                    content_buffer += delta.content
                    yield {"type": "text", "content": delta.content}

                # 处理工具调用 - 需要按 index 合并
                if delta.tool_calls:
                    for tc in delta.tool_calls:
                        idx = tc.index
                        if idx not in tool_calls_dict:
                            tool_calls_dict[idx] = {
                                "id": tc.id,
                                "name": tc.function.name or "",
                                "arguments": tc.function.arguments or ""
                            }
                        else:
                            # 合并分片的 arguments
                            if tc.function.name:
                                tool_calls_dict[idx]["name"] = tc.function.name
                            if tc.function.arguments:
                                tool_calls_dict[idx]["arguments"] += tc.function.arguments

            # 转换为列表
            tool_calls = list(tool_calls_dict.values())

            # 第二步：如果有工具调用，执行工具
            if tool_calls:
                yield {"type": "status", "content": f"AI 正在调用 {len(tool_calls)} 个工具..."}

                # 收集所有工具的执行结果
                tool_results = []

                # 处理所有工具调用
                for idx, tool_call in enumerate(tool_calls):
                    func_name = tool_call["name"]

                    if func_name == "nmap_scan":
                        raw_args = tool_call.get("arguments", "{}")
                        log("AI", f"执行工具 #{idx+1}: {func_name}, 参数: {raw_args}")

                        try:
                            args = json.loads(raw_args)
                        except json.JSONDecodeError:
                            yield {"type": "error", "content": f"工具 #{idx+1} 参数格式错误"}
                            continue

                        target = args.get("target")
                        nmap_args = args.get("arguments", "-sV -T4")

                        yield {"type": "status", "content": f"正在启动 Nmap 扫描目标: {target}..."}

                        # 执行扫描
                        nm = scan_hosts(target, nmap_args)
                        if not nm:
                            yield {"type": "error", "content": f"Nmap 执行失败: {target}"}
                            continue

                        hosts_data = parse_scan_results(nm)

                        # 保存入库
                        scan_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                        scan_id = ScannerModel.create_scan([target], nmap_args, scan_time)
                        save_to_db(scan_id, hosts_data)

                        yield {"type": "scan", "scan_id": scan_id}
                        yield {"type": "status", "content": f"扫描 {target} 完成，发现 {len(hosts_data)} 台主机"}

                        # 记录工具结果
                        tool_results.append({
                            "tool_call_id": tool_call["id"],
                            "name": func_name,
                            "content": json.dumps(hosts_data[:15], ensure_ascii=False)
                        })

                # 所有工具调用完成后，将结果发回 AI 继续对话
                if tool_results:
                    # 构建 tool_calls 消息
                    tool_calls_msg = []
                    for tc in tool_calls:
                        tc_id = tc["id"] or f"call_{tc.get('index', 0)}"
                        tool_calls_msg.append({
                            "id": tc_id,
                            "type": "function",
                            "function": {
                                "name": tc["name"],
                                "arguments": tc["arguments"]
                            }
                        })

                    messages.append({
                        "role": "assistant",
                        "content": content_buffer if content_buffer else "",
                        "tool_calls": tool_calls_msg
                    })

                    # 添加所有工具的结果
                    for result in tool_results:
                        messages.append({
                            "role": "tool",
                            "tool_call_id": result["tool_call_id"],
                            "name": result["name"],
                            "content": result["content"]
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

