#!/usr/bin/env node
// Tests of the static skills check at its one seam: the command line.
// Runs scripts/check-skills.mjs against the real tree (expects exit 0) and
// against mutated temp copies of the skills tree (expects non-zero).
// Run: node scripts/test-check-skills.mjs

import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { cpSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { test } from "node:test";

const repo = join(dirname(fileURLToPath(import.meta.url)), "..");
const script = join(repo, "scripts", "check-skills.mjs");

const run = (root) =>
  spawnSync(process.execPath, [script, ...(root ? [root] : [])], { encoding: "utf8" });

// Copy the skills tree, apply a mutation to one file, run the check, clean up.
function mutated(file, mutate) {
  const dir = mkdtempSync(join(tmpdir(), "check-skills-"));
  try {
    cpSync(join(repo, "skills"), join(dir, "skills"), { recursive: true });
    const path = join(dir, "skills", file);
    writeFileSync(path, mutate(readFileSync(path, "utf8")));
    return run(dir);
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
}

const dropLine = (needle) => (text) =>
  text
    .split("\n")
    .filter((line) => !line.includes(needle))
    .join("\n");

test("passes on the real tree", () => {
  const r = run();
  assert.equal(r.status, 0, r.stderr);
});

const boundaries = [
  ["engineering/grill/SKILL.md", "Stay in this session"],
  ["engineering/spec-gen/SKILL.md", "If your context is over 150k"],
  ["engineering/ticket-gen/SKILL.md", "Always start a new chat before `/implement`"],
  ["engineering/implement/SKILL.md", "Always start a new chat before `/code-review`"],
];

for (const [file, needle] of boundaries) {
  test(`fails when ${file} loses its boundary line`, () => {
    const r = mutated(file, dropLine(needle));
    assert.notEqual(r.status, 0);
    assert.match(r.stderr, new RegExp(file.split("/")[1]));
  });
}

test("fails when one word of the 150k sentence changes", () => {
  const r = mutated("engineering/spec-gen/SKILL.md", (t) =>
    t.replace("it is suggested to clear", "it is advised to clear"),
  );
  assert.notEqual(r.status, 0);
});
