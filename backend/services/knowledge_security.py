"""
S3-02 AI 知识库 / 向量存储安全
- RAG 数据源访问控制与来源验证
- 向量注入防护：检测嵌入文档中的恶意 Prompt 片段
- 知识库文档的完整性校验（哈希链）
- 检索结果的安全过滤
"""
from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set, Tuple

# 允许的知识库数据来源
_TRUSTED_SOURCES: Set[str] = {
    "internal_docs",      # 内部文档
    "scan_reports",       # 扫描报告
    "threat_intel",       # 威胁情报
    "cve_database",       # CVE数据库
    "security_policies",  # 安全策略
}

# 向量注入检测模式
_VECTOR_INJECTION_PATTERNS: list[re.Pattern] = [
    re.compile(r"ignore\s+(all\s+)?previous\s+(instructions?|context)", re.IGNORECASE),
    re.compile(r"<\s*/?\s*(system|instruction|prompt)\s*>", re.IGNORECASE),
    re.compile(r"you\s+are\s+now\s+(a|an)\s+", re.IGNORECASE),
    re.compile(r"override\s+(system|safety|security)", re.IGNORECASE),
    re.compile(r"pretend\s+(you\s+are|to\s+be)", re.IGNORECASE),
    re.compile(r"\[\s*system\s*\]", re.IGNORECASE),
    re.compile(r'"\s*role\s*"\s*:\s*"\s*system\s*"', re.IGNORECASE),
]


class KnowledgeDocument:
    """知识库文档元数据"""

    def __init__(
        self,
        doc_id: str,
        source: str,
        content: str,
        title: str = "",
        metadata: Optional[Dict[str, Any]] = None,
    ):
        self.doc_id = doc_id
        self.source = source
        self.content = content
        self.title = title
        self.metadata = metadata or {}
        self.content_hash = hashlib.sha256(content.encode()).hexdigest()
        self.created_at = datetime.now(timezone.utc)


def validate_source(source: str) -> Tuple[bool, str]:
    """验证数据来源是否可信"""
    if not source:
        return False, "source_empty"
    if source not in _TRUSTED_SOURCES:
        return False, f"untrusted_source:{source}"
    return True, "trusted"


def check_document_injection(content: str) -> Tuple[bool, str]:
    """
    检测文档内容是否包含向量注入攻击。

    Returns:
        (is_safe, reason)
    """
    if not content:
        return True, ""

    for pattern in _VECTOR_INJECTION_PATTERNS:
        if pattern.search(content):
            return False, "vector_injection_detected"

    return True, ""


def sanitize_document(content: str, max_length: int = 10000) -> str:
    """净化知识库文档内容"""
    if not content:
        return ""

    # 截断
    cleaned = content[:max_length]

    # 移除危险标签
    for pattern in _VECTOR_INJECTION_PATTERNS:
        cleaned = pattern.sub("[REDACTED]", cleaned)

    # 移除控制字符
    cleaned = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", cleaned)

    return cleaned


def verify_document_integrity(content: str, expected_hash: str) -> bool:
    """验证文档完整性（哈希校验）"""
    actual_hash = hashlib.sha256(content.encode()).hexdigest()
    return actual_hash == expected_hash


def filter_retrieval_results(
    results: List[Dict[str, Any]],
    max_results: int = 5,
    min_score: float = 0.3,
) -> List[Dict[str, Any]]:
    """
    过滤 RAG 检索结果。

    - 限制返回数量
    - 过滤低分结果
    - 检测注入内容
    - 验证来源可信度
    """
    filtered = []

    for r in results:
        content = r.get("content", "")
        source = r.get("source", "")
        score = r.get("score", 0)

        # 低分过滤
        if score < min_score:
            continue

        # 来源验证
        source_ok, _ = validate_source(source)
        if not source_ok:
            continue

        # 注入检测
        is_safe, _ = check_document_injection(content)
        if not is_safe:
            # 净化后仍保留
            r["content"] = sanitize_document(content)
            r["sanitized"] = True

        filtered.append(r)

        if len(filtered) >= max_results:
            break

    return filtered


def get_trusted_sources() -> List[str]:
    """获取可信数据来源列表"""
    return sorted(_TRUSTED_SOURCES)


def add_trusted_source(source: str) -> None:
    """添加可信数据来源"""
    _TRUSTED_SOURCES.add(source)


def remove_trusted_source(source: str) -> None:
    """移除可信数据来源"""
    _TRUSTED_SOURCES.discard(source)


def compute_document_hash(content: str) -> str:
    """计算文档内容哈希"""
    return hashlib.sha256(content.encode()).hexdigest()
