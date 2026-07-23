#!/bin/sh
set -eu

ROOT=$(CDPATH='' cd -- "$(dirname -- "$0")/.." && pwd -P)
TEMP_ROOT=$(mktemp -d "${TMPDIR:-/tmp}/uas-test.XXXXXX")
trap 'rm -rf -- "$TEMP_ROOT"' 0 HUP INT TERM

export UAS_HOME="$TEMP_ROOT/home"
export UAS_STATE_HOME="$TEMP_ROOT/state"
mkdir -p "$UAS_HOME"

fail() {
  printf 'test failure: %s\n' "$*" >&2
  exit 1
}

assert_link() {
  [ -L "$1" ] || fail "expected symbolic link: $1"
}

assert_missing() {
  if [ -e "$1" ] || [ -L "$1" ]; then
    fail "expected missing path: $1"
  fi
}

sh "$ROOT/install.sh" --mode link --agents all
assert_link "$UAS_HOME/.agents/skills/coding-style"
assert_link "$UAS_HOME/.agents/skills/surgical-implementation"
assert_link "$UAS_HOME/.claude/skills/coding-style"
assert_link "$UAS_HOME/.config/opencode/skills/coding-style"

sh "$ROOT/install.sh" --mode link --agents all
sh "$ROOT/install.sh" --uninstall --agents all
assert_missing "$UAS_HOME/.agents/skills/coding-style"
assert_missing "$UAS_HOME/.agents/skills/surgical-implementation"
assert_missing "$UAS_HOME/.claude/skills/coding-style"
assert_missing "$UAS_HOME/.config/opencode/skills/coding-style"

sh "$ROOT/install.sh" --mode link --agents copilot --skill simplify-code
assert_link "$UAS_HOME/.agents/skills/simplify-code"
sh "$ROOT/install.sh" --uninstall --agents copilot --skill simplify-code
assert_missing "$UAS_HOME/.agents/skills/simplify-code"

sh "$ROOT/install.sh" --mode copy --agents codex --skill coding-style
target="$UAS_HOME/.agents/skills/coding-style"
[ -f "$target/.uas-managed" ] || fail "copy marker missing"
cmp "$ROOT/skills/coding-style/SKILL.md" "$target/SKILL.md" >/dev/null || fail "copied skill differs"
sh "$ROOT/install.sh" --mode copy --agents codex --skill coding-style
sh "$ROOT/install.sh" --uninstall --agents codex --skill coding-style
assert_missing "$target"

mkdir -p "$target"
printf '%s\n' unmanaged > "$target/owner.txt"
if sh "$ROOT/install.sh" --mode link --agents codex --skill coding-style 2>/dev/null; then
  fail "unmanaged conflict should fail without --force"
fi
sh "$ROOT/install.sh" --mode link --agents codex --skill coding-style --force
find "$UAS_HOME/.agents/skills" -maxdepth 1 -name 'coding-style.uas-backup-*' | grep -q . || fail "backup missing"
sh "$ROOT/install.sh" --uninstall --agents codex --skill coding-style

project="$TEMP_ROOT/project"
mkdir -p "$project"
sh "$ROOT/install.sh" --mode copy --scope project --project-dir "$project" --agents claude
[ -f "$project/.claude/skills/verify-changes/SKILL.md" ] || fail "project install missing"
sh "$ROOT/install.sh" --uninstall --scope project --project-dir "$project" --agents claude
assert_missing "$project/.claude/skills/verify-changes"

dry_home="$TEMP_ROOT/dry-home"
UAS_HOME="$dry_home" sh "$ROOT/install.sh" --dry-run --agents all
[ ! -e "$dry_home" ] || fail "dry-run wrote to disk"

bootstrap_home="$TEMP_ROOT/bootstrap-home"
UAS_HOME="$bootstrap_home" sh "$ROOT/bootstrap.sh" --dry-run --agents all
[ ! -e "$bootstrap_home" ] || fail "bootstrap dry-run wrote to disk"
if UAS_HOME="$bootstrap_home" sh "$ROOT/bootstrap.sh" --dry-run \
  --repo https://github.com/example/repository.git --ref -unsafe 2>/dev/null; then
  fail "bootstrap accepted an option-like Git ref"
fi

fake_claude="$TEMP_ROOT/fake-claude"
printf '%s\n' '#!/bin/sh' "printf '%s\\n' '[]'" > "$fake_claude"
chmod +x "$fake_claude"
fake_codex="$TEMP_ROOT/fake-codex"
printf '%s\n' '#!/bin/sh' \
  'case "$*" in' \
  '  "plugin marketplace list --json") printf "%s\n" '\''{"marketplaces":[]}'\'' ;;' \
  '  "plugin list --available --json") printf "%s\n" '\''{"installed":[],"available":[]}'\'' ;;' \
  '  "mcp list --json") printf "%s\n" '\''[]'\'' ;;' \
  'esac' > "$fake_codex"
chmod +x "$fake_codex"
fake_text="$TEMP_ROOT/fake-text"
printf '%s\n' '#!/bin/sh' 'exit 0' > "$fake_text"
chmod +x "$fake_text"
stack_output=$(UAS_HOME="$bootstrap_home" \
  UAS_CLAUDE_COMMAND="$fake_claude" \
  UAS_CODEX_COMMAND="$fake_codex" \
  UAS_COPILOT_COMMAND="$fake_text" \
  UAS_OPENCODE_COMMAND="$fake_text" \
  UAS_CODE_COMMAND="$fake_text" \
  sh "$ROOT/bootstrap.sh" --dry-run --agents all --with-agent-stack)
printf '%s\n' "$stack_output" | grep -q 'audit complete; no changes were made' || \
  fail "bootstrap did not run the agent stack audit"
[ ! -e "$bootstrap_home" ] || fail "agent stack dry-run wrote to the test home"

target="$UAS_HOME/.agents/skills/coding-style"
sh "$ROOT/install.sh" --mode copy --agents codex --skill coding-style
rm -rf -- "$target"
mkdir -p "$target"
printf '%s\n' user-content > "$target/notes.txt"
sh "$ROOT/install.sh" --uninstall --agents codex --skill coding-style 2>/dev/null
[ -f "$target/notes.txt" ] || fail "uninstall removed an unmanaged replacement"
rm -rf -- "$target"

printf '%s\n' "POSIX installer tests passed."
