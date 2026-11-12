#!/usr/bin/env node
// Tests of the login check in scripts/eval-grill.sh. A stub `claude` on PATH
// stands in for the real CLI, so nothing is spent and nobody is logged out.
// Run: node scripts/test-eval-login.mjs

import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { chmodSync, existsSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { test } from "node:test";

const repo = fileURLToPath(new URL("..", import.meta.url));
const script = join(repo, "scripts", "eval-grill.sh");

// Runs the eval runner with a stub `claude` that reports the given login state
// for `claude auth status` and records every call. Returns the runner's result
// and the recorded calls. The label is removed afterwards so no results stay.
function runWithStub(loggedIn) {
  const stubDir = mkdtempSync(join(tmpdir(), "eval-login-stub-"));
  const callLog = join(stubDir, "calls.log");
  const label = `login-test-${process.pid}-${loggedIn ? "in" : "out"}`;
  const outDir = join(repo, "evals", "results", label);
  writeFileSync(
    join(stubDir, "claude"),
    [
      "#!/usr/bin/env bash",
      `echo "$*" >> "${callLog}"`,
      'if [ "$1" = auth ] && [ "$2" = status ]; then',
      `  echo '{"loggedIn": ${loggedIn}}'`,
      `  exit ${loggedIn ? 0 : 1}`,
      "fi",
      "exit 0",
      "",
    ].join("\n"),
  );
  chmodSync(join(stubDir, "claude"), 0o755);
  try {
    const result = spawnSync("bash", [script, label], {
      encoding: "utf8",
      env: { ...process.env, PATH: `${stubDir}:${process.env.PATH}` },
    });
    const calls = existsSync(callLog) ? readFileSync(callLog, "utf8") : "";
    return { result, calls, outDir, stubDir };
  } finally {
    rmSync(outDir, { recursive: true, force: true });
  }
}

test("logged out: exits non-zero with one line naming the login command", () => {
  const { result, calls, outDir, stubDir } = runWithStub(false);
  try {
    assert.notEqual(result.status, 0, result.stdout + result.stderr);
    const lines = result.stderr.trim().split("\n");
    assert.equal(lines.length, 1, result.stderr);
    assert.match(lines[0], /claude auth login/);
  } finally {
    rmSync(stubDir, { recursive: true, force: true });
  }
  assert.match(calls, /auth status/);
  assert.doesNotMatch(calls, /plugin eval/, "the eval must not start when logged out");
  assert.equal(existsSync(outDir), false, "no results may be written when logged out");
});

test("logged in: the runner goes on to the eval without the login message", () => {
  const { result, calls, stubDir } = runWithStub(true);
  try {
    assert.match(calls, /auth status/);
    assert.match(calls, /plugin eval/);
    assert.doesNotMatch(result.stderr, /auth login/);
  } finally {
    rmSync(stubDir, { recursive: true, force: true });
  }
});
