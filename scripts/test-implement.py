#!/usr/bin/env python3
"""Tests of the implement orchestration script at its one seam: the command line.

Each case builds a scratch git project in a temporary directory, runs the
script's commands in it, and asserts on exit codes, printed lines, the ledger,
and the resulting branches and worktrees. No network. Standard library only.

Run: python scripts/test-implement.py [name-filter]
"""
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import traceback
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SCRIPT = REPO / "skills" / "engineering" / "implement" / "scripts" / "implement.py"
OK, CONFLICT, USAGE, NOTHING_READY, ENV = 0, 1, 2, 3, 4
INTEGRATION = "spec-1"


def expect(cond, what, r=None):
    if not cond:
        detail = f"\n  exit={r.returncode}\n  stdout={r.stdout!r}\n  stderr={r.stderr!r}" if r is not None else ""
        raise AssertionError(what + detail)


class Project:
    """A scratch git repository with a couple of commits on main."""

    def __init__(self, base):
        self.base = Path(base)
        self.root = self.base / "proj"
        self.root.mkdir()
        self.git("init", "-q", "-b", "main")
        for k, v in (("user.name", "Test"), ("user.email", "test@example.invalid"),
                     ("commit.gpgsign", "false"), ("core.autocrlf", "false")):
            self.git("config", k, v)
        self.commit("README.md", "hello\n", "first")
        self.commit("src.txt", "one\n", "second")

    def git(self, *args, cwd=None):
        r = subprocess.run(["git", *args], cwd=cwd or self.root, capture_output=True, text=True)
        if r.returncode:
            raise AssertionError(f"git {' '.join(args)} failed: {r.stderr}")
        return r.stdout.strip()

    def commit(self, rel, text, msg):
        p = self.root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8", newline="\n")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", msg)

    def run(self, *args, cwd=None, clean=True):
        r = subprocess.run([sys.executable, str(SCRIPT), *args], cwd=cwd or self.root,
                           capture_output=True, text=True)
        if clean:
            expect(self.git("status", "--porcelain") == "", "git status should stay clean", r)
        return r

    def has_branch(self, name):
        return subprocess.run(["git", "rev-parse", "--verify", "-q", "refs/heads/" + name],
                              cwd=self.root, capture_output=True).returncode == 0

    def ledger(self):
        common = Path(self.git("rev-parse", "--path-format=absolute", "--git-common-dir"))
        files = list((common / "implement" / "runs").glob("*.json"))
        expect(len(files) == 1, f"expected one ledger file, found {files}")
        return json.loads(files[0].read_text(encoding="utf-8"))


def field(line, key):
    """The value of key=value in a printed line; the last field may hold spaces."""
    head, sep, rest = line.partition(f" {key}=")
    expect(sep != "", f"no {key}= in {line!r}")
    for other in ("branch", "worktree", "missing"):
        if other != key:
            rest = rest.split(f" {other}=")[0]
    return rest


def test_begin_creates_the_integration_branch_then_reuses_it(base):
    p = Project(base)
    tip = p.git("rev-parse", "HEAD")
    r = p.run("begin", INTEGRATION, "1", "2")
    expect(r.returncode == OK and r.stdout.strip() == f"begin: created {INTEGRATION}", "begin should create", r)
    expect(p.git("rev-parse", INTEGRATION) == tip, "the integration branch should start at HEAD")
    r = p.run("begin", INTEGRATION, "1", "2")
    expect(r.returncode == OK and r.stdout.strip() == f"begin: reused {INTEGRATION}", "begin should reuse", r)


def rmtree(path):
    def retry(func, p, _):
        os.chmod(p, stat.S_IWRITE)
        func(p)
    shutil.rmtree(path, onerror=retry)


def main():
    want = sys.argv[1] if len(sys.argv) > 1 else ""
    tests = [(n, f) for n, f in globals().items() if n.startswith("test_") and want in n]
    failed = 0
    for name, f in tests:
        base = tempfile.mkdtemp(prefix="implement-test-")
        try:
            f(base)
            print(f"PASS {name}")
        except Exception as e:  # a crash in one case must not hide the others
            failed += 1
            print(f"FAIL {name}: {e if isinstance(e, AssertionError) else traceback.format_exc()}")
        finally:
            try:
                rmtree(base)
            except OSError:
                pass
    print(f"{len(tests) - failed} passed, {failed} failed")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
