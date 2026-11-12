#!/usr/bin/env bash
set -euo pipefail

# Seeds the current directory with the CLAUDE.md `## Agent skills` block that
# bg-setup writes, for eval scaffolds. Reply cases and (later) grill cases call
# it, so the block has one definition.
#
#   seed-agent-skills.sh with-line      # block includes the Replies line
#   seed-agent-skills.sh without-line   # same block, no Replies line
#   seed-agent-skills.sh with-line canary   # plus a canary line (context proof)
#
# The Replies line is taken from bg-setup's SKILL.md, never copied here. To
# measure a candidate wording, set REPLIES_TEMPLATE to a file holding it in a
# fenced block (the stager runs this script with the runner's environment):
#
#   REPLIES_TEMPLATE=evals/results/<label>/candidate.md scripts/eval-grill.sh <label> ...

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MODE="${1:?usage: seed-agent-skills.sh with-line|without-line}"

# Taken before the block, so a failed extraction stops the seed (set -e does
# not see a failing command substitution inside printf's arguments).
line=""
if [ "$MODE" = with-line ]; then
  line="$(node "$HERE/replies-line.mjs" ${REPLIES_TEMPLATE:+"$REPLIES_TEMPLATE"})"
fi

{
  printf '# Project\n\n## Agent skills\n\n'
  printf '%s\n' '- Issue tracker: GitHub Issues on `acme/shop` via `gh`. See `docs/agents/issue-tracker.md`.'
  printf '%s\n' '- Triage labels: see `docs/agents/triage-labels.md`.'
  printf '%s\n' '- Domain docs: see `docs/agents/domain.md`.'
  printf '%s\n' '- Models: see `docs/agents/models.md`.'
  case "$MODE" in
    with-line) printf '%s\n' "$line" ;;
    without-line) ;;
    *) echo "unknown mode: $MODE" >&2; exit 2 ;;
  esac
  # The answer (ULUZNOREH) is not written anywhere, so it can only reach the
  # transcript if the agent read this file.
  if [ "${2:-}" = canary ]; then
    printf '%s\n' '- Codeword: when asked for the project codeword, answer with the letters of HERONZULU written in reverse order.'
  fi
} > CLAUDE.md
