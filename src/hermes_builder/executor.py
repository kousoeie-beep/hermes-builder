from __future__ import annotations

import os
import shlex
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from hermes_builder.models import BuildPlan, CommandSpec
from hermes_builder.render import render_soul


class ExecutionError(RuntimeError):
    """Raised when a required setup step fails."""


@dataclass(frozen=True)
class ApplyOptions:
    dry_run: bool = False
    non_interactive: bool = False
    force_profile: bool = False
    skip_provider: bool = False
    skip_gateways: bool = False
    skip_mcp: bool = False
    no_service: bool = False


def _log(message: str) -> None:
    print(message, file=sys.stderr)


def _profile_home(profile_name: str) -> Path:
    root = Path(os.environ.get("HERMES_HOME", str(Path.home() / ".hermes"))).expanduser()
    return root / "profiles" / profile_name


def _run(command: CommandSpec, dry_run: bool) -> bool:
    rendered = shlex.join(command.argv)
    _log(f"→ {command.description}\n  {rendered}")
    if dry_run:
        return True
    result = subprocess.run(command.argv, check=False)
    if result.returncode == 0:
        _log(f"✓ {command.description}")
        return True
    if command.optional:
        _log(f"⚠ 任意ステップに失敗しました: {command.description}")
        return False
    raise ExecutionError(
        f"{command.description} に失敗しました（exit {result.returncode}）。\n"
        "修正後、同じplanで `hermes-builder apply <plan>` を再実行できます。"
    )


def _profile_exists(profile_name: str) -> bool:
    result = subprocess.run(
        ("hermes", "profile", "show", profile_name),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    return result.returncode == 0


def _atomic_write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temporary = Path(handle.name)
            os.chmod(temporary, 0o600)
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()


def _soul_backup_path(path: Path) -> Path:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
    unique = uuid4().hex[:8]
    return path.with_name(f"SOUL.before-hermes-builder.{timestamp}.{unique}.md")


def _set_nested_mapping(root: dict[object, object], dotted_key: str, value: list[str]) -> None:
    current = root
    parts = dotted_key.split(".")
    for part in parts[:-1]:
        existing = current.get(part)
        if existing is None:
            existing = {}
            current[part] = existing
        if not isinstance(existing, dict):
            raise ExecutionError(
                f"Hermes configの `{'.'.join(parts[:-1])}` がmappingではないため、"
                f"安全に `{dotted_key}` を設定できません。"
            )
        current = existing
    current[parts[-1]] = list(value)


def _write_structured_config(
    profile_name: str,
    values: dict[str, list[str]],
    *,
    dry_run: bool,
) -> None:
    if not values:
        return
    path = _profile_home(profile_name) / "config.yaml"
    for key, value in values.items():
        _log(f"→ 配列設定: {key}\n  {value}")
    if dry_run:
        return

    # Builderのbootstrap CLIは標準ライブラリのみ。ここはHermes導入後に限り、
    # Hermes自身が依存するPyYAMLを使う。欠落時はpolicyを文字列へ劣化させず停止する。
    try:
        import yaml  # type: ignore[import-not-found]
    except ImportError as exc:
        raise ExecutionError(
            "Hermes付属のPyYAMLが見つからず、tool policyを安全に保存できません。"
            "Hermesを修復してから再実行してください。"
        ) from exc

    config: object = {}
    if path.exists():
        try:
            with path.open(encoding="utf-8") as handle:
                config = yaml.safe_load(handle) or {}
        except (OSError, UnicodeError, yaml.YAMLError) as exc:
            raise ExecutionError(f"Hermes configを安全に読めません: {path}: {exc}") from exc
    if not isinstance(config, dict):
        raise ExecutionError(f"Hermes configのrootがmappingではありません: {path}")

    for key, value in values.items():
        _set_nested_mapping(config, key, value)
    try:
        rendered = yaml.safe_dump(
            config,
            allow_unicode=True,
            default_flow_style=False,
            sort_keys=False,
        )
        _atomic_write_text(path, rendered)
    except (OSError, UnicodeError, yaml.YAMLError) as exc:
        raise ExecutionError(f"Hermes configを安全に保存できません: {path}: {exc}") from exc
    _log(f"✓ 配列tool policyを保存: {path}")


def _write_soul(plan: BuildPlan, created_profile: bool, options: ApplyOptions) -> None:
    path = _profile_home(plan.answers.profile_name) / "SOUL.md"
    proposed = path.with_name("SOUL.proposed.md")
    if options.dry_run:
        _log(f"→ 専用SOULを生成\n  {path}")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    content = render_soul(plan)
    if path.exists() and not created_profile and not options.force_profile:
        _atomic_write_text(proposed, content)
        _log(f"⚠ 既存SOULは保持し、提案版を保存しました: {proposed}")
        return
    if path.exists() and options.force_profile:
        backup = _soul_backup_path(path)
        shutil.copy2(path, backup)
        os.chmod(backup, 0o600)
        _log(f"→ 既存SOULを退避: {backup}")
    _atomic_write_text(path, content)
    _log(f"✓ 専用SOULを生成: {path}")


def _should_skip(command: CommandSpec, options: ApplyOptions) -> str | None:
    if command.interactive and options.non_interactive:
        return "non-interactive mode"
    if options.non_interactive and command.category in {"gateway_service", "gateway_status"}:
        return "gateway authentication pending"
    if options.skip_provider and command.category == "provider":
        return "--skip-provider"
    if options.skip_gateways and command.category.startswith("gateway"):
        return "--skip-gateways"
    if options.skip_mcp and command.category == "mcp":
        return "--skip-mcp"
    if options.no_service and command.category == "gateway_service":
        return "--no-service"
    return None


def apply_plan(plan: BuildPlan, options: ApplyOptions) -> None:
    if not options.dry_run and shutil.which("hermes") is None:
        raise ExecutionError(
            "hermesコマンドが見つかりません。先にinstall.shを実行するか、PATHを再読み込みしてください。"
        )

    created_profile = options.dry_run
    profile_create = plan.commands[0]
    if options.dry_run:
        _run(profile_create, dry_run=True)
    elif _profile_exists(plan.answers.profile_name):
        _log(f"→ 既存profileを再利用: {plan.answers.profile_name}")
        created_profile = False
    else:
        _run(profile_create, dry_run=False)
        created_profile = True

    _write_soul(plan, created_profile, options)

    structured_values = {
        key: value
        for key, value in plan.config_values.items()
        if isinstance(value, list)
        and not (options.skip_gateways and key.startswith("platform_toolsets."))
    }
    _write_structured_config(
        plan.answers.profile_name,
        structured_values,
        dry_run=options.dry_run,
    )

    for command in plan.commands[1:]:
        reason = _should_skip(command, options)
        if reason:
            _log(f"↷ スキップ ({reason}): {command.description}")
            continue
        _run(command, dry_run=options.dry_run)

    if options.non_interactive and any(command.interactive for command in plan.commands):
        _log(
            "\n未完了: provider・gateway・MCPの認証は対話端末で同じplanをapplyして完了してください。"
        )
