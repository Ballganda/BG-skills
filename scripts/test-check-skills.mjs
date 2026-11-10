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

// Copy the skills and agents trees, apply a mutation to one file (a path under
// skills/, or under the repo root when `fromRoot`), run the check, clean up.
function mutated(file, mutate, fromRoot = false) {
  const dir = mkdtempSync(join(tmpdir(), "check-skills-"));
  try {
    cpSync(join(repo, "skills"), join(dir, "skills"), { recursive: true });
    cpSync(join(repo, "agents"), join(dir, "agents"), { recursive: true });
    const path = fromRoot ? join(dir, file) : join(dir, "skills", file);
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

test("fails when the local ticket template loses its tier field", () => {
  const r = mutated("engineering/ticket-gen/SKILL.md", dropLine("**Tier:**"));
  assert.notEqual(r.status, 0);
  assert.match(r.stderr, /tier/i);
});

test("fails when the issue ticket template loses its tier field", () => {
  const r = mutated("engineering/ticket-gen/SKILL.md", dropLine("## Tier"));
  assert.notEqual(r.status, 0);
  assert.match(r.stderr, /tier/i);
});

test("fails when bg-setup stops writing the models doc", () => {
  const r = mutated("engineering/bg-setup/SKILL.md", dropLine("[models.md](./models.md)"));
  assert.notEqual(r.status, 0);
  assert.match(r.stderr, /models/i);
});

const words = (n) => Array.from({ length: n }, (_, i) => `word${i}`).join(" ");
const setDescription = (n) => (text) => text.replace(/^description:.*$/m, `description: ${words(n)}`);

test("fails when a user-invoked description is over 20 words", () => {
  const r = mutated("engineering/grill/SKILL.md", setDescription(21));
  assert.notEqual(r.status, 0);
  assert.match(r.stderr, /grill.*description/);
});

test("fails when a model-invoked description is over 40 words", () => {
  const r = mutated("engineering/tdd/SKILL.md", setDescription(41));
  assert.notEqual(r.status, 0);
  assert.match(r.stderr, /tdd.*description/);
});

for (const role of ["implementer", "explorer", "reviewer", "merger"]) {
  for (const field of ["model", "tools"]) {
    test(`fails when the ${role} agent loses its ${field}`, () => {
      const r = mutated(`agents/${role}.md`, dropLine(`${field}:`), true);
      assert.notEqual(r.status, 0);
      assert.match(r.stderr, new RegExp(`${role}.*${field}`));
    });
  }
}

const implementFormats = [
  ["implementer format", "`branch | tests: pass or fail | blocker: none or text"],
  ["lesson field", "| lesson: type @ location; type @ location`"],
  ["explorer format", "`notes: path`"],
  ["merger format", "`merged or conflict | files`"],
];

test("fails when code-review instructs pasting the smell list", () => {
  const r = mutated(
    "engineering/code-review/SKILL.md",
    (t) => `${t}\nPaste the smell baseline in full into the Standards prompt.\n`,
  );
  assert.notEqual(r.status, 0);
  assert.match(r.stderr, /code-review.*smell/);
});

test("fails when code-review drops the finding format", () => {
  const r = mutated("engineering/code-review/SKILL.md", (t) =>
    t.split("`hard or judgement | location | rule or spec line | finding`").join(""),
  );
  assert.notEqual(r.status, 0);
  assert.match(r.stderr, /code-review.*format/);
});

test("fails when code-review brings back a word limit", () => {
  const r = mutated("engineering/code-review/SKILL.md", (t) => `${t}\nReport in under 400 words.\n`);
  assert.notEqual(r.status, 0);
  assert.match(r.stderr, /code-review.*word limit/);
});

for (const [name, needle] of implementFormats) {
  test(`fails when implement loses the ${name}`, () => {
    const r = mutated("engineering/implement/SKILL.md", (t) => t.split(needle).join(""));
    assert.notEqual(r.status, 0);
    assert.match(r.stderr, /implement.*format/);
  });
}
