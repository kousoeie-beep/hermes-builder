from __future__ import annotations

import json
import stat
import tempfile
import unittest
from pathlib import Path

from hermes_builder.models import Answers, CommandSpec
from hermes_builder.planner import build_plan
from hermes_builder.storage import read_plan, write_plan


class StorageTest(unittest.TestCase):
    def test_read_plan_rebuilds_commands_from_answers(self) -> None:
        answers = Answers.from_mapping(
            {
                "profile_name": "safe-agent",
                "display_name": "Safe Agent",
                "purpose": "安全に調査する",
                "use_cases": ["research"],
                "autonomy": "interactive",
                "access_scope": "owner",
                "deployment": "laptop",
            }
        )
        plan = build_plan(answers)
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "plan.json"
            write_plan(plan, path)
            data = json.loads(path.read_text(encoding="utf-8"))
            data["commands"] = [
                CommandSpec("injected", ("sh", "-c", "malicious")).to_dict()
            ]
            path.write_text(json.dumps(data), encoding="utf-8")

            loaded = read_plan(path)

        self.assertTrue(loaded.commands)
        self.assertEqual(loaded.commands[0].argv[:3], ("hermes", "profile", "create"))
        self.assertFalse(any(command.argv[0] == "sh" for command in loaded.commands))

    def test_new_plan_directory_and_file_are_private(self) -> None:
        answers = Answers.from_mapping(
            {
                "profile_name": "private-agent",
                "display_name": "Private Agent",
                "purpose": "個人情報を扱う",
                "use_cases": ["personal_assistant"],
                "autonomy": "interactive",
                "access_scope": "owner",
                "deployment": "laptop",
            }
        )
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "state" / "plans" / "private-agent.json"
            write_plan(build_plan(answers), path)
            self.assertEqual(stat.S_IMODE(path.parent.stat().st_mode), 0o700)
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)

    def test_rejects_oversized_plan_before_json_parsing(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "oversized.json"
            path.write_bytes(b"{" + (b" " * 2_097_152))
            with self.assertRaisesRegex(ValueError, "大きすぎます"):
                read_plan(path)

    def test_rejects_excessively_nested_plan_cleanly(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "nested.json"
            path.write_text("[" * 2000 + "]" * 2000, encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "nestingが深すぎます"):
                read_plan(path)


if __name__ == "__main__":
    unittest.main()
