"""
Claude Code adapter

数据格式：~/.claude/projects/<dir>/*.jsonl
每行是一条消息记录，role=user 的 content 字段就是用户输入。

注意：这是基于公开调研的实现，不同版本可能有差异，需要用真实数据校验。
"""
import json
from pathlib import Path
from typing import Optional, List
from .base import BaseAdapter, Prompt, ProjectInfo

ROOT = Path.home() / ".claude" / "projects"


class ClaudeCodeAdapter(BaseAdapter):
    name = "claude_code"
    display_name = "Claude Code"

    def detect(self) -> bool:
        return ROOT.exists() and ROOT.is_dir()

    def list_projects(self) -> List[ProjectInfo]:
        if not self.detect():
            return []
        out = []
        for project_dir in ROOT.iterdir():
            if not project_dir.is_dir():
                continue
            for jsonl in project_dir.glob("*.jsonl"):
                try:
                    info = self._read_meta(jsonl)
                    if info:
                        out.append(info)
                except Exception as e:
                    print(f"[warn] claude_code failed: {jsonl}: {e}")
        return out

    def _read_meta(self, jsonl: Path) -> Optional[ProjectInfo]:
        first_at = 0
        last_at = 0
        prompt_count = 0
        first_preview = ""

        with open(jsonl, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    obj = json.loads(line)
                except Exception:
                    continue
                if obj.get("type") != "user":
                    continue
                msg = obj.get("message", {})
                content = msg.get("content", "")
                # claude code 的 content 可能是 str 或 list
                text = self._extract_text(content)
                if not text or text.startswith("/"):
                    continue
                # 时间戳可能在不同字段
                ts_str = obj.get("timestamp") or msg.get("timestamp")
                ts = self._parse_ts(ts_str)
                if not ts:
                    continue
                prompt_count += 1
                if first_at == 0:
                    first_at = ts
                    first_preview = text[:30].replace("\n", " ")
                last_at = max(last_at, ts)

        if prompt_count == 0:
            return None

        return ProjectInfo(
            source=self.name,
            source_display=self.display_name,
            project_id=str(jsonl),
            label=jsonl.parent.name.split("-")[-1] or jsonl.parent.name,
            prompt_count=prompt_count,
            first_prompt_preview=first_preview,
            first_at=first_at,
            last_updated=last_at,
        )

    def _extract_text(self, content) -> str:
        if isinstance(content, str):
            return content.strip()
        if isinstance(content, list):
            parts = []
            for c in content:
                if isinstance(c, dict) and c.get("type") == "text":
                    parts.append(c.get("text", ""))
                elif isinstance(c, str):
                    parts.append(c)
            return "\n".join(parts).strip()
        return ""

    def _parse_ts(self, ts_str) -> int:
        """支持 unix ms / ISO string"""
        if not ts_str:
            return 0
        if isinstance(ts_str, (int, float)):
            return int(ts_str)
        # ISO 字符串
        try:
            from datetime import datetime
            dt = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
            return int(dt.timestamp() * 1000)
        except Exception:
            return 0

    def extract_prompts(self, project_id: str) -> List[Prompt]:
        jsonl = Path(project_id)
        if not jsonl.exists():
            raise FileNotFoundError(f"Claude Code jsonl not found: {jsonl}")
        info = self._read_meta(jsonl)
        label = info.label if info else jsonl.parent.name

        prompts = []
        with open(jsonl, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    obj = json.loads(line)
                except Exception:
                    continue
                if obj.get("type") != "user":
                    continue
                msg = obj.get("message", {})
                content = msg.get("content", "")
                text = self._extract_text(content)
                if not text or text.startswith("/"):
                    continue
                ts = self._parse_ts(obj.get("timestamp") or msg.get("timestamp"))
                if not ts:
                    continue
                prompts.append(Prompt(
                    text=text,
                    timestamp=ts,
                    project_id=str(jsonl),
                    project_label=label,
                    source=self.name,
                ))
        return prompts
