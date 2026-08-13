from __future__ import annotations

from datetime import datetime, timezone
from hermes_builder.catalog import MCP_RECOMMENDATIONS, TOOLSETS_BY_USE_CASE
from hermes_builder.models import Answers, BuildPlan, CommandSpec


BASE_TOOLSETS = {"skills", "todo", "clarify"}
DANGEROUS_GATEWAY_TOOLSETS = {
    "terminal",
    "file",
    "code_execution",
    "computer_use",
    "cronjob",
    "delegation",
}

# Hermes v2026.8.3で `hermes tools --platform` が直接扱うbuilt-in platform。
# Teams/LINE等のplugin platformはgateway wizardでは設定できるが、tool policyは
# dedicated profileのglobal denyで安全側へ倒す。
TOOL_POLICY_PLATFORMS = {
    "telegram", "discord", "slack", "whatsapp", "whatsapp_cloud", "signal",
    "bluebubbles", "email", "homeassistant", "mattermost", "matrix",
    "dingtalk", "feishu", "wecom", "wecom_callback", "weixin", "qqbot",
    "yuanbao", "webhook", "api_server",
}


def build_plan(answers: Answers) -> BuildPlan:
    cli_toolsets = set(BASE_TOOLSETS)
    for use_case in answers.use_cases:
        cli_toolsets.update(TOOLSETS_BY_USE_CASE[use_case])

    if answers.autonomy in {"scheduled_review", "autonomous_limited"}:
        cli_toolsets.add("cronjob")
    if answers.autonomy == "autonomous_limited":
        cli_toolsets.add("delegation")

    gateway_toolsets = set(cli_toolsets)
    gateway_denied: set[str] = set()
    notes = ["秘密値はplanやログへ保存せず、Hermes公式ウィザードで入力する。"]

    if answers.access_scope == "trusted_team":
        gateway_denied = set(DANGEROUS_GATEWAY_TOOLSETS)
        gateway_toolsets.difference_update(gateway_denied)
        notes.append("チーム経由ではterminal・file・code execution等を初期無効化する。")
    elif answers.access_scope == "public":
        gateway_toolsets = {"web", "skills", "clarify", "todo"}
        gateway_denied = set(DANGEROUS_GATEWAY_TOOLSETS) | {"memory", "session_search", "browser"}
        notes.append("外部ユーザー向けgatewayは最小toolsetから開始する。")
    else:
        notes.append("自分専用でもgateway利用者allowlistまたはDM pairingを必須にする。")

    if gateway_denied:
        # 共有gateway用profileではglobal denyがCLIにも効くため、summaryと実際の
        # effective toolsetsを一致させる。
        cli_toolsets = set(gateway_toolsets)

    if answers.gateways:
        notes.append("gatewayをOSのuser serviceとして常駐化する（--no-serviceで省略可）。")
    if answers.deployment == "server":
        notes.append("公開portは直接露出せず、TLS終端と認証を持つproxyまたはtunnelを使う。")
    if "teams" in answers.gateways:
        notes.append("Teamsは公開HTTPS webhookとMicrosoft側のBot登録が別途必要。")
    if "line" in answers.gateways:
        notes.append("LINEはMessaging APIチャネルと公開HTTPS webhookが必要。")
    notes.append(f"provider設定方式: {answers.provider_mode}")

    mcp_recommendations: list[str] = []
    for integration in answers.integrations:
        mcp_recommendations.extend(MCP_RECOMMENDATIONS.get(integration, []))

    config_values: dict[str, str | list[str]] = {
        "approvals.mode": "smart",
        "approvals.cron_mode": "deny",
        "approvals.destructive_slash_confirm": "true",
        "display.file_mutation_verifier": "true",
    }
    if gateway_denied:
        # このprofileは共有gateway用として最小権限に固定する。plugin platformにも
        # 効くglobal denyを使うため、CLIでも同じ高権限toolsetは無効になる。
        config_values["agent.disabled_toolsets"] = sorted(gateway_denied)
        notes.append("共有用profileでは高権限toolsetをprofile全体で無効化する。")

    # Hermes v2026.8.3の `hermes tools --platform` はbuilt-in platformだけを
    # 受け付ける。plugin adapterはprofile configへ明示allowlistを書き、default
    # toolsetの自動展開で意図しない権限が増えないようにする。
    for gateway in answers.gateways:
        if gateway not in TOOL_POLICY_PLATFORMS:
            config_values[f"platform_toolsets.{gateway}"] = sorted(gateway_toolsets)

    profile = answers.profile_name
    commands = [
        CommandSpec(
            "専用Hermes profileを作る",
            ("hermes", "profile", "create", profile),
        )
    ]
    for key, value in config_values.items():
        if isinstance(value, list):
            continue
        commands.append(
            CommandSpec(
                f"安全設定: {key}",
                ("hermes", "-p", profile, "config", "set", key, value),
            )
        )
    if cli_toolsets:
        commands.append(
            CommandSpec(
                "CLI toolsetsを有効化",
                ("hermes", "-p", profile, "tools", "enable", *sorted(cli_toolsets)),
            )
        )
    for gateway in answers.gateways:
        if gateway not in TOOL_POLICY_PLATFORMS:
            notes.append(
                f"{gateway}はplugin adapterのため、configへ明示allowlistを適用する。"
            )
            continue
        if gateway_toolsets:
            commands.append(
                CommandSpec(
                    f"{gateway}のtoolsetsを有効化",
                    (
                        "hermes",
                        "-p",
                        profile,
                        "tools",
                        "enable",
                        "--platform",
                        gateway,
                        *sorted(gateway_toolsets),
                    ),
                    category="gateway_policy",
                )
            )
        if gateway_denied:
            commands.append(
                CommandSpec(
                    f"{gateway}の高権限toolsetsを無効化",
                    (
                        "hermes",
                        "-p",
                        profile,
                        "tools",
                        "disable",
                        "--platform",
                        gateway,
                        *sorted(gateway_denied),
                    ),
                    category="gateway_policy",
                )
            )
    if answers.provider_mode == "nous":
        commands.append(
            CommandSpec(
                "Nous PortalをOAuth設定",
                ("hermes", "-p", profile, "setup", "--portal"),
                interactive=True,
                category="provider",
            )
        )
    else:
        commands.append(
            CommandSpec(
                f"LLM providerを設定 ({answers.provider_mode})",
                ("hermes", "-p", profile, "model"),
                interactive=True,
                category="provider",
            )
        )
    if answers.gateways:
        commands.append(
            CommandSpec(
                "選択したgatewayを設定",
                ("hermes", "-p", profile, "gateway", "setup"),
                interactive=True,
                category="gateway_setup",
            )
        )
    if answers.integrations:
        commands.append(
            CommandSpec(
                "必要なMCPを選択・認証",
                ("hermes", "-p", profile, "mcp", "picker"),
                interactive=True,
                category="mcp",
            )
        )
    if answers.gateways:
        commands.extend(
            (
                CommandSpec(
                    "gatewayをuser serviceとして登録",
                    ("hermes", "-p", profile, "gateway", "install"),
                    category="gateway_service",
                ),
                CommandSpec(
                    "gateway serviceを起動",
                    ("hermes", "-p", profile, "gateway", "start"),
                    category="gateway_service",
                ),
            )
        )
    commands.append(
        CommandSpec(
            "Hermes全体を診断",
            ("hermes", "-p", profile, "doctor"),
            category="diagnostic",
        )
    )
    commands.append(
        CommandSpec(
            "依存関係をsecurity audit",
            ("hermes", "-p", profile, "security", "audit", "--fail-on", "critical"),
            category="diagnostic",
        )
    )
    if answers.gateways:
        commands.append(
            CommandSpec(
                "gatewayをdeep check",
                ("hermes", "-p", profile, "status", "--deep"),
                optional=True,
                category="gateway_status",
            )
        )

    return BuildPlan(
        schema_version=1,
        generated_at=datetime.now(timezone.utc).isoformat(),
        answers=answers,
        cli_toolsets=sorted(cli_toolsets),
        gateway_toolsets=sorted(gateway_toolsets),
        gateway_denied_toolsets=sorted(gateway_denied),
        config_values=config_values,
        mcp_recommendations=mcp_recommendations,
        notes=notes,
        commands=commands,
    )
