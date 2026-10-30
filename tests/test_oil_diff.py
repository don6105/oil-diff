#!/usr/bin/env python3
"""End-to-end unit tests for the oil-diff Skill scripts."""
from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

if sys.version_info < (3, 10):
    raise SystemExit("Python 3.10+ is required to run test_oil_diff.py.")

SKILL_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = SKILL_ROOT / "scripts"


def run_cmd(args: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        cwd=cwd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=True,
    )


class OilDiffWorkflowTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.repo = Path(self.temp_dir.name)
        run_cmd(["git", "init"], self.repo)
        run_cmd(["git", "config", "user.email", "tester@example.com"], self.repo)
        run_cmd(["git", "config", "user.name", "Tester"], self.repo)

        (self.repo / "SKILL.md").write_text(
            "# Demo Skill\n\n## Flow\nOld single step.\n",
            encoding="utf-8",
        )
        (self.repo / "references").mkdir()
        (self.repo / "references" / "guide.md").write_text(
            "# Guide\n\nInitial rule line.\n",
            encoding="utf-8",
        )
        (self.repo / "README.md").write_text(
            "# Demo\n\nOld summary.\n",
            encoding="utf-8",
        )
        run_cmd(["git", "add", "."], self.repo)
        run_cmd(["git", "commit", "-m", "Initial commit"], self.repo)

        # Modify files in working tree
        (self.repo / "SKILL.md").write_text(
            "# Demo Skill\n\n## Flow\nNew merged two-step check.\n",
            encoding="utf-8",
        )
        (self.repo / "references" / "guide.md").write_text(
            "# Guide\n\nUpdated rule line with clear boundary.\n",
            encoding="utf-8",
        )
        (self.repo / "README.md").write_text(
            "# Demo\n\nUpdated summary for users.\n",
            encoding="utf-8",
        )

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_collect_render_and_lint_pipeline(self) -> None:
        out_dir = self.repo / ".oil-diff"
        collect_res = run_cmd(
            [
                sys.executable,
                str(SCRIPTS_DIR / "collect_diff.py"),
                "--repo",
                str(self.repo),
                "--output",
                str(out_dir),
            ],
            cwd=self.repo,
        )
        summary = json.loads(collect_res.stdout)
        self.assertEqual(summary["uniquePaths"], 3)
        self.assertTrue((out_dir / ".gitignore").is_file())
        self.assertEqual((out_dir / ".gitignore").read_text(encoding="utf-8"), "*\n")

        spec = {
            "title": "这次修改了哪 1 件事",
            "eyebrow": "demo-skill / 改动汇报",
            "summary": "调整了主流程与参考说明文档，让规则边界更清晰。",
            "items": [
                {
                    "number": 1,
                    "module": "主流程与说明规范",
                    "navLabel": "合并主流程检查",
                    "title": "优化了主流程说明，把原本分散的检查步骤合并到同一处",
                    "overview": "把主流程说明里的检查步骤合并到一处，并同步更新参考文档。",
                    "fileIds": [
                        "working:SKILL.md",
                        "working:references/guide.md",
                        "working:README.md",
                    ],
                    "points": [
                        {
                            "title": "主流程改为合并检查",
                            "copy": "只改了主入口文件时，卡片不再重复显示第二行单文件说明。",
                            "diffs": [
                                {
                                    "file": "working:SKILL.md",
                                    "role": "更新主入口中的检查步骤描述。",
                                    "before": [{"line": 4}],
                                    "after": [{"line": 4}],
                                }
                            ],
                        },
                        {
                            "title": "同步更新主入口与参考说明",
                            "copy": "涉及多个文件时，卡片保留每个文件的职责说明。",
                            "diffs": [
                                {
                                    "file": "working:SKILL.md",
                                    "role": "入口文档写明合并后的检查要求。",
                                    "before": [{"line": 4}],
                                    "after": [{"line": 4}],
                                },
                                {
                                    "file": "working:references/guide.md",
                                    "role": "详细说明文档补充边界条件。",
                                    "before": [{"line": 3}],
                                    "after": [{"line": 3}],
                                },
                            ],
                        },
                    ],
                    "relatedTitle": "查看其余 {count} 个文件的对应修改",
                }
            ],
        }
        spec_path = out_dir / "assets" / "report-spec.json"
        spec_path.write_text(json.dumps(spec, ensure_ascii=False, indent=2), encoding="utf-8")

        html_path = out_dir / "index.html"
        run_cmd(
            [
                sys.executable,
                str(SCRIPTS_DIR / "render_report.py"),
                "--report-dir",
                str(out_dir),
            ],
            cwd=self.repo,
        )
        self.assertTrue(html_path.is_file())
        html_text = html_path.read_text(encoding="utf-8")
        self.assertIn('class="bg-grid"', html_text)
        self.assertIn('class="diff-drawer-root"', html_text)
        self.assertIn('id="related-1"', html_text)
        self.assertNotIn('<details class="diff-card"', html_text)

        lint_res = run_cmd(
            [
                sys.executable,
                str(SCRIPTS_DIR / "lint_report.py"),
                "--repo",
                str(self.repo),
                "--report-dir",
                str(out_dir),
            ],
            cwd=self.repo,
        )
        self.assertIn("PASS: 0 errors", lint_res.stdout)

        # Verify stray top-level file is rejected by lint_report.py
        stray_file = out_dir / "stray-screenshot.png"
        stray_file.write_text("dummy", encoding="utf-8")
        stray_proc = subprocess.run(
            [
                sys.executable,
                str(SCRIPTS_DIR / "lint_report.py"),
                "--repo",
                str(self.repo),
                "--report-dir",
                str(out_dir),
            ],
            cwd=self.repo,
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
        )
        self.assertNotEqual(stray_proc.returncode, 0)
        self.assertIn("move stray files into assets/", stray_proc.stdout)

    def test_lint_catches_hype_words(self) -> None:
        out_dir = self.repo / ".oil-diff"
        run_cmd(
            [
                sys.executable,
                str(SCRIPTS_DIR / "collect_diff.py"),
                "--repo",
                str(self.repo),
                "--output",
                str(out_dir),
            ],
            cwd=self.repo,
        )
        bad_spec = {
            "title": "这次修改了哪 1 件事",
            "summary": "通过组合拳赋能业务闭环。",
            "items": [
                {
                    "number": 1,
                    "module": "主流程",
                    "navLabel": "主流程",
                    "title": "优化了主流程说明与文件规则",
                    "overview": "优化了主流程说明与文件规则，确保上下游一致。",
                    "fileIds": [
                        "working:SKILL.md",
                        "working:references/guide.md",
                        "working:README.md",
                    ],
                    "points": [],
                }
            ],
        }
        spec_path = out_dir / "assets" / "report-spec.json"
        spec_path.write_text(json.dumps(bad_spec, ensure_ascii=False), encoding="utf-8")
        html_path = out_dir / "index.html"
        run_cmd(
            [
                sys.executable,
                str(SCRIPTS_DIR / "render_report.py"),
                "--data",
                str(out_dir / "assets" / "diff-data.json"),
                "--spec",
                str(spec_path),
                "--output",
                str(html_path),
            ],
            cwd=self.repo,
        )
        proc = subprocess.run(
            [
                sys.executable,
                str(SCRIPTS_DIR / "lint_report.py"),
                "--repo",
                str(self.repo),
                "--report-dir",
                str(out_dir),
            ],
            cwd=self.repo,
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
        )
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("Forbidden hype/jargon word", proc.stdout)

    def test_structured_diagrams_and_plain_text_diagram_lint(self) -> None:
        out_dir = self.repo / ".oil-diff"
        run_cmd(
            [
                sys.executable,
                str(SCRIPTS_DIR / "collect_diff.py"),
                "--repo",
                str(self.repo),
                "--output",
                str(out_dir),
            ],
            cwd=self.repo,
        )
        for dtype in ("routing", "comparison", "scenarios", "flow", "alignment", "diagnostics"):
            spec = {
                "title": "这次修改了哪 1 件事",
                "summary": "调整了主流程说明与文件边界。",
                "items": [
                    {
                        "number": 1,
                        "module": "主流程",
                        "navLabel": "主流程",
                        "title": "优化了主流程说明与文件规则",
                        "overview": "优化了主流程说明与文件规则，确保上下游一致。",
                        "problem": "以前只有一份总说明，找起来费劲。",
                        "example": "比如只改一处说明时还要翻完整篇文档。",
                        "diagram": {
                            "type": dtype,
                            "branches": [{"title": "分支 A", "file": "SKILL.md", "copy": "说明"}],
                            "scenarios": [{"title": "场景 A", "before": "以前", "after": "现在"}],
                            "rows": [{"title": "检查 1", "file": "SKILL.md", "detail": "锚点", "verdict": "通过", "pass": True}],
                        },
                        "fileIds": [
                            "working:SKILL.md",
                            "working:references/guide.md",
                            "working:README.md",
                        ],
                        "points": [],
                    }
                ],
            }
            spec_path = out_dir / "assets" / "report-spec.json"
            spec_path.write_text(json.dumps(spec, ensure_ascii=False), encoding="utf-8")
            run_cmd(
                [sys.executable, str(SCRIPTS_DIR / "render_report.py"), "--report-dir", str(out_dir)],
                cwd=self.repo,
            )
            lint_res = run_cmd(
                [
                    sys.executable,
                    str(SCRIPTS_DIR / "lint_report.py"),
                    "--repo",
                    str(self.repo),
                    "--report-dir",
                    str(out_dir),
                ],
                cwd=self.repo,
            )
            self.assertIn("PASS: 0 errors", lint_res.stdout)


if __name__ == "__main__":
    unittest.main()
