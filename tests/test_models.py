from __future__ import annotations

import unittest

from hermes_builder.catalog import GATEWAYS
from hermes_builder.models import Answers


VALID = {
    "profile_name": "my-hermes",
    "display_name": "My Hermes",
    "purpose": "調査する",
    "use_cases": ["research"],
    "autonomy": "interactive",
    "access_scope": "owner",
    "deployment": "laptop",
}


class AnswersTest(unittest.TestCase):
    def test_valid_mapping(self) -> None:
        answers = Answers.from_mapping(VALID)
        self.assertEqual(answers.profile_name, "my-hermes")
        self.assertEqual(answers.use_cases, ("research",))

    def test_rejects_secret_fields(self) -> None:
        data = dict(VALID, slack_bot_token="secret")
        with self.assertRaisesRegex(ValueError, "秘密値"):
            Answers.from_mapping(data)

    def test_rejects_known_secret_value_patterns(self) -> None:
        fake_token = "xoxb-" + "1234567890-" + "abcdefghijklmnop"
        data = dict(VALID, purpose=f"Slack token {fake_token}")
        with self.assertRaisesRegex(ValueError, "秘密値らしい文字列"):
            Answers.from_mapping(data)

    def test_rejects_terminal_control_characters(self) -> None:
        data = dict(VALID, display_name="Agent\x1b[2J")
        with self.assertRaisesRegex(ValueError, "制御文字"):
            Answers.from_mapping(data)

    def test_deduplicates_ordered_choices(self) -> None:
        data = dict(
            VALID,
            use_cases=["research", "research"],
            gateways=["slack", "slack", "teams"],
            integrations=["github", "github"],
        )
        answers = Answers.from_mapping(data)
        self.assertEqual(answers.use_cases, ("research",))
        self.assertEqual(answers.gateways, ("slack", "teams"))
        self.assertEqual(answers.integrations, ("github",))

    def test_rejects_unknown_gateway(self) -> None:
        data = dict(VALID, gateways=["carrier-pigeon"])
        with self.assertRaisesRegex(ValueError, "gateway"):
            Answers.from_mapping(data)

    def test_accepts_current_official_gateway_catalog(self) -> None:
        data = dict(
            VALID,
            gateways=["teams", "line", "feishu", "whatsapp_cloud", "simplex", "a2a"],
        )
        answers = Answers.from_mapping(data)
        self.assertIn("simplex", answers.gateways)
        self.assertIn("a2a", answers.gateways)

    def test_gateway_catalog_has_unique_keys(self) -> None:
        keys = [gateway.key for gateway in GATEWAYS]
        self.assertEqual(len(keys), len(set(keys)))

    def test_rejects_unknown_non_secret_field(self) -> None:
        data = dict(VALID, typo_field="value")
        with self.assertRaisesRegex(ValueError, "未対応の項目"):
            Answers.from_mapping(data)

    def test_rejects_unicode_profile_slug(self) -> None:
        data = dict(VALID, profile_name="エルメス")
        with self.assertRaisesRegex(ValueError, "profile_name"):
            Answers.from_mapping(data)


if __name__ == "__main__":
    unittest.main()
