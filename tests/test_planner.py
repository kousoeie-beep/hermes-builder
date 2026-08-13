from __future__ import annotations

import unittest

from hermes_builder.models import Answers
from hermes_builder.planner import build_plan
from hermes_builder.render import render_soul


def answers(**overrides: object) -> Answers:
    values: dict[str, object] = {
        "profile_name": "my-hermes",
        "display_name": "My Hermes",
        "purpose": "根拠つきで調査する",
        "use_cases": ("research",),
        "autonomy": "interactive",
        "access_scope": "owner",
        "deployment": "laptop",
        "gateways": ("slack",),
        "integrations": ("github",),
    }
    values.update(overrides)
    return Answers(**values)  # type: ignore[arg-type]


class PlannerTest(unittest.TestCase):
    def test_research_enables_research_tools(self) -> None:
        plan = build_plan(answers())
        self.assertIn("web", plan.cli_toolsets)
        self.assertIn("browser", plan.cli_toolsets)
        self.assertIn("x_search", plan.cli_toolsets)

    def test_team_gateway_removes_host_control(self) -> None:
        plan = build_plan(answers(access_scope="trusted_team"))
        self.assertNotIn("terminal", plan.gateway_toolsets)
        self.assertNotIn("file", plan.gateway_toolsets)
        self.assertNotIn("file", plan.cli_toolsets)
        self.assertIn("terminal", plan.gateway_denied_toolsets)
        self.assertIn("agent.disabled_toolsets", plan.config_values)

    def test_public_gateway_is_minimal(self) -> None:
        plan = build_plan(
            answers(access_scope="public", gateways=("slack", "teams"))
        )
        self.assertEqual(plan.gateway_toolsets, ["clarify", "skills", "todo", "web"])
        self.assertIn("memory", plan.gateway_denied_toolsets)
        self.assertEqual(
            plan.config_values["platform_toolsets.cli"],
            ["clarify", "skills", "todo", "web"],
        )
        for gateway in ("slack", "teams"):
            self.assertEqual(
                plan.config_values[f"platform_toolsets.{gateway}"],
                ["clarify", "no_mcp", "skills", "todo", "web"],
            )
        self.assertFalse(
            any("tools" in command.argv and "enable" in command.argv for command in plan.commands)
        )

    def test_cron_approval_remains_deny(self) -> None:
        plan = build_plan(answers(autonomy="autonomous_limited"))
        self.assertEqual(plan.config_values["approvals.cron_mode"], "deny")

    def test_soul_contains_safety_boundaries(self) -> None:
        soul = render_soul(build_plan(answers()))
        self.assertIn("認証情報", soul)
        self.assertIn("--yolo", soul)
        self.assertIn("allowlist", soul)

    def test_laptop_gateway_is_installed_as_user_service(self) -> None:
        plan = build_plan(answers(deployment="laptop"))
        categories = [command.category for command in plan.commands]
        self.assertIn("gateway_service", categories)

    def test_nous_provider_uses_portal_setup(self) -> None:
        plan = build_plan(answers(provider_mode="nous"))
        provider = next(command for command in plan.commands if command.category == "provider")
        self.assertEqual(provider.argv[-2:], ("setup", "--portal"))

    def test_shared_plugin_gateway_uses_structured_allowlist(self) -> None:
        plan = build_plan(
            answers(access_scope="trusted_team", gateways=("teams", "line", "simplex"))
        )
        per_platform = [
            command for command in plan.commands if "--platform" in command.argv
        ]
        self.assertEqual(per_platform, [])
        for gateway in ("teams", "line", "simplex"):
            self.assertEqual(
                plan.config_values[f"platform_toolsets.{gateway}"],
                sorted([*plan.gateway_toolsets, "no_mcp"]),
            )

    def test_disabled_toolsets_remain_a_json_array_value(self) -> None:
        plan = build_plan(answers(access_scope="trusted_team"))
        self.assertIsInstance(plan.config_values["agent.disabled_toolsets"], list)

    def test_gateway_policy_commands_are_skippable_as_gateway_steps(self) -> None:
        plan = build_plan(answers(gateways=("slack",)))
        platform_commands = [
            command for command in plan.commands if "--platform" in command.argv
        ]
        self.assertTrue(platform_commands)
        self.assertTrue(
            all(command.category == "gateway_policy" for command in platform_commands)
        )

    def test_critical_security_audit_is_required(self) -> None:
        plan = build_plan(answers())
        audit = next(
            command for command in plan.commands if command.argv[3:5] == ("security", "audit")
        )
        self.assertFalse(audit.optional)


if __name__ == "__main__":
    unittest.main()
