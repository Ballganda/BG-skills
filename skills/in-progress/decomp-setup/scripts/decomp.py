#!/usr/bin/env python3
"""Project tool for byte-for-byte decompilation.

Copied into a decomp project's tools/ by decomp-setup and frozen at the
decomp-setup tag. It is the only writer of ticket statuses and ledger records.
Standard library only. Run from the project root: python tools/decomp.py <cmd>.
"""
import argparse
import hashlib
import json
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


# ---------- environment ----------

ENV_EXIT = 6  # the machine's target or toolchain differs from toolchain.json
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


def tool_failure(t, env):
    """Why tool t is not the one toolchain.json pins, or None when it is."""
    missing = [f for f in t.get("files", []) if not (Path(t["root"]) / f).exists()]
    if missing:
        return f"{t['name']}: missing under {t['root']}: {missing}"
    out = version_output(tool_command(t["banner_cmd"], root=t["root"]), env)
    if t["banner"] not in out:
        return f"{t['name']}: banner lacks '{t['banner']}'; the command printed: {out.strip()[:300]}"
    return None


def environment_stamp(tc):
    """Changes whenever toolchain.json, the target, or a required file does."""
    tgt = tc["target"]
    watched = ([Path(tgt["path"])] if tgt["path"] else []) + [
        Path(t["root"]) / f for t in tc["tools"] for f in t.get("files", [])]
    stamp = [sha((ROOT / "toolchain.json").read_bytes()), tgt["path"]]
    for p in watched:
        try:
            st = p.stat()
            stamp.append(f"{p}:{st.st_size}:{st.st_mtime_ns}")
        except OSError:
            stamp.append(f"{p}:missing")
    return sha("\n".join(stamp).encode())


def doctor(full=True, need=None):
    """Stop unless the target, host prerequisites, and tools equal toolchain.json. Returns the report lines.

    need names the tools that must pass (None: all of them). A tool outside need that fails
    is reported and left in toolchain()["unusable"], so only the units built with it stop.
    Leaves the recognised edition in toolchain()["target"]["edition"].

    full=False trusts the last check that passed in full while toolchain.json, the target,
    and every required file keep the same size and modification time.
    """
    tc = toolchain()
    loc = local_dir()
    tgt = tc["target"]
    tc["unusable"] = {}
    stamp = environment_stamp(tc)
    cache = loc / "doctor.json"
    if not full and cache.exists():
        last = json.loads(cache.read_text(encoding="utf-8"))
        edition = edition_named(last.get("edition"))
        if last.get("ok") == stamp and edition:
            tgt["edition"] = edition
            return []
    bad, lines = [], []
    if not tgt["path"]:
        bad.append('target: no path; set "target" in .decomp/local.json or DECOMP_TARGET')
    elif not Path(tgt["path"]).is_file():
        bad.append(f"target: {tgt['path']} not found")
    else:
        tgt["edition"], line = recognise(tgt)
        (lines if tgt["edition"] else bad).append(line)
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
                tc["unusable"][t["name"]] = why
                lines.append(f"not usable here: {why}")
    if bad:
        cache.unlink(missing_ok=True)
        for b in bad:
            print(f"ENVIRONMENT: {b}", file=sys.stderr)
        die("this machine does not match toolchain.json; nothing was built or recorded. "
            "Fix it with `decomp.py provision` or the user's own install, never by editing toolchain.json.", ENV_EXIT)
    if tc["unusable"]:
        cache.unlink(missing_ok=True)
    else:
        loc.mkdir(parents=True, exist_ok=True)
        cache.write_text(json.dumps({"ok": stamp, "unix": now(), "edition": tgt["edition"]["name"]}), encoding="utf-8")
    return lines


def edition_differs(t):
    """True when the recognised edition holds ticket t's function differently. Needs doctor first."""
    held = toolchain()["target"]["edition"].get("differs", [])
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


def tools_needed(units):
    """Every tool but the compilers that build none of these units."""
    every = {CFG.get("compiler", "")} | set(CFG.get("unit_compilers", {}).values())
    return {t["name"] for t in toolchain()["tools"]} - (every - {compiler_for(u) for u in units})


def stop_if_edition_differs(t):
    """After doctor: stop with the environment exit when this machine's edition cannot judge ticket t."""
    if edition_differs(t):
        e = toolchain()["target"]["edition"]
        print(f"ENVIRONMENT: edition '{e['name']}' holds {t['id']} ({t['address']}) differently from the "
              "contract's expected bytes", file=sys.stderr)
        die("nothing was built or recorded; this function is matched only on an edition that holds it unchanged.",
            ENV_EXIT)


def cmd_doctor(a):
    for line in doctor(full=True):
        print(line)
    print("doctor: ok")


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

def ticket_path(tid):
    unit = tid.split("-")[0]
    return ROOT / "tickets" / unit / f"{tid}.md"


def read_ticket(tid):
    p = ticket_path(tid)
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


def all_tickets():
    out = []
    for p in sorted((ROOT / "tickets").glob("*/*.md")):
        out.append(read_ticket(p.stem)[0])
    return out


def set_status(tid, status, **extra):
    assert status in STATUSES
    fields, body = read_ticket(tid)
    fields["status"] = status
    fields.update(extra)
    write_ticket(fields, body)


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


def records(name):
    p = ROOT / "ledger" / name
    if not p.exists():
        return []
    return [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]


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


def fill(template, t, obj, report, tree):
    return expand(
        template, id=t["id"], unit=t["unit"], source=t["source"], expected=t["expected"],
        address=t["address"], obj=obj, report=report,
        symbols=Path(tree) / SYMBOLS, compiler=compiler_for(t["unit"]),
        tools=Path(tree) / "tools", python=sys.executable,
    )


def adapter(template, t, obj, report, tree, env):
    """Run one adapter command. A tool's output is in the tool's encoding, never assumed to be this system's."""
    return subprocess.run(fill(template, t, obj, report, tree), shell=True, cwd=tree, env=env,
                          capture_output=True, text=True, errors="replace")


def marker_count(text, tid):
    """How often the ticket's marker stands in a source: `// @decomp <id>` or `/* @decomp <id> */`."""
    return len(re.findall(r"(?://|/\*)[ \t]*@decomp " + re.escape(tid) + r"(?![\w.-])", text))


def build_and_diff(t, tree, report):
    """Build t's unit in tree and compare. Returns (result, differ_bytes, log)."""
    src = Path(tree) / t["source"]
    if not src.exists():
        return "build-fail", None, f"missing {t['source']}"
    text = src.read_text(encoding="utf-8", errors="replace")
    marks = marker_count(text, t["id"])
    if marks != 1:
        return "guardrail", None, f"expected one '@decomp {t['id']}' marker comment, found {marks}"
    bad = scan(text)
    for inc in sorted(includes(text)):  # project headers obey the same guardrails
        h = Path(tree) / "include" / inc
        if h.is_file():
            bad += [f"{inc}: {v}" for v in scan(h.read_text(encoding="utf-8", errors="replace"))]
    if bad:
        return "guardrail", None, "\n".join(bad)
    obj = str(Path(tempfile.mkdtemp(prefix="decomp-obj-")) / f"{t['unit']}.obj")
    env = tool_env()
    b = adapter(CFG["build"], t, obj, report, tree, env)
    if b.returncode != 0:
        return "build-fail", None, (b.stderr or b.stdout)[-4000:]
    d = adapter(CFG["diff"], t, obj, report, tree, env)
    try:
        out = json.loads(d.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        return "build-fail", None, f"diff adapter gave no JSON: {d.stderr[-2000:]}"
    if out.get("match") is True and out.get("differ_bytes", 0) == 0:
        return "bytes-match", 0, ""
    return "differ", int(out.get("differ_bytes", -1)), ""


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
    inv = json.loads((ROOT / "inventory.json").read_text(encoding="utf-8"))
    for f, key in zip(inv["functions"], function_keys(inv["functions"])):
        f["key"] = key
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
            lines.append(f"| {u['id']}-{f['key']} | {f['size']} | {tier(f['size'])} |")
        if out:
            lines += ["", "## Excluded", "", "| Address | Size | Scope | Evidence |", "| --- | --- | --- | --- |"]
            for f in out:
                lines.append(f"| {f['address']} | {f['size']} | {f['scope']} | {f.get('evidence', '')} |")
        p = ROOT / "units" / f"{u['id']}.md"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    print(f"wrote {len(inv['units'])} unit specs")


def cmd_gen_tickets(a):
    inv = json.loads((ROOT / "inventory.json").read_text(encoding="utf-8"))
    units = {u["id"]: u for u in inv["units"]}
    made = kept = 0
    for f, key in zip(inv["functions"], function_keys(inv["functions"])):
        if f["scope"] != "in":
            continue
        tid = f"{f['unit']}-{key}"
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
    ts = [t for t in all_tickets()]
    busy = {t["unit"] for t in ts if t["status"] in ("claimed", "bytes-match", "matched")}
    started = {t["unit"] for t in ts if t["status"] in MATCHED}
    ready = [t for t in ts if t["status"] in ("open", "regressed") and t["unit"] not in busy]
    order = {"TINY": 0, "SMALL": 1, "MEDIUM": 2, "LARGE": 3}
    ready.sort(key=lambda t: (t["unit"] not in started, order[t["tier"]], address_order(t["address"])))
    picked, units = [], set()
    for t in ready:  # one ticket per unit: units are one writer at a time
        if t["unit"] not in units:
            picked.append(t)
            units.add(t["unit"])
    if picked and not any(t["tier"] in ("MEDIUM", "LARGE") for t in picked[: a.n]):
        big = next((t for t in picked if t["tier"] in ("MEDIUM", "LARGE")), None)
        if big:  # keep one large slot so remaining bytes keep falling
            picked.remove(big)
            picked.insert(min(a.n - 1, len(picked)), big)
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
    t, _ = read_ticket(a.id)
    if t["status"] not in ("open", "regressed"):
        die(f"{a.id} is {t['status']}, not open")
    take_lock(f"unit-{t['unit']}", a.by)
    set_status(a.id, "claimed", claimed_by=a.by, claimed_at=str(now()))
    print(f"claimed {a.id}")


def cmd_release(a):
    t, _ = read_ticket(a.id)
    if a.to not in ("open", "blocked-reference"):
        die("release --to open|blocked-reference")
    if t["status"] == "claimed":
        set_status(a.id, a.to, claimed_by="", claimed_at="")
        lockfile(f"unit-{t['unit']}").unlink(missing_ok=True)
    elif a.to == "open" and t["status"] == "blocked-reference":
        set_status(a.id, "open")
    else:
        die(f"{a.id} is {t['status']}; nothing to release")
    print(f"{a.id} -> {read_ticket(a.id)[0]['status']}")


def cmd_check(a):
    t, _ = read_ticket(a.id)
    doctor(full=False, need=tools_needed([t["unit"]]))
    stop_if_edition_differs(t)
    report = str(Path(tempfile.mkdtemp(prefix="decomp-rep-")) / "diff.txt")
    result, n, log = build_and_diff(t, os.getcwd(), report)
    print(json.dumps({"result": result, "differ_bytes": n, "report": report}))
    if log:
        print(log)


def cmd_verify(a):
    frozen_check()
    t, _ = read_ticket(a.id)
    doctor(need=tools_needed([t["unit"]]))
    if t["status"] != "claimed":
        die(f"{a.id} is {t['status']}; verify needs a claimed ticket")
    if a.category and a.category not in CATEGORIES:
        die(f"unknown category {a.category}")
    stop_if_edition_differs(t)
    integ, branch = CFG["integration_branch"], a.branch or f"w/{a.id}"
    changed = git("diff", "--name-only", f"{integ}...{branch}").split()
    stamp = now()
    aid = f"{a.id}-a{1 + sum(r['ticket'] == a.id for r in records('attempts.jsonl')):03d}"
    evidence = ledger(f"evidence/{aid}.txt")
    rec = {"id": aid, "ticket": a.id, "unix": stamp, "model": a.model, "tier": t["tier"],
           "category": a.category or "", "differ_bytes": None, "evidence": evidence.relative_to(ROOT).as_posix()}
    outside = [p for p in changed if p != t["source"]]
    if outside:
        result, n, log = "guardrail", None, f"branch touches guarded paths: {outside}"
        src = b""
    else:
        src = git_bytes("show", f"{branch}:{t['source']}")
        with Worktree(integ) as tree:
            dest = Path(tree) / t["source"]
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(src)
            result, n, log = build_and_diff(t, tree, str(evidence))
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
        set_status(a.id, "bytes-match")
    print(json.dumps({"attempt": aid, "result": result, "differ_bytes": n}))
    sys.exit(0 if result == "bytes-match" else 4)


def cmd_audit(a):
    t, _ = read_ticket(a.id)
    if t["status"] != "bytes-match":
        die(f"{a.id} is {t['status']}; audit needs bytes-match")
    last = [r for r in records("attempts.jsonl") if r["ticket"] == a.id][-1]
    branch = a.branch or f"w/{a.id}"
    if a.verdict == "pass" and sha(git_bytes("show", f"{branch}:{t['source']}")) != last["source_sha256"]:
        die("branch changed since verify; record a fail, then verify again", 2)
    if a.verdict == "pass":
        if not any(m["ticket"] == a.id for m in records("matches.jsonl")):
            append("matches.jsonl", {"ticket": a.id, "unix": now(), "attempt": last["id"],
                                     "model": last["model"], "size": t["size"], "auditor": a.auditor})
        set_status(a.id, "matched")
        print(f"matched {a.id} (attempt {last['id']})")
    else:
        n = 1 + sum(r["ticket"] == a.id for r in records("attempts.jsonl"))
        append("attempts.jsonl", dict(last, id=f"{a.id}-a{n:03d}", unix=now(), result="audit-fail",
                                      category="unknown", auditor=a.auditor))
        set_status(a.id, "claimed")
        append_note(a.id, f"audit-fail: {a.note or 'see auditor'}")
        print(f"audit failed {a.id}; ticket back to claimed")


def cmd_integrate(a):
    t, _ = read_ticket(a.id)
    if t["status"] != "matched":
        die(f"{a.id} is {t['status']}; integrate needs matched")
    branch = a.branch or f"w/{a.id}"
    r = subprocess.run(["git", "merge-base", "--is-ancestor", branch, CFG["integration_branch"]], cwd=ROOT)
    if r.returncode != 0:
        die(f"{branch} is not merged into {CFG['integration_branch']}")
    set_status(a.id, "integrated", claimed_by="", claimed_at="")
    lockfile(f"unit-{t['unit']}").unlink(missing_ok=True)
    append("events.jsonl", {"unix": now(), "ticket": a.id, "event": "integrated"})
    print(f"integrated {a.id}")


def includes(text):
    return set(re.findall(r'#\s*include\s*[<"]([^>"]+)[>"]', text))


def cmd_revalidate(a):
    frozen_check()
    ts = [t for t in all_tickets() if t["status"] in MATCHED | {"regressed"}]
    built_with = {t["unit"]: compiler_for(t["unit"]) for t in ts}  # stops here, before any status is written
    doctor(need=tools_needed([]) | {CFG.get("compiler", "")})
    unusable = toolchain()["unusable"]
    ref = a.ref or CFG["integration_branch"]
    on_integ = ref == CFG["integration_branch"]
    if not on_integ:
        outside = [p for p in git("diff", "--name-only", f"{CFG['integration_branch']}...{ref}").split()
                   if not p.startswith("include/") and p != SYMBOLS]
        if outside:
            append("events.jsonl", {"unix": now(), "ref": ref, "event": "rejected-repair"})
            die(f"{ref} touches paths outside include/ and {SYMBOLS}: {outside}", 5)
    bad = skipped = measured = 0
    with Worktree(ref) as tree:
        if a.header:
            name = Path(a.header).name
            ts = [t for t in ts if (Path(tree) / t["source"]).exists() and any(
                Path(i).name == name for i in includes((Path(tree) / t["source"]).read_text(errors="replace")))]
        for t in ts:
            why = ("this machine's edition holds it differently" if edition_differs(t) else
                   f"its compiler '{built_with[t['unit']]}' is not usable here" if built_with[t["unit"]] in unusable
                   else "")
            if why:  # its bytes cannot be measured on this machine, either way
                skipped += 1
                print(f"SKIPPED {t['id']}: {why}")
                continue
            measured += 1
            report = str(Path(tempfile.mkdtemp(prefix="decomp-rep-")) / "diff.txt")
            result, n, _ = build_and_diff(t, tree, report)
            ok = result == "bytes-match"
            if not ok:
                bad += 1
                print(f"REGRESSED {t['id']} on {ref}: {result} {n}")
            if on_integ:
                if ok and t["status"] in ("integrated", "regressed"):
                    set_status(t["id"], "revalidated")
                    append("events.jsonl", {"unix": now(), "ticket": t["id"], "event": "revalidated"})
                elif not ok:
                    set_status(t["id"], "regressed")
                    append("events.jsonl", {"unix": now(), "ticket": t["id"], "event": "regressed"})
    if bad and not on_integ:
        append("events.jsonl", {"unix": now(), "ref": ref, "event": "rejected-repair"})
    print(f"revalidated {measured} on {ref}: {bad} regressed, {skipped} skipped")
    if bad:
        sys.exit(5)
    if skipped and not on_integ:  # a repair is accepted only where every match it could break was rebuilt
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


def cmd_report(a):
    ts = all_tickets()
    atts = records("attempts.jsonl")
    matches = records("matches.jsonl")
    inv = json.loads((ROOT / "inventory.json").read_text(encoding="utf-8"))
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
    excl = {}
    for f in inv["functions"]:
        if f["scope"] != "in":
            excl[f["scope"]] = excl.get(f["scope"], 0) + 1
    print("excluded:  " + (", ".join(f"{k} {v}" for k, v in sorted(excl.items())) or "none"))
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


def main():
    global ROOT, CFG
    top = subprocess.run(["git", "rev-parse", "--show-toplevel"], capture_output=True, text=True)
    if top.returncode != 0:
        die("run inside the decomp project repo")
    ROOT = Path(top.stdout.strip())
    p = argparse.ArgumentParser(prog="decomp.py")
    s = p.add_subparsers(dest="cmd", required=True)
    s.add_parser("doctor").set_defaults(f=cmd_doctor)
    x = s.add_parser("provision"); x.add_argument("--tool"); x.add_argument("--force", action="store_true")
    x.set_defaults(f=cmd_provision)
    s.add_parser("gen-specs").set_defaults(f=cmd_gen_specs)
    s.add_parser("gen-tickets").set_defaults(f=cmd_gen_tickets)
    x = s.add_parser("next"); x.add_argument("--n", type=int, default=3); x.set_defaults(f=cmd_next)
    x = s.add_parser("claim"); x.add_argument("id"); x.add_argument("--by", required=True); x.set_defaults(f=cmd_claim)
    x = s.add_parser("release"); x.add_argument("id"); x.add_argument("--to", default="open"); x.set_defaults(f=cmd_release)
    x = s.add_parser("check"); x.add_argument("id"); x.set_defaults(f=cmd_check)
    x = s.add_parser("verify"); x.add_argument("id"); x.add_argument("--model", required=True)
    x.add_argument("--category"); x.add_argument("--branch"); x.set_defaults(f=cmd_verify)
    x = s.add_parser("audit"); x.add_argument("id"); x.add_argument("verdict", choices=["pass", "fail"])
    x.add_argument("--auditor", required=True); x.add_argument("--note"); x.add_argument("--branch"); x.set_defaults(f=cmd_audit)
    x = s.add_parser("integrate"); x.add_argument("id"); x.add_argument("--branch"); x.set_defaults(f=cmd_integrate)
    x = s.add_parser("revalidate"); x.add_argument("--ref"); x.add_argument("--header"); x.set_defaults(f=cmd_revalidate)
    x = s.add_parser("note"); x.add_argument("id"); x.add_argument("text", nargs="+"); x.set_defaults(f=cmd_note)
    x = s.add_parser("similar"); x.add_argument("id"); x.add_argument("--n", type=int, default=3); x.set_defaults(f=cmd_similar)
    x = s.add_parser("lock"); x.add_argument("name"); x.add_argument("--by", required=True); x.set_defaults(f=cmd_lock)
    x = s.add_parser("unlock"); x.add_argument("name"); x.set_defaults(f=cmd_unlock)
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
