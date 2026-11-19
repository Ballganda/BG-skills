#!/usr/bin/env python3
"""Project tool for byte-for-byte decompilation.

Copied into a decomp project's tools/ by decomp-setup and frozen at the
decomp-setup tag. It is the only writer of ticket statuses and ledger records.
Standard library only. Run from the project root: python tools/decomp.py <cmd>.
"""
import argparse
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
import shutil
import subprocess
import sys
import tempfile
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


def diff_unit(environment, t, compiler, tree, source, obj, report):
    """Run the diff adapter on a built obj. Returns (result, differ_bytes, log) as build_and_diff does."""
    d = adapter(CFG["diff"], t, compiler, obj, report, tree, environment, source)
    try:
        out = json.loads(d.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        return "build-fail", None, f"diff adapter gave no JSON: {d.stderr[-2000:]}"
    if out.get("match") is True and out.get("differ_bytes", 0) == 0:
        return "bytes-match", 0, ""
    return "differ", int(out.get("differ_bytes", -1)), ""


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


def cmd_check(a):
    t, _ = read_ticket(a.id)
    environment, compiler = prepare(t)
    report = str(Path(tempfile.mkdtemp(prefix="decomp-rep-")) / "diff.txt")
    result, n, log = build_and_diff(environment, t, compiler, os.getcwd(), report)
    print(json.dumps({"result": result, "differ_bytes": n, "report": report}))
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
#   candidates       Template -> the seeds to try, in order
#   Worker.score     one candidate's source -> Score, through the build and diff adapters
#   run_round        the loop over candidates: keeps the best, stops on a match
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
# A choice point: its label, its alternatives' source text, its kind, and one likelihood per alternative
# (None: all alike). A Reference is a later PERM_VAR(label): the same pick again.
Choice = collections.namedtuple("Choice", "label alternatives kind likelihoods", defaults=("other", None))
Reference = collections.namedtuple("Reference", "label")
Score = collections.namedtuple("Score", "result differ_bytes log")  # as build_and_diff returns them


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

    def render(self, vector):
        """The candidate as plain source: each choice point replaced by its picked alternative."""
        return render_parts(self.parts, vector)


def render_parts(parts, vector):
    """Template.render, apart: each choice point replaced by its picked alternative, each reference by that pick again."""
    picks, said, out = iter(vector), {}, []
    for p in parts:
        if isinstance(p, Choice):
            said[p.label] = p.alternatives[next(picks)]
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


def read_likelihoods(where, alternatives):
    """Each alternative's text without its leading likelihood, and the likelihoods (None when none was given)."""
    texts, weights = [], []
    for alt in alternatives:
        weight = 1.0
        if alt.startswith("%"):
            m = LIKELIHOOD.match(alt)
            if not m or float(m.group(1)) <= 0:
                die(f"template {where}: a likelihood is a positive number after %, such as '%0.7 alternative'")
            weight, alt = float(m.group(1)), alt[m.end():]
        texts.append(alt)
        weights.append(weight)
    return texts, weights if any(w != 1.0 for w in weights) else None


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
            alternatives, weights = line_orders(here, body), None
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
            alternatives, weights = read_likelihoods(here, args)
            if macro == "PERM_ONCE":
                alternatives, weights = [""] + alternatives, weights and [1.0] + weights
            if len(alternatives) < 2:
                die(f"template {here}: a choice point needs two or more alternatives")
        label = label or choice_label(len(choices))
        if any(c.label == label for c in choices):
            die(f"template {here}: the label '{label}' is used twice; labels are what choice codes name")
        choice = Choice(label, alternatives, kind, weights)
        choices.append(choice)
        parts.append(choice)
        if macro == "PERM_VAR":
            variables.add(label)
    if len(choices) > MAX_CHOICES:
        die(f"template has {len(choices)} choice points; the limit is {MAX_CHOICES}")
    return Template(parts + [text[at:]])


def candidates(template):
    """The seeds a round tries, in order: the whole space, most likely first.

    A candidate's likelihood is the product of its alternatives' likelihoods. With no likelihoods
    given the order is the seeds', baseline first.
    """
    if all(c.likelihoods is None for c in template.choices):
        return range(template.space())
    return most_likely_first(template)


def most_likely_first(template):
    """Every seed, the likeliest candidate first, produced lazily so a large space costs nothing until it is read.

    Each choice point's alternatives are ranked by likelihood (written order breaking ties). A heap
    holds the frontier of rank vectors: raising one rank never raises the likelihood, and each vector
    is reached by one route, raising ranks left to right.
    """
    weights = [c.likelihoods or [1.0] * len(c.alternatives) for c in template.choices]
    ranked = [sorted(range(len(w)), key=lambda i, w=w: (-w[i], i)) for w in weights]
    cost = [[-math.log(w[i]) for i in order] for w, order in zip(weights, ranked)]

    def entry(ranks, last):
        seed = template.seed([order[r] for order, r in zip(ranked, ranks)])
        return (sum(k[r] for k, r in zip(cost, ranks)), seed, ranks, last)

    heap = [entry((0,) * len(ranked), 0)]
    while heap:
        _, seed, ranks, last = heapq.heappop(heap)
        yield seed
        for j in range(last, len(ranks)):
            if ranks[j] + 1 < len(ranked[j]):
                heapq.heappush(heap, entry(ranks[:j] + (ranks[j] + 1,) + ranks[j + 1:], j))


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

    def score(self, text):
        """Build and diff one candidate's source. The diff report of this candidate is left in self.report."""
        marks = marker_count(text, self.t["id"])
        if marks != 1:
            return Score("guardrail", None, f"expected one '@decomp {self.t['id']}' marker comment, found {marks}")
        bad = scan(text)
        if bad:
            return Score("guardrail", None, "\n".join(bad))
        self.source.write_bytes(source_bytes(text))
        self.report.unlink(missing_ok=True)
        args = (self.environment, self.t, self.compiler, self.tree, str(self.source))
        obj, failure = build_unit(*args, self.objdir, str(self.report))
        if failure:
            return Score("build-fail", None, failure)
        return Score(*diff_unit(*args, obj, str(self.report)))


def rank(score):
    """A score's sort key, lower being closer to the original. None when the candidate gave no score."""
    if score.result not in ("bytes-match", "differ") or score.differ_bytes is None or score.differ_bytes < 0:
        return None
    return (score.differ_bytes,)


def window(report):
    """The lines of a diff report the summary shows: its first ones, each cut to a fixed width."""
    try:
        with open(report, encoding="utf-8", errors="replace") as f:
            return [line.rstrip("\n")[:WINDOW_WIDTH] for _, line in zip(range(WINDOW_LINES), f)]
    except OSError:
        return []


def run_round(template, score, report):
    """Try each candidate until one matches or none is left. Returns (end reason, best, counts, results).

    score turns a candidate's source into a Score and leaves its diff report at report.
    best is a dict: seed, score, and diff window of the closest candidate, or only the first failure
    log when no candidate was scored. results holds one record per candidate tried.
    """
    counts = {"space": template.space(), "compiled": 0, "build_fail": 0, "guardrail": 0}
    best, results, failure = None, [], ""
    for seed in candidates(template):
        vector = template.vector(seed)
        s = score(template.render(vector))
        counts["guardrail" if s.result == "guardrail" else "compiled"] += 1
        counts["build_fail"] += s.result == "build-fail"
        results.append({"seed": seed, "code": template.code(vector), "result": s.result, "differ_bytes": s.differ_bytes})
        if rank(s) is None:
            failure = failure or s.log
        elif best is None or rank(s) < rank(best["score"]):
            best = {"seed": seed, "score": s, "window": window(report)}
        if s.result == "bytes-match":
            return "match", best, counts, results
    return "exhausted", best or {"failure": failure}, counts, results


def summary(template, end, best, counts, winner):
    """The round as the writer reads it: one JSON object, held under the token cap. It never holds source."""
    out = {"end": end, "best": None, "counts": counts}
    if "score" in best:
        out["best"] = {"code": template.code(template.vector(best["seed"])), "differ_bytes": best["score"].differ_bytes}
    if winner:
        out["winner"] = str(winner)
    elif "score" in best:
        out["window"] = list(best["window"])
    else:
        out["failure"] = best["failure"][-FAILURE_CHARS:]
    cap = SUMMARY_TOKENS * TOKEN_CHARS
    while len(json.dumps(out)) > cap and out.get("window"):
        out["window"].pop()
    over = len(json.dumps(out)) - cap
    if over > 0 and out.get("failure"):
        out["failure"] = out["failure"][over:]
    return out


def search_dir(tid):
    """Where a ticket's last template round is kept: on this machine only, shared by every worktree."""
    return checkout_dir() / "search" / tid


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
    try:
        data = Path(a.template).read_bytes()
    except OSError as e:
        die(f"cannot read the template: {e}")
    text = source_text(data)
    template = parse_template(text)
    tree = os.getcwd()
    scratch = tempfile.mkdtemp(prefix="decomp-search-")
    try:
        worker = Worker(Path(scratch) / "w0", environment, t, compiler, tree, text)
        end, best, counts, results = run_round(template, worker.score, worker.report)
    finally:
        shutil.rmtree(scratch, ignore_errors=True)
    state = search_dir(t["id"])
    state.mkdir(parents=True, exist_ok=True)
    (state / "template").write_bytes(data)
    (state / "results.jsonl").write_text("".join(json.dumps(r) + "\n" for r in results), encoding="utf-8")
    winner = None
    if end == "match":
        winner = Path(tempfile.mkdtemp(prefix="decomp-winner-")) / Path(t["source"]).name
        winner.write_bytes(source_bytes(template.render(template.vector(best["seed"]))))
    print(json.dumps(summary(template, end, best, counts, winner)))


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
    x = s.add_parser("check"); x.add_argument("id"); x.set_defaults(f=cmd_check)
    x = s.add_parser("verify"); x.add_argument("id"); x.add_argument("--model", required=True)
    x.add_argument("--category"); x.add_argument("--branch"); x.set_defaults(f=cmd_verify)
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
