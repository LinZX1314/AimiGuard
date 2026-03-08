"""
单包授权（SPA - Single Packet Authorization）服务

比端口敲门更安全的隐蔽访问方案：
  - 客户端生成带时间戳和 HMAC 签名的授权令牌
  - 服务端验证后临时放行该 IP
  - 令牌 5 分钟内有效，防重放

用法：
  客户端请求时携带 X-SPA-Token 头：
    curl -H "X-SPA-Token: <token>" https://aimiguard.example.com/api/health

  生成令牌：
    python -c "from services.spa_service import generate_spa_token; print(generate_spa_token('10.0.0.1', 'my-secret'))"
"""
from __future__ import annotations

import hashlib
import hmac
import logging
import os
import time

logger = logging.getLogger("aimiguan.spa")

SPA_SECRET = os.getenv("SPA_SECRET", "")
SPA_TOKEN_TTL = int(os.getenv("SPA_TOKEN_TTL", "300"))  # 默认 5 分钟


def generate_spa_token(client_ip: str, secret: str | None = None) -> str:
    """
    生成 SPA 授权令牌。

    格式: {ip}:{timestamp}:{hmac_sha256}
    """
    secret = secret or SPA_SECRET
    if not secret:
        raise ValueError("SPA_SECRET not configured")

    timestamp = int(time.time())
    message = f"{client_ip}:{timestamp}"
    signature = hmac.new(
        secret.encode(),
        message.encode(),
        hashlib.sha256,
    ).hexdigest()
    return f"{message}:{signature}"


def verify_spa_token(
    token: str,
    client_ip: str,
    secret: str | None = None,
    ttl: int | None = None,
) -> tuple[bool, str]:
    """
    验证 SPA 令牌。

    Returns:
        (is_valid, reason)
    """
    secret = secret or SPA_SECRET
    ttl = ttl if ttl is not None else SPA_TOKEN_TTL

    if not secret:
        return False, "spa_secret_not_configured"

    if not token:
        return False, "empty_token"

    try:
        parts = token.rsplit(":", 1)
        if len(parts) != 2:
            return False, "invalid_format"

        message, signature = parts
        msg_parts = message.split(":")
        if len(msg_parts) != 2:
            return False, "invalid_message_format"

        ip, ts_str = msg_parts

        # 验证 IP
        if ip != client_ip:
            logger.warning("SPA token IP mismatch: token=%s, client=%s", ip, client_ip)
            return False, "ip_mismatch"

        # 验证时效
        timestamp = int(ts_str)
        elapsed = time.time() - timestamp
        if elapsed > ttl:
            return False, "token_expired"
        if elapsed < -60:  # 允许 1 分钟时钟偏差
            return False, "token_future"

        # 验证签名
        expected = hmac.new(
            secret.encode(),
            message.encode(),
            hashlib.sha256,
        ).hexdigest()

        if not hmac.compare_digest(signature, expected):
            logger.warning("SPA token signature mismatch for ip=%s", client_ip)
            return False, "signature_mismatch"

        return True, "ok"

    except (ValueError, IndexError) as exc:
        return False, f"parse_error:{exc.__class__.__name__}"
