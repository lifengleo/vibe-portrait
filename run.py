#!/usr/bin/env python3
"""
Vibe 自画像 · 主入口（两阶段 pipeline）

工作流：
  阶段 1（analyze）：python3 run.py [选项] → 产出 data.json（含 LLM 待填字段）
  阶段 2（LLM 增强）：调起本 skill 的 agent 读 data.json，补齐 ctx/tag/alias 等字段
  阶段 3（finalize）：python3 run.py --finalize <data.json> → 渲染 HTML + 截图

用法：
  python3 run.py                              # 交互式 analyze
  python3 run.py --list                       # 只列项目
  python3 run.py --user 恩瑞 --multi 1,3       # 直接 analyze
  python3 run.py --finalize ./data.json       # 渲染（agent 增强后调）
  python3 run.py --user 恩瑞 --skip-llm        # 跳过 LLM 增强直接渲染（兜底默认）
"""
import argparse
import json
import sys
import io
import shutil
import subprocess
from pathlib import Path
from datetime import datetime

# === [Issue #1 P0] 强制 stdout/stderr 为 UTF-8 ===
# 某些终端环境（macOS Terminal、宿主 agent 透传 PIPE 等）默认 encoding 不是 utf-8，
# 会把所有中文输出渲染成 ��� 乱码。新用户根本看不懂窗口列表和「匹配作家」行。
# 文件 IO 不受影响，只修复 stdout/stderr。
def _force_utf8_io():
    for name in ("stdout", "stderr"):
        stream = getattr(sys, name, None)
        if stream is None:
            continue
        enc = (getattr(stream, "encoding", "") or "").lower()
        if enc and "utf-8" not in enc and "utf8" not in enc:
            try:
                buf = stream.buffer
                setattr(sys, name, io.TextIOWrapper(buf, encoding="utf-8", line_buffering=True))
            except Exception:
                pass

_force_utf8_io()

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))

from adapters import detect_all, list_all_projects, get_adapter_by_name, detect_host_agent  # noqa
from core.analyze import analyze  # noqa
from core.render import render  # noqa


CONFIG_PATH = Path.home() / ".vibe-portrait" / "config.json"


def load_config() -> dict:
    if CONFIG_PATH.exists():
        return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    return {}


def save_config(cfg: dict):
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")


def prompt_user_name() -> str:
    cfg = load_config()
    if cfg.get("user_name"):
        return cfg["user_name"]
    print("\n首次启动，需要先记一下你的昵称。这个名字会出现在海报封面上。")
    name = input("▸ 怎么称呼你？ ").strip()
    if not name:
        print("昵称不能为空，退出。")
        sys.exit(1)
    cfg["user_name"] = name
    save_config(cfg)
    print(f"✓ 已记住，下次启动不再询问。配置文件：{CONFIG_PATH}\n")
    return name


def list_projects_with_index(only_sources=None):
    projects = list_all_projects(only_sources=only_sources)
    if not projects:
        print("\n没检测到任何 agent 历史。")
        if only_sources:
            print(f"已限定只扫: {', '.join(only_sources)}")
            print("如需跨 agent 扫描，请加 --include 参数（如 --include workbuddy,claude,codex）")
        else:
            print("请确认下列目录是否存在：")
            print("  ~/.workbuddy/projects/")
            print("  ~/.claude/projects/")
            print("  ~/.codex/sessions/")
        sys.exit(1)
    sources_set = sorted({p.source for p in projects})
    print(f"\n▸ 检测到 {len(projects)} 个对话窗口（来源: {', '.join(sources_set)}）：\n")
    for i, p in enumerate(projects, 1):
        print("  " + p.render_line(i))
    return projects


def parse_selection(s: str, total: int):
    s = s.strip()
    if not s:
        return list(range(1, total + 1))
    out = set()
    for part in s.split(","):
        part = part.strip()
        if "-" in part:
            a, b = part.split("-")
            out.update(range(int(a), int(b) + 1))
        elif part:
            out.add(int(part))
    return sorted([i for i in out if 1 <= i <= total])


def select_projects(projects):
    print()
    sel = input("▸ 选哪几个？（输入编号，逗号分隔，回车默认全选） ").strip()
    indices = parse_selection(sel, len(projects))
    if not indices:
        print("没选任何项目，退出。")
        sys.exit(1)
    return [projects[i - 1] for i in indices]


def collect_prompts(projects):
    all_prompts = []
    for p in projects:
        adapter = get_adapter_by_name(p.source)
        try:
            prompts = adapter.extract_prompts(p.project_id)
            print(f"  ✓ {p.label}: 抽出 {len(prompts)} 条")
            all_prompts.extend(prompts)
        except Exception as e:
            print(f"  ✗ {p.label}: 失败 — {e}")
    return all_prompts


def write_data_json(analysis: dict, out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    # 把肖像复制过去
    assets_src = HERE / "assets"
    assets_dst = out_dir / "assets"
    if assets_dst.exists():
        shutil.rmtree(assets_dst)
    shutil.copytree(assets_src, assets_dst)
    # 写 data.json（包含 LLM 待填字段）
    data_path = out_dir / "data.json"
    # 把 matched_author 里的 distance（float）转可序列化
    safe = json.loads(json.dumps(analysis, ensure_ascii=False, default=str))
    data_path.write_text(json.dumps(safe, ensure_ascii=False, indent=2), encoding="utf-8")
    return data_path


def render_and_screenshot(analysis: dict, out_dir: Path, do_screenshot=True):
    # 把项目别名应用到 quotes 等字段（LLM 阶段如果填了 project_aliases，这里取出）
    aliases = {pa["project_id"]: (pa.get("alias") or pa.get("alias_default"))
               for pa in analysis.get("project_aliases", [])}
    for q in analysis.get("quotes", []):
        if q.get("project_label") in aliases.values():
            continue  # 已经是别名
        # 用 project_id 找别名（如果 quote 里有的话；当前结构没有，先用 label 兜）
    html = render(analysis)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "index.html").write_text(html, encoding="utf-8")
    print(f"  ✓ {out_dir}/index.html")

    if do_screenshot:
        print("\n▸ 截图...")
        screenshot(out_dir)
        for f in ("portrait-share.jpg", "portrait-hd.jpg"):
            p = out_dir / f
            if p.exists():
                size = p.stat().st_size / 1024
                print(f"  ✓ {f} ({size:.0f}KB)")


def screenshot(out_dir: Path):
    script = HERE / "scripts" / "screenshot.cjs"
    if not script.exists():
        print(f"⚠️  截图脚本不存在: {script}（跳过）")
        return
    import os
    env = {"VIBE_HTML": str(out_dir / "index.html"),
           "VIBE_OUT": str(out_dir)}
    env.update({k: v for k, v in os.environ.items() if k not in env})

    # 优先用 VIBE_NODE 环境变量，再用 PATH 里的 node，最后兜底常见安装路径
    node = os.environ.get("VIBE_NODE") or shutil.which("node")
    if not node:
        for cand in [
            Path.home() / ".workbuddy/binaries/node/versions/20.18.0/bin/node",
            Path("/usr/local/bin/node"),
            Path("/opt/homebrew/bin/node"),
        ]:
            if cand.exists():
                node = str(cand)
                break
    if not node:
        print("⚠️  没找到 node 可执行文件——请装 Node.js，或设置 VIBE_NODE 环境变量")
        return

    # NODE_PATH（找 playwright/sharp 用）— 优先 skill 本地 node_modules
    node_modules_candidates = [
        os.environ.get("NODE_PATH"),
        str(HERE / "node_modules"),
        str(Path.home() / ".workbuddy/binaries/node/workspace/node_modules"),
    ]
    node_path = next((p for p in node_modules_candidates if p and Path(p).exists()), None)
    if node_path:
        env["NODE_PATH"] = node_path

    try:
        subprocess.run([node, str(script)], cwd=str(HERE), env=env, check=True)
    except subprocess.CalledProcessError as e:
        print(f"⚠️  截图失败: {e}（确认装了 playwright + sharp）")


def _resolve_include(include_arg, host_agent):
    """解析 --include 参数，返回 only_sources 列表（None 表示不限制）。

    默认行为（include_arg=None）：
      - 如果识别出宿主 agent → 只扫宿主，返回 [host_agent]
      - 如果识别不出宿主（罕见） → 返回 None，扫所有

    显式：
      - --include all → 返回 None
      - --include workbuddy,claude → 返回 ['workbuddy','claude']
    """
    if include_arg is None:
        if host_agent:
            return [host_agent]
        return None  # 没识别出宿主，不限制
    if include_arg.strip().lower() == "all":
        return None
    parts = [p.strip() for p in include_arg.split(",") if p.strip()]
    return parts if parts else None


def _resolve_finalize_path(arg_value):
    """解析 --finalize 参数。

    传 '__AUTO__' 表示用户没传具体路径 → 自动找最新一份 data.json。
    传具体路径 → 直接用。
    """
    if arg_value == "__AUTO__":
        # 优先在 ./vibe-portrait/<日期>/ 下找最新
        candidates = []
        for base in [Path("./vibe-portrait"), HERE / "vibe-portrait"]:
            if base.exists():
                for d in sorted(base.iterdir(), reverse=True):
                    f = d / "data.json"
                    if f.exists():
                        candidates.append(f)
        if not candidates:
            print("没找到任何 data.json。")
            print("先跑一次 `python3 run.py` 生成数据，再用 --finalize。")
            return None
        path = candidates[0]
        print(f"▸ 自动定位到最新 data.json: {path}")
        return path

    p = Path(arg_value)
    if not p.exists():
        print(f"data.json 不存在: {p}")
        return None
    return p


def main():
    ap = argparse.ArgumentParser(description="Vibe 自画像生成器（两阶段）")
    ap.add_argument("--user", help="昵称（不传则从配置/交互获取）")
    ap.add_argument("--list", action="store_true", help="只列项目")
    ap.add_argument("--multi", help="逗号分隔的项目编号")
    ap.add_argument("--project", help="直接指定 jsonl 路径")
    ap.add_argument("--source", help="adapter 名称")
    ap.add_argument("--out", help="输出目录")
    ap.add_argument("--no-screenshot", action="store_true", help="跳过截图")
    ap.add_argument("--finalize", nargs="?", const="__AUTO__",
                    help="读取 enriched data.json 并直接渲染 + 截图。"
                         "不传路径时自动找最新一份 vibe-portrait/<日期>/data.json")
    ap.add_argument("--skip-llm", action="store_true",
                    help="不等 LLM 增强，直接用兜底默认渲染")
    ap.add_argument("--include", default=None,
                    help="扫描哪些 agent 的对话历史，逗号分隔（如 workbuddy,claude,codex）。"
                         "默认只扫脚本所在的宿主 agent，避免越权读取其他 agent 数据。"
                         "传 'all' 等价于显式扫描所有 agent。")
    args = ap.parse_args()

    # ===== Finalize 模式 =====
    if args.finalize:
        data_path = _resolve_finalize_path(args.finalize)
        if data_path is None:
            sys.exit(1)
        out_dir = data_path.parent
        analysis = json.loads(data_path.read_text(encoding="utf-8"))
        # axes 字段 in JSON 是 list，需要转回 tuple；其他都是 dict/list ok
        if isinstance(analysis.get("axes"), list):
            analysis["axes"] = tuple(analysis["axes"])
        print(f"▸ Finalize 模式：从 {data_path} 渲染")
        render_and_screenshot(analysis, out_dir, do_screenshot=not args.no_screenshot)
        print(f"\n完成。产物在 {out_dir}/")
        return

    print("Vibe 自画像 · 启动\n")

    # ===== 解析 --include 与宿主 agent =====
    host = detect_host_agent()
    only_sources = _resolve_include(args.include, host)
    if only_sources is None:
        # 显式 all
        print("▸ 跨 agent 扫描已开启：将读取 workbuddy / claude / codex 全部对话历史")
        print("  (这是 opt-in 行为；若只想扫宿主 agent，请去掉 --include all)\n")
    else:
        # 默认只扫宿主
        print(f"▸ 只扫描 [{', '.join(only_sources)}] 的对话历史"
              + ("（脚本所在宿主 agent）" if host and only_sources == [host] else "")
              + "\n  (跨 agent 扫描请加 --include all)\n")

    # ===== --list 模式：纯查询，不需要昵称 =====
    if args.list:
        list_projects_with_index(only_sources=only_sources)
        return

    # ===== --project 模式：直接指定 jsonl，跳过项目检测 =====
    if args.project:
        # 昵称
        if args.user:
            cfg = load_config()
            cfg["user_name"] = args.user
            save_config(cfg)
            user_name = args.user
        else:
            user_name = prompt_user_name()

        adapter_name = args.source or "workbuddy"
        adapter = get_adapter_by_name(adapter_name)
        from adapters.base import ProjectInfo
        pi = ProjectInfo(source=adapter_name, source_display=adapter.display_name,
                         project_id=args.project, label=Path(args.project).stem,
                         prompt_count=0, first_prompt_preview="",
                         first_at=0, last_updated=0)
        chosen = [pi]
    else:
        # 1. 昵称
        if args.user:
            cfg = load_config()
            cfg["user_name"] = args.user
            save_config(cfg)
            user_name = args.user
        else:
            user_name = prompt_user_name()

        # 2. 列项目
        projects = list_projects_with_index(only_sources=only_sources)

        # 3. 选项目
        if args.multi:
            indices = parse_selection(args.multi, len(projects))
            chosen = [projects[i - 1] for i in indices]
        else:
            chosen = select_projects(projects)

    print(f"\n▸ 选中 {len(chosen)} 个项目，开始抽取 prompt...")
    prompts = collect_prompts(chosen)
    if not prompts:
        print("\n没抽到任何 prompt，退出。")
        sys.exit(1)

    # 4. 分析
    print(f"\n▸ 共 {len(prompts)} 条 prompt，开始分析...")
    print("  [1/3] 计算三轴 + 匹配作家 + 抽取口癖 + 筛选金句 + 计算徽章...")
    analysis = analyze(prompts, user_name)
    print(f"  [2/3] ✓ 三轴: length={analysis['axes'][0]:.2f} calm={analysis['axes'][1]:.2f} architect={analysis['axes'][2]:.2f}")
    print(f"        ✓ 匹配作家: {analysis['matched_author']['name_zh']}")
    print(f"        ✓ 触发章节: {[ch['id'] for ch in analysis['chapters']]}")
    print(f"  [3/3] 拼装 data.json...")

    # 5. 输出 data.json
    out_dir = Path(args.out) if args.out else Path("./vibe-portrait") / datetime.now().strftime("%Y-%m-%d")
    out_dir = out_dir.resolve()
    data_path = write_data_json(analysis, out_dir)
    print(f"\n▸ 数据已写入 {data_path}")

    if args.skip_llm:
        # 直接渲染，用兜底
        print("\n▸ --skip-llm，直接用兜底默认渲染")
        render_and_screenshot(analysis, out_dir, do_screenshot=not args.no_screenshot)
        print(f"\n完成。产物在 {out_dir}/")
        return

    # 6. 提示 LLM 增强
    print("\n" + "=" * 60)
    print("▸ 下一步：LLM 增强（agent 任务）")
    print("=" * 60)
    print("\nagent 现在应该读取以下文件：")
    print(f"  {data_path}")
    print("\n执行 _llm_tasks 里描述的 5 个任务：")
    for i, t in enumerate(analysis["_llm_tasks"]["tasks"], 1):
        print(f"  {i}. {t['id']}: {t['instruction'][:50]}…")
    print(f"\n增强完成后，把修改后的 data.json 保存到原位置，然后调用：")
    print(f"  python3 {Path(__file__).resolve()} --finalize {data_path}")
    print("\n（或加 --skip-llm 直接用兜底默认渲染）\n")


if __name__ == "__main__":
    main()
