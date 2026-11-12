## What it does

`decomp-start` turns a set-up decomp project into work. It lists every function in the target (the **inventory**), groups them into units that stand for the original source files, writes one spec per unit, and writes one ticket per in-scope function. Then it freezes that ground truth with the `decomp-start` tag.

Scripts do the bulk, and the agent spends tokens only where a script cannot decide. The project tool runs the inventory, writes the specs and the tickets, and prints the report; no ticket is written by hand. The agent checks the inventory and reviews only what the adapter marked uncertain. Like setup, it reconstructs nothing.

## When to reach for it

You invoke this by typing `/decomp-start`, and the agent won't reach for it on its own. Run it from the decomp project root, once, after `/decomp-setup` has tagged the contract.

| Situation | Reach for |
| --- | --- |
| No project yet, or the pipeline check never passed | [decomp-setup](./decomp-setup.md) first; `decomp-start` stops and says so |
| Setup is tagged, and there are no tickets | `/decomp-start` |
| Tickets exist, and you want them worked | [decomp-run](./decomp-run.md), in a new chat |
| A better function finder, or a scope change, after the tag | `/decomp-start` again, with your go-ahead for a redo through the change flow |

## Prerequisites

- **A set-up project**: the `decomp-setup` tag, and a passed pipeline check recorded in `DECOMP.md`. Without both, the skill stops and tells you to run `/decomp-setup`.
- **The same machine state the contract pins.** The inventory runs the environment checks first; exit 6 means the target or toolchain differs, and nothing is written.

## The denominator

The inventory decides what "finished" will mean, so it is checked before anything depends on it. Function ranges must not overlap, every size must follow the tier rule, and in-scope bytes plus excluded bytes plus padding must account for every executable section, with any remainder named.

A function only leaves the denominator on evidence a reader can check. Each out-of-scope function (`library`, `compiler`, `asm-origin`, `excluded`) carries its evidence, and a function nobody can classify stays in scope. That is why the denominator can be trusted: no code drops out of the count because it looked hard.

## Units, specs, and tickets

A **unit** is a best-guess original source file: a run of functions in address order that one file produced. It matters because function order within a unit changes the bytes. [decomp-spec-gen](./decomp-spec-gen.md) strengthens the adapter's proposed boundaries with evidence (debug names, `__FILE__` strings, shared data, padding changes) and writes one spec per unit. [decomp-ticket-gen](./decomp-ticket-gen.md) then writes one ticket per in-scope function, and mirrors units and progress to GitHub issues when the contract enables it. The ticket files stay the source of truth; the issues are only a mirror.

## Common questions

**These skills used to be in `in-progress/`. Where are they now?**

`engineering/`. The decomp skills graduated out of the beta bucket and now ship in the plugin with the rest of the promoted set.

**The inventory missed functions, or I want to change the scope. Can I redo it?**

Yes, with your go-ahead. `inventory` refuses once the `decomp-start` tag exists, unless the redo is explicit. A redo follows the change flow: regenerate on a `c/<slug>` branch, re-run both generators (ticket statuses and notes survive), and measure it with a candidate revalidation before the tag moves.

**Why does it tell me to start a new chat at the end?**

All run state lives in the ledger and the ticket files, not in the conversation. A fresh window gives `/decomp-run` a clean coordinator, and nothing is lost by closing this one.

## It's working if

- The inventory checks come back as a ticked list, with any byte remainder named rather than skipped.
- Every excluded function in a unit spec carries its evidence.
- The number of tickets equals the number of in-scope functions, and no ticket was written by hand.
- The final report gives in-scope bytes and functions per tier and exclusions per scope, then sends you to a new chat for `/decomp-run`.

## Where it fits

`decomp-start` is the planning step of the decomp chain, run once per project:

```txt
decomp-setup → decomp-start → decomp-run
```

It reads what [decomp-setup](./decomp-setup.md) froze, drives [decomp-spec-gen](./decomp-spec-gen.md) and [decomp-ticket-gen](./decomp-ticket-gen.md) to write the specs and tickets, and hands those tickets to [decomp-run](./decomp-run.md). It plays the role `spec-gen` and `ticket-gen` play in the main chain, scripted end to end because a binary's functions can be counted. [skill-map](./skill-map.md) is the router over the whole set.
