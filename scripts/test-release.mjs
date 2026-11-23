#!/usr/bin/env node
// Tests of the local release command at its one seam: the command line.
// Each case builds a scratch git repository with a local bare repository as
// its remote, runs scripts/release.mjs in it, and asserts on the exit code, the
// printed lines and the resulting commits, tags and files. No network: the
// version step is a small fake named by RELEASE_VERSION_COMMAND (the real one
// needs a GitHub token), and the publishing step is skipped with --skip-publish.
// Run: node scripts/test-release.mjs

import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { mkdirSync, mkdtempSync, readFileSync, readdirSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { test } from "node:test";

const here = fileURLToPath(new URL(".", import.meta.url));
const RELEASE = join(here, "release.mjs");
const COMMIT_MESSAGE = "chore: version skills";

// The fake version step: bumps the patch number in package.json, syncs the
// plugin manifest, writes a changelog section and removes the changesets.
const FAKE_VERSION = `
import { readFileSync, readdirSync, rmSync, writeFileSync } from "node:fs";
const pkg = JSON.parse(readFileSync("package.json", "utf8"));
const [major, minor, patch] = pkg.version.split(".").map(Number);
pkg.version = [major, minor, patch + 1].join(".");
writeFileSync("package.json", JSON.stringify(pkg, null, 2) + "\\n");
const plugin = JSON.parse(readFileSync(".claude-plugin/plugin.json", "utf8"));
plugin.version = pkg.version;
writeFileSync(".claude-plugin/plugin.json", JSON.stringify(plugin, null, 2) + "\\n");
const old = readFileSync("CHANGELOG.md", "utf8").replace("# scratch\\n\\n", "");
writeFileSync("CHANGELOG.md", "# scratch\\n\\n## " + pkg.version + "\\n\\n### Patch Changes\\n\\n- Fixed the thing.\\n\\n" + old);
for (const f of readdirSync(".changeset")) if (f.endsWith(".md") && f !== "README.md") rmSync(".changeset/" + f);
`;

function sh(cwd, cmd, args) {
  const r = spawnSync(cmd, args, { cwd, encoding: "utf8" });
  assert.equal(r.status, 0, `${cmd} ${args.join(" ")} failed: ${r.stderr}`);
  return r.stdout.trim();
}

class Scratch {
  constructor() {
    this.base = mkdtempSync(join(tmpdir(), "release-"));
    this.remote = join(this.base, "remote.git");
    this.root = join(this.base, "proj");
    mkdirSync(this.root);
    sh(this.base, "git", ["init", "-q", "--bare", "-b", "main", this.remote]);
    this.git("init", "-q", "-b", "main");
    for (const [k, v] of [["user.name", "Test"], ["user.email", "test@example.invalid"],
      ["commit.gpgsign", "false"], ["core.autocrlf", "false"]]) this.git("config", k, v);
    this.git("remote", "add", "origin", this.remote);
    mkdirSync(join(this.root, ".claude-plugin"));
    mkdirSync(join(this.root, ".changeset"));
    writeFileSync(join(this.root, "package.json"), JSON.stringify({ name: "bg-skills", version: "1.2.3" }, null, 2) + "\n");
    writeFileSync(join(this.root, ".claude-plugin", "plugin.json"), JSON.stringify({ name: "bg-skills", version: "1.2.3" }, null, 2) + "\n");
    writeFileSync(join(this.root, "CHANGELOG.md"), "# scratch\n\n## 1.2.3\n\n- Older note.\n");
    writeFileSync(join(this.root, ".changeset", "README.md"), "Changesets live here.\n");
    writeFileSync(join(this.root, "fake-version.mjs"), FAKE_VERSION);
    this.addChangeset("one");
    this.git("add", "-A");
    this.git("commit", "-q", "-m", "first");
    this.git("push", "-q", "origin", "main");
  }

  git(...args) { return sh(this.root, "git", args); }

  addChangeset(name) {
    writeFileSync(join(this.root, ".changeset", `${name}.md`), `---\n"bg-skills": patch\n---\n\nChange ${name}.\n`);
  }

  commitFile(rel, text) {
    writeFileSync(join(this.root, rel), text);
    this.git("add", "-A");
    this.git("commit", "-q", "-m", "more: " + rel);
  }

  run(...args) {
    return spawnSync(process.execPath, [RELEASE, ...args], {
      cwd: this.root,
      encoding: "utf8",
      env: { ...process.env, RELEASE_VERSION_COMMAND: `node "${join(this.root, "fake-version.mjs")}"` },
    });
  }

  // Runs with the default version command (the variable unset); the scratch
  // repository has no node_modules.
  runDefault(...args) {
    const env = { ...process.env };
    delete env.RELEASE_VERSION_COMMAND;
    return spawnSync(process.execPath, [RELEASE, ...args], { cwd: this.root, encoding: "utf8", env });
  }

  state() {
    return [this.git("rev-parse", "HEAD"), this.git("status", "--porcelain"), this.git("tag"),
      this.git("--git-dir", this.remote, "tag"), readdirSync(join(this.root, ".changeset")).join(",")].join("|");
  }

  cleanup() { rmSync(this.base, { recursive: true, force: true }); }
}

function withScratch(fn) {
  const s = new Scratch();
  try { fn(s); } finally { s.cleanup(); }
}

function refuses(s, cause) {
  const before = s.state();
  const r = s.run("--skip-publish");
  assert.notEqual(r.status, 0, r.stdout);
  assert.match(r.stderr, cause);
  assert.equal(s.state(), before, "a refusal changes nothing");
}

test("a dry run prints the version, the changesets and the steps, and changes nothing", () => withScratch((s) => {
  s.addChangeset("two");
  s.git("add", "-A");
  s.git("commit", "-q", "-m", "second changeset");
  s.git("push", "-q", "origin", "main");
  const before = s.state();
  const r = s.run("--dry-run");
  assert.equal(r.status, 0, r.stderr);
  assert.match(r.stdout, /1\.2\.4/);
  assert.match(r.stdout, /one\.md/);
  assert.match(r.stdout, /two\.md/);
  for (const step of ["version", "commit", "tag v1.2.4", "push", "gh release create"]) assert.ok(r.stdout.includes(step), step);
  assert.equal(s.state(), before);
}));

test("it refuses when the checkout is not on main", () => withScratch((s) => {
  s.git("checkout", "-q", "-b", "feature");
  refuses(s, /not on main/);
}));

test("it refuses when the checkout is dirty", () => withScratch((s) => {
  writeFileSync(join(s.root, "stray.txt"), "x\n");
  refuses(s, /not clean/);
}));

test("it refuses when main is behind the remote", () => withScratch((s) => {
  s.commitFile("a.txt", "a\n");
  s.git("push", "-q", "origin", "main");
  s.git("reset", "-q", "--hard", "HEAD~1");
  refuses(s, /not level with origin\/main/);
}));

test("it refuses when main is ahead of the remote", () => withScratch((s) => {
  s.commitFile("a.txt", "a\n");
  refuses(s, /not level with origin\/main/);
}));

test("it refuses when no changeset is pending", () => withScratch((s) => {
  s.git("rm", "-q", ".changeset/one.md");
  s.git("commit", "-q", "-m", "drop changeset");
  s.git("push", "-q", "origin", "main");
  refuses(s, /no pending changeset/);
}));

test("a real run leaves one commit and a tag, both on the remote", () => withScratch((s) => {
  const start = s.git("rev-parse", "HEAD");
  const dry = s.run("--dry-run");
  const r = s.run("--skip-publish");
  assert.equal(r.status, 0, r.stderr);
  assert.equal(s.git("rev-list", "--count", `${start}..HEAD`), "1");
  assert.equal(s.git("log", "-1", "--format=%B"), COMMIT_MESSAGE);
  assert.equal(s.git("rev-parse", "v1.2.4^{commit}"), s.git("rev-parse", "HEAD"));
  assert.equal(sh(s.base, "git", ["--git-dir", s.remote, "rev-parse", "main"]), s.git("rev-parse", "HEAD"));
  assert.equal(sh(s.base, "git", ["--git-dir", s.remote, "rev-parse", "v1.2.4^{commit}"]), s.git("rev-parse", "HEAD"));
  assert.equal(s.git("status", "--porcelain"), "");
  assert.deepEqual(readdirSync(join(s.root, ".changeset")), ["README.md"]);
  const pkg = JSON.parse(readFileSync(join(s.root, "package.json"), "utf8"));
  const plugin = JSON.parse(readFileSync(join(s.root, ".claude-plugin", "plugin.json"), "utf8"));
  assert.equal(pkg.version, "1.2.4");
  assert.equal(plugin.version, pkg.version);
  assert.match(dry.stdout, /1\.2\.4/);
  // The notes it would publish are the new version's section of the changelog.
  assert.match(r.stdout, /Release notes for v1\.2\.4/);
  assert.match(r.stdout, /Fixed the thing\./);
  assert.ok(!r.stdout.includes("Older note."), "only the new section");
  assert.match(r.stdout, /skipped/);
}));

test("a failure after the commit names the step and the command that finishes it", () => withScratch((s) => {
  s.git("tag", "v1.2.4");
  const r = s.run("--skip-publish");
  assert.notEqual(r.status, 0);
  assert.match(r.stderr, /step "tag" failed/);
  assert.ok(r.stderr.includes("git tag v1.2.4"), r.stderr);
  assert.ok(r.stderr.includes("git push origin main v1.2.4"), r.stderr);
  assert.equal(s.git("log", "-1", "--format=%B"), COMMIT_MESSAGE);
}));

test("with the default version command and no installed dependencies, a real run refuses and names npm ci", () => withScratch((s) => {
  const before = s.state();
  const r = s.runDefault("--skip-publish");
  assert.notEqual(r.status, 0, r.stdout);
  assert.match(r.stderr, /release refused: .*dependencies are not installed.*npm ci/);
  assert.equal(s.state(), before, "a refusal changes nothing");
}));

test("with the default version command and no installed dependencies, a dry run warns and changes nothing", () => withScratch((s) => {
  const before = s.state();
  const r = s.runDefault("--dry-run");
  assert.equal(r.status, 0, r.stderr);
  assert.match(r.stdout, /1\.2\.4/);
  assert.match(r.stdout, /one\.md/);
  assert.match(r.stdout, /warning: a real run would refuse: the dependencies are not installed.*npm ci/i);
  assert.equal(s.state(), before);
}));

test("with the version command replaced, a dry run does not warn of missing dependencies", () => withScratch((s) => {
  const r = s.run("--dry-run");
  assert.equal(r.status, 0, r.stderr);
  assert.ok(!/npm ci/.test(r.stdout + r.stderr));
}));
