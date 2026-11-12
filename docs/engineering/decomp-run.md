## What it does

`decomp-run` works decomp tickets until each function's source compiles to the original bytes, byte for byte, and is recorded as matched. The agent you talk to is the coordinator. It picks ready tickets, hands each one to a writer subagent, judges the result, and records what each match teaches.

The coordinator never writes reconstruction source, and no agent grades its own work. Three roles stay separate. **Writers** ([decomp-match](./decomp-match.md)) write source in their own worktrees. **The tool** (`tools/decomp.py`) builds, compares, and records, and is the only judge of bytes. **Auditors** read a writer's diff against the guardrails and nothing else. A writer's own "it matched" counts for nothing until the tool's clean build and the auditor both agree.

## When to reach for it

You invoke this by typing `/decomp-run`, and the agent won't reach for it on its own. Run it from the decomp project root on the integration branch, in a new chat each time. Give it a ticket count, or nothing to run until no ticket is ready.

| Situation | Reach for |
| --- | --- |
| Tickets exist, and you want matches | `/decomp-run` |
| No tickets yet | [decomp-start](./decomp-start.md); `decomp-run` stops and says so |
| The report warns the compiler or flags are suspect, or the toolchain needs restoring | [decomp-setup](./decomp-setup.md) |
| One function you want to work by hand, outside a run | [decomp-match](./decomp-match.md) on its ticket |

## Prerequisites

- **A started project**: the `decomp-start` tag. Without it, the skill stops and tells you to run `/decomp-start`.
- **A machine that passes `doctor`.** Each pass of the loop checks it first. On exit 6 the run stops: the target, a host prerequisite, or a tool no longer equals the contract.
- **A harness that runs subagents**, each started with a fresh context window. Writers, auditors, and the repair agent are all subagents.

## The loop

Each pass checks health, then does repairs first, then fills free writer slots:

1. **Repair.** A ticket blocked on a missing or wrong shared declaration (a `reference-gap`) goes to one [decomp-reference](./decomp-reference.md) subagent at a time. A repair unblocks many tickets at once, so it goes ahead of new writers. The coordinator revalidates every existing match on the repair's branch itself, and any regression discards the repair.
2. **Dispatch.** Each ticket's writer runs on the contract's model for its size tier. A ticket that makes no progress in differing bytes over the contract's attempt budget moves up to the next tier's model. A reference gap never escalates: it is a repair, not a harder problem.
3. **Judge.** The tool's `verify` decides the bytes. A byte match goes to an auditor, which sees only the diff and the guardrails, and only an audit pass merges.
4. **Revalidate and link.** Every few integrations, the whole project is rebuilt to catch a match that a later change broke. When enough units have fully matched, the run links the whole binary from source plus raw blocks and reports the result.

Failed attempts stay in the ticket notes, so the next writer never repeats an approach without new evidence.

## Proven lessons

This is the automatic retro. When an audited match teaches an idiom the project's `PATTERNS.md` doesn't hold yet, the coordinator appends one short line: the instruction pattern, the source idiom that produces it, and the ticket that proved it. Writers read that file before every attempt, so it carries only proven patterns and every word stays short. Failures never go in it. Recurring ones surface in `OPEN.md` through the report, where they also steer escalation.

## Common questions

**These skills used to be in `in-progress/`. Where are they now?**

`engineering/`. The decomp skills graduated out of the beta bucket and now ship in the plugin with the rest of the promoted set.

**How do I know whether the project is done?**

Read the `state:` line the run relays from the tool's report. The coordinator never decides it.

| State | Means | Next |
| --- | --- | --- |
| `more` | Tickets are still workable | Run `/decomp-run` again; the reply says how many bytes and functions remain |
| `stuck` | Every remaining ticket is blocked on a reference gap or regressed | Resolve what blocks the named tickets, then run again |
| `finished` | Every in-scope ticket is revalidated | Nothing left to run; the reply states the final link result |

A run limited to a few tickets ends with `more`, never with something that looks like `finished`.

**A writer said it matched, but the ticket wasn't merged.**

The writer's local result doesn't count. The tool's clean build decides the bytes, then the auditor checks the guardrails, and a ticket merges only after both. Where the writer and `verify` disagree, the note says so. When that happens twice in a project, the run tells you, because the writer's environment and the clean build have drifted apart.

**The final link reports a mismatch. Are my matched tickets wrong?**

Not necessarily, and the link never changes a ticket's status. Per-function matching stays the only judge of tickets. A mismatch is reported with its first differing offset and its owner (a function, a raw block, or the header), and it points at link order or relocation handling. Fix it through a contract change. Where the target can't be linked whole at all, the finish message says so instead of reporting a failure.

**Why start a new chat before every run?**

All run state lives in the ledger and the ticket files. A coordinator that carries the last run's window pays for it on every decision, and a fresh one loses nothing.

## It's working if

- The coordinator's trace holds tool commands and subagent dispatches, and no source edits of its own.
- Every merged ticket shows a `verify` result and a one-line audit verdict in its record.
- Blocked tickets are repaired before new writers start, and a repair that breaks a match is thrown away.
- `PATTERNS.md` grows by short lines, each naming the ticket that proved it.
- The reply ends with the tool's `state:` line, the next input for that state, and a new-chat reminder.

## Where it fits

`decomp-run` is the build step of the decomp chain, run as many times as the project needs:

```txt
decomp-setup → decomp-start → decomp-run
```

It works the tickets [decomp-start](./decomp-start.md) wrote, dispatching [decomp-match](./decomp-match.md) writers and [decomp-reference](./decomp-reference.md) repairs under the rules in [decomp-standards](./decomp-standards.md). It is the decomp counterpart of [implement](./implement.md): one orchestrator that never writes the code itself, with fresh-context workers and a tiered choice of models. [skill-map](./skill-map.md) is the router over the whole set.
