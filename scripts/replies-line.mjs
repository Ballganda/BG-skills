#!/usr/bin/env node
// The Replies line that bg-setup writes into a repo's `## Agent skills` block.
// Eval fixtures take it from bg-setup's SKILL.md so there is one copy.
//
// Usage: node scripts/replies-line.mjs [path-to-bg-setup-SKILL.md]
// Prints the line (without a trailing newline).

import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const REPO = join(dirname(fileURLToPath(import.meta.url)), "..");
export const BG_SETUP = join(REPO, "skills", "engineering", "bg-setup", "SKILL.md");

// Returns the template line: the first line inside a fenced block that starts
// with "- Replies:". Throws when there is none.
export function extractRepliesLine(text) {
  let fenced = false;
  for (const raw of text.split(/\r?\n/)) {
    if (raw.startsWith("```")) fenced = !fenced;
    else if (fenced && raw.startsWith("- Replies:")) return raw.trimEnd();
  }
  throw new Error("no '- Replies:' line inside a fenced block");
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  process.stdout.write(extractRepliesLine(readFileSync(process.argv[2] ?? BG_SETUP, "utf8")));
}
