#!/usr/bin/env node
// Cuts a release from main on this machine: versions, commits, tags, pushes,
// and publishes a GitHub release. Run it as `npm run release`.
//
//   npm run release -- --dry-run        print what it would do, change nothing
//   npm run release -- --skip-publish   do everything but the GitHub release
//
// It refuses (naming the cause, changing nothing) unless the checkout is on
// main, clean, level with origin/main, and holds a pending changeset.
//
// RELEASE_VERSION_COMMAND names the command that does the versioning. It
// defaults to `npm run version` (changesets, then the plugin manifest sync).
// The real one needs a GitHub token (the changelog generator calls the GitHub
// API), so the test points this variable at a small fake and starts no network
// call. The test also passes --skip-publish, since `gh release create` must
// never run in a test.

import { spawnSync } from "node:child_process";
import { mkdtempSync, readFileSync, readdirSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

const COMMIT_MESSAGE = "chore: version skills";
const VERSION_COMMAND = process.env.RELEASE_VERSION_COMMAND || "npm run version";
const dryRun = process.argv.includes("--dry-run");
const skipPublish = process.argv.includes("--skip-publish");

function run(cmd, args, opts = {}) {
  return spawnSync(cmd, args, { encoding: "utf8", ...opts });
}

function git(...args) {
  const r = run("git", args);
  if (r.status !== 0) {
    console.error(`release: git ${args.join(" ")} failed: ${(r.stderr || r.stdout).trim()}`);
    process.exit(1);
  }
  return r.stdout.trim();
}

function refuse(cause) {
  console.error(`release refused: ${cause}. Nothing was changed.`);
  process.exit(1);
}

const root = git("rev-parse", "--show-toplevel");
process.chdir(root);

const pendingChangesets = () =>
  readdirSync(".changeset").filter((f) => f.endsWith(".md") && f !== "README.md").sort();

// Refusals.
const branch = git("rev-parse", "--abbrev-ref", "HEAD");
if (branch !== "main") refuse(`not on main (on ${branch})`);
if (git("status", "--porcelain") !== "") refuse("the checkout is not clean (uncommitted or untracked files)");
git("fetch", "-q", "origin", "main");
if (git("rev-parse", "HEAD") !== git("rev-parse", "origin/main")) {
  refuse("main is not level with origin/main (pull or push first)");
}
const changesets = pendingChangesets();
if (changesets.length === 0) refuse("no pending changeset in .changeset/");

// The version a dry run would cut: the highest bump among the changesets.
function nextVersion() {
  const rank = { patch: 0, minor: 1, major: 2 };
  let top = "patch";
  for (const f of changesets) {
    const front = readFileSync(join(".changeset", f), "utf8").match(/^---\r?\n([\s\S]*?)\r?\n---/);
    for (const m of front ? front[1].matchAll(/:\s*(patch|minor|major)\s*$/gm) : []) {
      if (rank[m[1]] > rank[top]) top = m[1];
    }
  }
  const [major, minor, patch] = JSON.parse(readFileSync("package.json", "utf8")).version.split(".").map(Number);
  if (top === "major") return `${major + 1}.0.0`;
  if (top === "minor") return `${major}.${minor + 1}.0`;
  return `${major}.${minor}.${patch + 1}`;
}

const publishCommand = (version) => `gh release create v${version} --title v${version} --notes-file <notes>`;

if (dryRun) {
  const version = nextVersion();
  console.log(`Dry run: would cut v${version} from main. Nothing is changed.`);
  console.log("Changesets it would consume:");
  for (const f of changesets) console.log(`  .changeset/${f}`);
  console.log("Steps:");
  console.log(`  1. version: ${VERSION_COMMAND}`);
  console.log(`  2. commit: git commit -m "${COMMIT_MESSAGE}"`);
  console.log(`  3. tag v${version}: git tag v${version}`);
  console.log(`  4. push: git push origin main v${version}`);
  console.log(`  5. ${skipPublish ? "publish (skipped by --skip-publish)" : "publish"}: ${publishCommand(version)}`);
  console.log("     notes: the new version's section of CHANGELOG.md");
  process.exit(0);
}

// The version step may leave files changed if it fails: the checkout was
// clean, so `git restore .` and `git clean -fd .changeset` undo it.
console.log(`Step "version": ${VERSION_COMMAND}`);
const versioned = run(VERSION_COMMAND, [], { shell: true, stdio: "inherit" });
if (versioned.status !== 0) {
  console.error(`release: step "version" failed before any commit. Undo with: git restore . && git clean -fd`);
  process.exit(1);
}
const version = JSON.parse(readFileSync("package.json", "utf8")).version;
const tag = `v${version}`;

function changelogSection(v) {
  const lines = readFileSync("CHANGELOG.md", "utf8").split(/\r?\n/);
  const start = lines.findIndex((l) => l.trim() === `## ${v}`);
  if (start === -1) return null;
  let end = lines.findIndex((l, i) => i > start && l.startsWith("## "));
  if (end === -1) end = lines.length;
  return lines.slice(start + 1, end).join("\n").trim() + "\n";
}

// From the commit on, each step that fails names itself and the commands that
// finish the release by hand.
const steps = [
  { name: "commit", cmd: ["git", "add", "-A"], then: ["git", "commit", "-q", "-m", COMMIT_MESSAGE],
    manual: `git add -A && git commit -m "${COMMIT_MESSAGE}"` },
  { name: "tag", cmd: ["git", "tag", tag], manual: `git tag ${tag}` },
  { name: "push", cmd: ["git", "push", "origin", "main", tag], manual: `git push origin main ${tag}` },
];

const manualCommands = steps.map((s) => s.manual);
manualCommands.push(publishCommand(version));

for (const [i, step] of steps.entries()) {
  console.log(`Step "${step.name}": ${step.manual}`);
  let r = run(step.cmd[0], step.cmd.slice(1));
  if (r.status === 0 && step.then) r = run(step.then[0], step.then.slice(1));
  if (r.status !== 0) {
    console.error(`release: step "${step.name}" failed: ${(r.stderr || r.stdout).trim()}`);
    console.error("Finish the release by hand with:");
    for (const c of manualCommands.slice(i)) console.error(`  ${c}`);
    process.exit(1);
  }
}

const notes = changelogSection(version);
if (notes === null) {
  console.error(`release: step "publish" failed: CHANGELOG.md has no "## ${version}" section.`);
  console.error(`Finish the release by hand with:\n  ${publishCommand(version)}`);
  process.exit(1);
}
console.log(`Release notes for ${tag}:\n${notes}`);
if (skipPublish) {
  console.log("Publish step skipped by --skip-publish.");
  console.log(`To publish by hand: ${publishCommand(version)}`);
  process.exit(0);
}
const dir = mkdtempSync(join(tmpdir(), "release-notes-"));
const file = join(dir, "notes.md");
writeFileSync(file, notes);
console.log(`Step "publish": gh release create ${tag}`);
const published = run("gh", ["release", "create", tag, "--title", tag, "--notes-file", file], { stdio: "inherit" });
rmSync(dir, { recursive: true, force: true });
if (published.status !== 0) {
  console.error(`release: step "publish" failed. Finish the release by hand with:\n  ${publishCommand(version)}`);
  console.error(`(write the "## ${version}" section of CHANGELOG.md to a file and pass it as --notes-file)`);
  process.exit(1);
}
console.log(`Released ${tag}.`);
