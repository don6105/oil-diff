#!/usr/bin/env python3
"""Render diff-data.json and report-spec.json into a standalone HTML change report."""
from __future__ import annotations

import argparse
from collections import Counter
import difflib
import hashlib
from html import escape as e
import json
from pathlib import Path, PurePosixPath
import re
import sys

if sys.version_info < (3, 10):
    raise SystemExit("Python 3.10+ is required to run render_report.py.")

SKILL_ROOT = Path(__file__).resolve().parent.parent
ASSETS_DIR = SKILL_ROOT / "assets"

CHEVRON_SVG = (
    '<svg class="chevron" viewBox="0 0 18 18" aria-hidden="true" focusable="false">'
    '<path d="m6.5 4 5 5-5 5" fill="none" stroke="currentColor" stroke-width="1.5" '
    'stroke-linecap="round" stroke-linejoin="round"/></svg>'
)

FOLDER_ICON_SVG = (
    '<svg class="folder-icon" viewBox="0 0 20 20" aria-hidden="true">'
    '<path d="M2 5a1.5 1.5 0 0 1 1.5-1.5H8l2 2h6.5A1.5 1.5 0 0 1 18 7v9H2z" '
    'fill="#E9C889" stroke="#C79F58"/><path d="M2 8h16v8H2z" fill="#F2DDA9"/></svg>'
)


def file_icon(path: str) -> str:
    outer = '<svg class="file-icon" viewBox="0 0 32 32" aria-hidden="true" focusable="false">'
    if path.endswith(".md"):
        body = (
            '<rect x="3" y="6" width="26" height="20" rx="2" fill="#3F91CF"/>'
            '<path fill="#fff" d="M6 22V10h3l4 5 4-5h3v12h-3v-7l-4 5-4-5v7zM24 10h2v7h3l-4 5-4-5h3z"/>'
        )
    elif path.endswith(".py"):
        body = (
            '<path fill="#3976A5" d="M16 2C8 2 8 5 8 5v5h9v2H5s-3 0-3 7 4 7 4 7h3v-5s0-4 4-4h8s4 0 4-4V6s0-4-9-4z"/>'
            '<circle cx="12" cy="6" r="1.5" fill="#fff"/>'
            '<path fill="#FFD54C" d="M16 30c8 0 8-3 8-3v-5h-9v-2h12s3 0 3-7-4-7-4-7h-3v5s0 4-4 4h-8s-4 0-4 4v7s0 4 9 4z"/>'
            '<circle cx="20" cy="26" r="1.5" fill="#fff"/>'
        )
    elif path.endswith((".js", ".mjs", ".ts", ".tsx", ".jsx")):
        body = (
            '<rect x="3" y="3" width="26" height="26" rx="2" fill="#F2CE3A"/>'
            '<path d="M17 13v9c0 5-7 5-7 0M26 15c-2-3-7-2-7 1 0 4 7 2 7 6 0 4-6 5-8 1" '
            'fill="none" stroke="#332E19" stroke-width="2.6"/>'
        )
    elif Path(path).name.startswith(".git"):
        body = (
            '<rect x="5" y="5" width="22" height="22" rx="2" transform="rotate(45 16 16)" fill="#E86646"/>'
            '<path d="M10 7l12 12M14 11v13" stroke="#fff" stroke-width="2"/>'
            '<g fill="#fff"><circle cx="14" cy="11" r="2.5"/><circle cx="22" cy="19" r="2.5"/>'
            '<circle cx="14" cy="24" r="2.5"/></g>'
        )
    else:
        body = '<path d="M7 3h12l6 6v20H7z" fill="#9AABB7"/><path d="M19 3v7h6" fill="#C9D2D9"/>'
    return outer + body + "</svg>"


def counts_html(f: dict[str, object]) -> str:
    return f'<span class="line-count"><b>+{f["add"]}</b><i>−{f["delete"]}</i></span>'


def colored_text(text: str, mask: list[bool]) -> str:
    if not text:
        return ""
    result: list[str] = []
    start = 0
    for i in range(1, len(text) + 1):
        if i == len(text) or mask[i] != mask[start]:
            value = e(text[start:i])
            result.append(f"<mark>{value}</mark>" if mask[start] else value)
            start = i
    return "".join(result)


def comparison_html(before: list[dict[str, object]], after: list[dict[str, object]], f: dict[str, object]) -> str:
    old = "\n".join(str(r["text"]) for r in before)
    new = "\n".join(str(r["text"]) for r in after)
    masks = [[False] * len(old), [False] * len(new)]
    for tag, i, j, k, l in difflib.SequenceMatcher(None, old, new, autojunk=False).get_opcodes():
        if tag != "equal":
            masks[0][i:j] = [True] * (j - i)
            masks[1][k:l] = [True] * (l - k)

    pair = '<div class="compare">'
    sides = [
        ("old", "修改前", before, str(f.get("from", ""))),
        ("new", "修改后", after, str(f.get("to", ""))),
    ]
    for index, (kind, title, rows, rev) in enumerate(sides):
        pair += (
            f'<section class="compare-side {kind}-side">'
            f'<div class="compare-heading"><strong>{title}</strong><span>{e(rev)}</span></div>'
        )
        if not rows:
            empty_msg = (
                ("原来没有这个文件。" if f.get("kind") == "A" else "此处原来没有这段内容。")
                if index == 0
                else "这段内容已删除。"
            )
            pair += f'<p class="empty-copy">{empty_msg}</p>'
        else:
            pair += '<pre class="source-lines">'
            offset = 0
            last: int | None = None
            for row in rows:
                line_no = int(row["line"])
                row_text = str(row["text"])
                if last is not None and line_no != last + 1:
                    pair += '<span class="source-gap">…</span>'
                mask = masks[index][offset : offset + len(row_text)]
                changed_cls = " has-change" if any(mask) else ""
                rendered_code = colored_text(row_text, mask) or " "
                pair += (
                    f'<span class="source-line{changed_cls}">'
                    f'<span class="line-number" aria-label="第 {line_no} 行">{line_no}</span>'
                    f"<code>{rendered_code}</code></span>"
                )
                offset += len(row_text) + 1
                last = line_no
            pair += "</pre>"
        pair += "</section>"
    return pair + "</div>"


def changed_rows(chunk: dict[str, object], side: str) -> list[dict[str, object]]:
    return [r for r in chunk.get(side, []) if r.get("changed")]


def select_rows(
    f: dict[str, object], side: str, specs: list[dict[str, object]] | None
) -> list[dict[str, object]]:
    chunks = f.get("chunks", [])
    if not chunks:
        return []
    if specs is None:
        return changed_rows(chunks[0], side)

    rows = {int(r["line"]): r for h in chunks for r in h.get(side, [])}
    result: list[dict[str, object]] = []
    for spec in specs:
        if "startLine" in spec and "endLine" in spec:
            start_l = int(spec["startLine"])
            end_l = int(spec["endLine"])
            for n in range(start_l, end_l + 1):
                if n in rows:
                    row = rows[n]
                    text = str(row["text"])
                    result.append({**row, "selection": (0, len(text))})
            continue
        n = int(spec["line"])
        if n not in rows:
            raise ValueError(f"Line {n} not found in {f['id']} ({side}). Available lines: {sorted(rows.keys())}")
        row = rows[n]
        text = str(row["text"])
        start = text.index(str(spec["start"])) if spec.get("start") else 0
        end = text.index(str(spec["end"]), start) if spec.get("end") else len(text)
        clipped = ("…" if start else "") + text[start:end] + ("…" if end < len(text) else "")
        result.append({**row, "text": clipped, "selection": (start, end)})
    return result


def remaining_chunks(
    f: dict[str, object], before: list[dict[str, object]], after: list[dict[str, object]]
) -> list[dict[str, object]]:
    shown: dict[str, dict[int, list[tuple[int, int]]]] = {"before": {}, "after": {}}
    for side, rows in [("before", before), ("after", after)]:
        for row in rows:
            line_no = int(row["line"])
            sel = row.get("selection", (0, len(str(row["text"]))))
            shown[side].setdefault(line_no, []).append(sel)

    result: list[dict[str, object]] = []
    for chunk in f.get("chunks", []):
        rem: dict[str, object] = {**chunk, "before": [], "after": []}
        for side in ("before", "after"):
            side_rows: list[dict[str, object]] = []
            for row in chunk.get(side, []):
                line_no = int(row["line"])
                spans = sorted(shown[side].get(line_no, []))
                if not spans:
                    side_rows.append(row)
                    continue
                text = str(row["text"])
                cursor = 0
                pieces: list[tuple[int, str]] = []
                for start, end in spans:
                    if start > cursor:
                        pieces.append((cursor, text[cursor:start]))
                    cursor = max(cursor, end)
                if cursor < len(text):
                    pieces.append((cursor, text[cursor:]))
                if pieces:
                    value = ("…" if pieces[0][0] else "") + "…".join(piece for _, piece in pieces)
                    if cursor == len(text):
                        value += "…"
                    side_rows.append({**row, "text": value})
            rem[side] = side_rows
        if any(r.get("changed") for side in ("before", "after") for r in rem[side]):
            result.append(rem)
    return result


def full_diff_html(f: dict[str, object], chunks: list[dict[str, object]]) -> str:
    out = ""
    for h in chunks:
        loc = str(h.get("location", "文件内容"))
        heading = f'<div class="hunk-heading">{e(loc)}</div>' if loc != "文件内容" else ""
        out += f'<div class="full-hunk">{heading}{comparison_html(h["before"], h["after"], f)}</div>'
    return out


def default_diagram_html(item: dict[str, object]) -> str:
    points = item.get("points", [])
    letters = "ABCDEF"
    cards = ""
    for idx, pt in enumerate(points):
        letter = letters[idx % len(letters)]
        pt_title = pt[0] if isinstance(pt, list) else pt.get("title", f"要点 {letter}")
        cards += (
            f'<section class="vis-card">'
            f'<div class="vis-card-head"><span>{letter}</span>{e(pt_title)}</div>'
            f'{specimen_pair_html({"title": pt_title}, idx)}</section>'
        )
    return f'<div class="visual-stage"><div class="vis-grid-3">{cards}</div></div>'


def normalize_diagram_html(diag_html: str) -> str:
    """Strip duplicate <p class="problem/example"> that belong in .section-header."""
    cleaned = re.sub(r'^\s*<p class="problem">.*?</p>\s*', "", diag_html, flags=re.DOTALL)
    cleaned = re.sub(r'^\s*<p class="example">.*?</p>\s*', "", cleaned, flags=re.DOTALL)
    return cleaned.strip()


def vis_arrow(extra: str = "") -> str:
    cls = f"vis-arrow {extra}".strip()
    return (
        f'<svg class="{cls}" viewBox="0 0 24 16" aria-hidden="true">'
        '<path d="M1 8h20m-5-5 5 5-5 5" fill="none" stroke="currentColor" '
        'stroke-width="1.3" stroke-linecap="round" stroke-linejoin="round"/></svg>'
    )


def artifact_file(name: str, extra: str = "") -> str:
    cls = f"artifact-file {extra}".strip()
    if name.endswith(".py"):
        svg = (
            '<svg viewBox="0 0 32 32" aria-hidden="true">'
            '<path fill="#3976A5" d="M16 2C8 2 8 5 8 5v5h9v2H5s-3 0-3 7 4 7 4 7h3v-5s0-4 4-4h8s4 0 4-4V6s0-4-9-4z"/>'
            '<path fill="#FFD54C" d="M16 30c8 0 8-3 8-3v-5h-9v-2h12s3 0 3-7-4-7-4-7h-3v5s0 4-4 4h-8s-4 0-4 4v7s0 4 9 4z"/>'
            '<g fill="#fffdf9"><circle cx="12" cy="6" r="1.5"/><circle cx="20" cy="26" r="1.5"/></g></svg>'
        )
    elif name.endswith((".js", ".mjs", ".ts", ".tsx")):
        svg = (
            '<svg viewBox="0 0 32 32" aria-hidden="true">'
            '<rect x="3" y="3" width="26" height="26" rx="3" fill="#F2CE3A"/>'
            '<path d="M17 13v9c0 5-7 5-7 0M26 15c-2-3-7-2-7 1 0 4 7 2 7 6 0 4-6 5-8 1" '
            'fill="none" stroke="#332E19" stroke-width="2.6"/></svg>'
        )
    else:
        svg = (
            '<svg viewBox="0 0 18 18" aria-hidden="true">'
            '<path d="M3 1.5h8l4 4V16H3z" fill="#6e9fbd"/><path d="M11 1.5V6h4" fill="#b8d1df"/>'
            '<path d="M5 12V8h1l1.5 2L9 8h1v4M12 9v3m-1-1 1 1 1-1" fill="none" stroke="#fffdf9" stroke-width=".9"/></svg>'
        )
    return f'<span class="{cls}">{svg}<span>{e(name)}</span></span>'


def vis_state(text: str, good: bool = False) -> str:
    kind = "is-new" if good else "is-old"
    return f'<div class="vis-state {kind}"><span class="state-dot"></span>{e(text)}</div>'


def domain_wire(kind: str) -> str:
    if kind == "play":
        return '<div class="domain-wire wire-play"><span>+</span><i></i><i></i></div>'
    if kind == "landing":
        kind = "marketing"
    w_kind = kind if kind in ("marketing", "content", "workspace") else "workspace"
    return f'<div class="domain-wire wire-{w_kind}">' + "".join("<i></i>" for _ in range(6)) + "</div>"


def mini_shot_window(kind: str = "", side: int = 40, label: str = "项目") -> str:
    return (
        f'<div class="shot-window {kind}" style="--mini-side:{side}px">'
        '<div class="window-chrome"><i></i><i></i><i></i></div>'
        '<div class="shot-sidebar"><i></i><i></i><i></i></div>'
        f'<div class="shot-content"><strong>{e(label)}</strong><span>名称 <i>状态</i></span>'
        "<b></b><b></b><b></b><b></b></div></div>"
    )


def shot_frame_html(src: str, title: str, tag: str, good: bool = True) -> str:
    cls = "is-good" if good else "is-bad"
    dot = '<span class="state-dot"></span>'
    cap = f"{title} · {tag}" if tag else title
    tag_html = f'<span class="vis-tag">{e(tag)}</span>' if tag else ""
    return (
        f'<div class="shot-frame {cls}">'
        f'<div class="shot-frame-bar"><span>{dot} {e(title)}</span>'
        '<span class="shot-zoom-hint">🔍 点击放大</span></div>'
        f'<button type="button" class="shot-zoom-trigger" data-lightbox-src="{e(src)}" data-lightbox-caption="{e(cap)}">'
        f'<img src="{e(src)}" alt="{e(title)}" loading="lazy"></button>'
        f"{tag_html}</div>"
    )


def specimen_pair_html(sc: dict[str, object], idx: int) -> str:
    kind = str(sc.get("kind", "")).lower()
    title = str(sc.get("title", ""))
    bad_tag = str(sc.get("badTag") or sc.get("beforeTag") or "")
    good_tag = str(sc.get("goodTag") or sc.get("afterTag") or "")
    shot_src = str(sc.get("src") or sc.get("afterSrc") or "")
    before_src = str(sc.get("beforeSrc") or "")

    if before_src and shot_src:
        return (
            f'<div class="vis-pair-stack">'
            f'<div class="vis-box is-bad"><button type="button" class="shot-zoom-trigger" data-lightbox-src="{e(before_src)}" data-lightbox-caption="{e(title + " · " + bad_tag)}"><img src="{e(before_src)}" alt="{e(title)}" loading="lazy"></button><span class="vis-tag">{e(bad_tag)}</span></div>'
            f'<div class="vis-box is-good"><button type="button" class="shot-zoom-trigger" data-lightbox-src="{e(shot_src)}" data-lightbox-caption="{e(title + " · " + good_tag)}"><img src="{e(shot_src)}" alt="{e(title)}" loading="lazy"></button><span class="vis-tag">{e(good_tag)}</span></div></div>'
        )
    if shot_src:
        g_lbl = good_tag or bad_tag or "✓ 实机截图对照"
        return (
            f'<div class="vis-box is-good" style="flex:1">'
            f'<button type="button" class="shot-zoom-trigger" style="aspect-ratio:4/3" data-lightbox-src="{e(shot_src)}" data-lightbox-caption="{e(title + " · " + g_lbl)}">'
            f'<img src="{e(shot_src)}" alt="{e(title)}" loading="lazy"></button>'
            f'<span class="vis-tag">{e(g_lbl)}</span></div>'
        )

    if kind == "chart" or any(k in title for k in ("图", "柱", "轴")):
        bad_svg = (
            '<svg class="ui-Chart-svg" viewBox="0 0 160 62" aria-hidden="true">'
            '<path d="M18 6v46h132" fill="none" stroke="#3a3228" stroke-width="2"/>'
            '<path d="M14 14h4M14 28h4M14 42h4M46 52v4M84 52v4M122 52v4" stroke="#3a3228" stroke-width="1.6"/>'
            '<rect x="32" y="24" width="20" height="27" fill="#c99b84"/>'
            '<rect x="70" y="14" width="20" height="37" fill="#b87b61"/>'
            '<rect x="108" y="30" width="20" height="21" fill="#c99b84"/></svg>'
        )
        good_svg = (
            '<svg class="ui-Chart-svg" viewBox="0 0 160 62" aria-hidden="true">'
            '<path d="M14 16h134M14 32h134M14 48h134" stroke="#dfd7c6" stroke-dasharray="3 3" stroke-width="1"/>'
            '<rect x="30" y="22" width="22" height="26" rx="4" fill="#7fa682"/>'
            '<rect x="69" y="11" width="22" height="37" rx="4" fill="#4f825b"/>'
            '<rect x="108" y="27" width="22" height="21" rx="4" fill="#7fa682"/></svg>'
        )
        b_lbl = bad_tag or "× 粗黑实线轴 + 刻度刺"
        g_lbl = good_tag or "✓ 隐藏实线轴 + 圆角柱"
        return (
            f'<div class="vis-pair-stack">'
            f'<div class="vis-box is-bad">{bad_svg}<span class="vis-tag">{e(b_lbl)}</span></div>'
            f'<div class="vis-box is-good">{good_svg}<span class="vis-tag">{e(g_lbl)}</span></div></div>'
        )

    if kind in ("select", "snapshot") or any(k in title for k in ("箭头", "下拉", "选择")):
        bad_txt = str(sc.get("badText") or "超长选项文字内容挤压")
        good_txt = str(sc.get("goodText") or "超长选项文字…")
        bad_ui = (
            '<div class="ui-select-demo bad-select">'
            f'<span class="sel-text">{e(bad_txt)}</span>'
            '<span class="sel-arrows">▾⌄</span></div>'
        )
        good_ui = (
            '<div class="ui-select-demo good-select">'
            f'<span class="sel-text">{e(good_txt)}</span>'
            '<span class="sel-arrows">⌄</span></div>'
        )
        b_lbl = bad_tag or "× 双箭头重叠 · 文字撞箭头"
        g_lbl = good_tag or "✓ 单套箭头 · 最长文字留白"
        return (
            f'<div class="vis-pair-stack">'
            f'<div class="vis-box is-bad">{bad_ui}<span class="vis-tag">{e(b_lbl)}</span></div>'
            f'<div class="vis-box is-good">{good_ui}<span class="vis-tag">{e(g_lbl)}</span></div></div>'
        )

    bad_rows = sc.get("badRows") or [("#01 列表项 A", "状态重置"), ("#02 列表项 B", "焦点丢失")]
    good_rows = sc.get("goodRows") or [("#01 列表项 A", "保留状态"), ("#02 列表项 B", "↩ 归还焦点")]
    bad_ui = '<div class="ui-focus-demo">' + "".join(
        f'<div class="ui-focus-row"><span>{e(r[0])}</span><span>{e(r[1])}</span></div>' for r in bad_rows[:2]
    ) + "</div>"
    good_ui = '<div class="ui-focus-demo">' + "".join(
        f'<div class="ui-focus-row{" is-focused" if i == len(good_rows[:2]) - 1 else ""}"><span>{e(r[0])}</span><span>{e(r[1])}</span></div>'
        for i, r in enumerate(good_rows[:2])
    ) + "</div>"
    b_lbl = bad_tag or "× 状态重置 · 焦点丢失"
    g_lbl = good_tag or "✓ 保留状态 · 焦点归还"
    return (
        f'<div class="vis-pair-stack">'
        f'<div class="vis-box is-bad">{bad_ui}<span class="vis-tag">{e(b_lbl)}</span></div>'
        f'<div class="vis-box is-good">{good_ui}<span class="vis-tag">{e(g_lbl)}</span></div></div>'
    )


def render_structured_diagram(diag: dict[str, object], item: dict[str, object]) -> str:
    dtype = str(diag.get("type", "scenarios"))
    if dtype == "routing":
        before_obj = diag.get("before") if isinstance(diag.get("before"), dict) else {}
        before_state = str(
            diag.get("beforeTitle")
            or diag.get("beforeState")
            or before_obj.get("state")
            or "修改前 · 单一主线"
        )
        before_file = str(diag.get("beforeFile") or before_obj.get("file") or "SKILL.md")
        before_note = str(diag.get("beforeNote") or before_obj.get("note") or "× 改后台也混跑海报流程")
        legacy_html = (
            f'<section class="legacy-domain">{vis_state(before_state)}'
            f'<div class="legacy-file">{artifact_file(before_file)}'
            f'<div class="mixed-pages">{domain_wire("marketing")}{domain_wire("workspace")}</div>'
            f"<span>所有页面共用同一套流程</span></div>"
            f'<div class="wrong-rule">{e(before_note)}</div></section>'
        )
        entry_obj = diag.get("entry") if isinstance(diag.get("entry"), dict) else {}
        after_state = str(diag.get("afterTitle") or diag.get("afterState") or "修改后 · 先定范围，再按页面分流")
        entry_file = str(diag.get("entryFile") or entry_obj.get("file") or "SKILL.md")
        entry_tag = str(diag.get("entryTag") or "① 定范围 → ② 选页面")
        branches = list(diag.get("branches", []))
        wire_cycle = ["marketing", "workspace", "content", "play"]
        nodes_html: list[str] = []
        for idx, br in enumerate(branches):
            w_type = str(br.get("wire") or wire_cycle[idx % len(wire_cycle)])
            badge = f' <small class="new-file-label">{e(br["badge"])}</small>' if br.get("badge") else ""
            main_file = artifact_file(str(br["file"])) if br.get("file") else ""
            sub_files = "".join(artifact_file(str(sf)) for sf in br.get("subFiles", []))
            sub_wrap = f'<div class="workspace-children">{sub_files}</div>' if sub_files else ""
            short_tag = str(br.get("tag") or "")
            tag_span = f"<span>{e(short_tag)}</span>" if short_tag else ""
            nodes_html.append(
                f'<div class="domain-node">{domain_wire(w_type)}'
                f'<strong>{e(br.get("title", ""))}{badge}</strong>'
                f"{main_file}{tag_span}{sub_wrap}</div>"
            )
        mid = (len(nodes_html) + 1) // 2
        col1 = "".join(f'<div class="route-branch">{n}</div>' for n in nodes_html[:mid])
        col2 = "".join(f'<div class="route-branch">{n}</div>' for n in nodes_html[mid:])
        cols_html = f'<div class="route-column">{col1}</div>' + (f'<div class="route-column">{col2}</div>' if col2 else "")
        routes_html = (
            f'<section class="new-domains">{vis_state(after_state, True)}'
            f'<div class="route-entry">{artifact_file(entry_file)}<span>· {e(entry_tag)}</span></div>'
            f'<div class="route-columns">{cols_html}</div></section>'
        )
        return f'<div class="visual-stage"><div class="domain-map">{legacy_html}{vis_arrow("domain-arrow")}{routes_html}</div></div>'

    if dtype == "comparison":
        before_state = str(diag.get("beforeTitle") or diag.get("beforeState") or "修改前 · 控件高低不齐、硬塞装饰图")
        after_state = str(diag.get("afterTitle") or diag.get("afterState") or "修改后 · 同行等高对齐、边界干净统一")
        brand_lbl = str(diag.get("brand") or "系统后台")
        good_heading = str(diag.get("goodHeading") or "业务管理工作台")
        bad_issues = list(diag.get("beforeIssues") or ["× 同行控件高低不齐", "× 色块与粗黑框混用", "× 硬塞无意义微图表"])
        good_stds = list(diag.get("afterStandards") or ["✓ 同行控件等高对齐", "✓ 分段滑块底槽", "✓ 同层边界统一"])
        old_sec = (
            f"<section>{vis_state(before_state)}"
            '<div class="admin-window fake-admin"><aside class="fake-sidebar">'
            f'<div class="fake-brand"><b>◈</b><span>{e(brand_lbl)}</span></div>'
            "<i></i><i></i><i></i></aside>"
            '<div class="fake-body">'
            '<div class="ui-toolbar-demo" style="margin-bottom:8px">'
            '<span class="ui-ctrl" style="height:20px">搜索</span>'
            '<span class="ui-ctrl" style="height:28px">全部状态 ▾⌄</span>'
            '<span class="ui-ctrl" style="height:18px">导出</span></div>'
            '<div class="fake-metrics" style="grid-template-columns:1fr 1fr;gap:6px">'
            '<div class="fake-metric" style="border:1.5px solid #6e5a4f;background:#efe2d5"><span>硬塞趋势</span><strong>〰〰</strong></div>'
            '<div class="fake-metric" style="border:1.5px solid #6e5a4f;background:#efe2d5"><span>凑数卡片</span><strong>〰〰</strong></div></div>'
            '<div class="fake-table" style="margin-top:8px">'
            '<div class="fake-row"><span>列表对象 A</span><span>异常</span><span>128</span></div>'
            '<div class="fake-row"><span>列表对象 B</span><span>正常</span><span>64</span></div></div></div></div>'
            + '<div class="issue-legend">' + "".join(f"<span>{e(x)}</span>" for x in bad_issues[:3]) + "</div></section>"
        )
        rows_data = diag.get("tableRows") or [
            ("核心列表对象 A", "待处理", "1,280"),
            ("次级列表对象 B", "处理中", "860"),
            ("归档列表对象 C", "已完成", "640"),
        ]
        realrows = "".join(
            f'<div class="real-row"><strong>{e(r[0])}</strong>'
            f'<span class="status-tag status-{i}"><i></i>{e(r[1])}</span>'
            f"<code>{e(r[2])}</code></div>"
            for i, r in enumerate(rows_data[:3])
        )
        new_sec = (
            f"<section>{vis_state(after_state, True)}"
            '<div class="admin-window real-admin"><aside class="real-sidebar"><span>◈</span><i></i><i></i><i></i></aside>'
            f'<div class="real-body"><header><strong>{e(good_heading)}</strong>'
            '<div class="ui-seg"><span class="is-active">待处理</span><span>全部</span></div></header>'
            '<div class="ui-toolbar-demo is-equal" style="margin:9px 0">'
            '<span class="ui-ctrl" style="height:24px;flex:1">⌕ 搜索关键词…</span>'
            '<span class="ui-ctrl" style="height:24px">状态 ⌄</span>'
            '<span class="ui-ctrl" style="height:24px;background:#edf3e6;color:#2f5c3e;border-color:#c9dac2">＋ 新建</span></div>'
            '<div class="real-table"><div class="real-table-head"><span>名称</span><span>状态</span><span>数值</span></div>'
            f"{realrows}</div></div></div>"
            + '<div class="workspace-standards">' + "".join(f"<span>{e(x)}</span>" for x in good_stds[:3]) + "</div></section>"
        )
        return f'<div class="visual-stage"><div class="workspace-comparison">{old_sec}{new_sec}</div></div>'

    if dtype == "flow":
        before_state = str(diag.get("beforeTitle") or diag.get("oldState") or "修改前 · 串行多轮冗余步骤")
        after_state = str(diag.get("afterTitle") or diag.get("newState") or "修改后 · 精简并行与按条件收尾")
        thumbs = [
            '<div class="candidate-thumbs"><i></i><i></i><i></i></div>',
            '<div class="score-preview"><b>8.0</b><span>/ 10</span></div>',
            '<div class="comparison-thumbs"><i></i><span>⇄</span><i></i></div>',
            '<div class="trial-preview"><span>冗余</span></div>',
        ]
        steps = list(diag.get("beforeSteps") or diag.get("oldSteps") or [])
        old_nodes = ""
        for i, st in enumerate(steps):
            label = st.get("label", "") if isinstance(st, dict) else str(st)
            removed = (
                bool(st.get("removed"))
                if isinstance(st, dict)
                else any(k in label for k in ("强制", "误报", "重复", "第 2 轮", "×"))
            )
            thumb = thumbs[i % len(thumbs)]
            rem_cls = " is-removed" if removed else ""
            old_nodes += f'<div class="serial-node{rem_cls}">{thumb}<span>{e(label)}</span></div>'
            if i < len(steps) - 1:
                old_nodes += vis_arrow("serial-arrow")
        fork = (
            '<svg class="track-junction" viewBox="0 0 28 150" preserveAspectRatio="none" aria-hidden="true">'
            '<path d="M1 75h10V34h15M11 75v41h15M22 30l4 4-4 4M22 112l4 4-4 4" fill="none" '
            'stroke="currentColor" stroke-width="1.2" vector-effect="non-scaling-stroke"/></svg>'
        )
        merge = (
            '<svg class="track-junction" viewBox="0 0 28 150" preserveAspectRatio="none" aria-hidden="true">'
            '<path d="M1 34h12v82H1m12-41h13m-4-4 4 4-4 4" fill="none" '
            'stroke="currentColor" stroke-width="1.2" vector-effect="non-scaling-stroke"/></svg>'
        )
        start_node = diag.get("startNode") or {"title": "入口执行", "tag": "统一输入"}
        tracks = list(
            diag.get("parallelTracks")
            or diag.get("tracks")
            or [
                {"symbol": "◉", "title": "主链路检查", "tag": "核心规则核对"},
                {"symbol": "↗", "title": "边界检查", "tag": "异常与状态核对"},
            ]
        )
        end_node = diag.get("endNode") or {"title": "汇总输出", "tag": "按条件收尾"}
        t_html = ""
        for idx, tr in enumerate(tracks[:2]):
            sym = tr.get("symbol") or ("◉" if idx == 0 else "↗")
            tr_tag = tr.get("tag") or tr.get("copy") or tr.get("sub") or ""
            t_html += (
                f'<div class="process-node track-node"><span class="track-symbol">{e(sym)}</span>'
                f'<div><strong>{e(tr.get("title", ""))}</strong><span>{e(tr_tag)}</span></div></div>'
            )
        start_tag = start_node.get("tag") or start_node.get("copy") or start_node.get("sub") or ""
        end_tag = end_node.get("tag") or end_node.get("copy") or end_node.get("sub") or ""
        now_html = (
            f'<div class="parallel-flow">'
            f'<div class="process-node maker-node"><div class="page-preview"><i></i><i></i><i></i></div>'
            f'<strong>{e(start_node.get("title", ""))}</strong><span>{e(start_tag)}</span></div>'
            f"{fork}<div class=\"parallel-tracks\">{t_html}</div>{merge}"
            f'<div class="process-node result-node"><div class="review-list"><i></i><i></i><i></i></div>'
            f'<strong>{e(end_node.get("title", ""))}</strong><span>{e(end_tag)}</span></div></div>'
        )
        return (
            f'<div class="visual-stage">{vis_state(before_state)}'
            f'<div class="serial-flow">{old_nodes}</div>'
            f"{vis_state(after_state, True)}{now_html}</div>"
        )

    if dtype == "alignment":
        before_state = str(diag.get("beforeTitle") or diag.get("beforeState") or "修改前 · 只按整张图宽度缩放")
        after_state = str(diag.get("afterTitle") or diag.get("afterState") or "修改后 · 先按共有元素同宽，再裁同一区域")
        old_col = (
            f'<section class="alignment-before">{vis_state(before_state)}'
            f'<div class="shot-pair"><div><span class="shot-caption">当前画面</span>'
            f'<div class="ruler short-ruler">120 px</div>{mini_shot_window("too-small", 20)}</div>'
            f'<div><span class="shot-caption">参考图</span>'
            f'<div class="ruler">240 px</div>{mini_shot_window("", 40)}</div></div>'
            '<div class="mismatch-ruler"><span>120 px</span><b>≠</b><span>240 px</span></div></section>'
        )
        new_col = (
            f'<section class="alignment-after">{vis_state(after_state, True)}'
            '<div class="tool-options"><code>matchWidth: 240</code><code>crop: {x, y, w, h}</code></div>'
            f'<div class="shot-pair aligned-pair"><div><span class="shot-caption">当前画面 <em>2.0×</em></span>'
            f'<div class="ruler">240 px</div>{mini_shot_window("has-crop", 40)}</div>'
            f'<div><span class="shot-caption">参考图</span>'
            f'<div class="ruler">240 px</div>{mini_shot_window("has-crop", 40)}</div></div>'
            '<div class="stitched-caption">1:1 并排裁切</div>'
            f'<div class="stitched-result">{mini_shot_window("crop-output", 40)}{mini_shot_window("crop-output", 40)}</div></section>'
        )
        return f'<div class="visual-stage"><div class="alignment-grid">{old_col}{new_col}</div></div>'

    if dtype == "screenshots":
        mode = str(diag.get("mode", "pair")).lower()
        b_src = str(diag.get("beforeSrc") or "")
        a_src = str(diag.get("afterSrc") or diag.get("src") or "")
        b_title = str(diag.get("beforeTitle") or "修改前")
        a_title = str(diag.get("afterTitle") or "修改后")
        b_tag = str(diag.get("beforeTag") or "")
        a_tag = str(diag.get("afterTag") or "")
        if mode == "slider" and b_src and a_src:
            return (
                f'<div class="visual-stage"><div class="shot-slider-wrap">'
                f'<div class="shot-slider" style="--split:50%">'
                f'<img src="{e(a_src)}" alt="{e(a_title)}" loading="lazy">'
                f'<div class="shot-slider-before"><img src="{e(b_src)}" alt="{e(b_title)}" loading="lazy"></div>'
                f'<span class="shot-slider-badge is-before">{e(b_title)}</span>'
                f'<span class="shot-slider-badge is-after">{e(a_title)}</span>'
                f'<div class="shot-slider-line"></div><div class="shot-slider-knob">↔</div>'
                f'<input type="range" min="5" max="95" value="50" class="shot-slider-input" aria-label="左右拖动对比修改前后截图">'
                f"</div>"
                f'<div class="shot-slider-foot">'
                f'<button type="button" class="shot-zoom-link is-bad" data-shot-zoom="{e(b_src)}" data-shot-caption="{e(b_title)}">{e(b_tag or b_title)} · 🔍 放大</button>'
                f'<button type="button" class="shot-zoom-link is-good" data-shot-zoom="{e(a_src)}" data-shot-caption="{e(a_title)}">{e(a_tag or a_title)} · 🔍 放大</button>'
                f"</div></div></div>"
            )
        if b_src and a_src:
            return (
                f'<div class="visual-stage"><div class="shot-pair-grid">'
                f"{shot_frame_html(b_src, b_title, b_tag, False)}"
                f"{shot_frame_html(a_src, a_title, a_tag, True)}</div></div>"
            )
        shots = list(diag.get("shots") or [])
        cols = "vis-grid-3" if len(shots) >= 3 else "shot-pair-grid"
        frames = "".join(
            shot_frame_html(
                str(s.get("src", "")),
                str(s.get("title", f"截图 {i + 1}")),
                str(s.get("tag", "")),
                bool(s.get("good", True)),
            )
            for i, s in enumerate(shots)
        )
        return f'<div class="visual-stage"><div class="{cols}">{frames}</div></div>'

    if dtype == "schema":
        b_title = str(diag.get("beforeTitle") or "修改前 · 旧结构")
        a_title = str(diag.get("afterTitle") or "修改后 · 新结构")
        b_rows = "".join(
            f'<div class="schema-row is-del"><code>− {e(r)}</code></div>'
            for r in diag.get("beforeRows", [])
        )
        a_rows = "".join(
            f'<div class="schema-row is-add"><code>+ {e(r)}</code></div>'
            for r in diag.get("afterRows", [])
        )
        return (
            f'<div class="visual-stage"><div class="schema-diff">'
            f'<div class="schema-box is-bad"><div class="schema-head">{e(b_title)}</div><div class="schema-rows">{b_rows}</div></div>'
            f'<div class="schema-box is-good"><div class="schema-head">{e(a_title)}</div><div class="schema-rows">{a_rows}</div></div>'
            f"</div></div>"
        )

    if dtype == "diagnostics":
        test_file = str(diag.get("testFile", "tests/test_domain_boundaries.py"))
        rows_html = ""
        for idx, row in enumerate(diag.get("rows", [])):
            passed = bool(row.get("pass", idx > 0))
            b_cls = "is-pass" if passed else "is-fail"
            left_node = str(row.get("left") or row.get("file") or "direction-persuasion.md")
            edge_lbl = str(row.get("edge") or ("误引" if not passed else "核对"))
            right_node = str(row.get("right") or row.get("target") or "workspace-data.md")
            verdict = str(row.get("verdict") or ("✓ 通过" if passed else "× 拦截"))
            rows_html += (
                f'<div class="pipe-row">'
                f'<span class="pipe-node">{artifact_file(left_node)}</span>'
                f'<span class="pipe-edge">{e(edge_lbl)}</span>'
                f'<span class="pipe-node"><code>{e(right_node)}</code></span>'
                f"{vis_arrow()}"
                f'<span class="pipe-badge {b_cls}">{e(verdict)}</span></div>'
            )
        return (
            f'<div class="visual-stage"><div class="test-file-label">{artifact_file(test_file)}</div>'
            f'<div class="pipe-board">{rows_html}</div></div>'
        )

    # Default: clean visual specimen cards (ZERO prose paragraphs inside cards)
    letters = "ABCDEF"
    cards = ""
    scenario_list = list(diag.get("scenarios") or diag.get("cards") or [])
    for idx, sc in enumerate(scenario_list):
        letter = letters[idx % len(letters)]
        title = str(sc.get("title", f"图示 {letter}"))
        cards += (
            f'<section class="vis-card">'
            f'<div class="vis-card-head"><span>{letter}</span>{e(title)}</div>'
            f"{specimen_pair_html(sc, idx)}</section>"
        )
    return f'<div class="visual-stage"><div class="vis-grid-3">{cards}</div></div>'


def render_report_body(data: dict[str, object], spec: dict[str, object]) -> str:
    files: dict[str, dict[str, object]] = {str(f["id"]): f for f in data.get("files", [])}
    spec_items: list[dict[str, object]] = list(spec.get("items", []))

    all_reported_ids = {fid for item in spec_items for fid in item.get("fileIds", [])}
    missing = set(files.keys()) - all_reported_ids
    if missing:
        raise ValueError(f"Unreported files in diff-data.json not covered by report-spec.json: {sorted(missing)}")

    targets: list[dict[str, object]] = []
    templates: list[str] = []
    serial = 0
    seen_files: set[str] = set()

    def diff_card(
        n: int,
        f: dict[str, object],
        role: str | None = None,
        before: list[dict[str, object]] | None = None,
        after: list[dict[str, object]] | None = None,
        variant: str | None = None,
        point_idx: int | None = None,
        point_title: str | None = None,
        drawer_role: str | None = None,
    ) -> str:
        nonlocal serial
        serial += 1
        dom_id = f"diff-{n}-{serial}"
        module_name = str(spec_items[n - 1].get("module", f"事项 {n}"))
        context = f"§ {n:02d} {module_name}"
        context += f" · 要点 {point_idx}：{point_title}" if point_idx else " · 关联文件"
        targets.append(
            {
                "requirement": n,
                "fileId": f["id"],
                "path": f["path"],
                "id": dom_id,
                "context": context,
                "role": drawer_role or role or "",
            }
        )
        first_occurrence = str(f["id"]) not in seen_files
        seen_files.add(str(f["id"]))
        chunks = f.get("chunks", [])
        if (before is None or (len(chunks) == 1 and first_occurrence)) and chunks:
            before = changed_rows(chunks[0], "before")
            after = changed_rows(chunks[0], "after")
        before = before or []
        after = after or []
        rem = remaining_chunks(f, before, after) if len(chunks) > 1 else []
        variant_html = f'<span class="file-variant">{e(variant)}</span>' if variant else ""
        content = comparison_html(before, after, f)
        if rem:
            content += (
                f'<details class="complete-diff"><summary><span>查看该文件其余修改（共 {len(rem)} 处）</span>'
                f'{CHEVRON_SVG}</summary><div class="fold-content" data-fold-content>'
                f'<div class="complete-body">{full_diff_html(f, rem)}</div></div></details>'
            )
        templates.append(f'<template id="source-{dom_id}">{content}</template>')
        return (
            f'<div class="diff-card" id="{dom_id}" tabindex="-1" data-file-id="{e(f["id"])}" data-requirement="{n}">'
            f'<button type="button" class="diff-file" aria-haspopup="dialog" aria-controls="diff-drawer-panel" aria-expanded="false" title="{e(f["path"])}">'
            f'<span class="diff-summary-copy"><span class="file-identity">{file_icon(str(f["path"]))}'
            f"<strong>{e(f['path'])}</strong>{variant_html}</span></span>"
            f'<span class="diff-controls">{counts_html(f)}</span></button></div>'
        )

    counted_files = [f for f in files.values() if f.get("scope") != "history"]
    total_add = sum(int(f["add"]) for f in counted_files)
    total_delete = sum(int(f["delete"]) for f in counted_files)
    ranges = data.get("ranges", {})
    range_tokens: list[str] = []
    for r_info in ranges.values():
        if not range_tokens:
            range_tokens.append(str(r_info.get("from", "")))
        range_tokens.append(str(r_info.get("to", "")))
    range_chain = " → ".join(dict.fromkeys(t for t in range_tokens if t)) or str(data.get("branch", "HEAD"))

    eyebrow = str(spec.get("eyebrow") or f'{data.get("repoName", "repo")} / 改动汇报')
    title = str(spec.get("title") or f"这次修改了哪 {len(spec_items)} 件事")
    summary = str(spec.get("summary") or "")

    # Compute core files (referenced directly in points[].diffs) vs peripheral sync files
    core_fids: list[str] = []
    for item in spec_items:
        for pt in item.get("points", []):
            if isinstance(pt, dict):
                for d in pt.get("diffs", []):
                    fid = str(d.get("file", ""))
                    if fid in files and fid not in core_fids:
                        core_fids.append(fid)
    if not core_fids:
        core_fids = [str(fid) for item in spec_items for fid in item.get("fileIds", [])[:2] if str(fid) in files]
    core_paths = {str(files[fid]["path"]) for fid in core_fids}
    all_paths = {str(f["path"]) for f in files.values()}
    sync_count = max(0, len(all_paths - core_paths))

    metadata = (
        f'<div class="header-controls">'
        f'<div class="report-meta"><span>{data["uniquePaths"]} 个文件 '
        f"<b>+{total_add}</b> <i>−{total_delete}</i></span>"
        f'<span>🎯 {len(core_fids)} 核心 · 📎 {sync_count} 外围</span>'
        f"<code>{e(range_chain)}</code></div></div>"
    )

    intro = (
        f'<header class="intro paper-card"><div class="eyebrow">{e(eyebrow)}</div>'
        f'<div class="title-row"><h1>{e(title)}</h1>{metadata}</div>'
        f"<p>{e(summary)}</p>"
        f'<nav class="overview-nav" aria-label="事项速览">'
    )
    for n, item in enumerate(spec_items, 1):
        nav_title = str(item.get("module") or item.get("navLabel") or f"事项 {n}")
        item_fids = [str(fid) for fid in item.get("fileIds", [])]
        intro += (
            f'<a href="#requirement-{n}" data-requirement-link="{n}">'
            f'<span class="nav-number">{n}</span>'
            f'<span class="nav-label">{e(nav_title)}</span>'
            f'<span class="nav-count">{len(item_fids)} 文件</span>'
            f'<span class="nav-arrow" aria-hidden="true">↘</span></a>'
        )
    intro += "</nav></header>"

    sticky = '<div class="sticky-nav-host" aria-hidden="true" inert><nav class="sticky-chapter-nav" aria-label="章节快速导航">'
    for n, item in enumerate(spec_items, 1):
        nav_label = str(item.get("navLabel") or item.get("module") or f"事项 {n}")
        sticky += f'<a href="#requirement-{n}" data-requirement-link="{n}"><span>§ {n:02d}</span>{e(nav_label)}</a>'
    chapters_html = ""

    for n, item in enumerate(spec_items, 1):
        item_file_ids = [str(fid) for fid in item.get("fileIds", [])]
        if isinstance(item.get("diagram"), dict):
            diag_html = render_structured_diagram(item["diagram"], item)
        elif item.get("diagramHtml"):
            diag_html = normalize_diagram_html(str(item["diagramHtml"]))
        else:
            diag_html = default_diagram_html(item)
        overview_text = str(item.get("overview") or item.get("problem") or "").strip()
        overview_html = f'<p class="chapter-overview">{e(overview_text)}</p>' if overview_text else ""
        hero_cls = " is-hero" if (len(spec_items) > 1 and len(spec_items) % 2 == 1 and n == 1) else ""
        used: set[str] = set()
        points = item.get("points", [])
        inline_diffs = item.get("inlineDiffs", [])
        points_html = ""
        for j, pt in enumerate(points, 1):
            if isinstance(pt, list):
                pt_title = str(pt[0]) if pt else ""
                pt_copy = str(pt[1]) if len(pt) > 1 else ""
                diffs = inline_diffs[j - 1] if j - 1 < len(inline_diffs) else []
            else:
                pt_title = str(pt.get("title", ""))
                pt_copy = str(pt.get("copy", ""))
                diffs = pt.get("diffs", [])
            points_html += (
                f'<section class="change-point" id="change-{n}-{j}">'
                f"<h3><span>{j}</span>{e(pt_title)}</h3>"
                f'<div class="point-pills">'
            )
            for d in diffs:
                fid = str(d["file"])
                if fid not in files:
                    raise ValueError(f"Unknown fileId '{fid}' in item {n}, point {j}")
                if fid not in item_file_ids:
                    raise ValueError(f"fileId '{fid}' in item {n}, point {j} is not listed in item.fileIds")
                f = files[fid]
                before_rows = select_rows(f, "before", d.get("before"))
                after_rows = select_rows(f, "after", d.get("after"))
                raw_role = str(d.get("role", "")).strip() or pt_copy or None
                points_html += diff_card(
                    n,
                    f,
                    role=None,
                    before=before_rows,
                    after=after_rows,
                    point_idx=j,
                    point_title=pt_title,
                    drawer_role=raw_role,
                )
                used.add(fid)
            points_html += "</div></section>"

        if not points_html and item_file_ids:
            points_html += f'<section class="change-point" id="change-{n}-1"><div class="point-pills">'
            for fid in item_file_ids[:2]:
                if fid in files:
                    points_html += diff_card(n, files[fid])
                    used.add(fid)
            points_html += "</div></section>"

        chapters_html += (
            f'<section class="requirement paper-card{hero_cls}" id="requirement-{n}" data-requirement="{n}">'
            f'<header class="section-header"><div class="chapter-topline">'
            f'<span class="section-tag">§ {n:02d}</span>'
            f'<span class="module-badge">{e(item.get("module", ""))}</span></div>'
            f'<h2>{e(item.get("title", ""))}</h2>{overview_html}</header>'
            f'<figure class="diagram">{diag_html}</figure>'
            f'<div class="changes blast-funnel">'
            f'<div class="changes-head"><span class="blast-badge is-core">🎯 核心必看 ({len(used)})</span></div>'
            f"{points_html}"
        )

        extra = [files[fid] for fid in item_file_ids if fid not in used]
        if extra:
            count = len({str(f["path"]) for f in extra})
            names = "、".join(list(dict.fromkeys(str(f["name"]) for f in extra))[:2])
            chapters_html += (
                f'<details class="related-files" id="related-{n}">'
                f'<summary><span class="related-summary-left"><span class="blast-badge is-sync">📎 外围同步 ({count})</span>'
                f'<span class="sync-names">{e(names)} 等</span></span>{CHEVRON_SVG}</summary>'
                f'<div class="fold-content" data-fold-content><div class="related-file-list">'
            )
            repeated = Counter(str(f["path"]) for f in extra)
            file_variants = spec.get("fileVariants", {})
            for f in extra:
                fid = str(f["id"])
                variant = (
                    str(file_variants.get(fid) or ranges.get(str(f["scope"]), {}).get("label", ""))
                    if repeated[str(f["path"])] > 1
                    else None
                )
                chapters_html += diff_card(n, f, variant=variant)
            chapters_html += "</div></div></details>"
        chapters_html += "</div></section>"

    body = sticky + "</nav></div>" + intro + f'<div class="bento-deck" id="bento-deck">{chapters_html}</div>'

    paths: dict[str, dict[str, object]] = {}
    for f in files.values():
        p_str = str(f["path"])
        entry = paths.setdefault(p_str, {"path": p_str, "requirements": [], "recordIds": []})
        entry["recordIds"].append(f["id"])

    for n, item in enumerate(spec_items, 1):
        for fid in item.get("fileIds", []):
            p_str = str(files[str(fid)]["path"])
            reqs = paths[p_str]["requirements"]
            if n not in reqs:
                reqs.append(n)

    tree: dict[str, object] = {"files": [], "folders": {}}
    for p in paths.values():
        node = tree
        for folder in PurePosixPath(str(p["path"])).parts[:-1]:
            node = node["folders"].setdefault(folder, {"files": [], "folders": {}})
        node["files"].append(p)

    def tree_html(node: dict[str, object], prefix: str = "") -> str:
        result = ""
        priority = {"README.md": 0, "README.en.md": 1, "SKILL.md": 2}
        sorted_files = sorted(
            node["files"],
            key=lambda p: (priority.get(PurePosixPath(str(p["path"])).name, 3), str(p["path"])),
        )
        for p in sorted_files:
            f = files[str(p["recordIds"][0])]
            result += (
                f'<button class="tree-file" data-path="{e(p["path"])}" title="{e(p["path"])}">'
                f'<span class="tree-file-identity">{file_icon(str(p["path"]))}'
                f'<span class="tree-file-name">{e(f["name"])}</span></span>'
                f"{counts_html(f)}</button>"
            )
        for name, child in sorted(node["folders"].items()):
            folder_path = f"{prefix}{name}/"
            result += (
                f'<details class="tree-folder" data-folder="{e(folder_path)}" open>'
                f"<summary>{CHEVRON_SVG}{FOLDER_ICON_SVG}<span>{e(name)}/</span></summary>"
                f'<div class="fold-content" data-fold-content><div class="tree-children">'
                f"{tree_html(child, folder_path)}</div></div></details>"
            )
        return result

    repo_label = str(data.get("repoName") or "repository")
    sidebar = (
        '<aside class="file-sidebar" id="file-sidebar" aria-label="改动文件树">'
        '<header class="tree-header"><div class="tree-heading">'
        f'<h2>改动文件树</h2><span class="repository-label">{e(repo_label)}</span></div>'
        '<button type="button" class="tree-toggle-btn" data-tree-toggle title="收起改动文件树" aria-label="收起改动文件树">收起 ⇥</button>'
        '</header><div class="tree-scroll" id="tree-scroll">'
        f"{tree_html(tree)}</div></aside>"
        f'<button type="button" class="tree-reopen-btn" data-tree-toggle title="展开改动文件树" aria-label="展开改动文件树">⇤ 文件树 ({data["uniquePaths"]})</button>'
    )

    drawer = (
        '<div class="diff-drawer-root" hidden><div class="diff-drawer-backdrop" aria-hidden="true"></div>\n'
        '<aside class="diff-drawer" id="diff-drawer-panel" role="dialog" aria-label="原文对照" tabindex="-1">\n'
        '<header class="drawer-header"><div class="drawer-toolbar"><span class="drawer-label">原文对照</span>'
        '<div class="drawer-actions">\n'
        '<button type="button" data-drawer-prev aria-label="查看上一处修改">← 上一处</button>'
        '<button type="button" data-drawer-next aria-label="查看下一处修改">下一处 →</button>\n'
        '<button type="button" class="drawer-close" data-drawer-close aria-label="关闭原文对照">'
        '<svg viewBox="0 0 20 20" aria-hidden="true"><path d="m5 5 10 10M15 5 5 15" fill="none" '
        'stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/></svg></button></div></div>\n'
        '<div class="drawer-information"><p class="drawer-context"></p>'
        '<div class="drawer-file-heading"><span class="drawer-file-identity"></span>'
        '<span class="drawer-counts"></span></div><p class="drawer-role" hidden></p></div></header>\n'
        '<div class="drawer-body"></div></aside></div>'
    )

    lightbox = (
        '<div class="shot-lightbox" id="shot-lightbox" hidden role="dialog" aria-label="截图预览">'
        '<img src="data:," alt="">'
        '<div class="shot-lightbox-bar"><span class="shot-lightbox-caption"></span>'
        '<button type="button" class="shot-lightbox-close">关闭 (Esc)</button></div></div>'
    )

    data["reading"] = {"treeFiles": list(paths.values()), "targets": targets}
    footer_label = str(data.get("branch") or repo_label)
    return (
        '<div class="bg-grid" aria-hidden="true"></div>'
        '<div class="bg-fade" aria-hidden="true"></div>'
        '<div class="report-layout"><main class="report-main">'
        + body
        + f'<footer class="page-footer"><span>{e(footer_label)}</span><a href="#top">回到顶部 ↑</a></footer>'
        + "</main>"
        + sidebar
        + "</div>"
        + drawer
        + lightbox
        + "".join(templates)
    )


def render_html_document(data: dict[str, object], spec: dict[str, object]) -> str:
    body_html = render_report_body(data, spec)
    css_text = (ASSETS_DIR / "report.css").read_text(encoding="utf-8")
    js_text = (ASSETS_DIR / "report.js").read_text(encoding="utf-8")
    serialized_data = json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("<", "\\u003c")
    page_title = f'{spec.get("title", "改动汇报")} · {data.get("repoName", "oil-diff")} 改动汇报'
    return (
        "<!doctype html>\n"
        '<html lang="zh-CN">\n'
        "<head>\n"
        '<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        '<meta name="color-scheme" content="light">\n'
        f"<title>{e(page_title)}</title>\n"
        '<link rel="icon" href="data:,">\n'
        "<style>\n"
        f"{css_text}\n"
        "</style>\n"
        "</head>\n"
        '<body id="top">\n'
        f"{body_html}\n"
        f'<script id="report-data" type="application/json">{serialized_data}</script>\n'
        "<script>\n"
        f"{js_text}\n"
        "</script>\n"
        "</body>\n"
        "</html>\n"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Render standalone HTML change report.")
    parser.add_argument(
        "--report-dir",
        default=None,
        help="Path to .oil-diff directory (auto-resolves assets/diff-data.json, assets/report-spec.json, and index.html).",
    )
    parser.add_argument("--data", default=None, help="Path to diff-data.json.")
    parser.add_argument("--spec", default=None, help="Path to report-spec.json.")
    parser.add_argument("--output", default=None, help="Output HTML file path (e.g. .oil-diff/index.html).")
    args = parser.parse_args()

    if args.report_dir:
        rdir = Path(args.report_dir).resolve()
        data_path = Path(args.data).resolve() if args.data else (rdir / "assets" / "diff-data.json")
        spec_path = Path(args.spec).resolve() if args.spec else (rdir / "assets" / "report-spec.json")
        out_path = Path(args.output).resolve() if args.output else (rdir / "index.html")
    else:
        if not (args.data and args.spec and args.output):
            parser.error("Provide --report-dir or all of --data, --spec, and --output.")
        data_path = Path(args.data).resolve()
        spec_path = Path(args.spec).resolve()
        out_path = Path(args.output).resolve()

    data = json.loads(data_path.read_text(encoding="utf-8"))
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    html_doc = render_html_document(data, spec)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html_doc, encoding="utf-8")

    raw_bytes = html_doc.encode("utf-8")
    print(
        json.dumps(
            {
                "output": str(out_path),
                "bytes": len(raw_bytes),
                "sha256": hashlib.sha256(raw_bytes).hexdigest(),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
