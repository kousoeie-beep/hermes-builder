from __future__ import annotations

import argparse
import json
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

from hermes_builder import __version__
from hermes_builder.catalog import GATEWAYS, INTEGRATIONS, USE_CASES
from hermes_builder.completions import completion_for
from hermes_builder.executor import ApplyOptions, ExecutionError, apply_plan
from hermes_builder.interview import InterviewCancelled, confirm, load_answers, run_interview
from hermes_builder.models import Answers, validate_profile_name
from hermes_builder.planner import build_plan
from hermes_builder.render import render_summary
from hermes_builder.storage import default_plan_path, read_plan, write_plan


def _add_apply_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--dry-run", action="store_true", help="変更せず実行予定を表示")
    parser.add_argument("--non-interactive", action="store_true", help="対話ステップをスキップ")
    parser.add_argument("--force-profile", action="store_true", help="既存SOULを退避して更新")
    parser.add_argument("--skip-provider", action="store_true", help="provider wizardを起動しない")
    parser.add_argument(
        "--skip-gateways",
        action="store_true",
        help="gatewayの認証wizard・service操作・疎通確認を行わない（安全policyは適用）",
    )
    parser.add_argument("--skip-mcp", action="store_true", help="MCP pickerを起動しない")
    parser.add_argument("--no-service", action="store_true", help="gatewayを常駐service化しない")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="hermes-builder",
        description="ヒアリングから専用Hermes Agentを安全に構築します。",
        epilog=(
            "例:\n"
            "  hermes-builder setup\n"
            "  hermes-builder plan --answers examples/research-operator.json\n"
            "  hermes-builder apply ~/.config/hermes-builder/plans/my-hermes.json --dry-run"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    subparsers = parser.add_subparsers(dest="command", required=True)

    setup = subparsers.add_parser("setup", help="ヒアリングからplan生成・適用まで実行")
    setup.add_argument("--answers", type=Path, help="回答JSONを読み込む")
    setup.add_argument("--plan-out", type=Path, help="plan保存先")
    setup.add_argument("--yes", action="store_true", help="plan確認後の実行確認を省略")
    _add_apply_options(setup)

    plan = subparsers.add_parser("plan", help="ヒアリングしてplanだけ生成")
    plan.add_argument("--answers", type=Path, help="回答JSONを読み込む")
    plan.add_argument("--out", type=Path, help="plan保存先")
    plan.add_argument("--non-interactive", action="store_true", help="回答JSONを必須にする")

    apply_parser = subparsers.add_parser("apply", help="保存済みplanを適用")
    apply_parser.add_argument("plan", type=Path, help="plan JSON")
    _add_apply_options(apply_parser)

    doctor = subparsers.add_parser("doctor", help="構築済みprofileを診断")
    doctor.add_argument("profile", help="Hermes profile名")
    doctor.add_argument("--deep", action="store_true", help="gatewayもdeep check")

    catalog = subparsers.add_parser("catalog", help="用途・gateway・連携候補を表示")
    catalog.add_argument("kind", choices=("use-cases", "gateways", "integrations"))
    catalog.add_argument("--json", action="store_true", help="JSONで出力")

    completion = subparsers.add_parser("completion", help="shell completionを出力")
    completion.add_argument("shell", choices=("bash", "zsh", "fish"))
    return parser


def _answers(args: argparse.Namespace) -> Answers:
    if args.answers:
        return load_answers(args.answers)
    if getattr(args, "non_interactive", False):
        raise ValueError("--non-interactiveでは--answersが必要です")
    if not sys.stdin.isatty():
        raise ValueError("対話端末ではありません。--answers <JSON> を指定してください")
    return run_interview()


def _options(args: argparse.Namespace) -> ApplyOptions:
    return ApplyOptions(
        dry_run=args.dry_run,
        non_interactive=args.non_interactive,
        force_profile=args.force_profile,
        skip_provider=args.skip_provider,
        skip_gateways=args.skip_gateways,
        skip_mcp=args.skip_mcp,
        no_service=args.no_service,
    )


def _plan_command(args: argparse.Namespace) -> int:
    plan = build_plan(_answers(args))
    destination = args.out or default_plan_path(plan.answers.profile_name)
    write_plan(plan, destination)
    print(render_summary(plan))
    print(f"\nPlan: {destination}")
    return 0


def _setup_command(args: argparse.Namespace) -> int:
    plan = build_plan(_answers(args))
    destination = args.plan_out or default_plan_path(plan.answers.profile_name)
    print(render_summary(plan))
    if args.dry_run:
        print("\nDry-runのためplanは保存していません。")
    else:
        write_plan(plan, destination)
        print(f"\nPlanを保存しました: {destination}")
    if not args.yes and not args.non_interactive and not confirm("この内容で構築を始めますか"):
        print("構築は行っていません。planを編集してからapplyできます。")
        return 0
    apply_plan(plan, _options(args))
    print(f"\n✓ Hermes構築フローが完了しました: {plan.answers.profile_name}")
    return 0


def _apply_command(args: argparse.Namespace) -> int:
    plan = read_plan(args.plan)
    print(render_summary(plan))
    apply_plan(plan, _options(args))
    print(f"\n✓ Plan適用が完了しました: {plan.answers.profile_name}")
    return 0


def _doctor_command(args: argparse.Namespace) -> int:
    profile = validate_profile_name(args.profile)
    if shutil.which("hermes") is None:
        raise ExecutionError("hermesコマンドが見つかりません")
    commands = [("hermes", "-p", profile, "doctor")]
    if args.deep:
        commands.append(("hermes", "-p", profile, "status", "--deep"))
    for command in commands:
        print(f"→ {shlex.join(command)}", file=sys.stderr)
        result = subprocess.run(command, check=False)
        if result.returncode != 0:
            return result.returncode
    return 0


def _catalog_command(args: argparse.Namespace) -> int:
    choices = {
        "use-cases": USE_CASES,
        "gateways": GATEWAYS,
        "integrations": INTEGRATIONS,
    }[args.kind]
    rows = [choice.__dict__ for choice in choices]
    if args.json:
        print(json.dumps(rows, ensure_ascii=False, indent=2))
    else:
        for choice in choices:
            print(f"{choice.key:20} {choice.label:18} {choice.description}")
    return 0


def main(argv: list[str] | None = None) -> None:
    arguments = list(sys.argv[1:] if argv is None else argv)
    if not arguments:
        arguments = ["setup"]
    parser = build_parser()
    args = parser.parse_args(arguments)
    try:
        if args.command == "setup":
            code = _setup_command(args)
        elif args.command == "plan":
            code = _plan_command(args)
        elif args.command == "apply":
            code = _apply_command(args)
        elif args.command == "doctor":
            code = _doctor_command(args)
        elif args.command == "catalog":
            code = _catalog_command(args)
        elif args.command == "completion":
            print(completion_for(args.shell), end="")
            code = 0
        else:
            parser.error(f"unknown command: {args.command}")
            return
    except InterviewCancelled:
        print("\nキャンセルしました。変更は行っていません。", file=sys.stderr)
        code = 130
    except (ExecutionError, ValueError) as exc:
        print(f"✗ {exc}", file=sys.stderr)
        code = 2
    raise SystemExit(code)
