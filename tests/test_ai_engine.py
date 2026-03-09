"""AIEngine tests — helpers, fallback, assess, scan, report, chat, exploit, attack path, honeypot."""
import pytest
from unittest.mock import patch, AsyncMock, MagicMock

from services.ai_engine import (
    AIEngine,
    LocalLLMClient,
    AIRunResult,
    _bool_env,
    _safe_int,
    _clamp_score,
    _normalize_action,
    _truncate,
    _extract_json_text,
    _default_scan_markdown,
    _default_report_markdown,
    _default_chat_reply,
    ALLOWED_ACTIONS,
)


# ── Pure helpers ──

def test_safe_int():
    assert _safe_int("42", 0) == 42
    assert _safe_int("abc", 99) == 99
    assert _safe_int(None, 5) == 5


def test_clamp_score():
    assert _clamp_score(50) == 50
    assert _clamp_score(-10) == 0
    assert _clamp_score(200) == 100
    assert _clamp_score("abc") == 50  # default


def test_normalize_action_valid():
    assert _normalize_action("BLOCK", 90) == "BLOCK"
    assert _normalize_action("MONITOR", 50) == "MONITOR"
    assert _normalize_action("IGNORE", 10) == "IGNORE"


def test_normalize_action_invalid_high_score():
    assert _normalize_action("bad", 85) == "BLOCK"


def test_normalize_action_invalid_low_score():
    assert _normalize_action("bad", 50) == "MONITOR"


def test_truncate():
    assert _truncate("short") == "short"
    assert len(_truncate("x" * 10000, 100)) == 100


def test_extract_json_text_fenced():
    text = 'Some text ```json\n{"score": 90}\n``` more text'
    assert _extract_json_text(text) == '{"score": 90}'


def test_extract_json_text_bare():
    text = 'prefix {"a": 1} suffix'
    assert _extract_json_text(text) == '{"a": 1}'


def test_extract_json_text_empty():
    assert _extract_json_text("") == "{}"
    assert _extract_json_text(None) == "{}"


def test_extract_json_text_no_braces():
    assert _extract_json_text("no json here") == "no json here"


# ── Fallback markdown generators ──

def test_default_scan_markdown():
    data = {"findings": [{"port": 22}, {"port": 80}], "target": "10.0.0.1"}
    md = _default_scan_markdown(data, "test_reason")
    assert "10.0.0.1" in md
    assert "22" in md
    assert "test_reason" in md


def test_default_report_markdown():
    data = {"scope": "weekly", "defense_summary": "ok", "scan_summary": "clean"}
    md = _default_report_markdown("weekly", data, "reason")
    assert "weekly" in md
    assert "reason" in md


def test_default_chat_reply():
    reply = _default_chat_reply("你好", None, "test_reason")
    assert "你好" in reply
    assert "test_reason" in reply


# ── AIRunResult ──

def test_ai_run_result_as_dict():
    r = AIRunResult(text="ok", degraded=False, fallback_reason=None, provider="ollama", model="llama2", trace_id="t1")
    d = r.as_dict()
    assert d["text"] == "ok"
    assert d["degraded"] is False
    assert d["provider"] == "ollama"


# ── LocalLLMClient ──

def test_llm_client_openai_endpoint():
    with patch.dict("os.environ", {"LLM_BASE_URL": "http://llm.local/v1"}):
        client = LocalLLMClient()
    assert client._openai_endpoint().endswith("/chat/completions")


def test_llm_client_openai_endpoint_already_full():
    with patch.dict("os.environ", {"LLM_BASE_URL": "http://llm.local/v1/chat/completions"}):
        client = LocalLLMClient()
    assert client._openai_endpoint() == "http://llm.local/v1/chat/completions"


def test_llm_client_headers_no_key():
    with patch.dict("os.environ", {"LLM_API_KEY": ""}):
        client = LocalLLMClient()
    headers = client._headers()
    assert "Authorization" not in headers


def test_llm_client_headers_with_key():
    with patch.dict("os.environ", {"LLM_API_KEY": "sk-123"}):
        client = LocalLLMClient()
    headers = client._headers()
    assert headers["Authorization"] == "Bearer sk-123"


# ── AIEngine.assess_threat fallback ──

@pytest.mark.asyncio
async def test_assess_threat_fallback():
    engine = AIEngine()
    engine.llm_client.generate_json = AsyncMock(side_effect=ConnectionError("offline"))
    result = await engine.assess_threat(ip="10.0.0.1", attack_type="ssh_brute", attack_count=5, trace_id="t1")
    assert result["degraded"] is True
    assert result["score"] == 100  # 50 + 5*10 = 100
    assert result["action_suggest"] == "BLOCK"
    assert "ConnectionError" in result["fallback_reason"]


@pytest.mark.asyncio
async def test_assess_threat_success():
    engine = AIEngine()
    engine.llm_client.generate_json = AsyncMock(return_value={
        "score": 75,
        "reason": "中等风险",
        "action_suggest": "MONITOR",
    })
    result = await engine.assess_threat(ip="10.0.0.1", attack_type="port_scan", attack_count=1, trace_id="t2")
    assert result["degraded"] is False
    assert result["score"] == 75
    assert result["action_suggest"] == "MONITOR"


# ── AIEngine.analyze_scan_result ──

@pytest.mark.asyncio
async def test_analyze_scan_fallback():
    engine = AIEngine()
    engine.llm_client.generate = AsyncMock(side_effect=RuntimeError("fail"))
    result = await engine.analyze_scan_result({"target": "10.0.0.1"}, trace_id="t3", with_meta=True)
    assert result["degraded"] is True
    assert "10.0.0.1" in result["text"]


@pytest.mark.asyncio
async def test_analyze_scan_success():
    engine = AIEngine()
    engine.llm_client.generate = AsyncMock(return_value="## 扫描分析\n正常")
    result = await engine.analyze_scan_result({}, trace_id="t4", with_meta=True)
    assert result["degraded"] is False
    assert "扫描分析" in result["text"]


@pytest.mark.asyncio
async def test_analyze_scan_without_meta():
    engine = AIEngine()
    engine.llm_client.generate = AsyncMock(return_value="report text")
    result = await engine.analyze_scan_result({}, with_meta=False)
    assert isinstance(result, str)
    assert result == "report text"


# ── AIEngine.generate_report ──

@pytest.mark.asyncio
async def test_generate_report_fallback():
    engine = AIEngine()
    engine.llm_client.generate = AsyncMock(side_effect=Exception("err"))
    result = await engine.generate_report("weekly", {"scope": "all"}, trace_id="t5", with_meta=True)
    assert result["degraded"] is True


@pytest.mark.asyncio
async def test_generate_report_success():
    engine = AIEngine()
    engine.llm_client.generate = AsyncMock(return_value="# Weekly Report\ncontent")
    result = await engine.generate_report("weekly", {}, with_meta=True)
    assert result["degraded"] is False
    assert "Weekly Report" in result["text"]


# ── AIEngine.chat ──

@pytest.mark.asyncio
async def test_chat_fallback():
    engine = AIEngine()
    engine.llm_client.generate = AsyncMock(side_effect=Exception("offline"))
    result = await engine.chat("你好", context={"mode": "defense"}, trace_id="t6", with_meta=True)
    assert result["degraded"] is True
    assert "你好" in result["text"]


@pytest.mark.asyncio
async def test_chat_success():
    engine = AIEngine()
    engine.llm_client.generate = AsyncMock(return_value="建议封禁IP")
    result = await engine.chat("怎么处理?", with_meta=True)
    assert result["degraded"] is False
    assert "封禁" in result["text"]


@pytest.mark.asyncio
async def test_chat_with_history():
    engine = AIEngine()
    engine.llm_client.generate = AsyncMock(return_value="回复")
    history = [{"role": "user", "content": "之前的问题"}, {"role": "assistant", "content": "之前的回答"}]
    result = await engine.chat("新问题", history=history, with_meta=False)
    assert result == "回复"


# ── AIEngine.assess_exploitability ──

@pytest.mark.asyncio
async def test_assess_exploitability_fallback_high():
    engine = AIEngine()
    engine.llm_client.generate_json = AsyncMock(side_effect=Exception("err"))
    result = await engine.assess_exploitability("CVE-2024-001", {"severity": "CRITICAL"}, trace_id="t7")
    assert result["degraded"] is True
    assert result["is_exploitable"] is True
    assert result["exploitation_complexity"] == "low"


@pytest.mark.asyncio
async def test_assess_exploitability_fallback_low():
    engine = AIEngine()
    engine.llm_client.generate_json = AsyncMock(side_effect=Exception("err"))
    result = await engine.assess_exploitability("CVE-2024-002", {"severity": "LOW"})
    assert result["is_exploitable"] is False


@pytest.mark.asyncio
async def test_assess_exploitability_success():
    engine = AIEngine()
    engine.llm_client.generate_json = AsyncMock(return_value={
        "is_exploitable": True,
        "exploit_source": "Exploit-DB",
        "exploitation_complexity": "low",
        "attack_prerequisites": ["network access"],
    })
    result = await engine.assess_exploitability("CVE-2024-003", {"severity": "HIGH"})
    assert result["degraded"] is False
    assert result["exploit_source"] == "Exploit-DB"


# ── AIEngine.analyze_attack_path ──

@pytest.mark.asyncio
async def test_analyze_attack_path_no_edges():
    engine = AIEngine()
    assets = [{"ip": "10.0.0.1"}, {"ip": "10.0.0.2"}]
    findings = [{"asset": "10.0.0.1", "port": 80, "service": "http"}]
    result = await engine.analyze_attack_path(assets, findings, trace_id="t8")
    assert result["total_nodes"] == 2
    assert result["total_edges"] == 0


@pytest.mark.asyncio
async def test_analyze_attack_path_with_lateral():
    engine = AIEngine()
    assets = [{"ip": "10.0.0.1"}, {"ip": "10.0.0.2"}]
    findings = [
        {"asset": "10.0.0.1", "port": 22, "service": "ssh", "severity": "HIGH"},
        {"asset": "10.0.0.2", "port": 22, "service": "ssh", "severity": "HIGH"},
    ]
    result = await engine.analyze_attack_path(assets, findings)
    assert result["high_risk_count"] == 2
    assert result["total_edges"] >= 1
    assert "lateral" in result["edges"][0]["label"]


# ── AIEngine.suggest_honeypot_strategy ──

@pytest.mark.asyncio
async def test_honeypot_strategy_with_attacks():
    engine = AIEngine()
    trend = {
        "top_attack_types": [
            {"type": "ssh_brute_force", "count": 100},
            {"type": "rdp_scan", "count": 50},
        ],
        "total_events": 150,
    }
    result = await engine.suggest_honeypot_strategy(trend, trace_id="t9")
    assert result["total_suggestions"] >= 2
    types = [s["honeypot_type"] for s in result["suggestions"]]
    assert "ssh" in types
    assert "rdp" in types


@pytest.mark.asyncio
async def test_honeypot_strategy_no_match_fallback():
    engine = AIEngine()
    trend = {"top_attack_types": [{"type": "unknown_attack", "count": 10}], "total_events": 10}
    result = await engine.suggest_honeypot_strategy(trend)
    assert result["total_suggestions"] >= 1
    assert result["suggestions"][0]["honeypot_type"] == "ssh"


@pytest.mark.asyncio
async def test_honeypot_strategy_empty():
    engine = AIEngine()
    trend = {"top_attack_types": [], "total_events": 0}
    result = await engine.suggest_honeypot_strategy(trend)
    assert result["total_suggestions"] == 0
