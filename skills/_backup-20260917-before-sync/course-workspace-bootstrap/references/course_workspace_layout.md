# 课程工作区结构与换课清单

## 一、标准结构

```
<课程根>/                          ← 目录名 = 课程代号，如 MAT3007
├── 0_inbox/                      ← 所有未处理材料先丢这里
├── 1_Syllabus/                   ← 教学大纲 + 全部课程非教学内容（评分/考核/课表/学术诚信）
├── 2_Textbook&Lecture_PPT/       ← 课件 + 教材（**已合并**：讲义 PPT 与教材 PDF 同目录）
├── 3_Essence/                    ← 每份课件对应的**同名（slug 化）** .md 笔记（+ 00_Index.md、figures/）
├── 4_Assignment/                 ← 课程作业（homework / assignment / lab report / project / 习题）
├── 5_Quiz/                       ← 小测 / 随堂演练 / 课堂练习
├── 6_Midterm Examination/        ← 期中试卷、答案
├── 7_Final Examination/          ← 期末试卷、答案
├── 10_Others/                    ← 其他（无法归类的）
├── Outline of <课程代号>.md       ← 课程纲要（来源：1_Syllabus + 2_Textbook&Lecture_PPT）
├── README.md                     ← 使用入口
└── _System/                      ← 引擎
    ├── ERROR_LOG.md              ← 过往教训库 + 流程核对的唯一事实源
    ├── taxonomy.json             ← 分类税表（**目录名的唯一事实源** + 关键词）
    ├── WORKFLOW.md               ← 完整流程规格
    ├── prompts/                  ← 跨平台 prompt（ChatGPT / Claude / DeepSeek / OpenAI）
    ├── scripts/
    │   ├── run_pipeline.py       ← 一键编排（Step 0 开工检查 → Step 4 收工核对）
    │   └── health_check.py       ← --phase open|close · --beat 写心跳
    ├── extracted/                ← 课件提取出的纯文本（笔记的事实基础）
    ├── _quarantine/              ← 误落位置/待人工处理的杂物（可安全删除）
    └── logs/                     ← 报告 + 可回滚移动清单 + 自动化心跳
```

> ⚠️ **目录名一律从 `_System/taxonomy.json` 的 `folders` 解析**，代码里不得硬编码（AIE-018 / AIE-024）。用户可自由改名，改完只需同步税表。
>
> ⚠️ 不要在**学期父目录**（`…/<学期>/`）下创建 `figures/` 之类的产物目录——生成物必须落在它所属的课程子目录里（AIE-023）。

## 二、资产分级（决定复制时怎么处理）

| 级别 | 内容 | 部署到新课程时 |
|:--|:--|:--|
| **流程级** | `_System/scripts/*.py`、`_System/prompts/*`、`_System/WORKFLOW.md`、`_System/ERROR_LOG.md`、`_System/taxonomy.json` | **复制**（改课程名/路径；ERROR_LOG 加继承说明） |
| **课程级·可重建** | `README.md`、`3_Essence/00_Index.md`、`Outline of <代号>.md` | **重建**（由脚本生成骨架） |
| **课程级·私有** | `logs/`、`extracted/`、`_quarantine/`、`2_Textbook&Lecture_PPT/` 下的课件与教材、`3_Essence/` 下的笔记、源课程的 `Outline of *.md` | **绝不复制** |

## 三、换课清单（逐项打勾）

- [ ] 确认新课程目录**尚不存在**
- [ ] 选一门**最近维护过**的课程作 `--source`（当前 `AIE2040`）
- [ ] `grep` 读一遍源课程 `_System/taxonomy.json` 的 `folders`，确认要建的目录名
- [ ] 跑 `bootstrap_course.py --source ... --target ... --code <新代号>`
- [ ] 用 `automation_update` 建 `<代号> 课件自动提炼 Essence`（**每周六**），时刻**与已有课程错开**
- [ ] 跑 `--patch-automation <ID> <HH:MM>` 回填
- [ ] `health_check.py --phase both` 验证（全绿；AIE-011 心跳在自动化本轮 `--beat` 时只报 NOTICE）
- [ ] `grep -rn "<源课程代号>" <新课程>/_System/scripts/` 确认无硬编码残留
- [ ] 逐条比对母版 `LESSON_CHECKS` 键集与 `ERROR_LOG.md` ID 集，缺项按编号空间**换名回补**
- [ ] 告知用户：把 syllabus 放进 `0_inbox/`、教材放进 `2_Textbook&Lecture_PPT/`，然后生成 `Outline`

## 四、自动化时刻分配（避免同时唤起多个模型会话）

| 课程 | 时刻（**每周六**） |
|:--|:--|
| AIE2040 | 00:00 |
| CHM1001 | 00:15 |
| MAT3007 | 00:30 |
| 下一门 | 00:45（依次 +15 分钟；同一天上限 4 条较稳妥） |

```text
rrule 形如：FREQ=WEEKLY;BYDAY=SA;BYHOUR=0;BYMINUTE=15
```

> `BYHOUR` **不支持多值**（AIE-012）；要多天用逗号分隔的 `BYDAY`，不要建多条自动化。
>
> 超过 4 条课程时，建议改由**单条「全课程」自动化**遍历各课程目录，而不是每课一条。这是刻意留的后续优化点。
>
> ⚠️ **延迟特性**：周频意味着「课件落进 `2_Textbook&Lecture_PPT/`」到「笔记生成」之间**最多有 7 天延迟**。想更快，可临时手动喊「提炼 PPT 知识点」，或把频率调密。
