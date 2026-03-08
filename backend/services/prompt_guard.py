"""
S1-01 Prompt 注入防护
检测并拦截常见 Prompt Injection 攻击模式：
- 角色扮演指令
- ignore previous instructions
- Base64 / Unicode 混淆
- XML/JSON/INI 伪装格式 (Policy Puppetry)
- 系统指令覆写尝试
"""
from __future__ import annotations

import base64
import re
import unicodedata
from typing import Tuple

# ── 危险模式正则 ──

_INJECTION_PATTERNS: list[re.Pattern] = [
    # 角色扮演 / 指令覆写
    re.compile(r"ignore\s+(all\s+)?previous\s+instructions", re.IGNORECASE),
    re.compile(r"ignore\s+(all\s+)?above\s+instructions", re.IGNORECASE),
    re.compile(r"disregard\s+(all\s+)?(previous|prior|above)", re.IGNORECASE),
    re.compile(r"forget\s+(all\s+)?(previous|prior|above)", re.IGNORECASE),
    re.compile(r"you\s+are\s+now\s+(a|an|the)\s+", re.IGNORECASE),
    re.compile(r"pretend\s+(you\s+are|to\s+be)\s+", re.IGNORECASE),
    re.compile(r"act\s+as\s+(a|an|if)\s+", re.IGNORECASE),
    re.compile(r"roleplay\s+as\s+", re.IGNORECASE),
    re.compile(r"from\s+now\s+on\s+you\s+(are|will)", re.IGNORECASE),
    re.compile(r"new\s+instructions?\s*:", re.IGNORECASE),
    re.compile(r"override\s+(system|safety|security)(\s+\w+)*\s+(prompt|instructions?|rules?)", re.IGNORECASE),
    re.compile(r"system\s*:\s*you\s+are", re.IGNORECASE),

    # DAN / 越狱
    re.compile(r"\bDAN\b.*\bmode\b", re.IGNORECASE),
    re.compile(r"jailbreak", re.IGNORECASE),
    re.compile(r"developer\s+mode\s+(enabled|on|activated)", re.IGNORECASE),

    # Policy Puppetry — XML/JSON/INI 伪装
    re.compile(r"<\s*system\s*>", re.IGNORECASE),
    re.compile(r"<\s*/?\s*instructions?\s*>", re.IGNORECASE),
    re.compile(r'"\s*system\s*"\s*:\s*"', re.IGNORECASE),
    re.compile(r"\[\s*system\s*\]", re.IGNORECASE),

    # 提示泄露
    re.compile(r"(reveal|show|print|output|repeat)\s+(\w+\s+)*(your|the|system)\s+(prompt|instructions?)", re.IGNORECASE),
    re.compile(r"what\s+(is|are)\s+your\s+(system\s+)?(prompt|instructions?)", re.IGNORECASE),
]

# Base64 特征：连续 40+ 字符的 Base64 编码块
_BASE64_PATTERN = re.compile(r"[A-Za-z0-9+/]{40,}={0,2}")

# Unicode 混淆检测阈值：非 ASCII 字符占比
_UNICODE_OBFUSCATION_THRESHOLD = 0.3


def sanitize_input(text: str) -> Tuple[bool, str]:
    """
    检查输入文本是否包含 Prompt 注入。

    Returns:
        (is_safe, reason)
        - is_safe=True  → 安全，reason 为空
        - is_safe=False → 检测到注入，reason 描述检测类型（不暴露给用户）
    """
    if not text or not text.strip():
        return True, ""

    # 1. 规范化 Unicode（NFD → NFC）防止视觉欺骗
    normalized = unicodedata.normalize("NFC", text)

    # 2. 检查危险模式
    for pattern in _INJECTION_PATTERNS:
        if pattern.search(normalized):
            return False, f"injection_pattern_detected:{pattern.pattern[:50]}"

    # 3. 检查 Base64 编码块（可能隐藏恶意指令）
    b64_matches = _BASE64_PATTERN.findall(normalized)
    for match in b64_matches:
        try:
            decoded = base64.b64decode(match).decode("utf-8", errors="ignore").lower()
            # 检查解码后内容是否包含危险关键词
            danger_keywords = [
                "ignore", "instructions", "system", "override",
                "jailbreak", "pretend", "roleplay",
            ]
            for kw in danger_keywords:
                if kw in decoded:
                    return False, "base64_encoded_injection"
        except Exception:
            pass

    # 4. Unicode 混淆检测
    if len(normalized) > 20:
        non_ascii = sum(1 for c in normalized if ord(c) > 127)
        ratio = non_ascii / len(normalized)
        # 只对高比例混淆且包含可疑结构的做拦截
        if ratio > _UNICODE_OBFUSCATION_THRESHOLD:
            # 检查是否为正常中文/日文（CJK 字符不算混淆）
            cjk_count = sum(1 for c in normalized if '\u4e00' <= c <= '\u9fff' or '\u3040' <= c <= '\u30ff')
            if cjk_count < non_ascii * 0.5:
                return False, "unicode_obfuscation_detected"

    # 5. 检查超长输入（可能是 Prompt 注入 payload）
    if len(normalized) > 10000:
        return False, "input_too_long"

    return True, ""


def sanitize_for_context(text: str, max_length: int = 2000) -> str:
    """
    S3-01: 净化用于 AI 上下文的外部数据。
    截断、移除危险标签、添加边界标记。
    """
    if not text:
        return ""

    # 截断
    cleaned = text[:max_length]

    # 移除可能的伪系统指令标签
    cleaned = re.sub(r"<\s*/?\s*(system|instruction|prompt)\s*>", "[FILTERED]", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r'"\s*system\s*"\s*:\s*"[^"]*"', "[FILTERED]", cleaned, flags=re.IGNORECASE)

    return cleaned
