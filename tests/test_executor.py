from __future__ import annotations

import os
import json
import stat
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from hermes_builder.executor import (
    ApplyOptions,
    ExecutionError,
    _run,
    _write_structured_config,
    apply_plan,
)
from hermes_builder.models import Answers, CommandSpec
from hermes_builder.planner import build_plan


class ExecutorTest(unittest.TestCase):
    @unittest.skipIf(os.name == "nt", "POSIX fake executable is covered by shell E2E")
    def test_noninteractive_apply_uses_fake_hermes_and_writes_soul(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            bin_dir = root / "bin"
            bin_dir.mkdir()
            command_log = root / "commands.log"
            fake = bin_dir / "hermes"
            fake.write_text(
                "#!/bin/sh\n"
                "if [ \"$1\" = profile ] && [ \"$2\" = show ]; then exit 1; fi\n"
                "printf '%s\\n' \"$*\" >> \"$HERMES_FAKE_LOG\"\n"
                "exit 0\n",
                encoding="utf-8",
            )
            fake.chmod(fake.stat().st_mode | stat.S_IXUSR)
            hermes_home = root / ".hermes"
            answers = Answers(
                profile_name="test-agent",
                display_name="Test Agent",
                purpose="安全に調査する",
                use_cases=("research",),
                autonomy="interactive",
                access_scope="owner",
                deployment="always_on",
                gateways=("slack",),
                integrations=("github",),
            )
            environment = {
                "HOME": str(root),
                "HERMES_HOME": str(hermes_home),
                "HERMES_FAKE_LOG": str(command_log),
                "PATH": f"{bin_dir}{os.pathsep}{os.environ.get('PATH', '')}",
            }
            with patch.dict(os.environ, environment, clear=False):
                apply_plan(build_plan(answers), ApplyOptions(non_interactive=True))

            soul = hermes_home / "profiles" / "test-agent" / "SOUL.md"
            self.assertTrue(soul.exists())
            self.assertIn("安全に調査する", soul.read_text(encoding="utf-8"))
            commands = command_log.read_text(encoding="utf-8")
            self.assertIn("profile create test-agent", commands)
            self.assertIn("-p test-agent doctor", commands)
            self.assertNotIn("gateway install", commands)
            self.assertNotIn("gateway start", commands)

    def test_structured_config_writes_real_lists_atomically(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            profile_home = root / "profiles" / "team-agent"
            profile_home.mkdir(parents=True)
            config_path = profile_home / "config.yaml"
            config_path.write_text('{"approvals": {"mode": "smart"}}', encoding="utf-8")
            fake_yaml = types.SimpleNamespace(
                YAMLError=ValueError,
                safe_load=lambda handle: json.load(handle),
                safe_dump=lambda value, **_kwargs: json.dumps(value, ensure_ascii=False),
            )
            values = {
                "agent.disabled_toolsets": ["terminal", "file"],
                "platform_toolsets.teams": ["clarify", "web"],
            }
            with (
                patch.dict(os.environ, {"HERMES_HOME": str(root)}, clear=False),
                patch.dict(sys.modules, {"yaml": fake_yaml}),
            ):
                _write_structured_config("team-agent", values, dry_run=False)

            saved = json.loads(config_path.read_text(encoding="utf-8"))
            self.assertEqual(saved["agent"]["disabled_toolsets"], ["terminal", "file"])
            self.assertEqual(saved["platform_toolsets"]["teams"], ["clarify", "web"])
            if os.name != "nt":
                self.assertEqual(stat.S_IMODE(config_path.stat().st_mode), 0o600)

    def test_strict_policy_denies_every_registry_toolset_not_allowed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            profile_home = root / "profiles" / "public-agent"
            profile_home.mkdir(parents=True)
            fake_yaml = types.SimpleNamespace(
                YAMLError=ValueError,
                safe_load=lambda handle: json.load(handle),
                safe_dump=lambda value, **_kwargs: json.dumps(value),
            )
            toolsets_module = types.ModuleType("toolsets")
            toolsets_module.TOOLSETS = {
                "web": {"tools": ["web_search"]},
                "kanban": {"tools": ["kanban"]},
                "hermes-cli": {"tools": [], "includes": ["web"]},
                "coding": {"tools": [], "posture": True},
            }
            hermes_cli_module = types.ModuleType("hermes_cli")
            hermes_cli_module.__path__ = []  # type: ignore[attr-defined]
            plugins_module = types.ModuleType("hermes_cli.plugins")
            plugins_module.discover_plugins = Mock()
            plugins_module.get_plugin_toolsets = Mock(
                return_value=[("image_gen", "Image", "Generate images")]
            )
            tools_config_module = types.ModuleType("hermes_cli.tools_config")
            tools_config_module.CONFIGURABLE_TOOLSETS = [
                ("clarify", "Clarify", "Ask"),
                ("terminal", "Terminal", "Run"),
                ("web", "Web", "Search"),
            ]
            modules = {
                "yaml": fake_yaml,
                "toolsets": toolsets_module,
                "hermes_cli": hermes_cli_module,
                "hermes_cli.plugins": plugins_module,
                "hermes_cli.tools_config": tools_config_module,
            }
            with (
                patch.dict(os.environ, {"HERMES_HOME": str(root)}, clear=False),
                patch.dict(sys.modules, modules),
            ):
                _write_structured_config(
                    "public-agent",
                    {
                        "agent.disabled_toolsets": ["terminal"],
                        "platform_toolsets.slack": ["clarify", "no_mcp", "web"],
                    },
                    dry_run=False,
                    strict_allowed_toolsets=["clarify", "web"],
                )

            saved = json.loads(
                (profile_home / "config.yaml").read_text(encoding="utf-8")
            )
            self.assertEqual(
                saved["agent"]["disabled_toolsets"],
                ["image_gen", "kanban", "terminal"],
            )
            self.assertEqual(
                saved["platform_toolsets"]["slack"],
                ["clarify", "no_mcp", "web"],
            )

    def test_required_security_audit_failure_stops_apply(self) -> None:
        command = CommandSpec(
            "依存関係をsecurity audit",
            ("hermes", "-p", "test-agent", "security", "audit", "--fail-on", "critical"),
            category="diagnostic",
        )
        with (
            patch("hermes_builder.executor.subprocess.run", return_value=Mock(returncode=9)),
            self.assertRaisesRegex(ExecutionError, "security audit"),
        ):
            _run(command, dry_run=False)

    def test_skip_gateways_keeps_all_safety_policy(self) -> None:
        plan = build_plan(
            Answers(
                profile_name="team-agent",
                display_name="Team Agent",
                purpose="安全に共同調査する",
                use_cases=("research",),
                autonomy="interactive",
                access_scope="trusted_team",
                deployment="always_on",
                gateways=("teams",),
            )
        )
        with (
            patch("hermes_builder.executor._run", return_value=True),
            patch("hermes_builder.executor._write_soul"),
            patch("hermes_builder.executor._write_structured_config") as writer,
        ):
            apply_plan(plan, ApplyOptions(dry_run=True, skip_gateways=True))

        saved_values = writer.call_args.args[1]
        self.assertIn("agent.disabled_toolsets", saved_values)
        self.assertIn("platform_toolsets.cli", saved_values)
        self.assertIn("platform_toolsets.teams", saved_values)
        self.assertIn("no_mcp", saved_values["platform_toolsets.teams"])
        self.assertEqual(
            writer.call_args.kwargs["strict_allowed_toolsets"],
            plan.gateway_toolsets,
        )

    def test_structured_config_fails_closed_without_hermes_yaml(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            with (
                patch.dict(os.environ, {"HERMES_HOME": temporary}, clear=False),
                patch.dict(sys.modules, {"yaml": None}),
                self.assertRaisesRegex(ExecutionError, "PyYAML"),
            ):
                _write_structured_config(
                    "team-agent",
                    {"agent.disabled_toolsets": ["terminal"]},
                    dry_run=False,
                )

    def test_force_profile_keeps_a_unique_backup_for_every_replacement(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            hermes_home = root / ".hermes"
            profile_home = hermes_home / "profiles" / "test-agent"
            profile_home.mkdir(parents=True)
            soul = profile_home / "SOUL.md"
            soul.write_text("original", encoding="utf-8")

            def plan(purpose: str):
                return build_plan(
                    Answers(
                        profile_name="test-agent",
                        display_name="Test Agent",
                        purpose=purpose,
                        use_cases=("research",),
                        autonomy="interactive",
                        access_scope="owner",
                        deployment="laptop",
                    )
                )

            with (
                patch.dict(os.environ, {"HERMES_HOME": str(hermes_home)}, clear=False),
                patch("hermes_builder.executor.shutil.which", return_value="hermes"),
                patch("hermes_builder.executor._profile_exists", return_value=True),
                patch("hermes_builder.executor._run", return_value=True),
            ):
                apply_plan(plan("first replacement"), ApplyOptions(force_profile=True))
                apply_plan(plan("second replacement"), ApplyOptions(force_profile=True))

            backups = sorted(profile_home.glob("SOUL.before-hermes-builder.*.md"))
            self.assertEqual(len(backups), 2)
            self.assertEqual(backups[0].read_text(encoding="utf-8"), "original")
            self.assertIn("first replacement", backups[1].read_text(encoding="utf-8"))
            self.assertIn("second replacement", soul.read_text(encoding="utf-8"))
            if os.name != "nt":
                self.assertEqual(stat.S_IMODE(soul.stat().st_mode), 0o600)

    def test_soul_replacement_failure_keeps_original_content(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            hermes_home = root / ".hermes"
            profile_home = hermes_home / "profiles" / "test-agent"
            profile_home.mkdir(parents=True)
            soul = profile_home / "SOUL.md"
            soul.write_text("original", encoding="utf-8")
            plan = build_plan(
                Answers(
                    profile_name="test-agent",
                    display_name="Test Agent",
                    purpose="replacement",
                    use_cases=("research",),
                    autonomy="interactive",
                    access_scope="owner",
                    deployment="laptop",
                )
            )
            with (
                patch.dict(os.environ, {"HERMES_HOME": str(hermes_home)}, clear=False),
                patch("hermes_builder.executor.shutil.which", return_value="hermes"),
                patch("hermes_builder.executor._profile_exists", return_value=True),
                patch("hermes_builder.executor._run", return_value=True),
                patch("hermes_builder.executor.os.replace", side_effect=OSError("disk error")),
                self.assertRaises(OSError),
            ):
                apply_plan(plan, ApplyOptions(force_profile=True))

            self.assertEqual(soul.read_text(encoding="utf-8"), "original")


if __name__ == "__main__":
    unittest.main()
