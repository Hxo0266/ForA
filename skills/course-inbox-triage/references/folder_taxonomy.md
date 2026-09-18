# 分类税表（taxonomy.json）使用与调优

分类器的一切可调项都集中在 `<course_root>/_System/taxonomy.json`。**脚本每次运行都重新读取**，改完立即生效，不需要改代码。

⚠️ **目录名的唯一事实源就是这个文件**（`ERROR_LOG AIE-018` / `AIE-024`）。`health_check.py`、`run_pipeline.py`、`triage_inbox.py` 里的所有路径都通过它解析；`FALLBACK_TAXONOMY` 只是「没有配置文件也能跑」的兜底。**改目录名 = 改这个文件**，不要改脚本。

## 字段说明

| 字段 | 作用 |
|:--|:--|
| `course` | 课程代号（如 `AIE2040`）。自动化名会据此推导，复制到新课程时必改（AIE-016） |
| `folders` | 逻辑名 → 实际文件夹名。想改文件夹叫法只改这里，脚本无需动 |
| `optional_folders` | 可选目录（缺失不报错）。**当前为空**——`Textbook` 已并入 `slides`，见 AIE-024 |
| `non_deck_keywords` | **「不是课件」的关键词**。命中者即使扩展名像课件（pdf/pptx）也不算课件，O3/O4 会跳过它们（防「给整本教材写笔记」） |
| `skip_names` / `skip_prefixes` / `skip_exts` | 直接跳过的文件（系统文件、Office 锁文件、下载残片） |
| `keywords` | 各类别的文件名关键词表（`final` / `midterm` / `exam` / `answer` / `slides` / `essence` / `textbook` / `assignment` / `quiz` / `syllabus`） |
| `lecture_token_patterns` | 讲次编号的正则。`^l\d{1,2}$` 表示整词形如 `l03` |
| `slide_exts` / `doc_exts` | 扩展名白名单 |
| `content_peek_keywords` | 文件名无结论时，读正文首段用的消歧关键词 |
| `batch_size_default` | 单批默认上限（默认 10） |

## 默认目录映射（可直接改）

```json
"folders": {
  "inbox":      "0_inbox",
  "syllabus":   "1_Syllabus",
  "slides":     "2_Textbook&Lecture_PPT",
  "textbook":   "2_Textbook&Lecture_PPT",
  "essence":    "3_Essence",
  "assignment": "4_Assignment",
  "quiz":       "5_Quiz",
  "midterm":    "6_Midterm Examination",
  "final":      "7_Final Examination",
  "others":     "10_Others"
}
```

## 匹配语义（重要）

- **英文单词 = 整词匹配**。先把文件名小写化、把非字母数字字符压成空格，再分词比对。
  - ✅ `Lecture 03` 会命中 `lecture`
  - ❌ `Midterm` 不会因为含 `mid` 而误命中别的词，`final` 也不会因为 `fin` 误伤
  - ✅ **关键词+数字的紧凑写法也算命中**：`assignment2` / `hw3` / `quiz1` / `lab1` / `chapter5`（AIE-024 补，纯整词匹配会漏掉这些）
- **中文关键词 = 子串匹配**（中文没有分词边界）。
- **多词短语**（`course outline`、`grading policy`）按归一化后的整串做子串匹配。

## 按课程习惯改写的三个例子

**1. 加一门课的专属讲次编号**
```json
"lecture_token_patterns": ["^l\\d{1,2}$", "^lec\\d{1,2}$", "^topic\\d{1,2}$", "^aie\\d{2,3}$"]
```
> 注意 JSON 里反斜杠要写两次：`\\d`。

**2. 把「随堂练」也算小测**
```json
"quiz": ["quiz", "quizzes", "pop quiz", "小测", "随堂", "随堂演练", "课堂练习", "随堂练"]
```

**3. 让某门课的教材不再被当成课件**（避免给整本书写笔记）
```json
"non_deck_keywords": ["textbook", "教材", "课本", "参考书", "solution", "solutions", "解答", "答案", "edition", "习题解答", "教师用书"]
```

## 常见误判与调法

| 现象 | 原因 | 调法 |
|:--|:--|:--|
| 教材 PDF 被列进「待提炼」 | `non_deck_keywords` 没覆盖到该教材的命名 | 往 `non_deck_keywords` 里加词；或改课件文件名 |
| 「随堂测验」被归到 `10_Others` | `quiz` 词表没这条中文写法 | 往 `quiz` 里补 `随堂测验` |
| 「期末复习提纲」被归到 `7_Final Examination` | `期末` 优先级高于 `提纲/essence` | 若你希望它进 `3_Essence`，把 `期末` 从 `final` 里删掉，或改用 `期末考试`/`期末试卷` 这类更具体的词 |
| 「Midterm & Final Review」去了期末 | 期末优先级更高 | 接受即可（报告里会标记） |
| 「Final Project Report」进了 `7_Final Examination` | 考试优先级高于作业 | 报告会**标记冲突**（同时命中期末与作业词）。要改口径就调整 `classify()` 分支顺序或关键词 |
| 一份 PDF 被归到课件但其实是卷子 | 文件名只有 `L03` 之类 | 手动移到 `6_Midterm Examination/`；或在 `content_peek_keywords` 里补针对性词 |
| 泛考试词（`exam`）全进了 `10_Others` | 设计如此——无期中/期末标识时**不猜** | 看报告的「需人工确认」区，确认后手工移动，或在 `midterm`/`final` 关键词表里补上该课程的命名习惯 |

## 修改税表的安全姿势

1. 改完先跑 **dry-run**（不加 `--apply`），看 `_System/logs/triage_<stamp>.md` 的判定依据是否符合预期。
2. 确认无误再 `--apply`。
3. 单批上限与 `--undo` 是你的安全网：`moved_<stamp>.json` 记录了每一步 `src → dst`，随时可全量回滚。
4. **改完目录名后必跑收工核对**：`health_check.py --phase close`。AIE-018 核对项会发现「税表声明的目录不存在」，AIE-024 核对项会验证「教材判定」仍然有效。
