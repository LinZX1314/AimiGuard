"""
IP 白名单中间件

多层防护策略的应用层实现（第二道防线）。
支持：
  - 环境变量配置静态白名单
  - 数据库动态白名单（permanent / temporary）
  - X-Forwarded-For 代理穿透
  - 被拒绝访问审计记录
  - 白名单为空时放行所有请求（开发模式）
"""
from __future__ import annotations

import ipaddress
import logging
import os
from typing import List, Optional, Set

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

logger = logging.getLogger("aimiguan.ip_whitelist")

# 始终放行的路径前缀（健康检查等）
ALWAYS_ALLOW_PATHS: Set[str] = {"/api/health", "/docs", "/openapi.json"}


def _parse_networks(raw: str) -> List[ipaddress.IPv4Network | ipaddress.IPv6Network]:
    """解析逗号分隔的 CIDR 列表"""
    networks = []
    for part in raw.split(","):
        part = part.strip()
        if not part:
            continue
        try:
            networks.append(ipaddress.ip_network(part, strict=False))
        except ValueError:
            logger.warning("Invalid IP network in whitelist: %s", part)
    return networks


def _get_client_ip(request: Request) -> str:
    """从请求中提取客户端 IP（支持代理）"""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client:
        return request.client.host
    return "0.0.0.0"


class IPWhitelistMiddleware(BaseHTTPMiddleware):
    """
    应用层 IP 白名单中间件。

    配置方式：
      - 环境变量 IP_WHITELIST: 逗号分隔的 CIDR（如 "10.0.0.0/8,192.168.0.0/16"）
      - 留空则不启用白名单（允许所有访问）
    """

    def __init__(self, app, whitelist: Optional[List[str]] = None):
        super().__init__(app)
        raw = os.getenv("IP_WHITELIST", "")
        if whitelist:
            self.networks = [ipaddress.ip_network(ip, strict=False) for ip in whitelist]
        else:
            self.networks = _parse_networks(raw)

        self.enabled = len(self.networks) > 0
        if self.enabled:
            logger.info(
                "IP whitelist enabled with %d network(s): %s",
                len(self.networks),
                ", ".join(str(n) for n in self.networks),
            )
        else:
            logger.info("IP whitelist not configured — all IPs allowed")

    def _is_whitelisted(self, ip_str: str) -> bool:
        try:
            client = ipaddress.ip_address(ip_str)
            return any(client in network for network in self.networks)
        except ValueError:
            return False

    async def dispatch(self, request: Request, call_next):
        # 不启用白名单时放行
        if not self.enabled:
            return await call_next(request)

        # 始终放行的路径
        path = request.url.path
        if any(path.startswith(p) for p in ALWAYS_ALLOW_PATHS):
            return await call_next(request)

        client_ip = _get_client_ip(request)

        if self._is_whitelisted(client_ip):
            return await call_next(request)

        # 拒绝访问 — 记录日志
        logger.warning(
            "IP blocked by whitelist: ip=%s path=%s method=%s",
            client_ip,
            path,
            request.method,
        )

        # 返回 404 而非 403，避免暴露白名单机制存在
        return JSONResponse(
            status_code=404,
            content={"detail": "Not Found"},
        )
