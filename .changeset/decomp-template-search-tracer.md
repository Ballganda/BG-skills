---
"bg-skills": patch
---

Decomp skills (in progress): the project tool gains `search`, the first slice of template search (spec #162).

- **`search <id> <template file>`** tries every candidate of a template (the unit's source with `PERM_GENERAL` choice points), each built in a scratch copy of the unit's folder layout, and stops at the first exact match. It prints a JSON summary capped at about 600 tokens: the best choice code, a diff window, counts, and the end reason (`match` or `exhausted`). On a match it writes the winner as plain C outside the tree.
- **`search <id> --detail '<choice code>'`** prints one candidate's score and source.
- **Refusals.** Exit 6 when `doctor`'s checks fail, and a refusal with the reason when the contract disallows template search. It records nothing: the unit, the ledger, and frozen files are unchanged.
- **`LAYOUT.md`** documents the command, the template, and the summary.
