---
name: implement
description: "Implement a Ticket batch, a spec, or work described in chat, by orchestrating fresh-context implementer subagents."
disable-model-invocation: true
---

You are the orchestrator, even for a single Ticket. Never implement in your own context: every unit of work goes to an implementer subagent started with a fresh context window, so your context stays small enough to track the whole run.

## Input

- **Tickets**: resolve a **Ticket batch** (below) and run the Steps. If no issue tracker is configured, tell the user to run `/bg-setup`. For a Ticket reference, fetch it from the issue tracker and state its title first; if the reference is ambiguous, ask.
- **No Tickets** (work described in chat, or a spec not split into Tickets): a batch of one. Start a single implementer subagent with a fresh context window, hand it the description (or a pointer to the spec), and have it do the implementer work from step 4 in the current checkout, committing to the current branch. Skip the task graph, the integration branch, and the worktree.

## Ticket batch

Arguments: a spec reference, plus optionally a label or milestone and/or a count N.

- Label or milestone only: every Ticket carrying it, run until all are done.
- N only: the next N ready Tickets of the spec.
- Both: the next N ready Tickets carrying the label.
- Neither: the next 1 ready Ticket.

A Ticket is ready when every blocker is merged into the integration branch. N is a fixed total with no refill: Tickets unblocked mid-run join only in a label-only batch. Never work a Ticket outside the batch. A batch Ticket whose unfinished blocker is outside the batch is skipped and listed in the final report. State the resolved batch (numbers and titles) before starting.

## Rules

- Tickets form a **task graph**; the **frontier** is the batch Tickets that are ready. Track merges yourself; the tracker's blocked-by count lags until issues close.
- At most 3 implementer subagents at once (the user may override per run), run in the background, each with a fresh context window, its own worktree, and its own branch.
- Talk to subagents through **context pointers** (spec, Ticket, notes path, commits), never pasted content. Ask for a report under 100 words: branch, test result, anything blocking.

## Steps

1. Read the spec and the batch Tickets.
2. (Optional) If Tickets need shared exploration, dispatch one exploration subagent with a fresh context window to save markdown notes to a directory outside the repo; pass its path to implementers.
3. Create the integration branch, or reuse it if a prior batch made one. If the tracker closes work through PRs, or the user asks, open a draft PR after the first merge, marked as closing the spec and Tickets.
4. For each frontier Ticket, start an implementer subagent that:
   - confirms its worktree is based on the integration branch tip, resetting onto it if not;
   - calls the Skill tool with `tdd` at pre-agreed seams where possible;
   - typechecks and runs the single relevant test file as it goes, and the full suite once at the end;
   - commits, then merges the integration branch tip into its branch before reporting done.
5. On each report, merge the branch into the integration branch yourself. Only on a conflict you can't resolve trivially, dispatch a merger subagent with a fresh context window.
6. Start implementers for any newly ready batch Tickets, within the cap.
7. When the batch is done, resolve each Ticket the way the tracker closes work (mark the draft PR ready only if the whole spec is now done). Report: integration branch, Tickets done, Tickets skipped and why.
8. Remove the implementer worktrees.

Don't review: review is a separate stage, so suggest `/code-review` when done.
