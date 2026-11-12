#!/usr/bin/env node
// Tests of the Replies-line extractor used by the reply evals.
// Run: node scripts/test-replies-line.mjs

import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { test } from "node:test";
import { BG_SETUP, extractRepliesLine } from "./replies-line.mjs";

const doc = [
  "Prose mentioning `- Replies:` is not the template.",
  "- Replies: outside a fence",
  "```markdown",
  "## Agent skills",
  "- Triage labels: see x.",
  "- Replies: the template line.",
  "```",
].join("\r\n");

test("takes the Replies line from inside the fenced block", () => {
  assert.equal(extractRepliesLine(doc), "- Replies: the template line.");
});

test("throws when the template has no Replies line", () => {
  assert.throws(() => extractRepliesLine("```\n- Triage labels: x\n```\n"));
});

test("the CLI prints exactly the line bg-setup holds", () => {
  const out = spawnSync(process.execPath, [new URL("./replies-line.mjs", import.meta.url).pathname.replace(/^\/(\w:)/, "$1")], { encoding: "utf8" });
  assert.equal(out.status, 0, out.stderr);
  assert.ok(readFileSync(BG_SETUP, "utf8").includes(out.stdout));
  assert.match(out.stdout, /^- Replies: /);
  assert.ok(!out.stdout.includes("\n"));
});
