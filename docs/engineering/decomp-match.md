## What it does

`decomp-match` takes one decomp ticket and writes the source for its function, so that the contract's compiler, with the contract's flags, emits the original function's bytes exactly. It is the **writer**: it reads the original's disassembly, writes the function into its unit's source file, and loops on the project tool's build-and-diff until the bytes match or the attempt budget for the ticket's size tier runs out.

The disassembly decides the source, not what the function appears to do. A readable function with the same behaviour is a failed attempt, and every type, field, callee and calling convention it uses has to come from the shared headers, the symbol map, or an instruction in the original. When one is missing or contradicts the evidence, it stops and reports a `gap` instead of declaring a local stand-in, because a local copy would hide the gap from every other function that needs the same declaration.

## When to reach for it

Type `/decomp-match`, or the agent reaches for it automatically when a task fits: solving a decomp ticket, or matching, decompiling or reconstructing one function.

Reach for it when you have one ticket and want one function matched. In practice you rarely type it: [decomp-run](./decomp-run.md) starts a fresh writer subagent per ticket, each running this skill in its own worktree.

| Your situation | Where to go |
| --- | --- |
| One ticket, one function to match | `decomp-match` |
| Work the whole queue of ready tickets, with verification and audits | [decomp-run](./decomp-run.md) |
| Tickets blocked on a wrong or missing shared declaration | [decomp-reference](./decomp-reference.md) |
| The compiler or flags themselves are in doubt | [decomp-identify](./decomp-identify.md), through [decomp-setup](./decomp-setup.md) |

## Prerequisites

A decomp project built by [decomp-setup](./decomp-setup.md) and filled by [decomp-start](./decomp-start.md): the contract (`DECOMP.md`), the project tool (`tools/decomp.py`), tickets, and a provisioned toolchain on this machine. The skill writes into exactly one file, the ticket's unit source under `src/`, and commits it to the ticket's `w/<ticket id>` branch.

## The loop: first difference, one change

Each pass runs `python tools/decomp.py check <id>` and reads one result:

| Result | What it means | What the writer does |
| --- | --- | --- |
| Exit 6, `ENVIRONMENT:` | The machine differs from the contract, this edition holds the function differently, or the unit's compiler is not provisioned | Stops: no source change fixes the machine |
| `build-fail` | The source does not compile | Fixes its own source, or stops with a `gap` if a shared declaration is at fault |
| `guardrail` | The scan quoted a line that breaks a rule | Rewrites it in plain form; an attribute the original needed is a `gap` for the contract |
| `differ` | Bytes differ | Finds the **first differing instruction**, ranks two or three hypotheses, makes one change |
| `bytes-match` | Every byte matches locally | Commits and reports |

The leading idea is **one change per iteration against the first difference**. Later differences are often echoes of the first, so chasing them wastes attempts. A change that does not lower `differ_bytes` is reverted unless it moves the first difference later. [MISMATCH.md](../../skills/engineering/decomp-match/MISMATCH.md) maps what the first difference looks like to its category and the source levers that move it.

## Common questions

**It reported `bytes-match`, but the ticket is not matched.**

That is by design. `check` records nothing; the writer's local result does not count. The coordinator rebuilds the branch in a clean worktree with `verify`, then an auditor reads the diff against the guardrails, and only a passed audit records the match. If `verify` disagrees with a writer's local match twice in a project, the writer's environment and the clean build differ, and [decomp-run](./decomp-run.md) tells you so.

**Why did it stop with a gap instead of declaring the struct itself?**

A local declaration would compile, and might even match, but it would leave every other function that touches the same struct compiling against the wrong one. The auditor fails a unit file that defines a type a shared header should own. The ticket moves to `blocked-reference`, and [decomp-reference](./decomp-reference.md) fixes the shared declaration once for every ticket that needs it.

**It stopped on exit 6. What should it have done?**

Nothing in the source. Exit 6 always means the machine, not the code: the target edition, a host prerequisite, or a tool differs from the contract, or this edition holds the function differently from the expected bytes. `doctor` names the difference, and the provisioning step of [decomp-setup](./decomp-setup.md) restores the toolchain. A ticket the local edition holds differently waits for a machine whose edition holds it unchanged.

## It's working if

- Each attempt's note names one change and what it did to the byte count, and no note repeats an approach an earlier note already tried.
- `differ_bytes` falls across attempts, or the first difference moves later.
- The branch touches one file, the unit source, plus at most an added include.
- A missing field or callee address comes back as a `gap` naming an address and instruction, never as a new struct in the unit file.
- The reply is six short lines, not a narrative.

## Where it fits

`decomp-match` is the writer step inside the decomp flow, dispatched per ticket rather than run as a step of its own:

```txt
decomp-setup → decomp-start → decomp-run
```

[decomp-run](./decomp-run.md) claims the ticket, starts the writer, verifies and audits its result, and turns a proven idiom from its report into a line of `PATTERNS.md` for the next writer. [decomp-standards](./decomp-standards.md) holds the guardrails and mismatch categories every attempt is judged against, and [decomp-reference](./decomp-reference.md) takes the gaps it reports. When you are unsure which skill fits, [skill-map](./skill-map.md) routes you.
