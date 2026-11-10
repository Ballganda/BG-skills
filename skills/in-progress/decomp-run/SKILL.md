---
name: decomp-run
description: Work decomp tickets to verified byte-for-byte matches by coordinating separate writer, auditor, and repair subagents, recording what each match teaches.
disable-model-invocation: true
argument-hint: "How many tickets (default: until none are ready)"
---

You are the coordinator. You never write reconstruction source. Three roles stay separate, so no agent grades its own work:

- **Writers** (`decomp-match`) write source in their own worktree.
- **The tool** (`tools/decomp.py`) builds, compares, and records. It is the tester and the only judge of bytes.
- **Auditors** read a writer's diff against the guardrails and nothing else.

Repairs to shared declarations and the symbol map go to one `decomp-reference` subagent at a time.

Run from the decomp project root, on the integration branch. If there is no `decomp-start` tag, tell the user to run `/decomp-start` and stop. Call the Skill tool with `decomp-standards` first. Read `DECOMP.md`'s Models and Tracking sections once.

Every subagent starts with a fresh context window and gets **pointers** (ticket path, worktree path, file paths), never pasted content.

## The loop

Repeat until the requested number of tickets have been attempted, or nothing is ready.

### 1. Check health

Run `python tools/decomp.py doctor`. On exit 6, stop and show the user what it printed: the target, a host prerequisite, or a tool on this machine no longer equals the contract, and `/decomp-setup`'s provisioning step restores it. Note the edition it prints: on an edition with a `differs` list, `check` and `verify` exit 6 for those tickets, so `release` them and leave them for a machine with an edition that holds them unchanged. A `not usable here` line names a compiler this machine lacks: the same goes for the units built with it.

Run `python tools/decomp.py report`. On `EARLY-WARNING`, stop and tell the user the contract's compiler or flags are suspect: they rerun `/decomp-setup`, which can start `decomp-identify` again. Read `OPEN.md`.

### 2. Repair first

If any ticket is `blocked-reference` and no repair is running: `python tools/decomp.py lock reference --by coordinator`, then start one background subagent. Tell it to call the Skill tool with `decomp-reference`, and give it the blocked tickets' paths. A gap unblocks many tickets at once, so this goes ahead of new writers.

When it reports, re-run `revalidate --ref <its branch>` yourself, because its own result does not count. On exit 0: merge the branch, `release <id> --to open` for each ticket it fixed, run `revalidate`, then `unlock reference`. On a regression (exit 5): discard the branch, `unlock reference`, and leave the tickets blocked with a note. On exit 6 with `SKIPPED` lines, this machine could not rebuild every match the repair could break: keep the branch, `unlock reference`, and tell the user it needs a machine that can.

### 3. Pick and dispatch

Fill free writer slots (the contract's cap) from `python tools/decomp.py next --n <free slots>`. Per ticket:

- **Model**: the contract's model for the ticket's tier. Escalate to the next tier's model once the ticket's notes show the contract's number of attempts with no fall in differ bytes, or when its category is listed in `OPEN.md`. Never escalate a `reference-gap`: that is a repair.
- `claim <id> --by <writer name>`, then `git worktree add <path> -b w/<id> <integration branch>`.
- Start a background writer subagent on that model, working in that worktree. Tell it to call the Skill tool with `decomp-match` for the ticket path, commit to `w/<id>`, and reply in the report format the skill defines.

### 4. Judge each report

- **Gap**: `release <id> --to blocked-reference`, then `note <id> gap: <the gap line>`.
- **Otherwise**: `verify <id> --model <writer's model> --category <reported category>`, then `note <id> <result> <category> <differ bytes>: <the writer's note line>`. If the writer reported a local match but `verify` disagrees, say so in the note. If that happens twice in a project, tell the user: the writer's environment and the clean build differ.
- **`bytes-match`**: save `git diff <integration branch>...w/<id> -- <source>` to a file, then start an auditor subagent on the contract's auditor model. Give it only that file's path and the path to `GUARDRAILS.md` in `decomp-standards`. Record its one-line verdict with `audit <id> pass|fail --auditor <model> --note "<verdict>"`.
- **Audit pass**: merge `w/<id>` into the integration branch, `integrate <id>`, record the lesson (step 5), then remove the worktree and branch.
- **Anything else**: `release <id>`, then remove the worktree and branch. The notes carry what was learned to the next writer.

Commit the ledger, ticket, and `PATTERNS.md` changes after each judged report: `decomp: <id> <result>`.

### 5. Record the lesson

This is the automatic retro. When an audited match's report carries a lesson that `PATTERNS.md` does not already state, append one line:

```
- <instruction pattern> => <source idiom that produces it> [proven: <ticket id>] [added: <Unix time>]
```

Keep it under 200 characters, with no explanation. Writers read this file before every attempt, so every word costs on every attempt. Failures never go in `PATTERNS.md`: they stay in ticket notes, and `report` collects recurring ones into `OPEN.md`. Any `PATTERN-` line in the next `report` means a malformed or unproven entry: fix or delete it.

### 6. Revalidate and mirror

After every N integrations (N is in the contract), run `revalidate`. On a regression, stop picking in that unit and tell the user which tickets regressed. Its tickets are claimable again as `regressed`. After each batch of integrations, run `sync` if GitHub is enabled.

## Finish

Report only numbers that `python tools/decomp.py report` printed: bytes and functions matched, the change since this run began, credit per model, open problems, and blocked tickets.
