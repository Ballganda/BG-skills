---
"bg-skills": patch
---

Decomp skills (in progress): `/decomp-setup` asks the diff adapter for what template search needs (spec #186, findings 3 and 4, project side).

- **Adapter contract.** The layout document asks for one report line per instruction with its offset, on 32-bit and 64-bit targets alike: a disassembler prints 8-digit or 16-digit addresses by target.
- **Setup.** Where the contract allows template search, the diff adapter prints `first_differ` and `function_sha256`. Where it does not, both stay optional.
- **Pipeline check.** One new box, ticked only when template search is allowed: for a build known to differ, the diff result carries both fields and the report holds more than its header line.
- **Skill upgrade.** It adds the same to an existing project's diff adapter where template search is allowed, as a contract change with its ADR. The signs that it is due are the `search` summary's two notice lines: no object identity, and no instruction diff.
