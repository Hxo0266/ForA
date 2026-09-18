#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
triage_inbox.py — 课程 Inbox 自动分类器（course-inbox-triage skill 的主脚本）

用途
    扫描 <course_root>/0_inbox 下的所有文件，依据「扩展名 + 文件名关键词 +（必要时）内容首段」
    判断该材料属于哪一类，然后移动到对应文件夹（1_Syllabus / 2_Textbook&Lecture_PPT /
    3_Essence / 4_Assignment / 5_Quiz / 6_Midterm Examination / 7_Final Examination /
    10_Others）。目录名一律从 _System/taxonomy.json 解析，代码不得硬编码（AIE-018/024）。

安全设计（对齐 personal-files 安全规约）
    1. 默认「只出计划」(dry-run)，必须显式加 --apply 才真正移动。
    2. 从不删除任何文件；只做同卷移动。
    3. 每次 --apply 都写一份可回滚的 manifest，可用 --undo 一键撤回。
    4. 单批默认最多 10 个文件（--batch-size 调整；--all 解除）。
    5. 内容级重复文件默认跳过并标记，交由人工决定（不自动删、不自动合）。

输入
    --root <path>        课程根目录（含 _System/taxonomy.json）。缺省从当前工作目录向上自动探测。
    --apply              真正执行移动（缺省为 dry-run）。
    --batch-size N       单次最多处理 N 个（默认 10；0 或 --all 表示不限）。
    --all                等同 --batch-size 0。
    --include <patt>     只处理文件名匹配该 glob 的文件（可多次）。
    --undo <stamp>       撤回一次已有运行：stamp 形如 20260914-160602（见 logs/moved_<stamp>.json）。
    --taxonomy <path>    显式指定 taxonomy.json。

输出
    _System/logs/triage_<timestamp>.md    人类可读的分类报告（Markdown 表格）
    _System/logs/moved_<timestamp>.json   本次实际移动清单（用于 --undo）

退出码
    0 = 正常；1 = 参数/环境错误
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path

# --- Windows 终端中文输出（见 ERROR_LOG 2026-07-16「中文输出乱码」）------------
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:  # pragma: no cover
    pass


# ─────────────────────────── 默认税表（兜底） ───────────────────────────
# 课程目录存在 _System/taxonomy.json 时以其为准；此兜底仅保证「没有配置文件也能跑」。
FALLBACK_TAXONOMY: dict = {
    "folders": {
        "inbox": "0_inbox",
        "syllabus": "1_Syllabus",
        "slides": "2_Textbook&Lecture_PPT",
        "textbook": "2_Textbook&Lecture_PPT",
        "essence": "3_Essence",
        "assignment": "4_Assignment",
        "quiz": "5_Quiz",
        "midterm": "6_Midterm Examination",
        "final": "7_Final Examination",
        "others": "10_Others"
    },
    "optional_folders": {},
    "skip_names": [
        "thumbs.db",
        "desktop.ini",
        ".ds_store",
        "icon\r"
    ],
    "skip_prefixes": [
        "~$",
        "._",
        ".~"
    ],
    "skip_exts": [
        ".tmp",
        ".part",
        ".crdownload",
        ".lock",
        ".lnk",
        ".ini"
    ],
    "keywords": {
        "final": [
            "final",
            "finals",
            "期末考试",
            "期末考",
            "期末",
            "末考",
            "大一统考"
        ],
        "midterm": [
            "midterm",
            "mid-term",
            "mid_term",
            "midtermexam",
            "期中考试",
            "期中考",
            "期中",
            "中段考"
        ],
        "exam": [
            "exam",
            "examination",
            "test",
            "mock",
            "试卷",
            "真题",
            "统考",
            "考试"
        ],
        "answer": [
            "answer",
            "answers",
            "ans",
            "solution",
            "solutions",
            "sol",
            "key",
            "答案",
            "解答",
            "参考答案",
            "解析"
        ],
        "slides": [
            "slide",
            "slides",
            "lecture",
            "ppt",
            "pptx",
            "chapter",
            "chap",
            "lect",
            "课件",
            "讲义",
            "幻灯片",
            "tutorial",
            "tut"
        ],
        "essence": [
            "essence",
            "summary",
            "digest",
            "笔记",
            "总结",
            "提炼",
            "知识点",
            "提纲",
            "纲要"
        ],
        "textbook": [
            "textbook",
            "教材",
            "课本",
            "参考书",
            "text"
        ],
        "syllabus": [
            "syllabus",
            "course outline",
            "course description",
            "course info",
            "course policy",
            "grading policy",
            "grading scheme",
            "grading",
            "assessment",
            "academic integrity",
            "honor code",
            "rubric",
            "reading list",
            "schedule",
            "timetable",
            "calendar",
            "handbook",
            "office hours",
            "attendance",
            "教学大纲",
            "课程大纲",
            "课程纲要",
            "课程介绍",
            "课程简介",
            "评分标准",
            "考核方式",
            "评分细则",
            "课程安排",
            "教学安排",
            "课表",
            "学术诚信",
            "出勤",
            "选课",
            "课程说明"
        ],
        "quiz": [
            "quiz",
            "quizzes",
            "pop quiz",
            "popquiz",
            "小测",
            "小测验",
            "随堂",
            "随堂演练",
            "随堂测验",
            "随堂练习",
            "课堂测验",
            "课堂练习",
            "mini test"
        ],
        "assignment": [
            "homework",
            "assignment",
            "hw",
            "作业",
            "大作业",
            "实验报告",
            "lab report",
            "lab",
            "report",
            "project",
            "习题",
            "练习册"
        ]
    },
    "non_deck_keywords": [
        "textbook",
        "教材",
        "课本",
        "参考书",
        "solution",
        "solutions",
        "解答",
        "答案",
        "edition",
        "习题解答",
        "教师用书"
    ],
    "lecture_token_patterns": [
        "^l\\d{1,2}$",
        "^lec\\d{1,2}$",
        "^lect\\d{1,2}$",
        "^ch\\d{1,2}$",
        "^chap\\d{1,2}$",
        "^chapter\\d{1,2}$",
        "^week\\d{1,2}$",
        "^wk\\d{1,2}$",
        "^unit\\d{1,2}$",
        "^topic\\d{1,2}$",
        "^session\\d{1,2}$"
    ],
    "slide_exts": [
        ".ppt",
        ".pptx",
        ".key",
        ".odp"
    ],
    "doc_exts": [
        ".pdf",
        ".doc",
        ".docx",
        ".md",
        ".txt",
        ".rtf",
        ".odt"
    ],
    "content_peek_keywords": {
        "midterm": [
            "midterm",
            "mid-term",
            "期中",
            "middle term"
        ],
        "final": [
            "final examination",
            "final exam",
            "期末考试",
            "final test"
        ],
        "slides": [
            "lecture",
            "chapter",
            "agenda",
            "outline",
            "learning objectives",
            "课件"
        ]
    },
    "batch_size_default": 10
}

CJK = re.compile(r"[\u4e00-\u9fff]")


# ─────────────────────────────── 工具函数 ───────────────────────────────
def norm(text: str) -> str:
    """小写化，并把非字母数字/非中日韩字符压成单个空格，便于分词。"""
    return re.sub(r"[^0-9a-z\u4e00-\u9fff]+", " ", text.lower()).strip()


def tokenize(text: str) -> list[str]:
    return [t for t in norm(text).split() if t]


def sha256_of(path: Path, chunk: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        while True:
            block = fh.read(chunk)
            if not block:
                break
            h.update(block)
    return h.hexdigest()


def find_course_root(start: Path) -> Path:
    """找课程根：**优先认税表**，其次认「有个叫 *inbox* 的目录」。

    ⚠️ 不要靠 `Inbox/ + PPT/` 认根：目录已改名为 `0_inbox/`、`2_Textbook&Lecture_PPT/`，
    那套判断会直接失效（AIE-018 / AIE-024）。
    """
    for p in [start, *start.parents]:
        try:
            if (p / "_System" / "taxonomy.json").is_file():
                return p
            if any(d.is_dir() and "inbox" in d.name.lower() for d in p.iterdir()):
                return p
        except OSError:
            continue
    return start


def load_taxonomy(root: Path, explicit: str | None) -> tuple[dict, str]:
    """返回 (taxonomy, 来源说明)。课程目录配置优先，缺失则用内置兜底。"""
    candidates = []
    if explicit:
        candidates.append(Path(explicit))
    candidates.append(root / "_System" / "taxonomy.json")
    for c in candidates:
        if c.is_file():
            try:
                data = json.loads(c.read_text(encoding="utf-8"))
                # 与兜底做一层浅合并，保证老配置缺字段时仍能运行
                merged = json.loads(json.dumps(FALLBACK_TAXONOMY))
                for k, v in data.items():
                    if isinstance(v, dict) and isinstance(merged.get(k), dict):
                        merged[k].update(v)
                    else:
                        merged[k] = v
                return merged, str(c)
            except Exception as exc:  # noqa: BLE001
                print(f"[WARN] 读取税表失败 {c}: {exc}；改用内置兜底", file=sys.stderr)
    return FALLBACK_TAXONOMY, "<builtin fallback>"


# ─────────────────────────── 分类核心逻辑 ───────────────────────────
def hit_keywords(haystack_tokens: list[str], haystack_text: str, keywords: list[str]) -> list[str]:
    """返回命中的关键词列表。

    匹配规则（三种，缺一不可）：
      1. 含中日韩字符 → 在原文里做**子串**匹配（中文没有词边界）；
      2. 含空格或连字符（多词短语，如 "course outline"）→ 在**归一化后的整串**里做子串匹配；
      3. 其余英文单词 → 按**整词**匹配（避免 final 里命中 fin、Midterm 里命中 mid）。
    """
    hits: list[str] = []
    tokset = set(haystack_tokens)
    joined = " ".join(haystack_tokens)
    for kw in keywords:
        if CJK.search(kw):
            if kw in haystack_text:
                hits.append(kw)
        elif " " in kw or "-" in kw:
            if norm(kw) in joined:
                hits.append(kw)
        else:
            # 英文单词按整词匹配；额外允许「关键词+数字」的紧凑写法
            # （assignment2 / hw3 / quiz1 / lab1 / chapter5）——AIE-024 实测补丁。
            if kw in tokset or any(
                re.fullmatch(re.escape(kw) + r"\d+", t) for t in haystack_tokens
            ):
                hits.append(kw)
    return hits


def looks_like_lecture(tokens: list[str], patterns: list[str]) -> str | None:
    for t in tokens:
        for pat in patterns:
            if re.match(pat, t):
                return t
    return None


def peek_text(path: Path, root: Path, limit: int = 4000) -> str:
    """只读前若干页/张的内容文本，用于消歧。失败返回空串（不抛错）。"""
    ext = path.suffix.lower()
    try:
        if ext == ".pdf":
            try:
                import pymupdf  # type: ignore
            except Exception:  # noqa: BLE001
                import fitz as pymupdf  # type: ignore
            out = []
            with pymupdf.open(str(path)) as doc:
                for page in doc[:4]:
                    out.append(page.get_text("text"))
                    if sum(len(x) for x in out) > limit:
                        break
            return "\n".join(out)[:limit]
        if ext == ".pptx":
            from pptx import Presentation  # type: ignore
            prs = Presentation(str(path))
            out = []
            for slide in list(prs.slides)[:6]:
                for shape in slide.shapes:
                    if shape.has_text_frame:
                        out.append(shape.text_frame.text)
                        if sum(len(x) for x in out) > limit:
                            break
            return "\n".join(out)[:limit]
        if ext == ".docx":
            import docx  # type: ignore
            d = docx.Document(str(path))
            return "\n".join(p.text for p in d.paragraphs[:80])[:limit]
    except Exception:  # noqa: BLE001
        return ""
    return ""


def classify(path: Path, tax: dict, root: Path) -> dict:
    """返回 {'target': <folder_key>, 'reason': str, 'flags': [...]}"""
    name = path.name
    stem_tokens = tokenize(path.stem)
    text_all = norm(path.stem)
    kw = tax["keywords"]

    flags: list[str] = []

    h_final = hit_keywords(stem_tokens, text_all, kw.get("final", []))
    h_mid = hit_keywords(stem_tokens, text_all, kw.get("midterm", []))
    h_exam = hit_keywords(stem_tokens, text_all, kw.get("exam", []))
    h_ans = hit_keywords(stem_tokens, text_all, kw.get("answer", []))
    h_slide = hit_keywords(stem_tokens, text_all, kw.get("slides", []))
    h_ess = hit_keywords(stem_tokens, text_all, kw.get("essence", []))
    h_syl = hit_keywords(stem_tokens, text_all, kw.get("syllabus", []))
    h_tb = hit_keywords(stem_tokens, text_all, kw.get("textbook", []))
    h_assign = hit_keywords(stem_tokens, text_all, kw.get("assignment", []))
    h_quiz = hit_keywords(stem_tokens, text_all, kw.get("quiz", []))
    lec_token = looks_like_lecture(stem_tokens, tax.get("lecture_token_patterns", []))

    if h_ans:
        flags.append("疑似含答案/解析：" + "/".join(h_ans))

    # ---- 定级：final > midterm > quiz > assignment > (泛 exam) > syllabus
    #            > essence > slides / textbook（合并目录） > others ----
    if h_final:
        if h_mid:
            flags.append("文件名同时含期中与期末关键词，已按期末处理")
        if h_assign:
            flags.append(
                "同时命中作业关键词，疑似期末项目/报告，请人工确认是否应归 "
                + tax["folders"].get("assignment", "4_Assignment")
            )
        return {"target": "final", "reason": "文件名命中期末关键词：" + "/".join(h_final), "flags": flags}
    if h_mid:
        return {"target": "midterm", "reason": "文件名命中期中关键词：" + "/".join(h_mid), "flags": flags}
    if h_quiz and not (h_slide or lec_token):
        # 5_Quiz/ = 课程小测 / 随堂演练 / 课堂练习
        return {"target": "quiz", "reason": "文件名命中测验关键词：" + "/".join(h_quiz), "flags": flags}
    if h_assign and not (h_slide or lec_token):
        # 4_Assignment/ = 课程作业（homework / assignment / lab report / project …）
        return {"target": "assignment", "reason": "文件名命中作业关键词：" + "/".join(h_assign), "flags": flags}
    if h_exam and not (h_slide or lec_token):
        flags.append("仅命中泛考试关键词，未标明期中/期末，需人工确认归属")
        return {"target": "others", "reason": "命中泛考试关键词但无期中/期末标识：" + "/".join(h_exam), "flags": flags}
    if h_syl and not (lec_token or h_slide):
        # Syllabus/ = 教学大纲 + 全部课程非教学内容（评分/考核方式/课表/学术诚信/教师信息…）
        return {"target": "syllabus", "reason": "命中大纲/非教学类关键词：" + "/".join(h_syl), "flags": flags}
    if h_ess:
        # Essence/ 的契约是「与课件同名的 .md 知识点笔记」，不接收素材类文件（pdf/docx 等）
        if path.suffix.lower() == ".md":
            return {"target": "essence", "reason": "文件名命中笔记类关键词：" + "/".join(h_ess), "flags": flags}
        flags.append("文件名像笔记/总结材料，但 Essence/ 只收与课件同名的 .md；已归入 Others")
        return {
            "target": "others",
            "reason": f"命中笔记类关键词（{'/'.join(h_ess)}）但扩展名 {path.suffix.lower()} 不是 .md",
            "flags": flags,
        }
    if h_slide or lec_token or path.suffix.lower() in tax.get("slide_exts", []):
        why = []
        if h_slide:
            why.append("关键词 " + "/".join(h_slide))
        if lec_token:
            why.append("讲次编号 " + lec_token)
        if path.suffix.lower() in tax.get("slide_exts", []):
            why.append("课件扩展名 " + path.suffix.lower())
        return {"target": "slides", "reason": "判定为课件（" + "、".join(why) + "）", "flags": flags}

    # Textbook/ 已与 PPT/ 合并进同一个 2_Textbook&Lecture_PPT/（AIE-024）：
    # 教材类材料直接归入合并后的课件目录，不再单独判定（optional_folders 已清空）。
    if h_tb:
        return {"target": "slides", "reason": "文件名命中教材关键词，归入合并后的课件目录：" + "/".join(h_tb), "flags": flags}

    # ---- 无结论时做内容探测 ----
    ext = path.suffix.lower()
    if ext in tax.get("doc_exts", []) + tax.get("slide_exts", []):
        body = norm(peek_text(path, root))
        if body:
            for key in ("midterm", "final", "slides"):
                kws = tax.get("content_peek_keywords", {}).get(key, [])
                if kws and hit_keywords(tokenize(body), body, kws):
                    flags.append("依据内容首段判定，建议人工复核")
                    pretty = {"midterm": "期中", "final": "期末", "slides": "课件"}[key]
                    return {"target": key, "reason": f"文件名无线索，但正文出现{pretty}特征", "flags": flags}

    return {"target": "others", "reason": "未命中任何专项规则", "flags": flags}


def should_skip(path: Path, tax: dict) -> str | None:
    name_l = path.name.lower()
    if name_l in [s.lower() for s in tax.get("skip_names", [])]:
        return "系统/隐藏文件"
    if any(name_l.startswith(p.lower()) for p in tax.get("skip_prefixes", [])):
        return "Office 临时锁文件"
    if path.suffix.lower() in tax.get("skip_exts", []):
        return "临时/快捷方式文件"
    if path.name.startswith("."):
        return "隐藏文件"
    return None


def unique_dest(dest_dir: Path, name: str) -> Path:
    dest = dest_dir / name
    if not dest.exists():
        return dest
    stem, suf = Path(name).stem, Path(name).suffix
    i = 2
    while True:
        cand = dest_dir / f"{stem} ({i}){suf}"
        if not cand.exists():
            return cand
        i += 1


# ─────────────────────────────── 主流程 ───────────────────────────────
def main() -> int:
    ap = argparse.ArgumentParser(description="课程 Inbox 自动分类器")
    ap.add_argument("--root", default=None, help="课程根目录（含 _System/taxonomy.json）")
    ap.add_argument("--apply", action="store_true", help="真正执行移动（缺省只出计划）")
    ap.add_argument("--batch-size", type=int, default=None, help="单次最多处理 N 个文件")
    ap.add_argument("--all", action="store_true", help="不限制单批数量")
    ap.add_argument("--include", action="append", default=[], help="只处理匹配该 glob 的文件")
    ap.add_argument("--undo", default=None, help="撤回某次运行，如 20260914-160602（秒级时间戳）")
    ap.add_argument("--taxonomy", default=None, help="显式指定 taxonomy.json")
    args = ap.parse_args()

    cwd = Path.cwd()
    root = Path(args.root).expanduser().resolve() if args.root else find_course_root(cwd)
    if not root.is_dir():
        print(f"[ERROR] 课程根目录不存在：{root}", file=sys.stderr)
        return 1

    tax, tax_src = load_taxonomy(root, args.taxonomy)
    fmap = tax["folders"]
    logs_dir = root / "_System" / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)

    # ---------- undo 分支 ----------
    if args.undo:
        return do_undo(root, logs_dir, args.undo)

    inbox = root / fmap["inbox"]
    if not inbox.is_dir():
        print(f"[ERROR] 未找到 Inbox 目录：{inbox}", file=sys.stderr)
        return 1

    # 时间戳精确到秒：同一分钟内的多次运行若共用 stamp，会互相覆盖 moved_*.json 而破坏 --undo
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    batch = 0 if args.all else (args.batch_size or tax.get("batch_size_default", 10))

    rows: list[dict] = []
    skipped: list[tuple[Path, str]] = []

    # 收集待处理文件（递归，跳过隐藏目录）
    files: list[Path] = []
    for p in sorted(inbox.rglob("*")):
        if not p.is_file():
            continue
        rel = p.relative_to(inbox)
        if any(part.startswith(".") for part in rel.parts[:-1]):
            continue
        if args.include and not any(p.match(g) for g in args.include):
            continue
        files.append(p)

    for p in files:
        reason_skip = should_skip(p, tax)
        if reason_skip:
            skipped.append((p, reason_skip))
            continue
        verdict = classify(p, tax, root)
        target_key = verdict["target"]
        target_dir = root / fmap.get(target_key) or (root / fmap["others"])
        if target_key in tax.get("optional_folders", {}):
            target_dir = root / tax["optional_folders"][target_key]
        rows.append(
            {
                "src": p,
                "rel": str(p.relative_to(inbox)),
                "target_key": target_key,
                "target_dir": target_dir,
                "reason": verdict["reason"],
                "flags": verdict["flags"],
                "dup_of": None,
                "action": "PLAN",
                "dst": None,
            }
        )

    # 重复检测（同内容已在目标目录存在 → 跳过，交人工）
    for row in rows:
        try:
            h = sha256_of(row["src"])
        except Exception:  # noqa: BLE001
            continue
        row["_sha"] = h
        td = row["target_dir"]
        if td.is_dir():
            for other in td.rglob("*"):
                if other.is_file() and other.name == row["src"].name:
                    try:
                        if sha256_of(other) == h:
                            row["dup_of"] = str(other)
                            row["action"] = "SKIP-DUPLICATE"
                            break
                    except Exception:  # noqa: BLE001
                        pass
    # 同批内互相重复也标记
    seen: dict[str, Path] = {}
    for row in rows:
        h = row.get("_sha")
        if not h or row["dup_of"]:
            continue
        if h in seen:
            row["dup_of"] = str(seen[h])
            row["action"] = "SKIP-DUPLICATE"
        else:
            seen[h] = row["src"]

    actionable = [r for r in rows if r["action"] == "PLAN"]
    limited = actionable[:batch] if batch else actionable
    deferred = actionable[batch:] if batch else []

    # ---------- 执行 ----------
    moved: list[dict] = []
    if args.apply:
        for row in limited:
            row["target_dir"].mkdir(parents=True, exist_ok=True)
            dst = unique_dest(row["target_dir"], row["src"].name)
            try:
                shutil.move(str(row["src"]), str(dst))
                row["action"] = "MOVED"
                row["dst"] = str(dst)
                moved.append({"src": str(row["src"]), "dst": str(dst), "target": row["target_key"]})
            except Exception as exc:  # noqa: BLE001
                row["action"] = "FAILED"
                row["flags"].append(f"移动失败：{exc}")
        if moved:
            mf = logs_dir / f"moved_{stamp}.json"
            payload = {
                "stamp": stamp,
                "root": str(root),
                "created": datetime.now().isoformat(timespec="seconds"),
                "moves": moved,
            }
            mf.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    else:
        for row in limited:
            row["action"] = "PLAN"

    # ---------- 报告 ----------
    report = logs_dir / f"triage_{stamp}.md"
    report.write_text(
        render_report(root, tax_src, stamp, rows, skipped, limited, deferred, args.apply, fmap, tax),
        encoding="utf-8",
    )

    # ---------- 终端摘要 ----------
    counts: dict[str, int] = {}
    for r in rows:
        counts[r["target_key"]] = counts.get(r["target_key"], 0) + 1
    mode = "APPLY（已实际移动）" if args.apply else "DRY-RUN（仅出计划，未动文件）"
    print(f"[triage] 模式：{mode}")
    print(f"[triage] 课程根目录：{root}")
    print(f"[triage] 税表来源：{tax_src}")
    print(f"[triage] Inbox 扫描到 {len(rows)} 个待分类文件（另有 {len(skipped)} 个被跳过）")
    for k, v in sorted(counts.items(), key=lambda x: -x[1]):
        label = fmap.get(k) or tax.get("optional_folders", {}).get(k, k)
        print(f"         {label:<24} {v}")
    if args.apply:
        print(f"[triage] 已移动 {len(moved)} 个 → 清单 {logs_dir / f'moved_{stamp}.json'}")
    else:
        print(f"[triage] 本轮计划移动 {len(limited)} 个（加 --apply 才真正执行）")
    if deferred:
        print(f"[triage] 受单批上限 {batch} 限制，还有 {len(deferred)} 个未纳入本轮；再跑一次或加 --all")
    print(f"[triage] 报告：{report}")
    return 0


def render_report(root: Path, tax_src: str, stamp: str, rows, skipped, limited, deferred, applied: bool, fmap: dict, tax: dict) -> str:
    def display(key: str) -> str:
        if key in fmap:
            return f"{fmap[key]}/"
        if key in tax.get("optional_folders", {}):
            return f"{tax['optional_folders'][key]}/"
        return key

    L: list[str] = []
    L.append(f"# Inbox 分类报告 — {stamp}\n")
    L.append(f"- 课程根目录：`{root}`")
    L.append(f"- 税表来源：`{tax_src}`")
    L.append(f"- 模式：**{'APPLY（已实际移动）' if applied else 'DRY-RUN（仅出计划）'}**")
    L.append(f"- 待分类文件：{len(rows)}；跳过：{len(skipped)}；本轮纳入：{len(limited)}；顺延：{len(deferred)}\n")

    L.append("## 分类计划 / 执行结果\n")
    L.append("| # | 文件 | 目标文件夹 | 判定依据 | 动作 | 备注 |")
    L.append("|:--|:--|:--|:--|:--|:--|")
    for i, r in enumerate(rows, 1):
        label = display(r["target_key"])
        note = "；".join(r["flags"]) if r["flags"] else ""
        if r["dup_of"]:
            note = (note + "；" if note else "") + f"内容与已有文件重复：`{r['dup_of']}`"
        L.append(f"| {i} | `{r['rel']}` | {label} | {r['reason']} | {r['action']} | {note} |")
    L.append("")

    if deferred:
        L.append("## 顺延到下一批（受单批上限限制）\n")
        for r in deferred:
            L.append(f"- `{r['rel']}` → {display(r['target_key'])}")
        L.append("")

    if skipped:
        L.append("## 已跳过（系统/临时文件）\n")
        L.append("| 文件 | 原因 |")
        L.append("|:--|:--|")
        for p, why in skipped:
            L.append(f"| `{p.name}` | {why} |")
        L.append("")

    L.append("## 人工需确认项\n")
    need = [r for r in rows if r["flags"] or r["dup_of"]]
    if not need:
        L.append("- 无。\n")
    else:
        for r in need:
            L.append(f"- `{r['rel']}`：{'；'.join(r['flags'])}{'；重复' if r['dup_of'] else ''}")
        L.append("")
    L.append("---\n")
    L.append("> 撤回本轮移动：`python triage_inbox.py --undo " + stamp + "`")
    L.append("")
    return "\n".join(L)


def do_undo(root: Path, logs_dir: Path, stamp: str) -> int:
    mf = logs_dir / f"moved_{stamp}.json"
    if not mf.is_file():
        print(f"[ERROR] 找不到移动清单：{mf}", file=sys.stderr)
        avail = sorted(p.name for p in logs_dir.glob("moved_*.json"))
        if avail:
            print("[ERROR] 可用的 stamp：" + ", ".join(a[6:-5] for a in avail), file=sys.stderr)
        return 1
    payload = json.loads(mf.read_text(encoding="utf-8"))
    ok = 0
    for m in reversed(payload.get("moves", [])):
        src, dst = Path(m["src"]), Path(m["dst"])
        if not dst.is_file():
            print(f"[WARN] 源已不存在，跳过：{dst}")
            continue
        src.parent.mkdir(parents=True, exist_ok=True)
        target = unique_dest(src.parent, src.name) if src.exists() else src
        try:
            shutil.move(str(dst), str(target))
            ok += 1
        except Exception as exc:  # noqa: BLE001
            print(f"[WARN] 撤回失败 {dst}: {exc}")
    print(f"[undo] 已撤回 {ok}/{len(payload.get('moves', []))} 个文件（清单 {mf}）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
