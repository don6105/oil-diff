#!/usr/bin/env python3
"""Collect Git diff snapshots and hunk metadata into an untracked report directory."""
from __future__ import annotations

import argparse
import difflib
import json
from pathlib import Path
import re
import subprocess
import sys

if sys.version_info < (3, 10):
    raise SystemExit("Python 3.10+ is required to run collect_diff.py.")


def run_git(repo: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        ["git", "-c", "core.quotepath=false", *args],
        cwd=repo,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if check and result.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed: {result.stderr.strip()}")
    return result


def read_source(repo: Path, rev: str, rel_path: str) -> str:
    if rev == "WT":
        target = repo / rel_path
        if target.is_symlink():
            raise ValueError(f"Refusing to follow worktree symlink: {rel_path}")
        return target.read_text(encoding="utf-8", errors="replace") if target.is_file() else ""
    res = run_git(repo, "show", f"{rev}:{rel_path}", check=False)
    return res.stdout if res.returncode == 0 else ""


def infer_location(lines: list[str], position: int, is_code: bool) -> str:
    upper = min(len(lines), position + 1)
    for line in reversed(lines[:upper]):
        if is_code and re.match(
            r"^\s*(?:async\s+)?(?:function |def |class |(?:export\s+)?(?:const|let|function|class)\s+)",
            line,
        ):
            return line.strip()[:140]
        if not is_code and line.startswith("#"):
            return line.lstrip("#").strip()[:140]
    return "文件内容"


def build_chunks(old_text: str, new_text: str, is_code: bool) -> list[dict[str, object]]:
    a = old_text.splitlines()
    b = new_text.splitlines()
    matcher = difflib.SequenceMatcher(None, a, b, autojunk=False)
    result: list[dict[str, object]] = []
    for number, group in enumerate(matcher.get_grouped_opcodes(2), 1):
        left: list[dict[str, object]] = []
        right: list[dict[str, object]] = []
        for tag, i, j, k, l in group:
            left.extend({"line": n + 1, "text": a[n], "changed": tag != "equal"} for n in range(i, j))
            right.extend({"line": n + 1, "text": b[n], "changed": tag != "equal"} for n in range(k, l))
        result.append(
            {
                "number": number,
                "location": infer_location(b if b else a, group[0][3] if b else group[0][1], is_code),
                "oldStart": group[0][1] + 1,
                "newStart": group[0][3] + 1,
                "oldEnd": group[-1][2],
                "newEnd": group[-1][4],
                "before": left,
                "after": right,
            }
        )
    return result


def collect_range_changes(repo: Path, before_rev: str, after_rev: str) -> tuple[dict[str, dict[str, int]], dict[str, str]]:
    diff_args = [before_rev] if after_rev == "WT" else [before_rev, after_rev]
    stats: dict[str, dict[str, int]] = {}
    numstat_out = run_git(
        repo, "diff", "--no-ext-diff", "--no-renames", "--numstat", *diff_args, "--"
    ).stdout
    for line in numstat_out.splitlines():
        parts = line.split("\t")
        if len(parts) != 3:
            continue
        add_s, del_s, path = parts
        is_bin = 1 if (add_s == "-" or del_s == "-") else 0
        add_n = int(add_s) if add_s.isdigit() else 0
        del_n = int(del_s) if del_s.isdigit() else 0
        stats[path] = {"add": add_n, "delete": del_n, "binary": is_bin}

    statuses: dict[str, str] = {}
    status_out = run_git(
        repo, "diff", "--no-ext-diff", "--no-renames", "--name-status", *diff_args, "--"
    ).stdout
    for line in status_out.splitlines():
        if "\t" not in line:
            continue
        code, path = line.split("\t", 1)
        statuses[path] = code[0]

    if after_rev == "WT":
        untracked = run_git(repo, "ls-files", "--others", "--exclude-standard").stdout.splitlines()
        for path in untracked:
            target = repo / path
            if target.is_symlink() or not target.is_file():
                continue
            raw_head = target.read_bytes()[:8192]
            if b"\x00" in raw_head:
                stats[path] = {"add": 0, "delete": 0, "binary": 1}
            else:
                text = target.read_text(encoding="utf-8", errors="replace")
                stats[path] = {"add": len(text.splitlines()), "delete": 0, "binary": 0}
            statuses[path] = "A"

    return stats, statuses


def parse_range_spec(spec: str) -> tuple[str, str, str, str]:
    """Parse '<scope>:<label>:<from>..<to>' into (scope, label, from_rev, to_rev)."""
    parts = spec.split(":", 2)
    if len(parts) != 3 or ".." not in parts[2]:
        raise ValueError(f"Invalid --range format '{spec}'. Expected '<id>:<label>:<from>..<to>'.")
    scope, label, rev_span = parts
    from_rev, to_rev = rev_span.split("..", 1)
    return scope.strip(), label.strip(), from_rev.strip(), to_rev.strip()


def resolve_short_rev(repo: Path, rev: str) -> str:
    if rev == "WT":
        return "当前工作区"
    full = run_git(repo, "rev-parse", f"{rev}^{{commit}}").stdout.strip()
    return full[:7]


def default_ranges(repo: Path) -> list[tuple[str, str, str, str]]:
    ranges: list[tuple[str, str, str, str]] = []
    wt_stats, _ = collect_range_changes(repo, "HEAD", "WT")
    if wt_stats:
        ranges.append(("working", "当前未提交", "HEAD", "WT"))
    has_parent = run_git(repo, "rev-parse", "--verify", "HEAD~1", check=False).returncode == 0
    if has_parent:
        if not wt_stats:
            ranges.append(("working", "最近一轮提交", "HEAD~1", "HEAD"))
        else:
            ranges.append(("committed", "最近一轮提交", "HEAD~1", "HEAD"))
    return ranges


def ensure_isolated_output(repo: Path, out_dir: Path) -> Path:
    if out_dir.is_symlink() or (out_dir.exists() and out_dir.parent.is_symlink()):
        raise RuntimeError(f"Refusing to use symlinked output directory: {out_dir}")
    out_dir.mkdir(parents=True, exist_ok=True)
    gitignore = out_dir / ".gitignore"
    if gitignore.is_symlink():
        raise RuntimeError(f"Refusing to write symlinked .gitignore: {gitignore}")
    gitignore.write_text("*\n", encoding="utf-8")
    assets_dir = out_dir / "assets"
    if assets_dir.is_symlink():
        raise RuntimeError(f"Refusing to use symlinked assets directory: {assets_dir}")
    assets_dir.mkdir(parents=True, exist_ok=True)
    try:
        rel = out_dir.resolve().relative_to(repo.resolve())
        tracked = run_git(repo, "ls-files", "--", str(rel)).stdout.strip()
        if tracked:
            raise RuntimeError(f"Output directory '{rel}' contains tracked Git files: {tracked}")
    except ValueError:
        pass
    return assets_dir


def status_label(scope: str, kind: str, to_rev: str) -> str:
    uncommitted = scope == "working" and to_rev == "WT"
    if kind == "A":
        return "未提交新增" if uncommitted else "已提交新增"
    if kind == "D":
        return "已删除"
    return "未提交修改" if uncommitted else "已提交修改"


def collect_diff(repo: Path, out_dir: Path, range_specs: list[str] | None = None) -> dict[str, object]:
    repo = repo.resolve()
    out_dir = out_dir.resolve()
    assets_dir = ensure_isolated_output(repo, out_dir)

    branch = run_git(repo, "branch", "--show-current").stdout.strip() or "HEAD"
    current_head = run_git(repo, "rev-parse", "HEAD").stdout.strip()
    parsed_ranges = (
        [parse_range_spec(spec) for spec in range_specs]
        if range_specs
        else default_ranges(repo)
    )

    files: list[dict[str, object]] = []
    ranges_meta: dict[str, dict[str, str]] = {}
    code_suffixes = (".py", ".js", ".mjs", ".ts", ".tsx", ".jsx", ".go", ".rs", ".java")

    for scope, label, from_rev, to_rev in parsed_ranges:
        from_short = resolve_short_rev(repo, from_rev)
        to_short = resolve_short_rev(repo, to_rev)
        ranges_meta[scope] = {"label": label, "from": from_short, "to": to_short}
        stats, statuses = collect_range_changes(repo, from_rev, to_rev)
        for path, nums in stats.items():
            kind = statuses.get(path, "M")
            is_binary = bool(nums.get("binary"))
            if is_binary:
                chunks: list[dict[str, object]] = []
            else:
                old_src = read_source(repo, from_rev, path)
                new_src = read_source(repo, to_rev, path)
                chunks = build_chunks(old_src, new_src, path.endswith(code_suffixes))
            files.append(
                {
                    "id": f"{scope}:{path}",
                    "scope": scope,
                    "path": path,
                    "name": Path(path).name,
                    "status": status_label(scope, kind, to_rev),
                    "kind": kind,
                    "binary": is_binary,
                    "add": nums["add"],
                    "delete": nums["delete"],
                    "from": from_short,
                    "to": to_short,
                    "chunks": chunks,
                }
            )

    unique_paths = len({str(f["path"]) for f in files})
    data: dict[str, object] = {
        "repoName": repo.name,
        "branch": branch,
        "currentHead": current_head,
        "uniquePaths": unique_paths,
        "ranges": ranges_meta,
        "files": files,
    }
    output_file = assets_dir / "diff-data.json"
    output_file.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return data


def main() -> int:
    parser = argparse.ArgumentParser(description="Collect Git diff snapshots into .oil-diff/assets/diff-data.json.")
    parser.add_argument("--repo", default=".", help="Path to the Git repository.")
    parser.add_argument("--output", default=None, help="Output directory (defaults to <repo>/.oil-diff).")
    parser.add_argument(
        "--range",
        action="append",
        dest="ranges",
        help="Comparison range in '<id>:<label>:<from>..<to>' format (may be repeated).",
    )
    args = parser.parse_args()
    repo = Path(args.repo).resolve()
    out_dir = Path(args.output).resolve() if args.output else (repo / ".oil-diff")
    data = collect_diff(repo, out_dir, args.ranges)
    print(
        json.dumps(
            {
                "output": str(out_dir / "assets" / "diff-data.json"),
                "fileRecords": len(data["files"]),
                "uniquePaths": data["uniquePaths"],
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
