"""
Codex CLI adapter

数据格式（2026 实测）：
  ~/.codex/sessions/YYYY/MM/DD/rollout-<ts>-<uuid>.jsonl

每行 JSON 结构：
  {
    "timestamp": "2026-04-02T06:58:09.890Z",
    "type": "response_item",
    "payload": {
      "type": "message",
      "role": "user",
      "content": [{"type": "input_text", "text": "..."}]
    }
  }

session_meta 行（每个文件第一行）含 cwd，可用于聚合"同一个工作目录"为一个项目。
"""
import json
import hashlib
from pathlib import Path
from typing import Optional, List, Dict
from .base import BaseAdapter, Prompt, ProjectInfo

ROOT = Path.home() / ".codex" / "sessions"


class CodexAdapter(BaseAdapter):
    name = "codex"
    display_name = "Codex"

    def detect(self) -> bool:
        return ROOT.exists() and ROOT.is_dir()

    def list_projects(self) -> List[ProjectInfo]:
        """把所有 jsonl 按 cwd 聚合成项目，每个项目一行展示。"""
        if not self.detect():
            return []

        # 按 cwd 聚合，cwd 缺失则按 jsonl 自身分组
        groups: Dict[str, List[Path]] = {}
        for jsonl in ROOT.rglob("*.jsonl"):
            cwd = self._read_session_cwd(jsonl)
            key = cwd or f"_single::{jsonl}"
            groups.setdefault(key, []).append(jsonl)

        out = []
        for key, files in groups.items():
            try:
                info = self._build_project_info(key, files)
                if info:
                    out.append(info)
            except Exception as e:
                print(f"[warn] codex group failed {key}: {e}")

        # 按 prompt 数量降序，最厚实的排前面
        out.sort(key=lambda p: -p.prompt_count)
        return out

    def _read_session_cwd(self, jsonl: Path) -> Optional[str]:
        """读 session_meta 行（通常是第一行）拿 cwd。"""
        try:
            with open(jsonl, "r", encoding="utf-8") as f:
                for i, line in enumerate(f):
                    if i > 5:  # session_meta 一定在前几行
                        break
                    try:
                        obj = json.loads(line)
                    except Exception:
                        continue
                    if obj.get("type") == "session_meta":
                        payload = obj.get("payload") or {}
                        return payload.get("cwd")
        except Exception:
            pass
        return None

    def _build_project_info(self, key: str, files: List[Path]) -> Optional[ProjectInfo]:
        first_at = 0
        last_at = 0
        prompt_count = 0
        first_preview = ""

        for jsonl in files:
            for text, ts in self._iter_user_prompts(jsonl):
                prompt_count += 1
                if first_at == 0 or (ts and ts < first_at):
                    first_at = ts
                    if not first_preview:
                        first_preview = text[:30].replace("\n", " ")
                if ts and ts > last_at:
                    last_at = ts

        if prompt_count == 0:
            return None

        # label：cwd 路径的最后两段；多文件时拼一下文件数
        if key.startswith("_single::"):
            jsonl = files[0]
            label = f"{jsonl.parent.name}/{jsonl.stem[:24]}"
            project_id = str(jsonl)
        else:
            cwd = key
            parts = cwd.rstrip("/").split("/")
            short = "/".join(parts[-2:]) if len(parts) >= 2 else cwd
            label = short
            if len(files) > 1:
                label = f"{short} ({len(files)} 段)"
            # project_id 把所有 jsonl 路径用 ; 串起来，extract_prompts 时按 ; 切分
            project_id = ";".join(str(f) for f in sorted(files))

        return ProjectInfo(
            source=self.name,
            source_display=self.display_name,
            project_id=project_id,
            label=label,
            prompt_count=prompt_count,
            first_prompt_preview=first_preview,
            first_at=first_at,
            last_updated=last_at,
        )

    def _iter_user_prompts(self, jsonl: Path):
        """遍历一个 jsonl，yield (text, ts_ms) 表示每条用户 prompt。"""
        try:
            with open(jsonl, "r", encoding="utf-8") as f:
                for line in f:
                    try:
                        obj = json.loads(line)
                    except Exception:
                        continue
                    # 顶层格式：{timestamp, type, payload}
                    if obj.get("type") != "response_item":
                        continue
                    payload = obj.get("payload") or {}
                    if not isinstance(payload, dict):
                        continue
                    if payload.get("type") != "message":
                        continue
                    if payload.get("role") != "user":
                        continue
                    text = self._extract_text(payload.get("content"))
                    if not text:
                        continue
                    # 跳过 slash 命令和 codex 内部转发的 environment_context 之类
                    if text.startswith("/"):
                        continue
                    if text.startswith("<environment_context>") or text.startswith("<user_instructions>"):
                        continue
                    ts = self._parse_ts(obj.get("timestamp"))
                    yield text, ts
        except Exception as e:
            print(f"[warn] codex parse {jsonl}: {e}")

    def _extract_text(self, content) -> str:
        """payload.content 可能是 list[{type,text}] 或 str。"""
        if isinstance(content, list):
            parts = []
            for c in content:
                if isinstance(c, dict):
                    t = c.get("text") or c.get("content") or ""
                    if t:
                        parts.append(t)
                elif isinstance(c, str):
                    parts.append(c)
            return "\n".join(parts).strip()
        if isinstance(content, str):
            return content.strip()
        return ""

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
        # project_id 可能是单个 jsonl 路径，也可能是 ";" 分隔的多个 jsonl 路径
        files = [Path(p) for p in project_id.split(";") if p]
        prompts = []
        for jsonl in files:
            if not jsonl.exists():
                print(f"[warn] codex jsonl not found: {jsonl}")
                continue
            label = f"{jsonl.parent.name}/{jsonl.stem[:24]}"
            for text, ts in self._iter_user_prompts(jsonl):
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
