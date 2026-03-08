"""S2-04 插件隔离沙箱 测试"""
import pytest
from starlette.testclient import TestClient


# ── 命令安全验证 ──

def test_validate_safe_command():
    """安全命令应通过"""
    from services.plugin_isolator import validate_command
    safe, reason = validate_command("python --version")
    assert safe is True


def test_validate_blocked_rm_rf():
    """rm -rf / 应被阻止"""
    from services.plugin_isolator import validate_command
    safe, reason = validate_command("rm -rf / --no-preserve-root")
    assert safe is False
    assert "blocked" in reason


def test_validate_blocked_shutdown():
    """shutdown 应被阻止"""
    from services.plugin_isolator import validate_command
    safe, reason = validate_command("shutdown -h now")
    assert safe is False


def test_validate_empty_command():
    """空命令应被拒绝"""
    from services.plugin_isolator import validate_command
    safe, reason = validate_command("")
    assert safe is False


def test_validate_not_whitelisted():
    """非白名单可执行文件应被拒绝"""
    from services.plugin_isolator import validate_command
    safe, reason = validate_command("gcc malware.c -o malware")
    assert safe is False
    assert "not_whitelisted" in reason


def test_validate_nmap_allowed():
    """nmap 应在白名单中"""
    from services.plugin_isolator import validate_command
    safe, reason = validate_command("nmap -sV 10.0.0.1")
    assert safe is True


# ── SandboxConfig ──

def test_sandbox_config_defaults():
    """默认沙箱配置"""
    from services.plugin_isolator import SandboxConfig
    config = SandboxConfig()
    assert config.timeout_seconds == 30
    assert config.max_memory_mb == 256
    assert config.network_enabled is False


def test_sandbox_config_to_dict():
    """配置序列化"""
    from services.plugin_isolator import SandboxConfig
    config = SandboxConfig(timeout_seconds=10, network_enabled=True)
    d = config.to_dict()
    assert d["timeout_seconds"] == 10
    assert d["network_enabled"] is True


# ── 沙箱环境 ──

def test_build_sandbox_env():
    """沙箱环境应只含白名单变量"""
    import os
    from services.plugin_isolator import SandboxConfig, build_sandbox_env
    config = SandboxConfig(env_whitelist=["PATH"])
    env = build_sandbox_env(config)
    assert "PATH" in env or len(env) == 0  # PATH might not exist in test env
    # 不应包含非白名单变量
    for key in env:
        assert key in config.env_whitelist


# ── 沙箱执行 ──

def test_execute_safe_command():
    """安全命令应成功执行"""
    from services.plugin_isolator import execute_in_sandbox
    result = execute_in_sandbox("python --version")
    assert result.success is True
    assert result.exit_code == 0
    assert result.elapsed_ms > 0


def test_execute_blocked_command():
    """阻止的命令应返回失败"""
    from services.plugin_isolator import execute_in_sandbox
    result = execute_in_sandbox("rm -rf /")
    assert result.success is False
    assert "rejected" in result.error


def test_execute_with_timeout():
    """超时应终止进程"""
    from services.plugin_isolator import execute_in_sandbox, SandboxConfig
    config = SandboxConfig(timeout_seconds=1)
    result = execute_in_sandbox("python -c \"import time; time.sleep(10)\"", config=config)
    assert result.success is False
    assert result.terminated is True


def test_sandbox_result_to_dict():
    """结果序列化"""
    from services.plugin_isolator import SandboxResult
    result = SandboxResult(success=True, stdout="hello", exit_code=0, elapsed_ms=15.5)
    d = result.to_dict()
    assert d["success"] is True
    assert d["exit_code"] == 0


# ── 沙箱状态 ──

def test_get_sandbox_status():
    """获取沙箱状态"""
    from services.plugin_isolator import get_sandbox_status
    status = get_sandbox_status()
    assert status["default_timeout_seconds"] == 30
    assert "python" in status["allowed_executables"]
    assert status["blocked_commands_count"] >= 5
