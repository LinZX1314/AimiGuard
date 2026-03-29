"""
Incident Skill 专用工具定义
这些工具会在应急响应模式下暴露给 AI Agent
"""

_TOOL_DEFS_CACHE: list[dict] | None = None


def clear_incident_tool_cache():
    """清除工具定义缓存，强制重新构建"""
    global _TOOL_DEFS_CACHE
    _TOOL_DEFS_CACHE = None


def get_incident_tool_definitions() -> list[dict]:
    """返回应急响应 Skill 的工具定义列表（带缓存）"""
    global _TOOL_DEFS_CACHE
    if _TOOL_DEFS_CACHE is None:
        _TOOL_DEFS_CACHE = [
            # ── 流量日志 ────────────────────────────────────────────────────────
            {
                "type": "function",
                "function": {
                    "name": "get_traffic_logs",
                    "description": "获取网络流量日志，分析异常流量",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "time_range": {
                                "type": "string",
                                "description": "时间范围，如 1小时内",
                            },
                            "port_filter": {
                                "type": "string",
                                "description": "端口过滤，如 4705",
                            },
                        },
                        "required": [],
                    },
                },
            },
            # ── 数据包捕获 ──────────────────────────────────────────────────────
            {
                "type": "function",
                "function": {
                    "name": "get_packet_capture",
                    "description": "获取数据包捕获内容，分析攻击特征",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "source_ip": {
                                "type": "string",
                                "description": "源IP过滤",
                            },
                            "port": {
                                "type": "string",
                                "description": "目标端口，如 4705",
                            },
                        },
                        "required": [],
                    },
                },
            },
            # ── 生成报告 ────────────────────────────────────────────────────────
            {
                "type": "function",
                "function": {
                    "name": "generate_incident_report",
                    "description": "生成安全应急响应报告",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "exec_summary": {
                                "type": "string",
                                "description": "执行摘要",
                            },
                        },
                        "required": ["exec_summary"],
                    },
                },
            },
            # ── 执行封禁 ────────────────────────────────────────────────────────
            {
                "type": "function",
                "function": {
                    "name": "apply_ban_policy",
                    "description": "执行封禁策略，阻断攻击流量",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "target": {
                                "type": "string",
                                "description": "封禁目标，可以是IP或端口",
                            },
                            "policy_type": {
                                "type": "string",
                                "description": "封禁类型：port（端口封禁）或 ip（IP封禁）",
                            },
                        },
                        "required": ["target", "policy_type"],
                    },
                },
            },
        ]
    return _TOOL_DEFS_CACHE
