#!/usr/bin/env python3
"""Project tool for byte-for-byte decompilation.

Copied into a decomp project's tools/ by decomp-setup and frozen at the
decomp-setup tag. It is the only writer of ticket statuses and ledger records.
Standard library only. Run from the project root: python tools/decomp.py <cmd>.
"""
import argparse
import atexit
import codecs
import collections
import contextlib
import hashlib
import heapq
import itertools
import json
import math
import os
import re
import shlex
import shutil
import signal
import statistics
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request
from pathlib import Path

TIERS = [("TINY", 25), ("SMALL", 256), ("MEDIUM", 511)]  # else LARGE
MATCHED = {"matched", "integrated", "revalidated"}
READY = ("open", "regressed")  # work a writer may claim
REGRESSABLE = tuple(sorted(MATCHED)) + ("regressed",)  # statuses a regress leaves, in `revalidate` and the lifecycle
BUSY = ("claimed", "bytes-match", "matched")  # a writer holds the unit
FINISHED = ("integrated", "revalidated")  # merged into the integration branch
STATUSES = {"open", "claimed", "blocked-reference", "bytes-match"} | MATCHED | {"regressed"}
CATEGORIES = {
    "build-fail", "reference-gap", "signedness", "width", "operator", "control-flow",
    "statement-order", "expression-shape", "register-allocation", "stack-layout",
    "data-layout", "calling-convention", "inlining", "optimization", "unit-order", "unknown",
}
BANNED = [
    (r"\b_{0,2}asm\b|\b__asm__\b", "assembly"),
    (r"\b_?_emit\b", "assembly"),
]
TRIGRAPH = re.compile(r"\?\?[=/'()!<>-]")
CONTINUATION = re.compile(r"\\[ \t]*$")
DIRECTIVE_PRAGMA = re.compile(r"\s*#\s*pragma\b")
PRAGMA_OPERATOR = re.compile(r"\b(__pragma|_Pragma)\b")
ATTRIBUTE = re.compile(r"\b(__attribute__|__attribute|__declspec|_declspec)\b")
BRACKET_ATTRIBUTE = re.compile(r"\[\[[^\[\]]*\]\]")
# Inside an attribute, in any compiler's spelling. No allowlist reaches these.
NAKED = re.compile(r"(?<![A-Za-z0-9])_*naked_*(?![A-Za-z0-9])")
PLACEMENT = re.compile(r"(?<![A-Za-z0-9])_*(section|allocate|code_seg|init_seg)_*(?![A-Za-z0-9])")
CHAR_LITERAL = re.compile(r"'(?:\\[^\n]|[^'\\\n]){1,4}'")
RAW_STRING = re.compile(r'R"([^()\\\s]{0,16})\(')
INCLUDE = re.compile(r"[ \t\f\v]*#[ \t]*(include_next|include|import)\b[ \t]*(.*)")
INCLUDE_NAME = re.compile(r'"([^"\n]+)"|<([^>\n]+)>')
KEY = re.compile(r"[0-9A-Za-z_.]+")  # a function's key: the part of its ticket id after the unit
HEX = re.compile(r"(0[xX])?[0-9A-Fa-f]+")
SYMBOLS = "symbols.json"  # the symbol map: symbol name to address in the original
OPEN_THRESHOLD = 3
EARLY_WARNING_ATTEMPTS = 10
FIELDS = ["id", "unit", "address", "size", "tier", "source", "expected", "status", "claimed_by", "claimed_at"]


def die(msg, code=1):
    print(f"error: {msg}", file=sys.stderr)
    sys.exit(code)


def now():
    return int(time.time())


def git(*args, cwd=None, check=True):
    r = subprocess.run(["git", *args], cwd=cwd or ROOT, capture_output=True, text=True, errors="replace")
    if check and r.returncode != 0:
        die(f"git {' '.join(args)}: {r.stderr.strip()}")
    return r.stdout


def git_bytes(*args):
    r = subprocess.run(["git", *args], cwd=ROOT, capture_output=True)
    if r.returncode != 0:
        die(f"git {' '.join(args)}: {r.stderr.decode(errors='replace').strip()}")
    return r.stdout


def tier(size):
    for name, limit in TIERS:
        if size <= limit:
            return name
    return "LARGE"


def sha(data):
    return hashlib.sha256(data).hexdigest()


def expand(template, **values):
    """Replace each {name} given here. Any other brace in a command stays as written."""
    return re.sub(r"\{(\w+)\}", lambda m: str(values.get(m.group(1), m.group(0))), template)


def address_parts(address):
    """An address split at its colons: plain (`0x00401000`), or with a segment, bank, or module in front."""
    return [int(p, 16) if HEX.fullmatch(p) else p for p in address.split(":")]


def address_order(address):
    return [(0, p, "") if isinstance(p, int) else (1, 0, p) for p in address_parts(address)]


def same_address(address):
    """One spelling per address, so `0x401000` and `00401000` compare equal."""
    return ":".join(f"{p:X}" if isinstance(p, int) else p for p in address_parts(address))


def function_key(f):
    """What names an inventory function in its ticket id and expected file: its `key`, else its address."""
    if f.get("key"):
        key = f["key"]
    elif HEX.fullmatch(f["address"]):
        key = f"{int(f['address'], 16):08X}"
    else:
        key = re.sub(r"[^0-9A-Za-z_.]", "_", f["address"])
    if not KEY.fullmatch(key):
        die(f"inventory: key '{key}' may hold only letters, digits, '_' and '.'")
    return key


def function_keys(functions):
    """Each function's key, by position. Stops when two functions share one."""
    keys, seen = [], {}
    for f in functions:
        key = function_key(f)
        if key in seen:
            die(f"inventory: {f['address']} in unit {f['unit']} and {seen[key]['address']} in unit "
                f"{seen[key]['unit']} share the key '{key}'. Give each a `key` of its own "
                "(a module or overlay name in front of the address).")
        seen[key] = f
        keys.append(key)
    return keys


def read_inventory():
    """The one reader of inventory.json: its units and functions, each function with its `key` and ticket `id` set."""
    inv = json.loads((ROOT / "inventory.json").read_text(encoding="utf-8"))
    for f, key in zip(inv["functions"], function_keys(inv["functions"])):
        f["key"] = key
        f["id"] = f"{f['unit']}-{key}"
    return inv


# ---------- environment ----------

ENV_EXIT = 6  # the machine's target or toolchain differs from toolchain.json
LINK_UNAVAILABLE_EXIT = 7  # the contract records that this target cannot be linked whole
_TOOLCHAIN = None


def file_sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def checkout_dir():
    """The .decomp/ directory of this repository's main checkout, which its worktrees share."""
    common = git("rev-parse", "--git-common-dir").strip()  # relative to ROOT in the main checkout
    return (ROOT / common).resolve().parent / ".decomp"


def local_dir():
    """Where this machine's target path, tools, and downloads live. DECOMP_LOCAL names another checkout's."""
    if os.environ.get("DECOMP_LOCAL"):
        return Path(os.environ["DECOMP_LOCAL"])
    return checkout_dir()


def on_host(entry):
    """True when a manifest entry applies to this system: no `hosts`, or one that sys.platform starts with."""
    hosts = entry.get("hosts")
    return not hosts or any(sys.platform.startswith(h) for h in hosts)


def toolchain():
    """toolchain.json (committed requirements) joined with .decomp/local.json (this machine's paths)."""
    global _TOOLCHAIN
    if _TOOLCHAIN is None:
        p = ROOT / "toolchain.json"
        if not p.exists():
            die("no toolchain.json; run /decomp-setup", ENV_EXIT)
        tc = json.loads(p.read_text(encoding="utf-8"))
        loc = local_dir()
        lp = loc / "local.json"
        local = json.loads(lp.read_text(encoding="utf-8")) if lp.exists() else {}
        tgt = tc["target"]
        if "editions" not in tgt:  # the single size-and-hash form is one accepted edition
            tgt["editions"] = [{"name": "contract target", "sha256": tgt["sha256"], "size": tgt["size"]}]
        tgt.setdefault("probes", [])
        tgt.setdefault("known_wrong", [])
        tgt["path"] = os.environ.get("DECOMP_TARGET") or local.get("target", "")
        tc["elsewhere"] = {t["name"] for t in tc["tools"] if not on_host(t)}
        tc["tools"] = [t for t in tc["tools"] if on_host(t)]
        tc["prerequisites"] = [h for h in tc.get("prerequisites", []) if on_host(h)]
        names = [t["name"] for t in tc["tools"]]
        twice = sorted({n for n in names if names.count(n) > 1})
        if twice:
            die(f"toolchain.json lists {twice} more than once for this host ({sys.platform})", ENV_EXIT)
        for t in tc["tools"]:
            t["root"] = str(Path(local.get("roots", {}).get(t["name"]) or loc / "toolchain" / t["name"]))
        _TOOLCHAIN = tc
    return _TOOLCHAIN


def tool_env():
    """Adapters and tool commands find the target and each tool through these variables."""
    tc = toolchain()
    env = dict(os.environ, DECOMP_TARGET=tc["target"]["path"])
    for t in tc["tools"]:
        env["DECOMP_TOOL_" + re.sub(r"\W", "_", t["name"]).upper()] = t["root"]
    return env


def tool_command(template, **values):
    """A manifest command with its placeholders filled. {python} is the interpreter running this tool."""
    return expand(template, tools=ROOT / "tools", python=sys.executable, **values)


def version_output(cmd, env):
    """What a version command prints, on stdout and stderr together."""
    try:
        r = subprocess.run(cmd, shell=True, cwd=ROOT, env=env, capture_output=True, text=True,
                           errors="replace", timeout=300)
        return r.stdout + r.stderr
    except subprocess.TimeoutExpired:
        return "(the command timed out)"


def recognise(tgt):
    """Which edition the target file is. Returns (accepted edition or None, report line)."""
    path = Path(tgt["path"])
    size, digest = path.stat().st_size, file_sha(path)
    for e in tgt["editions"]:
        if e.get("sha256") == digest and e.get("size", size) == size:
            return e, f"target ok: {e['name']}: {size} B sha256 {digest[:16]}"
    for w in tgt["known_wrong"]:
        if w["sha256"] == digest:
            return None, f"target: {path} is the known-wrong edition '{w['name']}': {w['message']}"
    hits = 0
    with open(path, "rb") as f:
        for p in tgt["probes"]:  # file offsets, so no executable format is parsed here
            f.seek(p["offset"])
            data = f.read(p["size"])
            hits += len(data) == p["size"] and sha(data) == p["sha256"]
    count = f"{hits} of {len(tgt['probes'])} probes matched"
    by_probe = [e for e in tgt["editions"] if 0 < e.get("probes_needed", 0) <= hits]
    if by_probe:
        e = max(by_probe, key=lambda e: e["probes_needed"])
        return e, f"target ok: {e['name']}: {count}; {size} B sha256 {digest[:16]}"
    whole = [e for e in tgt["editions"] if e.get("sha256")]
    wanted = f"; the contract's is {whole[0].get('size')} B sha256 {whole[0]['sha256']}" if len(whole) == 1 else ""
    return None, f"target: {path} is {size} B sha256 {digest}: not an accepted edition; {count}{wanted}"


def edition_named(name):
    return next((e for e in toolchain()["target"]["editions"] if e["name"] == name), None)


def prerequisite_failure(tc, env, lines):
    """The first host prerequisite that is missing or the wrong version, as a message. Passed ones go to lines."""
    for h in tc["prerequisites"]:  # the user installs these; a tool behind a missing one fails confusingly
        out = version_output(tool_command(h["version_cmd"]), env)
        if h["version"] not in out:
            return (f"prerequisite {h['name']}: missing or the wrong version: `{h['version_cmd']}` must print "
                    f"'{h['version']}'; it printed: {out.strip()[:300]}. The user installs it; provision never does.")
        lines.append(f"{h['name']} ok: {h['version']}")
    return None


def file_text(path):
    """A text file's contents in whatever encoding it holds: UTF-8, UTF-16 with or without a mark, or one byte per character."""
    data = Path(path).read_bytes()
    if data.startswith(codecs.BOM_UTF8):
        return data.decode("utf-8-sig", errors="replace")
    if data.startswith((codecs.BOM_UTF16_LE, codecs.BOM_UTF16_BE)):
        return data.decode("utf-16", errors="replace")
    if b"\0" in data:  # UTF-16 with no mark: ASCII text has its zero bytes on one side of each pair
        little = data[1::2].count(0) >= data[0::2].count(0)
        return data.decode("utf-16-le" if little else "utf-16-be", errors="replace")
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        return data.decode("latin-1")


def tool_failure(t, env):
    """Why tool t is not the one toolchain.json pins, or None when it is."""
    pins = [k for k in ("banner_file", "banner_cmd") if t.get(k)]
    if len(pins) != 1:
        return (f"{t['name']}: toolchain.json gives it {'both' if pins else 'neither'} banner_file "
                f"{'and' if pins else 'nor'} banner_cmd; a tool has exactly one")
    missing = [f for f in t.get("files", []) if not (Path(t["root"]) / f).exists()]
    if missing:
        return f"{t['name']}: missing under {t['root']}: {missing}"
    if t.get("banner_file"):
        banner_file = Path(t["root"]) / t["banner_file"]
        if not banner_file.is_file():
            return f"{t['name']}: banner file {banner_file} not found"
        if t["banner"] not in file_text(banner_file):
            return f"{t['name']}: banner lacks '{t['banner']}'; read from {banner_file}"
        return None
    out = version_output(tool_command(t["banner_cmd"], root=t["root"]), env)
    if t["banner"] not in out:
        return f"{t['name']}: banner lacks '{t['banner']}'; the command printed: {out.strip()[:300]}"
    return None


def environment_stamp(tc):
    """Changes whenever toolchain.json, the target, a required file, or a banner file does."""
    tgt = tc["target"]
    watched = ([Path(tgt["path"])] if tgt["path"] else []) + [
        Path(t["root"]) / f for t in tc["tools"]
        for f in t.get("files", []) + ([t["banner_file"]] if t.get("banner_file") else [])]
    stamp = [sha((ROOT / "toolchain.json").read_bytes()), tgt["path"]]
    for p in watched:
        try:
            st = p.stat()
            stamp.append(f"{p}:{st.st_size}:{st.st_mtime_ns}")
        except OSError:
            stamp.append(f"{p}:missing")
    return sha("\n".join(stamp).encode())


# What doctor found on this machine. edition: the recognised accepted edition. unusable: tool
# name to why it failed, for tools outside doctor's need. vars: the tool environment variables
# for adapters and tool commands. lines: doctor's report lines (none when the cache was trusted).
Environment = collections.namedtuple("Environment", "edition unusable vars lines")


def doctor(full=True, need=None):
    """Stop unless the target, host prerequisites, and tools equal toolchain.json. Returns the Environment.

    need names the tools that must pass (None: all of them). A tool outside need that fails
    is reported and returned in the Environment's unusable, so only the units built with it stop.
    The cached toolchain is never changed.

    full=False trusts the last check that passed in full while toolchain.json, the target,
    and every required file keep the same size and modification time.
    """
    tc = toolchain()
    loc = local_dir()
    tgt = tc["target"]
    unusable = {}
    stamp = environment_stamp(tc)
    cache = loc / "doctor.json"
    if not full and cache.exists():
        last = json.loads(cache.read_text(encoding="utf-8"))
        edition = edition_named(last.get("edition"))
        if last.get("ok") == stamp and edition:
            return Environment(edition=edition, unusable={}, vars=tool_env(), lines=[])
    bad, lines, edition = [], [], None
    if not tgt["path"]:
        bad.append('target: no path; set "target" in .decomp/local.json or DECOMP_TARGET')
    elif not Path(tgt["path"]).is_file():
        bad.append(f"target: {tgt['path']} not found")
    else:
        edition, line = recognise(tgt)
        (lines if edition else bad).append(line)
    env = tool_env()
    behind = prerequisite_failure(tc, env, lines)
    if behind:
        bad.append(behind)
    else:
        for t in tc["tools"]:
            why = tool_failure(t, env)
            if why is None:
                lines.append(f"{t['name']} ok: {t['banner']}")
            elif need is None or t["name"] in need:
                bad.append(why)
            else:
                unusable[t["name"]] = why
                lines.append(f"not usable here: {why}")
    if bad:
        cache.unlink(missing_ok=True)
        for b in bad:
            print(f"ENVIRONMENT: {b}", file=sys.stderr)
        die("this machine does not match toolchain.json; nothing was built or recorded. "
            "Fix it with `decomp.py provision` or the user's own install, never by editing toolchain.json.", ENV_EXIT)
    if unusable:
        cache.unlink(missing_ok=True)
    else:
        loc.mkdir(parents=True, exist_ok=True)
        cache.write_text(json.dumps({"ok": stamp, "unix": now(), "edition": edition["name"]}), encoding="utf-8")
    return Environment(edition=edition, unusable=unusable, vars=env, lines=lines)


def edition_differs(environment, t):
    """True when doctor's recognised edition holds ticket t's function differently."""
    held = environment.edition.get("differs", [])
    return (t["id"] in held or t["id"].split("-", 1)[1] in held
            or same_address(t["address"]) in {same_address(a) for a in held if ":" in a or HEX.fullmatch(a)})


def compiler_for(unit):
    """The manifest tool that builds this unit: its own when the contract maps one, else the default.

    Stops with the environment exit when toolchain.json has no such tool for this host.
    """
    name = CFG.get("unit_compilers", {}).get(unit) or CFG.get("compiler", "")
    tc = toolchain()
    if name and name not in {t["name"] for t in tc["tools"]}:
        where = f"lists only for another host than this one ({sys.platform})" if name in tc["elsewhere"] else "does not list"
        print(f"ENVIRONMENT: unit {unit} is built with '{name}', which toolchain.json {where}", file=sys.stderr)
        die("nothing was built or recorded; a unit is never built with another compiler than its own.", ENV_EXIT)
    return name


def tools_needed(compilers):
    """Every tool but the compilers outside these ones (each from compiler_for)."""
    every = {CFG.get("compiler", "")} | set(CFG.get("unit_compilers", {}).values())
    return {t["name"] for t in toolchain()["tools"]} - (every - set(compilers))


def stop_if_edition_differs(environment, t):
    """Stop with the environment exit when doctor's edition cannot judge ticket t."""
    if edition_differs(environment, t):
        e = environment.edition
        print(f"ENVIRONMENT: edition '{e['name']}' holds {t['id']} ({t['address']}) differently from the "
              "contract's expected bytes", file=sys.stderr)
        die("nothing was built or recorded; this function is matched only on an edition that holds it unchanged.",
            ENV_EXIT)


def prepare(t, full=False, judge=True):
    """Resolve ticket t's compiler, run doctor for the tools it needs, and (when judge) stop if the edition
    holds t differently. Returns (environment, compiler)."""
    compiler = compiler_for(t["unit"])
    environment = doctor(full=full, need=tools_needed([compiler]))
    if judge:
        stop_if_edition_differs(environment, t)
    return environment, compiler


FAKEMATCH_RULES = ("forbidden", "allowed")
UPGRADE_HINT = "It reaches a project past setup through the skill-upgrade section of /decomp-setup, as a change on a candidate branch."


def contract_rules():
    """The contract's template-search and fakematch rules as decomp.json holds them: (allowed, fakematch).

    Stops, naming the upgrade step, when either key is missing or malformed.
    """
    search, fake = CFG.get("template_search"), CFG.get("fakematch")
    missing = [k for k, ok in (("template_search", isinstance(search, bool)), ("fakematch", fake in FAKEMATCH_RULES)) if not ok]
    if missing:
        die(f"decomp.json lacks a valid {' and '.join('`' + k + '`' for k in missing)} "
            f"(`template_search`: true or false; `fakematch`: {' or '.join(repr(r) for r in FAKEMATCH_RULES)}). "
            f"{UPGRADE_HINT} `decomp.py contract-keys` prints the values the contract's lines give.")
    return search, fake


def cmd_doctor(a):
    for line in doctor(full=True).lines:
        print(line)
    if (ROOT / "decomp.json").exists():
        search, fake = contract_rules()
        print(f"template search: {'allowed' if search else 'not allowed'}")
        print(f"fakematch: {fake}")
    print("doctor: ok")


def contract_line(text, *names):
    """The value of the first contract bullet `- <name>: <value>` (any of names, case-insensitive), or None."""
    for line in text.splitlines():
        m = re.match(r"\s*[-*]\s*([^:]+):\s*(.*)$", line)
        if m and m.group(1).strip().lower() in names:
            return m.group(2).strip()
    return None


def reads_as_allowed(value):
    """True for an 'allowed' value, False for 'not allowed' or 'forbidden'; None when it says neither."""
    v = value.lower().strip("` .")
    if re.match(r"(not allowed|no\b|forbidden|not\b|never)", v):
        return False
    if re.match(r"(allowed|yes\b)", v):
        return True
    return None


def cmd_contract_keys(a):
    """Print the decomp.json keys the contract's lines give, for the skill upgrade. An old 'Permuter:' line
    is read as the 'Template search:' line."""
    path = ROOT / "DECOMP.md"
    if not path.exists():
        die("no DECOMP.md; run /decomp-setup")
    text = path.read_text(encoding="utf-8")
    search_line = contract_line(text, "template search")
    if search_line is None:
        search_line = contract_line(text, "permuter")
    fake_line = contract_line(text, "fakematch rule")
    search = reads_as_allowed(search_line) if search_line is not None else None
    fake = reads_as_allowed(fake_line) if fake_line is not None else None
    if search is None or fake is None:
        die("the contract's template-search (or old permuter) line or fakematch line is missing or unclear; "
            "ask the user which it is and record the answer in the upgrade's ADR.")
    print(json.dumps({"template_search": search, "fakematch": "allowed" if fake else "forbidden"}))


def cmd_provision(a):
    """Fetch and unpack every tool that has a source, verifying size and SHA-256 first."""
    tc = toolchain()
    dl = local_dir() / "downloads"
    dl.mkdir(parents=True, exist_ok=True)
    env = tool_env()
    behind = prerequisite_failure(tc, env, [])
    if behind:  # an unpack step behind a missing archive tool fails without saying why
        print(f"ENVIRONMENT: {behind}", file=sys.stderr)
        die("nothing was downloaded or unpacked.", ENV_EXIT)
    for t in tc["tools"]:
        if a.tool and t["name"] != a.tool:
            continue
        src, root = t.get("source"), Path(t["root"])
        if not src:
            print(f"{t['name']}: no source; the user installs it and names its folder in .decomp/local.json \"roots\"")
            continue
        if t.get("files") and all((root / f).exists() for f in t["files"]) and not a.force:
            print(f"{t['name']}: already unpacked at {root}")
            continue
        if not src["url"].startswith("https://"):
            die(f"{t['name']}: source url must be https")
        archive = dl / (src.get("file") or src["url"].split("?")[0].rsplit("/", 1)[-1])
        digest = file_sha(archive) if archive.exists() else None
        stale = digest is not None and src.get("sha256") and digest != src["sha256"]
        if digest is None or (stale and a.force):
            print(f"{t['name']}: downloading {src['url']}")
            part = archive.with_name(archive.name + ".part")
            try:
                with urllib.request.urlopen(src["url"]) as r, open(part, "wb") as f:
                    shutil.copyfileobj(r, f, 1 << 20)
            except OSError as e:
                die(f"{t['name']}: download failed: {e}", ENV_EXIT)
            part.replace(archive)
            digest = file_sha(archive)
        size = archive.stat().st_size
        if not src.get("sha256"):
            print(f"{t['name']}: downloaded {archive.name}: {size} B sha256 {digest}")
            die(f"{t['name']}: toolchain.json has no sha256 for this source. Record the size and hash above "
                "with where they come from, then run provision again. Nothing was unpacked.", ENV_EXIT)
        if digest != src["sha256"] or size != src.get("size", size):
            die(f"{t['name']}: {archive} is {size} B sha256 {digest}; toolchain.json says "
                f"{src.get('size')} B sha256 {src['sha256']}. Nothing was unpacked. "
                "`provision --force` downloads it again.", ENV_EXIT)
        root.mkdir(parents=True, exist_ok=True)
        for c in t.get("unpack", []):
            c = tool_command(c, archive=archive, root=root)
            if subprocess.run(c, shell=True, cwd=dl, env=env).returncode != 0:
                die(f"{t['name']}: unpack step failed: {c}", ENV_EXIT)
        print(f"{t['name']}: unpacked to {root}")
    print("provisioned; run `decomp.py doctor`")


# ---------- tickets ----------

def ticket_path(tid, root=None):
    unit = tid.split("-")[0]
    return (root or ROOT) / "tickets" / unit / f"{tid}.md"


def read_ticket(tid, root=None):
    p = ticket_path(tid, root)
    if not p.exists():
        die(f"no ticket {tid}")
    text = p.read_text(encoding="utf-8").replace("\r\n", "\n")
    m = re.match(r"---\n(.*?)\n---\n(.*)", text, re.S)
    if not m:
        die(f"malformed ticket {tid}")
    fields = {}
    for line in m.group(1).splitlines():
        k, _, v = line.partition(":")
        fields[k.strip()] = v.strip()
    fields["size"] = int(fields["size"])
    return fields, m.group(2)


def write_ticket(fields, body):
    p = ticket_path(fields["id"])
    p.parent.mkdir(parents=True, exist_ok=True)
    head = "\n".join(f"{k}: {fields.get(k, '')}".rstrip() for k in FIELDS)
    p.write_text(f"---\n{head}\n---\n{body}", encoding="utf-8", newline="\n")


def all_tickets(root=None):
    out = []
    for p in sorted(((root or ROOT) / "tickets").glob("*/*.md")):
        out.append(read_ticket(p.stem, root)[0])
    return out


def append_note(tid, text):
    fields, body = read_ticket(tid)
    if "## Notes" not in body:
        body = body.rstrip("\n") + "\n\n## Notes\n"
    body = body.rstrip("\n") + f"\n- {now()} {' '.join(text.split())}\n"
    write_ticket(fields, body)


# ---------- ledger ----------

def ledger(name):
    p = ROOT / "ledger" / name
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def append(name, rec):
    with ledger(name).open("a", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(rec, sort_keys=True) + "\n")


def next_attempt_id(tid):
    """The id of the ticket's next attempt: one numbering for verify and a failed audit."""
    return f"{tid}-a{1 + sum(r['ticket'] == tid for r in records('attempts.jsonl')):03d}"


def event_out_of_order(tid, reason):
    append("events.jsonl", {"unix": now(), "ticket": tid, "event": "out-of-order", "reason": reason})


def event_integrated(tid):
    append("events.jsonl", {"unix": now(), "ticket": tid, "event": "integrated"})


def event_revalidated(tid):
    append("events.jsonl", {"unix": now(), "ticket": tid, "event": "revalidated"})


def event_regressed(tid):
    append("events.jsonl", {"unix": now(), "ticket": tid, "event": "regressed"})


def event_rejected_repair(ref):
    append("events.jsonl", {"unix": now(), "ref": ref, "event": "rejected-repair"})


def event_link(result, *, edition, units, source_bytes, in_scope_bytes, **more):
    append("events.jsonl", dict({"unix": now(), "ref": CFG["integration_branch"], "event": "link", "edition": edition,
                                 "units": units, "source_bytes": source_bytes, "in_scope_bytes": in_scope_bytes,
                                 "result": result}, **more))


def records(name):
    p = ROOT / "ledger" / name
    if not p.exists():
        return []
    return [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]


# ---------- ticket lifecycle ----------

UNCLAIMED = {"claimed_by": "", "claimed_at": ""}
Move = collections.namedtuple("Move", "froms to writes")  # statuses it may leave, the status it reaches, fields it writes
EVENTS = {  # event: its Move
    "claim": Move(READY, "claimed", {}),
    "release": Move(("claimed",), "open", UNCLAIMED),
    "block": Move(("claimed",), "blocked-reference", UNCLAIMED),
    "unblock": Move(("blocked-reference",), "open", {}),
    "bytes-match": Move(("claimed",), "bytes-match", {}),
    "audit-pass": Move(("bytes-match",), "matched", {}),
    "audit-fail": Move(("bytes-match",), "claimed", {}),
    "integrate": Move(("matched",), "integrated", UNCLAIMED),
    "revalidate-pass": Move(("integrated", "regressed"), "revalidated", {}),
    "regress": Move(REGRESSABLE, "regressed", UNCLAIMED),
}
MOVES = {(s, e): m.to for e, m in EVENTS.items() for s in m.froms}  # (status, event): new status


def may_move(t, event):
    return (t["status"], event) in MOVES


def refuse_unless(t, event):
    """Stop, exit 1, unless the ticket `t` may take `event`: one message shape for every command."""
    if not may_move(t, event):
        froms = EVENTS[event].froms
        allowed = " or ".join(froms) if len(froms) < 3 else ", ".join(froms[:-1]) + " or " + froms[-1]
        die(f"{t['id']} is {t['status']}; {event} needs {allowed}")


def record_audit_pass(t, last, auditor):
    if not any(m["ticket"] == t["id"] for m in records("matches.jsonl")):  # a match is recorded once
        append("matches.jsonl", {"ticket": t["id"], "unix": now(), "attempt": last["id"],
                                 "model": last["model"], "size": t["size"], "auditor": auditor})


def record_audit_fail(t, last, auditor):
    append("attempts.jsonl", dict(last, id=next_attempt_id(t["id"]), unix=now(), result="audit-fail",
                                  category="unknown", auditor=auditor))


RECORDS = {  # event: what the move writes to the ledger
    "audit-pass": record_audit_pass,
    "audit-fail": record_audit_fail,
    "integrate": lambda t: event_integrated(t["id"]),
    "revalidate-pass": lambda t: event_revalidated(t["id"]),
    "regress": lambda t: event_regressed(t["id"]),
}


RECORD_FIRST = ("audit-pass", "audit-fail")  # events whose ledger record is written before the ticket moves


def move(tid, event, by=None, **args):
    """Move ticket `tid` by `event`, the one writer of a ticket's status.

    Refuses an illegal move, takes the unit lock on a claim (`by` names the claimant), writes the new status
    and fields, releases the unit lock when the move leaves the claim, and records the move's ledger event
    (`args` go to that record). Returns the new status.
    """
    fields, body = read_ticket(tid)
    refuse_unless(fields, event)
    before, after = fields["status"], MOVES[(fields["status"], event)]
    assert after in STATUSES
    lock = f"unit-{fields['unit']}"
    if after in BUSY and before not in BUSY:
        take_lock(lock, by)
        fields.update(claimed_by=by, claimed_at=str(now()))
    fields["status"] = after
    fields.update(EVENTS[event].writes)
    if event in RECORD_FIRST:  # a failed write here leaves the ticket where it was
        RECORDS[event](fields, **args)
    write_ticket(fields, body)
    if before in BUSY and after not in BUSY:
        lockfile(lock).unlink(missing_ok=True)
    if event in RECORDS and event not in RECORD_FIRST:
        RECORDS[event](fields, **args)
    return after


# ---------- build and compare ----------

def lexed(text):
    """Two copies of a source text, each the same length with the same line breaks.

    code: comments, and the insides of string and character literals, blanked.
    bare: comments blanked, literals kept.
    Text that only looks like a literal (an unclosed quote, a digit separator) stays code.
    """
    code, bare = list(text), list(text)

    def blank(out, a, b):
        for k in range(a, b):
            if out[k] != "\n":
                out[k] = " "

    i, n = 0, len(text)
    while i < n:
        c = text[i]
        if text.startswith("//", i):
            j = text.find("\n", i)
            j = n if j < 0 else j
            blank(code, i, j), blank(bare, i, j)
        elif text.startswith("/*", i):
            j = text.find("*/", i + 2)
            j = n if j < 0 else j + 2
            blank(code, i, j), blank(bare, i, j)
        elif c == '"':
            raw = RAW_STRING.match(text, i - 1) if i and text[i - 1] == "R" else None
            if raw:
                j = text.find(")" + raw.group(1) + '"', raw.end())
                j = -1 if j < 0 else j + len(raw.group(1)) + 1
            else:
                j = i + 1
                while j < n and text[j] not in '"\n':
                    j += 2 if text[j] == "\\" else 1
                j = j if j < n and text[j] == '"' else -1
            if j < 0:
                j = i  # not closed: leave it as code
            else:
                blank(code, i + 1, j)
            j += 1
        elif c == "'" and CHAR_LITERAL.match(text, i):
            j = CHAR_LITERAL.match(text, i).end()
            blank(code, i + 1, j - 1)
        else:
            j = i + 1
        i = j
    return "".join(code), "".join(bare)


def parenthesised(code, bare, start):
    """The (...) that opens at or after start: (its text from bare, the index after it). None when it does not close.

    Parentheses are counted in code, where no literal can hold one.
    """
    m = re.compile(r"\s*\(").match(code, start)
    if not m:
        return None
    depth = 1
    for i in range(m.end(), len(code)):
        depth += {"(": 1, ")": -1}.get(code[i], 0)
        if depth == 0:
            return bare[m.end():i], i + 1
    return None


def as_directive(inner):
    """What a pragma operator stands for: `#pragma` and its argument, a string literal unquoted."""
    inner = inner.strip()
    lit = re.fullmatch(r'L?"(.*)"', inner)
    return "#pragma " + (re.sub(r"\\(.)", r"\1", lit.group(1)) if lit else inner)


def scan(text):
    """Guardrail scan of one source file. Returns a list of violations.

    Comments and literals are set aside first, so neither can hide code nor be mistaken for it.
    Forms that hide a directive or a keyword from a line scan are refused, never interpreted.
    """
    bad = []
    pragmas = [re.compile(a) for a in CFG.get("pragma_allow", [])]
    attributes = [re.compile(a) for a in CFG.get("attribute_allow", [])]
    banned = BANNED + [(b, "contract ban") for b in CFG.get("banned", [])]
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    code_text, bare_text = lexed(text)
    rows = zip(text.split("\n"), code_text.split("\n"), bare_text.split("\n"))
    for n, (line, code, bare) in enumerate(rows, 1):
        def refuse(why):
            bad.append(f"line {n}: {why}: {line.strip()}")

        if TRIGRAPH.search(line):
            refuse("trigraph")
        if CONTINUATION.search(line):
            refuse("line continuation")
        if "%:" in code:
            refuse("digraph directive")
        if "##" in code:
            refuse("token pasting")
        inc = INCLUDE.match(code)
        if inc and not INCLUDE_NAME.match(inc.group(2)):  # a macro names the file, so no scan can follow it
            refuse("computed include")
        for m in PRAGMA_OPERATOR.finditer(code):  # held to the allowlist as the #pragma it stands for
            found = parenthesised(code, bare, m.end())
            if not found or not any(a.search(as_directive(found[0])) for a in pragmas):
                refuse(f"{m.group(1)} not in allowlist")
        spans = [(m.start(), m.end()) for m in BRACKET_ATTRIBUTE.finditer(code)]
        for m in ATTRIBUTE.finditer(code):
            found = parenthesised(code, bare, m.end())
            spans.append((m.start(), found[1] if found else None))
        for start, end in spans:
            if end is None:
                refuse("attribute does not close on its line")
                continue
            written = bare[start:end]
            if NAKED.search(written):
                refuse("naked function")
            elif PLACEMENT.search(written):
                refuse("section placement")
            elif not any(a.search(written) for a in attributes):
                refuse("attribute not in allowlist")
        for pat, why in banned:
            if re.search(pat, code):
                refuse(why)
        if DIRECTIVE_PRAGMA.match(code) and not any(a.search(bare) for a in pragmas):
            refuse("pragma not in allowlist")
    return bad


def fill(template, t, compiler, obj, report, tree, source=None):
    return expand(
        template, id=t["id"], unit=t["unit"], source=source or t["source"], expected=t["expected"],
        address=t["address"], obj=obj, report=report,
        symbols=Path(tree) / SYMBOLS, compiler=compiler,
        tools=Path(tree) / "tools", python=sys.executable,
    )


def launch(command, cwd, environment, capture=True):
    """The one place an adapter runs: through the host shell, in cwd, with the tools' environment.

    Captured output is in the tool's encoding, never assumed to be this system's. With capture off, it goes
    straight through to the caller.
    """
    if not capture:
        return subprocess.run(command, shell=True, cwd=cwd, env=environment.vars)
    if getattr(environment, "run", None):  # a search block's Launcher: no shell where it can, and a kill on a hang
        return environment.run(command, cwd)
    return subprocess.run(command, shell=True, cwd=cwd, env=environment.vars,
                          capture_output=True, text=True, errors="replace")


def adapter(template, t, compiler, obj, report, tree, environment, source=None):
    """Run one filled build or diff adapter command."""
    return launch(fill(template, t, compiler, obj, report, tree, source), tree, environment)


def build_unit(environment, t, compiler, tree, source, objdir, report=""):
    """Run the build adapter on source (as the template should see it) into objdir. Returns (obj, failure log or '')."""
    obj = str(Path(objdir) / f"{t['unit']}.obj")
    b = adapter(CFG["build"], t, compiler, obj, report, tree, environment, source)
    if b.returncode != 0:
        return obj, (b.stderr or b.stdout)[-4000:]
    return obj, ""


def diff_unit_first(environment, t, compiler, tree, source, obj, report, fields=None):
    """Run the diff adapter on a built obj. Returns (result, differ_bytes, log, first_differ or None).

    A dict given as fields is filled with the adapter's whole JSON, for a caller that reads more of it.
    """
    d = adapter(CFG["diff"], t, compiler, obj, report, tree, environment, source)
    try:
        out = json.loads(d.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        return "build-fail", None, f"diff adapter gave no JSON: {d.stderr[-2000:]}", None
    if fields is not None and isinstance(out, dict):
        fields.update(out)
    first = out.get("first_differ")  # optional: the byte offset of the first difference
    first = first if isinstance(first, int) and not isinstance(first, bool) and first >= 0 else None
    if out.get("match") is True and out.get("differ_bytes", 0) == 0:
        return "bytes-match", 0, "", first
    return "differ", int(out.get("differ_bytes", -1)), "", first


def diff_unit(environment, t, compiler, tree, source, obj, report):
    """Run the diff adapter on a built obj. Returns (result, differ_bytes, log) as build_and_diff does."""
    return diff_unit_first(environment, t, compiler, tree, source, obj, report)[:3]


def marker_count(text, tid):
    """How often the ticket's marker stands in a source: `// @decomp <id>` or `/* @decomp <id> */`."""
    return len(re.findall(r"(?://|/\*)[ \t]*@decomp " + re.escape(tid) + r"(?![\w.-])", text))


def build_and_diff(environment, t, compiler, tree, report):
    """Build t's unit in tree with compiler (from compiler_for) and compare. Returns (result, differ_bytes, log)."""
    src = Path(tree) / t["source"]
    if not src.exists():
        return "build-fail", None, f"missing {t['source']}"
    text = src.read_text(encoding="utf-8", errors="replace")
    marks = marker_count(text, t["id"])
    if marks != 1:
        return "guardrail", None, f"expected one '@decomp {t['id']}' marker comment, found {marks}"
    bad = scan(text)
    headers, outside = included(tree, t["source"])
    bad += outside
    for rel in headers:  # project headers obey the same guardrails, however deep the include chain
        bad += [f"{rel}: {v}" for v in scan((Path(tree) / rel).read_text(encoding="utf-8", errors="replace"))]
    if bad:
        return "guardrail", None, "\n".join(bad)
    with tempfile.TemporaryDirectory(prefix="decomp-obj-") as objdir:
        obj, failure = build_unit(environment, t, compiler, tree, t["source"], objdir, report)
        if failure:
            return "build-fail", None, failure
        return diff_unit(environment, t, compiler, tree, t["source"], obj, report)


def frozen_check():
    """Frozen paths on the integration branch must equal the tag that froze them."""
    for tag, paths in CFG["frozen"].items():
        if not git("tag", "--list", tag).strip():
            if tag == "decomp-setup":
                die("no decomp-setup tag; run /decomp-setup", 2)
            continue
        changed = git("diff", "--name-only", tag, CFG["integration_branch"], "--", *paths).split()
        if changed:
            die(f"frozen files differ from tag {tag}: {changed}. Only the skill that set the tag changes them.", 2)


class Worktree:
    def __init__(self, ref):
        self.ref = ref

    def __enter__(self):
        self.path = tempfile.mkdtemp(prefix="decomp-wt-")
        git("worktree", "add", "--detach", self.path, self.ref)
        return self.path

    def __exit__(self, *exc):
        git("worktree", "remove", "--force", self.path, check=False)
        shutil.rmtree(self.path, ignore_errors=True)


# ---------- commands ----------

def cmd_gen_specs(a):
    inv = read_inventory()
    funcs = sorted(inv["functions"], key=lambda f: address_order(f["address"]))
    for u in inv["units"]:
        mine = [f for f in funcs if f["unit"] == u["id"]]
        inn = [f for f in mine if f["scope"] == "in"]
        out = [f for f in mine if f["scope"] != "in"]
        lines = [
            f"# Unit {u['id']}", "",
            f"Source: `{u['source']}`. Range {u['start']} to {u['end']}. Evidence: {u.get('evidence', 'address order')}.", "",
            "**Success:** every ticket below reaches `matched` through `tools/decomp.py`, with the functions "
            "in the contract's order in the source file (address order unless it says otherwise), each "
            "under its `@decomp <id>` marker comment.", "",
            f"In scope: {len(inn)} functions, {sum(f['size'] for f in inn)} B.", "",
            "| Ticket | Size | Tier |", "| --- | --- | --- |",
        ]
        for f in inn:
            lines.append(f"| {f['id']} | {f['size']} | {tier(f['size'])} |")
        if out:
            lines += ["", "## Excluded", "", "| Address | Size | Scope | Evidence |", "| --- | --- | --- | --- |"]
            for f in out:
                lines.append(f"| {f['address']} | {f['size']} | {f['scope']} | {f.get('evidence', '')} |")
        p = ROOT / "units" / f"{u['id']}.md"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    print(f"wrote {len(inv['units'])} unit specs")


def cmd_gen_tickets(a):
    inv = read_inventory()
    units = {u["id"]: u for u in inv["units"]}
    made = kept = 0
    for f in inv["functions"]:
        key = f["key"]
        if f["scope"] != "in":
            continue
        tid = f["id"]
        plain = HEX.fullmatch(f["address"])
        fields = {
            "id": tid, "unit": f["unit"], "address": f"0x{int(f['address'], 16):08X}" if plain else f["address"],
            "size": f["size"], "tier": tier(f["size"]), "source": units[f["unit"]]["source"],
            "expected": f.get("expected") or f"expected/{key}.bin", "status": "open", "claimed_by": "", "claimed_at": "",
        }
        body = "## Notes\n"
        if ticket_path(tid).exists():
            old, body = read_ticket(tid)
            for k in ("status", "claimed_by", "claimed_at"):
                fields[k] = old.get(k, "")
            kept += 1
        else:
            made += 1
        write_ticket(fields, body)
    print(f"tickets: {made} new, {kept} kept")


def cmd_next(a):
    if bool(a.first) != bool(a.reason):
        die("next: --first and --reason go together")
    ts = [t for t in all_tickets()]
    busy = {t["unit"] for t in ts if t["status"] in BUSY}
    ready = [t for t in ts if t["status"] in READY and t["unit"] not in busy]
    order = {name: i for i, name in enumerate([n for n, _ in TIERS] + ["LARGE"])}
    ready.sort(key=lambda t: (order[t["tier"]], int(t["size"]), address_order(t["address"])))
    if a.first:
        head = next((t for t in ready if t["id"] == a.first), None)
        if not head:
            die(f"next --first: {a.first} is not a ready ticket")
        ready.remove(head)
        ready.insert(0, head)
    picked, units = [], set()
    for t in ready:  # one ticket per unit: units are one writer at a time
        if t["unit"] not in units:
            picked.append(t)
            units.add(t["unit"])
    if a.first:
        event_out_of_order(a.first, a.reason)
    for t in picked[: a.n]:
        print(f"{t['id']} {t['tier']} {t['size']}B {ticket_path(t['id']).relative_to(ROOT).as_posix()}")


def lockfile(name):
    d = checkout_dir() / "locks"  # one set per repository, so every worktree sees a claim
    d.mkdir(parents=True, exist_ok=True)
    return d / f"{name}.lock"


def take_lock(name, by):
    try:
        fd = os.open(lockfile(name), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        die(f"locked: {name}: {lockfile(name).read_text().strip()}", 3)
    os.write(fd, f"{by} {now()}\n".encode())
    os.close(fd)


def cmd_claim(a):
    move(a.id, "claim", by=a.by)
    print(f"claimed {a.id}")


def cmd_release(a):
    t, _ = read_ticket(a.id)
    if a.to not in ("open", "blocked-reference"):
        die("release --to open|blocked-reference")
    event = ("block" if a.to == "blocked-reference" else
             "unblock" if t["status"] == "blocked-reference" else "release")
    if not may_move(t, event):  # the user typed `release`, so name it and every status it accepts for --to
        accepted = "claimed" if a.to == "blocked-reference" else "claimed or blocked-reference"
        die(f"{a.id} is {t['status']}; release needs {accepted}")
    print(f"{a.id} -> {move(a.id, event)}")


def run_adapter(name, environment, **values):
    """Run an adapter that reports to the caller, in the project root. Exit 1, naming its exit code, when it fails.

    Its output goes straight through, in whatever encoding the tool writes.
    """
    if not CFG.get(name):
        die(f"decomp.json has no `{name}` adapter command; run /decomp-setup")
    code = launch(tool_command(CFG[name], **values), ROOT, environment, capture=False).returncode
    if code:
        die(f"the {name} adapter failed (exit {code})")


def cmd_inventory(a):
    environment = doctor(full=True)
    if git("tag", "--list", "decomp-start").strip() and not a.redo:
        die("the decomp-start tag exists, so inventory.json and expected/ are frozen; nothing was written. "
            "Redoing the inventory is /decomp-start's redo flow: with the user's go-ahead, run `inventory --redo`.", 2)
    run_adapter("inventory", environment)


def cmd_disasm(a):
    t, _ = read_ticket(a.id)
    environment, _ = prepare(t, judge=False)
    run_adapter("disasm", environment, expected=t["expected"], address=t["address"])


# ---------- check trail and the template-search gate ----------

TRAIL = "trail.jsonl"  # the check trail: this machine only, never committed, shared by every worktree
GATE_OPENS = ("register-allocation", "statement-order", "expression-shape")  # categories small source variations fix
GATE_CLOSES = ("reference-gap", "data-layout", "calling-convention", "optimization", "unit-order", "build-fail")
GATE_STALL = 3  # attempts with no fall in differ_bytes that open the gate


def trail(tid):
    """The ticket's check trail, oldest first: one record per `check` run and per template round."""
    p = checkout_dir() / TRAIL
    if not p.exists():
        return []
    return [r for r in (json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()) if r["ticket"] == tid]


def append_trail(tid, by, result, differ_bytes, category):
    """Add one attempt to the check trail. by is `check` or `search`."""
    p = checkout_dir() / TRAIL
    p.parent.mkdir(parents=True, exist_ok=True)
    rec = {"unix": now(), "ticket": tid, "by": by, "result": result, "differ_bytes": differ_bytes, "category": category}
    with p.open("a", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(rec, sort_keys=True) + "\n")


def stalled(entries):
    """True when the last GATE_STALL attempts show no fall in differ_bytes: none is closer than the first of them."""
    last = [float("inf") if e["differ_bytes"] is None else e["differ_bytes"] for e in entries[-GATE_STALL:]]
    return len(last) == GATE_STALL and last[-1] != float("inf") and min(last[1:]) >= last[0]


def gate(t):
    """Whether template search is open for ticket t, from its tier and check trail: (open, reason)."""
    entries = trail(t["id"])
    if CFG.get("template_search") is not True:
        return False, "the contract does not allow template search"
    if t["tier"] == "TINY":
        return False, "a TINY ticket never uses template search"
    if not entries:
        return False, "no check has run for this ticket on this machine"
    latest = entries[-1]
    if latest["by"] == "check" and latest["result"] == "bytes-match":  # a round's match is not one until check says so
        return False, "the latest check matched"
    category = latest["category"]
    if category in GATE_CLOSES:
        return False, f"the latest category, {category}, needs a stop or a report, which no template fixes"
    if category in GATE_OPENS:
        return True, f"the latest category is {category}"
    if stalled(entries):
        return True, f"differ_bytes has not fallen over the last {GATE_STALL} attempts"
    return False, (f"it opens on a latest category of {', '.join(GATE_OPENS[:-1])} or {GATE_OPENS[-1]}, "
                   f"or after {GATE_STALL} attempts with no fall in differ_bytes")


def cmd_check(a):
    t, _ = read_ticket(a.id)
    if a.category and a.category not in CATEGORIES:
        die(f"unknown category {a.category}; the mismatch categories are {', '.join(sorted(CATEGORIES))}")
    environment, compiler = prepare(t)
    report = str(Path(tempfile.mkdtemp(prefix="decomp-rep-")) / "diff.txt")
    result, n, log = build_and_diff(environment, t, compiler, os.getcwd(), report)
    category = "" if result == "bytes-match" else a.category or ("build-fail" if result == "build-fail" else "")
    append_trail(t["id"], "check", result, n, category)
    is_open, reason = gate(t)
    print(json.dumps({"result": result, "differ_bytes": n, "report": report, "search_open": is_open, "search_reason": reason}))
    if log:
        print(log)


def cmd_verify(a):
    frozen_check()
    t, _ = read_ticket(a.id)
    environment, compiler = prepare(t, full=True, judge=False)
    refuse_unless(t, "bytes-match")
    if a.category == "none":  # a writer that matched reports no category
        a.category = None
    if a.category and a.category not in CATEGORIES:
        die(f"unknown category {a.category}")
    template_round = kept_round(a.id) if a.template_round else None
    stop_if_edition_differs(environment, t)
    integ, branch = CFG["integration_branch"], a.branch or f"w/{a.id}"
    changed = git("diff", "--name-only", f"{integ}...{branch}").split()
    stamp = now()
    aid = next_attempt_id(a.id)
    evidence = ledger(f"evidence/{aid}.txt")
    rec = {"id": aid, "ticket": a.id, "unix": stamp, "model": a.model, "tier": t["tier"],
           "category": a.category or "", "differ_bytes": None, "evidence": evidence.relative_to(ROOT).as_posix()}
    outside = [p for p in changed if p != t["source"]]
    if outside:
        result, n, log = "guardrail", None, f"branch touches guarded paths: {outside}"
        swept = [q for q in outside if q.startswith(("tickets/", "ledger/"))]
        if swept:
            log += f"\n{swept} are status files: the branch was committed too broadly (stage named paths only)"
        src = b""
    else:
        src = git_bytes("show", f"{branch}:{t['source']}")
        with Worktree(integ) as tree:
            dest = Path(tree) / t["source"]
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(src)
            result, n, log = build_and_diff(environment, t, compiler, tree, str(evidence))
    rec.update(result=result, differ_bytes=n, source_sha256=sha(src))
    if result == "bytes-match":
        rec["category"] = ""
    elif not rec["category"]:
        rec["category"] = {"build-fail": "build-fail", "guardrail": "unknown"}.get(result, "unknown")
    if log:
        with evidence.open("a", encoding="utf-8", newline="\n") as f:
            f.write(log + "\n")
    if template_round:  # in the evidence file, so the ledger's committed fields stay as they are
        with evidence.open("a", encoding="utf-8", newline="\n") as f:
            f.write(ROUND_EVIDENCE + json.dumps(template_round, sort_keys=True) + "\n")
    append("attempts.jsonl", rec)
    if result == "bytes-match":
        move(a.id, "bytes-match")
    print(json.dumps({"attempt": aid, "result": result, "differ_bytes": n}))
    sys.exit(0 if result == "bytes-match" else 4)


def cmd_audit(a):
    t, _ = read_ticket(a.id)
    refuse_unless(t, f"audit-{a.verdict}")
    last = [r for r in records("attempts.jsonl") if r["ticket"] == a.id][-1]
    branch = a.branch or f"w/{a.id}"
    if a.verdict == "pass" and sha(git_bytes("show", f"{branch}:{t['source']}")) != last["source_sha256"]:
        die("branch changed since verify; record a fail, then verify again", 2)
    if a.verdict == "pass":
        move(a.id, "audit-pass", last=last, auditor=a.auditor)
        print(f"matched {a.id} (attempt {last['id']})")
    else:
        move(a.id, "audit-fail", last=last, auditor=a.auditor)
        append_note(a.id, f"audit-fail: {a.note or 'see auditor'}")
        print(f"audit failed {a.id}; ticket back to claimed")


def cmd_integrate(a):
    t, _ = read_ticket(a.id)
    refuse_unless(t, "integrate")
    branch = a.branch or f"w/{a.id}"
    r = subprocess.run(["git", "merge-base", "--is-ancestor", branch, CFG["integration_branch"]], cwd=ROOT)
    if r.returncode != 0:
        die(f"{branch} is not merged into {CFG['integration_branch']}")
    move(a.id, "integrate")
    print(f"integrated {a.id}")


def includes(text):
    """The file each include directive of a source text names. Comments and literals cannot fake one."""
    code, bare = lexed(text.replace("\r\n", "\n").replace("\r", "\n"))
    names = set()
    for c, b in zip(code.split("\n"), bare.split("\n")):
        m = INCLUDE.match(c)
        name = m and INCLUDE_NAME.match(b, m.start(2))
        if name:
            names.add(name.group(1) or name.group(2))
    return names


def in_tree(tree, parts):
    """The file under tree that these path parts name, whatever case they are written in. None when none.

    A compiler on a case-blind file system, or behind a compatibility layer, opens `Types.h`
    for `types.h`, so the scan follows it there too.
    """
    here = Path(tree)
    for part in parts:
        if not here.is_dir():
            return None
        same = [e for e in here.iterdir() if e.name.casefold() == part.casefold()]
        if not same:
            return None
        here = next((e for e in same if e.name == part), same[0])
    return here if here.is_file() else None


def included(tree, source):
    """Every file in the tree that source includes, directly or through another header.

    Returns (their paths relative to tree, violations). A name is looked up beside the
    including file and under include/. One that points outside the project is a violation.
    One found nowhere in the tree is taken to be the toolchain's own header.
    """
    found, bad, todo = [], [], [source]
    seen = {source.casefold()}
    while todo:
        rel = todo.pop()
        text = (Path(tree) / rel).read_text(encoding="utf-8", errors="replace")
        for name in sorted(includes(text)):
            spelled = name.replace("\\", "/")
            inside = 0
            if not spelled.startswith("/") and not re.match(r"[A-Za-z]:", spelled):
                for base in (os.path.dirname(rel), "include"):
                    parts = os.path.normpath(os.path.join(base, spelled)).replace("\\", "/").split("/")
                    if parts[0] == "..":
                        continue
                    inside += 1
                    hit = in_tree(tree, parts)
                    hit = hit and hit.relative_to(tree).as_posix()
                    if hit and hit.casefold() not in seen:
                        seen.add(hit.casefold())
                        found.append(hit)
                        todo.append(hit)
            if not inside:
                bad.append(f"{rel}: include outside the project: {name}")
    return sorted(found), bad


CANDIDATE = re.compile(r"c/[0-9A-Za-z_.-]+")  # a candidate ref: a branch holding a change to frozen paths


def candidate_ref(a):
    """The candidate ref a `revalidate` was given, or exit 2 when it was not given one, alone."""
    ref = a.candidate or ""
    if a.ref or a.header:
        die("--candidate rebuilds every matched ticket on a c/<slug> branch: it takes no --ref and no --header", 2)
    known = subprocess.run(["git", "show-ref", "--verify", "--quiet", f"refs/heads/{ref}"], cwd=ROOT).returncode == 0
    if not CANDIDATE.fullmatch(ref) or not known:
        die(f"--candidate takes a branch named c/<slug>; '{ref}' is not one. "
            "A repair ref goes to `revalidate --ref`.", 2)
    return ref


def judge_candidate(ref):
    """Hand a candidate ref to its own copy of this tool, run in a clean worktree of it. Records nothing.

    The copy in that tree rebuilds every ticket this project holds matched, so the candidate's
    tool, adapters, manifest, and contract are the ones that judge it.
    """
    with Worktree(ref) as tree:
        own = Path(tree) / "tools" / "decomp.py"
        if not own.exists():
            die(f"{ref} holds no tools/decomp.py to judge it", 2)
        cmd = [sys.executable, str(own), "revalidate", "--candidate", ref, "--judged-for", str(ROOT)]
        code = subprocess.run(cmd, cwd=tree).returncode
    sys.exit(code)


def cmd_revalidate(a):
    judging = bool(a.judged_for)  # this copy sits in the candidate's worktree and judges it
    if a.candidate or judging:
        candidate = candidate_ref(a)
        if not judging:
            judge_candidate(candidate)
        if git("rev-parse", "HEAD") != git("rev-parse", f"refs/heads/{candidate}"):
            die("--judged-for is set only by this tool, in its own worktree of the candidate; "
                "run `revalidate --candidate c/<slug>`", 2)
    gone = []
    if judging:  # the one exception to the frozen check: the candidate exists to change frozen paths
        matched_ids = [t["id"] for t in all_tickets(Path(a.judged_for)) if t["status"] in MATCHED]
        gone = [i for i in matched_ids if not ticket_path(i).exists()]
        ts = [read_ticket(i)[0] for i in matched_ids if i not in gone]
    else:
        frozen_check()
        ts = [t for t in all_tickets() if t["status"] in REGRESSABLE]
    built_with = {t["unit"]: compiler_for(t["unit"]) for t in ts}  # stops here, before any status is written
    environment = doctor(need=tools_needed([]) | {CFG.get("compiler", "")})
    unusable = environment.unusable
    ref = candidate if judging else a.ref or CFG["integration_branch"]
    on_integ = not judging and ref == CFG["integration_branch"]
    if not on_integ and not judging:
        outside = [p for p in git("diff", "--name-only", f"{CFG['integration_branch']}...{ref}").split()
                   if not p.startswith("include/") and p != SYMBOLS]
        if outside:
            event_rejected_repair(ref)
            die(f"{ref} touches paths outside include/ and {SYMBOLS}: {outside}", 5)
    bad, skipped, measured = len(gone), 0, 0
    for i in gone:
        print(f"REGRESSED {i} on {ref}: the candidate holds no such ticket")
    with (contextlib.nullcontext(str(ROOT)) if judging else Worktree(ref)) as tree:
        if a.header:
            name = Path(a.header).name.casefold()  # every ticket that reaches the header, through any chain
            ts = [t for t in ts if (Path(tree) / t["source"]).exists() and any(
                Path(h).name.casefold() == name for h in included(tree, t["source"])[0])]
        for t in ts:
            why = ("this machine's edition holds it differently" if edition_differs(environment, t) else
                   f"its compiler '{built_with[t['unit']]}' is not usable here" if built_with[t["unit"]] in unusable
                   else "")
            if why:  # its bytes cannot be measured on this machine, either way
                skipped += 1
                print(f"SKIPPED {t['id']}: {why}")
                continue
            measured += 1
            report = str(Path(tempfile.mkdtemp(prefix="decomp-rep-")) / "diff.txt")
            result, n, _ = build_and_diff(environment, t, built_with[t["unit"]], tree, report)
            ok = result == "bytes-match"
            if not ok:
                bad += 1
                print(f"REGRESSED {t['id']} on {ref}: {result} {n}")
            if on_integ:
                if ok and may_move(t, "revalidate-pass"):
                    move(t["id"], "revalidate-pass")
                elif not ok:
                    move(t["id"], "regress")
    if bad and not on_integ and not judging:
        event_rejected_repair(ref)
    print(f"revalidated {measured} on {ref}: {bad} regressed, {skipped} skipped")
    if bad and not (judging and skipped):  # a candidate that was not fully measured is exit 6, whatever it broke
        sys.exit(5)
    if skipped and not on_integ:  # a repair or candidate is proven only where every match it could break was rebuilt
        print(f"ENVIRONMENT: {skipped} matched tickets could not be measured on this machine", file=sys.stderr)
        die(f"{ref} is not proven here; revalidate it on a machine that can build every ticket above.", ENV_EXIT)


def cmd_note(a):
    append_note(a.id, " ".join(a.text))


def grams(data):
    if len(data) < 3:
        return {data} if data else set()
    return {data[i:i + 3] for i in range(len(data) - 2)}


def cmd_similar(a):
    t, _ = read_ticket(a.id)
    mine = grams((ROOT / t["expected"]).read_bytes())
    scored = []
    for o in all_tickets():
        if o["status"] in MATCHED and o["id"] != a.id:
            g = grams((ROOT / o["expected"]).read_bytes())
            if mine and g:
                scored.append((len(mine & g) / len(mine | g), o))
    for s, o in sorted(scored, key=lambda x: -x[0])[: a.n]:
        print(f"{s:.2f} {o['id']} {o['size']}B {o['source']}")


def cmd_lock(a):
    take_lock(a.name, a.by)
    print(f"locked {a.name}")


def cmd_unlock(a):
    lockfile(a.name).unlink(missing_ok=True)
    print(f"unlocked {a.name}")


LINK_MISMATCH_EXIT = 4  # the linked file is not the edition on this machine


def link_plan(environment, ts, inv):
    """Which units link from source, and the raw blocks of the target around them, on doctor's environment.

    Returns (source units: unit id to its in-scope functions in offset order, blocks, in-scope bytes).
    A unit links from source only when every in-scope function in it is integrated or revalidated
    and none is on this edition's differs list. Every other byte is a raw block.
    """
    status = {t["id"]: t for t in ts}
    funcs = inv["functions"]
    inn = [f for f in funcs if f["scope"] == "in"]
    by_unit = {}
    for f in inn:
        by_unit.setdefault(f["unit"], []).append(f)
    source = {}
    for unit, mine in by_unit.items():
        held = [status.get(f["id"]) for f in mine]
        if all(t and t["status"] in FINISHED and not edition_differs(environment, t) for t in held):
            missing = [f["id"] for f in mine if not isinstance(f.get("offset"), int)]
            if missing:
                die(f"inventory.json gives no file `offset` for {missing}; the link places a function by it. "
                    "Add it through the change flow (an inventory redo).")
            source[unit] = sorted(mine, key=lambda f: f["offset"])
    size = Path(toolchain()["target"]["path"]).stat().st_size
    placed = sorted((f["offset"], f["offset"] + f["size"]) for mine in source.values() for f in mine)
    blocks, at = [], 0
    for start, end in placed + [(size, size)]:
        if start > at:
            blocks.append({"offset": at, "size": start - at})
        at = max(at, end)
    return source, blocks, sum(f["size"] for f in inn)


def link_owner(offset, source, blocks, inv):
    """What owns a file offset of the target: a unit's function, the header, or a raw block."""
    for unit, mine in source.items():
        for f in mine:
            if f["offset"] <= offset < f["offset"] + f["size"]:
                return f"unit {unit} function {f['id']}"
    first = min((f["offset"] for f in inv["functions"] if isinstance(f.get("offset"), int)), default=None)
    if first is not None and offset < first:
        return "header"
    for b in blocks:
        if b["offset"] <= offset < b["offset"] + b["size"]:
            return f"raw block 0x{b['offset']:X} to 0x{b['offset'] + b['size']:X}"
    return "past the end of the target"


def cmd_link(a):
    if CFG.get("link_unavailable"):
        die(f"a whole-binary link is not available for this target: {CFG['link_unavailable']}", LINK_UNAVAILABLE_EXIT)
    if not CFG.get("link"):
        die("this project has no link adapter: decomp.json has no `link` command. It reaches a project past "
            "setup through the skill-upgrade section of /decomp-setup, as a change on a candidate branch.")
    ts = all_tickets()
    inv = read_inventory()
    whole = {t["unit"] for t in ts} - {t["unit"] for t in ts if t["status"] not in FINISHED}
    built_with = {u: compiler_for(u) for u in sorted(whole)}
    environment = doctor(need=tools_needed(built_with.values()))
    edition = environment.edition
    target = Path(toolchain()["target"]["path"])
    source, blocks, in_scope = link_plan(environment, ts, inv)
    out = local_dir() / "link" / target.name
    out.parent.mkdir(parents=True, exist_ok=True)
    out.unlink(missing_ok=True)
    from_source = sum(f["size"] for mine in source.values() for f in mine)
    linked = dict(edition=edition["name"], units=sorted(source), source_bytes=from_source, in_scope_bytes=in_scope)
    first, why = None, ""
    with Worktree(CFG["integration_branch"]) as tree:
        objdir = Path(tempfile.mkdtemp(prefix="decomp-link-"))
        objects = []
        for unit, mine in sorted(source.items()):
            t = next(t for t in ts if t["unit"] == unit)
            obj = objdir / f"{unit}.obj"
            b = adapter(CFG["build"], t, built_with[unit], str(obj), "", tree, environment)
            if b.returncode != 0:
                why = f"unit {unit} did not build: {(b.stderr or b.stdout)[-2000:]}"
                break
            objects.append({"unit": unit, "source": t["source"], "obj": str(obj), "functions": [
                {k: f[k] for k in ("id", "address", "offset", "size")} for f in mine]})
        if not why:
            plan = objdir / "plan.json"
            plan.write_text(json.dumps({"objects": objects, "blocks": blocks, "output": str(out)}, indent=1),
                            encoding="utf-8")
            r = launch(tool_command(CFG["link"], plan=plan, out=out), tree, environment)
            if r.returncode != 0 or not out.is_file():
                why = f"the link adapter failed (exit {r.returncode}): {(r.stderr or r.stdout)[-2000:]}"
    share = f"{from_source} / {in_scope} in-scope code B from source ({100 * from_source / in_scope:.2f}%)" \
        if in_scope else "no in-scope code"
    if why:
        event_link("fail", **linked)
        print(f"link: fail; {share}; output {out}")
        die(why)
    got, want = out.read_bytes(), target.read_bytes()
    more = {"sha256": sha(got), "size": len(got)}
    result = "pass"
    if got != want:
        result = "mismatch"
        first = next((i for i, (x, y) in enumerate(zip(got, want)) if x != y), min(len(got), len(want)))
        more["first_differ"] = first
    event_link(result, **linked, **more)
    print(f"link: {result}; {share}; output {out}")
    if first is not None:
        print(f"first difference at file offset 0x{first:X}: {link_owner(first, source, blocks, inv)}; "
              f"output {len(got)} B sha256 {sha(got)[:16]}, edition '{edition['name']}' {len(want)} B sha256 "
              f"{sha(want)[:16]}")
        sys.exit(LINK_MISMATCH_EXIT)


LINK_MILESTONE_FLOOR = 16 * 1024  # bytes: the default milestone never drops below this


def link_milestone(total):
    """The milestone size in bytes: `link_milestone` in decomp.json (a percentage like "10%" or a byte
    count), else 5% of the in-scope bytes with a floor of 16 KB. An override is used as given."""
    want = CFG.get("link_milestone")
    if want is None:
        return max(LINK_MILESTONE_FLOOR, -(-total * 5 // 100))
    text = str(want).strip()
    try:
        if text.endswith("%"):
            return -(-int(float(text[:-1]) * total) // 100)
        return int(text)
    except ValueError:
        die(f"decomp.json `link_milestone` is {want!r}; use a percentage such as \"5%\" or a byte count.")


def milestone_line(ts):
    """The report's milestone state: due when units fully matched since the last link reach the milestone."""
    if CFG.get("link_unavailable"):
        return "not due (link unavailable for this target)"
    linked = set()
    for e in records("events.jsonl"):
        if e.get("event") == "link":
            linked = set(e.get("units", []))
    open_units = {t["unit"] for t in ts if t["status"] not in FINISHED}
    fresh = sum(t["size"] for t in ts if t["unit"] not in open_units and t["unit"] not in linked)
    size = link_milestone(sum(t["size"] for t in ts))
    return f"{'due' if fresh >= size else 'not due'} ({fresh} B newly matched of {size} B)"


def project_state(ts):
    """finished, stuck or more. Regressed and blocked-reference tickets are not ready work here."""
    if ts and all(t["status"] == "revalidated" for t in ts):
        return "finished"
    if any(t["status"] not in ("regressed", "blocked-reference", "revalidated") for t in ts):
        return "more"
    return "stuck"


def cmd_report(a):
    ts = all_tickets()
    atts = records("attempts.jsonl")
    matches = records("matches.jsonl")
    inv = read_inventory()
    total_b = sum(t["size"] for t in ts)
    done = [t for t in ts if t["status"] in MATCHED]
    done_b = sum(t["size"] for t in done)
    pct = lambda x, y: f"{100 * x / y:.2f}%" if y else "n/a"
    print(f"bytes:     {done_b} / {total_b} ({pct(done_b, total_b)})")
    print(f"functions: {len(done)} / {len(ts)} ({pct(len(done), len(ts))})")
    for name in ("TINY", "SMALL", "MEDIUM", "LARGE"):
        tt = [t for t in ts if t["tier"] == name]
        dd = [t for t in tt if t["status"] in MATCHED]
        print(f"  {name:<6} {len(dd)} / {len(tt)} functions, {sum(t['size'] for t in dd)} / {sum(t['size'] for t in tt)} B")
    status = {}
    for t in ts:
        status[t["status"]] = status.get(t["status"], 0) + 1
    print("status:    " + ", ".join(f"{k} {v}" for k, v in sorted(status.items())))
    held = [f"{t['id']} {t['claimed_by']}" for t in ts if t["status"] in BUSY and t["claimed_by"]]
    print("claims:    " + (", ".join(held) or "none"))
    excl = {}
    for f in inv["functions"]:
        if f["scope"] != "in":
            excl[f["scope"]] = excl.get(f["scope"], 0) + 1
    print("excluded:  " + (", ".join(f"{k} {v}" for k, v in sorted(excl.items())) or "none"))
    print(f"state:     {project_state(ts)}")
    print(f"milestone: {milestone_line(ts)}")
    by_model = {}
    for m in matches:
        c = by_model.setdefault(m["model"], [0, 0])
        c[0] += 1
        c[1] += m["size"]
    print("credit:    " + (", ".join(f"{k} {v[0]} fn {v[1]} B" for k, v in sorted(by_model.items())) or "none"))
    days = {}
    for m in matches:
        d = time.strftime("%Y-%m-%d", time.gmtime(m["unix"]))
        days[d] = days.get(d, 0) + m["size"]
    for d in sorted(days)[-7:]:
        print(f"  {d} UTC +{days[d]} B")
    tried = {r["ticket"] for r in atts}
    if matches:
        print(f"attempts per match: {len([r for r in atts if r['ticket'] in {m['ticket'] for m in matches}]) / len(matches):.2f}")

    # Learning: match rate of attempts before and after the latest pattern, excluding its proof tickets.
    pats = parse_patterns()
    if pats:
        last = max(p["added"] for p in pats)
        proof = {p["proven"] for p in pats}
        pool = [r for r in atts if r["ticket"] not in proof and r["result"] in ("bytes-match", "differ", "build-fail")]
        before = [r for r in pool if r["unix"] < last]
        after = [r for r in pool if r["unix"] >= last]
        rate = lambda rs: pct(sum(r["result"] == "bytes-match" for r in rs), len(rs))
        print(f"learning:  match rate {rate(before)} over {len(before)} attempts before latest pattern, {rate(after)} over {len(after)} after")

    # Early warning: many small attempts, no match at all.
    small = [r for r in atts if r["tier"] in ("TINY", "SMALL")]
    if len(small) >= EARLY_WARNING_ATTEMPTS and not any(r["result"] == "bytes-match" for r in atts):
        print(f"EARLY-WARNING: {len(small)} TINY/SMALL attempts, no match. Suspect the contract's compiler or flags; stop and tell the user to revisit /decomp-setup.")

    # OPEN.md: latest category of every unsolved ticket, grouped.
    latest = {}
    for r in atts:
        latest[r["ticket"]] = r
    groups = {}
    for t in ts:
        r = latest.get(t["id"])
        if t["status"] not in MATCHED and r and r["result"] != "bytes-match" and r.get("category"):
            groups.setdefault(r["category"], []).append(t["id"])
    lines = ["# Open problems", "", f"Generated by `decomp.py report` at {now()}. Categories with {OPEN_THRESHOLD}+ unsolved tickets.", ""]
    for c, ids in sorted(groups.items(), key=lambda x: -len(x[1])):
        if len(ids) >= OPEN_THRESHOLD:
            lines.append(f"- `{c}`: {len(ids)} tickets ({', '.join(ids[:5])}{', ...' if len(ids) > 5 else ''})")
    (ROOT / "OPEN.md").write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    print(f"open:      {sum(len(v) >= OPEN_THRESHOLD for v in groups.values())} recurring categories (OPEN.md)")

    # PATTERNS.md lint.
    status_of = {t["id"]: t["status"] for t in ts}
    for p in pats:
        if status_of.get(p["proven"]) not in MATCHED:
            print(f"PATTERN-UNPROVEN: line {p['line']}: {p['proven']} is not matched")
    for n in bad_pattern_lines():
        print(f"PATTERN-MALFORMED: line {n}")
    print(f"tried:     {len(tried)} tickets, {len(atts)} attempts")


PATTERN = re.compile(r"^- .+\[proven: (u\d{4,}-[0-9A-Za-z_.]+)\] \[added: (\d+)\]\s*$")


def pattern_lines():
    p = ROOT / "PATTERNS.md"
    return p.read_text(encoding="utf-8").splitlines() if p.exists() else []


def parse_patterns():
    out = []
    for n, line in enumerate(pattern_lines(), 1):
        m = PATTERN.match(line)
        if m:
            out.append({"line": n, "proven": m.group(1), "added": int(m.group(2))})
    return out


def bad_pattern_lines():
    return [n for n, l in enumerate(pattern_lines(), 1) if l.startswith("- ") and not PATTERN.match(l)]


def cmd_sync(a):
    gh = CFG.get("github") or {}
    if not gh.get("enabled"):
        print("github sync disabled in decomp.json")
        return
    gh_path = shutil.which("gh")
    if not gh_path:
        die("gh was not found on PATH; install it to mirror progress to GitHub.", ENV_EXIT)
    if subprocess.run([gh_path, "auth", "status"], capture_output=True).returncode != 0:
        die("gh is not logged in; run `gh auth login`.", ENV_EXIT)
    repo = gh["repo"]
    state_p = ledger("github.json")
    state = json.loads(state_p.read_text()) if state_p.exists() else {"units": {}, "progress": None}
    ts = all_tickets()
    units = {}
    for t in ts:
        units.setdefault(t["unit"], []).append(t)

    def push(key, title, body, close):
        entry = state["units"].get(key) if key != "progress" else state.get("progress")
        h = sha(body.encode())
        f = Path(tempfile.mkdtemp(prefix="decomp-gh-")) / "body.md"
        f.write_text(body, encoding="utf-8")
        if not entry:
            out = subprocess.run(["gh", "issue", "create", "--repo", repo, "--title", title, "--body-file", str(f)],
                                 capture_output=True, text=True, check=True).stdout.strip()
            entry = {"number": int(out.rstrip("/").split("/")[-1]), "hash": h, "closed": False}
        elif entry["hash"] != h:
            subprocess.run(["gh", "issue", "edit", str(entry["number"]), "--repo", repo, "--body-file", str(f)], check=True)
            entry["hash"] = h
        if close and not entry["closed"]:
            subprocess.run(["gh", "issue", "close", str(entry["number"]), "--repo", repo], check=True)
            entry["closed"] = True
        if key == "progress":
            state["progress"] = entry
        else:
            state["units"][key] = entry
        return entry["number"]

    nums = {}
    for u, tt in sorted(units.items()):
        tt.sort(key=lambda t: address_order(t["address"]))
        body = "\n".join([f"Unit `{u}`: `{tt[0]['source']}`. Generated by `decomp.py sync`; do not edit.", ""] + [
            f"- [{'x' if t['status'] in MATCHED else ' '}] `{t['id']}` {t['size']} B {t['tier']} ({t['status']})" for t in tt])
        nums[u] = push(u, f"decomp unit {u}", body + "\n", all(t["status"] in MATCHED for t in tt))
    total = sum(t["size"] for t in ts)
    done = sum(t["size"] for t in ts if t["status"] in MATCHED)
    lines = [f"Verified byte progress: **{done} / {total} B** ({100 * done / max(total, 1):.2f}%), "
             f"{sum(t['status'] in MATCHED for t in ts)} / {len(ts)} functions. Generated by `decomp.py sync`.", ""]
    for u, tt in sorted(units.items()):
        d = sum(t["status"] in MATCHED for t in tt)
        lines.append(f"- [{'x' if d == len(tt) else ' '}] #{nums[u]} `{u}` {d} / {len(tt)}")
    first = state.get("progress") is None
    n = push("progress", "decomp progress", "\n".join(lines) + "\n", False)
    if first:
        subprocess.run(["gh", "issue", "pin", str(n), "--repo", repo], check=False)
    state_p.write_text(json.dumps(state, indent=1, sort_keys=True), encoding="utf-8")
    print(f"synced {len(units)} unit issues and progress issue #{n}")


# ---------- template search ----------
#
# The stages, in the order a round runs them:
#   parse_template   template text -> Template (the choice points and the text between them)
#   one_change       Template -> the seeds that open a round: the baseline and the one-change sweep
#   candidates       Template -> the seeds to try after them, in order
#   Memo.entry       one candidate's source -> its result, through the dedupe layers and a Worker's
#                    build and diff adapters, which a Launcher starts
#   run_block        the workers' loop over candidates: keeps the best, ends by Block's rules
#   summary          the round's result -> the capped JSON the writer reads
# A round's template and results stay in this machine's folder, where the detail form reads them.

SUMMARY_TOKENS = 600  # the summary's size cap
TOKEN_CHARS = 4  # how the cap is measured: characters of the summary's JSON per token
WINDOW_LINES = 7  # diff report lines the summary shows for the best candidate
WINDOW_WIDTH = 120  # characters kept of each of those lines
FAILURE_CHARS = 400  # what the summary keeps of a failure log when no candidate was scored
PERM_MACRO = re.compile(r"\bPERM_[A-Z_]+\b")
CHOICE_CODE = re.compile(r"([A-Za-z_]+)(\d+)")
MAX_CHOICES = 12  # choice points in one template
MAX_LINESWAP_LINES = 5  # lines in one PERM_LINESWAP
MAX_INT_VALUES = 64  # values in one PERM_INT range
KINDS = ("decl-order", "stmt-order", "loop-form", "temp-type", "signedness", "width", "operator",
         "expression-shape", "branch-order", "inlining", "other")  # the levers of decomp-match's MISMATCH.md
HEAD = re.compile(r"@([A-Za-z_]+)(?:[ \t]+(\S+))?")  # a choice point's first argument: @label kind
LIKELIHOOD = re.compile(r"%(\d+(?:\.\d*)?|\.\d+)(?:\s+|$)")  # an alternative's leading %0.7
STEER_TAG = re.compile(r"/\*\s*steer:(.*?)\*/\s*", re.S)  # leads a steering alternative: /* steer: <reason> */
# A choice point: its label, its alternatives' source text, its kind, one likelihood per alternative
# (None: all alike), and per alternative the reason it steers the compiler (None: the alternative is
# natural; an empty tuple: all natural). A Reference is a later PERM_VAR(label): the same pick again.
Choice = collections.namedtuple("Choice", "label alternatives kind likelihoods steers", defaults=("other", None, ()))
Reference = collections.namedtuple("Reference", "label")
Score = collections.namedtuple("Score", "result differ_bytes log first_differ", defaults=(None,))  # first_differ: optional


def steer(choice, pick):
    """The reason one alternative of a choice point steers the compiler, or None when it is natural."""
    return choice.steers[pick] if choice.steers else None


def picked(self, pick):
    """The source one alternative of a choice point stands for."""
    why = steer(self, pick)
    text = self.alternatives[pick]
    if why is None:
        return text
    note = f" /* fakematch: {why} */"
    return "\n".join(line + note if line.strip() else line for line in text.split("\n"))


Choice.picked = picked


def choice_label(n):
    """The label of the n-th choice point: A to Z, then AA, AB, and on."""
    return (choice_label(n // 26 - 1) if n >= 26 else "") + chr(ord("A") + n % 26)


def split_alternatives(code, text, start, end):
    """The alternatives between start and end: text split at the commas that sit inside no bracket in code."""
    out, depth, at = [], 0, start
    for i in range(start, end):
        depth += {"(": 1, "[": 1, "{": 1, ")": -1, "]": -1, "}": -1}.get(code[i], 0)
        if code[i] == "," and depth == 0:
            out.append(text[at:i].strip())
            at = i + 1
    return out + [text[at:end].strip()]


class Template:
    """A unit's source with choice points: parts holds the text between them and each Choice, in order.

    A candidate is one alternative per choice point. It is named three ways: a vector (one index per
    choice point), a seed (the vector as one mixed-radix integer, the first choice point lowest), and a
    choice code (`A1 B0`). Seed 0 is the baseline: every first alternative.
    """

    def __init__(self, parts):
        self.parts = parts
        self.choices = [p for p in parts if isinstance(p, Choice)]

    def space(self):
        n = 1
        for c in self.choices:
            n *= len(c.alternatives)
        return n

    def vector(self, seed):
        out = []
        for c in self.choices:
            seed, pick = divmod(seed, len(c.alternatives))
            out.append(pick)
        return out

    def seed(self, vector):
        seed = 0
        for c, pick in reversed(list(zip(self.choices, vector))):
            seed = seed * len(c.alternatives) + pick
        return seed

    def code(self, vector):
        return " ".join(f"{c.label}{pick}" for c, pick in zip(self.choices, vector))

    def from_code(self, code):
        """The vector a choice code names. A choice point the code leaves out keeps its first alternative."""
        picks = {}
        for word in code.split():
            m = CHOICE_CODE.fullmatch(word)
            choice = m and next((c for c in self.choices if c.label == m.group(1)), None)
            if not choice or int(m.group(2)) >= len(choice.alternatives):
                die(f"'{word}' names no alternative of this template; a choice code looks like "
                    f"'{self.code([0] * len(self.choices))}'")
            picks[choice.label] = int(m.group(2))
        return [picks.get(c.label, 0) for c in self.choices]

    def steering(self, vector):
        """The choice points whose pick steers the compiler, as (index into choices, reason) pairs."""
        return [(i, steer(c, pick)) for i, (c, pick) in enumerate(zip(self.choices, vector))
                if steer(c, pick) is not None]

    def render(self, vector):
        """The candidate as plain source: each choice point replaced by its picked alternative.

        A steering alternative's tag becomes a `fakematch: <why>` comment on each of its lines.
        """
        return render_parts(self.parts, vector)


def render_parts(parts, vector):
    """Template.render, apart: each choice point replaced by its picked alternative, each reference by that pick again."""
    picks, said, out = iter(vector), {}, []
    for p in parts:
        if isinstance(p, Choice):
            said[p.label] = p.picked(next(picks))
            out.append(said[p.label])
        else:
            out.append(said[p.label] if isinstance(p, Reference) else p)
    return "".join(out)


def read_head(where, args, default_kind):
    """A macro's arguments split into (label or None, kind, the rest). A first argument @label kind names the choice point."""
    if not args or not args[0].startswith("@"):
        return None, default_kind, args
    m = HEAD.fullmatch(args[0])
    if not m:
        die(f"template {where}: a choice point's name looks like '@label kind' (label: letters and underscores)")
    kind = m.group(2) or default_kind
    if kind not in KINDS:
        die(f"template {where}: '{kind}' is not a kind of choice; the kinds are {', '.join(KINDS)}")
    return m.group(1), kind, args[1:]


def read_alternatives(where, alternatives):
    """Each alternative's text without its leading likelihood and steering tag, which come in either order.

    Returns (texts, likelihoods or None when none was given, per alternative its steering reason or None).
    """
    texts, weights, steers = [], [], []
    for alt in alternatives:
        weight = why = None
        while True:
            tag = STEER_TAG.match(alt) if why is None else None
            if tag:
                why = " ".join(tag.group(1).split())
                if not why:
                    die(f"template {where}: a steering tag needs a reason: /* steer: <why> */")
                alt = alt[tag.end():].strip()
            elif weight is None and alt.startswith("%"):
                m = LIKELIHOOD.match(alt)
                if not m or float(m.group(1)) <= 0:
                    die(f"template {where}: a likelihood is a positive number after %, such as '%0.7 alternative'")
                weight, alt = float(m.group(1)), alt[m.end():]
            else:
                break
        texts.append(alt)
        weights.append(1.0 if weight is None else weight)
        steers.append(why)
    return texts, weights if any(w != 1.0 for w in weights) else None, tuple(steers)


def line_orders(where, body):
    """The alternatives of a PERM_LINESWAP: its non-blank lines in every order, the written order first."""
    nl = "\r\n" if "\r\n" in body else "\n"
    lines = [x.strip() for x in body.split(nl) if x.strip()]
    if len(lines) > MAX_LINESWAP_LINES:
        die(f"template {where}: PERM_LINESWAP has {len(lines)} lines; the limit is {MAX_LINESWAP_LINES}")
    if len(lines) < 2:
        die(f"template {where}: PERM_LINESWAP needs two or more lines, one per line of source")
    lead, trail = body[:len(body) - len(body.lstrip())], body[len(body.rstrip()):]
    last = body.rstrip().split(nl)[-1]
    indent = last[:len(last) - len(last.lstrip())]
    return [lead + (nl + indent).join(order) + trail for order in itertools.permutations(lines)]


def parse_template(text):
    """Read a template's choice points. Comments and literals cannot hold one. Stops on a malformed template.

    The macros, each with an optional first argument '@label kind' naming its choice point, and each
    alternative taking a leading '%0.7' likelihood:
      PERM_GENERAL(a, b, ...)   one of the alternatives
      PERM_VAR(@name, a, b ...) as PERM_GENERAL; a later PERM_VAR(name) repeats the pick
      PERM_ONCE(a, b, ...)      nothing, or one of the alternatives
      PERM_INT(lo, hi)          one integer from lo to hi
      PERM_LINESWAP(lines)      the lines in every order (at most MAX_LINESWAP_LINES)
      PERM_IGNORE(text)         the text itself: no choice, only a marked stretch to leave alone
    """
    code, _ = lexed(text)
    parts, choices, variables, at = [], [], set(), 0

    def where(i):
        return f"line {text.count(chr(10), 0, i) + 1}"

    for m in PERM_MACRO.finditer(code):
        if m.start() < at:
            die(f"template {where(m.start())}: a choice point inside another is not supported")
        here, macro = where(m.start()), m.group()
        if macro not in ("PERM_GENERAL", "PERM_VAR", "PERM_ONCE", "PERM_INT", "PERM_LINESWAP", "PERM_IGNORE"):
            die(f"template {here}: {macro} is not supported; the macros are PERM_GENERAL, PERM_VAR, PERM_ONCE, "
                "PERM_INT, PERM_LINESWAP, PERM_IGNORE")
        inner = parenthesised(code, text, m.end())
        if not inner:
            die(f"template {here}: {macro} has no closing parenthesis")
        end = inner[1]
        body_at = end - 1 - len(inner[0])
        parts.append(text[at:m.start()])
        at = end
        if macro == "PERM_IGNORE":
            parts.append(inner[0])
            continue
        if macro == "PERM_LINESWAP":
            first = inner[0].lstrip().startswith("@")
            head, _, body = inner[0].partition("\n") if first else ("", "", inner[0])
            label, kind, _ = read_head(here, [head.strip()] if first else [], "stmt-order")
            alternatives, weights, steers = line_orders(here, body), None, ()
        else:
            args = split_alternatives(code, text, body_at, end - 1)
            if macro == "PERM_VAR" and len(args) == 1 and re.fullmatch(r"[A-Za-z_]+", args[0]):
                if args[0] not in variables:
                    die(f"template {here}: PERM_VAR({args[0]}) comes before the PERM_VAR(@{args[0]}, ...) that defines it")
                parts.append(Reference(args[0]))
                continue
            label, kind, args = read_head(here, args, "other")
            if macro == "PERM_VAR" and label is None:
                die(f"template {here}: PERM_VAR(@name, a, b, ...) defines a variable; PERM_VAR(name) repeats its pick")
            if macro == "PERM_INT":
                try:
                    lo, hi = (int(x) for x in args)
                except ValueError:
                    die(f"template {here}: PERM_INT(lo, hi) takes two integers")
                if not lo <= hi or hi - lo + 1 > MAX_INT_VALUES:
                    die(f"template {here}: PERM_INT needs lo <= hi and at most {MAX_INT_VALUES} values")
                args = [str(i) for i in range(lo, hi + 1)]
            alternatives, weights, steers = read_alternatives(here, args)
            if macro == "PERM_ONCE":
                alternatives, weights, steers = [""] + alternatives, weights and [1.0] + weights, (None,) + steers
            if len(alternatives) < 2:
                die(f"template {here}: a choice point needs two or more alternatives")
        label = label or choice_label(len(choices))
        if any(c.label == label for c in choices):
            die(f"template {here}: the label '{label}' is used twice; labels are what choice codes name")
        choice = Choice(label, alternatives, kind, weights, steers)
        choices.append(choice)
        parts.append(choice)
        if macro == "PERM_VAR":
            variables.add(label)
    if len(choices) > MAX_CHOICES:
        die(f"template has {len(choices)} choice points; the limit is {MAX_CHOICES}")
    return Template(parts + [text[at:]])


def candidates(template, boost=None):
    """The seeds a round tries after its opening one-change sweep, in order: the whole space, most likely first.

    A candidate's likelihood is the product of its alternatives' likelihoods. With no likelihoods,
    no steering alternative and no history the order is the seeds', baseline first. boost maps a kind
    to the times it fixed the ticket's category (see history): it raises the likelihood of that
    kind's alternatives.
    """
    boosted = any(boost.get(c.kind) for c in template.choices) if boost else False
    if not boosted and all(c.likelihoods is None and not any(c.steers) for c in template.choices):
        return range(template.space())
    return most_likely_first(template, boost)


def likelihoods(template, boost=None):
    """Each choice point's likelihood per alternative: the writer's (1.0 where none was given), raised by history.

    A change from the baseline (alternative 0) is what a kind fixed, so boost raises every other alternative.
    """
    weights = [c.likelihoods or [1.0] * len(c.alternatives) for c in template.choices]
    for i, c in enumerate(template.choices):
        if boost and boost.get(c.kind):
            weights[i] = weights[i][:1] + [w * (1 + boost[c.kind]) for w in weights[i][1:]]
    return weights


def most_likely_first(template, boost=None):
    """Every seed, the likeliest candidate first, produced lazily so a large space costs nothing until it is read.

    Each choice point's alternatives are ranked by likelihood (a natural one before a steering one,
    then written order, breaking ties). A heap holds the frontier of rank vectors: raising one rank
    never raises the likelihood, and each vector is reached by one route, raising ranks left to right.
    At equal likelihood the candidate with fewer steering alternatives goes first.
    """
    weights = likelihoods(template, boost)
    ranked = [sorted(range(len(w)), key=lambda i, w=w, c=c: (-w[i], steer(c, i) is not None, i))
              for w, c in zip(weights, template.choices)]
    cost = [[-math.log(w[i]) for i in order] for w, order in zip(weights, ranked)]

    def entry(ranks, last):
        vector = [order[r] for order, r in zip(ranked, ranks)]
        return (sum(k[r] for k, r in zip(cost, ranks)), len(template.steering(vector)), template.seed(vector), ranks, last)

    heap = [entry((0,) * len(ranked), 0)]
    while heap:
        _, _, seed, ranks, last = heapq.heappop(heap)
        yield seed
        for j in range(last, len(ranks)):
            if ranks[j] + 1 < len(ranked[j]):
                heapq.heappush(heap, entry(ranks[:j] + (ranks[j] + 1,) + ranks[j + 1:], j))


def one_change(template, boost=None):
    """The seeds that open a round: the baseline, then each candidate with one choice point changed.

    The one-change candidates go most likely first. Where likelihoods tie or none was given, a natural
    alternative goes before a steering one, then template order decides.
    """
    changed = []
    for (i, c), weights in zip(enumerate(template.choices), likelihoods(template, boost)):
        for pick in range(1, len(c.alternatives)):
            vector = [0] * len(template.choices)
            vector[i] = pick
            changed.append((-weights[pick] / weights[0], steer(c, pick) is not None, len(changed), template.seed(vector)))
    return [0] + [seed for *_, seed in sorted(changed)]


def inert_choices(template, results):
    """The labels of the choice points whose alternatives all gave the baseline's object, among results so far."""
    by_seed = {r["seed"]: r for r in results}
    base = by_seed.get(0, {}).get("object")
    out = []
    for i, c in enumerate(template.choices):
        for pick in range(1, len(c.alternatives)):
            vector = [0] * len(template.choices)
            vector[i] = pick
            if not base or by_seed.get(template.seed(vector), {}).get("object") != base:
                break
        else:
            out.append(c.label)
    return out


def beside(tree, source, text):
    """The tree's files a source at this path reaches through includes looked up beside the including file.

    They are what a copy of the source elsewhere needs next to it. A header found only on the
    compiler's include path is not listed: the build still finds it from the tree.
    """
    found, todo, seen = [], [(source, text)], {source.casefold()}
    while todo:
        rel, body = todo.pop()
        for name in sorted(includes(body)):
            spelled = name.replace("\\", "/")
            if spelled.startswith("/") or re.match(r"[A-Za-z]:", spelled):
                continue
            parts = os.path.normpath(os.path.join(os.path.dirname(rel), spelled)).replace("\\", "/").split("/")
            hit = None if parts[0] == ".." else in_tree(tree, parts)
            hit = hit and hit.relative_to(tree).as_posix()
            if hit and hit.casefold() not in seen:
                seen.add(hit.casefold())
                found.append(hit)
                todo.append((hit, (Path(tree) / hit).read_text(encoding="utf-8", errors="replace")))
    return found


def source_text(data):
    """Source bytes as text that source_bytes turns back into the same bytes, whatever their encoding."""
    return data.decode("utf-8", errors="surrogateescape")


def source_bytes(text):
    return text.encode("utf-8", errors="surrogateescape")


class Worker:
    """One build slot: a scratch copy of the unit's folder layout, its file names fixed and overwritten per candidate.

    The candidate sits at the unit's own path under the scratch folder, with every header the template
    includes beside itself, so those includes still resolve. Adapters run in tree, as for `check`.
    """

    def __init__(self, folder, environment, t, compiler, tree, template_text):
        """environment is the block's Launcher."""
        self.environment, self.t, self.compiler, self.tree = environment, t, compiler, tree
        self.source = Path(folder) / "unit" / t["source"]
        self.objdir = Path(folder) / "obj"
        self.report = Path(folder) / "diff.txt"
        self.objdir.mkdir(parents=True)
        for rel in beside(tree, t["source"], template_text):
            dest = Path(folder) / "unit" / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(Path(tree) / rel, dest)
        self.source.parent.mkdir(parents=True, exist_ok=True)

    def refuse(self, text):
        """The guardrail Score for a source that must not be built, or None."""
        marks = marker_count(text, self.t["id"])
        if marks != 1:
            return Score("guardrail", None, f"expected one '@decomp {self.t['id']}' marker comment, found {marks}")
        bad = scan(text)
        if bad:
            return Score("guardrail", None, "\n".join(bad))
        return None

    def build(self, text):
        """Build one candidate's source. Returns (obj, failure log or ''). A build that passes is timed."""
        wait = self.environment.settings["lock_retry_s"]
        began = time.perf_counter()
        retrying(lambda: self.source.write_bytes(source_bytes(text)), wait)
        retrying(lambda: self.report.unlink(missing_ok=True), wait)
        self.environment.add("write", time.perf_counter() - began)
        with compile_slot(self):  # the wait for a slot is neither write time nor compile time
            start = time.perf_counter()
            obj, failure = build_unit(*self.args(), self.objdir, str(self.report))
            took = time.perf_counter() - start
            self.environment.add("compile", took)
            if not failure:
                self.environment.sample(took)
        return obj, failure

    def diff(self, obj, fields=None):
        """Diff a built object. The diff report of this candidate is left in self.report."""
        start = time.perf_counter()
        try:
            return Score(*diff_unit_first(*self.args(), obj, str(self.report), fields))
        finally:
            self.environment.add("compare", time.perf_counter() - start)

    def args(self):
        return (self.environment, self.t, self.compiler, self.tree, str(self.source))

    def score(self, text):
        """Build and diff one candidate's source. The diff report of this candidate is left in self.report."""
        refused = self.refuse(text)
        if refused:
            return refused
        obj, failure = self.build(text)
        if failure:
            return Score("build-fail", None, failure)
        return self.diff(obj)


def rank(score):
    """A score's sort key, lower being closer to the original. None when the candidate gave no score."""
    if score.result not in ("bytes-match", "differ") or score.differ_bytes is None or score.differ_bytes < 0:
        return None
    if score.first_differ is None:
        return (score.differ_bytes,)
    return (score.differ_bytes, -score.first_differ)  # equal bytes: the later first difference is closer


OFFSET_TOKEN = re.compile(r"(?<![0-9A-Za-z])(?:0[xX])?([0-9A-Fa-f]+)(?![0-9A-Za-z])")


def offset_line(lines, offset):
    """Index of the first report line holding offset as a whole number, in hex (0x optional, zeros ignored) or decimal."""
    want = {format(offset, "x"), str(offset)}
    for i, line in enumerate(lines):
        if any((m.group(1).lstrip("0") or "0").lower() in want for m in OFFSET_TOKEN.finditer(line)):
            return i
    return None


def window(report, first_differ=None):
    """The lines of a diff report the summary shows, each cut to a fixed width.

    With first_differ, the window is centred on the line holding that offset, with WINDOW_LINES // 2 lines of
    context each side. Without it, or when no line holds it, it is the report's first lines.
    """
    try:
        with open(report, encoding="utf-8", errors="replace") as f:
            lines = [line.rstrip("\n")[:WINDOW_WIDTH] for line in f]
    except OSError:
        return []
    at = None if first_differ is None else offset_line(lines, first_differ)
    start = 0 if at is None else max(0, at - WINDOW_LINES // 2)
    return lines[start:start + WINDOW_LINES]


SEARCH_DEFAULTS = {  # a block's constants; "search" in this machine's local.json overrides any of them
    "workers": 0,  # worker threads; 0 is the physical cores divided by the active writers
    "deadline_s": 0,  # a fixed block deadline; 0 leaves it to the floor and the ceiling
    "floor_s": 10.0,  # a block runs at least this long,
    "floor_compiles": 200,  # and on until it has built this many candidates,
    "ceiling_s": 60.0,  # or until the ceiling: the last round's model latency, never above this
    "plateau_compiles": 200,  # a plateau: this many scored candidates with no new best score and no new object,
    "plateau_frac": 0.25,  # and no fewer than this share of the block's scored candidates
    "buildfail_frac": 0.5,  # the block aborts when more than this share of its first 2 x workers builds fail
    "repeat_window": 100,  # the block is exhausted when, of its last this many candidates,
    "repeat_frac": 0.9,  # more than this share only repeated a source it had already tried
    "hang_factor": 10.0,  # an adapter run is killed after this many times the median compile time,
    "hang_floor_s": 5.0,  # though never sooner than this,
    "hang_start_s": 120.0,  # and after this long while fewer than 2 x workers compiles are timed
    "lock_retry_s": 2.0,  # how long an overwrite retries on a file another process still holds
    "cores": 0,  # the physical cores to plan for; 0 asks the platform
    "slots": 0,  # compile slots in the machine-wide pool; 0 is the cores, or `workers` when that is set higher
    "slot_heartbeat_s": 2.0,  # how often a running search renews its heartbeat in the pool,
    "slot_stale_s": 30.0,  # and how old a heartbeat makes its search's slots free for the taking
    "tune_s": 2.0,  # the tuning tick: how often a block adjusts its worker count; 0 keeps the count it started with
    "tune_gain": 0.05,  # a rise this large in compiles per second, against the tick before, adds a worker,
    "tune_loss": 0.1,  # a fall this large takes one back,
    "tune_spread": 2.0,  # as does a p95 compile time above this many times the tick's median
    "reference_s": 30.0,  # how often a block recompiles its reference candidate, the baseline; 0 is never
}


def search_settings():
    """The block constants for this machine: the defaults with local.json's "search" entries over them."""
    path = local_dir() / "local.json"
    local = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    given = local.get("search", {})
    bad = [k for k, v in given.items() if k not in SEARCH_DEFAULTS or isinstance(v, bool)
           or not isinstance(v, (int, float)) or v < 0] if isinstance(given, dict) else ["search"]
    if bad:
        die(f'{path}: "search" holds {sorted(bad)}; it takes a number, zero or more, for any of {sorted(SEARCH_DEFAULTS)}')
    return dict(SEARCH_DEFAULTS, **given)


def retrying(overwrite, seconds):
    """Run a file overwrite, again for a short while when a lingering handle or a scanner still holds the file."""
    end, pause = time.perf_counter() + seconds, 0.005
    while True:
        try:
            return overwrite()
        except PermissionError:
            if time.perf_counter() >= end:
                raise
            time.sleep(pause)
            pause = min(pause * 2, 0.1)


# What makes a command need the host's shell: the characters the shell itself reads.
SHELL_ONLY = re.compile(r"[%&|<>^\n]" if os.name == "nt" else r"[$`&|;<>()*?\[\]{}~#!\n]")
_KERNEL32 = None


def kernel32():
    """Windows' Job Object calls, with their handle types declared (a handle is pointer-sized)."""
    global _KERNEL32
    if _KERNEL32 is None:
        import ctypes
        k, handle = ctypes.WinDLL("kernel32"), ctypes.c_void_p
        k.CreateJobObjectW.restype, k.CreateJobObjectW.argtypes = handle, [ctypes.c_void_p, ctypes.c_wchar_p]
        k.AssignProcessToJobObject.argtypes = [handle, handle]
        k.TerminateJobObject.argtypes = [handle, ctypes.c_uint]
        k.CloseHandle.argtypes = [handle]
        _KERNEL32 = k
    return _KERNEL32


def tree_handle(proc):
    """What kill_tree needs to end a started process with its descendants.

    On Windows it is a new Job Object holding the process (None when it cannot be made). Elsewhere
    the process leads its own process group (see Launcher.start), and nothing more is needed.
    """
    if os.name != "nt":
        return None
    try:
        k = kernel32()
        job = k.CreateJobObjectW(None, None)
        if job and not k.AssignProcessToJobObject(job, int(proc._handle)):
            k.CloseHandle(job)
            job = None
        return job
    except (OSError, AttributeError):
        return None


def kill_tree(proc, job):
    """Kill a process and every descendant. Killing only proc would leave a compiler running, holding the worker's files."""
    if os.name != "nt":
        with contextlib.suppress(OSError):
            os.killpg(proc.pid, signal.SIGKILL)
    elif job:
        kernel32().TerminateJobObject(job, 1)
    else:
        subprocess.run(["taskkill", "/T", "/F", "/PID", str(proc.pid)], capture_output=True)
    with contextlib.suppress(OSError):
        proc.kill()


def physical_core_call():
    """The physical core count as the platform reports it. Raises, or counts nothing, where the platform cannot say."""
    if os.name == "nt":
        import ctypes
        k, size = ctypes.WinDLL("kernel32"), ctypes.c_ulong(0)
        k.GetLogicalProcessorInformationEx(0, None, ctypes.byref(size))  # 0 is RelationProcessorCore: one record per core
        buf = ctypes.create_string_buffer(size.value)
        if not k.GetLogicalProcessorInformationEx(0, buf, ctypes.byref(size)):
            raise OSError("GetLogicalProcessorInformationEx failed")
        raw, at, count = buf.raw[:size.value], 0, 0
        while at < len(raw):
            step = int.from_bytes(raw[at + 4:at + 8], "little")  # a record starts with its relationship, then its size
            if step <= 0:
                raise OSError("GetLogicalProcessorInformationEx returned a record of no size")
            at, count = at + step, count + 1
        return count
    if sys.platform == "darwin":
        import ctypes
        n, size = ctypes.c_int(0), ctypes.c_size_t(ctypes.sizeof(ctypes.c_int))
        if ctypes.CDLL(None).sysctlbyname(b"hw.physicalcpu", ctypes.byref(n), ctypes.byref(size), None, 0):
            raise OSError("sysctlbyname hw.physicalcpu failed")
        return n.value
    usable, seen = os.sched_getaffinity(0), set()  # Linux has no such call: the kernel lists each core's threads
    for cpu in usable:
        seen.add(Path(f"/sys/devices/system/cpu/cpu{cpu}/topology/thread_siblings_list").read_text().strip())
    return len(seen)


def cores():
    """This machine's physical cores, or its logical ones when the platform's call fails."""
    try:
        count = physical_core_call()
    except Exception:
        count = 0
    return count if isinstance(count, int) and count > 0 else os.cpu_count() or 1


SLOT_HOLDER = re.compile(r"\d+-[0-9a-f]+")  # a search's name in the pool: its process id and a random part


class SlotPool:
    """The compile slots every search on this machine shares, so concurrent writers do not oversubscribe the CPU.

    The pool is a folder under the machine-only .decomp/: `<n>.slot` is slot n, held by the search named
    inside it, and `<name>.writer` is a running search's heartbeat, touched every few seconds. A build
    runs only while its worker holds a slot, taken by creating the file and given back by removing it.
    A slot whose holder's heartbeat is missing or stale is reclaimed, so a search that died frees its
    slots within the stale time. No search holds more than its share (the slots divided by the active
    writers, rounded up) at once, so a search that takes a slot back the moment it frees one cannot
    starve another.
    """

    def __init__(self, settings):
        self.dir = local_dir() / "slots"  # beside local.json, whose settings size the pool
        self.cores = int(settings["cores"]) or cores()
        self.size = int(settings["slots"]) or max(self.cores, int(settings["workers"]))
        self.stale_s, self.beat_s, self.retry_s = settings["slot_stale_s"], settings["slot_heartbeat_s"], settings["lock_retry_s"]
        self.id = f"{os.getpid()}-{os.urandom(4).hex()}"
        self.beat = self.dir / f"{self.id}.writer"
        self.lock = threading.Condition()
        self.closed = threading.Event()
        self.held, self.busy, self.reclaimed = set(), 0, 0  # slots held; workers holding or waiting for one
        self.writers = self.writers_at_start = 1

    def open(self):
        """Join the pool: start the heartbeat and count the active writers, this one included."""
        self.dir.mkdir(parents=True, exist_ok=True)
        self.beat.write_text(self.id, encoding="utf-8")
        self.writers = self.writers_at_start = self.count_writers()
        atexit.register(self.close)  # a search that stops on an error still leaves the pool
        threading.Thread(target=self.heartbeat, daemon=True).start()
        return self

    def close(self):
        """Leave the pool: give back every slot and remove the heartbeat. Safe to call twice."""
        if self.closed.is_set():
            return
        self.closed.set()
        with self.lock:
            for i in sorted(self.held):
                with contextlib.suppress(OSError):
                    self.drop(i)
            self.held.clear()
            with contextlib.suppress(OSError):
                self.beat.unlink()

    def stale(self, path):
        """Whether a file was last written longer ago than the stale time, or is gone. By the wall clock: it spans processes."""
        try:
            return time.time() - path.stat().st_mtime > self.stale_s
        except OSError:
            return True

    def count_writers(self):
        """The searches whose heartbeat is fresh, this one included. A stale heartbeat is cleared away."""
        count = 1
        for beat in self.dir.glob("*.writer"):
            if beat == self.beat:
                continue
            if not self.stale(beat):
                count += 1
            else:
                with contextlib.suppress(OSError):
                    beat.unlink()
        return count

    def heartbeat(self):
        while not self.closed.wait(self.beat_s):
            with self.lock:
                if self.closed.is_set():
                    return
                with contextlib.suppress(OSError):
                    try:
                        os.utime(self.beat)
                    except FileNotFoundError:  # cleared as stale while this process stood still
                        self.beat.write_text(self.id, encoding="utf-8")
            writers = self.count_writers()
            with self.lock:
                self.writers = writers
                self.lock.notify_all()

    def start_workers(self):
        """The worker count a search starts with: the cores divided by the active writers."""
        return max(1, self.cores // self.writers_at_start)

    def share(self):
        """The slots this search may hold at once. Call with the lock held."""
        return max(1, -(-self.size // self.writers))

    def path(self, i):
        return self.dir / f"{i}.slot"

    def take(self, i):
        try:
            fd = os.open(self.path(i), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except OSError:  # held, or on Windows still being removed
            return False
        try:
            os.write(fd, self.id.encode())
        finally:
            os.close(fd)
        return True

    def acquire(self, prefer=0):
        """Wait for a free slot and take it, trying slot `prefer` first. Returns the slot's number."""
        with self.lock:
            while self.busy >= self.share():
                self.lock.wait(0.1)
            self.busy += 1
        pause, reap_at = 0.002, 0.0
        try:
            while True:
                for k in range(self.size):
                    i = (prefer + k) % self.size
                    if self.take(i):
                        with self.lock:
                            self.held.add(i)
                        return i
                if time.perf_counter() >= reap_at:
                    reap_at = time.perf_counter() + min(1.0, self.stale_s / 4)
                    if self.reap():
                        continue
                time.sleep(pause)
                pause = min(pause * 2, 0.05)
        except BaseException:
            with self.lock:
                self.busy -= 1
                self.lock.notify_all()
            raise

    def drop(self, i):
        """Remove slot i's file while it still names this search. Reclaimed from a search that stood still, it is another's."""
        slot = self.path(i)

        def remove():
            try:
                if slot.read_text(encoding="utf-8") == self.id:
                    slot.unlink()
            except FileNotFoundError:
                pass
        retrying(remove, self.retry_s)

    def release(self, i):
        try:
            self.drop(i)
            gone = True
        except OSError:  # another process still holds the file: close() tries again, and the stale time frees it at the latest
            gone = False
        with self.lock:
            self.busy -= 1
            if gone:
                self.held.discard(i)
            self.lock.notify_all()

    def abandoned(self, i):
        """Whether slot i is held by a search that stopped beating."""
        slot = self.path(i)
        try:
            holder = slot.read_text(encoding="utf-8")
        except (OSError, ValueError):
            return False  # free, or being written
        if holder == self.id:
            return False
        if SLOT_HOLDER.fullmatch(holder):
            return self.stale(self.dir / f"{holder}.writer")
        return slot.exists() and self.stale(slot)  # half written, or not a search's: judged by its own age

    def reap(self):
        """Free the slots of searches that stopped beating. Returns how many.

        One search reclaims at a time, under a lock file, and looks again once it holds the lock:
        without that, two waiting searches could each remove the slot the other had just taken.
        """
        found = [i for i in range(self.size) if self.abandoned(i)]
        if not found:
            return 0
        lock = self.dir / "reclaim.lock"
        try:
            os.close(os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY))
        except OSError:
            if self.stale(lock):  # its taker died while reclaiming
                with contextlib.suppress(OSError):
                    lock.unlink()
            return 0
        freed = 0
        try:
            for i in found:
                if self.abandoned(i):
                    with contextlib.suppress(OSError):
                        self.path(i).unlink()
                        freed += 1
        finally:
            with contextlib.suppress(OSError):
                retrying(lock.unlink, self.retry_s)
        with self.lock:
            self.reclaimed += freed
        return freed


@contextlib.contextmanager
def compile_slot(worker):
    """Hold one of the machine's compile slots for the length of a worker's build. A launcher with no pool builds freely."""
    pool = getattr(worker.environment, "pool", None)
    if pool is None:
        yield
        return
    worker.slot = pool.acquire(getattr(worker, "slot", 0))
    try:
        yield
    finally:
        pool.release(worker.slot)


class Launcher:
    """How a search block runs its adapters, standing where `check` passes doctor's Environment.

    It starts a command without the host's shell and falls back to the shell when the command
    needs one. It kills a run that hangs, as a whole process tree. It keeps the compile times that
    set the hang limit. Its counters are read after the block.
    """

    def __init__(self, environment, settings, workers):
        self.vars, self.settings, self.workers = environment.vars, settings, workers
        self.lock = threading.Lock()
        self.times, self.programs = [], {}
        self.killed = self.shell = 0
        self.samples, self.stage = [], dict.fromkeys(("write", "compile", "compare"), 0.0)  # the performance log's

    def sample(self, seconds):
        """Note the time one passing compile took."""
        with self.lock:
            self.times.append(seconds)
            self.samples.append(seconds)

    def add(self, stage, seconds):
        """Add to the time a stage of the block has taken (write, compile, compare), across its workers."""
        with self.lock:
            self.stage[stage] += seconds

    def restart_timing(self):
        """Begin the performance log's counts anew; the hang limit keeps its compile times."""
        with self.lock:
            self.samples, self.stage = [], dict.fromkeys(self.stage, 0.0)

    def limit(self):
        """Seconds a run may take before it counts as hung."""
        s = self.settings
        with self.lock:
            if len(self.times) < 2 * self.workers:
                return s["hang_start_s"]
            return max(s["hang_floor_s"], s["hang_factor"] * statistics.median(self.times[-512:]))

    def direct(self, command, cwd):
        """How to start a filled command with no shell: (Popen args, program file), or None when it needs the shell.

        It needs the shell for a character the shell reads (`%VAR%`, `&&`, a redirection), and for a
        program that is no executable file: a `.cmd` or `.bat` tool, or a shell builtin.
        """
        if SHELL_ONLY.search(command):
            return None
        try:
            words = shlex.split(command, posix=os.name != "nt")
        except ValueError:
            return None
        program = words[0].strip('"') if words else ""
        if not program or "=" in program:
            return None
        with self.lock:
            if program not in self.programs:
                named = os.path.join(cwd, program) if os.path.dirname(program) else program
                found = shutil.which(named, path=self.vars.get("PATH"))
                if found and os.name == "nt" and not found.lower().endswith((".exe", ".com")):
                    found = None
                self.programs[program] = found
            found = self.programs[program]
        if not found:
            return None
        # Windows hands the command line over as written: the program splits it as it would under cmd.exe.
        return (command, found) if os.name == "nt" else (words, None)

    def start(self, args, cwd, executable=None, shell=False):
        return subprocess.Popen(args, executable=executable, shell=shell, cwd=cwd, env=self.vars,
                                stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                text=True, errors="replace", start_new_session=os.name != "nt")

    def run(self, command, cwd):
        """Run one filled adapter command to its end or the hang limit. Returns it as subprocess.run would."""
        proc, direct = None, self.direct(command, cwd)
        if direct:
            with contextlib.suppress(OSError):
                proc = self.start(direct[0], cwd, executable=direct[1])
        if proc is None:
            proc = self.start(command, cwd, shell=True)
            with self.lock:
                self.shell += 1
        job, limit = tree_handle(proc), self.limit()
        try:
            out, err = proc.communicate(timeout=limit)
            return subprocess.CompletedProcess(command, proc.returncode, out, err)
        except subprocess.TimeoutExpired:
            kill_tree(proc, job)
            try:
                out, err = proc.communicate(timeout=5)
            except subprocess.TimeoutExpired:  # a survivor still holds the pipes: leave them
                out, err = "", ""
            with self.lock:
                self.killed += 1
            return subprocess.CompletedProcess(command, -9, out or "", f"{err or ''}\nkilled: still running after {limit:.1f} s")
        finally:
            if job:
                kernel32().CloseHandle(job)


def uses_wine():
    """True on a host that runs the toolchain under Wine: not Windows, and toolchain.json names wine as a prerequisite here."""
    return sys.platform != "win32" and any(h["name"] == "wine" for h in toolchain()["prerequisites"])


@contextlib.contextmanager
def persistent_wineserver(launcher):
    """Keep one wineserver running for a block, so each compile skips Wine's startup. Does nothing off Wine.

    The block starts it before the first compile and ends it after the last. A wineserver that cannot be
    found or started leaves the block as it was: Wine starts its own per compile.
    """
    proc = None
    found = shutil.which("wineserver", path=launcher.vars.get("PATH")) if uses_wine() else None
    if found:
        with contextlib.suppress(OSError):
            proc = subprocess.Popen([found, "-f", "-p"], env=launcher.vars, stdin=subprocess.DEVNULL,
                                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
    try:
        yield proc
    finally:
        if proc:
            with contextlib.suppress(OSError):
                os.killpg(proc.pid, signal.SIGTERM)
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                kill_tree(proc, None)
                proc.wait()


class Block:
    """One block's running state, shared by its workers under one lock: what was tried, and when to end.

    A block ends on, first that holds: a natural match; `abort-buildfail`, when most of its first builds
    fail; `exhausted`, when no candidate is left or nearly all of the last ones were repeats; `plateau`,
    when scored candidates stopped bringing a new best score or a new object; and `deadline`.

    The baseline goes first, then every one-choice-changed candidate, then the rest of the space, each
    group most likely first. The rest waits for the sweep's last result: a choice point whose
    alternatives all gave the baseline's object is inert, and stays at its first alternative from
    then on. A match that needs steering does not end the block: it is kept while the rest is tried
    for a natural one (see run_block). boost is the history's (see candidates).
    """

    def __init__(self, template, settings, workers, ceiling, boost=None):
        self.template, self.settings, self.workers, self.ceiling = template, settings, workers, ceiling
        self.boost = boost
        self.lock = threading.Condition()
        self.sweep = collections.deque(one_change(template, boost))  # the opening seeds, not yet handed out
        self.swept = set(self.sweep)
        self.pending = set(self.sweep)  # the opening seeds with no result yet
        self.seeds = None  # the seeds after the sweep, made when its results are in
        self.by_seed = {}  # seed to its result, for every candidate tried
        self.steered, self.natural = [], None  # seeds that match only through steering; the natural match
        self.start = time.perf_counter()  # monotonic and fine-grained: the wall clock steps about 15 ms on Windows
        self.end = self.best = self.error = None
        self.results, self.failure = [], ""
        self.counts = {"space": template.space(), "compiled": 0, "build_fail": 0, "guardrail": 0}
        self.early = []  # the first 2 x workers builds: whether each failed
        self.recent = collections.deque(maxlen=max(1, int(settings["repeat_window"])))  # per candidate: was it a repeat
        self.scored = self.since_gain = 0
        self.stage, self.busy, self.expanded, self.best_at = {"expand": 0.0, "score": 0.0}, 0.0, 0, None  # the performance log's

    def elapsed(self):
        return time.perf_counter() - self.start

    def due(self):
        """Whether the deadline has come: past the floor (its seconds and its compiles both), or at the ceiling."""
        s, t = self.settings, self.elapsed()
        if s["deadline_s"]:
            return t >= s["deadline_s"]
        return t >= s["floor_s"] and (self.counts["compiled"] >= s["floor_compiles"] or t >= self.ceiling)

    def take(self):
        """The next seed for a worker, or None when the block has ended."""
        with self.lock:
            while True:
                if self.end:
                    return None
                if self.due():
                    self.end = "deadline"
                    return None
                if self.sweep:
                    return self.sweep.popleft()
                if not self.pending:
                    break
                self.lock.wait(0.05)  # the sweep's last builds are still out: what is inert is not known yet
            if self.seeds is None:
                self.seeds = self.rest()
            seed = next(self.seeds, None)
            if seed is None:
                self.end = "exhausted"
            return seed

    def rest(self):
        """The seeds after the sweep: the space, most likely first, less the sweep and every candidate that varies
        an inert choice point. Call with the lock held, the sweep's results in."""
        t = self.template
        inert = inert_choices(t, self.results)
        frozen = {i for i, c in enumerate(t.choices) if c.label in inert}
        return (seed for seed in candidates(t, self.boost)
                if seed not in self.swept and not any(pick for i, pick in enumerate(t.vector(seed)) if i in frozen))

    def mostly_failing(self):
        return bool(self.early) and sum(self.early) > self.settings["buildfail_frac"] * len(self.early)

    def record(self, seed, e, how, new_object):
        """Count one tried candidate and end the block when a rule says so.

        e is its Memo entry; how is `built`, `cached`, `repeat`, or `refused`; new_object says
        whether its object was not seen before in this round.
        """
        s = self.settings
        score = Score(e["r"], e["d"], e.get("log", ""), e.get("f"))
        vector = self.template.vector(seed)
        with self.lock:
            self.results.append({"seed": seed, "code": self.template.code(vector), "result": score.result,
                                 "differ_bytes": score.differ_bytes, "object": e.get("o")})
            self.by_seed[seed] = score.result
            self.pending.discard(seed)
            self.lock.notify_all()
            self.counts["guardrail"] += score.result == "guardrail"
            self.counts["compiled"] += how == "built"
            self.counts["build_fail"] += score.result == "build-fail"
            gain = new_object
            if rank(score) is None:
                self.failure = self.failure or score.log
            elif self.best is None or (rank(score), seed) < (rank(self.best["score"]), self.best["seed"]):
                gain = gain or self.best is None or rank(score) < rank(self.best["score"])
                if gain and (self.best is None or rank(score) < rank(self.best["score"])):
                    self.best_at = self.elapsed()
                self.best = {"seed": seed, "score": score, "window": e.get("w", [])}
            if score.result == "bytes-match" and self.template.steering(vector):
                self.steered.append(seed)  # a match that needs steering: keep looking for a natural one
            elif score.result == "bytes-match":
                if self.natural is None or seed < self.natural["seed"]:
                    self.natural = {"seed": seed, "score": score, "window": e.get("w", [])}
                self.end = "match"  # even over an end another worker has set: the match is in hand
                return
            self.recent.append(how == "repeat")
            if how == "built" and len(self.early) < 2 * self.workers:
                self.early.append(score.result == "build-fail")
                if len(self.early) == 2 * self.workers and self.mostly_failing():
                    self.end = self.end or "abort-buildfail"
            if how in ("built", "cached"):
                self.scored += 1
                self.since_gain = 0 if gain else self.since_gain + 1
            if len(self.recent) == self.recent.maxlen and sum(self.recent) > s["repeat_frac"] * len(self.recent):
                self.end = self.end or "exhausted"
            if self.since_gain >= max(s["plateau_compiles"], s["plateau_frac"] * self.scored, 1):
                self.end = self.end or "plateau"

    def attempt(self, seed, memo, worker):
        """Score one candidate in the worker's own folder and record it."""
        began = time.perf_counter()
        text = self.template.render(self.template.vector(seed))
        expanded = time.perf_counter()
        try:
            found = memo.entry(text, worker)
        except OSError as err:  # a file of the worker's stayed locked: this candidate is lost, not the block
            found = {"r": "build-fail", "d": None, "log": str(err)}, "built", False
        scoring = time.perf_counter()
        self.record(seed, *found)
        done = time.perf_counter()
        with self.lock:
            self.stage["expand"] += expanded - began
            self.stage["score"] += done - scoring
            self.busy += done - began
            self.expanded += 1

    def result(self, seed, memo, worker):
        """A candidate's result, scored now when the block did not try it."""
        if seed not in self.by_seed:
            self.attempt(seed, memo, worker)
        return self.by_seed[seed]

    def work(self, memo, worker, admit=None):
        """One worker's loop: take a seed, score it, record it. admit, when given, is asked before each
        candidate: it holds the worker back while the block runs fewer workers, and is false once the block ended."""
        try:
            while True:
                if admit and not admit():
                    return
                seed = self.take()
                if seed is None:
                    return
                self.attempt(seed, memo, worker)
        except BaseException as err:  # raised again by run_block, on the main thread
            with self.lock:
                self.error, self.end = self.error or err, self.end or "stopped"


def run_block(template, memo, workers, settings, ceiling, boost=None, perf=None, tuner=None):
    """Try candidates on every worker until the block ends. Returns (end reason, best, counts, results).

    Each worker is a thread that drives one adapter process at a time, in its own folder, and takes
    its next candidate only when it is free, so a later candidate can use every earlier result.
    best is a dict: seed, score, and diff window of the closest candidate (the lowest seed among
    equals), or only the first failure log when no candidate was scored. results holds one record
    per candidate tried, by seed.
    A block that ends with no natural match but with one that needs steering ends as a match: the
    steered match, reduced to the steering it needs.
    A dict given as perf is filled with the block's timings for the performance log.
    A Tuner given as tuner sets how many of the workers run at once, from its starting count on;
    without one they all run.
    """
    block = Block(template, settings, tuner.start if tuner else len(workers), ceiling, boost)
    admits = [(lambda i=i: tuner.admit(i),) if tuner else () for i in range(len(workers))]
    threads = [threading.Thread(target=block.work, args=(memo, w, *a), daemon=True) for w, a in zip(workers, admits)]
    if tuner:
        tuner.begin(block)
    for th in threads:
        th.start()
    for th in threads:
        th.join()
    if tuner:
        tuner.finish()
    if block.error:
        raise block.error
    end, best = block.end, block.best or {"failure": block.failure}
    if end == "exhausted" and block.mostly_failing():  # the space ran out before 2 x workers builds were in
        end = "abort-buildfail"
    if block.natural:
        best = block.natural
    elif block.steered:
        seed = reduce_steering(template, block.steered, lambda at: block.result(at, memo, workers[0]), boost)
        end, best = "match", {"seed": seed, "score": Score("bytes-match", 0, ""), "window": []}
    wall = block.elapsed()
    block.counts.update(workers=block.workers, wall_s=round(wall, 2))
    if perf is not None:
        perf.update(wall=wall, busy=block.busy, expanded=block.expanded, stage=dict(block.stage), best_at=block.best_at)
        if tuner:
            perf.update(tuning=tuner.report())
    return end, best, block.counts, sorted(block.results, key=lambda r: r["seed"])


REF_SLOW = 0.3  # a reference compile this much slower than its base is contention or throttling
TUNE_RETRY_TICKS = 10  # judged ticks before the tuner tries again a worker count it had to give up


def pool_capacity(pool):
    """The slots the pool could give this search now: its share, or what the other searches leave free when that is less."""
    with pool.lock:
        share = pool.share()
    others = 0
    for i in range(pool.size):
        try:
            others += pool.path(i).read_text(encoding="utf-8") != pool.id
        except (OSError, ValueError):
            pass  # free, or being written
    return min(share, pool.size - others)


def reference_compile(worker, text):
    """Seconds one build of the reference source takes in worker's folder, the wait for a slot left out. None when it fails.

    It holds a compile slot like any build, and stays out of the block's compile times.
    """
    wait = worker.environment.settings["lock_retry_s"]
    try:
        retrying(lambda: worker.source.write_bytes(source_bytes(text)), wait)
    except OSError:
        return None
    with compile_slot(worker):
        start = time.perf_counter()
        _, failure = build_unit(*worker.args(), worker.objdir, str(worker.report))
        return None if failure else time.perf_counter() - start


class Tuner:
    """Sets how many of a block's workers run at once, and watches what the machine gives the block.

    The count starts at `start` (the cores divided by the active writers) and stays between the
    floor, half of that, and `most`, the worker threads the block has; it never rises past the
    pool's share. Every tuning tick it is judged on unique compiles per second against the tick
    before: the first judged tick adds a worker to try, a gain above `tune_gain` adds another, and a
    loss above `tune_loss`, or a p95 compile time above `tune_spread` medians, takes one back.
    Inside the noise band it holds. A tick with fewer than two compiles per worker is joined to the
    next. The tick after a cut only sets the new base, because it still holds compiles started
    before the cut, and a count the tuner gave up is not tried again for TUNE_RETRY_TICKS ticks.

    With a reference (a spare Worker and the baseline's source) it recompiles the baseline every
    `reference_s`. The base is the median of the block's first 2 x start compile times, or the
    first reference compile when the block has built nothing. A reference compile more than
    REF_SLOW over the base halves the worker count, down to the floor.

    At each tick it also notes whether the pool could give the block its floor: a block that spent
    over half its time below it was starved by the other writers.

    fixed (a worker count set in local.json) and a `tune_s` of 0 keep the count as it started.
    """

    def __init__(self, pool, launcher, settings, start, most, fixed=False, reference=None):
        self.pool, self.launcher, self.settings = pool, launcher, settings
        self.start = self.target = self.low = self.high = start
        self.most, self.floor = most, max(1, start // 2)
        self.adjusts = not fixed and settings["tune_s"] > 0
        self.tick_s = settings["tune_s"] or SEARCH_DEFAULTS["tune_s"]
        self.reference = reference if settings["reference_s"] > 0 else None
        self.lock = threading.Condition()
        self.stop = threading.Event()
        self.threads, self.block = [], None
        self.prev = None  # the compiles per second of the judged tick before
        self.moved = 0  # the last change to the count: below zero after a cut
        self.gave_up, self.gave_up_at, self.ticks = None, 0, 0
        self.compiled = self.seen = 0  # the block's compiles and compile times already counted
        self.span, self.built, self.times = 0.0, 0, []  # the tick being judged: seconds, compiles, compile times
        self.at = None  # when the block was last looked at
        self.short = False  # whether the pool then gave it less than the floor
        self.worker_s = self.starved_s = self.watched_s = 0.0
        self.refs, self.base = [], None

    def admit(self, index):
        """Hold worker `index` back while the count is at or under it. False once the block has ended."""
        with self.lock:
            while index >= self.target:
                if self.block.end or self.stop.is_set():
                    return False
                self.lock.wait(0.05)
        return True

    def set(self, count):
        """Change the count. Call with the lock held."""
        self.target = count
        self.low, self.high = min(self.low, count), max(self.high, count)
        self.lock.notify_all()

    def begin(self, block):
        self.block, self.at = block, time.perf_counter()
        self.short = pool_capacity(self.pool) < self.floor
        runs = [self.tune] + ([self.watch] if self.reference else [])
        self.threads = [threading.Thread(target=run, daemon=True) for run in runs]
        for th in self.threads:
            th.start()

    def finish(self):
        """Stop tuning. A reference compile still running is waited for: it builds in the block's scratch folder."""
        self.stop.set()
        for th in self.threads:
            th.join()
        self.look()

    def look(self):
        """Add the time since the last look to the block's totals, and note what the pool gives now. Returns that time."""
        now = time.perf_counter()
        took, self.at = now - self.at, now
        with self.lock:
            self.worker_s += took * self.target
        self.watched_s += took
        if self.short:
            self.starved_s += took
        self.short = pool_capacity(self.pool) < self.floor
        return took

    def tune(self):
        while not self.stop.wait(self.tick_s):
            took = self.look()
            if self.adjusts and not self.block.end:
                self.judge(took)

    def judge(self, took):
        """One tuning tick: move the count by what the compiles since the last judged tick show."""
        s = self.settings
        with self.block.lock:
            compiled = self.block.counts["compiled"]
        with self.launcher.lock:
            times = self.launcher.samples[self.seen:]
            self.seen += len(times)
        self.span, self.built, self.compiled = self.span + took, self.built + compiled - self.compiled, compiled
        self.times += times
        with self.pool.lock:
            room = min(self.most, self.pool.share())
        with self.lock:
            if self.built < 2 * self.target:
                return  # too few compiles to say anything: this tick is judged with the next
            self.ticks += 1
            rate, times = self.built / self.span, sorted(self.times)
            self.span, self.built, self.times = 0.0, 0, []
            prev, self.prev = self.prev, rate
            p95 = times[min(len(times) - 1, math.ceil(0.95 * len(times)) - 1)] if times else 0.0
            spread = bool(times) and p95 > s["tune_spread"] * statistics.median(times)
            waited = self.ticks - self.gave_up_at >= TUNE_RETRY_TICKS
            may_add = self.target < room and (self.gave_up is None or self.target + 1 < self.gave_up or waited)
            if self.moved < 0:
                move = 0
            elif prev is not None and (rate < (1 - s["tune_loss"]) * prev or spread):
                move = -1 if self.target > self.floor else 0
            elif prev is None or rate > (1 + s["tune_gain"]) * prev:
                move = 1 if may_add else 0
            else:
                move = 0
            if move < 0:
                self.gave_up, self.gave_up_at = self.target, self.ticks
            self.moved = move
            if move:
                self.set(self.target + move)

    def watch(self):
        worker, text = self.reference
        while not self.stop.wait(self.settings["reference_s"]):
            took = reference_compile(worker, text)
            if took is None:
                continue
            with self.launcher.lock:
                first = self.launcher.samples[:2 * self.start]
            with self.lock:
                if self.base is None:
                    self.base = statistics.median(first) if first else took
                self.refs.append(took)
                if took > (1 + REF_SLOW) * self.base and self.adjusts and self.target > self.floor:
                    self.gave_up, self.gave_up_at, self.moved = self.target, self.ticks, -1
                    self.set(max(self.floor, self.target // 2))

    def report(self):
        """What the block's record keeps of the tuning."""
        ms = [round(x * 1000, 2) for x in self.refs]
        return {"workers_min": self.low, "workers_max": self.high, "workers_end": self.target,
                "workers_floor": self.floor, "worker_s": self.worker_s,
                "starved_frac": round(self.starved_s / self.watched_s, 3) if self.watched_s > 0 else 0.0,
                "t_ref_ms": round(statistics.median(ms), 2) if ms else None, "t_ref_max_ms": max(ms) if ms else None,
                "t_ref_base_ms": None if self.base is None else round(self.base * 1000, 2)}


def reduce_steering(template, seeds, result, boost=None):
    """The seed of the steered match that keeps the fewest steer choices, each flipped to a natural alternative where
    the match survives it. result gives a seed's result, building only a candidate not scored before.

    Among steered matches the one with the fewest steer choices is kept, then the likeliest (boost is the
    history's, see candidates), then the lowest seed: the order their builds ended in decides nothing.
    """
    weights = likelihoods(template, boost)

    def order(seed):
        vector = template.vector(seed)
        return len(template.steering(vector)), -math.prod(w[pick] for w, pick in zip(weights, vector)), seed

    vector = template.vector(min(seeds, key=order))
    for i, _ in template.steering(vector):
        for pick in range(len(template.choices[i].alternatives)):
            if steer(template.choices[i], pick) is not None:
                continue
            flipped = vector[:i] + [pick] + vector[i + 1:]
            if result(template.seed(flipped)) == "bytes-match":
                vector = flipped
                break
    return template.seed(vector)


EFFECT_ROWS = 8  # choice points the effect table lists
NEXT_ROWS = 2  # runners-up the summary names


def insights(template, results, best):
    """What the round's results show: the effect table, the inert choice points, and the next two candidates.

    The table lists each choice point that changes the score, with its alternatives' change in
    differing bytes against the baseline, largest effect first. A runner-up is the best other
    candidate, named by the choices where it departs from the best.
    """
    by_seed = {r["seed"]: r for r in results}
    base = by_seed.get(0, {}).get("differ_bytes")
    effects = []
    for i, c in enumerate(template.choices):
        deltas = {}
        for pick in range(1, len(c.alternatives)):
            vector = [0] * len(template.choices)
            vector[i] = pick
            got = by_seed.get(template.seed(vector), {}).get("differ_bytes")
            if base is not None and got is not None and got != base:
                deltas[f"{c.label}{pick}"] = got - base
        if deltas:
            effects.append((max(abs(d) for d in deltas.values()), c.label, deltas))
    effects.sort(key=lambda e: (-e[0], e[1]))
    out = {"effects": [{label: deltas} for _, label, deltas in effects[:EFFECT_ROWS]],
           "inert": inert_choices(template, results)}
    if "seed" in best:
        top = template.vector(best["seed"])
        scored = sorted((r for r in results if r["seed"] != best["seed"] and r["differ_bytes"] is not None
                         and r["differ_bytes"] >= 0), key=lambda r: (r["differ_bytes"], r["seed"]))
        out["next"] = [" ".join(w for w, a, b in zip(r["code"].split(), template.vector(r["seed"]), top) if a != b)
                       + f": {r['differ_bytes']} bytes" for r in scored[:NEXT_ROWS]]
    if template.choices and len(out["inert"]) == len(template.choices):
        out["stop"] = "every choice point is inert: no alternative changes the object, so stop searching this template"
    return out


def summary(template, end, best, counts, winner, results=(), history_line="", notices=()):
    """The round as the writer reads it: one JSON object, held under the token cap. It never holds source."""
    out = {"end": end, "best": None, "counts": counts}
    if history_line:
        out["history"] = history_line
    if notices:
        out["notice"] = list(notices)  # for the user; the cap never drops it
    if "score" in best:
        out["best"] = {"code": template.code(template.vector(best["seed"])), "differ_bytes": best["score"].differ_bytes}
    if winner:
        out["winner"] = str(winner)
    elif "score" in best:
        out["window"] = list(best["window"])
    else:
        out["failure"] = best["failure"][-FAILURE_CHARS:]
    if results:
        out.update(insights(template, results, best))
    cap = SUMMARY_TOKENS * TOKEN_CHARS
    for key in ("window", "next", "effects"):  # what the cap drops first, a row at a time
        while len(json.dumps(out)) > cap and out.get(key):
            out[key].pop()
    over = len(json.dumps(out)) - cap
    if over > 0 and out.get("failure"):
        out["failure"] = out["failure"][over:]
    return out


CACHE_ENTRIES = 50000  # what the cache keeps of each kind of entry; the oldest go first
CACHE_KINDS = ("stable", "src", "obj")


def search_cache_path():
    """The result cache: on this machine only, under .decomp/, shared by every worktree and never committed."""
    return checkout_dir() / "search-cache.json"


def load_cache():
    """The cache as three maps: stable (is a compile's object repeatable), src (source hash to result), obj (object hash to result)."""
    try:
        data = json.loads(search_cache_path().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        data = {}
    return {k: data[k] if isinstance(data, dict) and isinstance(data.get(k), dict) else {} for k in CACHE_KINDS}


def save_cache(cache):
    """Write the cache, first merging what another search wrote since it was read."""
    merged = load_cache()
    for kind in CACHE_KINDS:
        merged[kind].update(cache[kind])
    for kind in ("src", "obj"):
        while len(merged[kind]) > CACHE_ENTRIES:
            del merged[kind][next(iter(merged[kind]))]
    path = search_cache_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + f".{os.getpid()}.tmp")
    tmp.write_text(json.dumps(merged), encoding="utf-8")
    os.replace(tmp, path)


def search_context(t, compiler, tree, text):
    """One hash of everything besides the candidate's source that a score depends on.

    The compiler's manifest entry, the build and diff commands, the tree's tools folder (where the
    wrappers and so the flags live), the expected bytes, the symbol map, and the headers beside the unit.
    """
    h = hashlib.sha256()

    def put(*parts):
        for part in parts:
            h.update(str(part).encode("utf-8", errors="replace") + b"\0")

    entry = next((x for x in toolchain()["tools"] if x["name"] == compiler), None)
    put(t["id"], compiler, CFG["build"], CFG["diff"], json.dumps(entry, sort_keys=True))
    for rel in [t["expected"], SYMBOLS] + beside(tree, t["source"], text):
        f = Path(tree) / rel
        put(rel, file_sha(f) if f.is_file() else "")
    tools = Path(tree) / "tools"
    for f in sorted(tools.rglob("*")) if tools.is_dir() else []:
        if f.is_file() and "__pycache__" not in f.parts and f.stat().st_size <= 1 << 20:
            put(f.relative_to(tools).as_posix(), file_sha(f))
    return h.hexdigest()


def objects_repeat(worker, spare, text, cache, ctx):
    """Whether compiling one source twice, in two folders, gives the same object file.

    COFF objects can carry a timestamp or the source's path. The answer is kept in the cache. The two
    builds run a second apart, so that a timestamp in whole seconds shows. When the source cannot be
    built there is no answer, and objects count as repeatable.
    """
    if ctx in cache["stable"]:
        return cache["stable"][ctx]
    hashes = []
    for w in (worker, spare):
        if hashes:
            time.sleep(1.1)
        obj, failure = w.build(text)
        if failure or not os.path.exists(obj):
            return True
        hashes.append(file_sha(obj))
    cache["stable"][ctx] = hashes[0] == hashes[1]
    return cache["stable"][ctx]


class Memo:
    """Scores candidates through the dedupe layers, so a build or a diff runs only for what is unseen.

    Order for one candidate: the source seen this round, the source in the cache, a refusal by the
    guardrails, the build, the object known to the cache (with `function` hashing: the function's bytes
    as the diff adapter reports them in `function_sha256`, known after the diff), and last the diff.
    A block's workers share one Memo. A source two workers hold at once is built by the first, and
    the other waits for that result.
    """

    def __init__(self, cache, ctx, hashing):
        self.cache, self.ctx, self.hashing = cache, ctx, hashing
        self.lock = threading.Lock()
        self.seen, self.objects = {}, set()  # seen: source key to its entry, or to an Event while a worker builds it
        self.src_hits = self.cache_hits = self.object_hits = 0

    def key(self, kind, data):
        h = hashlib.sha256(self.ctx.encode() + b"\0" + kind.encode() + b"\0")
        h.update(data if isinstance(data, bytes) else data.encode())
        return h.hexdigest()

    def new_object(self, e):
        """Whether the entry's object is the first of its hash this round. Call with the lock held."""
        new = bool(e.get("o")) and e["o"] not in self.objects
        if new:
            self.objects.add(e["o"])
        return new

    def entry(self, text, worker):
        """One candidate's result, built in worker's folder when it is unseen. Returns (entry, how, new object).

        The entry holds the result `r`, the differing bytes `d`, a failure `log`, the diff window `w`,
        and the object key `o`. how is `repeat` (the source was tried this round), `cached` (served
        from the result cache), `refused` (by the guardrails), or `built`.
        """
        skey = self.key("src", source_bytes(text))
        while True:
            with self.lock:
                e = self.seen.get(skey)
                if e is None and skey in self.cache["src"]:
                    e = self.seen[skey] = self.cache["src"][skey]
                    self.cache_hits += 1
                    return e, "cached", self.new_object(e)
                if e is None:
                    building = self.seen[skey] = threading.Event()
                    break
                if not isinstance(e, threading.Event):
                    self.src_hits += 1
                    return e, "repeat", False
            e.wait()
        try:
            e = self.fresh(text, worker)
        except BaseException:
            with self.lock:
                del self.seen[skey]
            building.set()
            raise
        with self.lock:
            self.seen[skey] = e
            if e["r"] in ("differ", "bytes-match"):
                self.cache["src"][skey] = e
            new = self.new_object(e)
        building.set()
        return e, "refused" if e["r"] == "guardrail" else "built", new

    def fresh(self, text, w):
        refused = w.refuse(text)
        if refused:
            return {"r": refused.result, "d": None, "log": refused.log}
        obj, failure = w.build(text)
        if failure:
            return {"r": "build-fail", "d": None, "log": failure}
        okey = None
        if self.hashing == "object" and os.path.exists(obj):
            okey = self.key("obj", file_sha(obj).encode())
            with self.lock:
                if okey in self.cache["obj"]:
                    self.object_hits += 1
                    return dict(self.cache["obj"][okey], o=okey)
        fields = {}
        s = w.diff(obj, fields)
        e = {"r": s.result, "d": s.differ_bytes, "log": s.log, "w": window(w.report, s.first_differ), "f": s.first_differ}
        if self.hashing == "function" and isinstance(fields.get("function_sha256"), str):
            okey = self.key("fn", fields["function_sha256"].encode())
        with self.lock:
            if self.hashing == "function" and okey in self.cache["obj"]:
                self.object_hits += 1
            if okey and e["r"] in ("differ", "bytes-match"):
                e["o"] = okey
                self.cache["obj"][okey] = e
        return e

    def counts(self):
        """What the layers did, for the summary."""
        return {"src_dedupe_hits": self.src_hits, "cache_hits": self.cache_hits, "object_hits": self.object_hits,
                "unique_objects": len(self.objects), "hashing": self.hashing}


PERF = "perf.jsonl"  # the performance log: this machine only, never committed, shared by every worktree
PERF_WINDOW = 20  # blocks of the same compiler a flag is compared with
PERF_MIN = 3  # blocks a median needs before it can raise a flag
PERF_COMPILES = 2  # compiles per worker a block needs before it says anything about speed
PERF_STREAK = 3  # blocks in a row a flag is raised before the user is told
PERF_DROP = 0.3  # a fall this large in compiles per worker-second against the median raises slow-compile
PERF_SHARE = 0.2  # idle share of the workers, or scoring share of the stage time, above which a flag is raised
PERF_JITTER = 3.0  # p95 compile time, in median compile times, above which io-jitter is raised
PERF_STARVED = 0.5  # share of a block's time below its worker floor above which starved-by-writers is raised
FLAG_FIXES = {  # the fix only the user can make, where there is one
    "slow-compile": "exclude the project folder and the system temp folder from antivirus scanning, stop other "
                    "CPU-heavy programs and check the power plan for throttling, or move the temp folder (TEMP) to a RAM disk",
    "io-jitter": "exclude the project folder and the system temp folder from antivirus scanning and the file indexer, "
                 "or move the temp folder (TEMP) to a RAM disk",
    "contention-or-throttle": "stop other CPU-heavy programs, and check the power plan and the cooling for throttling",
    "starved-by-writers": "lower the concurrent writer count in the contract, or stop the other searches on this machine",
}


def perf_records(compiler=None):
    """The performance log's records, oldest first, those of one compiler when it is given. A damaged line is skipped."""
    p = checkout_dir() / PERF
    out = []
    for line in p.read_text(encoding="utf-8", errors="replace").splitlines() if p.exists() else []:
        try:
            rec = json.loads(line)
        except ValueError:
            continue
        if isinstance(rec, dict) and (compiler is None or rec.get("compiler") == compiler):
            out.append(rec)
    return out


def append_perf(rec):
    """Add one record to the performance log. A log that cannot be written never stops a search."""
    p = checkout_dir() / PERF
    with contextlib.suppress(OSError):
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("a", encoding="utf-8", newline="\n") as f:
            f.write(json.dumps(rec, sort_keys=True) + "\n")


def block_rate(rec):
    """Compiles per worker-second of a block record, or None when it holds no rate."""
    try:
        rate = rec["compiled"] / (rec["workers_end"] * rec["wall_s"])
    except (KeyError, TypeError, ZeroDivisionError):
        return None
    return rate if rate > 0 else None


def tuning_flags(rec, past):
    """The flags the tuner's measurements raise: {flag: its measured cost as a sentence}.

    contention-or-throttle: a reference compile of the block ran more than REF_SLOW over the block's
    base, or the block's reference time is REF_SLOW or more over the median of the earlier blocks of
    the same unit, once PERF_MIN exist (another unit's compile time says nothing about this one's).
    starved-by-writers: the pool left the block below its worker floor for over PERF_STARVED of its
    time. past is the last PERF_WINDOW block records of the same compiler.
    """
    def number(x):
        return isinstance(x, (int, float)) and not isinstance(x, bool) and x > 0

    flags = {}
    base, slowest, ref = rec.get("t_ref_base_ms"), rec.get("t_ref_max_ms"), rec.get("t_ref_ms")
    refs = [r["t_ref_ms"] for r in past if rec.get("unit") and r.get("unit") == rec["unit"] and number(r.get("t_ref_ms"))]
    median = statistics.median(refs) if len(refs) >= PERF_MIN else None
    if number(base) and number(slowest) and slowest > (1 + REF_SLOW) * base:
        flags["contention-or-throttle"] = (f"the reference compile took {slowest:.0f} ms, {round(100 * (slowest / base - 1))} "
                                           f"percent over the {base:.0f} ms a compile took as the block began")
    elif median and number(ref) and ref >= (1 + REF_SLOW) * median:
        flags["contention-or-throttle"] = (f"the reference compile took {ref:.0f} ms, {round(100 * (ref / median - 1))} "
                                           f"percent over the median of {median:.0f} ms over the last {len(refs)} blocks of this unit")
    starved = rec.get("starved_frac")
    if number(starved) and starved > PERF_STARVED and rec["compiled"] > 0:
        flags["starved-by-writers"] = (f"the slot pool left the block fewer than its floor of {rec.get('workers_floor')} "
                                       f"workers for {round(100 * starved)} percent of its time")
    return flags


def perf_flags(rec, past):
    """The flags a block record raises: {flag: its measured cost as a sentence}.

    past is the log's earlier records of the same compiler, oldest first. slow-compile and io-jitter
    compare with the median of the last PERF_WINDOW blocks of them, once PERF_MIN exist.
    expander-starved and scorer-bound are shares of this block's own time. A block that built fewer
    than PERF_COMPILES per worker raises none of these. The tuner's flags are tuning_flags'.
    """
    past = [r for r in past if r.get("kind") == "block"][-PERF_WINDOW:]
    flags = tuning_flags(rec, past)
    if rec["compiled"] < PERF_COMPILES * rec["workers_end"]:  # served by the cache or ended at once: nothing to measure
        return flags
    rate = block_rate(rec)
    rates = [x for x in map(block_rate, past) if x is not None]
    if rate is not None and len(rates) >= PERF_MIN:
        median = statistics.median(rates)
        if rate <= (1 - PERF_DROP) * median:
            flags["slow-compile"] = (f"each worker built {rate:.1f} compiles a second, {round(100 * (1 - rate / median))} "
                                     f"percent fewer than the median of {median:.1f} over the last {len(rates)} blocks")
    idle = rec.get("idle_frac")
    if isinstance(idle, (int, float)) and idle > PERF_SHARE:
        flags["expander-starved"] = f"the workers sat idle {round(100 * idle)} percent of the block, waiting for candidates"
    stage = rec.get("stage_ms") or {}
    total = sum(v for v in stage.values() if isinstance(v, (int, float)))
    if total > 0 and stage.get("score", 0) / total > PERF_SHARE:
        flags["scorer-bound"] = f"scoring took {round(100 * stage['score'] / total)} percent of the block's stage time"
    p95 = rec.get("t_compile_p95_ms")
    p50s = [r["t_compile_p50_ms"] for r in past if isinstance(r.get("t_compile_p50_ms"), (int, float))]
    base = statistics.median(p50s) if len(p50s) >= PERF_MIN else rec.get("t_compile_p50_ms")
    if isinstance(p95, (int, float)) and isinstance(base, (int, float)) and base > 0 and p95 > PERF_JITTER * base:
        flags["io-jitter"] = (f"the slowest compiles took {p95:.0f} ms, {p95 / base:.1f} times the median compile "
                              f"of {base:.0f} ms")
    return flags


def perf_notices(flags, past):
    """What to tell the user now: the sentence for each flag raised in PERF_STREAK blocks in a row, once per streak.

    past is the log's earlier records of the same compiler, oldest first; each block record holds the
    flags it raised and those it showed. Returns {flag: sentence}.
    """
    out = {}
    for flag, cost in flags.items():
        streak, shown = 1, False
        for r in reversed([r for r in past if r.get("kind") == "block"]):
            if flag not in (r.get("flags") or []):
                break
            streak += 1
            shown = shown or flag in (r.get("shown") or [])
        if streak >= PERF_STREAK and not shown:
            fix = FLAG_FIXES.get(flag)
            out[flag] = f"{flag} in {streak} blocks in a row: {cost}." + (f" Only you can fix it: {fix}." if fix else "")
    return out


def block_record(t, compiler, perf, counts, memo_counts, launcher, end, best, latency, start_best, round_no, block_no):
    """The performance log's record of one finished block."""
    ms = sorted(round(x * 1000, 2) for x in launcher.samples)
    workers, wall = counts["workers"], perf["wall"]
    stage = {k: round(v * 1000, 1) for k, v in {**launcher.stage, **perf["stage"]}.items()}
    final = best["score"].differ_bytes if "score" in best else None
    tuning = perf.get("tuning") or {}  # the Tuner's report: without one the worker count never moved
    worker_s = tuning.get("worker_s") or workers * wall
    return {
        "kind": "block", "unix": now(), "ticket": t["id"], "unit": t["unit"], "compiler": compiler,
        "round": round_no, "block": block_no, "wall_s": round(wall, 3),
        "workers_min": tuning.get("workers_min", workers), "workers_max": tuning.get("workers_max", workers),
        "workers_end": tuning.get("workers_end", workers), "workers_floor": tuning.get("workers_floor", workers),
        "starved_frac": tuning.get("starved_frac", 0.0),
        "t_ref_base_ms": tuning.get("t_ref_base_ms"), "t_ref_max_ms": tuning.get("t_ref_max_ms"),
        "expanded": perf["expanded"], "compiled": counts["compiled"], "unique_objects": memo_counts["unique_objects"],
        "build_fail": counts["build_fail"], "killed": launcher.killed, "src_dedupe_hits": memo_counts["src_dedupe_hits"],
        "t_compile_p50_ms": statistics.median(ms) if ms else None,
        "t_compile_p95_ms": ms[min(len(ms) - 1, math.ceil(0.95 * len(ms)) - 1)] if ms else None,
        "t_ref_ms": tuning.get("t_ref_ms") or (round(launcher.samples[0] * 1000, 2) if launcher.samples else None),
        "stage_ms": stage, "idle_frac": round(max(0.0, 1 - perf["busy"] / worker_s), 3) if worker_s > 0 else 0.0,
        "best_score_start": start_best, "best_score_end": final,
        "t_to_best_s": None if perf["best_at"] is None else round(perf["best_at"], 3),
        "end_reason": end, "model_latency_s": None if latency is None else round(latency, 2),
        "writers_active": counts.get("writers_active", 1),  # the searches in the slot pool when this one started
    }


def log_block(compiler, rec):
    """Flag the block record against the log, append it, and return the sentences to tell the user."""
    past = perf_records(compiler)
    flags = perf_flags(rec, past)
    notices = perf_notices(flags, past)
    rec.update(flags=sorted(flags), shown=sorted(notices))
    append_perf(rec)
    return list(notices.values())


def search_dir(tid):
    """Where a ticket's last template round is kept: on this machine only, shared by every worktree."""
    return checkout_dir() / "search" / tid


def model_latency(state):
    """Seconds since the ticket's last round ended on this machine: the time the model took. None when unknown.

    This one timing is by the wall clock, because it spans two runs of the tool.
    """
    try:
        took = time.time() - float((state / "ended").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return took if took >= 0 else None


ROUND_EVIDENCE = "template-round: "  # starts the evidence line of an attempt `verify` recorded as a template round


def record_round(t, template, best, results):
    """Count a finished round as one attempt in the check trail, and keep what `verify --template-round` records.

    The round carries the category of the attempt before it: it worked on that difference.
    """
    category = trail(t["id"])[-1]["category"]
    kept = {"unix": now(), "category": category, "best": None, "result": results[0]["result"] if results else "build-fail",
            "differ_bytes": None, "kinds": []}
    if "score" in best:
        vector = template.vector(best["seed"])
        kinds = [getattr(c, "kind", None) for c, pick in zip(template.choices, vector) if pick]
        kept.update(best=template.code(vector), result=best["score"].result, differ_bytes=best["score"].differ_bytes,
                    kinds=[k for k in kinds if k])
    (search_dir(t["id"]) / "round.json").write_text(json.dumps(kept, sort_keys=True) + "\n", encoding="utf-8")
    append_trail(t["id"], "search", kept["result"], kept["differ_bytes"], category)


def history(compiler):
    """What template rounds fixed on this compiler, worked out from the attempts ledger: {category: {kind: [fixed, tried]}}.

    A round is an attempt whose evidence holds a ROUND_EVIDENCE line. It counts once toward each kind
    in that line, under the category it worked on; it fixed those kinds when the attempt is a
    bytes-match. Read afresh at every round start, so no file holds it and a win another writer
    recorded since the last round shows in this one.
    """
    out, units = {}, {}
    for rec in records("attempts.jsonl"):
        try:
            tid = rec["ticket"]
            if tid not in units:
                units[tid] = read_ticket(tid)[0]["unit"] if ticket_path(tid).exists() else None
            if units[tid] is None or compiler_for(units[tid]) != compiler:
                continue
            lines = (ROOT / rec["evidence"]).read_text(encoding="utf-8", errors="replace").splitlines()
            held = [json.loads(x[len(ROUND_EVIDENCE):]) for x in lines if x.startswith(ROUND_EVIDENCE)]
        except (OSError, ValueError, KeyError):
            continue
        for kept in held[-1:]:
            for kind in set(kept.get("kinds") or []):
                n = out.setdefault(kept.get("category") or "", {}).setdefault(kind, [0, 0])
                n[0] += rec.get("result") == "bytes-match"
                n[1] += 1
    return out


def history_line(past, category):
    """The summary's one line of project history for the ticket's category, or '' when none applies."""
    kinds = past.get(category or "", {})
    if not kinds:
        return ""
    kind, (fixed, tried) = max(kinds.items(), key=lambda kv: (kv[1][0], -kv[1][1], kv[0]))
    return f"{kind} fixed {category} {fixed} of {tried} times on this compiler"


def kept_round(tid):
    """The ticket's last template round as `verify --template-round` records it. Stops when this machine keeps none."""
    try:
        return json.loads((search_dir(tid) / "round.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        die(f"no template round is kept for {tid} on this machine, so --template-round has no evidence to record; "
            "nothing was recorded. Run verify on the machine that ran the round, or without the flag.")


def cmd_search(a):
    t, _ = read_ticket(a.id)
    if a.detail is not None:
        return search_detail(t, a.detail)
    if not a.template:
        die("search <id> <template file>, or search <id> --detail '<choice code>' for one candidate of the last round")
    environment, compiler = prepare(t)
    if not contract_rules()[0]:
        die("the contract does not allow template search (`template_search` is false in decomp.json); "
            "nothing was built.")
    is_open, reason = gate(t)
    if not is_open:
        die(f"template search is closed for {t['id']}: {reason}; nothing was built.")
    try:
        data = Path(a.template).read_bytes()
    except OSError as e:
        die(f"cannot read the template: {e}")
    text = source_text(data)
    template = parse_template(text)
    if contract_rules()[1] == "forbidden" and any(c.steers and any(w is not None for w in c.steers) for c in template.choices):
        die("the contract's fakematch rule is forbidden, and this template holds a steering alternative "
            "(`/* steer: <why> */`); remove it or search natural alternatives only. Nothing was built.")
    settings = search_settings()
    state = search_dir(t["id"])
    latency = model_latency(state)
    ceiling = settings["ceiling_s"] if latency is None else min(latency, settings["ceiling_s"])
    pool = SlotPool(settings).open()
    fixed = int(settings["workers"])
    start = max(1, min(fixed or pool.start_workers(), template.space()))
    count = start if fixed else max(start, min(pool.size, template.space()))  # threads: the tuner runs `start` of them at first
    launcher = Launcher(environment, settings, start)
    launcher.pool = pool
    tree = os.getcwd()
    scratch = tempfile.mkdtemp(prefix="decomp-search-")
    try:
        workers = [Worker(Path(scratch) / f"w{i}", launcher, t, compiler, tree, text) for i in range(count)]
        cache, ctx = load_cache(), search_context(t, compiler, tree, text)
        spare = None
        if ctx not in cache["stable"]:
            spare = workers[1] if count > 1 else Worker(Path(scratch) / "spare", launcher, t, compiler, tree, text)
        baseline = template.render(template.vector(0))
        calibrating, began = spare is not None, time.perf_counter()
        hashing = "object" if objects_repeat(workers[0], spare, baseline, cache, ctx) else "function"
        if calibrating:
            append_perf({"kind": "calibration", "unix": now(), "ticket": t["id"], "compiler": compiler,
                         "wall_s": round(time.perf_counter() - began, 3),
                         "t_ref_ms": round(launcher.samples[0] * 1000, 2) if launcher.samples else None})
        launcher.restart_timing()
        memo = Memo(cache, ctx, hashing)
        past = history(compiler)  # at each round start, so a win recorded since the last round counts
        category = (trail(t["id"]) or [{}])[-1].get("category")
        boost = {k: n[0] for k, n in past.get(category or "", {}).items()}
        trailed = trail(t["id"])
        timing = {}
        reference = (Worker(Path(scratch) / "ref", launcher, t, compiler, tree, text), baseline) if settings["reference_s"] else None
        tuner = Tuner(pool, launcher, settings, start, count, bool(fixed), reference)
        with persistent_wineserver(launcher):
            end, best, counts, results = run_block(template, memo, workers, settings, ceiling, boost, timing, tuner)
        counts.update(memo.counts(), killed=launcher.killed, shell=launcher.shell)
        counts.update(writers_active=pool.writers_at_start, slots=pool.size, slots_reclaimed=pool.reclaimed)
        save_cache(cache)
        mine = [r for r in perf_records(compiler) if r.get("ticket") == t["id"] and r.get("kind") == "block"]
        notices = log_block(compiler, block_record(
            t, compiler, timing, counts, memo.counts(), launcher, end, best, latency,
            trailed[-1]["differ_bytes"] if trailed else None, sum(r["by"] == "search" for r in trailed) + 1, len(mine) + 1))
    finally:
        pool.close()
        shutil.rmtree(scratch, ignore_errors=True)
    state.mkdir(parents=True, exist_ok=True)
    (state / "template").write_bytes(data)
    (state / "results.jsonl").write_text("".join(json.dumps(r) + "\n" for r in results), encoding="utf-8")
    record_round(t, template, best, results)
    winner = None
    if end == "match":
        winner = Path(tempfile.mkdtemp(prefix="decomp-winner-")) / Path(t["source"]).name
        winner.write_bytes(source_bytes(template.render(template.vector(best["seed"]))))
    print(json.dumps(summary(template, end, best, counts, winner, results, history_line(past, category), notices)))
    (state / "ended").write_text(str(time.time()), encoding="utf-8")


def search_detail(t, code):
    """Print one candidate of the ticket's last round: a JSON line with its score, then its source."""
    state = search_dir(t["id"])
    if not (state / "template").exists():
        die(f"no template round is kept for {t['id']} on this machine; run search with a template first")
    template = parse_template(source_text((state / "template").read_bytes()))
    vector = template.from_code(code)
    seed = template.seed(vector)
    tried = [json.loads(x) for x in (state / "results.jsonl").read_text(encoding="utf-8").splitlines()]
    hit = next((r for r in tried if r["seed"] == seed), {"result": "not-tried", "differ_bytes": None})
    print(json.dumps({"code": template.code(vector), "result": hit["result"], "differ_bytes": hit["differ_bytes"]}))
    sys.stdout.flush()
    sys.stdout.buffer.write(source_bytes(template.render(vector)))


def main():
    global ROOT, CFG
    top = subprocess.run(["git", "rev-parse", "--show-toplevel"], capture_output=True, text=True)
    if top.returncode != 0:
        die("run inside the decomp project repo")
    ROOT = Path(top.stdout.strip())
    p = argparse.ArgumentParser(prog="decomp.py")
    s = p.add_subparsers(dest="cmd", required=True)
    s.add_parser("doctor").set_defaults(f=cmd_doctor)
    s.add_parser("contract-keys").set_defaults(f=cmd_contract_keys)
    x = s.add_parser("provision"); x.add_argument("--tool"); x.add_argument("--force", action="store_true")
    x.set_defaults(f=cmd_provision)
    s.add_parser("gen-specs").set_defaults(f=cmd_gen_specs)
    s.add_parser("gen-tickets").set_defaults(f=cmd_gen_tickets)
    x = s.add_parser("next"); x.add_argument("--n", type=int, default=3); x.add_argument("--first"); x.add_argument("--reason"); x.set_defaults(f=cmd_next)
    x = s.add_parser("claim"); x.add_argument("id"); x.add_argument("--by", required=True); x.set_defaults(f=cmd_claim)
    x = s.add_parser("release"); x.add_argument("id"); x.add_argument("--to", default="open"); x.set_defaults(f=cmd_release)
    x = s.add_parser("inventory"); x.add_argument("--redo", action="store_true"); x.set_defaults(f=cmd_inventory)
    x = s.add_parser("disasm"); x.add_argument("id"); x.set_defaults(f=cmd_disasm)
    x = s.add_parser("check"); x.add_argument("id"); x.add_argument("--category"); x.set_defaults(f=cmd_check)
    x = s.add_parser("verify"); x.add_argument("id"); x.add_argument("--model", required=True)
    x.add_argument("--category"); x.add_argument("--branch"); x.add_argument("--template-round", action="store_true")
    x.set_defaults(f=cmd_verify)
    x = s.add_parser("audit"); x.add_argument("id"); x.add_argument("verdict", choices=["pass", "fail"])
    x.add_argument("--auditor", required=True); x.add_argument("--note"); x.add_argument("--branch"); x.set_defaults(f=cmd_audit)
    x = s.add_parser("integrate"); x.add_argument("id"); x.add_argument("--branch"); x.set_defaults(f=cmd_integrate)
    x = s.add_parser("revalidate"); x.add_argument("--ref"); x.add_argument("--header"); x.add_argument("--candidate")
    x.add_argument("--judged-for", help=argparse.SUPPRESS)  # set only by this tool, on a candidate's own copy
    x.set_defaults(f=cmd_revalidate)
    x = s.add_parser("note"); x.add_argument("id"); x.add_argument("text", nargs="+"); x.set_defaults(f=cmd_note)
    x = s.add_parser("similar"); x.add_argument("id"); x.add_argument("--n", type=int, default=3); x.set_defaults(f=cmd_similar)
    x = s.add_parser("lock"); x.add_argument("name"); x.add_argument("--by", required=True); x.set_defaults(f=cmd_lock)
    x = s.add_parser("unlock"); x.add_argument("name"); x.set_defaults(f=cmd_unlock)
    x = s.add_parser("search"); x.add_argument("id"); x.add_argument("template", nargs="?")
    x.add_argument("--detail", metavar="CODE"); x.set_defaults(f=cmd_search)
    s.add_parser("link").set_defaults(f=cmd_link)
    s.add_parser("report").set_defaults(f=cmd_report)
    s.add_parser("sync").set_defaults(f=cmd_sync)
    a = p.parse_args()
    cfg = ROOT / "decomp.json"
    if cfg.exists():
        CFG = json.loads(cfg.read_text(encoding="utf-8"))
    elif a.cmd in ("doctor", "provision"):  # setup provisions before the rest of the system exists
        CFG = {}
    else:
        die("no decomp.json; run /decomp-setup")
    CFG.setdefault("integration_branch", "main")
    CFG.setdefault("frozen", {"decomp-setup": ["decomp.json", "toolchain.json", "DECOMP.md", "tools"],
                              "decomp-start": ["inventory.json", "expected"]})
    a.f(a)


if __name__ == "__main__":
    main()
