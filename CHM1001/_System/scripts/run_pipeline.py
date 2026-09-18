#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
run_pipeline.py — 课程自动化学习流程 · 一键编排（薄编排层）

本脚本**只做调度**，不复制任何分类/提取/核对逻辑；真正的逻辑住在三个地方：
    ~/.workbuddy/skills/course-inbox-triage/scripts/triage_inbox.py
    ~/.workbuddy/skills/essence-extraction/scripts/extract_slides.py
    <course>/_System/scripts/health_check.py

执行顺序
    Step 0  开工检查（open）  → health_check.py：Inbox 残留 / 上轮遗留 / 待提炼 / 过期提取物 / 异常文件
    Step 1  Inbox 分类        → triage_inbox.py（默认 dry-run，加 --apply 才真的移动）
    Step 2  课件原文提取      → extract_slides.py（写 _System/extracted/）
    Step 3  覆盖率自检        → 对比 <课件目录>/ 与 <笔记目录>/ 文件名，列出「待提炼」任务
    Step 4  收工核对（close） → health_check.py：按 _System/ERROR_LOG.md 的教训逐条核对，输出固定回执

用法
    python run_pipeline.py --root "<course_root>"                 # 全流程，分类为 dry-run
    python run_pipeline.py --root "<course_root>" --apply         # 分类也真正执行
    python run_pipeline.py --root "<course_root>" --skip-triage   # 只做开工检查 + 提取 + 覆盖率 + 收工核对
    python run_pipeline.py --root "<course_root>" --essence-only  # 只做覆盖率自检
    python run_pipeline.py --root "<course_root>" --skip-health   # 跳过开工检查与收工核对
    python run_pipeline.py --root "<course_root>" --check-only    # 只做开工检查 + 收工核对

建议用带依赖的解释器运行（需 python-pptx / PyMuPDF / python-docx）：
    "D:/Courses/CHM1001/.venv/Scripts/python.exe" run_pipeline.py --root "..."

退出码  0=正常；1=环境问题；3=有需关注项；4=有严重问题
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:  # pragma: no cover
    pass

SKILLS = {
    "triage": ("course-inbox-triage", "triage_inbox.py"),
    "extract": ("essence-extraction", "extract_slides.py"),
}

# 目录名一律从 taxonomy.json 解析（AIE-018）；以下仅在「没有税表」时兜底。
# AIE-024：Textbook 与 PPT 合并成一个目录。
SLIDES_DEFAULT = "2_Textbook&Lecture_PPT"
DECK_EXTS = {".pptx", ".ppt", ".pdf", ".docx", ".key", ".odp"}


def find_course_root(start: Path) -> Path:
    """找课程根：**优先认税表**，其次认「有个叫 *inbox* 的目录」。

    ⚠️ 不要再靠 `Inbox/ + PPT/` 认根（AIE-018 的老坑）——目录改名后那套会全线失效。
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


def load_tax(root: Path) -> dict:
    try:
        return json.loads((root / "_System" / "taxonomy.json").read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return {}


def folder_map(root: Path) -> dict:
    """从 _System/taxonomy.json 读内容目录名（支持改名，见 AIE-018）。"""
    m = {"inbox": "0_inbox", "syllabus": "1_Syllabus", "slides": SLIDES_DEFAULT,
         "essence": "3_Essence", "assignment": "4_Assignment", "quiz": "5_Quiz",
         "midterm": "6_Midterm Examination", "final": "7_Final Examination",
         "others": "10_Others", "textbook": SLIDES_DEFAULT}
    try:
        d = json.loads((root / "_System" / "taxonomy.json").read_text(encoding="utf-8"))
        m.update(d.get("folders") or {})
        m.update(d.get("optional_folders") or {})
    except Exception:  # noqa: BLE001
        pass
    return m


def locate(skill_name: str, script_name: str, local_dir: Path) -> Path | None:
    """按优先级定位 skill 脚本：环境变量 → 用户级 skills → 本课程 _System/scripts 的本地副本。"""
    bases: list[Path] = []
    env = os.environ.get("COURSE_WORKFLOW_SKILLS_DIR")
    if env:
        bases.append(Path(env))
    bases.append(Path.home() / ".workbuddy" / "skills")
    for base in bases:
        cand = base / skill_name / "scripts" / script_name
        if cand.is_file():
            return cand
    local = local_dir / script_name
    if local.is_file():
        return local
    return None


def run(cmd: list[str]) -> int:
    print("\n$ " + " ".join(f'"{c}"' if " " in c else c for c in cmd))
    try:
        return subprocess.run(cmd, check=False).returncode
    except Exception as exc:  # noqa: BLE001
        print(f"[ERROR] 子进程启动失败：{exc}", file=sys.stderr)
        return 1


def slug(name: str) -> str:
    """课件名 → 路径/链接双安全的 slug（AIE-022）。

    ⚠️ canonical 实现在 ~/.workbuddy/skills/essence-extraction/scripts/extract_slides.py；
    这里是**兜底副本**，必须与它逐字一致（`health_check.py` 的 AIE-022 会做漂移断言）。
    课件 `A B.pptx` 的笔记是 `Essence/A-B.md`，所以配对必须按 slug 比。
    """
    s = re.sub(r"[\s\u3000]+", "-", name.strip())
    s = re.sub(r"[^\w\u4e00-\u9fff\-.]+", "-", s, flags=re.UNICODE)
    s = re.sub(r"-{2,}", "-", s).strip("-.")
    return s or "deck"


def is_deck(p: Path, tax: dict) -> bool:
    """课件判定：扩展名像课件，且文件名不含教材类关键词（AIE-024）。

    合并目录 `2_Textbook&Lecture_PPT/` 里教材和课件混放，不排除教材的话，
    覆盖率报告会把整本课本列成「待提炼」。
    """
    if not p.is_file() or p.suffix.lower() not in DECK_EXTS or p.name.startswith("~$"):
        return False
    low = p.name.lower()
    return not any(str(k).lower() in low for k in (tax.get("non_deck_keywords") or []))


def file_stems(d: Path, exts: set[str], skip: set[str] = frozenset()) -> set[str]:
    if not d.is_dir():
        return set()
    return {p.stem for p in d.iterdir() if p.is_file() and p.suffix.lower() in exts and not p.name.startswith("~$") and p.stem not in skip}


def main() -> int:
    ap = argparse.ArgumentParser(description="课程自动化学习流程编排")
    ap.add_argument("--root", default=None, help="课程根目录（含 _System/taxonomy.json）")
    ap.add_argument("--apply", action="store_true", help="分类阶段真正执行移动")
    ap.add_argument("--skip-triage", action="store_true", help="跳过 Inbox 分类")
    ap.add_argument("--essence-only", action="store_true", help="只做覆盖率自检")
    ap.add_argument("--force-extract", action="store_true", help="强制重新提取课件")
    ap.add_argument("--skip-health", action="store_true", help="跳过开工检查与收工核对")
    ap.add_argument("--check-only", action="store_true", help="只做开工检查 + 收工核对")
    args = ap.parse_args()

    root = Path(args.root).expanduser().resolve() if args.root else find_course_root(Path.cwd())
    if not root.is_dir():
        print(f"[ERROR] 课程根目录不存在：{root}", file=sys.stderr)
        return 1

    local_dir = root / "_System" / "scripts"
    logs_dir = root / "_System" / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    py = sys.executable

    triage = locate(*SKILLS["triage"], local_dir)
    extract = locate(*SKILLS["extract"], local_dir)
    health = local_dir / "health_check.py"
    health_ok = health.is_file()

    do_health = not args.skip_health
    do_check_only = args.check_only
    worst = 0
    health_codes: dict[str, int] = {}

    print(f"[pipeline] 课程根目录：{root}")
    print(f"[pipeline] 解释器：{py}")

    def run_health(phase: str, label: str) -> None:
        nonlocal worst
        if not health_ok:
            print(f"\n[WARN] 未找到 health_check.py —— 跳过{label}（预期位置：{health}）")
            return
        print(f"\n[pipeline] {label}")
        code = run([py, str(health), "--root", str(root), "--phase", phase])
        health_codes[phase] = code
        if code == 4:
            worst = max(worst, 4)
        elif code == 3:
            worst = max(worst, 3)

    # ---------- Step 0：开工检查 ----------
    if do_health:
        run_health("open", "Step 0 / 4 —— 开工检查（Inbox 残留 / 上轮遗留 / 待提炼 / 异常文件）")
    else:
        print("\n[pipeline] Step 0 已跳过（开工检查）")

    # ---------- Step 1：Inbox 分类 ----------
    if do_check_only:
        print("\n[pipeline] Step 1 已跳过（--check-only）")
    elif args.essence_only or args.skip_triage:
        print("\n[pipeline] Step 1 已跳过（Inbox 分类）")
    elif not triage:
        print("[WARN] 未找到 triage_inbox.py —— 跳过 Step 1。"
              "请确认 ~/.workbuddy/skills/course-inbox-triage/ 存在，或设 COURSE_WORKFLOW_SKILLS_DIR。")
    else:
        print("\n[pipeline] Step 1 / 4 —— Inbox 分类" + ("" if args.apply else "（dry-run）"))
        cmd = [py, str(triage), "--root", str(root)]
        if args.apply:
            cmd.append("--apply")
        run(cmd)

    # ---------- Step 2：课件提取 ----------
    if do_check_only:
        print("\n[pipeline] Step 2 已跳过（--check-only）")
    elif args.essence_only:
        print("\n[pipeline] Step 2 已跳过（课件提取）")
    elif not extract:
        print("[WARN] 未找到 extract_slides.py —— 跳过 Step 2。"
              "请确认 ~/.workbuddy/skills/essence-extraction/ 存在。")
    else:
        print("\n[pipeline] Step 2 / 4 —— 课件原文提取")
        cmd = [py, str(extract), "--root", str(root)]
        if args.force_extract:
            cmd.append("--force")
        run(cmd)

    # ---------- Step 3：覆盖率自检 ----------
    print("\n[pipeline] Step 3 / 4 —— 覆盖率自检（课件 ↔ 笔记）")
    _fm = folder_map(root)
    _tax = load_tax(root)
    ppt_dir, ess_dir = root / _fm["slides"], root / _fm["essence"]
    ppt_raw = {p.stem for p in ppt_dir.iterdir() if is_deck(p, _tax)} if ppt_dir.is_dir() else set()
    # AIE-022：笔记名是课件名的 slug（去空格），配对必须按 slug 比，
    # 否则 `A B.pptx` 会被永远报成「待提炼」。
    ppt_names = {slug(s): s for s in ppt_raw}          # slug -> 课件原名
    ppt_stems = set(ppt_names)
    ess_stems = {slug(s) for s in file_stems(ess_dir, {".md"}, skip={"00_Index"})}
    pending = sorted(ppt_stems - ess_stems)
    orphan = sorted(ess_stems - ppt_stems)
    done = sorted(ppt_stems & ess_stems)

    lines = [
        f"# 笔记覆盖率报告 — {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "",
        f"- 课件数：**{len(ppt_stems)}**（教材不计，见 AIE-024）",
        f"- 笔记数：**{len(ess_stems)}**",
        f"- 已完成配对：**{len(done)}**",
        f"- 待提炼：**{len(pending)}**",
        "",
    ]
    if pending:
        lines += [f"## 待提炼清单（需要在 {_fm['essence']}/ 下生成同名 .md）", "", "| # | 课件 | 目标文件 |", "|:--|:--|:--|"]
        lines += [f"| {i} | `{ppt_names.get(s, s)}` | `{_fm['essence']}/{s}.md` |" for i, s in enumerate(pending, 1)]
        lines.append("")
    else:
        lines += ["## 待提炼清单", "", "- 无，全部课件都已有对应笔记。", ""]
    if orphan:
        lines += [f"## ⚠️ 无对应课件的笔记（课件可能已改名或删除）", ""]
        lines += [f"- `{_fm['essence']}/{s}.md`" for s in orphan]
        lines.append("")
    lines += ["---", "", "> 覆盖率自检由 run_pipeline.py 生成；生成笔记请走 essence-extraction skill。", ""]

    rep = logs_dir / "pending_essence.md"
    rep.write_text("\n".join(lines), encoding="utf-8")

    print(f"          课件 {len(ppt_stems)} 份 / 笔记 {len(ess_stems)} 份")
    if pending:
        print(f"          待提炼 {len(pending)} 份：")
        for s in pending[:15]:
            print(f"            - {s}")
        if len(pending) > 15:
            print(f"            … 其余 {len(pending) - 15} 份见报告")
    else:
        print("          ✅ 全部课件均已有对应笔记")
    if orphan:
        print(f"          ⚠️ {len(orphan)} 份笔记找不到对应课件")
    print(f"[pipeline] 覆盖率报告：{rep}")

    # ---------- Step 4：收工核对 ----------
    if do_health:
        run_health("close", "Step 4 / 4 —— 收工核对（按 _System/ERROR_LOG.md 逐条核对）")
    else:
        print("\n[pipeline] Step 4 已跳过（收工核对）")

    # ---------- 收尾 ----------
    print("\n" + "=" * 68)
    if health_codes:
        for phase, code in health_codes.items():
            label = "开工检查" if phase == "open" else "收工核对"
            verdict = {0: "全绿", 3: "有需关注项", 4: "有严重问题"}.get(code, f"退出码 {code}")
            print(f"[pipeline] {label}：{verdict}")
    print("[pipeline] 完成。")
    # 流程终点动作：模型必须在回复里主动问一次（见 course-inbox-triage skill 的 Step 7）
    if pending:
        shown = "、".join(pending[:5]) + ("…" if len(pending) > 5 else "")
        print(f"[pipeline] ⚠️ 终点动作 → 请在回复里问用户：是否直接提炼 PPT 知识点？（当前待提炼 {len(pending)} 份：{shown}）")
    else:
        print("[pipeline] ⚠️ 终点动作 → 请在回复里问用户：是否直接提炼 PPT 知识点？（当前无待提炼课件）")
    print("[pipeline] 若本轮发现流程问题，修复后必须收录进 _System/ERROR_LOG.md（规则见该文件开头）。")
    return worst


if __name__ == "__main__":
    raise SystemExit(main())
