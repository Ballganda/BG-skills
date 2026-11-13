#!/usr/bin/env python3
"""Tests of the decomp project tool at its one seam: the command line.

Each case builds a scratch git project (a copy of decomp.py, a toolchain.json,
a decomp.json whose adapters are small `python -c` commands, a fake target, and
fake tools that only print a banner), runs decomp.py commands in it, and asserts
on exit codes and output. No real compiler, no network. Standard library only.

Run: python scripts/test-decomp.py [name-filter]

A full run takes minutes, longer than the default 120-second tool timeout, so run
it in the background. While iterating, pass a name filter (a substring of the test
function names) to run only the matching cases, for example:
python scripts/test-decomp.py verify
"""
import hashlib
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
TOOL = REPO / "skills" / "engineering" / "decomp-setup" / "scripts" / "decomp.py"
PY = f'"{sys.executable}"'
UNIT, TID, ADDRESS = "u0001", "u0001-00401000", "0x00401000"
SOURCE = "src/u0001.c"
ENV_EXIT = 6

# The fake "compiler" copies the source into the object and appends the compiler
# tool it was told to use. The fake "diff" reports a match when the object holds
# the word MATCH, and writes the symbol map path it received into the report.
BUILD = PY + (' -c "import sys;open(sys.argv[2],\'w\').write(open(sys.argv[1]).read()+chr(10)'
              '+\'compiler=\'+sys.argv[3]+chr(10))" "{source}" "{obj}" "{compiler}"')
DIFF = PY + (' -c "import sys,json;o=open(sys.argv[1]).read();'
             'open(sys.argv[2],\'a\').write(\'symbols=\'+sys.argv[3]+chr(10)+o);m=\'MATCH\' in o;'
             'print(json.dumps(dict(match=m,differ_bytes=0 if m else 3)))" "{obj}" "{report}" "{symbols}"')
BANNER_CMD = PY + ' "{root}/cc.py"'
FAKE_TOOL = 'import os\nprint(os.environ.get("FAKE_BANNER", "FakeCC 1.0"))\n'
UNPACK = ("import os, shutil, sys\n"
          "os.makedirs(sys.argv[2], exist_ok=True)\n"
          "shutil.copy(sys.argv[1], os.path.join(sys.argv[2], 'cc.py'))\n")

MARK = f"// @decomp {TID}\n"
CLEAN = MARK + "int f(void) { return 1; } /* MATCH */\n"

RETAIL = bytes(range(256)) * 16
PROBE_AT = [(0, 64), (1024, 64), (2048, 64)]


def patched(data, *offsets):
    b = bytearray(data)
    for o in offsets:
        b[o] ^= 0xFF
    return bytes(b)


STORE = patched(RETAIL, 2050, 3000)        # 2 of 3 probes hold
OTHER = patched(RETAIL, 10, 2050, 3000)    # 1 of 3 probes holds
WRONG = RETAIL + b"2021 update"


def sha(data):
    return hashlib.sha256(data).hexdigest()


def tool_entry(name="compiler"):
    return {"name": name, "product": "FakeCC 1.0", "installed_by": "user",
            "files": ["cc.py"], "banner_cmd": BANNER_CMD, "banner": "FakeCC 1.0"}


def legacy_manifest():
    return {"target": {"sha256": sha(RETAIL), "size": len(RETAIL)}, "tools": [tool_entry()]}


def editions_manifest():
    return {"target": {
        "editions": [
            {"name": "retail 1.0", "sha256": sha(RETAIL), "size": len(RETAIL)},
            {"name": "store re-release", "probes_needed": 2, "differs": [ADDRESS]},
        ],
        "probes": [{"offset": o, "size": n, "sha256": sha(RETAIL[o:o + n])} for o, n in PROBE_AT],
        "known_wrong": [{"name": "2021 update", "sha256": sha(WRONG),
                         "message": "roll back to the 1.0 depot"}],
    }, "tools": [tool_entry()]}


def ticket_text(tid, address, source, status):
    unit, key = tid.split("-")
    return "\n".join([
        "---", f"id: {tid}", f"unit: {unit}", f"address: {address}", "size: 37", "tier: SMALL",
        f"source: {source}", f"expected: expected/{key}.bin", f"status: {status}",
        "claimed_by:" + (" w1" if status == "claimed" else ""),
        "claimed_at:" + (" 1789000000" if status == "claimed" else ""), "---", "## Notes", ""])


class Project:
    """A scratch decomp project: committed, tagged decomp-setup, with one ticket."""

    def __init__(self, base, manifest=None, config=None, source=CLEAN, headers=None,
                 status="open", target=RETAIL, installed=("compiler",), files=None):
        self.base = Path(base)
        self.root = self.base / "proj"
        self.tmp = self.base / "tmp"
        self.tmp.mkdir()
        self.target = self.base / "target.bin"
        self.target.write_bytes(target)
        cfg = {"integration_branch": "main", "build": BUILD, "diff": DIFF, "pragma_allow": [], "banned": []}
        cfg.update(config or {})
        self.write("tools/decomp.py", TOOL.read_text(encoding="utf-8"))
        self.write("toolchain.json", json.dumps(manifest or legacy_manifest(), indent=1))
        self.write("decomp.json", json.dumps(cfg, indent=1))
        self.write("DECOMP.md", "# contract\n")
        self.write("symbols.json", "{}\n")
        self.write(".gitignore", ".decomp/\n")
        self.write("include/keep.h", "/* shared */\n")
        self.write(SOURCE, source)
        for name, text in (headers or {}).items():
            self.write("include/" + name, text)
        for name, text in (files or {}).items():
            self.write(name, text)
        self.write(f"tickets/{UNIT}/{TID}.md", ticket_text(TID, ADDRESS, SOURCE, status))
        self.write(".decomp/local.json", json.dumps({"target": str(self.target)}))
        for name in installed:
            self.write(f".decomp/toolchain/{name}/cc.py", FAKE_TOOL)
        self.git("init", "-q", "-b", "main")
        for k, v in (("user.name", "Test"), ("user.email", "test@example.invalid"),
                     ("commit.gpgsign", "false"), ("core.autocrlf", "false")):
            self.git("config", k, v)
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "setup")
        self.git("tag", "decomp-setup")

    def write(self, rel, text, root=None):
        p = (root or self.root) / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")

    def git(self, *args, cwd=None):
        r = subprocess.run(["git", *args], cwd=cwd or self.root, capture_output=True, text=True)
        assert r.returncode == 0, f"git {args}: {r.stderr}"
        return r.stdout

    def branch(self, name, changes):
        """Commit `changes` (path -> text) on a new branch from main, then return to main."""
        self.git("checkout", "-q", "-b", name, "main")
        for rel, text in changes.items():
            self.write(rel, text)
        self.git("add", "-A")
        self.git("commit", "-q", "-m", name)
        self.git("checkout", "-q", "main")

    def run(self, *args, cwd=None, env=None, tool=None):
        """Run the tree's own copy of the tool, or the copy at `tool`."""
        cwd = Path(cwd or self.root)
        e = {k: v for k, v in os.environ.items() if k not in ("DECOMP_LOCAL", "DECOMP_TARGET", "FAKE_BANNER")}
        e.update(PYTHONDONTWRITEBYTECODE="1", TMP=str(self.tmp), TEMP=str(self.tmp), TMPDIR=str(self.tmp))
        e.update(env or {})
        r = subprocess.run([sys.executable, str(tool or cwd / "tools" / "decomp.py"), *args], cwd=cwd, env=e,
                           capture_output=True, text=True, errors="replace")
        r.all = r.stdout + r.stderr
        return r

    def statuses(self):
        """Ticket statuses as the tool reports them: {status: count} from the status line of `report`."""
        made = not (self.root / "inventory.json").exists()
        had_open = (self.root / "OPEN.md").exists()
        if made:
            self.write("inventory.json", '{"units": [], "functions": []}\n')
        try:
            r = self.run("report", tool=TOOL)  # the skill's copy: a test may break the project's own
        finally:
            if made:
                (self.root / "inventory.json").unlink()
            if not had_open:
                (self.root / "OPEN.md").unlink(missing_ok=True)
        line = [l for l in r.stdout.splitlines() if l.startswith("status:")]
        expect(r.returncode == 0 and len(line) == 1, "report should print one status line", r)
        return {k: int(v) for k, v in (c.split() for c in line[0][len("status:"):].split(","))}

    def status(self):
        """The status of a project that holds one ticket."""
        got = self.statuses()
        expect(sum(got.values()) == 1, f"expected one ticket, report says {got}")
        return next(iter(got))

    def advance(self, to):
        """Drive the ticket through the CLI to `to`: claimed, bytes-match, matched or integrated."""
        want = ("claimed", "bytes-match", "matched", "integrated").index(to)
        branch = f"w/{TID}"
        if want >= 1:  # branch first: the claim edits a tracked ticket, which a branch commit would sweep up
            self.branch(branch, {SOURCE: CLEAN + "/* w */\n"})
        r = self.run("claim", TID, "--by", "w1")
        expect(r.returncode == 0, "claim should pass", r)
        if want >= 1:
            r = self.run("verify", TID, "--model", "m")
            expect(r.returncode == 0, "verify should reach bytes-match", r)
        if want >= 2:
            r = self.run("audit", TID, "pass", "--auditor", "a1")
            expect(r.returncode == 0, "audit pass should reach matched", r)
        if want >= 3:
            self.git("merge", "-q", "--no-edit", branch)
            r = self.run("integrate", TID)
            expect(r.returncode == 0, "integrate should pass", r)
        expect(self.status() == to, f"the scenario should end {to}")

    def lines(self, name):
        f = self.root / "ledger" / name
        return [json.loads(x) for x in f.read_text().splitlines()] if f.exists() else []

    def lock_file(self, name):
        return self.root / ".decomp" / "locks" / f"{name}.lock"

    def check(self, **kw):
        """Run `check` and return (process, parsed result line or None)."""
        r = self.run("check", TID, **kw)
        try:
            return r, json.loads(r.stdout.splitlines()[0])
        except (ValueError, IndexError):
            return r, None


def expect(cond, what, r=None):
    if not cond:
        detail = f"\n  exit {r.returncode}\n  stdout: {r.stdout.strip()}\n  stderr: {r.stderr.strip()}" if r else ""
        raise AssertionError(what + detail)


def expect_guardrail(p, *quoted):
    r, out = p.check()
    expect(out is not None and out["result"] == "guardrail", "check should report guardrail", r)
    for q in quoted:
        expect(q in r.stdout, f"the refusal should quote {q!r}", r)


def expect_match(p, **kw):
    r, out = p.check(**kw)
    expect(r.returncode == 0 and out is not None and out["result"] == "bytes-match", "check should report bytes-match", r)
    return r, out


# ---------- guardrail scan ----------

def test_clean_source_matches(base):
    expect_match(Project(base))


def test_scan_refuses_assembly(base):
    expect_guardrail(Project(base, source=CLEAN + "void g(void) { __asm nop }\n"), "assembly", "__asm nop")


def each(base, cases):
    """One scratch folder per case, so a test can build several projects."""
    for n, case in enumerate(cases):
        d = Path(base) / str(n)
        d.mkdir()
        yield d, case


def test_scan_sees_code_behind_literals_and_comments(base):
    hidden = ['const char *u = "http://x"; __asm nop',
              "int n = 1'0; __asm nop; int m = 2'0;",
              'const char *r = R"(")"; __asm nop',
              "/* note */ __asm nop",
              "char q = '\"'; __asm nop; char p = '\"';"]
    for d, line in each(base, hidden):
        expect_guardrail(Project(d, source=CLEAN + line + "\n"), "assembly", line)


def test_scan_passes_banned_words_in_literals_and_comments(base):
    src = (CLEAN + 'const char *p = "src\\\\asm\\\\x.c";\n/* was inline asm in the original */\n'
           "// __declspec(naked) once\nint tag = 'asm';\nconst char *s = \"#pragma optimize\";\n")
    expect_match(Project(base, source=src))


def test_scan_refuses_directive_hidden_from_a_line_reader(base):
    hidden = [('#\fpragma optimize("", off)', "pragma"), ('#\vpragma optimize("", off)', "pragma"),
              ('/**/#pragma optimize("", off)', "pragma"), ('/**/%:pragma optimize("", off)', "digraph"),
              ("#define J(a, b) a##b", "token pasting"), ("#define J(a, b) a%:%:b", "digraph")]
    for d, (line, why) in each(base, hidden):
        expect_guardrail(Project(d, source=CLEAN + line + "\n"), why, line.strip())


def test_scan_refuses_naked_and_placement_in_every_spelling(base):
    spelled = [("__declspec(naked) void g(void) {}", "naked"),
               ("void g(void) __attribute__((noinline, naked));", "naked"),
               ("void g(void) __attribute__((__naked__));", "naked"),
               ("[[gnu::naked]] void g(void);", "naked"),
               ('int v __attribute__((__section__(".sdata"))) = 1;', "section placement"),
               ('__declspec(section ".init") void g(void);', "section placement"),
               ('__declspec(allocate(".seg")) int v = 1;', "section placement")]
    allow_all = {"attribute_allow": ["."]}  # no allowlist reaches these
    for d, (line, why) in each(base, spelled):
        expect_guardrail(Project(d, source=CLEAN + line + "\n", config=allow_all), why, line)


def test_scan_holds_attributes_to_the_allowlist(base):
    unlisted = ['void g(void) __attribute__((optimize("O0")));', "__declspec(noinline) void g(void);",
                "[[gnu::noinline]] void g(void);", "void g(void) __attribute__((noinline", ]
    for d, line in each(Path(base), unlisted):
        expect_guardrail(Project(d, source=CLEAN + line + "\n"), "attribute", line)
    d = Path(base) / "listed"
    d.mkdir()
    src = CLEAN + "__declspec(dllimport) int g(void);\nstruct S { char c; } __attribute__((packed));\n"
    expect_match(Project(d, source=src, config={"attribute_allow": [r"^__declspec\(dllimport\)$", r"\(\(packed\)\)"]}))


def test_marker_may_be_a_block_comment(base):
    expect_match(Project(base, source=f"/* @decomp {TID} */\nint f(void) {{ return 1; }} /* MATCH */\n"))


def test_marker_of_a_longer_id_does_not_count(base):
    r, out = Project(base, source=f"// @decomp {TID}0\nint f(void) {{ return 1; }} /* MATCH */\n").check()
    expect(out is not None and out["result"] == "guardrail" and "marker" in r.stdout, "the marker is missing", r)


def test_scan_refuses_unlisted_pragma(base):
    expect_guardrail(Project(base, source=CLEAN + '#pragma optimize("", off)\n'), "pragma", '#pragma optimize("", off)')


def test_scan_refuses_trigraph(base):
    expect_guardrail(Project(base, source=CLEAN + '??=pragma optimize("", off)\n'),
                     "trigraph", '??=pragma optimize("", off)')


def test_scan_refuses_line_continuation(base):
    expect_guardrail(Project(base, source=CLEAN + '#pra\\ \t\ngma optimize("", off)\n'), "line continuation", "#pra\\")


def test_scan_refuses_digraph_directive(base):
    expect_guardrail(Project(base, source=CLEAN + '  %:pragma optimize("", off)\n'),
                     "digraph", '%:pragma optimize("", off)')


def test_scan_refuses_unlisted_pragma_operators(base):
    expect_guardrail(Project(base, source=CLEAN + '__pragma(optimize("", off))\n'),
                     "__pragma", '__pragma(optimize("", off))')


def test_scan_refuses_unlisted_Pragma_operator(base):
    expect_guardrail(Project(base, source=CLEAN + '_Pragma("optimize(\\"\\", off)")\n'), "_Pragma", '_Pragma("optimize')


def test_scan_passes_allowlisted_pragma_operators(base):
    src = CLEAN + '#pragma pack(push, 1)\n__pragma(pack(push, 1))\n_Pragma("pack(pop)")\n'
    expect_match(Project(base, source=src, config={"pragma_allow": [r"#\s*pragma\s+pack\b"]}))


def test_scan_covers_included_project_headers(base):
    for n, bad in enumerate(['??=pragma optimize("", off)', "#define A 1 \\", '%:pragma once', "__pragma(optimize(off))"]):
        d = Path(base) / str(n)
        d.mkdir()
        p = Project(d, source='#include "shared.h"\n' + CLEAN, headers={"shared.h": "int x;\n" + bad + "\nint y;\n"})
        expect_guardrail(p, "shared.h", bad)


def test_scan_follows_a_chain_of_headers(base):
    p = Project(base, source='#include "outer.h"\n' + CLEAN,
                headers={"outer.h": '#include "deep/inner.h"\n', "deep/inner.h": '#include "leaf.h"\n',
                         "deep/leaf.h": "__asm nop\n"})
    expect_guardrail(p, "include/deep/leaf.h", "assembly")


def test_scan_covers_a_header_beside_the_source(base):
    p = Project(base, source='#include "local.h"\n' + CLEAN, files={"src/local.h": "__asm nop\n"})
    expect_guardrail(p, "src/local.h", "assembly")


def test_scan_follows_an_include_spelled_in_another_case(base):
    p = Project(base, source='#include <SHARED.H>\n' + CLEAN, headers={"shared.h": "__asm nop\n"})
    expect_guardrail(p, "include/shared.h", "assembly")


def test_scan_refuses_computed_include(base):
    for d, line in each(base, ['#define H "keep.h"\n#include H', "# include_next KEEP_H", "#import KEEP_H"]):
        expect_guardrail(Project(d, source=CLEAN + line + "\n"), "computed include")


def test_scan_refuses_include_outside_the_project(base):
    outside = ['#include "C:/Temp/x.h"', "#include </tmp/x.h>", '#include "../../x.h"', '#include "..\\\\..\\\\x.h"']
    for d, line in each(base, outside):
        expect_guardrail(Project(d, source=CLEAN + line + "\n"), "include outside the project")


def test_scan_passes_toolchain_and_commented_includes(base):
    src = '#include <windows.h>\n#include "../include/keep.h"\n// #include "C:/Temp/x.h"\n' + CLEAN
    expect_match(Project(base, source=src))


def test_revalidate_header_reaches_tickets_through_a_chain(base):
    p = Project(base, status="matched", source=MARK + '#include "outer.h"\nint f(void) { return K; }\n',
                config={"build": BUILD.replace("open(sys.argv[1]).read()", "open('include/keep.h').read()")},
                headers={"outer.h": '#include "KEEP.H"\n', "keep.h": "/* MATCH */\n"})
    p.branch("r/sym", {"include/keep.h": "/* broken */\n"})
    r = p.run("revalidate", "--ref", "r/sym", "--header", "include/keep.h")
    expect(r.returncode == 5 and f"REGRESSED {TID}" in r.stdout, "the ticket includes the header through another", r)


# ---------- target editions ----------

def test_doctor_passes_legacy_single_hash_manifest(base):
    r = Project(base).run("doctor")
    expect(r.returncode == 0 and "doctor: ok" in r.stdout and "target ok" in r.stdout, "legacy manifest should pass", r)


def test_doctor_refuses_other_file_under_legacy_manifest(base):
    r = Project(base, target=STORE).run("doctor")
    expect(r.returncode == ENV_EXIT and "ENVIRONMENT: target" in r.stderr, "another file should exit 6", r)


def test_doctor_prints_whole_file_edition(base):
    r = Project(base, manifest=editions_manifest()).run("doctor")
    expect(r.returncode == 0 and "retail 1.0" in r.stdout, "doctor should name the recognised edition", r)


def test_doctor_names_known_wrong_edition_with_its_message(base):
    r = Project(base, manifest=editions_manifest(), target=WRONG).run("doctor")
    expect(r.returncode == ENV_EXIT, "known-wrong edition should exit 6", r)
    expect("2021 update" in r.stderr and "roll back to the 1.0 depot" in r.stderr, "name and message should print", r)


def test_doctor_accepts_edition_matching_enough_probes(base):
    r = Project(base, manifest=editions_manifest(), target=STORE).run("doctor")
    expect(r.returncode == 0 and "store re-release" in r.stdout, "probe edition should pass by name", r)
    expect("2 of 3" in r.stdout, "doctor should say how many probes matched", r)


def test_doctor_refuses_too_few_probes_with_the_count(base):
    r = Project(base, manifest=editions_manifest(), target=OTHER).run("doctor")
    expect(r.returncode == ENV_EXIT and "1 of 3" in r.stderr, "unrecognised file should print the probe count", r)


def hermetic_path(base, own=None):
    """A PATH holding only git and the test's own folder, where looking up gh finds nothing but the test's fake.

    `own` is the folder holding the fake gh; when omitted, an empty one is created. On Windows a link to git's
    launcher does not work, so git's own folder stands in for the link folder."""
    own = Path(own) if own else Path(base) / "empty-path"
    own.mkdir(exist_ok=True)
    git = Path(shutil.which("git"))
    if os.name == "nt":
        git_dir = git.parent
    else:
        git_dir = Path(base) / "git-only"
        git_dir.mkdir(exist_ok=True)
        if not (git_dir / "git").exists():
            (git_dir / "git").symlink_to(git)
    path = os.pathsep.join([str(own), str(git_dir)])
    found = shutil.which("gh", path=path)
    if found and Path(found).parent.resolve() != own.resolve():
        raise AssertionError(f"the test PATH finds a gh other than the fake: {found}")
    return path


def gh_project(base):
    return Project(base, config={"github": {"enabled": True, "repo": "o/r"}})


def one_line(r):
    return len(r.all.strip().splitlines()) == 1 and "Traceback" not in r.all


def test_sync_without_gh_on_path_exits_6_with_one_line(base):
    r = gh_project(base).run("sync", env={"PATH": hermetic_path(base)})
    expect(r.returncode == ENV_EXIT, "sync without gh should exit 6", r)
    expect("gh" in r.all and "not found on PATH" in r.all and one_line(r), "one line saying gh was not found", r)


def test_sync_with_gh_not_logged_in_exits_6_with_one_line(base):
    bin_dir = Path(base) / "fake-bin"
    bin_dir.mkdir()
    if os.name == "nt":
        (bin_dir / "gh.cmd").write_text("@echo off\r\nexit /b 1\r\n")
    else:
        (bin_dir / "gh").write_text("#!/bin/sh\nexit 1\n")
        (bin_dir / "gh").chmod(0o755)
    r = gh_project(base).run("sync", env={"PATH": hermetic_path(base, bin_dir)})
    expect(r.returncode == ENV_EXIT, "sync with gh logged out should exit 6", r)
    expect("gh" in r.all and "not logged in" in r.all and one_line(r), "one line saying gh is not logged in", r)


def test_sync_disabled_does_not_check_gh(base):
    r = Project(base).run("sync", env={"PATH": hermetic_path(base)})
    expect(r.returncode == 0 and "disabled" in r.stdout, "disabled sync should print so and exit 0", r)


def test_doctor_is_unchanged_without_gh(base):
    r = gh_project(base).run("doctor", env={"PATH": hermetic_path(base)})
    expect(r.returncode == 0 and "doctor: ok" in r.stdout and "gh" not in r.all, "doctor ignores gh", r)


def test_check_stops_on_function_the_edition_holds_differently(base):
    p = Project(base, manifest=editions_manifest(), target=STORE)
    r = p.run("check", TID)
    expect(r.returncode == ENV_EXIT, "check should exit 6 on a differs address", r)
    expect("store re-release" in r.stderr and ADDRESS.lower() in r.stderr.lower(), "it should say why", r)
    expect('"result"' not in r.stdout, "nothing should be built", r)
    r = p.run("check", TID)  # the cached environment check must not lose the edition
    expect(r.returncode == ENV_EXIT, "the second check should exit 6 too", r)


def test_verify_records_nothing_on_function_the_edition_holds_differently(base):
    p = Project(base, manifest=editions_manifest(), target=STORE, status="claimed")
    p.branch(f"w/{TID}", {SOURCE: CLEAN + "/* w */\n"})
    r = p.run("verify", TID, "--model", "m")
    expect(r.returncode == ENV_EXIT, "verify should exit 6 on a differs address", r)
    expect(not (p.root / "ledger").exists(), "no ledger record should be written", r)
    expect(p.status() == "claimed", "the ticket should not change", r)


def test_check_runs_on_the_whole_file_edition_of_the_same_contract(base):
    expect_match(Project(base, manifest=editions_manifest()))


def test_differs_may_name_a_function_by_its_key(base):
    m = editions_manifest()
    m["target"]["editions"][1]["differs"] = ["00401000"]
    r = Project(base, manifest=m, target=STORE).run("check", TID)
    expect(r.returncode == ENV_EXIT and "store re-release" in r.stderr, "check should exit 6 on a differs key", r)


def test_revalidate_skips_on_the_integration_branch_and_says_so(base):
    p = Project(base, manifest=editions_manifest(), target=STORE, status="integrated")
    r = p.run("revalidate")
    expect(r.returncode == 0 and f"SKIPPED {TID}" in r.stdout and "1 skipped" in r.stdout, "it should skip, exit 0", r)
    expect(p.status() == "integrated", "the ticket should not change", r)


def test_revalidate_does_not_accept_a_repair_it_could_not_measure(base):
    p = Project(base, manifest=editions_manifest(), target=STORE, status="matched")
    p.branch("r/sym", {"include/keep.h": "/* shared, repaired */\n"})
    r = p.run("revalidate", "--ref", "r/sym")
    expect(r.returncode == ENV_EXIT and f"SKIPPED {TID}" in r.stdout, "an unmeasured repair should exit 6", r)
    expect("not proven here" in r.stderr, "it should say the repair is unproven", r)


# ---- functions named by more than an address ----

def inventory(*functions):
    return {"inventory.json": json.dumps({
        "units": [{"id": UNIT, "source": SOURCE, "start": "0", "end": "0"}],
        "functions": [dict({"size": 8, "unit": UNIT, "scope": "in"}, **f) for f in functions]})}


def tickets_of(p):
    return sorted(f.stem for f in (p.root / "tickets" / UNIT).glob("*.md"))


def test_tickets_for_a_64_bit_target(base):
    p = Project(base, files=inventory({"address": "0x0000000140001000"}))
    r = p.run("gen-tickets")
    expect(r.returncode == 0 and "u0001-140001000" in tickets_of(p), f"got {tickets_of(p)}", r)
    text = (p.root / f"tickets/{UNIT}/u0001-140001000.md").read_text()
    expect("expected: expected/140001000.bin" in text and "address: 0x140001000" in text, text, r)
    p.write("PATTERNS.md", "# Patterns\n- a => b [proven: u0001-140001000] [added: 1789000000]\n")
    r = p.run("report")
    expect(r.returncode == 0 and "PATTERN-MALFORMED" not in r.stdout, "a 64-bit ticket id is well formed", r)
    expect("PATTERN-UNPROVEN: line 2" in r.stdout, "the line should be read as a pattern", r)


def test_functions_sharing_an_address_need_keys(base):
    shared = [{"address": "0x80101000"}, {"address": "0x80101000"}]
    r = Project(base, files=inventory(*shared)).run("gen-tickets")
    expect(r.returncode != 0 and "share the key" in r.stderr, "two functions at one address should stop", r)


def test_keyed_functions_get_their_own_tickets_and_expected_files(base):
    d = Path(base) / "keys"
    d.mkdir()
    p = Project(d, files=inventory({"address": "0x80101000", "key": "ovl1_80101000"},
                                   {"address": "0x80101000", "key": "ovl2_80101000"}))
    r = p.run("gen-tickets")
    expect(r.returncode == 0 and {"u0001-ovl1_80101000", "u0001-ovl2_80101000"} <= set(tickets_of(p)),
           f"got {tickets_of(p)}", r)
    expect("expected: expected/ovl2_80101000.bin" in (p.root / f"tickets/{UNIT}/u0001-ovl2_80101000.md").read_text(),
           "each key should name its own expected file", r)
    expect(p.run("gen-specs").returncode == 0 and "u0001-ovl1_80101000" in (p.root / "units/u0001.md").read_text(),
           "the unit spec should list tickets by key")
    d = Path(base) / "banks"
    d.mkdir()
    p = Project(d, files=inventory({"address": "03:8000"}, {"address": "02:C000"}))
    r = p.run("gen-tickets")
    expect(r.returncode == 0 and {"u0001-02_C000", "u0001-03_8000"} <= set(tickets_of(p)), f"got {tickets_of(p)}", r)
    r = p.run("next", "--n", "5")
    expect(r.returncode == 0, "a bank:offset address should sort", r)


# ---------- next: smallest first ----------

def add_ticket(p, unit, key, tier, size, address, status="open"):
    text = ticket_text(f"{unit}-{key}", address, SOURCE, status)
    text = text.replace("tier: SMALL", f"tier: {tier}").replace("size: 37", f"size: {size}")
    p.write(f"tickets/{unit}/{unit}-{key}.md", text)


def listed(r):
    return [line.split()[0] for line in r.stdout.splitlines()]


def events(p):
    f = p.root / "ledger" / "events.jsonl"
    return [json.loads(x) for x in f.read_text().splitlines()] if f.exists() else []


def test_next_lists_tiny_in_unstarted_unit_before_small_in_started_unit(base):
    p = Project(base, status="integrated")
    p.write(f"tickets/{UNIT}/{UNIT}-00402000.md", ticket_text(f"{UNIT}-00402000", "0x00402000", SOURCE, "open"))
    add_ticket(p, "u0002", "00500000", "TINY", 4, "0x00500000")
    expect(listed(p.run("next", "--n", "5")) == ["u0002-00500000", f"{UNIT}-00402000"], "TINY should come first")


def test_next_lists_smaller_before_lower_address_within_a_tier(base):
    p = Project(base)
    add_ticket(p, "u0002", "00300000", "SMALL", 50, "0x00300000")
    add_ticket(p, "u0003", "00600000", "SMALL", 10, "0x00600000")
    expect(listed(p.run("next", "--n", "5")) == ["u0003-00600000", TID, "u0002-00300000"], "size, then address")


def test_next_injects_no_large_ticket_into_a_small_batch(base):
    p = Project(base)
    add_ticket(p, "u0002", "00500000", "TINY", 4, "0x00500000")
    add_ticket(p, "u0003", "00600000", "LARGE", 900, "0x00600000")
    expect(listed(p.run("next", "--n", "2")) == ["u0002-00500000", TID], "no LARGE in a batch of two")


def test_next_first_lists_the_ticket_first_and_records_one_event(base):
    p = Project(base)
    add_ticket(p, "u0002", "00500000", "TINY", 4, "0x00500000")
    r = p.run("next", "--n", "5", "--first", TID, "--reason", "user asked")
    expect(r.returncode == 0 and listed(r) == [TID, "u0002-00500000"], "ticket first", r)
    ev = [e for e in events(p) if e["event"] == "out-of-order"]
    expect(len(ev) == 1 and ev[0]["ticket"] == TID and ev[0]["reason"] == "user asked", f"got {ev}", r)


def test_next_first_refused_without_reason_or_on_a_ticket_not_ready(base):
    p = Project(base)
    r = p.run("next", "--first", TID)
    expect(r.returncode != 0, "--first without --reason should fail", r)
    q = Project(Path(base) / "claimed", status="claimed") if (Path(base) / "claimed").mkdir() is None else None
    r2 = q.run("next", "--first", TID, "--reason", "x")
    expect(r2.returncode != 0, "a claimed ticket is not ready", r2)
    expect(not events(p) and not events(q), "no event should be appended")


# ---------- symbol map ----------

def test_diff_adapter_receives_symbol_map_path(base):
    p = Project(base)
    r, out = expect_match(p)
    line = Path(out["report"]).read_text().splitlines()[0]
    expect(line.startswith("symbols="), "the report should hold the path the adapter received", r)
    expect(Path(line[len("symbols="):]).samefile(p.root / "symbols.json"), f"wrong symbol map path: {line}", r)


def test_verify_accepts_clean_writer_branch(base):
    p = Project(base, status="claimed")
    p.branch(f"w/{TID}", {SOURCE: CLEAN + "/* w */\n"})
    r = p.run("verify", TID, "--model", "m")
    expect(r.returncode == 0 and '"result": "bytes-match"' in r.stdout, "verify should record bytes-match", r)
    ev = (p.root / "ledger" / "evidence" / f"{TID}-a001.txt").read_text()
    expect(ev.splitlines()[0].replace("\\", "/").endswith("/symbols.json"), f"evidence lacks the symbol map path: {ev}", r)


def test_verify_accepts_the_category_none_a_matching_writer_reports(base):
    p = Project(base, status="claimed")
    p.branch(f"w/{TID}", {SOURCE: CLEAN + "/* w */\n"})
    r = p.run("verify", TID, "--model", "m", "--category", "bogus")
    expect(r.returncode != 0 and "unknown category" in r.stderr, "an unknown category should still stop", r)
    r = p.run("verify", TID, "--model", "m", "--category", "none")
    expect(r.returncode == 0 and '"result": "bytes-match"' in r.stdout, "verify should take category none", r)


def test_verify_rejects_writer_branch_touching_symbol_map(base):
    p = Project(base, status="claimed")
    p.branch(f"w/{TID}", {SOURCE: CLEAN + "/* w */\n", "symbols.json": '{"f": "0x00401000"}\n'})
    r = p.run("verify", TID, "--model", "m")
    expect(r.returncode == 4 and '"result": "guardrail"' in r.stdout, "verify should record guardrail", r)
    ev = (p.root / "ledger" / "evidence" / f"{TID}-a001.txt").read_text()
    expect("guarded" in ev and "symbols.json" in ev, f"evidence should name the guarded path: {ev}", r)


def test_verify_names_status_files_swept_onto_a_writer_branch(base):
    p = Project(base, status="claimed")
    p.branch(f"w/{TID}", {SOURCE: CLEAN + "/* w */\n", f"tickets/{TID}.md": "status: open\n"})
    r = p.run("verify", TID, "--model", "m")
    expect(r.returncode == 4 and '"result": "guardrail"' in r.stdout, "verify should record guardrail", r)
    ev = (p.root / "ledger" / "evidence" / f"{TID}-a001.txt").read_text()
    expect("status files" in ev and "too broadly" in ev, f"evidence should name status files and a broad commit: {ev}", r)


def test_revalidate_accepts_repair_branch_touching_symbol_map(base):
    p = Project(base, status="matched")
    p.branch("r/sym", {"symbols.json": '{"f": "0x00401000"}\n', "include/keep.h": "/* shared, repaired */\n"})
    r = p.run("revalidate", "--ref", "r/sym")
    expect(r.returncode == 0 and "revalidated 1 on r/sym: 0 regressed" in r.stdout, "the repair should be accepted", r)


def test_revalidate_rejects_repair_branch_touching_source(base):
    p = Project(base, status="matched")
    p.branch("r/bad", {"symbols.json": '{"f": "0x00401000"}\n', SOURCE: CLEAN + "/* r */\n"})
    r = p.run("revalidate", "--ref", "r/bad")
    expect(r.returncode == 5 and SOURCE in r.stderr, "a repair may not touch a unit's source", r)


def test_revalidate_rejects_repair_that_breaks_a_match(base):
    p = Project(base, status="matched", source=MARK + '#include "keep.h"\nint f(void) { return K; }\n',
                config={"build": BUILD.replace("open(sys.argv[1]).read()", "open('include/keep.h').read()")},
                headers={"keep.h": "/* MATCH */\n"})
    p.branch("r/sym", {"symbols.json": '{"f": "0x00401004"}\n', "include/keep.h": "/* broken */\n"})
    r = p.run("revalidate", "--ref", "r/sym")
    expect(r.returncode == 5 and f"REGRESSED {TID}" in r.stdout, "a regression should reject the repair", r)


# ---------- candidate ref ----------

NEVER_MATCHES = PY + ' -c "import json;print(json.dumps(dict(match=False,differ_bytes=3)))"'
TOOL_MARKER = "the candidate's own copy ran"


def started_project(base, **kw):
    """A project past decomp-start: both tags set, its one ticket integrated unless told otherwise."""
    kw.setdefault("status", "integrated")
    files = {"inventory.json": '{"units": [], "functions": []}\n', "expected/00401000.bin": "old\n"}
    p = Project(base, files=dict(files, **kw.pop("files", {})), **kw)
    p.git("tag", "decomp-start")
    return p


def config_with(p, **changes):
    return json.dumps(dict(json.loads((p.root / "decomp.json").read_text()), **changes), indent=1)


def expect_nothing_recorded(p, r, status="integrated"):
    expect(not (p.root / "ledger").exists(), "a candidate run should write no ledger record", r)
    expect(p.git("status", "--porcelain").strip() == "", "the checkout should be left as it was", r)
    held = len(list((p.root / "tickets").glob("*/*.md")))
    expect(p.statuses() == {status: held}, "the tickets should not change", r)


def test_candidate_may_change_paths_frozen_by_either_tag(base):
    p = started_project(base)
    p.branch("c/flags", {"DECOMP.md": "# contract, changed\n", "decomp.json": config_with(p, banned=["goto"]),
                         "inventory.json": '{"units": [], "functions": [], "redo": 1}\n',
                         "expected/00401000.bin": "new\n"})
    r = p.run("revalidate", "--candidate", "c/flags")
    expect(r.returncode == 0 and "revalidated 1 on c/flags: 0 regressed, 0 skipped" in r.stdout,
           "a candidate that keeps every match should exit 0", r)
    expect_nothing_recorded(p, r)


def test_candidate_must_be_a_c_branch(base):
    p = started_project(base)
    p.branch("r/sym", {"include/keep.h": "/* shared, repaired */\n"})
    p.branch("flags", {"DECOMP.md": "# contract, changed\n"})
    for ref in ("r/sym", "flags", "c/", "c/no-such-branch", "decomp-setup"):
        r = p.run("revalidate", "--candidate", ref)
        expect(r.returncode not in (0, 5, ENV_EXIT) and "c/<slug>" in r.stderr, f"{ref} should be refused", r)
        expect("revalidated" not in r.stdout, f"nothing should be rebuilt for {ref}", r)


def test_candidate_is_judged_by_its_own_copy_of_the_tool(base):
    p = started_project(base)
    head = "def main():\n    global ROOT, CFG\n"
    tool = TOOL.read_text(encoding="utf-8")
    assert head in tool
    p.branch("c/tool", {"tools/decomp.py": tool.replace(head, head + f'    print("{TOOL_MARKER}")\n')})
    r = p.run("revalidate", "--candidate", "c/tool")
    expect(r.returncode == 0 and TOOL_MARKER in r.stdout, "the candidate's copy of the tool should do the rebuild", r)
    expect(TOOL_MARKER not in p.run("report").stdout, "the checkout's own copy should be untouched")


def test_candidate_that_breaks_a_match_lists_it_and_records_nothing(base):
    p = started_project(base)
    p.branch("c/diff", {"decomp.json": config_with(p, diff=NEVER_MATCHES)})
    r = p.run("revalidate", "--candidate", "c/diff")
    expect(r.returncode == 5 and f"REGRESSED {TID}" in r.stdout and "1 regressed" in r.stdout,
           "a broken match should be listed, with a nonzero exit", r)
    expect_nothing_recorded(p, r)


def test_candidate_it_could_not_measure_exits_6(base):
    p = started_project(base, manifest=editions_manifest(), target=STORE)
    p.branch("c/flags", {"DECOMP.md": "# contract, changed\n"})
    r = p.run("revalidate", "--candidate", "c/flags")
    expect(r.returncode == ENV_EXIT and f"SKIPPED {TID}" in r.stdout, "an unmeasured candidate should exit 6", r)
    expect("not proven here" in r.stderr, "it should say the candidate is unproven", r)
    expect_nothing_recorded(p, r)


def test_candidate_rebuilds_the_tickets_the_project_holds_matched(base):
    p = started_project(base)
    p.branch("c/diff", {"decomp.json": config_with(p, diff=NEVER_MATCHES)})
    ticket = p.root / f"tickets/{UNIT}/{TID}.md"  # matched after the candidate branched, and not committed
    ticket.write_text(ticket.read_text().replace("status: integrated", "status: open"))
    p.git("commit", "-q", "-am", "an open ticket")
    r = p.run("revalidate", "--candidate", "c/diff")
    expect(r.returncode == 0 and "revalidated 0 on c/diff" in r.stdout, "an open ticket is not rebuilt", r)
    ticket.write_text(ticket.read_text().replace("status: open", "status: matched"))
    r = p.run("revalidate", "--candidate", "c/diff")
    expect(r.returncode == 5 and f"REGRESSED {TID}" in r.stdout, "the project's matched ticket is rebuilt", r)


TID2 = "u0002-00402000"  # a second unit's ticket, which no edition holds differently
MATCHING2 = f"// @decomp {TID2}\nint g(void) {{ return 2; }} /* MATCH */\n"


def second_ticket(status="integrated", source=MATCHING2):
    """Files that give a project a second unit with one ticket."""
    return {"src/u0002.c": source, f"tickets/u0002/{TID2}.md": ticket_text(TID2, "0x00402000", "src/u0002.c", status)}


def test_candidate_with_a_regression_and_a_skipped_ticket_exits_6_and_lists_both(base):
    p = started_project(base, manifest=editions_manifest(), target=STORE, files=second_ticket())
    p.branch("c/diff", {"decomp.json": config_with(p, diff=NEVER_MATCHES)})
    r = p.run("revalidate", "--candidate", "c/diff")
    expect(r.returncode == ENV_EXIT, "a skipped ticket should win over a regression: exit 6", r)
    expect(f"SKIPPED {TID}" in r.stdout and f"REGRESSED {TID2}" in r.stdout, "both should still be listed", r)
    expect_nothing_recorded(p, r)


def test_candidate_refuses_to_be_narrowed_to_a_header(base):
    p = started_project(base)
    p.branch("c/flags", {"DECOMP.md": "# contract, changed\n"})
    r = p.run("revalidate", "--candidate", "c/flags", "--header", "include/keep.h")
    expect(r.returncode == 2 and "--header" in r.stderr, "a candidate run rebuilds every matched ticket", r)
    expect("revalidated" not in r.stdout, "nothing should be rebuilt", r)


def test_judged_for_is_refused_outside_a_candidates_own_worktree(base):
    p = started_project(base)
    p.branch("flags", {"DECOMP.md": "# contract, changed\n"})
    p.branch("c/flags", {"DECOMP.md": "# contract, changed\n"})
    p.write("DECOMP.md", "# edited on the integration branch\n")
    p.git("commit", "-q", "-am", "edit a frozen path")
    for args in ([], ["--candidate", "flags"], ["--candidate", "c/flags"], ["--ref", "c/flags"]):
        r = p.run("revalidate", "--judged-for", str(p.root), *args)
        expect(r.returncode == 2 and "revalidated" not in r.stdout, f"--judged-for with {args} should be refused", r)


def test_candidate_is_not_blamed_for_a_ticket_already_regressed(base):
    broken = f"// @decomp {TID2}\nint g(void) {{ return 3; }}\n"
    p = started_project(base, files=second_ticket(status="regressed", source=broken))
    p.branch("c/flags", {"DECOMP.md": "# contract, changed\n"})
    r = p.run("revalidate", "--candidate", "c/flags")
    expect(r.returncode == 0 and "REGRESSED" not in r.stdout, "only matched tickets count against a candidate", r)
    expect("revalidated 1 on c/flags: 0 regressed" in r.stdout, "the regressed ticket is not rebuilt", r)


def test_candidate_that_drops_a_matched_ticket_lists_it_as_regressed(base):
    p = started_project(base, files=second_ticket())
    p.git("checkout", "-q", "-b", "c/redo", "main")
    p.git("rm", "-q", f"tickets/u0002/{TID2}.md")
    p.git("commit", "-q", "-m", "an inventory without the second function")
    p.git("checkout", "-q", "main")
    r = p.run("revalidate", "--candidate", "c/redo")
    expect(r.returncode == 5 and f"REGRESSED {TID2} on c/redo: the candidate holds no such ticket" in r.stdout,
           "a matched ticket the candidate lacks is a regression", r)
    expect("revalidated 1 on c/redo: 1 regressed" in r.stdout, "the ticket it still holds is rebuilt", r)
    expect_nothing_recorded(p, r)


def test_skills_copy_judges_a_candidate_for_a_project_whose_tool_has_no_candidate_mode(base):
    p = started_project(base)
    p.write("tools/decomp.py", "raise SystemExit('an older tool: no --candidate')\n")
    p.git("commit", "-q", "-am", "the tool an older skill version set up")
    p.git("tag", "-f", "decomp-setup")
    p.branch("c/upgrade", {"tools/decomp.py": TOOL.read_text(encoding="utf-8")})
    expect(p.run("revalidate", "--candidate", "c/upgrade").returncode == 1, "the project's own copy cannot run it")
    r = p.run("revalidate", "--candidate", "c/upgrade", tool=TOOL)
    expect(r.returncode == 0 and "revalidated 1 on c/upgrade: 0 regressed, 0 skipped" in r.stdout,
           "the skill's copy, run from the project root, should hand the candidate to its own copy", r)
    expect_nothing_recorded(p, r)


def test_plain_revalidate_still_refuses_when_a_frozen_path_differs(base):
    for d, (rel, tag) in each(base, [("DECOMP.md", "decomp-setup"), ("inventory.json", "decomp-start")]):
        p = started_project(d)
        p.write(rel, "changed\n")
        p.git("commit", "-q", "-am", "edit a frozen path")
        r = p.run("revalidate")
        expect(r.returncode == 2 and "frozen" in r.stderr and tag in r.stderr, "a moved frozen path should refuse", r)
        expect(not (p.root / "ledger").exists(), "nothing should be recorded", r)


def test_repair_ref_is_still_held_to_headers_and_the_symbol_map(base):
    p = started_project(base)
    p.branch("r/contract", {"DECOMP.md": "# contract, changed\n"})
    r = p.run("revalidate", "--ref", "r/contract")
    expect(r.returncode == 5 and "DECOMP.md" in r.stderr, "a repair ref may not touch a frozen path", r)
    p.branch("c/flags", {"DECOMP.md": "# contract, changed\n"})
    r = p.run("revalidate", "--ref", "c/flags")
    expect(r.returncode == 5 and "DECOMP.md" in r.stderr, "only --candidate lifts the limit", r)


# ---------- provisioning ----------

def with_prerequisites(*pre):
    m = legacy_manifest()
    m["prerequisites"] = [{"name": n, "version_cmd": c, "version": v} for n, c, v in pre]
    return m


def test_doctor_passes_present_host_prerequisite(base):
    r = Project(base, manifest=with_prerequisites(("python", PY + " --version", "Python 3"))).run("doctor")
    expect(r.returncode == 0 and "python ok" in r.stdout, "a present prerequisite should pass by name", r)


def test_doctor_fails_missing_host_prerequisite_by_name(base):
    m = with_prerequisites(("python", PY + " --version", "Python 3"),
                           ("archiver", "no-such-archiver-zz9 --version", "Archiver 9"),
                           ("layer", "no-such-layer-zz9 --version", "Layer 8"))
    r = Project(base, manifest=m, installed=()).run("doctor")
    expect(r.returncode == ENV_EXIT and "archiver" in r.stderr, "the missing prerequisite should be named", r)
    expect("layer" not in r.stderr, "only the first missing prerequisite should be named", r)
    expect("compiler" not in r.stderr, "tools should not be checked behind a missing prerequisite", r)


def test_doctor_fails_wrong_version_host_prerequisite(base):
    r = Project(base, manifest=with_prerequisites(("python", PY + " --version", "Python 1.5.2"))).run("doctor")
    expect(r.returncode == ENV_EXIT and "python" in r.stderr and "Python 1.5.2" in r.stderr, "wrong version exits 6", r)


def sourced_manifest(archive, digest=None):
    m = legacy_manifest()
    m["tools"][0].update(installed_by="agent", unpack=[PY + ' "{tools}/unpack.py" "{archive}" "{root}"'], source={
        "url": "https://127.0.0.1:9/cc-1.0.bin", "size": len(archive),
        "sha256": sha(archive) if digest is None else digest})
    return m


def provision_project(base, digest=None, manifest=None):
    archive = FAKE_TOOL.encode()
    p = Project(base, manifest=manifest or sourced_manifest(archive, digest), installed=(),
                files={"tools/unpack.py": UNPACK})
    (p.root / ".decomp" / "downloads").mkdir(parents=True)
    (p.root / ".decomp" / "downloads" / "cc-1.0.bin").write_bytes(archive)
    return p


def test_provision_unpacks_with_a_project_script(base):
    p = provision_project(base)
    r = p.run("provision")
    expect(r.returncode == 0 and (p.root / ".decomp/toolchain/compiler/cc.py").is_file(), "the script should unpack", r)
    r = p.run("doctor")
    expect(r.returncode == 0 and "compiler ok" in r.stdout, "doctor should pass after provision", r)
    r = p.run("provision")
    expect(r.returncode == 0 and "already unpacked" in r.stdout, "a second provision should do nothing", r)


def test_provision_unpacks_nothing_on_hash_mismatch(base):
    p = provision_project(base, digest="0" * 64)
    r = p.run("provision")
    expect(r.returncode == ENV_EXIT, "a wrong hash should exit 6", r)
    expect("0" * 64 in r.stderr and sha(FAKE_TOOL.encode()) in r.stderr, "both hashes should print", r)
    expect("downloading" not in r.stdout, "a file already there is compared, never silently replaced", r)
    expect(not (p.root / ".decomp/toolchain/compiler/cc.py").exists(), "nothing should be unpacked", r)


def test_provision_unpacks_nothing_on_size_mismatch(base):
    m = sourced_manifest(FAKE_TOOL.encode())
    m["tools"][0]["source"]["size"] += 1
    p = provision_project(base, manifest=m)
    r = p.run("provision")
    expect(r.returncode == ENV_EXIT and "Nothing was unpacked" in r.stderr, "a wrong size should exit 6", r)
    expect(not (p.root / ".decomp/toolchain/compiler/cc.py").exists(), "nothing should be unpacked", r)


def test_provision_names_a_missing_host_prerequisite(base):
    m = sourced_manifest(FAKE_TOOL.encode())
    m["prerequisites"] = [{"name": "archiver", "version_cmd": "no-such-archiver-zz9 --version", "version": "Archiver 9"}]
    p = provision_project(base, manifest=m)
    r = p.run("provision")
    expect(r.returncode == ENV_EXIT and "prerequisite archiver" in r.stderr, "the prerequisite should be named", r)
    expect(not (p.root / ".decomp/toolchain/compiler/cc.py").exists(), "nothing should be unpacked", r)


# ---- hosts ----

HERE, ELSEWHERE = [sys.platform], ["no-such-host"]


def test_prerequisite_for_another_host_is_not_checked(base):
    m = with_prerequisites(("layer", "no-such-layer-zz9 --version", "Layer 8"))
    m["prerequisites"][0]["hosts"] = ELSEWHERE
    r = Project(base, manifest=m).run("doctor")
    expect(r.returncode == 0 and "layer" not in r.all, "another host's prerequisite should be ignored", r)


def test_prerequisite_for_this_host_is_checked(base):
    m = with_prerequisites(("layer", "no-such-layer-zz9 --version", "Layer 8"))
    m["prerequisites"][0]["hosts"] = HERE
    r = Project(base, manifest=m).run("doctor")
    expect(r.returncode == ENV_EXIT and "prerequisite layer" in r.stderr, "this host's prerequisite should fail", r)


def test_tool_entry_is_chosen_by_host(base):
    m = legacy_manifest()
    here, there = dict(tool_entry(), hosts=HERE), dict(tool_entry(), hosts=ELSEWHERE, banner="OtherCC 9", files=["no.exe"])
    m["tools"] = [there, here]
    r = Project(base, manifest=m).run("doctor")
    expect(r.returncode == 0 and "compiler ok: FakeCC 1.0" in r.stdout, "this host's entry should be the one checked", r)


def test_compiler_listed_only_for_another_host_is_an_environment_result(base):
    m = legacy_manifest()
    m["tools"] = [dict(tool_entry(), hosts=ELSEWHERE)]
    r = Project(base, manifest=m, config={"compiler": "compiler"}).run("check", TID)
    expect(r.returncode == ENV_EXIT and "another host" in r.stderr and '"result"' not in r.stdout, "check should exit 6", r)


def test_provision_unpacks_nothing_without_a_recorded_hash(base):
    p = provision_project(base, digest="")
    r = p.run("provision")
    expect(r.returncode == ENV_EXIT and sha(FAKE_TOOL.encode()) in r.stdout, "it should print the hash and stop", r)
    expect(not (p.root / ".decomp/toolchain/compiler/cc.py").exists(), "nothing should be unpacked", r)


def test_provision_refuses_non_https_source(base):
    m = sourced_manifest(FAKE_TOOL.encode())
    m["tools"][0]["source"]["url"] = "http://127.0.0.1:9/cc-1.0.bin"
    r = Project(base, manifest=m, installed=()).run("provision")
    expect(r.returncode != 0 and "https" in r.stderr, "an http source should be refused", r)


def two_compilers():
    m = legacy_manifest()
    m["tools"].append(tool_entry("compiler2"))
    return m


def built_with(out):
    return [l for l in Path(out["report"]).read_text().splitlines() if l.startswith("compiler=")]


def test_build_adapter_receives_default_compiler(base):
    p = Project(base, manifest=two_compilers(), installed=("compiler", "compiler2"), config={"compiler": "compiler"})
    r, out = expect_match(p)
    expect(built_with(out) == ["compiler=compiler"], f"wrong compiler: {built_with(out)}", r)


def test_build_adapter_receives_units_own_compiler(base):
    p = Project(base, manifest=two_compilers(), installed=("compiler", "compiler2"),
                config={"compiler": "compiler", "unit_compilers": {UNIT: "compiler2"}})
    r, out = expect_match(p)
    expect(built_with(out) == ["compiler=compiler2"], f"wrong compiler: {built_with(out)}", r)


def test_unit_mapped_to_unprovisioned_compiler_is_an_environment_result(base):
    p = Project(base, manifest=two_compilers(), installed=("compiler",),
                config={"compiler": "compiler", "unit_compilers": {UNIT: "compiler2"}})
    r = p.run("check", TID)
    expect(r.returncode == ENV_EXIT and "compiler2" in r.stderr and '"result"' not in r.stdout, "check should exit 6", r)


def test_another_units_unprovisioned_compiler_stops_only_that_unit(base):
    p = Project(base, manifest=two_compilers(), installed=("compiler",),
                config={"compiler": "compiler", "unit_compilers": {"u0002": "compiler2"}})
    r, out = expect_match(p)
    expect(built_with(out) == ["compiler=compiler"], f"wrong compiler: {built_with(out)}", r)
    r = p.run("doctor")
    expect(r.returncode == ENV_EXIT and "compiler2" in r.stderr, "a full doctor still reports the missing compiler", r)


def test_revalidate_skips_a_unit_whose_compiler_is_not_usable(base):
    p = Project(base, manifest=two_compilers(), installed=("compiler",), status="integrated",
                config={"compiler": "compiler", "unit_compilers": {UNIT: "compiler2"}})
    r = p.run("revalidate")
    expect(r.returncode == 0 and f"SKIPPED {TID}" in r.stdout and "compiler2" in r.stdout, "it should skip that unit", r)
    expect(p.status() == "integrated", "the ticket should not change", r)


def test_revalidate_stops_before_any_write_on_a_compiler_outside_the_manifest(base):
    p = Project(base, status="integrated", config={"compiler": "compiler", "unit_compilers": {UNIT: "ghost"}})
    r = p.run("revalidate")
    expect(r.returncode == ENV_EXIT and "ghost" in r.stderr and not (p.root / "ledger").exists(), "exit 6, no record", r)


# ---- adapter commands ----

def test_adapter_commands_fill_tools_and_python(base):
    script = "import sys\nopen(sys.argv[2], 'w').write(open(sys.argv[1]).read() + chr(10) + 'compiler=wrapped' + chr(10))\n"
    p = Project(base, files={"tools/cc_wrap.py": script},
                config={"build": '"{python}" "{tools}/cc_wrap.py" "{source}" "{obj}"'})
    r, out = expect_match(p)
    expect(built_with(out) == ["compiler=wrapped"], "the build should run the project's script", r)


def test_adapter_command_keeps_braces_it_does_not_know(base):
    build = PY + (' -c "import sys;d={1:chr(10)};open(sys.argv[2],\'w\').write(open(sys.argv[1]).read()+d[1]'
                  '+\'compiler={other}\'+d[1])" "{source}" "{obj}"')
    r, out = expect_match(Project(base, config={"build": build}))
    expect(built_with(out) == ["compiler={other}"], f"an unknown brace should stay as written: {built_with(out)}", r)


def test_tool_output_in_another_encoding_does_not_lose_the_result(base):
    diff = PY + (' -c "import sys;sys.stdout.buffer.write(bytes([0x83,0x65,0x81,10]));'
                 'sys.stderr.buffer.write(bytes([0x93,0xfa]));'
                 'print(chr(123)+chr(34)+\'match\'+chr(34)+\': true, \'+chr(34)+\'differ_bytes\'+chr(34)+\': 0\'+chr(125))"')
    expect_match(Project(base, config={"diff": diff}))


# ---- inventory and disasm through the project tool ----

# The fake adapters record what they received: the inventory in the file it writes,
# the disassembler on stdout.
RECEIVED = ("import json, os, sys\n"
            "got = {'argv': sys.argv[1:], 'env': {k: v for k, v in os.environ.items() if k.startswith('DECOMP_T')}}\n")
ADAPTERS = {"tools/inv.py": RECEIVED + "json.dump(got, open('inventory.json', 'w'))\n",
            "tools/dis.py": RECEIVED + "print(json.dumps(got))\n"}
ADAPTER_CMDS = {"inventory": '"{python}" "{tools}/inv.py"',
                "disasm": '"{python}" "{tools}/dis.py" "{expected}" "{address}"'}


def adapter_project(base, config=None, **kw):
    return Project(base, files=ADAPTERS, config=dict(ADAPTER_CMDS, **(config or {})), **kw)


def expect_tool_env(p, env, r):
    expect(Path(env.get("DECOMP_TARGET", "")) == p.target, f"wrong DECOMP_TARGET: {env}", r)
    expect(Path(env.get("DECOMP_TOOL_COMPILER", "")) == p.root / ".decomp" / "toolchain" / "compiler",
           f"wrong DECOMP_TOOL_COMPILER: {env}", r)


def test_inventory_adapter_receives_the_tool_environment(base):
    p = adapter_project(base)
    r = p.run("inventory")
    expect(r.returncode == 0 and (p.root / "inventory.json").is_file(), "the inventory adapter should run", r)
    expect_tool_env(p, json.loads((p.root / "inventory.json").read_text())["env"], r)


def test_inventory_writes_nothing_on_a_target_that_is_not_accepted(base):
    p = adapter_project(base, target=STORE)
    r = p.run("inventory")
    expect(r.returncode == ENV_EXIT and "ENVIRONMENT: target" in r.stderr, "a wrong target should exit 6", r)
    expect(not (p.root / "inventory.json").exists(), "the adapter should not run", r)


def test_inventory_never_trusts_the_cached_environment_check(base):
    p = adapter_project(base)
    expect_match(p)  # leaves a cached pass behind
    r = p.run("inventory", env={"FAKE_BANNER": "FakeCC 2.0"})
    expect(r.returncode == ENV_EXIT and not (p.root / "inventory.json").exists(), "inventory runs the full check", r)


def test_inventory_refuses_once_the_decomp_start_tag_exists(base):
    p = adapter_project(base)
    p.git("tag", "decomp-start")
    r = p.run("inventory")
    expect(r.returncode not in (0, ENV_EXIT), "a frozen inventory should be refused", r)
    expect("decomp-start" in r.stderr and "redo" in r.stderr, "the refusal should name the redo flow", r)
    expect(not (p.root / "inventory.json").exists(), "the adapter should not run", r)


def test_inventory_redo_runs_with_the_decomp_start_tag(base):
    p = adapter_project(base)
    p.git("tag", "decomp-start")
    r = p.run("inventory", "--redo")
    expect(r.returncode == 0 and (p.root / "inventory.json").is_file(), "--redo should run the adapter", r)


def test_inventory_exits_with_the_adapters_failure(base):
    p = adapter_project(base, config={"inventory": '"{python}" -c "raise SystemExit(3)"'})
    r = p.run("inventory")
    expect(r.returncode not in (0, ENV_EXIT), "a failed adapter is a failed inventory, never an environment result", r)


def test_disasm_adapter_receives_the_tickets_file_and_address(base):
    p = adapter_project(base)
    r = p.run("disasm", TID)
    expect(r.returncode == 0 and r.stdout.strip(), "the disasm adapter's output should be printed", r)
    got = json.loads(r.stdout.splitlines()[-1])
    expect(got["argv"] == ["expected/00401000.bin", ADDRESS], f"wrong expected file or address: {got['argv']}", r)
    expect_tool_env(p, got["env"], r)


def test_disasm_stops_on_a_target_that_is_not_accepted(base):
    r = adapter_project(base, target=STORE).run("disasm", TID)
    expect(r.returncode == ENV_EXIT and "ENVIRONMENT: target" in r.stderr, "a wrong target should exit 6", r)
    expect("argv" not in r.stdout, "the adapter should not run", r)


# ---- locks ----

def test_a_claim_in_one_worktree_holds_in_every_other(base):
    p = Project(base)
    wt = p.base / "wt"
    p.git("worktree", "add", "-q", str(wt), "-b", "side")
    r = p.run("claim", TID, "--by", "w1", cwd=wt)
    expect(r.returncode == 0, "the claim should succeed", r)
    r = p.run("claim", TID, "--by", "w2")
    expect(r.returncode == 3 and "locked" in r.stderr and "w1" in r.stderr, "the main checkout should see the lock", r)
    r = p.run("lock", "reference", "--by", "c")
    expect(r.returncode == 0, "another lock is free", r)
    r = p.run("lock", "reference", "--by", "d", cwd=wt)
    expect(r.returncode == 3, "the worktree should see the reference lock", r)


def test_unit_mapped_to_tool_outside_manifest_is_an_environment_result(base):
    p = Project(base, config={"compiler": "compiler", "unit_compilers": {UNIT: "ghost"}}, status="claimed")
    r = p.run("check", TID)
    expect(r.returncode == ENV_EXIT and "ghost" in r.stderr and '"result"' not in r.stdout, "check should exit 6", r)
    p.branch(f"w/{TID}", {SOURCE: CLEAN + "/* w */\n"})
    r = p.run("verify", TID, "--model", "m")
    expect(r.returncode == ENV_EXIT and not (p.root / "ledger").exists(), "verify should exit 6, recording nothing", r)


# ---------- behaviour of doctor that predates this script ----------

def test_doctor_fails_on_missing_tool_file(base):
    r = Project(base, installed=()).run("doctor")
    expect(r.returncode == ENV_EXIT and "compiler: missing" in r.stderr, "a missing tool file should exit 6", r)


def test_doctor_fails_on_wrong_banner(base):
    r = Project(base).run("doctor", env={"FAKE_BANNER": "FakeCC 2.0"})
    expect(r.returncode == ENV_EXIT and "banner lacks" in r.stderr, "a wrong banner should exit 6", r)


# ---------- banner file: a tool with no executable is pinned by a file ----------

SDK_VERSION_FILE = "include/sdkver.h"


def sdk_version_file(p):
    return p.root / ".decomp" / "toolchain" / "sdk" / SDK_VERSION_FILE


def sdk_project(base, contents="#define SDK_VERSION \"FakeSDK 7.1\"\n", encoding="utf-8", **fields):
    """A project with a header-only tool. `contents` None leaves its banner file missing."""
    sdk = {"name": "sdk", "product": "FakeSDK 7.1", "installed_by": "user",
           "banner_file": SDK_VERSION_FILE, "banner": "FakeSDK 7.1"}
    sdk.update(fields)
    sdk = {k: v for k, v in sdk.items() if v is not None}
    p = Project(base, manifest=dict(legacy_manifest(), tools=[tool_entry(), sdk]))
    if contents is not None:
        sdk_version_file(p).parent.mkdir(parents=True)
        sdk_version_file(p).write_bytes(contents.encode(encoding))
    return p


def test_doctor_passes_when_the_banner_file_holds_the_banner(base):
    r = sdk_project(base).run("doctor")
    expect(r.returncode == 0 and "sdk ok: FakeSDK 7.1" in r.stdout, "doctor should pass on the banner file", r)


def test_doctor_fails_when_the_banner_file_holds_another_version(base):
    r = sdk_project(base, contents="#define SDK_VERSION \"FakeSDK 7.0\"\n").run("doctor")
    expect(r.returncode == ENV_EXIT and "ENVIRONMENT: sdk: banner lacks 'FakeSDK 7.1'" in r.stderr,
           "another version in the banner file should exit 6, naming the tool", r)


def test_doctor_fails_on_a_missing_banner_file(base):
    r = sdk_project(base, contents=None).run("doctor")
    expect(r.returncode == ENV_EXIT and "ENVIRONMENT: sdk:" in r.stderr and "sdkver.h" in r.stderr,
           "a missing banner file should exit 6, naming the file", r)


def test_doctor_fails_on_a_tool_with_both_banner_file_and_banner_cmd(base):
    r = sdk_project(base, banner_cmd=PY + ' -c "print(\'FakeSDK 7.1\')"').run("doctor")
    expect(r.returncode == ENV_EXIT and "ENVIRONMENT: sdk:" in r.stderr and "both" in r.stderr,
           "a tool with both pins should exit 6, naming the tool", r)


def test_doctor_fails_on_a_tool_with_neither_banner_file_nor_banner_cmd(base):
    r = sdk_project(base, banner_file=None).run("doctor")
    expect(r.returncode == ENV_EXIT and "ENVIRONMENT: sdk:" in r.stderr and "neither" in r.stderr,
           "a tool with no pin should exit 6, naming the tool", r)


def test_doctor_reads_a_banner_file_in_another_encoding(base):
    for d, encoding in each(base, ("utf-16", "utf-16-le", "cp1252")):
        r = sdk_project(d, contents="// café ©\r\n#define SDK_VERSION \"FakeSDK 7.1\"\r\n",
                        encoding=encoding).run("doctor")
        expect(r.returncode == 0 and "sdk ok: FakeSDK 7.1" in r.stdout, f"doctor should read a {encoding} file", r)


def test_check_stops_trusting_the_last_pass_when_the_banner_file_changes(base):
    p = sdk_project(base)
    expect_match(p)
    sdk_version_file(p).write_text("#define SDK_VERSION \"FakeSDK 8.0 beta\"\n")
    r = p.run("check", TID)
    expect(r.returncode == ENV_EXIT and "sdk: banner lacks" in r.stderr, "a changed banner file ends the trust", r)


def test_worktrees_share_the_main_checkouts_machine_folder(base):
    p = Project(base)
    wt = p.base / "wt"
    p.git("worktree", "add", "-q", str(wt), "-b", "side")
    expect(not (wt / ".decomp").exists(), "the worktree should have no machine folder of its own")
    r = p.run("doctor", cwd=wt)
    expect(r.returncode == 0 and "doctor: ok" in r.stdout, "doctor should pass in a worktree", r)
    r = p.run("check", TID, cwd=wt)
    expect(r.returncode == 0 and "bytes-match" in r.stdout, "check should run in a worktree", r)


def test_decomp_local_names_another_machine_folder(base):
    p = Project(base)
    clone = p.base / "clone"
    subprocess.run(["git", "clone", "-q", str(p.root), str(clone)], check=True, capture_output=True)
    r = p.run("doctor", cwd=clone)
    expect(r.returncode == ENV_EXIT, "a clone has no machine folder", r)
    r = p.run("doctor", cwd=clone, env={"DECOMP_LOCAL": str(p.root / ".decomp")})
    expect(r.returncode == 0, "DECOMP_LOCAL should supply one", r)


def test_check_trusts_the_last_pass_until_a_watched_file_changes(base):
    p = Project(base)
    broken = {"FAKE_BANNER": "FakeCC 2.0"}
    expect_match(p)
    expect_match(p, env=broken)  # trusted: nothing watched has changed
    r = p.run("doctor", env=broken)
    expect(r.returncode == ENV_EXIT, "a full doctor never trusts the cache", r)
    r = p.run("check", TID, env=broken)
    expect(r.returncode == ENV_EXIT, "a failed doctor should clear the cached pass", r)
    expect_match(p)
    p.target.write_bytes(STORE)
    r = p.run("check", TID)
    expect(r.returncode == ENV_EXIT and "ENVIRONMENT: target" in r.stderr, "a changed target ends the trust", r)


def state_of(p):
    r = p.run("report")
    lines = [l for l in r.stdout.splitlines() if l.startswith("state:")]
    expect(r.returncode == 0 and len(lines) == 1, "report should print exactly one state line", r)
    return lines[0]


def test_report_states_more_when_a_ticket_is_ready(base):
    p = started_project(base, status="integrated", files=second_ticket(status="open"))
    expect(state_of(p).split()[1] == "more", "a ready ticket means more", p.run("report"))


def test_report_states_stuck_when_the_rest_are_blocked_or_regressed(base):
    p = started_project(base, status="regressed", files=second_ticket(status="blocked-reference"))
    expect(state_of(p).split()[1] == "stuck", "nothing ready means stuck", p.run("report"))


def test_report_states_finished_when_every_ticket_is_revalidated(base):
    p = started_project(base, status="revalidated", files=second_ticket(status="revalidated"))
    expect(state_of(p).split()[1] == "finished", "all revalidated means finished", p.run("report"))


def test_report_does_not_state_finished_for_integrated_tickets(base):
    p = started_project(base, status="revalidated", files=second_ticket(status="integrated"))
    expect(state_of(p).split()[1] == "more", "integrated, not revalidated, is not finished", p.run("report"))


# ---- whole-binary link ----

# The fake linker concatenates the plan's raw blocks and each source function's bytes
# in file offset order. A function's bytes are what its object holds: the fake compiler
# copies the source, so a source line `/* bytes <id> <hex> */` is the compiled function.
FAKE_LINK = ("import json, os, re, sys\n"
             "plan = json.load(open(sys.argv[1]))\n"
             "target = open(os.environ['DECOMP_TARGET'], 'rb').read()\n"
             "pieces = [(b['offset'], target[b['offset']:b['offset'] + b['size']]) for b in plan['blocks']]\n"
             "for o in plan['objects']:\n"
             "    held = dict(re.findall(r'bytes (\\S+) ([0-9a-f]+)', open(o['obj']).read()))\n"
             "    pieces += [(f['offset'], bytes.fromhex(held.get(f['id'], ''))) for f in o['functions']]\n"
             "open(sys.argv[2], 'wb').write(b''.join(d for _, d in sorted(pieces)))\n"
             "open(sys.argv[2] + '.plan.json', 'w').write(json.dumps(plan))\n")
LINK_CMD = '"{python}" "{tools}/link.py" "{plan}" "{out}"'
TID3 = "u0002-00402030"  # the second unit's second function, never matched
LAYOUT = [(TID, ADDRESS, 0x400), (TID2, "0x00402000", 0x800), (TID3, "0x00402030", 0x830)]
LIBRARY_AT = 0x430  # an out-of-scope function in the first unit


def code_line(tid, offset, flip=False):
    data = RETAIL[offset:offset + 37]
    if flip:
        data = patched(data, 5)
    return f"/* bytes {tid} {data.hex()} */\n"


def link_project(base, statuses=("integrated", "integrated", "open"), config=None, flip=None, **kw):
    """Two units: u0001 holds one in-scope and one library function, u0002 two in-scope ones."""
    functions = [{"address": a, "size": 37, "unit": t.split("-")[0], "scope": "in", "offset": o} for t, a, o in LAYOUT]
    functions.insert(1, {"address": "0x00401030", "size": 16, "unit": UNIT, "scope": "library", "offset": LIBRARY_AT})
    inv = {"units": [{"id": UNIT, "source": SOURCE, "start": "0", "end": "0"},
                     {"id": "u0002", "source": "src/u0002.c", "start": "0", "end": "0"}], "functions": functions}
    src2 = MATCHING2 + code_line(TID2, 0x800, flip == TID2) + f"// @decomp {TID3}\n" + code_line(TID3, 0x830)
    files = dict(second_ticket(statuses[1], source=src2), **{
        "inventory.json": json.dumps(inv), "tools/link.py": FAKE_LINK,
        f"tickets/u0002/{TID3}.md": ticket_text(TID3, "0x00402030", "src/u0002.c", statuses[2])})
    files.update(kw.pop("files", {}))
    p = Project(base, source=CLEAN + code_line(TID, 0x400, flip == TID), status=statuses[0],
                config=dict({"link": LINK_CMD}, **(config or {})), files=files, **kw)
    p.git("tag", "decomp-start")
    return p


def link_output(r):
    """The path the result line names."""
    line = next(l for l in r.stdout.splitlines() if l.startswith("link:"))
    return Path(line.split("output ", 1)[1].strip())


def received_plan(r):
    return json.loads(Path(str(link_output(r)) + ".plan.json").read_text())


def test_link_takes_a_fully_matched_unit_from_source_and_a_partly_matched_one_from_blocks(base):
    p = link_project(base)
    r = p.run("link")
    expect(r.returncode == 0 and "link: pass" in r.stdout, "the link should reproduce the target", r)
    plan = received_plan(r)
    expect([o["unit"] for o in plan["objects"]] == [UNIT], f"only u0001 is from source: {plan['objects']}", r)
    expect([f["id"] for f in plan["objects"][0]["functions"]] == [TID], "the library function is not from source", r)
    covered = sorted([(b["offset"], b["size"]) for b in plan["blocks"]] + [(0x400, 37)])
    expect(covered == [(0, 0x400), (0x400, 37), (0x425, len(RETAIL) - 0x425)], f"blocks cover the rest: {covered}", r)
    expect(link_output(r).read_bytes() == RETAIL, "the output is the target's bytes", r)


def link_events(p):
    path = p.root / "ledger" / "events.jsonl"
    return [e for e in map(json.loads, path.read_text().splitlines()) if e["event"] == "link"] if path.exists() else []


def ticket_texts(p):
    return {f: f.read_text() for f in sorted((p.root / "tickets").glob("*/*.md"))}


def test_link_takes_a_unit_holding_a_function_the_edition_differs_on_from_blocks(base):
    manifest = {"target": {"editions": [{"name": "retail 1.0", "sha256": sha(RETAIL), "size": len(RETAIL),
                                         "differs": ["0x00402000"]}]}, "tools": [tool_entry()]}
    p = link_project(base, statuses=("integrated",) * 3, manifest=manifest, flip=TID2)
    r = p.run("link")
    expect(r.returncode == 0 and "link: pass" in r.stdout, "u0002 comes from blocks, so its source is not linked", r)
    expect([o["unit"] for o in received_plan(r)["objects"]] == [UNIT], "only u0001 is from source", r)


def test_link_from_raw_blocks_alone_reproduces_the_target_hash(base):
    p = link_project(base, statuses=("open",) * 3)
    r = p.run("link")
    expect(r.returncode == 0 and "link: pass" in r.stdout, "a blocks-only link should pass", r)
    expect(received_plan(r)["objects"] == [], "no unit comes from source", r)
    expect(sha(link_output(r).read_bytes()) == sha(RETAIL), "the output hashes as the target", r)


def test_link_reports_the_share_of_in_scope_code_bytes_from_source(base):
    for d, (statuses, share) in each(base, [(("integrated", "integrated", "open"), "37 / 111 in-scope code B from source (33.33%)"),
                                            (("revalidated",) * 3, "111 / 111 in-scope code B from source (100.00%)"),
                                            (("open", "revalidated", "integrated"), "74 / 111 in-scope code B from source (66.67%)")]):
        r = link_project(d, statuses=statuses).run("link")
        expect(r.returncode == 0 and share in r.stdout, f"the result line should say {share}", r)


def test_link_mismatch_names_the_first_differing_offset_and_its_owner(base):
    p = link_project(base, flip=TID)
    before = ticket_texts(p)
    r = p.run("link")
    expect(r.returncode not in (0, ENV_EXIT) and "link: mismatch" in r.stdout, "a mismatch should exit nonzero", r)
    expect(f"first difference at file offset 0x405: unit {UNIT} function {TID}" in r.stdout, "it names the owner", r)
    expect(ticket_texts(p) == before, "no ticket status changes", r)
    expect([e["result"] for e in link_events(p)] == ["mismatch"], "the event records the mismatch", r)


def test_link_appends_exactly_one_event_per_run(base):
    p = link_project(base)
    for n in (1, 2):
        r = p.run("link")
        expect(r.returncode == 0 and len(link_events(p)) == n, f"run {n} should leave {n} link events", r)
    e = link_events(p)[-1]
    expect(e["result"] == "pass" and e["units"] == [UNIT] and e["source_bytes"] == 37 and e["in_scope_bytes"] == 111,
           f"the event holds the result: {e}", r)


def test_link_output_lands_in_the_uncommitted_machine_folder(base):
    p = link_project(base)
    r = p.run("link")
    out = link_output(r)
    expect(r.returncode == 0 and out.is_file() and (p.root / ".decomp") in out.parents, f"output at {out}", r)
    expect(str(out.relative_to(p.root).as_posix()) not in p.git("status", "--porcelain", "--untracked-files=all"),
           "git never sees the output", r)


def test_link_stops_on_the_environment_before_the_adapter_runs(base):
    p = link_project(base)
    r = p.run("link", env={"DECOMP_TARGET": str(p.root / "DECOMP.md")})
    expect(r.returncode == ENV_EXIT and "ENVIRONMENT" in r.stderr, "a wrong target exits 6", r)
    expect(not (p.root / ".decomp" / "link").exists() and not link_events(p), "nothing ran or was recorded", r)


def test_link_without_a_link_adapter_says_so(base):
    r = link_project(base, config={"link": ""}).run("link")
    expect(r.returncode not in (0, ENV_EXIT) and "no link adapter" in r.stderr, "the message names the gap", r)


def test_link_marked_unavailable_exits_with_its_own_code_and_reason(base):
    why = "the header checksum covers the whole file and the linker cannot reproduce it"
    p = link_project(base, config={"link_unavailable": why})
    r = p.run("link")
    expect(r.returncode == 7 and why in r.stderr, "the contract's reason, with exit 7", r)
    expect(not (p.root / ".decomp" / "link").exists() and not link_events(p), "nothing ran or was recorded", r)


# ---- link milestones ----

def milestone_project(base, sizes, statuses=("integrated", "integrated", "open"), config=None):
    """A link project whose three tickets have the given sizes (bytes, in ticket order)."""
    p = link_project(base, statuses=statuses, config=config)
    for tid, size in zip((TID, TID2, TID3), sizes):
        t = next((p.root / "tickets").glob(f"*/{tid}.md"))
        t.write_text(t.read_text().replace("size: 37", f"size: {size}"))
    p.git("commit", "-aq", "--allow-empty", "-m", "sizes")
    return p


def milestone_of(p):
    r = p.run("report")
    lines = [l for l in r.stdout.splitlines() if l.startswith("milestone:")]
    expect(r.returncode == 0 and len(lines) == 1, "report should print exactly one milestone line", r)
    return lines[0].split(":", 1)[1].strip()


def test_milestone_is_due_at_five_percent_of_in_scope_bytes(base):
    for d, (sizes, due) in each(base, [((29999, 285001, 285000), False), ((30000, 285000, 285000), True)]):
        got = milestone_of(milestone_project(d, sizes, statuses=("integrated", "open", "open")))
        expect(got.startswith("due") == due and "of 30000 B" in got, f"{sizes}: want due={due} of 30000 B, got {got}")


def test_milestone_floor_is_16_kb_on_a_small_project(base):
    for d, (size, due) in each(base, [(16383, False), (16384, True)]):
        got = milestone_of(milestone_project(d, (size, 37, 37), statuses=("integrated", "open", "open")))
        expect(got.startswith("due") == due and "of 16384 B" in got, f"{size}: want due={due} of 16384 B, got {got}")


def test_milestone_honours_a_percentage_override(base):
    for d, (statuses, due) in each(base, [(("integrated", "open", "open"), False), (("open", "integrated", "integrated"), True)]):
        got = milestone_of(milestone_project(d, (37, 37, 37), statuses, {"link_milestone": "50%"}))
        expect(got.startswith("due") == due and "of 56 B" in got, f"{statuses}: want due={due} of 56 B, got {got}")


def test_milestone_honours_a_byte_count_override(base):
    for d, (size, due) in each(base, [(37, True), (36, False)]):
        got = milestone_of(milestone_project(d, (size, 37, 37), statuses=("integrated", "open", "open"),
                                             config={"link_milestone": 37}))
        expect(got.startswith("due") == due and "of 37 B" in got, f"{size}: want due={due} of 37 B, got {got}")


def test_milestone_is_not_due_after_a_link_until_new_units_complete(base):
    p = milestone_project(base, (37, 37, 37), config={"link_milestone": 10})
    expect(milestone_of(p).startswith("due"), "the finished unit is due before any link")
    r = p.run("link")
    expect(r.returncode == 0, "the link should pass", r)
    expect(milestone_of(p).startswith("not due"), "a recorded link clears the milestone")
    t = p.root / "tickets" / "u0002" / f"{TID3}.md"
    t.write_text(t.read_text().replace("status: open", "status: integrated"))
    p.git("commit", "-aq", "-m", "complete u0002")
    expect(milestone_of(p).startswith("due"), "a newly completed unit makes it due again")


def test_milestone_is_never_due_when_the_link_is_unavailable(base):
    p = milestone_project(base, (37, 37, 37), config={"link_milestone": 10, "link_unavailable": "no linker can do it"})
    got = milestone_of(p)
    expect(got.startswith("not due") and "unavailable" in got, f"unavailable means never due, got {got}")


def test_verify_checks_the_environment_before_recording(base):
    p = Project(base, status="claimed")
    p.branch(f"w/{TID}", {SOURCE: CLEAN + "/* w */\n"})
    r = p.run("verify", TID, "--model", "m", env={"DECOMP_TARGET": str(p.root / "DECOMP.md")})
    expect(r.returncode == ENV_EXIT and not (p.root / "ledger").exists(), "verify should exit 6, recording nothing", r)


# ---------- lifecycle commands: audit, integrate, release, note, similar, lock ----------

def test_scenario_reaches_each_late_status_through_the_cli(base):
    for d, to in each(base, ["claimed", "bytes-match", "matched", "integrated"]):
        Project(d).advance(to)


def test_audit_pass_records_the_match_once_even_when_run_twice(base):
    p = Project(base)
    p.advance("matched")
    r = p.run("audit", TID, "pass", "--auditor", "a1")
    expect(r.returncode != 0 and "audit-pass needs bytes-match" in r.stderr, "a second pass on a matched ticket is refused", r)
    expect(len(p.lines("matches.jsonl")) == 1, "one match record", r)
    expect(p.status() == "matched", "still matched", r)


def test_audit_pass_is_refused_with_exit_2_when_the_branch_changed_since_verify(base):
    p = Project(base)
    p.advance("bytes-match")
    p.git("checkout", "-q", f"w/{TID}")
    p.write(SOURCE, CLEAN + "/* changed after verify */\n")
    p.git("add", SOURCE)
    p.git("commit", "-q", "-m", "late edit")
    p.git("checkout", "-q", "main")
    r = p.run("audit", TID, "pass", "--auditor", "a1")
    expect(r.returncode == 2 and "branch changed since verify" in r.stderr, "audit pass should exit 2", r)
    expect(p.status() == "bytes-match" and not p.lines("matches.jsonl"), "nothing should be recorded", r)


def test_audit_fail_appends_an_attempt_returns_to_claimed_and_notes(base):
    p = Project(base)
    p.advance("bytes-match")
    r = p.run("audit", TID, "fail", "--auditor", "a1", "--note", "uses a banned trick")
    expect(r.returncode == 0 and "back to claimed" in r.stdout, "audit fail should pass", r)
    ids = [a["id"] for a in p.lines("attempts.jsonl")]
    expect(ids == [f"{TID}-a001", f"{TID}-a002"], f"the next attempt id follows verify's, got {ids}", r)
    expect(p.status() == "claimed", "the ticket returns to claimed", r)
    notes = (p.root / f"tickets/{UNIT}/{TID}.md").read_text()
    expect("audit-fail: uses a banned trick" in notes, "a note is appended", r)
    r = p.run("verify", TID, "--model", "m")
    expect(f"{TID}-a003" in r.stdout, "the next verify numbers after the failed audit", r)


def test_audit_is_refused_unless_the_ticket_is_bytes_match(base):
    p = Project(base)
    p.advance("claimed")
    r = p.run("audit", TID, "pass", "--auditor", "a1")
    expect(r.returncode == 1 and f"{TID} is claimed; audit-pass needs bytes-match" in r.stderr, "audit refuses", r)


def test_integrate_is_refused_when_the_branch_is_not_merged(base):
    p = Project(base)
    p.advance("matched")
    r = p.run("integrate", TID)
    expect(r.returncode == 1 and "is not merged into main" in r.stderr, "integrate refuses an unmerged branch", r)
    expect(p.status() == "matched" and p.lock_file(f"unit-{UNIT}").exists(), "ticket and lock are unchanged", r)
    expect(not events(p), "no event is recorded", r)


def test_integrate_releases_the_unit_lock_and_records_the_event(base):
    p = Project(base)
    p.advance("matched")
    expect(p.lock_file(f"unit-{UNIT}").exists(), "the claim holds the unit lock")
    p.git("merge", "-q", "--no-edit", f"w/{TID}")
    r = p.run("integrate", TID)
    expect(r.returncode == 0 and f"integrated {TID}" in r.stdout, "integrate passes once merged", r)
    expect(p.status() == "integrated", "the ticket is integrated", r)
    expect(not p.lock_file(f"unit-{UNIT}").exists(), "the unit lock is released", r)
    got = [(e["ticket"], e["event"]) for e in events(p)]
    expect(got == [(TID, "integrated")], f"one integrated event, got {got}", r)


def test_integrate_is_refused_unless_the_ticket_is_matched(base):
    p = Project(base)
    p.advance("bytes-match")
    r = p.run("integrate", TID)
    expect(r.returncode == 1 and f"{TID} is bytes-match; integrate needs matched" in r.stderr, "integrate refuses", r)


def test_release_moves_claimed_to_open_and_frees_the_lock(base):
    p = Project(base)
    p.advance("claimed")
    r = p.run("release", TID)
    expect(r.returncode == 0 and f"{TID} -> open" in r.stdout, "release to open", r)
    expect(p.status() == "open" and not p.lock_file(f"unit-{UNIT}").exists(), "open and unlocked", r)


def test_release_moves_claimed_to_blocked_reference_and_blocked_back_to_open(base):
    p = Project(base)
    p.advance("claimed")
    r = p.run("release", TID, "--to", "blocked-reference")
    expect(r.returncode == 0 and f"{TID} -> blocked-reference" in r.stdout, "release to blocked-reference", r)
    expect(p.status() == "blocked-reference" and not p.lock_file(f"unit-{UNIT}").exists(), "blocked and unlocked", r)
    r = p.run("release", TID)
    expect(r.returncode == 0 and f"{TID} -> open" in r.stdout and p.status() == "open", "blocked back to open", r)


def test_release_is_refused_from_any_other_status(base):
    for d, status in each(base, ["open", "bytes-match", "matched", "integrated", "regressed", "revalidated"]):
        p = Project(d, status=status)
        r = p.run("release", TID)
        expect(r.returncode == 1 and f"{TID} is {status}; release needs claimed" in r.stderr, f"{status}: release refuses", r)
        expect(p.status() == status, f"{status}: the ticket does not change", r)


def test_release_refuses_an_unknown_target(base):
    p = Project(base, status="claimed")
    r = p.run("release", TID, "--to", "matched")
    expect(r.returncode == 1 and "release --to open|blocked-reference" in r.stderr, "release names its targets", r)


def test_each_command_refuses_an_illegal_move_with_the_shared_message(base):
    cases = [("matched", ["claim", TID, "--by", "w2"], "claim needs open or regressed"),
             ("open", ["verify", TID, "--model", "m"], "bytes-match needs claimed"),
             ("claimed", ["audit", TID, "pass", "--auditor", "a1"], "audit-pass needs bytes-match"),
             ("claimed", ["audit", TID, "fail", "--auditor", "a1"], "audit-fail needs bytes-match"),
             ("bytes-match", ["integrate", TID], "integrate needs matched"),
             ("open", ["release", TID], "release needs claimed"),
             ("open", ["release", TID, "--to", "blocked-reference"], "block needs claimed")]
    for d, (status, args, needs) in each(base, cases):
        p = Project(d, status=status)
        r = p.run(*args)
        expect(r.returncode == 1 and f"{TID} is {status}; {needs}" in r.stderr, f"{args[0]} refuses {status}", r)
        expect(p.status() == status, f"{args[0]}: the ticket does not change", r)


def test_every_move_that_leaves_the_claim_frees_the_unit_for_another_ticket(base):
    other = f"{UNIT}-00402000"
    broken = {SOURCE: MARK + "int f(void) { return 2; }\n"}
    for d, leave in each(base, ["release", "block", "integrate", "regress"]):
        p = Project(d)
        p.advance("matched" if leave in ("integrate", "regress") else "claimed")
        p.write(f"tickets/{UNIT}/{other}.md", ticket_text(other, "0x00402000", SOURCE, "open"))
        if leave == "release":
            r = p.run("release", TID)
        elif leave == "block":
            r = p.run("release", TID, "--to", "blocked-reference")
        elif leave == "integrate":
            p.git("merge", "-q", "--no-edit", f"w/{TID}")
            r = p.run("integrate", TID)
        else:
            for rel, text in broken.items():
                p.write(rel, text)
            p.git("commit", "-aq", "-m", "break the match")
            r = p.run("revalidate")
            expect(r.returncode == 5 and "REGRESSED" in r.stdout, "the match regresses", r)
        expect(leave == "regress" or r.returncode == 0, f"{leave} passes", r)
        r = p.run("claim", other, "--by", "w2")
        expect(r.returncode == 0 and f"claimed {other}" in r.stdout, f"after {leave} the unit is free", r)


def test_note_appends_a_line_under_notes(base):
    p = Project(base)
    r = p.run("note", TID, "tried", "a", "loop")
    expect(r.returncode == 0, "note passes", r)
    text = (p.root / f"tickets/{UNIT}/{TID}.md").read_text()
    expect(text.rstrip().endswith("tried a loop") and "## Notes" in text, "the note lands under Notes", r)
    expect(p.status() == "open", "the status is unchanged", r)


def test_similar_ranks_matched_tickets_by_their_expected_bytes(base):
    other, third = "u0002-00402000", "u0003-00403000"
    files = {"expected/00401000.bin": "abcdefgh\n", "expected/00402000.bin": "abcdefgx\n",
             "expected/00403000.bin": "zzzzzzzz\n", "src/u0002.c": "x\n", "src/u0003.c": "x\n",
             f"tickets/u0002/{other}.md": ticket_text(other, "0x00402000", "src/u0002.c", "integrated"),
             f"tickets/u0003/{third}.md": ticket_text(third, "0x00403000", "src/u0003.c", "integrated")}
    p = Project(base, files=files)
    r = p.run("similar", TID, "--n", "2")
    rows = r.stdout.splitlines()
    got = [l.split()[1] for l in rows]
    expect(r.returncode == 0 and got == [other, third], f"closest first, got {got}", r)
    expect(float(rows[0].split()[0]) > float(rows[1].split()[0]), "scores fall", r)


def test_similar_ignores_tickets_that_are_not_matched(base):
    other = "u0002-00402000"
    files = {"expected/00401000.bin": "abcdefgh\n", "expected/00402000.bin": "abcdefgh\n", "src/u0002.c": "x\n",
             f"tickets/u0002/{other}.md": ticket_text(other, "0x00402000", "src/u0002.c", "open")}
    r = Project(base, files=files).run("similar", TID)
    expect(r.returncode == 0 and r.stdout.strip() == "", "an open ticket is never a model", r)


def test_lock_refuses_a_held_lock_with_exit_3_and_unlock_frees_it(base):
    p = Project(base)
    r = p.run("lock", "gen", "--by", "w1")
    expect(r.returncode == 0 and "locked gen" in r.stdout and p.lock_file("gen").exists(), "lock takes", r)
    r = p.run("lock", "gen", "--by", "w2")
    expect(r.returncode == 3 and "locked: gen: w1" in r.stderr, "a held lock exits 3 and names its holder", r)
    r = p.run("unlock", "gen")
    expect(r.returncode == 0 and "unlocked gen" in r.stdout and not p.lock_file("gen").exists(), "unlock frees it", r)
    r = p.run("lock", "gen", "--by", "w2")
    expect(r.returncode == 0, "the lock can be taken again", r)
    r = p.run("unlock", "never-held")
    expect(r.returncode == 0, "unlocking a free lock is not an error", r)


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
        base = tempfile.mkdtemp(prefix="decomp-test-")
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
