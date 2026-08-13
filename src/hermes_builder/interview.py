from __future__ import annotations

import json
import re
import sys
from pathlib import Path

from hermes_builder.catalog import (
    ACCESS_SCOPES,
    AUTONOMY,
    DEPLOYMENTS,
    GATEWAYS,
    INTEGRATIONS,
    PROVIDERS,
    USE_CASES,
    Choice,
)
from hermes_builder.models import Answers, RESERVED_PROFILE_NAMES
from hermes_builder.json_safety import reject_excessive_nesting


class InterviewCancelled(Exception):
    """Raised when the user cancels interactive onboarding."""


MAX_ANSWERS_BYTES = 1_048_576


def load_answers(path: Path) -> Answers:
    try:
        with path.open("rb") as handle:
            payload = handle.read(MAX_ANSWERS_BYTES + 1)
    except FileNotFoundError as exc:
        raise ValueError(f"回答ファイルが見つかりません: {path}") from exc
    except OSError as exc:
        raise ValueError(f"回答ファイルを読めません: {path}: {exc}") from exc
    if len(payload) > MAX_ANSWERS_BYTES:
        raise ValueError("回答ファイルが大きすぎます（上限1 MiB）")
    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError("回答ファイルはUTF-8で保存してください") from exc
    reject_excessive_nesting(text)
    try:
        data = json.loads(text)
    except (json.JSONDecodeError, RecursionError) as exc:
        raise ValueError(f"回答ファイルがJSONとして不正です: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError("回答ファイルのrootはJSON objectにしてください")
    return Answers.from_mapping(data)


def _read(prompt: str) -> str:
    try:
        return input(prompt).strip()
    except (EOFError, KeyboardInterrupt) as exc:
        raise InterviewCancelled from exc


def ask_text(prompt: str, default: str = "", required: bool = True) -> str:
    suffix = f" [{default}]" if default else ""
    while True:
        value = _read(f"{prompt}{suffix}: ") or default
        if value or not required:
            return value
        print("  入力が必要です。", file=sys.stderr)


def ask_single(prompt: str, choices: tuple[Choice, ...], default: int = 1) -> str:
    print(f"\n{prompt}")
    for index, choice in enumerate(choices, start=1):
        marker = " (推奨)" if index == default else ""
        print(f"  {index}. {choice.label}{marker} — {choice.description}")
    while True:
        raw = _read(f"番号を選択 [{default}]: ") or str(default)
        if raw.isdigit() and 1 <= int(raw) <= len(choices):
            return choices[int(raw) - 1].key
        print("  表示されている番号を1つ入力してください。", file=sys.stderr)


def ask_multi(prompt: str, choices: tuple[Choice, ...]) -> tuple[str, ...]:
    print(f"\n{prompt}")
    for index, choice in enumerate(choices, start=1):
        print(f"  {index}. {choice.label} — {choice.description}")
    print("  複数選択はカンマ区切り。不要ならEnter。")
    while True:
        raw = _read("番号を選択: ")
        if not raw:
            return ()
        parts = [part.strip() for part in raw.split(",") if part.strip()]
        if all(part.isdigit() and 1 <= int(part) <= len(choices) for part in parts):
            selected = []
            for part in parts:
                key = choices[int(part) - 1].key
                if key not in selected:
                    selected.append(key)
            return tuple(selected)
        print("  例: 1,3,5 の形式で入力してください。", file=sys.stderr)


def confirm(prompt: str, default: bool = False) -> bool:
    suffix = "Y/n" if default else "y/N"
    while True:
        raw = _read(f"{prompt} [{suffix}]: ").lower()
        if not raw:
            return default
        if raw in {"y", "yes"}:
            return True
        if raw in {"n", "no"}:
            return False
        print("  y または n を入力してください。", file=sys.stderr)


def run_interview() -> Answers:
    print("\nHermes Builder — あなたに合うHermesを設計します")
    print("秘密値はここでは聞きません。認証は後で各公式ウィザードから行います。\n")

    display_name = ask_text("Hermesの表示名", "My Hermes")
    default_slug = "my-hermes"
    while True:
        profile_name = ask_text("profile名（英小文字・数字・ハイフン）", default_slug).lower()
        if (
            re.fullmatch(r"[a-z0-9][a-z0-9-]{0,62}", profile_name)
            and profile_name not in RESERVED_PROFILE_NAMES
        ):
            break
        print("  英小文字・数字・ハイフンだけを使ってください。", file=sys.stderr)

    purpose = ask_text("このHermesに任せたい一番重要な仕事")
    use_cases = ask_multi("主な用途を選んでください", USE_CASES)
    if not use_cases:
        use_cases = ("research",)
    autonomy = ask_single("どこまで自律的に動かしますか", AUTONOMY, default=1)
    access_scope = ask_single("誰がこのHermesを使いますか", ACCESS_SCOPES, default=1)
    deployment = ask_single("どこで動かしますか", DEPLOYMENTS, default=1)
    gateways = ask_multi("指示を出したい媒体を選んでください", GATEWAYS)
    integrations = ask_multi("接続したい外部サービスを選んでください", INTEGRATIONS)
    provider_mode = ask_single("LLM providerはどうしますか", PROVIDERS, default=5)
    workspace = ask_text("主に作業するフォルダ（後でも変更可）", required=False)
    persona_style = ask_single(
        "話し方を選んでください",
        (
            Choice("concise", "簡潔", "結論と次の行動を短く返す"),
            Choice("collaborative", "相棒型", "壁打ちしながら一緒に決める"),
            Choice("formal", "フォーマル", "業務向けに丁寧に返す"),
        ),
        default=2,
    )

    # 対話入力もanswers JSONと同じvalidation pathへ通す。
    return Answers.from_mapping(
        {
            "profile_name": profile_name,
            "display_name": display_name,
            "purpose": purpose,
            "use_cases": use_cases,
            "autonomy": autonomy,
            "access_scope": access_scope,
            "deployment": deployment,
            "gateways": gateways,
            "integrations": integrations,
            "provider_mode": provider_mode,
            "workspace": workspace,
            "persona_style": persona_style,
        }
    )
