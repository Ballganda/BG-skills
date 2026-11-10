# Project layout

A decomp project is its own private git repo. Nothing from the target binary, its bytes, or its reconstructed source ever goes into a public repo.

| Path | Holds | Written by |
| --- | --- | --- |
| `DECOMP.md` | The contract: target, compiler, flags, scope, policies, model roster | `/decomp-setup` only |
| `decomp.json` | The contract's machine-readable part (commands, guarded paths, the pragma and attribute allowlists, the default compiler and each unit that names its own) | `/decomp-setup` only |
| `toolchain.json` | The accepted target editions (hashes, probes, the functions each holds differently), the known-wrong editions, host prerequisites, and each required tool (per host, where hosts differ): version banner, required files, source, size, hash, unpack steps | `/decomp-setup` only |
| `.decomp/` | This machine only, never committed: `local.json` (target path, user-installed tool folders), `toolchain/`, `downloads/`, locks | `/decomp-setup`, `decomp.py` |
| `IDENTIFY.md` | The compiler investigation: facts, inferences, ranked candidates, toolchain requirements | `decomp-identify` |
| `docs/adr/` | Hard-to-reverse decisions (scope, relocation policy, fakematch rule, an accepted edition) | `domain-modeling` |
| `tools/` | `decomp.py` plus the project's adapters, the tool wrapper, and any unpack scripts | `/decomp-setup` only |
| `inventory.json` | Every function and unit found in the target | `tools/inventory` |
| `expected/` | One file of original bytes per function, named by the function's key | `tools/inventory` |
| `units/<unit>.md` | One spec per unit | `decomp.py gen-specs` |
| `tickets/<unit>/<id>.md` | One ticket per in-scope function | `decomp.py gen-tickets`, then `decomp.py` subcommands |
| `src/` | Reconstructed source, one file per unit | writers |
| `include/` | Shared declarations | `decomp-reference` |
| `symbols.json` | The **symbol map**: one JSON object, symbol name to its address in the original. See [Symbol map](#symbol-map) | `tools/inventory` seeds it, `decomp-reference` extends it |
| `ledger/` | `attempts.jsonl`, `matches.jsonl`, `events.jsonl`, `evidence/`, `github.json` | `decomp.py` only |
| `PATTERNS.md` | Proven lessons | `/decomp-run` |
| `OPEN.md` | Recurring unsolved failures | `decomp.py report` |

Two git tags freeze the ground truth: `decomp-setup` freezes `tools/`, `decomp.json`, `toolchain.json`, and `DECOMP.md`; `decomp-start` freezes `inventory.json` and `expected/`. `decomp.py` refuses to verify or revalidate when the integration branch differs from a tag in any path it froze. The one exception is `revalidate --candidate`, which skips that check for a candidate ref. Only the skill that set a tag moves it, and only with the user's go-ahead, through the [change flow](#change-flow).

The symbol map is guarded from writers like the shared headers, but no tag freezes it, because it grows: a repair branch changes it, and `revalidate` judges the change.

## Units and ids

A **unit** is a best-guess original source file: a run of functions in address order. Its id is `u` plus four digits (`u0001`). A ticket id is `<unit>-<key>` (`u0001-00401000`). A function's **key** names it in its ticket id and its expected file. By default it is the address in hex, zero-padded to at least 8 digits (a 64-bit address is longer). Where an address alone does not name one function (overlays or modules loaded at the same address, banked memory), `inventory` gives each function a `key` of letters, digits, `_`, and `.`, such as `ovl2_80101000`, and writes the address with its prefix (`ovl2:0x80101000`, `03:8000`). A writer's branch for a ticket is `w/<ticket id>`. A **repair ref** is a branch named `r/<slug>`: it may touch only the shared headers and the symbol map. A **candidate ref** is a branch named `c/<slug>` that holds a proposed change to paths a tag freezes: it may change any path frozen by either tag.

In the unit's source file, every function sits in the contract's function order (address order, unless the contract records that this compiler emits another) with a marker comment directly above its definition: `// @decomp <ticket id>`, or `/* @decomp <ticket id> */` where the contract's language has no line comment.

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

Run from the project root: `python tools/decomp.py <command>`. `python` is the host's Python 3: where only `python3` exists, write that.

| Command | Does |
| --- | --- |
| `doctor` | Check this machine against `toolchain.json`: which edition the target is, each host prerequisite's version, each tool's required files and version banner. Prints the recognised edition. Exit 6 on any difference |
| `provision [--tool <name>] [--force]` | Download each tool that has a source, compare size and SHA-256, then unpack it under `.decomp/toolchain/`. Checks the host prerequisites first. A file already in `.decomp/downloads/` is compared, and replaced only with `--force`. Never installs a host prerequisite |
| `inventory [--redo]` | Run the `inventory` adapter, after the full `doctor` checks. Once the `decomp-start` tag exists it refuses, naming the redo flow, unless `--redo` is passed. Pass `--redo` only with the user's go-ahead for an inventory redo, or in a throwaway clone, where it writes nothing to the project |
| `disasm <id>` | Print the original function's disassembly: run the `disasm` adapter with the ticket's expected file and address |
| `gen-specs`, `gen-tickets` | Write unit specs and tickets from `inventory.json`; existing status and notes survive |
| `next [--n N]` | List open tickets in pick order |
| `claim <id> --by <name>` / `release <id> [--to <status>]` | Take or give back a ticket |
| `check <id>` | Writer's loop: build and diff in the current worktree, record nothing |
| `verify <id> --model <m> [--category <c>]` | Rebuild the writer's branch in a clean worktree, compare bytes, record the attempt |
| `audit <id> pass\|fail --auditor <m>` | Record the auditor's verdict; `pass` records the match |
| `integrate <id>` | Mark a merged match integrated |
| `revalidate [--ref <branch>] [--header <path>]` | Rebuild matched tickets on a ref (with `--header`, only those that include that header, directly or through another); nonzero exit on any regression. A repair ref may touch only `include/` and `symbols.json` |
| `revalidate --candidate <c/slug>` | Rebuild every matched ticket on a candidate ref, in a clean worktree of it, with that tree's own copy of `decomp.py`. Accepts only a `c/<slug>` branch, and takes no `--ref` or `--header`. Records nothing: no ledger line, no status change. Exit 0 when every match holds; nonzero, listing each `REGRESSED` ticket, when one does not. A ticket the integration branch holds matched and the candidate lacks is listed `REGRESSED` too. A ticket already `regressed` is not rebuilt and does not count |
| `note <id> <text>` | Append an attempt note to a ticket |
| `similar <id>` | Closest matched functions by byte pattern |
| `lock <name> --by <n>` / `unlock <name>` | Exclusive lock, used for shared header and symbol map repair. Locks and claims are shared by every worktree of the repository |
| `report` | Progress, attribution, learning metrics, early warning; regenerates `OPEN.md`, checks `PATTERNS.md`. Prints one `state:` line computed from ticket statuses: `finished` (every in-scope ticket is `revalidated`), `stuck` (not finished, and every remaining ticket is `blocked-reference` or `regressed`), or `more` (anything else) |
| `sync` | Push unit checklists and the progress issue to GitHub, when enabled |

`inventory`, `disasm`, `check`, `verify`, and `revalidate` run the `doctor` checks first and run no adapter when they fail. `check` and `disasm` skip them while `toolchain.json`, the target, and the tools' files are unchanged since the last pass. Exit 6 always means the machine, not the source: no writer fixes it, and no attempt is recorded.

`check` and `verify` also exit 6 for a ticket no result could count for on this machine: the recognised edition's `differs` list names it, or its unit's compiler is missing from `toolchain.json`, listed only for another host, or not provisioned. A compiler that builds only other units does not stop this one.

`revalidate` prints `SKIPPED` for each such ticket. On the integration branch it leaves that ticket's status alone and still exits 0. On a repair ref or a candidate ref it exits 6: a repair is accepted, and a candidate measured, only on a machine that rebuilt every match it could break. A candidate run with a skipped ticket exits 6 even when it also lists regressions.

## Change flow

Every change to a path a tag freezes (a contract change, a skill upgrade, an inventory redo, a new edition) takes these steps, in this order. The tag moves only after the change has been measured:

1. Make the change on a `c/<slug>` branch from the integration branch tip.
2. Run `python tools/decomp.py revalidate --candidate c/<slug>` and show the user the result. The candidate's own tool, adapters, manifest, and contract judge it, and nothing is recorded. Regressions inform the user's go-ahead and do not block it: a corrected flag breaks matches on purpose. On exit 6, run it again on a machine that can build every matched ticket.
3. On the user's go-ahead, merge the candidate into the integration branch and move the tag that freezes the changed paths. Without it, delete the branch: nothing else changed.
4. Run a plain `python tools/decomp.py revalidate` on the integration branch. It records `revalidated` and `regressed`.

## Target editions

`toolchain.json`'s `target` lists the accepted editions, the probes that recognise one without a whole-file hash, and the editions known to be wrong. `doctor` tries, in order:

1. A whole-file SHA-256 (and size) equal to an accepted edition's: pass.
2. A whole-file SHA-256 equal to a known-wrong edition's: fail, printing its name and its message.
3. The probes. Each is a file offset, a length, and the SHA-256 of that range: never target bytes, never a virtual address. Offsets are into the target file as it sits on disk, so when the product ships its code compressed or encrypted, the contract's target is the unpacked image. An edition that declares `probes_needed` is accepted when at least that many probes match.
4. Otherwise fail, printing how many probes matched out of how many.

An edition's `differs` lists the functions it holds differently from `expected/`, each by address, or by key where an address names more than one. A `target` holding only `sha256` and `size` is one accepted edition.

## Adapters

`/decomp-setup` writes these for the project's format and toolchain. Each is a command in `decomp.json`, run from a worktree root, with `{placeholders}` filled from the ticket. Adapters are run only through `decomp.py` (`inventory`, `disasm`, and the commands that build and diff), never directly: that is what gives each one its environment. Every command also gets `{tools}` (the `tools/` folder of the tree being built) and `{python}` (the interpreter running `decomp.py`), and a brace that is not a placeholder stays as written. `decomp.py` gives each one the target's path as `DECOMP_TARGET` and each tool's folder as `DECOMP_TOOL_<NAME>` (the tool's `name` in `toolchain.json`, upper-cased); an adapter holds no absolute path and no lookup of `.decomp/local.json`.

- **inventory**: reads the target, writes `inventory.json` and `expected/`, and seeds `symbols.json` with what the target itself proves (exports, imports, any symbols present). Shape: `{"units": [{"id", "source", "start", "end", "evidence"}], "functions": [{"address", "size", "unit", "scope", "evidence"}]}`; a function may add `key` (see Units and ids) and `expected` (its expected file, when not `expected/<key>.bin`); `scope` is `in`, `library`, `compiler`, `asm-origin`, or `excluded`; `size` follows the tier rule.
- **build** (`{source}`, `{unit}`, `{obj}`, `{compiler}`): compiles one unit with the contract's compiler and flags. `{compiler}` is the tool name from `toolchain.json` that builds this unit: `decomp.json`'s `compiler`, or the unit's entry in `unit_compilers`. Exit nonzero on failure, errors on stderr.
- **diff** (`{obj}`, `{expected}`, `{id}`, `{source}`, `{report}`, `{symbols}`): finds the function after the `@decomp {id}` marker in the object, compares it to the expected bytes under the contract's relocation policy, writes a readable instruction diff to `{report}`, and prints `{"match": true|false, "differ_bytes": N}` on stdout. `{symbols}` is the path of the symbol map in the tree being built.
- **disasm** (`{expected}`, `{address}`): prints the original function's disassembly. `decomp.py disasm <id>` fills the placeholders from the ticket.

Every adapter and banner command invokes a tool through the one wrapper in `tools/`, which owns the environment, path conversion, and any compatibility layer. `decomp.py` reads a tool's output in whatever encoding the tool writes, so an adapter never depends on the host's.

## Symbol map

`symbols.json` is one JSON object. The tool passes its path to the `diff` adapter and reads nothing in it, so these are the conventions the adapter and `decomp-reference` share:

- **Global symbol**: its name as the object file spells it, to its address in the original: `{"_memcpy": "0x00412340"}`. An address is written the way `inventory.json` writes it, prefix included.
- **Symbol private to a unit** (a `static`, a compiler-generated label): `<unit>:<name>`, so two units' statics of the same name do not collide: `{"u0007:helper": "0x00418A10"}`.
- **Section of a unit**: `<unit>:<section>`, the address where this unit's part of that section sits in the original: `{"u0007:.rodata": "0x0051A2C0"}`. A relocation against a section symbol plus an addend resolves through it.
- **Base symbol**: an address the format's relocations are relative to (`_gp`, `_SDA_BASE_`) is an entry like any other.

## Default relocation policy

The `diff` adapter applies this unless the contract names a departure with its ADR. An **operand** here is the bits one relocation fills: a whole address field on some architectures, a bit-field inside one or two instructions on others (a high and low half, a branch displacement, an offset from a base register). The adapter computes what those bits would hold from the relocation's type and the symbol's address in the map, and compares that. A relocated operand is never a free pass:

- **Excluded only when proven.** A relocated operand is left out of the byte comparison only when the relocation's symbol resolves, through the symbol map or through another function matched in the same object, to the address the original's operand refers to.
- **Unresolved symbol.** A symbol that resolves through neither makes the result `differ`. The report names the symbol.
- **Wrong target.** A symbol that resolves to another address than the original holds makes the result `differ`. The report gives the offset, the symbol, the address it resolves to, and the address the original holds.
- **One tolerance.** A string or floating-point literal whose bytes are identical at both addresses compares equal: which pooled copy the linker keeps is not decided by the source.
- **Exact extent.** The compiled function's extent equals the ticket's size, and every byte after it is padding. A candidate longer than the original never matches on a prefix.
