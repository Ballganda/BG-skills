#!/usr/bin/env bash
set -euo pipefail

# Runs the eval suite (the /grill cases evals/grill-* and the reply cases
# evals/reply-*) against this repo's bg-skills
# plugin and writes the results plus a token/round summary to
# evals/results/<label>/ (default label: a UTC timestamp).
#
#   scripts/eval-grill.sh            # a run to compare against the baseline
#   scripts/eval-grill.sh baseline   # refresh the committed baseline
#
# The baseline is committed under evals/results/baseline/; other labels are
# git-ignored. Extra arguments after the label go to `claude plugin eval`
# (for example `--runs 1` or `--case grill-term-clash`). The default run
# covers the tags grill and reply; pass `--tag <tag>` to choose others, for
# example `--tag reply-control` for the no-Replies-line control run.
#
# Cost and duration (figures from the recorded runs under evals/results/
# reply-status and evals/results/reply-control: one reply case each, 5 samples
# per arm, both arms, run with --runs 5): 73 s and 77 s, $4.19 and $3.50, so
# $7.69 together. A default run takes the grill and reply cases at 3 samples
# per arm (case.runs in each case.yaml). The grill cases are not in the
# recorded figures, so a default run takes longer and costs more than those.
#
# One-sample smoke run (one case, one sample per arm, written to
# evals/results/smoke):
#
#   scripts/eval-grill.sh smoke --case reply-status --runs 1
#
# Context proof: the reply-context-proof case passes only when the seeded
# CLAUDE.md is loaded (about $0.13, no LLM judge). Add --no-scaffold to see it
# fail:
#
#   scripts/eval-grill.sh smoke --case reply-context-proof --no-scaffold
#
# The runner needs a logged-in claude. When `claude auth status` reports
# not logged in, it prints one line naming `claude auth login`, exits
# non-zero, and writes no results.

REPO="$(cd "$(dirname "$0")/.." && pwd)"
LABEL="${1:-$(date -u +%Y-%m-%dT%H-%M-%SZ)}"
shift || true
OUT="$REPO/evals/results/$LABEL"

tags=(--tag grill --tag reply)
for a in "$@"; do [ "$a" = "--tag" ] && tags=(); done

# The term-clash case seeds GLOSSARY.md with a bash scaffold. On Windows the
# eval looks bash up on PATH, and Git for Windows only puts git on PATH, so add
# the directory of the bash running this script.
PATH="$(dirname "$(command -v bash)"):$PATH"
export PATH

# Before anything is spent or written, ask claude whether it is logged in.
# `claude auth status` prints JSON with a loggedIn flag; any other output
# (or no output, if claude is missing) counts as logged out.
auth="$(claude auth status 2>/dev/null || true)"
if ! printf '%s' "$auth" | node -e 'let s = ""; process.stdin.on("data", (d) => (s += d)).on("end", () => { try { process.exit(JSON.parse(s).loggedIn === true ? 0 : 1); } catch { process.exit(1); } });'; then
  echo "Not logged in to claude: run \`claude auth login\`, then run this script again." >&2
  exit 1
fi

mkdir -p "$OUT"

# Each case's workspace is empty or holds one fixture file, so a fact-finding
# sub-agent finds nothing and only adds a late follow-up message the graders
# would have to read around: keep Task/Agent out. The judge is sonnet because
# haiku failed correct replies in trial runs.
cd "$REPO"
status=0
claude plugin eval . "${tags[@]}" \
  --scaffold --allow-tools Edit Write --disallow-tools Task Agent \
  --judge-model sonnet \
  --keep-temp --trust-plugin --no-publish -j 3 \
  --output-dir "$OUT" --report "$OUT/report.html" "$@" || status=$?

# Also writes replies.md (each run's judged Reply and grader votes) before the
# traces are removed below.
node scripts/grill-eval-summary.mjs "$OUT/aggregate-result.json" "$OUT"

# --keep-temp kept each run's workspace so the summary could read its trace.
# Only out/ is ours; the rest was written by the agent under test, so remove
# the whole directory without running anything inside it.
node -e '
const r = require(process.argv[1]);
const fs = require("fs"), path = require("path");
for (const c of r.cases) for (const arm of Object.values(c.arms ?? {})) for (const run of arm)
  if (run.tracePath) {
    const dir = path.dirname(path.dirname(run.tracePath));
    if (path.basename(dir).startsWith("claude-eval-")) fs.rmSync(dir, { recursive: true, force: true });
  }
' "$OUT/aggregate-result.json"

exit "$status"
