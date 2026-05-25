# Vibe 自画像（vibe-portrait）

> 把你和 AI 共写产品时的 prompt 历史，做成一张「自画像」海报。

```
你 vibe 了一个项目，叫 Sona。
在 Sona 里，你口喷了 32,767 个字。
耗时 53 天。
```

整张海报 6 个章节：你说了多少话 / 你的 vibe 生物钟 / 翻来覆去就这几句 / 你是这样欺负 AI 的 / 给你的 vibe 颁几个奖 / 字数是有了文学是没有。每个用户的数据、口癖、徽章、匹配作家都不一样。

---

## 安装

### 1. 拉到 skills 目录

**支持 WorkBuddy / Claude Code / Codex CLI 的 skill 机制。**

```bash
git clone https://github.com/lifengleo/vibe-portrait ~/.workbuddy/skills/vibe-portrait
# 或
git clone https://github.com/lifengleo/vibe-portrait ~/.claude/skills/vibe-portrait
```

### 2. 装依赖

**系统要求**：Python 3.9+ / Node.js 18+

```bash
# Node 包：截图 + 压图
npm install -g playwright sharp
npx playwright install chromium
```

Python 用标准库，无需额外装。

### 3. 跑

对你的 agent 说：

> 跑我的 vibe 自画像

或者命令行：

```bash
python3 ~/.workbuddy/skills/vibe-portrait/run.py
```

---

## 工作原理

```
┌─────────────────────────┐
│  阶段 1：纯 Python 数据  │ → data.json（含 5 个 LLM 待填字段 + 兜底）
│  扫 jsonl / 三轴算法     │
└────────────┬─────────────┘
             │
┌────────────▼─────────────┐
│  阶段 2：agent LLM 增强   │ → 写 ctx / tag / 项目别名 /
│  本地宿主 agent 调自己   │   作家吐槽 / 终番戏谑（可跳过）
└────────────┬─────────────┘
             │
┌────────────▼─────────────┐
│  阶段 3：渲染 + 截图      │ → index.html + portrait.jpg
│  Python + Playwright     │
└──────────────────────────┘
```

**关键设计**：用户在自己本地跑 skill，宿主 agent 的 LLM 推理是**用户自己的 token**，所以海报里所有「需要灵性」的部分都让 agent 写。

**完全本地**：不上传任何对话内容到任何服务器。

---

## 支持的 agent

| Agent | 路径 | 状态 |
|---|---|---|
| WorkBuddy | `~/.workbuddy/projects/` | ✅ 真实数据测过 |
| Claude Code | `~/.claude/projects/` | ✅ 实现完成（待真实环境验证） |
| Codex CLI | `~/.codex/sessions/` | ✅ 实现完成（待真实环境验证） |
| Cursor / Aider / ... | — | 欢迎 PR adapter |

---

## 命令行

```bash
# 交互式（推荐）
python3 run.py

# 直接传参
python3 run.py --user 恩瑞 --multi 1,3

# 跨项目
python3 run.py --multi 1,3,5

# 跳过 LLM 增强（一步到位 + 兜底文案）
python3 run.py --skip-llm

# Finalize（agent 增强 data.json 后调用）
python3 run.py --finalize ./vibe-portrait/2026-05-25/data.json
```

---

## 自定义

### 替换作家肖像

`assets/portraits/` 下放你想要的 9 张作家肖像（统一风格、推荐圆形友好的正方形构图、≥600×600 px、JPG）。同步改 `_meta.json` 里每个作家的三轴分数（length / calm / architect）+ 代表作 + tagline。

详见 [SPEC.md §4](./SPEC.md#4-作家库9-人阵容--三轴定位)。

### 调整徽章

`assets/badges.json` 包含 15 个候选徽章 + 触发条件 + 锐评模板。新增徽章时按现有结构加，注意 evidence_template 必须保持锐评调性（详见 SPEC §9.4）。

### 调整章节

`core/render.py` 里每个章节是一个独立函数，按需改。如果某章你想关掉，删掉对应函数 + `chapters` 里的注册即可。

---

## 文档

- [SKILL.md](./SKILL.md) — agent 调用入口（必读）
- [SPEC.md](./SPEC.md) — 产品规则总文档（三轴算法、章节优先级、徽章字典、葬AI 文风基准、9 位作家定位）

---

## License

MIT

灵感来源：Spotify Wrapped（数据可视化年鉴） + 公众号「葬 AI」（反高潮口语风）。
