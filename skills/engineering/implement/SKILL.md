---
name: implement
description: "Implement a Ticket batch, a spec, or work described in chat, by orchestrating fresh-context implementer subagents."
disable-model-invocation: true
---

You are the orchestrator, even for a single Ticket. Never implement in your own context: every unit of work goes to an implementer subagent started with a fresh context window, so your context stays small enough to track the whole run.

## Input

- **Tickets**: resolve a **Ticket batch** (below) and run the Steps. If no issue tracker is configured, tell the user to run `/bg-setup`. For a Ticket reference, fetch it from the issue tracker and state its title first; if the reference is ambiguous, ask.
- **No Tickets** (work described in chat, or a spec not split into Tickets): a batch of one at the Standard tier. Start a single implementer subagent with a fresh context window, hand it the description (or a pointer to the spec), and have it do the implementer work from step 4 in the current checkout, without the bullets marked *Tickets only*, committing to the current branch. Skip the task graph, the integration branch, the worktree, and the script: the no-Tickets path never calls it.

## Ticket batch

Arguments: a spec reference, plus optionally a label or milestone and/or a count N.

- Label or milestone only: every Ticket carrying it, run until all are done.
- N only: the next N ready Tickets of the spec.
- Both: the next N ready Tickets carrying the label.
- Neither: the next 1 ready Ticket.

A Ticket is ready when every blocker is merged into the integration branch (`ready` below computes it). N is a fixed total with no refill: Tickets unblocked mid-run join only in a label-only batch. Never work a Ticket outside the batch. A batch Ticket whose unfinished blocker is outside the batch is skipped and listed in the final reply. State the resolved batch (numbers and titles) before starting.

## Roles and models

Start every subagent by **role**, with a fresh context window, on the model this table picks:

| Role | Agent | Model |
| --- | --- | --- |
| Implementer | `implementer` | the Ticket's tier model |
| Explorer | `explorer` | the Exploration model |
| Merger | `merger` | the Merging model |

Read the models from the models doc (`docs/agents/models.md`, linked from the `## Agent skills` block). A Ticket with no tier is Standard. If the repo has no models doc, use the defaults: Mechanical Haiku, Standard Sonnet, Hard the top model; Exploration the Mechanical model, Merging the Standard model.

On Claude Code, start the role's plugin agent (`bg-skills:<agent>`) and override its model at dispatch with the one above. On a harness without agent definitions, start a general subagent on that model and give it the role's report format.

## Rules

- Tickets form a **task graph**; the **frontier** is the batch Tickets that are ready. The script's ledger tracks merges, since the tracker's blocked-by count lags until issues close.
- At most 3 implementer subagents at once (the user may override per run), run in the background, each with a fresh context window, its own worktree, and its own branch.
- Talk to subagents through **context pointers** (spec, Ticket, notes path, commits), never pasted content.
- **Retry once, then report.** When an implementer reports failing tests or a blocker, start one fresh implementer for that Ticket on the next tier's model (Mechanical to Standard, Standard to Hard). If the retry fails too, stop work on the Ticket and list it in the final reply. A Hard Ticket that fails is not retried.

## Report formats

Each subagent reports in one fixed line, nothing else:

- Implementer: `branch | tests: pass or fail | blocker: none or text | lesson: type @ location; type @ location`
- Explorer: `notes: path`
- Merger: `merged or conflict | files`

The implementer's `lesson` field is optional, filled only when something cost it time. Each lesson's type is one of navigation, automated check, coding standard, tool economy, information access; location is a file, with a line where one applies. Collect the lesson lines for the final reply.

If the user asks what a report means, explain it in plain language.

## The script

Every mechanical step is one command of `scripts/implement.py` beside this file, run as `python3 <this skill's directory>/scripts/implement.py <command>`. Each prints one fixed line; errors go to stderr as `error: <text>`. Exit codes: 0 ok, 1 merge conflict, 2 bad arguments or a Ticket the run cannot take, 3 nothing ready, 4 environment problem, 5 the test command failed. Run `--help` for arguments.

Before the first command, run `python3 --version`. If Python 3 is missing, tell the user to install it and stop.

| Command | Does | Prints |
| --- | --- | --- |
| `begin INTEGRATION TICKET[:TIER]...` | creates or reuses the integration branch, opens the run's ledger | `begin: created or reused <branch>` |
| `ready [--cap N] [--tracker T]` | lists batch Tickets whose blockers are merged, up to the free slots | `ticket ID TIER` per Ticket, or `ready: none` (exit 3) |
| `start TICKET [--slug TEXT]` | claims a Ticket, creates or reuses its worktree and branch | `start: created or reused branch=B worktree=W` |
| `status` | one line per batch Ticket | `ticket ID STATE TIER attempts=N branch=B worktree=W`, plus `missing=` when either is gone |
| `test TICKET COMMAND` | runs COMMAND in the Ticket's worktree, logs the output | `test: pass or fail log=PATH` |
| `merge TICKET` | merges the Ticket's branch into the integration branch | `merge: merged`, or `merge: conflict files=...` (exit 1) |
| `fail TICKET` | records a failed attempt, frees the Ticket for a retry | `fail: ticket ID attempts=N` |
| `clean` | removes worktrees and branches of merged and failed Tickets | `clean: N removed` |

`ready` reads blockers from the local tracker (`--tracker local`, the default) and from GitHub (`--tracker github`). On any other tracker it exits 4: compute readiness yourself from the tracker's blocking links and your own record of merges, then pass the ids to `start`.

## Steps

1. Read the spec and the batch Tickets.
2. (Optional) If Tickets need shared exploration, start one explorer with a fresh context window to save markdown notes to a directory outside the repo; pass its path to implementers.
3. Run `begin` with the integration branch name and the batch Tickets with their tiers. If the tracker closes work through PRs, or the user asks, open a draft PR after the first merge, marked as closing the spec and Tickets.
4. Run `ready --cap 3` (or the user's cap). For each Ticket it lists, run `start`, then start an implementer on the printed worktree, on its tier's model. The implementer:
   - calls the Skill tool with `tdd` at pre-agreed seams where possible;
   - typechecks and runs the single relevant test file as it goes, and the full suite once at the end;
   - commits;
   - merges the integration branch tip into its branch before reporting done.
5. On each passing report, run `test` with the project's full suite command, then `merge`. Implementers already ran the full suite before merging the integration tip into their branch, so `test` is the orchestrator's check of that merged state; skip it when the report gives no reason to doubt it. On a `merge: conflict`, resolve it trivially yourself, or start a merger with a fresh context window. On a failing report or a failing `test`, run `fail` and apply the retry rule.
6. Run `ready` again for newly ready batch Tickets, within the cap, and repeat from step 4 until it prints `ready: none` and no implementer is running.
7. When the batch is done, resolve each Ticket the way the tracker closes work (mark the draft PR ready only if the whole spec is now done).
8. If at least one lesson line came back, call the Skill tool with `retro`, passing the lesson-line mode and the collected lesson lines. It only suggests; change nothing on its findings. If no lesson came back, skip this step.
9. Write the final reply: integration branch, Tickets done, Tickets skipped or stopped and why, the lesson lines, and retro's suggestions when it ran.
10. Run `clean`.

## Resuming

In a new chat, run `status` instead of `begin`: the ledger survives, so it shows each Ticket's state, attempts, and any missing worktree or branch. Re-run `start` on a claimed Ticket whose worktree is missing to rebuild it, then continue from step 4.

Don't review: review is a separate stage, so suggest `/code-review` when done. End the closing message with this line: Always start a new chat before `/code-review`.
