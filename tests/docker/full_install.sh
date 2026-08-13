#!/usr/bin/env bash
set -euo pipefail

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
answers="$project_root/examples/research-operator.json"
profile="research-operator"
expected_hermes_commit="3c27eb6234bf91b8ceee9e9071591b31e9b148cb"
export PATH="$HOME/.local/bin:$HOME/.hermes/bin:$PATH"

assert_install() {
  test -x "$HOME/.local/bin/hermes-builder"
  command -v hermes >/dev/null
  command -v hermes-builder >/dev/null
  test "$(git -C "$HOME/.hermes/hermes-agent" rev-parse HEAD)" = "$expected_hermes_commit"
  test -f "$HOME/.hermes/profiles/$profile/SOUL.md"
  test -f "$HOME/.hermes/profiles/$profile/config.yaml"
  test -f "$HOME/.config/hermes-builder/plans/$profile.json"
  test "$(stat -c '%a' "$HOME/.hermes/profiles/$profile/SOUL.md")" = "600"
  test "$(stat -c '%a' "$HOME/.hermes/profiles/$profile/config.yaml")" = "600"
  test "$(stat -c '%a' "$HOME/.config/hermes-builder/plans/$profile.json")" = "600"
  grep -q "複数ソースを調査" "$HOME/.hermes/profiles/$profile/SOUL.md"
  hermes-builder --version | grep -q "0.1.2"
  hermes profile show "$profile" >/dev/null
  "$HOME/.hermes/hermes-agent/venv/bin/python" - \
    "$HOME/.hermes/profiles/$profile/config.yaml" \
    "$HOME/.config/hermes-builder/plans/$profile.json" <<'PY'
import json
import sys
from pathlib import Path

import yaml
from hermes_cli.tools_config import _get_platform_tools

config = yaml.safe_load(Path(sys.argv[1]).read_text(encoding="utf-8"))
plan = json.loads(Path(sys.argv[2]).read_text(encoding="utf-8"))
denied = config["agent"]["disabled_toolsets"]
slack = config["platform_toolsets"]["slack"]
teams = config["platform_toolsets"]["teams"]
assert isinstance(denied, list), type(denied)
assert isinstance(slack, list), type(slack)
assert isinstance(teams, list), type(teams)
assert {"terminal", "file", "code_execution", "computer_use"} <= set(denied)
assert "no_mcp" in slack
assert "no_mcp" in teams
expected = set(plan["gateway_toolsets"])
assert set(_get_platform_tools(config, "slack")) == expected
assert set(_get_platform_tools(config, "teams")) == expected
PY
}

seed_dummy_mcp() {
  "$HOME/.hermes/hermes-agent/venv/bin/python" - \
    "$HOME/.hermes/profiles/$profile/config.yaml" <<'PY'
import sys
from pathlib import Path

import yaml

path = Path(sys.argv[1])
config = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
config.setdefault("mcp_servers", {})["github"] = {
    "command": "unused-dummy-command",
    "enabled": True,
}
path.write_text(
    yaml.safe_dump(config, allow_unicode=True, sort_keys=False),
    encoding="utf-8",
)
PY
}

echo "== first install: official Hermes + Builder =="
bash "$project_root/install.sh" \
  --source-dir "$project_root" \
  --answers "$answers" \
  --non-interactive \
  --skip-gateways
assert_install
seed_dummy_mcp

echo "== second install: idempotent Builder re-apply =="
bash "$project_root/install.sh" \
  --skip-hermes \
  --source-dir "$project_root" \
  --answers "$answers" \
  --non-interactive \
  --skip-gateways
assert_install

backup_count="$(find "$HOME/.local/share" -maxdepth 1 -type d -name 'hermes-builder.backup.*' | wc -l)"
test "$backup_count" -ge 1

echo "DOCKER_E2E_OK base=${HERMES_TEST_BASE:-unknown} profile=$profile"
