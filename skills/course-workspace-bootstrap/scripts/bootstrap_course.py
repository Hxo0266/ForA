#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
bootstrap_course.py — 把已有的「课程自动化学习流程」整套部署到一门新课程

用法
    ① 部署新课程
        python bootstrap_course.py --source "<已有课程根>" --target "<新课程根>" --code MAT3007
                                   [--automation-time 22:00]
    ② 自动化建好后回填信息（自动化只能由 Agent 通过 automation_update 创建，脚本无法代劳）
        python bootstrap_course.py --target "<新课程根>" --code MAT3007 \
                                   --patch-automation <自动化ID> <HH:MM>

资产分流原则（见 ERROR_LOG 的 AIE-015 / AIE-016）
    复制并改名 : _System/scripts/*.py · _System/prompts/* · _System/WORKFLOW.md ·
                 _System/ERROR_LOG.md · _System/taxonomy.json · README.md
    重建（骨架）: 3_Essence/00_Index.md · Outline of <CODE>.md
    绝不复制   : logs/ · extracted/ · 2_Textbook&Lecture_PPT/ · 3_Essence 下的笔记 · Outline of <源课程>.md
    ⚠️ 脚本内不得出现硬编码课程名（AIE-016），一切从 --code 推导。
    ⚠️ 目录名一律照 taxonomy.json 的 folders 建（AIE-018 / AIE-024），不要另起一套。

退出码  0=成功；1=参数/环境错误；3=有文件被跳过
"""

from __future__ import annotations

import argparse
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:  # pragma: no cover
    pass

FOLDERS = [
    "0_inbox", "1_Syllabus", "2_Textbook&Lecture_PPT", "3_Essence",
    "4_Assignment", "5_Quiz", "6_Midterm Examination", "7_Final Examination",
    "8_Correction_Notebook", "10_Others",
    "_System", "_System/scripts", "_System/prompts", "_System/extracted", "_System/logs",
]
STAMP = datetime.now().strftime("%Y-%m-%d")

skipped: list[str] = []


def say(msg: str) -> None:
    print(msg)


def write(path: Path, content: str, force: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and not force:
        skipped.append(str(path))
        return
    path.write_text(content, encoding="utf-8")


def copy_file(src: Path, dst: Path, force: bool = False) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.exists() and not force:
        skipped.append(str(dst))
        return
    shutil.copy2(src, dst)


def rewrite(text: str, src_code: str, dst_code: str) -> str:
    """源课程代号 → 目标课程代号；同时换掉自动化名与 ID。顺序：先具体后笼统。"""
    if src_code:
        text = re.sub(rf"\b{re.escape(src_code)}\b", dst_code, text)
    return text


# ─────────────────────────── ① 部署 ───────────────────────────
def bootstrap(source: Path, target: Path, code: str, auto_time: str | None, force: bool) -> int:
    for sub in ("_System", "_System/scripts", "_System/taxonomy.json"):
        if not (source / sub).exists():
            say(f"[ERROR] 源课程缺少 {sub}：{source}")
            return 1
    src_code = source.name

    say(f"[bootstrap] 源：{source}（代号 {src_code}）")
    say(f"[bootstrap] 目标：{target}（代号 {code}）")
    say("")

    for d in FOLDERS:
        (target / d).mkdir(parents=True, exist_ok=True)
    say(f"[1/6] 目录骨架：{len(FOLDERS)} 个")

    # 脚本
    n = 0
    for f in sorted((source / "_System" / "scripts").glob("*.py")):
        copy_file(f, target / "_System" / "scripts" / f.name, force)
        n += 1
    say(f"[2/6] 脚本：{n} 个 .py")

    # taxonomy
    tax = (source / "_System" / "taxonomy.json").read_text(encoding="utf-8")
    tax = re.sub(r'"course"\s*:\s*"[^"]*"', f'"course": "{code}"', tax, count=1)
    write(target / "_System" / "taxonomy.json", tax, force)
    say("[3/6] taxonomy.json（course 已改）")

    # prompts
    pn = 0
    for f in sorted((source / "_System" / "prompts").glob("*.md")):
        write(target / "_System" / "prompts" / f.name,
              rewrite(f.read_text(encoding="utf-8"), src_code, code), force)
        pn += 1
    say(f"[4/6] prompts：{pn} 个")

    # WORKFLOW.md
    wf = rewrite((source / "_System" / "WORKFLOW.md").read_text(encoding="utf-8"), src_code, code)
    auto_line = (
        f"| 频率 | **每周六 {auto_time}** |" if auto_time
        else "| 频率 | `待配置` —— 见本文件 §8.1 与 ERROR_LOG 头部 |"
    )
    wf = re.sub(r"\| 频率 \| \*\*(?:每天|每周六)[^|]*\|", auto_line, wf, count=1)
    wf = re.sub(r"\| ID \| `[0-9a-f\-]{36}` \|", "| ID | `<见 ERROR_LOG 头部>` |", wf, count=1)
    wf = re.sub(r"\| 首次运行 \| [^|]*\|", f"| 首次运行 | `待首次触发` |", wf, count=1)
    wf += (
        f"\n| {STAMP} | 本工作区由 **{src_code}** 整套流程部署而来（`bootstrap_course.py`）："
        f"继承 ERROR_LOG 的既有流程级教训；本课程新增教训**从下一个未占用编号**起。 |\n"
    )
    write(target / "_System" / "WORKFLOW.md", wf, force)
    say("[5/6] WORKFLOW.md（已改课程名与自动化信息）")

    # ERROR_LOG.md —— 头部加继承说明
    el_path = source / "_System" / "ERROR_LOG.md"
    el = el_path.read_text(encoding="utf-8")
    ids = re.findall(r"^##\s+(AIE-\d+)", el, re.M)
    last = ids[-1] if ids else "AIE-000"
    nxt = f"AIE-{int(last.split('-')[1]) + 1:03d}" if ids else "AIE-001"
    auto_desc = (
        f"`{code} 课件自动提炼 Essence`（每周六 {auto_time}）" if auto_time
        else f"`{code} 课件自动提炼 Essence`（**待配置**：需用 automation_update 创建，时刻请与已有课程错开）"
    )
    header = (
        f"# ERROR_LOG — {code} 课程自动化学习流程\n\n"
        f"> ℹ️ **本文件继承自 {src_code} 工作区**（整套流程为同源部署）。\n"
        f"> 现有 **{ids[0]} ~ {last}**（共 {len(ids)} 条）是**流程级**教训，与具体课程无关，故原样保留；"
        f"其中出现「{src_code}」的地方，指的是这套流程最初建立的位置。\n"
        f"> **本课程（{code}）新增的教训请从「文件内现有最大编号 + 1」起编号**"
        f"（先 `grep \"^## AIE-\"` 确认），不要覆盖或重排继承条目。\n"
        f"> 本课程自动化：{auto_desc}。\n\n---\n"
    )
    body = re.sub(r"^# ERROR_LOG[^\n]*\n", "", el, count=1).lstrip("\n")
    write(target / "_System" / "ERROR_LOG.md", header + body, force)
    say(f"[6/6] ERROR_LOG.md（继承 {ids[0]}~{last}，新增从 {nxt} 起）")

    # README.md
    rd = rewrite((source / "README.md").read_text(encoding="utf-8"), src_code, code)
    rd = re.sub(r"（\d+ 条 AIE-001~\d+）", f"（{len(ids)} 条 {ids[0]}~{last}，继承自 {src_code}）", rd)
    rd = re.sub(r"^# .* · 课程自动化学习流程",
                f"# {code} · 课程自动化学习流程\n\n> ℹ️ 本工作区由 **{src_code}** 的整套流程部署而来"
                f"（见 `_System/ERROR_LOG.md` 头部继承说明）。", rd, count=1, flags=re.M)
    write(target / "README.md", rd, force)

    # Essence 索引
    write(target / "3_Essence" / "00_Index.md", f"""---
course: {code}
type: index
updated: {STAMP}
---

# Essence 索引 · {code}

每份课件在 `2_Textbook&Lecture_PPT/` 里对应本目录下的一个**同名**（slug 化）`.md` 知识点笔记。

| # | 课件 | 主题 | 张数 | 笔记 | 更新时间 |
|:--|:--|:--|:--|:--|:--|
| — | *(暂无)* | | | | |

## 维护说明

1. 每生成/重写一份笔记，就在上表补一行。
2. 本文件（`00_Index.md`）**不参与**「课件 ↔ 笔记」覆盖率统计。
3. 覆盖率自检：
   ```bash
   python "../_System/scripts/run_pipeline.py" --root ".." --essence-only
   ```

## 状态

- 课件数：0（教材 PDF 不计入，见 `non_deck_keywords`）
- 已有笔记数：0
- 待提炼：0

> 本工作区由 `{src_code}` 的整套流程部署而来（{STAMP}）。
""", force)

    # Outline 骨架
    write(target / f"Outline of {code}.md", f"""---
course: {code}
type: outline
generated: {STAMP}
status: 骨架（缺教学大纲与教材）
---

# Outline of {code}

> ⚠️ **本文件目前只是骨架**：`1_Syllabus/` 空、`2_Textbook&Lecture_PPT/` 里还没有教材，**没有任何事实来源**，因此下方一律不做推测，全部标为 `[待补充]`。
>
> **补齐方法**：
> 1. 把本课教学大纲（Course Outline / Syllabus，PDF / Word / 图片均可）放进 `0_inbox/`，然后说「处理一下 inbox」——它会按税表自动归入 `1_Syllabus/`。
> 2. 把课本放进 `2_Textbook&Lecture_PPT/`（与课件同一目录；或直接告知教材名称，可由助手联网核准目录）。
> 3. 说一句「生成 Outline of {code}」——助手会合并大纲与教材目录，补全本文件。

## 1. 课程标识

| 项 | 值 |
|:--|:--|
| 课程代号 | **{code}** |
| 课程标题 | `[待补充：需 Syllabus]` |
| 开课单位 / 授课教师 | `[待补充：需 Syllabus]` |
| 学分 / 周学时 | `[待补充：需 Syllabus]` |
| 学期 | `[待补充]` |
| 考核方式与占比 | `[待补充：需 Syllabus]` |
| 课程学习目标（ILOs） | `[待补充：需 Syllabus]` |

## 2. 教材

| 项 | 内容 |
|:--|:--|
| 主教材 | `[待补充：需放入 2_Textbook&Lecture_PPT/]` |
| 同目录配套 | `[待补充]` |
| 先修要求 | `[待补充：需 Syllabus]` |

## 3. 课程纲要（按教材章节）

`[待补充：2_Textbook&Lecture_PPT/ 中无教材，无法生成]`

## 4. 建议学习顺序

`[待补充]`

## 5. 待补充清单

- [ ] 将教学大纲放入 `1_Syllabus/`
- [ ] 将教材放入 `2_Textbook&Lecture_PPT/`
- [ ] 补全第 1、2、3、4 节

## 6. 与学习工作流的对接

| 工作流组件 | 与本纲要的关系 |
|:--|:--|
| `1_Syllabus/` | 教学大纲与全部课程非教学内容；本文件头部信息由它补齐 |
| `2_Textbook&Lecture_PPT/` | 教材 + 各讲课件（**已合并**）；用「提炼 PPT 知识点」生成笔记 |
| `3_Essence/` | 每份课件对应的同名（slug 化）`.md` 知识点笔记 |
| `4_Assignment/` | 课程作业（homework / assignment / lab report / project / 习题） |
| `5_Quiz/` | 小测 / 随堂演练 / 课堂练习 |
| `6_Midterm Examination/`、`7_Final Examination/` | 期中、期末试卷与答案 |

---

*本骨架由 `bootstrap_course.py` 生成于 {STAMP}（由 {src_code} 的整套流程部署而来）。在第 1 节 `[待补充]` 全部落实前，本文件不包含任何关于 {code} 课程内容的断言。*
""", force)

    say("")
    if skipped:
        say(f"[!] 有 {len(skipped)} 个文件已存在被跳过（加 --force 可覆盖）：")
        for s in skipped[:10]:
            say("    " + s)
    say("")
    say("【下一步 —— 必须由 Agent 完成，脚本做不了】")
    say(f"  1) 用 automation_update 建定时自动化：")
    say(f"       名称：{code} 课件自动提炼 Essence")
    say(f"       作用域 cwds：{target}")
    say(f"       时刻：**每周六**选一个与已有课程错开的整点/半点（已有：AIE2040 周六 00:00、CHM1001 周六 00:15、MAT3007 周六 00:30）")
    say(f"       rrule 形如：FREQ=WEEKLY;BYDAY=SA;BYHOUR=0;BYMINUTE=<下一步的错峰分钟>")
    say(f"       提示词：复制已有课程的同类自动化，把课程代号换成本课程")
    say(f"  2) 拿到自动化 ID 后回填：")
    say(f"       python bootstrap_course.py --target \"{target}\" --code {code} --patch-automation <ID> <HH:MM>")
    say(f"  3) 跑一遍核对：python \"{target}/_System/scripts/health_check.py\" --root \"{target}\" --phase both")
    return 3 if skipped else 0


# ────────────────────── ② 回填自动化信息 ──────────────────────
def patch_automation(target: Path, code: str, auto_id: str, auto_time: str) -> int:
    name = f"{code} 课件自动提炼 Essence"
    changed = []

    wf_path = target / "_System" / "WORKFLOW.md"
    if wf_path.is_file():
        t = wf_path.read_text(encoding="utf-8")
        t = re.sub(r"\| 名称 \| `[^`]*` \|", f"| 名称 | `{name}` |", t, count=1)
        t = re.sub(r"\| ID \| `[^`]*` \|", f"| ID | `{auto_id}` |", t, count=1)
        t = re.sub(r"\| 频率 \| \*\*(?:每天|每周六)[^|]*\|",
                   f"| 频率 | **每周六 {auto_time}** |", t, count=1)
        t = re.sub(r"\| 频率 \| `待配置`[^|]*\|", f"| 频率 | **每周六 {auto_time}** |", t, count=1)
        t = re.sub(r"\| 首次运行 \| [^|]*\|", "| 首次运行 | `待首次触发` |", t, count=1)
        wf_path.write_text(t, encoding="utf-8")
        changed.append(str(wf_path))

    el_path = target / "_System" / "ERROR_LOG.md"
    if el_path.is_file():
        t = el_path.read_text(encoding="utf-8")
        t = re.sub(r"> 本课程自动化：[^\n]*",
                   f"> 本课程自动化：`{name}`（ID `{auto_id}`，每周六 {auto_time}）。", t, count=1)
        el_path.write_text(t, encoding="utf-8")
        changed.append(str(el_path))

    for c in changed:
        say(f"[patch] 已更新 {c}")
    say(f"[patch] 自动化 `{name}`（ID {auto_id}，每周六 {auto_time}）信息已回填")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="课程工作流整套部署")
    ap.add_argument("--source", default=None, help="作为模板的已有课程根目录")
    ap.add_argument("--target", required=True, help="新课程根目录")
    ap.add_argument("--code", required=True, help="新课程代号，如 MAT3007")
    ap.add_argument("--automation-time", default=None, help="自动化时刻 HH:MM（仅用于文档占位）")
    ap.add_argument("--patch-automation", nargs=2, metavar=("ID", "HH:MM"),
                    help="回填自动化 ID 与时刻（不重新部署）")
    ap.add_argument("--force", action="store_true", help="覆盖已存在的文件")
    args = ap.parse_args()

    target = Path(args.target).expanduser().resolve()
    if args.patch_automation:
        auto_id, auto_time = args.patch_automation
        if not target.is_dir():
            say(f"[ERROR] 目标不存在：{target}")
            return 1
        return patch_automation(target, args.code, auto_id, auto_time)

    if not args.source:
        say("[ERROR] 首次部署必须给 --source（用哪门已有课程作模板）")
        return 1
    return bootstrap(Path(args.source).expanduser().resolve(), target, args.code,
                     args.automation_time, args.force)


if __name__ == "__main__":
    raise SystemExit(main())
