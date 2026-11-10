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
        files = list((common / "implement" / "runs").glob(f"{INTEGRATION}.json"))
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
    common = Path(p.git("rev-parse", "--path-format=absolute", "--git-common-dir")).resolve()
    expect(common == (p.root / ".git").resolve() and (common / "implement" / "runs").is_dir(),
           "the ledger lives under the git directory")


def begun(base, *tickets):
    p = Project(base)
    r = p.run("begin", INTEGRATION, *(tickets or ("1", "2:hard")), "--worktree-root", str(p.base / "wts"))
    expect(r.returncode == OK, "begin should succeed", r)
    p.commit("later.txt", "on main\n", "main moves on")  # the integration tip is not main's tip
    return p


def start(p, ticket, *extra):
    r = p.run("start", ticket, *extra)
    expect(r.returncode == OK, f"start {ticket} should succeed", r)
    line = r.stdout.strip()
    expect("\n" not in line, "start prints one line", r)
    return line, field(line, "branch"), Path(field(line, "worktree"))


def test_start_creates_a_worktree_and_branch_at_the_integration_tip(base):
    p = begun(base)
    line, branch, wt = start(p, "1")
    expect(line.startswith("start: created "), f"start should say created: {line!r}")
    expect(branch == "ticket-1" and p.has_branch(branch), f"branch ticket-1 should exist: {line!r}")
    expect(wt.is_dir() and wt.parent == (p.base / "wts").resolve(), f"worktree under the root: {line!r}")
    expect(p.git("rev-parse", "HEAD", cwd=wt) == p.git("rev-parse", INTEGRATION), "based on the integration tip")
    expect(p.git("branch", "--show-current", cwd=wt) == branch, "the worktree has the ticket branch checked out")


def test_start_names_the_branch_with_a_slug(base):
    p = begun(base)
    _, branch, _ = start(p, "2", "--slug", "script-core")
    expect(branch == "ticket-2-script-core", f"slugged branch, got {branch}")


def test_start_reuses_the_worktree_and_branch_of_a_claimed_ticket(base):
    p = begun(base)
    _, branch, wt = start(p, "1")
    (wt / "work.txt").write_text("in progress\n")
    line, branch2, wt2 = start(p, "1")
    expect(line.startswith("start: reused ") and (branch2, wt2) == (branch, wt), f"reuse both: {line!r}")
    expect((wt / "work.txt").exists(), "reuse keeps the work in the worktree")
    expect(p.ledger()["tickets"]["1"]["attempts"] == 1, "a reuse is not a new attempt")


def test_start_recreates_a_claimed_tickets_missing_worktree(base):
    p = begun(base)
    _, branch, wt = start(p, "1")
    rmtree(wt)
    line, branch2, wt2 = start(p, "1")
    expect(wt2.is_dir() and branch2 == branch, f"start should rebuild the worktree: {line!r}")


def status_lines(p):
    r = p.run("status")
    expect(r.returncode == OK, "status should succeed", r)
    return {line.split()[1]: line for line in r.stdout.splitlines()}


def test_status_shows_every_batch_ticket_as_recorded(base):
    p = begun(base, "1:mechanical", "2", "3:HARD")
    _, branch, wt = start(p, "3")
    lines = status_lines(p)  # each run is a fresh process, so this reads the ledger alone
    expect(list(lines) == ["1", "2", "3"], f"one line per ticket in batch order: {lines}")
    expect(lines["1"] == "ticket 1 open Mechanical attempts=0 branch=- worktree=-", lines["1"])
    expect(lines["2"] == "ticket 2 open Standard attempts=0 branch=- worktree=-", lines["2"])
    expect(lines["3"] == f"ticket 3 claimed Hard attempts=1 branch={branch} worktree={wt.as_posix()}", lines["3"])


def test_status_flags_a_deleted_worktree(base):
    p = begun(base)
    _, _, wt = start(p, "1")
    rmtree(wt)
    line = status_lines(p)["1"]
    expect(line.endswith(" missing=worktree"), f"status should flag the worktree: {line!r}")


def test_status_flags_a_deleted_branch(base):
    p = begun(base)
    _, branch, wt = start(p, "1")
    p.git("worktree", "remove", "--force", str(wt))
    p.git("branch", "-D", branch)
    line = status_lines(p)["1"]
    expect(line.endswith(" missing=worktree,branch"), f"status should flag both: {line!r}")


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
