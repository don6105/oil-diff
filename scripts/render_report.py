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
            f'<div class="diagram-box is-emphasis">'
            f'<span class="diagram-pill">要点 {idx}</span>'
            f"<strong>{e(pt_title)}</strong>"
            f"<p>{e(pt_copy)}</p>"
            f"</div>"
        )
    cols = min(max(len(points), 1), 3)
    return (
        f'<div class="diagram-card">'
        f'<div class="diagram-head"><span>{e(item.get("module", "改动模块"))}</span>'
        f'<span>共 {len(points)} 处关键调整</span></div>'
        f'<div class="diagram-columns-{cols}">{cards}</div>'
        f"</div>"
    )


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
        diag_html = str(item.get("diagramHtml") or default_diagram_html(item))
        body += (
            f'<section class="requirement paper-card" id="requirement-{n}" data-requirement="{n}">'
            f'<header class="section-header"><div class="chapter-topline">'
            f'<span class="section-tag">§ {n:02d}</span>'
            f'<span class="module-badge">{e(item.get("module", ""))}</span></div>'
            f'<h2>{e(item.get("title", ""))}</h2></header>'
            f'<figure class="diagram">{diag_html}</figure><div class="changes">'
        )
        used: set[str] = set()
        points = item.get("points", [])
        for j, pt in enumerate(points, 1):
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
    parser.add_argument("--data", required=True, help="Path to diff-data.json.")
    parser.add_argument("--spec", required=True, help="Path to report-spec.json.")
    parser.add_argument("--output", required=True, help="Output HTML file path (e.g. .oil-diff/index.html).")
    args = parser.parse_args()

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
