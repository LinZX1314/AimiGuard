import os
import json
import re
import requests
import nmap
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

    def _call_llm(self, prompt, system_prompt="/no_think 你是一个专业的网络安全扫描助手。"):
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.1
        }
        try:
            response = requests.post(self.api_url, headers=headers, json=payload, timeout=self.timeout)
            response.raise_for_status()
            result = response.json()
            return result.get("choices", [{}])[0].get("message", {}).get("content", "")
        except Exception as e:
            return f"Error calling AI: {str(e)}"

    def parse_instruction(self, user_input):
        """
        使用 LLM 将自然语言转换为 Nmap 参数
        """
        prompt = f"""
请将以下用户的扫描指令转换为 Nmap 扫描参数。
用户的输入: "{user_input}"

请仅返回如下 JSON 格式 (不要包含 Markdown 代码块标签，也不要包含任何其他文字):
{{
    "target": "目标IP或范围",
    "arguments": "nmap参数",
    "description": "对本次扫描任务的简短描述"
}}

默认参数建议使用: "-sV -T4" (如果用户没有特别指定)。
如果你认为用户的问题不是扫描指令，或者缺少必要的目标 IP 信息，请在 target 中返回 "none"。
"""
        response = self._call_llm(prompt)
        # 清理可能的 markdown 代码块
        clean_response = re.sub(r'```json\s*|\s*```', '', response).strip()
        try:
            return json.loads(clean_response)
        except:
            # 尝试回退处理
            return {"target": "none", "arguments": "", "description": "无法解析指令"}

    def analyze_results(self, user_input, scan_results):
        """
        使用 LLM 分析扫描结果并回答用户
        """
        # 精简结果以避免超出 token 限制
        simplified_results = []
        for host in scan_results[:20]: # 限制前20个主机
            simplified_results.append({
                "ip": host.get("ip"),
                "hostname": host.get("hostname"),
                "state": host.get("state"),
                "ports": [s.get("port") for s in host.get("services", [])[:10]]
            })

        prompt = f"""
用户的问题是: "{user_input}"

以下是 Nmap 扫描的结果数据:
{json.dumps(simplified_results, ensure_ascii=False, indent=2)}

请作为安全专家，结合扫描结果回答用户的问题。回答要专业、简洁，重点关注开放的敏感端口和潜在风险。使用中文回答。
"""
        return self._call_llm(prompt)

    def chat_and_scan(self, user_input):
        """
        核心流程：对话 -> 扫描 -> 解释
        """
        print(f"[*] AI 正在解析指令: {user_input}")
        instruction = self.parse_instruction(user_input)
        
        target = instruction.get("target")
        arguments = instruction.get("arguments", "-sV -T4")
        description = instruction.get("description", "")

        if not target or target.lower() == "none":
            return f"抱歉，我无法从您的指令中提取到有效的扫描目标。请确保提供了 IP 地址、域名或网段（例如：'帮我扫一下 192.168.1.1'）。"

        print(f"[*] 解析结果: 描述='{description}', 目标='{target}', 参数='{arguments}'")
        print(f"[*] 正在开始 Nmap 扫描，请稍候...")
        
        try:
            # 执行扫描
            nm = scan_hosts(target, arguments)
            if not nm:
                return "扫描执行失败，请检查网络连接或 Nmap 路径配置。"
            
            hosts_data = parse_scan_results(nm)
            
            # 保存到数据库
            from network_scan import save_to_db
            scan_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            scan_id = ScannerModel.create_scan([target], arguments, scan_time)
            save_to_db(scan_id, hosts_data)
            
            print(f"[*] 扫描完成，发现 {len(hosts_data)} 个存活主机。正在请求 AI 进行结果分析...")
            
            # 分析结果
            analysis = self.analyze_results(user_input, hosts_data)
            
            return {
                "scan_id": scan_id,
                "description": description,
                "target": target,
                "arguments": arguments,
                "hosts_count": len(hosts_data),
                "analysis": analysis
            }
            
        except Exception as e:
            return f"执行扫描任务时发生错误: {str(e)}"

if __name__ == "__main__":
    scanner = AIScanner()
    if len(sys.argv) > 1:
        query = " ".join(sys.argv[1:])
        result = scanner.chat_and_scan(query)
        if isinstance(result, dict):
            print("\n=== 扫描结果分析 ===")
            print(result["analysis"])
        else:
            print(result)
    else:
        print("用法: python ai_scanner.py <你的扫描指令>")
        print("示例: python ai_scanner.py 扫描 127.0.0.1 看看开了哪些端口")
