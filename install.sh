#!/usr/bin/env bash
set -euo pipefail

VERSION="0.1.0"
DEFAULT_HERMES_REF="v2026.8.3"
DEFAULT_HERMES_COMMIT="3c27eb6234bf91b8ceee9e9071591b31e9b148cb"
HERMES_REF="${HERMES_REF:-$DEFAULT_HERMES_REF}"
HERMES_COMMIT="${HERMES_COMMIT:-}"
BUILDER_REPO="${HERMES_BUILDER_REPO:-kousoeie-beep/hermes-builder}"
BUILDER_REF="${HERMES_BUILDER_REF:-v0.1.0}"
BUILDER_HOME="${HERMES_BUILDER_HOME:-$HOME/.local/share/hermes-builder}"
BIN_DIR="${HERMES_BUILDER_BIN_DIR:-$HOME/.local/bin}"
SOURCE_DIR=""
ANSWERS_FILE=""
DRY_RUN=false
SKIP_HERMES=false
NON_INTERACTIVE=false
hermes_home="${HERMES_HOME:-$HOME/.hermes}"

usage() {
  cat <<'EOF'
Hermes Builder installer

Usage: install.sh [options]

Options:
  --dry-run             Show actions without changing the machine
  --skip-hermes         Reuse an existing Hermes installation
  --source-dir PATH     Install Hermes Builder from a local checkout
  --answers PATH        Use an answers JSON file
  --non-interactive     Skip interactive provider/gateway/MCP steps
  --hermes-ref REF      Pin Hermes to a tag or commit
  --hermes-commit SHA   Exact Hermes commit (resolved automatically when omitted)
  --builder-ref REF     Git ref for Hermes Builder
  -h, --help            Show this help
EOF
}

log() { printf '%s\n' "$*" >&2; }
die() { log "ERROR: $*"; exit 1; }

curl_fetch() {
  # GitHub raw/APIの一時的な429・5xx・network errorを有限回retryする。
  curl -fsSL --retry 5 --retry-delay 2 --retry-max-time 120 "$@"
}

run_privileged() {
  if [ "$(id -u)" -eq 0 ]; then
    "$@"
  elif command -v sudo >/dev/null 2>&1; then
    sudo "$@"
  else
    die "system packageの導入にsudoが必要です。rootで実行するかsudoを導入してください。"
  fi
}

ensure_archive_tools() {
  os_name="$(uname -s)"
  if command -v tar >/dev/null 2>&1 && {
    command -v xz >/dev/null 2>&1 || [ "$os_name" = "Darwin" ]
  }; then
    return
  fi
  log "→ HermesのNode.js展開に必要なtar/xzを導入"
  if command -v apt-get >/dev/null 2>&1; then
    run_privileged apt-get update
    run_privileged apt-get install -y tar xz-utils
  elif command -v dnf >/dev/null 2>&1; then
    run_privileged dnf install -y tar xz
  elif command -v yum >/dev/null 2>&1; then
    run_privileged yum install -y tar xz
  elif command -v apk >/dev/null 2>&1; then
    run_privileged apk add --no-cache tar xz
  elif command -v pacman >/dev/null 2>&1; then
    run_privileged pacman -Sy --noconfirm tar xz
  else
    die "tar/xzがなく、対応package managerも見つかりません。tarとxzを導入して再実行してください。"
  fi
  command -v tar >/dev/null 2>&1 || die "tarの導入を確認できませんでした。"
  command -v xz >/dev/null 2>&1 || die "xzの導入を確認できませんでした。"
}

require_option_value() {
  option="$1"
  value="${2:-}"
  [ -n "$value" ] || die "$option requires a value"
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --dry-run) DRY_RUN=true; shift ;;
    --skip-hermes) SKIP_HERMES=true; shift ;;
    --source-dir) require_option_value "$1" "${2:-}"; SOURCE_DIR="$2"; shift 2 ;;
    --answers) require_option_value "$1" "${2:-}"; ANSWERS_FILE="$2"; shift 2 ;;
    --non-interactive) NON_INTERACTIVE=true; shift ;;
    --hermes-ref) require_option_value "$1" "${2:-}"; HERMES_REF="$2"; shift 2 ;;
    --hermes-commit) require_option_value "$1" "${2:-}"; HERMES_COMMIT="$2"; shift 2 ;;
    --builder-ref) require_option_value "$1" "${2:-}"; BUILDER_REF="$2"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) die "Unknown option: $1" ;;
  esac
done

if [ "$NON_INTERACTIVE" = true ] && [ -z "$ANSWERS_FILE" ]; then
  die "--non-interactive requires --answers PATH"
fi

if [ -n "$HERMES_COMMIT" ] && ! [[ "$HERMES_COMMIT" =~ ^[0-9a-fA-F]{40}$ ]]; then
  die "--hermes-commitは40文字のcommit SHAで指定してください。"
fi

if [ -z "$HERMES_COMMIT" ]; then
  if [ "$HERMES_REF" = "$DEFAULT_HERMES_REF" ]; then
    HERMES_COMMIT="$DEFAULT_HERMES_COMMIT"
  elif [[ "$HERMES_REF" =~ ^[0-9a-fA-F]{40}$ ]]; then
    HERMES_COMMIT="$HERMES_REF"
  fi
fi

log "Hermes Builder v$VERSION"
log "  Hermes ref: $HERMES_REF"
log "  Hermes commit: ${HERMES_COMMIT:-<resolve during install>}"
log "  Builder:    $BUILDER_REPO@$BUILDER_REF"

# 公式installer直後や--skip-hermes時も、新しいshellを開かず検出できるようにする。
export PATH="$BIN_DIR:$hermes_home/bin:$PATH"

if [ "$DRY_RUN" = true ]; then
  log "[dry-run] Hermes installerを取得し、${HERMES_REF} (${HERMES_COMMIT:-resolve during install})へ固定して実行"
  if [ -n "$SOURCE_DIR" ]; then
    log "[dry-run] Builder source: $SOURCE_DIR"
  else
    log "[dry-run] git clone https://github.com/$BUILDER_REPO.git ($BUILDER_REF)"
  fi
  log "[dry-run] Install: $BUILDER_HOME"
  log "[dry-run] Command: $BIN_DIR/hermes-builder setup"
  if [ -n "$SOURCE_DIR" ] && command -v python3 >/dev/null 2>&1; then
    args=(setup --dry-run --yes)
    if [ -n "$ANSWERS_FILE" ]; then args+=(--answers "$ANSWERS_FILE"); fi
    if [ "$NON_INTERACTIVE" = true ]; then args+=(--non-interactive); fi
    PYTHONPATH="$SOURCE_DIR/src" python3 -m hermes_builder "${args[@]}"
  fi
  exit 0
fi

command -v curl >/dev/null 2>&1 || die "curlが必要です。OSのpackage managerでcurlを入れて再実行してください。"

if [ "$SKIP_HERMES" = false ]; then
  ensure_archive_tools
  if [ -z "$HERMES_COMMIT" ]; then
    commit_response="$(mktemp "${TMPDIR:-/tmp}/hermes-commit.XXXXXX")"
    trap 'rm -f "$commit_response"' EXIT
    commit_url="https://api.github.com/repos/NousResearch/hermes-agent/commits/$HERMES_REF"
    log "→ Hermes refをcommit SHAへ解決: $HERMES_REF"
    curl_fetch -H "Accept: application/vnd.github+json" "$commit_url" -o "$commit_response"
    HERMES_COMMIT="$(grep -m1 -Eo '"sha"[[:space:]]*:[[:space:]]*"[0-9a-fA-F]{40}"' "$commit_response" | sed -E 's/.*"([0-9a-fA-F]{40})"/\1/' || true)"
    rm -f "$commit_response"
    [ -n "$HERMES_COMMIT" ] || die "Hermes refのcommit SHAを解決できませんでした: $HERMES_REF"
  fi
  hermes_installer="$(mktemp "${TMPDIR:-/tmp}/hermes-install.XXXXXX")"
  trap 'rm -f "$hermes_installer" "${commit_response:-}"' EXIT
  installer_url="https://raw.githubusercontent.com/NousResearch/hermes-agent/$HERMES_COMMIT/scripts/install.sh"
  log "→ Hermes公式installerを取得: $installer_url"
  curl_fetch "$installer_url" -o "$hermes_installer"
  log "→ Hermesを${HERMES_REF} (${HERMES_COMMIT:0:12})へ固定してinstall"
  bash "$hermes_installer" --skip-setup --commit "$HERMES_COMMIT"
else
  command -v hermes >/dev/null 2>&1 || die "--skip-hermesが指定されましたがhermesがPATHにありません。"
fi

command -v git >/dev/null 2>&1 || die "Hermes導入後もgitが見つかりません。新しいterminalで再実行してください。"

staging_root="$(mktemp -d "${TMPDIR:-/tmp}/hermes-builder.XXXXXX")"
source_tree="$staging_root"
trap 'rm -rf "$staging_root"; rm -f "${hermes_installer:-}" "${commit_response:-}"' EXIT
if [ -n "$SOURCE_DIR" ]; then
  [ -d "$SOURCE_DIR/src/hermes_builder" ] || die "Hermes Builder sourceではありません: $SOURCE_DIR"
  cp -R "$SOURCE_DIR"/. "$source_tree"/
else
  log "→ Hermes Builderを取得"
  source_tree="$staging_root/repo"
  git clone --depth 1 --branch "$BUILDER_REF" "https://github.com/$BUILDER_REPO.git" "$source_tree"
fi

if [ -e "$BUILDER_HOME" ]; then
  backup_base="$BUILDER_HOME.backup.$(date +%Y%m%d%H%M%S)"
  backup="$backup_base"
  backup_suffix=1
  while [ -e "$backup" ]; do
    backup="$backup_base.$backup_suffix"
    backup_suffix=$((backup_suffix + 1))
  done
  log "→ 既存Builderを退避: $backup"
  mv "$BUILDER_HOME" "$backup"
fi
mkdir -p "$(dirname "$BUILDER_HOME")" "$BIN_DIR"
mv "$source_tree" "$BUILDER_HOME"

python_cmd="$hermes_home/hermes-agent/venv/bin/python"
if [ ! -x "$python_cmd" ]; then
  python_cmd="$(command -v python3 || true)"
fi
[ -n "$python_cmd" ] || die "Hermes Builderを実行できるPythonが見つかりません。"

wrapper="$BIN_DIR/hermes-builder"
cat > "$wrapper" <<EOF
#!/usr/bin/env sh
PYTHONPATH="$BUILDER_HOME/src" exec "$python_cmd" -m hermes_builder "\$@"
EOF
chmod 0755 "$wrapper"
log "✓ hermes-builder command: $wrapper"

args=(setup --yes)
if [ -n "$ANSWERS_FILE" ]; then args+=(--answers "$ANSWERS_FILE"); fi
if [ "$NON_INTERACTIVE" = true ]; then
  args+=(--non-interactive)
  "$wrapper" "${args[@]}"
elif [ -r /dev/tty ] && [ -w /dev/tty ]; then
  # `curl ... | bash`でもヒアリングはpipeではなく利用者のterminalから読む。
  "$wrapper" "${args[@]}" < /dev/tty
else
  die "対話terminalがありません。--answers PATH --non-interactiveを指定してください。"
fi
