from __future__ import annotations

from dataclasses import asdict, dataclass, field
import re
from typing import Any


VALID_USE_CASES = {
    "research",
    "software",
    "operations",
    "content",
    "sales_support",
    "personal_assistant",
}
VALID_AUTONOMY = {"interactive", "scheduled_review", "autonomous_limited"}
VALID_ACCESS = {"owner", "trusted_team", "public"}
VALID_DEPLOYMENTS = {"laptop", "always_on", "server"}
VALID_PROVIDERS = {"nous", "oauth", "api_key", "local", "decide_later"}
VALID_GATEWAYS = {
    "telegram", "discord", "slack", "google_chat", "whatsapp",
    "whatsapp_cloud", "signal", "sms", "email", "homeassistant",
    "mattermost", "matrix", "dingtalk", "feishu", "wecom",
    "wecom_callback", "weixin", "bluebubbles", "photon", "qqbot",
    "yuanbao", "teams", "line", "ntfy", "raft", "irc", "buzz",
    "simplex", "a2a", "webhook", "api_server",
}
VALID_INTEGRATIONS = {
    "github", "google_workspace", "microsoft_365", "notion", "linear", "n8n",
    "database", "observability", "custom",
}
CONTROL_CHARACTERS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
SECRET_VALUE_PATTERNS = (
    re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b"),
    re.compile(r"\bsk-(?:proj-)?[A-Za-z0-9_-]{16,}\b"),
    re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\b"),
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    re.compile(r"\bBearer\s+[A-Za-z0-9._~-]{20,}\b", re.IGNORECASE),
)
RESERVED_PROFILE_NAMES = {
    "default", "hermes", "test", "tmp", "root", "sudo", "model",
    "gateway", "mcp", "install", "start", "status",
}


def validate_profile_name(value: object) -> str:
    profile_name = str(value).strip().lower()
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,62}", profile_name):
        raise ValueError("profile_nameは英小文字・数字・ハイフンで指定してください")
    if profile_name in RESERVED_PROFILE_NAMES:
        raise ValueError(f"予約済みのprofile_nameです: {profile_name}")
    return profile_name


def _ordered_unique(values: object) -> tuple[str, ...]:
    if not isinstance(values, (list, tuple)):
        raise ValueError("複数選択項目はJSON arrayで指定してください")
    return tuple(dict.fromkeys(str(item) for item in values))


def _validate_free_text(key: str, value: object) -> str:
    text = str(value)
    if len(text) > 1000:
        raise ValueError(f"{key}が長すぎます（最大1000文字）")
    if CONTROL_CHARACTERS.search(text):
        raise ValueError(f"{key}にterminal表示を壊す制御文字を含めないでください")
    if any(pattern.search(text) for pattern in SECRET_VALUE_PATTERNS):
        raise ValueError(f"{key}に秘密値らしい文字列を保存しないでください")
    return text


@dataclass(frozen=True)
class Answers:
    profile_name: str
    display_name: str
    purpose: str
    use_cases: tuple[str, ...]
    autonomy: str
    access_scope: str
    deployment: str
    gateways: tuple[str, ...] = ()
    integrations: tuple[str, ...] = ()
    provider_mode: str = "decide_later"
    workspace: str = ""
    language: str = "ja"
    persona_style: str = "concise"

    @classmethod
    def from_mapping(cls, data: dict[str, Any]) -> "Answers":
        allowed_keys = {
            "profile_name", "display_name", "purpose", "use_cases", "autonomy",
            "access_scope", "deployment", "gateways", "integrations",
            "provider_mode", "workspace", "language", "persona_style",
        }
        secret_markers = ("token", "secret", "password", "api_key", "credential")
        unsafe_keys = [key for key in data if any(marker in key.lower() for marker in secret_markers)]
        if unsafe_keys:
            raise ValueError(
                "回答ファイルへ秘密値を保存しないでください。検出項目: "
                + ", ".join(sorted(unsafe_keys))
            )
        unknown_keys = sorted(set(data) - allowed_keys)
        if unknown_keys:
            raise ValueError(
                "回答ファイルに未対応の項目があります: " + ", ".join(unknown_keys)
            )
        required = (
            "profile_name",
            "display_name",
            "purpose",
            "use_cases",
            "autonomy",
            "access_scope",
            "deployment",
        )
        missing = [key for key in required if key not in data]
        if missing:
            raise ValueError(f"回答ファイルに必須項目がありません: {', '.join(missing)}")

        use_cases = _ordered_unique(data["use_cases"])
        unknown_use_cases = sorted(set(use_cases) - VALID_USE_CASES)
        if unknown_use_cases:
            raise ValueError(f"未対応の用途です: {', '.join(unknown_use_cases)}")

        autonomy = str(data["autonomy"])
        access_scope = str(data["access_scope"])
        deployment = str(data["deployment"])
        provider_mode = str(data.get("provider_mode", "decide_later"))
        if autonomy not in VALID_AUTONOMY:
            raise ValueError(f"未対応の自律度です: {autonomy}")
        if access_scope not in VALID_ACCESS:
            raise ValueError(f"未対応の利用範囲です: {access_scope}")
        if deployment not in VALID_DEPLOYMENTS:
            raise ValueError(f"未対応の設置場所です: {deployment}")
        if provider_mode not in VALID_PROVIDERS:
            raise ValueError(f"未対応のprovider設定方法です: {provider_mode}")

        language = str(data.get("language", "ja"))
        persona_style = str(data.get("persona_style", "concise"))
        if language not in {"ja", "en"}:
            raise ValueError(f"未対応の言語です: {language}")
        if persona_style not in {"concise", "collaborative", "formal"}:
            raise ValueError(f"未対応の話し方です: {persona_style}")

        profile_name = validate_profile_name(data["profile_name"])
        display_name = _validate_free_text("display_name", data["display_name"]).strip()
        purpose = _validate_free_text("purpose", data["purpose"]).strip()
        workspace = _validate_free_text("workspace", data.get("workspace", "")).strip()
        if not display_name or not purpose:
            raise ValueError("display_nameとpurposeは空にできません")

        gateways = _ordered_unique(data.get("gateways", ()))
        unknown_gateways = sorted(set(gateways) - VALID_GATEWAYS)
        if unknown_gateways:
            raise ValueError(f"未対応のgatewayです: {', '.join(unknown_gateways)}")
        integrations = _ordered_unique(data.get("integrations", ()))
        unknown_integrations = sorted(set(integrations) - VALID_INTEGRATIONS)
        if unknown_integrations:
            raise ValueError(f"未対応のintegrationです: {', '.join(unknown_integrations)}")

        return cls(
            profile_name=profile_name,
            display_name=display_name,
            purpose=purpose,
            use_cases=use_cases,
            autonomy=autonomy,
            access_scope=access_scope,
            deployment=deployment,
            gateways=gateways,
            integrations=integrations,
            provider_mode=provider_mode,
            workspace=workspace,
            language=language,
            persona_style=persona_style,
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class CommandSpec:
    description: str
    argv: tuple[str, ...]
    interactive: bool = False
    optional: bool = False
    category: str = "configuration"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class BuildPlan:
    schema_version: int
    generated_at: str
    answers: Answers
    cli_toolsets: list[str]
    gateway_toolsets: list[str]
    gateway_denied_toolsets: list[str]
    config_values: dict[str, str | list[str]]
    mcp_recommendations: list[str]
    notes: list[str]
    commands: list[CommandSpec] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "generated_at": self.generated_at,
            "answers": self.answers.to_dict(),
            "cli_toolsets": self.cli_toolsets,
            "gateway_toolsets": self.gateway_toolsets,
            "gateway_denied_toolsets": self.gateway_denied_toolsets,
            "config_values": self.config_values,
            "mcp_recommendations": self.mcp_recommendations,
            "notes": self.notes,
            "commands": [command.to_dict() for command in self.commands],
        }

    @classmethod
    def from_mapping(cls, data: dict[str, Any]) -> "BuildPlan":
        if int(data.get("schema_version", 0)) != 1:
            raise ValueError("未対応のplan schemaです")
        return cls(
            schema_version=1,
            generated_at=str(data["generated_at"]),
            answers=Answers.from_mapping(data["answers"]),
            cli_toolsets=list(data["cli_toolsets"]),
            gateway_toolsets=list(data["gateway_toolsets"]),
            gateway_denied_toolsets=list(data["gateway_denied_toolsets"]),
            config_values={
                str(key): (
                    [str(item) for item in value]
                    if isinstance(value, list)
                    else str(value)
                )
                for key, value in data["config_values"].items()
            },
            mcp_recommendations=list(data["mcp_recommendations"]),
            notes=list(data["notes"]),
            commands=[
                CommandSpec(
                    description=str(command["description"]),
                    argv=tuple(str(item) for item in command["argv"]),
                    interactive=bool(command.get("interactive", False)),
                    optional=bool(command.get("optional", False)),
                    category=str(command.get("category", "configuration")),
                )
                for command in data.get("commands", [])
            ],
        )
