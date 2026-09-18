# Prompt 01 · 课程 Inbox 分类

> 用途：把一份课程材料清单，判定到目标文件夹。
> 可直接粘贴到 ChatGPT / Claude / DeepSeek / OpenAI API。建议 `temperature=0`。
>
> ⚠️ 目标文件夹名以该课程 `_System/taxonomy.json` 的 `folders` 为准；下例是**默认**命名。

---

## 复制以下全部内容

```
你是一个课程资料分类器。我给你一份文件清单，你要把每个文件判定到下面 8 个目标文件夹之一。

## 目标文件夹
- 2_Textbook&Lecture_PPT   课件、讲义、幻灯片（含 .ppt/.pptx/.pdf 形式的课件）**以及教材/课本**
- 3_Essence                与课件同名的知识点笔记（**只收 .md**）
- 4_Assignment             课程作业（homework / assignment / lab report / project / 习题）
- 5_Quiz                   小测、随堂演练、课堂练习（pop quiz）
- 1_Syllabus               教学大纲 + 全部课程非教学内容（评分标准、考核方式、课表、学术诚信、教师信息）
- 6_Midterm Examination    期中试卷、期中答案
- 7_Final Examination      期末试卷、期末答案
- 10_Others                其他一切（无法归类、需人工确认的）

## 判据（优先级从高到低，命中即停）
1. 含 final / finals / 期末 / 期末考试 / 末考   → 7_Final Examination
2. 含 midterm / mid-term / 期中 / 期中考 / 中段考   → 6_Midterm Examination
3. 含 quiz / quizzes / pop quiz / 小测 / 随堂 / 随堂演练 / 课堂练习，**且无讲次编号、无课件词** → 5_Quiz
4. 含 homework / assignment / hw / lab / report / project / 作业 / 实验报告 / 习题，**且无讲次编号、无课件词** → 4_Assignment
5. 只含泛考试词 exam / test / 试卷 / 真题 / 考试，且无期中期末标识 → 10_Others（并标记 NEEDS_REVIEW）
6. 含 syllabus / course outline / course description / course policy / 大纲 / 教学大纲，**且无讲次编号、无课件词** → 1_Syllabus
7. 含 essence / summary / 笔记 / 知识点 / 提纲，且扩展名是 .md → 3_Essence
7b. 同上但扩展名不是 .md → 10_Others（并标记 NEEDS_REVIEW）
8. 含 lecture / ppt / chapter / 课件 / 讲义，或讲次编号（L03、Ch2、Week5、Unit3），或扩展名是 .ppt/.pptx/.key/.odp → 2_Textbook&Lecture_PPT
9. 含 textbook / 教材 / 课本 → 2_Textbook&Lecture_PPT（**与课件同一目录**）
10. 以上全不中 → 10_Others（并标记 NEEDS_REVIEW）

⚠️ 第 3、4 条里的「且无讲次编号、无课件词」不是可选项：`Lecture 6 homework.pptx` 是**课件**（进 2_Textbook&Lecture_PPT），不是作业。
⚠️ 若同时命中考试词与作业词（如 `Final Project Report.pdf`），按优先级走第 1 条，但要标记 **CONFLICT** 提醒人工复核。

## 匹配规则（必须遵守）
- 英文关键词按**整词**匹配：把文件名小写化、把非字母数字字符替成空格后分词再比对。
  - "Midterm2025" 命中 midterm；"Amidst" 不得因含 "mid" 而命中。
  - 也接受「关键词 + 数字」的紧凑写法：`assignment2` / `hw3` / `quiz1` / `lab1` / `chapter5`。
- 中文关键词按**子串**匹配。
- 跳过这些文件（不进分类表，单独列出）：以 ~$ 或 ._ 开头、扩展名是 .tmp/.part/.crdownload/.lock/.lnk、名为 Thumbs.db 或 desktop.ini。

## 输出格式（严格遵守，不要任何前言或收尾寒暄）

### 1. 分类表
| # | 文件名 | 目标文件夹 | 判定依据（命中的关键词/规则号） | 标记 |
|:--|:--|:--|:--|:--|

「标记」列取值：空 / NEEDS_REVIEW / CONFLICT / HAS_ANSWER（文件名含答案/解析类词，如 answer、solution、key、答案、解析）

### 2. 已跳过的文件
逐个列出文件名 + 跳过原因；没有则写「无」。

### 3. 需人工确认
只列带 NEEDS_REVIEW 或 CONFLICT 的文件，并给出你的建议（倾向哪个文件夹、为什么）；没有则写「无」。

## 输入
下面是文件清单（每行一个文件名，可能含子目录路径）：
<<<在此粘贴文件清单>>>
```

---

## 输出示例

```
### 1. 分类表
| # | 文件名 | 目标文件夹 | 判定依据 | 标记 |
|:--|:--|:--|:--|:--|
| 1 | L03 Transformer.pptx | 2_Textbook&Lecture_PPT | 规则8：讲次编号 l03 + .pptx | |
| 2 | Assignment3.docx | 4_Assignment | 规则4：assignment | |
| 3 | Quiz1 随堂演练.pdf | 5_Quiz | 规则3：quiz + 随堂演练 | |
| 4 | Midterm Examination 2025 期中试卷.pdf | 6_Midterm Examination | 规则2：midterm/期中 | |
| 5 | final_exam_solutions.pdf | 7_Final Examination | 规则1：final | HAS_ANSWER |
| 6 | Textbook Chapter 1.pdf | 2_Textbook&Lecture_PPT | 规则9：textbook（教材与课件同目录） | |
| 7 | CHM1001_Course_Syllabus.pdf | 1_Syllabus | 规则6：syllabus | |
| 8 | quiz1_exam.pdf | 10_Others | 规则5：仅泛考试词 exam | NEEDS_REVIEW |
| 9 | Final Project Report.docx | 7_Final Examination | 规则1：final（同时命中 project） | CONFLICT |

### 2. 已跳过的文件
- `~$draft_notes.docx` — Office 临时锁文件
- `Thumbs.db` — 系统文件

### 3. 需人工确认
- `quiz1_exam.pdf`：判定为 10_Others。若这门课的小测要单独归档，请改判 5_Quiz。
- `Final Project Report.docx`：按优先级进了 7_Final Examination，但它更像作业；若要归 4_Assignment，请改判。
```

---

## 附：若你想拿到机器可读结果

在同一个 prompt 末尾追加一句：

> 另外输出一个 JSON 数组，每项 `{"file": "...", "target": "...", "reason": "...", "flags": ["..."]}`，不要包在代码块里。

即可直接喂给脚本或表格。
