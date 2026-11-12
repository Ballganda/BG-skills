#!/usr/bin/env node
// Stages the eval cases for `claude plugin eval --eval-dir`, so the CLAUDE.md
// a case's scaffold seeds is in the context of the agent under test.
//
// The eval child runs with `--setting-sources user`, so it never loads the
// project CLAUDE.md the scaffold writes into its workspace (ticket #83). This
// copies every case directory under <evals-dir> (not results/) to
// <staged-dir>, runs each case.yaml case's scaffold in a scratch directory,
// and, when that seeds a CLAUDE.md, gives the case its text as
// `execution.append_system_prompt`. The text still comes only from the
// scaffold (for reply cases, scripts/seed-agent-skills.sh and so the bg-setup
// template), so it has one source.
//
// Usage: node scripts/stage-evals.mjs <evals-dir> <staged-dir> [--no-scaffold]
// With --no-scaffold (the eval run skips scaffolds too) the cases are copied
// unchanged, so nothing seeded reaches the agent.
// <staged-dir> must sit at the same depth as <evals-dir>, because scaffolds
// reach shared scripts by a relative path from their own directory.

import { spawnSync } from "node:child_process";
import { cpSync, existsSync, mkdtempSync, readdirSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";

const [evalsDir, stagedDir] = process.argv.slice(2, 4).map((p) => p && resolve(p));
const noScaffold = process.argv.includes("--no-scaffold");
if (!evalsDir || !stagedDir) {
  console.error("usage: stage-evals.mjs <evals-dir> <staged-dir> [--no-scaffold]");
  process.exit(2);
}

const KEY = "append_system_prompt";

// Runs the case's scaffold the way the eval does (bash, in an empty working
// directory) and returns the CLAUDE.md it seeds, or null.
function seededClaudeMd(caseDir, scaffold) {
  const work = mkdtempSync(join(tmpdir(), "eval-stage-"));
  try {
    const script = join(caseDir, scaffold).replace(/\\/g, "/");
    const r = spawnSync("bash", [script], { cwd: work, encoding: "utf8" });
    if (r.status !== 0) throw new Error(`scaffold ${script} failed (exit ${r.status}): ${r.stderr}${r.error ?? ""}`);
    const file = join(work, "CLAUDE.md");
    return existsSync(file) ? readFileSync(file, "utf8").replace(/\r\n/g, "\n") : null;
  } finally {
    rmSync(work, { recursive: true, force: true });
  }
}

// Inserts the key as the first line of the execution block. A JSON string is
// a valid YAML double-quoted scalar, so the text needs no other escaping.
function withAppendedPrompt(caseYaml, text) {
  const lines = caseYaml.replace(/\r\n/g, "\n").split("\n");
  const end = lines.indexOf("---");
  const head = end === -1 ? lines : lines.slice(0, end);
  if (head.some((l) => l.trimStart().startsWith(`${KEY}:`))) throw new Error(`case.yaml already sets ${KEY}`);
  const value = `  ${KEY}: ${JSON.stringify(text)}`;
  const at = head.indexOf("execution:");
  if (at === -1) lines.splice(head.length, 0, "execution:", value);
  else lines.splice(at + 1, 0, value);
  return lines.join("\n");
}

rmSync(stagedDir, { recursive: true, force: true });
for (const entry of readdirSync(evalsDir, { withFileTypes: true })) {
  if (!entry.isDirectory() || entry.name === "results") continue;
  const src = join(evalsDir, entry.name);
  const dst = join(stagedDir, entry.name);
  cpSync(src, dst, { recursive: true });
  const caseFile = join(src, "case.yaml");
  if (noScaffold || !existsSync(caseFile)) continue;
  const caseYaml = readFileSync(caseFile, "utf8");
  const scaffold = caseYaml.match(/^\s+scaffold_script:\s*(\S+)\s*$/m)?.[1];
  if (!scaffold) continue;
  const text = seededClaudeMd(src, scaffold);
  if (text === null) continue;
  const prompt = `Contents of CLAUDE.md (project instructions, checked into the codebase):\n\n${text}`;
  writeFileSync(join(dst, "case.yaml"), withAppendedPrompt(caseYaml, prompt));
}
