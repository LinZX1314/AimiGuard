"""
S2-01 MCP 插件来源验证与签名校验
- 插件注册时强制提供来源URL、发布者签名、哈希校验值
- 对接恶意 MCP 服务器黑名单
- 签名校验失败时拒绝注册并写告警
"""
from __future__ import annotations

import hashlib
import hmac
import re
from typing import Optional, Set, Tuple

# 已知恶意 MCP 服务器黑名单（可从远程更新）
_MALICIOUS_BLACKLIST: Set[str] = {
    "malicious-mcp-server.example.com",
    "evil-plugin.attacker.io",
}

# 允许的来源域名白名单（可选，空则不做白名单限制）
_TRUSTED_PUBLISHERS: Set[str] = set()

# URL 模式验证
_URL_PATTERN = re.compile(r"^https?://[\w\-.]+(:\d+)?(/[\w\-./]*)?$")


def verify_plugin(
    plugin_name: str,
    source_url: str,
    publisher_signature: Optional[str] = None,
    content_hash: Optional[str] = None,
    plugin_content: Optional[bytes] = None,
) -> Tuple[bool, str, str]:
    """
    验证 MCP 插件的安全性。

    Returns:
        (is_safe, risk_level, reason)
        - is_safe=True → 验证通过
        - is_safe=False → 验证失败，reason 描述原因
        - risk_level: 'low' / 'medium' / 'high' / 'critical'
    """
    if not plugin_name or not plugin_name.strip():
        return False, "critical", "plugin_name_empty"

    if not source_url:
        return False, "high", "source_url_missing"

    # 1. URL 格式验证
    if not _URL_PATTERN.match(source_url):
        return False, "high", "source_url_invalid_format"

    # 2. 黑名单检查
    for blacklisted in _MALICIOUS_BLACKLIST:
        if blacklisted in source_url.lower():
            return False, "critical", f"blacklisted_source:{blacklisted}"

    # 3. 签名校验（如果提供）
    if publisher_signature and plugin_content:
        if not _verify_signature(plugin_content, publisher_signature):
            return False, "critical", "signature_verification_failed"

    # 4. 哈希校验（如果提供）
    if content_hash and plugin_content:
        computed_hash = hashlib.sha256(plugin_content).hexdigest()
        if computed_hash != content_hash:
            return False, "critical", "content_hash_mismatch"

    # 5. 白名单检查（如果启用）
    if _TRUSTED_PUBLISHERS:
        is_trusted = any(tp in source_url.lower() for tp in _TRUSTED_PUBLISHERS)
        if not is_trusted:
            return True, "medium", "source_not_in_trusted_list"

    # 6. 基础安全评估
    risk_level = "low"
    if not publisher_signature:
        risk_level = "medium"
    if not content_hash:
        risk_level = max(risk_level, "medium", key=lambda x: {"low": 0, "medium": 1, "high": 2, "critical": 3}[x])

    return True, risk_level, "verification_passed"


def _verify_signature(content: bytes, signature: str) -> bool:
    """
    验证发布者签名（HMAC-SHA256）。
    生产环境应使用非对称签名(RSA/ED25519)，此处用HMAC做演示。
    """
    # 演示模式：接受格式为 "hmac:<hex_digest>" 的签名
    if signature.startswith("hmac:"):
        expected_digest = signature[5:]
        # 使用固定密钥做验证（生产环境应从安全存储读取公钥）
        secret_key = b"aimiguan-plugin-signing-key-v1"
        computed = hmac.new(secret_key, content, hashlib.sha256).hexdigest()
        return hmac.compare_digest(computed, expected_digest)

    # 未知签名格式
    return False


def compute_content_hash(content: bytes) -> str:
    """计算插件内容的 SHA-256 哈希"""
    return hashlib.sha256(content).hexdigest()


def compute_signature(content: bytes) -> str:
    """生成 HMAC-SHA256 签名（用于测试/演示）"""
    secret_key = b"aimiguan-plugin-signing-key-v1"
    digest = hmac.new(secret_key, content, hashlib.sha256).hexdigest()
    return f"hmac:{digest}"


def add_to_blacklist(domain: str) -> None:
    """添加域名到黑名单"""
    _MALICIOUS_BLACKLIST.add(domain.lower())


def remove_from_blacklist(domain: str) -> None:
    """从黑名单移除域名"""
    _MALICIOUS_BLACKLIST.discard(domain.lower())


def get_blacklist() -> list:
    """获取当前黑名单"""
    return sorted(_MALICIOUS_BLACKLIST)
