#!/usr/bin/env bash
set -euo pipefail

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
test_root="$(mktemp -d "${TMPDIR:-/tmp}/hermes-builder-e2e.XXXXXX")"
trap 'rm -rf "$test_root"' EXIT

export HOME="$test_root/home"
export HERMES_HOME="$HOME/.hermes"
export HERMES_BUILDER_HOME="$HOME/builder"
export HERMES_BUILDER_BIN_DIR="$HOME/bin"
export HERMES_FAKE_LOG="$test_root/hermes.log"
mkdir -p "$HERMES_HOME/bin" "$HOME"

missing_value_log="$test_root/missing-value.log"
if bash "$project_root/install.sh" --source-dir >"$missing_value_log" 2>&1; then
  echo "missing option value must fail" >&2
  exit 1
fi
grep -q -- "--source-dir requires a value" "$missing_value_log"

invalid_commit_log="$test_root/invalid-commit.log"
if HERMES_COMMIT="not-a-commit" bash "$project_root/install.sh" --dry-run >"$invalid_commit_log" 2>&1; then
  echo "invalid commit must fail even in dry-run" >&2
  exit 1
fi
grep -q -- "40文字のcommit SHA" "$invalid_commit_log"
grep -q -- "--retry 5 --retry-delay 2 --retry-max-time 120" "$project_root/install.sh"

fake_hermes="$HERMES_HOME/bin/hermes"
cat > "$fake_hermes" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
if [ "${1:-}" = "profile" ] && [ "${2:-}" = "show" ]; then
  exit 1
fi
printf '%s\n' "$*" >> "$HERMES_FAKE_LOG"
EOF
chmod 0755 "$fake_hermes"

run_installer() {
  bash "$project_root/install.sh" \
    --skip-hermes \
    --source-dir "$project_root" \
    --answers "$project_root/tests/fixtures/owner-local.json" \
    --non-interactive \
    --skip-gateways
}

run_installer
run_installer
run_installer

test -x "$HERMES_BUILDER_BIN_DIR/hermes-builder"
test -f "$HERMES_HOME/profiles/local-operator/SOUL.md"
test -f "$HOME/.config/hermes-builder/plans/local-operator.json"
test "$(find "$HOME" -maxdepth 1 -type d -name 'builder.backup.*' | wc -l | tr -d ' ')" -ge 2
grep -q "profile create local-operator" "$HERMES_FAKE_LOG"
grep -q -- "-p local-operator doctor" "$HERMES_FAKE_LOG"
if grep -q "gateway install" "$HERMES_FAKE_LOG"; then
  echo "gateway service must wait for interactive authentication" >&2
  exit 1
fi
