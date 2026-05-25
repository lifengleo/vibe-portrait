"""
WorkBuddy adapter

数据格式：~/.workbuddy/projects/<dir>/<id>.jsonl + .meta.json
每条 user message 的 content[0].text 可能被 <system-reminder>...</system-reminder><user_query>...</user_query> 包装。
"""
import json
import re
import os
from pathlib import Path
from typing import Optional, List, Tuple
from .base import BaseAdapter, Prompt, ProjectInfo

ROOT = Path.home() / ".workbuddy" / "projects"

# 提取 <user_query>...</user_query> 内的真实输入
USER_QUERY_RE = re.compile(r"<user_query>(.*?)</user_query>", re.DOTALL)
# 老格式：<system-reminder>...</system-reminder> 后面是真实输入
SYSTEM_REMINDER_RE = re.compile(r"<system-reminder[^>]*>.*?</system-reminder>", re.DOTALL)


def _strip_wrapper(text: str) -> str:
    """剥离 system-reminder + user_query 包装，返回真实用户输入"""
    if not text:
        return ""
    # 优先 <user_query>
    matches = USER_QUERY_RE.findall(text)
    if matches:
        return "\n".join(m.strip() for m in matches if m.strip())
    # 次选 strip system-reminder 留剩余
    stripped = SYSTEM_REMINDER_RE.sub("", text).strip()
    return stripped


def _is_skippable(text: str) -> bool:
    """跳过附件占位、slash 命令、空内容"""
    if not text:
        return True
    t = text.strip()
    if not t:
        return True
    # /compact /clear 等命令
    if t.startswith("/") and len(t.split()[0]) < 30 and " " not in t.split()[0]:
        return True
    # 图片附件占位
    if t.startswith("@image#") or t.startswith("<image_local_path"):
        return True
    if t.startswith("[Image from"):
        return True
    return False


class WorkBuddyAdapter(BaseAdapter):
    name = "workbuddy"
    display_name = "WorkBuddy"

    def detect(self) -> bool:
        return ROOT.exists() and ROOT.is_dir()

    def _find_jsonl_files(self) -> List[Tuple[Path, Optional[Path]]]:
        """返回 (jsonl_file, meta_file) 列表"""
        if not self.detect():
            return []
        results = []
        for project_dir in ROOT.iterdir():
            if not project_dir.is_dir():
                continue
            for jsonl in project_dir.glob("*.jsonl"):
                meta = jsonl.with_suffix(".meta.json")
                results.append((jsonl, meta if meta.exists() else None))
        return results

    def list_projects(self) -> List[ProjectInfo]:
        out = []
        for jsonl, meta in self._find_jsonl_files():
            try:
                info = self._read_meta(jsonl, meta)
                if info:
                    out.append(info)
            except Exception as e:
                print(f"[warn] failed to read {jsonl}: {e}")
        return out

    def _read_meta(self, jsonl: Path, meta: Optional[Path]) -> Optional[ProjectInfo]:
        """从 jsonl 抽取项目级元信息（不展开全文）"""
        first_at = 0
        last_at = 0
        prompt_count = 0
        first_preview = ""
        label_from_first = ""

        with open(jsonl, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    obj = json.loads(line)
                except Exception:
                    continue
                if obj.get("type") != "message" or obj.get("role") != "user":
                    continue
                ts = obj.get("timestamp", 0)
                if not ts:
                    continue
                content = obj.get("content", [])
                texts = []
                if isinstance(content, list):
                    for c in content:
                        if isinstance(c, dict) and c.get("type") == "input_text":
                            texts.append(c.get("text", ""))
                raw = "\n".join(texts)
                stripped = _strip_wrapper(raw)
                if _is_skippable(stripped):
                    continue
                prompt_count += 1
                if first_at == 0:
                    first_at = ts
                    first_preview = stripped[:30].replace("\n", " ")
                    # 从第一句话提取一个粗略的项目主题
                    label_from_first = stripped[:20].replace("\n", " ")
                last_at = max(last_at, ts)

        if prompt_count == 0:
            return None

        # 项目标签：用目录名末尾段
        dir_name = jsonl.parent.name
        # 把 "Users-fengli-WorkBuddy-20260402153431" 简化成最后的时间戳/任务名
        parts = dir_name.split("-")
        label = parts[-1] if parts else dir_name
        # 如果最后一段是纯数字时间戳，用第一句话补充语义
        if label.isdigit() and label_from_first:
            label = f"{label_from_first}…"

        return ProjectInfo(
            source=self.name,
            source_display=self.display_name,
            project_id=str(jsonl),  # 用绝对路径作为 ID（最可靠）
            label=label,
            prompt_count=prompt_count,
            first_prompt_preview=first_preview,
            first_at=first_at,
            last_updated=last_at,
        )

    def extract_prompts(self, project_id: str) -> List[Prompt]:
        jsonl = Path(project_id)
        if not jsonl.exists():
            raise FileNotFoundError(f"WorkBuddy jsonl not found: {jsonl}")

        # 项目标签同 list_projects
        info = self._read_meta(jsonl, None)
        label = info.label if info else jsonl.parent.name

        prompts = []
        with open(jsonl, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    obj = json.loads(line)
                except Exception:
                    continue
                if obj.get("type") != "message" or obj.get("role") != "user":
                    continue
                ts = obj.get("timestamp", 0)
                if not ts:
                    continue  # 没有时间戳的条目跳过
                content = obj.get("content", [])
                texts = []
                if isinstance(content, list):
                    for c in content:
                        if isinstance(c, dict) and c.get("type") == "input_text":
                            texts.append(c.get("text", ""))
                raw = "\n".join(texts)
                stripped = _strip_wrapper(raw)
                if _is_skippable(stripped):
                    continue
                prompts.append(Prompt(
                    text=stripped,
                    timestamp=ts,
                    project_id=str(jsonl),
                    project_label=label,
                    source=self.name,
                ))
        return prompts
