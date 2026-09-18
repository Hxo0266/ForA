#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
extract_slides.py — 课件全文/备注/**图表**提取器（essence-extraction skill 的前置步骤）

用途
    把 <course_root>/PPT 下的 .pptx / .pdf / .docx 逐页（逐张）提取为
    ① 纯文本 + 结构化 JSON（笔记的**唯一事实基础**，禁止凭视觉印象写内容）
    ② **每页的图表 PNG**（按需），供 Essence 笔记把图**贴在对应知识点旁边**

为什么要渲染整页而不是只抽嵌图
    PPT 里的示意图多数是「形状 + 箭头 + 文本框」拼出来的，不是一张嵌入式图片。
    只抽 embed 图片会漏掉绝大部分图。所以对 **含图表的页** 直接渲染整页为 PNG，
    所见即所得；含嵌入图的页也一并被整页渲染覆盖。

渲染链路（纯脚本，无需 COM）
    .pdf  → PyMuPDF 直接渲染
    .pptx → LibreOffice 无头转 PDF（soffice --headless --convert-to pdf）→ PyMuPDF 渲染
    .docx → 不产图（没有「页/张」语义）

输入
    --root <path>       课程根目录（含 `_System/taxonomy.json`），缺省自动向上探测
    --deck <path>       只处理指定课件（可多次）
    --force             已存在结果也重新提取
    --ocr-hint          对无文本 PDF 额外标注「疑似扫描件」
    --figures {auto,all,none}   图表导出策略，默认 auto（只为含图表的页导出）
    --figures-dpi N     渲染 DPI，默认 110
    --figures-dir <path> 图表输出根目录，默认 <root>/<taxonomy.folders.essence>/figures
    --include-non-decks 批量模式也提取「非课件」（教材/习题解答），默认跳过（AIE-024）

输出
    _System/extracted/<stem>.slides.txt      逐页文本（含 [FIGURE] 行指路）
    _System/extracted/<stem>.slides.json     结构化（每页 index/title/text/tables/notes/n_images/n_shapes）
    _System/extracted/<stem>.figures.json    图表清单（每页 has_figure / kind / file）
    <essence>/figures/<slug>/slide-NN.png    含图表的页（整页渲染）
                                             <slug> = 课件名的**路径安全化**形式（空格→`-`，见 slug()）
    _System/logs/extract_<stamp>.md          提取报告：成功 / 跳过 / 无法解析 / 图表统计

目录名约定（AIE-018 / AIE-024）
    课件目录、笔记目录一律从 `<root>/_System/taxonomy.json` 的 `folders` 解析
    （`slides` / `essence`），**不硬编码**；读不到税表才退回内置默认。

命名约定（AIE-022）
    `<essence>/figures/<slug>/` 与笔记文件名 `<essence>/<slug>.md` 都使用同一个 slug()。
    课件原名里的空格会让 Markdown 链接在空格处被截断（图全部断链）、也会让预览按空格
    截断文件名，所以**生成物一律不含空格**；课件原文件本身不动。

生成物归属（AIE-023）
    所有生成物必须落在**本课程目录内**；`--figures-dir` 若指向课程根之外，直接报错退出，
    防止把图写到学期父目录（历史上就出现过父级 `figures/` 残留）。

退出码  0=全部成功；1=参数/环境错误；2=存在无法解析的文件
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:  # pragma: no cover
    pass

# ─────────────── 目录名解析（AIE-018 / AIE-024）：一律从 taxonomy.json 取 ───────────────
# ⚠️ 目录名会随用户习惯改名/合并（`Inbox`→`0_inbox`、`PPT`+`Textbook`→`2_Textbook&Lecture_PPT`…），
#    所以**不得硬编码**。只有读不到税表时才退回这里的默认值。
FALLBACK_FOLDERS = {
    "inbox": "0_inbox",
    "syllabus": "1_Syllabus",
    "slides": "2_Textbook&Lecture_PPT",
    "textbook": "2_Textbook&Lecture_PPT",
    "essence": "3_Essence",
    "assignment": "4_Assignment",
    "quiz": "5_Quiz",
    "midterm": "6_Midterm Examination",
    "final": "7_Final Examination",
    "others": "10_Others",
}


def load_folders(root: Path) -> dict:
    """读 <root>/_System/taxonomy.json 的 folders；读不到就用内置默认。"""
    t = root / "_System" / "taxonomy.json"
    if t.is_file():
        try:
            data = json.loads(t.read_text(encoding="utf-8"))
            fm = data.get("folders") or {}
            merged = dict(FALLBACK_FOLDERS)
            merged.update({k: v for k, v in fm.items() if isinstance(v, str) and v})
            return merged
        except Exception:  # noqa: BLE001
            pass
    return dict(FALLBACK_FOLDERS)


def fd(root: Path, folders: dict, key: str) -> Path:
    """逻辑名（slides/essence/…）→ 真实目录路径。"""
    return root / (folders.get(key) or FALLBACK_FOLDERS.get(key) or key)


# 「不是课件」的兜底关键词（读不到税表时用）——AIE-024
FALLBACK_NON_DECKS = ("textbook", "教材", "课本", "参考书", "solution", "solutions",
                      "解答", "答案", "edition", "习题解答", "教师用书")


def load_non_deck_keywords(root: Path) -> list[str]:
    """读税表的 `non_deck_keywords`：命中的文件**不是课件**（教材 / 习题解答 / 答案…）。

    ⚠️ AIE-024：`Textbook` 与 `PPT` 合并进 `2_Textbook&Lecture_PPT/` 之后，
    批量提取若不过这一层，就会去**逐页提取整本教材**——既浪费时间，
    又会给教材生成一堆本该属于课件的提取物。
    """
    t = root / "_System" / "taxonomy.json"
    if t.is_file():
        try:
            data = json.loads(t.read_text(encoding="utf-8"))
            kws = [str(k).lower() for k in (data.get("non_deck_keywords") or [])]
            if kws:
                return kws
        except Exception:  # noqa: BLE001
            pass
    return list(FALLBACK_NON_DECKS)

# 「含图表」的判定阈值（auto 模式）
# 宁可多抓：多导一张 PNG 的代价（~几十 KB）远小于漏掉一张示意图。
MIN_SHAPES_FOR_DIAGRAM = 3      # 非文字形状（自选图形/箭头/线条/组合）≥ 3 个 → 视为示意图
SPARSE_TEXT_LEN = 40            # 正文极短 + 有图形 → 视为图页

# ─────────────────────── 路径/链接安全化（AIE-022） ───────────────────────
# ⚠️ 为什么必须做：Markdown 图片语法 `![alt](dest)` 的目标里**不允许未转义的空格**。
#    渲染器在第一个空格处截断，把后半截当成 title，于是图**全部断链**（AIE-017 只查
#    「文件在不在」，会把这种断链误判成 PASS，因为它把整条含空格的串都当路径了）。
#    文件名里的空格同样会让预览/卡片按空格截断（PPT 名 "CHM1001W1-Electronic Structure"
#    在卡片里显示成 "CHM1001W1-Electronic"），文档因此无法正常可视化。
#    所以**凡本流程生成的名字**（图表目录、笔记文件名）一律过 slug()，去掉空格。
_UNSAFE_WS = re.compile(r"[\s\u3000]+")
_UNSAFE_CHR = re.compile(r"[^\w\u4e00-\u9fff\-.]+", re.UNICODE)


def slug(name: str) -> str:
    """把课件名转成「文件系统 + Markdown 链接」双安全的 slug。

    规则：空白（含全角空格）→ `-`；其他不安全字符 → `-`；合并连续 `-`；首尾去 `-`/`.`。
    中文保留（渲染器与文件系统都能正确处理 UTF-8 路径，只有空格/括号才是杀手）。

    ⚠️ 这是**唯一**的 slug 实现（canonical）。`health_check.py` 与 `run_pipeline.py`
    通过动态加载本脚本复用同一个函数；它们各自留的本地兜底副本必须与这里**逐字一致**
    （AIE-022 的核对项会做一致性断言，防止悄悄分叉）。
    """
    s = _UNSAFE_WS.sub("-", name.strip())
    s = _UNSAFE_CHR.sub("-", s)
    s = re.sub(r"-{2,}", "-", s).strip("-.")
    return s or "deck"


def md_dest(rel_posix: str) -> str:
    """兜底：把链接目标里仍不安全/有歧义的字符做百分号编码。

    正常情况（slug 之后）这里无事可做；留作最后一道保险，保证产出的 `[FIGURE]` 路径
    粘进 `![]()` 一定能被解析。
    """
    return (rel_posix.replace("%", "%25").replace(" ", "%20")
            .replace("(", "%28").replace(")", "%29")
            .replace("<", "%3C").replace(">", "%3E")
            .replace("#", "%23").replace("?", "%3F"))


def find_course_root(start: Path) -> Path:
    """找课程根：**税表优先**，其次「有名字含 inbox 的目录」。

    ⚠️ AIE-024：旧判据「同时有 `Inbox/` 与 `PPT/`」已废弃——目录改名/合并后
    那套判断永远认不到课程根，流程会静默失效。
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


def find_soffice() -> str | None:
    for c in (r"C:\Program Files\LibreOffice\program\soffice.exe",
              r"C:\Program Files (x86)\LibreOffice\program\soffice.exe"):
        if Path(c).is_file():
            return c
    return shutil.which("soffice")


def pptx_to_pdf(deck: Path, workdir: Path) -> tuple[Path | None, str]:
    """用 LibreOffice 无头把 pptx 转成 pdf。返回 (pdf路径|None, 说明)。"""
    soffice = find_soffice()
    if not soffice:
        return None, "未找到 LibreOffice（soffice.exe），无法渲染 pptx"
    workdir.mkdir(parents=True, exist_ok=True)
    cmd = [soffice, "--headless", "--norestore", "--nolockcheck", "--nodefault",
           "--convert-to", "pdf", "--outdir", str(workdir), str(deck)]
    try:
        r = subprocess.run(cmd, capture_output=True, timeout=300)
    except Exception as exc:  # noqa: BLE001
        return None, f"LibreOffice 调用失败：{exc}"
    out = workdir / (deck.stem + ".pdf")
    if out.is_file():
        return out, "ok"
    err = (r.stderr or b"").decode("utf-8", "ignore").strip()[:200]
    return None, f"LibreOffice 未产出 PDF（{err or '无输出'}）"


# ─────────────────────────── 逐页「含图」分析 ───────────────────────────
def analyze_pptx(deck: Path) -> tuple[list[dict], list[str]]:
    from pptx import Presentation  # type: ignore
    from pptx.enum.shapes import MSO_SHAPE_TYPE  # type: ignore

    pages: list[dict] = []
    warns: list[str] = []
    prs = Presentation(str(deck))
    for idx, slide in enumerate(prs.slides, 1):
        title, texts, tables, n_img, n_shape = "", [], [], 0, 0
        for shape in slide.shapes:
            try:
                st = shape.shape_type
            except Exception:  # noqa: BLE001
                st = None
            if st == MSO_SHAPE_TYPE.PICTURE or shape.__class__.__name__ == "Picture":
                n_img += 1
                continue
            if getattr(shape, "has_table", False) and shape.has_table:
                tables.append([[c.text.strip() for c in row.cells] for row in shape.table.rows])
                continue
            if getattr(shape, "has_chart", False) and shape.has_chart:
                n_shape += 1           # 原生图表：也是图
                continue
            if st in (MSO_SHAPE_TYPE.AUTO_SHAPE, MSO_SHAPE_TYPE.FREEFORM,
                      MSO_SHAPE_TYPE.LINE, MSO_SHAPE_TYPE.GROUP):
                n_shape += 1
            if getattr(shape, "has_text_frame", False) and shape.has_text_frame:
                t = shape.text_frame.text.strip()
                if not t:
                    continue
                if not title and getattr(shape, "is_placeholder", False):
                    title = t.splitlines()[0]
                texts.append(t)
        if not title and texts:
            title = texts[0].splitlines()[0]
        notes = ""
        try:
            if slide.has_notes_slide and slide.notes_slide.notes_text_frame is not None:
                notes = slide.notes_slide.notes_text_frame.text.strip()
        except Exception:  # noqa: BLE001
            warns.append(f"第 {idx} 张备注读取失败")
        pages.append({"index": idx, "title": title, "text": "\n".join(texts).strip(),
                      "tables": tables, "notes": notes,
                      "n_images": n_img, "n_shapes": n_shape})
    return pages, warns


def analyze_pdf(pdf: Path, ocr_hint: bool) -> tuple[list[dict], list[str]]:
    try:
        import pymupdf  # type: ignore
    except Exception:  # noqa: BLE001
        import fitz as pymupdf  # type: ignore

    pages: list[dict] = []
    warns: list[str] = []
    with pymupdf.open(str(pdf)) as doc:
        empty = 0
        for idx, page in enumerate(doc, 1):
            txt = page.get_text("text").strip()
            if not txt:
                empty += 1
            first = next((ln.strip() for ln in txt.splitlines() if ln.strip()), "")
            tables = []
            try:
                for tb in page.find_tables():
                    tables.append(tb.extract())
            except Exception:  # noqa: BLE001
                pass
            try:
                n_draw = len(page.get_drawings())
            except Exception:  # noqa: BLE001
                n_draw = 0
            pages.append({"index": idx, "title": first, "text": txt, "tables": tables, "notes": "",
                          "n_images": len(page.get_images(full=True)),
                          "n_shapes": n_draw,
                          "_text_len": len(txt)})
        if doc.page_count and empty / doc.page_count > 0.5:
            warns.append(f"{empty}/{doc.page_count} 页无文本层" +
                         ("（疑似扫描件，需 OCR）" if ocr_hint else "（可能是扫描件或纯图排版）"))
    return pages, warns


def analyze_docx(path: Path) -> tuple[list[dict], list[str]]:
    import docx  # type: ignore

    d = docx.Document(str(path))
    chunks, cur = [], []
    for p in d.paragraphs:
        if p.style.name.lower().startswith("heading") and cur:
            chunks.append(cur)
            cur = []
        if p.text.strip():
            cur.append(p.text.strip())
    if cur:
        chunks.append(cur)
    pages = [{"index": i + 1, "title": (c[0] if c else ""), "text": "\n".join(c),
              "tables": [], "notes": "", "n_images": 0, "n_shapes": 0} for i, c in enumerate(chunks)]
    return pages, []


def classify_figure(pg: dict) -> tuple[bool, str]:
    """返回 (是否需要导出为图, 类型说明)。"""
    if pg["n_images"] > 0:
        return True, f"{pg['n_images']} 张嵌入图"
    if pg["tables"]:
        return True, "表格"
    if pg["n_shapes"] >= MIN_SHAPES_FOR_DIAGRAM:
        return True, f"{pg['n_shapes']} 个矢量图形（示意图）"
    if pg["n_shapes"] > 0 and len(pg.get("text", "")) < SPARSE_TEXT_LEN:
        return True, f"文字极短 + {pg['n_shapes']} 个图形"
    return False, ""


# ─────────────────────────────── 渲染 ───────────────────────────────
def render_pages(pdf: Path, out_dir: Path, indexes: list[int], dpi: int) -> tuple[dict[int, Path], list[str]]:
    try:
        import pymupdf  # type: ignore
    except Exception:  # noqa: BLE001
        import fitz as pymupdf  # type: ignore

    out_dir.mkdir(parents=True, exist_ok=True)
    made: dict[int, Path] = {}
    warns: list[str] = []
    with pymupdf.open(str(pdf)) as doc:
        for i in indexes:
            if i < 1 or i > doc.page_count:
                warns.append(f"第 {i} 张超出 PDF 页数（{doc.page_count}）")
                continue
            try:
                pix = doc[i - 1].get_pixmap(dpi=dpi, colorspace=pymupdf.csRGB, alpha=False)
                fp = out_dir / f"slide-{i:02d}.png"
                pix.save(str(fp))
                made[i] = fp
            except Exception as exc:  # noqa: BLE001
                warns.append(f"第 {i} 张渲染失败：{exc}")
    return made, warns


def render_txt(deck_name: str, pages: list[dict], figs: dict[int, dict]) -> str:
    out = [f"# SOURCE: {deck_name}", f"# TOTAL_UNITS: {len(pages)}", ""]
    for pg in pages:
        i = pg["index"]
        out.append(f"===== SLIDE {i} =====")
        if pg["title"]:
            out.append(f"[TITLE] {pg['title']}")
        if pg["text"]:
            out.append(pg["text"])
        for ti, tbl in enumerate(pg["tables"], 1):
            out.append(f"[TABLE {ti}]")
            for row in tbl:
                out.append(" | ".join("" if c is None else str(c).replace("\n", " ") for c in row))
        if pg["notes"]:
            out.append(f"[NOTES] {pg['notes']}")
        if pg["n_images"]:
            out.append(f"[IMAGES] {pg['n_images']}")
        f = figs.get(i)
        if f:
            # 这一行是给模型看的指路牌：把图贴在对应知识点旁边
            out.append(f"[FIGURE] {f['rel']}  ({f['kind']})")
        out.append("")
    return "\n".join(out)


EXTRACTORS = {".pptx": lambda p, o: analyze_pptx(p),
              ".pdf": lambda p, o: analyze_pdf(p, o),
              ".docx": lambda p, o: analyze_docx(p)}


def main() -> int:
    ap = argparse.ArgumentParser(description="课件全文/备注/图表提取器")
    ap.add_argument("--root", default=None, help="课程根目录（含 _System/taxonomy.json）")
    ap.add_argument("--deck", action="append", default=[], help="只处理指定课件路径（可多次）")
    ap.add_argument("--force", action="store_true", help="已存在结果也重新提取")
    ap.add_argument("--ocr-hint", action="store_true", help="对无文本 PDF 额外标注疑似扫描件")
    ap.add_argument("--figures", choices=["auto", "all", "none"], default="auto",
                    help="图表导出策略（默认 auto：只为含图表的页导出）")
    ap.add_argument("--figures-dpi", type=int, default=150, help="渲染 DPI（默认 150，保证图内文字可读）")
    ap.add_argument("--figures-dir", default=None, help="图表输出根目录（默认 <root>/<essence>/figures；必须在课程根内）")
    ap.add_argument("--include-non-decks", action="store_true",
                    help="批量模式也提取「非课件」文件（教材/习题解答等），默认跳过（AIE-024）")
    args = ap.parse_args()

    root = Path(args.root).expanduser().resolve() if args.root else find_course_root(Path.cwd())
    if not root.is_dir():
        print(f"[ERROR] 课程根目录不存在：{root}", file=sys.stderr)
        return 1

    folders = load_folders(root)
    ppt_dir = fd(root, folders, "slides")
    ess_dir = fd(root, folders, "essence")
    if not ppt_dir.is_dir():
        print(f"[ERROR] 未找到课件目录（税表 slides = `{folders.get('slides')}`）：{ppt_dir}", file=sys.stderr)
        return 1

    out_dir = root / "_System" / "extracted"
    logs_dir = root / "_System" / "logs"
    fig_root = (Path(args.figures_dir).expanduser().resolve() if args.figures_dir
                else (ess_dir / "figures"))
    # AIE-023：生成物不得逃出课程目录（历史上曾把图写到学期父目录的 `figures/`）
    try:
        fig_root.relative_to(root)
    except ValueError:
        print(f"[ERROR] 图表输出目录在课程根之外（AIE-023）：{fig_root}\n"
              f"        课程根：{root}", file=sys.stderr)
        return 1
    out_dir.mkdir(parents=True, exist_ok=True)
    logs_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")

    if args.deck:
        targets = [Path(d).expanduser().resolve() for d in args.deck]
        targets = [t for t in targets if t.is_file()]
        skipped_non_deck: list[Path] = []
    else:
        all_files = [p for p in sorted(ppt_dir.rglob("*"))
                     if p.is_file() and not p.name.startswith("~$")]
        if args.include_non_decks:
            targets, skipped_non_deck = all_files, []
        else:
            # AIE-024：批量模式默认只处理**课件**；教材/习题解答/答案一律跳过
            nd_kw = load_non_deck_keywords(root)
            targets = [p for p in all_files if not any(k in p.name.lower() for k in nd_kw)]
            skipped_non_deck = [p for p in all_files if any(k in p.name.lower() for k in nd_kw)]

    done, skipped, failed = [], [], []
    tmp_root = Path(tempfile.mkdtemp(prefix="slides_pdf_"))

    try:
        for f in targets:
            stem, ext = f.stem, f.suffix.lower()
            txt_out = out_dir / f"{stem}.slides.txt"
            json_out = out_dir / f"{stem}.slides.json"
            fig_json = out_dir / f"{stem}.figures.json"
            if txt_out.exists() and json_out.exists() and not args.force:
                skipped.append(f)
                continue
            if ext not in EXTRACTORS:
                failed.append((f, f"不支持的格式 {ext}（旧版 .ppt 请先另存为 .pptx）"))
                continue

            try:
                pages, warns = EXTRACTORS[ext](f, args.ocr_hint)
            except Exception as exc:  # noqa: BLE001
                failed.append((f, f"提取异常：{exc}"))
                continue

            # ---------- 图表 ----------
            figs: dict[int, dict] = {}
            fig_notes: list[str] = []
            if args.figures != "none" and pages:
                if args.figures == "all":
                    want = [pg["index"] for pg in pages]
                    kinds = {pg["index"]: "all 模式：强制导出" for pg in pages}
                else:
                    want, kinds = [], {}
                    for pg in pages:
                        ok, why = classify_figure(pg)
                        if ok:
                            want.append(pg["index"])
                            kinds[pg["index"]] = why

                if want:
                    fig_name = slug(stem)      # AIE-022：目录名安全化（去空格/特殊字符）
                    if fig_name != stem:
                        fig_notes.append(
                            f"目录/笔记名已安全化：`{stem}` → `{fig_name}`（原名含空格或特殊字符，"
                            f"直接当路径会让 Markdown 链接在空格处截断）")
                    pdf_src, how = (f, "原生 PDF") if ext == ".pdf" else (None, "")
                    if ext == ".pptx":
                        pdf_src, how = pptx_to_pdf(f, tmp_root / stem)
                    if ext == ".docx":
                        pdf_src, how = None, "docx 无「页」语义，不渲染"
                    if pdf_src:
                        made, rwarns = render_pages(pdf_src, fig_root / fig_name, want, args.figures_dpi)
                        fig_notes += rwarns
                        for i, fp in made.items():
                            # [FIGURE] 给出的路径必须是「笔记自己（<essence>/<slug>.md）可直接用的相对路径」，
                            # 即相对笔记目录，形如 figures/<slug>/slide-NN.png。
                            # 若写成了相对课程根的路径，笔记里粘过去会全部断链（AIE-017 会报 FAIL）。
                            try:
                                rel = fp.relative_to(ess_dir).as_posix()
                            except ValueError:
                                try:
                                    rel = fp.relative_to(root).as_posix()
                                except ValueError:
                                    rel = str(fp)
                            figs[i] = {"index": i, "file": str(fp), "rel": md_dest(rel),
                                       "kind": kinds.get(i, ""), "dpi": args.figures_dpi}
                        missing = [i for i in want if i not in figs]
                        if missing:
                            fig_notes.append(f"以下页未渲染成功：{missing}")
                    else:
                        fig_notes.append(f"无法渲染图表：{how}")
                        if ext == ".pptx":
                            fig_notes.append(f"提示：装 LibreOffice 即可渲染 pptx；或先把课件另存为 PDF 再放回 `{folders.get('slides')}/`")

            fig_json.write_text(json.dumps(
                {"source": f.name, "strategy": args.figures, "dpi": args.figures_dpi,
                 "figure_root": str(fig_root), "count": len(figs),
                 "figures": [figs[i] for i in sorted(figs)], "notes": fig_notes},
                ensure_ascii=False, indent=2), encoding="utf-8")

            txt_out.write_text(render_txt(f.name, pages, figs), encoding="utf-8")
            json_out.write_text(json.dumps(
                {"source": f.name, "path": str(f), "ext": ext, "units": len(pages),
                 "pages": pages, "figure_count": len(figs), "warnings": warns},
                ensure_ascii=False, indent=2), encoding="utf-8")
            done.append((f, len(pages), len(figs), warns, fig_notes))
    finally:
        shutil.rmtree(tmp_root, ignore_errors=True)

    # ---------- 报告 ----------
    rep = logs_dir / f"extract_{stamp}.md"
    L = [f"# 课件提取报告 — {stamp}\n", f"- 课程根目录：`{root}`",
         f"- 文本输出：`{out_dir}`", f"- 图表输出：`{fig_root}`（策略 `{args.figures}`，DPI {args.figures_dpi}）", ""]
    L.append(f"## 已提取（{len(done)}）\n")
    if done:
        L.append("| 课件 | 单元数 | 图表数 | 备注 |")
        L.append("|:--|:--|:--|:--|")
        for f, n, nf, warns, fnotes in done:
            msg = "；".join(warns + fnotes)
            L.append(f"| `{f.name}` | {n} | {nf} | {msg} |")
    else:
        L.append("- 无")
    L.append("")
    if skipped:
        L.append(f"## 已跳过（{len(skipped)}，已有提取结果）\n")
        L += [f"- `{f.name}`" for f in skipped]
        L.append("")
    if skipped_non_deck:
        L.append(f"## 已跳过（{len(skipped_non_deck)}，判定为非课件：教材 / 习题解答 / 答案）\n")
        L += [f"- `{f.name}`" for f in skipped_non_deck]
        L.append("")
        L.append("> 这些文件按 `taxonomy.json` 的 `non_deck_keywords` 被排除，**不生成笔记**；"
                 "若要强制提取，加 `--include-non-decks`（AIE-024）。")
        L.append("")
    if failed:
        L.append(f"## ⚠️ 无法解析（{len(failed)}）\n")
        L.append("| 课件 | 原因 |")
        L.append("|:--|:--|")
        L += [f"| `{f.name}` | {why} |" for f, why in failed]
        L.append("")
    L.append("> 图表清单：`_System/extracted/<课件名>.figures.json`；文本里以 `[FIGURE] <相对路径>` 标记该页有图。")
    L.append("")
    rep.write_text("\n".join(L), encoding="utf-8")

    total_figs = sum(nf for _, _, nf, _, _ in done)
    print(f"[extract] 已提取 {len(done)} / 跳过 {len(skipped)} / 失败 {len(failed)}；图表 {total_figs} 张")
    for f, n, nf, warns, fnotes in done:
        extra = "；".join(warns + fnotes)
        print(f"          OK   {f.name}  ({n} 单元, {nf} 图)" + (f"  [{extra}]" if extra else ""))
    for f, why in failed:
        print(f"          FAIL {f.name}  -> {why}")
    print(f"[extract] 报告：{rep}")
    return 2 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
