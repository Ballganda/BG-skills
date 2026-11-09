# Project layout

A decomp project is its own private git repo. Nothing from the target binary, its bytes, or its reconstructed source ever goes into a public repo.

| Path | Holds | Written by |
| --- | --- | --- |
| `DECOMP.md` | The contract: target, compiler, flags, scope, policies, model roster | `/decomp-setup` only |
| `decomp.json` | The contract's machine-readable part (commands, guarded paths, allowlists, the default compiler and each unit that names its own) | `/decomp-setup` only |
| `toolchain.json` | The accepted target editions (hashes, probes, the functions each holds differently), the known-wrong editions, host prerequisites, and each required tool: version banner, required files, source, size, hash, unpack steps | `/decomp-setup` only |
| `.decomp/` | This machine only, never committed: `local.json` (target path, user-installed tool folders), `toolchain/`, `downloads/`, locks | `/decomp-setup`, `decomp.py` |
| `IDENTIFY.md` | The compiler investigation: facts, inferences, ranked candidates, toolchain requirements | `decomp-identify` |
| `docs/adr/` | Hard-to-reverse decisions (scope, relocation policy, fakematch rule) | `domain-modeling` |
| `tools/` | `decomp.py` plus the project's adapters, the tool wrapper, and any unpack scripts | `/decomp-setup` only |
| `inventory.json` | Every function and unit found in the target | `tools/inventory` |
| `expected/` | One file of original bytes per function | `tools/inventory` |
| `units/<unit>.md` | One spec per unit | `decomp.py gen-specs` |
| `tickets/<unit>/<id>.md` | One ticket per in-scope function | `decomp.py gen-tickets`, then `decomp.py` subcommands |
| `src/` | Reconstructed source, one file per unit | writers |
| `include/` | Shared declarations | `decomp-reference` |
| `symbols.json` | The **symbol map**: one JSON object, symbol name to its address in the original (`{"_memcpy": "0x00412340"}`) | `tools/inventory` seeds it, `decomp-reference` extends it |
| `ledger/` | `attempts.jsonl`, `matches.jsonl`, `events.jsonl`, `evidence/`, `github.json` | `decomp.py` only |
| `PATTERNS.md` | Proven lessons | `/decomp-run` |
| `OPEN.md` | Recurring unsolved failures | `decomp.py report` |

Two git tags freeze the ground truth: `decomp-setup` freezes `tools/`, `decomp.json`, `toolchain.json`, and `DECOMP.md`; `decomp-start` freezes `inventory.json` and `expected/`. `decomp.py` refuses to verify or revalidate when the integration branch differs from a tag in any path it froze. Only the skill that set a tag moves it, and only with the user's go-ahead.

The symbol map is guarded from writers like the shared headers, but no tag freezes it, because it grows: a repair branch changes it, and `revalidate` judges the change.

## Units and ids

A **unit** is a best-guess original source file: a run of functions in address order. Its id is `u` plus four digits (`u0001`). A ticket id is `<unit>-<address as 8 hex digits>` (`u0001-00401000`). A writer's branch for a ticket is `w/<ticket id>`; a repair branch is `r/<slug>`.

In the unit's source file, every function sits in address order with a marker line directly above its definition: `// @decomp <ticket id>`.

## Ticket

```
---
id: u0001-00401000
unit: u0001
address: 0x00401000
size: 37
tier: SMALL
source: src/u0001.cpp
expected: expected/00401000.bin
status: open
claimed_by:
claimed_at:
---
## Notes
- 1789000000 differ register-allocation 4B: swapped the two temporaries, no change
```

Notes are one line per attempt, appended by `decomp.py note`, read by the next writer on this ticket and by no one else.

## Statuses

| Status | Meaning | Set by |
| --- | --- | --- |
| `open` | Ready to work | `gen-tickets`, `release` |
| `claimed` | A writer has it (one claim per unit at a time) | `claim` |
| `blocked-reference` | Waiting on a shared declaration fix | `release --to blocked-reference` |
| `bytes-match` | Clean build matched every byte; audit pending | `verify` |
| `matched` | Audit passed; counts toward progress | `audit pass` |
| `integrated` | Merged into the integration branch | `integrate` |
| `revalidated` | Rebuilt with the whole project and still matching | `revalidate` |
| `regressed` | Was matched, no longer matches on the integration branch | `revalidate` |

Out-of-scope functions (`library`, `compiler`, `asm-origin`, `excluded`) get no ticket; their unit spec lists them with evidence.

## Records

All lines are JSON, one per line, with Unix times.

- `attempts.jsonl`: `id`, `ticket`, `unix`, `model`, `tier`, `result` (`build-fail`, `differ`, `bytes-match`, `guardrail`, `audit-fail`), `category`, `differ_bytes`, `evidence`, `source_sha256`.
- `matches.jsonl`: the **first** verified match per ticket, never rewritten: `ticket`, `unix`, `attempt`, `model`, `size`, `auditor`.
- `events.jsonl`: `unix`, `ticket` or `ref`, `event` (`integrated`, `revalidated`, `regressed`, `rejected-repair`).

## Commands

Run from the project root: `python tools/decomp.py <command>`.

| Command | Does |
| --- | --- |
| `doctor` | Check this machine against `toolchain.json`: which edition the target is, each host prerequisite's version, each tool's required files and version banner. Prints the recognised edition. Exit 6 on any difference |
| `provision [--tool <name>] [--force]` | Download each tool that has a source, compare size and SHA-256, then unpack it under `.decomp/toolchain/`. Never installs a host prerequisite |
| `gen-specs`, `gen-tickets` | Write unit specs and tickets from `inventory.json`; existing status and notes survive |
| `next [--n N]` | List open tickets in pick order |
| `claim <id> --by <name>` / `release <id> [--to <status>]` | Take or give back a ticket |
| `check <id>` | Writer's loop: build and diff in the current worktree, record nothing |
| `verify <id> --model <m> [--category <c>]` | Rebuild the writer's branch in a clean worktree, compare bytes, record the attempt |
| `audit <id> pass\|fail --auditor <m>` | Record the auditor's verdict; `pass` records the match |
| `integrate <id>` | Mark a merged match integrated |
| `revalidate [--ref <branch>] [--header <path>]` | Rebuild matched tickets on a ref; nonzero exit on any regression. A repair ref may touch only `include/` and `symbols.json` |
| `note <id> <text>` | Append an attempt note to a ticket |
| `similar <id>` | Closest matched functions by byte pattern |
| `lock <name> --by <n>` / `unlock <name>` | Exclusive lock, used for shared header and symbol map repair |
| `report` | Progress, attribution, learning metrics, early warning; regenerates `OPEN.md`, checks `PATTERNS.md` |
| `sync` | Push unit checklists and the progress issue to GitHub, when enabled |

`check`, `verify`, and `revalidate` run the `doctor` checks first and build nothing when they fail. `check` skips them while `toolchain.json`, the target, and the tools' files are unchanged since the last pass. Exit 6 always means the machine, not the source: no writer fixes it, and no attempt is recorded.

`check` and `verify` also exit 6 for a ticket no result could count for on this machine: its address is in the recognised edition's `differs` list, or its unit names a compiler `toolchain.json` does not list. `revalidate` skips a ticket in `differs` and says so.

## Target editions

`toolchain.json`'s `target` lists the accepted editions, the probes that recognise one without a whole-file hash, and the editions known to be wrong. `doctor` tries, in order:

1. A whole-file SHA-256 (and size) equal to an accepted edition's: pass.
2. A whole-file SHA-256 equal to a known-wrong edition's: fail, printing its name and its message.
3. The probes. Each is a file offset, a length, and the SHA-256 of that range: never target bytes, never a virtual address. An edition that declares `probes_needed` is accepted when at least that many probes match.
4. Otherwise fail, printing how many probes matched out of how many.

An edition's `differs` lists the addresses of the functions it holds differently from `expected/`. A `target` holding only `sha256` and `size` is one accepted edition.

## Adapters

`/decomp-setup` writes these for the project's format and toolchain. Each is a command in `decomp.json`, run from a worktree root, with `{placeholders}` filled from the ticket. `decomp.py` gives each one the target's path as `DECOMP_TARGET` and each tool's folder as `DECOMP_TOOL_<NAME>` (the tool's `name` in `toolchain.json`, upper-cased); an adapter holds no absolute path.

- **inventory**: reads the target, writes `inventory.json` and `expected/`, and seeds `symbols.json` with what the target itself proves (exports, imports, any symbols present). Shape: `{"units": [{"id", "source", "start", "end", "evidence"}], "functions": [{"address", "size", "unit", "scope", "evidence"}]}`; `scope` is `in`, `library`, `compiler`, `asm-origin`, or `excluded`; `size` follows the tier rule.
- **build** (`{source}`, `{unit}`, `{obj}`, `{compiler}`): compiles one unit with the contract's compiler and flags. `{compiler}` is the tool name from `toolchain.json` that builds this unit: `decomp.json`'s `compiler`, or the unit's entry in `unit_compilers`. Exit nonzero on failure, errors on stderr.
- **diff** (`{obj}`, `{expected}`, `{id}`, `{source}`, `{report}`, `{symbols}`): finds the function after the `// @decomp {id}` marker in the object, compares it to the expected bytes under the contract's relocation policy, writes a readable instruction diff to `{report}`, and prints `{"match": true|false, "differ_bytes": N}` on stdout. `{symbols}` is the path of the symbol map in the tree being built.
- **disasm** (`{expected}`, `{address}`): prints the original function's disassembly.

Every adapter and banner command invokes a tool through the one wrapper in `tools/`, which owns the environment, path conversion, and any compatibility layer.

## Default relocation policy

The `diff` adapter applies this unless the contract names a departure with its ADR. A relocated operand is never a free pass:

- **Excluded only when proven.** A relocated operand is left out of the byte comparison only when the relocation's symbol resolves, through the symbol map or through another function matched in the same object, to the address the original's operand refers to.
- **Unresolved symbol.** A symbol that resolves through neither makes the result `differ`. The report names the symbol.
- **Wrong target.** A symbol that resolves to another address than the original holds makes the result `differ`. The report gives the offset, the symbol, the address it resolves to, and the address the original holds.
- **One tolerance.** A string or floating-point literal whose bytes are identical at both addresses compares equal: which pooled copy the linker keeps is not decided by the source.
- **Exact extent.** The compiled function's extent equals the ticket's size, and every byte after it is padding. A candidate longer than the original never matches on a prefix.
