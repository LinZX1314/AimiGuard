"""
S1-02 AI 输出内容安全校验
- 检测AI回复中不应出现的内部系统信息、凭据片段、恶意指令
- 超出安全边界的回复替换为标准降级响应
"""
from __future__ import annotations

import re
from typing import Tuple

# 敏感信息模式
_SENSITIVE_PATTERNS: list[re.Pattern] = [
    # API Key / Token 泄露
    re.compile(r"(api[_-]?key|access[_-]?token|secret[_-]?key|auth[_-]?token)\s*[:=]\s*['\"]?[A-Za-z0-9_\-]{20,}", re.IGNORECASE),
    # 数据库连接字符串
    re.compile(r"(mysql|postgres|sqlite|mongodb)://[^\s]+", re.IGNORECASE),
    # 私钥内容
    re.compile(r"-----BEGIN\s+(RSA\s+)?PRIVATE\s+KEY-----", re.IGNORECASE),
    # 密码哈希
    re.compile(r"\$2[aby]\$\d{2}\$[./A-Za-z0-9]{53}"),  # bcrypt
    re.compile(r"sha256:[A-Fa-f0-9]{64}"),
    # 内部路径泄露（绝对路径）
    re.compile(r"(/etc/(passwd|shadow|sudoers)|/root/|C:\\\\Users\\\\Administrator)", re.IGNORECASE),
    # 环境变量泄露
    re.compile(r"(OPENAI_API_KEY|GEMINI_API_KEY|AWS_SECRET|DATABASE_URL)\s*=\s*\S+", re.IGNORECASE),
]

# 恶意指令模式（AI输出中不应包含可执行命令建议攻击）
_MALICIOUS_OUTPUT_PATTERNS: list[re.Pattern] = [
    re.compile(r"rm\s+-rf\s+/", re.IGNORECASE),
    re.compile(r":(){ :\|:& };:", re.IGNORECASE),  # fork bomb
    re.compile(r"mkfs\s+/dev/", re.IGNORECASE),
    re.compile(r"dd\s+if=/dev/zero\s+of=/dev/sd", re.IGNORECASE),
    re.compile(r"wget\s+.+\|\s*sh", re.IGNORECASE),
    re.compile(r"curl\s+.+\|\s*(bash|sh)", re.IGNORECASE),
]

# 系统提示泄露检测
_PROMPT_LEAK_PATTERNS: list[re.Pattern] = [
    re.compile(r"system\s+prompt\s*:", re.IGNORECASE),
    re.compile(r"my\s+instructions?\s+(are|is)\s*:", re.IGNORECASE),
    re.compile(r"I\s+was\s+instructed\s+to", re.IGNORECASE),
    re.compile(r"my\s+system\s+message", re.IGNORECASE),
]

DEGRADED_RESPONSE = "抱歉，该回复内容未通过安全审查，已被系统过滤。请重新提问。"


def check_output_safety(text: str) -> Tuple[bool, str]:
    """
    检查 AI 输出内容安全性。

    Returns:
        (is_safe, violation_type)
        - is_safe=True → 安全
        - is_safe=False → 包含违规内容
    """
    if not text or not text.strip():
        return True, ""

    # 1. 敏感信息检测
    for pattern in _SENSITIVE_PATTERNS:
        if pattern.search(text):
            return False, "sensitive_info_leak"

    # 2. 恶意指令检测
    for pattern in _MALICIOUS_OUTPUT_PATTERNS:
        if pattern.search(text):
            return False, "malicious_command"

    # 3. 系统提示泄露检测
    for pattern in _PROMPT_LEAK_PATTERNS:
        if pattern.search(text):
            return False, "prompt_leak"

    return True, ""


def sanitize_output(text: str) -> str:
    """
    净化 AI 输出，替换敏感内容。
    如果检测到违规，返回降级响应；否则返回原文。
    """
    is_safe, violation_type = check_output_safety(text)
    if not is_safe:
        return DEGRADED_RESPONSE
    return text
