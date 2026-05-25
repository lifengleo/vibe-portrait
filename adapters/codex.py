"""
Codex CLI adapter

数据格式：~/.codex/sessions/<date>/*.jsonl

注意：Codex 格式仍在演进，实现是 best-effort，需要用真实数据校验。
如果检测到目录但解析失败，会跳过该项目并打 warning。
"""
import json
from pathlib import Path
from typing import Optional, List
from .base import BaseAdapter, Prompt, ProjectInfo

ROOT = Path.home() / ".codex" / "sessions"


class CodexAdapter(BaseAdapter):
    name = "codex"
    display_name = "Codex"

    def detect(self) -> bool:
        return ROOT.exists() and ROOT.is_dir()

    def list_projects(self) -> List[ProjectInfo]:
        if not self.detect():
            return []
        out = []
        for date_dir in ROOT.iterdir():
            if not date_dir.is_dir():
                continue
            for jsonl in date_dir.glob("*.jsonl"):
                try:
                    info = self._read_meta(jsonl)
                    if info:
                        out.append(info)
                except Exception as e:
                    print(f"[warn] codex failed: {jsonl}: {e}")
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
                # Codex 格式：role=user 的消息
                role = obj.get("role") or obj.get("type")
                if role != "user":
                    continue
                content = obj.get("content") or obj.get("text") or ""
                text = content if isinstance(content, str) else self._extract_text(content)
                if not text or text.startswith("/"):
                    continue
                ts = self._parse_ts(obj.get("timestamp") or obj.get("created_at"))
                if not ts:
                    continue
                prompt_count += 1
                if first_at == 0:
                    first_at = ts
                    first_preview = text[:30].replace("\n", " ")
                last_at = max(last_at, ts)

        if prompt_count == 0:
            return None

        # Codex session 名通常是日期 + 短 hash
        label = f"{jsonl.parent.name}/{jsonl.stem}"
        return ProjectInfo(
            source=self.name,
            source_display=self.display_name,
            project_id=str(jsonl),
            label=label,
            prompt_count=prompt_count,
            first_prompt_preview=first_preview,
            first_at=first_at,
            last_updated=last_at,
        )

    def _extract_text(self, content) -> str:
        if isinstance(content, list):
            parts = []
            for c in content:
                if isinstance(c, dict):
                    parts.append(c.get("text", "") or c.get("content", ""))
                elif isinstance(c, str):
                    parts.append(c)
            return "\n".join(parts).strip()
        return str(content)

    def _parse_ts(self, ts_str) -> int:
        if not ts_str:
            return 0
        if isinstance(ts_str, (int, float)):
            return int(ts_str * 1000) if ts_str < 1e12 else int(ts_str)
        try:
            from datetime import datetime
            dt = datetime.fromisoformat(str(ts_str).replace("Z", "+00:00"))
            return int(dt.timestamp() * 1000)
        except Exception:
            return 0

    def extract_prompts(self, project_id: str) -> List[Prompt]:
        jsonl = Path(project_id)
        if not jsonl.exists():
            raise FileNotFoundError(f"Codex jsonl not found: {jsonl}")
        info = self._read_meta(jsonl)
        label = info.label if info else jsonl.stem

        prompts = []
        with open(jsonl, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    obj = json.loads(line)
                except Exception:
                    continue
                role = obj.get("role") or obj.get("type")
                if role != "user":
                    continue
                content = obj.get("content") or obj.get("text") or ""
                text = content if isinstance(content, str) else self._extract_text(content)
                if not text or text.startswith("/"):
                    continue
                ts = self._parse_ts(obj.get("timestamp") or obj.get("created_at"))
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
