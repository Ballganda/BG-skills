---
name: decomp-start
description: Read a set-up decomp target, list every function to recreate, and turn them into unit specs and function tickets.
disable-model-invocation: true
---

Turn the target into work: an inventory of every function, one spec per unit, one ticket per in-scope function. Scripts do the bulk; spend tokens only where a script cannot decide. This skill reconstructs nothing.

Run from the decomp project root. If there is no `decomp-setup` tag, or `DECOMP.md` has no passed pipeline check, tell the user to run `/decomp-setup` and stop.

Call the Skill tool with `decomp-standards` first.

## 1. Inventory

Run `python tools/decomp.py inventory`. It checks the environment, then runs the `inventory` adapter, which writes `inventory.json` and `expected/`, and seeds `symbols.json`. Exit 6 means the machine's target or toolchain differs from the contract: nothing was written, so stop and report it. Once the `decomp-start` tag exists the command refuses: pass `--redo` only with the user's go-ahead for a redo.

Check it before anything depends on it:

- [ ] The functions' address ranges do not overlap, and every size follows the tier rule.
- [ ] Every function outside scope (`library`, `compiler`, `asm-origin`, `excluded`) carries evidence that a reader can check, per the contract's scope rules.
- [ ] In-scope bytes plus excluded bytes plus padding account for every executable section; name any remainder.
- [ ] No two functions share a key. Where two share an address (overlays, modules, banks), each has a `key` of its own.
- [ ] Every expected file's length equals its function's size.

Review by hand only what the adapter marked uncertain. A function you cannot classify stays `in` scope, so no code drops out of the denominator without evidence.

## 2. Specs

Call the Skill tool with `decomp-spec-gen`.

## 3. Tickets

Call the Skill tool with `decomp-ticket-gen`.

## 4. Freeze and report

Commit `inventory.json`, `expected/`, the seeded `symbols.json`, `units/`, and `tickets/`, then tag `decomp-start` so the ground truth stays frozen. Report, from `python tools/decomp.py report`: in-scope bytes and functions per tier, and exclusions per scope. Tell the user to run `/decomp-run`.

Redoing the inventory later (a better function finder, a scope change) needs the user's go-ahead and follows the change flow in `decomp-standards`' layout: on the `c/<slug>` branch, regenerate and re-run both generators (statuses and notes survive). The `decomp-start` tag moves only after the candidate revalidation.
