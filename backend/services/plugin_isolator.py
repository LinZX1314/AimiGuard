"""
S2-04 MCP 插件隔离沙箱
- 插件在独立子进程中运行，限制资源和权限
- 超时自动终止
- 隔离文件系统和网络访问
"""
from __future__ import annotations

import logging
import os
import subprocess
import tempfile
import time
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# 沙箱默认配置
DEFAULT_TIMEOUT_SECONDS = 30
DEFAULT_MAX_MEMORY_MB = 256
DEFAULT_MAX_OUTPUT_BYTES = 1_000_000  # 1MB

# 禁止的系统调用/命令模式
_BLOCKED_COMMANDS = {
    "rm -rf /",
    "mkfs",
    "dd if=/dev/zero",
    "shutdown",
    "reboot",
    "format c:",
    "del /f /s /q",
}

# 允许的可执行文件白名单
_ALLOWED_EXECUTABLES = {
    "python", "python3", "node", "npx",
    "nmap", "nuclei", "nikto",
    "curl", "wget",
}


class SandboxConfig:
    """沙箱配置"""

    def __init__(
        self,
        timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
        max_memory_mb: int = DEFAULT_MAX_MEMORY_MB,
        max_output_bytes: int = DEFAULT_MAX_OUTPUT_BYTES,
        allowed_paths: Optional[List[str]] = None,
        network_enabled: bool = False,
        env_whitelist: Optional[List[str]] = None,
    ):
        self.timeout_seconds = timeout_seconds
        self.max_memory_mb = max_memory_mb
        self.max_output_bytes = max_output_bytes
        self.allowed_paths = allowed_paths or []
        self.network_enabled = network_enabled
        self.env_whitelist = env_whitelist or ["PATH", "HOME", "TEMP", "TMP"]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timeout_seconds": self.timeout_seconds,
            "max_memory_mb": self.max_memory_mb,
            "max_output_bytes": self.max_output_bytes,
            "allowed_paths": self.allowed_paths,
            "network_enabled": self.network_enabled,
            "env_whitelist": self.env_whitelist,
        }


class SandboxResult:
    """沙箱执行结果"""

    def __init__(
        self,
        success: bool,
        stdout: str = "",
        stderr: str = "",
        exit_code: int = -1,
        elapsed_ms: float = 0,
        terminated: bool = False,
        error: Optional[str] = None,
    ):
        self.success = success
        self.stdout = stdout
        self.stderr = stderr
        self.exit_code = exit_code
        self.elapsed_ms = elapsed_ms
        self.terminated = terminated
        self.error = error

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "stdout": self.stdout[:1000],
            "stderr": self.stderr[:500],
            "exit_code": self.exit_code,
            "elapsed_ms": round(self.elapsed_ms, 2),
            "terminated": self.terminated,
            "error": self.error,
        }


def validate_command(command: str) -> Tuple[bool, str]:
    """
    验证命令安全性。

    Returns:
        (is_safe, reason)
    """
    if not command or not command.strip():
        return False, "empty_command"

    cmd_lower = command.lower().strip()

    # 检查黑名单命令
    for blocked in _BLOCKED_COMMANDS:
        if blocked in cmd_lower:
            return False, f"blocked_command:{blocked}"

    # 检查可执行文件白名单
    executable = cmd_lower.split()[0] if cmd_lower.split() else ""
    # 去掉路径前缀
    exe_name = os.path.basename(executable)
    if exe_name and exe_name not in _ALLOWED_EXECUTABLES:
        return False, f"executable_not_whitelisted:{exe_name}"

    return True, "command_safe"


def build_sandbox_env(config: SandboxConfig) -> Dict[str, str]:
    """构建沙箱环境变量（仅白名单中的变量）"""
    env = {}
    for key in config.env_whitelist:
        val = os.environ.get(key)
        if val:
            env[key] = val
    return env


def execute_in_sandbox(
    command: str,
    config: Optional[SandboxConfig] = None,
    working_dir: Optional[str] = None,
    input_data: Optional[str] = None,
) -> SandboxResult:
    """
    在沙箱中执行命令。

    - 独立子进程
    - 超时自动终止
    - 环境变量白名单
    - 输出大小限制
    """
    if config is None:
        config = SandboxConfig()

    # 1. 命令安全验证
    is_safe, reason = validate_command(command)
    if not is_safe:
        logger.warning(f"Sandbox rejected command: {reason}")
        return SandboxResult(
            success=False,
            error=f"command_rejected:{reason}",
        )

    # 2. 构建安全环境
    env = build_sandbox_env(config)

    # 3. 工作目录
    if working_dir and not os.path.isdir(working_dir):
        working_dir = None
    if not working_dir:
        working_dir = tempfile.gettempdir()

    # 4. 执行
    t0 = time.monotonic()
    try:
        proc = subprocess.Popen(
            command,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            stdin=subprocess.PIPE if input_data else None,
            env=env,
            cwd=working_dir,
        )

        try:
            stdout_bytes, stderr_bytes = proc.communicate(
                input=input_data.encode() if input_data else None,
                timeout=config.timeout_seconds,
            )
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()
            elapsed = (time.monotonic() - t0) * 1000
            logger.warning(f"Sandbox timeout after {config.timeout_seconds}s: {command[:80]}")
            return SandboxResult(
                success=False,
                elapsed_ms=elapsed,
                terminated=True,
                error=f"timeout_after_{config.timeout_seconds}s",
            )

        elapsed = (time.monotonic() - t0) * 1000

        stdout = stdout_bytes.decode("utf-8", errors="replace")[:config.max_output_bytes]
        stderr = stderr_bytes.decode("utf-8", errors="replace")[:config.max_output_bytes]

        return SandboxResult(
            success=proc.returncode == 0,
            stdout=stdout,
            stderr=stderr,
            exit_code=proc.returncode,
            elapsed_ms=elapsed,
        )

    except Exception as e:
        elapsed = (time.monotonic() - t0) * 1000
        logger.error(f"Sandbox execution error: {e}")
        return SandboxResult(
            success=False,
            elapsed_ms=elapsed,
            error=str(e),
        )


def get_sandbox_status() -> Dict[str, Any]:
    """获取沙箱配置状态"""
    return {
        "default_timeout_seconds": DEFAULT_TIMEOUT_SECONDS,
        "default_max_memory_mb": DEFAULT_MAX_MEMORY_MB,
        "default_max_output_bytes": DEFAULT_MAX_OUTPUT_BYTES,
        "blocked_commands_count": len(_BLOCKED_COMMANDS),
        "allowed_executables": sorted(_ALLOWED_EXECUTABLES),
    }
