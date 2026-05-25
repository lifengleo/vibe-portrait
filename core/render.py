"""
Render 渲染层

把 analyze() 产出的 dict 渲染成 HTML 字符串。
每番一个独立函数，按 chapters 列表里的触发结果拼起来。
"""
import html as html_lib
from pathlib import Path
from typing import Dict, Any, List

TEMPLATE_DIR = Path(__file__).parent.parent / "template"
HEAD = (TEMPLATE_DIR / "head.html").read_text(encoding="utf-8")
TAIL = (TEMPLATE_DIR / "tail.html").read_text(encoding="utf-8")

WEEKDAY_ORDER = ["五", "四", "二", "日", "一", "六", "三"]  # 占位，实际按数据排
WEEKDAY_FULL_ZH = ["一", "二", "三", "四", "五", "六", "日"]


def _esc(s) -> str:
    """HTML 转义"""
    return html_lib.escape(str(s))


def _author_portrait_path(slug: str) -> str:
    """肖像相对路径（部署时 assets/ 文件夹会和 index.html 同级）"""
    return f"assets/portraits/{slug}.jpg"


# ============================================================
# Header（封面）
# ============================================================

def render_head(a: Dict[str, Any]) -> str:
    user_name = _esc(a["user_name"])
    total_chars = f"{a['stats']['total_chars']:,}"
    span_days = a['stats']['span_days']
    author = a["matched_author"]
    portrait_path = _author_portrait_path(author["slug"])

    # author_followup：LLM 增强 → 兜底
    followup = a.get("author_followup") or a.get("author_followup_default") or "你呢 😅"

    return f"""
  <header class="head">
    <div class="portrait">
      <img src="{portrait_path}" alt="{_esc(author['name_en'])}">
    </div>
    <div class="portrait-cap">
      <b>{_esc(author['name_en'])}</b>
      {_esc(author['tagline'])}<br>
      {_esc(followup)}
    </div>
    <h1>Vibe 自画像</h1>
    <div class="h1-en">A portrait of how you vibe.</div>

    <p class="lede">
      这是 <em>{user_name}</em> 的 Vibe 自画像。<br>
      没什么深刻洞察，<br>
      就是把你这阵子说的话拉出来，跟你对个账。<br>
      <span style="color:var(--muted);font-size:0.85em;">总共 <em>{total_chars} 个字</em>，耗时 <em>{span_days} 天</em>。</span>
    </p>
  </header>
"""


# ============================================================
# 番 1: 数据墙（永远必出）
# ============================================================

def render_stats(a: Dict[str, Any], num: str) -> str:
    s = a["stats"]
    prompts = f"{s['prompts']:,}"
    total_chars = f"{s['total_chars']:,}"
    a4_pages = max(1, s['total_chars'] // 500)
    active_days = s['active_days']
    span_days = s['span_days']
    peak_count = s['peak_count']
    peak_day = s['peak_day'][5:].replace("-", ".")  # 04-03 → 04.03
    mean_len = s['mean_len']

    return f"""
  <section class="ch">
    <div class="ch-num">Vibe 自画像 · 第 {num} 番</div>
    <h2 class="ch-title">先瞧瞧你这张嘴</h2>
    <p class="ch-sub">先把账算清楚。</p>

    <div class="stat-grid">
      <div class="stat">
        <div class="label">Prompt 总数</div>
        <div class="num">{prompts}<small>条</small></div>
      </div>
      <div class="stat">
        <div class="label">总字数</div>
        <div class="num">{total_chars}<small>字</small></div>
        <div class="desc">打印出来 {a4_pages} 张 A4，<br>能糊一面墙。</div>
      </div>
      <div class="stat">
        <div class="label">活跃天数</div>
        <div class="num">{active_days}<small>/ {span_days}</small></div>
        <div class="desc">{span_days} 天里 {active_days} 天没放过它，<br>剩下那几天估计在睡。</div>
      </div>
      <div class="stat">
        <div class="label">单日峰值</div>
        <div class="num">{peak_count}<small>条</small></div>
        <div class="desc">{peak_day} 这天 vibe 了 {peak_count} 次，<br>键盘没冒烟算它命大。</div>
      </div>
    </div>

    <div class="hero-num">
      <div class="label">平均每条长度</div>
      <div class="number">{mean_len}<span class="unit">字</span></div>
      <div class="ann">
        日常一句话，偶尔写小作文。
      </div>
    </div>
  </section>
"""


# ============================================================
# 番 2: vibe 生物钟
# ============================================================

def render_clock(a: Dict[str, Any], num: str) -> str:
    s = a["stats"]
    night_count = a["night_count"]
    weekday_dist = a["weekday_dist_zh"]
    weekday_max = a["weekday_max_zh"]
    weekday_max_ratio = a["weekday_max_ratio"]
    weekday_max_count = a["weekday_max_count"]

    night_line = (
        f'你不是夜猫子。<em>从零点到清晨六点，{night_count} 条。</em>'
        f'<span class="ann">不是不卷，是 Mac 也得睡。</span>'
        if night_count == 0
        else
        f'你就是夜猫子本人。<em>从零点到清晨六点，{night_count} 条。</em>'
        f'<span class="ann">Mac 比你先困。</span>'
    )

    # weekday bars
    sorted_weekday = sorted(weekday_dist.items(), key=lambda x: -x[1])
    if sorted_weekday:
        max_count = sorted_weekday[0][1]
        bars = []
        for day_zh, count in sorted_weekday:
            ratio = count / max_count
            cls = "row king" if day_zh == sorted_weekday[0][0] else "row"
            bars.append(f"""
      <div class="{cls}">
        <span class="day">周 {day_zh}</span>
        <span class="bar" style="width:{ratio*100:.1f}%"></span>
        <span class="val">{count}</span>
      </div>""")
        bars_html = "".join(bars)
    else:
        bars_html = ""

    # 周分布陈述
    least_day = sorted_weekday[-1] if sorted_weekday else ("一", 0)
    weekday_pct = int(weekday_max_ratio * 100)
    statement = (
        f'你是 <em>「周{weekday_max} 战神」</em>——<br>'
        f'{weekday_pct}% 的 vibe 都堆在周{weekday_max}。'
        f'<span class="ann">周{least_day[0]} 只 vibe 了 {least_day[1]} 条。剩下六天，是在给周{weekday_max} 攒怨气。</span>'
    )

    return f"""
  <div class="ornament">番 · {num}</div>

  <section class="ch">
    <div class="ch-num">Vibe 自画像 · 第 {num} 番</div>
    <h2 class="ch-title">你的 vibe 生物钟</h2>
    <p class="ch-sub">别装勤奋，数据看着呢。</p>

    <div class="heatmap" id="heatmap"></div>
    <div class="hours-axis" id="hours"></div>

    <div class="big-statement">
      {night_line}
    </div>

    <hr class="rule">

    <div class="weekday-bars">{bars_html}
    </div>

    <div class="big-statement" style="margin-top:36px;">
      {statement}
    </div>
  </section>
"""


# ============================================================
# 番 3: 翻来覆去就这几句
# ============================================================

def render_patterns(a: Dict[str, Any], num: str) -> str:
    medals = ["🥇", "🥈", "🥉"]
    rows = []
    for i, p in enumerate(a["top_patterns"]):
        rk = medals[i] if i < 3 else str(i + 1)
        examples = "、".join(f'"{ex}"' for ex in p.get("examples", [])[:3])
        small = f'<small>{examples}</small>' if examples else ""
        rows.append(f"""
      <div class="verbal-row">
        <span class="rk">{rk}</span>
        <span class="ph">{_esc(p['label'])}{small}</span>
        <span class="cnt"><b>{p['count']}</b>次</span>
      </div>""")

    praise_count = a.get("praise_count", 0)
    praise_line = (
        f'<p style="font-family:\'Noto Serif SC\',serif;font-style:italic;font-size:14.5px;'
        f'color:var(--muted);margin-top:18px;line-height:1.75;">'
        f'整页里「完美 / 非常准确」类夸赞词，'
        f'<b style="color:var(--red);font-style:normal;font-weight:700;">{praise_count} 次</b>。AI 没你想的那么烂，是你嘴硬。</p>'
    )

    return f"""
  <div class="ornament">番 · {num}</div>

  <section class="ch">
    <div class="ch-num">Vibe 自画像 · 第 {num} 番</div>
    <h2 class="ch-title">翻来覆去就这几句</h2>
    <p class="ch-sub">你自己念一遍试试。</p>

    <div class="verbal-list">{"".join(rows)}
    </div>

    {praise_line}
  </section>
"""


# ============================================================
# 番 4: 你是这样欺负 AI 的（金句章）
# ============================================================

def render_quotes(a: Dict[str, Any], num: str) -> str:
    quotes = a["quotes"]
    cards = []
    for q in quotes:
        slot = q["slot"]
        text = _esc(q["text"]).replace("\n", "<br>")
        cls = "quote"
        if slot == "shortest" and len(q["text"]) <= 5:
            cls = "quote shortest"
        elif slot == "longest":
            cls = "quote"
        elif len(q["text"]) <= 30:
            cls = "quote short"

        # ctx 和 tag：LLM 增强 → 兜底
        ctx = q.get("ctx") or q.get("ctx_default") or ""
        tag = q.get("tag") or q.get("tag_default") or ""

        ctx_html = (
            f'<div class="ctx">{_esc(ctx)}</div>'
            if ctx else ""
        )

        cards.append(f"""
    <div class="{cls}">
      <div class="meta">
        <span class="when">{_esc(q['datetime'])}</span>
        <span class="tag">{_esc(tag)}</span>
      </div>
      <div class="text">{text}</div>
      {ctx_html}
    </div>""")

    return f"""
  <div class="ornament">番 · {num}</div>

  <section class="ch">
    <div class="ch-num">Vibe 自画像 · 第 {num} 番</div>
    <h2 class="ch-title">你是这样欺负 AI 的</h2>
    <p class="ch-sub">AI 没脾气，但有时间戳。</p>
{"".join(cards)}
  </section>
"""


# ============================================================
# 番 5: 给你的 vibe 颁几个奖（徽章）
# ============================================================

def render_badges(a: Dict[str, Any], num: str) -> str:
    badges = a["badges"]
    cards = []
    for i, b in enumerate(badges, 1):
        cards.append(f"""
      <div class="badge">
        <div class="id">第 {i} 号</div>
        <div class="nm">{_esc(b['name'])}</div>
        <div class="ev">{b['evidence']}</div>
      </div>""")

    summary = a.get("badges_summary", "")
    summary_html = (
        f'<p style="font-family:\'Noto Serif SC\',serif;font-style:italic;font-size:15px;'
        f'color:var(--ink-2);margin-top:36px;line-height:1.7;text-align:center;">'
        f'—— {_esc(summary)} ——</p>'
        if summary else ""
    )

    return f"""
  <div class="ornament">番 · {num}</div>

  <section class="ch">
    <div class="ch-num">Vibe 自画像 · 第 {num} 番</div>
    <h2 class="ch-title">给你的 vibe 颁几个奖</h2>
    <p class="ch-sub">认就完事了。</p>

    <div class="badges">{"".join(cards)}
    </div>
    {summary_html}
  </section>
"""


# ============================================================
# 终番: 字数是有了，文学是没有
# ============================================================

def render_outro(a: Dict[str, Any]) -> str:
    s = a["stats"]
    total_chars = f"{s['total_chars']:,}"
    author = a["matched_author"]
    book = author["book"]
    book_words = author["book_words"]
    author_zh = author["name_zh"]

    # 比例：用户字数 / 书的字数 — 用人文气词代替百分比
    ratio = s["total_chars"] / book_words
    book_name = book.strip("《》")
    if ratio < 0.15:
        compare_line = f"够给 <b>《{book_name}》写个开头</b>。"
    elif ratio < 0.35:
        compare_line = f"差不多是 <b>小半本《{book_name}》</b>。"
    elif ratio < 0.55:
        compare_line = f"差不多是 <b>半本《{book_name}》</b>。"
    elif ratio < 0.8:
        compare_line = f"差不多是 <b>大半本《{book_name}》</b>。"
    elif ratio <= 1.3:
        compare_line = f"差不多是 <b>整本《{book_name}》</b>的体量。"
    elif ratio <= 2.2:
        compare_line = f"够写 <b>一本半《{book_name}》</b>。"
    elif ratio <= 3.5:
        compare_line = f"够写 <b>两三本《{book_name}》</b>。"
    else:
        compare_line = f"够写 <b>{int(ratio)} 本《{book_name}》</b>了。"

    # 戏谑句：LLM 增强 → 兜底
    pun_html = a.get("outro_pun") or a.get("outro_pun_default") or ""

    return f"""
  <div class="ornament">番 · 终</div>

  <section class="ch">
    <div class="ch-num">Vibe 自画像 · 终番</div>
    <h2 class="ch-title">字数是有了，<br>文学是没有</h2>
    <p class="ch-sub">{author_zh}：你呢 😅</p>

    <div class="compare">
      <p class="big">
        你 vibe 出来的全部 Prompt 加起来 <b>{total_chars} 字</b>。<br>
        {compare_line}
      </p>
      <hr>
      <p class="pun">
        {pun_html}
      </p>
    </div>
  </section>
"""


# ============================================================
# 底款
# ============================================================

def render_footer(a: Dict[str, Any]) -> str:
    return f"""
  <footer class="colophon">
    <div class="left">
      <div class="title">Vibe 自画像 · {_esc(a['user_name'])}</div>
    </div>
  </footer>
"""


# ============================================================
# Hour data 注入（用于 24h 热力图 JS）
# ============================================================

def _inject_hour_data(a: Dict[str, Any]) -> str:
    """生成 hourData JS 对象，会替换 tail.html 里的 const hourData = {...}"""
    hd = a["hour_dist"]
    pairs = ", ".join(f"{h}: {c}" for h, c in sorted(hd.items()))
    max_v = max(hd.values()) if hd else 1
    return f"const hourData = {{ {pairs} }};\n  const max = {max_v};"


# ============================================================
# 主入口
# ============================================================

CHAPTER_RENDERERS = {
    "stats": render_stats,
    "clock": render_clock,
    "patterns": render_patterns,
    "quotes": render_quotes,
    "badges": render_badges,
}


def render(a: Dict[str, Any]) -> str:
    """主渲染函数：吃 analyze 产出，吐完整 HTML 字符串"""
    parts = [HEAD]
    parts.append(render_head(a))

    # 找最后一个普通章节的编号，给终番前的 ornament 用
    last_num = "1"
    last_ornament = ""

    for ch in a["chapters"]:
        cid = ch["id"]
        num = ch["display_num"]
        if cid == "outro":
            a["_last_ornament_num"] = last_num
            parts.append(render_outro(a))
        else:
            parts.append(CHAPTER_RENDERERS[cid](a, num))
            last_num = num

    parts.append(render_footer(a))

    # tail 里要替换掉硬编码的 hourData
    tail = TAIL
    import re
    new_hour = _inject_hour_data(a)
    tail = re.sub(
        r"const hourData = \{[^}]*\};\s*\n\s*const max = \d+;",
        new_hour,
        tail,
        count=1,
    )

    parts.append(tail)
    return "".join(parts)
