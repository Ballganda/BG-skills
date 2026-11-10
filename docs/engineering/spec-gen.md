## What it does

`spec-gen` turns the conversation you have just had into a **spec**, and publishes it to your issue tracker as a single issue.

It does not interview you. When you reach for it, the deciding is already done. So it synthesises what is known (from the thread, the codebase, your `GLOSSARY.md` and ADRs) and does not start a new round of questions. The spec records decisions you already made. It is not a place to make new ones.

## When to reach for it

You invoke this by typing `/spec-gen`; the agent won't reach for it on its own.

Reach for it when the build is too big for one agent session and must be split across several. That is the whole trigger:

| Where you are | What to run |
| --- | --- |
| You haven't decided anything yet | [grill](grill.md) first |
| Decided, and the work fits one context window | [implement](implement.md): skip the spec |
| Decided, and the work spans several sessions | `/spec-gen`, then [ticket-gen](ticket-gen.md) |
| A [wayfinder](wayfinder.md) map has cleared | `/spec-gen #<map_issue>` |
| You grilled an [improve-codebase-architecture](improve-codebase-architecture.md) candidate | `/spec-gen A2` (its ID), in the same session |

## Prerequisites

`spec-gen` publishes the spec as an issue, so [bg-setup](bg-setup.md) must first configure a tracker and the triage-label vocabulary for this repo. Either kind of tracker works: a real tracker like GitHub, or local markdown files under `.scratch/`, which work with no extra setup.

## The spec is a decision record

The spec exists because context windows end. You settled many things while grilling: the shape of the solution, the choices you argued through, and what you deliberately refused. All of that is in one conversation that will eventually end. The spec keeps it.

The skill's closing message ends with one line: if your context is over 150k, it is suggested to clear or start a new chat before `/ticket-gen`. The agent cannot read its own token count, so the line is conditional on what you see. Under 150k, carry straight on.

So the spec does not validate or decide anything. It records what you decided, in your project's own vocabulary, so a fresh session can pick up the work without you explaining it again. If the spec states something you never said, that is a defect.

## Seams before prose

Before it writes anything, `spec-gen` sketches the **seams** where the feature will be tested, and checks them with you. It prefers existing seams to new ones, and picks the highest seam it can. The ideal number of seams for a change is one.

Other skills use those agreed seams later. [tdd](tdd.md) works only at seams you agreed in advance. [code-review](code-review.md) reviews the diff against the spec, so a seam nobody agreed to shows up as a review finding. Both connections go through this document. That is why you should take the seam conversation seriously here, and not leave it for implementation.

## Common questions

**Where did `/to-prd` go?**
It is this skill, renamed in v1.1. "Spec" is now the one term used throughout, and the old `to-prd` slug no longer works, so reinstall under the new name. The old vocabulary is replaced by the pair *spec* and *tickets*. The spec is the destination and the decisions that fix it. The tickets are the steps that get there. If you change direction, delete the unfinished tickets and keep the spec.

**Why does the spec get the `ready-for-agent` label? I don't want an agent implementing off it.**
The label means "no further triage needed": the document is complete enough for an agent to work from. It marks an input, not a work order. But AFK agents that poll for `ready-for-agent` cannot see that difference. They will try to build the whole spec in one run instead of picking up the ticket slices. This is the most-reported problem with the skill. Until it changes, exclude the parent spec explicitly in your AFK agent's prompt, or remove the label after `/ticket-gen` has run.

**Why not go straight from grilling to `/ticket-gen` and skip the spec?**
Often you should. The spec is worth its step only on multi-session work. Its value is that the tickets are disposable and the spec is not. Each ticket is sized for one fresh context window and then gets deleted or closed, while the spec stays as the one place that records the reasoning behind them. On a single-session change, that gives you nothing, and you pay for an extra synthesis step where the model can drift. Go from grilling to `/implement`.

**I just finished a wayfinder map. What do I feed it?**
Give it the main map issue, `/spec-gen #<map_issue>`, not the individual decision tickets. [wayfinder](wayfinder.md) produces decisions spread across a map, not deliverables. `spec-gen` collapses them into one document you can build from. If you loop the map straight into `/implement`, you lose that step.

**Is the spec for me to review, or is it just for the agent?**
Mostly for the agent, and it reads that way: complete, dense, and full of references. Read the seams and the out-of-scope section. In those two places, a wrong decision is cheapest to catch now and most expensive to find later. It is leaner than it used to be: one user story per distinct behaviour, no boilerplate on what makes a good test, and no empty sections. There is still no summary mode. If the spec surprises you, the grilling was too shallow; the spec is not too long.

**Do I keep the spec frozen once tickets start, or let the agent rewrite it?**
Nothing keeps it in sync. In practice it is a snapshot of what you knew at that moment, and it goes out of date the first time implementation teaches you something. Treat it as disposable after the work ships. Your `GLOSSARY.md` and ADRs are the files meant to last. If you learn something during implementation that should last, put it there, not in an edited spec.

**My work is a refactor or a module boundary, not a feature. Does the template fit?**
Better than it did. Stories are one per distinct behaviour and any section with nothing to say is left out, so a refactor spec can carry few or no stories and lean on the implementation-decisions and testing-decisions sections. Record the lasting architectural decisions as ADRs through [grill](grill.md), not in the spec.

**Will it check the tracker for related work, or cite the ADRs it's respecting?**
No to both. It reads and follows the ADRs for the area it touches, but it does not link them. It also does not search the tracker for overlapping issues before it writes, so a spec can duplicate work that someone already filed, and nothing warns you. If the area is busy, search the tracker yourself first.

**`/ticket-gen` couldn't read my spec: it kept truncating.**
A tracker issue may not return a very large spec in full, and there is no local copy to use instead. To fix this, do not clear or compact between `/spec-gen` and `/ticket-gen`. Run them in the same window, and `/ticket-gen` never has to fetch the spec again.

## It's working if

- It starts writing instead of asking you a new round of questions.
- It shows you the seams before it writes, and proposes as few as it can.
- It uses your project's nouns, not generic product-management boilerplate.
- You remember making every decision in it. It invented nothing to fill a section.
- The out-of-scope section lists real things. The things you refused are usually the most useful lines on the page.

## Where it fits

`spec-gen` is a step in the main build chain, but only on the multi-session branch of it:

```txt
grill → spec-gen → ticket-gen → implement → code-review → retro
```

Upstream, [grill](grill.md) makes the decisions that this skill only records, and a finished [wayfinder](wayfinder.md) map joins the chain here. Downstream, [ticket-gen](ticket-gen.md) cuts the spec into tracer-bullet tickets for [implement](implement.md) to build. When you're unsure which skill or flow fits, [skill-map](skill-map.md) routes you.
