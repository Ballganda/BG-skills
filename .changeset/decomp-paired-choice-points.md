---
"bg-skills": patch
---

Decomp skills (in progress): one choice can span two places in a template (spec #186, finding 12).

- **Paired use.** `PERM_VAR(name, a, b, ...)`, a name with no `@` followed by alternatives, pairs with the earlier `PERM_VAR(@name, ...)` and expands to its own alternative at the index that one picked. It is no choice point: it adds nothing to the space, the limit of 12, or the choice code.
- **Refusals.** A paired use with another number of alternatives is refused with both counts, one before its definition as a back reference is, and one with a label, kind, or likelihood.
- **Steering.** A steering tag on a paired alternative makes that pick steering, and its line in the winner carries its own `fakematch:` comment.
- **`PERM_VAR(@name)`** with no alternatives is refused with a message naming `PERM_VAR(name)` and `PERM_VAR(name, a, b, ...)`.
- **Docs.** `decomp-standards`' grammar table and `decomp-match`'s template step name the paired form.
