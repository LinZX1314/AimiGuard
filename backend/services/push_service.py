"""Push delivery service for webhook/wecom/dingtalk/email channels."""

from __future__ import annotations

import asyncio
import json
import os
import smtplib
from email.message import EmailMessage
from typing import Any, Dict

import httpx

from core.database import PushChannel


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
    async def _send_dingtalk(channel: PushChannel, message: str) -> Dict[str, Any]:
        payload = {
            "msgtype": "text",
            "text": {"content": message},
        }
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(channel.target, json=payload)
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
    def _send_email_sync(channel: PushChannel, message: str, trace_id: str) -> Dict[str, Any]:
        recipient = channel.target.replace("mailto:", "").strip()
        if not recipient:
            return {
                "success": False,
                "status": "failed",
                "detail": "email_target_empty",
                "response_status": None,
                "simulated": False,
            }

        host = os.getenv("PUSH_SMTP_HOST", "").strip()
        if not host:
            return {
                "success": False,
                "status": "failed",
                "detail": "smtp_not_configured",
                "response_status": None,
                "simulated": False,
            }

        port = int(os.getenv("PUSH_SMTP_PORT", "587"))
        user = os.getenv("PUSH_SMTP_USER", "").strip()
        password = os.getenv("PUSH_SMTP_PASSWORD", "").strip()
        use_tls = _bool_env("PUSH_SMTP_TLS", True)
        sender = os.getenv("PUSH_SMTP_FROM", user or "aimiguan@localhost")

        config = PushService._parse_config(channel)
        subject = str(config.get("subject") or f"[Aimiguan] Push test ({trace_id})")

        mail = EmailMessage()
        mail["From"] = sender
        mail["To"] = recipient
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
                "detail": "smtp_sent",
                "response_status": 250,
                "simulated": False,
            }
        except Exception as exc:
            return {
                "success": False,
                "status": "failed",
                "detail": f"smtp_error:{exc.__class__.__name__}",
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

