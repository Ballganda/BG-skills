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

    def run(self, *args, cwd=None, clean=True, env=None):
        r = subprocess.run([sys.executable, str(SCRIPT), *args], cwd=cwd or self.root,
                           capture_output=True, text=True, env={**os.environ, **(env or {})})
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


def work(p, wt, rel, text, msg):
    (wt / rel).write_text(text, encoding="utf-8", newline="\n")
    p.git("add", "-A", cwd=wt)
    p.git("commit", "-q", "-m", msg, cwd=wt)


def py(code):
    return f'"{sys.executable}" -c "{code}"'


def test_test_passes_and_logs_the_full_output(base):
    p = begun(base)
    _, _, wt = start(p, "1")
    r = p.run("test", "1", py("import os;print(os.getcwd());print('line two')"))
    expect(r.returncode == OK and r.stdout.startswith("test: pass log="), "a passing command", r)
    log = Path(r.stdout.strip().split("log=", 1)[1])
    text = log.read_text(encoding="utf-8")
    expect("line two" in text and wt.name in text, f"the log holds the output from the worktree: {text!r}")


def test_test_fails_with_a_nonzero_exit_and_keeps_the_log(base):
    p = begun(base)
    start(p, "1")
    r = p.run("test", "1", py("import sys;print('boom');print('err', file=sys.stderr);sys.exit(3)"))
    expect(r.returncode not in (OK, CONFLICT, USAGE, ENV) and r.stdout.startswith("test: fail log="), "a failing command", r)
    text = Path(r.stdout.strip().split("log=", 1)[1]).read_text(encoding="utf-8")
    expect("boom" in text and "err" in text, f"the log holds stdout and stderr: {text!r}")
    r = p.run("test", "9", "true")
    expect(r.returncode == USAGE, "a ticket outside the batch", r)


def test_merge_brings_the_ticket_commits_into_the_integration_branch(base):
    p = begun(base)
    _, branch, wt = start(p, "1")
    work(p, wt, "one.txt", "1\n", "ticket one")
    r = p.run("merge", "1")
    expect(r.returncode == OK and r.stdout.strip() == "merge: merged", "a clean merge", r)
    expect(p.git("show", f"{INTEGRATION}:one.txt") == "1", "the integration branch has the commit")
    expect(p.ledger()["tickets"]["1"]["state"] == "merged", "the ledger records the merge")
    tip = p.git("rev-parse", INTEGRATION)
    r = p.run("merge", "1")
    expect(r.returncode == OK and r.stdout.strip() == "merge: merged", "a rerun reports merged", r)
    expect(p.git("rev-parse", INTEGRATION) == tip, "no second merge commit")


def test_merge_recovers_when_the_ledger_missed_a_completed_merge(base):
    p = begun(base)
    _, branch, wt = start(p, "1")
    work(p, wt, "one.txt", "1\n", "ticket one")
    p.git("worktree", "add", "-q", str(p.base / "tmp-int"), INTEGRATION)
    p.git("merge", "-q", "--no-ff", "-m", "manual", branch, cwd=p.base / "tmp-int")
    p.git("worktree", "remove", "--force", str(p.base / "tmp-int"))
    tip = p.git("rev-parse", INTEGRATION)
    r = p.run("merge", "1")
    expect(r.returncode == OK and r.stdout.strip() == "merge: merged", "merge after a crash", r)
    expect(p.git("rev-parse", INTEGRATION) == tip and p.ledger()["tickets"]["1"]["state"] == "merged",
           "the ledger catches up without a new merge")


def test_merge_of_a_conflicting_branch_reports_the_files_and_aborts(base):
    p = begun(base)
    _, _, wt1 = start(p, "1")
    _, _, wt2 = start(p, "2")
    work(p, wt1, "src.txt", "ticket one\n", "one edits")
    work(p, wt2, "src.txt", "ticket two\n", "two edits")
    expect(p.run("merge", "1").returncode == OK, "first merge")
    tip = p.git("rev-parse", INTEGRATION)
    r = p.run("merge", "2")
    expect(r.returncode == CONFLICT and r.stdout.strip() == "merge: conflict files=src.txt", "a conflict", r)
    expect(p.git("rev-parse", INTEGRATION) == tip, "the integration branch is untouched")
    common = Path(p.git("rev-parse", "--path-format=absolute", "--git-common-dir"))
    expect(not list(common.glob("worktrees/*/MERGE_HEAD")), "no merge is left in progress")
    expect(p.ledger()["tickets"]["2"]["state"] == "claimed", "a conflicting ticket stays claimed")
    r = p.run("merge", "2")
    expect(r.returncode == CONFLICT, "a retry can run again", r)


def test_fail_frees_the_ticket_and_counts_the_attempt(base):
    p = begun(base)
    start(p, "1")
    r = p.run("fail", "1")
    expect(r.returncode == OK and r.stdout.strip() == "fail: ticket 1 attempts=1", "fail prints the count", r)
    expect(status_lines(p)["1"].startswith("ticket 1 failed Standard attempts=1"), "status shows the attempt")
    start(p, "1")
    r = p.run("fail", "1")
    expect(r.stdout.strip() == "fail: ticket 1 attempts=2", "the second attempt counts", r)
    r = p.run("fail", "2")
    expect(r.returncode == USAGE, "only a claimed ticket can fail", r)


def test_clean_removes_merged_and_failed_tickets_only(base):
    p = begun(base, "1", "2", "3", "4")
    _, b1, w1 = start(p, "1")
    _, b2, w2 = start(p, "2")
    _, b3, w3 = start(p, "3")
    work(p, w1, "one.txt", "1\n", "one")
    expect(p.run("merge", "1").returncode == OK, "merge")
    expect(p.run("fail", "2").returncode == OK, "fail")
    r = p.run("clean")
    expect(r.returncode == OK and r.stdout.strip() == "clean: 2 removed", "clean prints the count", r)
    listing = p.git("worktree", "list", "--porcelain")
    expect(w1.as_posix() not in listing and w2.as_posix() not in listing, "no worktree for cleaned tickets")
    expect(w3.as_posix() in listing and p.has_branch(b3), "a claimed ticket stays")
    expect(not p.has_branch(b1) and not p.has_branch(b2) and not w1.exists(), "branches and directories gone")
    expect(p.run("clean").stdout.strip() == "clean: 0 removed", "a second clean removes nothing")
    start(p, "2")
    expect(p.ledger()["tickets"]["2"]["state"] == "claimed", "a cleaned failed ticket can start again")


def ticket_file(p, num, blocked_by=(), status="ready-for-agent"):
    """Commit a local-tracker ticket file: .scratch/feat/issues/NN-t.md with a Blocked by line."""
    edges = ", ".join(f"{b:02d}" for b in blocked_by) or "None"
    text = chr(10).join([f"# Ticket {num}", "", f"Status: {status}", f"Blocked by: {edges}", "", "Body.", ""])
    p.commit(f".scratch/feat/issues/{num:02d}-t.md", text, f"ticket {num}")


def set_state(p, ticket, state):
    """Stand in for merge and fail, which later tickets add: write the state into the ledger."""
    common = Path(p.git("rev-parse", "--path-format=absolute", "--git-common-dir"))
    path = common / "implement" / "runs" / f"{INTEGRATION}.json"
    ledger = json.loads(path.read_text(encoding="utf-8"))
    ledger["tickets"][ticket]["state"] = state
    path.write_text(json.dumps(ledger), encoding="utf-8")


def ready(p, *extra):
    r = p.run("ready", *extra)
    expect(r.returncode == OK, "ready should succeed", r)
    return [line.split() for line in r.stdout.splitlines()]


def test_ready_in_a_linear_chain_lists_only_the_head_until_it_is_merged(base):
    p = begun(base, "1:mechanical", "2", "3:hard")
    ticket_file(p, 1)
    ticket_file(p, 2, [1])
    ticket_file(p, 3, [2])
    expect(ready(p) == [["ticket", "1", "Mechanical"]], "only the head is ready")
    set_state(p, "1", "merged")
    expect(ready(p) == [["ticket", "2", "Standard"]], "the next one after the head is merged")
    set_state(p, "2", "merged")
    expect(ready(p) == [["ticket", "3", "Hard"]], "then the tail")


def test_ready_in_a_diamond_lists_the_join_only_after_both_blockers_merge(base):
    p = begun(base, "1", "2", "3", "4")
    ticket_file(p, 1)
    ticket_file(p, 2, [1])
    ticket_file(p, 3, [1])
    ticket_file(p, 4, [2, 3])
    set_state(p, "1", "merged")
    set_state(p, "2", "merged")
    expect([t[1] for t in ready(p)] == ["3"], "the join waits for its second blocker")
    set_state(p, "3", "merged")
    expect([t[1] for t in ready(p)] == ["4"], "the join is ready when both are merged")


def test_ready_lists_at_most_the_free_slots_under_the_cap(base):
    p = begun(base, "1", "2", "3", "4", "5")
    for n in range(1, 6):
        ticket_file(p, n)
    start(p, "1")
    start(p, "2")
    expect([t[1] for t in ready(p)] == ["3"], "cap 3 with two claimed leaves one slot")
    r = p.run("ready", "--cap", "2")
    expect(r.returncode == NOTHING_READY, "no free slot under a cap of 2", r)
    expect([t[1] for t in ready(p, "--cap", "5")] == ["3", "4", "5"], "the cap can be overridden")


def test_ready_skips_a_ticket_blocked_outside_the_batch_and_status_shows_it(base):
    p = begun(base, "1", "2")
    ticket_file(p, 1)
    ticket_file(p, 2, [9])
    ticket_file(p, 9)
    expect([t[1] for t in ready(p)] == ["1"], "the blocked ticket is never listed")
    expect(status_lines(p)["2"].startswith("ticket 2 skipped "), "status shows skipped")
    ticket_file(p, 9, status="resolved")
    expect([t[1] for t in ready(p)] == ["1", "2"], "a resolved outside blocker no longer skips")


def test_ready_with_nothing_ready_exits_with_the_nothing_ready_code(base):
    p = begun(base, "1", "2")
    ticket_file(p, 1)
    ticket_file(p, 2, [1])
    start(p, "1")
    r = p.run("ready")
    expect(r.returncode == NOTHING_READY and r.stdout.strip() == "ready: none", "nothing ready", r)


def test_start_on_a_ticket_outside_the_batch_creates_no_worktree(base):
    p = begun(base, "1")
    r = p.run("start", "9")
    expect(r.returncode == USAGE and "not in the batch" in r.stderr, "usage code", r)
    expect(not p.has_branch("ticket-9") and not (p.base / "wts").exists(), "no branch or worktree")


def test_outside_a_git_repository_every_command_is_an_environment_problem(base):
    p = Project(base)
    outside = p.base / "plain"
    outside.mkdir()
    env = {"GIT_CEILING_DIRECTORIES": str(p.base)}
    for args in (("begin", INTEGRATION, "1"), ("start", "1"), ("status",), ("test", "1", "true"),
                 ("merge", "1"), ("fail", "1"), ("clean",)):
        r = p.run(*args, cwd=outside, env=env)
        expect(r.returncode == ENV and "not a git repository" in r.stderr, f"{args[0]} outside a repo", r)
    expect(list(outside.iterdir()) == [], "nothing should be written outside a repository")


def test_a_dirty_integration_branch_stops_begin_and_start_before_any_change(base):
    p = begun(base)
    p.git("checkout", "-q", INTEGRATION)
    (p.root / "src.txt").write_text("edited\n")
    before = p.ledger()
    r = p.run("start", "1", clean=False)
    expect(r.returncode == ENV and "uncommitted" in r.stderr, "start on a dirty integration branch", r)
    expect(not p.has_branch("ticket-1") and not (p.base / "wts").exists(), "start should create nothing")
    r = p.run("begin", INTEGRATION, "1", "3", clean=False)
    expect(r.returncode == ENV and "uncommitted" in r.stderr, "begin on a dirty integration branch", r)
    expect(p.ledger() == before, "the ledger should be unchanged")


def test_bad_arguments_exit_with_the_usage_code(base):
    p = begun(base)
    for args in ((), ("frobnicate",), ("begin", INTEGRATION), ("begin", INTEGRATION, "1:enormous"),
                 ("begin", "bad..name", "1"), ("start",), ("start", "9"), ("start", "1", "--slug", "a b"),
                 ("status", "extra")):
        r = p.run(*args)
        expect(r.returncode == USAGE and r.stderr.startswith("error: "), f"usage code for {args}", r)
    expect(not p.has_branch("ticket-9"), "a ticket outside the batch is never started")


def test_parallel_starts_all_land_in_the_ledger(base):
    p = begun(base, *[str(n) for n in range(1, 7)])
    procs = [subprocess.Popen([sys.executable, str(SCRIPT), "start", str(n)], cwd=p.root,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True) for n in range(1, 7)]
    for proc in procs:
        _, err = proc.communicate()
        expect(proc.returncode == OK, f"a parallel start failed: {err}")
    tickets = p.ledger()["tickets"]
    expect(all(t["state"] == "claimed" for t in tickets.values()), f"every start recorded: {tickets}")


def test_the_script_and_tests_contain_no_em_dashes(base):
    for path in (SCRIPT, Path(__file__)):
        expect(chr(0x2014) not in path.read_text(encoding="utf-8"), f"em-dash in {path}")


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
