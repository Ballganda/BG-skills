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
  skills: readSkills(), // read once per run, shared by every check that needs the skill tree
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

// Decomp skills carry lines that guard against skipped steps. Add a row per required line.
const decompRequiredLines = [
  [
    "engineering/decomp-run/SKILL.md",
    "Compare the integration branch's `tools/decomp.py` with `../decomp-setup/scripts/decomp.py`, ignoring line endings.",
  ],
  [
    "engineering/decomp-run/SKILL.md",
    "Never skip a step because the contract, a ticket, or a memory says something about the machine: the tool's result is the evidence.",
  ],
];

function checkDecompRequiredLines({ read, fail }) {
  for (const [file, line] of decompRequiredLines) {
    if (!read(file).includes(line)) fail(`${file}: missing required line: ${line}`);
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

// The plugin ships one restricted agent per role, each with a model and a tool list.
const agentRoles = ["implementer", "explorer", "reviewer", "merger"];

function checkAgentDefinitions({ fail }) {
  for (const role of agentRoles) {
    const rel = `agents/${role}.md`;
    let text;
    try {
      text = readFileSync(join(root, rel), "utf8");
    } catch {
      fail(`${rel}: agent definition for ${role} is missing`);
      continue;
    }
    const front = text.match(/^---\r?\n([\s\S]*?)\r?\n---/)?.[1] ?? "";
    for (const field of ["model", "tools"]) {
      if (!new RegExp(`^${field}:[ \\t]*\\S`, "m").test(front)) fail(`${rel}: ${role} agent lacks a ${field}`);
    }
  }
}

// implement states each subagent's fixed one-line report, the implementer's with its lesson field.
const implementFormats = [
  ["implementer", "`branch | tests: pass or fail | blocker: none or text | lesson: type @ location; type @ location`"],
  ["explorer", "`notes: path`"],
  ["merger", "`merged or conflict | files`"],
];

function checkImplementFormats({ read, fail }) {
  const file = "engineering/implement/SKILL.md";
  const text = read(file);
  for (const [role, format] of implementFormats) {
    if (!text.includes(format)) fail(`${file}: missing the ${role} report format: ${format}`);
  }
}

// code-review hands the Standards reviewer its smell list by path, never pasted,
// and both reviewers report in the one-line finding format, with no word limit.
function checkReviewSmellPointer({ read, fail }) {
  const file = "engineering/code-review/SKILL.md";
  const text = read(file);
  if (/past(e|ed|ing)\b[^.\n]*smell|smell[^.\n]*\bpast(e|ed|ing)\b/i.test(text))
    fail(`${file}: instructs pasting the smell list instead of passing its path`);
  if (!text.includes("SMELLS.md")) fail(`${file}: does not pass the smell list's path`);
  if (/\*\*Feature Envy\*\*/.test(text)) fail(`${file}: carries the smell list itself instead of SMELLS.md`);
  if (!text.includes("`hard or judgement | location | rule or spec line | finding`"))
    fail(`${file}: missing the reviewer finding format`);
  if (/under \d+ words/i.test(text)) fail(`${file}: sets a word limit instead of the finding format`);
  try {
    read("engineering/code-review/SMELLS.md");
  } catch {
    fail("engineering/code-review/SMELLS.md: smell list reference file is missing");
  }
}

// Every skill directory with a SKILL.md, with its frontmatter and invocation in
// both harnesses: Claude (`disable-model-invocation`) and Codex
// (`allow_implicit_invocation: false` in agents/openai.yaml).
function readSkills() {
  const skillsDir = join(root, "skills");
  const skills = [];
  for (const bucket of readdirSync(skillsDir, { withFileTypes: true })) {
    if (!bucket.isDirectory()) continue;
    for (const skill of readdirSync(join(skillsDir, bucket.name), { withFileTypes: true })) {
      if (!skill.isDirectory()) continue;
      const dir = `${bucket.name}/${skill.name}`;
      let text;
      try {
        text = readFileSync(join(skillsDir, dir, "SKILL.md"), "utf8");
      } catch {
        continue;
      }
      const front = text.match(/^---\r?\n([\s\S]*?)\r?\n---/)?.[1] ?? "";
      const claudeUser = /^disable-model-invocation:\s*true\s*$/m.test(front);
      let codexUser = claudeUser; // no Codex metadata: nothing to disagree with
      let hasCodex = false;
      try {
        const codex = readFileSync(join(skillsDir, dir, "agents", "openai.yaml"), "utf8");
        codexUser = /^\s*allow_implicit_invocation:\s*false\s*$/m.test(codex);
        hasCodex = true;
      } catch {}
      skills.push({ dir, name: skill.name, front, claudeUser, codexUser, hasCodex });
    }
  }
  return skills;
}

// Descriptions are loaded into every session: keep them short.
const descriptionLimits = { user: 20, model: 40 };

function checkDescriptionLengths({ fail, skills }) {
  for (const { dir, front, claudeUser } of skills) {
    const raw = front.match(/^description:[ \t]*(.*)$/m)?.[1] ?? "";
    const description = raw.trim().replace(/^"(.*)"$/, "$1");
    const kind = claudeUser ? "user" : "model";
    const count = description.split(/\s+/).filter(Boolean).length;
    if (count > descriptionLimits[kind]) {
      fail(`${dir}/SKILL.md: description is ${count} words, over the ${kind}-invoked limit of ${descriptionLimits[kind]}`);
    }
  }
}

// Every skill carries Codex metadata. Each is user-invoked in both harnesses or neither. implement and
// diagnosing-bugs call retro, so it must be model-invoked in both.
function checkInvocation({ fail, skills }) {
  for (const { dir, name, claudeUser, codexUser, hasCodex } of skills) {
    if (!hasCodex) {
      fail(`${dir}: missing Codex metadata agents/openai.yaml`);
      continue;
    }
    if (claudeUser !== codexUser) fail(`${dir}: frontmatter and Codex metadata disagree on invocation`);
    if (name !== "retro") continue;
    if (claudeUser) fail(`${dir}/SKILL.md: retro must be model-invoked`);
    if (codexUser) fail(`${dir}/agents/openai.yaml: retro must be model-invoked`);
  }
}

// The plugin icon sits beside the plugin manifest and meets the plugin
// validator's rules. Width and height come from the PNG IHDR chunk, which
// starts right after the 8-byte signature.
const iconRel = ".claude-plugin/icon.png";

function checkPluginIcon({ fail }) {
  let png;
  try {
    png = readFileSync(join(root, iconRel));
  } catch {
    fail(`${iconRel}: plugin icon is missing`);
    return;
  }
  if (png.length < 24 || png.toString("ascii", 12, 16) !== "IHDR") {
    fail(`${iconRel}: plugin icon is not a PNG`);
    return;
  }
  const width = png.readUInt32BE(16);
  const height = png.readUInt32BE(20);
  if (width !== height) fail(`${iconRel}: plugin icon is ${width}x${height}, not square`);
  for (const side of new Set([width, height])) {
    if (side < 512 || side > 2048) fail(`${iconRel}: plugin icon side is ${side} px, outside 512 to 2048`);
  }
  if (png.length > 2 * 1024 * 1024) fail(`${iconRel}: plugin icon is ${png.length} bytes, over 2 MB`);
}

const checks = [
  checkBoundaryLines,
  checkDecompRequiredLines,
  checkDescriptionLengths,
  checkTicketTiers,
  checkModelsDoc,
  checkAgentDefinitions,
  checkImplementFormats,
  checkInvocation,
  checkReviewSmellPointer,
  checkPluginIcon,
];

for (const check of checks) check(ctx);

if (failures.length) {
  for (const f of failures) console.error(`FAIL ${f}`);
  process.exit(1);
}
console.log(`skills check passed (${checks.length} checks)`);
