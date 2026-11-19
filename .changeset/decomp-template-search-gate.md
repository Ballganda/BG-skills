---
"bg-skills": patch
---

Decomp skills (in progress): the project tool decides when template search may start (spec #162).

- **Check trail.** Every `check` run and every template round appends one record to `.decomp/trail.jsonl` (ticket, result, `differ_bytes`, category, time). It stays on this machine and is never committed.
- **`check <id> --category <c>`** takes the writer's mismatch category and refuses one outside the list.
- **The gate.** `check`'s JSON gains `search_open` and `search_reason`. Template search opens on a latest category of `register-allocation`, `statement-order`, or `expression-shape`, or after 3 attempts with no fall in `differ_bytes`. It stays closed for TINY tickets and for the stop-or-report categories. `search` refuses with the reason while it is closed.
- **`verify --template-round`** marks the attempt as a template round: its evidence file gains the round's best candidate and winning kinds. The fields of `attempts.jsonl` are unchanged.
- **`LAYOUT.md`** documents the trail, the gate, the argument, the JSON fields, and the flag.
