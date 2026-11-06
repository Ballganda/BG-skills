---
name: implement-spec
description: "Implement a Ticket batch from /to-spec and /to-tickets in code, with parallel implementer subagents."
disable-model-invocation: true
---

Implement one **Ticket batch** of a spec on a single **integration branch**. If no issue tracker is configured, tell the user to run `/setup-matt-pocock-skills`.

## Ticket batch

Arguments: a spec reference, plus optionally a label or milestone and/or a count N.

- Label or milestone only: every Ticket carrying it, run until all are done.
- N only: the next N ready Tickets of the spec.
- Both: the next N ready Tickets carrying the label.
- Neither: the next 1 ready Ticket.

A Ticket is ready when every blocker is merged into the integration branch. N is a fixed total: Tickets unblocked mid-run join only if they are in a label-only batch. Never work a Ticket outside the batch. A batch Ticket whose unfinished blocker is outside the batch is skipped and listed in the final report. State the resolved batch (numbers and titles) before starting.

## Rules

- Tickets form a **task graph**; the **frontier** is the batch Tickets that are ready. Track merges yourself; the tracker's blocked-by count lags until issues close.
- At most 3 implementer subagents at once (the user may override), run in the background, each with a fresh context window, its own worktree, and its own branch.
- Talk to subagents through **context pointers** (spec, Ticket, notes path, commits), never pasted content. Ask for a report under 100 words: branch, test result, anything blocking.

## Steps

1. Read the spec and the batch Tickets.
2. (Optional) If Tickets need shared exploration, dispatch one exploration subagent with a fresh context window to save markdown notes to a directory outside the repo; pass its path to implementers.
3. Create the integration branch, or reuse it if a prior batch made one. If the tracker closes work through PRs, or the user asks, open a draft PR after the first merge, marked as closing the spec and Tickets.
4. For each frontier Ticket, start an implementer subagent that:
   - confirms its worktree is based on the integration branch tip, resetting onto it if not;
   - calls the Skill tool with `tdd` to build the Ticket;
   - merges the integration branch tip into its branch before reporting done.
5. On each report, merge the branch into the integration branch yourself. Only on a conflict you can't resolve trivially, dispatch a merger subagent with a fresh context window.
6. Start implementers for any newly ready batch Tickets, within the cap.
7. When the batch is done, resolve each Ticket the way the tracker closes work (mark the draft PR ready only if the whole spec is now done). Report: integration branch, Tickets done, Tickets skipped and why. Review is a separate stage: suggest `/code-review`.
8. Remove the implementer worktrees.
