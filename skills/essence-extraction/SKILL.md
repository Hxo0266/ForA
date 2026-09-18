---
name: essence-extraction
description: This skill should be used when the user wants to read course slides and distil them into study notes — for example "提炼PPT知识点", "把PPT整理成笔记", "生成Essence", "把课件总结成markdown", "PPT转笔记", "extract the essence from these slides", "summarise the lecture decks". It extracts the full text, tables and speaker notes from every slide deck in a course workspace's PPT folder, then the agent reads that extracted text (never the visual slide impression) and writes a compact, same-named Markdown knowledge digest into the Essence folder, one file per deck, with an index and a coverage check that lists which decks still lack an essence file.
agent_created: true
---

# Essence Extraction（课件 → 知识点提炼）

## 用途

把 `2_Textbook&Lecture_PPT/` 里每一份课件，提炼成 `3_Essence/` 里一份**同名**、排版紧凑的 Markdown 知识点笔记。

## 何时使用

- 「提炼 PPT 知识点」「把 PPT 整理成笔记」「生成 Essence」「课件转 Markdown」
- 「把这份 PPT 总结一下」「extract the essence from these slides」

## 独立文件（非课程工作区）怎么办

用户直接丢来一个**不在任何课程工作区里**的课件/文档（如桌面上的一份 PDF）并要求提炼时，`extract_slides.py` 跑不了（它依赖课程根的税表与目录约定）。此时**不放弃纪律，只换载体**：

1. **先提取后写作的纪律不变**：用 venv 里的 pymupdf（PDF）逐页提取全文，写成带 `===== 第 N 页 =====` 标记的 `.txt` 作为唯一事实来源；含嵌入图的页按 150dpi 渲染整页 PNG。
2. **产物落位**：**绝不放桌面**（用户明确要求）。放进合适的文件夹：属于某门课 → 该课 `3_Essence/`；非课程文档 → `D:\Courses\<主题项目文件夹>\`（拿不准先问）。命名 `<主干>-Essence.md` + `<主干>-Essence-figures/page-NN.png`（无空格，AIE-022 依旧生效）。
3. **笔记结构不变**：front matter 的 `course` 写实际来源（如「大创项目（XX大学，非课程文档）」）；出处索引落到**页码**而非张号。
4. **不要塞进课程工作区**：除非用户明确说这文件属于某门课，否则不要写进 `3_Essence/`——课程目录的配对规则（同名课件 ↔ 同名笔记）会被破坏。
5. Windows 注意：给 python.exe 传路径用 Windows 风格（`C:/...`），MSYS 的 `/c/...` 会被解析成 `c:\c\...`。

## 核心纪律：先提取，再写作

**禁止凭视觉印象写 PPT 内容。** 必须先由脚本把课件逐张提取成纯文本，笔记的每一个事实点都要能在提取文本里指到出处。这是 `ERROR_LOG 2026-05-04`（读 PDF 捏造章节名与术语）的直接对策。

## 执行步骤

### Step 1 — 提取原文（事实基础）

```bash
python "<skill_dir>/scripts/extract_slides.py" --root "<course_root>"
```

产出：

- `_System/extracted/<stem>.slides.txt` — 逐张文本 + `[TITLE]` / `[TABLE]` / `[NOTES]` / **`[FIGURE]`** 标记
- `_System/extracted/<stem>.slides.json` — 同内容的机读版
- `_System/extracted/<stem>.figures.json` — **图表清单**（哪些页有图、类型、文件路径）
- `3_Essence/figures/<slug>/slide-NN.png` — **含图表页的整页渲染图**（默认 150 dpi）

**关于 `<slug>`**：`<slug>` 是课件名的**路径安全化**形式（空格/括号等 → `-`，中文保留），
笔记文件名也用它。例：课件 `CHM1001W1-Electronic Structure.pptx` → 图表目录
`3_Essence/figures/CHM1001W1-Electronic-Structure/`、笔记 `3_Essence/CHM1001W1-Electronic-Structure.md`。
**原因**：Markdown 图片语法 `![alt](dest)` 的目标里**不允许出现未转义的空格**，否则渲染器在第一个
空格处截断、图全部断链；文件名里的空格还会让预览/卡片按空格截断，文档打不开。详见 AIE-022。
- `_System/logs/extract_<stamp>.md` — 成功 / 跳过 / **无法解析** / 图表统计

只处理某几份：`--deck "<path>"`（可重复）；强制重提取：`--force`。

**图表策略** `--figures {auto,all,none}`（默认 `auto`）：

| 值 | 行为 |
|:--|:--|
| `auto` | 只为**含图表**的页导出。判定：有嵌入图、或有表格、或有 ≥3 个矢量图形（自选图形/箭头/线条，即**用形状拼出来的示意图**）。**宁可多导，不漏** |
| `all` | 每一页都导出 |
| `none` | 完全不导出（纯文本，回退到旧行为） |

> **为什么渲染整页而不是只抽嵌入图**：PPT 里的示意图多数是「形状 + 箭头 + 文本框」拼的，不是一张 embed 图片。只抽 embed 图会漏掉绝大部分图。渲染整页 = 所见即所得。

**渲染依赖**：`.pdf` 用 PyMuPDF 直接渲染；`.pptx` 需要 **LibreOffice**（`soffice --headless --convert-to pdf`）先转 PDF 再渲染；`.docx` 无「页」语义，不产图。若本机没有 LibreOffice，报告里会写明「无法渲染图表」并提示先把课件另存为 PDF 放回 `2_Textbook&Lecture_PPT/`。

**若报告里出现「无法解析」**（例如旧版 `.ppt`、扫描件 PDF），必须如实告诉用户并给出可行路径（另存为 `.pptx` / 先 OCR），**不要**靠猜把内容补上。

### Step 2 — 读提取文本

Read `_System/extracted/<stem>.slides.txt`（长课件分段读，不要跳读）。必要时对照 `.json` 里的表格结构。

### Step 3 — 写 Essence 笔记

对每份课件，在 `3_Essence/` 下创建**与课件同名（经 `slug()` 安全化）**的 `<slug>.md`。统一使用下面的结构（紧凑优先，宁缺勿凑）：

```markdown
---
course: <课程名>
source: <课件文件名>
slides: <张数>
extracted: <YYYY-MM-DD>
tags: [course/essence, <主题标签>]
---

# <课件标题>（<English Title>）

> 一句话主旨：<这份课件到底在讲什么>

## 1. <主题中文>（<English Topic>）
- **要点**：…
- **要点**：…
- 公式：$…$（若有）
- 该式在图内，提取文本未给出 → <u>公式在图内</u>

![第 3 张：<这张图说明了什么>](figures/<slug>/slide-03.png)

## 2. <主题中文>（<English Topic>）
…

## 关键术语
| 术语（English） | 释义 |
|:--|:--|
| 波长（Wavelength） | 相邻对应点之间的距离 |

## 易错点 / 待核实
- …

## 出处索引
- 第 3、4 张：<要点归属>

## 公式在图内（提取文本丢失）
- 第 14 张：公式在图内、提取文本丢失
```

> `## 公式在图内（提取文本丢失）` **永远是全文最后一节**（排在「出处索引」之后）；没有这类情况就**整节不写**。

写作要求：

1. **紧凑**：列表优于段落；一屏内能扫完一个主题。不写客套话、不复述废话过渡句。
2. **信息密度优先**：保留数字、公式、定义、算法步骤、对比表；删掉「本节介绍…」这类空壳。
3. **⭐ 英文名优先（本次流程优化的核心要求之一）**：
   - **每个术语、每个重点区域都必须带英文名**；中英文都存在时，**英文在前**。
   - 重点区域 = 小节标题：`## 波长与频率（Wavelength and Frequency）`，**不得**只写中文。
   - 术语首次出现：**`English（中文）`**，例如 `Wavelength（波长）`；`## 关键术语` 表的「术语」列同样英文在前。
   - 英文名一律取自提取文本；文本里没有英文名的，**不要自己翻译**，标 `[待核实]`。
4. **不确定就标注 `[待核实]`**，并写清是哪一张、哪句话让你不确定。
5. **表格/公式按原样保留**，LaTeX 行内 `$ $`、行间 `$$ $$`。
6. 笔记里出现的每个实质结论，都要能在 `## 出处索引` 里落到具体张号。
7. **⭐「公式在图内」的固定写法（本次流程优化的核心要求之一）**：
   - 当某个公式 / 关系式**只存在于幻灯片图形里**、而 `slides.txt` 的提取文本里**没有**它时：
     - 正文该处**只写** <u>公式在图内</u> 这几个字（用 `<u>…</u>` 加下划线），**位置放在该知识点那一行/那一条的末尾**；
     - **禁止**凭图片印象或常识把公式补出来，**禁止**写成「该式在第 N 张图内，提取文本丢失」之类的长句；
   - 同时**在 markdown 文件末尾**用 `## 公式在图内（提取文本丢失）` 一节逐条列出：
     `- 第 N 张：公式在图内、提取文本丢失`。
   - 正文里出现几处 <u>公式在图内</u>，文末就**必须**有几条对应记录（张号要对得上）。
8. **⭐ 图必须贴在对应知识点旁边**：
   - `slides.txt` 里出现 `[FIGURE] <相对路径>` 的**每一张**，都要用 Markdown 图片语法把该图**插入到这一张所讲知识点所在的小节内、该知识点正下方**。
   - **禁止**把所有图集中堆到文末，也**禁止**只在文中写「（见第 7 张图）」而不真的插图。
   - 图题格式：`![第 N 张：<一句话说明这张图在讲什么>](<相对路径>)`；说明必须来自该张的文本，不要脑补。
   - 相对路径**直接原样复制** `[FIGURE]` 行里给的那串（相对 `3_Essence/` 目录，形如 `figures/<slug>/slide-07.png`）。
     **不要自己改写、不要加空格、不要在路径两侧加反引号**——路径里一旦出现空格，图就全断（AIE-022）。
     若路径确实含空格或 `()`，改用尖括号形式 `](<path with space.png>)` 并同时告知用户课件名需要安全化。
   - 若某张的图**本身就是主体内容**（例如流程图、结构图），除插图外还要用要点把图中的关键关系写出来——不能让笔记在纯文字阅读时失去信息。

### Step 4 — 覆盖率自检

`3_Essence/00_Index.md` 之外，还要核对「`2_Textbook&Lecture_PPT/` 里还有哪些课件没生成笔记」：

```bash
python "<course_root>/_System/scripts/run_pipeline.py" --root "<course_root>" --skip-triage
```

该模式会打印 `PPT 有 N 份 / Essence 有 M 份 / 待提炼：…`，并把任务清单写到 `_System/logs/pending_essence.md`。

### Step 5 — 维护索引

`3_Essence/00_Index.md` 汇总所有笔记（课件名 / 主题 / 张数 / 最后更新）。新增或重写笔记后同步该表。

## 硬规则

1. **同名配对（经安全化）**：`2_Textbook&Lecture_PPT/<stem>.<ext>` ↔ `3_Essence/<slug(stem)>.md`，副本名只在**去空格**这一步与原名不同（`slug()` 由 `extract_slides.py` 提供，是唯一实现）。
2. **先提取后写作**。提取文本缺失时，先跑 Step 1，不要跳。
3. **不臆造**。提取文本里没有的内容不写；看不清的标 `[待核实]`。
4. **不覆盖已有人工修改**。若 `3_Essence/<slug>.md` 已存在且含用户手写内容，先问再改，或另存为 `<slug>_v2.md`。
5. **一份课件一个文件**，不要把所有课件塞进一个巨型笔记。
6. **中文输出 UTF-8**；笔记一律写成 `.md` 文件，不要在终端口述全文。
7. **有图必贴，且贴在点上**。`[FIGURE]` 标记了几张，笔记里就要有几张图；位置必须在对应知识点旁边，不得集中堆放、不得只写「见图」。图件由脚本渲染，**不要自己生成或美化图片**。
8. **图表渲染失败要如实说**。报告里出现「无法渲染图表」时，明确告诉用户原因（例如缺 LibreOffice / 扫描件 / 旧版 .ppt）与解决办法，**不要用文字硬凑出「图」**。
9. **⭐ 英文名优先**。每个术语与每个重点区域（小节标题）都必须有英文名，中英并存时英文在前；英文名必须来自提取文本，不自行翻译，缺就标 `[待核实]`。
10. **⭐ 公式在图内**。公式只存在于图形里、提取文本没有时：正文只写 <u>公式在图内</u>（下划线），并在文末 `## 公式在图内（提取文本丢失）` 逐条列 `第 N 张：公式在图内、提取文本丢失`。**不得**凭印象补公式。
11. **⭐ 生成物路径一律无空格**。图表目录与笔记文件名都走 `slug()`；`![]()` 里的路径原样复制 `[FIGURE]`，不改写、不加空格、不加反引号。
12. **⭐ 目录名从税表解析，不硬编码**。课件目录 / 笔记目录一律取 `<root>/_System/taxonomy.json` 的 `folders`（`slides` / `essence`）；用户改名（`PPT`+`Textbook`→`2_Textbook&Lecture_PPT`、`Essence`→`3_Essence`…）后只改税表即可（AIE-018 / AIE-024）。
13. **⭐ 生成物不得逃出课程目录**。笔记、图、提取物都必须落在本课程目录内；`--figures-dir` 指向课程根之外时脚本**直接报错退出**，不要绕过它（AIE-023：历史上曾把图写到学期父目录的 `figures/`）。
14. **⭐ 教材不是课件**。合并目录 `2_Textbook&Lecture_PPT/` 里既有讲义也有教材；教材 / 课本 / 习题解答 / 答案（`non_deck_keywords`）**不提炼**，别给整本书写笔记（AIE-024）。

## 参考文件

- `references/essence_format.md` — 笔记模板详解 + 完整范例（含图文混排）+ 常见质量问题对照
- `scripts/extract_slides.py` — 课件提取脚本（文本 + 表格 + 备注 + 图表）
