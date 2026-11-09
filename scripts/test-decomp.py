#!/usr/bin/env python3
"""Tests of the decomp project tool at its one seam: the command line.

Each case builds a scratch git project (a copy of decomp.py, a toolchain.json,
a decomp.json whose adapters are small `python -c` commands, a fake target, and
fake tools that only print a banner), runs decomp.py commands in it, and asserts
on exit codes and output. No real compiler, no network. Standard library only.

Run: python scripts/test-decomp.py [name-filter]
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
TOOL = REPO / "skills" / "in-progress" / "decomp-setup" / "scripts" / "decomp.py"
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
        self.write(f"tickets/{UNIT}/{TID}.md", "\n".join([
            "---", f"id: {TID}", f"unit: {UNIT}", f"address: {ADDRESS}", "size: 37", "tier: SMALL",
            f"source: {SOURCE}", "expected: expected/00401000.bin", f"status: {status}",
            "claimed_by:" + (" w1" if status == "claimed" else ""),
            "claimed_at:" + (" 1789000000" if status == "claimed" else ""), "---", "## Notes", ""]))
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
        p.write_text(text, encoding="utf-8", newline="\n")

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

    def run(self, *args, cwd=None, env=None):
        cwd = Path(cwd or self.root)
        e = {k: v for k, v in os.environ.items() if k not in ("DECOMP_LOCAL", "DECOMP_TARGET", "FAKE_BANNER")}
        e.update(PYTHONDONTWRITEBYTECODE="1", TMP=str(self.tmp), TEMP=str(self.tmp), TMPDIR=str(self.tmp))
        e.update(env or {})
        r = subprocess.run([sys.executable, str(cwd / "tools" / "decomp.py"), *args], cwd=cwd, env=e,
                           capture_output=True, text=True, errors="replace")
        r.all = r.stdout + r.stderr
        return r

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


def test_scan_refuses_assembly_and_unlisted_pragma(base):
    expect_guardrail(Project(base, source=CLEAN + "void g(void) { __asm nop }\n"), "assembly", "__asm nop")


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
    expect("status: claimed" in (p.root / f"tickets/{UNIT}/{TID}.md").read_text(), "the ticket should not change", r)


def test_check_runs_on_the_whole_file_edition_of_the_same_contract(base):
    expect_match(Project(base, manifest=editions_manifest()))


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


def test_verify_rejects_writer_branch_touching_symbol_map(base):
    p = Project(base, status="claimed")
    p.branch(f"w/{TID}", {SOURCE: CLEAN + "/* w */\n", "symbols.json": '{"f": "0x00401000"}\n'})
    r = p.run("verify", TID, "--model", "m")
    expect(r.returncode == 4 and '"result": "guardrail"' in r.stdout, "verify should record guardrail", r)
    ev = (p.root / "ledger" / "evidence" / f"{TID}-a001.txt").read_text()
    expect("guarded" in ev and "symbols.json" in ev, f"evidence should name the guarded path: {ev}", r)


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


def provision_project(base, digest=None):
    archive = FAKE_TOOL.encode()
    p = Project(base, manifest=sourced_manifest(archive, digest), installed=(), files={"tools/unpack.py": UNPACK})
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
    expect(not (p.root / ".decomp/toolchain/compiler/cc.py").exists(), "nothing should be unpacked", r)


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


def test_verify_checks_the_environment_before_recording(base):
    p = Project(base, status="claimed")
    p.branch(f"w/{TID}", {SOURCE: CLEAN + "/* w */\n"})
    r = p.run("verify", TID, "--model", "m", env={"DECOMP_TARGET": str(p.root / "DECOMP.md")})
    expect(r.returncode == ENV_EXIT and not (p.root / "ledger").exists(), "verify should exit 6, recording nothing", r)


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
