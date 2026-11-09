#!/usr/bin/env bash
set -euo pipefail

# Runs the /grill eval suite (evals/grill-*) against this repo's bg-skills
# plugin and writes the results plus a token/round summary to
# evals/results/<label>/ (default label: a UTC timestamp).
#
#   scripts/eval-grill.sh            # a run to compare against the baseline
#   scripts/eval-grill.sh baseline   # refresh the committed baseline
#
# The baseline is committed under evals/results/baseline/; other labels are
# git-ignored. Extra arguments after the label go to `claude plugin eval`
# (for example `--runs 1` or `--case grill-term-clash`).

REPO="$(cd "$(dirname "$0")/.." && pwd)"
LABEL="${1:-$(date -u +%Y-%m-%dT%H-%M-%SZ)}"
shift || true
OUT="$REPO/evals/results/$LABEL"
mkdir -p "$OUT"

# The term-clash case seeds GLOSSARY.md with a bash scaffold. On Windows the
# eval looks bash up on PATH, and Git for Windows only puts git on PATH, so add
# the directory of the bash running this script.
PATH="$(dirname "$(command -v bash)"):$PATH"
export PATH

# Each case's workspace is empty or holds one fixture file, so a fact-finding
# sub-agent finds nothing and only adds a late follow-up message the graders
# would have to read around: keep Task/Agent out. The judge is sonnet because
# haiku failed correct replies in trial runs.
cd "$REPO"
status=0
claude plugin eval . --tag grill \
  --scaffold --allow-tools Edit Write --disallow-tools Task Agent \
  --judge-model sonnet \
  --keep-temp --trust-plugin --no-publish -j 3 \
  --output-dir "$OUT" --report "$OUT/report.html" "$@" || status=$?

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
