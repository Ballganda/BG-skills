---
name: implement
description: "Implement a Ticket batch, a spec, or work described in chat, by orchestrating fresh-context implementer subagents."
disable-model-invocation: true
---

You are the orchestrator, even for a single Ticket. Never implement in your own context: every unit of work goes to an implementer subagent started with a fresh context window, so your context stays small enough to track the whole run.

## Input

- **Tickets**: resolve a **Ticket batch** (below) and run the Steps. If no issue tracker is configured, tell the user to run `/bg-setup`. For a Ticket reference, fetch it from the issue tracker and state its title first; if the reference is ambiguous, ask.
- **No Tickets** (work described in chat, or a spec not split into Tickets): a batch of one at the Standard tier. Start a single implementer subagent with a fresh context window, hand it the description (or a pointer to the spec), and have it do the implementer work from step 4 in the current checkout, without the bullets marked *Tickets only*, committing to the current branch. Skip the task graph, the integration branch, and the worktree.

## Ticket batch

Arguments: a spec reference, plus optionally a label or milestone and/or a count N.

- Label or milestone only: every Ticket carrying it, run until all are done.
- N only: the next N ready Tickets of the spec.
- Both: the next N ready Tickets carrying the label.
- Neither: the next 1 ready Ticket.

A Ticket is ready when every blocker is merged into the integration branch. N is a fixed total with no refill: Tickets unblocked mid-run join only in a label-only batch. Never work a Ticket outside the batch. A batch Ticket whose unfinished blocker is outside the batch is skipped and listed in the final report. State the resolved batch (numbers and titles) before starting.

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

- Tickets form a **task graph**; the **frontier** is the batch Tickets that are ready. Track merges yourself; the tracker's blocked-by count lags until issues close.
- At most 3 implementer subagents at once (the user may override per run), run in the background, each with a fresh context window, its own worktree, and its own branch.
- Talk to subagents through **context pointers** (spec, Ticket, notes path, commits), never pasted content.
- **Retry once, then report.** When an implementer reports failing tests or a blocker, start one fresh implementer for that Ticket on the next tier's model (Mechanical to Standard, Standard to Hard). If the retry fails too, stop work on the Ticket and list it in the final report. A Hard Ticket that fails is not retried.

## Report formats

Each subagent reports in one fixed line, nothing else:

- Implementer: `branch | tests: pass or fail | blocker: none or text | lesson: type @ location; type @ location`
- Explorer: `notes: path`
- Merger: `merged or conflict | files`

The implementer's `lesson` field is optional, filled only when something cost it time. Each lesson's type is one of navigation, automated check, coding standard, tool economy, information access; location is a file, with a line where one applies. Collect the lesson lines for the final report.

If the user asks what a report means, explain it in plain language.

## Steps

1. Read the spec and the batch Tickets.
2. (Optional) If Tickets need shared exploration, start one explorer with a fresh context window to save markdown notes to a directory outside the repo; pass its path to implementers.
3. Create the integration branch, or reuse it if a prior batch made one. If the tracker closes work through PRs, or the user asks, open a draft PR after the first merge, marked as closing the spec and Tickets.
4. For each frontier Ticket, start an implementer that:
   - *Tickets only*: confirms its worktree is based on the integration branch tip, resetting onto it if not;
   - calls the Skill tool with `tdd` at pre-agreed seams where possible;
   - typechecks and runs the single relevant test file as it goes, and the full suite once at the end;
   - commits;
   - *Tickets only*: merges the integration branch tip into its branch before reporting done.
5. On each passing report, merge the branch into the integration branch yourself. Only on a conflict you can't resolve trivially, start a merger with a fresh context window. On a failing report, apply the retry rule.
6. Start implementers for any newly ready batch Tickets, within the cap.
7. When the batch is done, resolve each Ticket the way the tracker closes work (mark the draft PR ready only if the whole spec is now done). Report: integration branch, Tickets done, Tickets skipped or stopped and why, and the lesson lines.
8. Remove the implementer worktrees.

Don't review: review is a separate stage, so suggest `/code-review` when done. End the closing message with this line: Always start a new chat before `/code-review`.
