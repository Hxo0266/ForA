---
name: course-inbox-triage
description: This skill should be used when the user asks to process, sort, classify, file, or clean up a course Inbox folder of study materials — for example "处理一下inbox", "处理inbox", "整理课程资料", "把inbox里的文件分类", "归档课件和试卷", "开工检查", "process my course inbox", "triage these lecture files". It runs a pre-flight check on the course workspace (leftover files still sitting in 0_inbox from a previous run, decks awaiting notes, stale extractions, junk files, misclassified files in 10_Others), then scans every file in 0_inbox, decides which category each one belongs to (lecture slides & textbook, distilled notes, homework/assignment, quiz/pop-quiz, midterm paper or answers, final paper or answers, syllabus, or miscellaneous) using file extension plus filename keywords plus an optional content peek, moves each file into the matching sibling folder (2_Textbook&Lecture_PPT / 3_Essence / 4_Assignment / 5_Quiz / 6_Midterm Examination / 7_Final Examination / 1_Syllabus / 10_Others), writes a Markdown triage report, and closes with an ERROR_LOG-based process check. Folder names are always resolved from _System/taxonomy.json, never hard-coded. It never deletes anything and every move is undoable.
agent_created: true
---

# Course Inbox Triage

## 用途

把一份「课程工作区」里 `0_inbox/` 的杂乱材料，按类别自动归位到同级文件夹。**只移动，不删除**；每次移动都可回滚。

流程两端各有一道闸门，都不是可选项：

- **开工检查**（动手前）：盘点 `0_inbox/` 残留与工作区异常
- **收工核对**（干完活）：按 `_System/ERROR_LOG.md` 的教训逐条核对

## 何时使用

当用户说出下列任何一类意图时使用：

- 「处理一下 inbox」「处理 inbox」「清一下收件箱」「开工检查」
- 「整理课程资料」「把 inbox 里的文件分类」「归档这些课件/试卷」
- 「process my course inbox」「sort these lecture files into folders」

**不适用**：用户只是想「看看 inbox 里有什么」（那么只列清单、不做任何移动）；或目标目录不是课程工作区结构（没有 `0_inbox/`，也没有 `_System/taxonomy.json`）。

## 课程工作区结构（前置假设）

```
<course_root>/
├── 0_inbox/                    ← 待分类材料入口
├── 1_Syllabus/                 ← 教学大纲 + **全部课程非教学内容**（评分标准、考核方式、课表、学术诚信、教师信息…）
├── 2_Textbook&Lecture_PPT/     ← 课件 + 教材（**已合并**：教材 PDF 与讲义 PPT 同目录）
├── 3_Essence/                  ← 每份课件对应的同名知识点提炼（.md）+ figures/
├── 4_Assignment/               ← 课程作业（homework / assignment / lab report / project / 习题）
├── 5_Quiz/                     ← 小测 / 随堂演练 / 课堂练习
├── 6_Midterm Examination/      ← 期中试卷/答案
├── 7_Final Examination/        ← 期末试卷/答案
├── 10_Others/                  ← 其他
└── _System/
    ├── ERROR_LOG.md            ← 过往教训库 + 流程核对的唯一事实源
    ├── taxonomy.json           ← 分类税表（**目录名的唯一事实源**，关键词可编辑）
    ├── scripts/run_pipeline.py ← 一键编排
    ├── scripts/health_check.py ← 开工检查 / 收工核对
    ├── extracted/              ← 课件提取产物（中间件）
    └── logs/                   ← triage / extract / health 报告 + 移动清单
```

⚠️ **目录名一律从 `_System/taxonomy.json` 的 `folders` 解析，代码里不得硬编码**（见 `ERROR_LOG AIE-018` / `AIE-024`）。用户可自由改名（例如把 `0_inbox` 改成 `收件箱`），改完**只需同步税表**；改完必须跑一遍收工核对，让 AIE-018 核对项确认税表与磁盘一致。

`<course_root>` 可显式传 `--root`，也可省略——脚本会从当前目录向上自动探测「含 `_System/taxonomy.json`」或「含名字带 `inbox` 的目录」的目录。

> ⚠️ 旧判据「同时有 `Inbox/` 与 `PPT/`」**已废弃**（改名合并后会永远认不到课程根，AIE-024）。

## 执行步骤（严格按序）

### Step 0 — 开工检查（必须先做，别跳过）

```bash
python "<course_root>/_System/scripts/health_check.py" --root "<course_root>" --phase open
```

检查 O1–O6：**Inbox 残留**（附预估归类）、上一轮未收尾项、课件待提炼、提取物过期、异常文件、`Others/` 漏判复查。

把结果**直接讲给用户**，特别是：

- `O1` 里 Inbox 还剩什么（这就是本次要处理的量）
- `O2` 里上次有没有 **移动失败** 或 **重复待决**——这两类没人管就会一直躺着
- `✖ 有严重问题` 时**先停下来报告**，不要继续跑分类

若 `health_check.py` 不存在（老旧工作区），跳过并在回执里说明。

### Step 1 — 出计划（默认，不动文件）

```bash
python "<skill_dir>/scripts/triage_inbox.py" --root "<course_root>"
```

不加 `--apply` 时是 **dry-run**：只打印并写出 `_System/logs/triage_<stamp>.md`，不移动任何文件。

### Step 2 — 把计划念给用户，等确认

把报告里的**三块**摘出来讲清楚：① 文件 → 目标文件夹的映射；② 被标记为「需人工确认」的项（泛考试关键词、内容探测判定、重复文件）；③ 顺延到下一批的项。

**必须等用户明确同意后才进入 Step 3。** 若用户改了口径（比如「`exam` 开头的都放进 Midterm」），先改 `_System/taxonomy.json` 的关键词，再重跑 Step 1。

### Step 3 — 执行

```bash
python "<skill_dir>/scripts/triage_inbox.py" --root "<course_root>" --apply
```

单批默认最多 10 个文件（安全上限）。剩余文件会列入报告的「顺延」区，再跑一次即可；文件很多且用户明确同意时可用 `--all`。

### Step 4 — 回执与收尾

- 报告移动到哪几个、每个文件夹各收了多少
- 明确列出**未处理**的文件与原因（重复、需确认、顺延）
- 如用户要求撤回：`python "<skill_dir>/scripts/triage_inbox.py" --root "<course_root>" --undo <stamp>`
  （`<stamp>` 形如 `20260914-160602`，秒级；在报告文件名与终端回执里都能拿到）

### Step 5 — 收工核对（干完活必做）

```bash
python "<course_root>/_System/scripts/health_check.py" --root "<course_root>" --phase close
```

脚本读取 `_System/ERROR_LOG.md` 的全部 `AIE-nnn` 教训，逐条执行自动核对，输出固定回执：

```
[ERROR_LOG 自检] 已过 N 条 / 命中 X 条
```

**回执必须出现在给用户的最终回复里。** 有 `❌ FAIL` 时先修再回复；有 `👤 需人工核对` 的条目要人工比对一遍。

### Step 6 — 新问题回写 ERROR_LOG（硬性要求）

若本轮**发现或修好了任何流程问题**（用户的反馈、你自己踩的坑、检查报出的异常），必须把「问题 + 根因 + 纠正 + 教训 + 核对项」写进 `_System/ERROR_LOG.md`：

- 标题用 `## AIE-nnn — 标题 [严重|中等|低]`，编号在现有基础上递增
- 若该条能自动化核对，去 `health_check.py` 的 `LESSON_CHECKS` 登记同 ID 的核对函数
- 登记后**必须做故障注入测试**（故意造出该缺陷，确认真的报警）——只会 PASS 的检查等于没有检查

### Step 7 — 收尾自动询问（对话场景必做）

**每处理完一次 Inbox，都必须主动问一次**，附在最终回复的最后：

> 是否直接提炼 PPT 知识点？（当前 `2_Textbook&Lecture_PPT/` 待提炼 **N** 份：`a`、`b`）

规则：

1. **每次都要问，不问就是漏了流程**——不要等用户自己想起来。
2. **必须带上当前待提炼数量**，让用户一眼判断值不值得顺手做；为 0 时写「当前 `2_Textbook&Lecture_PPT/` 无待提炼课件」。
3. **只问，不要擅自开始提炼**。写笔记耗时且会产出文件，必须等用户点头。
4. **仅限对话场景**。定时自动化里没有人在等回答，**不要在那里发问**——自动化只回一行就退出。
5. 用户答「是 / 直接做」→ 转入 `essence-extraction` skill；答「不用」→ 正常结束，不要追问第二次。

## 硬规则

1. **先开工检查，再动手**。跳过 Step 0 就等于放弃了「上一次没干完的活」的可见性。
2. **默认 dry-run**。没有用户确认，绝不加 `--apply`。
3. **绝不删除**。只做同卷 `move`；重复文件只标记、不删、不合并。
4. **移动即留痕**。每次 `--apply` 写 `_System/logs/moved_<stamp>.json`，保证可 `--undo`。
5. **不改用户内容**。不改文件名（除同名冲突时追加 ` (2)`）、不改文件内容。
6. **单批 ≤10**。超出部分顺延，不擅自放大批量。
7. **Office 临时文件跳过**（`~$*`、`.tmp`、`Thumbs.db`、`desktop.ini`）。
8. **拿不准就归 `Others` 并标记**，不要为了「分类完整」硬塞进考试/课件类。
9. **收工必核对且必给回执**，新问题必回写 ERROR_LOG。
10. **中文输出走 UTF-8**。脚本已 `reconfigure` 到 UTF-8；若终端仍乱码，读 `_System/logs/` 下的报告文件而不是看 stdout。
11. **收尾必问一句**「是否直接提炼 PPT 知识点？」并附上待提炼数量——见 Step 7。这是**流程终点动作**，不是可选项；仅用于对话场景，定时自动化不发问。

## 分类判据（优先级从高到低）

> 目标文件夹名以 `_System/taxonomy.json` 的 `folders` 为准；下表写的是**默认**命名。

| 优先级 | 条件 | 目标 |
|:--|:--|:--|
| 1 | 命中 `final / finals / 期末 / 期末考试` 等 | `7_Final Examination` |
| 2 | 命中 `midterm / mid-term / 期中 / 期中考` 等 | `6_Midterm Examination` |
| 3 | 命中测验词（`quiz / quizzes / 小测 / 随堂 / 随堂演练 / 课堂练习`）且无讲次编号、无课件词 | `5_Quiz` |
| 4 | 命中作业词（`homework / assignment / hw / lab / report / project / 作业 / 实验报告 / 习题`）且无讲次编号、无课件词 | `4_Assignment` |
| 5 | 只命中泛考试词（`exam / test / 试卷 / 真题 / 考试`）且无期中/期末标识 | `10_Others` + **标记需确认** |
| 6 | 命中大纲/非教学类词（`syllabus` / `course outline` / `grading policy` / `schedule` / `academic integrity` / `教学大纲` / `考核方式`…）**且没有讲次编号、也没有课件词** | `1_Syllabus` |
| 7 | 命中 `essence / summary / 笔记 / 知识点` 等 **且扩展名为 `.md`** | `3_Essence` |
| 7b | 同上但扩展名非 `.md` | `10_Others` + 标记（`3_Essence/` 只收与课件同名的 `.md`） |
| 8 | 命中课件词（`lecture / ppt / chapter / 课件 / 讲义`）或讲次编号（`L03`、`Ch2`、`Week5`）或扩展名为 `.ppt/.pptx` | `2_Textbook&Lecture_PPT` |
| 9 | 命中教材词（`textbook / 教材 / 课本`） | `2_Textbook&Lecture_PPT`（**与课件同一目录，AIE-024**） |
| 10 | 以上都不中，则读正文首段消歧（出现 Midterm/Final/Lecture 特征） | 对应分类 + **标记需复核** |
| 11 | 兜底 | `10_Others` |

> **`1_Syllabus` 的优先级是刻意设计的**：讲次编号与课件词**优先于**大纲词。所以「Lecture 5 Outline.pdf」会进 `2_Textbook&Lecture_PPT`（有 `lecture`），而「Course Outline.pdf」「Grading Policy.pdf」才进 `1_Syllabus`——避免把带 "Outline" 字样的讲义误判成大纲。

> **`quiz` 已从泛 `exam` 里拆出来**（AIE-024）：小测 ≠ 考试。以前 `quiz` 落在 `exam` 组里，会被当成「未标明期中/期末 → 需人工确认 → Others」；现在 `Quiz 1.pdf` 直接进 `5_Quiz`。

> **`Textbook` 与 `PPT` 已合并**（AIE-024）：教材类材料与课件同放 `2_Textbook&Lecture_PPT/`，不再有独立 `Textbook/` 目录。因此**「教材 PDF 不是课件」这条判断改由文件名承担**——`health_check.py` 的 `is_deck()` 会用 `non_deck_keywords`（`textbook`/`教材`/`解答`/`答案`/`solution`/`edition`…）把教材从「待提炼课件」里排除，否则每周自动化都会去给整本课本写笔记。

> 若用户明确要求「同时命中时可以放弃考试类、优先作业/小测」（例如 `Final Project Report.pdf` 想进 `4_Assignment` 而不是 `7_Final Examination`），改 `_System/taxonomy.json` 的关键词或调整 `classify()` 的分支顺序。默认保持「考试 > 作业」并**标记冲突**，不擅自替用户决定。

> 匹配规则有**四种，缺一不可**：中文按**子串**；英文单词按**整词**（避免 `final` 里的 `fin`、`Midterm` 里的 `mid` 误伤）；**多词短语**（`course outline`、`grading policy`）按归一化后的整串做子串匹配；**关键词+数字**的紧凑写法（`assignment2`、`hw3`、`quiz1`、`lab1`、`chapter5`）也算命中（AIE-024 补）。少一种，税表里对应形态的关键词就会**静默失效**（见 `ERROR_LOG AIE-014` / `AIE-024`）。

## 参考文件

- `references/folder_taxonomy.md` — 税表字段说明、如何按课程习惯改写、常见误判与调法
- `scripts/triage_inbox.py` — 主脚本（含 `--apply` / `--undo` / `--batch-size` / `--include`）
- `<course_root>/_System/ERROR_LOG.md` — 本工作区的教训库与核对判据
