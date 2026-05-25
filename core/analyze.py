"""
Analyze 核心引擎

输入：list[Prompt]（来自 adapter）
输出：完整的 Analysis 字典（供 render 用）

实现 SPEC §3 / §6 / §7 / §8 的算法。
"""
import re
import math
import json
from datetime import datetime, timezone, timedelta
from collections import Counter
from pathlib import Path
from typing import List, Dict, Any

CN_TZ = timezone(timedelta(hours=8))
ASSETS = Path(__file__).parent.parent / "assets"
LEXICON = json.loads((ASSETS / "lexicon.json").read_text(encoding="utf-8"))
BADGES = json.loads((ASSETS / "badges.json").read_text(encoding="utf-8"))
AUTHORS = {
    k: v for k, v in
    json.loads((ASSETS / "portraits" / "_meta.json").read_text(encoding="utf-8")).items()
    if not k.startswith("_")
}

WEEKDAY_ZH = {"Monday": "一", "Tuesday": "二", "Wednesday": "三", "Thursday": "四",
              "Friday": "五", "Saturday": "六", "Sunday": "日"}


def _privacy_mask(text: str) -> str:
    """SPEC §13.1 隐私脱敏（默认开启）"""
    text = re.sub(r"1[3-9]\d{9}", "1XX****XXXX", text)
    text = re.sub(r"[\w._-]+@[\w.-]+", "XXX@XXX", text)
    text = re.sub(r"\d{17}[\dXx]", "XXX...XXX", text)
    return text


def _shrink_urls(text: str) -> str:
    """把超长 URL 缩成 域名+… 的样子，避免破窗"""
    def replacer(m):
        url = m.group(0)
        if len(url) <= 40:
            return url
        # 提取域名
        m2 = re.match(r"https?://([^/]+)", url)
        if m2:
            return f"[{m2.group(1)} 链接]"
        return "[链接]"
    return re.sub(r"https?://\S+", replacer, text)


# 每种 slot 的泛化锐评模板
SLOT_CTX = {
    "longest": "你写了一段小作文。这是你给 AI 最完整的一次表达。",
    "shortest": "一个字搞定。说收工就收工。",
    "strong_negation": "AI 又翻车了。你没解释，直接训。",
    "naming": "命名时刻。你给项目里的某个东西起了名字——命名是设计的一半。",
    "drama": "情绪外露的瞬间。这种东西 AI 没法 fake。",
    "night": "凌晨派的灵感。Mac 没睡，你也没。",
    "last": "最后一句。你和这个项目的当前态度。",
}


def analyze(prompts: List, user_name: str) -> Dict[str, Any]:
    """主入口：吃 prompts，吐 analysis"""
    if not prompts:
        return {"empty": True}

    # 排序：按时间戳，用于上下文窗口和 first_prompt
    sorted_prompts = sorted(prompts, key=lambda p: p.timestamp)

    # ===== 基础统计 =====
    n = len(prompts)
    chars = [len(p.text) for p in prompts]
    total_chars = sum(chars)
    sorted_chars = sorted(chars)
    median_len = sorted_chars[n // 2]
    mean_len = total_chars / n
    max_len = max(chars)
    min_len = min(chars)

    # 时间分布
    hour_dist = Counter()
    weekday_dist = Counter()
    daily_dist = Counter()
    earliest_ts = min(p.timestamp for p in prompts)
    latest_ts = max(p.timestamp for p in prompts)

    for p in prompts:
        dt = datetime.fromtimestamp(p.timestamp / 1000, tz=CN_TZ)
        hour_dist[dt.hour] += 1
        weekday_dist[dt.strftime("%A")] += 1
        daily_dist[dt.strftime("%Y-%m-%d")] += 1

    active_days = len(daily_dist)
    span_days = max(1, (latest_ts - earliest_ts) // (1000 * 86400) + 1)
    peak_day, peak_count = daily_dist.most_common(1)[0]

    # 17 点峰值等
    hour_max_hour, hour_max_count = hour_dist.most_common(1)[0]
    hour_max_ratio = hour_max_count / n
    weekday_max_day, weekday_max_count = weekday_dist.most_common(1)[0]
    weekday_max_ratio = weekday_max_count / n
    night_count = sum(hour_dist.get(h, 0) for h in range(0, 6))
    night_ratio = night_count / n
    morning_count = sum(hour_dist.get(h, 0) for h in range(6, 9))
    morning_ratio = morning_count / n

    # ===== 口癖匹配（SPEC §6.1）=====
    pattern_counts = []
    for pat in LEXICON["patterns"]:
        regs = [re.compile(r) for r in pat["regex"]]
        count = 0
        for p in prompts:
            if any(r.search(p.text) for r in regs):
                count += 1
        if count >= 2:
            pattern_counts.append({
                "label": pat["label"],
                "count": count,
                "examples": pat.get("examples", []),
            })
    pattern_counts.sort(key=lambda x: -x["count"])

    # 否定词占比（calm 轴）
    neg_words = LEXICON["negation_words_for_calm_axis"]
    neg_re = re.compile("|".join(re.escape(w) for w in neg_words))
    negation_count = sum(1 for p in prompts if neg_re.search(p.text))
    negation_ratio = negation_count / n

    # 三轴
    length_axis = min(1.0, math.log(max(median_len, 5)) / math.log(300))
    calm_axis = max(0.0, min(1.0, 1.0 - negation_ratio * 1.7))
    # architect 信号
    first_prompt_len = len(sorted_prompts[0].text) if sorted_prompts else 0
    long_count = sum(1 for c in chars if c >= 200)
    long_ratio = long_count / n
    architect_axis = min(1.0, (first_prompt_len / 300) * 0.5 + long_ratio * 8)

    user_axes = (length_axis, calm_axis, architect_axis)

    # ===== 作家匹配（SPEC §4）=====
    matched_slug, matched_dist = None, float("inf")
    for slug, info in AUTHORS.items():
        a = info["axes"]
        d = math.sqrt(
            (user_axes[0] - a["length"]) ** 2
            + (user_axes[1] - a["calm"]) ** 2
            + (user_axes[2] - a["architect"]) ** 2
        )
        if d < matched_dist:
            matched_dist = d
            matched_slug = slug
    matched_author = dict(AUTHORS[matched_slug])
    matched_author["slug"] = matched_slug
    matched_author["distance"] = matched_dist

    # ===== 金句筛选（SPEC §7）=====
    quotes = _pick_quotes(prompts, sorted_prompts)

    # ===== 徽章（SPEC §8）=====
    project_count = len(set(p.project_id for p in prompts))
    pattern_lookup = {p["label"]: p["count"] for p in pattern_counts}
    short_cmd_count = sum(1 for p in prompts if p.text.strip() in
                          ("好", "可以", "部署吧", "下一步", "继续", "嗯", "对", "ok", "OK"))
    naming_count = sum(1 for p in prompts if re.search(r"叫.{1,8}吧|命名为|我们就叫", p.text))

    badges = _pick_badges({
        "weekday_max_ratio": weekday_max_ratio,
        "weekday_max_day": weekday_max_day,
        "weekday_max_count": weekday_max_count,
        "weekday_max_zh": WEEKDAY_ZH.get(weekday_max_day, weekday_max_day),
        "hour_max_ratio": hour_max_ratio,
        "hour_max_hour": hour_max_hour,
        "hour_max_count": hour_max_count,
        "night_ratio": night_ratio,
        "morning_ratio": morning_ratio,
        "active_days": active_days,
        "span_days": span_days,
        "total_chars": total_chars,
        "mean_len": int(mean_len),
        "median_len": median_len,
        "project_count": project_count,
        "short_cmd_count": short_cmd_count,
        "naming_count": naming_count,
        "pattern_lookup": pattern_lookup,
        "peak_count": peak_count,
        "peak_day": peak_day,
    })

    # ===== 章节触发（SPEC §5.2）=====
    chapters = []  # 顺序：1=数据墙, 2=生物钟, 3=口癖, 4=金句, 5=徽章, 终
    chapters.append({"id": "stats", "render": True})  # 永远必出
    chapters.append({"id": "clock", "render": active_days >= 2})
    chapters.append({"id": "patterns", "render": len(pattern_counts) >= 3})
    chapters.append({"id": "quotes", "render": len(quotes) >= 4})
    chapters.append({"id": "badges", "render": len(badges) >= 4})
    chapters.append({"id": "outro", "render": True})  # 永远必出

    # 重新连续编号（SPEC §5.3）
    rendered_chapters = []
    counter = 0
    for ch in chapters:
        if not ch["render"]:
            continue
        if ch["id"] == "outro":
            ch["display_num"] = "终"
        else:
            counter += 1
            ch["display_num"] = str(counter)
        rendered_chapters.append(ch)

    # ===== 项目别名收集（待 LLM 起名） =====
    project_groups = {}
    for p in prompts:
        project_groups.setdefault(p.project_id, []).append(p)
    project_aliases = []
    for pid, ps in project_groups.items():
        ps_sorted = sorted(ps, key=lambda x: x.timestamp)
        first_text = ps_sorted[0].text[:200] if ps_sorted else ""
        first_text = _shrink_urls(first_text)
        project_aliases.append({
            "project_id": pid,
            "current_label": ps_sorted[0].project_label if ps_sorted else "",
            "first_prompt": first_text,
            "prompt_count": len(ps),
            "alias": None,           # ← LLM 待填
            "alias_default": ps_sorted[0].project_label if ps_sorted else "",
        })

    # ===== 终番 pun 兜底文本 =====
    haishi = pattern_lookup.get("还是…", 0)
    redo = pattern_lookup.get("重做 / 重来 / 重新", 0)
    nogood = pattern_lookup.get("不好 / 不对", 0)
    pun_default_lines = [
        f'{matched_author["name_zh"]}用 {matched_author["book_words"]//10000} 万字写完了《{matched_author["book"].strip("《》")}》。',
        f'你用 {total_chars//10000 if total_chars>=10000 else "%.1f" % (total_chars/10000)} 万字 vibe 出了一个项目——',
    ]
    fragments = []
    if nogood > 0:
        fragments.append(f'说了 {nogood} 次"不好/不对"')
    if redo > 0:
        fragments.append(f'重做了 {redo} 次')
    if haishi > 0:
        fragments.append(f'抱怨"还是没变" {haishi} 次')
    if fragments:
        pun_default_lines.append('，'.join(fragments) + '。')
    pun_default_lines.append('但你也真的把它搞出来了。')
    pun_default = "<br>".join(pun_default_lines)

    return {
        "user_name": user_name,
        "stats": {
            "prompts": n,
            "total_chars": total_chars,
            "active_days": active_days,
            "span_days": span_days,
            "peak_count": peak_count,
            "peak_day": peak_day,
            "median_len": median_len,
            "mean_len": int(mean_len),
            "max_len": max_len,
            "min_len": min_len,
            "earliest": datetime.fromtimestamp(earliest_ts/1000, tz=CN_TZ).strftime("%Y.%m.%d"),
            "latest": datetime.fromtimestamp(latest_ts/1000, tz=CN_TZ).strftime("%Y.%m.%d"),
        },
        "axes": user_axes,
        "matched_author": matched_author,
        "hour_dist": dict(hour_dist),
        "weekday_dist": dict(weekday_dist),
        "weekday_dist_zh": {WEEKDAY_ZH[k]: v for k, v in weekday_dist.items()},
        "weekday_max_zh": WEEKDAY_ZH.get(weekday_max_day, weekday_max_day),
        "weekday_max_ratio": weekday_max_ratio,
        "weekday_max_count": weekday_max_count,
        "hour_max_hour": hour_max_hour,
        "hour_max_count": hour_max_count,
        "night_count": night_count,
        "top_patterns": pattern_counts[:5],
        "praise_count": _count_praise(prompts),
        "quotes": quotes,
        "badges": badges,
        "chapters": rendered_chapters,
        "project_count": project_count,
        "negation_ratio": negation_ratio,
        "long_ratio": long_ratio,
        "first_prompt_len": first_prompt_len,
        # ===== LLM 增强字段（默认为兜底，agent 可覆盖） =====
        "project_aliases": project_aliases,
        "author_followup": "你呢 😅",                  # 默认兜底
        "author_followup_default": "你呢 😅",
        "badges_summary": "",                          # 6 个徽章的总结陈词，默认空
        "outro_pun": pun_default,                      # 终番戏谑句
        "outro_pun_default": pun_default,
        "_llm_tasks": _build_llm_tasks_descriptor(quotes, project_aliases, matched_author, badges),
    }


def _build_llm_tasks_descriptor(quotes, project_aliases, matched_author, badges):
    """生成给 agent 看的 LLM 任务清单（提示词模板 + 字段路径）"""
    return {
        "tasks": [
            {
                "id": "quote_ctx_and_tag",
                "instruction": (
                    "对每条金句结合前后 ±3 条对话上下文（context_before / context_after），"
                    "写一句 ≤30 字的「贴脸锐评」+ 一个 4-6 字的中文「标签」。"
                    "\n\n## 锐评的语气基准（必须狠）"
                    "\n- 葬AI 风 + 即刻吐槽体：反高潮、自嘲、像朋友损你"
                    "\n- 不要写成「客观描述」（错误：「你给 AI 起了个名字。」）"
                    "\n- 要写出「损人不带脏字」的反差感（正确：「为了这俩字你折腾了两周。」）"
                    "\n- 不要总结，不要赞美，不要鸡汤，不要排比"
                    "\n- 多用具体动词、数字、对比；少用抽象词（'命名是设计的一半'这种格言禁用）"
                    "\n\n## 写作流程"
                    "\n1. 先看 context 弄清「这条话当时在干嘛」"
                    "\n2. 找出最荒诞/最戳/最反差的那个点"
                    "\n3. 用一句话把那个点拎出来损一下"
                    "\n\n## 例子（学这个调）"
                    "\n  bad → AI 漏了一期没做。你直接「别偷懒」。"
                    "\n  good → 你管的不是 AI，是你的小弟。"
                    "\n  bad → 命名时刻。你给某个东西起了名字。"
                    "\n  good → 为了「探测」这俩字，你折腾了两周。"
                    "\n  bad → AI 又翻车了。你没解释，直接训。"
                    "\n  good → AI 已被你踢出群聊。"
                    "\n\n诚实，不能编造细节；上下文实在看不出就保留 ctx_default。"
                ),
                "fields_per_quote": ["ctx", "tag"],
                "count": len(quotes),
            },
            {
                "id": "project_aliases",
                "instruction": (
                    "看每个项目的 first_prompt（第一句话），给项目起一个 2-6 字的中文别名。"
                    "如果第一句信息不足以判断主题，就保留 alias_default 不动（不要瞎起）。"
                ),
                "fields_per_project": ["alias"],
                "count": len(project_aliases),
            },
            {
                "id": "author_followup",
                "instruction": (
                    "看用户匹配到的作家（{author_zh}）+ 用户三轴特征 + TOP 口癖 + 徽章，"
                    "把封面作家头像下方的「你呢 😅」换成一句**贴脸吐槽**（≤20 字）。"
                    "\n\n## 要求"
                    "\n- 必须以「{author_zh}：」开头，模仿作家口吻**反过来损用户**"
                    "\n- 不能写成褒义（错误：「{author_zh}：你也很厉害。」）"
                    "\n- 要利用作家特征 + 用户数据形成反差"
                    "\n- 例子（学这个调）："
                    "\n  good → 海明威：我一句没写过 200 字，你一句 300。"
                    "\n  good → 卡夫卡：起码我没「重做」50 次。"
                    "\n  good → 博尔赫斯：他迷宫只画一遍，你呢？"
                    "\n  bad  → 加缪：你也很有想法。"
                    "\n\n想不出比默认更狠的就保留 author_followup_default。"
                ).format(author_zh=matched_author["name_zh"]),
                "field": "author_followup",
            },
            {
                "id": "badges_summary",
                "instruction": (
                    "看 6 个徽章 + 用户三轴 + 匹配作家，给整章写一句**贴脸总结**（≤25 字）。"
                    "\n\n## 要求"
                    "\n- 葬AI 风：反高潮、自嘲、不要鸡汤"
                    "\n- 把多个徽章串成一句话「人格速写」，要有反差"
                    "\n- 例子（学这个调）："
                    "\n  good → 一个反复推翻的架构师，靠周五一天干完一周的活。"
                    "\n  good → 视觉强迫症 + 周五战神，组合起来是个偏执的拖延者。"
                    "\n  bad  → 你是一个非常努力且有创造力的人。"
                    "\n\n空字符串 = 不展示（不强出，宁缺毋滥）。"
                ),
                "field": "badges_summary",
            },
            {
                "id": "outro_pun",
                "instruction": (
                    "终番戏谑句：把「作家 vs 你」对照写成 4-6 行 HTML（<br> 分行）。"
                    "\n\n## 必须遵守"
                    "\n- 第 1 行：作家的具体反差事实（不是泛泛的字数比，要找作家身上「最反差」的小知识）"
                    "\n- 第 2-4 行：用用户的真实数据（字数、口癖次数、重做次数）写自嘲"
                    "\n- 最后 1 行：反高潮收尾「但你也真的把它搞出来了。」或类似"
                    "\n\n## 要求"
                    "\n- 葬AI 风，不要鸡汤，不要排比，不要文学化"
                    "\n- 数据必须从 stats / top_patterns 里取，不能编"
                    "\n- 第 1 行可以「冒犯一下作家」让对比更戳"
                    "\n\n## 例子（学这个调）"
                    "\n  good → 博尔赫斯一辈子最长的小说不到 2 万字。<br>"
                    "你用 5.7 万字 vibe 出一个项目——<br>"
                    "说了 16 次「不好」，重做了 11 次，<br>"
                    "「还是没变」念了 50 次。<br>"
                    "但你也真的把它搞出来了。"
                    "\n\n想不出比 default 狠的就保留 outro_pun_default。"
                ),
                "field": "outro_pun",
            },
        ],
        "_format_note": (
            "agent 完成后要把所有字段写回 data.json 的对应位置，"
            "然后调用：python3 run.py --finalize <data.json>"
        ),
    }


def _count_praise(prompts):
    words = LEXICON.get("praise_words", [])
    if not words:
        return 0
    pattern = re.compile("|".join(re.escape(w) for w in words))
    return sum(1 for p in prompts if pattern.search(p.text))


def _pick_quotes(prompts, sorted_by_ts):
    """SPEC §7 金句筛选 + 给每条加 ±3 条上下文窗口"""
    if not prompts:
        return []
    sorted_by_len = sorted(prompts, key=lambda p: len(p.text))

    # 建一个 timestamp -> index 的索引（取 sorted_by_ts 的位置）
    ts_idx = {id(p): i for i, p in enumerate(sorted_by_ts)}

    drama_emojis = LEXICON.get("drama_emoji", [])

    candidates = []
    seen_texts = set()

    def _ctx_window(p, before=3, after=3):
        """返回这条 prompt 前后 N 条（精简到关键字段）"""
        idx = ts_idx.get(id(p))
        if idx is None:
            return [], []
        b_start = max(0, idx - before)
        a_end = min(len(sorted_by_ts), idx + after + 1)
        before_list = [_compact(x) for x in sorted_by_ts[b_start:idx]]
        after_list = [_compact(x) for x in sorted_by_ts[idx+1:a_end]]
        return before_list, after_list

    def _compact(p):
        """压缩单条 prompt 给 LLM 用：截 100 字 + 时间"""
        t = _shrink_urls(p.text)
        if len(t) > 100:
            t = t[:100] + "…"
        return {
            "t": t,
            "ts": datetime.fromtimestamp(p.timestamp/1000, tz=CN_TZ).strftime("%m-%d %H:%M"),
        }

    def _add(p, slot, tag):
        if not p:
            return
        if p.text in seen_texts:
            return
        seen_texts.add(p.text)
        text = _privacy_mask(p.text)
        text = _shrink_urls(text)
        if len(text) > 200:
            text = text[:200] + "…"
        before, after = _ctx_window(p)
        candidates.append({
            "slot": slot,
            "tag": tag,                            # 兜底 tag（LLM 可覆盖）
            "tag_default": tag,                    # 永远保留兜底，方便 fallback
            "text": text,
            "ctx": SLOT_CTX.get(slot, ""),         # 兜底 ctx
            "ctx_default": SLOT_CTX.get(slot, ""), # 永远保留兜底
            "context_before": before,              # ←给 LLM 的素材
            "context_after": after,                # ←给 LLM 的素材
            "timestamp": p.timestamp,
            "datetime": datetime.fromtimestamp(p.timestamp/1000, tz=CN_TZ).strftime("%Y.%m.%d · %H:%M"),
            "project_label": p.project_label,
        })

    # 1. 最长（≤500 字）
    for p in reversed(sorted_by_len):
        if len(p.text) <= 500:
            _add(p, "longest", "小作文派"); break
    # 2. 最短（≥1 字）
    if sorted_by_len:
        _add(sorted_by_len[0], "shortest", "单字 KO")
    # 3. 最强否定（短）
    strong_neg_re = re.compile(r"^(你太|你怎么|到底|为什么)")
    strong_neg_candidates = [p for p in prompts if strong_neg_re.search(p.text) and len(p.text) <= 100]
    if strong_neg_candidates:
        _add(strong_neg_candidates[0], "strong_negation", "训斥型反馈")
    # 4. 命名时刻
    naming_re = re.compile(r"叫.{1,8}吧|命名为|我们就叫")
    naming_candidates = [p for p in prompts if naming_re.search(p.text)]
    if naming_candidates:
        _add(naming_candidates[0], "naming", "命名时刻")
    # 5. 含戏剧表情
    if drama_emojis:
        emoji_re = re.compile("|".join(re.escape(e) for e in drama_emojis))
        emoji_candidates = [p for p in prompts if emoji_re.search(p.text) and len(p.text) <= 200]
        if emoji_candidates:
            _add(emoji_candidates[0], "drama", "情绪外露")
    # 6. 凌晨派
    night_candidates = [p for p in prompts
                        if 0 <= datetime.fromtimestamp(p.timestamp/1000, tz=CN_TZ).hour < 6]
    if night_candidates:
        _add(night_candidates[0], "night", "凌晨派")
    # 7. 最后一句
    if sorted_by_ts:
        _add(sorted_by_ts[-1], "last", "终极态度")

    return candidates


def _pick_badges(stats):
    """SPEC §8 徽章选取（按 weight 排序，至少 4 个才算成立）"""
    triggered = []
    for badge in BADGES["badges"]:
        ok, fmt = _check_trigger(badge, stats)
        if not ok:
            continue
        # 套模板
        name = badge["name_template"]
        evidence = badge["evidence_template"]
        for k, v in fmt.items():
            name = name.replace("{" + k + "}", str(v))
            evidence = evidence.replace("{" + k + "}", str(v))
        triggered.append({
            "id": badge["id"],
            "name": name,
            "evidence": evidence,
            "weight": badge["weight"],
        })
    triggered.sort(key=lambda b: -b["weight"])
    return triggered[:6]


def _check_trigger(badge, stats):
    """检查徽章是否触发，返回 (是否触发, 格式化字典)"""
    t = badge["trigger"]
    typ = t["type"]
    fmt = {}

    if typ == "weekday_max_ratio":
        if stats["weekday_max_ratio"] >= t["min"]:
            fmt = {
                "X_weekday_zh": stats["weekday_max_zh"],
                "ratio_pct": int(stats["weekday_max_ratio"] * 100),
                "peak_count": stats["peak_count"],
            }
            return True, fmt
    elif typ == "hour_max_ratio":
        if stats["hour_max_ratio"] >= t["min"]:
            fmt = {"hour": stats["hour_max_hour"], "count": stats["hour_max_count"]}
            return True, fmt
    elif typ == "night_ratio":
        if stats["night_ratio"] >= t["min"]:
            fmt = {"ratio_pct": round(stats["night_ratio"] * 100, 1)}
            return True, fmt
    elif typ == "morning_ratio":
        if stats["morning_ratio"] >= t["min"]:
            fmt = {"ratio_pct": round(stats["morning_ratio"] * 100, 1)}
            return True, fmt
    elif typ == "pattern_combo":
        a = stats["pattern_lookup"].get(t["patterns"][0], 0)
        b = stats["pattern_lookup"].get(t["patterns"][1], 0)
        if a + b >= t["min_total"]:
            fmt = {"count_a": a, "count_b": b}
            return True, fmt
    elif typ == "pattern_count":
        c = stats["pattern_lookup"].get(t["pattern"], 0)
        if c >= t["min"]:
            fmt = {"count": c}
            return True, fmt
    elif typ == "active_days":
        if stats["active_days"] >= t["min"]:
            fmt = {"active_days": stats["active_days"], "span_days": stats["span_days"]}
            return True, fmt
    elif typ == "blitz":
        if stats["active_days"] <= t["max_days"] and stats["total_chars"] >= t["min_chars"]:
            fmt = {"active_days": stats["active_days"], "total_chars": stats["total_chars"]}
            return True, fmt
    elif typ == "mean_len":
        if "min" in t and stats["mean_len"] >= t["min"]:
            fmt = {"mean_len": stats["mean_len"]}
            return True, fmt
        if "max" in t and stats["mean_len"] <= t["max"]:
            fmt = {"mean_len": stats["mean_len"]}
            return True, fmt
    elif typ == "project_count":
        if stats["project_count"] >= t["min"]:
            fmt = {"project_count": stats["project_count"]}
            return True, fmt
    elif typ == "short_command_count":
        if stats["short_cmd_count"] >= t["min"]:
            fmt = {"count": stats["short_cmd_count"]}
            return True, fmt
    elif typ == "total_chars":
        if stats["total_chars"] >= t["min"]:
            fmt = {"total_chars": stats["total_chars"]}
            return True, fmt
    elif typ == "naming_count":
        if stats["naming_count"] >= t["min"]:
            fmt = {"count": stats["naming_count"]}
            return True, fmt
    return False, fmt
