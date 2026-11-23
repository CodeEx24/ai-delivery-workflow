#!/usr/bin/env bash
# Installs the AI delivery workflow kit into ~/.claude (macOS / Linux / Git Bash).
#   ./install.sh [--dry-run] [--with-blueprint] [--skip-third-party] [--claude-home <path>]
set -euo pipefail

KIT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CLAUDE_HOME="${HOME}/.claude"
DRY_RUN=0
WITH_BLUEPRINT=0
SKIP_THIRD_PARTY=0

while [ $# -gt 0 ]; do
  case "$1" in
    --dry-run) DRY_RUN=1 ;;
    --with-blueprint) WITH_BLUEPRINT=1 ;;
    --skip-third-party) SKIP_THIRD_PARTY=1 ;;
    --claude-home) shift; CLAUDE_HOME="$1" ;;
    -h|--help) sed -n '2,3p' "$0"; exit 0 ;;
    *) echo "unknown option: $1" >&2; exit 1 ;;
  esac
  shift
done

THIRD_PARTY=(
  "getsentry/skills@security-review"
  "obra/superpowers@test-driven-development"
  "microsoft/playwright-cli@playwright-cli"
  "anthropics/skills@webapp-testing"
  "vercel-labs/skills@find-skills"
)

BACKUP_DIR="${CLAUDE_HOME}/backups/ai-delivery-workflow-$(date +%Y%m%d-%H%M%S)"

# run <label> <command...>: prints the label, runs the command unless --dry-run.
run() {
  local label="$1"; shift
  if [ "$DRY_RUN" -eq 1 ]; then echo "[dry-run] $label"; else echo "$label"; "$@"; fi
}

backup_item() { # <relative path under CLAUDE_HOME>
  local target="${CLAUDE_HOME}/$1" dest="${BACKUP_DIR}/$1"
  [ -e "$target" ] || return 0
  run "backup  $target -> $dest" sh -c 'mkdir -p "$(dirname "$2")" && cp -R "$1" "$2"' _ "$target" "$dest"
}

install_item() { # <source> <relative path under CLAUDE_HOME>
  local target="${CLAUDE_HOME}/$2"
  run "install $1 -> $target" sh -c 'mkdir -p "$(dirname "$2")" && rm -rf "$2" && cp -R "$1" "$2"' _ "$1" "$target"
}

echo "AI delivery workflow kit -> $CLAUDE_HOME"
[ "$DRY_RUN" -eq 1 ] && echo "(dry run: nothing will be changed)"
echo

# 1. Collect what to install: skills, agents, workflow file.
SOURCES=(); TARGETS=()
for dir in "$KIT_DIR"/skills/*/; do
  name="$(basename "$dir")"
  if [ "$name" = "delivery-blueprint" ] && [ "$WITH_BLUEPRINT" -eq 0 ]; then
    echo "skip    skills/delivery-blueprint (synced from claude.ai; use --with-blueprint to install)"
    continue
  fi
  SOURCES+=("${dir%/}"); TARGETS+=("skills/$name")
done
for file in "$KIT_DIR"/agents/*.md; do
  SOURCES+=("$file"); TARGETS+=("agents/$(basename "$file")")
done
SOURCES+=("$KIT_DIR/workflow/ai-delivery-workflow.md"); TARGETS+=("workflows/ai-delivery-workflow.md")
SOURCES+=("$KIT_DIR/board"); TARGETS+=("delivery-board")
# Templates for /delivery-init (after the skills, so they land inside the installed skill).
SOURCES+=("$KIT_DIR/settings"); TARGETS+=("skills/delivery-init/templates")

# 2. Back up whatever already exists at those targets.
for i in "${!TARGETS[@]}"; do backup_item "${TARGETS[$i]}"; done

# 3. Copy the kit in.
for i in "${!TARGETS[@]}"; do install_item "${SOURCES[$i]}" "${TARGETS[$i]}"; done

# 4. Third-party skills (global, through the skills CLI).
echo
if [ "$SKIP_THIRD_PARTY" -eq 1 ]; then
  echo "skip    third-party skills (--skip-third-party)"
elif ! command -v npx >/dev/null 2>&1; then
  echo "warn    npx not found: install Node.js, then run the commands in third-party.md"
else
  for pkg in "${THIRD_PARTY[@]}"; do
    run "npx -y skills add $pkg -g -y" npx -y skills add "$pkg" -g -y \
      || echo "warn    failed: $pkg (install it by hand, see third-party.md)"
  done
fi

# 5. Next steps. settings.json is never touched.
echo
[ "$DRY_RUN" -eq 0 ] && [ -d "$BACKUP_DIR" ] && echo "Backup: $BACKUP_DIR"
cat <<'EOF'
Done. Next steps:
  1. In each project, open Claude Code and run:  /delivery-init
     (adds the CLAUDE.md block, docs/workflow/README.md, .gitignore entry; settings only on your yes)
  2. Restart open Claude Code sessions so they pick up the new skills
  3. Manual alternative: see INSTALL.md (section "Set up a project by hand")
  4. Optional tools (Orca, PM tool MCP, gh, Context7, ...): see third-party.md
  5. Start:  /loop /deliver <PROJECT-KEY>   (new project: /delivery-blueprint first)
     GitHub issues labeled "factory":  /loop /factory run
  6. Live board (try it now):  python3 "$HOME/.claude/delivery-board/board.py" serve --demo --open
EOF
