#!/usr/bin/env node
// Regrades kept `claude plugin eval` results with one grader file, without
// running the agent. Rebuilds each run's judge input from the kept aggregate
// result (the grader's recorded evidence, else the run's trace file), asks the
// judge (`claude -p`, Sonnet, no tools, JSON output) for N votes and writes the
// votes, majority, reasons (reasoning mode) and cost to a regrade file. The
// aggregate is never rewritten.
//
// Usage: node scripts/regrade-eval.mjs --results <dir|aggregate-result.json>
//   --grader <file.md> --mode eval|reasoning --votes N --max-cost USD
//   [--focus trace|last_message] [--out <dir>] [--arm with|without|all]
//   [--effort low|medium|high|xhigh|max] [--model sonnet]
//   [--judge-cmd <executable | JSON array>]
// Output: <out>/regrade-<grader name>-<mode>.json (out defaults to the results directory).
// eval mode ends the prompt with the eval's one-word instruction, reconstructed
// from the eval's judge prompt (the prompt itself lives only in the CLI binary).

import { readFileSync, writeFileSync, existsSync, statSync, mkdirSync } from "node:fs";
import { dirname, resolve, join, basename } from "node:path";
import { spawnSync } from "node:child_process";

const opts = { arm: "with", model: "sonnet", "judge-cmd": "claude", votes: "3", mode: "eval" };
const argv = process.argv.slice(2);
for (let i = 0; i < argv.length; i += 2) opts[argv[i].replace(/^--/, "")] = argv[i + 1];

function die(msg, code = 1) {
  console.error(`regrade: ${msg}`);
  process.exit(code);
}

if (!opts.results || !opts.grader || !["eval", "reasoning"].includes(opts.mode) || !opts["max-cost"]) {
  die("usage: regrade-eval.mjs --results <dir|file> --grader <file> --mode eval|reasoning --votes N --max-cost USD", 2);
}
const votesWanted = Number(opts.votes);
const ceiling = Number(opts["max-cost"]);
if (!(votesWanted >= 1) || !(ceiling >= 0)) die("--votes must be at least 1 and --max-cost a number", 2);

const aggPath = statSync(opts.results).isDirectory() ? join(opts.results, "aggregate-result.json") : opts.results;
const agg = JSON.parse(readFileSync(aggPath, "utf8"));

// Grader file: optional frontmatter (type, focus), then the criterion text.
const graderSrc = readFileSync(opts.grader, "utf8");
const fm = graderSrc.match(/^---\r?\n([\s\S]*?)\r?\n---\r?\n?([\s\S]*)$/);
const meta = Object.fromEntries(
  (fm ? fm[1] : "").split(/\r?\n/).map((l) => l.match(/^(\w+):\s*(.*)$/)).filter(Boolean).map((m) => [m[1], m[2].trim()]),
);
const criterion = (fm ? fm[2] : graderSrc).trim();
const focus = opts.focus ?? meta.focus ?? "last_message";
if (!["trace", "last_message"].includes(focus)) die(`focus ${focus} is not supported (trace or last_message)`, 2);
const graderName = basename(opts.grader).replace(/\.md$/, "");

function textOf(message) {
  const c = message?.content;
  if (typeof c === "string") return c;
  if (Array.isArray(c)) return c.filter((b) => b.type === "text").map((b) => b.text).join("\n");
  return "";
}

// Same rule as the summary script: the last top-level assistant message with text.
function finalReply(transcript) {
  let reply = null;
  for (const line of transcript.split(/\r?\n/).filter(Boolean)) {
    let ev;
    try { ev = JSON.parse(line); } catch { continue; }
    if (ev.type !== "assistant" || ev.parent_tool_use_id) continue;
    const text = textOf(ev.message);
    if (text.trim()) reply = text;
  }
  return reply;
}

// The transcript the eval's judge saw: the grader's kept evidence, else the trace file.
function transcriptOf(run) {
  const graders = run.graders ?? [];
  const own = graders.find((g) => g.name === graderName && g.evidence) ?? graders.find((g) => g.evidence);
  if (own) return own.evidence;
  const p = run.tracePath ? resolve(dirname(aggPath), run.tracePath) : null;
  return p && existsSync(p) ? readFileSync(p, "utf8").trimEnd() : null;
}

function buildPrompt(input) {
  const label = focus === "trace" ? "Transcript:" : "Final message:";
  const head = `${criterion}\n\n${label}\n${input}\n\n`;
  if (opts.mode === "eval") return `${head}Respond with exactly one word: PASS or FAIL.`;
  return (
    `${head}Check each item against the criterion, one by one, saying whether it is one fact (or one offer). ` +
    `Then end with a final line holding the verdict alone: "VERDICT: PASS" or "VERDICT: FAIL".`
  );
}

// Cost of one call before making it: about 4 characters a token at Sonnet's
// input price, plus an output allowance for the mode.
const estimateCost = (prompt) => (prompt.length / 4) * 3e-6 + (opts.mode === "eval" ? 10 : 800) * 15e-6;

function parseVerdict(text) {
  if (opts.mode === "reasoning") {
    const m = [...text.matchAll(/VERDICT:\s*(PASS|FAIL)/gi)].pop();
    return m ? m[1].toUpperCase() : null;
  }
  const m = [...text.matchAll(/\b(PASS|FAIL)\b/gi)].pop();
  return m ? m[1].toUpperCase() : null;
}

const judge = opts["judge-cmd"].startsWith("[") ? JSON.parse(opts["judge-cmd"]) : [opts["judge-cmd"]];
function callJudge(prompt) {
  const args = [...judge.slice(1), "-p", "--model", opts.model, "--output-format", "json", "--tools", "", "--system-prompt", "You are a strict grader. Follow the instructions in the message exactly.", "--setting-sources", "", "--no-session-persistence"];
  if (opts.effort) args.push("--effort", opts.effort);
  const r = spawnSync(judge[0], args, { input: prompt, encoding: "utf8", maxBuffer: 64 * 1024 * 1024 });
  if (r.status !== 0) die(`judge command failed: ${(r.stderr || r.error?.message || "").trim().split("\n")[0]}`);
  let out;
  try { out = JSON.parse(r.stdout); } catch { die("judge command did not return JSON"); }
  return { text: String(out.result ?? ""), cost: Number(out.total_cost_usd ?? 0) };
}

const arms = opts.arm === "all" ? null : [opts.arm];
const result = { results: aggPath, grader: opts.grader, mode: opts.mode, focus, votesWanted, ceilingUsd: ceiling, runs: [] };
let spent = 0;
let stopped = null;

outer: for (const c of agg.cases) {
  for (const [arm, runs] of Object.entries(c.arms ?? {})) {
    if (arms && !arms.includes(arm)) continue;
    for (const [i, run] of runs.entries()) {
      const transcript = transcriptOf(run);
      const input = transcript === null ? null : focus === "trace" ? transcript : finalReply(transcript);
      if (input === null) continue;
      const prompt = buildPrompt(input);
      const rec = {
        case: c.name, arm, run: i + 1,
        recordedVotes: ((run.graders ?? []).find((g) => g.name === graderName)?.judgeVotes ?? []).map((v) => (v ? "PASS" : "FAIL")),
        votes: [], reasons: [], costUsd: 0, majority: null,
      };
      result.runs.push(rec);
      for (let v = 0; v < votesWanted; v++) {
        const est = estimateCost(prompt);
        if (spent + est > ceiling) {
          stopped = v === 0 && spent === 0
            ? `cost ceiling $${ceiling} is below the estimated cost of one call ($${est.toFixed(4)}), no call made`
            : `cost ceiling $${ceiling} reached at $${spent.toFixed(4)}, stopped before the next call`;
          break outer;
        }
        const { text, cost } = callJudge(prompt);
        spent += cost;
        rec.costUsd += cost;
        rec.votes.push(parseVerdict(text) ?? "UNPARSED");
        if (opts.mode === "reasoning") rec.reasons.push(text.trim());
      }
    }
  }
}

for (const rec of result.runs) {
  const pass = rec.votes.filter((v) => v === "PASS").length;
  const fail = rec.votes.filter((v) => v === "FAIL").length;
  rec.majority = rec.votes.length === 0 ? null : pass > fail ? "PASS" : "FAIL";
  if (opts.mode !== "reasoning") delete rec.reasons;
}
result.totalCostUsd = spent;
result.stopped = stopped;

if (spent > 0 || result.runs.length) {
  const outDir = opts.out ?? dirname(aggPath);
  mkdirSync(outDir, { recursive: true });
  if (!(stopped && spent === 0)) writeFileSync(join(outDir, `regrade-${graderName}-${opts.mode}.json`), JSON.stringify(result, null, 2) + "\n");
}
if (!(stopped && spent === 0)) {
  for (const r of result.runs) {
    console.log(`${r.case} ${r.arm} run ${r.run}: ${r.votes.join(" ")} -> ${r.majority} (recorded: ${r.recordedVotes.join(" ")}) $${r.costUsd.toFixed(4)}`);
  }
  console.log(`Total cost $${spent.toFixed(4)}`);
}
if (stopped) die(stopped);
