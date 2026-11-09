---
name: decomp-start
description: Read a set-up decomp target, list every function to recreate, and turn them into unit specs and function tickets.
disable-model-invocation: true
---

Turn the target into work: an inventory of every function, one spec per unit, one ticket per in-scope function. Scripts do the bulk; spend tokens only where a script cannot decide. This skill reconstructs nothing.

Run from the decomp project root. If there is no `decomp-setup` tag, or `DECOMP.md` has no passed pipeline check, tell the user to run `/decomp-setup` and stop.

Call the Skill tool with `decomp-standards` first.

## 1. Inventory

Run the `inventory` adapter from `decomp.json`. It writes `inventory.json` and `expected/`.

Check it before anything depends on it:

- [ ] The functions' address ranges do not overlap, and every size follows the tier rule.
- [ ] Every function outside scope (`library`, `compiler`, `asm-origin`, `excluded`) carries evidence that a reader can check, per the contract's scope rules.
- [ ] In-scope bytes plus excluded bytes plus padding account for the whole code section; name any remainder.
- [ ] Every expected file's length equals its function's size.

Review by hand only what the adapter marked uncertain. A function you cannot classify stays `in` scope, so no code drops out of the denominator without evidence.

## 2. Specs

Call the Skill tool with `decomp-spec-gen`.

## 3. Tickets

Call the Skill tool with `decomp-ticket-gen`.

## 4. Freeze and report

Commit `inventory.json`, `expected/`, `units/`, and `tickets/`, then tag `decomp-start` so the ground truth stays frozen. Report, from `python tools/decomp.py report`: in-scope bytes and functions per tier, and exclusions per scope. Tell the user to run `/decomp-run`.

Redoing the inventory later (a better function finder, a scope change) needs the user's go-ahead: regenerate, re-run both generators (statuses and notes survive), move the tag, and run `revalidate`.
