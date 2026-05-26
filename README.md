# Vibe 自画像（vibe-portrait）

> 把你 vibe coding 时的 prompt 历史，做成一张「自画像」海报。

```
你 vibe 了一个项目，叫 Sona。
在 Sona 里，你口喷了 32,767 个字。
耗时 53 天。
```

整张海报 6 个章节：你说了多少话 / 你的 vibe 生物钟 / 翻来覆去就这几句 / 你是这样欺负 AI 的 / 给你的 vibe 颁几个奖 / 字数是有了文学是没有。

---

## 安装（一行命令）

**Claude Code**：
```bash
git clone https://github.com/lifengleo/vibe-portrait ~/.claude/skills/vibe-portrait
```

**Codex CLI**：
```bash
git clone https://github.com/lifengleo/vibe-portrait ~/.codex/skills/vibe-portrait
```

**WorkBuddy**：
```bash
git clone https://github.com/lifengleo/vibe-portrait ~/.workbuddy/skills/vibe-portrait
```

装完直接在 agent 里说一句 **「跑我的 vibe 自画像」** 或 **「hi」**，agent 会主动招呼并引导你。

---

## 完全本地

不上传任何对话内容到任何服务器。所有数据扫描、分析、渲染都在你自己电脑上完成。

默认只读取你**当前 agent**的对话历史（装在 Codex 下就只读 Codex 的）。要跨 agent 合并需要你显式同意。

---

## 可选：装 JPG 截图依赖

只想要 HTML 海报可以**完全跳过**——核心产出就是 HTML，浏览器打开就能看。

如果想要自动导出 JPG（分享到朋友圈/即刻用）：

```bash
cd <skill 目录>
npm install
```

需要 Node.js 18+，会装 playwright + sharp（版本锁在 package.json）。

---

## 工作原理

```
扫本地 prompt 历史 → 三轴算法（句长/情绪/架构感）
        ↓
匹配 9 位作家中最像的一位
        ↓
agent 用自己的 LLM 写 5 段贴脸锐评
        ↓
HTML 海报 + JPG 截图
```

**关键设计**：宿主 agent 的 LLM 推理用你自己的 token，所以不收任何费。

---

## 支持的 agent

| Agent | 路径 | 状态 |
|---|---|---|
| WorkBuddy | `~/.workbuddy/projects/` | ✅ 真实数据测过 |
| Claude Code | `~/.claude/projects/` | 🟡 实现完成 |
| Codex CLI | `~/.codex/sessions/` | 🟡 实现完成 |
| Cursor / Aider | — | 欢迎 PR |

---

## 命令行（高级用法）

```bash
cd <skill 目录>

python3 run.py                    # 交互式（推荐）
python3 run.py --list             # 只列对话窗口
python3 run.py --user 小李 --multi 1,3   # 直接传参
python3 run.py --skip-llm         # 跳过 LLM 增强（用兜底文案）
python3 run.py --finalize         # 渲染最新一份 data.json
python3 run.py --include all      # 跨 agent 扫描（需要显式 opt-in）
```

---

## 升级

```bash
cd <skill 目录> && git pull
```

---

## 自定义

- **替换作家肖像**：改 `assets/portraits/` 下的 9 张图 + `_meta.json` 三轴分数
- **调整徽章**：改 `assets/badges.json`（15 个候选徽章 + 触发条件）
- **调整章节**：改 `core/render.py`

详见 [SPEC.md](./SPEC.md)（产品规则总文档）。

---

## 文档

- [SKILL.md](./SKILL.md) — agent 调用入口（必读）
- [SPEC.md](./SPEC.md) — 产品规则总文档（三轴算法 / 章节优先级 / 徽章字典 / 9 位作家定位）

---

## License

MIT

灵感来源：Spotify Wrapped + 公众号「葬 AI」。
