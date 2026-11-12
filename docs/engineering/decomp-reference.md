## What it does

`decomp-reference` repairs the shared declarations every writer compiles against (structs, fields, function signatures, calling conventions in `include/`) and the symbol map every diff resolves against (`symbols.json`). It runs when writers have stopped on a `gap`: it gathers the evidence for each gap from every function that touches the declaration, edits the headers and the map, and proves the change.

A repair that breaks one existing match is rejected, however many blocked tickets it would unblock. One wrong field breaks many functions at once, so every change must leave every matched function still matching, and when the old matches and the new evidence cannot both hold, the change for that gap is discarded and the conflict reported with its addresses.

## When to reach for it

Type `/decomp-reference`, or the agent reaches for it automatically when a task fits: tickets blocked on a reference gap.

Reach for it when tickets sit at `blocked-reference`. In practice [decomp-run](./decomp-run.md) starts it as a background subagent, one at a time, ahead of any new writers, because one gap fix unblocks many tickets.

| Your situation | Where to go |
| --- | --- |
| A shared struct, signature, convention or symbol address is missing or wrong | `decomp-reference` |
| One function's own source does not match yet | [decomp-match](./decomp-match.md) |
| The compiler, flags, scope or project tooling need to change | [decomp-setup](./decomp-setup.md) |

## Prerequisites

A decomp project from [decomp-setup](./decomp-setup.md) and [decomp-start](./decomp-start.md), with tickets blocked on a gap and the gap lines in their notes. It writes only `include/` and `symbols.json`, on a new `r/<slug>` branch in its own worktree, while holding the project's `reference` lock.

## Evidence, then revalidation

The leading word is **evidence**. Every added or changed member carries a trailing comment citing the instruction that proves it (`// 0x00401234 mov eax, [ecx+0x1c]`); a symbol map entry, which JSON cannot comment, cites its instruction in the commit message. A member whose meaning is unknown is named `unk_<offset>` and typed only as wide as its accesses show. Nothing is chosen to make something compile, and no address is chosen to make a diff pass.

The proof is `revalidate` on the repair branch, which rebuilds every matched function against the changed headers. The coordinator re-runs it itself before merging, since the repair's own result does not count:

| `revalidate` result | What happens |
| --- | --- |
| Exit 0 | The branch is merged and the tickets it fixed reopen |
| Exit 5, a regression | The branch is discarded and the tickets stay blocked with a note |
| Exit 6, `SKIPPED` lines | This machine could not rebuild every match the repair could break; the branch is kept for a machine that can |

## Common questions

**The repair stopped at once, saying the reference lock is held.**

Repairs run under one exclusive lock, so a second one stops. An earlier version of [decomp-run](./decomp-run.md) took the lock itself before starting the repair, so every repair found it held and none could run. The repair subagent now takes the lock and the coordinator only releases it. If you still see this, another repair is running, or an interrupted run left the lock behind (`python tools/decomp.py unlock reference` clears it once you are sure nothing is running).

**It found the gap, but the repair was discarded.**

The fix that satisfied the blocked ticket broke a function that already matched. The skill first tries a declaration under which both hold; when none exists, the evidence conflicts, and it reports the conflicting addresses instead of trading one match for another. That report is worth reading yourself, because the skill will never choose which match to give up.

**The repair passed on one machine and was refused on another.**

A repair is accepted only on a machine that rebuilt every match it could break. A machine with a different target edition, or without the compiler one unit needs, skips those tickets and exits 6, so the branch waits for a machine that can build them all.

## It's working if

- Every changed header line carries an address and an instruction in its comment.
- Unknown fields appear as `unk_<offset>` with padding of exact size, not as guessed names.
- The diff of the repair branch touches only `include/` and `symbols.json`.
- Blocked tickets reopen in batches after a merge, and the matched count does not fall.

## Where it fits

`decomp-reference` is the repair role inside the decomp flow (`decomp-setup → decomp-start → decomp-run`), started by [decomp-run](./decomp-run.md) whenever tickets are blocked and no repair is running. Its neighbours are [decomp-match](./decomp-match.md), whose writers report the gaps it fixes and compile against what it writes, and [decomp-standards](./decomp-standards.md), whose guardrails make the shared headers the only place a declaration may live. When you are unsure which skill fits, [skill-map](./skill-map.md) routes you.
