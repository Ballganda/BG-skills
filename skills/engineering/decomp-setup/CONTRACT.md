# DECOMP.md template

Copy into the project as `DECOMP.md` and fill every section. A section with nothing to say states why. Each value names its source: `IDENTIFY.md`, an ADR, or the user.

The contract records nothing about the current state of this machine (what is installed, logged in, or missing). Facts about the machine come from `doctor` and the tool at run time: the contract is frozen by the `decomp-setup` tag, so such a note goes stale and cannot be corrected without a contract change.

Each heading carries one tag. `[needs IDENTIFY]` means its answers depend on the compiler, so they wait for `IDENTIFY.md`. `[independent]` means the user can decide them before identify finishes.

```markdown
# Decomp contract: <target name>

## Target [independent]
- Accepted editions (mirrored in `toolchain.json`). Per edition: its name, its SHA-256 and size or the number of probes it must match, and how it was told apart from the others. The target's path is per machine, in `.decomp/local.json`.
- Probes: each file offset and length, and why that range was chosen.
- Per accepted edition, the functions it holds differently (`differs`), each address with its evidence. None: say so.
- Known-wrong editions: name, SHA-256, and the message `doctor` prints, saying what the user should do.
- Format and architecture. When the product ships its code compressed or encrypted: that the target is the unpacked image, and how the user produces it.
- How a function is named: by address alone, or by a key, when overlays, modules, or banks share addresses.
- Other modules in the same product, and whether each is in this project.

## Toolchain [needs IDENTIFY]
- Compiler: exact product and version, with its version banner.
- Linker: exact version, with its banner.
- SDK and platform headers: exact version, with the evidence that the original was built against them (a version macro, a header banner, or the product's documentation).
- Global flags: compiler and linker, each with its evidence.
- Default compiler: its tool name in `toolchain.json` (mirrored in `decomp.json`).
- Per-unit compilers and flags: only where evidence shows the original used them, each unit with its evidence (compilers mirrored in `decomp.json`).
- Pragma allowlist and attribute allowlist (regexes, mirrored in `decomp.json`), each entry with the evidence that the original used it.
- Function order within a unit: address order, or the order this compiler emits (deferred inlining, one section per function, hot and cold splitting), with its evidence.
- Provisioning, per tool (mirrored in `toolchain.json`): installed by the agent or the user, the source URL, size, SHA-256, and where the hash comes from.
- Host: the operating systems the tools run on, and each host prerequisite (an archive tool, a compatibility layer) with its version command, the string it must print, and the hosts it applies to (mirrored in `toolchain.json`). The user installs these.
- Wrapper: the one script in `tools/` every tool invocation goes through, and what it sets.
- `doctor` output from this machine, with the Unix time.

## Scope [needs IDENTIFY]
- In scope: which code counts.
- First-party static libraries with public reference source: in scope, or excluded as `library`, with the evidence that the library is first-party and its source is public.
- Excluded: runtime library, compiler-generated code, `asm-origin`, anything else, each rule with the evidence that identifies it.
- The denominator: in-scope bytes and functions as `inventory` counts them.

## Matching [needs IDENTIFY]
- Diff adapter and the tool under it.
- Link adapter and the linker flags under it, or the link marked unavailable: the reason (the format or linker cannot place raw blocks at fixed positions, or cannot reproduce the headers), the evidence for it, and that `decomp.json`'s `link_unavailable` holds the reason. There is no patched-original fallback.
- Relocation policy: the default in `decomp-standards`' layout, or a named departure with its ADR.
- Symbol map: what `inventory` seeds it with for this format, and the relocation types the `diff` adapter resolves.
- Marker comment form: `// @decomp <id>`, or `/* @decomp <id> */` where the language has no line comment.
- Fakematch rule: `forbidden`, or `allowed with a fakematch: comment` (ADR).
- Permuter: allowed or not, and if allowed, its output is fakematch-governed.

## Models [independent]
| Tier | Writer model | Attempt budget |
| --- | --- | --- |
| TINY | | |
| SMALL | | |
| MEDIUM | | |
| LARGE | | |
- Escalation: after how many attempts with no fall in `differ_bytes` a ticket moves to the next tier's model.
- Auditor model.
- Concurrent writers (default 3).

## Tracking [independent]
- Integration branch.
- GitHub mirror: off, or the private repo.
- Full revalidation: after every how many integrations.
- Link milestone: a percentage or a byte count of in-scope bytes (default 5%, floor 16 KB), recorded as `link_milestone` in `decomp.json`.

## Pipeline check [needs IDENTIFY]
- The link from raw blocks alone, with no source unit, reproduces the original's hash (or the link is marked unavailable above).
- Each check, the command, its result, and the Unix time it passed.
```
