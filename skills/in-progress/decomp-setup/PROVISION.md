# Provisioning the toolchain

The contract names exact tools. Provisioning puts those tools on this machine, records where each came from, and gives `decomp.py doctor` what it needs to refuse a machine that differs. The record is what lets a second machine, or the same one a year later, rebuild the same environment.

## Two files

**`toolchain.json`** is committed and frozen by the `decomp-setup` tag. It holds requirements, never a machine path:

```json
{
  "target": {"sha256": "<hash>", "size": 15038976},
  "host": "Windows runs the tools natively; Linux and macOS need Wine 8 or later",
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
      "unpack": ["<command using {archive} and {root}>"],
      "files": ["VC/bin/cl.exe", "SDK/Include/windows.h"],
      "banner_cmd": "\"{root}/VC/bin/cl.exe\"",
      "banner": "<exact version string the tool prints>"
    }
  ]
}
```

- `name` is how adapters find the tool: `decomp.py` exports each tool's folder as `DECOMP_TOOL_<NAME>` and the target's path as `DECOMP_TARGET`. Adapters and `banner_cmd` use those and `{root}`, never an absolute path.
- `files` lists everything a build needs that an incomplete install tends to lack (the compiler binary, the platform headers the sources include).
- `banner` is a literal substring of what `banner_cmd` prints, on stdout or stderr. It carries the full version, so a neighbouring build cannot pass.
- A tool the user installs has `"installed_by": "user"` and no `source` or `unpack`.

**`.decomp/local.json`** is this machine's half, and is never committed:

```json
{"target": "<absolute path to the target>", "roots": {"<tool name>": "<folder of a user-installed tool>"}}
```

A tool with no entry in `roots` lives in `.decomp/toolchain/<name>/`, where `provision` unpacks it.

## Steps

1. **List.** From `IDENTIFY.md`'s Toolchain requirements, list every tool the contract and the four adapters need, with its status on this machine (installed with a matching banner, installed with a different one, missing).
2. **Find sources.** For each tool that is not installed, call the Skill tool with `research` to find the vendor's official download: the URL, the size, and a published hash when one exists. A mirror, an archive site, or a repack is not a source: when the vendor no longer offers the tool, say so, and that tool is the user's to supply.
3. **Ask.** Show the user one table: tool, exact version, source URL, size, and what unpacking does. Ask who installs each tool:
   - **The agent**: you download and unpack it, after the user approves this list. The approval covers these files from these URLs and nothing else.
   - **The user**: they install it their own way and give you the folder, which goes in `.decomp/local.json`.

   Prefer unpacking to installing: extract only the files the build needs into `.decomp/toolchain/<name>/`, so nothing touches the system, no installer runs, and removing the folder undoes it. If a tool only works installed, it is the user's to install.
4. **Write** `toolchain.json` and `.decomp/local.json`, and copy [scripts/decomp.py](scripts/decomp.py) into `tools/` if it is not there yet.
5. **Provision.** Run `python tools/decomp.py provision`. It downloads over HTTPS, compares size and SHA-256 before unpacking anything, and stops on a difference. When the vendor publishes no hash, leave `sha256` empty for the first run: `provision` prints the download's size and hash and unpacks nothing. Record them with `hash_from` as `first download on <Unix time>`, tell the user that this hash pins the file but does not vouch for it, and run again.
6. **Prove.** Run `python tools/decomp.py doctor`. It passes only when the target's size and hash, every listed file, and every banner equal `toolchain.json`. Paste its output into `DECOMP.md`.
7. **Probe.** With the toolchain present, run the probes `IDENTIFY.md` listed for this candidate and record each result there. A probe that kills the candidate sends you back to step 1 with the next one: remove the dead candidate's folder and its `toolchain.json` entry.

## The wrong target

When `doctor` reports a target whose hash differs from the contract's, stop and show the user what it printed. A different edition or patch level is a different binary, and no match against it counts. Obtaining or converting the right file is the user's decision and the user's action.

## Never

- Download anything the user has not approved in step 3, or from a URL that is not in `toolchain.json`.
- Edit `toolchain.json` to make `doctor` pass. The machine changes to fit the contract, or the contract changes through the user and an ADR.
- Commit anything under `.decomp/`: tools, downloads, and the target stay on the machine.
