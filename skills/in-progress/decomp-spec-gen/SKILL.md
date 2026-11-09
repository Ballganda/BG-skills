---
name: decomp-spec-gen
description: Group a decomp inventory's functions into units (best-guess original source files) and write one spec per unit, saying what each must reproduce and its success test. Use when decomp-start reaches specs, or when unit boundaries need revising.
---

A **unit** is a best-guess original source file: a run of functions in address order that the original compiler emitted from one file. Its spec says what to reproduce and how success is tested. Function order within a unit affects the bytes, so units matter.

## 1. Check the boundaries

The `inventory` adapter proposes units in `inventory.json`. Strengthen them with evidence the adapter may have missed, strongest first:

1. Debug information or symbols naming source files.
2. Assert, log, or `__FILE__` strings naming a source file, and the functions that reference them.
3. Runs of functions sharing the same data, strings, or class (RTTI names, one vtable's methods).
4. Alignment gaps and changes in padding style between runs.

Move a boundary only on evidence, and write that evidence into the unit's `evidence` field. A guess stays a guess: say so in the field. Boundaries can be revised later; the tickets keep their status.

## 2. Generate

Run `python tools/decomp.py gen-specs`. It writes `units/<unit>.md` for every unit: its source path, address range, evidence, success criterion, a table of its in-scope functions with size and tier, and its excluded functions with their evidence.

**Done when** every unit has an `evidence` value and a spec file, and no function belongs to two units.
