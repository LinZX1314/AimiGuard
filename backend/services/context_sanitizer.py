"""
S3-01 上下文输入来源可信度校验
- 对进入 AI Prompt 的外部数据做可信度标记
- 外部来源数据在 Prompt 中以明确边界隔离
- 为每类上下文数据定义最大长度、允许字符集、危险模式过滤
"""
from __future__ import annotations

import re
from enum import Enum
from typing import Any, Dict, Tuple


class TrustLevel(str, Enum):
    HIGH = "high"       # 内部系统生成（扫描结果、AI评分）
    MEDIUM = "medium"   # 用户提交但经过验证（IP地址、端口号）
    LOW = "low"         # 外部来源未验证（告警原始载荷、用户描述文本）


# 各类上下文数据的安全策略
_CONTEXT_POLICIES: Dict[str, Dict[str, Any]] = {
    "scan_result": {
        "trust_level": TrustLevel.HIGH,
        "max_length": 5000,
        "boundary_tag": "SCAN_DATA",
        "strip_patterns": [],
    },
    "threat_event": {
        "trust_level": TrustLevel.MEDIUM,
        "max_length": 3000,
        "boundary_tag": "EVENT_DATA",
        "strip_patterns": [
            re.compile(r"<\s*/?\s*(system|instruction|prompt)\s*>", re.IGNORECASE),
        ],
    },
    "alert_payload": {
        "trust_level": TrustLevel.LOW,
        "max_length": 2000,
        "boundary_tag": "ALERT_PAYLOAD",
        "strip_patterns": [
            re.compile(r"<\s*/?\s*(system|instruction|prompt)\s*>", re.IGNORECASE),
            re.compile(r'"\s*system\s*"\s*:\s*"[^"]*"', re.IGNORECASE),
            re.compile(r"ignore\s+(all\s+)?previous\s+instructions", re.IGNORECASE),
            re.compile(r"you\s+are\s+now\s+(a|an|the)\s+", re.IGNORECASE),
        ],
    },
    "user_description": {
        "trust_level": TrustLevel.LOW,
        "max_length": 1000,
        "boundary_tag": "USER_INPUT",
        "strip_patterns": [
            re.compile(r"<\s*/?\s*(system|instruction|prompt)\s*>", re.IGNORECASE),
            re.compile(r'"\s*system\s*"\s*:\s*"[^"]*"', re.IGNORECASE),
            re.compile(r"ignore\s+(all\s+)?previous\s+instructions", re.IGNORECASE),
            re.compile(r"you\s+are\s+now\s+(a|an|the)\s+", re.IGNORECASE),
            re.compile(r"pretend\s+(you\s+are|to\s+be)\s+", re.IGNORECASE),
            re.compile(r"act\s+as\s+(a|an|if)\s+", re.IGNORECASE),
        ],
    },
    "nmap_xml": {
        "trust_level": TrustLevel.HIGH,
        "max_length": 10000,
        "boundary_tag": "NMAP_XML",
        "strip_patterns": [],
    },
}


def sanitize_context(
    data: str,
    context_type: str,
    wrap_boundary: bool = True,
) -> Tuple[str, TrustLevel]:
    """
    净化上下文数据并标记可信度。

    Args:
        data: 原始上下文数据
        context_type: 数据类型 (scan_result/threat_event/alert_payload/user_description/nmap_xml)
        wrap_boundary: 是否用边界标签包裹

    Returns:
        (sanitized_text, trust_level)
    """
    policy = _CONTEXT_POLICIES.get(context_type, _CONTEXT_POLICIES["user_description"])
    trust_level = policy["trust_level"]

    if not data:
        return "", trust_level

    # 1. 截断
    cleaned = data[:policy["max_length"]]

    # 2. 应用过滤模式
    for pattern in policy["strip_patterns"]:
        cleaned = pattern.sub("[FILTERED]", cleaned)

    # 3. 移除 null 字节和控制字符（保留换行和制表符）
    cleaned = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", cleaned)

    # 4. 添加边界标签
    if wrap_boundary:
        tag = policy["boundary_tag"]
        cleaned = f"<{tag} trust=\"{trust_level.value}\">\n{cleaned}\n</{tag}>"

    return cleaned, trust_level


def build_safe_prompt_context(
    context_parts: Dict[str, Tuple[str, str]],
) -> str:
    """
    构建安全的 Prompt 上下文。

    Args:
        context_parts: {label: (data, context_type)} 字典

    Returns:
        带边界标签的完整上下文字符串
    """
    sections = []
    for label, (data, ctx_type) in context_parts.items():
        sanitized, trust = sanitize_context(data, ctx_type)
        if sanitized:
            sections.append(f"--- {label} (trust:{trust.value}) ---\n{sanitized}")

    return "\n\n".join(sections)


def get_context_policy(context_type: str) -> Dict[str, Any]:
    """获取指定类型的上下文安全策略"""
    policy = _CONTEXT_POLICIES.get(context_type)
    if not policy:
        return {"error": f"unknown context type: {context_type}"}
    return {
        "context_type": context_type,
        "trust_level": policy["trust_level"].value,
        "max_length": policy["max_length"],
        "boundary_tag": policy["boundary_tag"],
        "filter_count": len(policy["strip_patterns"]),
    }


def list_context_policies() -> list:
    """列出所有上下文安全策略"""
    return [get_context_policy(ct) for ct in _CONTEXT_POLICIES]
