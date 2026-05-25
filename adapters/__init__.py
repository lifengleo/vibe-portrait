"""
Adapters: 把不同 agent 的对话历史适配成统一的 Prompt[] 结构。
"""
from pathlib import Path
from typing import List, Optional
from .base import BaseAdapter, Prompt, ProjectInfo
from .workbuddy import WorkBuddyAdapter
from .claude_code import ClaudeCodeAdapter
from .codex import CodexAdapter

ALL_ADAPTERS = [
    WorkBuddyAdapter(),
    ClaudeCodeAdapter(),
    CodexAdapter(),
]


def detect_all() -> List[BaseAdapter]:
    """返回所有本机检测到的 adapter"""
    return [a for a in ALL_ADAPTERS if a.detect()]


def detect_host_agent(skill_path: Optional[Path] = None) -> Optional[str]:
    """根据 skill 安装路径推断"宿主 agent"。

    返回 adapter name (workbuddy/claude/codex) 或 None。

    判定规则：
      - 路径含 .codex/skills 或 .codex/sessions → codex
      - 路径含 .claude/skills 或 .claude/projects → claude
      - 路径含 .workbuddy/skills 或 .workbuddy/projects → workbuddy
      - 否则 None（让用户显式指定）

    用于：默认只扫宿主 agent 自己的对话历史，避免越权读取其他 agent 的数据。
    """
    if skill_path is None:
        # 调用方默认就是 run.py，找它所在的目录链
        skill_path = Path(__file__).resolve().parent.parent
    s = str(skill_path).lower()
    if "/.codex/" in s or "\\.codex\\" in s:
        return "codex"
    if "/.claude/" in s or "\\.claude\\" in s:
        return "claude"
    if "/.workbuddy/" in s or "\\.workbuddy\\" in s:
        return "workbuddy"
    return None


def list_all_projects(only_sources: Optional[List[str]] = None) -> List[ProjectInfo]:
    """合并 adapter 的项目，按更新时间倒序。

    Args:
        only_sources: 只列出这些 source 的项目（如 ["codex"]）。
                      None 表示不过滤（向后兼容老用法，但调用方应显式传入以避免越权）。
    """
    projects = []
    for adapter in detect_all():
        if only_sources is not None and adapter.name not in only_sources:
            continue
        try:
            projects.extend(adapter.list_projects())
        except Exception as e:
            print(f"[warn] adapter {adapter.name} list_projects failed: {e}")
    projects.sort(key=lambda p: p.last_updated, reverse=True)
    return projects


def get_adapter_by_name(name: str) -> BaseAdapter:
    for a in ALL_ADAPTERS:
        if a.name == name:
            return a
    raise ValueError(f"Unknown adapter: {name}")
