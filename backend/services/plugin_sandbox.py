"""
S2-02 MCP 插件权限最小化（OWASP 最小 Agency 原则）
- 每个插件声明权限范围
- 运行时按声明权限做沙箱隔离
- 超出声明权限的调用立即终止并告警
"""
from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger(__name__)

VALID_PERMISSIONS = {
    "read_only",        # 只读访问
    "execute",          # 执行命令
    "network_access",   # 网络访问
    "file_system",      # 文件系统访问
}

# 工具调用到所需权限的映射
TOOL_PERMISSION_MAP: Dict[str, str] = {
    "read_file": "read_only",
    "list_directory": "read_only",
    "query_database": "read_only",
    "execute_command": "execute",
    "run_script": "execute",
    "http_request": "network_access",
    "api_call": "network_access",
    "write_file": "file_system",
    "delete_file": "file_system",
    "create_directory": "file_system",
}


def parse_permissions(permissions_json: Optional[str]) -> Set[str]:
    """解析插件声明的权限列表"""
    if not permissions_json:
        return set()
    try:
        perms = json.loads(permissions_json)
        if isinstance(perms, list):
            return {p for p in perms if p in VALID_PERMISSIONS}
    except (json.JSONDecodeError, ValueError):
        pass
    return set()


def check_permission(
    declared_permissions: Set[str],
    tool_name: str,
) -> tuple[bool, str]:
    """
    检查插件调用是否在声明权限范围内。

    Returns:
        (allowed, reason)
    """
    required = TOOL_PERMISSION_MAP.get(tool_name)
    if required is None:
        # 未知工具默认需要 execute 权限
        required = "execute"

    if required in declared_permissions:
        return True, f"permission_granted:{required}"

    return False, f"permission_denied:requires_{required}"


def validate_declared_permissions(permissions: List[str]) -> tuple[bool, str]:
    """验证声明的权限列表是否合法"""
    if not permissions:
        return False, "no_permissions_declared"

    invalid = [p for p in permissions if p not in VALID_PERMISSIONS]
    if invalid:
        return False, f"invalid_permissions:{','.join(invalid)}"

    return True, "valid"


def compute_risk_score(permissions: List[str]) -> int:
    """根据声明权限计算风险评分 (0-100)"""
    risk_weights = {
        "read_only": 10,
        "network_access": 30,
        "execute": 40,
        "file_system": 50,
    }
    score = sum(risk_weights.get(p, 20) for p in permissions)
    return min(score, 100)


def enforce_sandbox(
    plugin_id: int,
    plugin_name: str,
    declared_permissions_json: Optional[str],
    tool_name: str,
    args: Optional[Dict[str, Any]] = None,
) -> tuple[bool, str]:
    """
    沙箱隔离执行点。在MCP工具调用前调用此方法。

    Returns:
        (allowed, reason)
    """
    perms = parse_permissions(declared_permissions_json)

    if not perms:
        return False, "no_permissions_declared"

    allowed, reason = check_permission(perms, tool_name)

    if not allowed:
        logger.warning(
            f"Plugin sandbox violation: plugin={plugin_name}(id={plugin_id}) "
            f"tool={tool_name} reason={reason}"
        )

    return allowed, reason
