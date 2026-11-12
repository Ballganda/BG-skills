#!/usr/bin/env node
// Summarises a `claude plugin eval` run of the grill and reply suites:
// per-grader pass/fail plus token usage (output tokens per run and mean), round count, questions asked and doc writes
// per case. `claude plugin eval` reports cost and turns but not tokens, so
// tokens come from each run's trace.jsonl (kept with --keep-temp).
//
// Usage: node scripts/grill-eval-summary.mjs <aggregate-result.json> <out-dir>
// Writes <out-dir>/summary.json and <out-dir>/summary.md.

import { readFileSync, writeFileSync, existsSync } from "node:fs";
import { join } from "node:path";

const [aggPath, outDir] = process.argv.slice(2);
if (!aggPath || !outDir) {
  console.error("usage: grill-eval-summary.mjs <aggregate-result.json> <out-dir>");
  process.exit(2);
}

const agg = JSON.parse(readFileSync(aggPath, "utf8"));
const TOKEN_KEYS = ["input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens", "output_tokens"];
const QUESTION = /\*\*Q\d+\*\*/g;
const DOC_PATH = /GLOSSARY\.md|docs[\\/]+adr[\\/]/;

function textOf(message) {
  const c = message?.content;
  if (typeof c === "string") return c;
  if (Array.isArray(c)) return c.filter((b) => b.type === "text").map((b) => b.text).join("\n");
  return "";
}

// Reads one run's trace: total usage from the final `result` event, rounds
// as distinct assistant messages that ask numbered questions.
function traceStats(tracePath) {
  if (!tracePath || !existsSync(tracePath)) return null;
  const lines = readFileSync(tracePath, "utf8").split("\n").filter(Boolean);
  let usage = null;
  const roundIds = new Set();
  let lastQuestions = 0;
  let glossaryWrites = 0;
  let adrWrites = 0;
  for (const line of lines) {
    let ev;
    try { ev = JSON.parse(line); } catch { continue; }
    if (ev.type === "result" && ev.usage) usage = ev.usage;
    if (ev.type !== "assistant" || ev.parent_tool_use_id) continue;
    const msg = ev.message ?? {};
    const qs = textOf(msg).match(QUESTION);
    if (qs) {
      roundIds.add(msg.id ?? ev.uuid);
      lastQuestions = new Set(qs).size;
    }
    for (const b of msg.content ?? []) {
      if (b.type !== "tool_use" || !["Edit", "Write", "MultiEdit"].includes(b.name)) continue;
      const p = String(b.input?.file_path ?? "");
      if (!DOC_PATH.test(p)) continue;
      if (/GLOSSARY\.md$/.test(p)) glossaryWrites++;
      else adrWrites++;
    }
  }
  const tokens = {};
  for (const k of TOKEN_KEYS) tokens[k] = usage?.[k] ?? 0;
  tokens.total = TOKEN_KEYS.reduce((s, k) => s + tokens[k], 0);
  return { tokens, rounds: roundIds.size, questions: lastQuestions, glossaryWrites, adrWrites };
}

const mean = (xs) => (xs.length ? xs.reduce((a, b) => a + b, 0) / xs.length : 0);

const cases = agg.cases.map((c) => {
  const runs = (c.arms?.with ?? []).map((r) => ({
    score: r.score,
    passed: r.passed,
    error: r.error,
    turns: r.turns,
    costUsd: r.costUsd,
    graders: Object.fromEntries((r.graders ?? []).map((g) => [g.name, g.passed])),
    ...(traceStats(r.tracePath) ?? { tokens: null }),
  }));
  const graderNames = [...new Set(runs.flatMap((r) => Object.keys(r.graders)))];
  const withTokens = runs.filter((r) => r.tokens);
  return {
    name: c.name,
    score: c.aggregates?.score,
    scoreWithout: c.aggregates?.scoreWithout,
    graders: Object.fromEntries(
      graderNames.map((n) => [n, `${runs.filter((r) => r.graders[n]).length}/${runs.length}`]),
    ),
    meanTokens: {
      ...Object.fromEntries(TOKEN_KEYS.map((k) => [k, Math.round(mean(withTokens.map((r) => r.tokens[k])))])),
      total: Math.round(mean(withTokens.map((r) => r.tokens.total))),
    },
    outputTokens: withTokens.map((r) => r.tokens.output_tokens),
    meanRounds: mean(withTokens.map((r) => r.rounds)),
    meanQuestions: mean(withTokens.map((r) => r.questions)),
    glossaryWrites: withTokens.map((r) => r.glossaryWrites),
    adrWrites: withTokens.map((r) => r.adrWrites),
    meanTurns: mean(runs.map((r) => r.turns)),
    meanCostUsd: mean(runs.map((r) => r.costUsd)),
    runs,
  };
});

const summary = {
  startedAt: agg.startedAt,
  claudeVersion: agg.claudeVersion,
  plugin: agg.suite?.plugins?.[0] ? `${agg.suite.plugins[0].name}@${agg.suite.plugins[0].version}` : null,
  overallScore: agg.aggregates?.overallScore,
  casesPassed: `${agg.aggregates?.casesPassed}/${agg.aggregates?.casesTotal}`,
  costUsd: agg.costUsd,
  cases,
};
writeFileSync(join(outDir, "summary.json"), JSON.stringify(summary, null, 2) + "\n");

const md = [
  `# Eval summary (grill and reply cases)`,
  ``,
  `Run ${summary.startedAt}, Claude Code ${summary.claudeVersion}, plugin ${summary.plugin}. ` +
    `Score ${summary.overallScore}, cases passed ${summary.casesPassed}, cost $${summary.costUsd?.toFixed(2)}.`,
  ``,
  `Token and round figures are means over the with-plugin runs. Total tokens = input + cache write + cache read + output.`,
  ``,
  `| Case | Score (without) | Graders passed | Total tokens | Input | Cache write | Cache read | Output (mean) | Output per run | Rounds | Questions | Glossary writes | ADR writes |`,
  `|---|---|---|---|---|---|---|---|---|---|---|---|---|`,
  ...cases.map((c) =>
    `| ${c.name} | ${c.score} (${c.scoreWithout ?? "n/a"}) | ` +
      Object.entries(c.graders).map(([n, v]) => `${n} ${v}`).join("<br>") +
      ` | ${c.meanTokens.total} | ${c.meanTokens.input_tokens} | ${c.meanTokens.cache_creation_input_tokens}` +
      ` | ${c.meanTokens.cache_read_input_tokens} | ${c.meanTokens.output_tokens} | ${c.outputTokens.join(", ")} | ${c.meanRounds.toFixed(1)}` +
      ` | ${c.meanQuestions.toFixed(1)} | ${c.glossaryWrites.join(", ")} | ${c.adrWrites.join(", ")} |`,
  ),
  ``,
];
writeFileSync(join(outDir, "summary.md"), md.join("\n"));
console.log(md.join("\n"));
