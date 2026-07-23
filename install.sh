#!/bin/sh
set -eu

umask 077

ROOT=$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd -P)
SKILLS_DIR="$ROOT/skills"
ADAPTERS_FILE="$ROOT/adapters/agents.tsv"
USER_HOME=${UAS_HOME:-${HOME:?HOME is not set}}
STATE_HOME=${UAS_STATE_HOME:-${XDG_STATE_HOME:-$USER_HOME/.local/state}/universal-agent-skills}
STATE_FILE="$STATE_HOME/installed.tsv"

MODE=auto
AGENTS=codex,claude,opencode
SCOPE=global
PROJECT_DIR=
DRY_RUN=0
FORCE=0
UNINSTALL=0
UPDATE=0
SKILL_FILTER=

usage() {
  cat <<'EOF'
Usage: ./install.sh [options]

Options:
  --agents LIST       Comma-separated: codex,claude,opencode,copilot,universal,all
  --skill NAME        Install or remove one skill; repeat for multiple skills
  --mode MODE         auto, link, or copy (default: auto)
  --scope SCOPE       global or project (default: global)
  --project-dir DIR   Project root for --scope project (default: current dir)
  --update            Fast-forward the source repository before installing
  --uninstall         Remove installations owned by this repository
  --dry-run           Print planned changes without writing
  --force             Back up unmanaged conflicts before installing
  -h, --help          Show this help

Environment:
  UAS_HOME            Override the home directory (useful for testing)
  UAS_STATE_HOME      Override the state directory
EOF
}

say() {
  printf '%s\n' "$*"
}

warn() {
  printf 'warning: %s\n' "$*" >&2
}

die() {
  printf 'error: %s\n' "$*" >&2
  exit 1
}

valid_name() {
  printf '%s\n' "$1" | grep -Eq '^[a-z0-9]+(-[a-z0-9]+)*$'
}

append_skill_filter() {
  valid_name "$1" || die "invalid skill name: $1"
  if [ -z "$SKILL_FILTER" ]; then
    SKILL_FILTER=$1
  else
    SKILL_FILTER="$SKILL_FILTER,$1"
  fi
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --agents)
      [ "$#" -ge 2 ] || die "--agents requires a value"
      AGENTS=$2
      shift 2
      ;;
    --skill)
      [ "$#" -ge 2 ] || die "--skill requires a value"
      append_skill_filter "$2"
      shift 2
      ;;
    --mode)
      [ "$#" -ge 2 ] || die "--mode requires a value"
      MODE=$2
      shift 2
      ;;
    --scope)
      [ "$#" -ge 2 ] || die "--scope requires a value"
      SCOPE=$2
      shift 2
      ;;
    --project-dir)
      [ "$#" -ge 2 ] || die "--project-dir requires a value"
      PROJECT_DIR=$2
      shift 2
      ;;
    --update)
      UPDATE=1
      shift
      ;;
    --uninstall)
      UNINSTALL=1
      shift
      ;;
    --dry-run)
      DRY_RUN=1
      shift
      ;;
    --force)
      FORCE=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      die "unknown option: $1"
      ;;
  esac
done

case "$MODE" in
  auto|link|copy) ;;
  *) die "--mode must be auto, link, or copy" ;;
esac

case "$SCOPE" in
  global|project) ;;
  *) die "--scope must be global or project" ;;
esac

[ -d "$SKILLS_DIR" ] || die "missing canonical skills directory: $SKILLS_DIR"
[ -f "$ADAPTERS_FILE" ] || die "missing adapter registry: $ADAPTERS_FILE"

if [ "$SCOPE" = project ]; then
  PROJECT_DIR=${PROJECT_DIR:-$(pwd -P)}
  if [ ! -d "$PROJECT_DIR" ]; then
    die "project directory does not exist: $PROJECT_DIR"
  fi
  BASE_DIR=$(CDPATH='' cd -- "$PROJECT_DIR" && pwd -P)
else
  BASE_DIR=$USER_HOME
fi

adapter_path() {
  agent=$1
  column=2
  [ "$SCOPE" = project ] && column=3
  awk -F '\t' -v agent="$agent" -v column="$column" '
    $0 !~ /^#/ && $1 == agent { if (NF != 3) exit 1; print $column; found = 1; exit }
    END { if (!found) exit 1 }
  ' "$ADAPTERS_FILE"
}

normalize_agents() {
  raw=$(printf '%s' "$AGENTS" | tr -d ' ' | tr '[:upper:]' '[:lower:]')
  [ -n "$raw" ] || die "--agents cannot be empty"
  case ",$raw," in
    *,all,*) raw=codex,claude,opencode ;;
  esac

  result=
  old_ifs=$IFS
  IFS=,
  for agent in $raw; do
    case "$agent" in
      universal|copilot) agent=codex ;;
    esac
    valid_name "$agent" || die "invalid agent id: $agent"
    adapter_path "$agent" >/dev/null || die "unsupported agent: $agent"
    case ",$result," in
      *",$agent,"*) ;;
      *)
        if [ -z "$result" ]; then result=$agent; else result="$result,$agent"; fi
        ;;
    esac
  done
  IFS=$old_ifs
  printf '%s\n' "$result"
}

SELECTED_AGENTS=$(normalize_agents)

skill_selected() {
  [ -z "$SKILL_FILTER" ] && return 0
  case ",$SKILL_FILTER," in
    *",$1,"*) return 0 ;;
    *) return 1 ;;
  esac
}

agent_selected() {
  case ",$SELECTED_AGENTS," in
    *",$1,"*) return 0 ;;
    *) return 1 ;;
  esac
}

list_skills() {
  for skill_dir in "$SKILLS_DIR"/*/; do
    [ -f "$skill_dir/SKILL.md" ] || continue
    basename "$skill_dir"
  done | LC_ALL=C sort
}

validate_requested_skills() {
  [ -z "$SKILL_FILTER" ] && return 0
  old_ifs=$IFS
  IFS=,
  for name in $SKILL_FILTER; do
    [ -f "$SKILLS_DIR/$name/SKILL.md" ] || die "unknown skill: $name"
  done
  IFS=$old_ifs
}

# Uninstall must keep working for skills that were removed from the repository.
[ "$UNINSTALL" -eq 1 ] || validate_requested_skills

if [ "$UPDATE" -eq 1 ] && [ "$UNINSTALL" -eq 0 ]; then
  command -v git >/dev/null 2>&1 || die "git is required for --update"
  git -C "$ROOT" rev-parse --is-inside-work-tree >/dev/null 2>&1 || die "source is not a git repository"
  dirty=$(git -C "$ROOT" status --porcelain) || die "cannot read the source repository status"
  if [ -n "$dirty" ]; then
    die "source repository has local changes; commit or stash them before --update"
  fi
  if [ "$DRY_RUN" -eq 1 ]; then
    say "would run: git -C $ROOT pull --ff-only"
  else
    git -C "$ROOT" pull --ff-only
  fi
fi

if [ "$MODE" = auto ]; then
  MODE='link'
fi

state_record() {
  agent=$1
  skill=$2
  mode=$3
  source=$4
  target=$5
  [ "$DRY_RUN" -eq 1 ] && return 0

  mkdir -p "$STATE_HOME"
  temp="$STATE_FILE.tmp.$$"
  if [ -f "$STATE_FILE" ]; then
    awk -F '\t' -v target="$target" '$6 != target' "$STATE_FILE" > "$temp"
  else
    : > "$temp"
  fi
  printf '%s\t%s\t%s\t%s\t%s\t%s\n' "$SCOPE" "$agent" "$skill" "$mode" "$source" "$target" >> "$temp"
  mv "$temp" "$STATE_FILE"
}

is_managed_copy() {
  [ -f "$1/.uas-managed" ] && grep -qx 'managed-by=universal-agent-skills' "$1/.uas-managed"
}

is_owned_target() {
  target=$1
  source=$2
  if [ -L "$target" ]; then
    [ "$(readlink "$target")" = "$source" ]
  else
    is_managed_copy "$target"
  fi
}

remove_owned_target() {
  target=$1
  source=$2
  if [ ! -e "$target" ] && [ ! -L "$target" ]; then
    return 0
  fi
  is_owned_target "$target" "$source" || return 1
  if [ "$DRY_RUN" -eq 1 ]; then
    say "would remove: $target"
  else
    rm -rf -- "$target"
  fi
}

prepare_target() {
  target=$1
  source=$2
  if [ ! -e "$target" ] && [ ! -L "$target" ]; then
    return 0
  fi

  if is_owned_target "$target" "$source"; then
    if [ "$DRY_RUN" -eq 1 ]; then
      say "would replace managed target: $target"
    else
      rm -rf -- "$target"
    fi
    return 0
  fi

  [ "$FORCE" -eq 1 ] || die "refusing to overwrite unmanaged target: $target (use --force to back it up)"
  backup="$target.uas-backup-$(date -u +%Y%m%dT%H%M%SZ).$$"
  if [ "$DRY_RUN" -eq 1 ]; then
    say "would back up unmanaged target: $target -> $backup"
  else
    mv "$target" "$backup"
    say "backed up unmanaged target: $backup"
  fi
}

install_one() {
  agent=$1
  skill=$2
  source=$3
  target=$4

  if [ "$MODE" = link ] && [ -L "$target" ] && [ "$(readlink "$target")" = "$source" ]; then
    say "unchanged [$agent]: $skill"
    state_record "$agent" "$skill" link "$source" "$target"
    return 0
  fi

  if [ -e "$target" ] || [ -L "$target" ]; then
    prepare_target "$target" "$source"
  fi

  parent=$(dirname -- "$target")
  if [ "$DRY_RUN" -eq 1 ]; then
    say "would install [$agent/$MODE]: $skill -> $target"
    return 0
  fi

  mkdir -p "$parent"
  if [ "$MODE" = link ]; then
    ln -s "$source" "$target"
  else
    temp="$parent/.$skill.uas-tmp.$$"
    rm -rf -- "$temp"
    mkdir -p "$temp"
    cp -R "$source/." "$temp/"
    printf '%s\nsource=%s\n' 'managed-by=universal-agent-skills' "$source" > "$temp/.uas-managed"
    mv "$temp" "$target"
  fi
  say "installed [$agent/$MODE]: $skill"
  state_record "$agent" "$skill" "$MODE" "$source" "$target"
}

uninstall_from_state() {
  [ -f "$STATE_FILE" ] || return 1
  temp="$STATE_FILE.keep.$$"
  : > "$temp"

  while IFS="$(printf '\t')" read -r record_scope agent skill mode source target || [ -n "$target" ]; do
    [ -n "$target" ] || continue
    if [ "$record_scope" != "$SCOPE" ] || ! agent_selected "$agent" || ! skill_selected "$skill"; then
      printf '%s\t%s\t%s\t%s\t%s\t%s\n' "$record_scope" "$agent" "$skill" "$mode" "$source" "$target" >> "$temp"
      continue
    fi

    relative=$(adapter_path "$agent") || die "state references unsupported agent: $agent"
    expected="$BASE_DIR/$relative/$skill"
    if [ "$target" != "$expected" ]; then
      warn "state target is outside the expected adapter path; leaving it unchanged: $target"
      printf '%s\t%s\t%s\t%s\t%s\t%s\n' "$record_scope" "$agent" "$skill" "$mode" "$source" "$target" >> "$temp"
      continue
    fi

    if remove_owned_target "$target" "$source"; then
      say "removed [$agent]: $skill"
    else
      warn "target is no longer owned by this installer; leaving it unchanged: $target"
      printf '%s\t%s\t%s\t%s\t%s\t%s\n' "$record_scope" "$agent" "$skill" "$mode" "$source" "$target" >> "$temp"
    fi
  done < "$STATE_FILE"

  if [ "$DRY_RUN" -eq 1 ]; then
    rm -f -- "$temp"
  elif [ -s "$temp" ]; then
    mv "$temp" "$STATE_FILE"
  else
    rm -f -- "$temp" "$STATE_FILE"
  fi
  return 0
}

if [ "$UNINSTALL" -eq 1 ]; then
  if uninstall_from_state; then
    exit 0
  fi
  warn "no installer state found; checking current canonical skills only"
  for agent in $(printf '%s' "$SELECTED_AGENTS" | tr ',' ' '); do
    relative=$(adapter_path "$agent")
    for skill in $(list_skills); do
      skill_selected "$skill" || continue
      source="$SKILLS_DIR/$skill"
      target="$BASE_DIR/$relative/$skill"
      if remove_owned_target "$target" "$source"; then
        say "removed [$agent]: $skill"
      fi
    done
  done
  exit 0
fi

for agent in $(printf '%s' "$SELECTED_AGENTS" | tr ',' ' '); do
  relative=$(adapter_path "$agent")
  case "$relative" in
    ''|/*|*..*) die "unsafe adapter path for $agent: $relative" ;;
  esac
  for skill in $(list_skills); do
    skill_selected "$skill" || continue
    source="$SKILLS_DIR/$skill"
    target="$BASE_DIR/$relative/$skill"
    install_one "$agent" "$skill" "$source" "$target"
  done
done

say "done"
