"""
Adapters: 把不同 agent 的对话历史适配成统一的 Prompt[] 结构。
"""
from typing import List
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


def list_all_projects() -> List[ProjectInfo]:
    """合并所有 adapter 的项目，按更新时间倒序"""
    projects = []
    for adapter in detect_all():
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
