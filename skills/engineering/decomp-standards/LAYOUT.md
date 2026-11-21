# Project layout

A decomp project is its own private git repo. Nothing from the target binary, its bytes, or its reconstructed source ever goes into a public repo.

| Path | Holds | Written by |
| --- | --- | --- |
| `DECOMP.md` | The contract: target, compiler, flags, scope, policies, model roster | `/decomp-setup` only |
| `decomp.json` | The contract's machine-readable part. See [decomp.json](#decompjson) | `/decomp-setup` only |
| `toolchain.json` | The accepted target editions, host prerequisites and required tools. See [toolchain.json](#toolchainjson) | `/decomp-setup` only |
| `.decomp/` | This machine only, never committed. See [The .decomp folder](#the-decomp-folder) | `/decomp-setup`, `decomp.py` |
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

### decomp.json

- It holds the contract's commands.
- It holds the guarded paths.
- It holds the pragma and attribute allowlists.
- It holds `template_search` and `fakematch`: the contract's template-search and fakematch rules, which `doctor` prints and stops without.
- It holds the default compiler and each unit that names its own.
- It holds `link_milestone` (see [report](#report)).
- It holds `link_unavailable` when the target cannot be linked whole.

### toolchain.json

- It holds the accepted target editions: hashes, probes, and the functions each holds differently.
- It holds the known-wrong editions.
- It holds the host prerequisites.
- It holds each required tool (per host, where hosts differ): version banner, required files, source, size, hash, unpack steps.

### The .decomp folder

- It is for this machine only and is never committed.
- `local.json`: the target path and the user-installed tool folders.
- `toolchain/` and `downloads/`.
- Locks.
- `link/`: the linked binary.
- `trail.jsonl`: the [check trail](#check-trail).
- `perf.jsonl`: the [performance log](#performance-log).
- `check/<ticket id>/diff.txt`: the diff report of the ticket's last `check`.
- `search/<ticket id>/`: the ticket's last template round.
  - It holds the round's template.
  - It holds each candidate's score.
  - It holds what `verify --template-round` records.
  - `background/`: the files of its [background search](#background-search).
  - `background.log`: the log of the last background search that tried nothing.
  - `winner/<source file name>`: the winning source of the ticket's last round that matched.
  - `winner-background/<source file name>`: the winning source of the last collected background search that matched.
- `slots/`: the [slot pool](#slot-pool) every search on this machine shares.

### Temp folders

- No command leaves a folder in the system temp folder.
- Every temp folder the tool makes sits under one parent there: `decomp-<project folder name>-<8 hex digits>`.
  - The hex digits are a hash of the main checkout's path, so every worktree of the checkout shares the parent.
- A command removes the temp folders it made before it exits: on success, a refusal, an error, and an interrupt.
  - It removes the parent too once that is empty.
  - A temp worktree leaves git's worktree list as well as the disk.
- Removal tries again for 2 seconds while a file is held, then leaves the folder and does not fail the command.
- Every command first removes the entries of the parent that are older than one day.
  - Those are what a killed command left.
  - A younger entry may belong to a command that is still running, so it stays.
- A background search removes its own scratch folder as it exits, since it can outlive the call that started it.
- What a reader needs after a command is kept under `.decomp/`: the diff report of `check` and a search's winning source.

## Tags and frozen paths

- Two git tags freeze the ground truth.
- `decomp-setup` freezes `tools/`, `decomp.json`, `toolchain.json`, and `DECOMP.md`.
- `decomp-start` freezes `inventory.json` and `expected/`.
- `decomp.py` refuses to verify or revalidate when the integration branch differs from a tag in any path it froze.
- The one exception is `revalidate --candidate`, which skips that check for a candidate ref.
- Only the skill that set a tag moves it, and only with the user's go-ahead, through the [change flow](#change-flow).
- The symbol map is guarded from writers like the shared headers, but no tag freezes it, because it grows.
- A repair branch changes the symbol map, and `revalidate` judges the change.

## Units and ids

- A **unit** is a best-guess original source file: a run of functions in address order.
- A unit's id is `u` plus four digits (`u0001`).
- A ticket id is `<unit>-<key>` (`u0001-00401000`).
- A function's **key** names it in its ticket id and its expected file.
- By default the key is the address in hex, zero-padded to at least 8 digits (a 64-bit address is longer).
- Where an address alone does not name one function (overlays or modules loaded at the same address, banked memory), `inventory` gives each function a `key` of letters, digits, `_`, and `.`, such as `ovl2_80101000`.
- In that case it writes the address with its prefix (`ovl2:0x80101000`, `03:8000`).
- A writer's branch for a ticket is `w/<ticket id>`.
- A **repair ref** is a branch named `r/<slug>`: it may touch only the shared headers and the symbol map.
- A **candidate ref** is a branch named `c/<slug>` that holds a proposed change to paths a tag freezes: it may change any path frozen by either tag.
- In the unit's source file, every function sits in the contract's function order (address order, unless the contract records that this compiler emits another).
- Each function has a marker comment directly above its definition: `// @decomp <ticket id>`, or `/* @decomp <ticket id> */` where the contract's language has no line comment.

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

- Notes are one line per attempt, appended by `decomp.py note`.
- Notes are read by the next writer on this ticket and by no one else.

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
- `events.jsonl`: `unix`, `ticket` or `ref`, `event` (`integrated`, `revalidated`, `regressed`, `rejected-repair`, `link`, `out-of-order` with a `reason`).
  - A `link` event also holds `result`: `pass`, `mismatch`, or `fail` when a source unit did not build or the adapter failed.
  - A `link` event also holds `edition`.
  - A `link` event also holds `units`: the units linked from source.
  - A `link` event also holds `source_bytes` and `in_scope_bytes`.
  - Once a file was linked, a `link` event also holds its `sha256` and `size`.
  - A mismatch adds `first_differ`, the first differing file offset.

## Commands

Run from the project root: `python tools/decomp.py <command>`. `python` is the host's Python 3: where only `python3` exists, write that.

Commands with detail link to their section below the table.

| Command | Does |
| --- | --- |
| `doctor` | Check this machine against `toolchain.json`. See [doctor](#doctor) |
| `contract-keys` | For the skill upgrade: print the `decomp.json` keys `DECOMP.md` gives. See [contract-keys](#contract-keys) |
| `provision [--tool <name>] [--force]` | Download each tool that has a source, verify it, unpack it. See [provision](#provision) |
| `inventory [--redo]` | Run the `inventory` adapter, after the full `doctor` checks. See [inventory](#inventory) |
| `disasm <id>` | Print the original function's disassembly. See [disasm](#disasm) |
| `gen-specs`, `gen-tickets` | Write unit specs and tickets from `inventory.json`; existing status and notes survive |
| `next [--n N] [--first ID --reason TEXT]` | List ready tickets smallest first. See [next](#next) |
| `claim <id> --by <name>` / `release <id> [--to <status>]` | Take or give back a ticket. See [claim and release](#claim-and-release) |
| `check <id> [--category <c>]` | Writer's loop: build and diff in the current worktree. See [check](#check) |
| `search <id> <template file>` | One template round: try every candidate of a template, report the closest. See [search](#search) |
| `search <id> --stop` | Stop the ticket's background search. See [search](#search) |
| `search <id> --detail '<choice code>'` | Print one candidate of the ticket's last round. See [search](#search) |
| `verify <id> --model <m> [--category <c>] [--template-round]` | Rebuild the writer's branch in a clean worktree, compare bytes, record the attempt. See [verify](#verify) |
| `audit <id> pass\|fail --auditor <m>` | Record the auditor's verdict; `pass` records the match |
| `integrate <id>` | Mark a merged match integrated |
| `revalidate [--ref <branch>] [--header <path>]` | Rebuild matched tickets on a ref; nonzero exit on any regression. See [revalidate](#revalidate) |
| `revalidate --candidate <c/slug>` | Rebuild every matched ticket on a candidate ref. See [revalidate](#revalidate) |
| `note <id> <text>` | Append an attempt note to a ticket |
| `similar <id>` | Closest matched functions by byte pattern, from the tickets `ledger/matches.jsonl` names |
| `lock <name> --by <n>` / `unlock <name>` | Exclusive lock, used for shared header and symbol map repair. See [lock and unlock](#lock-and-unlock) |
| `link` | Link the whole binary from the reconstructed source plus raw blocks of the target. See [link](#link) |
| `report` | Progress, attribution, learning metrics, early warning. See [report](#report) |
| `sync` | Push unit checklists and the progress issue to GitHub, when enabled |

### Machine checks and exit 6

- `inventory`, `disasm`, `check`, `search`, `verify`, `revalidate`, and `link` run the `doctor` checks first and run no adapter when they fail.
- `check`, `search`, and `disasm` skip the `doctor` checks while `toolchain.json`, the target, and the tools' files are unchanged since the last pass.
- Exit 6 always means the machine, not the source: no writer fixes it, and no attempt is recorded.
- `check`, `search`, and `verify` also exit 6 for a ticket no result could count for on this machine.
  - The recognised edition's `differs` list names it, or
  - its unit's compiler is missing from `toolchain.json`, listed only for another host, or not provisioned.
- A compiler that builds only other units does not stop this one.

### doctor

- It checks this machine against `toolchain.json`.
- It checks which edition the target is.
- It checks each host prerequisite's version.
- It checks each tool's required files and version banner.
- It prints the recognised edition.
- It then prints the contract's rules from `decomp.json`: `template search: allowed` or `not allowed`, and `fakematch: forbidden` or `allowed`.
- It exits 6 on any difference.
- It exits 1, naming the skill upgrade, when `decomp.json` lacks a valid `template_search` or `fakematch`.

### contract-keys

- It is for the skill upgrade.
- It reads `DECOMP.md` and prints the `decomp.json` keys its lines give, as one JSON line (`template_search`, `fakematch`).
- An old "Permuter:" line is read as the "Template search:" line.
- Markdown emphasis on a bullet's name or value (bold, italic, backticks) is ignored.
- It stops when a line is missing or unclear.

### provision

- It downloads each tool that has a source, compares size and SHA-256, then unpacks it under `.decomp/toolchain/`.
- It checks the host prerequisites first.
- A file already in `.decomp/downloads/` is compared, and replaced only with `--force`.
- It never installs a host prerequisite.

### inventory

- It runs the `inventory` adapter, after the full `doctor` checks.
- Once the `decomp-start` tag exists it refuses, naming the redo flow, unless `--redo` is passed.
- Pass `--redo` only with the user's go-ahead for an inventory redo, or in a throwaway clone, where it writes nothing to the project.

### disasm

- It prints the original function's disassembly.
- It runs the `disasm` adapter with the ticket's expected file and address.

### next

- It lists ready tickets smallest first: tier, then size, then address.
- `--first` lists that ready ticket first and records an `out-of-order` event.

### claim and release

- `claim` and `release` take or give back a ticket.
- `release` also ends the ticket's [background search](#background-search) and drops what it found.
- `release` also removes the ticket's `check` report and its winning sources.

### check

- It is the writer's loop: build and diff in the current worktree.
- It records nothing in the ledger.
- It appends one record to the [check trail](#check-trail).
- `--category` is the writer's reading of the first difference, one of the mismatch categories.
- Any other category is refused before anything runs.
- It prints one JSON line with these fields:
  - `result`
  - `differ_bytes`
  - `report`: the path of the diff report, `.decomp/check/<ticket id>/diff.txt`
  - `search_open`: whether [the gate](#the-gate) is open for this ticket
  - `search_reason`
- The report path is one per ticket: each `check` of the ticket replaces the report.
- The file exists after every `check`, and is empty when the diff did not run (a guardrail refusal, a build failure).

### search

- `search <id> <template file>` is one template round: it tries every candidate of a template and reports the closest. See [Template search](#template-search).
- It refuses, with the reason, while [the gate](#the-gate) is closed.
- A round that ran is one attempt in the check trail, unless it is a repeat (every candidate served from the result cache).
- It records nothing in the ledger and writes nothing in the tree.
- It first stops the ticket's [background search](#background-search) and reports what that found.
  - A call that then prints no summary prints `{"background": <its report>}` alone on standard output.
- `search <id> --stop` stops the ticket's background search, with every process under it.
- `--stop` prints one JSON line: `{"background": <its report>}`, or `null` when the ticket has none.
- The results of a stopped search join the kept round.
- `search <id> --detail '<choice code>'` prints one candidate of the ticket's last round.
- `--detail` prints a JSON line (`code`, `result`, `differ_bytes`), then the candidate's source as plain C.
- Its `result` is `not-tried` for a candidate the round did not reach.

### verify

- It rebuilds the writer's branch in a clean worktree, compares bytes, and records the attempt.
- `--template-round` marks the attempt as a template round.
- A template round's evidence file gains one line, `template-round: ` then JSON holding the ticket's last round on this machine.
  - `best`: the best candidate's choice code.
  - `result`.
  - `differ_bytes`.
  - `kinds`: the kinds of the choice points where that candidate leaves the baseline.
  - A match by the baseline records no kind, so `kinds` is empty.
  - `category`: the trail's category the round worked on.
  - `unix`.
- The fields of `attempts.jsonl` are unchanged.
- It refuses, recording nothing, when this machine keeps no round for the ticket.

### revalidate

- `revalidate [--ref <branch>] [--header <path>]` rebuilds matched tickets on a ref.
- With `--header`, it rebuilds only those that include that header, directly or through another.
- It exits nonzero on any regression.
- A repair ref may touch only `include/` and `symbols.json`.
- It prints `SKIPPED` for each ticket no result could count for on this machine (see [Machine checks and exit 6](#machine-checks-and-exit-6)).
- On the integration branch it leaves a skipped ticket's status alone and still exits 0.
- On a repair ref or a candidate ref it exits 6: a repair is accepted, and a candidate measured, only on a machine that rebuilt every match it could break.
- A candidate run with a skipped ticket exits 6 even when it also lists regressions.
- `revalidate --candidate <c/slug>` rebuilds every matched ticket on a candidate ref, in a clean worktree of it.
- It uses that tree's own copy of `decomp.py`.
- It accepts only a `c/<slug>` branch, and takes no `--ref` or `--header`.
- It records nothing: no ledger line, no status change.
- It exits 0 when every match holds.
- It exits nonzero, listing each `REGRESSED` ticket, when one does not.
- A ticket the integration branch holds matched and the candidate lacks is listed `REGRESSED` too.
- A ticket already `regressed` is not rebuilt and does not count.

### lock and unlock

- An exclusive lock, used for shared header and symbol map repair.
- Locks and claims are shared by every worktree of the repository.

### link

- It links the whole binary from the reconstructed source plus raw blocks of the target, after the full `doctor` checks.
- A unit links from source only when every in-scope function in it is `integrated` or `revalidated`.
- A unit also links from source only when none of its functions is on the recognised edition's `differs` list.
- Every other unit, every out-of-scope function, all data, and every other byte of the file is a raw block.
- It builds each source unit in a clean worktree of the integration branch.
- It runs the `link` adapter.
- It compares the output with the target on this machine, the edition `doctor` recognised.
- It prints one result line: `link: pass` or `link: mismatch`.
- The line gives the in-scope code bytes from source over all in-scope code bytes.
- The line gives the output path, `.decomp/link/<target file name>`.
- On a mismatch it prints the first differing file offset and its owner, and exits 4.
  - The owner is `unit <unit> function <id>`.
  - Or `header`, before the first function's offset in `inventory.json`.
  - Or `raw block <start> to <end>`.
- It appends one `link` event and changes no ticket status.
- Without a `link` command in `decomp.json` it says the project has no link adapter.
- With `link_unavailable` set it prints that reason and exits 7.

### report

- It prints progress, attribution, learning metrics, and early warning.
- It regenerates `OPEN.md` and checks `PATTERNS.md`.
- It prints one `claims:` line after the `status:` line.
  - The line lists each `claimed`, `bytes-match` or `matched` ticket with its claimant (`<id> <claimant>`, comma-separated), or `none`.
- It prints one `state:` line computed from ticket statuses.
  - `finished`: every in-scope ticket is `revalidated`.
  - `stuck`: not finished, and every remaining ticket is `blocked-reference` or `regressed`.
  - `more`: anything else.
- It prints one `milestone:` line.
  - It says `due` when the in-scope bytes of units fully matched reach the link milestone.
  - A unit is fully matched when every in-scope ticket is `integrated` or `revalidated`.
  - Units already in the last `link` event's `units` do not count.
  - Otherwise it says `not due`.
  - The line gives those bytes and the milestone size.
  - It never says `due` when `link_unavailable` is set.
- The milestone is `link_milestone` in `decomp.json`, mirrored in the contract's Tracking section.
- It is a percentage of the in-scope bytes (`"10%"`) or a byte count (`65536`), used as given.
- Without it, the milestone is 5% of the in-scope bytes with a floor of 16 KB (16384 B).

## Template search

A **template** is the unit's whole source file, `@decomp` marker included, with **choice points**, each listing alternative spellings of the text at that place.

- Keep the template file outside the project tree.
- The tool only combines alternatives the writer wrote.

| Macro | The choice point is |
| --- | --- |
| `PERM_GENERAL(a, b, ...)` | One of the alternatives |
| `PERM_VAR(@name, a, b, ...)` | As `PERM_GENERAL`; a later `PERM_VAR(name)` repeats the same pick |
| `PERM_VAR(name, a, b, ...)` | No choice point: a **paired use** of the earlier `PERM_VAR(@name, ...)`, its own alternative at the index that one picked |
| `PERM_ONCE(a, b, ...)` | Nothing, or one of the alternatives |
| `PERM_INT(lo, hi)` | One integer from `lo` to `hi` (at most 64 values) |
| `PERM_LINESWAP(lines)` | Its lines in every order (at most 5 lines) |
| `PERM_IGNORE(text)` | The text itself: no choice, a stretch the tool leaves alone |

### Alternatives

- Alternatives are split at the commas that sit inside no bracket, so an alternative holding a bare comma (`int a, b;`) is written another way.
- Surrounding white space is dropped.
- An empty alternative is allowed.
- A choice point inside a comment or a literal is not read.
- A choice point inside another, and any other `PERM_` macro, is refused.
- A template may hold at most 12 choice points.
- A file with no choice point is refused before any build.
- The message says a template needs a choice point and that a plain compile is `check`'s job.

### Paired use

- `PERM_VAR(name, a, b, ...)`, a name with no `@` followed by alternatives, makes a second place vary under the choice `PERM_VAR(@name, ...)` defined earlier: a loop header and the expression that depends on it, say.
- It holds as many alternatives as its definition, and is refused with both counts otherwise.
- One before its definition is refused, as `PERM_VAR(name)` is.
- It adds nothing to the space, the limit of 12, or the choice code.
- It takes no label, kind, or likelihood.
- Its alternatives may lead with a steering tag.
- A pick is steering when the definition's alternative or any paired alternative at that index is.
- Each steering place carries its own `fakematch:` comment in the winner.
- `PERM_VAR(@name)` with no alternatives is refused.
- The refusal names `PERM_VAR(name)` to repeat the pick and `PERM_VAR(name, a, b, ...)` to pair with it.

### Label and kind

- The first argument may be `@label kind` (for `PERM_LINESWAP`, a first line).
- The label names the choice point and must be unique.
- A label holds letters and underscores only, with no digits; a label with a digit is refused.
- The label defaults to `A`, `B`, and on, in file order.
- The kind is one of `decl-order`, `stmt-order`, `loop-form`, `temp-type`, `signedness`, `width`, `operator`, `expression-shape`, `branch-order`, `inlining`, `other`.
- The kind defaults to `other`, and to `stmt-order` for `PERM_LINESWAP`.

### Likelihood

- An alternative may start with `%0.7`: the writer's likelihood that it is right.
- Without likelihoods, all alternatives are alike.

### Natural and steering

- An alternative is natural unless it leads with `/* steer: <why> */`.
- A steering alternative carries its reason.
- The reason may hold commas, not `*/`.
- An empty reason is refused.
- The tag and a likelihood come in either order.
- `PERM_INT` and `PERM_LINESWAP` take no tag.
- `search` refuses a template holding a steering alternative, building nothing, when `fakematch` is `forbidden` in `decomp.json`.
- At equal likelihood a natural alternative is tried before a steering one.

### Choice code

- Alternatives are numbered from 0.
- A candidate is one alternative per choice point, named by its choice code: `A1 B0`.
- All zeros is the baseline.

### A round

- `search` needs `template_search` to be true in `decomp.json` and [the gate](#the-gate) open, and refuses, with the reason, otherwise.
- It builds each candidate in a scratch copy of the unit's folder layout.
  - The candidate sits at the unit's own path.
  - The headers the template includes sit beside it.
- It runs the adapters from the current worktree as `check` does.
- It scores each candidate with the `diff` adapter's `differ_bytes`, breaking ties by its optional `first_differ` (later is better).
- A candidate the guardrail scan refuses, or with no single marker, is not built.
- A round tries the baseline first, then every one-choice-changed candidate, then the rest of the space.
- Each group goes most likely first (with several workers, candidates are handed out in that order and finish in any).
- When the rest does not fit the block's budget, it is sampled instead (see [Sampling](#sampling)).
- A choice point whose alternatives all give the baseline's object is **inert**: it is frozen at its first alternative.
  - The freeze is a guess made at the baseline, so it is tried again wherever the code changes.
  - The first time a candidate gives an object the block has not seen, the block owes one retry per other alternative of every choice point then frozen.
  - A retry is that candidate with the one choice point set to the one alternative, and nothing else changed.
  - Owed retries are handed out before the next candidate of the rest of the space, in the order the objects appeared.
  - A retry that gives that candidate's object again leaves the choice point frozen.
  - A retry that gives anything else (another object, a build failure, a guardrail refusal) unfreezes the choice point for the rest of the block.
  - The candidates that vary an unfrozen choice point join the rest of the space, and the retries still owed for it are dropped.
  - A retry is a candidate like any other: it counts in `compiled` and toward the budget, the deadline and the plateau.
  - A choice point is not tried again against a candidate whose object the block has already seen.
- The round stops at the first exact match that uses only natural alternatives.
- A match that needs steering is kept while the rest of the block looks for a natural one.
- When the block ends without a natural match, the match with the fewest steering choices is reduced further.
  - Each steering choice is flipped to a natural alternative where the candidate still matches.
- The `winner` is written as plain C with a `/* fakematch: <why> */` comment appended to each line of each surviving steering alternative.

#### Likelihood from closeness and history

- Closeness to solved functions raises a likelihood.
- An alternative written as one of the 3 matched functions `similar` ranks closest is written has its likelihood multiplied by 1 plus that function's closeness.
- "Is written" means the same keywords and punctuation, any names and numbers, two tokens or more.
- That does not apply when every alternative of its choice point is so written.
- The candidates for those 3 are the tickets `ledger/matches.jsonl` names that are still matched.
- `search` reads those ticket files and no other, so its cost does not grow with the open tickets.
- Project history raises a likelihood too.
- At each round start the attempts ledger is read for the template rounds `verify` recorded on this compiler.
- Each time a kind fixed the ticket's latest category raises that kind's alternatives other than the first.
- No file holds the history.

### A block

- A round runs its candidates as one block, on worker threads.
- The candidates after the one-change sweep wait for its last result, which settles the inert choice points.
  - They do not wait once the round has no object identity: from the first diffed result without `function_sha256` (with hashing on the function's bytes), no choice point can be frozen, so every free worker takes the next candidate.
- Each worker drives one adapter process at a time in its own scratch folder.
- The scratch folder's file names are fixed and overwritten per candidate (an overwrite retries briefly on a file another process still holds).
- A worker takes its next candidate only when it is free.
- `search` starts the `build` and `diff` adapters without the host's shell.
- It falls back to the shell for a command that needs it.
  - A character the shell reads (`%VAR%`, `&&`, a redirection).
  - A program that is no executable file (a `.cmd` or `.bat` tool, a shell builtin).
- `check`, `verify`, and `link` keep the shell.
- An adapter run that takes longer than 10 times the median compile time is killed with every process it started, and counts as a build-fail.

### Sampling

- The block's budget is the compiles it is expected to fit: its compile rate over the one-change sweep, times the seconds its deadline leaves.
- A block served wholly from the cache has no rate, and tries the whole space.
- Sampling applies when the candidates left after the sweep, inert choice points frozen, outnumber the budget left.
  - It is judged again when a choice point is unfrozen, which then is free for the sampler, mutation and crossover.
  - Owed retries are handed out before the sampler's next pick.
- Then the tool picks them one at a time, each from every result in so far.
- Each alternative holds a belief that it helps.
  - It starts at the alternative's share of its choice point's likelihoods (history and closeness included).
  - A steering alternative counts 0.9 of a natural one, so at equal likelihood the natural one ranks above it.
  - The starting belief weighs 4 results.
  - A scored candidate moves the belief of each alternative it holds by how far its `differ_bytes` fall below the baseline's or rise above.
  - A candidate that does not build counts as the worst.
- The first pick is the likeliest untried candidate.
- After it a pick is Thompson sampling: one random draw from each belief, the highest draw of each choice point taken.
- At least 20 percent of the picks are exploratory instead.
  - They are uniform at random, never the candidate of every top-ranked alternative.
  - Of 8 such draws, the one holding the most pairs of alternatives no tried candidate held is taken.
  - A pair that only helps together is so reached when the likelihoods point away from it.
- With a budget under 100 compiles, the sampling opens with a pairwise covering sample.
  - It is candidates that, with the sweep's, hold every pair of alternatives of two choice points, likeliest first.
  - It is skipped when the alternatives make more than 4000 pairs.
- No candidate is picked twice, and each is built only from the template's alternatives.
- The random generator is seeded from the block constants, so with one worker the order is the same on every run.

### Learning across rounds

- At the end of a round the tool keeps each choice point's beliefs as likelihoods, in the ticket's search folder (`learned.json`).
- They are the starting beliefs above moved by that round's results.
- They are scaled so that the largest of a choice point is 1, and rounded to 6 places.
- **Floor:** no likelihood a round learned is kept below 0.01, so an alternative that hurt every round goes last and is still tried.
- **Frozen:** a choice point that is inert when the round ends learns nothing from that round.
  - Its entry holds the likelihoods it began the round with: what the last round learned, or the writer's.
  - Every candidate after the sweep holds its first alternative, so the results say nothing about that alternative.
- A choice point that was free learns from every candidate of the round.
- A choice point the next template **keeps** starts from those likelihoods in place of the writer's.
- **Reading:** a kept likelihood that is zero, negative, not a number, or not finite is read as the floor, 0.01.
  - So a `learned.json` an older tool wrote a zero into stops no search.
- A choice point is kept when it has the same label, and the same kind, alternatives, likelihoods, and steering tags as the writer wrote them.
- A choice point that is new or edited starts from its priors.
- A round that scored no baseline keeps the earlier ones.

### Mutation and crossover

- A later block of a template (a round on a ticket that already has a kept round) also builds candidates from the best distinct objects of the earlier block, up to 4.
- Those parents are carried by choice label and alternative text.
- A choice point or alternative that was rewritten takes its first alternative.
- **Mutation** changes 1 or 2 free choice points of one of them to another alternative the writer wrote.
- **Crossover** takes each free choice point's alternative from one of two of them.
- Both are built only from the template's alternatives, and never repeat a candidate.
- Both fall back to the sampling above when 24 draws find none new.
- A bandit shares the picks between the sampling, mutation, and crossover.
  - Each starts with a share of 2, 1, and 1 parts.
  - A sampler's share then follows its gain per pick.
  - The gain is how far its candidates brought the best `differ_bytes` down, as a share of the best at the time.
  - Recent picks count most.
  - Every sampler keeps at least 10 percent of the picks.
- A template's first block has no parents and only samples.
- A block that used parents adds `arm_picks` to `counts`.

### Slot pool

- Every search on this machine shares one pool of compile slots, `.decomp/slots/`, so concurrent writers never run more builds at once than the pool has slots.
- The pool has one slot per physical core.
  - The platform's count is used, or the logical count when the platform's call fails.
  - Or `workers` slots when that is set higher.
- A worker holds a slot only while its build runs.
- `<n>.slot` names the search holding slot n.
- Each running search keeps a heartbeat, `<name>.writer`, renewed every 2 seconds.
- A slot whose holder's heartbeat is gone or older than 30 seconds is reclaimed.
- The searches with a fresh heartbeat are the active writers.
- A search starts with the cores divided by the active writers as its worker count.
- A search holds no more than the slots divided by the active writers (rounded up) at once.

### Tuning

- A block changes its worker count as it runs, unless `workers` is set.
- The count stays between the floor and the search's share of the pool.
- The floor is half the starting count, at least 1.
- Every 2 seconds (the tuning tick) the block compares its unique compiles per second with the tick before.
  - The first judged tick adds a worker to try.
  - A gain above 5 percent adds another.
  - A loss above 10 percent, or a p95 compile time above 2 times the tick's median, takes one back.
  - In between it holds.
- A tick with fewer than 2 compiles per worker is judged together with the next.
- The tick after a cut only sets the new base.
- A count the block gave up is not tried again for 10 ticks.
- Workers above the count wait.
- `abort-buildfail` and the hang limit keep using the starting count.

### Reference compile

- Every 30 seconds the block recompiles its reference candidate, the baseline, in a folder of its own, holding a compile slot like any build.
- Its base is the median of the block's first 2 × workers compile times.
- When the block built nothing before it, the base is the first reference compile.
- Under batching a compile time is a call's time shared among its candidates, so the base is the first reference compile instead.
  - It is made as the block begins, and a failed one gives no base: the next that passes becomes it.
- A reference compile more than 30 percent over the base halves the worker count, down to the floor.
- It also raises `contention-or-throttle` in the [performance log](#performance-log).

### How a block ends

A block ends on the first of these that holds:

- `match`: a candidate matches exactly with natural alternatives only.
  - A block that ends another way while it holds a match that needs steering also reports `match`, with that match reduced.
- `abort-buildfail`: more than half of the first 2 × workers builds failed. Fix the template.
- `exhausted`: every candidate was tried, or more than 90 percent of the last 100 candidates repeated a source already tried.
  - A block that finished its last pass (see `deadline`) ends here.
  - It is reported only when no retry of a frozen choice point is owed (see [A round](#a-round)).
  - So every candidate was tried, or was left out by a freeze that held against every object the block found.
  - A block whose deadline or plateau comes with retries owed ends on that reason.
- `plateau`: the last 200 scored candidates, and no fewer than a quarter of all scored in the block, brought no new best score and no new object.
  - It is no new best score alone when the round has no object identity: see [Result cache](#result-cache).
- `deadline`: the block ran for 10 seconds and built 200 candidates, or reached its ceiling first.
  - The ceiling is the time since the ticket's last round ended on this machine (the model's latency), and never more than 60 seconds.
  - A block with the `budget` constant set also ends here once it built that many candidates.
  - The last pass: when the deadline comes with no more candidates left in the space than the block runs workers, the block does not end here.
  - It hands them out, waits for them, and ends `exhausted`, so it leaves no background search.
  - Owed retries count among the candidates left.
  - A last pass that brings a new retry or unfreezes a choice point does not build what that adds, and ends `deadline`.
  - Plateau and repeats do not end a last pass.
  - A match and a hung compile's kill still apply, so the overrun is the compile in hand plus the last pass, or the hang limit at most.
  - Under batching a worker starts no batch once the deadline has come, unless it is in the last pass.
  - So the overrun is one batch: its compiler call and the diffs of its candidates.

### Background search

- When a block ends on `plateau` or `deadline` with time left under the ceiling and candidates untried, `search` prints its summary, with `continues_s`.
- It leaves a detached process searching the same template on for that many seconds.
- That process builds only what the round has not tried.
- Its block freezes, retries and unfreezes by the same rule (see [A round](#a-round)), judged from the results the round already holds.
- It ends on a match, its time, or the end of the space.
- It is no attempt.
- It yields to foreground blocks.
  - No foreground search counts it as a writer.
  - It starts no build while any foreground search on this machine has a fresh heartbeat in the pool.
  - A block has its slots back within one compile, or within one batch under batching.
  - It starts no build once its time has come or it was stopped, whether it waits on the foreground or holds a slot: a build in hand runs to its end.
  - A search whose time ended while foreground searches were beating starts no build and ends with the line `ended: deadline, waited its whole budget on the foreground: <their names>, no build started`.
  - Its report then holds `waited_on_foreground: true`, and no other report holds that field.
  - Its `tried` is 0, so its log is kept (see below).
- Under batching it starts no batch once its time has come or it was stopped.
- The call that started it is the one exception: that call left the pool before it started the search.
- So a heartbeat still under its name is one it failed to remove, and the search does not wait on it.
- A call that cannot remove its own heartbeat as it leaves the pool does not fail.
  - It keeps a line with the heartbeat's name and the error.
  - The background search it then starts copies that line into its log, at its start.
- The next `search` call for the ticket stops it and reports it under `background`.
- A call that collected it and then prints no summary still prints the report.
  - It is one JSON line on standard output, `{"background": <its report>}`, the shape `search <id> --stop` prints.
  - This covers a refusal (a closed gate, an unreadable template, no choice point, a misspelt block constant, a forbidden steering alternative).
  - It also covers an error nothing caught.
  - The error message and the exit code are as they would be without the line.
  - The search's files are gone by then, so no later call could print the report.
  - `end`: how it ended: a block's end reason when it ended by itself, or one of the three below.
  - `stopped`: the call cut it short while it was working.
  - `killed`: it would not go within the stop's bound, or it was still alive after its budget plus that bound.
  - `error`: it died.
  - `error` (the field): only with `end: error`, the error's text, or that the process was gone and left no report.
  - `overrun`: `true`, only when it was still alive after its budget plus the stop's bound.
  - `ran_s`: the seconds from its start to its collection.
  - `budget_s`: the seconds it was given.
  - `tried`.
  - `waited_on_foreground`: `true`, only when the search started no build because foreground searches were beating until its time ended.
  - `best`: the fewest differing bytes, then the lowest seed, among the candidates it tried, named in the old template's choice codes.
- When `tried` is 0, the report also holds `log`.
  - The search's log is kept as `.decomp/search/<ticket id>/background.log`, in place of the last kept one.
  - A search that tried candidates keeps none.
- The kept log holds the search's own lines: when it started, when it was ready, which foreground searches it waited on, how it ended.
- The kept log holds any error the search died of: a `died of an error:` line, then the traceback of an error nothing caught.
- The kept log ends with a `collected:` line of what the collecting call saw.
  - It holds `ran_s` and `budget_s` as the report does.
  - It holds `died`: whether the search's process was gone, with no report written, before any kill.
- Its results join the kept round, so `--detail` serves them until a new round replaces it.
- When it found a match, the report holds `winner` and `natural`, and `verify --template-round` records that match.
  - That `winner` is `.decomp/search/<ticket id>/winner-background/<source file name>`.
- When the match is natural, the call searches nothing.
  - It prints the old template's summary with `end: match`, the `winner`, and `discarded` in the report.
  - It drops the new template and adds no attempt.
- `search <id> --stop` and `release` end it too.
- Stopping kills it with every process it started: its Job Object on Windows, its process tree's groups elsewhere.
- Stopping works only while its heartbeat file is fresh, since liveness is read from that file and never from a process signal.
- The kill is asked for at once.
- The stop then waits for the search's process to be gone, for no longer than 10 seconds from its start.
- A process still there then is killed once more, by its process tree.
- A search whose process is already gone is not killed: the stop reports it as `error`.
- The stop returns what the search had written.
- It inherits no standard handle, so the call that started it returns at once.
- Its output goes to `background/log`, which is removed with the folder when the search is collected, unless it is kept as above.

### Block constants

Each number above is a default.

- `"search"` in `.decomp/local.json` overrides any of them for this machine.
- `search` refuses any other key.
- `workers`: 0, the default, is the physical cores divided by the active writers.
- `cores`: 0 asks the platform.
- `slots`: 0 is the cores.
- `slot_heartbeat_s`: 2.
- `slot_stale_s`: 30.
- `background`: 1; 0 never leaves a background search.
- `deadline_s`: a fixed deadline in place of the floor and ceiling; 0 is off.
- `floor_s`, `floor_compiles`, `ceiling_s`, `plateau_compiles`, `plateau_frac`, `buildfail_frac`, `repeat_window`, `repeat_frac`, `hang_factor`.
- `hang_floor_s`: 5; no run is killed sooner.
- `hang_start_s`: 120; the limit until 2 × workers compiles are timed.
- `lock_retry_s`: 2.
- `budget`: the block's budget in compiles, in place of the measured one; 0, the default, is off.
- `seed`: 0; seeds the sampling's random generator.
- `probe_gain`: 0.05; the share by which a calibration probe's mode must be faster to be kept.
- `probe_runs`: 2; the builds a probe times of each mode, of which the fastest counts.
- `probe_min_chars`: 2000; the least body text, in characters, the single-function probe must be able to cut to run; an estimate, not measured.
- `tune_s`: 2; the tuning tick; 0 keeps the starting worker count.
- `tune_gain`: 0.05.
- `tune_loss`: 0.1.
- `tune_spread`: 2.
- `reference_s`: 30; the reference compile's interval; 0 is never.

### Calibration probes

- With no kept answer for the ticket, `search` probes three faster ways to build before the first block.
- Each probe runs on the baseline.
- A probe is kept only if it is faster and byte-identical.
- Byte-identical means the same object file.
- Where `hashing` is `function`, and for the single-function build, it means the same function bytes.
- The function bytes are the `diff` adapter's `function_sha256`, or without it the diff's result, counts, and report together.
- Each probe writes one calibration record to the [performance log](#performance-log).
- The answers are kept in the result cache until something the cache key covers changes.
- Those are the source outside the target function, the `build_batch` or `build_resolve` command, or anything else the cache key covers.

#### Single-function build

- The candidate is built with the body of every other marked function cut away.
- A body is found with the lexer and the `@decomp` markers, with no C parser: the first brace pair after a marker.
- A cut body becomes `;` (an endless loop for a member function), and its line breaks stay.
- A function is left whole where that reading is not certain.
  - Something other than a function's head stands between marker and brace.
  - The braces do not close.
  - The body holds a preprocessor conditional.
- Unmarked functions stay whole.
- It is skipped when there is nothing to cut.
- It is skipped when the bodies it would cut hold fewer characters together than `probe_min_chars`.
- The time a cut saves follows the amount of code cut, whatever the unit's headers cost, so the build pair is not spent where it cannot win.
- The record's `reason` names the count.
- The default of 2,000 characters is an estimate and has not been measured.
- Changing which side of it a unit falls on probes again.
- The probe compares the baseline only, so a match found under this build is built once more as the full unit.
- When that does not hold, the build is dropped for the ticket and the block runs again on the full unit.
- Its results are cached apart from the full unit's.

#### Batching

- It needs a `build_batch` adapter (see [Adapters](#adapters)).
- One compiler call builds 4, then 8, then 16 copies of the baseline.
- A size is kept while every object equals the single build's and the time per candidate keeps falling.
- A size that changes the bytes drops batching.
- A worker then takes up to that many candidates at a time, builds the unseen ones in one call, and diffs each as before.
- A candidate whose object is missing after the call is a build-fail.
- It is skipped without the adapter.

#### Resolved compiler

- It needs a `build_resolve` adapter.
- The probe runs the compiler from the argument list and environment the adapter hands over, with no adapter and no wrapper in between.
- It records `eligible` when that is faster and byte-identical.
- It is measured only: no block builds this way, because it departs from the wrapper rule, and adopting it needs an ADR.
- It is skipped without the adapter.

### Summary

The summary is one JSON line, capped at about 600 tokens, that never holds candidate source.

- `end`: why the block ended (see [How a block ends](#how-a-block-ends)).
- `best`: the closest candidate's `code` and `differ_bytes`, or `null` when none was scored.
- `window`: 7 lines of the best candidate's diff report (no match only).
  - When the `diff` adapter reports `first_differ`, the window is centred on the report line whose own offset is the greatest one not above it, with 3 lines of context each side.
  - Of several lines with that offset, the first in the report is the centre.
  - Without `first_differ`, with no line offset, or with every line offset above it, the window is the report's first lines.
  - Otherwise, or when no line holds it, it is the report's first lines.
  - A report line longer than 120 characters is cut inside that width and ends in ` ...`, so a line without the mark is whole.
  - When the report holds fewer than 2 lines, `notice` gains one line.
  - In full, that line starts with `no-instruction-diff:`, says the diff report holds no instruction diff, and says the fix is the `diff` adapter (see its contract under [Adapters](#adapters)).
  - Once the ticket has read it in full, the line is the name `no-instruction-diff` alone (see [Adapter notices](#adapter-notices)).
- `failure`: the end of the first failure log (only when none was scored).
- `effects`: the choice points that change the score, at most 8, largest first, each with its alternatives' change in differing bytes against the baseline (`{"B": {"B1": -2}}`).
- `inert`: the choice points still frozen when the round ended, each as `"<label>: <n> of <m> objects"`.
  - `m` is the round's distinct objects, and `n` is how many of them the freeze was tried against and held, the baseline's included.
  - `n` is below `m` only when the block ended with retries owed.
  - A choice point is safe to leave out of the next round when `n` equals `m`, and is worth another round when it does not.
  - A choice point unfrozen during the block is not listed: it is a free choice point when the round ends.
- `next`: the next two closest candidates, each as the choices where it differs from the best, then its `differ_bytes`.
- `pairs`: at most 3 pairs of alternatives whose joint effect differs from the sum of their single effects, largest first, such as `B2+D2: -6 bytes`.
  - Negative means they help more together than apart.
  - It is an estimate over every scored candidate.
  - It is the mean `differ_bytes` of those holding both, less those holding only one, less those holding only the other, plus those holding neither.
  - It appears only when a pair shows one.
- `stop`: advice to stop.
  - It is given when every choice point is inert (no alternative changes the object) and every `inert` entry holds all of the round's objects.
  - It is given after 2 template rounds in a row that brought no new best score.
  - A round brings a new best score when it is lower in `differ_bytes` than every earlier attempt on the ticket, checks included.
  - A repeat is no round here.
- `history`: one line of project history for the ticket's latest category, such as `decl-order fixed register-allocation 7 of 9 times on this compiler` (only when the ledger holds a template round for it).
  - A match by the baseline records no kind, so the history counts nothing for it.
- `counts`: the numbers of the round, listed below.
- `winner`: on a match, the path of the matching candidate as plain C with no macros: `.decomp/search/<ticket id>/winner/<source file name>`.
  - The next round of the ticket that matches replaces it.
- `continues_s`: only when the round left a background search running: the seconds it may run.
- `repeat`: `true`, only when the round is a repeat.
  - A repeat is a round where every candidate it tried was served from the result cache.
  - Nothing was built and nothing newly scored (`compiled` is 0), as when an unchanged template is run again.
  - A repeat is no attempt: it adds no record to the check trail, does not count towards the `stop` advice, and starts no background search.
  - A round that builds even one candidate is not a repeat.
- `background`: only when the call collected a background search: its report (see [Background search](#background-search)), with `log` when it tried nothing.
  - The cap never drops `background`.
  - The cap applies to the whole printed line, `background`, `repeat` and `continues_s` included: the other parts give way, in the order above.
  - The same holds for the summary a collected natural match prints.

#### Counts

- `space`: candidates in the template.
- `compiled`: built this round.
- `build_fail`.
- `guardrail`.
- `src_dedupe_hits`: candidates whose source was already seen this round, never built twice.
- `cache_hits`: candidates served from the result cache without building.
- `object_hits`: built, but the object or function bytes were already scored.
  - Under `object` hashing a hit skips the diff.
  - Under `function` hashing the diff adapter still runs on a hit, since the function's bytes are known only from its output; a hit then means only that those bytes were already scored.
- `unique_objects`: distinct objects scored.
- `hashing`: `object`, or `function` when the compiler's objects differ between two compiles of one source.
- `workers`: the count the block started with.
  - It is the cores divided by the active writers, unless `workers` is set.
  - At its first heartbeat the search counts the writers again.
  - A higher count becomes its starting count: `workers` is cut to the cores divided by it when above that, and the tuner's floor follows.
  - A lower count changes nothing, and neither does a block that ends before its first heartbeat.
  - A set `workers` is never cut.
- `wall_s`: the block's seconds: the time candidates were tried, without the calibration before it.
- `call_s`: the seconds of the whole `search` call, from its start to the summary.
  - It covers calibration, probes, and the block.
  - It is never smaller than `wall_s`.
  - It is the number to compare with what the writer waited.
- `collect_s`: the seconds of the call spent collecting the ticket's background search: stopping it and taking in its results.
  - It is part of `call_s`, so a call far longer than its block names this part when it was the long one.
  - It is near 0 when the ticket had none.
- `killed`: adapter runs killed as hung.
- `shell`: adapter runs that needed the shell.
- `single_function`: whether candidates were built as the single-function source.
- `batch`: candidates per compiler call; 1 is no batching.
- `writers_active`: searches running on this machine when the round started, this one included.
  - A higher count at the search's first heartbeat replaces it, so two searches started together report the same count.
  - A set `workers` still corrects `writers_active`.
- `slots`: the pool's size.
- `slots_reclaimed`: slots taken back from a search that stopped beating.
- A block that sampled adds these:
  - `budget`: the compiles the block was expected to fit.
    - It is an estimate made once, when sampling began, from the compile rate until then and the time the block had left.
    - The block does not end on the estimate, and `compiled` can pass it.
    - Only a `budget` set in the block constants ends the block.
  - `pairwise`: candidates of the covering sample.
  - `sampled`: picks after it.
  - `explored`: the exploratory ones among those.
- A later block adds `arm_picks`: the picks of each of `sample`, `mutate`, and `cross`.

### Result cache

- Scores are kept in `.decomp/search-cache.json`, on this machine only and never committed, across rounds and sessions.
- A key covers these:
  - The compiler.
  - The build and diff commands.
  - The tree's `tools/`.
  - The expected bytes.
  - The symbol map.
  - The headers beside the unit.
  - The candidate's source or object hash.
- At the start of a round with no kept answer, the tool compiles the baseline twice in two folders, a second apart.
- When the objects differ (a timestamp or a path) it hashes the function's bytes instead.
- The `diff` adapter may print `function_sha256` (a hash of the function's bytes under the relocation policy) beside `match` and `differ_bytes`.
- Without `function_sha256` only the source layers dedupe.
- The round then has no object identity.
  - `unique_objects` and `object_hits` are `null` (unknown, not zero) in the summary's `counts`.
  - `unique_objects` is `null` in the block's performance record.
  - No choice point is frozen as inert.
  - The `plateau` rule rests on the best score alone.
- The summary's `notice` list says so in one line.
- In full, that line starts with `no-object-identity:` and names `function_sha256`, the diff adapter, and `/decomp-setup`'s upgrade as the fix (a contract change).
- Once the ticket has read it in full, the line is the name `no-object-identity` alone (see [Adapter notices](#adapter-notices)).
- No identity is derived from the score or the report in its place.

### Not a match claim

- A `match` is a search result.
- The writer copies the winner into the unit and still passes `check`, `verify`, and the audit.

### Check trail

`.decomp/trail.jsonl` holds one JSON line per `check` run and per template round.

- It is for this machine only: it is never committed, and every worktree of the checkout shares it.
- The committed ledger still gets one record per writer return, through `verify`.
- Fields: `unix`, `ticket`, `by` (`check` or `search`), `result`, `differ_bytes`, `category`.
- A `check` records the `--category` it was given, `build-fail` when the build failed and none was given, and no category on a match.
- A template round records its best candidate's `result` and `differ_bytes`, and the category of the attempt before it.
- A run that exits 6, a refused `check` or `search`, and a `search` round marked `repeat`, add nothing.

### Adapter notices

Two notices in the summary's `notice` list come from the `diff` adapter: `no-object-identity` and `no-instruction-diff`.

- Each has a full form and a name form.
- The full form is the sentence, starting with the name, and carrying the fix.
- The name form is the name alone: it means the notice stated earlier in the ticket still holds.
- The first round of a ticket in which a condition holds states its notice in full.
- A later round of the same ticket in which it holds names it.
- A round in which a condition does not hold clears that notice's record, so the next round that meets it states it in full.
- `release` clears both records with the ticket's other round state.
- Another ticket starts with no record, so it reads each sentence in full.
- A record is kept on this machine only, with the ticket's round state.
- A repeat round states by the same rule and changes no record.
- The summary of a collected background match follows the same rule.
- The summary cap never drops a notice, in either form.
- The speed notices are no part of this: each shows once per streak (see [Flags](#flags)).

### Performance log

`.decomp/perf.jsonl` holds one JSON line per search block and one per calibration.

- A calibration is the start-of-search double compile that tells whether objects repeat, or each [calibration probe](#calibration-probes).
- It is for this machine only: it is never committed, and every worktree of the checkout shares it.
- Timings are facts about this machine, so they go in neither `attempts.jsonl` nor `events.jsonl`.

#### Every record

- `kind`: `block` or `calibration`.
- `unix`.
- `ticket`.
- `compiler`.
- `wall_s`: the seconds of the block alone, or of the calibration alone.
- `t_ref_ms`: the median of the block's reference compiles.
  - Without one, it is the first passing compile of the block, or of the calibration.
  - Under batching it is always a single build's time, so `null` without a reference compile.

#### A probe's calibration record

- `probe`: `single-function`, `batching`, or `resolved-compiler`.
- `outcome`: `kept`, `dropped`, or `skipped`.
  - `eligible` stands in place of `kept` for the resolved compiler, which is never used.
- `reason`.
- A `skipped` record is written once per ticket, probe and reason: the log already holding one says the same.
  - A skip for another reason is written, and so is every record with another outcome.
- `t_ref_ms`: a build the usual way.
- `t_probe_ms`: the probed mode, per candidate.
- `identical`: where bytes were compared.
- For batching: `batch`, the size kept (1 for none), and `sizes_ms`, per candidate, by size tried.
- The double compile's record holds no `probe`.

#### A block record

- Every number is rounded where it is written: milliseconds to 2 places, seconds and shares to 3.
  - That covers the median and p95 compile times.
- `unit`, `round`, `block`.
- `repeat`: `true` on the record of a repeat, a round served wholly from the result cache; a counted round's record has no such field.
  - A repeat's `round` is the number of the last counted round, the one it repeated.
  - A repeat takes a `block` number like any block, and its `model_latency_s` is as measured.
  - A repeat does not write the ticket's round-end time, so the next round's `model_latency_s` runs from the last counted round.
- `call_s`: the seconds of the whole `search` call up to this record, calibration included.
  - It is never smaller than `wall_s`.
  - It is a little under the summary's `call_s`, which is taken at the call's end.
- `collect_s`: the seconds of the call spent collecting the ticket's background search, as in the summary.
- `workers_min`, `workers_max`, `workers_end`, `workers_floor`.
- `starved_frac`: the share of the block's time the pool could give it fewer slots than its floor.
- `t_ref_base_ms` and `t_ref_max_ms`: the reference compile's base and its slowest run, when one ran.
- `expanded`, `compiled`, `unique_objects`, `build_fail`, `killed`, `src_dedupe_hits`.
- `t_compile_p50_ms`, `t_compile_p95_ms`.
- `stage_ms`: totals for `expand`, `write`, `compile`, `compare`, `score`.
  - `compare` is the diff adapter run.
  - `score` is the scoring in the tool's own process.
- `idle_frac`: the share of the workers' time spent waiting for a candidate, counted up to the moment the block's last candidate was handed to a worker.
  - The wait for the sweep's results is part of it.
  - That wait is absent when the round has no object identity.
- `best_score_start`: the `differ_bytes` of the ticket's latest attempt before the block, from the check trail; `null` without one.
- `best_score_end`: the `differ_bytes` of this block's own best candidate; `null` when none was scored.
  - It is the block's best, not the ticket's, so it can be worse than `best_score_start`.
- `t_to_best_s`, `end_reason`, `model_latency_s`, `writers_active`.
  - `writers_active` is the corrected count (see the summary's `writers_active`).
- The `flags` it raised and those it `shown`.
- `unique_objects` is `null` when the round had no object identity (see [Result cache](#result-cache)).

#### Flags

- Flags compare a block with the earlier blocks of its own unit, taken from the last 20 block records of the same compiler: another unit's headers say nothing about this one's speed.
- `slow-compile`: raised when compiles per worker-second are down 30 percent or more against the median of those blocks, once 3 exist, so a unit's first blocks raise nothing.
  - A block that killed one or more compiles raises no `slow-compile`: a hang is not a slow machine.
  - In the streak such a block is passed over, like a block that could not measure.
  - Its rate is left out of the medians later blocks are compared with.
  - The other flags are unchanged.
- The next three read the block alone.
- `io-jitter`: its p95 compile time is above 3 times its own median compile time.
- `expander-starved`: `idle_frac` is above 20 percent.
  - Idle time after the last candidate was handed out does not count, so a small space that ends `exhausted` raises nothing.
- `scorer-bound`: the diff adapter run and scoring together, `compare` plus `score`, are above 20 percent of stage time.
- A block that built fewer than 2 candidates per worker raises none of these four.
- `contention-or-throttle`: raised when a reference compile ran more than 30 percent over the block's base.
  - It is also raised when the block's `t_ref_ms` is 30 percent or more over the median of the earlier blocks of the same unit among those 20, once 3 exist.
- `starved-by-writers`: raised when `starved_frac` is above one half.
- Every raised flag is logged.
- A flag raised in 3 blocks in a row is shown to the user once per streak, in the search summary's `notice` list.
  - A streak counts the earlier blocks of the same compiler and the same unit; a block of another unit is passed over.
  - For the four measured flags, a block that built fewer than 2 candidates per worker is passed over too: it neither adds to the streak nor ends it.
  - The tuner's flags count every block of the unit.
  - A block that could have raised the flag and did not ends the streak.
- A shown flag comes with its measured cost and the fix only the user can make, where there is one.
- The `no-object-identity` line (see [Result cache](#result-cache)) is no flag: it is shown in every round it holds, in full or by name (see [Adapter notices](#adapter-notices)).

### The gate

`decomp.py` decides from the ticket's tier and its check trail whether template search is open.

- `check` reports it as `search_open`, with `search_reason`.
- `search` refuses with that reason while it is closed.

The first rule below that applies decides:

1. Closed when `template_search` is false in `decomp.json`.
2. Closed for a TINY ticket.
3. Closed before the ticket's first `check` on this machine, and when the latest `check` matched.
4. Closed when the latest trail record's category is `reference-gap`, `data-layout`, `calling-convention`, `optimization`, `unit-order`, or `build-fail`: these need a stop or a report, which no template fixes.
5. Open when that category is `register-allocation`, `statement-order`, or `expression-shape`.
6. Open after 3 attempts with no fall in `differ_bytes`: none of the ticket's last 3 trail records is lower than the first of them, and the latest holds a count.
7. Closed otherwise.

## Change flow

Every change to a path a tag freezes (a contract change, a skill upgrade, an inventory redo, a new edition) takes these steps, in this order. The tag moves only after the change has been measured:

1. Make the change on a `c/<slug>` branch from the integration branch tip.
2. Run `python tools/decomp.py revalidate --candidate c/<slug>` and show the user the result.
   - The candidate's own tool, adapters, manifest, and contract judge it, and nothing is recorded.
   - Regressions inform the user's go-ahead and do not block it: a corrected flag breaks matches on purpose.
   - On exit 6, run it again on a machine that can build every matched ticket.
3. On the user's go-ahead, merge the candidate into the integration branch and move the tag that freezes the changed paths. Without it, delete the branch: nothing else changed.
4. Run a plain `python tools/decomp.py revalidate` on the integration branch. It records `revalidated` and `regressed`.

## Target editions

`toolchain.json`'s `target` lists the accepted editions, the probes that recognise one without a whole-file hash, and the editions known to be wrong. `doctor` tries, in order:

1. A whole-file SHA-256 (and size) equal to an accepted edition's: pass.
2. A whole-file SHA-256 equal to a known-wrong edition's: fail, printing its name and its message.
3. The probes. Each is a file offset, a length, and the SHA-256 of that range: never target bytes, never a virtual address.
   - Offsets are into the target file as it sits on disk.
   - So when the product ships its code compressed or encrypted, the contract's target is the unpacked image.
   - An edition that declares `probes_needed` is accepted when at least that many probes match.
4. Otherwise fail, printing how many probes matched out of how many.

- An edition's `differs` lists the functions it holds differently from `expected/`, each by address, or by key where an address names more than one.
- A `target` holding only `sha256` and `size` is one accepted edition.

## Adapters

`/decomp-setup` writes these for the project's format and toolchain.

- Each is a command in `decomp.json`, run from a worktree root, with `{placeholders}` filled from the ticket.
- Adapters are run only through `decomp.py` (`inventory`, `disasm`, `link`, and the commands that build and diff), never directly: that is what gives each one its environment.
- Every command also gets `{tools}` (the `tools/` folder of the tree being built) and `{python}` (the interpreter running `decomp.py`).
- A brace that is not a placeholder stays as written.
- `decomp.py` gives each one the target's path as `DECOMP_TARGET`.
- `decomp.py` gives each one each tool's folder as `DECOMP_TOOL_<NAME>` (the tool's `name` in `toolchain.json`, upper-cased).
- An adapter holds no absolute path and no lookup of `.decomp/local.json`.

- **inventory**: reads the target, writes `inventory.json` and `expected/`, and seeds `symbols.json` with what the target itself proves (exports, imports, any symbols present).
  - Shape: `{"units": [{"id", "source", "start", "end", "evidence"}], "functions": [{"address", "size", "unit", "scope", "offset", "evidence"}]}`.
  - `offset` is the file offset of the function's first byte in the target as it sits on disk, which `link` places it by.
  - A unit is linked from source only when each of its in-scope functions has an `offset`.
  - A function may add `key` (see Units and ids).
  - A function may add `expected` (its expected file, when not `expected/<key>.bin`).
  - `scope` is `in`, `library`, `compiler`, `asm-origin`, or `excluded`.
  - `size` follows the tier rule.
- **build** (`{source}`, `{unit}`, `{obj}`, `{compiler}`): compiles one unit with the contract's compiler and flags.
  - `{compiler}` is the tool name from `toolchain.json` that builds this unit: `decomp.json`'s `compiler`, or the unit's entry in `unit_compilers`.
  - Exit nonzero on failure, errors on stderr.
- **build_batch** (optional; `{sources}`, `{objdir}`, `{unit}`, `{compiler}`): compiles several candidates of one unit in one compiler call, with the same compiler and flags as `build`.
  - `{sources}` is the candidates' paths, each in double quotes, separated by spaces.
  - The sources sit in one folder and are named `<unit source stem>.<n><suffix>`, so take the unit from `{unit}`, never from a file name.
  - Each object goes to `{objdir}/<source file name with its suffix replaced by .obj>`.
  - A source that fails leaves no object; exit nonzero when any fails.
  - Only `search` uses it, and only after its probe showed it faster and byte-identical.
- **build_resolve** (optional; `{unit}`, `{compiler}`): prints one JSON line, `{"argv": [...], "env": {...}}`.
  - The line holds the argument list that compiles one unit as `build` does, with `{source}` and `{obj}` left in it for the candidate's paths.
  - The line holds the variables to lay over the tools' environment.
  - Only `search`'s resolved-compiler probe uses it.
- **diff** (`{obj}`, `{expected}`, `{id}`, `{source}`, `{report}`, `{symbols}`): finds the function after the `@decomp {id}` marker in the object.
  - It compares the function to the expected bytes under the contract's relocation policy.
  - It writes a readable instruction diff to `{report}`.
  - It prints `{"match": true|false, "differ_bytes": N}` on stdout (and may add `function_sha256`, see [Result cache](#result-cache)).
  - `{symbols}` is the path of the symbol map in the tree being built.
  - The JSON may also carry `first_differ`, the byte offset of the first difference (optional, a non-negative integer).
  - `search` uses `first_differ` to break ties and to place the diff window, and everything else ignores it.
  - The report holds one line per instruction, each leading with its offset in the function as a whole number (hex, `0x` optional, or decimal), on 32-bit and 64-bit targets alike.
  - Only the number a line leads with is its offset: after nothing but white space and punctuation (a diff mark, `+`, `0x`, a bracket). No other number on the line is read, and a line led by a word has none.
  - `0x` makes the reading certain. Without it the report is read as hex when any line's offset holds a hex letter, and as decimal otherwise.
  - `first_differ` may fall inside an instruction, such as in an operand or a displacement.
  - A report that prints both sides of a differing instruction may give both lines the same offset.
  - A disassembler prints 8-digit or 16-digit addresses by target, so an adapter that parses its output reads both widths.
  - A report of a header line alone is a fault in the adapter.
  - `first_differ` and `function_sha256` stay optional where the contract does not allow template search.
  - Where it does, `/decomp-setup` writes an adapter that prints both, and its pipeline check proves it.
- **disasm** (`{expected}`, `{address}`): prints the original function's disassembly.
  - `decomp.py disasm <id>` fills the placeholders from the ticket.
- **link** (`{plan}`, `{out}`): links one whole file with the contract's linker and linker flags and writes it to `{out}`.
  - `{plan}` is a JSON file: `{"objects": [{"unit", "source", "obj", "functions": [{"id", "address", "offset", "size"}]}], "blocks": [{"offset", "size"}], "output"}`.
  - Each object is a unit built by the `build` adapter, whose functions go at their file offsets.
  - Each block is a range of the target file, at `DECOMP_TARGET`, copied to the same offset.
  - Together they cover every byte of the target once.
  - Exit nonzero on failure.
  - Where the format or linker cannot place raw blocks at fixed offsets or reproduce the file's headers, there is no `link` adapter.
  - In that case `decomp.json`'s `link_unavailable` holds the reason, with its evidence in the contract.

- Every adapter and banner command invokes a tool through the one wrapper in `tools/`, which owns the environment, path conversion, and any compatibility layer.
- The one run outside the wrapper is `search`'s resolved-compiler probe, a measurement nothing is scored from.
- `decomp.py` reads a tool's output in whatever encoding the tool writes, so an adapter never depends on the host's.

## Symbol map

`symbols.json` is one JSON object. The tool passes its path to the `diff` adapter and reads nothing in it, so these are the conventions the adapter and `decomp-reference` share:

- **Global symbol**: its name as the object file spells it, to its address in the original: `{"_memcpy": "0x00412340"}`. An address is written the way `inventory.json` writes it, prefix included.
- **Symbol private to a unit** (a `static`, a compiler-generated label): `<unit>:<name>`, so two units' statics of the same name do not collide: `{"u0007:helper": "0x00418A10"}`.
- **Section of a unit**: `<unit>:<section>`, the address where this unit's part of that section sits in the original: `{"u0007:.rodata": "0x0051A2C0"}`. A relocation against a section symbol plus an addend resolves through it.
- **Base symbol**: an address the format's relocations are relative to (`_gp`, `_SDA_BASE_`) is an entry like any other.

## Default relocation policy

The `diff` adapter applies this unless the contract names a departure with its ADR.

- An **operand** here is the bits one relocation fills.
- On some architectures it is a whole address field.
- On others it is a bit-field inside one or two instructions (a high and low half, a branch displacement, an offset from a base register).
- The adapter computes what those bits would hold from the relocation's type and the symbol's address in the map, and compares that.

A relocated operand is never a free pass:

- **Excluded only when proven.** A relocated operand is left out of the byte comparison only when the relocation's symbol resolves, through the symbol map or through another function matched in the same object, to the address the original's operand refers to.
- **Unresolved symbol.** A symbol that resolves through neither makes the result `differ`. The report names the symbol.
- **Wrong target.** A symbol that resolves to another address than the original holds makes the result `differ`. The report gives the offset, the symbol, the address it resolves to, and the address the original holds.
- **One tolerance.** A string or floating-point literal whose bytes are identical at both addresses compares equal: which pooled copy the linker keeps is not decided by the source.
- **Exact extent.** The compiled function's extent equals the ticket's size, and every byte after it is padding. A candidate longer than the original never matches on a prefix.
