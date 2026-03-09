"""Push delivery service for webhook/wecom/dingtalk/feishu/email channels."""

from __future__ import annotations

import asyncio
import base64
import hashlib
import hmac
import json
import logging
import os
import smtplib
import time
from email.message import EmailMessage
from typing import Any, Dict, List, Optional

import httpx

from core.database import PushChannel

logger = logging.getLogger(__name__)


def _bool_env(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


class PushService:
    @staticmethod
    def sandbox_mode() -> bool:
        return _bool_env("PUSH_SANDBOX_MODE", True)

    @staticmethod
    def _parse_config(channel: PushChannel) -> Dict[str, Any]:
        if not channel.config_json:
            return {}
        try:
            data = json.loads(channel.config_json)
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}

    @staticmethod
    async def _send_webhook(channel: PushChannel, message: str, trace_id: str) -> Dict[str, Any]:
        config = PushService._parse_config(channel)
        method = str(config.get("method") or "POST").upper()
        timeout_seconds = float(config.get("timeout_seconds") or os.getenv("PUSH_TIMEOUT_SECONDS", "10"))
        headers = config.get("headers")
        if not isinstance(headers, dict):
            headers = {"Content-Type": "application/json"}

        payload = {
            "message": message,
            "channel_name": channel.channel_name,
            "channel_type": channel.channel_type,
            "trace_id": trace_id,
        }

        async with httpx.AsyncClient(timeout=timeout_seconds) as client:
            if method == "GET":
                response = await client.get(channel.target, params=payload, headers=headers)
            else:
                response = await client.post(channel.target, json=payload, headers=headers)

        ok = response.status_code < 400
        return {
            "success": ok,
            "status": "success" if ok else "failed",
            "detail": f"webhook_status={response.status_code}",
            "response_status": response.status_code,
            "simulated": False,
        }

    @staticmethod
    async def _send_wecom(channel: PushChannel, message: str) -> Dict[str, Any]:
        config = PushService._parse_config(channel)
        use_markdown = config.get("markdown", True)
        if use_markdown:
            payload = {
                "msgtype": "markdown",
                "markdown": {"content": message},
            }
        else:
            payload = {
                "msgtype": "text",
                "text": {"content": message},
            }
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(channel.target, json=payload)
        success = response.status_code < 400
        detail = f"wecom_status={response.status_code}"
        if success:
            try:
                body = response.json()
                if isinstance(body, dict):
                    errcode = int(body.get("errcode", 0))
                    success = errcode == 0
                    detail = f"wecom_errcode={errcode}"
            except Exception:
                pass
        return {
            "success": success,
            "status": "success" if success else "failed",
            "detail": detail,
            "response_status": response.status_code,
            "simulated": False,
        }

    @staticmethod
    def _dingtalk_sign(secret: str) -> tuple:
        """Generate DingTalk HMAC-SHA256 signature. Returns (timestamp, sign)."""
        timestamp = str(int(time.time() * 1000))
        string_to_sign = f"{timestamp}\n{secret}"
        hmac_code = hmac.new(
            secret.encode("utf-8"),
            string_to_sign.encode("utf-8"),
            digestmod=hashlib.sha256,
        ).digest()
        sign = base64.b64encode(hmac_code).decode("utf-8")
        return timestamp, sign

    @staticmethod
    async def _send_dingtalk(channel: PushChannel, message: str) -> Dict[str, Any]:
        config = PushService._parse_config(channel)
        use_markdown = config.get("markdown", True)
        if use_markdown:
            payload = {
                "msgtype": "markdown",
                "markdown": {
                    "title": "Aimiguan 安全通知",
                    "text": message,
                },
            }
        else:
            payload = {
                "msgtype": "text",
                "text": {"content": message},
            }
        url = channel.target
        secret = config.get("secret", "").strip()
        if secret:
            ts, sign = PushService._dingtalk_sign(secret)
            sep = "&" if "?" in url else "?"
            url = f"{url}{sep}timestamp={ts}&sign={sign}"
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(url, json=payload)
        success = response.status_code < 400
        detail = f"dingtalk_status={response.status_code}"
        if success:
            try:
                body = response.json()
                if isinstance(body, dict):
                    errcode = body.get("errcode")
                    if errcode is not None:
                        success = str(errcode) in {"0", "ok"}
                        detail = f"dingtalk_errcode={errcode}"
            except Exception:
                pass
        return {
            "success": success,
            "status": "success" if success else "failed",
            "detail": detail,
            "response_status": response.status_code,
            "simulated": False,
        }

    @staticmethod
    def _feishu_sign(secret: str) -> tuple:
        """Generate Feishu HMAC-SHA256 signature. Returns (timestamp, sign)."""
        timestamp = str(int(time.time()))
        string_to_sign = f"{timestamp}\n{secret}"
        hmac_code = hmac.new(
            string_to_sign.encode("utf-8"),
            b"",
            digestmod=hashlib.sha256,
        ).digest()
        sign = base64.b64encode(hmac_code).decode("utf-8")
        return timestamp, sign

    @staticmethod
    async def _send_feishu(channel: PushChannel, message: str) -> Dict[str, Any]:
        config = PushService._parse_config(channel)
        use_rich = config.get("rich", True)
        if use_rich:
            payload: Dict[str, Any] = {
                "msg_type": "interactive",
                "card": {
                    "header": {
                        "title": {"tag": "plain_text", "content": "Aimiguan 安全通知"},
                        "template": "red",
                    },
                    "elements": [
                        {"tag": "markdown", "content": message},
                    ],
                },
            }
        else:
            payload = {
                "msg_type": "text",
                "content": {"text": message},
            }
        secret = config.get("secret", "").strip()
        if secret:
            ts, sign = PushService._feishu_sign(secret)
            payload["timestamp"] = ts
            payload["sign"] = sign
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(channel.target, json=payload)
        success = response.status_code < 400
        detail = f"feishu_status={response.status_code}"
        if success:
            try:
                body = response.json()
                if isinstance(body, dict):
                    code = body.get("code") or body.get("StatusCode")
                    if code is not None:
                        success = int(code) == 0
                        detail = f"feishu_code={code}"
            except Exception:
                pass
        return {
            "success": success,
            "status": "success" if success else "failed",
            "detail": detail,
            "response_status": response.status_code,
            "simulated": False,
        }

    @staticmethod
    def _send_email_sync(channel: PushChannel, message: str, trace_id: str) -> Dict[str, Any]:
        raw_target = channel.target.replace("mailto:", "").strip()
        if not raw_target:
            return {
                "success": False,
                "status": "failed",
                "detail": "email_target_empty",
                "response_status": None,
                "simulated": False,
            }

        recipients = [r.strip() for r in raw_target.replace("；", ";").replace(";", ",").split(",") if r.strip()]
        if not recipients:
            return {
                "success": False,
                "status": "failed",
                "detail": "email_target_empty",
                "response_status": None,
                "simulated": False,
            }

        config = PushService._parse_config(channel)

        host = str(config.get("smtp_host") or os.getenv("PUSH_SMTP_HOST", "")).strip()
        if not host:
            return {
                "success": False,
                "status": "failed",
                "detail": "smtp_not_configured：请在通道配置中填写 SMTP 服务器地址",
                "response_status": None,
                "simulated": False,
            }

        port = int(config.get("smtp_port") or os.getenv("PUSH_SMTP_PORT", "587"))
        user = str(config.get("smtp_user") or os.getenv("PUSH_SMTP_USER", "")).strip()
        password = str(config.get("smtp_password") or os.getenv("PUSH_SMTP_PASSWORD", "")).strip()
        use_tls = config.get("smtp_tls", True) if "smtp_tls" in config else _bool_env("PUSH_SMTP_TLS", True)
        sender = str(config.get("smtp_from") or os.getenv("PUSH_SMTP_FROM", "") or user or "aimiguan@localhost").strip()

        subject = str(config.get("subject") or f"[Aimiguan] 安全告警通知 ({trace_id})")

        mail = EmailMessage()
        mail["From"] = sender
        mail["To"] = ", ".join(recipients)
        mail["Subject"] = subject
        mail.set_content(message)

        try:
            with smtplib.SMTP(host=host, port=port, timeout=10) as smtp:
                if use_tls:
                    smtp.starttls()
                if user and password:
                    smtp.login(user, password)
                smtp.send_message(mail)
            return {
                "success": True,
                "status": "success",
                "detail": f"smtp_sent_to_{len(recipients)}_recipients",
                "response_status": 250,
                "simulated": False,
            }
        except Exception as exc:
            return {
                "success": False,
                "status": "failed",
                "detail": f"smtp_error:{exc.__class__.__name__}:{exc}",
                "response_status": None,
                "simulated": False,
            }

    @staticmethod
    async def _send_email(channel: PushChannel, message: str, trace_id: str) -> Dict[str, Any]:
        return await asyncio.to_thread(PushService._send_email_sync, channel, message, trace_id)

    @staticmethod
    async def send_test(channel: PushChannel, message: str, trace_id: str) -> Dict[str, Any]:
        if not channel.enabled:
            return {
                "success": False,
                "status": "failed",
                "detail": "channel_disabled",
                "response_status": None,
                "simulated": False,
                "channel_id": channel.id,
                "channel_type": channel.channel_type,
                "channel_name": channel.channel_name,
                "trace_id": trace_id,
            }

        if PushService.sandbox_mode():
            return {
                "success": True,
                "status": "simulated_success",
                "detail": "sandbox_mode",
                "response_status": 200,
                "simulated": True,
                "channel_id": channel.id,
                "channel_type": channel.channel_type,
                "channel_name": channel.channel_name,
                "target": channel.target,
                "trace_id": trace_id,
            }

        channel_type = str(channel.channel_type or "").lower()
        try:
            if channel_type == "webhook":
                result = await PushService._send_webhook(channel, message, trace_id)
            elif channel_type == "wecom":
                result = await PushService._send_wecom(channel, message)
            elif channel_type == "dingtalk":
                result = await PushService._send_dingtalk(channel, message)
            elif channel_type == "feishu":
                result = await PushService._send_feishu(channel, message)
            elif channel_type == "email":
                result = await PushService._send_email(channel, message, trace_id)
            else:
                result = {
                    "success": False,
                    "status": "failed",
                    "detail": f"unsupported_channel_type:{channel.channel_type}",
                    "response_status": None,
                    "simulated": False,
                }
        except Exception as exc:
            result = {
                "success": False,
                "status": "failed",
                "detail": f"push_send_error:{exc.__class__.__name__}",
                "response_status": None,
                "simulated": False,
            }

        return {
            **result,
            "channel_id": channel.id,
            "channel_type": channel.channel_type,
            "channel_name": channel.channel_name,
            "target": channel.target,
            "trace_id": trace_id,
        }

    # ── event-driven alert push ──

    @staticmethod
    def format_alert_message(
        *,
        title: str = "安全告警",
        severity: str = "HIGH",
        ip: str = "",
        source: str = "",
        summary: str = "",
        event_id: Optional[int] = None,
        extra: Optional[Dict[str, Any]] = None,
    ) -> str:
        severity_emoji = {
            "CRITICAL": "🔴",
            "HIGH": "🟠",
            "MEDIUM": "🟡",
            "LOW": "🟢",
        }.get(severity.upper(), "⚪")
        lines = [
            f"### {severity_emoji} {title}",
            "",
            f"**严重等级**: {severity}",
        ]
        if ip:
            lines.append(f"**攻击 IP**: `{ip}`")
        if source:
            lines.append(f"**数据来源**: {source}")
        if summary:
            lines.append(f"**摘要**: {summary}")
        if event_id:
            lines.append(f"**事件 ID**: {event_id}")
        if extra:
            for k, v in extra.items():
                lines.append(f"**{k}**: {v}")
        lines.append("")
        lines.append(f"---")
        lines.append(f"*Aimiguan 安全运营平台*")
        return "\n".join(lines)

    @staticmethod
    async def send_alert(
        db_session_factory: Any,
        *,
        title: str = "安全告警",
        severity: str = "HIGH",
        ip: str = "",
        source: str = "",
        summary: str = "",
        event_id: Optional[int] = None,
        trace_id: str = "",
        extra: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """Send alert to ALL enabled push channels. Runs in background."""
        message = PushService.format_alert_message(
            title=title,
            severity=severity,
            ip=ip,
            source=source,
            summary=summary,
            event_id=event_id,
            extra=extra,
        )

        db = db_session_factory()
        results: List[Dict[str, Any]] = []
        try:
            channels: List[PushChannel] = (
                db.query(PushChannel)
                .filter(PushChannel.enabled == 1)
                .all()
            )
            if not channels:
                return results

            for channel in channels:
                try:
                    result = await PushService.send_test(channel, message, trace_id)
                    results.append(result)
                    if not result.get("success"):
                        logger.warning(
                            "push_alert_failed channel=%s detail=%s",
                            channel.channel_name,
                            result.get("detail"),
                        )
                except Exception as exc:
                    logger.error(
                        "push_alert_exception channel=%s error=%s",
                        channel.channel_name,
                        str(exc),
                    )
                    results.append({
                        "success": False,
                        "channel_name": channel.channel_name,
                        "detail": str(exc),
                    })
        finally:
            db.close()

        return results

