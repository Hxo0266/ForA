#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
health_check.py — 课程工作区健康检查（开工检查 / 收工核对）

两种模式
    --phase open    开工检查：动手之前先扫一遍，看有没有「上一次没干完的活」和异常文件
    --phase close   收工核对：任务跑完之后，按 _System/ERROR_LOG.md 里的教训逐条核对流程
    --phase both    两段都跑

产出
    _System/logs/health_open_<stamp>.md     开工检查报告
    _System/logs/health_close_<stamp>.md    收工核对报告（含固定回执行）

退出码
    0 = 全绿；3 = 有需要处理/关注项；4 = 有严重问题；1 = 环境错误

设计约定
    1. 「核对项」的**唯一事实源**是 _System/ERROR_LOG.md ——脚本只在里面登记过的 ID 上执行自动核对。
    2. ERROR_LOG 里出现、但脚本没有登记自动核对的条目 → 标为「需人工核对」，**绝不静默跳过**。
    3. 脚本登记了、但 ERROR_LOG 里已删除的 ID → 标为「登记失效」，提示同步清理。
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:  # pragma: no cover
    pass

MARK = {
    "PASS": "✅ PASS",
    "NOTICE": "ℹ️  待办",
    "WARN": "⚠️  WARN",
    "FAIL": "❌ FAIL",
    "N/A": "—  N/A",
    "MANUAL": "👤 需人工核对",
    "STALE": "🕳  登记失效",
}

DECK_EXTS = {".pptx", ".ppt", ".pdf", ".docx", ".key", ".odp"}
SKIP_PREFIXES = ("~$", "._")
SKIP_EXTS = {".tmp", ".part", ".crdownload", ".lock", ".lnk", ".ini", ".db"}


# ─────────────────────────── 基础设施 ───────────────────────────
def find_course_root(start: Path) -> Path:
    """找课程根：**税表优先**，其次「有名字含 inbox 的目录」。

    ⚠️ AIE-024：旧判据是「同时有 `Inbox/` 与 `PPT/`」。目录改名/合并为
    `0_inbox/` + `2_Textbook&Lecture_PPT/` 之后，那套判断**永远认不到课程根**，
    整个流程会静默失效。凡参与「判断」的目录名，一律从税表解析。
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


def locate_skill_script(root: Path, skill: str, script: str) -> Path | None:
    bases: list[Path] = []
    env = os.environ.get("COURSE_WORKFLOW_SKILLS_DIR")
    if env:
        bases.append(Path(env))
    bases.append(Path.home() / ".workbuddy" / "skills")
    for base in bases:
        cand = base / skill / "scripts" / script
        if cand.is_file():
            return cand
    local = root / "_System" / "scripts" / script
    if local.is_file():
        return local
    return None


def locate_skill_file(root: Path, skill: str, filename: str) -> Path | None:
    """定位 skill **目录内的任意文件**（如 `SKILL.md`），不限于 `scripts/`。

    存在理由：`locate_skill_script` 只在 `<skill>/scripts/` 下找，用它找 `SKILL.md`
    必然落空——AIE-013 的核对项最初就踩了这个坑，于是把「skill 层交接点缺失」
    误报成 FAIL。**核查工具自己也要被核查。**
    搜索顺序与 `locate_skill_script` 保持一致：环境变量 > 用户级 skill 目录 > 课程内副本。
    """
    bases: list[Path] = []
    env = os.environ.get("COURSE_WORKFLOW_SKILLS_DIR")
    if env:
        bases.append(Path(env))
    bases.append(Path.home() / ".workbuddy" / "skills")
    for base in bases:
        cand = base / skill / filename
        if cand.is_file():
            return cand
    for cand in (root / "_System" / "skills" / skill / filename,
                 root / "skills" / skill / filename):
        if cand.is_file():
            return cand
    return None


def load_triage_module(root: Path):
    """动态加载 triage_inbox.py，用于复用它的分类器（不复制逻辑）。"""
    f = locate_skill_script(root, "course-inbox-triage", "triage_inbox.py")
    if not f:
        return None
    try:
        spec = importlib.util.spec_from_file_location("_ct_triage", f)
        mod = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
        spec.loader.exec_module(mod)  # type: ignore[union-attr]
        return mod
    except Exception:  # noqa: BLE001
        return None


# ─────────────── 命名安全化（AIE-022）：与 extract_slides.slug() 保持一致 ───────────────
# ⚠️ 这里是一份**兜底副本**，canonical 实现在
#    ~/.workbuddy/skills/essence-extraction/scripts/extract_slides.py 的 slug()。
#    AIE-022 的核对项会做「漂移断言」：拿技能里的实现跟这份副本对同一组探针比结果，
#    不一致就 FAIL —— 防止两边悄悄分叉（AIE-018 的教训：同一件事只能有一个解析入口）。
_UNSAFE_WS = re.compile(r"[\s\u3000]+")
_UNSAFE_CHR = re.compile(r"[^\w\u4e00-\u9fff\-.]+", re.UNICODE)


def slug(name: str) -> str:
    """课件名 → 路径/链接双安全的 slug（空格等 → `-`，中文保留）。"""
    s = _UNSAFE_WS.sub("-", name.strip())
    s = _UNSAFE_CHR.sub("-", s)
    s = re.sub(r"-{2,}", "-", s).strip("-.")
    return s or "deck"


SLUG_PROBES = ("CHM1001W1-Electronic Structure", "L03 Transformer", "第一讲 绪论",
               "Wave (Part 1)", "a  b", "  x  ", "A/B:C*D", "正常名字")


def skill_slug_fn(root: Path):
    """动态加载技能里的 canonical slug()；拿不到就返回 None（退回本地副本）。"""
    f = locate_skill_script(root, "essence-extraction", "extract_slides.py")
    if not f:
        return None
    try:
        spec = importlib.util.spec_from_file_location("_ct_extract_slides", f)
        mod = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
        spec.loader.exec_module(mod)  # type: ignore[union-attr]
        fn = getattr(mod, "slug", None)
        return fn if callable(fn) else None
    except Exception:  # noqa: BLE001
        return None


# 图片链接解析：刻意**贪婪抓到第一个 `)`**，这样含空格的坏链接也会被看到，
# 而不是因为「不像合法链接」被正则静默跳过（那正是 AIE-022 假 PASS 的来源）。
IMG_RE = re.compile(r"!\[(?P<alt>[^\]]*)\]\((?P<dest>[^)]*)\)")
BELIEF_U = "<u>公式在图内</u>"


def split_img_dest(raw: str) -> tuple[str, str]:
    """拆出 (链接目标, 非法原因)。返回的 dest 已去掉 <> 包裹与可选 title。"""
    d = raw.strip()
    if not d:
        return "", "链接目标为空"
    if d.startswith("<"):
        if not d.endswith(">"):
            return d, "尖括号没闭合"
        return d[1:-1].strip(), ""
    # 未加尖括号：目标里出现空白 → Markdown 会在第一个空格处截断，链接必断
    if re.search(r"\s", d):
        return d, "链接目标含空格（渲染器会在空格处截断 → 图全断链）"
    if any(c in d for c in "()<>"):
        return d, "链接目标含未转义的括号/尖括号"
    if "#" in d or "?" in d:
        return d, "链接目标含 `#`/`?`（会被当成 URL 片段或查询串）"
    return d, ""


def iter_image_links(text: str):
    for m in IMG_RE.finditer(text):
        yield m.group("alt"), m.group("dest")


def is_junk(p: Path) -> str | None:
    n = p.name.lower()
    if any(n.startswith(x.lower()) for x in SKIP_PREFIXES):
        return "Office 临时文件"
    if p.suffix.lower() in SKIP_EXTS:
        return "临时/系统文件"
    if p.name.startswith("."):
        return "隐藏文件"
    return None


# ─────────── 占位文件（AIE-025）：不是内容，是「目录存在」的证明 ───────────
# 每个内容目录都放一个 `README.md` 占位，避免空目录在打包/备份时静默丢失。
# 但**占位文件不是材料**——所有「这个目录里有没有东西」的检查都必须把它排除，
# 否则 `0_inbox/README.md` 会被 O1/AIE-002 永远报成「Inbox 残留」，用户每天
# 看到一条假警告，久而久之就会无视这条检查（狼来了）。
PLACEHOLDER_NAMES = {"readme.md", "_keep.md", ".gitkeep"}


def is_placeholder(p: Path) -> bool:
    """是否是占位文件（而非真实内容）。

    ⚠️ 判据是「文件名」而非「文件大小/内容」——占位文件也可能写得很长
    （本工作区的占位文件就带了目录用途说明）。用文件名是最稳的判据：
    真实材料极少正好叫 `README.md`。
    """
    return p.is_file() and p.name.lower() in PLACEHOLDER_NAMES


def content_files(d: Path) -> list[Path]:
    """列出目录里的**真实内容文件**（排除占位文件、临时文件）。"""
    if not d.is_dir():
        return []
    return [p for p in sorted(d.rglob("*"))
            if p.is_file() and not is_junk(p) and not is_placeholder(p)]


def _non_deck_kw(ctx: dict) -> list[str]:
    """税表里声明的「不是课件」关键词（教材 / 习题解答 之类）。"""
    tax = ctx.get("tax") or {}
    return [str(k).lower() for k in (tax.get("non_deck_keywords") or [])]


def is_deck(p: Path, ctx: dict) -> bool:
    """课件判定：扩展名像课件，且文件名不含教材类关键词。

    ⚠️ AIE-024：`Textbook` 与 `PPT` 已合并为 `2_Textbook&Lecture_PPT/`，同一个目录里
    既有课件也有教材 PDF。不排除教材的话，O3 会**永远**报「教材待提炼」，
    每周自动化还会去给整本课本写笔记。
    """
    if not p.is_file() or p.suffix.lower() not in DECK_EXTS or p.name.startswith("~$"):
        return False
    low = p.name.lower()
    return not any(k in low for k in _non_deck_kw(ctx))


def deck_stems(ppt_dir: Path, ctx: dict) -> set[str]:
    if not ppt_dir.is_dir():
        return set()
    return {p.stem for p in ppt_dir.iterdir() if is_deck(p, ctx)}


def essence_stems(ess_dir: Path) -> set[str]:
    if not ess_dir.is_dir():
        return set()
    return {p.stem for p in ess_dir.iterdir() if p.is_file() and p.suffix.lower() == ".md" and p.stem != "00_Index"}


def read_text_safe(p: Path) -> str:
    try:
        return p.read_text(encoding="utf-8")
    except Exception:  # noqa: BLE001
        return ""


def latest(root: Path, pattern: str) -> Path | None:
    d = root / "_System" / "logs"
    if not d.is_dir():
        return None
    got = sorted(d.glob(pattern), key=lambda p: p.stat().st_mtime)
    return got[-1] if got else None


def _folders(ctx: dict) -> dict:
    """内容目录名映射（folders + optional_folders）。改名后只改 taxonomy.json 即可，见 AIE-018。"""
    tax = ctx.get("tax") or {}
    m = dict(tax.get("folders") or {})
    m.update(tax.get("optional_folders") or {})
    return m


def fd(root: Path, ctx: dict, key: str, default: str) -> Path:
    """把逻辑名（inbox/slides/essence/…）解析成真实目录路径。"""
    return root / (_folders(ctx).get(key) or default)


def content_dirs(root: Path, ctx: dict, keys: tuple = ("inbox", "syllabus", "slides", "essence",
                                                       "assignment", "quiz", "midterm", "final",
                                                       "correction", "others")) -> list:
    m = _folders(ctx)
    return [root / m[k] for k in keys if m.get(k)]


def mk(status: str, summary: str, details: list[str] | None = None) -> dict:
    return {"status": status, "summary": summary, "details": details or []}


# ─────────────────────────── 开工检查项 ───────────────────────────
def o1_inbox_residual(root: Path, ctx: dict) -> dict:
    """O1  Inbox 是否还有未处理的材料（含预估归类）。"""
    inbox = fd(root, ctx, "inbox", "Inbox")
    if not inbox.is_dir():
        return mk("FAIL", "Inbox 目录不存在")
    files, junk = [], []
    for p in sorted(inbox.rglob("*")):
        if not p.is_file():
            continue
        if is_placeholder(p):          # AIE-025 占位文件不是待分类材料
            continue
        r = is_junk(p)
        (junk if r else files).append((p, r))

    details = []
    mod = ctx.get("triage_mod")
    tax = ctx.get("tax")
    for p, _ in files:
        guess = ""
        if mod and tax:
            try:
                v = mod.classify(p, tax, root)
                key = v["target"]
                label = tax["folders"].get(key) or tax.get("optional_folders", {}).get(key, key)
                guess = f" → 预估 **{label}/**（{v['reason']}）"
                if v["flags"]:
                    guess += " ⚠️" + "；".join(v["flags"])
            except Exception:  # noqa: BLE001
                guess = ""
        details.append(f"`{p.relative_to(inbox)}`{guess}")
    for p, r in junk:
        details.append(f"`{p.relative_to(inbox)}` — 🗑 {r}（可安全忽略/手动清理）")

    if not files and not junk:
        return mk("PASS", "Inbox 已空，无残留")
    if not files:
        return mk("WARN", f"Inbox 无正经材料，但有 {len(junk)} 个临时/隐藏文件需清理", details)
    return mk("NOTICE", f"Inbox 还有 {len(files)} 个文件待分类" + (f"（另有 {len(junk)} 个临时文件）" if junk else ""), details)


def o2_last_run_leftovers(root: Path, ctx: dict) -> dict:
    """O2  上一轮分类是否留下未收尾的项（重复/待确认/失败/顺延）。"""
    rep = latest(root, "triage_*.md")
    if not rep:
        return mk("N/A", "还没有任何 triage 报告，属首次运行")
    txt = read_text_safe(rep)
    leftover, deferred, failed = [], [], []
    in_deferred = in_skipped = False
    for line in txt.splitlines():
        s = line.strip()
        if s.startswith("## 顺延"):
            in_deferred, in_skipped = True, False
            continue
        if s.startswith("## 已跳过") or s.startswith("## 人工需确认"):
            in_deferred = False
            in_skipped = s.startswith("## 已跳过")
            continue
        if s.startswith("## ") and not s.startswith("## 顺延"):
            in_deferred = in_skipped = False
        if "SKIP-DUPLICATE" in s:
            leftover.append(s)
        if "FAILED" in s:
            failed.append(s)
        if in_deferred and s.startswith("- `"):
            deferred.append(s)
    details = []
    if failed:
        details.append(f"❌ **有 {len(failed)} 条移动失败**（需人工处理）：")
        details += ["  " + x for x in failed[:10]]
    if leftover:
        details.append(f"⚠️ **有 {len(leftover)} 条内容重复被跳过**（需人工决定去留）：")
        details += ["  " + x for x in leftover[:10]]
    if deferred:
        details.append(f"ℹ️ 上轮受单批上限顺延 {len(deferred)} 条（再跑一次即可消化）")
    if failed or leftover:
        return mk("WARN", f"上轮遗留：失败 {len(failed)} / 重复待决 {len(leftover)} / 顺延 {len(deferred)}", details)
    if deferred:
        return mk("NOTICE", f"上轮顺延 {len(deferred)} 条未消化", details)
    return mk("PASS", "上一轮分类没有遗留项", [f"依据：`{rep.name}`"])


def o3_pending_essence(root: Path, ctx: dict) -> dict:
    """O3  有没有课件还没生成 Essence 笔记。

    ⚠️ 配对按 **slug** 比：课件 `A B.pptx` 的笔记是 `Essence/A-B.md`（AIE-022 去空格），
    拿原名直接比对会永远报「待提炼」。细节里同时给出原名 → 目标文件，便于照做。
    """
    ppt_raw = deck_stems(fd(root, ctx, "slides", "PPT"), ctx)
    ess = {slug(s) for s in essence_stems(fd(root, ctx, "essence", "Essence"))}
    ppt = {slug(s): s for s in ppt_raw}          # slug -> 课件原名
    pend = sorted(s for s in ppt if s not in ess)
    if not ppt:
        return mk("N/A", "PPT/ 里还没有课件")
    if not pend:
        return mk("PASS", f"{len(ppt)} 份课件全部已有 Essence 笔记")
    return mk("NOTICE", f"还有 {len(pend)} 份课件待提炼",
              [f"`{ppt[s]}` → `Essence/{s}.md`" for s in pend])


def o4_stale_extract(root: Path, ctx: dict) -> dict:
    """O4  课件改了但提取物没更新（提取物过期）。"""
    ppt_dir = fd(root, ctx, "slides", "PPT")
    if not ppt_dir.is_dir():
        return mk("N/A", "无 PPT/ 目录")
    ex_dir = root / "_System" / "extracted"
    stale, missing = [], []
    for p in ppt_dir.iterdir():
        if not is_deck(p, ctx):
            continue
        t = ex_dir / f"{p.stem}.slides.txt"
        if not t.is_file():
            missing.append(p.name)
        elif t.stat().st_mtime < p.stat().st_mtime:
            stale.append(p.name)
    det = [f"未提取：`{x}`" for x in missing] + [f"已过期（课件更新过）：`{x}`" for x in stale]
    if not missing and not stale:
        return mk("PASS", "提取物均为最新")
    st = "NOTICE" if missing and not stale else "WARN"
    return mk(st, f"提取物待更新：未提取 {len(missing)} / 过期 {len(stale)}", det)


def o5_anomalous_files(root: Path, ctx: dict) -> dict:
    """O5  0 字节文件、Office 锁文件散落在各归位目录里。"""
    zero, locks = [], []
    for d in content_dirs(root, ctx):
        if not d.is_dir():
            continue
        for p in d.rglob("*"):
            if not p.is_file():
                continue
            if p.name.startswith("~$") or p.name.lower().endswith((".tmp", ".lock")):
                locks.append(f"{d.name}/{p.name}")
            elif p.stat().st_size == 0:
                zero.append(f"{d.name}/{p.name}")
    det = [f"0 字节：`{x}`" for x in zero] + [f"残留临时文件：`{x}`" for x in locks]
    if not zero and not locks:
        return mk("PASS", "未发现 0 字节文件或残留临时文件")
    return mk("WARN", f"异常文件：0 字节 {len(zero)} / 临时残留 {len(locks)}", det)


def o6_others_misfiled(root: Path, ctx: dict) -> dict:
    """O6  漏判复查：Others/ 里有没有文件名其实能明确归到考试/课件类 的文件。"""
    others = fd(root, ctx, "others", "Others")
    if not others.is_dir():
        return mk("N/A", "无 Others/ 目录")
    mod, tax = ctx.get("triage_mod"), ctx.get("tax")
    if not (mod and tax):
        return mk("N/A", "分类器不可用，跳过漏判复查")
    fmap = tax["folders"]
    mis = []
    for p in sorted(others.iterdir()):
        if not p.is_file() or is_junk(p) or is_placeholder(p):
            continue
        try:
            v = mod.classify(p, tax, root)
        except Exception:  # noqa: BLE001
            continue
        key = v["target"]
        # 只报「明确命中」的错位；带 NEEDS_REVIEW 的泛考试项留在 Others 是设计如此
        if key in ("final", "midterm", "slides", "assignment", "quiz") and not any("需人工确认" in f for f in v["flags"]):
            mis.append(f"`{p.name}` → 应为 **{fmap.get(key, key)}/**（{v['reason']}）")
    if not mis:
        return mk("PASS", "Others/ 里没有可明确归类的文件")
    return mk("WARN", f"Others/ 有 {len(mis)} 个文件其实可以明确归类", mis)


OPEN_CHECKS: list[tuple[str, str, object]] = [
    ("O1", "Inbox 残留检查", o1_inbox_residual),
    ("O2", "上一轮未收尾项", o2_last_run_leftovers),
    ("O3", "课件待提炼清单", o3_pending_essence),
    ("O4", "提取物时效", o4_stale_extract),
    ("O5", "异常文件扫描", o5_anomalous_files),
    ("O6", "漏判/错位复查（Others）", o6_others_misfiled),
]


# ─────────────────────────── 收工核对项（绑定 ERROR_LOG 的 AIE-ID） ───────────────────────────
def c_essence_only_md(root: Path, ctx: dict) -> dict:
    """AIE-001  Essence/ 只应出现与课件同名的 .md。"""
    ess = fd(root, ctx, "essence", "Essence")
    if not ess.is_dir():
        return mk("N/A", "无 Essence/ 目录")
    bad = [p.name for p in ess.iterdir() if p.is_file() and p.suffix.lower() != ".md"]
    return mk("PASS", "Essence/ 内只有 .md") if not bad else mk("FAIL", f"Essence/ 混入 {len(bad)} 个非 .md 文件", [f"`{x}`" for x in bad])


def c_inbox_clean(root: Path, ctx: dict) -> dict:
    """AIE-002  处理完之后 Inbox 里不该再留正经材料。"""
    inbox = fd(root, ctx, "inbox", "Inbox")
    if not inbox.is_dir():
        return mk("FAIL", "Inbox 目录不存在")
    left = [p.name for p in inbox.rglob("*")
            if p.is_file() and not is_junk(p) and not is_placeholder(p)]
    if not left:
        return mk("PASS", "Inbox 已清空（无正经材料残留）")
    return mk("WARN", f"Inbox 仍残留 {len(left)} 个文件未归位", [f"`{x}`" for x in left[:20]])


def c_coverage(root: Path, ctx: dict) -> dict:
    """AIE-003  PPT 每份课件都应有同名 Essence 笔记。"""
    r = o3_pending_essence(root, ctx)
    return mk(r["status"], r["summary"], r["details"])


def c_extract_fresh(root: Path, ctx: dict) -> dict:
    """AIE-004  课件更新后必须重新提取（提取物不得过期）。"""
    r = o4_stale_extract(root, ctx)
    return mk("WARN" if r["status"] == "WARN" else r["status"], r["summary"], r["details"])


def c_manifests(root: Path, ctx: dict) -> dict:
    """AIE-005  每次 --apply 都必须留下可回滚的 moved_*.json。"""
    logs = root / "_System" / "logs"
    if not logs.is_dir():
        return mk("N/A", "尚无日志目录")
    applied = []
    for rep in logs.glob("triage_*.md"):
        txt = read_text_safe(rep)
        if "APPLY（已实际移动）" in txt:
            applied.append(rep)
    if not applied:
        return mk("N/A", "还没有执行过 --apply，无可回滚记录需核对")
    missing = [rep.name for rep in applied if not (logs / f"moved_{rep.stem.split('_', 1)[1]}.json").is_file()]
    if missing:
        return mk("FAIL", f"{len(missing)} 次 --apply 缺少移动清单（无法回滚）", [f"`{x}`" for x in missing])
    return mk("PASS", f"{len(applied)} 次 --apply 均有对应移动清单，可回滚")


def c_logs_readable(root: Path, ctx: dict) -> dict:
    """AIE-006  报告必须已落盘且是 UTF-8 可读文本（不要出现被改成二进制的情况）。"""
    logs = root / "_System" / "logs"
    if not logs.is_dir():
        return mk("N/A", "尚无日志目录")
    bad = []
    for p in sorted(logs.glob("*")):
        if not p.is_file():
            continue
        head = p.read_bytes()[:2]
        if head == b"PK":
            bad.append(f"{p.name}（是 xlsx/zip 二进制，被编辑器覆盖过）")
            continue
        try:
            p.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            bad.append(f"{p.name}（不是 UTF-8 文本）")
    if bad:
        return mk("FAIL", f"{len(bad)} 个日志文件不可读", [f"`{x}`" for x in bad])
    n = len([p for p in logs.glob("*") if p.is_file()])
    return mk("PASS", f"{n} 个日志文件均为可读 UTF-8 文本")


def c_scripts_syntax(root: Path, ctx: dict) -> dict:
    """AIE-007  改动脚本后必须复核：语法 + 不留 __pycache__。"""
    import ast

    targets: list[Path] = []
    sd = root / "_System" / "scripts"
    if sd.is_dir():
        targets += [p for p in sd.glob("*.py")]
    for skill in ("course-inbox-triage", "essence-extraction"):
        f = locate_skill_script(root, skill, "triage_inbox.py" if "inbox" in skill else "extract_slides.py")
        if f:
            targets.append(f)
    broken, pycache = [], []
    for f in targets:
        try:
            ast.parse(f.read_text(encoding="utf-8"))
        except Exception as exc:  # noqa: BLE001
            broken.append(f"{f.name}：{exc}")
    for base in [root / "_System", Path.home() / ".workbuddy" / "skills" / "course-inbox-triage", Path.home() / ".workbuddy" / "skills" / "essence-extraction"]:
        if base.is_dir():
            pycache += [str(p) for p in base.rglob("__pycache__")]
    det = [f"语法错误：`{x}`" for x in broken] + [f"缓存残留：`{x}`" for x in pycache]
    if broken:
        return mk("FAIL", f"{len(broken)} 个脚本语法错误", det)
    if pycache:
        return mk("WARN", f"发现 {len(pycache)} 处 __pycache__（打包/交付前需清理）", det)
    return mk("PASS", f"{len(targets)} 个脚本语法正常，无缓存残留")


def c_essence_citations(root: Path, ctx: dict) -> dict:
    """AIE-008  Essence 笔记需带「出处索引」，否则无法核对是否臆造。"""
    ess = fd(root, ctx, "essence", "Essence")
    if not ess.is_dir():
        return mk("N/A", "无 Essence/ 目录")
    notes = [p for p in ess.glob("*.md") if p.stem != "00_Index"]
    if not notes:
        return mk("N/A", "还没有任何 Essence 笔记")
    pat = re.compile(r"^#{1,6}\s*出处索引", re.M)
    missing = [p.name for p in notes if not pat.search(read_text_safe(p))]
    if missing:
        return mk("WARN", f"{len(missing)}/{len(notes)} 份笔记缺「出处索引」，无法核对是否臆造", [f"`{x}`" for x in missing])
    return mk("PASS", f"{len(notes)} 份笔记均含「出处索引」")


def c_report_labels(root: Path, ctx: dict) -> dict:
    """AIE-009  分类报告里的「目标文件夹」列必须是人可读的文件夹名，不是内部键名。"""
    rep = latest(root, "triage_*.md")
    if not rep:
        return mk("N/A", "还没有 triage 报告")
    bad = []
    for line in read_text_safe(rep).splitlines():
        if not line.startswith("| ") or line.startswith("| #") or line.startswith("|:"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) >= 6 and not cells[2].endswith("/"):
            bad.append(cells[2])
    if bad:
        return mk("FAIL", f"报告出现 {len(bad)} 处内部键名而非文件夹名", [f"`{x}`" for x in sorted(set(bad))])
    return mk("PASS", "分类报告的目标文件夹列显示正常")


def c_automation_alive(root: Path, ctx: dict) -> dict:
    """AIE-011  自动化必须真的在跑——靠心跳文件判断，不能只看「当初配置过」。

    ⚠️ 预期自动化名必须**从 taxonomy.json 的 course 推导**，不要硬编码课程名——
    否则整套复制到新课程后，提示会指错课程（见 ERROR_LOG AIE-016）。
    """
    beat = root / "_System" / "logs" / "automation_heartbeat.json"
    course = (ctx.get("tax") or {}).get("course") or root.name
    expect = f"{course} 课件自动提炼 Essence"
    if not beat.is_file():
        if ctx.get("will_write_beat"):
            # AIE-019：本轮自己就会写心跳（`--beat` 在核对之后落盘），
            # 「文件不存在」只说明这是本工作区的第一份心跳，不是故障，不能报 WARN。
            return mk(
                "NOTICE",
                "本工作区还没有历史心跳——本轮正在写入第一份（下次收工核对方可判断是否在跑）",
                [f"自查：WorkBuddy 的自动化列表里，`{expect}` 是否处于 ACTIVE"],
            )
        return mk(
            "WARN",
            "无心跳记录：自动化可能从未运行、被暂停/删除，或没登记心跳",
            ["预期文件：`_System/logs/automation_heartbeat.json`",
             f"自查：WorkBuddy 的自动化列表里，`{expect}` 是否处于 ACTIVE"],
        )
    try:
        data = json.loads(read_text_safe(beat))
        ts = datetime.fromisoformat(str(data["last_run"]))
    except Exception as exc:  # noqa: BLE001
        return mk("FAIL", f"心跳文件无法解析：{exc}")
    name = data.get("automation", "?")
    age = (datetime.now() - ts).total_seconds() / 86400
    det = [
        f"自动化：`{name}`",
        f"最近一次运行：{ts:%Y-%m-%d %H:%M:%S}（{age:.1f} 天前）",
    ]
    if data.get("processed"):
        det.append("上次处理：" + "、".join(str(x) for x in data["processed"][:8]))
    if age > 3:
        det.append("⚠️ 超过 3 天没有心跳 → 自动化可能被暂停/删除，或计划任务执行失败")
        return mk("WARN", f"自动化「{name}」已 {age:.1f} 天未运行", det)
    return mk("PASS", f"自动化「{name}」{age:.1f} 天内有运行", det)


def c_first_heartbeat(root: Path, ctx: dict) -> dict:
    """AIE-019  「本轮会写心跳」时不得把「没有心跳文件」误报成 WARN。

    故障注入式自测（只读，不碰真实工作区）：在临时根目录上跑 `c_automation_alive`——
      ① 不给 `will_write_beat`（普通会话）→ **必须仍然 WARN**，证明检测没被削弱；
      ② 给 `will_write_beat=True`（自动化本轮写心跳）→ **不得 WARN/FAIL**；
      ③ 心跳停在 9 天前 → **必须 WARN**，证明「三天未运行」的真告警没被顺手削弱。
    任一条不符即 FAIL，防止日后有人把抑制逻辑改坏或写反（只会 PASS 的检查等于没有检查）。
    """
    import tempfile
    from datetime import timedelta

    got: dict[bool, str] = {}
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        (tmp / "_System" / "logs").mkdir(parents=True, exist_ok=True)
        tax = ctx.get("tax") or {}
        for flag in (False, True):
            got[flag] = str(
                c_automation_alive(tmp, {"tax": tax, "will_write_beat": flag}).get("status")
            )
        # 再注入一条「心跳停在 9 天前」：证明 age>3 的真告警没被顺手削弱
        stale_beat = tmp / "_System" / "logs" / "automation_heartbeat.json"
        stale_beat.write_text(
            json.dumps(
                {
                    "automation": f"{tax.get('course') or 'ZZPROBE'} 课件自动提炼 Essence",
                    "last_run": (datetime.now() - timedelta(days=9)).isoformat(timespec="seconds"),
                }
            ),
            encoding="utf-8",
        )
        got_stale = str(
            c_automation_alive(tmp, {"tax": tax, "will_write_beat": True}).get("status")
        )
    bad = []
    if got.get(False) != "WARN":
        bad.append(f"注入「无心跳 + 非本轮写入」：期望 WARN，实际 {got.get(False)} —— 真实缺失会漏报")
    if got.get(True) in ("WARN", "FAIL"):
        bad.append(f"注入「无心跳 + 本轮会写」：期望不告警，实际 {got.get(True)} —— 首次运行会假告警")
    if got_stale != "WARN":
        bad.append(f"注入「心跳停在 9 天前」：期望 WARN，实际 {got_stale} —— 超期告警已失效")
    if bad:
        return mk("FAIL", "首次心跳的告警抑制逻辑异常", bad)
    return mk("PASS", "故障注入通过：真缺失仍 WARN、首次写入不误报、超期仍 WARN")


def c_bilingual_names(root: Path, ctx: dict) -> dict:
    """AIE-020  术语与重点区域必须有英文名，中英并存时英文在前。

    「重点区域」= 小节标题（`##`/`###`/`####`）。结构性小节（出处索引、公式在图内、
    关键术语、易错点）由模板固定，不参与判定。
    另外抽查 `## 关键术语` 表的每一行：前两列里至少有一列含英文（兼容
    「术语（English）| 释义」与旧的「术语|英文|释义」两种表头）。
    """
    ess = fd(root, ctx, "essence", "Essence")
    if not ess.is_dir():
        return mk("N/A", "无 Essence/ 目录")
    notes = [p for p in sorted(ess.glob("*.md")) if p.stem != "00_Index"]
    if not notes:
        return mk("N/A", "还没有任何 Essence 笔记")

    struct = ("出处索引", "公式在图内", "关键术语", "易错点", "待核实")
    bad_head, bad_term, n_head, n_term = [], [], 0, 0
    for n in notes:
        body = read_text_safe(n)
        for line in body.splitlines():
            m = re.match(r"^#{2,4}\s+(.+?)\s*$", line)
            if not m:
                continue
            txt = m.group(1).strip()
            if any(k in txt for k in struct):
                continue
            n_head += 1
            if not re.search(r"[A-Za-z]{2,}", txt):
                bad_head.append(f"`{n.name}` → `{txt}`")
        # 关键术语表逐行抽查
        in_terms = False
        for line in body.splitlines():
            if re.match(r"^#{2,6}\s*关键术语", line):
                in_terms = True
                continue
            if in_terms and re.match(r"^#{2,6}\s+", line):
                in_terms = False
            if not (in_terms and line.strip().startswith("|")):
                continue
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if not cells or set("".join(cells)) <= set("-: "):
                continue
            if cells[0] in ("术语", "术语（English）"):
                continue
            n_term += 1
            if not any(re.search(r"[A-Za-z]{2,}", c) for c in cells[:2]):
                bad_term.append(f"`{n.name}` → 术语行 `{cells[0]}` 没有英文名")

    got = bad_head + bad_term
    if got:
        return mk("FAIL",
                  f"英文名缺失：{len(bad_head)}/{n_head} 个小节标题、{len(bad_term)}/{n_term} 个术语行",
                  got[:12])
    return mk("PASS", f"{n_head} 个小节标题、{n_term} 个术语行均带英文名（英文优先）")


def c_formula_in_figure(root: Path, ctx: dict) -> dict:
    """AIE-021  「公式在图内」必须正文下划线标注 + 文末清单一一对应，且清单在全文最末。

    规则：正文该处**只写** `<u>公式在图内</u>`；文末 `## 公式在图内（提取文本丢失）`
    逐条列 `- 第 N 张：公式在图内、提取文本丢失`，条数必须与正文标注数相等，
    且该节必须是全文最后一个 `##` 小节。
    """
    ess = fd(root, ctx, "essence", "Essence")
    if not ess.is_dir():
        return mk("N/A", "无 Essence/ 目录")
    notes = [p for p in sorted(ess.glob("*.md")) if p.stem != "00_Index"]
    if not notes:
        return mk("N/A", "还没有任何 Essence 笔记")

    problems, n_notes_with = [], 0
    for n in notes:
        body = read_text_safe(n)
        lines = body.splitlines()
        n_mark = body.count(BELIEF_U)
        heads = [(i, ln) for i, ln in enumerate(lines) if re.match(r"^#{2,6}\s+", ln)]
        tail_i, tail = None, []
        if heads:
            li, lh = heads[-1]
            if "公式在图内" in lh:
                tail_i = li
                tail = [x.strip() for x in lines[li + 1:] if x.strip().startswith("-")]
        if n_mark or tail:
            n_notes_with += 1
        if n_mark and tail_i is None:
            problems.append(f"`{n.name}`：正文有 {n_mark} 处 `<u>公式在图内</u>`，"
                            f"但文末没有 `## 公式在图内（提取文本丢失）` 一节")
        elif tail_i is not None and n_mark != len(tail):
            problems.append(f"`{n.name}`：正文 {n_mark} 处标注 ≠ 文末 {len(tail)} 条清单（必须一一对应）")
        for t in tail:
            if not re.search(r"第\s*\d+\s*张", t):
                problems.append(f"`{n.name}`：文末清单缺张号 → `{t}`")
        # 正文里出现的「公式在图内」都必须是下划线形式
        plain = body.count("公式在图内")
        expect = n_mark + (1 if tail_i is not None else 0) + len(tail)
        if plain > expect:
            problems.append(f"`{n.name}`：有 {plain - expect} 处「公式在图内」没写成 "
                            f"`<u>公式在图内</u>`（正文只写下划线形式）")

    if problems:
        return mk("FAIL", f"{len(problems)} 处「公式在图内」写法不合规", problems[:12])
    if not n_notes_with:
        return mk("N/A", "本批笔记没有「公式在图内」的情况，无需核对")
    return mk("PASS", f"{n_notes_with} 份笔记的「公式在图内」标注与文末清单一致")


def c_link_safe(root: Path, ctx: dict) -> dict:
    """AIE-022  生成物路径一律不得含空格；图片链接必须语法合法、相对、且指向真实文件。

    同时做 **slug 漂移断言**：`health_check.py` 里的兜底 `slug()` 与技能里 canonical 的
    `extract_slides.slug()` 必须给出相同结果，否则两边会各自生成不同的目录名。
    """
    ess = fd(root, ctx, "essence", "Essence")
    problems, checked = [], 0

    fn = skill_slug_fn(root)
    if fn:
        diff = [p for p in SLUG_PROBES if fn(p) != slug(p)]
        if diff:
            problems.append("`slug()` 实现分叉：health_check.py 与技能结果不一致 → "
                            + "、".join(f"`{p}`" for p in diff))

    if ess.is_dir():
        for n in sorted(ess.glob("*.md")):
            if n.stem == "00_Index":
                continue
            for _alt, raw in iter_image_links(read_text_safe(n)):
                dest, why = split_img_dest(raw)
                if dest.startswith(("http://", "https://")):
                    continue
                checked += 1
                if why:
                    problems.append(f"`{n.name}` → `{dest}`：{why}")
                elif re.match(r"^[A-Za-z]:[\\/]", dest) or Path(dest).is_absolute():
                    problems.append(f"`{n.name}` → `{dest}`：绝对路径，换目录即断")
                elif not (n.parent / dest).resolve().is_file():
                    problems.append(f"`{n.name}` → `{dest}`：文件不存在")
        figdir = ess / "figures"
        if figdir.is_dir():
            for d in sorted(figdir.iterdir()):
                if d.is_dir() and re.search(r"\s", d.name):
                    problems.append(f"图表目录名含空格：`figures/{d.name}/` → 应为 `figures/{slug(d.name)}/`")

    ex = root / "_System" / "extracted"
    if ex.is_dir():
        for t in sorted(ex.glob("*.slides.txt")):
            for line in read_text_safe(t).splitlines():
                if not line.startswith("[FIGURE]"):
                    continue
                payload = line[len("[FIGURE]"):].strip()
                if "  (" in payload:
                    payload = payload.split("  (")[0].strip()
                checked += 1
                if re.search(r"\s", payload):
                    problems.append(f"`{t.name}` 的 `[FIGURE]` 路径含空格：`{payload}`")
                elif ess.is_dir() and not (ess / payload).is_file():
                    problems.append(f"`{t.name}` 的 `[FIGURE]` 指向不存在的文件：`{payload}`")

    if problems:
        return mk("FAIL", f"发现 {len(problems)} 处路径/链接不安全", problems[:15])
    if checked == 0:
        # 没有链接可查时不要给「PASS」——那会看起来像「查过且没问题」。
        tail = "（本课 slug() 两个实现一致）" if fn else "（技能不可用，未做漂移断言）"
        return mk("N/A", f"当前没有图片链接 / [FIGURE] 需要核对{tail}")
    return mk("PASS", f"图片链接与图表目录命名均安全（检查 {checked} 处）")


def c_keyword_matcher(root: Path, ctx: dict) -> dict:
    """AIE-014  税表里的多词短语必须真的能被匹配器命中（防静默失效）。

    做法：拿配置本身当输入——把每个含空格/连字符的关键词丢回 hit_keywords()，
    若连它自己的原文都命不中，说明该关键词在真实文件上永远不会生效。
    """
    mod, tax = ctx.get("triage_mod"), ctx.get("tax")
    if not (mod and tax):
        return mk("N/A", "分类器不可用，跳过关键词自校验")
    bad, total = [], 0
    for group, kws in (tax.get("keywords") or {}).items():
        for kw in kws:
            if " " in kw or "-" in kw:
                total += 1
                toks = mod.tokenize(kw)
                if not mod.hit_keywords(toks, mod.norm(kw), [kw]):
                    bad.append(f"{group}: `{kw}`")
    if bad:
        return mk("FAIL", f"{len(bad)}/{total} 个多词短语永远匹配不到（匹配器不支持该形态）", bad)
    if total == 0:
        return mk("N/A", "税表中没有多词短语需要校验")
    return mk("PASS", f"税表中 {total} 个多词短语均可正常命中")


def c_figure_links(root: Path, ctx: dict) -> dict:
    """AIE-017  笔记与图表必须**双向**对齐：引用的图要存在，已渲染的图要被引用。

    单向核对只能防一半：只查「引用→文件」会漏掉「图导出来了却没放进笔记」。
    """
    ess = fd(root, ctx, "essence", "Essence")
    if not ess.is_dir():
        return mk("N/A", "无 Essence/ 目录")
    notes = [p for p in ess.glob("*.md") if p.stem != "00_Index"]
    if not notes:
        return mk("N/A", "还没有任何 Essence 笔记")

    pat = IMG_RE
    broken, total = [], 0
    for n in notes:
        body = read_text_safe(n)
        for _alt, raw in iter_image_links(body):
            dest, why = split_img_dest(raw)
            if dest.startswith(("http://", "https://")):
                continue
            total += 1
            if why:
                # 语法就不合法的链接（如含空格）在渲染器里必然断 → 直接算断图。
                # AIE-022 专门核这类问题；这里只保证 AIE-017 不再给它们「PASS」。
                broken.append(f"`{n.name}` → `{dest}`（{why}）")
            elif not (n.parent / dest).resolve().is_file():
                broken.append(f"`{n.name}` → `{dest}`")

    unref = []
    figdir = ess / "figures"
    if figdir.is_dir():
        for d in sorted(figdir.iterdir()):
            if not d.is_dir():
                continue
            note = ess / f"{d.name}.md"
            body = read_text_safe(note) if note.is_file() else ""
            for png in sorted(d.glob("*.png")):
                if f"{d.name}/{png.name}" not in body:
                    unref.append(f"`{d.name}/{png.name}`")

    det = [f"断图：{x}" for x in broken] + [f"未被引用：{x}" for x in unref]
    if broken:
        return mk("FAIL", f"{len(broken)} 处图片引用指向不存在的文件", det)
    if unref:
        return mk("WARN", f"{len(unref)} 张已渲染的图没被任何笔记引用（应贴在知识点旁边）", det)
    if total == 0:
        return mk("N/A", "笔记里还没有插图")
    return mk("PASS", f"{len(notes)} 份笔记共 {total} 处插图引用，全部有效且无遗漏")


def c_correction_links(root: Path, ctx: dict) -> dict:
    """AIE-026  错题本（8_Correction_Notebook）笔记的图片链接必须语法合法、相对、且指向真实文件。

    错题笔记常附题目截图；若链接含空格、用了绝对路径、或指向不存在的文件，
    复习时图会静默断链。复用与 Essence 相同的解析（`split_img_dest` / `IMG_RE`），
    保证判定口径一致（同 AIE-022：先验语法合法，再验文件存在）。
    """
    corr = fd(root, ctx, "correction", "8_Correction_Notebook")
    if not corr.is_dir():
        return mk("N/A", "无错题本目录")
    notes = [p for p in sorted(corr.glob("*.md")) if p.name != "README.md"]
    if not notes:
        return mk("N/A", "错题本还没有任何错题笔记")
    problems, total = [], 0
    for n in notes:
        body = read_text_safe(n)
        for _alt, raw in iter_image_links(body):
            dest, why = split_img_dest(raw)
            if dest.startswith(("http://", "https://")):
                continue
            total += 1
            if why:
                problems.append(f"`{n.name}` → `{dest}`：{why}")
            elif re.match(r"^[A-Za-z]:[\\/]", dest) or Path(dest).is_absolute():
                problems.append(f"`{n.name}` → `{dest}`：绝对路径，换目录即断")
            elif not (n.parent / dest).resolve().is_file():
                problems.append(f"`{n.name}` → `{dest}`：文件不存在")
    if problems:
        return mk("FAIL", f"错题本发现 {len(problems)} 处图片链接不安全", problems[:15])
    if total == 0:
        return mk("N/A", "错题笔记里还没有插图")
    return mk("PASS", f"错题本 {len(notes)} 份笔记共 {total} 处插图链接全部有效")


def c_apply_honest(root: Path, ctx: dict) -> dict:
    """AIE-027  「模式」标签必须忠实反映**真实动作**，而不是命令行参数。

    故障注入式自测（只读）：直接调用分类器的 `apply_mode()` 验证——
      ① dry-run（无论是否有待处理文件）→ 绝不能含「已实际移动」；
      ② --apply 但 0 个移动（Inbox 已空 / 全部被跳过）→ 绝不能含「已实际移动」；
      ③ --apply 且确有移动 → 必须是「已实际移动」。
    任一条不符即 FAIL——防止有人把「按真实结果取模式」退回成「按参数取模式」。
    """
    mod = ctx.get("triage_mod")
    if not mod or not callable(getattr(mod, "apply_mode", None)):
        return mk("N/A", "分类器不可用或缺少 apply_mode()，跳过")
    am = mod.apply_mode
    bad = []
    if "已实际移动" in am(False, 0):
        bad.append("dry-run（空）被标成「已实际移动」")
    if "已实际移动" in am(False, 5):
        bad.append("dry-run（有待处理文件）被标成「已实际移动」")
    if "已实际移动" in am(True, 0):
        bad.append("空 Inbox 的 --apply 被标成「已实际移动」（谎报 → 触发 AIE-005）")
    if am(True, 0) != "APPLY（无文件可移动）":
        bad.append("空 Inbox 的 --apply 未标注「无文件可移动」")
    if am(True, 3) != "APPLY（已实际移动）":
        bad.append("确有移动时未标注「已实际移动」")
    if bad:
        return mk("FAIL", "「模式」标签与真实动作不符", bad)
    return mk("PASS", "故障注入通过：模式忠实反映真实移动情况")


def c_folder_map(root: Path, ctx: dict) -> dict:
    """AIE-018  税表声明的每个内容目录都必须真实存在。

    用户给目录改名是正常操作（排序/命名习惯）。改名后若忘记同步 taxonomy.json，
    这里会立刻暴露——而不是等到某个流程莫名 FAIL 才去查。
    """
    tax = ctx.get("tax") or {}
    fm = dict(tax.get("folders") or {})
    if not fm:
        return mk("N/A", "税表未声明 folders，跳过")
    missing = [f"{k} → `{v}`" for k, v in fm.items() if not (root / v).is_dir()]
    opt_missing = [f"{k} → `{v}`" for k, v in (tax.get("optional_folders") or {}).items()
                   if not (root / v).is_dir()]
    det = [f"缺失：{x}" for x in missing]
    if opt_missing:
        det.append("（可选项缺失，不报错）：" + "、".join(opt_missing))
    if missing:
        return mk("FAIL", f"税表声明的 {len(missing)} 个目录不存在 —— 目录可能被改名了，请同步 taxonomy.json", det)
    return mk("PASS", f"税表声明的 {len(fm)} 个内容目录均存在")


# ─────────────── AIE-023 / AIE-024：生成物归属 与 目录改名同步 ───────────────
# 父级目录下**不得**出现本流程的生成物：任何生成物都必须落在它所属课程的子目录里。
ESCAPE_ARTIFACT_NAMES = ("figures", "extracted", "Essence", "PPT", "Textbook",
                         "Midterm Examination", "Final Examination", "Others")


def _escaped_artifacts(parent: Path) -> list[str]:
    """扫描 parent 下是否有「本流程的裸产物目录」——即生成物逃出了课程目录。"""
    problems: list[str] = []
    if not parent.is_dir():
        return problems
    for child in sorted(parent.iterdir()):
        if not child.is_dir() or child.name not in ESCAPE_ARTIFACT_NAMES:
            continue
        inner = [p.name for p in child.rglob("*") if p.is_file()][:5]
        problems.append(
            f"`{parent.name}/{child.name}/`（课程目录之外）"
            + (f"，内含：{'、'.join(inner)}" if inner else "（空目录，建议清理）")
        )
    return problems


def c_no_stray_artifacts(root: Path, ctx: dict) -> dict:
    """AIE-023  生成物不得跑到课程目录之外（父级残留 `figures/` 之类）。

    生成物的**归属**必须绑定到「哪个课程」，而不是绑定到「脚本从哪儿跑的」（CWD）。
    历史事故：从父目录运行 `extract_slides.py`，图被写到
    `.../2-1 Early Sophomore/figures/…`——课程边界被击穿、父目录被污染，
    而当时所有核对项都只看课程根**内部**，谁也没发现。

    故障注入自测（只读，不碰真实工作区）：
      ① 临时父级里放一个 `figures/` → **必须报出逃逸**；
      ② 临时父级里只放课程子文件夹 → **必须干净**（不误报）。
    任一条不符即 FAIL——只会 PASS 的检查等于没有检查。
    """
    import tempfile

    with tempfile.TemporaryDirectory() as td:
        base = Path(td)
        dirty = base / "SEM"
        (dirty / "figures").mkdir(parents=True)
        (dirty / "figures" / "slide-01.png").write_bytes(b"")
        (dirty / "AIE2040").mkdir()
        pure = base / "PURE"
        (pure / "AIE2040").mkdir(parents=True)
        (pure / "CHM1001").mkdir()
        injected = _escaped_artifacts(dirty)
        clean = _escaped_artifacts(pure)

    bad = []
    if not injected:
        bad.append("注入「父级有 `figures/`」：期望报出逃逸，实际没报 —— 边界检查已失效")
    if clean:
        bad.append("注入「父级只有课程文件夹」：期望干净，实际误报：" + "；".join(clean))
    if bad:
        return mk("FAIL", "逃逸生成物检测逻辑异常", bad)

    problems = _escaped_artifacts(root.parent) if root.parent != root else []
    if problems:
        return mk("FAIL", f"发现 {len(problems)} 个生成物逃出了课程目录", problems)
    return mk("PASS", "未发现逃出课程目录的生成物（故障注入：能报出伪造 `figures/`，且不误报课程文件夹）")


def c_dir_rename_sync(root: Path, ctx: dict) -> dict:
    """AIE-024  目录改名/合并后，识别层必须与税表一致（含「教材 ≠ 课件」判定）。

    `c_folder_map`（AIE-018）只保证「税表声明的目录都存在」。本项补上另一半：
     ① **合并不变量**：`textbook` 与 `slides` 若都存在，必须指向同一目录；
     ② **课件判定（故障注入）**：用临时文件构造 `Textbook Ch1.pdf` / `习题解答 Chapter 1.pdf`
        → 必须判为「非课件」；`Lecture 01 - Intro.pptx` → 必须判为「课件」。
        否则合并目录里的教材会被当成新课件列进「待提炼」，每周自动化都去给整本课本写笔记。
    """
    import tempfile

    tax = ctx.get("tax") or {}
    fm = dict(tax.get("folders") or {})
    problems, tested = [], []

    if fm.get("textbook") and fm.get("slides") and fm["textbook"] != fm["slides"]:
        problems.append(
            f"`textbook` 与 `slides` 未指向同一目录（合并未生效）："
            f"`{fm['textbook']}` vs `{fm['slides']}`"
        )

    cases = [("Textbook Ch1.pdf", False), ("习题解答 Chapter 1.pdf", False),
             ("Lecture 01 - Intro.pptx", True)]
    with tempfile.TemporaryDirectory() as td:
        tdir = Path(td)
        for name, want in cases:
            f = tdir / name
            f.write_bytes(b"")          # 空文件即可，is_deck 只看名字与扩展名
            got = is_deck(f, ctx)
            tested.append(f"`{name}` → 判定为{'课件' if got else '非课件'}")
            if got != want:
                problems.append(
                    f"`{name}`：期望{'课件' if want else '非课件'}，实际"
                    f"{'课件' if got else '非课件'} —— 合并目录里的教材会被误当课件"
                )

    if problems:
        return mk("FAIL", "目录改名/合并后识别层与税表不一致", problems + ["——"] + tested)
    return mk("PASS", f"改名/合并同步正常（合并不变量 OK；课件判定探针 {len(cases)}/{len(cases)} 通过）")


def _self_course() -> str:
    """本脚本**所在工作区**的课程码（读本文件旁边的 taxonomy.json）。

    用途：AIE-016 的核对项要扫脚本自身，需要知道「哪个码算本课、不算跨课」。
    返回空串表示读不到——此时该核对项会退化为「只报不白名单」，宁可多报不可漏报。
    """
    try:
        tax = Path(__file__).resolve().parent.parent / "taxonomy.json"
        return str(json.loads(tax.read_text(encoding="utf-8")).get("course") or "")
    except Exception:  # noqa: BLE001
        return ""


# 故障注入样本的识别标记：这些子串只出现在**探针输入**里，不是真实硬编码。
# 故障注入样本 / 临时造物的识别标记：这些子串只出现在**探针的测试数据**里，
# 不是真实硬编码。判据按「行内容」而非「文件位置」——因为同一行可能是真缺陷，
# 也可能是测试数据，用行内容区分最可靠。
_INJECTION_MARKERS = (
    'print("自查', "print('自查",       # 探针的注入输入
    "_scan('", '_scan("',               # 故障注入调用行本身
    'dirty / "', 'pure / "',            # 临时工作区里造的假目录名
)


def _is_injection_line(line: str) -> bool:
    """判断一行是否是**探针的测试数据**（注入样本 / 临时造物），而非真实硬编码。

    ⚠️ 只用于**真实扫描**，绝不能用在故障注入自测里——否则探针会把自己的
    测试用例一起跳过，`_scan` 永远返回空，检查退化成「只会 PASS」。
    """
    return any(m in line for m in _INJECTION_MARKERS)


def _in_docstring_ranges(src: str) -> list[tuple[int, int]]:
    """返回源码中所有**文档字符串**占据的行号区间（1-based，闭区间）。

    用途：`AIE-016` 的核对项要扫脚本正文，但 docstring 里会大段**引用历史事故**
    （「事故：硬编码了 `AIE2040 课件自动提炼 Essence`」）——那是**说明**，不是缺陷。
    不排除就会造成每次核对都误报，用户久而久之无视这条检查。
    """
    ranges: list[tuple[int, int]] = []
    open_at: int | None = None
    triple = ('"""', "'''")
    for i, line in enumerate(src.splitlines(), 1):
        hits = [t for t in triple if t in line]
        if open_at is None:
            # 只认「以三引号开启」的行；同行成对三引号（`"""x"""`）不算跨行 docstring
            for t in hits:
                if line.count(t) == 1:
                    open_at = i
                    break
        else:
            if any(t in line for t in triple):
                ranges.append((open_at, i))
                open_at = None
    return ranges


# ═══════════ AIE-010 / 013 / 016 / 025：从「需人工」升级为「可自动核对」═══════════
# 背景：这四条原先标为「无法自动核对」，因为当时认为它们「属核对逻辑质量 / 属对话行为 /
#       属代码习惯 / 属交付物」，不适合常驻检查。复核后确认——**它们全都能被静态检查抓住**：
#         · AIE-010 → 扫描所有核对函数，禁止用裸词 `in text` 判结构
#         · AIE-013 → 交接点在 skill 与脚本两个层面都有锚点，锚点在不在是可查的
#         · AIE-016 → 硬编码课程名是纯文本特征，grep 级别即可
#         · AIE-025 → 占位文件策略是否生效，看目录即可
# 每条函数都自带**故障注入**：先构造缺陷副本，确认检查真的会报警，再对真实工作区判定。
# 「只会 PASS 的检查等于没有检查」——这是 AIE-010 的教训，用它来监督它自己。

def c_check_logic_strict(root: Path, ctx: dict) -> dict:
    """AIE-010  核对逻辑不得用「裸词子串包含」判断结构是否存在。

    背景事故：判「笔记有无出处索引」写成 `"出处索引" not in text`，于是一句
    「本页故意省略了出处索引」的缺陷文本反而 PASS —— **提到该词** 被当成了
    **存在该段落**。正确做法是匹配结构标记（`^## 出处索引`）而非裸词。

    故障注入：造两个样本——① 含结构标题的真实笔记（期望判「有」）；
    ② 只在正文提到该词的缺陷笔记（期望判「无」）。若解析器把 ② 也判成「有」，
    说明它退回了子串判断，检查本身失效 → FAIL。
    """
    import tempfile

    self_path = Path(__file__).resolve()
    src = read_text_safe(self_path)

    # ── ① 静态扫描：本文件内是否残留「裸词 in/not in 文本变量」形态的结构判断 ──
    # 白名单：注释、文档字符串、以及对**已解析结构**（如标题列表）的成员判断。
    BARE_PAT = re.compile(
        r"""^\s*(?:if|elif|while)\b[^\n#]*?"""
        r"""(?:["'][^"']{1,30}["'])\s*(?:not\s+)?in\s+"""
        r"""(?:text|body|src_txt|content|raw|note_txt|essence_txt|whole)\b""",
        re.M,
    )
    SUSPECT_HINT = ("出处索引", "英文名", "公式在图内", "00_Index", "作业")
    hits = []
    for m in BARE_PAT.finditer(src):
        line = m.group(0).strip()
        if not any(h in line for h in SUSPECT_HINT):
            continue          # 只盯「判断段落/结构」的场景，无关词放行
        hits.append(f"第 {src[:m.start()].count(chr(10)) + 1} 行：`{line}`")

    # ── ② 故障注入：结构标记解析器必须能区分「有段落」与「提到词」 ──
    def _has_heading(txt: str, word: str) -> bool:
        return bool(re.search(rf"^#{{1,6}}\s*{re.escape(word)}", txt, re.M))

    clean_sample = "# 笔记\n\n## 出处索引\n\n- 第 3 页\n"
    defect_sample = "# 笔记\n\n本页故意省略了出处索引，只有结论。\n"
    inj_bad = []
    if not _has_heading(clean_sample, "出处索引"):
        inj_bad.append("注入「含 `## 出处索引` 标题」：期望判「有」，实际判「无」")
    if _has_heading(defect_sample, "出处索引"):
        inj_bad.append("注入「仅在正文提到『出处索引』」：期望判「无」，实际判「有」—— 退回子串判断")

    if inj_bad:
        return mk("FAIL", "结构判定故障注入失败：检查逻辑已退化为子串包含", inj_bad)
    if hits:
        return mk("FAIL", f"发现 {len(hits)} 处疑似裸词结构判断（应改用标题级正则）", hits)
    return mk("PASS", "未发现裸词结构判断；故障注入通过（能区分「有该段落」与「提到该词」）")


def c_handoff_present(root: Path, ctx: dict) -> dict:
    """AIE-013  流程终点必须显式交给用户「下一步选择」，且两个层面都要落地。

    事故：分类跑完就结束，脚本只打印一句「按 skill 逐份生成」——说给模型听、不说给
    用户听，课件于是长期躺在 `PPT/` 里。纠正要求交接点**双落地**：
      ① skill（管对话行为）：`course-inbox-triage/SKILL.md` 有收尾询问的约定；
      ② 脚本（提醒模型）：`run_pipeline.py` 收尾打印 `⚠️ 终点动作` 提示。
    只做一层最容易漏——所以本项对两层分别做「存在性断言 + 故障注入」。

    故障注入：构造一段**删掉了交接锚点**的假脚本，确认探针判其「缺失」；
    构造一段**含锚点**的假脚本，确认判其「存在」。只会 PASS 的探针等于没有探针。
    """
    def _probe(txt: str) -> bool:
        """脚本层探针：必须同时出现「终点动作」字样与「是否直接提炼」的询问语。"""
        return ("终点动作" in txt) and ("是否直接提炼" in txt)

    def _skill_probe(txt: str) -> bool:
        """skill 层探针：必须出现询问「提炼 PPT 知识点」的收尾约定。"""
        return bool(re.search(r"是否直接提炼\s*PPT\s*知识点", txt))

    # ── 故障注入 ──
    inj_bad = []
    if _probe("print('跑完了')\n"):
        inj_bad.append("注入「无交接锚点的脚本」：期望判缺失，实际判存在")
    if not _probe('print("⚠️ 终点动作 → 请在回复里问用户：是否直接提炼 PPT 知识点？")\n'):
        inj_bad.append("注入「含交接锚点的脚本」：期望判存在，实际判缺失")
    if _skill_probe("处理完 inbox 就结束。\n"):
        inj_bad.append("注入「无收尾询问的 skill」：期望判缺失，实际判存在")
    if not _skill_probe("请在回复末尾问：是否直接提炼 PPT 知识点？（当前 N 份）\n"):
        inj_bad.append("注入「含收尾询问的 skill」：期望判存在，实际判缺失")
    if inj_bad:
        return mk("FAIL", "交接点探针故障注入失败（探针本身失效）", inj_bad)

    # ── 真实判定：两层分别查 ──
    problems = []
    pipe = root / "_System" / "scripts" / "run_pipeline.py"
    if not pipe.is_file():
        problems.append("`_System/scripts/run_pipeline.py` 不存在 —— 无法确认脚本层交接点")
    elif not _probe(read_text_safe(pipe)):
        problems.append("`run_pipeline.py` 收尾**没有**打印 `⚠️ 终点动作` 询问（脚本层交接点缺失）")

    sk = locate_skill_file(root, "course-inbox-triage", "SKILL.md")
    if not sk:
        problems.append("找不到 `course-inbox-triage/SKILL.md` —— 无法确认 skill 层交接点")
    elif not _skill_probe(read_text_safe(sk)):
        problems.append("`course-inbox-triage/SKILL.md` **没有**收尾询问约定（skill 层交接点缺失）")

    if problems:
        return mk("FAIL", f"交接点未双落地（{len(problems)} 处缺失）", problems)
    return mk("PASS", "交接点双落地完好：脚本打印终点动作 + skill 约定收尾询问（故障注入通过）")


def c_no_hardcoded_course(root: Path, ctx: dict) -> dict:
    """AIE-016  脚本/配置里不得硬编码课程专属字面量（整套复制时的定时炸弹）。

    事故：`health_check.py` 的提示文案里硬编码了 `AIE2040 课件自动提炼 Essence`，
    随文件被复制到 CHM1001 后，本课的检查让用户去查**另一门课**的自动化。
    AIE-015 管住了文档，AIE-016 管代码——两者合起来才是「整套复制」的完整检查面。

    做法：扫 `_System/scripts/*.py` 与 `_System/taxonomy.json`，找**别的课程码**
    （形如 AIE2040 / MAT3007 之类的课程码字面量）——本课码从税表 `course` 字段读，
    所以「本课名出现在本课脚本里」是合法的，只有**其他课**的码才算问题。
    同时允许出现在明确的「排除清单 / 说明性注释」里（白名单：含 `继承` `移植` `迁移` 的行）。

    故障注入：先确认探针能报出伪造的跨课字面量，再确认它对「本课码」不误报。
    """
    course = str((ctx.get("tax") or {}).get("course") or "").strip()
    if not course:
        return mk("N/A", "税表无可用的 course 字段，跳过硬编码扫描")

    CROSS_PAT = re.compile(r"\b([A-Z]{2,4}\d{3,4})\b")
    ALLOW_HINT = ("继承", "移植", "迁移", "母版", "示例", "e.g.", "例：", "noqa")
    # 已知的**非课程码**白名单：形如 `ZZZnnnn` 但其实是工具/规范标识符，不是课程码。
    # `BLE001` 是 flake8-bugbear 的规则号（本文件多处 `# noqa: BLE001`），
    # 若不放行会造成每次核对都误报，久而久之用户就会无视这条检查（狼来了）。
    NOT_A_COURSE = {"BLE001", "E501", "F401", "W291", "UP015", "SIM108"}

    def _scan(txt: str, self_code: str, *, skip_injection: bool = False) -> list[str]:
        """扫出一行里的跨课码。跳过对象：注释行、白名单说明行、已知非课程码。

        ⚠️ 这是**行级**扫描，不解析 AST。三个必须小心的点：

        1. **注释行要跳过**——本文件的注释里大量出现别课码（讲历史事故），
           那不是硬编码缺陷。
        2. **docstring 要跳过**——同理，说明性文字会引用别课码作为例子。
        3. **`skip_injection` 只在扫真实工作区时开**。本文件里含故障注入样本
           与临时造物名（如 `'print("自查 AIE2040 的自动化")'`、`dirty / "AIE2040"`），
           那是探针的**测试数据**，不是缺陷。但该参数**绝不能**用在故障注入
           自测里——否则探针会把自己的测试用例一起跳过，`_scan` 永远返回空，
           检查就退化成「只会 PASS」。**这个坑我踩过两次**：第一版把跳过逻辑
           写在 `_scan` 内部，结果第一条注入测试就报「期望报出，实际没报」。
        """
        bad = []
        doc_lines = {n for a, b in _in_docstring_ranges(txt) for n in range(a, b + 1)}
        for ln, line in enumerate(txt.splitlines(), 1):
            if ln in doc_lines:                   # docstring 内的说明性引用
                continue
            if line.strip().startswith("#"):      # 纯注释行
                continue
            if any(h in line for h in ALLOW_HINT):
                continue
            if skip_injection and _is_injection_line(line):
                continue
            for m in CROSS_PAT.finditer(line):
                code = m.group(1)
                if code == self_code or code in NOT_A_COURSE:
                    continue
                bad.append(code)
        return bad

    # ── 故障注入（**不开** skip_injection，否则探针自欺）──
    inj_bad = []
    if not _scan('print("自查 AIE2040 的自动化")', "CHM1001"):
        inj_bad.append("注入「含跨课字面量」：期望报出，实际没报")
    if _scan('print("自查 CHM1001 的自动化")', "CHM1001"):
        inj_bad.append("注入「仅本课码」：期望干净，实际误报")
    if _scan('# 教训移植自 AIE2040（母版）', "CHM1001"):
        inj_bad.append("注入「白名单说明行」：期望放行，实际误报")
    if _scan('    except Exception:  # noqa: BLE001', "CHM1001"):
        inj_bad.append("注入「linter 规则号 BLE001」：期望放行，实际误报")
    if _scan("    # 纯注释：AIE2040 曾在别处出现\n", "CHM1001"):
        inj_bad.append("注入「纯注释行」：期望放行，实际误报")
    if inj_bad:
        return mk("FAIL", "跨课字面量探针故障注入失败", inj_bad)

    # ── 真实扫描（开 skip_injection，忽略本文件内的探针样本）──
    hits = []
    sdir = root / "_System" / "scripts"
    if sdir.is_dir():
        for p in sorted(sdir.glob("*.py")):
            for code in sorted(set(_scan(read_text_safe(p), course, skip_injection=True))):
                hits.append(f"`{p.name}` 出现跨课码 `{code}`")
    tax_file = root / "_System" / "taxonomy.json"
    if tax_file.is_file():
        for code in set(_scan(read_text_safe(tax_file), course)):
            hits.append(f"`taxonomy.json` 出现跨课码 `{code}`")

    if hits:
        return mk("FAIL", f"发现 {len(hits)} 处硬编码的其他课程码（复制到新课程后会指错对象）", hits)
    return mk("PASS", f"脚本与税表均无跨课硬编码（本课码 `{course}` 从税表推导；故障注入通过）")


def c_placeholder_dirs(root: Path, ctx: dict) -> dict:
    """AIE-025  空目录必须有占位文件，否则打包/备份时目录会静默丢失。

    事故：zip 只记录**文件条目**，`0_inbox/` 等空目录不进包；对方解压后第一次跑
    `--phase both` 就 `❌ FAIL AIE-018`（税表声明的目录不存在），而报错文案还把人
    往「目录被改名了」的错误方向带。纠正：每个内容目录放一个占位文件。

    故障注入：构造「有 3 个目录、其中 1 个空」的假工作区 → 期望正好报出那 1 个；
    构造「全部都有占位文件」的假工作区 → 期望干净。只会 PASS 的检查等于没有检查。

    ⚠️ 只报**本流程的内容目录**（税表 folders 声明的那些），不碰 `_System/` 这类
    必然有文件的目录，也不碰用户自己新建的目录。
    """
    import tempfile

    tax = ctx.get("tax") or {}
    fm = dict(tax.get("folders") or {})
    if not fm:
        return mk("N/A", "税表未声明 folders，跳过占位文件检查")

    def _empties(root_dir: Path, dirs: list[str]) -> list[str]:
        out = []
        for name in dirs:
            d = root_dir / name
            if not d.is_dir():
                continue                       # 目录不存在由 AIE-018 负责报，本项不重复
            if not any(p.is_file() for p in d.rglob("*")):
                out.append(name)
        return out

    # ── 故障注入 ──
    with tempfile.TemporaryDirectory() as td:
        base = Path(td)
        dirty = base / "dirty"
        (dirty / "0_inbox").mkdir(parents=True)
        (dirty / "1_Syllabus").mkdir()
        (dirty / "1_Syllabus" / "README.md").write_text("x", encoding="utf-8")
        (dirty / "3_Essence").mkdir()
        (dirty / "3_Essence" / "00_Index.md").write_text("x", encoding="utf-8")
        clean = base / "clean"
        for n in ("0_inbox", "1_Syllabus", "3_Essence"):
            (clean / n).mkdir(parents=True)
            (clean / n / "README.md").write_text("x", encoding="utf-8")
        inj_dirty = _empties(dirty, ["0_inbox", "1_Syllabus", "3_Essence"])
        inj_clean = _empties(clean, ["0_inbox", "1_Syllabus", "3_Essence"])

    inj_bad = []
    if inj_dirty != ["0_inbox"]:
        inj_bad.append(f"注入「1 个空目录」：期望报出 `['0_inbox']`，实际 `{inj_dirty}`")
    if inj_clean:
        inj_bad.append(f"注入「全部有占位文件」：期望干净，实际报出 `{inj_clean}`")
    if inj_bad:
        return mk("FAIL", "占位文件检测故障注入失败", inj_bad)

    empties = _empties(root, list(fm.values()))
    if empties:
        return mk("FAIL",
                  f"{len(empties)} 个内容目录是空的（打包/备份后会静默丢失整个目录）",
                  [f"`{n}/` —— 请放入占位文件（如 `README.md`）" for n in empties])
    return mk("PASS", f"{len(fm)} 个内容目录均含占位文件（打包后结构不丢；故障注入通过）")


def c_inheritance_header(root: Path, ctx: dict) -> dict:
    """AIE-015  整套复制后，`ERROR_LOG.md` 头部必须有**继承说明**。

    事故：把 AIE2040 的流程全盘拷到 CHM1001 时，ERROR_LOG 里满篇是 AIE2040 的
    叙述。原样复制会让新课程的教训库**看起来像本课记录、实际在讲另一门课**，
    日后追溯张冠李戴。

    这条原先标「无法自动核对」，复核后确认**可以**——继承说明是文件头的固定结构：
     ① 头部（前 20 行内）必须声明**继承自哪门课**；
     ② 必须声明**本课新增教训的起编编号**（否则会覆盖继承条目）。

    故障注入：造一份「无继承头」的假 ERROR_LOG → 必须报出；造一份「含完整继承头」
    的 → 必须干净。另外验证「本课新增编号是否真的与继承条目冲突」。
    """
    def _check_header(txt: str) -> list[str]:
        head = "\n".join(txt.splitlines()[:25])
        probs = []
        if not re.search(r"继承自|继承说明|inherited from", head):
            probs.append("头部未声明「继承自」哪门课")
        if not re.search(r"(新增|新条目|起编号|从.{0,12}\+ ?1 ?起|本课程新增)", head):
            probs.append("头部未声明本课新增教训的起编编号规则")
        return probs

    # ── 故障注入 ──
    inj_bad = []
    if not _check_header("# ERROR_LOG — 某课程\n\n> 现有 AIE-001~024 是流程级教训。\n"):
        inj_bad.append("注入「无继承头的 ErrorLog」：期望报出，实际没报")
    good = ("# ERROR_LOG\n\n> ℹ️ **本文件继承自 AIE2040 工作区**。\n"
            "> **本课程新增的教训请从现有最大编号 + 1 起编号**。\n")
    if _check_header(good):
        inj_bad.append("注入「含完整继承头」：期望干净，实际误报")
    if inj_bad:
        return mk("FAIL", "继承头探针故障注入失败", inj_bad)

    err_log = root / "_System" / "ERROR_LOG.md"
    if not err_log.is_file():
        return mk("N/A", "无 ERROR_LOG.md")
    probs = _check_header(read_text_safe(err_log))

    # ── 编号冲突检查：本课条目编号不得与继承条目重复 ──
    ids = [i for i, _t in parse_lesson_ids(err_log)]
    dupes = sorted({x for x in ids if ids.count(x) > 1})
    if dupes:
        probs.append(f"编号重复：{', '.join(dupes)}（继承条目与本课新增条目撞号）")

    if probs:
        return mk("FAIL", f"ERROR_LOG 继承说明不完整（{len(probs)} 处）", probs)
    return mk("PASS", f"继承说明完整（{len(ids)} 条教训、编号无重复；故障注入通过）")


def c_rrule_single_hour(root: Path, ctx: dict) -> dict:
    """AIE-012  调度规则不得含多值 `BYHOUR`（后端只接受单个整点）。

    事故：想「每天 12:30 与 21:30 各跑一次」，写了 `FREQ=DAILY;BYHOUR=12,21;BYMINUTE=30`，
    创建直接失败（`BYHOUR must be an integer between 0 and 23`）。后端只接受**单个**
    `BYHOUR`，多值只对 `BYDAY` / `BYMONTHDAY` 生效。

    这条原先标「无法自动核对」（属平台限制、不是工作区状态）。复核后确认可以做，
    而且**更该做**——因为它的正确形态是一条**容易写错的规则**：

     ① 静态自检：本核对项自带探针，验证「多值 BYHOUR 探测器」真能识别出违规写法；
     ② 文档守卫：`WORKFLOW.md` / `README.md` 必须写明这条限制，
        否则下一个人还会照着 RRULE 规范写出多值 BYHOUR。
    """
    BAD_RRULE = re.compile(r"BYHOUR\s*=\s*\d{1,2}\s*(?:,\s*\d{1,2})", re.I)

    # ── ① 探测器自检（故障注入）──
    inj_bad = []
    if not BAD_RRULE.search("FREQ=DAILY;BYHOUR=12,21;BYMINUTE=30"):
        inj_bad.append("注入「多值 BYHOUR」：期望识别，实际漏过")
    if BAD_RRULE.search("FREQ=WEEKLY;BYDAY=SA;BYHOUR=0;BYMINUTE=15"):
        inj_bad.append("注入「单值 BYHOUR」：期望放行，实际误报")
    if BAD_RRULE.search("FREQ=WEEKLY;BYDAY=MO,WE,FR;BYHOUR=9;BYMINUTE=0"):
        inj_bad.append("注入「多值 BYDAY + 单值 BYHOUR」：期望放行，实际误报")
    if inj_bad:
        return mk("FAIL", "多值 BYHOUR 探测器故障注入失败", inj_bad)

    # ── ② 文档守卫：限制必须被写下来 ──
    problems = []
    docs = [root / "_System" / "WORKFLOW.md", root / "README.md"]
    found = False
    for d in docs:
        if not d.is_file():
            continue
        txt = read_text_safe(d)
        if "BYHOUR" in txt and ("多值" in txt or "单个" in txt or "一条只能" in txt):
            found = True
            break
    if not found:
        problems.append("`WORKFLOW.md` / `README.md` 未写明「rrule 的 BYHOUR 只能是单个整点」")
    if problems:
        return mk("FAIL", "AIE-012 的平台限制未被文档化（下一个人还会踩）", problems)
    return mk("PASS", "多值 BYHOUR 限制已文档化，探测器自检通过")


LESSON_CHECKS: dict[str, tuple[str, object]] = {
    "AIE-001": ("Essence/ 只收与课件同名的 .md", c_essence_only_md),
    "AIE-002": ("Inbox 处理完必须为空（仅允许临时文件）", c_inbox_clean),
    "AIE-003": ("PPT 每份课件都有同名 Essence 笔记", c_coverage),
    "AIE-004": ("提取物不得过期（课件更新过就要重提取）", c_extract_fresh),
    "AIE-005": ("每次 --apply 都留下可回滚的 moved_*.json", c_manifests),
    "AIE-006": ("报告已落盘且为 UTF-8 可读文本", c_logs_readable),
    "AIE-007": ("脚本语法自检通过、不留 __pycache__", c_scripts_syntax),
    "AIE-008": ("Essence 笔记含「出处索引」段（防臆造）", c_essence_citations),
    "AIE-009": ("报告显示真实文件夹名而非内部键名", c_report_labels),
    "AIE-010": ("核对逻辑不得用裸词子串判断结构（含故障注入自测）", c_check_logic_strict),
    "AIE-011": ("自动化必须真的在跑（心跳检测）", c_automation_alive),
    "AIE-012": ("rrule 不得用多值 BYHOUR（且限制已文档化）", c_rrule_single_hour),
    "AIE-013": ("流程终点交接点必须双落地（脚本 + skill）", c_handoff_present),
    "AIE-016": ("脚本/税表不得硬编码其他课程码", c_no_hardcoded_course),
    "AIE-019": ("首次写心跳那一轮不得误报「无心跳」（故障注入自测）", c_first_heartbeat),
    "AIE-020": ("术语与重点区域必须带英文名（英文优先）", c_bilingual_names),
    "AIE-021": ("「公式在图内」正文下划线 ↔ 文末清单一一对应", c_formula_in_figure),
    "AIE-022": ("生成物路径无空格 / 图片链接语法合法且可解析", c_link_safe),
    "AIE-014": ("税表里的多词短语必须真的能命中", c_keyword_matcher),
    "AIE-015": ("ERROR_LOG 头部必须含继承说明且编号不冲突", c_inheritance_header),
    "AIE-017": ("笔记与图表双向对齐（防断图/防漏用）", c_figure_links),
    "AIE-018": ("税表声明的目录必须都存在（防改名脱节）", c_folder_map),
    "AIE-023": ("生成物不得逃出课程目录（父级无 figures/ 残留）", c_no_stray_artifacts),
    "AIE-024": ("目录改名/合并后识别层与税表一致（含教材≠课件）", c_dir_rename_sync),
    "AIE-025": ("内容目录不得为空（空目录打包后会静默丢失）", c_placeholder_dirs),
    "AIE-026": ("错题本笔记图片链接语法合法且指向真实文件", c_correction_links),
    "AIE-027": ("报告模式标签忠实反映真实动作（空 Inbox 的 --apply 不谎报）", c_apply_honest),
}


def parse_lesson_ids(err_log: Path) -> list[tuple[str, str]]:
    """从 ERROR_LOG.md 抽取 (ID, 标题)。"""
    if not err_log.is_file():
        return []
    out = []
    for line in read_text_safe(err_log).splitlines():
        m = re.match(r"^##\s+(AIE-\d+)\s*[—\-–]\s*(.+)$", line.strip())
        if m:
            title = re.sub(r"\[[^\]]*\]\s*$", "", m.group(2)).strip()
            out.append((m.group(1), title))
    return out


# ─────────────────────────── 报告渲染 ───────────────────────────
def render(root: Path, phase: str, results: list[tuple[str, str, dict]], extra: dict) -> str:
    L = [f"# 工作区健康检查（{'开工检查' if phase == 'open' else '收工核对'}） — {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", ""]
    L.append(f"- 课程根目录：`{root}`")
    L.append(f"- 阶段：`{phase}`")
    if extra.get("receipt"):
        L.append(f"- **{extra['receipt']}**")
    L.append("")

    bad = [r for r in results if r[2]["status"] in ("FAIL",)]
    warn = [r for r in results if r[2]["status"] in ("WARN",)]
    notice = [r for r in results if r[2]["status"] in ("NOTICE",)]
    if bad:
        L.append(f"## 结论：❌ 有 {len(bad)} 项严重问题，必须先处理\n")
    elif warn:
        L.append(f"## 结论：⚠️ 有 {len(warn)} 项需要关注\n")
    elif notice:
        L.append(f"## 结论：ℹ️ 有 {len(notice)} 项待办（属正常作业，非故障）\n")
    else:
        L.append("## 结论：✅ 全部通过\n")

    L.append("## 检查明细\n")
    L.append("| 编号 | 检查项 | 结果 | 说明 |")
    L.append("|:--|:--|:--|:--|")
    for code, name, r in results:
        L.append(f"| {code} | {name} | {MARK.get(r['status'], r['status'])} | {r['summary']} |")
    L.append("")

    detailed = [(c, n, r) for c, n, r in results if r["details"]]
    if detailed:
        L.append("## 明细\n")
        for code, name, r in detailed:
            L.append(f"### {code} · {name} — {MARK.get(r['status'], r['status'])}\n")
            for d in r["details"]:
                L.append(("- " + d.lstrip()) if not d.startswith("  ") else d)
            L.append("")

    if phase == "close":
        L.append("## ERROR_LOG 核对说明\n")
        L.append(f"- 教训来源：`{extra.get('err_log')}`（共 {extra.get('lesson_total', 0)} 条）")
        L.append(f"- 已自动核对：{extra.get('auto_n', 0)} 条；需人工核对：{extra.get('manual', 0)} 条；登记失效：{extra.get('stale', 0)} 条")
        if extra.get("manual_ids"):
            L.append(f"- 👤 **需人工核对的条目**：{', '.join(extra['manual_ids'])}")
        if extra.get("stale_ids"):
            L.append(f"- 🕳 **脚本登记但 ERROR_LOG 已无此条**：{', '.join(extra['stale_ids'])}（请同步清理脚本）")
        L.append("")
        L.append("> 新增教训时：① 在 `_System/ERROR_LOG.md` 记 `## AIE-nnn — 标题`；② 若可自动化，在 `health_check.py` 的 `LESSON_CHECKS` 里登记同 ID 的核对函数。未登记的条目会被标为「需人工核对」，不会被静默跳过。")
        L.append("")
    L.append("---")
    L.append("")
    L.append("> 本报告由 `_System/scripts/health_check.py` 生成。")
    L.append("")
    return "\n".join(L)


def main() -> int:
    ap = argparse.ArgumentParser(description="课程工作区健康检查")
    ap.add_argument("--root", default=None, help="课程根目录（含 _System/taxonomy.json）")
    ap.add_argument("--phase", choices=["open", "close", "both"], default="open")
    ap.add_argument("--quiet", action="store_true", help="只输出一行回执")
    ap.add_argument("--beat", default=None, metavar="NAME", help="检查完后写一份自动化心跳（值为自动化名称）")
    ap.add_argument("--beat-processed", default="", help="写入心跳的「本轮处理清单」，逗号分隔（可选）")
    args = ap.parse_args()

    root = Path(args.root).expanduser().resolve() if args.root else find_course_root(Path.cwd())
    if not root.is_dir():
        print(f"[ERROR] 课程根目录不存在：{root}", file=sys.stderr)
        return 1
    logs = root / "_System" / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")

    mod = load_triage_module(root)
    # AIE-019：`--beat` 在核对**之后**才落盘，所以本轮核对时心跳可能还不存在。
    # 把「本轮会不会写心跳」提前告知核对函数，避免首次运行误报。
    ctx: dict = {"triage_mod": mod, "tax": None, "will_write_beat": bool(args.beat)}
    if mod:
        try:
            ctx["tax"], _ = mod.load_taxonomy(root, None)
        except Exception:  # noqa: BLE001
            ctx["tax"] = None

    phases = ["open", "close"] if args.phase == "both" else [args.phase]
    worst = 0
    summary_lines = []

    for phase in phases:
        if phase == "open":
            results = [(c, n, fn(root, ctx)) for c, n, fn in OPEN_CHECKS]  # type: ignore[operator]
            extra = {}
        else:
            err_log = root / "_System" / "ERROR_LOG.md"
            lessons = parse_lesson_ids(err_log)
            results, auto_n, manual_ids, stale_ids = [], 0, [], []
            for lid, title in lessons:
                reg = LESSON_CHECKS.get(lid)
                if reg is None:
                    results.append((lid, title, mk("MANUAL", "未登记自动核对，需人工比对")))
                    manual_ids.append(lid)
                    continue
                name, fn = reg
                results.append((lid, f"{title}", fn(root, ctx)))  # type: ignore[operator]
                auto_n += 1
            known = {lid for lid, _ in lessons}
            for lid, (name, _fn) in LESSON_CHECKS.items():
                if lid not in known:
                    stale_ids.append(lid)
            hits = sum(1 for _, _, r in results if r["status"] in ("FAIL", "WARN"))
            receipt = f"[ERROR_LOG 自检] 已过 {len(lessons)} 条 / 命中 {hits} 条"
            extra = {
                "err_log": err_log,
                "lesson_total": len(lessons),
                "auto_n": auto_n,
                "manual": len(manual_ids),
                "stale": len(stale_ids),
                "manual_ids": manual_ids,
                "stale_ids": stale_ids,
                "receipt": receipt,
            }

        rep = logs / f"health_{phase}_{stamp}.md"
        rep.write_text(render(root, phase, results, extra), encoding="utf-8")

        fails = [r for r in results if r[2]["status"] == "FAIL"]
        warns = [r for r in results if r[2]["status"] == "WARN"]
        notices = [r for r in results if r[2]["status"] == "NOTICE"]
        if fails:
            worst = max(worst, 4)
        elif warns:
            worst = max(worst, 3)

        tag = "开工检查" if phase == "open" else "收工核对"
        line = f"[{'✖' if fails else '⚠' if warns else '✔'}] {tag}：通过 {len(results) - len(fails) - len(warns) - len(notices)} / 关注 {len(warns)} / 待办 {len(notices)} / 严重 {len(fails)}"
        summary_lines.append(line)
        if extra.get("receipt"):
            summary_lines.append("    " + extra["receipt"])

        if not args.quiet:
            print(f"\n{'=' * 68}\n{tag}  （报告：{rep.name}）\n{'=' * 68}")
            for code, name, r in results:
                print(f"  {MARK.get(r['status'], r['status']):<12} {code:<8} {name}")
                if r["status"] in ("FAIL", "WARN"):
                    for d in r["details"][:6]:
                        print(f"                            {d.lstrip()}")
            if extra.get("receipt"):
                print(f"\n  {extra['receipt']}")

    if args.beat:
        beat = logs / "automation_heartbeat.json"
        processed = [x.strip() for x in args.beat_processed.split(",") if x.strip()]
        beat.write_text(
            json.dumps(
                {
                    "automation": args.beat,
                    "last_run": datetime.now().isoformat(timespec="seconds"),
                    "phases": phases,
                    "worst_exit": worst,
                    "processed": processed,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        print(f"[beat] 已写心跳：{beat}")

    print("\n" + "\n".join(summary_lines))
    return worst


if __name__ == "__main__":
    raise SystemExit(main())
