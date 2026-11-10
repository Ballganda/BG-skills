#!/usr/bin/env node
// Static check over the skills tree. Uses no tokens; exits 1 on any failure.
// Usage: node scripts/check-skills.mjs [repo-root]
// To add a check, push a function onto `checks`: it receives a `ctx` and calls
// `ctx.fail(message)` for each problem.

import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = process.argv[2] ?? join(dirname(fileURLToPath(import.meta.url)), "..");
const failures = [];

const ctx = {
  read: (rel) => readFileSync(join(root, "skills", rel), "utf8"),
  fail: (message) => failures.push(message),
};

// Each creation-flow skill ends its closing message with one boundary line.
const boundaryLines = [
  ["engineering/grill/SKILL.md", "Stay in this session for `/spec-gen`."],
  [
    "engineering/spec-gen/SKILL.md",
    "If your context is over 150k, it is suggested to clear or start a new chat before /ticket-gen.",
  ],
  ["engineering/ticket-gen/SKILL.md", "Always start a new chat before `/implement`."],
  ["engineering/implement/SKILL.md", "Always start a new chat before `/code-review`."],
];

function checkBoundaryLines({ read, fail }) {
  for (const [file, line] of boundaryLines) {
    if (!read(file).includes(line)) fail(`${file}: missing boundary line: ${line}`);
  }
}

// ticket-gen's two templates each carry a tier field.
function checkTicketTiers({ read, fail }) {
  const text = read("engineering/ticket-gen/SKILL.md");
  if (!text.includes("**Tier:**")) fail("engineering/ticket-gen/SKILL.md: local ticket template lacks a tier field");
  if (!text.includes("## Tier")) fail("engineering/ticket-gen/SKILL.md: issue template lacks a tier field");
}

// bg-setup writes the models doc from its seed template.
function checkModelsDoc({ read, fail }) {
  if (!read("engineering/bg-setup/SKILL.md").includes("[models.md](./models.md)"))
    fail("engineering/bg-setup/SKILL.md: no longer writes the models doc");
  try {
    read("engineering/bg-setup/models.md");
  } catch {
    fail("engineering/bg-setup/models.md: models doc seed template is missing");
  }
}

const checks = [checkBoundaryLines, checkTicketTiers, checkModelsDoc];

for (const check of checks) check(ctx);

if (failures.length) {
  for (const f of failures) console.error(`FAIL ${f}`);
  process.exit(1);
}
console.log(`skills check passed (${checks.length} checks)`);
