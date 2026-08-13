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
  hermes-builder --version | grep -q "0.1.1"
  hermes profile show "$profile" >/dev/null
  "$HOME/.hermes/hermes-agent/venv/bin/python" - \
    "$HOME/.hermes/profiles/$profile/config.yaml" <<'PY'
import sys
from pathlib import Path

import yaml

config = yaml.safe_load(Path(sys.argv[1]).read_text(encoding="utf-8"))
denied = config["agent"]["disabled_toolsets"]
teams = config["platform_toolsets"]["teams"]
assert isinstance(denied, list), type(denied)
assert isinstance(teams, list), type(teams)
assert {"terminal", "file", "code_execution", "computer_use"} <= set(denied)
assert {"terminal", "file", "code_execution", "computer_use"}.isdisjoint(teams)
assert {"clarify", "skills", "todo", "web"} <= set(teams)
PY
}

echo "== first install: official Hermes + Builder =="
bash "$project_root/install.sh" \
  --source-dir "$project_root" \
  --answers "$answers" \
  --non-interactive
assert_install

echo "== second install: idempotent Builder re-apply =="
bash "$project_root/install.sh" \
  --skip-hermes \
  --source-dir "$project_root" \
  --answers "$answers" \
  --non-interactive
assert_install

backup_count="$(find "$HOME/.local/share" -maxdepth 1 -type d -name 'hermes-builder.backup.*' | wc -l)"
test "$backup_count" -ge 1

echo "DOCKER_E2E_OK base=${HERMES_TEST_BASE:-unknown} profile=$profile"
