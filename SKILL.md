---
name: vibe-portrait
description: |
  Vibe 自画像——把用户 vibe coding 时的 prompt 历史，做成一张「年度自画像」海报。
  自动检测本地多个 agent（WorkBuddy / Claude Code / Codex CLI 等）的对话历史，
  让用户选一个或多个对话窗口，统计 prompt 习惯（句长/作息/口癖/金句），
  匹配 9 位作家中最像的一位作为镜像，输出 HTML + JPG 长图。

  ▸ 用户视角（不是项目视角）——海报主语永远是"用户"
  ▸ 跨 agent 适配——不绑定任何特定平台
  ▸ 完全本地——不上传任何对话内容
  ▸ 两阶段流程——agent 自己用 LLM 能力增强海报文案

  当用户说以下任一意图时触发本 skill：
    "跑我的 vibe 自画像" / "做一份 vibe 自画像" / "盘点我的 vibe coding"
    "看看我 vibe 了多少" / "我的 prompt 习惯是什么样的"
    "vibe portrait" / "vibe wrapped"

  也在以下"模糊触发"场景下主动响应（Phase 0）：
    用户刚装完 skill、第一次说 "你好" / "hi" / "在吗"，或问"这个 skill 怎么用"、
    "vibe portrait 是什么"、"你能干嘛"——主动用 Phase 0 的开场白介绍并引导。
allowed-tools: Bash, Read, Write
agent_created: true
---

# Vibe 自画像（vibe-portrait）

---

## 🎬 Phase 0：装完之后第一次见面（**必读，放最前面**）

> **写给宿主 agent**：
> 这个 skill 装好之后，**用户大概率不知道下一步该说什么**。所以你不能等用户来问「怎么用」——
> 一旦满足下面任一条件，**主动开口介绍并引导**。

### 触发主动招呼的条件（任一即满足）

1. **本机首次跑**：`~/.vibe-portrait/config.json` 不存在或 `user_name` 为空（说明没跑过）
2. **用户提到本 skill**：消息含 "vibe portrait" / "vibe 自画像" / "vibe wrapped" 等关键词，但**没有给具体指令**
3. **用户问怎么用**："这个 skill 是干嘛的" / "怎么用 vibe-portrait" / "我装了个 vibe portrait"
4. **泛触发**：用户在装完 skill 后第一次开口（"hi" / "在吗" / "试试看" / "跑一个看看"），**且最近 30 天没生成过海报**

### 开场白模板（请直接说，不要省略）

agent 应主动说出**类似下面这段话**（口吻按写作基准——简洁、不油腻、可以略带"葬 AI 风"自嘲，但**Phase 0 这里以友好优先，不要为了风格牺牲清晰**）：

```
👋 Vibe 自画像装好了。

简单说，它会把你最近 Vibe Coding 的 prompt 历史，
拉出来对个账，画一张"Vibe Coding 自画像"：
  ▸ 你说了多少话 / 什么时候说 / 最爱念叨哪几句
  ▸ 顺带颁几个徽章（视觉强迫症？周五战神？重做大师？）
  ▸ 匹配一位最像你风格的作家

完全本地跑，不上传任何对话内容。

要现在跑一个吗？我会先问你两件事：
  1. 怎么称呼你（写进海报）
  2. 想分析哪几个对话窗口（我会列出本地检测到的）
```

> **请不要省略这段话**——这是用户安装后**唯一**理解 skill 价值的窗口。

### 立刻做的下一步

如果用户回复"好"/"跑吧"/"试试"/任何肯定意图：
1. 立刻调用 `AskUserQuestion` 问昵称（如果 config.json 还没昵称）
2. 跑 `python3 <skill 目录>/run.py --list` 拿到对话窗口列表
3. 用 `AskUserQuestion` 让用户挑（**列出标题 + prompt 数 + 起止日期**，最多 4 个候选 + Other）
4. 进入 Phase 1（即下文「完整执行流程」）

如果用户回复"先看看产物长啥样"/"有没有示例"：
- 告诉用户：**装完先生成一张 demo 海报需要至少 5 条本地 prompt**——如果本机没历史数据，建议先聊几句再回来跑。

如果跑 `--list` 发现没有对话窗口（adapter 扫不到任何 jsonl）：
- 告诉用户：「在这个 agent 里多聊几次，回头再来跑就行」
- **绝对不要**问用户能不能去读其他 agent 的历史——见下方「🔒 严格宿主隔离原则」

### 反例：装完之后**不要**这样做

❌ **保持沉默，等用户主动问怎么用**——这是当前 v0.2.0 的最大体验缺陷
❌ 一上来就 dump SKILL.md 的全部技术细节（"两阶段 pipeline 是这样的..."）
❌ 立刻自己跑 `python3 run.py` 不问用户——必须先问昵称和窗口选择
❌ 把作家清单/徽章字典/三轴公式当开场白讲——那是用户**看到海报后**自己去翻的

### 🔒 严格宿主隔离原则（**强制约束**）

> v0.2.2 起，本 skill 严格遵守"宿主隔离"——agent 之间像不同的应用，互不感知。

**唯一规则**：skill 装在哪个 agent 下，**就只读那个 agent 的对话历史，永远不读其他 agent 的数据，永远不询问用户能不能跨 agent 读**。

- skill 装在 `~/.codex/skills/...`     → 只扫 `~/.codex/sessions/`
- skill 装在 `~/.claude/skills/...`    → 只扫 `~/.claude/projects/`
- skill 装在 `~/.workbuddy/skills/...` → 只扫 `~/.workbuddy/projects/`

`run.py` 自动通过路径检测宿主 agent 并写死扫描范围，没有任何参数能扩大它。

**如果当前 agent 没有足够对话历史怎么办**：
- 直接告诉用户「在这个 agent 里多聊几次，回头再来跑就行」
- **不要**主动提到其他 agent 的数据可以"补"——用户在 Codex 里跑就当作 WorkBuddy 不存在
- **不要**给用户 AskUserQuestion 选要不要合并其他 agent 数据
- **不要**在任何文案里出现"WorkBuddy / Codex / Claude Code"等其他 agent 的名字

**为什么这条规则存在**：用户在不同 agent 里聊不同话题，agent 之间应当隔离。"在 Codex 里被询问要不要读 WorkBuddy 数据" 这件事本身就是体验断点，会让用户觉得越权。这个 skill 的目标是做一个"通用的 vibe coding 自画像工具"，每个 agent 内自成一体即可。

---

## 这个 skill 做什么

把用户这阵子和 AI 说过的话，拉出来跟他对个账。

输出是一张图——上面有他说了多少话、什么时候说的、最爱说哪几句、最有戏的几句、可以颁给他的几个奖、以及和他最像的一位作家。

整张图保持「葬AI」反高潮口语风：不写「AI 味」装饰文，不写「××分布·按次数排序」这种说明文。

## 核心机制：两阶段 pipeline

这是 skill 设计的关键——**LLM 能力是用户本地 agent 的能力，是免费的工具**。所以海报里所有"看起来需要灵性"的部分都让 agent 自己写：

```
[阶段 1] python3 run.py [选项]
    ↓
[产出 data.json，里面 5 个 LLM 待填字段]
    ↓
[阶段 2] agent 读 data.json，调自己的 LLM 能力填 5 个字段
    ↓
[阶段 3] python3 run.py --finalize <data.json>
    ↓
[产出 index.html + portrait-share.jpg + portrait-hd.jpg]
```

## 完整执行流程（agent 必读）

> 进入这个流程的前提是 **Phase 0 已经做完**——用户已经看过开场白，明确表达"现在就跑"。
> 如果用户只是问"这是什么"，**回到 Phase 0**，不要直接进流程。

### Phase 1（第 1 步）：必填昵称

读取 `~/.vibe-portrait/config.json`：
- 已有 `user_name` → 跳过
- 没有 → 问用户「怎么称呼你？」，写入配置

### 第 2 步：调起 analyze

skill 的入口脚本就在本目录的 `run.py`（你正在读的这个 SKILL.md 同级）。所有命令都在 skill 目录下跑，例如：

```bash
cd <skill 目录>          # WorkBuddy: ~/.workbuddy/skills/vibe-portrait
                         # Claude Code: ~/.claude/skills/vibe-portrait
                         # Codex CLI: ~/.codex/skills/vibe-portrait
python3 run.py
```

CLI 会自动列出本地检测到的对话窗口，让用户挑。

或者直接传参：
```bash
python3 run.py --user 恩瑞 --multi 1,3
```

> 想直接指定一个 jsonl，也可以：`python3 run.py --user 恩瑞 --project /abs/path/file.jsonl --source workbuddy`。这种方式不需要本机有默认 agent 历史。

完成后会产出：
- `./vibe-portrait/<日期>/data.json` ← 待你增强
- `./vibe-portrait/<日期>/assets/` ← 肖像资源

### 第 3 步：LLM 增强（**agent 必须做的 5 个任务**）

读取 data.json，找到 `_llm_tasks.tasks` 列表（5 个任务），按以下要求填字段：

> ⚠️ **写作基准**（5 个任务都要遵守，详见 SPEC §9.4）：
>
> 整张海报的口吻 = **葬 AI 风 + 即刻吐槽体**：反高潮、自嘲、像朋友损你。
>
> **❌ 禁忌**：鸡汤陈述（"命名是设计的一半"）/ 客观描述（"AI 翻车了你直接训"，像新闻播报）/ 排比 / 抽象格言 / 主动夸用户
>
> **✅ 鼓励**：具体动词 + 数字（"折腾了两周"）/ 反差对比 / 损人不带脏字（"AI 已被你踢出群聊"）/ 网络梗 / 口语转折
>
> **对照（学这个调）**：
> | ❌ 温柔（不要这样写） | ✅ 锐评（要这样写） |
> |---|---|
> | 命名时刻。你给某个东西起了名字。 | 为了「探测」这俩字，你折腾了两周。 |
> | AI 又翻车了。你没解释，直接训。 | AI 已被你踢出群聊。 |
> | 不连续，但很笃定。 | 放不下的不是项目，是手。 |
> | 这是难得的好习惯——你的 Mac 也要睡觉。 | 不是不卷，是 Mac 也得睡。 |

#### 任务 1：quote_ctx_and_tag

**位置**：`quotes` 数组里每条金句

**对每条金句做**：
- 读 `text`（金句原文） + `context_before` + `context_after`（前后各 3 条对话上下文，含时间戳）
- 写 `ctx`：一句 ≤30 字的「贴脸锐评」
  - good → "为了「探测」这俩字，你折腾了两周。"
  - good → "AI 已被你踢出群聊。"
  - bad → "命名时刻。你给某个东西起了名字。"（鸡汤陈述）
  - bad → "AI 又翻车了。你没解释，直接训。"（客观描述）
  - **诚实，不能编造细节**——上下文看不出"当时在做什么"，**保留 ctx_default 不动**
- 写 `tag`：4-6 字的中文标签
  - 例：情报指挥官、一字 KO、二连暴击、Sona 命名、工头收工

#### 任务 2：project_aliases

**位置**：`project_aliases` 数组里每个项目

**对每个项目做**：
- 读 `first_prompt`（第一句话）
- 写 `alias`：2-6 字的中文别名（覆盖目录名）
  - 例：first_prompt 是"我想做一个网站，目标是筛选..." → alias = "Sona"
  - first_prompt 是"分析礼物业务..." → alias = "礼物周报"
- **如果第一句信息不足以判断主题**，**保留 alias_default 不动**

#### 任务 3：author_followup

**位置**：顶层 `author_followup` 字段

**做什么**：
- 看 `matched_author.name_zh` + 用户三轴 + TOP 口癖 + 徽章
- 把封面作家头像下方的「你呢 😅」换成**贴脸吐槽**（≤20 字）
- 格式：以「{作家名}：」开头，**模仿作家口吻反过来损用户**
  - good → 海明威：我一句没写过 200 字，你一句 300。
  - good → 卡夫卡：起码我没「重做」50 次。
  - good → 博尔赫斯：他迷宫只画一遍，你呢？
  - bad → 加缪：你也很有想法。（褒义禁止）
- **想不出比默认更狠**就保留 `author_followup_default`

#### 任务 4：badges_summary

**位置**：顶层 `badges_summary` 字段（默认空字符串）

**做什么**：
- 看 6 个徽章 + 用户三轴 + 匹配作家
- 写一句**贴脸总结**（≤25 字）：把多个徽章串成一句话「人格速写」，要有反差
  - good → 一个反复推翻的架构师，靠周五一天干完一周的活。
  - good → 视觉强迫症 + 周五战神，组合起来是个偏执的拖延者。
  - bad → 你是一个非常努力且有创造力的人。（鸡汤）
- **不强出**——空字符串 = 不展示这一行

#### 任务 5：outro_pun（终番戏谑句）

**位置**：顶层 `outro_pun` 字段

**做什么**：4-6 行 HTML（`<br>` 分行）写「作家 vs 你」对照
- **第 1 行**：作家身上**最反差的小知识**（不是泛泛字数对比）
- **第 2-4 行**：用用户真实数据（字数、口癖次数、重做次数）写自嘲
- **最后 1 行**：反高潮收尾
- 数字必须从 stats / top_patterns 取，**不能编**

  good 例（博尔赫斯）：
  ```
  博尔赫斯一辈子最长的小说不到 2 万字。<br>
  你用 5.7 万字 vibe 出一个项目——<br>
  说了 16 次「不好」，重做了 11 次，<br>
  「还是没变」念了 50 次。<br>
  但你也真的把它搞出来了。
  ```

- **想不出比默认更戳**就保留 `outro_pun_default`

### 第 4 步：保存 + finalize

把修改后的 data.json 保存到原位置，然后调用：

```bash
python3 <skill 目录>/run.py --finalize <data.json 绝对路径>
```

会产出（同 data.json 所在目录）：
- `index.html`
- `portrait-share.jpg`（约 1.5MB，分享版；需要 Node 截图依赖）
- `portrait-hd.jpg`（约 2.3MB，高清版；需要 Node 截图依赖）

> 没装截图依赖时，HTML 仍会正常输出，JPG 会跳过并打 warning。

### 第 5 步：展示 + 交付

把产物交给用户，**用宿主 agent 自己的方式**——这一步**没有规定工具名**，因为不同 agent 工具集不一样：

- **WorkBuddy**：用 `preview_url` 打开 `index.html`，用 `deliver_attachments` 推两张 JPG
- **Claude Code / Codex CLI**：直接把 `index.html` 的绝对路径告诉用户，让用户在浏览器里打开；JPG 路径一并给出
- **任何 agent**：通用兜底——把产物目录路径列给用户（HTML + 两张 JPG），让用户自己取

**核心原则**：海报已经落到磁盘上，宿主 agent 用任何能用的方式把绝对路径透给用户即可。

## 兜底机制（关键）

每个 LLM 字段都有 `<field>_default` 兜底值。如果你不动 LLM 字段（保持为 `null` 或保持等于 default），渲染时会自动用兜底文案——海报照样能出，只是不那么贴肉。

**所以：当 LLM 写不出比兜底更好的内容时，必须保留兜底。绝对不要为了"显得有 LLM 增强"而瞎写。**

## 跳过 LLM 模式

如果用户明确想"快速跑一个版本"或者你判断 LLM 调用成本太高（比如 token 紧张）：

```bash
python3 run.py --user 恩瑞 --multi 1,3 --skip-llm
```

直接用兜底文案出图，整个 pipeline 一步到位。

## 关键约束

1. **必填昵称才能继续**——第一次跑必须先问
2. **数据完全本地处理**——不上传任何 prompt 内容到任何服务器
3. **章节按规则触发**——数据不足时整章跳过，不要凑数
4. **LLM 增强写不出就保留兜底**——不要为了显示存在感瞎写
5. **诚实**——ctx 里不能编造细节（"当时正在做 X"必须有上下文证据）

## 错误处理

- 没检测到任何 agent → 提示用户检查 `~/.workbuddy/` `~/.claude/` `~/.codex/`
- 选中项目数据 < 5 条 prompt → 提示数据太少
- 生成失败 → 透出 stderr

## Pitfalls（开发踩过的坑，新手别再踩）

1. **静态文案和 LLM 文案要风格一致**——只调 LLM prompt 让 agent 写得狠没用，`assets/badges.json` 里的 evidence_template、`render.py` 里的 desc/ann 也得同步成锐评款。「锐评要做就做全」。
2. **WorkBuddy 5 月起的对话格式有 `<system-reminder>...</system-reminder><user_query>...</user_query>` 包装**——adapter 必须正则剥离，否则会把 system 注入也算成用户字数（漏算/多算几万字）。
3. **timestamps=0 的脏数据**——adapter 里要过滤，否则 earliest 会算成 1970-01-01，span_days 爆表。
4. **Python 3.9 不支持 `Path | None`**——所有类型注解用 `Optional[Path]`。
5. **Bash stdout 中文显示乱码不代表数据真错了**——是 Bash 工具的渲染问题，文件本身 UTF-8 正常。验证数据要 Read 文件，不要 grep 看 stdout。
6. **截图视口不能小于 768**——会触发 v2 的移动端媒体查询，stat-grid 变成单列。Playwright 视口固定 900px，截图时只截 `.poster` 元素去除两侧白边。
7. **PNG 大于 4MB 会被某些客户端拒绝**——sharp 转 mozjpeg quality 88，2x 高清 ~2MB，1500 宽 share 版 ~1.5MB。
8. **「小半本《XX》」语序敏感**——汉语里"《XX》的小半本"读着别扭，正确语序是"小半本《XX》"。
9. **百分比对照很伤气质**——海报里禁用「28% 本《XX》」这种数字，必须用"小半本/半本/大半本/整本/一本半"等人文气词。
10. **加缪不是默认作家**——如果用户匹配距离不算高（< 0.4），caption 仍用最近的作家；旧版海报里固定写"加缪"是 v1 硬编码，v3 完全数据驱动。

## 文档参照

- `SPEC.md` — 产品规则总文档（三轴算法、章节优先级、徽章字典等）
- `README.md` — 给开源/CLI 用户看
- `assets/portraits/_meta.json` — 9 位作家的元数据
- `assets/lexicon.json` — 口癖词典 + 否定词

## 命令行兼容（用户视角）

所有命令都在 skill 目录下跑（路径因 agent 而异，见第 2 步）：

```bash
# 交互式 + 完整两阶段（推荐）
python3 run.py
# 然后 agent 增强 data.json
python3 run.py --finalize <data.json>

# 快速版（跳过 LLM 增强）
python3 run.py --skip-llm

# 跨项目
python3 run.py --multi 1,3,5

# 直接指定 jsonl（不依赖默认 agent 历史检测）
python3 run.py --user 恩瑞 --project /abs/path/file.jsonl --source workbuddy
```
