"""
Drill Skill 专用工具定义
这些工具会在演练模式下暴露给 AI Agent
"""

# ─── 文档分析工具 ──────────────────────────────────────────────────────────────


def get_drill_tool_definitions() -> list[dict]:
    """返回演练 Skill 的工具定义列表"""
    return [
        # ── 文档与规划 ────────────────────────────────────────────────────────
        {
            'type': 'function',
            'function': {
                'name': 'drill_analyze_document',
                'description': (
                    '【文档分析】当用户上传了安全演练文档后，使用此工具解析文档内容，'
                    '提取：目标系统、扫描范围、重点服务、演练要求等关键信息。'
                    '此工具是演练的起点，必须首先调用。'
                ),
                'parameters': {
                    'type': 'object',
                    'properties': {
                        'document_content': {
                            'type': 'string',
                            'description': '安全演练文档的完整文本内容',
                        },
                    },
                    'required': ['document_content'],
                },
            },
        },
        {
            'type': 'function',
            'function': {
                'name': 'drill_plan_actions',
                'description': (
                    '【行动计划生成】基于文档分析结果，制定完整的演练执行计划。'
                    '包括：扫描顺序、重点目标、优先检查的服务、需要截图的资产。'
                    '返回分阶段的行动计划，供后续 Agent 循环逐阶段执行。'
                ),
                'parameters': {
                    'type': 'object',
                    'properties': {
                        'analysis_result': {
                            'type': 'string',
                            'description': 'drill_analyze_document 的分析结果',
                        },
                    },
                    'required': ['analysis_result'],
                },
            },
        },

        # ── 网络扫描工具（复用现有能力）────────────────────────────────────────
        {
            'type': 'function',
            'function': {
                'name': 'drill_network_scan',
                'description': (
                    '【网络资产探测】对目标网络进行资产发现和端口扫描。'
                    '发现存活主机、开放端口、服务类型。'
                    '支持：单个IP、网段(CIDR)、多IP逗号分隔。'
                    '这是演练的核心步骤，用于摸清目标网络拓扑。'
                ),
                'parameters': {
                    'type': 'object',
                    'properties': {
                        'target': {
                            'type': 'string',
                            'description': '扫描目标：IP、网段(192.168.1.0/24)或多IP(192.168.1.1,192.168.1.2)',
                        },
                        'ports': {
                            'type': 'string',
                            'description': '扫描端口，默认常用端口',
                            'default': '21,22,23,80,81,135,139,443,445,1433,3306,5432,6379,8080,8443',
                        },
                        'threads': {
                            'type': 'integer',
                            'description': '扫描线程数',
                            'default': 6000,
                        },
                    },
                    'required': ['target'],
                },
            },
        },
        {
            'type': 'function',
            'function': {
                'name': 'drill_web_screenshot',
                'description': (
                    '【Web界面截图】对已发现的目标Web服务进行页面截图。'
                    '用于记录Web系统的登录页面、管理后台、认证界面等。'
                    '截图结果将自动保存到截图库中。'
                ),
                'parameters': {
                    'type': 'object',
                    'properties': {
                        'url': {
                            'type': 'string',
                            'description': '完整URL，如 http://192.168.1.1 或 https://example.com:8443',
                        },
                        'ip': {
                            'type': 'string',
                            'description': '目标IP地址',
                        },
                        'port': {
                            'type': 'integer',
                            'description': '端口号',
                        },
                    },
                    'required': ['url', 'ip', 'port'],
                },
            },
        },

        # ── 弱口令检测工具 ────────────────────────────────────────────────────
        {
            'type': 'function',
            'function': {
                'name': 'drill_bruteforce_ssh',
                'description': (
                    '【SSH弱口令检测】对已发现的SSH服务(端口22)进行弱口令检测。'
                    '使用常见弱口令字典（root/root, admin/admin, password/123456等）进行测试。'
                    '仅用于授权的安全演练环境。'
                ),
                'parameters': {
                    'type': 'object',
                    'properties': {
                        'target_ip': {
                            'type': 'string',
                            'description': '目标SSH服务器IP',
                        },
                        'port': {
                            'type': 'integer',
                            'description': 'SSH端口，默认22',
                            'default': 22,
                        },
                    },
                    'required': ['target_ip'],
                },
            },
        },
        {
            'type': 'function',
            'function': {
                'name': 'drill_bruteforce_rdp',
                'description': (
                    '【RDP远程桌面弱口令检测】对已发现的RDP服务(端口3389)进行弱口令检测。'
                    '使用常见弱口令字典进行测试。'
                    '仅用于授权的安全演练环境。'
                ),
                'parameters': {
                    'type': 'object',
                    'properties': {
                        'target_ip': {
                            'type': 'string',
                            'description': '目标RDP服务器IP',
                        },
                        'port': {
                            'type': 'integer',
                            'description': 'RDP端口，默认3389',
                            'default': 3389,
                        },
                    },
                    'required': ['target_ip'],
                },
            },
        },
        {
            'type': 'function',
            'function': {
                'name': 'drill_bruteforce_mysql',
                'description': (
                    '【MySQL数据库弱口令检测】对已发现的MySQL服务(端口3306)进行弱口令检测。'
                    '使用常见弱口令字典测试root等高权限账户。'
                    '仅用于授权的安全演练环境。'
                ),
                'parameters': {
                    'type': 'object',
                    'properties': {
                        'target_ip': {
                            'type': 'string',
                            'description': '目标MySQL服务器IP',
                        },
                        'port': {
                            'type': 'integer',
                            'description': 'MySQL端口，默认3306',
                            'default': 3306,
                        },
                    },
                    'required': ['target_ip'],
                },
            },
        },

        # ── 蜜罐审计工具 ─────────────────────────────────────────────────────
        {
            'type': 'function',
            'function': {
                'name': 'drill_honeypot_audit',
                'description': (
                    '【蜜罐日志审计】查询HFish蜜罐系统的攻击日志。'
                    '获取攻击来源IP、攻击时间、服务类型、来源地区等详细信息。'
                    '用于分析内网或外网遭受的攻击情况。'
                ),
                'parameters': {
                    'type': 'object',
                    'properties': {
                        'service_name': {
                            'type': 'string',
                            'description': '服务名称筛选，如 ssh、http、mysql、redis 等',
                        },
                        'limit': {
                            'type': 'integer',
                            'description': '返回记录数，默认50条',
                            'default': 50,
                        },
                    },
                    'required': [],
                },
            },
        },
        {
            'type': 'function',
            'function': {
                'name': 'drill_honeypot_stats',
                'description': (
                    '【蜜罐态势统计】获取HFish蜜罐的整体态势统计。'
                    '包括：总攻击次数、热门攻击服务Top10、攻击来源Top10、7天攻击趋势。'
                ),
                'parameters': {
                    'type': 'object',
                    'properties': {},
                    'required': [],
                },
            },
        },

        # ── 封禁工具 ─────────────────────────────────────────────────────────
        {
            'type': 'function',
            'function': {
                'name': 'drill_ban_ip',
                'description': (
                    '【封禁恶意IP】将已确认的恶意IP添加到交换机ACL封禁列表。'
                    '用于在演练中发现攻击者后主动防御。'
                    '需要传入要封禁的IP地址。'
                ),
                'parameters': {
                    'type': 'object',
                    'properties': {
                        'target_ip': {
                            'type': 'string',
                            'description': '要封禁的恶意IP地址',
                        },
                        'reason': {
                            'type': 'string',
                            'description': '封禁原因描述',
                        },
                    },
                    'required': ['target_ip'],
                },
            },
        },

        # ── 报告生成 ─────────────────────────────────────────────────────────
        {
            'type': 'function',
            'function': {
                'name': 'drill_generate_report',
                'description': (
                    '【生成演练报告】在所有演练步骤完成后，生成完整的安全演练报告。'
                    '报告包含：执行摘要、发现的安全问题、漏洞列表、截图证据、修复建议。'
                    '返回格式化的Markdown报告内容。'
                ),
                'parameters': {
                    'type': 'object',
                    'properties': {
                        'exec_summary': {
                            'type': 'string',
                            'description': '演练执行摘要',
                        },
                        'findings': {
                            'type': 'string',
                            'description': '发现的安全问题列表（JSON格式）',
                        },
                        'scan_results': {
                            'type': 'string',
                            'description': '扫描结果摘要',
                        },
                        'screenshot_count': {
                            'type': 'integer',
                            'description': '截图数量',
                        },
                        'bruteforce_results': {
                            'type': 'string',
                            'description': '弱口令检测结果',
                        },
                        'honeypot_summary': {
                            'type': 'string',
                            'description': '蜜罐审计摘要',
                        },
                    },
                    'required': ['exec_summary'],
                },
            },
        },

        # ── 状态查询 ─────────────────────────────────────────────────────────
        {
            'type': 'function',
            'function': {
                'name': 'drill_get_status',
                'description': '【演练状态查询】查询当前演练的进度和已收集的证据。用于 Agent 判断下一步行动。',
                'parameters': {
                    'type': 'object',
                    'properties': {},
                    'required': [],
                },
            },
        },

        # ── 系统信息 ─────────────────────────────────────────────────────────
        {
            'type': 'function',
            'function': {
                'name': 'drill_get_local_ip',
                'description': (
                    '【本机IP查询】获取当前运行系统的 IP 地址信息。'
                    '返回：本机局域网IP（内网）、公网IP（外网）、主机名。'
                    '在演练前使用，确认本机网络环境。'
                ),
                'parameters': {
                    'type': 'object',
                    'properties': {},
                    'required': [],
                },
            },
        },
    ]
