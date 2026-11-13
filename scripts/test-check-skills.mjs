#!/usr/bin/env node
// Tests of the static skills check at its one seam: the command line.
// Runs scripts/check-skills.mjs against the real tree (expects exit 0) and
// against mutated temp copies of the tree (expects non-zero).
// Run: node scripts/test-check-skills.mjs

import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { cpSync, mkdtempSync, readFileSync, rmSync, unlinkSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { test } from "node:test";

const repo = join(dirname(fileURLToPath(import.meta.url)), "..");
const script = join(repo, "scripts", "check-skills.mjs");

const run = (root) =>
  spawnSync(process.execPath, [script, ...(root ? [root] : [])], { encoding: "utf8" });

// Copy the checked trees into a temp dir, let `change` edit the copy, run the
// check, clean up.
function withCopy(change) {
  const dir = mkdtempSync(join(tmpdir(), "check-skills-"));
  try {
    for (const tree of ["skills", "agents", ".claude-plugin"]) {
      cpSync(join(repo, tree), join(dir, tree), { recursive: true });
    }
    change(dir);
    return run(dir);
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
}

// Apply a mutation to one text file (a path under skills/, or under the repo
// root when `fromRoot`) in a copy of the tree and run the check.
const mutated = (file, mutate, fromRoot = false) =>
  withCopy((dir) => {
    const path = fromRoot ? join(dir, file) : join(dir, "skills", file);
    writeFileSync(path, mutate(readFileSync(path, "utf8")));
  });

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

// Required lines in decomp skills: [file, the exact line the check requires].
const decompRequired = [
  [
    "engineering/decomp-run/SKILL.md",
    "Compare the integration branch's `tools/decomp.py` with `../decomp-setup/scripts/decomp.py`, ignoring line endings.",
  ],
  [
    "engineering/decomp-run/SKILL.md",
    "Never skip a step because the contract, a ticket, or a memory says something about the machine: the tool's result is the evidence.",
  ],
  [
    "engineering/decomp-standards/SKILL.md",
    "Every commit a decomp skill makes ends with the harness's attribution lines.",
  ],
  [
    "engineering/decomp-run/SKILL.md",
    "Every commit in this step ends with the harness's attribution lines: see the Commits rule in `decomp-standards`.",
  ],
  [
    "engineering/decomp-setup/CONTRACT.md",
    "The contract records nothing about the current state of this machine (what is installed, logged in, or missing).",
  ],
];

for (const [file, line] of decompRequired) {
  test(`fails naming ${file} when it loses a required line: ${line.slice(0, 30)}`, () => {
    const r = mutated(file, (t) => t.replace(line, ""));
    assert.notEqual(r.status, 0);
    assert.ok(r.stderr.includes(`${file}: missing required line: ${line}`), r.stderr);
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

const makeFrontUserInvoked = (t) =>
  t.replace(/^description:.*$/m, (line) => `${line}\ndisable-model-invocation: true`);
const makeCodexUserInvoked = (t) => `${t.trimEnd()}\npolicy:\n  allow_implicit_invocation: false\n`;

test("fails when a skill other than retro has harnesses that disagree on invocation", () => {
  const r = mutated("engineering/tdd/SKILL.md", makeFrontUserInvoked);
  assert.notEqual(r.status, 0);
  assert.match(r.stderr, /engineering\/tdd: frontmatter and Codex metadata disagree on invocation/);
  assert.doesNotMatch(r.stderr, /retro must be model-invoked/);
});

test("fails when retro's frontmatter makes it user-invoked", () => {
  const r = mutated("engineering/retro/SKILL.md", makeFrontUserInvoked);
  assert.notEqual(r.status, 0);
  assert.match(r.stderr, /engineering\/retro\/SKILL\.md: retro must be model-invoked/);
});

test("fails when retro's Codex metadata makes it user-invoked", () => {
  const r = mutated("engineering/retro/agents/openai.yaml", makeCodexUserInvoked);
  assert.notEqual(r.status, 0);
  assert.match(r.stderr, /engineering\/retro\/agents\/openai\.yaml: retro must be model-invoked/);
});

test("fails when a skill other than retro has no Codex metadata", () => {
  const r = withCopy((dir) => unlinkSync(join(dir, "skills", "engineering", "implement", "agents", "openai.yaml")));
  assert.notEqual(r.status, 0);
  assert.match(r.stderr, /engineering\/implement: missing Codex metadata agents\/openai\.yaml/);
  assert.doesNotMatch(r.stderr, /disagree/);
});

test("fails when retro has no Codex metadata", () => {
  const r = withCopy((dir) => unlinkSync(join(dir, "skills", "engineering", "retro", "agents", "openai.yaml")));
  assert.notEqual(r.status, 0);
  assert.match(r.stderr, /engineering\/retro: missing Codex metadata agents\/openai\.yaml/);
  assert.doesNotMatch(r.stderr, /disagree/);
});

const iconRel = join(".claude-plugin", "icon.png");

test("fails when the plugin icon is missing", () => {
  const r = withCopy((dir) => unlinkSync(join(dir, iconRel)));
  assert.notEqual(r.status, 0);
  assert.match(r.stderr, /icon/);
});

// A PNG signature and IHDR chunk of the given size, padded to `bytes` long.
// Only the header is real: enough for a check that reads width and height.
function fakePng(width, height, bytes = 64) {
  const png = Buffer.alloc(bytes);
  Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]).copy(png, 0);
  png.writeUInt32BE(13, 8);
  png.write("IHDR", 12, "ascii");
  png.writeUInt32BE(width, 16);
  png.writeUInt32BE(height, 20);
  return png;
}

const withIcon = (png) => withCopy((dir) => writeFileSync(join(dir, iconRel), png));

test("fails when the plugin icon is not square", () => {
  const r = withIcon(fakePng(1024, 768));
  assert.notEqual(r.status, 0);
  assert.match(r.stderr, /icon.*square/);
});

test("fails when the plugin icon is under 512 px", () => {
  const r = withIcon(fakePng(511, 511));
  assert.notEqual(r.status, 0);
  assert.match(r.stderr, /icon.*512 to 2048/);
});

test("fails when the plugin icon is over 2 MB", () => {
  const r = withIcon(fakePng(1024, 1024, 2 * 1024 * 1024 + 1));
  assert.notEqual(r.status, 0);
  assert.match(r.stderr, /icon.*2 MB/);
});

test("fails when the plugin icon is over 2048 px", () => {
  const r = withIcon(fakePng(2049, 2049));
  assert.notEqual(r.status, 0);
  assert.match(r.stderr, /icon.*512 to 2048/);
});
