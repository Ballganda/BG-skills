# Provisioning the toolchain

The contract names exact tools. Provisioning puts those tools on this machine, records where each came from, and gives `decomp.py doctor` what it needs to refuse a machine that differs. The record is what lets a second machine, or the same one a year later, rebuild the same environment.

## Two files

**`toolchain.json`** is committed and frozen by the `decomp-setup` tag. It holds requirements, never a machine path:

```json
{
  "target": {
    "editions": [
      {"name": "retail 1.0", "sha256": "<whole file>", "size": 15038976},
      {"name": "store re-release", "probes_needed": 12, "differs": ["0x00401000"]}
    ],
    "probes": [{"offset": 4096, "size": 93, "sha256": "<hash of that range>"}],
    "known_wrong": [{"name": "2021 update", "sha256": "<whole file>", "message": "<what the user should do>"}]
  },
  "host": "Windows runs the tools natively; Linux and macOS need Wine 8 or later",
  "prerequisites": [
    {"name": "7z", "version_cmd": "7z", "version": "7-Zip 23.01"},
    {"name": "wine", "version_cmd": "wine --version", "version": "wine-8", "hosts": ["linux", "darwin"]}
  ],
  "tools": [
    {
      "name": "compiler",
      "product": "<exact product and version>",
      "installed_by": "agent",
      "source": {
        "url": "https://<vendor's official host>/<file>",
        "size": 1237436416,
        "sha256": "<hash>",
        "hash_from": "vendor page <url> | first download on <Unix time>"
      },
      "unpack": ["<command using {archive}, {root}, and {tools}>"],
      "files": ["VC/bin/cl.exe", "SDK/Include/windows.h"],
      "banner_cmd": "\"{root}/VC/bin/cl.exe\"",
      "banner": "<exact version string the tool prints>"
    }
  ]
}
```

- `target` with only `sha256` and `size` is one accepted edition. See [Editions](#editions) for the full form.
- `prerequisites` are what the host must already have: an archive tool, a compatibility layer. `doctor` runs each `version_cmd` before it looks at any tool, and stops at the first whose output lacks `version`, naming it. `provision` never downloads one: the user installs it.
- `name` is how adapters find the tool: `decomp.py` exports each tool's folder as `DECOMP_TOOL_<NAME>` and the target's path as `DECOMP_TARGET`. Adapters and `banner_cmd` use those and `{root}`, never an absolute path.
- `files` lists everything a build needs that an incomplete install tends to lack (the compiler binary, the platform headers the sources include).
- `banner` is a literal substring of what `banner_cmd` prints, on stdout or stderr. It carries the full version, so a neighbouring build cannot pass.
- `unpack` steps run in the downloads folder. `{tools}` is the project's `tools/` folder, so a step can run a script the project ships (see [Unpack scripts](#unpack-scripts)). `{python}` is the interpreter running `decomp.py`: write it, never a bare `python`, in every command the manifest or `decomp.json` holds, because some systems have only `python3`.
- `hosts` limits a prerequisite or a tool entry to the systems whose `sys.platform` starts with one of its values (`win32`, `linux`, `darwin`). Without it the entry applies everywhere. A tool that needs another archive, other files, or another banner per system gets one entry per host under the same `name`.
- A tool the user installs has `"installed_by": "user"` and no `source` or `unpack`.
- A unit built with another compiler build than the rest gets that build as its own tool entry. `decomp.json` names the default in `compiler` and maps the unit in `unit_compilers`.

**`.decomp/local.json`** is this machine's half, and is never committed:

```json
{"target": "<absolute path to the target>", "roots": {"<tool name>": "<folder of a user-installed tool>"}}
```

A tool with no entry in `roots` lives in `.decomp/toolchain/<name>/`, where `provision` unpacks it.

## Steps

1. **List.** From `IDENTIFY.md`'s Toolchain requirements, list every host prerequisite and every tool the contract and the four adapters need, with its status on this machine (installed with a matching banner, installed with a different one, missing).
2. **Find sources.** For each tool that is not installed, call the Skill tool with `research` to find the vendor's official download: the URL, the size, and a published hash when one exists. A mirror, an archive site, or a repack is not a source: when the vendor no longer offers the tool, say so, and that tool is the user's to supply.
3. **Ask.** Show the user one table: tool, exact version, source URL, size, and what unpacking does. Ask who installs each tool:
   - **The agent**: you download and unpack it, after the user approves this list. The approval covers these files from these URLs and nothing else.
   - **The user**: they install it their own way and give you the folder, which goes in `.decomp/local.json`.

   Prefer unpacking to installing: extract only the files the build needs into `.decomp/toolchain/<name>/`, so nothing touches the system, no installer runs, and removing the folder undoes it. If a tool only works installed, it is the user's to install.
4. **Write** `toolchain.json` and `.decomp/local.json`, copy [scripts/decomp.py](scripts/decomp.py) into `tools/` if it is not there yet, and write the [wrapper](#the-wrapper) and any [unpack scripts](#unpack-scripts).
5. **Provision.** Run `python tools/decomp.py provision`. It checks the host prerequisites, downloads over HTTPS, compares size and SHA-256 before unpacking anything, and stops on a difference. A file already in `.decomp/downloads/` (one the user supplied, or an earlier download) is compared as it is, and downloaded again only with `--force`. When the vendor publishes no hash, leave `sha256` empty for the first run: `provision` prints the download's size and hash and unpacks nothing. Record them with `hash_from` as `first download on <Unix time>`, tell the user that this hash pins the file but does not vouch for it, and run again.
6. **Prove.** Run `python tools/decomp.py doctor`. It passes only when the target is an accepted edition and every prerequisite, listed file, and banner equals `toolchain.json`. Paste its output into `DECOMP.md`.
7. **Probe.** With the toolchain present, run the probes `IDENTIFY.md` listed for this candidate and record each result there. A probe that kills the candidate sends you back to step 1 with the next one: remove the dead candidate's folder and its `toolchain.json` entry.

## Unpack scripts

An old compiler often sits inside an installer image that no one-line command opens. Write a script in `tools/` that extracts exactly the files the build needs, and call it from `unpack`: `"{python}" "{tools}/unpack_compiler.py" "{archive}" "{root}"`.

- It uses only the standard library and the declared host prerequisites.
- It is frozen with the rest of `tools/` by the `decomp-setup` tag.
- It runs no installer and writes nowhere but `{root}`.

## The wrapper

Write one wrapper in `tools/` (`tools/run_tool.py`). The adapters and every `banner_cmd` invoke a tool through it, never directly: `"{python}" "{tools}/run_tool.py" compiler <the tool's arguments>`.

- It owns the environment: include and library paths, built from `DECOMP_TOOL_<NAME>`.
- It owns path conversion between the host and what the tool expects.
- It owns the compatibility layer, when the host needs one.
- It collects the tool's output through a file, not a pipe, then prints it. A compatibility layer's background services can hold an inherited pipe open and hang the caller.

One frozen place for all of this means every build, banner, and probe runs the tool the same way.

## Editions

Two editions of a product often carry the same code and differ only outside it (a loader section, a signature, a handful of patched functions). The contract can accept more than one:

- **Whole-file edition**: `name`, `sha256`, `size`. The edition `expected/` was cut from is always one of these.
- **Probe edition**: `name`, `probes_needed`, and `differs`. It is accepted when at least `probes_needed` of the `probes` match.
- **Probes**: file offsets and lengths with the SHA-256 of each range, chosen inside the code the editions share. Compute them from the reference edition. They hold hashes only, never target bytes. A product that ships its code compressed or encrypted has no stable offsets: make the unpacked image the contract's target, and record in `DECOMP.md` how the user produces it.
- **`differs`**: every function the edition holds differently, by address (or by key, where one address names more than one function), each proven by comparing the two editions. `check` and `verify` exit 6 on those tickets on that edition, so no match is measured against the wrong bytes.
- **Known-wrong edition**: `name`, `sha256`, and a `message` telling the user what to do.

Adding an edition is a contract change: an ADR, the user's go-ahead, a tag move, then `revalidate`.

## The wrong target

`doctor` names a known-wrong edition and prints the contract's message for it. For a file it does not recognise, it prints how many probes matched: most of them means a near edition worth the user's attention, none means an unrelated file. Either way, stop and show the user what it printed. No match against an unaccepted file counts. Obtaining or converting the right file is the user's decision and the user's action.

## Never

- Download anything the user has not approved in step 3, or from a URL that is not in `toolchain.json`.
- Install a host prerequisite. Name it, give its version, and leave the install to the user.
- Edit `toolchain.json` to make `doctor` pass. The machine changes to fit the contract, or the contract changes through the user and an ADR.
- Commit anything under `.decomp/`: tools, downloads, and the target stay on the machine.
