#!/usr/bin/env node
// Static check over the skills tree. Uses no tokens; exits 1 on any failure.
// Usage: node scripts/check-skills.mjs [repo-root]
// To add a check, push a function onto `checks`: it receives a `ctx` and calls
// `ctx.fail(message)` for each problem.

import { readdirSync, readFileSync } from "node:fs";
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


// Descriptions are loaded into every session: keep them short.
const descriptionLimits = { user: 20, model: 40 };

function checkDescriptionLengths({ fail }) {
  const skillsDir = join(root, "skills");
  for (const bucket of readdirSync(skillsDir, { withFileTypes: true })) {
    if (!bucket.isDirectory()) continue;
    for (const skill of readdirSync(join(skillsDir, bucket.name), { withFileTypes: true })) {
      if (!skill.isDirectory()) continue;
      const rel = `${bucket.name}/${skill.name}/SKILL.md`;
      let text;
      try {
        text = readFileSync(join(skillsDir, rel), "utf8");
      } catch {
        continue;
      }
      const front = text.match(/^---\r?\n([\s\S]*?)\r?\n---/)?.[1] ?? "";
      const raw = front.match(/^description:[ \t]*(.*)$/m)?.[1] ?? "";
      const description = raw.trim().replace(/^"(.*)"$/, "$1");
      const kind = /^disable-model-invocation:\s*true\s*$/m.test(front) ? "user" : "model";
      const count = description.split(/\s+/).filter(Boolean).length;
      if (count > descriptionLimits[kind]) {
        fail(`${rel}: description is ${count} words, over the ${kind}-invoked limit of ${descriptionLimits[kind]}`);
      }
    }
  }
}

const checks = [checkBoundaryLines, checkDescriptionLengths, checkTicketTiers, checkModelsDoc];

for (const check of checks) check(ctx);

if (failures.length) {
  for (const f of failures) console.error(`FAIL ${f}`);
  process.exit(1);
}
console.log(`skills check passed (${checks.length} checks)`);
