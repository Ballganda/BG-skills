#!/usr/bin/env python3
"""Mechanical steps of an implement run: one command per step, one line back.

Commands:
  begin INTEGRATION TICKET[:TIER]...  create or reuse the integration branch, open the run's ledger
  start TICKET [--slug TEXT]          claim a ticket, create or reuse its worktree and branch
  status                              one line per batch ticket
  test TICKET COMMAND                 run COMMAND in the ticket's worktree, log the output
  merge TICKET                        merge the ticket's branch into the integration branch
  fail TICKET                         record a failed attempt and free the ticket
  clean                               remove worktrees and branches of merged and failed tickets

The ledger lives under the repository's git directory (shared by every worktree,
never committed). Every command prints a short fixed-format line on stdout,
errors go to stderr as `error: <text>`, and the exit code is one of the
constants below. Standard library only.
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

OK = 0             # success
CONFLICT = 1       # a merge conflict (merge)
USAGE = 2          # bad arguments, or a ticket the run cannot take
NOTHING_READY = 3  # no ticket is ready (ready)
TEST_FAILED = 5    # the command given to test exited nonzero
ENV = 4           # environment problem: not a git repository, dirty integration branch, no tracker access

TIERS = ("Mechanical", "Standard", "Hard")
STATES = ("open", "claimed", "merged", "failed", "skipped")
TICKET_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")
LOCK_WAIT = 30.0


class Stop(Exception):
    """End the command with an exit code and a message on stderr."""

    def __init__(self, code, message):
        super().__init__(message)
        self.code = code


def git(*args, cwd=None, check=True):
    r = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True)
    if check and r.returncode:
        raise Stop(ENV, f"git {' '.join(args)}: {r.stderr.strip()}")
    return r


def out(*args, cwd=None):
    return git(*args, cwd=cwd).stdout.strip()


def branch_exists(name):
    return git("rev-parse", "--verify", "-q", "refs/heads/" + name, check=False).returncode == 0


def worktrees():
    """Map of branch name to worktree path for every worktree whose directory exists."""
    found, path = {}, None
    for line in out("worktree", "list", "--porcelain").splitlines():
        if line.startswith("worktree "):
            path = line[len("worktree "):]
        elif line.startswith("branch refs/heads/") and path and Path(path).is_dir():
            found[line[len("branch refs/heads/"):]] = Path(path).resolve().as_posix()
    return found


def require_clean_integration(integration):
    """A checkout of the integration branch with uncommitted changes stops the command."""
    path = worktrees().get(integration)
    if path and out("status", "--porcelain", cwd=path):
        raise Stop(ENV, f"integration branch {integration} has uncommitted changes in {path}")


class Store:
    """The run ledgers under <git common dir>/implement, guarded by one lock file."""

    def __init__(self):
        r = git("rev-parse", "--path-format=absolute", "--git-common-dir", check=False)
        if r.returncode:
            raise Stop(ENV, "not a git repository")
        self.dir = Path(r.stdout.strip()) / "implement"
        self.runs = self.dir / "runs"
        self.current = self.dir / "current"
        self.lock = self.dir / "lock"

    def __enter__(self):
        self.runs.mkdir(parents=True, exist_ok=True)
        deadline = time.monotonic() + LOCK_WAIT
        while True:
            try:
                os.close(os.open(self.lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY))
                return self
            except FileExistsError:
                if time.monotonic() > deadline:
                    raise Stop(ENV, f"ledger is locked: remove {self.lock} if no command is running")
                time.sleep(0.05)

    def __exit__(self, *exc):
        try:
            os.remove(self.lock)
        except OSError:
            pass

    def path(self, integration):
        return self.runs / (re.sub(r"[^A-Za-z0-9_.-]", "_", integration) + ".json")

    def active(self):
        """The integration branch of the last begin, or None."""
        try:
            return self.current.read_text(encoding="utf-8").strip() or None
        except FileNotFoundError:
            return None

    def load(self, integration=None):
        integration = integration or self.active()
        if not integration:
            raise Stop(ENV, "no run begun: run begin first")
        try:
            return json.loads(self.path(integration).read_text(encoding="utf-8"))
        except FileNotFoundError:
            raise Stop(ENV, f"no ledger for {integration}: run begin first")

    def save(self, ledger):
        self.write(self.path(ledger["integration"]), json.dumps(ledger, indent=1) + "\n")

    def activate(self, integration):
        self.write(self.current, integration + "\n")

    @staticmethod
    def write(path, text):
        """Write via a temporary file in the same directory and an atomic rename."""
        fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=path.name + ".", suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
                f.write(text)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp, path)
        except BaseException:
            try:
                os.remove(tmp)
            except OSError:
                pass
            raise


def parse_ticket(text):
    ticket, _, tier = text.lstrip("#").partition(":")
    if not TICKET_ID.match(ticket):
        raise Stop(USAGE, f"bad ticket id: {text}")
    if not tier:
        return ticket, "Standard"
    for t in TIERS:
        if t.lower() == tier.lower():
            return ticket, t
    raise Stop(USAGE, f"bad tier {tier} for ticket {ticket}: one of {', '.join(TIERS)}")


def cmd_begin(store, args):
    tickets = [parse_ticket(t) for t in args.tickets]
    if git("check-ref-format", "--branch", args.integration, check=False).returncode:
        raise Stop(USAGE, f"bad branch name: {args.integration}")
    with store:
        existed = branch_exists(args.integration)
        if existed:
            require_clean_integration(args.integration)
        else:
            r = git("rev-parse", "--verify", "-q", args.base + "^{commit}", check=False)
            if r.returncode:
                raise Stop(ENV, f"base {args.base} is not a commit")
        try:
            ledger = store.load(args.integration)
        except Stop:
            ledger = {"version": 1, "integration": args.integration, "worktree_root": None, "tickets": {}}
        root = Path(args.worktree_root) if args.worktree_root else default_worktree_root()
        ledger["worktree_root"] = root.resolve().as_posix()
        for ticket, tier in tickets:
            ledger["tickets"].setdefault(ticket, {"state": "open", "tier": tier, "attempts": 0,
                                                  "branch": None, "worktree": None})
        if not existed:
            git("branch", args.integration, args.base)
        store.save(ledger)
        store.activate(args.integration)
    print(f"begin: {'reused' if existed else 'created'} {args.integration}")
    return OK


def cmd_start(store, args):
    ticket, _ = parse_ticket(args.ticket)
    if args.slug is not None and not re.match(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$", args.slug):
        raise Stop(USAGE, f"bad slug: {args.slug}")
    with store:
        ledger = store.load()
        integration = ledger["integration"]
        entry = ledger["tickets"].get(ticket)
        if entry is None:
            raise Stop(USAGE, f"ticket {ticket} is not in the batch")
        if entry["state"] not in ("open", "failed", "claimed"):
            raise Stop(USAGE, f"ticket {ticket} is {entry['state']}")
        if not branch_exists(integration):
            raise Stop(ENV, f"integration branch {integration} is missing")
        require_clean_integration(integration)
        reused = entry["state"] == "claimed"
        if not reused:
            branch = f"ticket-{ticket}" + (f"-{args.slug}" if args.slug else "")
            entry.update(state="claimed", attempts=entry["attempts"] + 1, branch=branch,
                         worktree=(Path(ledger["worktree_root"]) / branch).as_posix())
            store.save(ledger)  # claim first, so a crash below leaves a claim the next start completes
        branch, path = entry["branch"], Path(entry["worktree"])
        have = worktrees()
        if branch in have:
            if have[branch] != path.resolve().as_posix():
                entry["worktree"] = have[branch]
                store.save(ledger)
        else:
            reused = False
            if path.exists():
                raise Stop(ENV, f"{path} exists and is not the worktree of {branch}")
            git("worktree", "prune")
            path.parent.mkdir(parents=True, exist_ok=True)
            if branch_exists(branch):
                git("worktree", "add", "-q", str(path), branch)
            else:
                git("worktree", "add", "-q", "-b", branch, str(path), integration)
    print(f"start: {'reused' if reused else 'created'} branch={entry['branch']} worktree={entry['worktree']}")
    return OK


def cmd_status(store, args):
    with store:
        ledger = store.load()
    paths = set(worktrees().values())
    for ticket, e in ledger["tickets"].items():
        line = (f"ticket {ticket} {e['state']} {e['tier']} attempts={e['attempts']}"
                f" branch={e['branch'] or '-'} worktree={e['worktree'] or '-'}")
        missing = []
        if e["worktree"] and Path(e["worktree"]).resolve().as_posix() not in paths:
            missing.append("worktree")
        if e["branch"] and not branch_exists(e["branch"]):
            missing.append("branch")
        print(line + (f" missing={','.join(missing)}" if missing else ""))
    return OK


def batch_entry(ledger, ticket):
    parse_ticket(ticket)
    entry = ledger["tickets"].get(ticket)
    if entry is None:
        raise Stop(USAGE, f"ticket {ticket} is not in the batch")
    return entry


def cmd_test(store, args):
    with store:
        ledger = store.load()
        entry = batch_entry(ledger, args.ticket)
        if entry["state"] != "claimed":
            raise Stop(USAGE, f"ticket {args.ticket} is {entry['state']}")
        if not Path(entry["worktree"]).is_dir():
            raise Stop(ENV, f"worktree of ticket {args.ticket} is missing: run start first")
        logs = store.dir / "logs"
        logs.mkdir(parents=True, exist_ok=True)
        log = logs / f"{args.ticket}-{entry['attempts']}.log"
    r = subprocess.run(args.shell_command, shell=True, cwd=entry["worktree"], stdout=subprocess.PIPE,
                       stderr=subprocess.STDOUT)
    log.write_bytes(r.stdout)
    print(f"test: {'fail' if r.returncode else 'pass'} log={log.as_posix()}")
    return TEST_FAILED if r.returncode else OK


def merge_into(store, integration, branch, ticket):
    """Merge branch into the integration branch; return the conflicting files, or [] on success."""
    path = worktrees().get(integration)
    temp = None
    if path is None:
        temp = store.dir / "merge-worktree"
        if temp.exists():  # left by a crashed merge
            git("worktree", "remove", "--force", str(temp), check=False)
            shutil.rmtree(temp, ignore_errors=True)
        git("worktree", "prune")
        git("worktree", "add", "-q", str(temp), integration)
        path = str(temp)
    try:
        r = git("merge", "--no-ff", "-q", "-m", f"Merge ticket {ticket}", branch, cwd=path, check=False)
        if r.returncode == 0:
            return []
        files = out("diff", "--name-only", "--diff-filter=U", cwd=path).splitlines()
        git("merge", "--abort", cwd=path, check=False)
        if not files:
            raise Stop(ENV, f"git merge {branch}: {r.stderr.strip() or r.stdout.strip()}")
        return files
    finally:
        if temp is not None:
            git("worktree", "remove", "--force", str(temp), check=False)
            shutil.rmtree(temp, ignore_errors=True)
            git("worktree", "prune", check=False)


def cmd_merge(store, args):
    with store:
        ledger = store.load()
        integration = ledger["integration"]
        entry = batch_entry(ledger, args.ticket)
        if entry["state"] != "merged":
            if entry["state"] != "claimed":
                raise Stop(USAGE, f"ticket {args.ticket} is {entry['state']}")
            branch = entry["branch"]
            if not branch_exists(branch) or not branch_exists(integration):
                raise Stop(ENV, f"branch {branch} or {integration} is missing")
            require_clean_integration(integration)
            # a merge that landed before the ledger was written needs no second merge commit
            if git("merge-base", "--is-ancestor", branch, integration, check=False).returncode:
                conflicts = merge_into(store, integration, branch, args.ticket)
                if conflicts:
                    print("merge: conflict files=" + ",".join(conflicts))
                    return CONFLICT
            entry["state"] = "merged"
            store.save(ledger)
    print("merge: merged")
    return OK


def cmd_fail(store, args):
    with store:
        ledger = store.load()
        entry = batch_entry(ledger, args.ticket)
        if entry["state"] != "claimed":
            raise Stop(USAGE, f"ticket {args.ticket} is {entry['state']}")
        entry["state"] = "failed"
        store.save(ledger)
    print(f"fail: ticket {args.ticket} attempts={entry['attempts']}")
    return OK


def cmd_clean(store, args):
    removed = 0
    with store:
        ledger = store.load()
        for entry in ledger["tickets"].values():
            if entry["state"] not in ("merged", "failed") or not (entry["branch"] or entry["worktree"]):
                continue
            if entry["worktree"]:
                git("worktree", "remove", "--force", entry["worktree"], check=False)
                shutil.rmtree(entry["worktree"], ignore_errors=True)
            git("worktree", "prune", check=False)
            if entry["branch"] and branch_exists(entry["branch"]):
                git("branch", "-D", entry["branch"])
            entry["branch"] = entry["worktree"] = None
            store.save(ledger)  # per ticket, so an interrupted clean resumes with the rest
            removed += 1
    print(f"clean: {removed} removed")
    return OK


def default_worktree_root():
    """A sibling of the main checkout, so worktrees never sit inside the tree."""
    main = Path(out("rev-parse", "--path-format=absolute", "--git-common-dir")).parent
    return main.parent / (main.name + ".worktrees")


class Parser(argparse.ArgumentParser):
    def error(self, message):
        raise Stop(USAGE, message)


def parser():
    p = Parser(prog="implement.py", description="Mechanical steps of an implement run.")
    sub = p.add_subparsers(dest="command", required=True, parser_class=Parser)
    b = sub.add_parser("begin", help="create or reuse the integration branch and open the run's ledger")
    b.add_argument("integration", help="integration branch name")
    b.add_argument("tickets", nargs="+", help="batch tickets as ID or ID:TIER")
    b.add_argument("--base", default="HEAD", help="where a new integration branch starts (default HEAD)")
    b.add_argument("--worktree-root", help="directory for ticket worktrees (default: beside the main checkout)")
    s = sub.add_parser("start", help="claim a ticket and create or reuse its worktree and branch")
    s.add_argument("ticket", help="a batch ticket id")
    s.add_argument("--slug", help="suffix for a new branch name: ticket-ID-SLUG")
    sub.add_parser("status", help="one line per batch ticket, flagging a missing worktree or branch")
    t = sub.add_parser("test", help="run a command in a ticket's worktree and log its output")
    t.add_argument("ticket", help="a claimed ticket id")
    t.add_argument("shell_command", metavar="COMMAND", help="shell command to run")
    m = sub.add_parser("merge", help="merge a ticket's branch into the integration branch")
    m.add_argument("ticket", help="a claimed ticket id")
    f = sub.add_parser("fail", help="record a failed attempt and free the ticket")
    f.add_argument("ticket", help="a claimed ticket id")
    sub.add_parser("clean", help="remove worktrees and branches of merged and failed tickets")
    return p


COMMANDS = {"begin": cmd_begin, "start": cmd_start, "status": cmd_status, "test": cmd_test,
            "merge": cmd_merge, "fail": cmd_fail, "clean": cmd_clean}


def main(argv=None):
    try:
        args = parser().parse_args(argv)
        return COMMANDS[args.command](Store(), args)
    except Stop as e:
        print(f"error: {e}", file=sys.stderr)
        return e.code


if __name__ == "__main__":
    sys.exit(main())
