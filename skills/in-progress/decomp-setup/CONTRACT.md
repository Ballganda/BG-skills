# DECOMP.md template

Copy into the project as `DECOMP.md` and fill every section. A section with nothing to say states why. Each value names its source: `IDENTIFY.md`, an ADR, or the user.

```markdown
# Decomp contract: <target name>

## Target
- SHA-256 and size (mirrored in `toolchain.json`). Its path is per machine, in `.decomp/local.json`.
- Edition or patch level, and which other editions are known not to match.
- Format and architecture.
- Other modules in the same product, and whether each is in this project.

## Toolchain
- Compiler: exact product and version, with its version banner.
- Linker: exact version, with its banner.
- Global flags: compiler and linker, each with its evidence.
- Per-unit flags: only where evidence shows the original used them.
- Pragma and attribute allowlist (regexes, mirrored in `decomp.json`).
- Provisioning, per tool (mirrored in `toolchain.json`): installed by the agent or the user, the source URL, size, SHA-256, and where the hash comes from.
- Host: the operating systems the tools run on, and what each needs (a compatibility layer and its version).
- `doctor` output from this machine, with the Unix time.

## Scope
- In scope: which code counts.
- Excluded: runtime library, compiler-generated code, `asm-origin`, anything else, each rule with the evidence that identifies it.
- The denominator: in-scope bytes and functions as `inventory` counts them.

## Matching
- Diff adapter and the tool under it.
- Relocation policy: how an operand that the linker fills in compares (ADR).
- Fakematch rule: `forbidden`, or `allowed with a // fakematch: comment` (ADR).
- Permuter: allowed or not, and if allowed, its output is fakematch-governed.

## Models
| Tier | Writer model | Attempt budget |
| --- | --- | --- |
| TINY | | |
| SMALL | | |
| MEDIUM | | |
| LARGE | | |
- Escalation: after how many attempts with no fall in `differ_bytes` a ticket moves to the next tier's model.
- Auditor model.
- Concurrent writers (default 3).

## Tracking
- Integration branch.
- GitHub mirror: off, or the private repo.
- Full revalidation: after every how many integrations.

## Pipeline check
- Each check, the command, its result, and the Unix time it passed.
```
