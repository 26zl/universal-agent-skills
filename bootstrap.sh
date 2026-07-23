#!/bin/sh
set -eu

umask 077

SCRIPT_DIR=$(CDPATH='' cd -- "$(dirname -- "$0")" 2>/dev/null && pwd -P || printf '')
USER_HOME=${UAS_HOME:-${HOME:?HOME is not set}}
DATA_HOME=${XDG_DATA_HOME:-$USER_HOME/.local/share}

REPO=${UAS_REPO_URL:-}
REF=${UAS_REF:-main}
INSTALL_DIR=${UAS_INSTALL_DIR:-$DATA_HOME/universal-agent-skills/repo}
MODE=auto
AGENTS=codex,claude,opencode
SCOPE=global
PROJECT_DIR=
DRY_RUN=0
FORCE=0
UNINSTALL=0
ALLOW_INSECURE=0
SYNC_AGENT_STACK=0
UPDATE_AGENT_STACK=0
INCLUDE_SENSITIVE_PLUGINS=0
SKILLS=

usage() {
  cat <<'EOF'
Usage: ./bootstrap.sh [options]

Clone or refresh this repository, then run the idempotent installer.

Options:
  --repo URL           Git repository URL (required when run remotely)
  --ref REF            Branch, tag, or commit (default: main)
  --install-dir DIR    Managed checkout location
  --agents LIST        Passed to install.sh
  --skill NAME         Passed to install.sh; repeatable
  --mode MODE          auto, link, or copy
  --scope SCOPE        global or project
  --project-dir DIR    Project root for project scope
  --uninstall          Remove managed skill installations
  --dry-run            Print planned changes
  --force              Back up unmanaged conflicts
  --with-agent-stack   Install declared plugins, MCPs, instructions, and portable skills
  --update-agent-stack Update installed external plugins during stack sync
  --include-sensitive-plugins
                       Include explicit opt-in plugins such as claude-mem
  --allow-insecure-repo  Allow a non-HTTPS/non-SSH repository URL
  -h, --help           Show this help
EOF
}

die() {
  printf 'error: %s\n' "$*" >&2
  exit 1
}

append_skill() {
  if [ -z "$SKILLS" ]; then SKILLS=$1; else SKILLS="$SKILLS,$1"; fi
}

# main() guards a piped download: a truncated script fails to parse instead of running a prefix.
main() {

while [ "$#" -gt 0 ]; do
  case "$1" in
    --repo) [ "$#" -ge 2 ] || die "--repo requires a value"; REPO=$2; shift 2 ;;
    --ref) [ "$#" -ge 2 ] || die "--ref requires a value"; REF=$2; shift 2 ;;
    --install-dir) [ "$#" -ge 2 ] || die "--install-dir requires a value"; INSTALL_DIR=$2; shift 2 ;;
    --agents) [ "$#" -ge 2 ] || die "--agents requires a value"; AGENTS=$2; shift 2 ;;
    --skill) [ "$#" -ge 2 ] || die "--skill requires a value"; append_skill "$2"; shift 2 ;;
    --mode) [ "$#" -ge 2 ] || die "--mode requires a value"; MODE=$2; shift 2 ;;
    --scope) [ "$#" -ge 2 ] || die "--scope requires a value"; SCOPE=$2; shift 2 ;;
    --project-dir) [ "$#" -ge 2 ] || die "--project-dir requires a value"; PROJECT_DIR=$2; shift 2 ;;
    --uninstall) UNINSTALL=1; shift ;;
    --dry-run) DRY_RUN=1; shift ;;
    --force) FORCE=1; shift ;;
    --with-agent-stack) SYNC_AGENT_STACK=1; shift ;;
    --update-agent-stack) SYNC_AGENT_STACK=1; UPDATE_AGENT_STACK=1; shift ;;
    --include-sensitive-plugins) SYNC_AGENT_STACK=1; INCLUDE_SENSITIVE_PLUGINS=1; shift ;;
    --allow-insecure-repo) ALLOW_INSECURE=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) die "unknown option: $1" ;;
  esac
done

case "$REF" in
  ''|-*) die "--ref must be non-empty and must not start with '-'" ;;
esac

if command -v id >/dev/null 2>&1 && [ "$(id -u)" -eq 0 ]; then
  die "do not run the bootstrap as root"
fi

LOCAL_ROOT=
if [ -n "$SCRIPT_DIR" ] && [ -f "$SCRIPT_DIR/install.sh" ] && [ -d "$SCRIPT_DIR/skills" ]; then
  LOCAL_ROOT=$SCRIPT_DIR
fi

if [ -n "$REPO" ]; then
  case "$REPO" in
    https://*|ssh://*|git@*:*) ;;
    *) [ "$ALLOW_INSECURE" -eq 1 ] || die "repository URL must use HTTPS or SSH" ;;
  esac
  command -v git >/dev/null 2>&1 || die "git is required"

  if [ "$DRY_RUN" -eq 1 ]; then
    printf 'would sync %s at %s into %s\n' "$REPO" "$REF" "$INSTALL_DIR"
    [ -d "$INSTALL_DIR" ] || exit 0
  else
    parent=$(dirname -- "$INSTALL_DIR")
    mkdir -p "$parent"
    if [ -e "$INSTALL_DIR" ]; then
      [ -d "$INSTALL_DIR/.git" ] || die "install directory exists but is not a managed git checkout: $INSTALL_DIR"
      origin=$(git -C "$INSTALL_DIR" remote get-url origin)
      [ "$origin" = "$REPO" ] || die "existing checkout uses a different origin: $origin"
      [ -z "$(git -C "$INSTALL_DIR" status --porcelain)" ] || die "managed checkout has local changes: $INSTALL_DIR"
      git -C "$INSTALL_DIR" fetch --depth 1 origin "$REF"
      git -C "$INSTALL_DIR" checkout --detach --force FETCH_HEAD
    else
      temp="$parent/.repo.uas-tmp.$$"
      trap 'rm -rf -- "$temp"' 0 HUP INT TERM
      git init -q "$temp"
      git -C "$temp" remote add origin "$REPO"
      git -C "$temp" fetch --depth 1 origin "$REF"
      git -C "$temp" checkout -q --detach FETCH_HEAD
      mv "$temp" "$INSTALL_DIR"
      trap - 0 HUP INT TERM
    fi
  fi
  LOCAL_ROOT=$INSTALL_DIR
fi

[ -n "$LOCAL_ROOT" ] || die "--repo is required when bootstrap.sh is not run from a repository checkout"
[ -f "$LOCAL_ROOT/install.sh" ] || die "checkout does not contain install.sh"
[ "$UNINSTALL" -eq 0 ] || [ "$SYNC_AGENT_STACK" -eq 0 ] || die "agent stack sync cannot be combined with --uninstall"

set -- --agents "$AGENTS" --mode "$MODE" --scope "$SCOPE"
[ -n "$PROJECT_DIR" ] && set -- "$@" --project-dir "$PROJECT_DIR"
[ "$DRY_RUN" -eq 1 ] && set -- "$@" --dry-run
[ "$FORCE" -eq 1 ] && set -- "$@" --force
[ "$UNINSTALL" -eq 1 ] && set -- "$@" --uninstall

if [ -n "$SKILLS" ]; then
  old_ifs=$IFS
  IFS=,
  for skill in $SKILLS; do
    set -- "$@" --skill "$skill"
  done
  IFS=$old_ifs
fi

sh "$LOCAL_ROOT/install.sh" "$@"

if [ "$SYNC_AGENT_STACK" -eq 1 ]; then
  command -v python3 >/dev/null 2>&1 || die "python3 is required for agent stack sync"
  set -- "$LOCAL_ROOT/scripts/sync_agent_stack.py"
  [ "$DRY_RUN" -eq 0 ] && set -- "$@" --apply
  [ "$UPDATE_AGENT_STACK" -eq 1 ] && set -- "$@" --update
  [ "$INCLUDE_SENSITIVE_PLUGINS" -eq 1 ] && set -- "$@" --include-sensitive
  python3 "$@"
fi

}

main "$@"
