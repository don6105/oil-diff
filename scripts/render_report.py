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
    cards = ""
    for idx, pt in enumerate(points, 1):
        pt_title = pt[0] if isinstance(pt, list) else pt.get("title", "")
        pt_copy = pt[1] if isinstance(pt, list) else pt.get("copy", "")
        cards += (
            f'<div class="scenario">'
            f'<h4><span>{idx:02d}</span>{e(pt_title)}</h4>'
            f'<p class="scenario-new">{e(pt_copy)}</p>'
            f"</div>"
        )
    return f'<div class="visual-stage"><div class="scenario-grid">{cards}</div></div>'


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


def render_structured_diagram(diag: dict[str, object], item: dict[str, object]) -> str:
    dtype = str(diag.get("type", "scenarios"))
    if dtype == "routing":
        before_obj = diag.get("before") if isinstance(diag.get("before"), dict) else {}
        before_state = str(
            diag.get("beforeTitle")
            or diag.get("beforeState")
            or before_obj.get("state")
            or "修改前 · 一份文件混写"
        )
        before_file = str(diag.get("beforeFile") or before_obj.get("file") or "SKILL.md")
        before_copy = str(
            diag.get("beforeCopy")
            or before_obj.get("desc")
            or before_obj.get("copy")
            or "多类页面或模块共用同一套说明"
        )
        before_note = str(diag.get("beforeNote") or before_obj.get("note") or "↳ 容易误触不相关的规则")
        legacy_html = (
            f'<section class="legacy-domain">{vis_state(before_state)}'
            f'<div class="legacy-file">{artifact_file(before_file)}'
            f'<div class="mixed-pages">{domain_wire("marketing")}{domain_wire("workspace")}</div>'
            f"<span>{e(before_copy)}</span></div>"
            f'<div class="wrong-rule">{e(before_note)}</div></section>'
        )
        entry_obj = diag.get("entry") if isinstance(diag.get("entry"), dict) else {}
        after_state = str(diag.get("afterTitle") or diag.get("afterState") or "修改后 · 总入口按领域分流")
        entry_file = str(diag.get("entryFile") or entry_obj.get("file") or "SKILL.md")
        entry_desc = str(diag.get("entryCopy") or entry_obj.get("desc") or entry_obj.get("copy") or "")
        entry_desc_html = f"<span>{e(entry_desc)}</span>" if entry_desc else ""
        branches = list(diag.get("branches", []))
        wire_cycle = ["marketing", "workspace", "content", "play"]
        nodes_html: list[str] = []
        for idx, br in enumerate(branches):
            w_type = str(br.get("wire") or wire_cycle[idx % len(wire_cycle)])
            badge = f' <small class="new-file-label">{e(br["badge"])}</small>' if br.get("badge") else ""
            main_file = artifact_file(str(br["file"])) if br.get("file") else ""
            sub_files = "".join(artifact_file(str(sf)) for sf in br.get("subFiles", []))
            sub_wrap = f'<div class="workspace-children">{sub_files}</div>' if sub_files else ""
            br_copy = br.get("copy") or br.get("desc") or ""
            copy_span = f"<span>{e(br_copy)}</span>" if br_copy else ""
            deleted = f'<del>{e(br["deleted"])}</del>' if br.get("deleted") else ""
            nodes_html.append(
                f'<div class="domain-node">{domain_wire(w_type)}'
                f'<strong>{e(br.get("title", ""))}{badge}</strong>'
                f"{main_file}{copy_span}{sub_wrap}{deleted}</div>"
            )
        mid = (len(nodes_html) + 1) // 2
        col1 = "".join(f'<div class="route-branch">{n}</div>' for n in nodes_html[:mid])
        col2 = "".join(f'<div class="route-branch">{n}</div>' for n in nodes_html[mid:])
        cols_html = f'<div class="route-column">{col1}</div>' + (f'<div class="route-column">{col2}</div>' if col2 else "")
        routes_html = (
            f'<section class="new-domains">{vis_state(after_state, True)}'
            f'<div class="route-entry">{artifact_file(entry_file)}{entry_desc_html}</div>'
            f'<div class="route-columns">{cols_html}</div></section>'
        )
        return f'<div class="visual-stage"><div class="domain-map">{legacy_html}{vis_arrow("domain-arrow")}{routes_html}</div></div>'

    if dtype == "comparison":
        before_state = str(diag.get("beforeTitle") or diag.get("beforeState") or "修改前 · 容易做成千篇一律的模板")
        after_state = str(diag.get("afterTitle") or diag.get("afterState") or "修改后 · 结构干净、组件与数字对齐")
        problems = list(
            diag.get("beforeItems")
            or diag.get("beforeCallouts")
            or diag.get("problems")
            or ["配色杂乱", "多余小图", "边框混用"]
        )
        standards = list(
            diag.get("afterItems")
            or diag.get("afterCallouts")
            or diag.get("standards")
            or ["成熟组件", "同行等高", "边界统一"]
        )
        metrics = "".join('<div class="fake-metric"><span>指标</span><strong>128</strong></div>' for _ in range(4))
        badrows = "".join('<div class="fake-row"><span>#a8f921</span><span>模块 A</span><span>128</span></div>' for _ in range(4))
        legend = "".join(
            f'<span><b>{i}</b>{e(str(text).lstrip("×✓ "))}</span>'
            for i, text in enumerate(problems[:5], 1)
        )
        old_sec = (
            f"<section>{vis_state(before_state)}"
            '<div class="admin-window fake-admin"><aside class="fake-sidebar">'
            '<div class="fake-brand"><b>A</b><span>TEMPLATE</span><mark class="issue-pin pin-1">1</mark></div>'
            "<i></i><i></i><i></i></aside>"
            f'<div class="fake-body"><div class="fake-metrics">{metrics}<mark class="issue-pin pin-2">2</mark></div>'
            '<select disabled aria-label="旧筛选框"><option>全部状态</option></select>'
            f'<div class="fake-table">{badrows}<mark class="issue-pin pin-3">3</mark></div></div></div>'
            f'<div class="issue-legend">{legend}</div></section>'
        )
        rows_data = diag.get("tableRows") or [
            ("核心工作台", "运行中", "12,480.00"),
            ("门店补货单", "待审核", "8,320.00"),
            ("权限与设置", "已对齐", "960.00"),
        ]
        realrows = "".join(
            f'<div class="real-row"><strong>{e(r[0])}</strong>'
            f'<span class="status-tag status-{i}"><i></i>{e(r[1])}</span>'
            f"<code>{e(r[2])}</code></div>"
            for i, r in enumerate(rows_data[:3])
        )
        std_spans = "".join(f"<span>{e(s)}</span>" for s in standards)
        foot_note = f'<div class="deleted-standard">{e(diag["footerNote"])}</div>' if diag.get("footerNote") else ""
        new_sec = (
            f"<section>{vis_state(after_state, True)}"
            '<div class="admin-window real-admin"><aside class="real-sidebar"><span>◈</span><i></i><i></i><i></i></aside>'
            '<div class="real-body"><header><strong>工作区视图</strong><span class="new-project">＋ 新建</span></header>'
            '<div class="real-toolbar"><span>⌕ 搜索记录…</span><span>状态筛选 ⌄</span></div>'
            '<div class="real-table"><div class="real-table-head"><span>对象</span><span>状态</span><span>数值</span></div>'
            f"{realrows}</div></div></div>"
            f'<div class="workspace-standards">{std_spans}</div>{foot_note}</section>'
        )
        return f'<div class="visual-stage"><div class="workspace-comparison">{old_sec}{new_sec}</div></div>'

    if dtype == "flow":
        before_state = str(diag.get("beforeTitle") or diag.get("oldState") or "修改前 · 串行排队逐项检查")
        after_state = str(diag.get("afterTitle") or diag.get("newState") or "修改后 · 合并重复环节并行的流程")
        thumbs = [
            '<div class="candidate-thumbs"><i></i><i></i><i></i></div>',
            '<div class="sketch-thumb"><i></i><i></i><i></i><i></i></div>',
            '<div class="comparison-thumbs"><i></i><span>⇄</span><i></i></div>',
            '<div class="score-preview"><b>8.5</b><span>/ 10</span></div>',
            '<div class="trial-preview"><span>检查</span></div>',
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
            note = str(st.get("note", "")) if isinstance(st, dict) else ("已精简" if removed else "")
            thumb = thumbs[i % len(thumbs)]
            rem_cls = " is-removed" if removed else ""
            note_html = f"<small>{e(note)}</small>" if note else ""
            old_nodes += f'<div class="serial-node{rem_cls}">{thumb}<span>{e(label)}</span>{note_html}</div>'
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
        start_node = diag.get("startNode") or {"title": "首轮生成与检查", "copy": "直接按领域规范实现"}
        tracks = list(
            diag.get("parallelTracks")
            or diag.get("tracks")
            or [
                {"symbol": "◉", "title": "工作区专项评审", "copy": "核对 11 项结果与参考图对齐"},
                {"symbol": "↗", "title": "shoot.mjs 截图拼图", "copy": "同比例缩放裁切，免钥匙串弹窗"},
            ]
        )
        end_node = diag.get("endNode") or {"title": "达标即停交付", "copy": "首轮 8 分无硬伤微调即停"}
        t_html = ""
        for idx, tr in enumerate(tracks[:2]):
            sym = tr.get("symbol") or ("◉" if idx == 0 else "↗")
            tr_copy = tr.get("copy") or tr.get("sub") or ""
            t_html += (
                f'<div class="process-node track-node"><span class="track-symbol">{e(sym)}</span>'
                f'<div><strong>{e(tr.get("title", ""))}</strong><span>{e(tr_copy)}</span></div></div>'
            )
        start_copy = start_node.get("copy") or start_node.get("sub") or ""
        end_copy = end_node.get("copy") or end_node.get("sub") or ""
        now_html = (
            f'<div class="parallel-flow">'
            f'<div class="process-node maker-node"><div class="page-preview"><i></i><i></i><i></i></div>'
            f'<strong>{e(start_node.get("title", ""))}</strong><span>{e(start_copy)}</span></div>'
            f"{fork}<div class=\"parallel-tracks\">{t_html}</div>{merge}"
            f'<div class="process-node result-node"><div class="review-list"><i></i><i></i><i></i></div>'
            f'<strong>{e(end_node.get("title", ""))}</strong><span>{e(end_copy)}</span></div></div>'
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
            '<div class="mismatch-ruler"><span>120 px</span><b>≠</b><span>240 px</span>'
            "<small>共有侧栏与文字比例不一致</small></div></section>"
        )
        new_col = (
            f'<section class="alignment-after">{vis_state(after_state, True)}'
            '<div class="tool-options"><code>matchWidth: 240</code><code>crop: {x, y, w, h}</code></div>'
            f'<div class="shot-pair aligned-pair"><div><span class="shot-caption">当前画面 <em>放大 2.0×</em></span>'
            f'<div class="ruler">240 px</div>{mini_shot_window("has-crop", 40)}</div>'
            f'<div><span class="shot-caption">参考图</span>'
            f'<div class="ruler">240 px</div>{mini_shot_window("has-crop", 40)}</div></div>'
            '<div class="stitched-caption">同坐标裁切 · 1:1 并排对比</div>'
            f'<div class="stitched-result">{mini_shot_window("crop-output", 40)}{mini_shot_window("crop-output", 40)}</div></section>'
        )
        return f'<div class="visual-stage"><div class="alignment-grid">{old_col}{new_col}</div></div>'

    if dtype == "diagnostics":
        test_file = str(diag.get("testFile", "tests/test_domain_boundaries.py"))
        rows_html = ""
        for idx, row in enumerate(diag.get("rows", [])):
            passed = bool(row.get("pass", idx > 0))
            v_cls = "verdict-pass" if passed else "verdict-fail"
            badge = str(row.get("badge") or ("✓ PASS" if passed else "× FAIL"))
            raw_code = str(row.get("code", ""))
            title = str(row.get("title") or raw_code or f"检查项 {idx + 1}")
            verdict = str(row.get("verdict", "")).lstrip("×✓ ")
            sample_file = str(row.get("file") or (raw_code.split()[0] if raw_code else "SKILL.md"))
            detail = str(row.get("detail") or row.get("input") or row.get("desc") or "")
            if idx % 3 == 0:
                box = f'<div class="reference-editor">{artifact_file(sample_file)}<code class="invalid-reference">↳ {e(detail)}</code></div>'
            elif idx % 3 == 1:
                box = (
                    f'<div class="route-check">{artifact_file(sample_file)}{vis_arrow()}'
                    '<span class="four-entries"><i></i><i></i><i></i><i></i><span>领域入口</span></span>'
                    f'{vis_arrow()}<span class="rule-files">{e(detail)}</span></div>'
                )
            else:
                box = f'<div class="heading-check"><code>{e(sample_file)}</code><span>核对规则：<code>{e(detail)}</code></span></div>'
            rows_html += (
                f'<div class="diagnostic-row"><div class="diagnostic-input"><h4>{e(title)}</h4>{box}</div>'
                f'{vis_arrow()}<div class="test-verdict {v_cls}"><span>{e(badge)}</span>'
                f"<strong>{e(verdict)}</strong></div></div>"
            )
        return (
            f'<div class="visual-stage"><div class="test-file-label">{artifact_file(test_file)}</div>'
            f'<div class="diagnostic-board">{rows_html}</div></div>'
        )

    # Default: scenarios with miniature visual specimens
    frames = ""
    for i, (t_lbl, s_lbl) in enumerate([("0 ms", "收起"), ("120 ms", "过渡中"), ("240 ms", "完成 ✓")]):
        frames += (
            f'<div class="menu-frame"><div class="menu-screen"><span class="menu-trigger">选项 ⌄</span>'
            f'<div class="menu-popup phase-{i}"><i></i><i></i><i></i></div></div>'
            f"<code>{t_lbl}</code><span>{s_lbl}</span></div>"
        )
        if i < 2:
            frames += vis_arrow("frame-arrow")
    shots = "".join(
        f'<div class="snapshot-tile {"changed-tile" if i == 1 else "reused-tile"}"><i></i><i></i>'
        f'<span>{"重点核对" if i == 1 else "✓ 保持"}</span></div>'
        for i in range(4)
    )
    runs = (
        '<div class="run-history"><div><span>修改前</span>'
        '<code class="old-run">× 轴线繁杂</code><code class="old-run">× 双箭头重叠</code></div>'
        '<div><span>修改后</span><code class="new-run">✓ 圆角去轴线</code>'
        '<span class="run-done">✓ 单箭头留白</span></div></div>'
    )
    specimens = [runs, f'<div class="snapshot-grid">{shots}</div>', f'<div class="menu-filmstrip">{frames}</div>']
    letters = "ABCDEF"
    cards = ""
    scenario_list = list(diag.get("scenarios") or diag.get("cards") or [])
    for idx, sc in enumerate(scenario_list):
        letter = letters[idx % len(letters)]
        title = str(sc.get("title", f"场景 {letter}"))
        spec_html = specimens[idx % len(specimens)]
        before_txt = str(sc.get("before") or sc.get("old") or "")
        after_txt = str(sc.get("after") or sc.get("new") or "")
        cards += (
            f'<section class="scenario"><h4><span>{letter}</span>{e(title)}</h4>'
            f'<p class="scenario-old">{e(before_txt)}</p>'
            f"{spec_html}"
            f'<p class="scenario-new">{e(after_txt)}</p></section>'
        )
    return f'<div class="visual-stage"><div class="scenario-grid">{cards}</div></div>'


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
        role_html = f'<span class="file-explanation">{e(role)}</span>' if role else ""
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
            f'<button type="button" class="diff-file" aria-haspopup="dialog" aria-controls="diff-drawer-panel" aria-expanded="false">'
            f'<span class="diff-summary-copy"><span class="file-identity">{file_icon(str(f["path"]))}'
            f"<strong>{e(f['path'])}</strong>{variant_html}</span>{role_html}</span>"
            f'<span class="diff-controls">{counts_html(f)}{CHEVRON_SVG}</span></button></div>'
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

    metadata = (
        f'<div class="report-meta"><span>{data["uniquePaths"]} 个文件 '
        f"<b>+{total_add}</b> <i>−{total_delete}</i></span>"
        f"<code>{e(range_chain)}</code></div>"
    )
    intro = (
        f'<header class="intro paper-card"><div class="eyebrow">{e(eyebrow)}</div>'
        f'<div class="title-row"><h1>{e(title)}</h1>{metadata}</div>'
        f"<p>{e(summary)}</p>"
        f'<nav class="overview-nav" aria-label="事项速览">'
    )
    for n, item in enumerate(spec_items, 1):
        intro += (
            f'<a href="#requirement-{n}" data-requirement-link="{n}">'
            f'<span class="nav-number">{n}</span>'
            f'<span class="overview-copy"><span class="module-badge">{e(item.get("module", ""))}</span>'
            f'<span>{e(item.get("overview", item.get("title", "")))}</span></span>'
            f'<span class="nav-arrow" aria-hidden="true">↘</span></a>'
        )
    intro += "</nav></header>"

    sticky = '<div class="sticky-nav-host" aria-hidden="true" inert><nav class="sticky-chapter-nav" aria-label="章节快速导航">'
    for n, item in enumerate(spec_items, 1):
        nav_label = str(item.get("navLabel") or item.get("module") or f"事项 {n}")
        sticky += f'<a href="#requirement-{n}" data-requirement-link="{n}"><span>§ {n:02d}</span>{e(nav_label)}</a>'
    body = sticky + "</nav></div>" + intro

    for n, item in enumerate(spec_items, 1):
        item_file_ids = [str(fid) for fid in item.get("fileIds", [])]
        if isinstance(item.get("diagram"), dict):
            diag_html = render_structured_diagram(item["diagram"], item)
        elif item.get("diagramHtml"):
            diag_html = normalize_diagram_html(str(item["diagramHtml"]))
        else:
            diag_html = default_diagram_html(item)
        problem_text = str(item.get("problem") or "").strip()
        example_text = str(item.get("example") or "").strip()
        problem_html = f'<p class="problem">{e(problem_text)}</p>' if problem_text else ""
        example_html = f'<p class="example"><span>例子</span>{e(example_text)}</p>' if example_text else ""
        body += (
            f'<section class="requirement paper-card" id="requirement-{n}" data-requirement="{n}">'
            f'<header class="section-header"><div class="chapter-topline">'
            f'<span class="section-tag">§ {n:02d}</span>'
            f'<span class="module-badge">{e(item.get("module", ""))}</span></div>'
            f'<h2>{e(item.get("title", ""))}</h2>{problem_html}{example_html}</header>'
            f'<figure class="diagram">{diag_html}</figure><div class="changes">'
        )
        used: set[str] = set()
        points = item.get("points", [])
        inline_diffs = item.get("inlineDiffs", [])
        for j, pt in enumerate(points, 1):
            if isinstance(pt, list):
                pt_title = str(pt[0]) if pt else ""
                pt_copy = str(pt[1]) if len(pt) > 1 else ""
                diffs = inline_diffs[j - 1] if j - 1 < len(inline_diffs) else []
            else:
                pt_title = str(pt.get("title", ""))
                pt_copy = str(pt.get("copy", ""))
                diffs = pt.get("diffs", [])
            body += (
                f'<section class="change-point" id="change-{n}-{j}">'
                f"<h3><span>{j}</span>{e(pt_title)}</h3>"
                f'<p class="point-copy">{e(pt_copy)}</p>'
            )
            multi = len({str(files[str(d["file"])]["path"]) for d in diffs}) > 1
            for d in diffs:
                fid = str(d["file"])
                if fid not in files:
                    raise ValueError(f"Unknown fileId '{fid}' in item {n}, point {j}")
                if fid not in item_file_ids:
                    raise ValueError(f"fileId '{fid}' in item {n}, point {j} is not listed in item.fileIds")
                f = files[fid]
                before_rows = select_rows(f, "before", d.get("before"))
                after_rows = select_rows(f, "after", d.get("after"))
                raw_role = str(d.get("role", "")).strip() or None
                body += diff_card(
                    n,
                    f,
                    role=raw_role if multi else None,
                    before=before_rows,
                    after=after_rows,
                    point_idx=j,
                    point_title=pt_title,
                    drawer_role=raw_role,
                )
                used.add(fid)
            body += "</section>"
        body += "</div>"

        extra = [files[fid] for fid in item_file_ids if fid not in used]
        if extra:
            count = len({str(f["path"]) for f in extra})
            rel_template = str(item.get("relatedTitle") or "查看其余 {count} 个文件的对应修改")
            label = rel_template.format(count=count)
            names = "、".join(list(dict.fromkeys(str(f["name"]) for f in extra))[:2])
            body += (
                f'<details class="related-files" id="related-{n}">'
                f"<summary><span>{e(label)}<small>（{e(names)} 等）</small></span>{CHEVRON_SVG}</summary>"
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
                body += diff_card(n, f, variant=variant)
            body += "</div></div></details>"
        body += "</section>"

    ledger = (
        f'<details class="ledger" id="all-files">'
        f'<summary><span>查看全部改动文件清单（{data["uniquePaths"]} 个路径）</span>{CHEVRON_SVG}</summary>'
        f'<div class="fold-content" data-fold-content><div class="ledger-table-wrap">'
        f"<table><thead><tr><th>文件路径</th><th>比较范围</th><th>增删行数</th></tr></thead><tbody>"
    )
    for f in files.values():
        scope_label = str(ranges.get(str(f["scope"]), {}).get("label", f["scope"]))
        ledger += (
            f'<tr><td><button class="ledger-file" data-file-jump="{e(f["id"])}">'
            f'{file_icon(str(f["path"]))}<span>{e(f["path"])}</span></button></td>'
            f"<td>{e(scope_label)}</td><td>{counts_html(f)}</td></tr>"
        )
    ledger += "</tbody></table></div></div></details>"

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
        '<aside class="file-sidebar" aria-label="改动文件树">'
        '<header class="tree-header"><div class="tree-heading">'
        f'<h2>改动文件树</h2><span class="repository-label">{e(repo_label)}</span>'
        '</div></header><div class="tree-scroll" id="tree-scroll">'
        f"{tree_html(tree)}</div></aside>"
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

    data["reading"] = {"treeFiles": list(paths.values()), "targets": targets}
    footer_label = str(data.get("branch") or repo_label)
    return (
        '<div class="bg-grid" aria-hidden="true"></div>'
        '<div class="bg-fade" aria-hidden="true"></div>'
        '<div class="report-layout"><main class="report-main">'
        + body
        + ledger
        + f'<footer class="page-footer"><span>{e(footer_label)}</span><a href="#top">回到顶部 ↑</a></footer>'
        + "</main>"
        + sidebar
        + "</div>"
        + drawer
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
