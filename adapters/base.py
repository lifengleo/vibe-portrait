"""
Adapter 接口定义 + 公共数据结构
"""
from dataclasses import dataclass, field
from typing import Optional, List


@dataclass
class Prompt:
    """统一的 user prompt 结构"""
    text: str
    timestamp: int  # Unix ms
    project_id: str
    project_label: str
    source: str  # workbuddy / claude_code / codex


@dataclass
class ProjectInfo:
    """对话窗口的元信息（用于让用户挑选）"""
    source: str          # adapter 标识
    source_display: str  # "WorkBuddy" / "Claude Code" / "Codex"
    project_id: str      # 项目唯一 ID（adapter 内部）
    label: str           # 用户可读的项目名
    prompt_count: int    # 用户消息数（粗略估算）
    first_prompt_preview: str  # 第一句话前 30 字
    first_at: int        # 第一条 user prompt 时间（Unix ms）
    last_updated: int    # 最后更新时间（Unix ms）

    def render_line(self, idx: int) -> str:
        """渲染为列表里的一行"""
        from datetime import datetime
        first = datetime.fromtimestamp(self.first_at / 1000).strftime("%m.%d")
        last = datetime.fromtimestamp(self.last_updated / 1000).strftime("%m.%d")
        return (
            f"[{idx:02d}] [{self.source_display}] {self.label} / "
            f"{self.prompt_count} 条 / {first} → {last}"
        )


class BaseAdapter:
    """所有 agent adapter 的基类"""
    name: str = ""
    display_name: str = ""

    def detect(self) -> bool:
        """检查本机是否能找到这个 agent 的对话历史目录"""
        raise NotImplementedError

    def list_projects(self) -> List[ProjectInfo]:
        """列出所有可用的对话窗口"""
        raise NotImplementedError

    def extract_prompts(self, project_id: str) -> List[Prompt]:
        """从指定项目抽取所有 user prompt"""
        raise NotImplementedError
