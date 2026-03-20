"""
Skill 注册中心 - 管理所有 AI Skill
"""
import json
import os
from typing import Any

# ─── Skill 注册表 ─────────────────────────────────────────────────────────────


class Skill:
    """单个 Skill 的元信息 + 执行器"""

    def __init__(self, name: str, description: str, tools: list[dict], executor: Any):
        self.name = name
        self.description = description
        self.tools = tools          # OpenAI function calling 格式的工具定义列表
        self.executor = executor    # 实际执行器（callable）

    def __repr__(self):
        return f"<Skill: {self.name}>"


class SkillRegistry:
    """全局 Skill 注册表"""

    def __init__(self):
        self._skills: dict[str, Skill] = {}

    def register(self, skill: Skill):
        self._skills[skill.name] = skill

    def get(self, name: str) -> Skill | None:
        return self._skills.get(name)

    def all(self) -> dict[str, Skill]:
        return dict(self._skills)

    def all_tools(self) -> list[dict]:
        """获取所有 skill 的工具定义（扁平化）"""
        tools = []
        for skill in self._skills.values():
            tools.extend(skill.tools)
        return tools

    def get_tools_by_skill(self, skill_name: str) -> list[dict]:
        skill = self.get(skill_name)
        return skill.tools if skill else []


# ─── 全局实例 ─────────────────────────────────────────────────────────────────

_registry = SkillRegistry()


def register_skill(skill: Skill):
    _registry.register(skill)


def get_all_skills() -> dict[str, Skill]:
    return _registry.all()


def get_skill(name: str) -> Skill | None:
    return _registry.get(name)


def get_all_skill_tools() -> list[dict]:
    return _registry.all_tools()


def get_skill_tools(skill_name: str) -> list[dict]:
    return _registry.get_tools_by_skill(skill_name)


# ─── 懒加载 drill_executor ────────────────────────────────────────────────────
# 避免循环导入，延迟到真正使用时才导入


def _load_drill_executor():
    from .drill_executor import DrillExecutor
    return DrillExecutor()


def get_drill_tools() -> list[dict]:
    return _registry.get_tools_by_skill('drill_executor')


# ─── drill_executor skill 注册 ────────────────────────────────────────────────
# 在首次访问时自动注册


def _ensure_drill_registered():
    if _registry.get('drill_executor') is None:
        executor = _load_drill_executor()
        skill = Skill(
            name='drill_executor',
            description=(
                '【安全演练执行器】当用户提供安全演练文档或要求执行渗透测试/安全评估时，必须使用此 Skill。'
                '支持：文档分析、资产发现、端口扫描、Web截图、弱口令检测、蜜罐日志审计、报告生成。'
                'AI 将智能分析文档内容，动态决定执行步骤，以 Agent 循环方式逐步完成任务。'
            ),
            tools=[],        # 工具定义由 DrillExecutor 动态提供
            executor=executor,
        )
        _registry.register(skill)


# 提供一个属性式的访问器，触发自动注册
class _DrillExecutorProxy:
    """懒加载 + 自动注册的 drill_executor 代理"""
    _instance = None

    def __getattr__(self, name):
        _ensure_drill_registered()
        return getattr(_registry.get('drill_executor'), name)

    def __call__(self, *args, **kwargs):
        _ensure_drill_registered()
        return _registry.get('drill_executor').executor(*args, **kwargs)


drill_executor = _DrillExecutorProxy()
