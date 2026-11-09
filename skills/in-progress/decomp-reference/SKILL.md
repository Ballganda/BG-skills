---
name: decomp-reference
description: Repair shared decomp declarations (struct layouts, field types, signatures, calling conventions) from evidence in the binary, without breaking any existing match. Use when decomp tickets are blocked on a reference gap, or when asked to fix a struct, class, or header in a decomp project.
---

You repair the shared declarations every writer compiles against, and the symbol map every diff resolves against. One wrong field breaks many functions, and one careless change can break functions that already match. Every change rests on evidence and must leave every existing match intact.

Call the Skill tool with `decomp-standards` first.

## 1. Lock and branch

Run `python tools/decomp.py lock reference --by <your name>`. If it is already locked, report that and stop. Work in a worktree on a new `r/<slug>` branch from the integration branch tip.

## 2. Gather evidence

For each gap in the blocked tickets' notes, collect evidence from **every** function that touches the declaration, not just the one that reported the gap. Use the `disasm` adapter on the blocked tickets, and read the source of matched functions that use the declaration:

- **Field offsets and widths**: every `[reg+offset]` access, with its operand size.
- **Signedness**: `movsx`/`movzx`, and the signed or unsigned branches that test the value.
- **Structure size**: allocation sizes passed near constructors, array strides, `memset` and copy lengths.
- **Virtual tables**: pointer arrays in read-only data, RTTI names, the order of methods called through them.
- **Signatures and conventions**: callers' argument setup and the callee's stack cleanup (`ret N`, `this` in `ecx`).
- **Symbol addresses**: the operand of every `call`, `jmp`, and data reference to the symbol in the original, read with `disasm`. They must agree.

## 3. Edit

Edit headers in `include/` and `symbols.json`, nothing else. Every added or changed member carries a trailing comment citing one piece of evidence: `// 0x00401234 mov eax, [ecx+0x1c]`. A member whose meaning is unknown is `unk_<hex offset>`, typed only as wide as its accesses show. Fill a span with no observed accesses as padding of the exact size. Name, type, and signedness come only from evidence; never pick them to make something compile.

In `symbols.json`, add or correct one `"<symbol as the object file spells it>": "0x<address in the original>"` entry per gap. JSON holds no comments, so the evidence (the referencing instruction and its address) goes in the commit message, one line per entry. Never pick an address to make a diff pass: a wrong one breaks the matches that already resolve through it, and `revalidate` shows it.

## 4. Prove it breaks nothing

1. Commit on `r/<slug>`.
2. Run `python tools/decomp.py revalidate --ref r/<slug>`. Every matched function must still match: exit 0.
3. On a regression, fix the declaration so both the old matches and the new evidence hold. If both cannot hold, the evidence conflicts: discard the change for that gap, and report the conflict with its addresses.

## 5. Report

Reply in at most 60 words: your branch, the headers and symbols changed, the tickets each gap fix unblocks, and the final `revalidate` line. The coordinator re-runs `revalidate` itself before merging, then releases the lock.
