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

First check the project tool is current, before `doctor`. Compare the integration branch's `tools/decomp.py` with `../decomp-setup/scripts/decomp.py`, ignoring line endings. The path is relative to this skill's folder. The tool carries no version constant: the diff is the whole test. This skill only detects; `decomp-setup` is the only skill that upgrades a project.

- **Different**: stop. Tell the user the project was set up by another version of the skills, and that `/decomp-setup` upgrades it. Their next input is `/decomp-setup`, then a new `/decomp-run`.
- **Sibling file missing**: stop. Tell the user `decomp-setup` is not installed beside `decomp-run`, so the check cannot run. Their next input is to install the `decomp-setup` skill beside this one, then run `/decomp-run` again.

Never skip a step because the contract, a ticket, or a memory says something about the machine: the tool's result is the evidence.

Run `python tools/decomp.py doctor`. On exit 6, stop and show the user what it printed: the target, a host prerequisite, or a tool on this machine no longer equals the contract, and `/decomp-setup`'s provisioning step restores it. Note the edition it prints: on an edition with a `differs` list, `check` and `verify` exit 6 for those tickets, so `release` them and leave them for a machine with an edition that holds them unchanged. A `not usable here` line names a compiler this machine lacks: the same goes for the units built with it.

Run `python tools/decomp.py report`. On `EARLY-WARNING`, stop and tell the user the contract's compiler or flags are suspect: they rerun `/decomp-setup`, which can start `decomp-identify` again. Read `OPEN.md`.

### 2. Repair first

If any ticket is `blocked-reference` and no repair is running, start one background subagent. Tell it to call the Skill tool with `decomp-reference`, and give it the blocked tickets' paths. It takes the `reference` lock itself, so do not take it for it: you only release it, below. A gap unblocks many tickets at once, so this goes ahead of new writers.

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

Commit the ledger, ticket, and `PATTERNS.md` changes after each judged report, staging those paths by name (never `git commit -a` or `git add -A`): `decomp: <id> <result>`. Every commit in this step ends with the harness's attribution lines: see the Commits rule in `decomp-standards`.

### 5. Record the lesson

This is the automatic retro. When an audited match's report carries a lesson that `PATTERNS.md` does not already state, append one line:

```
- <instruction pattern> => <source idiom that produces it> [proven: <ticket id>] [added: <Unix time>]
```

Keep it under 200 characters, with no explanation. Writers read this file before every attempt, so every word costs on every attempt. Failures never go in `PATTERNS.md`: they stay in ticket notes, and `report` collects recurring ones into `OPEN.md`. Any `PATTERN-` line in the next `report` means a malformed or unproven entry: fix or delete it.

### 6. Revalidate and mirror

After every N integrations (N is in the contract), run `revalidate`. On a regression, stop picking in that unit and tell the user which tickets regressed. Its tickets are claimable again as `regressed`. After each batch of integrations, run `sync` whenever `decomp.json` enables GitHub, whatever a note says about `gh`. On exit 6, carry on with the loop and keep the line `sync` printed for the Finish report.

### 7. Link

After the revalidation step, run `python tools/decomp.py report` and read its `milestone:` line. When it says `due`, run `python tools/decomp.py link` and tell the user its result line. When the state is `finished`, run the link regardless of the milestone. A link that exits 7 means the target cannot be linked whole: not an error, and the `milestone:` line never says `due` for it.

## Finish

Report only numbers that `python tools/decomp.py report` printed: bytes and functions matched, the change since this run began, credit per model, open problems, and blocked tickets. Relay the `state:` line as the tool printed it; never decide the state yourself. Then give the next input for that state:

- **more**: run `/decomp-run` again. Say how many bytes and functions remain, from the report.
- **stuck**: name the blocked and regressed tickets, and tell the user to resolve what blocks them (a reference gap, a regression, or a machine that can build them) before running again.
- **finished**: nothing is left to run. State the link result (`pass`, or `mismatch` with its first differing offset and owner), or, when the link exited 7, that a whole-binary link is not available for this target.

If any `sync` exited 6, repeat the line it printed.

End by telling the user to start a new chat before the next `/decomp-run`.
