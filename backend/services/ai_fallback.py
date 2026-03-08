"""
S1-05 AI 降级安全边界
- 当检测到潜在越狱/异常行为时，自动切换到严格规则引擎
- 规则引擎提供确定性、安全的兜底响应
- 记录降级事件用于后续分析
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# 规则引擎兜底响应表：按 context_type 匹配
_RULE_ENGINE_RESPONSES: Dict[str, str] = {
    "threat": (
        "⚠️ AI 分析暂时不可用，已切换至规则引擎模式。\n"
        "根据当前威胁事件的严重程度，建议：\n"
        "1. 确认事件来源IP和目标资产\n"
        "2. 检查相关日志和告警\n"
        "3. 如属高危事件，立即隔离受影响资产\n"
        "4. 联系安全团队进行人工研判"
    ),
    "scan": (
        "⚠️ AI 分析暂时不可用，已切换至规则引擎模式。\n"
        "扫描结果处理建议：\n"
        "1. 按 CVSS 评分排序处理高危漏洞\n"
        "2. 对有 EPSS > 0.1 的漏洞优先修复\n"
        "3. 检查是否有已知利用（CISA KEV）\n"
        "4. 生成修复工单分配给相关责任人"
    ),
    "report": (
        "⚠️ AI 分析暂时不可用，已切换至规则引擎模式。\n"
        "报告生成建议：\n"
        "1. 使用标准模板生成安全报告\n"
        "2. 包含扫描摘要、漏洞统计、修复建议\n"
        "3. 手动审核后再发送给相关方"
    ),
    "chat": (
        "⚠️ AI 助手暂时不可用，已切换至安全模式。\n"
        "您可以：\n"
        "1. 查看仪表盘获取实时安全态势\n"
        "2. 通过扫描模块执行资产扫描\n"
        "3. 查看告警和威胁事件列表\n"
        "4. 联系安全管理员获取帮助"
    ),
}

_DEFAULT_RESPONSE = (
    "⚠️ AI 分析暂时不可用，已切换至安全模式。\n"
    "请通过其他功能模块完成操作，或联系管理员。"
)


class FallbackReason:
    """降级原因枚举"""
    JAILBREAK_DETECTED = "jailbreak_detected"
    OUTPUT_UNSAFE = "output_unsafe"
    MODEL_ERROR = "model_error"
    CONFIDENCE_LOW = "confidence_low"
    RATE_LIMIT = "rate_limit"
    MANUAL = "manual_fallback"


def get_fallback_response(
    context_type: Optional[str] = None,
    reason: str = FallbackReason.JAILBREAK_DETECTED,
) -> Dict[str, Any]:
    """
    获取规则引擎兜底响应。

    Args:
        context_type: 对话上下文类型 (threat/scan/report/chat)
        reason: 降级原因

    Returns:
        包含兜底响应和元数据的字典
    """
    response_text = _RULE_ENGINE_RESPONSES.get(
        context_type or "chat", _DEFAULT_RESPONSE
    )

    return {
        "text": response_text,
        "fallback": True,
        "fallback_reason": reason,
        "model": "rule_engine_v1",
        "confidence": 1.0,  # 规则引擎确定性输出
    }


def should_fallback(
    confidence: Optional[float] = None,
    jailbreak_detected: bool = False,
    output_unsafe: bool = False,
    model_error: bool = False,
    consecutive_failures: int = 0,
) -> tuple[bool, str]:
    """
    判断是否应该降级到规则引擎。

    Returns:
        (should_fallback, reason)
    """
    if jailbreak_detected:
        return True, FallbackReason.JAILBREAK_DETECTED

    if output_unsafe:
        return True, FallbackReason.OUTPUT_UNSAFE

    if model_error:
        return True, FallbackReason.MODEL_ERROR

    if confidence is not None and confidence < 0.3:
        return True, FallbackReason.CONFIDENCE_LOW

    if consecutive_failures >= 3:
        return True, FallbackReason.RATE_LIMIT

    return False, ""


def get_available_context_types() -> list:
    """获取规则引擎支持的上下文类型"""
    return list(_RULE_ENGINE_RESPONSES.keys())
