from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile

from hermes_builder.models import Answers, BuildPlan
from hermes_builder.json_safety import reject_excessive_nesting
from hermes_builder.planner import build_plan


MAX_PLAN_BYTES = 2_097_152


def default_state_dir() -> Path:
    configured = os.environ.get("HERMES_BUILDER_STATE_HOME")
    return Path(configured).expanduser() if configured else Path.home() / ".config" / "hermes-builder"


def default_plan_path(profile_name: str) -> Path:
    return default_state_dir() / "plans" / f"{profile_name}.json"


def write_plan(plan: BuildPlan, path: Path) -> None:
    parent_existed = path.parent.exists()
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    if not parent_existed:
        os.chmod(path.parent, 0o700)
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
            json.dump(plan.to_dict(), handle, ensure_ascii=False, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()


def read_plan(path: Path) -> BuildPlan:
    try:
        with path.open("rb") as handle:
            payload = handle.read(MAX_PLAN_BYTES + 1)
    except FileNotFoundError as exc:
        raise ValueError(f"planが見つかりません: {path}") from exc
    except OSError as exc:
        raise ValueError(f"planを読めません: {path}: {exc}") from exc
    if len(payload) > MAX_PLAN_BYTES:
        raise ValueError("planが大きすぎます（上限2 MiB）")
    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError("planはUTF-8で保存してください") from exc
    reject_excessive_nesting(text)
    try:
        data = json.loads(text)
    except (json.JSONDecodeError, RecursionError) as exc:
        raise ValueError(f"plan JSONが不正です: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError("planのrootはJSON objectにしてください")
    if int(data.get("schema_version", 0)) != 1:
        raise ValueError("未対応のplan schemaです")
    answers_data = data.get("answers")
    if not isinstance(answers_data, dict):
        raise ValueError("planにanswers objectがありません")

    # commandsやpolicyは監査表示用の派生データ。JSONから実行せず、検証済みの
    # answersだけをsource of truthとして毎回再生成し、plan改ざんによる任意実行を防ぐ。
    plan = build_plan(Answers.from_mapping(answers_data))
    plan.generated_at = str(data.get("generated_at", plan.generated_at))
    return plan
