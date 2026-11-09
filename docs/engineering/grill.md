## What it does

`grill` interviews you about a plan or design until you and the agent share one understanding of it, and writes the vocabulary and the hard decisions into your repo while it does. It is the same interview [grill-me](../productivity/grill-me.md) runs (a round of questions, then wait, then the next round), pointed at a codebase.

It is **stateful**. Every other grilling skill leaves the session in your head; this one leaves files on disk. When a term resolves, the skill writes it to `GLOSSARY.md` at once, not in a batch at the end. When a decision passes three gates, the skill writes it as an ADR. That is the whole difference, and it also causes most of the trouble people have with the skill. The artifacts are real files in a real repo, so they can be missing when you expected them, and they can drift when more than one person writes them.

Those two files are all it writes. It edits no code, config or skill files, and it never moves down the chain by itself. When the interview is done it asks one closing question, whether you are ready to turn the result into a spec, and tells you to type `/spec-gen`. Then it stops and waits for you to type it.

## When to reach for it

You invoke this by typing `/grill`, and the agent won't reach for it on its own.

Reach for it at the start of a change, in a repo, when the plan is still fuzzy and the words for the thing are not settled yet. It is the single-session tool. Which grilling skill you want depends on what is in front of you:

| What you have | Reach for |
| --- | --- |
| You aren't working in a working directory at all | [grill-me](../productivity/grill-me.md) |
| A repo, and a change you can settle in one session | `grill` |
| An effort too big to hold in one session (a greenfield build, a large feature) | [wayfinder](wayfinder.md) |
| A repo with no domain docs at all, and no particular feature in mind | `grill`, aimed at the repo rather than a change |
| A decision blocked on knowledge in someone else's head | [to-questionnaire](../productivity/to-questionnaire.md) |

The wayfinder split comes down to session count: `/grill` for single-session planning, `/wayfinder` for multi-session planning.

## Prerequisites

The skill writes into your repo, so you need to be somewhere it is safe to write. Resolved terms go to a `GLOSSARY.md` glossary at the root, or to the relevant context's `GLOSSARY.md`, if a `GLOSSARY-MAP.md` at the root marks the repo as multi-context. Decisions go to `docs/adr/`. The skill creates both only when it needs them. Nothing exists until the first term or decision is settled, so you set up nothing in advance.

It also needs two other skills present, because its own `SKILL.md` delegates to them and adds only the write limit and the ending. [grilling](../productivity/grilling.md) supplies the interview, and [domain-modeling](domain-modeling.md) supplies the writing. Installing `grill` alone gets you a skill that does not work.

## The paper trail

Three things come out of a session, and they are not equal.

| What resolved | Where it lands |
| --- | --- |
| A term: the project's own word for a thing | `GLOSSARY.md`, inline, the moment it resolves |
| A decision that is hard to reverse, surprising without context, and a real trade-off | An ADR under `docs/adr/` |
| Everything else you decided | The conversation, and nowhere else |

That third row is the one that catches people out. `GLOSSARY.md` is only a glossary. It holds no implementation details, no spec, and no scratch notes. An ADR needs all three conditions at once, so most decisions do not qualify and most sessions produce none. A session that yields a sharper glossary and zero ADRs is working as designed, but it means most of what you agreed exists only in the context window you agreed it in. Hand that same conversation to [spec-gen](spec-gen.md) rather than clearing it.

The glossary is the main output. This skill builds domain language: the project's own words, agreed once, so you, the agent and your colleagues do not have to work them out again. Not everyone agrees that this improves agent performance. The strongest objection is that a term and its plain-English expansion get the same result from the model, and that the vocabulary mainly shortens communication between the humans who share it. On that view the glossary is still valuable, but the value goes to the humans.

## Common questions

**Should I use this or `/wayfinder`?**
Scope decides it. Use this for anything you can settle in one session; use [wayfinder](wayfinder.md) when the effort is too big to hold in one, and it charts the work as a map of decision tickets first. Wayfinder is slower and denser, and reaching for it on a well-scoped feature is the common mistake. It does not replace this skill, and it can start a grilling session for the parts of the map that suit one.

**It ran, but no `GLOSSARY.md` and no ADRs appeared.**
There are two known causes. The first is that nothing qualified. ADRs need all three gates, and a session about a change with no new vocabulary has nothing to write. The second is a real bug. When the skill runs inside another orchestration layer (a spec-driven-development wrapper, a multi-agent framework, a rule that invokes it as a step in someone else's pipeline), users report that the file-writing half silently does not happen, while the interview still runs. The bug is filed and unfixed. If you are in that setup, check the working directory before you trust the session's output.

**It asked everything at once, with no recommendations, and never mentioned `GLOSSARY.md`.**
That is the skill failing to load its two dependencies. Because `SKILL.md` delegates the interview and the writing, an agent that does not pick up [grilling](../productivity/grilling.md) and [domain-modeling](domain-modeling.md) guesses at what grilling means, and you get every question at once with no structure. Partial loading is more confusing. `grilling` loads, `domain-modeling` does not, and you get a good interview with no paper trail. How often it happens depends on the model and the effort level, and it is the most reported problem with this skill. If you suspect it, ask the agent directly which skills it loaded.

**Where did all my other decisions go?**
Into the conversation only. This is the most serious open complaint about the skill. The glossary is not a spec, most answers do not earn an ADR, and no record links each resolved answer to a spec, a ticket and a test. Later steps soften precise answers (ordering guarantees, negative requirements, numeric defaults) into weaker prose, and the result can look complete while missing the thing you decided. For now, keep the session and feed it straight to [spec-gen](spec-gen.md). Then re-read the spec against your own answers rather than assuming it captured them.

**Can I point it at an existing repo that has no docs at all?**
Yes. This is the right skill for a codebase with no ADRs, no domain language and no design principles: invoke it and say "help me document my repo". Users often pair it with [improve-codebase-architecture](improve-codebase-architecture.md) for building or repairing a `GLOSSARY.md`. Expect to steer it. It reads code and asks you about what it finds, and you decide which of the words already in the codebase are the right ones.

**What should I do when the session ends?**
Type `/spec-gen` in the same conversation. The session ends with one closing question that says so, and the agent waits for you. Answering "yes" is not enough, because [spec-gen](spec-gen.md) is user-invoked and only you can start it. If the change is small enough to build immediately, type `/implement` instead; that choice is yours too.

**Why didn't it start building when I said "agree all" or "just build it"?**
Because skipping the spec is the failure this skill now guards against. In one session an agent took "agree all", an answer to a single round, as the end of the interview and started editing files with no spec or tickets. Round answers settle that round only. A request to build mid-session gets the closing question back, so moving on is always something you type.

**Why is it called that?**
Nobody is happy with the name. There is an open suggestion to rename it `grill-domain-model`, which describes the behaviour more accurately. Nothing has moved on it. If a rename ever lands, the docs page moves with it and the URL changes.

## It's working if

- `GLOSSARY.md` changes *during* the session, term by term, rather than appearing in one lump at the end.
- The glossary reads as pure vocabulary (your project's words with tight definitions) and contains no implementation detail or spec-like prose.
- Questions the codebase can answer get answered by reading the codebase, not asked of you.
- You get few or no ADRs, and the ones you get are decisions you would be annoyed to have to argue again.
- It challenges a word you used because your existing glossary defines it differently.
- `git status` after the session shows changes only to `GLOSSARY.md` and ADRs.
- It ends with a single question telling you to type `/spec-gen`, and nothing happens until you do.

## Where it fits

`grill` is the head of the main build chain:

```txt
grill → spec-gen → ticket-gen → implement → code-review → retro
```

It comes before anything is written down as a spec. It produces the shared understanding and settled vocabulary that [spec-gen](spec-gen.md) then synthesises without interviewing you again. Its close neighbours are [grill-me](../productivity/grill-me.md), the same interview with no repo and no files, and [domain-modeling](domain-modeling.md), the glossary-and-ADR discipline it drives; both use the [grilling](../productivity/grilling.md) primitive for the interview. Upstream of it, [wayfinder](wayfinder.md) charts efforts too large for one session and can hand parts of the map back down to it. When you're unsure which skill or flow fits, [skill-map](skill-map.md) routes you.
