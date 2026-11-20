#!/usr/bin/env python3
"""Tests of the decomp project tool at its one seam: the command line.

Each case builds a scratch git project (a copy of decomp.py, a toolchain.json,
a decomp.json whose adapters are small `python -c` commands, a fake target, and
fake tools that only print a banner), runs decomp.py commands in it, and asserts
on exit codes and output. No real compiler, no network. Standard library only.

Run: python scripts/test-decomp.py [--list] [filter ...]

A full run takes minutes, longer than the default 120-second tool timeout, so run
it in the background. While iterating, pass filters to run only the cases they
select: a filter that is a full case name selects that case alone, and any other
filter selects the cases whose names hold it as a run of whole words (split at
underscores), for example: python scripts/test-decomp.py verify search_picks.
A filter that selects nothing exits 2, a module-level name bound twice exits 3,
and --list prints the selected names without running them.

Each case receives its scratch folder in resolved (long) form. A Windows temp folder
can be given in short form (8.3 names), and the tool prints the long form, so a path
a case builds from a short-form folder would not equal the path the tool prints for
the same file.
"""
import ast
import hashlib
import itertools
import json
import math
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import time
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
        cfg = {"integration_branch": "main", "build": BUILD, "diff": DIFF, "pragma_allow": [], "banned": [],
               "template_search": True, "fakematch": "forbidden"}
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
        self.write(".decomp/local.json", json.dumps({"target": str(self.target), "search": {"background": 0}}))
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
        return {k: int(v) for k, v in (c.split() for c in report_line(r, "status:").split(","))}

    def claims(self):
        """Claimants as the tool reports them: {ticket id: claimant} from the `claims:` line of `report`."""
        made = not (self.root / "inventory.json").exists()
        had_open = (self.root / "OPEN.md").exists()
        if made:
            self.write("inventory.json", '{"units": [], "functions": []}\n')
        try:
            r = self.run("report", tool=TOOL)
        finally:
            if made:
                (self.root / "inventory.json").unlink()
            if not had_open:
                (self.root / "OPEN.md").unlink(missing_ok=True)
        body = report_line(r, "claims:").strip()
        return {} if body == "none" else dict(c.split() for c in body.split(", "))

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


def report_line(r, prefix):
    """What follows `prefix` on the one line of `report` output that starts with it. Fails unless there is exactly one."""
    line = [l for l in r.stdout.splitlines() if l.startswith(prefix)]
    expect(r.returncode == 0 and len(line) == 1, f"report should print exactly one {prefix} line", r)
    return line[0][len(prefix):]


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

def sub(base, name):
    """A fresh folder under base, for a test that builds more than one project."""
    d = Path(base) / name
    d.mkdir()
    return d


def test_doctor_reports_the_template_search_and_fakematch_rules(base):
    r = Project(base, config={"template_search": False, "fakematch": "allowed"}).run("doctor")
    expect(r.returncode == 0 and "template search: not allowed" in r.stdout and "fakematch: allowed" in r.stdout,
           "doctor should print both rules from decomp.json", r)
    r = Project(sub(base, "b"), config={"template_search": True, "fakematch": "forbidden"}).run("doctor")
    expect(r.returncode == 0 and "template search: allowed" in r.stdout and "fakematch: forbidden" in r.stdout,
           "doctor should print the other values too", r)


def test_doctor_names_the_upgrade_when_the_rule_keys_are_missing(base):
    p = Project(base)
    cfg = json.loads((p.root / "decomp.json").read_text())
    del cfg["template_search"], cfg["fakematch"]
    (p.root / "decomp.json").write_text(json.dumps(cfg))
    r = p.run("doctor")
    expect(r.returncode == 1 and "template_search" in r.stderr and "fakematch" in r.stderr
           and "skill-upgrade" in r.stderr and "doctor: ok" not in r.stdout, "doctor should name the upgrade step", r)


def test_upgrade_maps_an_old_permuter_line_to_template_search(base):
    for line, want in (("Permuter: allowed", True), ("Permuter: not allowed", False),
                       ("Permuter: allowed, and its output is fakematch-governed.", True)):
        p = Project(sub(base, str(len(line))))
        p.write("DECOMP.md", f"# contract\n- Fakematch rule: `forbidden`\n- {line}\n")
        r = p.run("contract-keys")
        expect(r.returncode == 0 and json.loads(r.stdout) == {"template_search": want, "fakematch": "forbidden"},
               f"{line!r} should read as template_search {want}", r)
    p = Project(sub(base, "n"))
    p.write("DECOMP.md", "# contract\n- Fakematch rule: allowed with a fakematch: comment (ADR)\n"
                         "- Template search: not allowed\n- Permuter: allowed\n")
    r = p.run("contract-keys")
    expect(json.loads(r.stdout) == {"template_search": False, "fakematch": "allowed"},
           "a template-search line wins over a permuter line", r)


def test_upgrade_reads_contract_bullets_through_markdown_emphasis(base):
    want = {"template_search": False, "fakematch": "allowed"}
    contracts = (
        ("bold, colon inside", "- **Fakematch rule:** allowed, with a note\n- **Permuter:** not allowed (ADR 0003).\n"),
        ("bold, colon outside", "- **Fakematch rule**: allowed\n- **Template search**: not allowed\n"),
        ("italic asterisk", "- *Fakematch rule:* allowed\n- *Template search*: not allowed\n"),
        ("italic underscore", "- _Fakematch rule:_ allowed\n- _Permuter_: not allowed\n"),
        ("backtick name", "- `Fakematch rule`: allowed\n- `Template search:` not allowed\n"),
        ("backtick value", "- **Fakematch rule:** `allowed`\n- **Template search:** `not allowed`\n"),
        ("emphasised value", "* **Fakematch rule:** **allowed**\n* __Template search:__ _not allowed_\n"),
        ("plain", "- Fakematch rule: allowed\n- Template search: not allowed\n"),
    )
    for i, (name, bullets) in enumerate(contracts):
        p = Project(sub(base, f"c{i}"))
        p.write("DECOMP.md", "# contract\n" + bullets)
        r = p.run("contract-keys")
        expect(r.returncode == 0 and json.loads(r.stdout) == want, f"a contract with {name} bullets should read", r)
    p = Project(sub(base, "on"))
    p.write("DECOMP.md", "# contract\n- **Fakematch rule:** forbidden\n- **Template search:** allowed\n")
    r = p.run("contract-keys")
    expect(r.returncode == 0 and json.loads(r.stdout) == {"template_search": True, "fakematch": "forbidden"},
           "bold bullets should give the other values too", r)
    p = Project(sub(base, "unclear"))
    p.write("DECOMP.md", "# contract\n- **Fakematch rule:** allowed\n- **Template search:** see the ADR\n")
    r = p.run("contract-keys")
    expect(r.returncode == 1 and "missing or unclear" in r.stderr and not r.stdout.strip(),
           "a line that says neither should still stop", r)


def test_doctor_reports_the_rules_of_a_project_upgraded_from_a_bold_contract(base):
    p = Project(base)
    cfg = json.loads((p.root / "decomp.json").read_text())
    del cfg["template_search"], cfg["fakematch"]
    (p.root / "decomp.json").write_text(json.dumps(cfg))
    p.write("DECOMP.md", "# contract\n- **Fakematch rule:** allowed, with a note\n- **Permuter:** not allowed (ADR 0003).\n")
    r = p.run("contract-keys")
    expect(r.returncode == 0, "the upgrade should read a bold-bullet contract", r)
    cfg.update(json.loads(r.stdout))
    (p.root / "decomp.json").write_text(json.dumps(cfg))
    r = p.run("doctor")
    expect(r.returncode == 0 and "template search: not allowed" in r.stdout and "fakematch: allowed" in r.stdout,
           "doctor should print the rules the upgrade wrote", r)


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


def test_tickets_and_patterns_for_a_64_bit_target(base):
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


def test_keyed_and_bank_addressed_functions_get_their_own_tickets(base):
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


def test_verify_refuses_an_unknown_category_and_takes_none(base):
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


def test_repair_ref_may_not_touch_a_frozen_path_and_only_a_candidate_may(base):
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


def test_revalidate_stops_before_measuring_any_unit_when_a_later_units_compiler_is_missing(base):
    p = Project(base, status="integrated", files=second_ticket(),
                config={"compiler": "compiler", "unit_compilers": {"u0002": "ghost"}})
    r = p.run("revalidate")
    expect(r.returncode == ENV_EXIT and "ghost" in r.stderr, "exit 6 on the missing compiler", r)
    expect("revalidated" not in r.stdout and not (p.root / "ledger").exists(), "no unit is measured or recorded", r)
    expect(p.statuses() == {"integrated": 2}, "no status should change", r)


def test_check_and_verify_stop_on_the_edition_after_a_cached_doctor(base):
    p = Project(base, manifest=editions_manifest(), target=STORE, status="claimed")
    p.branch(f"w/{TID}", {SOURCE: CLEAN + "/* w */\n"})
    r = p.run("doctor")
    expect(r.returncode == 0, "doctor should pass and cache its check", r)
    for args in (("check", TID), ("verify", TID, "--model", "m")):
        r = p.run(*args)
        expect(r.returncode == ENV_EXIT and "store re-release" in r.stderr, f"{args[0]} should exit 6 on the edition", r)
    expect(not (p.root / "ledger").exists() and p.status() == "claimed", "nothing should be recorded", r)


def test_verify_refuses_before_the_edition_check(base):
    for d, (status, extra, word) in each(base, [("open", [], "bytes-match needs claimed"),
                                                ("claimed", ["--category", "bogus"], "unknown category")]):
        p = Project(d, manifest=editions_manifest(), target=STORE, status=status)
        p.branch(f"w/{TID}", {SOURCE: CLEAN + "/* w */\n"})
        r = p.run("verify", TID, "--model", "m", *extra)
        expect(r.returncode == 1 and word in r.stderr, f"verify refuses with exit 1 ({word})", r)
        expect(not (p.root / "ledger").exists() and p.status() == status, "nothing is recorded", r)


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
    """The state word `report` prints on its state line."""
    r = p.run("report")
    return report_line(r, "state:").split()[0]


def test_report_states_more_when_a_ticket_is_ready(base):
    p = started_project(base, status="integrated", files=second_ticket(status="open"))
    expect(state_of(p) == "more", "a ready ticket means more", p.run("report"))


def test_report_states_stuck_when_the_rest_are_blocked_or_regressed(base):
    p = started_project(base, status="regressed", files=second_ticket(status="blocked-reference"))
    expect(state_of(p) == "stuck", "nothing ready means stuck", p.run("report"))


def test_report_states_finished_when_every_ticket_is_revalidated(base):
    p = started_project(base, status="revalidated", files=second_ticket(status="revalidated"))
    expect(state_of(p) == "finished", "all revalidated means finished", p.run("report"))


def test_report_does_not_state_finished_for_integrated_tickets(base):
    p = started_project(base, status="revalidated", files=second_ticket(status="integrated"))
    expect(state_of(p) == "more", "integrated, not revalidated, is not finished", p.run("report"))


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
    return report_line(r, "milestone:").strip()


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


def test_second_audit_pass_on_a_matched_ticket_is_refused_and_keeps_one_record(base):
    p = Project(base)
    p.advance("matched")
    r = p.run("audit", TID, "pass", "--auditor", "a1")
    expect(r.returncode != 0 and "audit-pass needs bytes-match" in r.stderr, "a second pass on a matched ticket is refused", r)
    expect(len(p.lines("matches.jsonl")) == 1, "one match record", r)
    expect(p.status() == "matched", "still matched", r)


def test_audit_pass_after_regress_and_reclaim_still_has_one_match_record(base):
    p = Project(base)
    p.advance("matched")
    p.write(SOURCE, MARK + "int f(void) { return 2; }\n")
    p.git("commit", "-aq", "-m", "break the match")
    r = p.run("revalidate")
    expect(r.returncode == 5 and "REGRESSED" in r.stdout, "the match regresses", r)
    expect(p.status() == "regressed", "regressed", r)
    r = p.run("claim", TID, "--by", "w1")
    expect(r.returncode == 0, "the regressed ticket is claimed again", r)
    r = p.run("verify", TID, "--model", "m")
    expect(r.returncode == 0, "verify reaches bytes-match again", r)
    r = p.run("audit", TID, "pass", "--auditor", "a1")
    expect(r.returncode == 0 and "matched" in r.stdout, "the second audit pass succeeds", r)
    expect(p.status() == "matched", "matched again", r)
    expect(len(p.lines("matches.jsonl")) == 1, "still one match record", r)


def test_audit_pass_leaves_bytes_match_when_the_match_record_cannot_be_written(base):
    p = Project(base)
    p.advance("bytes-match")
    (p.root / "ledger").mkdir(exist_ok=True)
    (p.root / "ledger" / "matches.jsonl").mkdir()  # a directory: neither read nor append can work
    r = p.run("audit", TID, "pass", "--auditor", "a1")
    expect(r.returncode != 0, "audit pass fails when the record cannot be written", r)
    (p.root / "ledger" / "matches.jsonl").rmdir()  # so `report` can read the ledger again
    expect(p.status() == "bytes-match", "the ticket stays bytes-match", r)


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


def test_audit_fail_whose_attempt_cannot_be_recorded_leaves_the_ticket_at_bytes_match(base):
    p = Project(base)
    p.advance("bytes-match")
    ticket = p.root / f"tickets/{UNIT}/{TID}.md"
    before = ticket.read_bytes()
    ledger = p.root / "ledger" / "attempts.jsonl"
    os.chmod(ledger, stat.S_IREAD)
    try:
        r = p.run("audit", TID, "fail", "--auditor", "a1")
    finally:
        os.chmod(ledger, stat.S_IREAD | stat.S_IWRITE)
    expect(r.returncode != 0, "an unwritable attempt record should fail the audit", r)
    expect(ticket.read_bytes() == before, "the ticket should be byte for byte as it was", r)
    expect(p.status() == "bytes-match", "the ticket stays at bytes-match", r)


def test_regressing_an_integrated_or_revalidated_ticket_leaves_its_claimant_fields_alone(base):
    for d, status in each(base, ["integrated", "revalidated"]):
        p = Project(d)
        p.advance("integrated")
        if status == "revalidated":
            r = p.run("revalidate")
            expect(r.returncode == 0 and p.status() == "revalidated", "the match revalidates", r)
        ticket = p.root / f"tickets/{UNIT}/{TID}.md"
        claimant = lambda: [l for l in ticket.read_text().splitlines() if l.startswith(("claimed_by", "claimed_at"))]
        before = claimant()
        expect(len(before) == 2 and p.claims() == {}, f"a {status} ticket names no claimant", p.claims())
        p.write(SOURCE, MARK + "int f(void) { return 2; }\n")
        p.git("commit", "-aq", "-m", "break the match")
        r = p.run("revalidate")
        expect(r.returncode == 5 and p.status() == "regressed", f"the {status} ticket regresses", r)
        expect(claimant() == before, f"regressing a {status} ticket leaves its claimant fields unchanged", r)
        expect(p.claims() == {}, f"the {status} ticket adds no claims line", p.claims())


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
             ("open", ["release", TID], "release needs claimed or blocked-reference"),
             ("open", ["release", TID, "--to", "blocked-reference"], "release needs claimed")]
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


def test_a_regressed_ticket_shows_no_claimant(base):
    p = Project(base)
    p.advance("matched")
    expect(p.claims() == {TID: "w1"}, "the matched ticket still names its claimant", p.claims())
    p.write(SOURCE, MARK + "int f(void) { return 2; }\n")
    p.git("commit", "-aq", "-m", "break the match")
    r = p.run("revalidate")
    expect(r.returncode == 5 and p.status() == "regressed", "the match regresses", r)
    expect(p.claims() == {}, "a regressed ticket names no claimant", p.claims())


def test_report_lists_each_claim_and_its_claimant(base):
    for to in ("open", "claimed", "bytes-match", "matched", "integrated"):
        (Path(base) / to).mkdir()
        p = Project(Path(base) / to)
        if to != "open":
            p.advance(to)
        want = {TID: "w1"} if to in ("claimed", "bytes-match", "matched") else {}
        expect(p.claims() == want, f"a {to} ticket's claimants", p.claims())


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


# ---------- template search ----------

# The fake compiler for `search` copies the candidate into the object with every header it includes
# beside itself, and fails when one is missing or the candidate holds SYNTAX_ERROR. The fake diff
# scores 2 bytes per WRONG in the object and writes a long report that holds no source.
SEARCH_BUILD_PY = """import os, re, sys
src, obj = sys.argv[1], sys.argv[2]
text = open(src).read()
out = [text]
for name in re.findall(r'#include "([^"]+)"', text):
    beside = os.path.join(os.path.dirname(src), name)
    if not os.path.exists(beside):
        sys.exit("cannot open include file: " + name)
    out.append(open(beside).read())
if "SYNTAX_ERROR" in text:
    sys.exit("error C2143: syntax error")
open(obj, "w").write(chr(10).join(out))
"""
SEARCH_DIFF_PY = """import json, sys
n = open(sys.argv[1]).read().count("WRONG")
open(sys.argv[2], "w").write("".join("%04d mov eax, %s%s" % (i, "x" * 300, chr(10)) for i in range(400)))
print(json.dumps({"match": n == 0, "differ_bytes": 2 * n}))
"""
SEARCH_CONFIG = {"build": PY + ' "{tools}/search_build.py" "{source}" "{obj}"',
                 "diff": PY + ' "{tools}/search_diff.py" "{obj}" "{report}"'}
SEARCH_FILES = {"tools/search_build.py": SEARCH_BUILD_PY, "tools/search_diff.py": SEARCH_DIFF_PY}
STUCK = MARK + "int f(void) { int WRONG_now; return 1; }\n"  # the unit as the writer left it
MATCHING = MARK + ("int f(void) { PERM_GENERAL(int WRONG_a;, int right_a;) "
                   "PERM_GENERAL(int WRONG_b;, int WRONG_c; int WRONG_d;, int right_b;) return 1; }\n")
NEVER = MARK + ("int f(void) { PERM_GENERAL(int WRONG_a; int WRONG_b;, int WRONG_c;) "
                "PERM_GENERAL(int WRONG_d;, int WRONG_e; int WRONG_f; int WRONG_g;) return 1; }\n")


def search_project(base, gate="register-allocation", **kw):
    """A project with the search fakes. A `check` with the category `gate` opens template search; None runs none."""
    kw["config"] = dict(SEARCH_CONFIG, **kw.get("config", {}))
    kw["files"] = dict(SEARCH_FILES, **kw.get("files", {}))
    kw.setdefault("source", STUCK)
    p = Project(base, **kw)
    if gate:
        p.run("check", TID, "--category", gate)
    return p


def search(p, template, *more):
    """Run `search` on a template kept outside the tree. Returns (process, parsed summary or None)."""
    path = p.base / "template.c"
    path.write_text(template, encoding="utf-8")
    r = p.run("search", TID, str(path), *more)
    try:
        return r, json.loads(r.stdout.splitlines()[0])
    except (ValueError, IndexError):
        return r, None


def test_search_returns_the_matching_combination_and_a_plain_winner(base):
    p = search_project(base)
    r, out = search(p, MATCHING)
    expect(r.returncode == 0 and out is not None, "search should print a summary", r)
    expect(out["end"] == "match" and out["best"] == {"code": "A1 B2", "differ_bytes": 0},
           "the summary should name the matching choices", r)
    winner = Path(out["winner"])
    expect(p.root.resolve() not in winner.resolve().parents, "the winner is written outside the tree", r)
    expect(winner.read_text() == MARK + "int f(void) { int right_a; int right_b; return 1; }\n",
           f"the winner should be plain C: {winner.read_text()!r}", r)


def test_search_without_a_match_returns_the_closest_candidate_as_exhausted(base):
    r, out = search(search_project(base), NEVER)
    expect(r.returncode == 0 and out is not None, "search should print a summary", r)
    expect(out["end"] == "exhausted" and out["best"] == {"code": "A1 B0", "differ_bytes": 4},
           "the summary should name the candidate with the fewest differing bytes", r)
    expect({k: out["counts"][k] for k in ("space", "compiled", "build_fail", "guardrail")}
           == {"space": 4, "compiled": 4, "build_fail": 0, "guardrail": 0}, "every candidate is built", r)
    expect("winner" not in out, "a round without a match writes no winner", r)


def test_search_is_refused_when_the_contract_disallows_template_search(base):
    r, out = search(search_project(base, config={"template_search": False}), MATCHING)
    expect(r.returncode == 1 and out is None, "search should be refused", r)
    expect("does not allow template search" in r.stderr, "the refusal should give the reason", r)


def test_search_exits_6_when_the_doctor_checks_fail(base):
    r, out = search(search_project(base, installed=()), MATCHING)
    expect(r.returncode == ENV_EXIT and out is None and "ENVIRONMENT" in r.stderr, "search should exit 6", r)


def test_search_candidate_builds_with_a_header_beside_the_unit(base):
    p = search_project(base, files={"src/local.h": "/* beside the unit */\n"})
    r, out = search(p, '#include "local.h"\n' + MATCHING)
    expect(out is not None and out["end"] == "match" and out["counts"]["build_fail"] == 0,
           "the include beside the unit should resolve for each candidate", r)


def test_search_summary_stays_under_the_cap_and_holds_no_source(base):
    r, out = search(search_project(base), NEVER)
    expect(out is not None and len(r.stdout) <= 600 * 4, f"the summary is {len(r.stdout)} characters", r)
    expect(out["window"] and out["window"][0].startswith("0000 mov eax"), "the summary shows the report's first lines", r)
    expect("WRONG" not in r.stdout and "int f" not in r.stdout, "the summary holds no candidate source", r)


def test_search_reports_the_build_failure_when_no_candidate_builds(base):
    r, out = search(search_project(base), MATCHING.replace("return 1;", "SYNTAX_ERROR"))
    expect(out is not None and out["end"] == "abort-buildfail" and out["best"] is None, "no candidate is the best", r)
    expect(2 <= out["counts"]["build_fail"] <= 6 and "C2143" in out["failure"], "the summary carries the compiler's error", r)


def test_search_detail_returns_one_candidates_source_and_score(base):
    p = search_project(base)
    search(p, NEVER)
    r = p.run("search", TID, "--detail", "A0 B1")
    head, _, source = r.stdout.partition("\n")
    expect(r.returncode == 0 and json.loads(head) == {"code": "A0 B1", "result": "differ", "differ_bytes": 10},
           "the detail should give the candidate's score", r)
    expect(source == MARK + "int f(void) { int WRONG_a; int WRONG_b; int WRONG_e; int WRONG_f; int WRONG_g; return 1; }\n",
           "the detail should give the candidate's source", r)
    r = p.run("search", TID, "--detail", "A0 B7")
    expect(r.returncode == 1 and "B7" in r.stderr, "a code outside the template is refused", r)


def test_search_refuses_a_macro_it_does_not_read(base):
    r, out = search(search_project(base), MATCHING + "PERM_RAND(a; b;)\n")
    expect(r.returncode == 1 and out is None and "PERM_RAND" in r.stderr and "line 3" in r.stderr,
           "the refusal should name the macro and its line", r)


ORDER_BUILD_PY = """import re, sys
text = open(sys.argv[1]).read()
open(LOG, "a").write(" ".join(re.findall(r"tag_\\w+", text)) + chr(10))
if "SYNTAX_ERROR" in text:
    sys.exit("error C2143: syntax error")
open(sys.argv[2], "w").write(text)
"""


def in_function(body):
    return MARK + "int f(void) {\n" + body + "\n}\n"


def refused(base, body, *words):
    r, out = search(search_project(sub(base, f"r{len(os.listdir(base))}")), in_function(body))
    expect(r.returncode == 1 and out is None, "the template should be refused", r)
    for w in words:
        expect(w in r.stderr, f"the refusal should name {w!r}", r)


def detail(p, body, code):
    """The source of one candidate of a template, as `search --detail` prints it."""
    search(p, in_function(body))
    r = p.run("search", TID, "--detail", code)
    expect(r.returncode == 0, "the detail should be given", r)
    return r.stdout.partition("\n")[2]


def test_search_perm_var_repeats_one_pick_at_every_reference(base):
    src = detail(search_project(base), "PERM_VAR(@t temp-type, int, short) x = 1; PERM_VAR(t) y;", "t1")
    expect("short x = 1; short y;" in src, f"the reference should repeat the pick: {src!r}")
    refused(base, "PERM_VAR(t) y;", "PERM_VAR(t)", "defines it")


PAIRED = ("PERM_VAR(@t loop-form, int WRONG_a;, int WRONG_b;, int right_c;)\n"
          "PERM_VAR(t, int WRONG_x;, int WRONG_y;, int right_z;)")


def test_search_paired_use_takes_the_alternative_at_its_definitions_index(base):
    p = search_project(base)
    r, out = search(p, in_function(PAIRED))
    expect(out is not None and out["counts"]["space"] == 3 and out["counts"]["compiled"] == 3,
           "a definition of 3 and one paired use of 3 give 3 candidates", r)
    expect(out["end"] == "match" and out["best"]["code"] == "t2", "the choice code names the definition only", r)
    for code, pair in (("t0", "int WRONG_a;\nint WRONG_x;"), ("t1", "int WRONG_b;\nint WRONG_y;"), ("t2", "int right_c;\nint right_z;")):
        r = p.run("search", TID, "--detail", code)
        expect(r.stdout.partition("\n")[2] == in_function(pair), f"{code} should hold the two alternatives of one index", r)
    src = detail(search_project(sub(base, "ref")), PAIRED + "\nPERM_VAR(t)", "t1")
    expect(src == in_function("int WRONG_b;\nint WRONG_y;\nint WRONG_b;"), f"PERM_VAR(t) still repeats the definition: {src!r}")


def test_search_paired_uses_add_nothing_to_the_12_choice_limit(base):
    twelve = "\n".join("PERM_VAR(@v%s, int WRONG_%d;, int right_%d;) PERM_VAR(v%s, int WRONG_p%d;, int right_p%d;)"
                       % (chr(97 + i), i, i, chr(97 + i), i, i) for i in range(12))
    r, out = search(search_project(base), in_function(twelve))
    expect(out is not None and out["counts"]["space"] == 2 ** 12,
           "twelve choice points, each with a paired use, are twelve choices", r)
    expect([word[:2] for word in out["best"]["code"].split()] == ["v%s" % chr(97 + i) for i in range(12)],
           "the code holds the definitions only", r)


def test_search_refuses_a_malformed_paired_use(base):
    define = "PERM_VAR(@t temp-type, int, short, long) x; "
    refused(base, define + "PERM_VAR(t, a, b)", "PERM_VAR(t, ...)", "2 alternatives", "holds 3")
    refused(base, "PERM_VAR(t, a, b) " + define, "PERM_VAR(t, ...)", "defines it")
    refused(base, define + "PERM_VAR(t, @u, a, b, c)", "paired use", "no label")
    refused(base, define + "PERM_VAR(t temp-type, a, b, c)", "paired use", "no kind")
    refused(base, define + "PERM_VAR(t, a, %0.6 b, c)", "paired use", "no likelihood")
    refused(base, define + "PERM_VAR(@t)", "PERM_VAR(t)", "PERM_VAR(t, a, b, ...)")


def test_search_paired_steering_alternative_makes_its_pick_steering(base):
    steered = in_function("PERM_VAR(@t, int WRONG_a;, int right_a;)\nPERM_VAR(t, int b;, /* steer: pin it */ int c;)")
    r, out = search(search_project(base), steered)
    expect(r.returncode == 1 and out is None and "fakematch" in r.stderr and "Nothing was built" in r.stderr,
           "a steering paired alternative is refused when fakematch is forbidden", r)
    r, out = search(search_project(sub(base, "a"), **ALLOWED), steered)
    expect(out is not None and out["end"] == "match" and out["best"]["code"] == "t1", "the steered pick matches", r)
    text = Path(out["winner"]).read_text()
    expect(text == in_function("int right_a;\nint c; /* fakematch: pin it */"),
           f"only the paired line should carry the comment: {text!r}", r)
    r, out = search(search_project(sub(base, "n"), **ALLOWED), in_function(
        "PERM_VAR(@t, int WRONG_a;, /* steer: first */ int right_a;)\nPERM_VAR(t, int b;, /* steer: second */ int c;)"))
    expect(out is not None and out["end"] == "match" and out["best"]["code"] == "t1", "the steered pick matches", r)
    text = Path(out["winner"]).read_text()
    expect(text == in_function("int right_a; /* fakematch: first */\nint c; /* fakematch: second */"),
           f"each steering line should carry its own comment: {text!r}", r)
    r, out = search(search_project(sub(base, "r"), **ALLOWED), in_function(
        "PERM_VAR(@t, int WRONG_a;, int right_a;, int fine_a;)\nPERM_VAR(t, int b;, /* steer: pin it */ int c;, int d;)"))
    expect(out is not None and out["end"] == "match" and out["best"]["code"] == "t2",
           "the natural index should win over the one a paired alternative steers", r)
    expect("fakematch" not in Path(out["winner"]).read_text(), "the natural winner holds no steering comment", r)


def test_search_perm_lineswap_tries_every_order_of_its_lines(base):
    p = search_project(base)
    r, out = search(p, in_function("  PERM_LINESWAP(\n  a;\n  b;\n  c;\n  )"))
    expect(out is not None and out["counts"]["space"] == 6, "three lines give six orders", r)
    r = p.run("search", TID, "--detail", "A0")
    expect(r.stdout.partition("\n")[2] == in_function("  \n  a;\n  b;\n  c;\n  "), "the first order is as written", r)
    r = p.run("search", TID, "--detail", "A5")
    expect("  c;\n  b;\n  a;\n" in r.stdout, "the last order reverses the lines", r)


def test_search_perm_once_offers_nothing_or_one_alternative(base):
    p = search_project(base)
    expect(detail(p, "PERM_ONCE(a_stmt;, b_stmt;)", "A0") == in_function(""), "the baseline holds nothing")
    expect("b_stmt;" in detail(p, "PERM_ONCE(a_stmt;, b_stmt;)", "A2"), "the last alternative can be picked")


def test_search_perm_int_counts_through_its_range_and_ignore_passes_through(base):
    p = search_project(base)
    src = detail(p, "PERM_IGNORE(keep_me;) n = PERM_INT(3, 5);", "A2")
    expect("keep_me; n = 5;" in src, f"PERM_INT(3, 5) offers 3 to 5: {src!r}")
    r, out = search(p, in_function("PERM_IGNORE(keep_me;) n = PERM_INT(3, 5);"))
    expect(out is not None and out["counts"]["space"] == 3, "PERM_IGNORE adds no choice point", r)


def test_search_leaves_calling_convention_keywords_alone(base):
    src = detail(search_project(base), "PERM_GENERAL(int __stdcall g(void);, int __fastcall g(void);) __cdecl __thiscall", "A1")
    expect(src == in_function("int __fastcall g(void); __cdecl __thiscall"), f"the keywords should come through: {src!r}")


def test_search_refuses_a_template_with_more_than_12_choice_points(base):
    refused(base, "\n".join("PERM_GENERAL(a, b)" for _ in range(13)), "13 choice points", "limit is 12")
    twelve = "\n".join("PERM_GENERAL(int right_%d;, int WRONG_%d;)" % (i, i) for i in range(12))
    r, out = search(search_project(sub(base, "b")), in_function(twelve))
    expect(out is not None and out["end"] == "match", "twelve choice points are allowed", r)


def test_search_refuses_a_line_swap_over_5_lines(base):
    refused(base, "PERM_LINESWAP(\na;\nb;\nc;\nd;\ne;\nf;\n)", "PERM_LINESWAP", "6 lines", "limit is 5")
    r, out = search(search_project(base), in_function("PERM_LINESWAP(\nint right_a;\nb;\nc;\nd;\ne;\n)"))
    expect(out is not None and out["end"] == "match" and out["counts"]["space"] == 120, "five lines are allowed", r)


def test_search_refuses_a_malformed_choice_point(base):
    refused(base, "PERM_GENERAL(@r mood, a, b)", "mood", "decl-order")
    refused(base, "PERM_GENERAL(@r decl-order, a, b) PERM_GENERAL(@r decl-order, a, b)", "'r' is used twice")
    refused(base, "PERM_GENERAL(a, %0 b)", "likelihood")


def test_search_names_choice_codes_by_label(base):
    r, out = search(search_project(base), in_function(
        "PERM_GENERAL(@regs decl-order, int WRONG_a;, int right_a;) "
        "PERM_GENERAL(@shape expression-shape, int WRONG_b;, int right_b;)"))
    expect(out is not None and out["best"] == {"code": "regs1 shape1", "differ_bytes": 0},
           "the summary should name each choice by its label", r)


def test_search_compiles_higher_likelihood_combinations_first(base):
    log = Path(base) / "order.log"
    p = search_project(base, files={"tools/search_build.py": ORDER_BUILD_PY.replace("LOG", repr(str(log)))})
    tune(p, workers=1)  # one worker builds in the order the candidates come
    r, out = search(p, in_function(
        "PERM_GENERAL(%0.2 tag_a0 WRONG_1, %0.5 tag_a1 WRONG_2, %0.3 tag_a2 WRONG_3) "
        "PERM_GENERAL(%0.9 tag_b0 WRONG_4, %0.1 tag_b1 WRONG_5)"))
    expect(out is not None and out["counts"]["compiled"] == 6, "the whole space is built", r)
    built = log.read_text().splitlines()[-6:]  # after the start-up builds that check the compiler repeats itself
    expect(built[0] == "tag_a0 tag_b0", f"the baseline builds first: {built}", r)
    expect(built[1:4] == ["tag_a1 tag_b0", "tag_a2 tag_b0", "tag_a0 tag_b1"],
           f"the one-change candidates should build next, most likely first: {built}", r)
    expect(built[4:] == ["tag_a1 tag_b1", "tag_a2 tag_b1"], f"the rest should build most likely first: {built}", r)


def test_search_leaves_the_unit_the_ledger_and_frozen_files_unchanged(base):
    p = search_project(base)
    for template in (MATCHING, NEVER):
        r, out = search(p, template)
        expect(out is not None, "search should run", r)
    expect((p.root / SOURCE).read_text() == STUCK, "the unit's source is as the writer left it")
    expect(not (p.root / "ledger").exists(), "search records nothing in the ledger")
    expect(p.git("status", "--porcelain") == "" and p.git("diff", "--name-only", "decomp-setup") == "",
           "nothing tracked or frozen changed, and nothing new sits in the tree")


# A fake diff that also reports `first_differ`: the offset of the first WRONG in the object.
SEARCH_FIRST_DIFF_PY = """import json, sys
text = open(sys.argv[1]).read()
n = text.count("WRONG")
open(sys.argv[2], "w").write("".join("%04d mov eax, %s" % (i, chr(10)) for i in range(400)))
out = dict(match=n == 0, differ_bytes=2 * n)
if n:
    out["first_differ"] = text.index("WRONG")
print(json.dumps(out))
"""
FIRST_CONFIG = {"diff": PY + ' "{tools}/search_diff.py" "{obj}" "{report}"'}
FIRST_FILES = {"tools/search_diff.py": SEARCH_FIRST_DIFF_PY}
SAME_BYTES = MARK + "int f(void) { PERM_GENERAL(int WRONG_a; int ok_b;, int ok_b; int WRONG_a;) return 1; }\n"


def test_search_breaks_a_tie_by_the_later_first_difference(base):
    r, out = search(search_project(base, files=FIRST_FILES), SAME_BYTES)
    expect(out is not None and out["best"] == {"code": "A1", "differ_bytes": 2},
           "of equal differ_bytes the later first difference should rank higher", r)


def test_search_window_is_centred_on_the_first_difference_with_three_lines_of_context(base):
    r, out = search(search_project(base, files=FIRST_FILES), SAME_BYTES)
    first = int(out["window"][3].split()[0])
    expect(len(out["window"]) == 7 and first > 3, "the window should hold 3 lines each side", r)
    expect([int(w.split()[0]) for w in out["window"]] == list(range(first - 3, first + 4)),
           f"the window should be consecutive report lines: {out['window']}", r)
    expect(first > 20, "the centre is the offset of the first difference, not the report's start", r)


def test_search_without_first_differ_keeps_the_first_lines_and_the_old_order(base):
    r, out = search(search_project(base), SAME_BYTES)
    expect(out is not None and out["best"] == {"code": "A0", "differ_bytes": 2},
           "with no first_differ the first of equal candidates stays the best", r)
    expect(out["window"][0].startswith("0000 mov eax"), "the window is the report's first lines", r)


# A fake diff whose report is the lines given as its third argument, a JSON list.
SEARCH_REPORT_DIFF_PY = """import json, sys
n = open(sys.argv[1]).read().count("WRONG")
open(sys.argv[2], "w").write("".join(line + chr(10) for line in json.load(open(sys.argv[3]))))
print(json.dumps({"match": n == 0, "differ_bytes": 2 * n}))
"""
EMPTY_REPORT = "holds no instruction diff"  # what the summary says of a report with nothing but its header


def report_project(base, lines):
    """A search project whose diff report holds exactly these lines."""
    return search_project(base, files={"tools/search_diff.py": SEARCH_REPORT_DIFF_PY, "tools/report.json": json.dumps(lines)},
                          config={"diff": PY + ' "{tools}/search_diff.py" "{obj}" "{report}" "{tools}/report.json"'})


def test_search_window_marks_a_cut_line_and_leaves_a_shorter_one_alone(base):
    exact, long = "0000 " + "a" * 115, "0004 " + "b" * 116
    r, out = search(report_project(base, ["0008 short", exact, long]), NEVER)
    expect(out is not None and out["window"][:2] == ["0008 short", exact],
           "a line no longer than the width is unchanged", r)
    expect(out["window"][2] == long[:116] + " ...", f"a longer line is cut inside the width and ends in the mark: {out['window']}", r)
    expect(all(len(w) <= 120 for w in out["window"]), "no window line is longer than the width", r)
    expect(EMPTY_REPORT not in r.stdout, "a report of 2 or more lines is not called empty", r)
    expect(len(r.stdout) <= 600 * 4, f"the summary is {len(r.stdout)} characters", r)


def test_search_summary_names_a_report_with_no_instruction_diff(base):
    r, out = search(report_project(base, ["f: expected 0x180001000 size 64, built size 71, " + "9" * 5000]), NEVER)
    said = [n for n in (out or {}).get("notice", []) if EMPTY_REPORT in n]
    expect(len(said) == 1 and "diff adapter" in said[0] and "\n" not in said[0],
           "the summary should say in one line that the report holds no instruction diff, and name the diff adapter", r)
    expect(len(out["window"]) == 1 and out["window"][0].endswith(" ...") and len(out["window"][0]) == 120,
           f"the one line is cut with its mark: {out['window']}", r)
    expect(len(r.stdout) <= 600 * 4, f"the summary is {len(r.stdout)} characters", r)


def test_search_summary_of_a_two_line_report_names_no_empty_report(base):
    r, out = search(report_project(base, ["f: expected size 64, built size 71", "0000 mov eax, 1"]), NEVER)
    expect(out is not None and len(out["window"]) == 2 and EMPTY_REPORT not in r.stdout,
           "a report of 2 lines is shown without the empty-report line", r)


# A steering alternative leads with /* steer: <why> */. The fake diff only counts WRONG, so these templates
# match whenever no WRONG is left: A1 steers, A2 is natural, and B1 steers where B0 is natural.
STEERED = MARK + ("int f(void) { PERM_GENERAL(int WRONG_a;, /* steer: keep a, in a register */ int right_a;) "
                  "PERM_GENERAL(int right_b;, /* steer: not needed */ int right_c;) return 1; }\n")
STEER_AND_NATURAL = MARK + ("int f(void) { PERM_GENERAL(int WRONG_a;, /* steer: pin it */ int right_a;, int fine_a;) "
                            "return 1; }\n")
ALLOWED = {"config": {"fakematch": "allowed"}}


def test_search_refuses_a_steering_alternative_when_fakematch_is_forbidden(base):
    r, out = search(search_project(base), STEERED)
    expect(r.returncode == 1 and out is None and "fakematch" in r.stderr and "steer" in r.stderr,
           "the refusal should name the rule", r)
    expect("Nothing was built" in r.stderr, "nothing should be built", r)
    r, out = search(search_project(sub(base, "n")), MATCHING)
    expect(out is not None and out["end"] == "match", "natural alternatives are still searched", r)


def test_search_prefers_a_natural_match_over_a_steering_one(base):
    r, out = search(search_project(base, **ALLOWED), STEER_AND_NATURAL)
    expect(out is not None and out["end"] == "match" and out["best"]["code"] == "A2", "the natural match should win", r)
    text = Path(out["winner"]).read_text()
    expect(text == MARK + "int f(void) { int fine_a; return 1; }\n" and "fakematch" not in text,
           f"the winner should hold no steering: {text!r}", r)


def test_search_drops_a_steer_choice_the_match_does_not_need(base):
    r, out = search(search_project(base, **ALLOWED), STEERED)
    expect(out is not None and out["end"] == "match" and out["best"]["code"] == "A1 B0",
           "the match without the unneeded steer choice should win", r)
    text = Path(out["winner"]).read_text()
    expect(text == MARK + "int f(void) { int right_a; /* fakematch: keep a, in a register */ int right_b; return 1; }\n",
           f"the winner should carry the tag's reason on its steering line only: {text!r}", r)


def test_search_reads_a_steering_tag_beside_a_label_and_a_likelihood(base):
    r, out = search(search_project(base, **ALLOWED), in_function(
        "PERM_GENERAL(@r decl-order, int WRONG_a;, %0.6 /* steer: pin it */ int right_a;, /* steer: other */ %0.2 int right_b;)"))
    expect(out is not None and out["end"] == "match" and out["best"]["code"] == "r1",
           "the likelier steering match should win, the tag and the likelihood in either order", r)
    text = Path(out["winner"]).read_text()
    expect(text == in_function("int right_a; /* fakematch: pin it */"), f"the winner should carry the reason: {text!r}", r)


# A fake compiler that takes longer over a source holding a SLOW_ tag, so that candidate's result comes in last.
STEER_SLOW_BUILD_PY = SEARCH_BUILD_PY.replace('open(obj, "w")', '''if "SLOW_" in text:
    import time
    time.sleep(1)
open(obj, "w")''')


def test_search_picks_the_likelier_steering_match_whichever_build_ends_first(base):
    p = search_project(base, files={"tools/search_build.py": STEER_SLOW_BUILD_PY}, **ALLOWED)
    tune(p, workers=3)  # the three candidates build at once, the likelier match the slowest
    r, out = search(p, in_function(
        "PERM_GENERAL(@r decl-order, int WRONG_a;, %0.6 /* steer: likely */ int SLOW_a;, %0.2 /* steer: other */ int right_b;)"))
    expect(out is not None and out["end"] == "match" and out["best"]["code"] == "r1",
           "the likelier steering match should win, though its build ended last", r)


# A fake compiler that logs each compile's WRONG_ tags in order, and ignores every IGNORED_ tag.
SWEEP_BUILD_PY = SEARCH_BUILD_PY.replace('open(obj, "w")', '''log = os.path.join(os.path.dirname(os.path.abspath(__file__)), "order.log")
open(log, "a").write(" ".join(re.findall(r"WRONG_([a-z0-9]+)", text)) + chr(10))
text = re.sub(r"IGNORED_[a-z0-9]+", "", text)
out[0] = text
open(obj, "w")''')


def sweep_project(base):
    return search_project(base, files={"tools/search_build.py": SWEEP_BUILD_PY})


def test_search_compiles_the_baseline_and_each_one_change_candidate_first(base):
    p = sweep_project(base)
    tune(p, workers=1)  # one worker builds in the order the candidates come
    template = MARK + ("int f(void) { PERM_GENERAL(int WRONG_a0;, int WRONG_a1;) "
                       "PERM_GENERAL(int WRONG_b0;, int WRONG_b1;) "
                       "PERM_GENERAL(int WRONG_c0;, int WRONG_c1;, int WRONG_c2;) return 1; }\n")
    log = p.root / "tools" / "order.log"
    before = len(log.read_text().splitlines())  # the check that opened the gate built the unit
    r, out = search(p, template)
    order = log.read_text().splitlines()[before:]
    expect(order[:2] == ["a0 b0 c0"] * 2, f"the baseline is first built twice, to see whether objects repeat: {order}", r)
    order = order[2:]  # those two builds are not candidate builds
    expect(out is not None and out["counts"]["compiled"] == 12 and len(order) == 12 and len(set(order)) == 12,
           f"every candidate is built once: {order}", r)
    expect(order[:5] == ["a0 b0 c0", "a1 b0 c0", "a0 b1 c0", "a0 b0 c1", "a0 b0 c2"],
           f"the baseline and the one-change candidates come first: {order}", r)


def test_search_freezes_a_choice_the_compiler_ignores(base):
    p = sweep_project(base)
    template = MARK + ("int f(void) { PERM_GENERAL(int WRONG_a;, int WRONG_b; int WRONG_b2;) "
                       "PERM_GENERAL(int IGNORED_x;, int IGNORED_y;, int IGNORED_z;) return 1; }\n")
    r, out = search(p, template)
    expect(out is not None and out["inert"] == ["B"], f"the ignored choice should be inert: {out}", r)
    expect(out["counts"]["compiled"] == 4, "the inert choice is not varied after the one-change candidates", r)
    expect(out["effects"] == [{"A": {"A1": 2}}], f"the effect table lists only choices that change the score: {out['effects']}", r)
    expect("stop" not in out, "a search with a live choice carries no stop advice", r)


def test_search_advises_stopping_when_every_choice_is_inert(base):
    template = MARK + "int f(void) { int WRONG_k; PERM_GENERAL(int IGNORED_x;, int IGNORED_y;) return 1; }\n"
    r, out = search(sweep_project(base), template)
    expect(out is not None and out["inert"] == ["A"] and out["effects"] == [], f"every choice is inert: {out}", r)
    expect(out["end"] == "exhausted" and out["counts"]["compiled"] == 2 and "stop searching" in out["stop"],
           "the summary should carry stop advice", r)


def test_search_effect_table_lists_at_most_eight_choices_and_names_the_next_two(base):
    others = " ".join(f"PERM_GENERAL(int ok_{i};, int WRONG_{i};)" for i in range(8))
    template = MARK + ("int f(void) { PERM_GENERAL(int WRONG_a;, int right_a;) "
                       "PERM_GENERAL(int WRONG_b;, int right_b;) " + others + " return 1; }\n")
    r, out = search(search_project(base), template)
    expect(out is not None and out["end"] == "match", "the pair of changes matches", r)
    expect(len(out["effects"]) == 8 and out["inert"] == [], f"the table is cut to 8 choices: {out['effects']}", r)
    expect(len(out["next"]) == 2 and all(": " in line and line.endswith(" bytes") for line in out["next"]),
           f"two runners-up are named: {out['next']}", r)
    expect(len(r.stdout) <= 600 * 4, f"the summary is {len(r.stdout)} characters", r)


# A counting fake compiler: it logs every build to a file, and with STAMP it writes a changing timestamp
# into each object. The matching fake diff reports the function's bytes (the object without comments,
# white space, or the stamp) as `function_sha256`.
COUNT_BUILD_PY = """import sys, time
src, obj, log = sys.argv[1], sys.argv[2], sys.argv[3]
text = open(src).read()
open(log, "a").write("build" + chr(10))
open(obj, "w").write(text + (chr(10) + "STAMP " + str(time.time_ns()) if "STAMP" in sys.argv[4:] else ""))
"""
COUNT_DIFF_PY = """import hashlib, json, re, sys
body = re.sub(r"/[*].*?[*]/|STAMP .*", "", open(sys.argv[1]).read(), flags=re.S)
body = "".join(body.split())
n = body.count("WRONG")
open(sys.argv[2], "w").write("report" + chr(10))
out = {"match": n == 0, "differ_bytes": 2 * n, "function_sha256": hashlib.sha256(body.encode()).hexdigest()}
if "NOSHA" in sys.argv[3:]:
    del out["function_sha256"]
print(json.dumps(out))
"""
TWINS = MARK + "int f(void) { PERM_GENERAL(int WRONG_a;, int WRONG_a;) PERM_GENERAL(int WRONG_b;, int WRONG_c;) return 1; }\n"
COMMENTED = MARK + "int f(void) { PERM_GENERAL(int WRONG_a;, int WRONG_a; /* the same bytes */) return 1; }\n"


def counting_project(base, stamp=False, sha=True):
    log = Path(base) / "builds.log"
    build = PY + f' "{{tools}}/count_build.py" "{{source}}" "{{obj}}" "{log.as_posix()}"' + (" STAMP" if stamp else "")
    p = search_project(base, config={"build": build, "diff": PY + ' "{tools}/count_diff.py" "{obj}" "{report}"' + ("" if sha else " NOSHA")},
                       files={"tools/count_build.py": COUNT_BUILD_PY, "tools/count_diff.py": COUNT_DIFF_PY})
    return p, lambda: len(log.read_text().splitlines()) if log.exists() else 0


def test_search_compiles_alternatives_with_identical_source_once(base):
    p, builds = counting_project(base)
    r, out = search(p, TWINS)
    expect(out is not None and out["counts"]["space"] == 4, "the template has four candidates", r)
    expect(out["counts"]["compiled"] == 2 and out["counts"]["src_dedupe_hits"] == 1,
           f"the twin is seen once, and the freeze of its inert choice skips the fourth: {out['counts']}", r)
    expect(out["counts"]["unique_objects"] == 2 and out["counts"]["hashing"] == "object", "two distinct objects", r)


def test_search_serves_a_second_round_with_the_same_template_from_the_cache(base):
    p, builds = counting_project(base)
    r, first = search(p, TWINS)
    built = builds()
    r, again = search(p, TWINS)
    expect(again is not None and again["counts"]["compiled"] == 0 and again["counts"]["cache_hits"] == 2,
           f"the second round should build nothing: {again and again['counts']}", r)
    expect(builds() == built, "no compiler ran in the second round, not even for the stability check", r)
    expect(again["best"] == first["best"] and again["window"] == first["window"], "the cache keeps the result and window", r)
    cache = p.root / ".decomp" / "search-cache.json"
    expect(cache.exists() and p.git("status", "--porcelain") == "", "the cache sits under .decomp/ and is not committed", r)


def test_search_hashes_function_bytes_when_the_compiler_stamps_its_objects(base):
    p, builds = counting_project(base, stamp=True)
    r, out = search(p, COMMENTED)
    expect(out is not None and out["counts"]["hashing"] == "function", f"the stamp should be detected: {out}", r)
    expect(out["counts"]["compiled"] == 2 and out["counts"]["unique_objects"] == 1,
           "two sources with the same function bytes are one object", r)
    r, again = search(p, COMMENTED)
    expect(again["counts"]["compiled"] == 0 and again["counts"]["hashing"] == "function", "and the cache still serves them", r)
    for o in (out, again):
        expect(o["counts"]["unique_objects"] == 1 and isinstance(o["counts"]["object_hits"], int),
               f"the counts are numbers: {o['counts']}", r)
        expect(not any("function_sha256" in n for n in o.get("notice", [])), f"no notice is due: {o.get('notice')}", r)


def test_search_reads_object_identity_as_unknown_without_function_sha256(base):
    p, builds = counting_project(base, stamp=True, sha=False)
    r, out = search(p, COMMENTED)
    expect(out is not None and out["counts"]["hashing"] == "function", f"the stamp should be detected: {out}", r)
    c = out["counts"]
    expect("unique_objects" in c and c["unique_objects"] is None and "object_hits" in c and c["object_hits"] is None,
           f"nothing was hashed, so both counts are unknown: {c}", r)
    block = [x for x in perf_log(p) if x.get("kind") == "block"][-1]
    expect("unique_objects" in block and block["unique_objects"] is None, f"the performance record says unknown too: {block}", r)
    notices = [n for n in out.get("notice", []) if "function_sha256" in n]
    expect(len(notices) == 1 and "diff adapter" in notices[0] and "/decomp-setup" in notices[0] and "upgrade" in notices[0],
           f"one notice names the missing hash, the adapter and the upgrade: {out.get('notice')}", r)
    expect(len(r.stdout.splitlines()[0]) <= 600 * 4, f"the summary is {len(r.stdout)} characters", r)
    expect(c["compiled"] == 2 and out["inert"] == [] and "stop" not in out,
           f"equal scores and reports freeze no choice as inert: {out}", r)
    r, again = search(p, COMMENTED)
    expect(again["counts"]["unique_objects"] is None and any("function_sha256" in n for n in again.get("notice", [])),
           f"a round served from the cache knows no more: {again}", r)


def test_search_counts_objects_and_gives_no_identity_notice_when_objects_are_stable(base):
    p, builds = counting_project(base, sha=False)
    r, out = search(p, COMMENTED)
    c = out["counts"] if out else {}
    expect(c.get("hashing") == "object" and isinstance(c["unique_objects"], int) and isinstance(c["object_hits"], int),
           f"stable objects are hashed whole: {out}", r)
    expect(not any("function_sha256" in n for n in out.get("notice", [])), f"no notice is due: {out.get('notice')}", r)


# ---------- check trail and the template-search gate ----------

GATE_OPENS = ("register-allocation", "statement-order", "expression-shape")
GATE_CLOSES = ("reference-gap", "data-layout", "calling-convention", "optimization", "unit-order", "build-fail")
ATTEMPT_FIELDS = {"id", "ticket", "unix", "model", "tier", "result", "category", "differ_bytes", "evidence", "source_sha256"}


def trail(p):
    f = p.root / ".decomp" / "trail.jsonl"
    return [json.loads(x) for x in f.read_text().splitlines()] if f.exists() else []


def check_with(p, wrong, *args):
    """Run `check` on a unit the search fake scores at 2 * wrong differing bytes. Returns its parsed JSON line."""
    p.write(SOURCE, MARK + "int f(void) { " + "int WRONG; " * wrong + "return 1; }\n")
    r = p.run("check", TID, *args)
    expect(r.returncode == 0, "check should run", r)
    return json.loads(r.stdout.splitlines()[0])


def set_tier(p, tier):
    ticket = p.root / "tickets" / UNIT / f"{TID}.md"
    ticket.write_text(ticket.read_text().replace("tier: SMALL", f"tier: {tier}"))


def test_check_appends_one_trail_record_per_run_outside_the_commit(base):
    p = search_project(base, gate=None)
    before = time.time()
    check_with(p, 2, "--category", "signedness")
    check_with(p, 0)
    got = trail(p)
    expect([(e["ticket"], e["result"], e["differ_bytes"], e["category"]) for e in got] ==
           [(TID, "differ", 4, "signedness"), (TID, "bytes-match", 0, "")], f"the trail should hold both runs: {got}")
    expect(all(before - 1 <= e["unix"] <= time.time() + 1 for e in got), f"each record holds its time: {got}")
    p.write(SOURCE, STUCK)
    expect(p.git("status", "--porcelain") == "", "the trail is never something git would commit")
    expect(not (p.root / "ledger").exists(), "check records nothing in the ledger")


def test_check_refuses_a_category_outside_the_mismatch_list(base):
    p = search_project(base, gate=None)
    r = p.run("check", TID, "--category", "bogus")
    expect(r.returncode == 1 and "unknown category bogus" in r.stderr and "register-allocation" in r.stderr,
           "check should refuse the category and list the real ones", r)
    expect(trail(p) == [], "a refused check leaves no trail record")


def test_gate_opens_on_a_latest_category_that_small_variations_fix(base):
    p = search_project(base, gate=None)
    for category in GATE_OPENS:
        out = check_with(p, 1, "--category", category)
        expect(out["search_open"] is True and category in out["search_reason"], f"{category} should open the gate: {out}")
    out = check_with(p, 0, "--category", "signedness")
    expect(out["search_open"] is False, f"another category as the latest closes it again: {out}")
    out = check_with(p, 1, "--category", "statement-order")
    expect(out["search_open"] is True, f"the gate follows the latest category: {out}")
    out = check_with(p, 0, "--category", "statement-order")
    expect(out["search_open"] is False, f"a match leaves nothing to search for: {out}")


def test_gate_opens_after_three_attempts_with_no_fall_in_differ_bytes(base):
    p = search_project(base, gate=None)
    opened = [check_with(p, wrong, "--category", "signedness")["search_open"] for wrong in (3, 2, 2, 3, 1, 1, 2)]
    #         6      4      4      6 (none below 4)  2 (a fall)  2      4 (none below 2)
    expect(opened == [False, False, False, True, False, False, True], f"the gate should open only on a stall: {opened}")


def test_gate_stays_closed_for_tiny_tickets_and_stop_or_report_categories(base):
    p = search_project(base, gate=None)
    for category in GATE_CLOSES:
        for _ in range(3):
            out = check_with(p, 1, "--category", category)
        expect(out["search_open"] is False and category in out["search_reason"],
               f"{category} should keep the gate closed through a stall: {out}")
    set_tier(p, "TINY")
    out = check_with(p, 1, "--category", "register-allocation")
    expect(out["search_open"] is False and "TINY" in out["search_reason"], f"a TINY ticket stays closed: {out}")
    r, _ = search(p, MATCHING)
    expect(r.returncode == 1 and "TINY" in r.stderr, "search should refuse a TINY ticket with the reason", r)


def test_a_build_failure_keeps_the_gate_closed_without_a_category(base):
    p = search_project(base, gate=None)
    for _ in range(3):
        p.write(SOURCE, MARK + "SYNTAX_ERROR\n")
        r = p.run("check", TID)
        out = json.loads(r.stdout.splitlines()[0])
    expect(out["result"] == "build-fail" and out["search_open"] is False and "build-fail" in out["search_reason"],
           f"three build failures should not open the gate: {out}")
    expect(trail(p)[-1]["category"] == "build-fail", "the trail records the failure's category")


def test_search_is_refused_with_the_reason_while_the_gate_is_closed(base):
    p = search_project(base, gate=None)
    r, out = search(p, MATCHING)
    expect(r.returncode == 1 and out is None and "closed" in r.stderr and "no check has run" in r.stderr,
           "search should refuse before any check", r)
    check_with(p, 1, "--category", "data-layout")
    r, out = search(p, MATCHING)
    expect(r.returncode == 1 and out is None and "data-layout" in r.stderr, "the refusal should give the reason", r)
    expect(len(trail(p)) == 1 and not (p.root / ".decomp" / "search").exists(), "a refused search is not an attempt")


def test_gate_is_reported_closed_when_the_contract_disallows_template_search(base):
    p = search_project(base, gate=None, config={"template_search": False})
    out = check_with(p, 1, "--category", "register-allocation")
    expect(out["search_open"] is False and "contract" in out["search_reason"], f"check should say why: {out}")


def test_a_search_round_adds_one_attempt_to_the_trail(base):
    p = search_project(base)
    r, out = search(p, NEVER)
    expect(out is not None and out["end"] == "exhausted", "the round should run", r)
    got = trail(p)
    expect(len(got) == 2 and (got[1]["by"], got[1]["result"], got[1]["differ_bytes"]) == ("search", "differ", 4),
           f"the round is one trail record holding its best score: {got}")
    expect(got[1]["category"] == "register-allocation", "the round keeps the category it worked on")
    r, out = search(p, MATCHING)
    expect(out is not None and out["end"] == "match" and len(trail(p)) == 3, "each round is one more attempt", r)


def test_verify_records_a_template_round_in_the_evidence_and_leaves_the_ledger_fields(base):
    p = search_project(base, status="claimed")
    r, out = search(p, MATCHING)
    expect(out is not None and out["end"] == "match", "the round should match", r)
    p.branch(f"w/{TID}", {SOURCE: Path(out["winner"]).read_text()})
    r = p.run("verify", TID, "--model", "m", "--template-round")
    expect(r.returncode == 0 and '"result": "bytes-match"' in r.stdout, "verify should record bytes-match", r)
    lines = (p.root / "ledger" / "evidence" / f"{TID}-a001.txt").read_text().splitlines()
    marked = [l for l in lines if l.startswith("template-round: ")]
    expect(len(marked) == 1, f"the evidence should mark the attempt as a template round: {lines[-3:]}", r)
    got = json.loads(marked[0][len("template-round: "):])
    expect((got["best"], got["differ_bytes"], got["kinds"], got["category"]) == ("A1 B2", 0, ["other", "other"], "register-allocation"),
           f"the evidence should hold the round's best candidate, its kinds, and its category: {got}")
    attempts = p.lines("attempts.jsonl")
    expect(len(attempts) == 1 and set(attempts[0]) == ATTEMPT_FIELDS, f"the ledger's fields are unchanged: {attempts}")


def test_verify_without_the_flag_marks_no_template_round(base):
    p = search_project(base, status="claimed")
    r, out = search(p, MATCHING)
    p.branch(f"w/{TID}", {SOURCE: Path(out["winner"]).read_text()})
    r = p.run("verify", TID, "--model", "m")
    expect(r.returncode == 0, "verify should pass", r)
    expect("template-round" not in (p.root / "ledger" / "evidence" / f"{TID}-a001.txt").read_text(),
           "an attempt is a template round only when the flag says so")


def test_verify_refuses_the_template_round_flag_when_no_round_is_kept(base):
    p = search_project(base, status="claimed")
    p.branch(f"w/{TID}", {SOURCE: CLEAN})
    r = p.run("verify", TID, "--model", "m", "--template-round")
    expect(r.returncode == 1 and "no template round is kept" in r.stderr, "verify should refuse", r)
    expect(p.lines("attempts.jsonl") == [] and p.status() == "claimed", "the refusal records nothing")


def second_writer(p, n, kinds, result="bytes-match", category="register-allocation"):
    """Record, as another writer's `verify --template-round` would, attempt n of the ticket: a round holding these kinds."""
    ledger = p.root / "ledger"
    (ledger / "evidence").mkdir(parents=True, exist_ok=True)
    aid = f"{TID}-a{n:03d}"
    rec = {"id": aid, "ticket": TID, "unix": 1, "model": "m", "tier": "SMALL", "category": "", "differ_bytes": 0,
           "evidence": f"ledger/evidence/{aid}.txt", "result": result, "source_sha256": "0"}
    kept = {"category": category, "best": "x", "differ_bytes": 0, "kinds": kinds, "result": result, "unix": 1}
    (ledger / "evidence" / f"{aid}.txt").write_text(f"template-round: {json.dumps(kept)}\n", encoding="utf-8")
    with (ledger / "attempts.jsonl").open("a", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(rec) + "\n")


HISTORY_TEMPLATE = in_function("PERM_GENERAL(@regs decl-order, int WRONG_a;, int right_a;) "
                               "PERM_GENERAL(@shape expression-shape, int WRONG_b;, int right_b;)")


def test_history_line_counts_template_round_wins_by_kind_for_the_category(base):
    p = search_project(base, status="claimed")
    r, out = search(p, HISTORY_TEMPLATE)
    expect(out is not None and out["end"] == "match" and "history" not in out, "no history before a recorded win", r)
    p.branch(f"w/{TID}", {SOURCE: Path(out["winner"]).read_text()})
    r = p.run("verify", TID, "--model", "m", "--template-round")
    expect(r.returncode == 0, "verify should record the win", r)
    r, out = search(p, HISTORY_TEMPLATE)
    expect(out is not None and out["history"] == "expression-shape fixed register-allocation 1 of 1 times on this compiler",
           f"the history line should count the win by kind: {out}", r)


def test_a_win_recorded_by_a_second_writer_changes_the_next_rounds_history_line(base):
    p = search_project(base)
    second_writer(p, 1, ["decl-order"])
    r, out = search(p, HISTORY_TEMPLATE)
    expect(out is not None and out["history"] == "decl-order fixed register-allocation 1 of 1 times on this compiler",
           f"the first round should see the first writer's win: {out}", r)
    second_writer(p, 2, ["decl-order"])
    second_writer(p, 3, ["decl-order"], result="differ")
    r, out = search(p, HISTORY_TEMPLATE)
    expect(out is not None and out["history"] == "decl-order fixed register-allocation 2 of 3 times on this compiler",
           f"the next round should see what was recorded in between: {out}", r)


def test_history_of_another_category_adds_no_line(base):
    p = search_project(base)
    second_writer(p, 1, ["decl-order"], category="data-layout")
    r, out = search(p, HISTORY_TEMPLATE)
    expect(out is not None and "history" not in out, f"only the ticket's category counts: {out}", r)


def test_a_kind_with_more_history_compiles_its_alternatives_earlier(base):
    log = Path(base) / "order.log"
    p = search_project(base, files={"tools/search_build.py": ORDER_BUILD_PY.replace("LOG", repr(str(log)))})
    template = in_function("PERM_GENERAL(@regs decl-order, tag_a0 WRONG_1, tag_a1 WRONG_2) "
                           "PERM_GENERAL(@shape expression-shape, tag_b0 WRONG_3, tag_b1 WRONG_4)")
    second_writer(p, 1, ["expression-shape"])
    second_writer(p, 2, ["expression-shape"])
    tune(p, workers=1)  # one worker builds in the order the candidates come
    r, out = search(p, template)
    after = log.read_text().splitlines()[-4:]
    expect(after == ["tag_a0 tag_b0", "tag_a0 tag_b1", "tag_a1 tag_b0", "tag_a1 tag_b1"],
           f"after the baseline, the kind with a win history should compile its alternative first: {after}", r)


def test_a_search_writes_no_priors_file(base):
    p = search_project(base)
    second_writer(p, 1, ["decl-order"])
    search(p, HISTORY_TEMPLATE)
    names = [f.name for d in (p.root / ".decomp", p.root / "ledger") if d.is_dir() for f in d.rglob("*") if f.is_file()]
    expect(not [n for n in names if "prior" in n.lower() or "histor" in n.lower()], f"no priors file: {names}")


# ---------- template search: parallel blocks ----------

# A fake compiler that counts how many of itself run at once: each run marks itself in a folder,
# stays a while, and logs how many marks it sees when it starts and when it ends.
PEAK_BUILD_PY = """import os, sys, time
src, obj, folder = sys.argv[1:4]
os.makedirs(os.path.join(folder, "running"), exist_ok=True)
me = os.path.join(folder, "running", str(os.getpid()))
def note():
    open(os.path.join(folder, "peak.log"), "a").write(str(len(os.listdir(os.path.join(folder, "running")))) + chr(10))
open(me, "w").close()
note()
time.sleep(0.5)
note()
os.remove(me)
open(obj, "w").write(open(src).read())
"""
# A fake compiler that hangs on a candidate holding HANG, after starting a grandchild that keeps
# adding to a heartbeat file for up to 30 seconds.
HANG_BUILD_PY = """import subprocess, sys, time
src, obj, beat = sys.argv[1:4]
text = open(src).read()
if "HANG" in text:
    code = "import sys, time" + chr(10) + "for i in range(300):" + chr(10) + "    open(sys.argv[1], 'a').write('x')" + chr(10) + "    time.sleep(0.1)"
    subprocess.Popen([sys.executable, "-c", code, beat])
    time.sleep(30)
open(obj, "w").write(text)
"""
# A fake compiler whose object leaves the comments out.
BARE_BUILD_PY = """import re, sys
open(sys.argv[2], "w").write(re.sub(r"/[*].*?[*]/", "", open(sys.argv[1]).read()))
"""


def tune(p, **search):
    """Override block constants in the project's local.json, as a user would for this machine."""
    path = p.root / ".decomp" / "local.json"
    search.setdefault("background", 0)  # a test that wants a search to go on in the background asks for it
    path.write_text(json.dumps(dict(json.loads(path.read_text()), search=search)))


def wide(n, alternatives=("int WRONG_{c}0;", "int WRONG_{c}1; int WRONG_{c}2;")):
    """A template of n choice points that never matches."""
    return MARK + "int f(void) { int WRONG_now; " + " ".join(
        "PERM_GENERAL(" + ", ".join(a.format(c=chr(97 + i)) for a in alternatives) + ")" for i in range(n)) + " return 1; }\n"


def test_search_runs_as_many_compiles_at_once_as_it_has_workers(base):
    folder = Path(base) / "peak"
    build = PY + f' "{{tools}}/peak_build.py" "{{source}}" "{{obj}}" "{folder.as_posix()}"'
    p = search_project(base, config={"build": build}, files={"tools/peak_build.py": PEAK_BUILD_PY})
    tune(p, workers=3)
    r, out = search(p, wide(3))
    expect(out is not None and out["end"] == "exhausted" and out["counts"]["compiled"] == 8, "all 8 candidates are built", r)
    peak = max(int(x) for x in (folder / "peak.log").read_text().split())
    expect(peak == 3 and out["counts"]["workers"] == 3, f"3 workers should build 3 at once, the peak was {peak}", r)
    expect(out["counts"]["shell"] == 0, "an adapter with no shell feature starts without the shell", r)
    expect(out["best"] == {"code": "A0 B0 C0", "differ_bytes": 8}, "the best is the same whatever the workers' order", r)


def test_search_block_ends_at_an_overridden_deadline(base):
    p = search_project(base)
    tune(p, workers=2, deadline_s=1)
    r, out = search(p, wide(10))
    expect(out is not None and out["end"] == "deadline", f"the block should end on its deadline: {out}", r)
    c = out["counts"]
    expect(1.0 <= c["wall_s"] < 6.0, f"the block ran {c['wall_s']} s on a 1 s deadline", r)
    expect(0 < c["compiled"] < c["space"] == 1024, "it stopped with candidates left", r)


def test_search_block_aborts_when_most_early_candidates_fail_to_build(base):
    p = search_project(base)
    tune(p, workers=2)
    r, out = search(p, wide(3, ("int WRONG_{c};", "SYNTAX_ERROR {c}1;", "SYNTAX_ERROR {c}2;", "SYNTAX_ERROR {c}3;")))
    expect(out is not None and out["end"] == "abort-buildfail", f"3 of the first 4 builds fail: {out}", r)
    c = out["counts"]
    expect(c["build_fail"] >= 3 and c["compiled"] < c["space"] == 64, "the block ends long before the space does", r)
    expect(out["best"] == {"code": "A0 B0 C0", "differ_bytes": 8}, "the candidate that built is still the best", r)


def test_search_block_is_exhausted_when_its_candidates_are_mostly_repeats(base):
    p = search_project(base)
    tune(p, workers=1, repeat_window=10)
    r, out = search(p, wide(3, ("int WRONG_same;",) * 5))
    expect(out is not None and out["end"] == "exhausted", f"every candidate has one source: {out}", r)
    c = out["counts"]
    expect(c["compiled"] == 1 and c["src_dedupe_hits"] == 10 and c["space"] == 125,
           f"one build, then a window of 10 repeats ends the block: {c}", r)


def test_search_block_ends_on_a_plateau(base):
    p = search_project(base, config={"build": PY + ' "{tools}/bare_build.py" "{source}" "{obj}"'},
                       files={"tools/bare_build.py": BARE_BUILD_PY})
    tune(p, workers=1, plateau_compiles=6)
    r, out = search(p, wide(8, ("/* {c}0 */", "/* {c}1 */")))
    expect(out is not None and out["end"] == "plateau", f"no candidate brings a new object or score: {out}", r)
    c = out["counts"]
    expect(c["compiled"] == 7 and c["unique_objects"] == 1 and c["space"] == 256,
           f"the first build, then 6 with nothing new: {c}", r)


def test_search_kills_a_hung_compile_with_its_grandchild_as_a_build_fail(base):
    beat = Path(base) / "beat"
    build = PY + f' "{{tools}}/hang_build.py" "{{source}}" "{{obj}}" "{beat.as_posix()}"'
    p = search_project(base, config={"build": build}, files={"tools/hang_build.py": HANG_BUILD_PY})
    tune(p, workers=1, hang_floor_s=2, hang_start_s=10)
    r, out = search(p, MARK + "int f(void) { PERM_GENERAL(int WRONG_a;, int WRONG_b; int WRONG_c;, int HANG;) return 1; }\n")
    expect(out is not None and out["end"] == "exhausted", f"the block should outlive the hang: {out}", r)
    c = out["counts"]
    expect(c["killed"] == 1 and c["build_fail"] == 1 and c["compiled"] == 3, f"the hang is one killed build-fail: {c}", r)
    expect(out["best"] == {"code": "A0", "differ_bytes": 2}, "the other candidates are scored", r)
    expect(beat.exists() and beat.stat().st_size > 0, "the grandchild should have started")
    size = beat.stat().st_size
    time.sleep(0.6)
    expect(beat.stat().st_size == size, "the grandchild should be dead: its heartbeat still grows")


# A fake compiler that takes a second, so a block's first builds end after a half-second deadline.
# It hangs on a candidate holding HANG.
SLOW_BUILD_PY = """import sys, time
text = open(sys.argv[1]).read()
time.sleep(30 if "HANG" in text else 1)
open(sys.argv[2], "w").write(text)
"""


def slow_project(base, **constants):
    """A search project whose 2 workers are both still on their first build when the block's deadline comes."""
    build = PY + ' "{tools}/slow_build.py" "{source}" "{obj}"'
    p = search_project(base, config={"build": build}, files={"tools/slow_build.py": SLOW_BUILD_PY})
    tune(p, **dict({"workers": 2, "deadline_s": 0.5}, **constants))
    return p


def test_search_block_at_its_deadline_finishes_a_last_pass_of_its_workers(base):
    p = slow_project(base, ceiling_s=30, background=1)
    try:
        r, out = search(p, wide(2))  # 4 candidates: 2 are out at the deadline, 2 are left for 2 workers
        expect(out is not None and out["end"] == "exhausted", f"the last 2 candidates are built: {out}", r)
        expect(out["counts"]["compiled"] == out["counts"]["space"] == 4, f"every candidate is built: {out['counts']}", r)
        expect("continues_s" not in out and not background_folder(p).exists(),
               f"an exhausted space leaves no background search: {out}", r)
    finally:
        stop_background(p)


def test_search_block_at_its_deadline_ends_there_with_more_candidates_left_than_workers(base):
    p = slow_project(base)
    r, out = search(p, wide(3))  # 8 candidates: 6 are left for 2 workers
    expect(out is not None and out["end"] == "deadline", f"the block should end on its deadline: {out}", r)
    expect(out["counts"]["compiled"] == 2 and out["counts"]["space"] == 8, f"only the first 2 are built: {out['counts']}", r)


def test_search_kills_a_hung_compile_in_a_deadline_blocks_last_pass(base):
    p = slow_project(base, hang_floor_s=2, hang_start_s=4)
    began = time.time()
    r, out = search(p, MARK + "int f(void) { PERM_GENERAL(int WRONG_a;, int WRONG_b; int WRONG_c;, int HANG;) return 1; }\n")
    took = time.time() - began
    expect(out is not None and out["end"] == "exhausted", f"the block should outlive the hang: {out}", r)
    c = out["counts"]
    expect(c["killed"] == 1 and c["build_fail"] == 1 and c["compiled"] == 3, f"the hang is one killed build-fail: {c}", r)
    expect(took < 25, f"the hung compile is killed, not waited for: the call took {took:.1f} s", r)


def test_search_falls_back_to_the_shell_for_an_adapter_that_needs_it(base):
    p = search_project(base, config={"build": "cd . && " + SEARCH_CONFIG["build"]})
    r, out = search(p, MATCHING)
    expect(out is not None and out["end"] == "match" and out["counts"]["build_fail"] == 0,
           f"a build adapter using && should still build: {out}", r)
    expect(out["counts"]["shell"] > 0, "it ran through the shell", r)


def test_search_refuses_an_unknown_override_in_local_json(base):
    p = search_project(base)
    tune(p, deadline=1)
    r, out = search(p, MATCHING)
    expect(r.returncode == 1 and out is None and "deadline" in r.stderr and "deadline_s" in r.stderr,
           "a misspelt override is named with the ones that exist", r)


# A fake diff where two alternatives only help together: tag_b2 with tag_d2 takes 6 bytes off, either alone none.
PAIR_DIFF_PY = """import json, sys
text = open(sys.argv[1]).read()
n = 2 * text.count("WRONG") - (6 if "tag_b2" in text and "tag_d2" in text else 0)
open(sys.argv[2], "w").write("report" + chr(10))
print(json.dumps({"match": n == 0, "differ_bytes": n}))
"""


def grid(n, weight=lambda i, a: "", alternatives=3):
    """A template of n choice points whose alternative a of choice point c holds tag_<c><a>, a weight before it, and one WRONG."""
    return in_function(" ".join(
        "PERM_GENERAL(" + ", ".join(f"{weight(i, a)} tag_{chr(97 + i)}{a} WRONG_x".strip() for a in range(alternatives)) + ")"
        for i in range(n)))


def sampled_search(base, template, files=None, config=None, **constants):
    """Search with one worker and a compiler that logs its order. Returns (process, summary, the candidates built, in order)."""
    log = Path(base) / "order.log"
    p = search_project(base, config=config or {},
                       files=dict({"tools/search_build.py": ORDER_BUILD_PY.replace("LOG", repr(str(log)))}, **(files or {})))
    tune(p, workers=1, **constants)  # one worker builds in the order the candidates come
    r, out = search(p, template)
    expect(out is not None, "search should print a summary", r)
    return r, out, log.read_text().splitlines()[-out["counts"]["compiled"]:]


def test_search_samples_in_the_same_order_on_every_run_with_one_seed(base):
    runs = [sampled_search(sub(base, name), grid(6), budget=120, **kw)
            for name, kw in (("a", {}), ("b", {}), ("c", {"seed": 7}))]
    (r, out, first), (_, _, again), (_, _, other) = runs
    c = out["counts"]
    expect(c["space"] == 729 and c["compiled"] == 120 and out["end"] == "deadline", f"the budget ends the block: {out}", r)
    expect(c["sampled"] == 120 - 13 and len(set(first)) == 120, f"13 open the round, the rest are sampled, none twice: {c}", r)
    expect(first == again, "one seed should give one order")
    expect(first[:13] == other[:13] and first != other, "another seed should give another order after the sweep")


def test_search_samples_a_high_likelihood_combination_before_a_low_one(base):
    r, out, order = sampled_search(base, grid(6, lambda i, a: ("%0.3", "%0.6", "%0.1")[a]), budget=120)
    expect(order[13] == " ".join(f"tag_{c}1" for c in "abcdef"),
           f"the likeliest combination should be the first one sampled: {order[13:16]}", r)
    picks = " ".join(order[13:]).split()
    high, low = sum(x.endswith("1") for x in picks), sum(x.endswith("2") for x in picks)
    expect(high > low, f"the likelier alternative should be sampled more: {high} against {low}", r)


def test_search_samples_a_natural_alternative_before_a_steering_one_at_equal_likelihood(base):
    template = grid(6, lambda i, a: ("%0.2", "%0.4", "/* steer: pin it */ %0.4")[a])
    r, out, order = sampled_search(base, template, config={"fakematch": "allowed"}, budget=60)
    natural, steering = (" ".join(f"tag_{c}{a}" for c in "abcdef") for a in (1, 2))
    expect(order[13] == natural, f"the first combination sampled should be the natural one: {order[13]}", r)
    expect(steering not in order or order.index(steering) > 13, "the steering combination comes after it", r)
    singles = [x for line in order[1:13] for x in line.split() if not x.endswith("0")]
    expect([x[-1] for x in singles] == ["1"] * 6 + ["2"] * 6, f"the sweep tries the natural alternatives first: {singles}", r)


def test_search_finds_a_pair_that_only_helps_together_against_the_priors(base):
    away = grid(6, lambda i, a: "%0.02" if a == 2 and i in (1, 3) else "%0.49")
    r, out, order = sampled_search(base, away, files={"tools/search_diff.py": PAIR_DIFF_PY}, budget=120)
    code = out["best"]["code"].split()
    expect(out["best"]["differ_bytes"] == 6 and "B2" in code and "D2" in code, f"the best should hold the pair: {out['best']}", r)
    expect(out["effects"] == [], f"neither alternative helps alone: {out['effects']}", r)
    expect(out.get("pairs") and out["pairs"][0].startswith("B2+D2: -"), f"the summary should name the pair first: {out.get('pairs')}", r)
    expect(len(out["pairs"]) <= 3, "at most three pairs are named", r)


def test_search_with_a_budget_of_tens_of_compiles_covers_every_pair_of_alternatives(base):
    weights = (0.5, 0.3, 0.2)
    r, out, order = sampled_search(base, grid(5, lambda i, a: f"%{weights[a]}"), budget=40)
    c = out["counts"]
    opening = 11 + c["pairwise"]
    expect(c["space"] == 243 and c["compiled"] == 40 and 0 < c["pairwise"] <= 29, f"the covering sample fits the budget: {c}", r)
    held = {(x, y) for line in order[:opening] for x, y in itertools.combinations(line.split(), 2)}
    expect(len(held) == 10 * 9, f"the sweep and the sample should hold all 90 pairs, they hold {len(held)}", r)
    prior = [math.prod(weights[int(x[-1])] for x in line.split()) for line in order[11:opening]]
    expect(prior == sorted(prior, reverse=True), f"the sample is tried likeliest first: {prior}", r)


def test_search_makes_a_fifth_of_its_sampled_picks_exploratory(base):
    r, out, order = sampled_search(base, grid(6, lambda i, a: ("%0.3", "%0.6", "%0.1")[a]), budget=150)
    c = out["counts"]
    expect(c["sampled"] == 150 - 13 and c["pairwise"] == 0, f"a budget of 150 samples without the covering opening: {c}", r)
    expect(c["explored"] >= 0.2 * c["sampled"], f"{c['explored']} of {c['sampled']} picks were exploratory", r)
    top = " ".join(f"tag_{x}1" for x in "abcdef")
    expect(top not in order[14:], "no later pick repeats the best-ranked candidate", r)


def test_search_tries_first_the_alternative_written_as_the_closest_solved_function_is(base):
    other = "u0002-00402000"
    files = {"expected/00401000.bin": "abcdefgh\n", "expected/00402000.bin": "abcdefgx\n",
             "src/u0002.c": f"// @decomp {other}\nint g(int n) {{ int k = 0; while (k < n) k++; return k; }}\n",
             f"tickets/u0002/{other}.md": ticket_text(other, "0x00402000", "src/u0002.c", "integrated"),
             "ledger/matches.jsonl": matches_ledger(other)}
    r, out, order = sampled_search(base, LOOP_SPELLINGS, files=files)
    expect([line.split()[1] for line in order] == ["tag_base", "tag_while", "tag_for"],
           f"the spelling the solved function uses should be tried before the other: {order}", r)


# Read by every Python the tool starts: it writes down each ticket file that is opened.
TICKET_READS_PY = """import os, sys
def _hook(event, args):
    if event == "open" and args:
        path = str(args[0]).replace(os.sep, "/")
        if "/tickets/" in path and path.endswith(".md"):
            with open(os.environ["TICKET_READS"], "a") as f:
                f.write(path.rsplit("/", 1)[1][:-3] + chr(10))
sys.addaudithook(_hook)
"""
LOOP_SPELLINGS = in_function("int tag_a; PERM_GENERAL(tag_base = WRONG_x;, for (; tag_for < WRONG_n;) WRONG_k++;, "
                             "while (tag_while < WRONG_n) WRONG_k++;)")
WHILE_LOOP = "int g(int n) { int k = 0; while (k < n) k++; return k; }\n"


def matches_ledger(*tids):
    """The matches ledger as `audit pass` leaves it for these tickets."""
    return "".join(json.dumps({"ticket": tid, "unix": 1789000000, "attempt": f"{tid}-a001", "model": "m", "size": 37,
                               "auditor": "a1"}, sort_keys=True) + "\n" for tid in tids)


def solved_ticket(n, status="integrated", source=WHILE_LOOP, expected="abcdefgx\n"):
    """The files of one more ticket, u<n>, close to the project's own: its ticket, its unit and its expected bytes."""
    tid = f"u{n:04d}-{0x00400000 + n * 0x1000:08x}"
    files = {f"tickets/u{n:04d}/{tid}.md": ticket_text(tid, f"0x{tid.split('-')[1]}", f"src/u{n:04d}.c", status),
             f"src/u{n:04d}.c": f"// @decomp {tid}\n{source}"}
    if expected is not None:
        files[f"expected/{tid.split('-')[1]}.bin"] = expected
    return tid, files


def ticket_reads(base, files):
    """Search LOOP_SPELLINGS in a project of `files`. Returns (process, the candidates built in order, the ticket files read)."""
    base = Path(base)
    hook, reads, log = base / "hook", base / "reads.log", base / "order.log"
    hook.mkdir()
    (hook / "sitecustomize.py").write_text(TICKET_READS_PY, encoding="utf-8")
    files = dict({"expected/00401000.bin": "abcdefgh\n",
                  "tools/search_build.py": ORDER_BUILD_PY.replace("LOG", repr(str(log)))}, **files)
    p = search_project(base, files=files)
    tune(p, workers=1)
    template = base / "template.c"
    template.write_text(LOOP_SPELLINGS, encoding="utf-8")
    r = p.run("search", TID, str(template), env={"PYTHONPATH": str(hook), "TICKET_READS": str(reads)})
    expect(r.returncode == 0, "search should pass", r)
    order = [line.split()[1] for line in log.read_text().splitlines()[-3:]]
    return r, order, (reads.read_text().split() if reads.exists() else [])


def test_search_reads_no_more_ticket_files_however_many_tickets_are_open(base):
    counts = {}
    for extra in (0, 40):
        files, solved = {}, []
        for n in (2, 3):
            tid, more = solved_ticket(n)
            solved.append(tid)
            files.update(more)
        for n in range(4, 4 + extra):
            files.update(solved_ticket(n, status="open")[1])
        files["ledger/matches.jsonl"] = matches_ledger(*solved)
        r, order, reads = ticket_reads(sub(base, f"open{extra}"), files)
        expect(order == ["tag_base", "tag_while", "tag_for"], f"the bonus should hold with {extra} open tickets: {order}", r)
        expect(set(reads) == {TID, *solved}, f"only the ticket and the matched ones are read: {sorted(set(reads))}", r)
        counts[extra] = len(reads)
    expect(counts[0] == counts[40], f"the ticket files read should not grow with the open tickets: {counts}")


def test_search_leaves_out_a_matched_ticket_it_cannot_read(base):
    gone, files = solved_ticket(2)
    del files[f"tickets/u0002/{gone}.md"]
    bare, more = solved_ticket(3, expected=None)
    files.update(more)
    regressed, more = solved_ticket(4, status="regressed")
    files.update(more)
    files["ledger/matches.jsonl"] = matches_ledger(gone, bare, regressed)
    r, order, reads = ticket_reads(base, files)
    expect(order == ["tag_base", "tag_for", "tag_while"], f"no function is left to give a bonus: {order}", r)


def test_search_reads_no_other_ticket_in_a_project_without_a_match(base):
    files = {}
    for n, status in ((2, "open"), (3, "claimed"), (4, "integrated")):  # the last was never recorded as a match
        files.update(solved_ticket(n, status=status)[1])
    r, order, reads = ticket_reads(base, files)
    expect(order == ["tag_base", "tag_for", "tag_while"], f"no match gives no bonus: {order}", r)
    expect(set(reads) == {TID}, f"only the ticket searched is read: {sorted(set(reads))}", r)


# ---------- template search: the machine-wide slot pool ----------

def peak_project(base, folder, **search):
    """A search project whose fake compiler logs how many of itself run at once into `folder`."""
    build = PY + f' "{{tools}}/peak_build.py" "{{source}}" "{{obj}}" "{Path(folder).as_posix()}"'
    p = search_project(base, config={"build": build}, files={"tools/peak_build.py": PEAK_BUILD_PY})
    tune(p, **search)
    return p


def peak_of(folder):
    return max(int(x) for x in (Path(folder) / "peak.log").read_text().split())


def slot_folder(p):
    d = p.root / ".decomp" / "slots"
    d.mkdir(exist_ok=True)
    return d


def writer(p, name, age):
    """Leave another writer's heartbeat in the pool, last beaten `age` seconds ago (below zero: it stays fresh)."""
    beat = slot_folder(p) / f"{name}.writer"
    beat.write_text(name)
    os.utime(beat, (time.time() - age,) * 2)
    return beat


def hold_slot(p, index, name):
    slot = slot_folder(p) / f"{index}.slot"
    slot.write_text(name)
    return slot


def test_two_concurrent_searches_never_compile_more_at_once_than_the_pool_has_slots(base):
    import threading
    folder = Path(base) / "peak"
    one = peak_project(sub(base, "one"), folder, workers=3, slots=2, slot_heartbeat_s=0.2)
    two = peak_project(sub(base, "two"), folder)
    shared = {"DECOMP_LOCAL": str(one.root / ".decomp")}  # one machine folder: its settings and its pool
    got = {}

    def run(name, p):
        path = p.base / "template.c"
        path.write_text(wide(2), encoding="utf-8")
        got[name] = p.run("search", TID, str(path), env=shared)

    threads = [threading.Thread(target=run, args=a) for a in (("one", one), ("two", two))]
    for th in threads:
        th.start()
    for th in threads:
        th.join()
    outs = []
    for name in ("one", "two"):
        expect(got[name].returncode == 0 and got[name].stdout, f"search {name} should finish", got[name])
        outs.append(json.loads(got[name].stdout.splitlines()[0]))
    for out in outs:
        c = out["counts"]
        expect(out["end"] == "exhausted" and c["compiled"] == 4, f"every candidate is built: {out}")
        expect(c["workers"] == 3 and c["slots"] == 2, f"3 workers each, on a pool of 2 slots: {c}")
    expect(max(o["counts"]["writers_active"] for o in outs) == 2, f"the later search should count both writers: {outs}")
    expect(peak_of(folder) == 2, f"6 workers on 2 slots should build 2 at once, the peak was {peak_of(folder)}")
    left = sorted(f.name for f in slot_folder(one).iterdir())
    expect(left == [], f"both searches should leave the pool empty: {left}")


def test_search_reclaims_the_slots_of_a_holder_whose_heartbeat_is_stale(base):
    folder = Path(base) / "peak"
    p = peak_project(base, folder, workers=3, slots=2)
    beat = writer(p, "111-dead", 3600)
    hold_slot(p, 0, "111-dead")
    hold_slot(p, 1, "222-beef")  # a holder with no heartbeat at all
    r, out = search(p, wide(2))
    expect(out is not None and out["end"] == "exhausted" and out["counts"]["compiled"] == 4,
           f"the search should build on the reclaimed slots: {out}", r)
    c = out["counts"]
    expect(c["slots_reclaimed"] == 2 and c["writers_active"] == 1, f"both stale slots are reclaimed: {c}", r)
    expect(peak_of(folder) == 2, f"both slots should be in use again, the peak was {peak_of(folder)}", r)
    expect(not beat.exists(), "the stale heartbeat should be cleared away")


def test_search_leaves_the_slot_of_a_holder_whose_heartbeat_is_fresh(base):
    folder = Path(base) / "peak"
    p = peak_project(base, folder, workers=3, slots=2)
    writer(p, "333-cafe", -3600)
    slot = hold_slot(p, 1, "333-cafe")
    r, out = search(p, wide(2))
    expect(out is not None and out["end"] == "exhausted" and out["counts"]["compiled"] == 4,
           f"the search should build on the slot that is free: {out}", r)
    c = out["counts"]
    expect(c["slots_reclaimed"] == 0 and c["writers_active"] == 2, f"a live holder keeps its slot: {c}", r)
    expect(peak_of(folder) == 1, f"one free slot builds one at a time, the peak was {peak_of(folder)}", r)
    expect(slot.read_text() == "333-cafe", "the live holder's slot is untouched")


def test_search_starts_with_the_cores_divided_by_the_active_writers(base):
    p = search_project(base)
    tune(p, cores=8)
    r, out = search(p, wide(4))
    c = out["counts"] if out else {}
    expect(c.get("workers") == 8 and c.get("slots") == 8 and c.get("writers_active") == 1,
           f"one writer on 8 cores starts 8 workers: {c}", r)
    writer(p, "111-dead", 3600)  # stale: not an active writer
    writer(p, "333-cafe", -3600)
    r, out = search(p, wide(4))
    c = out["counts"] if out else {}
    expect(c.get("workers") == 4 and c.get("writers_active") == 2, f"two writers on 8 cores start 4 workers each: {c}", r)
    writer(p, "444-f00d", -3600)
    r, out = search(p, wide(4))
    c = out["counts"] if out else {}
    expect(c.get("workers") == 2 and c.get("writers_active") == 3, f"three writers on 8 cores start 2 workers each: {c}", r)
    tune(p, cores=8, workers=5)
    r, out = search(p, wide(4))
    expect(out is not None and out["counts"]["workers"] == 5, f"a set worker count is kept: {out}", r)


def test_core_count_falls_back_to_the_logical_count_when_the_platform_call_fails(base):
    # The one case that reaches into the tool: no command line can make the platform's call fail.
    import importlib.util
    kept, sys.dont_write_bytecode = sys.dont_write_bytecode, True
    try:
        spec = importlib.util.spec_from_file_location("decomp_tool", TOOL)
        tool = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(tool)
    finally:
        sys.dont_write_bytecode = kept
    logical = os.cpu_count()
    expect(1 <= tool.cores() <= logical, f"the physical count is {tool.cores()} of {logical} logical cores")

    def fails():
        raise OSError("no such call")
    tool.physical_core_call = fails
    expect(tool.cores() == logical, f"a failing call should give the logical count: {tool.cores()}")
    tool.physical_core_call = lambda: 0
    expect(tool.cores() == logical, f"a call that counts nothing should give the logical count: {tool.cores()}")


PERF_FIELDS = {"unix", "ticket", "round", "block", "wall_s", "call_s", "workers_min", "workers_max", "workers_end", "expanded",
               "compiled", "unique_objects", "build_fail", "killed", "src_dedupe_hits", "t_compile_p50_ms",
               "t_compile_p95_ms", "t_ref_ms", "stage_ms", "idle_frac", "best_score_start", "best_score_end",
               "t_to_best_s", "end_reason", "model_latency_s", "writers_active"}


def perf_log(p):
    f = p.root / ".decomp" / "perf.jsonl"
    return [json.loads(x) for x in f.read_text().splitlines()] if f.exists() else []


def fresh(p, template):
    """Search with the result cache emptied, so the block compiles. Returns (process, summary)."""
    (p.root / ".decomp" / "search-cache.json").unlink(missing_ok=True)
    return search(p, template)


def seed_perf(p, n, **fields):
    """Append n block records of the last record's compiler and unit, as an earlier machine history, each with the
    given fields. A `unit` among them makes it another unit's history."""
    last = perf_log(p)[-1]
    base = {"kind": "block", "compiler": last["compiler"], "unit": last["unit"], "ticket": "other",
            "compiled": 1000000, "wall_s": 1.0, "workers_end": 1,
            "t_compile_p50_ms": 10, "t_compile_p95_ms": 12, "idle_frac": 0.0, "stage_ms": {"compile": 1000, "score": 1},
            "flags": [], "shown": []}
    with (p.root / ".decomp" / "perf.jsonl").open("a") as f:
        for _ in range(n):
            f.write(json.dumps(dict(base, **fields)) + "\n")


def test_search_writes_one_record_per_block_and_one_per_calibration(base):
    p = search_project(base)
    tune(p, workers=2)
    r, out = search(p, NEVER)
    expect(out is not None, "the round should run", r)
    got = perf_log(p)
    expect([x["kind"] for x in got] == ["calibration"] * 4 + ["block"] and [x.get("probe") for x in got[:4]]
           == [None, "single-function", "batching", "resolved-compiler"],
           f"a cold cache calibrates once (the double compile, then one record per probe), then one block: {got}", r)
    rec = got[4]
    expect(PERF_FIELDS <= set(rec), f"the block record lacks {PERF_FIELDS - set(rec)}", r)
    expect(rec["ticket"] == TID and rec["round"] == 1 and rec["block"] == 1 and rec["workers_end"] == 2, f"identity: {rec}", r)
    expect(rec["compiled"] == out["counts"]["compiled"] and rec["end_reason"] == "exhausted", f"counts and end: {rec}", r)
    expect(rec["best_score_end"] == 4 and set(rec["stage_ms"]) == {"write", "compile", "compare", "expand", "score"},
           f"the end score and the five stages: {rec}", r)
    expect(0.0 <= rec["idle_frac"] <= 1.0 and rec["t_compile_p95_ms"] >= rec["t_compile_p50_ms"] > 0, f"timings: {rec}", r)
    probes = sum(x["wall_s"] for x in got[:4])
    expect(probes > 0 and rec["call_s"] >= rec["wall_s"] + probes - 0.02,
           f"call_s covers the calibration ({probes} s) and the block: {rec}", r)
    c = out["counts"]
    expect(c["call_s"] >= rec["call_s"] and c["call_s"] >= c["wall_s"] + probes - 0.02,
           f"the summary's call_s covers the whole call: {c}", r)
    r, out = search(p, NEVER)
    expect(out["counts"]["call_s"] >= out["counts"]["wall_s"], f"call_s is no smaller than wall_s: {out['counts']}", r)
    got = perf_log(p)
    expect([x["kind"] for x in got[4:]] == ["block", "block"] and got[5]["round"] == 2 and got[5]["block"] == 2,
           f"a warm cache adds one block record and no calibration: {got}", r)


def test_search_perf_log_is_never_committed(base):
    p = search_project(base)
    r, out = search(p, NEVER)
    expect(perf_log(p), "the round should log", r)
    tracked = subprocess.run(["git", "ls-files"], cwd=p.root, capture_output=True, text=True).stdout
    status = subprocess.run(["git", "status", "--porcelain"], cwd=p.root, capture_output=True, text=True).stdout
    expect("perf.jsonl" not in tracked and "perf.jsonl" not in status, f"the log stays out of git: {status}", r)


def test_search_raises_slow_compile_for_a_block_30_percent_slower_per_worker(base):
    p = search_project(base)
    tune(p, workers=1)
    search(p, NEVER)
    seed_perf(p, 3)  # 1,000,000 compiles per worker-second
    r, out = fresh(p, NEVER)
    rec = perf_log(p)[-1]
    expect("slow-compile" in rec["flags"], f"a block far below the median should raise slow-compile: {rec}", r)
    seed_perf(p, 3, compiled=1, wall_s=1000.0)  # a median so slow the next block is faster than it
    fresh(p, NEVER)
    expect("slow-compile" not in perf_log(p)[-1]["flags"], "a block faster than the median raises nothing", r)


def test_search_shows_a_flag_raised_three_blocks_in_a_row_once(base):
    p = search_project(base)
    tune(p, workers=1)
    search(p, NEVER)
    seed_perf(p, 12)  # enough fast blocks that the slow ones the loop adds leave the median where it is
    notices = []
    for _ in range(5):
        r, out = fresh(p, NEVER)
        notices.append([n for n in out.get("notice", []) if n.startswith("slow-compile")] or None)
    log = perf_log(p)
    log = [x for x in log if x["kind"] == "block"]
    expect(all("slow-compile" in x["flags"] for x in log[-5:]), f"every block is slow: {[x.get('flags') for x in log]}", r)
    expect(notices[0] is None and notices[1] is None, f"a flag raised once or twice is logged, not shown: {notices}", r)
    expect(notices[2] is not None and len(notices[2]) == 1 and notices[2][0].startswith("slow-compile in 3 blocks in a row")
           and "percent fewer than the median" in notices[2][0] and "blocks of this unit" in notices[2][0]
           and "antivirus" in notices[2][0],
           f"the third in a row is shown with its cost against the unit's history and the user's fix: {notices}", r)
    expect(notices[3] is None and notices[4] is None, f"it is shown once: {notices}", r)
    expect("slow-compile" in log[-3]["shown"] and "slow-compile" not in log[-4]["shown"] + log[-2]["shown"], f"the record says what was shown: {log[-4:]}", r)


OTHER_UNIT = "src/fast.c"  # a unit with no heavy headers, in the seeded history


def test_search_compares_a_block_with_its_own_unit_only(base):
    # Every compile of this unit takes 0.5 s; the history holds another unit's blocks, far faster.
    build = PY + ' "{tools}/wait_build.py" "{source}" "{obj}" "{tools}/built.log"'
    p = search_project(base, config={"build": build}, files={"tools/wait_build.py": WAIT_BUILD_PY.replace("0.3", "0.5")})
    tune(p, workers=1)
    search(p, NEVER)
    seed_perf(p, 8, unit=OTHER_UNIT, t_compile_p50_ms=0.001)
    r, out = fresh(p, NEVER)
    rec = perf_log(p)[-1]
    expect(rec["compiled"] >= 2 and "slow-compile" not in rec["flags"] and "io-jitter" not in rec["flags"],
           f"a slow unit after a fast unit's blocks raises neither flag: {rec}", r)


def test_search_raises_no_slow_compile_before_the_unit_has_enough_blocks(base):
    p = search_project(base)
    tune(p, workers=1)
    search(p, NEVER)  # the unit's first block
    seed_perf(p, 1)  # its second, far faster than the next
    seed_perf(p, 8, unit=OTHER_UNIT)
    r, out = fresh(p, NEVER)
    rec = perf_log(p)[-1]
    expect(rec["compiled"] >= 2 and "slow-compile" not in rec["flags"],
           f"two earlier blocks of the unit are too few, however many another unit has: {rec}", r)


# A fake compiler that takes 2 s over a source that holds a SLOW_ tag and no FAST_ tag, or 5 LATE_ tags.
STARVE_BUILD_PY = SEARCH_BUILD_PY.replace('open(obj, "w")', '''if ("SLOW_" in text and "FAST_" not in text) or text.count("LATE_") >= 5:
    import time
    time.sleep(2)
open(obj, "w")''')
STARVE_FILES = {"tools/search_build.py": STARVE_BUILD_PY}
ONE_SLOW = MARK + ("int f(void) { PERM_GENERAL(int WRONG_a0;, int SLOW_a1; int WRONG_a2;) "
                   "PERM_GENERAL(int WRONG_b0;, int FAST_b1; int WRONG_b2;) return 1; }\n")


def test_search_raises_io_jitter_when_p95_is_far_above_the_blocks_own_median_compile(base):
    p = search_project(base, files=STARVE_FILES)
    tune(p, workers=1)
    search(p, NEVER)
    seed_perf(p, 8, t_compile_p50_ms=1000000)  # a history of compiles far slower than any of this block's
    r, out = fresh(p, ONE_SLOW)  # 4 candidates, one of them 2 s slower than the rest
    rec = perf_log(p)[-1]
    expect("io-jitter" in rec["flags"], f"p95 over 3 times the block's own median raises io-jitter, whatever the history: {rec}", r)


def test_search_raises_scorer_bound_for_a_slow_diff_adapter(base):
    slow_diff = "import time\ntime.sleep(0.3)\n" + SEARCH_DIFF_PY
    p = search_project(base, files={"tools/search_diff.py": slow_diff})
    tune(p, workers=1)
    r, out = search(p, NEVER)
    rec = perf_log(p)[-1]
    stage = rec["stage_ms"]
    expect("scorer-bound" in rec["flags"], f"a diff adapter that takes most of the stage time is flagged: {rec}", r)
    expect(stage["score"] < 0.05 * sum(stage.values()) and stage["compare"] > 0.2 * sum(stage.values()),
           f"the time is the adapter's, not the in-process scoring's: {stage}", r)


def paired(n, tag):
    """A template of n choice points of 2 alternatives: the first's second alternative holds SLOW_, the others' hold tag."""
    return MARK + "int f(void) { PERM_GENERAL(int WRONG_a0;, int SLOW_a1; int WRONG_a2;) " + " ".join(
        f"PERM_GENERAL(int WRONG_{chr(98 + i)}0;, int {tag}_{chr(98 + i)}1; int WRONG_{chr(98 + i)}2;)" for i in range(n - 1)
    ) + " return 1; }\n"


def test_search_raises_expander_starved_when_workers_wait_while_candidates_remain(base):
    p = search_project(base, files=STARVE_FILES)
    tune(p, workers=8, reference_s=0)
    # 32 candidates. The opening sweep's one slow build holds the other 26 back for 2 s, with 7 workers waiting.
    r, out = search(p, paired(5, "FAST"))
    rec = perf_log(p)[-1]
    expect(out is not None and out["end"] == "exhausted" and rec["compiled"] >= 16, f"the block should try the space: {out}", r)
    expect("expander-starved" in rec["flags"] and rec["idle_frac"] > 0.2, f"waiting for candidates that remain is flagged: {rec}", r)


def test_search_raises_no_expander_starved_for_a_small_space_that_ends_exhausted(base):
    p = search_project(base, files=STARVE_FILES)
    tune(p, workers=8, reference_s=0)
    # 32 candidates. The one slow build is not in the sweep: the other workers sit idle for 2 s with nothing left to hand out.
    r, out = search(p, MARK + "int f(void) { " + " ".join(
        f"PERM_GENERAL(int WRONG_{c}0;, int LATE_{c}1; int WRONG_{c}2;)" for c in "abcde") + " return 1; }\n")
    rec = perf_log(p)[-1]
    expect(out is not None and out["end"] == "exhausted" and rec["compiled"] >= 16, f"the block should try the space: {out}", r)
    expect(rec["wall_s"] >= 2 and "expander-starved" not in rec["flags"],
           f"idle time after the last candidate was handed out is not starvation: {rec}", r)


# ---------- calibration probes ----------

# A unit of two marked functions. The fake compiler takes longer while the other function's body is in
# the source, and logs which form it was given. The fake diff reads the target function alone, so
# cutting the other body leaves the bytes as they were; with USES_G in the target, the bytes depend
# on that body being there, which only a candidate shows.
HELPER = "// @decomp u0001-00402000\nint g(void) { SLOW_BODY; return 2; }\n"
TWO_FUNCTIONS = HELPER + MATCHING
CALLS_HELPER = HELPER + MARK + "int f(void) { PERM_GENERAL(int WRONG_a;, int right_a; USES_G;) return 1; }\n"
FORM_BUILD_PY = """import sys, time
src, obj, log = sys.argv[1:4]
text = open(src).read()
whole = "SLOW_BODY" in text
open(log, "a").write(("full" if whole else "cut") + chr(10))
time.sleep(0.3 if whole else 0)
open(obj, "w").write(text)
"""
TARGET_DIFF_PY = """import hashlib, json, sys
text = open(sys.argv[1]).read()
body = text[text.index("int f("):]
n = body.count("WRONG") + ("USES_G" in body and "SLOW_BODY" in text)
open(sys.argv[2], "w").write("report" + chr(10))
print(json.dumps({"match": n == 0, "differ_bytes": 2 * n, "function_sha256": hashlib.sha256(body.encode()).hexdigest()}))
"""
# A fake batch compiler: one call builds every source it is given into the object folder, after a
# wait per call and a wait per source, and logs how many sources the call held.
BATCH_BUILD_PY = """import os, sys, time
objdir, log, per_call, per_source = sys.argv[1:5]
sources, bad = sys.argv[5:], 0
open(log, "a").write("batch %d" % len(sources) + chr(10))
time.sleep(float(per_call) + float(per_source) * len(sources))
for s in sources:
    text = open(s).read()
    if "SYNTAX_ERROR" in text:
        bad = 1
        continue
    open(os.path.join(objdir, os.path.splitext(os.path.basename(s))[0] + ".obj"), "w").write(text)
sys.exit(bad)
"""
WAIT_BUILD_PY = """import sys, time
src, obj, log = sys.argv[1:4]
text = open(src).read()
open(log, "a").write("single" + chr(10))
time.sleep(0.3)
if "SYNTAX_ERROR" in text:
    sys.exit("error C2143: syntax error")
open(obj, "w").write(text)
"""
# A fake resolved compiler: `build_resolve` prints its argument list and one variable, and the compiler
# it names logs each run with that variable. With ALTER it writes other bytes than the build adapter.
RESOLVE_PY = """import json, os, sys
here = os.path.dirname(os.path.abspath(__file__))
print(json.dumps({"argv": [sys.executable, os.path.join(here, "direct_build.py"), "{source}", "{obj}"] + sys.argv[1:],
                  "env": {"RESOLVED": "yes"}}))
"""
DIRECT_BUILD_PY = """import os, sys
src, obj, log = sys.argv[1:4]
open(log, "a").write("resolved " + os.environ.get("RESOLVED", "") + chr(10))
open(obj, "w").write(open(src).read() + ("altered" if "ALTER" in sys.argv[4:] else ""))
"""
BATCHED = MARK + ("int f(void) { PERM_GENERAL(int WRONG_a;, int right_a;) PERM_GENERAL(int WRONG_b;, int right_b;) "
                  "PERM_GENERAL(int WRONG_c;, SYNTAX_ERROR, int right_c;) return 1; }\n")


def probes(p):
    """The performance log's probe records, by probe: the last of each."""
    return {x["probe"]: x for x in perf_log(p) if x["kind"] == "calibration" and "probe" in x}


def form_project(base, diff, helper=HELPER, probe_min_chars=0):
    """A two-function unit whose compiler is faster on the single-function source. Returns (project, the logged forms).

    probe_min_chars is 0 unless a test asks, so the helper's short body is still worth a probe; None leaves the default.
    """
    log = Path(base) / "forms.log"
    p = search_project(base, config={"build": PY + f' "{{tools}}/form_build.py" "{{source}}" "{{obj}}" "{log.as_posix()}"',
                                     "diff": PY + ' "{tools}/probe_diff.py" "{obj}" "{report}"'},
                       files={"tools/form_build.py": FORM_BUILD_PY, "tools/probe_diff.py": diff},
                       source=helper + STUCK)
    tune(p, workers=1, **({} if probe_min_chars is None else {"probe_min_chars": probe_min_chars}))
    return p, lambda: log.read_text().split() if log.exists() else []


def test_search_rejects_a_single_function_build_that_changes_the_bytes(base):
    p, forms = form_project(base, COUNT_DIFF_PY)  # this diff hashes the whole object, so the cut shows in the bytes
    r, out = search(p, TWO_FUNCTIONS)
    got = probes(p).get("single-function", {})
    expect(got.get("outcome") == "dropped" and got.get("identical") is False and "bytes changed" in got.get("reason", ""),
           f"the probe should drop the single-function build: {got}", r)
    expect(got["t_probe_ms"] < got["t_ref_ms"], f"though it was faster: {got}", r)
    expect(out is not None and out["end"] == "match" and out["counts"]["single_function"] is False, f"the round runs: {out}", r)
    expect(forms().count("cut") == 2 and forms()[-out["counts"]["compiled"]:] == ["full"] * out["counts"]["compiled"],
           f"only the probe's two builds were cut, and every candidate was built whole: {forms()}", r)


def test_search_keeps_a_single_function_build_that_is_faster_and_byte_identical(base):
    p, forms = form_project(base, TARGET_DIFF_PY)
    r, out = search(p, TWO_FUNCTIONS)
    got = probes(p).get("single-function", {})
    expect(got.get("outcome") == "kept" and got.get("identical") is True, f"the probe should keep it: {got}", r)
    expect(out is not None and out["end"] == "match" and out["best"] == {"code": "A1 B2", "differ_bytes": 0}
           and out["counts"]["single_function"] is True, f"the round matches under the single-function build: {out}", r)
    built = out["counts"]["compiled"]
    expect(forms()[-built - 1:] == ["cut"] * built + ["full"],
           f"candidates are built cut, and the match is confirmed on the full unit: {forms()}", r)
    winner = Path(out["winner"]).read_text()
    expect("SLOW_BODY" in winner, "the winner is the whole unit, not the cut source", r)
    before = len(forms())
    r, out = search(p, TWO_FUNCTIONS.replace("int right_b;", "int right_b2;"))
    expect("full" not in forms()[before:-1] and len([x for x in perf_log(p) if x.get("probe")]) == 3,
           f"a later round keeps the answer without probing again: {forms()[before:]}", r)


def test_search_drops_the_single_function_build_when_its_match_fails_on_the_full_unit(base):
    p, forms = form_project(base, TARGET_DIFF_PY)
    r, out = search(p, CALLS_HELPER)
    log = [x for x in perf_log(p) if x.get("probe") == "single-function"]
    expect([x["outcome"] for x in log] == ["kept", "dropped"] and "did not hold" in log[1]["reason"],
           f"the baseline kept it, the match dropped it: {log}", r)
    expect(out is not None and out["end"] == "exhausted" and "winner" not in out and out["best"]["differ_bytes"] == 2
           and out["counts"]["single_function"] is False, f"the round reports the full unit's result: {out}", r)
    before = len(forms())
    r, out = search(p, CALLS_HELPER.replace("USES_G;", "USES_G; int other;"))
    expect("cut" not in forms()[before:], f"the next round builds the full unit: {forms()[before:]}", r)


# A helper whose body holds more text than the default threshold of the single-function probe.
LONG_HELPER = HELPER.replace("SLOW_BODY;", "SLOW_BODY; " + "int pad; " * 250)
HELPER_BODY = len(HELPER[HELPER.index("{"):HELPER.index("}") + 1])


def test_search_skips_the_single_function_probe_when_there_is_too_little_to_cut(base):
    p, forms = form_project(base, TARGET_DIFF_PY, probe_min_chars=None)
    r, out = search(p, TWO_FUNCTIONS)
    got = probes(p).get("single-function", {})
    expect(got.get("outcome") == "skipped" and f"{HELPER_BODY} characters" in got.get("reason", "")
           and "2000" in got.get("reason", ""), f"the probe should be skipped, naming the text it would cut: {got}", r)
    expect("cut" not in forms(), f"no single-function build was run: {forms()}", r)
    expect(out is not None and out["end"] == "match" and out["counts"]["single_function"] is False, f"the round runs: {out}", r)


def test_search_probes_the_single_function_build_when_there_is_enough_to_cut(base):
    p, forms = form_project(base, TARGET_DIFF_PY, helper=LONG_HELPER, probe_min_chars=None)
    r, out = search(p, LONG_HELPER + MATCHING)
    got = probes(p).get("single-function", {})
    expect(got.get("outcome") == "kept" and got.get("identical") is True, f"the probe should run and keep it: {got}", r)
    expect(out is not None and out["end"] == "match" and out["counts"]["single_function"] is True, f"the round runs: {out}", r)
    (Path(base) / "changed").mkdir()
    p, forms = form_project(Path(base) / "changed", COUNT_DIFF_PY, helper=LONG_HELPER, probe_min_chars=None)
    r, out = search(p, LONG_HELPER + MATCHING)
    got = probes(p).get("single-function", {})
    expect(got.get("outcome") == "dropped" and "bytes changed" in got.get("reason", ""),
           f"the probe should run and drop it: {got}", r)


def test_search_takes_the_single_function_probes_threshold_from_local_json(base):
    p, forms = form_project(base, TARGET_DIFF_PY, helper=LONG_HELPER, probe_min_chars=5000)
    r, out = search(p, LONG_HELPER + MATCHING)
    got = probes(p).get("single-function", {})
    expect(got.get("outcome") == "skipped" and "5000" in got.get("reason", "") and "cut" not in forms(),
           f"a higher threshold skips the long unit: {got} {forms()}", r)
    tune(p, workers=1, probe_min_chars=HELPER_BODY)
    r, out = search(p, LONG_HELPER + MATCHING.replace("int right_b;", "int right_b2;"))
    got = probes(p).get("single-function", {})
    expect(got.get("outcome") == "kept", f"lowering the threshold probes the same unit again: {got}", r)
    (Path(base) / "short").mkdir()
    p, forms = form_project(Path(base) / "short", TARGET_DIFF_PY, probe_min_chars=HELPER_BODY)
    r, out = search(p, TWO_FUNCTIONS)
    got = probes(p).get("single-function", {})
    expect(got.get("outcome") == "kept" and "cut" in forms(),
           f"a threshold no higher than the text to cut runs the probe on the short unit: {got}", r)


def batch_project(base, per_call, per_source):
    log = Path(base) / "calls.log"
    batch = PY + f' "{{tools}}/batch_build.py" "{{objdir}}" "{log.as_posix()}" {per_call} {per_source} {{sources}}'
    p = search_project(base, config={"build": PY + f' "{{tools}}/slow_build.py" "{{source}}" "{{obj}}" "{log.as_posix()}"',
                                     "build_batch": batch},
                       files={"tools/batch_build.py": BATCH_BUILD_PY, "tools/slow_build.py": WAIT_BUILD_PY})
    tune(p, workers=1)
    return p, lambda: log.read_text().splitlines()


def test_search_keeps_batching_that_is_faster_and_byte_identical(base):
    p, calls = batch_project(base, 0.3, 0)  # one wait per call, however many sources: a batch is cheaper per candidate
    r, out = search(p, BATCHED)
    got = probes(p).get("batching", {})
    expect(got.get("outcome") == "kept" and got.get("batch") == 16 and set(got["sizes_ms"]) == {"4", "8", "16"}
           and got["t_probe_ms"] < got["t_ref_ms"], f"the probe should keep batches of 16: {got}", r)
    expect(out is not None and out["end"] == "match" and out["best"] == {"code": "A1 B1 C2", "differ_bytes": 0}
           and out["counts"]["batch"] == 16, f"the batched round finds the match: {out}", r)
    expect([x for x in calls() if x.startswith("batch")] == ["batch 4", "batch 8", "batch 16", "batch 5", "batch 7"],
           f"after the probe, the sweep is one compiler call and the rest another: {calls()}", r)
    expect(calls().count("single") == 6,  # the gate's check, the double compile, and the probes' three reference builds
           f"no candidate of the block was built singly: {calls()}", r)
    expect(out["counts"]["compiled"] == 12 and out["counts"]["build_fail"] == 4,
           f"a candidate that fails in a batch fails alone: {out['counts']}", r)


def test_search_drops_batching_that_is_slower(base):
    p, calls = batch_project(base, 0, 0.5)  # a longer wait per source than a single build takes
    r, out = search(p, BATCHED)
    got = probes(p).get("batching", {})
    expect(got.get("outcome") == "dropped" and got.get("batch") == 1 and "not faster" in got.get("reason", ""),
           f"the probe should drop batching: {got}", r)
    expect(out is not None and out["end"] == "match" and out["counts"]["batch"] == 1, f"the round runs unbatched: {out}", r)
    expect([x for x in calls() if x.startswith("batch")] == ["batch 4"], f"no block build is batched: {calls()}", r)


def test_search_records_each_probe_and_skips_those_the_adapters_do_not_support(base):
    p = search_project(base)
    r, out = search(p, MATCHING)
    got = probes(p)
    expect(set(got) == {"single-function", "batching", "resolved-compiler"}, f"one record per probe: {perf_log(p)}", r)
    expect(all(x["outcome"] == "skipped" and x["kind"] == "calibration" and x["ticket"] == TID for x in got.values()),
           f"a one-function unit and adapters without the two modes skip all three: {got}", r)
    expect("build_resolve" in got["resolved-compiler"]["reason"] and "build_batch" in got["batching"]["reason"],
           f"each skip gives its reason: {got}", r)
    expect(out is not None and out["counts"]["single_function"] is False and out["counts"]["batch"] == 1, "the round runs", r)


def resolve_project(base, *more):
    log = Path(base) / "resolved.log"
    args = "".join(f' "{x}"' for x in (log.as_posix(),) + more)
    p = search_project(base, config={"build": PY + f' "{{tools}}/slow_build.py" "{{source}}" "{{obj}}" "{log.as_posix()}"',
                                     "build_resolve": PY + ' "{tools}/resolve.py"' + args},
                       files={"tools/resolve.py": RESOLVE_PY, "tools/direct_build.py": DIRECT_BUILD_PY,
                              "tools/slow_build.py": WAIT_BUILD_PY})
    tune(p, workers=1)
    return p, lambda: [x for x in log.read_text().splitlines() if x.startswith("resolved")]


def test_search_probes_the_resolved_compiler_and_records_it_without_using_it(base):
    p, resolved = resolve_project(base)
    r, out = search(p, MATCHING)
    got = probes(p).get("resolved-compiler", {})
    expect(got.get("outcome") == "eligible" and got.get("identical") is True and got["t_probe_ms"] < got["t_ref_ms"],
           f"a faster byte-identical resolved compiler is recorded as eligible: {got}", r)
    expect(resolved() == ["resolved yes"] * 2, f"it ran with the adapter's environment, in the probe only: {resolved()}", r)
    expect(out is not None and out["end"] == "match", f"the block builds through the build adapter: {out}", r)


def test_search_drops_a_resolved_compiler_that_changes_the_bytes(base):
    p, resolved = resolve_project(base, "ALTER")
    r, out = search(p, MATCHING)
    got = probes(p).get("resolved-compiler", {})
    expect(got.get("outcome") == "dropped" and got.get("identical") is False, f"other bytes drop the mode: {got}", r)
    expect(out is not None and out["end"] == "match", f"the round runs: {out}", r)


# ---------- template search: self-tuning workers and the reference compile ----------

# A fake compiler that is fast until more than `limit` workers run: each build marks its worker's folder
# as it starts and as it ends, and a build that starts with more than `limit` folders marked in the last
# 1.5 seconds takes ten times as long.
LIMIT_BUILD_PY = """import hashlib, os, sys, time
src, obj, folder, limit = sys.argv[1:5]
os.makedirs(folder, exist_ok=True)
me = os.path.join(folder, hashlib.sha256(os.path.dirname(os.path.abspath(obj)).encode()).hexdigest())
open(me, "w").close()
ages = []
for name in os.listdir(folder):
    try:
        ages.append(time.time() - os.path.getmtime(os.path.join(folder, name)))
    except OSError:
        pass
time.sleep(1.0 if sum(age < 1.5 for age in ages) > int(limit) else 0.1)
open(me, "w").close()
open(obj, "w").write(open(src).read())
"""
# A fake compiler that throttles the baseline of `wide(10)`: its first two builds (the start-of-search
# double compile) are fast like every other candidate, and each later one takes 1.5 seconds longer.
THROTTLE_BUILD_PY = """import re, sys, time
src, obj, log = sys.argv[1:4]
text = open(src).read()
if "WRONG_j0" in text and not re.search(r"WRONG_[a-j]1", text):
    open(log, "a").write("baseline" + chr(10))
    if len(open(log).read().splitlines()) > 2:
        time.sleep(1.5)
open(obj, "w").write(text)
"""


def test_search_worker_count_settles_near_the_count_the_compiler_is_fast_at(base):
    folder = Path(base) / "limit"
    build = PY + f' "{{tools}}/limit_build.py" "{{source}}" "{{obj}}" "{folder.as_posix()}" 4'
    p = search_project(base, config={"build": build}, files={"tools/limit_build.py": LIMIT_BUILD_PY})
    # 3 cores start 3 workers on a pool of 8 slots. The wide noise band and the long spread keep the
    # count from moving on anything but the tenfold slowdown, whatever else this machine is doing.
    tune(p, cores=3, slots=8, tune_s=1, tune_gain=0.15, tune_loss=0.3, tune_spread=50, reference_s=0, deadline_s=9)
    r, out = search(p, wide(10))
    expect(out is not None and out["end"] == "deadline" and out["counts"]["workers"] == 3, f"the block starts 3 workers: {out}", r)
    rec = perf_log(p)[-1]
    expect(rec["workers_min"] >= 1 and rec["workers_max"] >= 4, f"the count should climb from 3 to the 4 the compiler is fast at: {rec}", r)
    expect(3 <= rec["workers_end"] <= 5, f"the count should end near 4, it ended at {rec['workers_end']}: {rec}", r)
    expect("starved-by-writers" not in rec["flags"] and "contention-or-throttle" not in rec["flags"],
           f"a block with the pool to itself and no reference compile raises neither tuning flag: {rec}", r)


def test_search_sheds_workers_and_flags_contention_when_the_reference_compile_slows(base):
    log = Path(base) / "baseline.log"
    build = PY + f' "{{tools}}/throttle_build.py" "{{source}}" "{{obj}}" "{log.as_posix()}"'
    p = search_project(base, config={"build": build}, files={"tools/throttle_build.py": THROTTLE_BUILD_PY})
    tune(p, cores=4, tune_s=60, reference_s=0.5, deadline_s=4)  # the tick never comes: only the reference moves the count
    r, out = search(p, wide(10))
    expect(out is not None and out["end"] == "deadline", f"the block should run to its deadline: {out}", r)
    rec = perf_log(p)[-1]
    expect(len(log.read_text().splitlines()) >= 4, "the baseline is built again as the reference, after the block built it", r)
    expect("contention-or-throttle" in rec["flags"], f"a reference compile far slower than the block's first compiles is flagged: {rec}", r)
    expect(rec["t_ref_max_ms"] > 1.3 * rec["t_ref_base_ms"] > 0 and rec["t_ref_ms"] >= 1500, f"the record holds both times: {rec}", r)
    expect(rec["workers_max"] == 4 and rec["workers_end"] == 2 and rec["workers_min"] == 2,
           f"the 4 workers should be halved: {rec}", r)


def test_search_flags_a_block_the_pool_holds_below_its_worker_floor(base):
    p = search_project(base)
    tune(p, cores=8)
    writer(p, "333-cafe", -3600)
    held = [hold_slot(p, i, "333-cafe") for i in range(1, 8)]  # another live writer holds 7 of the 8 slots
    r, out = search(p, wide(4))
    expect(out is not None and out["end"] == "exhausted" and out["counts"]["workers"] == 4, f"two writers on 8 cores: {out}", r)
    rec = perf_log(p)[-1]
    expect(rec["workers_floor"] == 2 and rec["starved_frac"] > 0.5, f"one free slot is below the floor of 2 workers: {rec}", r)
    expect("starved-by-writers" in rec["flags"], f"the block should be flagged as starved: {rec}", r)
    for slot in held:
        slot.unlink()
    r, out = fresh(p, wide(4))
    rec = perf_log(p)[-1]
    expect(rec["starved_frac"] == 0 and "starved-by-writers" not in rec["flags"], f"with its share free it is not starved: {rec}", r)


def test_search_shows_a_tuning_flag_with_the_fix_only_the_user_can_make(base):
    p = search_project(base)
    tune(p, cores=8)
    writer(p, "333-cafe", -3600)
    for i in range(1, 8):
        hold_slot(p, i, "333-cafe")
    notices = []
    for _ in range(3):
        r, out = fresh(p, wide(3))
        notices.append([n for n in out.get("notice", []) if n.startswith("starved-by-writers")])
    expect(notices[0] == [] and notices[1] == [] and len(notices[2]) == 1, f"the third starved block in a row is shown: {notices}", r)
    expect("floor of 2 workers" in notices[2][0] and "concurrent writer count" in notices[2][0],
           f"with its cost and the user's fix: {notices[2]}", r)


# A fake `wineserver` that logs each start and then idles until it is killed. Linux and macOS only: Windows
# has no Wine and no `sh` to run it.
FAKE_WINESERVER = "#!/bin/sh" + chr(10) + 'echo "$@" >> "$WINESERVER_LOG"' + chr(10) + "exec sleep 60" + chr(10)


def wine_project(base, wine=True):
    """A search project on a host that runs its toolchain under Wine, with a fake wineserver first on PATH."""
    m = legacy_manifest()
    if wine:
        m["prerequisites"] = [{"name": "wine", "version_cmd": "echo wine-8", "version": "wine-8", "hosts": HERE}]
    p = search_project(base, manifest=m)
    fake = Path(base) / "fake-wine"
    fake.mkdir()
    (fake / "wineserver").write_text(FAKE_WINESERVER, encoding="utf-8")
    (fake / "wineserver").chmod(0o755)
    log = Path(base) / "wineserver.log"
    p.env = {"PATH": str(fake) + os.pathsep + os.environ["PATH"], "WINESERVER_LOG": str(log)}
    return p, log


def search_with_env(p, template):
    path = p.base / "template.c"
    path.write_text(template, encoding="utf-8")
    r = p.run("search", TID, str(path), env=p.env)
    return r, json.loads(r.stdout.splitlines()[0])


def test_search_starts_one_wineserver_per_block_not_per_candidate(base):
    if sys.platform == "win32":
        print("SKIP: Windows runs the tools natively and has no wineserver, so the Wine path cannot run here")
        return
    p, log = wine_project(base)
    r, out = search_with_env(p, MATCHING)
    expect(out["counts"]["compiled"] > 1, f"the block should compile several candidates: {out}", r)
    started = log.read_text(encoding="utf-8").splitlines() if log.exists() else []
    expect(started == ["-f -p"], f"one persistent wineserver per block, not per candidate: {started}", r)
    r, out = search_with_env(p, MATCHING)
    expect(len(log.read_text(encoding="utf-8").splitlines()) == 2, "a second block starts its own wineserver", r)


def test_search_starts_no_wineserver_when_the_toolchain_does_not_use_wine(base):
    if sys.platform == "win32":
        print("SKIP: Windows runs the tools natively and has no wineserver, so the Wine path cannot run here")
        return
    p, log = wine_project(base, wine=False)
    r, out = search_with_env(p, MATCHING)
    expect(out["end"] == "match" and not log.exists(), "no wine prerequisite, no wineserver", r)


# ---------- template search: learning across rounds, mutation, crossover, and stop advice ----------

def learn_template(b="tag_b", note=""):
    """Two choice points. Alternative 2 of each has one WRONG, alternative 0 two, alternative 1 three: 2 is the one that helps."""
    return in_function(
        "PERM_GENERAL(tag_a0 WRONG_1 WRONG_2, tag_a1 WRONG_1 WRONG_2 WRONG_3, tag_a2 WRONG_1) "
        f"PERM_GENERAL({b}0 WRONG_4 WRONG_5, {b}1 WRONG_4 WRONG_5 WRONG_6, {b}2 WRONG_4) {note}")


def two_rounds(base, second, first=None, **constants):
    """Run two rounds on one worker. Returns (the second summary, the candidates the second round built, in order)."""
    log = Path(base) / "order.log"
    p = search_project(base, files={"tools/search_build.py": ORDER_BUILD_PY.replace("LOG", repr(str(log)))})
    tune(p, workers=1, **constants)
    r, out = search(p, first or learn_template())
    expect(out is not None, "the first round should print a summary", r)
    built = len(log.read_text().splitlines())
    cache = p.root / ".decomp" / "search-cache.json"
    if cache.exists():
        cache.unlink()  # the second round builds what it tries instead of reading the first's results
    r, out = search(p, second)
    expect(out is not None, "the second round should print a summary", r)
    return r, out, log.read_text().splitlines()[built:]


def singles(order):
    """The alternative each one-change candidate of a round changes, in build order."""
    return [next(x for x in line.split() if not x.endswith("0")) for line in order[1:] if len([x for x in line.split() if not x.endswith("0")]) == 1]


def test_search_second_round_starts_a_kept_label_from_what_the_first_learned(base):
    r, out, order = two_rounds(base, learn_template(note="/* round two */"))
    got = singles(order)[:4]
    expect(got.index("tag_a2") < got.index("tag_a1") and got.index("tag_b2") < got.index("tag_b1"),
           f"both kept choice points should try the alternative that helped before the one that hurt: {got}", r)
    expect(got[:2] and {got[0], got[1]} == {"tag_a2", "tag_b2"}, f"the helpful alternatives lead the sweep: {got}", r)


def test_search_second_round_resets_an_edited_label_to_its_priors(base):
    r, out, order = two_rounds(base, learn_template(b="tag_e", note="/* round two */"))
    got = singles(order)[:4]
    expect(got == ["tag_a2", "tag_e1", "tag_e2", "tag_a1"],
           f"A keeps what it learned and the edited B is back at uniform priors, in template order: {got}", r)


def test_search_mutation_and_crossover_only_combine_the_written_alternatives(base):
    r, out, order = two_rounds(base, grid(6), first=grid(6), budget=60)
    arms = out["counts"].get("arm_picks")
    expect(arms and arms["mutate"] > 0 and arms["cross"] > 0, f"the second round should mutate and cross over: {out['counts']}", r)
    for line in order:
        words = line.split()
        expect([w[4] for w in words] == list("abcdef") and all(w[5] in "012" for w in words),
               f"every candidate holds one written alternative of each choice point: {line}", r)


def test_search_first_round_of_a_template_neither_mutates_nor_crosses_over(base):
    log = Path(base) / "order.log"
    p = search_project(base, files={"tools/search_build.py": ORDER_BUILD_PY.replace("LOG", repr(str(log)))})
    tune(p, workers=1, budget=40)
    r, out = search(p, grid(6))
    expect(out is not None and "arm_picks" not in out["counts"], f"a first block has no parents: {out}", r)


def load_tool():
    """decomp.py as a module, for the one rule no command line can set up: how the samplers' shares move."""
    import importlib.util
    kept, sys.dont_write_bytecode = sys.dont_write_bytecode, True
    try:
        spec = importlib.util.spec_from_file_location("decomp_tool", TOOL)
        tool = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(tool)
    finally:
        sys.dont_write_bytecode = kept
    return tool


def share_of_arms(tool, rewarded, picks=150):
    """Run the arms for `picks` picks where only candidates of the `rewarded` sampler bring the best score down."""
    import random
    template = tool.parse_template(grid(6))
    rng = random.Random(3)
    sampler = tool.Sampler(template, set(), [0], None, rng)
    parents = [(1000.0, f"o{i}", v) for i, v in enumerate(([1] * 6, [2] * 6, [0, 1, 2, 0, 1, 2]))]
    arms = tool.Arms(sampler, parents, rng)
    results, best = [{"seed": 0, "differ_bytes": 1000.0, "object": "o-base"}], 1000.0
    for _ in range(picks):
        sampler.learn(results)
        arms.learn(results)
        seed = arms.pick()
        d = best * 0.95 if arms.owner[seed] == rewarded else 5000.0
        best = min(best, d)
        # A rewarded candidate carries no object hash, so it never becomes a parent: the parents stay
        # as diverse as they began, and only the share each sampler earns by its gains is measured.
        results.append({"seed": seed, "differ_bytes": d, "object": None if d < 5000.0 else f"s{seed}"})
    return arms.picked


def test_search_gives_a_sampler_that_keeps_finding_gains_a_larger_share_of_the_compiles(base):
    tool = load_tool()
    for winner in ("mutate", "cross"):
        got = share_of_arms(tool, winner)
        others = [n for a, n in got.items() if a != winner]
        expect(got[winner] > 1.5 * max(others), f"the sampler that finds gains should lead: {got}")
        expect(min(others) >= 0.05 * sum(got.values()), f"a sampler that fell behind keeps a share: {got}")


def test_search_advises_stopping_after_two_rounds_with_no_new_best_score(base):
    p = search_project(base)
    r, out = search(p, NEVER)
    expect(out is not None and "stop" not in out, f"one flat round is no reason to stop: {out}", r)
    r, out = search(p, wide(2))
    expect(out is not None and "no new best" in out.get("stop", ""), f"two flat rounds should carry stop advice: {out}", r)
    expect("repeat" not in out, f"a round that built its candidates is no repeat: {out}", r)
    r, out = search(p, MATCHING)
    expect(out is not None and out["end"] == "match" and "stop" not in out, f"a round that matches carries none: {out}", r)


# ---------- template search: a round with nothing new ----------

# NEVER with one more alternative: four of its six candidates are NEVER's own, and two are new.
NEVER_AND_MORE = NEVER.replace("int WRONG_c;)", "int WRONG_c;, int WRONG_h; int WRONG_i; int WRONG_j;)", 1)


def test_search_refuses_a_template_with_no_choice_point_before_any_build(base):
    p, builds = counting_project(base)
    built = builds()
    r, out = search(p, STUCK)
    expect(r.returncode != 0 and out is None, "a plain source file is no template", r)
    expect("choice point" in r.stderr and "check" in r.stderr,
           f"the message names the missing choice point and points to check: {r.stderr!r}", r)
    expect(builds() == built, "nothing is built for it", r)
    expect(len(trail(p)) == 1, f"and it is no attempt: {trail(p)}", r)
    r, out = search(p, MARK + "int f(void) { PERM_IGNORE(int WRONG_now;) return 1; }\n")
    expect(r.returncode != 0 and "choice point" in r.stderr, "PERM_IGNORE is no choice point either", r)
    expect(builds() == built, "nothing is built for it", r)


def test_search_marks_a_second_run_of_an_unchanged_template_a_repeat(base):
    p, builds = counting_project(base)
    r, first = search(p, TWINS)
    expect(first is not None and "repeat" not in first, f"the first run builds, so it is no repeat: {first}", r)
    built, before = builds(), trail(p)
    r, again = search(p, TWINS)
    expect(again is not None and again.get("repeat") is True, f"the second run should be marked a repeat: {again}", r)
    expect(builds() == built and again["counts"]["compiled"] == 0, "a repeat builds nothing", r)
    expect(again["best"] == first["best"], "a repeat still returns its summary", r)
    expect(trail(p) == before, f"a repeat adds no record to the check trail: {trail(p)}", r)


def test_search_repeats_do_not_count_towards_stop_advice(base):
    p = search_project(base)
    r, out = search(p, NEVER)
    expect(out is not None and "stop" not in out and "repeat" not in out, f"one real round: {out}", r)
    for _ in range(2):
        r, out = search(p, NEVER)
        expect(out is not None and out.get("repeat") is True and "stop" not in out,
               f"a repeat run gives no stop advice: {out}", r)
    expect([e["by"] for e in trail(p)] == ["check", "search"], f"the repeats are no attempts: {trail(p)}", r)
    r, out = search(p, wide(2))
    expect(out is not None and "repeat" not in out and "no new best" in out.get("stop", ""),
           f"a second real round with no new best score still carries stop advice: {out}", r)


def test_search_round_that_builds_one_new_candidate_is_no_repeat(base):
    p = search_project(base)
    r, out = search(p, NEVER)
    expect(out is not None and out["counts"]["compiled"] == 4, f"the first round builds its four candidates: {out}", r)
    r, out = search(p, NEVER_AND_MORE)
    expect(out is not None and out["counts"]["cache_hits"] == 4 and out["counts"]["compiled"] == 2,
           f"four candidates come from the cache and two are built: {out and out['counts']}", r)
    expect("repeat" not in out, f"a round that builds a candidate is no repeat: {out}", r)
    expect([e["by"] for e in trail(p)] == ["check", "search", "search"], f"it counts as an attempt: {trail(p)}", r)
    expect("no new best" in out.get("stop", ""), f"and towards stop advice, as before: {out}", r)


def test_search_repeat_starts_no_background_search(base):
    p = search_project(base, config={"build": PY + ' "{tools}/bare_build.py" "{source}" "{obj}"'},
                       files={"tools/bare_build.py": BARE_BUILD_PY})
    template = wide(8, ("/* {c}0 */", "/* {c}1 */"))
    tune(p, workers=1, plateau_compiles=8)
    r, out = search(p, template)
    expect(out is not None and out["end"] == "plateau" and out["counts"]["compiled"] == 9,
           f"the first round ends on a plateau after its sweep: {out}", r)
    time.sleep(2)  # the time the model took: what a background search would have to run in
    tune(p, workers=1, plateau_compiles=8, background=1)
    try:
        r, out = search(p, template)
        expect(out is not None and out["end"] == "plateau" and out.get("repeat") is True,
               f"the same template ends on the same plateau, from the cache: {out}", r)
        expect("continues_s" not in out and not background_folder(p).exists(),
               f"a repeat leaves no background search: {out}", r)
    finally:
        stop_background(p)


# ---------- template search: background search ----------

# A fake compiler that takes 0.3 s and logs when each build starts and ends, with the TAG_ word its
# source holds. On a candidate holding HANG it first starts a grandchild that keeps adding to a
# heartbeat file for up to 30 seconds, then hangs.
BG_BUILD_PY = """import os, re, subprocess, sys, time
src, obj, folder = sys.argv[1:4]
text = open(src).read()
tag = (re.findall(r"TAG_([a-z]+)", text) or ["none"])[0]
os.makedirs(folder, exist_ok=True)
def note(what):
    open(os.path.join(folder, "builds.log"), "a").write("%s %s %.3f%s" % (tag, what, time.time(), chr(10)))
note("start")
if "HANG" in text:
    code = "import sys, time" + chr(10) + "for i in range(300):" + chr(10) + "    open(sys.argv[1], 'a').write('x')" + chr(10) + "    time.sleep(0.1)"
    subprocess.Popen([sys.executable, "-c", code, os.path.join(folder, "beat")])
    time.sleep(60)
time.sleep(0.3)
open(obj, "w").write(text)
note("end")
"""
# The sweep builds the baseline, then each alternative in turn: the one that hangs is the fourth build.
HANGING = MARK + ("int f(void) { PERM_GENERAL(int WRONG_a;, int WRONG_b; int WRONG_c;, "
                  "int WRONG_d; int WRONG_e; int WRONG_f;, int HANG;) return 1; }\n")


def background_project(base, folder=None, **search):
    """A search project with the slow fake compiler, whose blocks end after half a second and search on in the background."""
    folder = Path(folder or Path(base) / "bg")
    build = PY + f' "{{tools}}/bg_build.py" "{{source}}" "{{obj}}" "{folder.as_posix()}"'
    p = search_project(base, config={"build": build}, files={"tools/bg_build.py": BG_BUILD_PY})
    tune(p, **dict({"workers": 1, "deadline_s": 0.5, "ceiling_s": 30, "background": 1}, **search))
    return p


def background_folder(p):
    return p.root / ".decomp" / "search" / TID / "background"


def background_tried(p):
    """How many candidates the running background search has written down."""
    f = background_folder(p) / "results.jsonl"
    return len(f.read_text().splitlines()) if f.exists() else 0


def wait_for(cond, seconds=40):
    end = time.time() + seconds
    while time.time() < end:
        if cond():
            return True
        time.sleep(0.1)
    return False


def stop_background(p, **kw):
    """Stop a project's background search. Returns (process, what it reports or None)."""
    r = p.run("search", TID, "--stop", **kw)
    try:
        return r, json.loads(r.stdout.splitlines()[0])["background"]
    except (ValueError, IndexError, KeyError):
        return r, None


def test_search_returns_while_its_background_search_goes_on(base):
    p = background_project(base)
    began = time.time()
    r, out = search(p, wide(8))
    took = time.time() - began
    try:
        expect(out is not None and out["end"] == "deadline", f"the block should end on its deadline: {out}", r)
        expect(0 < out.get("continues_s", 0) <= 30, f"the summary says the search goes on, up to the ceiling: {out}", r)
        expect(took < 20, f"search should return long before the 30 s ceiling, it took {took:.1f} s", r)
        before = background_tried(p)
        expect(wait_for(lambda: background_tried(p) >= before + 2), "the background search should keep building candidates")
        expect(not (background_folder(p) / "done.json").exists(), "and still be running")
    finally:
        stop_background(p)


def test_the_next_search_reports_what_the_background_search_found(base):
    p = background_project(base)
    try:
        r, out = search(p, wide(8))
        expect(out is not None and out.get("continues_s"), f"the search should go on in the background: {out}", r)
        expect(wait_for(lambda: background_tried(p) >= 2), "the background search should build candidates")
        tune(p, workers=1)
        r, out = search(p, NEVER)
        expect(out is not None and out["end"] == "exhausted" and out["best"] == {"code": "A1 B0", "differ_bytes": 4},
               f"the new template is searched as usual: {out}", r)
        found = out.get("background")
        expect(found is not None and found["end"] == "stopped" and found["tried"] >= 2,
               f"the summary reports the background search, stopped by this call: {out}", r)
        picks = [int(word[1:]) for word in found["best"]["code"].split()]
        expect(found["best"]["differ_bytes"] == 20 and len(picks) == 8 and sum(picks) == 1,
               f"its best is a one-change candidate of the old template: {found}", r)
        expect(not background_folder(p).exists(), "the background search's files are cleared away")
        r, out = search(p, NEVER)
        expect(out is not None and "background" not in out, f"a background search is reported once: {out}", r)
    finally:
        stop_background(p)


def test_a_natural_match_found_in_the_background_is_returned_and_the_new_template_dropped(base):
    p = background_project(base)
    try:
        r, out = search(p, MATCHING)
        expect(out is not None and out["end"] == "deadline" and out.get("continues_s"),
               f"the block should end before it reaches the match: {out}", r)
        expect(wait_for(lambda: (background_folder(p) / "done.json").exists()), "the background search should end on the match")
        attempts = len(trail(p))
        tune(p, workers=1)
        r, out = search(p, NEVER)
        expect(out is not None and out["end"] == "match" and out["best"] == {"code": "A1 B2", "differ_bytes": 0},
               f"the call returns the background's match, named in the old template's choices: {out}", r)
        expect(Path(out["winner"]).read_text() == MARK + "int f(void) { int right_a; int right_b; return 1; }\n",
               "the winner is the old template's matching candidate", r)
        expect(out["background"]["natural"] is True and "discarded" in out["background"],
               f"the summary says the new template was not searched: {out}", r)
        expect(len(trail(p)) == attempts, "the dropped template is no attempt")
        r = p.run("search", TID, "--detail", "A1 B2")
        expect(r.returncode == 0 and json.loads(r.stdout.splitlines()[0])["result"] == "bytes-match",
               "the kept round is still the old template's, with the background's results", r)
    finally:
        stop_background(p)


def hung_background(base):
    """A project whose background search is stuck in a compile that hangs. Returns (project, the grandchild's heartbeat)."""
    p = background_project(base)
    beat = Path(base) / "bg" / "beat"
    r, out = search(p, HANGING)
    expect(out is not None and out.get("continues_s"), f"the search should go on in the background: {out}", r)
    if not wait_for(lambda: beat.exists() and beat.stat().st_size > 0):
        stop_background(p)
        expect(False, "the background search should reach the compile that hangs")
    return p, beat


def expect_background_dead(p, beat, r):
    size = beat.stat().st_size
    time.sleep(0.6)
    expect(beat.stat().st_size == size, "the compile's grandchild should be dead: its heartbeat still grows", r)
    expect(not background_folder(p).exists(), "the background search's files are cleared away", r)
    left = sorted(f.name for f in slot_folder(p).iterdir())
    expect(left == [], f"the background search should hold no slot and no heartbeat in the pool: {left}", r)


def test_search_stop_ends_the_background_search_and_its_children(base):
    p, beat = hung_background(base)
    r, found = stop_background(p)
    expect(r.returncode == 0 and found is not None and found["end"] == "stopped" and found["tried"] >= 1,
           f"the stop form reports what the background search found: {r.stdout}", r)
    expect_background_dead(p, beat, r)
    r, found = stop_background(p)
    expect(r.returncode == 0 and found is None and '"background": null' in r.stdout, "with none running it says so", r)


def test_release_ends_the_background_search_and_its_children(base):
    p = background_project(base)
    r = p.run("claim", TID, "--by", "w1")
    expect(r.returncode == 0, "claim should pass", r)
    beat = Path(base) / "bg" / "beat"
    try:
        r, out = search(p, HANGING)
        expect(out is not None and out.get("continues_s"), f"the search should go on in the background: {out}", r)
        expect(wait_for(lambda: beat.exists() and beat.stat().st_size > 0), "the background search should reach the hang")
        r = p.run("release", TID)
        expect(r.returncode == 0 and f"{TID} -> open" in r.stdout, "release to open", r)
        expect_background_dead(p, beat, r)
    finally:
        stop_background(p)


def build_starts(folder, tag):
    """When each build of the sources tagged `tag` started, in order."""
    lines = [x.split() for x in (Path(folder) / "builds.log").read_text().splitlines()]
    return sorted(float(x[2]) for x in lines if len(x) == 3 and x[0] == tag and x[1] == "start")


def test_a_foreground_block_gets_its_slots_back_from_a_background_search(base):
    folder = Path(base) / "bg"
    one = background_project(sub(base, "one"), folder, workers=2, slots=2, ceiling_s=60)
    two = background_project(sub(base, "two"), folder)
    shared = {"DECOMP_LOCAL": str(one.root / ".decomp")}  # one machine folder: its settings and its pool

    def run(p, tag):
        path = p.base / "template.c"
        path.write_text(wide(8).replace("int f(void) {", f"int f(void) {{ /* TAG_{tag} */"), encoding="utf-8")
        r = p.run("search", TID, str(path), env=shared)
        return r, json.loads(r.stdout.splitlines()[0]) if r.stdout.startswith("{") else None

    try:
        r, out = run(one, "one")
        expect(out is not None and out.get("continues_s"), f"the first search should go on in the background: {out}", r)
        returned = time.time()
        expect(wait_for(lambda: len([t for t in build_starts(folder, "one") if t > returned]) >= 2),
               "the background search should be building on both slots")
        r, out = run(two, "two")
        expect(out is not None and out["end"] == "deadline", f"the second search should run its block: {out}", r)
        built = out["counts"]["compiled"]
        expect(built >= 2, f"the foreground block should get slots while a background search wants them all: {out}", r)
        mine = build_starts(folder, "two")[:2 + built]  # the calibration's two builds, then the block's
        yielded = [t for t in build_starts(folder, "one") if mine[0] < t < mine[-1]]
        expect(len(yielded) <= 2, "the background search should start no build while the foreground block runs, beyond "
               f"what it had in hand: it started {len(yielded)} in {mine[-1] - mine[0]:.1f} s", r)
        ended = time.time()
        expect(wait_for(lambda: any(t > ended for t in build_starts(folder, "one"))),
               "the background search should take its slots again once the foreground block has ended")
    finally:
        stop_background(one, env=shared)
        stop_background(two, env=shared)


def kept_log(p):
    return p.root / ".decomp" / "search" / TID / "background.log"


def forget_latency(p):
    """Drop when the last round ended, so the next round's ceiling is the setting and not the seconds since."""
    (p.root / ".decomp" / "search" / TID / "ended").unlink()


def waits_on(p, name):
    """Whether the running background search has logged that it waits on the foreground search `name`."""
    log = background_folder(p) / "log"
    return log.exists() and name in log.read_text(encoding="utf-8", errors="replace")


def test_a_background_search_that_built_nothing_leaves_its_log(base):
    p = background_project(base)
    try:
        writer(p, "4242-feed", -600)  # another search's foreground block, for as long as the test runs
        r, out = search(p, wide(8))
        expect(out is not None and out.get("continues_s"), f"the search should go on in the background: {out}", r)
        expect(wait_for(lambda: waits_on(p, "4242-feed")), "the background search should wait on the foreground block")
        r, found = stop_background(p)
        expect(found is not None and found["tried"] == 0, f"it should have built nothing: {r.stdout}", r)
        expect(found.get("log") and Path(found["log"]) == kept_log(p) and kept_log(p).exists(),
               f"the report names the kept log, beside the round's files: {found}", r)
        first = kept_log(p).read_text(encoding="utf-8", errors="replace")
        expect("4242-feed" in first, f"the log names the foreground search it waited on: {first}", r)
        expect(not background_folder(p).exists(), "the background search's other files are cleared away", r)

        (slot_folder(p) / "4242-feed.writer").unlink()
        forget_latency(p)
        r, out = search(p, wide(7))
        expect(out is not None and out.get("continues_s"), f"the search should go on in the background: {out}", r)
        expect(wait_for(lambda: background_tried(p) >= 2), "with no foreground block the background search builds")
        r, found = stop_background(p)
        expect(found is not None and found["tried"] >= 2 and "log" not in found,
               f"a background search that tried candidates keeps no log: {found}", r)
        expect(kept_log(p).read_text(encoding="utf-8", errors="replace") == first, "the last kept log stays as it was", r)

        writer(p, "4343-beef", -600)
        forget_latency(p)
        r, out = search(p, wide(6))
        expect(out is not None and out.get("continues_s"), f"the search should go on in the background: {out}", r)
        expect(wait_for(lambda: waits_on(p, "4343-beef")), "the background search should wait on the foreground block")
        r, found = stop_background(p)
        expect(found is not None and found["tried"] == 0 and found.get("log"), f"it should have built nothing: {r.stdout}", r)
        last = kept_log(p).read_text(encoding="utf-8", errors="replace")
        expect("4343-beef" in last and "4242-feed" not in last, f"the new log replaces the last kept one: {last}", r)
    finally:
        stop_background(p)


def test_a_background_search_does_not_yield_to_the_call_that_started_it(base):
    p = background_project(base)
    try:
        r, out = search(p, wide(8))
        expect(out is not None and out.get("continues_s"), f"the search should go on in the background: {out}", r)
        caller = json.loads((background_folder(p) / "spawn.json").read_text()).get("writer")
        expect(caller, "the background search is told the name its caller had in the pool", r)
        beat = writer(p, caller, -600)  # the call has exited, and its heartbeat in the pool is still fresh
        before = background_tried(p)
        expect(wait_for(lambda: background_tried(p) >= before + 2, seconds=out["continues_s"]),
               "the background search should build candidates within its budget", r)
        expect(beat.exists(), "the caller's heartbeat stayed in the pool all the while", r)
    finally:
        stop_background(p)


def test_collecting_a_background_search_stuck_in_a_compile_is_bounded(base):
    p, beat = hung_background(base)
    began = time.time()
    r, found = stop_background(p)
    took = time.time() - began
    expect(r.returncode == 0 and found is not None and found["end"] == "stopped",
           f"the stop form returns what the background search had: {r.stdout}", r)
    expect(took < 15, f"collecting should wait no longer than its 10 s bound, it took {took:.1f} s", r)
    expect_background_dead(p, beat, r)


def test_a_case_receives_its_scratch_folder_in_resolved_form(base):
    expect(base == str(Path(base).resolve()), f"the scratch folder {base} differs from its resolved form {Path(base).resolve()}")


def rmtree(path):
    def retry(func, p, _):
        os.chmod(p, stat.S_IWRITE)
        func(p)
    shutil.rmtree(path, onerror=retry)


NO_MATCH_EXIT, COLLISION_EXIT = 2, 3


def module_level_collisions(source):
    """One message per module-level name that a def, a class or a plain assignment binds more than once."""
    seen, found = {}, []

    def bind(name, line):
        if name in seen:
            found.append(f"{name} is bound at line {seen[name]} and again at line {line}")
        else:
            seen[name] = line

    def targets(node):
        if isinstance(node, ast.Name):
            yield node.id
        elif isinstance(node, (ast.Tuple, ast.List)):
            for e in node.elts:
                yield from targets(e)

    for node in ast.parse(source).body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            bind(node.name, node.lineno)
        elif isinstance(node, ast.Assign):
            for t in node.targets:
                for name in targets(t):
                    bind(name, node.lineno)
        elif isinstance(node, ast.AnnAssign) and node.value is not None:
            for name in targets(node.target):
                bind(name, node.lineno)
    return found


def select_cases(names, filters):
    """The case names the filters select, in order, and the filters that select none."""
    chosen, unmatched = set(), []
    for flt in filters:
        if flt in names:
            hit = {flt}
        else:
            words = flt.split("_")
            hit = {n for n in names if any(n.split("_")[i:i + len(words)] == words for i in range(len(n.split("_"))))}
        chosen |= hit
        if not hit:
            unmatched.append(flt)
    return [n for n in names if n in chosen] if filters else list(names), unmatched


def say(text):
    print(text, flush=True)


def main(argv=None, namespace=None, source=None):
    """Run a module's test_ cases. The module is this one unless a caller passes its globals and its file."""
    argv = sys.argv[1:] if argv is None else argv
    namespace = globals() if namespace is None else namespace
    source = Path(source or __file__)
    list_only = "--list" in argv
    filters = [a for a in argv if a != "--list"]
    clashes = module_level_collisions(source.read_text(encoding="utf-8"))
    if clashes:
        for c in clashes:
            say(f"COLLISION {source.name}: {c}")
        sys.exit(COLLISION_EXIT)
    names, unmatched = select_cases([n for n in namespace if n.startswith("test_")], filters)
    if unmatched:
        for f in unmatched:
            say(f"NO CASE matches the filter {f!r}")
        sys.exit(NO_MATCH_EXIT)
    if list_only:
        for n in names:
            say(n)
        sys.exit(0)
    failed = 0
    for name in names:
        base = str(Path(tempfile.mkdtemp(prefix="decomp-test-")).resolve())
        try:
            namespace[name](base)
            say(f"PASS {name}")
        except Exception as e:  # a crash in one case must not hide the others
            failed += 1
            say(f"FAIL {name}: {e if isinstance(e, AssertionError) else traceback.format_exc()}")
        finally:
            try:
                rmtree(base)
            except OSError:
                pass
    say(f"{len(names) - failed} passed, {failed} failed")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
