#!/usr/bin/env node
// Tests of the reply-context-proof case and of the staging that puts a
// case's seeded CLAUDE.md into the agent's context.
// Run: node scripts/test-eval-context.mjs

import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
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
