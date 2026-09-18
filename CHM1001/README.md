# CHM1001 · 课程自动化学习流程

> ℹ️ 本工作区由 **AIE2040** 的整套流程复制而来（见 `_System/ERROR_LOG.md` 头部继承说明）。

把课程材料丢进 `0_inbox/`，剩下的交给模型和脚本：**开工检查 → 自动分类 → 自动提取课件原文 → 自动生成同名知识点笔记 → 收工核对**。

## 目录结构

```
CHM1001/
├── README.md                  ← 本文件
├── 0_inbox/                     ← 所有未处理的课程材料先丢这里
├── 1_Syllabus/                  ← 教学大纲 + 全部课程非教学内容（评分/考核/课表/学术诚信）
├── 2_Textbook&Lecture_PPT/      ← 课件 + 教材（**已合并**：讲义 PPT 与教材 PDF 同目录）
├── 3_Essence/                   ← 每份课件对应的同名（slug 化）.md 知识点笔记（+ figures/）
├── 4_Assignment/                ← 课程作业（homework / assignment / lab / project / 习题）
├── 5_Quiz/                      ← 小测 / 随堂演练 / 课堂练习
├── 6_Midterm Examination/       ← 期中试卷、答案
├── 7_Final Examination/         ← 期末试卷、答案
├── 10_Others/                   ← 其他（无法归类的）
└── _System/                   ← 引擎，平时不用动
    ├── ERROR_LOG.md           ← ⭐ 过往教训库 + 流程核对的唯一事实源（25 条 AIE-001~025，AIE-025 已同步）
    ├── taxonomy.json          ← 分类税表：关键词、文件夹名，可自由编辑
    ├── WORKFLOW.md            ← 完整流程规格
    ├── prompts/               ← 跨平台 prompt（ChatGPT / Claude / DeepSeek / OpenAI）
    ├── scripts/
    │   ├── run_pipeline.py    ← 一键编排（含开工检查与收工核对）
    │   └── health_check.py    ← 健康检查：--phase open 开工 / --phase close 收工 / --beat 写心跳
    ├── extracted/             ← 课件提取出的纯文本（笔记的事实基础）
    └── logs/                  ← 每次运行的报告 + 可回滚的移动清单 + 自动化心跳
```

## 怎么用（四条口令）

| 你想干什么 | 对 WorkBuddy 说 | 实际发生什么 |
|:--|:--|:--|
| **先看有没有残留的活** | **「开工检查」** | 扫 `0_inbox/` 残留、上轮遗留、待提炼课件、过期提取物、异常文件 |
| 分类新丢进来的材料 | **「处理一下 inbox」** | 先开工检查 → 扫 `0_inbox/` 出分类计划给你确认 → 你点头后移动 → 收工核对。作业 → `4_Assignment/`，小测/随堂演练 → `5_Quiz/` |
| 把课件变成笔记 | **「提炼 PPT 知识点」** | 提取 `2_Textbook&Lecture_PPT/` 里课件的全文与备注，逐份生成 `3_Essence/<同名>.md` |
| 一键跑完整条流水线 | **「跑一遍课程流程」** | 开工检查 → 分类（dry-run）→ 提取 → 覆盖率自检 → 收工核对 |
| 生成/补全课程纲要 | **「生成 Outline of CHM1001」** | 合并 `1_Syllabus/` 与 `2_Textbook&Lecture_PPT/`，补全根目录的 `Outline of CHM1001.md` |
| 部署到另一门课 | **「创建 XXX 文件夹」** | 用 `course-workspace-bootstrap` 一键复制整套工作流到新课程 |

> 💬 **收尾一问**：每次跑完「处理一下 inbox」，我都会在回复末尾主动问一句「**是否直接提炼 PPT 知识点？**」并附上当前待提炼份数——你回一句就行，不用自己想起来。
>
> （这条只用于对话场景；定时自动化无人在场，不会发问。）

也可以直接手跑脚本：

```bash
PY="D:/Courses/CHM1001/.venv/Scripts/python.exe"   # 本机解释器（需 python-pptx / PyMuPDF / python-docx）

# 0) 开工检查（动手前先看有没有上一次没干完的活）
"$PY" "_System/scripts/health_check.py" --root "." --phase open

# 1) 全流程：分类先看计划
"$PY" "_System/scripts/run_pipeline.py" --root "."
# 2) 全流程：确认后执行分类（会写可回滚清单）
"$PY" "_System/scripts/run_pipeline.py" --root "." --apply
# 3) 只做开工检查 + 收工核对，不碰文件
"$PY" "_System/scripts/run_pipeline.py" --root "." --check-only
# 4) 只想看还差哪些课件没笔记
"$PY" "_System/scripts/run_pipeline.py" --root "." --essence-only
```

## 自动化：课件丢进去，笔记自己出来

**已配置一条 WorkBuddy 定时自动化**，不用你开口：

| 项 | 值 |
|:--|:--|
| 名称 | `CHM1001 课件自动提炼 Essence` |
| 频率 | **每周六 00:15** |
| 干什么 | 找 `2_Textbook&Lecture_PPT/` 里缺同名 `.md` 的课件 → 提取原文 → 写 `3_Essence/<同名>.md` → 更新索引 → 收工核对 |
| 没事时 | 只回一行「本轮无待提炼课件」就退出（不刷屏） |
| 不会做 | **绝不移动 / 删除 `0_inbox` 里的文件**（那必须你本人确认） |
| 心跳 | 每次运行写 `_System/logs/automation_heartbeat.json` |

把课件拖进 `2_Textbook&Lecture_PPT/`，下一轮（周六凌晨）笔记就会自己出现。急用的话直接说「提炼 PPT 知识点」，即时处理。

> ⚠️ 它是**定时**触发，不是文件监听，所以最坏情况有 **一周延迟**。想更快可以直接说「提炼 PPT 知识点」即时处理。

## 开工检查 & 收工核对

这是**内置的两道闸门**，属于流程的一部分，不是可选项。

**开工检查（`--phase open`，O1–O6）** —— 动手之前先盘点：

| 编号 | 查什么 |
|:--|:--|
| O1 | `0_inbox/` 有没有残留的 PPT 等文件（附**预估归类**） |
| O2 | 上一轮有没有没干完的活（移动失败 / 内容重复待决 / 顺延未消化） |
| O3 | 有没有课件还没生成 Essence 笔记 |
| O4 | 课件更新过、但提取物还是旧的（会导致笔记基于过期内容） |
| O5 | 0 字节文件、散落的 Office 锁文件 |
| O6 | `10_Others/` 里有没有其实能明确归类的文件（漏判复查） |

**收工核对（`--phase close`）** —— 干完活按教训逐条核对：

脚本读取 `_System/ERROR_LOG.md` 里的每条教训编号，执行对应的自动核对，输出固定回执：

```
[ERROR_LOG 自检] 已过 25 条 / 命中 X 条
```

- 结果状态：`✅ PASS` / `ℹ️ 待办`（正常作业，非故障）/ `⚠️ WARN` / `❌ FAIL` / `— N/A`
- 有 `❌ FAIL` 时退出码为 **4**，有 `⚠️ WARN` 为 **3**，全绿为 **0**

## ERROR_LOG 规则（强制）

`_System/ERROR_LOG.md` 是本工作区的**过往教训库**，也是流程核对的**唯一事实源**。

1. **开工前**通读一遍，确认没有「上一次没干完的活」。
2. **收工后**由 `health_check.py --phase close` 逐条自动核对。
3. **发现问题 → 先修复 → 再把问题与教训收录进 ERROR_LOG**。这是硬性要求，不是可选项。
4. 新增教训的格式：标题必须是 `## AIE-nnn — 标题 [严重|中等|低]`，正文写清 `场景 / 问题 / 根因 / 纠正 / 教训 / 核对项`。
   若该条能自动核对，再去 `health_check.py` 的 `LESSON_CHECKS` 里登记同 ID 的核对函数。
   **没登记的条目会被标为「👤 需人工核对」，绝不会被静默跳过。**

## 安全承诺（重要）

- **默认只出计划，不动文件**。必须显式确认才会移动。
- **永不删除**。只做移动；重复文件只标记、交你决定。
- **可一键回滚**。每次移动都写 `_System/logs/moved_<时间戳>.json`：
  ```bash
  "$PY" "$HOME/.workbuddy/skills/course-inbox-triage/scripts/triage_inbox.py" --root "." --undo <时间戳>
  ```
- **单批上限 10 个文件**，超出自动顺延，避免一次性大动作。
- **笔记不臆造**。所有内容先由脚本从课件里提取成文本，笔记只从那份文本写；不确定的标 `[待核实]`，且每份笔记必须有 `## 出处索引`。

## 配套 Skill（已装在用户级，所有课程通用）

| Skill | 触发词 | 作用 |
|:--|:--|:--|
| `course-inbox-triage` | 处理一下 inbox / 整理课程资料 | Inbox 分类器（开工检查为首个必做步骤） |
| `essence-extraction` | 提炼 PPT 知识点 / 生成 Essence | 课件 → 同名 Markdown 笔记 |
| `course-workspace-bootstrap` | 创建 XXX 文件夹 / 部署到 X 课程 | 一键把整套工作流复制到新课程 |

按 `_System/WORKFLOW.md` 的规格执行；税表在 `_System/taxonomy.json`，改完立即生效。

## 换一门课怎么办

把这套 `README.md + _System/ + 内容文件夹` 整个拷到新课程目录即可（或直接用 `course-workspace-bootstrap` skill 一键部署）：

- 两个 skill 会自动探测「含 `_System/taxonomy.json`」的目录（其次「含名字带 `inbox` 的目录」），无需改任何代码
  - ⚠️ 旧判据「同时含 `Inbox/` 与 `PPT/`」已废弃（目录改名/合并后会永远认不到课程根，见 AIE-024）
- `_System/ERROR_LOG.md` 建议**清空重来**（只保留使用规则与空表格），因为旧课的教训未必适用；也可保留通用条目
- 按新课程的命名习惯微调 `_System/taxonomy.json`
