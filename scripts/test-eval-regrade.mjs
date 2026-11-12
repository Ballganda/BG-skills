#!/usr/bin/env node
// Tests the regrade command over the recorded aggregate fixture with a stub
// judge command, so nothing is spent.
// Run: node scripts/test-eval-regrade.mjs

import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { mkdtempSync, readFileSync, rmSync, writeFileSync, existsSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { test } from "node:test";

const here = (p) => fileURLToPath(new URL(p, import.meta.url));
const FIXTURE = here("./fixtures/eval-aggregate/aggregate-result.json");
const STUB = here("./fixtures/regrade-stub-judge.mjs");

const GRADER = (focus) =>
  `---\ntype: llm\nfocus: ${focus}\n---\n\nPASS only if the detail is one fact per bullet.\n`;

function regrade({ focus = "trace", mode = "eval", votes = 3, maxCost = 1, args = [], verdicts = "PASS,FAIL,PASS" } = {}) {
  const dir = mkdtempSync(join(tmpdir(), "eval-regrade-"));
  const grader = join(dir, "detail.md");
  writeFileSync(grader, GRADER(focus));
  const log = join(dir, "calls.jsonl");
  const outDir = join(dir, "out");
  const r = spawnSync(
    process.execPath,
    [
      here("./regrade-eval.mjs"), "--results", FIXTURE, "--grader", grader, "--mode", mode,
      "--votes", String(votes), "--max-cost", String(maxCost), "--out", outDir,
      "--judge-cmd", JSON.stringify([process.execPath, STUB]), ...args,
    ],
    { encoding: "utf8", env: { ...process.env, STUB_LOG: log, STUB_VERDICTS: verdicts, STUB_COST: "0.01" } },
  );
  const calls = existsSync(log) ? readFileSync(log, "utf8").split("\n").filter(Boolean).map((l) => JSON.parse(l)) : [];
  const file = join(outDir, "regrade-detail-" + mode + ".json");
  return { dir, r, calls, file, regraded: existsSync(file) ? JSON.parse(readFileSync(file, "utf8")) : null };
}

test("trace focus sends the kept transcript", () => {
  const { dir, calls } = regrade({ focus: "trace" });
  try {
    assert.equal(calls.length, 3);
    assert.ok(calls[0].prompt.includes('"subtype":"init"'));
    assert.ok(calls[0].prompt.includes("Let me look."));
    assert.ok(calls[0].prompt.includes("Done: the build is green."));
    assert.ok(calls[0].args.includes("-p") && calls[0].args.includes("json"));
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
});

test("last_message focus sends only the final Reply, as the Replies file shows it", () => {
  const { dir, calls } = regrade({ focus: "last_message" });
  try {
    assert.ok(calls[0].prompt.includes("Done: the build is green.\n- 3 files changed"));
    assert.ok(!calls[0].prompt.includes("Let me look."));
    assert.ok(!calls[0].prompt.includes("init"));
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
});

test("eval mode ends with the one-word instruction", () => {
  const { dir, calls } = regrade({ mode: "eval" });
  try {
    assert.ok(calls[0].prompt.trimEnd().endsWith("Respond with exactly one word: PASS or FAIL."));
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
});

test("reasoning mode asks for the per-item check before a verdict line", () => {
  const { dir, calls, regraded } = regrade({ mode: "reasoning", verdicts: "PASS" });
  try {
    const p = calls[0].prompt;
    assert.match(p, /each item/);
    assert.ok(p.indexOf("each item") < p.indexOf("VERDICT: PASS"));
    assert.ok(!p.includes("exactly one word"));
    assert.match(regraded.runs[0].reasons[0], /item 1 is one fact/);
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
});

test("votes, majority, cost land in the regrade file and recorded votes are untouched", () => {
  const before = readFileSync(FIXTURE, "utf8");
  const { dir, regraded, r } = regrade({});
  try {
    assert.equal(r.status, 0, r.stderr);
    const run = regraded.runs[0];
    assert.deepEqual(run.votes, ["PASS", "FAIL", "PASS"]);
    assert.equal(run.majority, "PASS");
    assert.equal(run.recordedVotes.join(" "), "FAIL FAIL FAIL");
    assert.ok(Math.abs(run.costUsd - 0.03) < 1e-9);
    assert.ok(Math.abs(regraded.totalCostUsd - 0.03) < 1e-9);
    assert.match(r.stdout, /total cost \$0\.03/i);
    assert.equal(readFileSync(FIXTURE, "utf8"), before);
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
});

test("a ceiling below one call's cost makes no call and exits non-zero with one line", () => {
  const { dir, calls, r } = regrade({ maxCost: 0.000001 });
  try {
    assert.notEqual(r.status, 0);
    assert.equal(calls.length, 0);
    assert.equal(r.stderr.trim().split("\n").length, 1);
    assert.match(r.stderr, /ceiling/);
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
});

test("the ceiling stops later calls once the spend reaches it", () => {
  const { dir, calls, r, regraded } = regrade({ maxCost: 0.02 });
  try {
    assert.notEqual(r.status, 0);
    assert.equal(calls.length, 2);
    assert.equal(regraded.runs[0].votes.length, 2);
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
});

test("effort is passed to the judge command when given", () => {
  const { dir, calls } = regrade({ args: ["--effort", "low"] });
  try {
    const a = calls[0].args;
    assert.equal(a[a.indexOf("--effort") + 1], "low");
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
});
