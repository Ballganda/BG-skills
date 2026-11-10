## What it does

`implement` builds work that has already been decided: a **Ticket batch** of a spec's tickets, a spec that was never split up, or work you just described in the conversation. Every run is an orchestration, even for one ticket. The orchestrating agent never writes the code itself; it hands each unit of work to an implementer subagent started with a fresh context window, so its own window stays small enough to track the whole run. Each implementer drives [tdd](tdd.md) at the seams, typechecks as it goes, and commits.

It never reopens the plan. There is no interview, no clarifying round, no proposal of a different approach. It does not review its own work either: [code-review](code-review.md) is the next stage, run separately.

## When to reach for it

You invoke this by typing `/implement`, and the agent won't reach for it on its own. It ships with `disable-model-invocation: true`, so no other skill can call it either.

| The work is… | Reach for |
| --- | --- |
| Tickets on the tracker with blocking edges | `/implement` with the spec, plus a label, a count, or both |
| One ticket | `/implement #42`: a batch of one, still built by a subagent |
| A spec, not yet split up, and the build spans sessions | [ticket-gen](ticket-gen.md) first, then `/implement` |
| A small spec, or a plan you just agreed in the conversation | `/implement` right there; with no tickets it is a batch of one |
| Not written down anywhere yet | [grill](grill.md), or [grill-me](../productivity/grill-me.md) if there's no codebase |
| One concrete behaviour you want test-first, with no spec | [tdd](tdd.md) directly |
| Already built, and you want it checked | [code-review](code-review.md) directly |

If the plan lives only in the thread, say so when you invoke it, so the orchestrator hands that description to the implementer instead of hunting for a file.

## Prerequisites

- **An issue tracker**, for ticket work. The skill reads the tickets from, and resolves them on, the tracker [bg-setup](bg-setup.md) configured. If none has been configured, it stops and tells you to run that first. Work described in chat needs no tracker.
- **A harness that runs subagents**, ideally in the background with a git worktree each. On a harness that runs them one at a time, a multi-ticket batch still works, only serially.
- **The right branch checked out.** Chat work commits to the branch you are on; ticket work lands on an integration branch the run creates or reuses.

## The Ticket batch

One run works one batch, and you choose it:

| Argument | Batch |
| --- | --- |
| Nothing | The next 1 ready ticket |
| `next N` | The next N ready tickets, a fixed total: tickets unblocked mid-run wait for the next run |
| A label or milestone | Every ticket carrying it, worked until all are done |
| Both | The next N ready tickets carrying the label |

The orchestrator reads the tickets as a **task graph**, not a list. A ticket is ready once every blocker has merged into the integration branch, and the ready set is the **frontier**, run in parallel up to 3 implementers at once (raise or lower the cap per run). A batch ticket whose unfinished blocker sits outside the batch is skipped and reported, never pulled in. The orchestrator states the resolved batch before it starts.

## The integration branch

Everything from a ticket batch lands on one branch. Each implementer works in its own worktree based on the integration branch tip, builds its ticket with `tdd`, runs single test files as it goes and the full suite once at the end, commits, and merges the integration branch tip into its own branch before reporting done. The orchestrator then does the merge itself; a merger subagent is started only for a conflict it cannot resolve trivially.

Implementers talk to the orchestrator through context pointers (the spec, the ticket, shared exploration notes, earlier commits) rather than pasted summaries, and report back in one fixed line (branch, test result, blocker, and any lessons). That is what keeps the orchestrator's window small across a long batch.

When the run ends, the closing message tells you to always start a new chat before `/code-review`, so the review starts from the diff and the spec alone.

Chat work skips all of this. Its one implementer works in your current checkout with no worktree, builds with `tdd` the same way, and commits straight to the branch you are on.

A pull request opens only if your tracker closes work through PRs or you ask for one. Otherwise the run stops on the integration branch with every ticket resolved, which works fully offline against a local markdown tracker.

## Tiers, models and roles

Each ticket carries a **tier** from [ticket-gen](ticket-gen.md), and the tier picks the implementer's model from the models doc [bg-setup](bg-setup.md) writes:

| Tier | Default model | If it fails |
| --- | --- | --- |
| Mechanical | Haiku | One retry on the Standard model, then reported |
| Standard (also any ticket with no tier, and chat work) | Sonnet | One retry on the Hard model, then reported |
| Hard | The top model | Reported, not retried |

A repo set up before the models doc existed runs on these defaults until you rerun setup. A ticket that still fails after its retry is stopped and listed in the final report, so a bad ticket never climbs every tier.

On Claude Code, each subagent runs as one of the plugin's **restricted agents** (implementer, explorer, merger, plus the reviewer [code-review](code-review.md) uses), each with only the tools its role needs, so it starts from a lower token floor. The orchestrator overrides the agent's model at dispatch. Other harnesses get the same roles and models through a general subagent.

## Common questions

**The subagent reports are one terse line. What do they mean?**

That is by design: each role reports in a fixed line (the implementer's is `branch | tests | blocker | lesson`) so the orchestrator's window holds only what it acts on. Ask the orchestrator to explain any report in plain language and it will.

**Why did a ticket run on a bigger model than its tier?**

Its first implementer reported failing tests or a blocker, so the orchestrator retried it once on the next tier's model. The final report lists any ticket that failed the retry too, and any Hard ticket that failed.


**Where did `implement-spec` go?**

It was folded into this skill. `implement` used to build one ticket in your own window while `implement-spec` orchestrated a whole spec; now `implement` always orchestrates, and its default batch is the next 1 ready ticket. `/implement #42` and `/implement <spec> next 3` replace the two old entry points.

**Why use a subagent for a single ticket?**

So the orchestrating session stays small. A non-trivial ticket's exploration, red-green loop, and full suite can run past 100k tokens; in a subagent that cost is thrown away when it reports, and your session keeps only the report. You can run the next batch from the same window without clearing first. If one ticket still burns its whole window, the ticket is too big: right-size it in [ticket-gen](ticket-gen.md).

**How do I stop it doing too much in one run?**

Give it a smaller batch. With no argument it builds only the next ready ticket. `next 3` builds three and stops, even if finishing them unblocks more. A label alone is the one batch that keeps going until every ticket carrying it is done.

**Blocked tickets never start, even after their blocker has merged.**

The tracker's blocked-by count only drops when a blocker *closes*, and tickets typically close at the end of the run. The orchestrator tracks merges into the integration branch itself and computes the frontier from that. If you still see it, check whether the blocker is outside the batch: those are skipped by design, and the final report lists them.

**Two implementers collided on the same file, or picked different names for the same thing.**

Worktrees don't remove collisions; they postpone them to merge time. Two tickets on "different parts of the codebase" still share a message catalogue, a config registry, or a type, and each implementer sees only its own ticket. One user's web and mobile tickets added the same string as `blockedSince` and `blockedOn`. When two frontier tickets touch one shared file, add a blocking edge between them, or have shared exploration notes fix the exact names each ticket adds.

**Can I still run several `/implement` sessions side by side?**

Don't, in one checkout. One field report describes a `git commit --amend` in one session landing on another session's commit, a stash vanishing from `refs/stash`, and commits landing on the wrong branch, all in one afternoon. The sessions share one working directory, one index, and one HEAD. Give one run a bigger batch instead: the orchestrator already parallelises across worktrees.

**`code-review` says it cannot see my changes.**

`code-review` reviews `git diff <fixed-point>...HEAD`, which excludes staged and working-tree changes. `implement` commits before it stops, so review against the point you branched from (for a ticket batch, the integration branch's base). Run it as its own stage, ideally in a fresh session: an agent reviewing the code it just orchestrated is biased toward its own solution.

**A ticket's key test was skipped inside its worktree, and it reported green.**

A worktree holds only what git tracks. Tests that read gitignored fixtures, local databases, or credentials can silently skip there. For a ticket whose verification depends on untracked material, tell the orchestrator to run it in the main checkout instead.

**`/implement #2` worked on something completely unrelated.**

The agent resolved `#2` against another numbered list in context rather than the configured tracker. `implement` now fetches a passed reference from the issue tracker and states its title before starting, and asks when the reference is ambiguous. Passing the issue URL or `owner/repo#2` removes the ambiguity entirely.

## It's working if

- The session opens by stating the resolved batch (ticket numbers and titles), or the one piece of chat work it is handing off, rather than asking you what to build.
- The orchestrating session never edits code itself: every change arrives from a subagent's report.
- Each ticket's implementer runs on its tier's model, and every subagent report is a single line.
- Several implementers (up to 3) run at once whenever the graph allows, and a ticket starts as soon as its last blocker lands.
- Every implementer's trace shows a `tdd` Skill tool call, repeated typechecks and single test files, and one full suite near the end.
- The run ends on one branch with every batch ticket resolved or listed as skipped, and suggests `/code-review` instead of running it.

## Where it fits

`implement` is the build step of the main chain:

```txt
grill → spec-gen → ticket-gen → implement → code-review → retro
```

Its neighbours are [ticket-gen](ticket-gen.md), which declares the blocking edges it reads as a task graph; [tdd](tdd.md), which each implementer drives at the seams; and [code-review](code-review.md), the next stage, which you run after it commits. It trusts what the planning skills hand it and does not re-validate their shape, which is why [wayfinder](wayfinder.md) merges onto the chain at [spec-gen](spec-gen.md) rather than looping its map straight into `implement`. [skill-map](skill-map.md) is the router over the whole set when you are not sure which flow you are in.
