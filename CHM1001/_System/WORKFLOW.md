# 工作流程规格（CHM1001）

本文件是这套自动化流程的**权威规格**。`README.md` 讲怎么用，本文件讲每一步的输入/输出/判据。

流水线步骤编号与 `_System/scripts/run_pipeline.py` 的打印保持一致：**Step 0 → Step 4**。

---

## 0. 全景

```
                   ┌──────────────────────────────────────────────┐
                   │ Step 0  开工检查（health_check --phase open） │
                   │  Inbox 残留 / 上轮遗留 / 待提炼 / 过期提取物   │
                   │  / 异常文件 / Others 漏判复查                 │
                   └──────────────────┬───────────────────────────┘
                                      ▼
   用户丢文件 ────► ┌──────────────────────────────────────────────┐
                   │  0_inbox/                                      │
                   └──────────────────┬───────────────────────────┘
                                      │ 口令：「处理一下 inbox」
                                      ▼
                   ┌──────────────────────────────────────────────┐
                   │ Step 1  分类（course-inbox-triage）           │
                   │  extension + 文件名关键词 + 内容首段消歧       │
                   │  产出：logs/triage_<ts>.md（先计划，后确认）   │
                   └──┬─────┬──────┬─────┬──────┬──────┬─────┘
                      ▼     ▼      ▼     ▼      ▼      ▼
              2_Textbook  4_Assignment  5_Quiz  1_Syllabus
              &Lecture_PPT/           （作业）（小测）  （大纲）
              6_Midterm Examination/   7_Final Examination/
              3_Essence/               10_Others/
                      │ 口令：「提炼 PPT 知识点」
                      ▼
                   ┌──────────────────────────────────────────────┐
                   │ Step 2  提取（essence-extraction）            │
                   │  pptx/pdf → extracted/<stem>.slides.txt|json │
                   └──────────────────┬───────────────────────────┘
                                      ▼
                   ┌──────────────────────────────────────────────┐
                   │ （模型环节）写作                              │
                   │  3_Essence/<slug>.md（课件名去空格）              │
                   └──────────────────┬───────────────────────────┘
                                      ▼
                   ┌──────────────────────────────────────────────┐
                   │ Step 3  覆盖率自检                            │
                   │  logs/pending_essence.md：还差哪些课件没笔记   │
                   └──────────────────┬───────────────────────────┘
                                      ▼
                   ┌──────────────────────────────────────────────┐
                   │ Step 4  收工核对（health_check --phase close）│
                   │  按 _System/ERROR_LOG.md 的教训逐条核对        │
                   │  回执：[ERROR_LOG 自检] 已过 N 条 / 命中 X 条  │
                   └──────────────────────────────────────────────┘
```

**触发方式说明**：WorkBuddy 端没有文件夹监听器，所以「自动」= 你说一句口令（或跑一次 `run_pipeline.py`），流程即自动跑完。如需无人值守，可把 `run_pipeline.py` 挂到 Windows 计划任务上（见 §8）。

---

## 1. Step 0 — 开工检查（`--phase open`）

**为什么要有这一步**：分类是**有上限的**（单批 10 个）、且有意跳过重复文件与「需人工确认」项。所以「跑过一次分类」**不等于** Inbox 空了。没有开工检查，失败与顺延会被静默吞掉（见 `ERROR_LOG AIE-002`）。

**输入**：整个课程工作区
**产出**：`_System/logs/health_open_<stamp>.md`

| 编号 | 检查项 | 判据 |
|:--|:--|:--|
| O1 | **Inbox 残留** | `0_inbox/` 下是否还有非临时文件；每个给出**预估归类**与理由 |
| O2 | 上一轮未收尾项 | 最新 `triage_*.md` 里是否有 `FAILED` / `SKIP-DUPLICATE` / 顺延条目 |
| O3 | 课件待提炼 | `2_Textbook&Lecture_PPT/` 有、`3_Essence/` 无同名（**按 slug 比**）`.md` 的**课件**（教材/习题解答由 `is_deck()` 排除，见 AIE-024） |
| O4 | 提取物时效 | `_System/extracted/<stem>.slides.txt` 是否比对应课件旧 |
| O5 | 异常文件 | 0 字节文件、散落的 `~$*` / `.lock` / `.tmp` |
| O6 | 漏判复查 | `10_Others/` 里有没有文件名能**明确**归到 `Final/Midterm/PPT/Assignment/Quiz` 的文件 |

**状态语义**：`ℹ️ 待办` 表示「有活要干」（正常），`⚠️ WARN` 表示「有异常要处理」，`❌ FAIL` 表示「环境坏了」。

---

## 2. Step 1 — Inbox 分类

**输入**：`0_inbox/` 下所有文件（递归，含子目录）
**产出**：`_System/logs/triage_<YYYYMMDD-HHMMSS>.md`；执行时另出 `moved_<stamp>.json`

### 判据优先级

| 级别 | 条件 | 目标 |
|:--|:--|:--|
| 1 | `final / finals / 期末 / 期末考试 / 末考` | `7_Final Examination/` |
| 2 | `midterm / mid-term / 期中 / 期中考 / 中段考` | `6_Midterm Examination/` |
| 3 | 测验词（`quiz / quizzes / pop quiz / 小测 / 随堂 / 随堂演练 / 课堂练习`）且无讲次编号、无课件词 | `5_Quiz/` |
| 4 | 作业词（`homework / assignment / hw / lab / report / project / 作业 / 实验报告 / 习题`）且无讲次编号、无课件词 | `4_Assignment/` |
| 5 | 仅泛考试词（`exam / test / 试卷 / 真题 / 考试`），无期中期末标识 | `10_Others/` + **标记需人工确认** |
| 6 | 大纲/非教学类词（`syllabus / course outline / grading policy / 学术诚信 / 教学大纲 / 考核方式`…）且无讲次编号、无课件词 | `1_Syllabus/` |
| 7 | `essence / summary / 笔记 / 知识点 / 提纲` **且扩展名为 `.md`** | `3_Essence/` |
| 7b | 同上但扩展名非 `.md` | `10_Others/` + 标记（见 `ERROR_LOG AIE-001`） |
| 8 | 课件词（`lecture / ppt / chapter / 课件 / 讲义`）或讲次编号（`L03`/`Ch2`/`Week5`）或 `.ppt/.pptx/.key/.odp` | `2_Textbook&Lecture_PPT/` |
| 9 | 教材词（`textbook / 教材 / 课本`） | `2_Textbook&Lecture_PPT/`（**与课件同一目录**，见 AIE-024） |
| 10 | 以上全不中 → 读正文首段（前 4 页/6 张）找 Midterm/Final/Lecture 特征 | 对应分类 + **标记需复核** |
| 11 | 兜底 | `10_Others/` |

> `quiz` 已从泛 `exam` 里**拆出来**（AIE-024）：`Quiz 1.pdf` 进 `5_Quiz/`，不再被当成「未标明期中/期末 → 需人工确认」。
> `Textbook/` 已并入 `2_Textbook&Lecture_PPT/`（AIE-024）：「教材不是课件」改由 `non_deck_keywords` + `is_deck()` 判定。

**匹配语义**：英文关键词**整词**匹配（`Midterm` 不会因含 `mid` 误伤）；也接受「关键词+数字」的紧凑写法（`assignment2` / `hw3` / `quiz1` / `lab1`）；中文关键词**子串**匹配；多词短语按归一化整串匹配（`course outline`）。

### 跳过规则

`~$*`（Office 锁文件）、`._*`、`.tmp/.part/.crdownload/.lock/.lnk`、`Thumbs.db`、`desktop.ini`、隐藏文件。

### 冲突与重复

- **同名冲突**（目标已有同名但内容不同）→ 自动改名为 `<stem> (2).ext`。
- **内容重复**（目标已有或同批中存在 sha256 相同文件）→ **跳过 + 标记**，不删不合并，交人工。

### 安全约束

| 约束 | 值 |
|:--|:--|
| 默认模式 | dry-run（只出计划） |
| 真正移动 | 需 `--apply`（且需用户口头确认） |
| 删除操作 | **不存在** |
| 单批上限 | 10（`--batch-size N` 调整，`--all` 解除） |
| 回滚 | `--undo <stamp>`，依据 `moved_<stamp>.json` 反向移动 |

---

## 3. Step 2 — 课件原文提取

**输入**：`2_Textbook&Lecture_PPT/` 下 `.pptx / .pdf / .docx`（`--deck` 可指定单份）
**产出**：
- `_System/extracted/<stem>.slides.txt` — 逐张文本，分页标记 `===== SLIDE n =====`，含 `[TITLE]` / `[TABLE n]` / `[NOTES]` / `[IMAGES]`
- `_System/extracted/<stem>.slides.json` — 同内容机读版
- `_System/logs/extract_<stamp>.md` — 成功 / 跳过 / **无法解析** 清单

### 为什么必须先提取

直接「看」PDF/PPT 会让模型捏造章节名和术语。提取文本是笔记的**唯一事实基础**，写笔记时每个结论都能指到具体张号（见 `ERROR_LOG AIE-008`）。

### 无法解析的情况（如实报告，不猜）

| 情况 | 处理 |
|:--|:--|
| 旧版 `.ppt` | python-pptx 读不了 → 报告里列出，提示另存为 `.pptx` |
| 扫描件 PDF | 提取文本为空 → 报告标注「疑似扫描件，需 OCR」 |
| 加密/损坏 | 报告列出异常信息 |

> ⚠️ 课件被**同名覆盖**后，已有提取物不会自动刷新（脚本默认跳过已存在的产物）——需 `--force`；`O4` 检查专门负责发现这种情况（见 `ERROR_LOG AIE-004`）。

---

## 4. 模型环节 — 写 Essence 笔记

**输入**：`_System/extracted/<stem>.slides.txt`
**产出**：`3_Essence/<slug>.md`（`<slug>` = 课件名去掉空格/特殊字符后的形式，中文保留；PPT 原文件不改名）

> ⚠️ **笔记名与图表目录都不含空格**（AIE-022）：Markdown 链接目标里出现空格会被渲染器在第一个空格处
> 截断，导致**整篇的图全部不显示**，文件名里的空格还会让预览按空格截断、文档打不开。
> `extract_slides.py` 的 `slug()` 是唯一实现，图表目录 `3_Essence/figures/<slug>/`、笔记名都过它。

结构见 `~/.workbuddy/skills/essence-extraction/references/essence_format.md`。要点：

- frontmatter：`course / source / slides / extracted / tags`
- 一句话主旨 → 分主题列表（紧凑，信息密度优先）→ 关键术语表 → 易错点/待核实 → **`## 出处索引`（标到张号，必须是 Markdown 标题）**
- **英文名优先**：每个术语、每个重点区域（小节标题）都必须带英文名，中英并存时**英文在前**
  （`## 波长与频率（Wavelength and Frequency）`、`Wavelength（波长）`）；英文名取自提取文本，**不自行翻译**
- **公式只存在于图内、文本没有时**：正文该处**只写** `<u>公式在图内</u>`（下划线），并在**文末**
  `## 公式在图内（提取文本丢失）` 逐条列 `- 第 N 张：公式在图内、提取文本丢失`；**禁止**凭图补公式
- 公式保留 LaTeX；不确定标 `[待核实]`；**图必须贴在对应知识点正下方**（不许堆文末、不许只写「见图」）
- 一份课件一个文件；已有用户手改版本先问再动

> 这一步**无法脚本化**，由模型读提取文本后写作。若要换模型，用 `_System/prompts/02_essence_extraction.md`。

### 4.1 收尾必问（对话场景的流程终点动作）

流程跑完（**Step 4 收工核对之后**），模型**必须在给用户的最终回复末尾主动问一次**：

> 是否直接提炼 PPT 知识点？（当前 `2_Textbook&Lecture_PPT/` 待提炼 **N** 份：`a`、`b`）

| 规则 | 说明 |
|:--|:--|
| 每次都问 | 不问即视为流程未走完 |
| 带数量 | 必须附当前待提炼份数；为 0 时写明「当前 `2_Textbook&Lecture_PPT/` 无待提炼课件」 |
| 只问不做 | **不擅自开始写笔记**——写笔记耗时且产出文件，须用户点头 |
| 仅限对话 | 定时自动化无人在场，**不发问**（§8.1），只回一行即退出 |
| 答「是」后 | 转入 `essence-extraction` skill 逐份生成 |

`run_pipeline.py` 在收尾会打印一条 `⚠️ 终点动作` 提示，供模型据此发问。

---

## 5. Step 3 — 覆盖率自检

`run_pipeline.py` 对比 `2_Textbook&Lecture_PPT/` 与 `3_Essence/` 的文件名集合：

- `待提炼` = PPT 有、Essence 没有 → 需要生成笔记
- `无对应课件的笔记` = Essence 有、PPT 没有 → 课件可能改名/删除了

报告写入 `_System/logs/pending_essence.md`。

---

## 6. Step 4 — 收工核对（`--phase close`）

**输入**：`_System/ERROR_LOG.md` + 当前工作区状态
**产出**：`_System/logs/health_close_<stamp>.md`

脚本从 ERROR_LOG 抽取全部 `AIE-nnn` 条目，对每条执行登记的自动核对，输出固定回执：

```
[ERROR_LOG 自检] 已过 N 条 / 命中 X 条
```

| 编号 | 教训 | 核对判据 |
|:--|:--|:--|
| AIE-001 | 3_Essence/ 混入非 .md 素材 | `3_Essence/` 下除 `00_Index.md` 外只有 `.md` |
| AIE-002 | Inbox 残留无人发现 | `0_inbox/` 无残留正经文件 |
| AIE-003 | 课件 ↔ 笔记覆盖率 | 每份 `2_Textbook&Lecture_PPT/` 课件都有同名（**按 slug 比**）的 `3_Essence/*.md` |
| AIE-004 | 提取物未刷新 | 提取物 mtime ≥ 课件 mtime |
| AIE-005 | 移动清单被覆盖 | 每份 `APPLY` 报告都有同 stamp 的 `moved_*.json` |
| AIE-006 | 日志被改成二进制 | `logs/` 下文件均可 UTF-8 解码且不以 `PK` 开头 |
| AIE-007 | Edit 静默丢失 | 全部脚本 `ast.parse` 通过；无 `__pycache__` 残留 |
| AIE-008 | 笔记缺出处索引 | 每份笔记含 `## 出处索引` **标题** |
| AIE-009 | 报告显示内部键名 | 分类表「目标文件夹」列均以 `/` 结尾 |
| AIE-010 | 核对逻辑过松 | 👤 **无自动核对**（属核对逻辑自身质量），需人工复核 |
| AIE-011 | 自动化静默停摆 | 心跳文件存在且 mtime ≤ 3 天（首次写入只报待办） |
| AIE-017 | 笔记 ↔ 图表双向对齐 | 断图 FAIL；已渲染却未被引用 WARN |
| AIE-018 | 目录名硬编码 | 税表声明的每个内容目录都存在 |
| AIE-019 | 首次心跳误报 | 故障注入：真缺失仍 WARN、首次写入不报警、超期仍 WARN |
| AIE-020 | 术语缺英文名 | 每个小节标题含 ≥2 连续英文字母；术语表英文优先 |
| AIE-021 | 「公式在图内」无固定写法 | 正文下划线段数 == 文末清单条数，且该节在全文最末 |
| AIE-022 | 生成物路径含空格 | 图片链接语法合法、相对、指向真实文件；slug 两个实现无漂移 |
| AIE-023 | 生成物逃出课程目录 | 学期父目录下无 `figures/` 之类裸产物目录（含故障注入自测） |
| AIE-024 | 目录改名/合并未同步 | `textbook` 与 `slides` 指向同一目录；教材探针判为**非**课件 |
| AIE-025 | 打包交接时空目录丢失 | 👤 无自动核对（针对交付物）；解压后跑一次 `--phase both`，AIE-018 会报出缺失目录 |

**状态语义**：`✅ PASS` / `ℹ️ 待办` / `⚠️ WARN` / `❌ FAIL` / `— N/A` / `👤 需人工核对`

**退出码**：`0` 全绿；`3` 有需关注项；`4` 有严重问题。

---

## 7. ERROR_LOG 规则（强制）

`_System/ERROR_LOG.md` 是本工作区的**过往教训库**，也是流程核对的**唯一事实源**。

1. **开工前**通读一遍，确认没有「上一次没干完的活」。
2. **收工后**由 `health_check.py --phase close` 逐条自动核对。
3. **发现问题 → 先修复 → 再把问题与教训收录进 ERROR_LOG**。这是硬性要求。
4. 新增教训格式：
   - 标题必须是 `## AIE-nnn — 标题 [严重|中等|低]`（三位编号递增，脚本靠它抽取条目）
   - 正文写清 `场景 / 问题 / 根因 / 纠正 / 教训 / 核对项`
   - 若可自动核对，去 `health_check.py` 的 `LESSON_CHECKS` 里登记同 ID 的核对函数
   - **没登记的条目会被标为「👤 需人工核对」，绝不会被静默跳过**；反之，脚本登记了但 ERROR_LOG 已删除的 ID 会被标为「🕳 登记失效」
5. **新增自动核对项后，必须做故障注入测试**——故意造出该缺陷，确认它真的报警。只会 PASS 的检查等于没有检查（见 `ERROR_LOG AIE-010`）。

---

## 8. 自动化：让流程自己跑起来

### 8.1 已配置的 WorkBuddy 定时自动化（覆盖 Step 3 写笔记）

| 项 | 值 |
|:--|:--|
| 名称 | `CHM1001 课件自动提炼 Essence` |
| ID | `fd62caf2-fccc-4afb-9bd5-5b57351534bf` |
| 频率 | **每周六 00:15** |
| 作用域 | 仅本课程工作区 |
| 注册日期 | 2026-09-17（本机首次正式登记） |
| 心跳 | 每次运行写 `_System/logs/automation_heartbeat.json` |

> ⚠️ **2026-09-17 更正**：旧版这里记的 ID 是 `4c0bc2b5-…`、首次运行「2026-09-14 21:45」——
> 那是**母版 AIE2040 上的记录**，随文档一起被复制了过来。本机（`D:\Courses`）此前**从未真正注册过**
> 这条自动化（`automations` 表为空），而 `AIE-011` 的心跳检查又一直报绿，因为**心跳文件从没被写过、
> 检查便无从报警**。这正是 AIE-011 想防的「配置过一次 ≠ 一直在跑」——只是这一次，它连「配置过」
> 都没发生过。现已按实际登记并回填真实 ID。

#### ⚠️ 调度规则限制（AIE-012，必读）

写 `rrule` 时**只能给单个整点**：

```
✅ FREQ=WEEKLY;BYDAY=SA;BYHOUR=0;BYMINUTE=15     ← 正确：单个 BYHOUR
❌ FREQ=DAILY;BYHOUR=12,21;BYMINUTE=30           ← 错误：多值 BYHOUR，创建直接失败
```

后端会报 `invalid recurring rrule: BYHOUR must be an integer between 0 and 23`。
**多值只对 `BYDAY` / `BYMONTHDAY` 生效**，`BYHOUR` 不行——这是实现限制，与 RRULE 规范无关。

想「一天跑两次」怎么办：**建两条自动化**（各自单整点），或改用 `FREQ=HOURLY;INTERVAL=n`
靠间隔覆盖。不要试图往一个 `BYHOUR` 里塞多个值。

本限制由收工核对的 **AIE-012** 自动守卫（它会检查本条文档是否还在）。

**为什么必须是 WorkBuddy 自动化**：Step 3（读提取文本 → 写 Essence 笔记）**必须模型介入**，纯脚本做不到。WorkBuddy 的定时自动化会带着模型一起跑，所以这是唯一能真正把「写笔记」也自动化的机制。

自动化的行为约定：

- **有课件待提炼** → 提取原文 → 写 `3_Essence/<同名>.md` → 更新 `3_Essence/00_Index.md` → 写心跳 → 回执
- **无待办** → **只回一行即退出**（幂等，不刷屏、不浪费）
- **禁止 `--apply`**：移动/归档 `0_inbox` 里的文件必须由你本人确认，自动化只做「PPT → Essence」与只读检查
- 发现流程问题必须回写 `_System/ERROR_LOG.md`（见 §7）

**存活验证**：收工核对的 **AIE-011** 检查 `automation_heartbeat.json`——超过 3 天没有心跳就报 `⚠️ WARN`（说明自动化被暂停、删除，或执行失败）。这条检查的存在本身就是教训（见 `ERROR_LOG AIE-011`）：*「配置过一次」不等于「一直在跑」。*

> ⚠️ 局限：定时自动化不是文件监听器，所以「课件落进 `2_Textbook&Lecture_PPT/`」到「笔记生成」之间**最多有一周延迟**（每周六 00:00 之前丢进去的，那一轮处理）。想更快可临时喊一句「提炼 PPT 知识点」，或把频率调密——但会更频繁地唤起模型。

### 8.2 可选：Windows 计划任务（只覆盖 Step 0–3，不含写笔记）

若希望「丢进 `0_inbox/` 后自动分类」，可用计划任务定时触发（比如每 30 分钟）：

```powershell
# ⚠️ 下面两个路径必须换成本机实际路径（此为示例）
$PY = "D:\Courses\CHM1001\.venv\Scripts\python.exe"
$ROOT = "D:\Courses\CHM1001"

$action  = New-ScheduledTaskAction -Execute $PY `
           -Argument "`"$ROOT\_System\scripts\run_pipeline.py`" --root `"$ROOT`" --apply"
$trigger = New-ScheduledTaskTrigger -Once -At (Get-Date) -RepetitionInterval (New-TimeSpan -Minutes 30)
Register-ScheduledTask -TaskName "CHM1001-Course-Pipeline" -Action $action -Trigger $trigger -Description "CHM1001 课程材料自动分类与提取"
```

> ⚠️ 注意：`--apply` 意味着**无需确认即移动文件**。若不放心，去掉 `--apply`（只出计划），或把上限压到 `--batch-size 5`。
> 这条计划任务**只覆盖 Step 0–3**（检查 / 分类 / 提取 / 覆盖率），**不含写笔记**——写笔记请交给 §8.1 的 WorkBuddy 自动化。

### 8.3 三种触发方式对照

| 方式 | 覆盖范围 | 延迟 | 是否推荐 |
|:--|:--|:--|:--|
| 口令（「提炼 PPT 知识点」） | Step 0–4 全流程 | 即时 | ✅ 默认 |
| WorkBuddy 定时自动化 | Step 0–4（含写笔记） | ≤7 天（每周六凌晨；急用请喊口令） | ✅ **已配置** |
| Windows 计划任务 | Step 0–3（不含写笔记） | 自定义 | ⭕ 可选 |

---

## 9. 换课复用

整目录拷贝即可。两个 skill 通过「含 `_System/taxonomy.json`」（其次「含名字带 `inbox` 的目录」）自动识别课程根，不需要改代码；只需按新课程命名习惯调整 `_System/taxonomy.json` 的 `folders`。
> ⚠️ 旧判据「同时含 `Inbox/` 与 `PPT/`」**已废弃**——目录改名/合并后它会永远认不到课程根（AIE-024）。
`_System/ERROR_LOG.md` 建议先清空（只留使用规则与空表格），因为旧课的教训未必适用。

---

## 10. 变更记录

| 日期 | 变更 |
|:--|:--|
| 2026-09-14 | 首版：目录结构 + 两个 skill（course-inbox-triage / essence-extraction）+ run_pipeline 编排 + 跨平台 prompt；冒烟测试通过（分类/移动/回滚/提取/覆盖率五条链路） |
| 2026-09-14 | 新增 **Step 0 开工检查**（O1–O6）与 **Step 4 收工核对**（AIE-001 ~ AIE-010），落地为 `_System/scripts/health_check.py` 并接入 `run_pipeline.py`；建立 `_System/ERROR_LOG.md`（10 条教训）；故障注入测试 15/15 通过 |

| 2026-09-14 | 本工作区由 **AIE2040** 整套流程复制而来：继承 ERROR_LOG 的 AIE-001~016（流程级教训）；独立配置自动化 `CHM1001 课件自动提炼 Essence`（ID `4c0bc2b5-8e8f-4132-8e00-a26a2c2b0993`，每天 21:45，与 AIE2040 的 21:30 错开避免同时唤起模型）。本课程新增教训请从 **AIE-017** 起编号。**（⚠️ 此行所记自动化实为母版记录，本机未注册——见 2026-09-17 条目）** |
| 2026-09-17 | **框架全面体检与修复**（本次）：① 真正注册本机自动化（真实 ID `fd62caf2-fccc-4afb-9bd5-5b57351534bf`，每周六 00:15）——此前 `automations` 表为空；② `§8.1` 补上多值 `BYHOUR` 限制的真实说明（此前只存在于 ERROR_LOG 的**虚假声称**里）；③ 新增 **AIE-028**，并把 AIE-010/012/013/015/016/025 六条从「需人工」升级为**自动核对**（各带故障注入），`LESSON_CHECKS` 21 → 28 条；④ 7 个空目录补占位文件（AIE-025）；⑤ 引入 `is_placeholder()` 统一排除占位文件，消除 AIE-002 假警报 |
