#!/usr/bin/env node
// Tests of the reply-context-proof case and of the staging that puts a
// case's seeded CLAUDE.md into the agent's context.
// Run: node scripts/test-eval-context.mjs

import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { existsSync, mkdtempSync, readFileSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { test } from "node:test";

const here = (p) => fileURLToPath(new URL(p, import.meta.url));

// Applies a regex grader file the way `claude plugin eval` does: the pattern
// is searched in the whole trace, and `match` says whether a hit passes.
function grade(graderFile, traceFile) {
  const md = readFileSync(here(graderFile), "utf8");
  const pattern = md.match(/^pattern: '(.*)'$/m)[1];
  const match = md.match(/^match: (\S+)$/m)?.[1] ?? "contains";
  const hit = new RegExp(pattern).test(readFileSync(here(traceFile), "utf8"));
  return match === "not_contains" ? !hit : hit;
}

const NOT_READ = "../evals/reply-context-proof/graders/seeded-file-not-read.md";
const CANARY = "../evals/reply-context-proof/graders/canary-answered.md";

test("the proof fails a run that found the codeword by reading the seeded file", () => {
  assert.equal(grade(CANARY, "./fixtures/eval-context/read-trace.jsonl"), true);
  assert.equal(grade(NOT_READ, "./fixtures/eval-context/read-trace.jsonl"), false);
});

test("the proof passes a run that answered from its context", () => {
  assert.equal(grade(CANARY, "./fixtures/eval-context/context-trace.jsonl"), true);
  assert.equal(grade(NOT_READ, "./fixtures/eval-context/context-trace.jsonl"), true);
});

// Staging copies the eval cases and gives each case whose scaffold seeds a
// CLAUDE.md that file's text as execution.append_system_prompt, because the
// eval child runs with --setting-sources user and never loads it itself.
function stage(...flags) {
  const out = join(mkdtempSync(join(tmpdir(), "eval-stage-")), "staged");
  const r = spawnSync(process.execPath, [here("./stage-evals.mjs"), here("./fixtures/eval-stage/evals"), out, ...flags], { encoding: "utf8" });
  assert.equal(r.status, 0, r.stderr);
  return out;
}

const appended = (caseYaml) => {
  const line = caseYaml.split("\n").find((l) => l.startsWith("  append_system_prompt: "));
  return line && JSON.parse(line.slice("  append_system_prompt: ".length));
};

test("a case whose scaffold seeds CLAUDE.md gets its text as the appended system prompt", () => {
  const out = stage();
  try {
    const yaml = readFileSync(join(out, "seeds-claude-md", "case.yaml"), "utf8");
    const prompt = appended(yaml);
    assert.ok(prompt.endsWith('# Fixture\n\n- Codeword: say "x" `y`.\n'), prompt);
    assert.match(prompt, /^Contents of CLAUDE\.md/);
    assert.match(yaml, /^execution:\n  append_system_prompt: .*\n  max_turns: 5\n/m);
    assert.ok(existsSync(join(out, "seeds-claude-md", "scaffold.sh")));
  } finally {
    rmSync(out, { recursive: true, force: true });
  }
});

test("a case whose scaffold seeds no CLAUDE.md is copied unchanged, and results are not copied", () => {
  const out = stage();
  try {
    const src = readFileSync(here("./fixtures/eval-stage/evals/no-claude-md/case.yaml"), "utf8");
    assert.equal(readFileSync(join(out, "no-claude-md", "case.yaml"), "utf8"), src);
    assert.ok(!existsSync(join(out, "results")));
  } finally {
    rmSync(out, { recursive: true, force: true });
  }
});

test("with --no-scaffold nothing is seeded, so the proof can be seen to fail", () => {
  const out = stage("--no-scaffold");
  try {
    const src = readFileSync(here("./fixtures/eval-stage/evals/seeds-claude-md/case.yaml"), "utf8");
    assert.equal(readFileSync(join(out, "seeds-claude-md", "case.yaml"), "utf8"), src);
  } finally {
    rmSync(out, { recursive: true, force: true });
  }
});
