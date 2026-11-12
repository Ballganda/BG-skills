## What it does

`bg-setup` answers four questions about one repo: where issues live, what the triage labels are called, where the domain docs sit, and which model builds each ticket tier and runs each subagent task. It records the answers as markdown files under `docs/agents/`.

Those files are the only thing that varies between repos. The skills themselves are identical everywhere. They read `docs/agents/issue-tracker.md` at run time and do what it says. That is why the set is not tied to GitHub, and why you never edit a skill file to point it at another tracker. Invoking it with "link the skills to a custom issue tracker" works with anything you can connect to programmatically, with no changes to the skills.

Every other skill reads those files on every run, so setup writes only what your repo uses. The tracker doc gets the PR triage section only when PRs are a request surface, the Wayfinding section only when [wayfinder](wayfinder.md) is installed, and only the `gh` command forms your installed version supports. The domain doc carries its reading rules, plus the multi-context layout only in a monorepo.

It is a prompt-driven skill, not a deterministic script. It reads your `git remote`, `gh --version`, `CLAUDE.md` and `GLOSSARY.md`, proposes what it found, and waits for you to confirm before it writes anything.

## When to reach for it

You invoke this by typing `/bg-setup`; the agent won't reach for it on its own. Its metadata marks it non-invokable on purpose, so no other skill can fire it for you.

Reach for it once per repo, before the first use of any other engineering skill. If [triage](triage.md), [spec-gen](spec-gen.md), [ticket-gen](ticket-gen.md) or [wayfinder](wayfinder.md) start guessing where your issues go, or apply labels your tracker doesn't have, this repo has not been set up yet. You can run it in a repo halfway through a project. The skill reads what is already there, so no earlier work is lost.

## Prerequisites

It writes into the repo you run it in:

| It writes | Where |
| --- | --- |
| `issue-tracker.md` | `docs/agents/` |
| `domain.md` | `docs/agents/` |
| `triage-labels.md` | `docs/agents/`, only when the `triage` skill is installed |
| `models.md` | `docs/agents/` |
| An `## Agent skills` block | whichever of `CLAUDE.md` or `AGENTS.md` already exists |

You commit all of it as markdown. There is no user-level or global mode. The config lives in the repo, so every repo gets its own copy.

## The four decisions

It starts each section with the recommended answer, and skips any question its exploration already answered. Most runs need only two confirmations.

| Decision | What it proposes | When it asks |
| --- | --- | --- |
| **Issue tracker** | the one matching your `git remote` | always, because this is the one real choice |
| **Triage labels** | keep the five canonical names (`needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, `wontfix`) | only if the `triage` skill is installed |
| **Domain docs** | single-context: one `GLOSSARY.md` plus `docs/adr/` at the root | only if it spots monorepo signals, and then it offers a multi-context `GLOSSARY-MAP.md` |
| **Models** | Haiku for Mechanical tickets, Sonnet for Standard, the top model for Hard; exploration on the Mechanical model, merging and Standards review on the Standard model, Spec review on the Hard model | always; on a harness without those names it offers its smallest, middle and largest models instead |

The tracker options:

| Option | Where issues live | Needs |
| --- | --- | --- |
| **GitHub** | the repo's GitHub Issues | the `gh` CLI |
| **GitLab** | the repo's GitLab Issues | the `glab` CLI |
| **Local markdown** | files under `.scratch/<feature>/` in this repo | nothing, not even a remote |
| **Other** | wherever you say | one paragraph from you describing the workflow |

The first three ship as templates in the skill and work out of the box. Local markdown is a full option, not a fallback. The skill supports a solo project with no remote. One caveat: don't use local markdown if you use GitHub. They are alternatives, so pick one.

"Other" is a full option too. It is how Jira, Linear, Azure DevOps and Beads all work. You describe the workflow, the skill records your prose in `docs/agents/issue-tracker.md`, and the downstream skills follow the prose. Users have already built this: a Jira-over-MCP variant, a Gitea CLI shaped like `gh`, a hand-built local dashboard.

## Common questions

**Do I have to use GitHub?**

No. GitHub, GitLab and local markdown under `.scratch/` all ship as ready-made templates, and anything else works through the "other" path. This is the most-repeated question, in roughly these words: *"hard locked to github"*, *"can I use GitLab / Jira"*, *"what about Azure DevOps"*. The answer is always the same: setup chooses the tracker, not the skill.

**Do I need to re-run it after updating the skills?**

The direct answer after v1.1 was yes. The skill's own closing message is softer. It tells you to re-run only to switch trackers or start over. Both are defensible. The seed templates change between versions, so a `docs/agents/issue-tracker.md` from an older release can go out of date against the skills that now read it. Because the docs are trimmed to the repo, re-run setup too when you install `wayfinder`, upgrade `gh` past 2.94, or want external PRs triaged: each adds or swaps a section. If a downstream skill does something different from what the docs describe, re-run setup. It is cheap.

**Will a re-run overwrite lines I added to the `## Agent skills` block?**

No. Setup knows its own lines by their prefixes (`- Issue tracker:`, `- Triage labels:`, `- Domain docs:`, `- Models:`, `- Replies:`) and rewrites only those. Any other line in the block is yours: the draft lists them and asks "Keep these N lines you added?" Say yes and they stay unchanged, in their own paragraph below the list; say no and they are removed. It asks again on every re-run. A block in the older format, with a `###` heading per topic, is converted to the list, and your lines in it get the same question.

**What is the `- Replies:` line?**

A one-line rule, written word for word into the `## Agent skills` block, that shapes every reply the agent writes to you in chat: an "Understood: ..." line when you gave an instruction beyond a bare "yes", the outcome in one sentence, then bullets that each hold one fact (numbered when you answer per item). Each offer of further work is its own numbered item with a recommendation that "yes" accepts, and so is each decision when it asks two or more. Explanations stay prose, and a subagent's Report keeps its caller's format. Unlike the other lines it carries its rule instead of pointing at a file, so it holds on every turn. A repo set up earlier gets it by re-running `/bg-setup`, which adds the line when missing. If you edited it, setup shows the template next to your version and asks before rewriting.

**It wrote to `CLAUDE.md`, but I'm on Codex.**

This is a known gap, and still open. The file-selection rule is "edit `CLAUDE.md` if it exists, else `AGENTS.md`". It checks which file exists, not which harness is running. In a repo with a `CLAUDE.md` left over from Claude Code, the skill writes its `## Agent skills` block to a file Codex never reads. Users have two workarounds: move the block to `AGENTS.md` by hand, or keep `AGENTS.md` canonical and make `CLAUDE.md` a one-line pointer at it. If neither file exists, the skill asks you which to create instead of picking one. This has confused people who expected it to decide.

**Did it create my triage labels?**

Yes, on GitHub and GitLab: when the label question runs, it creates each configured label the tracker lacks. `docs/agents/triage-labels.md` is a *mapping* that tells `/triage` which strings in your tracker correspond to the five canonical roles. If your tracker already uses the canonical names, the mapping is an identity table and there is nothing to configure, which is the intended common case.

It does not create [wayfinder](wayfinder.md)'s `wayfinder:map` and `wayfinder:<type>` labels, and `gh issue create --label <missing>` fails instead of creating the label. Create them by hand before the first wayfinder run on a GitHub repo.

**Can I configure the other skills' behaviour here (grilling cadence, question format, tone)?**

No. It configures three things: tracker, labels, doc layout. Users have asked to make it the place for per-user preferences. The answer is that skills stay opinionated and take no per-user config. Preferences belong in your `CLAUDE.md` as plain instructions, which every skill already reads.

**Can I keep the config in `~/.claude` instead of committing it to every repo?**

Not today. A user who runs the skills across many repos has an open request for this, but no user-level mode exists. Every repo carries its own `docs/agents/`.

**Isn't it strange to have a skill that configures the other skills?**

One long-standing complaint says yes, in these words: *"having a skill to set up the other skill does not feel right to me: that means the LLM is configuring its own skills."* The trade-off is real. Without a setup step, every skill that touches issues would need its own copy of the tracker instructions. The output is markdown you can read and edit, and that limits the risk. You can read every file it wrote and change it by hand. Make day-to-day changes that way, not with another run.

## It's working if

- `docs/agents/issue-tracker.md`, `docs/agents/domain.md` and `docs/agents/models.md` exist, plus `triage-labels.md` if `triage` is installed.
- An `## Agent skills` section appears in the instruction file your harness reads, as a list of up to four pointers (`- Issue tracker:`, `- Triage labels:`, `- Domain docs:`, `- Models:`) plus the `- Replies:` rule. Only the tracker line and the Replies line say more than "see" the file: the tracker line names the host and repo, the Replies line holds the reply format. The triage line appears only if `triage` is installed, and the block has no marker comments.
- The tracker it proposed matches the remote you use, and the label strings match labels that exist in your tracker.
- Afterwards, `/ticket-gen` publishes without asking you where issues live, and `/triage` applies labels rather than inventing them.
- Nothing in the skill files themselves changed. If setup edited a `SKILL.md`, something went wrong.

## Where it fits

`bg-setup` is the **run-once setup** for the engineering flow, the precondition everything else assumes rather than a step in the chain. Its neighbours are its readers: [triage](triage.md), which applies the label vocabulary written here; [spec-gen](spec-gen.md) and [ticket-gen](ticket-gen.md), which publish into the tracker named here; and [wayfinder](wayfinder.md), which reads the Wayfinding section of the same tracker file (written only when wayfinder is installed) to learn how to store maps and child tickets. [domain-modeling](domain-modeling.md) later fills in the domain-doc layout that setup records. It creates `GLOSSARY.md` and ADRs only when you resolve a term or decision, so a repo with no domain docs after setup is normal. For which skill to reach for next, [skill-map](skill-map.md) routes the whole set.
