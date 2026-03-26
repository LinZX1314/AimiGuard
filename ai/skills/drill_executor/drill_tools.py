"""
Drill Skill 专用工具定义
这些工具会在演练模式下暴露给 AI Agent
"""

# ─── 工具定义缓存（避免每次调用重建）───────────────────────────────────
_TOOL_DEFS_CACHE: list[dict] | None = None


def clear_tool_cache():
    """清除工具定义缓存，强制重新构建"""
    global _TOOL_DEFS_CACHE
    _TOOL_DEFS_CACHE = None


def get_drill_tool_definitions() -> list[dict]:
    """返回演练 Skill 的工具定义列表（带缓存）"""
    global _TOOL_DEFS_CACHE
    if _TOOL_DEFS_CACHE is None:
        _TOOL_DEFS_CACHE = [
            {
                "type": "function",
                "function": {
                    "name": "network_scan",
                    "description": "扫描目标网络，发现存活主机和开放端口",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "target": {
                                "type": "string",
                                "description": "IP或网段，如 192.168.1.0/24",
                            },
                            "ports": {
                                "type": "string",
                                "description": "端口列表",
                                "default": "21,22,23,80,81,135,139,443,445,1433,3306,5432,6379,8080,8443",
                            },
                        },
                        "required": ["target"],
                    },
                },
            },
            # ── Web截图 ─────────────────────────────────────────────────────────
            {
                "type": "function",
                "function": {
                    "name": "web_screenshot",
                    "description": "对Web服务页面截图",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "url": {"type": "string", "description": "完整URL"},
                            "ip": {"type": "string", "description": "目标IP"},
                            "port": {"type": "integer", "description": "端口"},
                        },
                        "required": ["url", "ip", "port"],
                    },
                },
            },
            # ── SSH弱口令 ───────────────────────────────────────────────────────
            {
                "type": "function",
                "function": {
                    "name": "bruteforce_ssh",
                    "description": "检测SSH服务弱口令（端口22）",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "target_ip": {"type": "string", "description": "目标IP"},
                            "port": {
                                "type": "integer",
                                "description": "端口",
                                "default": 22,
                            },
                        },
                        "required": ["target_ip"],
                    },
                },
            },
            # ── RDP弱口令 ───────────────────────────────────────────────────────
            {
                "type": "function",
                "function": {
                    "name": "bruteforce_rdp",
                    "description": "检测RDP服务弱口令（端口3389）",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "target_ip": {"type": "string", "description": "目标IP"},
                            "port": {
                                "type": "integer",
                                "description": "端口",
                                "default": 3389,
                            },
                        },
                        "required": ["target_ip"],
                    },
                },
            },
            # ── MySQL弱口令 ─────────────────────────────────────────────────────
            {
                "type": "function",
                "function": {
                    "name": "bruteforce_mysql",
                    "description": "检测MySQL服务弱口令（端口3306）",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "target_ip": {"type": "string", "description": "目标IP"},
                            "port": {
                                "type": "integer",
                                "description": "端口",
                                "default": 3306,
                            },
                        },
                        "required": ["target_ip"],
                    },
                },
            },
            # ── 蜜罐审计 ────────────────────────────────────────────────────────
            {
                "type": "function",
                "function": {
                    "name": "honeypot_audit",
                    "description": "查询HFish蜜罐攻击日志",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "service_name": {
                                "type": "string",
                                "description": "服务筛选，如ssh",
                            },
                            "limit": {
                                "type": "integer",
                                "description": "记录数",
                                "default": 50,
                            },
                        },
                        "required": [],
                    },
                },
            },
            # ── 报告生成 ────────────────────────────────────────────────────────
            {
                "type": "function",
                "function": {
                    "name": "generate_report",
                    "description": "生成安全演练报告",
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
            # ── 本机IP查询 ──────────────────────────────────────────────────────
            {
                "type": "function",
                "function": {
                    "name": "get_local_ip",
                    "description": "获取本机IP",
                    "parameters": {
                        "type": "object",
                        "properties": {},
                        "required": [],
                    },
                },
            },
        ]
    return _TOOL_DEFS_CACHE
