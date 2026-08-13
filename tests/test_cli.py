from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ENV = dict(os.environ, PYTHONPATH=str(ROOT / "src"), PYTHONUTF8="1")


class CliTest(unittest.TestCase):
    def run_cli(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            (sys.executable, "-m", "hermes_builder", *args),
            cwd=ROOT,
            env=ENV,
            text=True,
            capture_output=True,
            check=False,
        )

    def test_help(self) -> None:
        result = self.run_cli("--help")
        self.assertEqual(result.returncode, 0)
        self.assertIn("setup", result.stdout)
        self.assertIn("completion", result.stdout)

    def test_version(self) -> None:
        result = self.run_cli("--version")
        self.assertEqual(result.returncode, 0)
        self.assertIn("0.1.2", result.stdout)

    def test_noninteractive_plan_and_dry_run(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            plan = Path(temporary) / "plan.json"
            result = self.run_cli(
                "setup",
                "--answers",
                str(ROOT / "examples" / "research-operator.json"),
                "--plan-out",
                str(plan),
                "--non-interactive",
                "--dry-run",
                "--yes",
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertFalse(plan.exists())
            self.assertIn("Dry-runのためplanは保存していません", result.stdout)
            self.assertIn("hermes profile create", result.stderr)
            self.assertIn("未完了", result.stderr)
            self.assertIn("gateway authentication pending", result.stderr)

    def test_completion(self) -> None:
        result = self.run_cli("completion", "bash")
        self.assertEqual(result.returncode, 0)
        self.assertIn("complete -F", result.stdout)

    def test_doctor_rejects_option_like_profile_name(self) -> None:
        result = self.run_cli("doctor", "--", "--version")
        self.assertEqual(result.returncode, 2)
        self.assertIn("profile_name", result.stderr)


if __name__ == "__main__":
    unittest.main()
