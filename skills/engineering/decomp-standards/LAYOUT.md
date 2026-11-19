# Project layout

A decomp project is its own private git repo. Nothing from the target binary, its bytes, or its reconstructed source ever goes into a public repo.

| Path | Holds | Written by |
| --- | --- | --- |
| `DECOMP.md` | The contract: target, compiler, flags, scope, policies, model roster | `/decomp-setup` only |
| `decomp.json` | The contract's machine-readable part (commands, guarded paths, the pragma and attribute allowlists, `template_search` and `fakematch` (the contract's template-search and fakematch rules, which `doctor` prints and stops without), the default compiler and each unit that names its own, `link_milestone` (see below), and `link_unavailable` when the target cannot be linked whole) | `/decomp-setup` only |
| `toolchain.json` | The accepted target editions (hashes, probes, the functions each holds differently), the known-wrong editions, host prerequisites, and each required tool (per host, where hosts differ): version banner, required files, source, size, hash, unpack steps | `/decomp-setup` only |
| `.decomp/` | This machine only, never committed: `local.json` (target path, user-installed tool folders), `toolchain/`, `downloads/`, locks, `link/` (the linked binary), `trail.jsonl` (the [check trail](#check-trail)), `search/<ticket id>/` (the ticket's last template round: its template, each candidate's score, and what `verify --template-round` records) | `/decomp-setup`, `decomp.py` |
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
- `events.jsonl`: `unix`, `ticket` or `ref`, `event` (`integrated`, `revalidated`, `regressed`, `rejected-repair`, `link`, `out-of-order` with a `reason`).
  A `link` event also holds `result` (`pass`, `mismatch`, or `fail` when a source unit did not build or the adapter failed), `edition`, `units` (the units linked from source), `source_bytes`, `in_scope_bytes`, and, once a file was linked, its `sha256` and `size`; a mismatch adds `first_differ`, the first differing file offset.

## Commands

Run from the project root: `python tools/decomp.py <command>`. `python` is the host's Python 3: where only `python3` exists, write that.

| Command | Does |
| --- | --- |
| `doctor` | Check this machine against `toolchain.json`: which edition the target is, each host prerequisite's version, each tool's required files and version banner. Prints the recognised edition, then the contract's rules from `decomp.json`: `template search: allowed` or `not allowed`, and `fakematch: forbidden` or `allowed`. Exit 6 on any difference; exit 1, naming the skill upgrade, when `decomp.json` lacks a valid `template_search` or `fakematch` |
| `contract-keys` | For the skill upgrade: read `DECOMP.md` and print the `decomp.json` keys its lines give, as one JSON line (`template_search`, `fakematch`). An old "Permuter:" line is read as the "Template search:" line. Stops when a line is missing or unclear |
| `provision [--tool <name>] [--force]` | Download each tool that has a source, compare size and SHA-256, then unpack it under `.decomp/toolchain/`. Checks the host prerequisites first. A file already in `.decomp/downloads/` is compared, and replaced only with `--force`. Never installs a host prerequisite |
| `inventory [--redo]` | Run the `inventory` adapter, after the full `doctor` checks. Once the `decomp-start` tag exists it refuses, naming the redo flow, unless `--redo` is passed. Pass `--redo` only with the user's go-ahead for an inventory redo, or in a throwaway clone, where it writes nothing to the project |
| `disasm <id>` | Print the original function's disassembly: run the `disasm` adapter with the ticket's expected file and address |
| `gen-specs`, `gen-tickets` | Write unit specs and tickets from `inventory.json`; existing status and notes survive |
| `next [--n N] [--first ID --reason TEXT]` | List ready tickets smallest first (tier, then size, then address). `--first` lists that ready ticket first and records an `out-of-order` event |
| `claim <id> --by <name>` / `release <id> [--to <status>]` | Take or give back a ticket |
| `check <id> [--category <c>]` | Writer's loop: build and diff in the current worktree. Records nothing in the ledger, and appends one record to the [check trail](#check-trail). `--category` is the writer's reading of the first difference, one of the mismatch categories (any other is refused before anything runs). Prints one JSON line: `result`, `differ_bytes`, `report`, `search_open` (whether [the gate](#the-gate) is open for this ticket), and `search_reason` |
| `search <id> <template file>` | One template round: try every candidate of a template and report the closest. See [Template search](#template-search). Refuses, with the reason, while [the gate](#the-gate) is closed. A round that ran is one attempt in the check trail. Records nothing in the ledger and writes nothing in the tree |
| `search <id> --detail '<choice code>'` | Print one candidate of the ticket's last round: a JSON line (`code`, `result`, `differ_bytes`), then its source as plain C. `result` is `not-tried` for a candidate the round did not reach |
| `verify <id> --model <m> [--category <c>] [--template-round]` | Rebuild the writer's branch in a clean worktree, compare bytes, record the attempt. `--template-round` marks the attempt as a template round: its evidence file gains one line, `template-round: ` then JSON holding the ticket's last round on this machine (`best`, the best candidate's choice code; `result`; `differ_bytes`; `kinds`, the kinds of the choice points where that candidate leaves the baseline; `category`, the trail's category the round worked on; `unix`). The fields of `attempts.jsonl` are unchanged. It refuses, recording nothing, when this machine keeps no round for the ticket |
| `audit <id> pass\|fail --auditor <m>` | Record the auditor's verdict; `pass` records the match |
| `integrate <id>` | Mark a merged match integrated |
| `revalidate [--ref <branch>] [--header <path>]` | Rebuild matched tickets on a ref (with `--header`, only those that include that header, directly or through another); nonzero exit on any regression. A repair ref may touch only `include/` and `symbols.json` |
| `revalidate --candidate <c/slug>` | Rebuild every matched ticket on a candidate ref, in a clean worktree of it, with that tree's own copy of `decomp.py`. Accepts only a `c/<slug>` branch, and takes no `--ref` or `--header`. Records nothing: no ledger line, no status change. Exit 0 when every match holds; nonzero, listing each `REGRESSED` ticket, when one does not. A ticket the integration branch holds matched and the candidate lacks is listed `REGRESSED` too. A ticket already `regressed` is not rebuilt and does not count |
| `note <id> <text>` | Append an attempt note to a ticket |
| `similar <id>` | Closest matched functions by byte pattern |
| `lock <name> --by <n>` / `unlock <name>` | Exclusive lock, used for shared header and symbol map repair. Locks and claims are shared by every worktree of the repository |
| `link` | Link the whole binary from the reconstructed source plus raw blocks of the target, after the full `doctor` checks. A unit links from source only when every in-scope function in it is `integrated` or `revalidated` and none is on the recognised edition's `differs` list; every other unit, every out-of-scope function, all data, and every other byte of the file is a raw block. Builds each source unit in a clean worktree of the integration branch, runs the `link` adapter, and compares the output with the target on this machine, the edition `doctor` recognised. Prints one result line: `link: pass` or `link: mismatch`, the in-scope code bytes from source over all in-scope code bytes, and the output path, `.decomp/link/<target file name>`. On a mismatch it prints the first differing file offset and its owner (`unit <unit> function <id>`, `header` before the first function's offset in `inventory.json`, or `raw block <start> to <end>`) and exits 4. Appends one `link` event and changes no ticket status. Without a `link` command in `decomp.json` it says the project has no link adapter; with `link_unavailable` set it prints that reason and exits 7 |
| `report` | Progress, attribution, learning metrics, early warning; regenerates `OPEN.md`, checks `PATTERNS.md`. Prints one `claims:` line after the `status:` line: each `claimed`, `bytes-match` or `matched` ticket with its claimant (`<id> <claimant>`, comma-separated), or `none`. Prints one `state:` line computed from ticket statuses: `finished` (every in-scope ticket is `revalidated`), `stuck` (not finished, and every remaining ticket is `blocked-reference` or `regressed`), or `more` (anything else). Prints one `milestone:` line: `due` when the in-scope bytes of units fully matched (every in-scope ticket `integrated` or `revalidated`) and not in the last `link` event's `units` reach the link milestone, else `not due`, with those bytes and the milestone size. It never says `due` when `link_unavailable` is set. The milestone is `link_milestone` in `decomp.json`, mirrored in the contract's Tracking section: a percentage of the in-scope bytes (`"10%"`) or a byte count (`65536`), used as given; without it, 5% of the in-scope bytes with a floor of 16 KB (16384 B) |
| `sync` | Push unit checklists and the progress issue to GitHub, when enabled |

`inventory`, `disasm`, `check`, `search`, `verify`, `revalidate`, and `link` run the `doctor` checks first and run no adapter when they fail. `check`, `search`, and `disasm` skip them while `toolchain.json`, the target, and the tools' files are unchanged since the last pass. Exit 6 always means the machine, not the source: no writer fixes it, and no attempt is recorded.

`check`, `search`, and `verify` also exit 6 for a ticket no result could count for on this machine: the recognised edition's `differs` list names it, or its unit's compiler is missing from `toolchain.json`, listed only for another host, or not provisioned. A compiler that builds only other units does not stop this one.

`revalidate` prints `SKIPPED` for each such ticket. On the integration branch it leaves that ticket's status alone and still exits 0. On a repair ref or a candidate ref it exits 6: a repair is accepted, and a candidate measured, only on a machine that rebuilt every match it could break. A candidate run with a skipped ticket exits 6 even when it also lists regressions.

## Template search

A **template** is the unit's whole source file, `@decomp` marker included, with **choice points**, each listing alternative spellings of the text at that place. Keep the template file outside the project tree. The tool only combines alternatives the writer wrote.

| Macro | The choice point is |
| --- | --- |
| `PERM_GENERAL(a, b, ...)` | One of the alternatives |
| `PERM_VAR(@name, a, b, ...)` | As `PERM_GENERAL`; a later `PERM_VAR(name)` repeats the same pick |
| `PERM_ONCE(a, b, ...)` | Nothing, or one of the alternatives |
| `PERM_INT(lo, hi)` | One integer from `lo` to `hi` (at most 64 values) |
| `PERM_LINESWAP(lines)` | Its lines in every order (at most 5 lines) |
| `PERM_IGNORE(text)` | The text itself: no choice, a stretch the tool leaves alone |

- **Alternatives.** They are split at the commas that sit inside no bracket, so an alternative holding a bare comma (`int a, b;`) is written another way. Surrounding white space is dropped, and an empty alternative is allowed. A choice point inside a comment or a literal is not read. A choice point inside another, and any other `PERM_` macro, is refused. A template may hold at most 12 choice points.
- **Label and kind.** The first argument may be `@label kind` (for `PERM_LINESWAP`, a first line). The label names the choice point and must be unique; it defaults to `A`, `B`, and on, in file order. The kind is one of `decl-order`, `stmt-order`, `loop-form`, `temp-type`, `signedness`, `width`, `operator`, `expression-shape`, `branch-order`, `inlining`, `other` (default `other`, `stmt-order` for `PERM_LINESWAP`).
- **Likelihood.** An alternative may start with `%0.7`: the writer's likelihood that it is right. Without likelihoods, all alternatives are alike.
- **Natural and steering.** An alternative is natural unless it leads with `/* steer: <why> */`, a steering alternative with its reason (the reason may hold commas, not `*/`; an empty one is refused). The tag and a likelihood come in either order. `PERM_INT` and `PERM_LINESWAP` take no tag. `search` refuses a template holding a steering alternative, building nothing, when `fakematch` is `forbidden` in `decomp.json`. At equal likelihood a natural alternative is tried before a steering one.
- **Choice code.** Alternatives are numbered from 0. A candidate is one alternative per choice point, named by its choice code: `A1 B0`. All zeros is the baseline.
- **A round.** `search` needs `template_search` to be true in `decomp.json` and [the gate](#the-gate) open, and refuses, with the reason, otherwise. It builds each candidate in a scratch copy of the unit's folder layout (the candidate at the unit's own path, with the headers the template includes beside itself), runs the adapters from the current worktree as `check` does, and scores each candidate with the `diff` adapter's `differ_bytes`, breaking ties by its optional `first_differ` (later is better). A candidate the guardrail scan refuses, or with no single marker, is not built. A round tries the baseline first, then every one-choice-changed candidate, then the rest of the space, each group most likely first. A choice point whose alternatives all give the baseline's object is **inert**: it is frozen at its first alternative and not varied afterwards. The round stops at the first exact match that uses only natural alternatives. A match that needs steering is kept while the rest of the template is tried for a natural one. When none turns up, the match with the fewest steering choices is reduced further: each steering choice is flipped to a natural alternative where the candidate still matches. The `winner` is written as plain C with a `/* fakematch: <why> */` comment appended to each line of each surviving steering alternative.
- **Summary.** One JSON line, capped at about 600 tokens, that never holds candidate source:
  - `end`: `match`, or `exhausted` when every candidate was tried without one.
  - `best`: the closest candidate's `code` and `differ_bytes`, or `null` when none was scored.
  - `window`: 7 lines of the best candidate's diff report (no match only). When the `diff` adapter reports `first_differ`, the window is centred on the first report line holding that offset, with 3 lines of context each side; otherwise, or when no line holds it, it is the report's first lines.
  - `failure`: the end of the first failure log (only when none was scored).
  - `effects`: the choice points that change the score, at most 8, largest first, each with its alternatives' change in differing bytes against the baseline (`{"B": {"B1": -2}}`).
  - `inert`: the labels of the frozen choice points.
  - `next`: the next two closest candidates, each as the choices where it differs from the best, then its `differ_bytes`.
  - `stop`: only when every choice point is inert; advice to stop searching this template.
  - `counts`: `space` (candidates in the template), `compiled` (built this round), `build_fail`, `guardrail`, `src_dedupe_hits` (candidates whose source was already seen this round, never built twice), `cache_hits` (candidates served from the result cache without building), `object_hits` (built, but the diff skipped because the object or function bytes were already scored), `unique_objects`, and `hashing` (`object`, or `function` when the compiler's objects differ between two compiles of one source).
  - `winner`: on a match, the path of the matching candidate as plain C with no macros, in a temporary folder outside the tree.
- **Result cache.** Scores are kept in `.decomp/search-cache.json`, on this machine only and never committed, across rounds and sessions. A key covers the compiler, the build and diff commands, the tree's `tools/`, the expected bytes, the symbol map, the headers beside the unit, and the candidate's source or object hash. At the start of a round with no kept answer, the tool compiles the baseline twice in two folders, a second apart, and when the objects differ (a timestamp or a path) it hashes the function's bytes instead: the `diff` adapter may print `function_sha256` (a hash of the function's bytes under the relocation policy) beside `match` and `differ_bytes`, and without it only the source layers dedupe.
- **Not a match claim.** A `match` is a search result. The writer copies the winner into the unit and still passes `check`, `verify`, and the audit.

### Check trail

`.decomp/trail.jsonl` holds one JSON line per `check` run and per template round, for this machine only: it is never committed, and every worktree of the checkout shares it. The committed ledger still gets one record per writer return, through `verify`.

- Fields: `unix`, `ticket`, `by` (`check` or `search`), `result`, `differ_bytes`, `category`.
- A `check` records the `--category` it was given, `build-fail` when the build failed and none was given, and no category on a match.
- A template round records its best candidate's `result` and `differ_bytes`, and the category of the attempt before it.
- A run that exits 6, and a refused `check` or `search`, add nothing.

### The gate

`decomp.py` decides from the ticket's tier and its check trail whether template search is open. `check` reports it as `search_open`, with `search_reason`, and `search` refuses with that reason while it is closed. The first rule below that applies decides:

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

`/decomp-setup` writes these for the project's format and toolchain. Each is a command in `decomp.json`, run from a worktree root, with `{placeholders}` filled from the ticket. Adapters are run only through `decomp.py` (`inventory`, `disasm`, `link`, and the commands that build and diff), never directly: that is what gives each one its environment. Every command also gets `{tools}` (the `tools/` folder of the tree being built) and `{python}` (the interpreter running `decomp.py`), and a brace that is not a placeholder stays as written. `decomp.py` gives each one the target's path as `DECOMP_TARGET` and each tool's folder as `DECOMP_TOOL_<NAME>` (the tool's `name` in `toolchain.json`, upper-cased); an adapter holds no absolute path and no lookup of `.decomp/local.json`.

- **inventory**: reads the target, writes `inventory.json` and `expected/`, and seeds `symbols.json` with what the target itself proves (exports, imports, any symbols present). Shape: `{"units": [{"id", "source", "start", "end", "evidence"}], "functions": [{"address", "size", "unit", "scope", "offset", "evidence"}]}`; `offset` is the file offset of the function's first byte in the target as it sits on disk, which `link` places it by (a unit is linked from source only when each of its in-scope functions has one); a function may add `key` (see Units and ids) and `expected` (its expected file, when not `expected/<key>.bin`); `scope` is `in`, `library`, `compiler`, `asm-origin`, or `excluded`; `size` follows the tier rule.
- **build** (`{source}`, `{unit}`, `{obj}`, `{compiler}`): compiles one unit with the contract's compiler and flags. `{compiler}` is the tool name from `toolchain.json` that builds this unit: `decomp.json`'s `compiler`, or the unit's entry in `unit_compilers`. Exit nonzero on failure, errors on stderr.
- **diff** (`{obj}`, `{expected}`, `{id}`, `{source}`, `{report}`, `{symbols}`): finds the function after the `@decomp {id}` marker in the object, compares it to the expected bytes under the contract's relocation policy, writes a readable instruction diff to `{report}`, and prints `{"match": true|false, "differ_bytes": N}` on stdout (and may add `function_sha256`, see Template search). `{symbols}` is the path of the symbol map in the tree being built. The JSON may also carry `first_differ`, the byte offset of the first difference (optional, a non-negative integer): `search` uses it to break ties and to place the diff window, and everything else ignores it. For the window, write each report line with its offset as a whole number (hex, `0x` optional, or decimal).
- **disasm** (`{expected}`, `{address}`): prints the original function's disassembly. `decomp.py disasm <id>` fills the placeholders from the ticket.
- **link** (`{plan}`, `{out}`): links one whole file with the contract's linker and linker flags and writes it to `{out}`. `{plan}` is a JSON file: `{"objects": [{"unit", "source", "obj", "functions": [{"id", "address", "offset", "size"}]}], "blocks": [{"offset", "size"}], "output"}`. Each object is a unit built by the `build` adapter, whose functions go at their file offsets; each block is a range of the target file, at `DECOMP_TARGET`, copied to the same offset. Together they cover every byte of the target once. Exit nonzero on failure. Where the format or linker cannot place raw blocks at fixed offsets or reproduce the file's headers, there is no `link` adapter: `decomp.json`'s `link_unavailable` holds the reason, with its evidence in the contract.

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
