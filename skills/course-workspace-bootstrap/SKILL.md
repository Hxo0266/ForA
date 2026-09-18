---
name: course-workspace-bootstrap
description: This skill should be used when the user wants to set up a NEW course workspace that reuses the existing course-study automation workflow — for example "创建 MAT3007 文件夹", "给 MAT3007 也做一套", "新建课程工作区", "把这套流程部署到 X 课程", "set up a new course folder with the same workflow". It creates the standard folder skeleton (0_inbox / 1_Syllabus / 2_Textbook&Lecture_PPT / 3_Essence / 4_Assignment / 5_Quiz / 6_Midterm Examination / 7_Final Examination / 8_Correction_Notebook / 10_Others / _System), copies the flow-level assets from an existing course (health-check and pipeline scripts, taxonomy, cross-platform prompts, WORKFLOW spec, ERROR_LOG with an inheritance header) while renaming the course code, regenerates the course-specific files (README, Essence index, Outline skeleton) and never copies course-private data (logs, extracted text, textbook, notes). It then instructs the agent to register a matching weekly (Saturday) scheduled automation at a non-conflicting time and to verify the new workspace with health_check. Folder names are always resolved from _System/taxonomy.json, never hard-coded.
agent_created: true
---

# Course Workspace Bootstrap（新课程工作区部署）

## 用途

把已有的「课程自动化学习流程」**整套部署**到一门新课程，产出与既有课程结构完全一致的工作区。

## 何时使用

- 「创建 MAT3007 文件夹」「给 MAT3007 也做一套」「新建课程工作区」
- 「把这套流程部署到 X 课程」「帮我给这门课建个同样的目录结构」
- 用户给了一个**课程代号**，并期待它像已有课程一样能用（有分类、有笔记流程、有核对）

**不适用**：只想建一个**纯空目录**（那就直接 `mkdir`，别部署整套）；或目标目录不是课程工作区语义。

## 一条命令

```bash
python "<skill_dir>/scripts/bootstrap_course.py" \
  --source "<用哪门已有课程作模板>" \
  --target "<新课程根目录>" \
  --code <新课程代号>
```

`--source` 建议用**最近维护过的那门课**（它的 `_System/` 最新）。省略 `--automation-time` 时，文档里会写成 `待配置`，等自动化建好再回填。

## 执行步骤（严格按序）

### Step 1 — 确认源与目标

- 源：挑一门已有课程（例如 `<学期目录>/AIE2040`），确认它有 `_System/scripts/`、`_System/taxonomy.json`、`_System/ERROR_LOG.md`
- 目标：`<学期目录>/<课程代号>`；**先确认该目录尚不存在**（`find` 一下），如果已存在要读一遍再决定是否 `--force`

### Step 2 — 部署

跑上面的命令。产出：

- **结构**：`0_inbox / 1_Syllabus / 2_Textbook&Lecture_PPT / 3_Essence / 4_Assignment / 5_Quiz / 6_Midterm Examination / 7_Final Examination / 8_Correction_Notebook / 10_Others / _System`
- **流程级资产**（改名后复制）：`_System/scripts/*.py`、`_System/taxonomy.json`、`_System/prompts/`、`_System/WORKFLOW.md`、`_System/ERROR_LOG.md`（带继承说明）
- **课程级文件**（重建）：`README.md`、`3_Essence/00_Index.md`、`Outline of <CODE>.md`（骨架）
- **不复制**：`logs/`、`extracted/`、`2_Textbook&Lecture_PPT/`、`3_Essence/` 下的笔记、源课程的 `Outline of *.md`

> ⚠️ 目录名以 `_System/taxonomy.json` 的 `folders` 为准（AIE-018 / AIE-024）。若用户给已有课程改过名，`--source` 里带过来的税表就是你新课程要用的名字——**先把税表读一遍再建目录**。

### Step 3 — 建定时自动化（**必须由 Agent 做，脚本无法代劳**）

用 `automation_update` 创建 `create`：

| 字段 | 值 |
|:--|:--|
| `name` | `<CODE> 课件自动提炼 Essence` |
| `cwds` | 新课程根目录 |
| `scheduleType` | `recurring` |
| `rrule` | `FREQ=WEEKLY;BYDAY=SA;BYHOUR=<H>;BYMINUTE=<M>`（**每周六**） |
| `status` | `ACTIVE` |
| `prompt` | **复制一门已有课程的同类自动化提示词**，把课程代号与路径全部替换 |

**时刻必须与已有课程错开**（避免同一分钟唤起多个模型会话）。已知占用：AIE2040 周六 00:00、CHM1001 周六 00:15、MAT3007 周六 00:30 → 下一门用周六 00:45，依次顺延 15 分钟。

> ⚠️ `rrule` 的 `BYHOUR` **不支持多值**，一条自动化只能设一个整点（见 ERROR_LOG AIE-012）。频率若要跨多天，用逗号分隔的 `BYDAY`（如 `BYDAY=SA,SU`），**不要**建多条自动化。

> ⚠️ 提示词里若引用了 ERROR_LOG 的条目编号，**要按新课程的编号空间换算**——各课编号是独立命名空间：母版 `AIE2040` 与 `CHM1001` 一致；`MAT3007` 因多一条独立教训（AIE-020「副本静默落后于母版」），**自 AIE-021 起整体 +1**。直接照搬编号会让提示词指错条目。

### Step 4 — 回填自动化信息

拿到自动化 ID 后：

```bash
python "<skill_dir>/scripts/bootstrap_course.py" --target "<新课程根目录>" --code <CODE> \
  --patch-automation <自动化ID> <HH:MM>
```

它会更新 `_System/WORKFLOW.md` 的 §8.1 表格与 `_System/ERROR_LOG.md` 头部。

### Step 5 — 验证

```bash
python "<新课程根>/_System/scripts/health_check.py" --root "<新课程根>" --phase both
```

要求：开工 O1–O6 全绿；收工核对条目数与源课程一致，且**命中 0 条**。
（AIE-019 之后，「还没有心跳」在自动化本轮自带 `--beat` 时只报 NOTICE、不报 WARN，所以首轮部署不必再看到那条假警报；若真报了 WARN，说明 `will_write_beat` 没注入或本课程副本落后于母版。）

再扫一遍残留，确认没有源课程的硬编码（见 ERROR_LOG AIE-016）：

```bash
grep -rn "<源课程代号>" "<新课程根>/_System/scripts/" || echo "干净"
```

### Step 6 — 回报

告诉用户：目录结构、继承的教训条数与新增起始编号、自动化名称/ID/时刻、验证结果、以及**下一步需要用户提供什么**（syllabus 与 textbook，才能生成真正的 `Outline`）。

## 硬规则

1. **绝不复制课程私有数据**：`logs/`、`extracted/`、`2_Textbook&Lecture_PPT/` 下的课件与教材、`3_Essence/` 笔记、`Outline of <源课程>.md`。
2. **ERROR_LOG 必须带继承说明**：写明继承来源、已用编号、本课程新编号起点（见 AIE-015）。
3. **脚本与配置里不得留硬编码课程名**：一切从 `--code` 推导（见 AIE-016）；部署后必须 `grep` 验证。
4. **自动化时刻必须错开**，且**新建而非复用**已有课程的自动化（作用域不同）。
5. **不猜测课程内容**：`Outline of <CODE>.md` 生成时只能是骨架，`[待补充]` 标满；没有 syllabus/textbook 就不写任何课程内容的断言。
6. **同名文件默认跳过**，只有显式 `--force` 才覆盖；跳过项要如实回报。
7. **生成物只写在新课程自己的目录里**，绝不落到学期父目录（`…/<学期>/`）下（AIE-023）。部署时**不要**在父目录下 `mkdir figures` 之类的产物目录。
8. **中文输出走 UTF-8**。
9. **母版自动跟进（铁律，ForA 1.1.0）**：`_System/` 最新版永远在母版 **AIE2040**；其他课程是**快照复制、不会自动跟进**，而落后的副本只会显示「全绿」、不会报错。因此**框架改动必须自动同步到每一门课**（版本更新、目录增删、`taxonomy.json` / `health_check.py` / `run_pipeline.py` / `ERROR_LOG.md` / skill 脚本），逐课比对 `LESSON_CHECKS` 键集与 `ERROR_LOG.md` 的 ID 集，缺失项按「**脚本实现 + ERROR_LOG 条目 + 变更记录**」三件套回补（只补文档等于没补）。**唯一例外**：用户明确说「只改某一门课」时才单独改那一门，否则一律全量同步。
   - 选 `--source` 时用**最近维护过的那门课**（当前 `AIE2040`，它的 `_System/` 最新）；
   - 各课编号是**独立命名空间**，「ID 对得上」不代表「内容对得上」——比对要看教训标题与实现，不能只看编号；
   - 回补脚本实现时，**按该课编号空间换名**（`MAT3007` 因多一条独立教训占用 AIE-020，**自 AIE-021 起整体 +1**），别把母版编号直接塞进去。

## 参考文件

- `scripts/bootstrap_course.py` — 部署与回填脚本（含资产分流规则）
- `references/course_workspace_layout.md` — 工作区结构、资产分级（流程级 / 课程级）与换课清单
