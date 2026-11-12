#!/usr/bin/env node
// Tests the kept Reply and grader votes the eval summary writes.
// Run: node scripts/test-eval-replies.mjs

import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { mkdtempSync, readFileSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { test } from "node:test";

const here = (p) => fileURLToPath(new URL(p, import.meta.url));

function summarise() {
  const out = mkdtempSync(join(tmpdir(), "eval-replies-"));
  const r = spawnSync(
    process.execPath,
    [here("./grill-eval-summary.mjs"), here("./fixtures/eval-aggregate/aggregate-result.json"), out],
    { encoding: "utf8" },
  );
  assert.equal(r.status, 0, r.stderr);
  return { out, stdout: r.stdout };
}

test("replies.md holds each arm's final Reply beside the grader votes", () => {
  const { out } = summarise();
  try {
    const md = readFileSync(join(out, "replies.md"), "utf8");
    assert.match(md, /reply-fixture/);
    const withArm = md.split("### with, run 1")[1].split("### without")[0];
    assert.ok(withArm.includes("> Done: the build is green.\n> - 3 files changed"));
    assert.ok(!withArm.includes("Let me look."));
    assert.match(withArm, /outcome-first: PASS PASS FAIL/);
    assert.match(withArm, /detail: FAIL FAIL FAIL/);
    const withoutArm = md.split("### without, run 1")[1];
    assert.ok(withoutArm.includes("> Here is a long status with many facts."));
    assert.match(withoutArm, /outcome-first: FAIL PASS FAIL/);
  } finally {
    rmSync(out, { recursive: true, force: true });
  }
});

test("the summary still reports output tokens per case", () => {
  const { out, stdout } = summarise();
  try {
    assert.match(stdout, /\| reply-fixture \|.*\| 120 \|/);
    assert.deepEqual(JSON.parse(readFileSync(join(out, "summary.json"), "utf8")).cases[0].outputTokens, [120]);
  } finally {
    rmSync(out, { recursive: true, force: true });
  }
});
