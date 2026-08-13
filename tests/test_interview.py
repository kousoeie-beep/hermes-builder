from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from hermes_builder.interview import load_answers


class InterviewFileTest(unittest.TestCase):
    def test_rejects_oversized_answers_before_json_parsing(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "oversized.json"
            path.write_bytes(b"{" + (b" " * 1_048_576))
            with self.assertRaisesRegex(ValueError, "大きすぎます"):
                load_answers(path)

    def test_rejects_non_utf8_answers(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "invalid.json"
            path.write_bytes(b"{\xff}")
            with self.assertRaisesRegex(ValueError, "UTF-8"):
                load_answers(path)

    def test_rejects_excessively_nested_json_cleanly(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "nested.json"
            path.write_text("[" * 2000 + "]" * 2000, encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "nestingが深すぎます"):
                load_answers(path)

    def test_nesting_scanner_ignores_brackets_inside_strings(self) -> None:
        answers = {
            "profile_name": "bracket-agent",
            "display_name": "Bracket Agent",
            "purpose": "[not nesting]" * 40,
            "use_cases": ["research"],
            "autonomy": "interactive",
            "access_scope": "owner",
            "deployment": "laptop",
        }
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "answers.json"
            path.write_text(json.dumps(answers), encoding="utf-8")
            self.assertEqual(load_answers(path).profile_name, "bracket-agent")


if __name__ == "__main__":
    unittest.main()
