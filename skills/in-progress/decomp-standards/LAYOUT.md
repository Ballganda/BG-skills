# Project layout

A decomp project is its own private git repo. Nothing from the target binary, its bytes, or its reconstructed source ever goes into a public repo.

| Path | Holds | Written by |
| --- | --- | --- |
| `DECOMP.md` | The contract: target, compiler, flags, scope, policies, model roster | `/decomp-setup` only |
| `decomp.json` | The contract's machine-readable part (commands, guarded paths, allowlists) | `/decomp-setup` only |
| `IDENTIFY.md` | The compiler investigation: facts, inferences, ranked candidates | `decomp-identify` |
| `docs/adr/` | Hard-to-reverse decisions (scope, relocation policy, fakematch rule) | `domain-modeling` |
| `tools/` | `decomp.py` plus the project's adapters | `/decomp-setup` only |
| `inventory.json` | Every function and unit found in the target | `tools/inventory` |
| `expected/` | One file of original bytes per function | `tools/inventory` |
| `units/<unit>.md` | One spec per unit | `decomp.py gen-specs` |
| `tickets/<unit>/<id>.md` | One ticket per in-scope function | `decomp.py gen-tickets`, then `decomp.py` subcommands |
| `src/` | Reconstructed source, one file per unit | writers |
| `include/` | Shared declarations | `decomp-reference` |
| `ledger/` | `attempts.jsonl`, `matches.jsonl`, `events.jsonl`, `evidence/`, `github.json` | `decomp.py` only |
| `PATTERNS.md` | Proven lessons | `/decomp-run` |
| `OPEN.md` | Recurring unsolved failures | `decomp.py report` |

Two git tags freeze the ground truth: `decomp-setup` freezes `tools/`, `decomp.json`, and `DECOMP.md`; `decomp-start` freezes `inventory.json` and `expected/`. `decomp.py` refuses to verify or revalidate when the integration branch differs from a tag in any path it froze. Only the skill that set a tag moves it, and only with the user's go-ahead.

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
| `gen-specs`, `gen-tickets` | Write unit specs and tickets from `inventory.json`; existing status and notes survive |
| `next [--n N]` | List open tickets in pick order |
| `claim <id> --by <name>` / `release <id> [--to <status>]` | Take or give back a ticket |
| `check <id>` | Writer's loop: build and diff in the current worktree, record nothing |
| `verify <id> --model <m> [--category <c>]` | Rebuild the writer's branch in a clean worktree, compare bytes, record the attempt |
| `audit <id> pass\|fail --auditor <m>` | Record the auditor's verdict; `pass` records the match |
| `integrate <id>` | Mark a merged match integrated |
| `revalidate [--ref <branch>] [--header <path>]` | Rebuild matched tickets on a ref; nonzero exit on any regression |
| `note <id> <text>` | Append an attempt note to a ticket |
| `similar <id>` | Closest matched functions by byte pattern |
| `lock <name> --by <n>` / `unlock <name>` | Exclusive lock, used for shared header repair |
| `report` | Progress, attribution, learning metrics, early warning; regenerates `OPEN.md`, checks `PATTERNS.md` |
| `sync` | Push unit checklists and the progress issue to GitHub, when enabled |

## Adapters

`/decomp-setup` writes these for the project's format and toolchain. Each is a command in `decomp.json`, run from a worktree root, with `{placeholders}` filled from the ticket.

- **inventory**: reads the target, writes `inventory.json` and `expected/`. Shape: `{"units": [{"id", "source", "start", "end", "evidence"}], "functions": [{"address", "size", "unit", "scope", "evidence"}]}`; `scope` is `in`, `library`, `compiler`, `asm-origin`, or `excluded`; `size` follows the tier rule.
- **build** (`{source}`, `{unit}`, `{obj}`): compiles one unit with the contract's compiler and flags. Exit nonzero on failure, errors on stderr.
- **diff** (`{obj}`, `{expected}`, `{id}`, `{source}`, `{report}`): finds the function after the `// @decomp {id}` marker in the object, compares it to the expected bytes under the contract's relocation policy, writes a readable instruction diff to `{report}`, and prints `{"match": true|false, "differ_bytes": N}` on stdout.
- **disasm** (`{expected}`, `{address}`): prints the original function's disassembly.
