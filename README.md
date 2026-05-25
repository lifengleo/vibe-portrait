# Vibe 自画像（vibe-portrait）

> 把你 vibe coding 时的 prompt 历史，做成一张「自画像」海报。

```
你 vibe 了一个项目，叫 Sona。
在 Sona 里，你口喷了 32,767 个字。
耗时 53 天。
```

整张海报 6 个章节：你说了多少话 / 你的 vibe 生物钟 / 翻来覆去就这几句 / 你是这样欺负 AI 的 / 给你的 vibe 颁几个奖 / 字数是有了文学是没有。每个用户的数据、口癖、徽章、匹配作家都不一样。

---

## 安装

### Claude Code（一键装，推荐）

在 Claude Code 里输入：

```
/plugin marketplace add lifengleo/vibe-portrait
/plugin install vibe-portrait@vibe-portrait
```

然后说一句「跑我的 vibe 自画像」就行。

### WorkBuddy / Codex CLI / 其他 agent（git clone）

```bash
# WorkBuddy
git clone https://github.com/lifengleo/vibe-portrait ~/.workbuddy/skills/vibe-portrait

# Codex CLI
git clone https://github.com/lifengleo/vibe-portrait ~/.codex/skills/vibe-portrait
```

> 不会用 git？也可以下 [release tar 包](https://github.com/lifengleo/vibe-portrait/releases) 解压到对应目录。

### 装截图依赖（可选）

只想要 HTML 海报可以**完全跳过这一步**——核心产出就是 HTML，能直接打开看。

如果想要自动导出 JPG（分享到朋友圈/即刻用）：

```bash
cd <skill 目录>
npm install     # 装 playwright + sharp，版本锁在 package.json
```

### 3. 跑

**方式 A：在 agent 里说**（推荐，会触发 LLM 增强让海报更贴脸）

> 跑我的 vibe 自画像

或者第一次装完直接说：

> hi / 这个 skill 怎么用 / vibe portrait 是啥

**安装后第一次对话长这样**（agent 应该主动招呼，不要等你问）：

```
你 ▸ hi

agent ▸ 👋 Vibe 自画像装好了。

       简单说，它会把你最近 Vibe Coding 的 prompt 历史，
       拉出来对个账，画一张"Vibe Coding 自画像"：
         ▸ 你说了多少话 / 什么时候说 / 最爱念叨哪几句
         ▸ 顺带颁几个徽章（视觉强迫症？周五战神？重做大师？）
         ▸ 匹配一位最像你风格的作家

       完全本地跑，不上传任何对话内容。

       要现在跑一个吗？我会先问你两件事：
         1. 怎么称呼你（写进海报）
         2. 想分析哪几个对话窗口（我会列出本地检测到的）

你 ▸ 跑吧

agent ▸ 怎么称呼你？

你 ▸ 小李

agent ▸ [拉出本地 35 个对话窗口让你选]
```

> ⚠️ 如果装完之后 agent 没主动招呼，是宿主 agent 的 SKILL.md 加载机制问题——
> 试试明确说一句 `用一下 vibe-portrait skill`，或参考 [SKILL.md Phase 0](./SKILL.md#-phase-0装完之后第一次见面必读放最前面)。

**方式 B：命令行**

```bash
cd ~/.workbuddy/skills/vibe-portrait    # 或对应的 Claude / Codex 路径
python3 run.py
```

第一次会问你昵称（保存到 `~/.vibe-portrait/config.json`，下次不再问）。然后列出本机所有对话窗口让你选哪个 / 哪几个项目要分析。最后产出在当前目录的 `vibe-portrait/<日期>/` 下。

### 4. 升级

```bash
cd ~/.workbuddy/skills/vibe-portrait && git pull && npm install
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
| Claude Code | `~/.claude/projects/` | 🟡 实现完成（best-effort，待真实数据校验） |
| Codex CLI | `~/.codex/sessions/` | 🟡 实现完成（best-effort，待真实数据校验） |
| Cursor / Aider / ... | — | 欢迎 PR adapter |

> 🟡 含义：adapter 代码已写完、能跑通合成数据；但 Claude / Codex 的 jsonl 字段在真实环境里可能略有差异，欢迎在 issue 里反馈，或直接传 `--project /abs/path/file.jsonl` 绕过自动检测。

---

## 命令行

```bash
# 交互式（推荐）
python3 run.py

# 直接传参
python3 run.py --user 恩瑞 --multi 1,3

# 跨项目
python3 run.py --multi 1,3,5

# 直接指定 jsonl（不依赖默认 agent 历史检测，适合 Claude / Codex / 自定义路径）
python3 run.py --user 恩瑞 --project /abs/path/file.jsonl --source workbuddy

# 跳过 LLM 增强（一步到位 + 兜底文案）
python3 run.py --skip-llm

# Finalize（agent 增强 data.json 后调用）
python3 run.py --finalize ./vibe-portrait/2026-05-25/data.json

# 只列对话窗口，不跑分析
python3 run.py --list
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
