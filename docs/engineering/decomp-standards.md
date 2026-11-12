## What it does

`decomp-standards` holds the rules every decomp skill loads before it touches a function: the acceptance criterion, the guardrails, the size tiers, the mismatch categories, and the layout of a decomp project's files, records and tool commands. [decomp-match](./decomp-match.md), [decomp-reference](./decomp-reference.md) and [decomp-run](./decomp-run.md) each call it first, and the auditor in a run is handed its guardrails and nothing else.

A function counts as **matched** only when the project tool has recorded it: a clean build, an exact byte comparison against the original, and a passed audit. Matching behaviour, a matching algorithm, a clean build or a near match counts for nothing, and no project's contract loosens the guardrails. Like [codebase-design](./codebase-design.md), it is a reference, not a process: it runs no loop and writes nothing, and invoked on its own it gives you the rules and stops.

## When to reach for it

Type `/decomp-standards`, or the agent reaches for it automatically when a task fits: reconstructing, verifying, auditing or repairing a decomp function, or when another decomp skill needs the rules.

Reach for it yourself when you want to know what a decomp project will and will not accept, what a status or record means, or which command does what. To actually work tickets, use [decomp-run](./decomp-run.md); to set up or change a project, use [decomp-setup](./decomp-setup.md).

## What it holds

The leading word is **byte-for-byte**: the original binary is the authority, the contract (`DECOMP.md`) is the constraint, and the byte comparison is the test.

| Part | What it settles |
| --- | --- |
| The goal | Source that the contract's compiler and flags turn into the original's bytes, for every in-scope function |
| [Guardrails](../../skills/engineering/decomp-standards/GUARDRAILS.md) | Eight rules no contract loosens, plus the auditor's checklist |
| Size tiers | TINY (25 B or less), SMALL (to 256 B), MEDIUM (to 511 B), LARGE (512 B or more); the contract maps each to a model and an attempt budget |
| Mismatch categories | One tag per failed attempt, for the category that best explains the first differing instruction |
| [Layout](../../skills/engineering/decomp-standards/LAYOUT.md) | Every project file and who writes it, ticket statuses, ledger records, tool commands, the change flow, and the default relocation policy |

The guardrails, in short:

- A writer changes one file, its ticket's source.
- No assembly in any form, even where the original used it; such a function is `asm-origin` and out of scope.
- Only the contract's compiler and flags, with pragmas and attributes held to the contract's allowlists, and no spelling that hides a directive from a reader.
- Bytes come straight from the compiler, with no post-processing.
- Every declaration comes from the shared headers or from evidence in the binary.
- Only the project tool records a match.
- Any construct written only to steer the compiler is declared with a `fakematch:` comment, within the contract's rule.
- Scope, compiler and flags change only through `/decomp-setup`, recorded in an ADR.

## Common questions

**Why are trigraphs, line continuations and `%:` refused, even where they do no harm?**

Because each of them can spell a directive the allowlist never sees. A check that read only literal `#pragma` lines let `??=pragma`, a directive assembled across a backslash line break, `%:pragma`, and the `__pragma` and `_Pragma` operators all reach the compiler, so a writer could change code generation and still be recorded as a clean match. No legitimate reconstruction needs any of these forms, so they are refused outright rather than interpreted; refusing is the only version that cannot be outsmarted.

**Why is a relocated operand compared at all? Masking every relocation would be simpler.**

Masking every relocated operand records a match for a function that calls the wrong callee. The default relocation policy leaves an operand out of the comparison only when its symbol resolves, through the symbol map or another matched function in the same object, to the address the original refers to. An unresolved symbol or a wrong target makes the result `differ`, and the report names the symbol and both addresses.

**Can I change the compiler flags once matching has started?**

Yes, through `/decomp-setup`, and the change is measured before it lands. The change goes on a candidate branch (`c/<slug>`), `revalidate --candidate` rebuilds every match against it and records nothing, and you see the result before the frozen tag moves. Regressions inform your go-ahead and do not block it, since a corrected flag can break matches on purpose.

## It's working if

- The decomp skills' reports use the same category names, statuses and tier names, and nothing else.
- No reply claims a match the tool did not print, and every claim cites an attempt id.
- An audit verdict comes back as one line, `pass` or `fail: rule <n>: <quoted line>`.
- Invoking it alone answers the question and starts no work.

## Where it fits

`decomp-standards` is the shared rules layer under the decomp flow (`decomp-setup → decomp-start → decomp-run`), not a step in it. Its closest neighbours are [decomp-match](./decomp-match.md), whose every attempt is judged by these rules, and [decomp-run](./decomp-run.md), which hands the auditor its guardrails and relays the states its layout defines. When you are unsure which skill fits, [skill-map](./skill-map.md) routes you.
