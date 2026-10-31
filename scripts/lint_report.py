#!/usr/bin/env python3
"""Audit a generated oil-diff report for Git isolation, copy quality, and UI structure."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys

if sys.version_info < (3, 10):
    raise SystemExit("Python 3.10+ is required to run lint_report.py.")

FORBIDDEN_HYPE_WORDS = (
    "赋能",
    "抓手",
    "闭环",
    "心智",
    "打通",
    "拉齐",
    "沉淀",
    "颗粒度",
    "护城河",
    "组合拳",
    "解耦",
    "契约",
)

VISUAL_PRIMITIVE_TOKENS = (
    "<svg",
    "domain-wire",
    "admin-window",
    "shot-window",
    "menu-filmstrip",
    "snapshot-grid",
    "run-history",
    "track-junction",
    "artifact-file",
    "ui-Chart-svg",
    "ui-select-demo",
    "ui-focus-demo",
    "ui-toolbar-demo",
    "pipe-board",
    "vis-card",
    "shot-frame",
    "shot-slider",
    "shot-zoom-trigger",
    "schema-diff",
)

FORBIDDEN_NOISE_PHRASES = (
    "展开原文对照",
    "收起原文对照",
    "跟随滚动高亮",
    "仅看当前需求",
    "把这份文档中默认看视频或重复准备截图的要求",
)


def check_git_isolation(repo: Path, report_dir: Path, errors: list[str]) -> None:
    gitignore = report_dir / ".gitignore"
    if not gitignore.is_file():
        errors.append(f"Missing .gitignore inside report directory: {gitignore}")
    elif gitignore.read_text(encoding="utf-8").strip() != "*":
        errors.append(f"{gitignore} must contain '*' to keep the report untracked.")

    res = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=repo,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if res.returncode == 0:
        try:
            rel_report = report_dir.resolve().relative_to(repo.resolve()).as_posix()
            for line in res.stdout.splitlines():
                if rel_report in line:
                    errors.append(f"Report directory '{rel_report}' appears in git status: {line.strip()}")
        except ValueError:
            pass


def collect_spec_texts(spec: dict[str, object]) -> list[str]:
    texts = [str(spec.get("title", "")), str(spec.get("summary", ""))]
    for item in spec.get("items", []):
        texts.extend(
            [
                str(item.get("module", "")),
                str(item.get("navLabel", "")),
                str(item.get("title", "")),
                str(item.get("overview", "")),
                str(item.get("problem", "")),
                str(item.get("example", "")),
            ]
        )
        for pt in item.get("points", []):
            if isinstance(pt, list):
                texts.extend(str(x) for x in pt[:2])
            elif isinstance(pt, dict):
                texts.extend([str(pt.get("title", "")), str(pt.get("copy", ""))])
                for d in pt.get("diffs", []):
                    if isinstance(d, dict) and d.get("role"):
                        texts.append(str(d["role"]))
    return [t for t in texts if t]


def lint_report(repo: Path, report_dir: Path) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []

    check_git_isolation(repo, report_dir, errors)

    assets_dir = report_dir / "assets"
    if not assets_dir.is_dir():
        errors.append(f"Missing assets directory inside report directory: {assets_dir}")
    data_path = assets_dir / "diff-data.json"
    spec_path = assets_dir / "report-spec.json"
    html_path = report_dir / "index.html"

    for p in (data_path, spec_path, html_path):
        if not p.is_file():
            errors.append(f"Missing required report artifact: {p.relative_to(report_dir)}")

    allowed_top = {".gitignore", "index.html", "assets"}
    if report_dir.is_dir():
        stray_top = sorted(p.name for p in report_dir.iterdir() if p.name not in allowed_top)
        if stray_top:
            errors.append(
                f"Top-level .oil-diff directory should only contain index.html, .gitignore, and assets/; move stray files into assets/: {stray_top}"
            )

    if errors:
        return errors, warnings

    data = json.loads(data_path.read_text(encoding="utf-8"))
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    html = html_path.read_text(encoding="utf-8")

    # 1. File coverage check
    all_file_ids = {str(f["id"]) for f in data.get("files", [])}
    reported_ids = {
        str(fid)
        for item in spec.get("items", [])
        for fid in item.get("fileIds", [])
    }
    unreported = sorted(all_file_ids - reported_ids)
    if unreported:
        errors.append(f"Unreported files missing from report-spec.json: {unreported}")

    # 2. Copywriting & item structure checks
    items = spec.get("items", [])
    if not items:
        errors.append("report-spec.json must define at least one item in 'items'.")

    for idx, item in enumerate(items, 1):
        module = str(item.get("module", "")).strip()
        title = str(item.get("title", "")).strip()
        overview = str(item.get("overview", "")).strip()
        if not module:
            errors.append(f"Item {idx} is missing a business 'module' badge.")
        if len(title) < 6:
            errors.append(f"Item {idx} 'title' is too short ({len(title)} chars): '{title}'")
        if len(overview) < 8:
            errors.append(
                f"Item {idx} 'overview' must be a complete sentence (>= 8 chars), got: '{overview}'"
            )

    joined_copy = "\n".join(collect_spec_texts(spec))
    for word in FORBIDDEN_HYPE_WORDS:
        if word in joined_copy:
            errors.append(f"Forbidden hype/jargon word '{word}' found in report copy.")
    for phrase in FORBIDDEN_NOISE_PHRASES:
        if phrase in joined_copy or phrase in html:
            errors.append(f"Forbidden noise phrase '{phrase}' found in report.")

    # 3. HTML structure & interaction checks
    required_selectors = (
        'class="bg-grid"',
        'class="intro paper-card"',
        'class="requirement paper-card',
        'id="bento-deck"',
        'class="changes blast-funnel"',
        'class="point-pills"',
        'class="file-sidebar"',
        'data-tree-toggle',
        'class="diff-drawer-root"',
        'id="diff-drawer-panel"',
    )
    for token in required_selectors:
        if token not in html:
            errors.append(f"index.html is missing required structure token: {token}")

    if 'id="all-files"' in html or '<details class="ledger"' in html:
        errors.append("index.html must not render the redundant bottom #all-files ledger; use the collapsible right file sidebar instead.")

    if '<details class="diff-card"' in html:
        errors.append("index.html uses inline <details class=\"diff-card\"> instead of slide-over drawer triggers.")

    rendered_leaf_tokens = (
        "<img",
        "<svg",
        "domain-node",
        "admin-window",
        "shot-window",
        "serial-node",
        "process-node",
        "vis-box",
        "schema-row",
        "pipe-row",
        "shot-frame",
        "shot-slider",
        "menu-filmstrip",
        "snapshot-grid",
        "run-history",
    )
    for fig_idx, fig_match in enumerate(
        re.finditer(r'<figure class="diagram"[^>]*>(.*?)</figure>', html, re.DOTALL), 1
    ):
        fig_body = fig_match.group(1)
        if re.search(r"<p(?:\s|>)", fig_body):
            errors.append(
                f"Diagram {fig_idx} contains <p> prose inside <figure class=\"diagram\">; keep prose in overview/points and use only visual elements + short tags inside diagrams."
            )
        if not any(tok in fig_body for tok in rendered_leaf_tokens):
            errors.append(
                f"Diagram {fig_idx} rendered an empty <figure class=\"diagram\"> without any visual nodes; check 'diagram' fields in report-spec.json."
            )

    # 4. Screenshot authenticity & anti-scavenging check
    diff_paths = {str(f.get("path", "")) for f in data.get("files", [])}
    valid_capture_sources = {"live-capture", "git-diff", "user-provided"}
    referenced_shots: list[tuple[int, str, str]] = []
    for idx, item in enumerate(items, 1):
        diag = item.get("diagram")
        if not isinstance(diag, dict):
            continue
        top_cap = str(diag.get("captureSource") or item.get("captureSource") or "").strip()
        shot_entries: list[tuple[str, str]] = []
        for k in ("beforeSrc", "afterSrc", "src"):
            if diag.get(k):
                shot_entries.append((str(diag[k]), top_cap))
        for b_key in ("before", "after"):
            b_val = diag.get(b_key)
            if isinstance(b_val, dict) and b_val.get("src"):
                c_src = str(b_val.get("captureSource") or top_cap).strip()
                shot_entries.append((str(b_val["src"]), c_src))
        for list_key in ("shots", "items", "cards", "scenarios"):
            for entry in diag.get(list_key) or []:
                if isinstance(entry, dict):
                    c_src = str(entry.get("captureSource") or top_cap).strip()
                    for s_key in ("src", "beforeSrc", "afterSrc"):
                        if entry.get(s_key):
                            shot_entries.append((str(entry[s_key]), c_src))
        for s_ref, c_src in shot_entries:
            if c_src not in valid_capture_sources:
                errors.append(
                    f"Item {idx} uses screenshots ({s_ref}) without a valid 'captureSource' in {sorted(valid_capture_sources)}. Never use unverified/research images as diff screenshots."
                )
                break
        for s_ref, c_src in shot_entries:
            referenced_shots.append((idx, s_ref, c_src))

    # Build SHA-256 index of non-diff images in repo to block copying from _work/, research/, fixtures/, etc.
    img_exts = {".png", ".jpg", ".jpeg", ".webp", ".gif"}
    shot_files_in_report = [
        p for p in (report_dir / "assets").rglob("*") if p.is_file() and p.suffix.lower() in img_exts
    ]
    if shot_files_in_report or referenced_shots:
        non_diff_repo_hashes: dict[str, str] = {}
        skip_dirs = {".git", ".oil-diff", "node_modules", ".venv", "__pycache__"}
        for root_path in repo.rglob("*"):
            if not root_path.is_file() or root_path.suffix.lower() not in img_exts:
                continue
            rel_parts = root_path.relative_to(repo).parts
            if any(part in skip_dirs for part in rel_parts):
                continue
            rel_posix = root_path.relative_to(repo).as_posix()
            if rel_posix not in diff_paths:
                try:
                    h = hashlib.sha256(root_path.read_bytes()).hexdigest()
                    non_diff_repo_hashes.setdefault(h, rel_posix)
                except OSError:
                    pass
        for shot_p in shot_files_in_report:
            try:
                shot_h = hashlib.sha256(shot_p.read_bytes()).hexdigest()
            except OSError:
                continue
            if shot_h in non_diff_repo_hashes:
                errors.append(
                    f"Screenshot '{shot_p.relative_to(report_dir)}' has the exact same SHA-256 as unchanged/untracked repo image '{non_diff_repo_hashes[shot_h]}' (not in git diff). Never copy research/reference images into diff reports!"
                )

    # 5. Single-file point must not render .file-explanation on the card trigger
    for idx, item in enumerate(items, 1):
        if item.get("diagramHtml") and not any(tok in str(item["diagramHtml"]) for tok in VISUAL_PRIMITIVE_TOKENS):
            errors.append(
                f"Item {idx} uses plain-text diagramHtml without visual primitives; use structured 'diagram' (routing/comparison/scenarios/flow/alignment/diagnostics) instead."
            )
        if not item.get("diagram") and not item.get("diagramHtml"):
            warnings.append(
                f"Item {idx} omits structured 'diagram' spec; add 'diagram': {{'type': ...}} for richer miniature UI visuals."
            )
        for p_idx, pt in enumerate(item.get("points", []), 1):
            diffs = pt.get("diffs", []) if isinstance(pt, dict) else []
            if len(diffs) == 1:
                section_pattern = re.compile(
                    rf'<section class="change-point" id="change-{idx}-{p_idx}">(.*?)</section>',
                    re.DOTALL,
                )
                match = section_pattern.search(html)
                if match and 'class="file-explanation"' in match.group(1):
                    errors.append(
                        f"Single-file point change-{idx}-{p_idx} must not render .file-explanation on the card trigger."
                    )

    return errors, warnings


def main() -> int:
    parser = argparse.ArgumentParser(description="Lint an oil-diff HTML change report.")
    parser.add_argument("--repo", default=".", help="Path to the Git repository.")
    parser.add_argument("--report-dir", required=True, help="Path to the .oil-diff report directory.")
    parser.add_argument("--json", action="store_true", help="Emit JSON summary.")
    args = parser.parse_args()

    repo = Path(args.repo).resolve()
    report_dir = Path(args.report_dir).resolve()
    errors, warnings = lint_report(repo, report_dir)

    if args.json:
        print(
            json.dumps(
                {"passed": not errors, "errors": errors, "warnings": warnings},
                ensure_ascii=False,
                indent=2,
            )
        )
    else:
        for err in errors:
            print(f"[ERROR] {err}")
        for warn in warnings:
            print(f"[WARN] {warn}")
        if not errors:
            print(f"PASS: 0 errors, {len(warnings)} warnings")

    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
