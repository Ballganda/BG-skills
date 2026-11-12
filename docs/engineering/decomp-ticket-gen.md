## What it does

`decomp-ticket-gen` writes one **ticket** per in-scope function in a decomp project's inventory, as a file under `tickets/<unit>/`, and mirrors progress to GitHub when the contract enables it. Each ticket names one function: its unit, address, size, tier, source file, expected bytes, and a status that starts at `open`.

No ticket is written by hand. The project tool generates every one from `inventory.json`, so the ticket set is a mechanical consequence of the inventory: one function, one ticket, nothing to decide. Run it again and an existing ticket keeps its status, claim, and notes, so regenerating never loses work.

## When to reach for it

Type `/decomp-ticket-gen`, or the agent reaches for it automatically when a task fits. Usually you never type it: `/decomp-start` calls it right after [decomp-spec-gen](./decomp-spec-gen.md).

Reach for it when a decomp project's units are settled and need tickets, or after the inventory or units change. For tickets that split a feature build into tracer bullets on your issue tracker, use [ticket-gen](./ticket-gen.md) instead.

| | `decomp-ticket-gen` | [ticket-gen](./ticket-gen.md) |
| --- | --- | --- |
| Input | `inventory.json` | A plan, a spec, or the conversation |
| Ticket | One function to match byte for byte | A tracer bullet through every layer of a change |
| Where tickets live | Files in the private decomp repo; GitHub is only a mirror | Issues on your tracker |
| Sizing | Always one function; its size tier picks the model and attempt budget | Judged to fit one fresh context window |

## Prerequisites

A decomp project set up by [decomp-setup](./decomp-setup.md), with `inventory.json` and its expected byte files in place, and unit specs from [decomp-spec-gen](./decomp-spec-gen.md). The GitHub mirror needs `github` enabled in `decomp.json`, which the contract allows only for a private repo, and `gh` authenticated against it.

## Files are the source of truth

The ticket files are the record. The skill checks two things after generating: the ticket count equals the number of in-scope functions in `inventory.json`, and every ticket's expected byte file exists.

With GitHub enabled it then runs the project tool's `sync`, which rebuilds the mirror from the ticket files:

| Issue | Holds |
| --- | --- |
| One per unit | A checklist of the unit's functions, with size, tier, and status |
| One pinned progress issue | Verified byte progress across the project, and a checklist of units |

Only `sync` writes those issues. Editing one by hand changes nothing, and the next `sync` overwrites it.

## Common questions

**Can I close or edit the GitHub issues to track progress?**

No. They are a mirror, rebuilt from the ticket files on every `sync`, and `sync` closes a unit issue once every function in it is matched. Progress moves only through the project tool's commands (`claim`, `verify`, `audit`, `integrate`, `revalidate`), which [decomp-run](./decomp-run.md) drives.

**It used to be in `in-progress/`. Where is it now?**

`engineering/`. It graduated with the rest of the decomp skills and now ships in the plugin. Its behaviour did not change on the move.

## It's working if

- The number of ticket files matches the number of in-scope functions the inventory reports, with none extra and none missing.
- Re-running after a change reports existing tickets as kept, and their statuses and notes are still there.
- Out-of-scope functions (`library`, `compiler`, `asm-origin`, `excluded`) have no tickets; they appear in their unit's spec instead.
- With the mirror on, there is one issue per unit plus one pinned progress issue, and their checklists agree with the ticket files.

## Where it fits

`decomp-ticket-gen` is the last generation step inside [decomp-start](./decomp-start.md):

```txt
decomp-setup → decomp-start (inventory → decomp-spec-gen → decomp-ticket-gen) → decomp-run
```

[decomp-spec-gen](./decomp-spec-gen.md) settles the units it writes tickets into, and [decomp-run](./decomp-run.md) works the tickets, one function at a time through [decomp-match](./decomp-match.md). When you are unsure which skill fits, [skill-map](./skill-map.md) routes you.
