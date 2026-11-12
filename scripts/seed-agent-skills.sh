#!/usr/bin/env bash
set -euo pipefail

# Seeds the current directory with the CLAUDE.md `## Agent skills` block that
# bg-setup writes, for eval scaffolds. Reply cases and (later) grill cases call
# it, so the block has one definition.
#
#   seed-agent-skills.sh with-line      # block includes the Replies line
#   seed-agent-skills.sh without-line   # same block, no Replies line
#
# The Replies line is taken from bg-setup's SKILL.md, never copied here.

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MODE="${1:?usage: seed-agent-skills.sh with-line|without-line}"

{
  printf '# Project\n\n## Agent skills\n\n'
  printf '%s\n' '- Issue tracker: GitHub Issues on `acme/shop` via `gh`. See `docs/agents/issue-tracker.md`.'
  printf '%s\n' '- Triage labels: see `docs/agents/triage-labels.md`.'
  printf '%s\n' '- Domain docs: see `docs/agents/domain.md`.'
  printf '%s\n' '- Models: see `docs/agents/models.md`.'
  case "$MODE" in
    with-line) printf '%s\n' "$(node "$HERE/replies-line.mjs")" ;;
    without-line) ;;
    *) echo "unknown mode: $MODE" >&2; exit 2 ;;
  esac
} > CLAUDE.md
