"""AI engine service with real model invocation and explicit fallback metadata."""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from typing import Any, Dict, Optional

import httpx


def _bool_env(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _safe_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except Exception:
        return default


def _clamp_score(value: Any, default: int = 50) -> int:
    return max(0, min(100, _safe_int(value, default)))


def _normalize_action(value: Any, score: int) -> str:
    action = str(value or "").strip().upper()
    if action in {"BLOCK", "MONITOR"}:
        return action
    return "BLOCK" if score >= 80 else "MONITOR"


def _truncate(text: str, limit: int = 8000) -> str:
    content = str(text or "")
    return content if len(content) <= limit else content[:limit]


def _extract_json_text(text: str) -> str:
    raw = str(text or "").strip()
    if not raw:
        return "{}"

    fenced = re.search(r"```(?:json)?\s*(\{.*\})\s*```", raw, re.DOTALL | re.IGNORECASE)
    if fenced:
        return fenced.group(1)

    left = raw.find("{")
    right = raw.rfind("}")
    if left >= 0 and right > left:
        return raw[left : right + 1]
    return raw


def _default_scan_markdown(scan_data: Dict[str, Any], reason: str) -> str:
    findings = scan_data.get("findings") or []
    findings_count = _safe_int(scan_data.get("findings_count"), len(findings))
    target = str(scan_data.get("target") or "unknown")

    high_ports = sorted(
        {
            str(item.get("port"))
            for item in findings
            if isinstance(item, dict) and item.get("port") is not None
        }
    )[:10]
    port_info = ", ".join(high_ports) if high_ports else "无明显端口样本"

    return (
        "## 扫描结果分析（降级输出）\n\n"
        f"- 目标: `{target}`\n"
        f"- 样本发现数: `{findings_count}`\n"
        f"- 观察到端口: {port_info}\n"
        "- 建议:\n"
        "  1. 优先核查对外暴露服务的鉴权与访问控制。\n"
        "  2. 对高危端口执行最小暴露与白名单策略。\n"
        "  3. 对扫描发现建立复测任务，确认修复闭环。\n\n"
        f"> fallback_reason: {reason}\n"
    )


def _default_report_markdown(report_type: str, data: Dict[str, Any], reason: str) -> str:
    defense_summary = str(data.get("defense_summary") or "暂无防御摘要")
    scan_summary = str(data.get("scan_summary") or "暂无扫描摘要")
    scope = str(data.get("scope") or "global")
    return (
        f"# {report_type} 报告（降级输出）\n\n"
        f"- Scope: `{scope}`\n"
        f"- 防御摘要: {defense_summary}\n"
        f"- 探测摘要: {scan_summary}\n"
        "- 建议:\n"
        "  1. 对高风险事件设置明确 SLA。\n"
        "  2. 对高危发现建立责任人和复测计划。\n"
        "  3. 对失败链路补充告警和重试策略。\n\n"
        f"> fallback_reason: {reason}\n"
    )


def _default_chat_reply(message: str, context: Any, reason: str) -> str:
    context_text = str(context or "无上下文")
    msg = _truncate(message, 300)
    return (
        "当前 AI 模型不可用，已切换到规则化回复。\n"
        f"- 你的问题: {msg}\n"
        f"- 当前上下文: {_truncate(context_text, 500)}\n"
        "- 建议: 先处理高风险和人工介入积压，再复盘规则命中质量。\n"
        f"- fallback_reason: {reason}"
    )


@dataclass
class AIRunResult:
    text: str
    degraded: bool
    fallback_reason: Optional[str]
    provider: str
    model: str
    trace_id: Optional[str] = None

    def as_dict(self) -> Dict[str, Any]:
        return {
            "text": self.text,
            "degraded": self.degraded,
            "fallback_reason": self.fallback_reason,
            "provider": self.provider,
            "model": self.model,
            "trace_id": self.trace_id,
        }


class LocalLLMClient:
    """LLM client supporting Ollama/LocalAI and OpenAI-compatible endpoints."""

    def __init__(self) -> None:
        self.provider = os.getenv("LLM_PROVIDER", "ollama").strip() or "ollama"
        self.base_url = os.getenv("LLM_BASE_URL", "http://localhost:11434").strip()
        self.model = os.getenv("LLM_MODEL", "llama2").strip() or "llama2"
        self.api_key = os.getenv("LLM_API_KEY", "").strip()
        self.timeout_seconds = float(os.getenv("LLM_TIMEOUT_SECONDS", "60"))

    def _headers(self) -> Dict[str, str]:
        headers: Dict[str, str] = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    def _openai_endpoint(self) -> str:
        base = self.base_url.rstrip("/")
        if base.endswith("/chat/completions"):
            return base
        if base.endswith("/v1"):
            return f"{base}/chat/completions"
        return f"{base}/v1/chat/completions"

    async def _generate_ollama(self, prompt: str, system: Optional[str]) -> str:
        endpoint = f"{self.base_url.rstrip('/')}/api/generate"
        payload: Dict[str, Any] = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
        }
        if system:
            payload["system"] = system

        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            response = await client.post(endpoint, headers=self._headers(), json=payload)
            response.raise_for_status()
            body = response.json()

        if isinstance(body.get("response"), str):
            return body["response"]
        choices = body.get("choices")
        if isinstance(choices, list) and choices:
            first = choices[0]
            if isinstance(first, dict):
                message = first.get("message")
                if isinstance(message, dict) and isinstance(message.get("content"), str):
                    return message["content"]
                if isinstance(first.get("text"), str):
                    return first["text"]
        raise ValueError("invalid_ollama_response")

    async def _generate_openai_compatible(self, prompt: str, system: Optional[str]) -> str:
        endpoint = self._openai_endpoint()
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.2,
        }

        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            response = await client.post(endpoint, headers=self._headers(), json=payload)
            response.raise_for_status()
            body = response.json()

        choices = body.get("choices")
        if isinstance(choices, list) and choices:
            first = choices[0]
            if isinstance(first, dict):
                message = first.get("message")
                if isinstance(message, dict) and isinstance(message.get("content"), str):
                    return message["content"]
                if isinstance(first.get("text"), str):
                    return first["text"]
        raise ValueError("invalid_openai_response")

    async def generate(self, prompt: str, system: Optional[str] = None) -> str:
        provider = self.provider.strip().lower()
        if provider in {"ollama", "localai", "local"}:
            return await self._generate_ollama(prompt, system)
        return await self._generate_openai_compatible(prompt, system)

    async def generate_json(self, prompt: str, system: Optional[str] = None) -> Dict[str, Any]:
        text = await self.generate(prompt, system=system)
        json_text = _extract_json_text(text)
        parsed = json.loads(json_text)
        if not isinstance(parsed, dict):
            raise ValueError("json_response_not_object")
        return parsed


class AIEngine:
    """AI engine for threat assessment, scan analysis, report generation, and chat."""

    def __init__(self) -> None:
        self.llm_client = LocalLLMClient()

    async def assess_threat(
        self,
        ip: str,
        attack_type: str,
        attack_count: int,
        history: Optional[str] = None,
        trace_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        fallback_score = _clamp_score(50 + max(1, _safe_int(attack_count, 1)) * 10)
        fallback_action = "BLOCK" if fallback_score >= 80 else "MONITOR"
        fallback = {
            "score": fallback_score,
            "reason": f"规则降级评分: {ip} 在 {attack_type} 下出现 {attack_count} 次行为",
            "action_suggest": fallback_action,
        }

        prompt = (
            "你是安全分析助手。请评估下面威胁事件并严格输出 JSON:\n"
            "{\n"
            '  "score": 0-100,\n'
            '  "reason": "简要原因",\n'
            '  "action_suggest": "BLOCK 或 MONITOR"\n'
            "}\n\n"
            f"ip={ip}\n"
            f"attack_type={attack_type}\n"
            f"attack_count={attack_count}\n"
            f"history={history or 'none'}\n"
        )

        try:
            result = await self.llm_client.generate_json(
                prompt,
                system="你是 SOC 风险评估模型，只输出 JSON，不输出多余文本。",
            )
            score = _clamp_score(result.get("score"), fallback_score)
            action = _normalize_action(result.get("action_suggest"), score)
            reason = _truncate(str(result.get("reason") or fallback["reason"]), 300)
            return {
                "score": score,
                "reason": reason,
                "action_suggest": action,
                "degraded": False,
                "fallback_reason": None,
                "provider": self.llm_client.provider,
                "model": self.llm_client.model,
                "trace_id": trace_id,
            }
        except Exception as exc:
            return {
                **fallback,
                "degraded": True,
                "fallback_reason": f"llm_assess_failed:{exc.__class__.__name__}",
                "provider": self.llm_client.provider,
                "model": self.llm_client.model,
                "trace_id": trace_id,
            }

    async def analyze_scan_result(
        self,
        scan_data: Dict[str, Any],
        trace_id: Optional[str] = None,
        with_meta: bool = False,
    ) -> Any:
        prompt = (
            "请基于以下扫描数据输出 Markdown 风险分析，包含：\n"
            "1) 风险摘要 2) 高风险点 3) 修复建议\n\n"
            f"{json.dumps(scan_data, ensure_ascii=False, indent=2)}"
        )
        try:
            text = _truncate(
                await self.llm_client.generate(
                    prompt,
                    system="你是安全扫描分析助手，输出结构化 Markdown。",
                ),
                12000,
            ).strip()
            if not text:
                raise ValueError("empty_scan_analysis")
            result = AIRunResult(
                text=text,
                degraded=False,
                fallback_reason=None,
                provider=self.llm_client.provider,
                model=self.llm_client.model,
                trace_id=trace_id,
            )
        except Exception as exc:
            fallback_reason = f"llm_scan_analysis_failed:{exc.__class__.__name__}"
            result = AIRunResult(
                text=_default_scan_markdown(scan_data, fallback_reason),
                degraded=True,
                fallback_reason=fallback_reason,
                provider=self.llm_client.provider,
                model=self.llm_client.model,
                trace_id=trace_id,
            )
        return result.as_dict() if with_meta else result.text

    async def generate_report(
        self,
        report_type: str,
        data: Dict[str, Any],
        trace_id: Optional[str] = None,
        with_meta: bool = False,
    ) -> Any:
        prompt = (
            f"请生成 `{report_type}` 安全运营报告（Markdown）。\n"
            "要求包含：执行摘要、风险概况、处置建议、后续行动。\n\n"
            f"{json.dumps(data, ensure_ascii=False, indent=2)}"
        )
        try:
            text = _truncate(
                await self.llm_client.generate(
                    prompt,
                    system="你是安全运营报告助手，输出面向管理与执行团队的 Markdown 报告。",
                ),
                15000,
            ).strip()
            if not text:
                raise ValueError("empty_report")
            result = AIRunResult(
                text=text,
                degraded=False,
                fallback_reason=None,
                provider=self.llm_client.provider,
                model=self.llm_client.model,
                trace_id=trace_id,
            )
        except Exception as exc:
            fallback_reason = f"llm_report_failed:{exc.__class__.__name__}"
            result = AIRunResult(
                text=_default_report_markdown(report_type, data, fallback_reason),
                degraded=True,
                fallback_reason=fallback_reason,
                provider=self.llm_client.provider,
                model=self.llm_client.model,
                trace_id=trace_id,
            )
        return result.as_dict() if with_meta else result.text

    async def chat(
        self,
        message: str,
        context: Optional[Any] = None,
        history: Optional[list] = None,
        trace_id: Optional[str] = None,
        with_meta: bool = False,
    ) -> Any:
        context_text = ""
        if context is not None:
            if isinstance(context, str):
                context_text = context
            else:
                context_text = json.dumps(context, ensure_ascii=False)

        system_prompt = (
            "你是 SOC 安全运营助手，回答要结合上下文，优先给出可执行建议。"
        )

        parts: list[str] = []
        if context_text:
            parts.append(f"上下文:\n{_truncate(context_text, 4000)}")
        if history:
            turns = []
            for h in history[-10:]:
                role_label = "用户" if h.get("role") == "user" else "助手"
                turns.append(f"{role_label}: {_truncate(str(h.get('content', '')), 800)}")
            parts.append("对话历史:\n" + "\n".join(turns))
        parts.append(f"用户问题:\n{message}")
        prompt = "\n\n".join(parts)

        try:
            text = _truncate(await self.llm_client.generate(prompt, system=system_prompt), 8000).strip()
            if not text:
                raise ValueError("empty_chat_response")
            result = AIRunResult(
                text=text,
                degraded=False,
                fallback_reason=None,
                provider=self.llm_client.provider,
                model=self.llm_client.model,
                trace_id=trace_id,
            )
        except Exception as exc:
            fallback_reason = f"llm_chat_failed:{exc.__class__.__name__}"
            result = AIRunResult(
                text=_default_chat_reply(message, context, fallback_reason),
                degraded=True,
                fallback_reason=fallback_reason,
                provider=self.llm_client.provider,
                model=self.llm_client.model,
                trace_id=trace_id,
            )
        return result.as_dict() if with_meta else result.text


ai_engine = AIEngine()

