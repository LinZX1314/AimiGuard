"""S1-05 AI降级安全边界 测试"""
import pytest
from starlette.testclient import TestClient


# ── ai_fallback 服务逻辑 ──

def test_fallback_response_chat():
    """chat类型降级应返回安全模式提示"""
    from services.ai_fallback import get_fallback_response, FallbackReason
    result = get_fallback_response("chat", FallbackReason.JAILBREAK_DETECTED)
    assert result["fallback"] is True
    assert result["model"] == "rule_engine_v1"
    assert result["confidence"] == 1.0
    assert "安全模式" in result["text"]


def test_fallback_response_threat():
    """threat类型降级应返回威胁处理建议"""
    from services.ai_fallback import get_fallback_response
    result = get_fallback_response("threat")
    assert "威胁事件" in result["text"]
    assert result["fallback"] is True


def test_fallback_response_scan():
    """scan类型降级应返回扫描处理建议"""
    from services.ai_fallback import get_fallback_response
    result = get_fallback_response("scan")
    assert "CVSS" in result["text"]


def test_fallback_response_report():
    """report类型降级应返回报告建议"""
    from services.ai_fallback import get_fallback_response
    result = get_fallback_response("report")
    assert "报告" in result["text"]


def test_fallback_response_unknown_type():
    """未知类型应返回默认响应"""
    from services.ai_fallback import get_fallback_response
    result = get_fallback_response("unknown_type")
    assert "安全模式" in result["text"]


def test_should_fallback_jailbreak():
    """越狱检测应触发降级"""
    from services.ai_fallback import should_fallback, FallbackReason
    fb, reason = should_fallback(jailbreak_detected=True)
    assert fb is True
    assert reason == FallbackReason.JAILBREAK_DETECTED


def test_should_fallback_output_unsafe():
    """输出不安全应触发降级"""
    from services.ai_fallback import should_fallback, FallbackReason
    fb, reason = should_fallback(output_unsafe=True)
    assert fb is True
    assert reason == FallbackReason.OUTPUT_UNSAFE


def test_should_fallback_model_error():
    """模型错误应触发降级"""
    from services.ai_fallback import should_fallback, FallbackReason
    fb, reason = should_fallback(model_error=True)
    assert fb is True
    assert reason == FallbackReason.MODEL_ERROR


def test_should_fallback_low_confidence():
    """低置信度应触发降级"""
    from services.ai_fallback import should_fallback
    fb, reason = should_fallback(confidence=0.1)
    assert fb is True
    assert "confidence" in reason


def test_should_fallback_consecutive_failures():
    """连续失败应触发降级"""
    from services.ai_fallback import should_fallback
    fb, reason = should_fallback(consecutive_failures=3)
    assert fb is True


def test_should_not_fallback_normal():
    """正常情况不应触发降级"""
    from services.ai_fallback import should_fallback
    fb, reason = should_fallback(confidence=0.8)
    assert fb is False
    assert reason == ""


def test_get_available_context_types():
    """应返回支持的上下文类型"""
    from services.ai_fallback import get_available_context_types
    types = get_available_context_types()
    assert "chat" in types
    assert "threat" in types
    assert "scan" in types
    assert "report" in types
