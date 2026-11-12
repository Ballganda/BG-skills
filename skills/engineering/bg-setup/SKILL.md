---
name: bg-setup
description: Set up this repo's issue tracker, triage labels, and domain docs. Run once before the other engineering skills.
disable-model-invocation: true
---

# BG Setup

Scaffold the per-repo config the engineering skills read: the **issue tracker**, the **triage labels** for the five canonical roles, the **domain docs** layout, and the **models** that build each ticket tier and run each subagent task. Every skill reads these files on every run, so write only what this repo uses. Explore, present findings, confirm, then write.

## Process

### 1. Explore

Read what exists; don't assume:

- `git remote -v` and `.git/config`: GitHub, GitLab, or neither? Which repo?
- `gh --version`, once (GitHub only): decides which command forms the tracker doc gets.
- `AGENTS.md` and `CLAUDE.md` at the root: which exist, and does either already have `## Agent skills`?
- `GLOSSARY.md` / `GLOSSARY-MAP.md` at the root, and the legacy `CONTEXT.md` / `CONTEXT-MAP.md`. If a legacy file exists, offer to `git mv` it to its `GLOSSARY` name and rewrite those names in `docs/agents/domain.md`.
- `docs/adr/` and any `src/*/docs/adr/`.
- `docs/agents/`: prior output of this skill.
- `.scratch/`: a sign of the local-markdown tracker.
- Whether `triage` and `wayfinder` are installed (a skill folder alongside this one, or in your available skills). `triage` decides whether Section B runs; `wayfinder` decides whether the tracker doc gets its Wayfinding operations section.
- Monorepo signals: `pnpm-workspace.yaml`, a `workspaces` field in `package.json`, or a populated `packages/*` with its own `src/`. None means single-context, which is almost every repo.

### 2. Present findings and ask

Summarise what's present and missing, then take the sections in order, one answer each. Lead each with the recommended answer so the user can accept it in a word. Skip a section exploration already settled (B without `triage`, C without monorepo signals).

**Section A: Issue tracker.** Where this repo's issues live; `spec-gen`, `ticket-gen`, `triage` and others read and write it. Propose GitHub if a remote points at GitHub, GitLab if one points at `gitlab.com` or a self-hosted GitLab. Otherwise offer:

- **GitHub**: the repo's GitHub Issues, via `gh`.
- **GitLab**: the repo's GitLab Issues, via [`glab`](https://gitlab.com/gitlab-org/cli).
- **Local markdown**: files under `.scratch/<feature>/` (solo projects, no remote).
- **Other** (Jira, Linear, etc.): the user describes the workflow in a paragraph, recorded as prose.

The GitHub and GitLab docs carry a "PRs as a request surface" flag, default **off**. Leave it off and don't raise it.

GitHub or GitLab needs a reachable repo. If no remote points at the chosen host, get the URL from the user and wire it up (`git init` if needed, `git remote add origin <url>`). Done when `gh repo view` / `glab repo view` prints the project from this directory; if it can't, stop and tell the user what's missing.

**Section B: Triage labels.** Only when `triage` is installed. Ask exactly one question:

> Do you want to keep the default triage labels? (recommended: **yes**)

Defaults: each label string equals its role, `needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, `wontfix`. On **yes**, write them as-is. On no (usually because the tracker already uses other names, e.g. `bug:triage`), collect the overrides so `triage` applies existing labels instead of creating duplicates.

**Section C: Domain docs.** Default **single-context** (one `GLOSSARY.md` plus `docs/adr/` at the root); write it without asking. Offer **multi-context** (a root `GLOSSARY-MAP.md` pointing to per-context `GLOSSARY.md` files) only when exploration found monorepo signals, then confirm the layout.

**Section D: Models.** Ticket tiers (Mechanical, Standard, Hard, set by `ticket-gen`) and subagent tasks each name a model. Ask once, leading with the defaults:

- Tiers: Mechanical on Haiku, Standard on Sonnet, Hard on the top model.
- Tasks: exploration on the Mechanical model, merging on the Standard model, Standards review on the Standard model, Spec review on the Hard model.

On a harness without those names (not Claude Code), offer its smallest model for Mechanical, its middle one for Standard, and its largest for Hard, and let the user name them.

### 3. Confirm and edit

Show a draft of the `## Agent skills` block (for the file picked in step 4) and of `docs/agents/issue-tracker.md`, `docs/agents/domain.md`, `docs/agents/models.md`, and `docs/agents/triage-labels.md` (only with `triage`). If an existing block holds lines that aren't setup's (see step 4), list them in the draft and ask "Keep these N lines you added?" Let the user edit before writing.

### 4. Write

**Pick the file to edit:**

- If `CLAUDE.md` exists, edit it.
- Else if `AGENTS.md` exists, edit it.
- If neither exists, ask the user which to create; don't pick for them.

Never create `AGENTS.md` when `CLAUDE.md` exists (or vice versa). If an `## Agent skills` block already exists, update it in place rather than appending a duplicate, and leave the surrounding sections alone.

The block points; each `docs/agents/*.md` file owns its topic, so restate nothing they define. The one exception is the Replies line: it carries its rule inline, so it holds on every turn without a read:

```markdown
## Agent skills

- Issue tracker: [host] Issues on `<owner>/<repo>` via `[cli]`. See `docs/agents/issue-tracker.md`.
- Triage labels: see `docs/agents/triage-labels.md`.
- Domain docs: see `docs/agents/domain.md`.
- Models: see `docs/agents/models.md`.
- Replies: to the user in chat. If the message gave an instruction, decision or correction, open with one line, "Understood: <your interpretation>". Then the outcome in one line. Then bullets, one fact per line; number them when the user answers per item. Use a table to compare items across attributes, a code block for commands and code. Two or more decisions: number each with a recommendation that "yes" accepts. Write prose when the user asks for an explanation. A subagent's Report follows its caller's format.
```

For local markdown or "other", the tracker line names where issues live instead of host and repo. Include the triage line, and write `docs/agents/triage-labels.md`, only when Section B ran.

Setup's lines are the ones starting `- Issue tracker:`, `- Triage labels:`, `- Domain docs:`, `- Models:`, `- Replies:`; add no marker comments. On a re-run, add the `- Replies:` line when it is missing. When the existing one differs from the template, show both and ask before rewriting it. An older block with `### Issue tracker` / `### Triage labels` / `### Domain docs` headings is setup's too: replace each heading and setup's own sentence under it (the one pointing at its `docs/agents/` file) with the list. Anything else under those headings, including words added after setup's sentence on the same line, is the user's. The block runs from `## Agent skills` to the next `#` or `##` heading, or the end of the file; every other non-blank line inside it is the user's. Rewrite only setup's lines. Kept user lines go unchanged, in their original order, in their own paragraph below the list; lines the user declined are dropped.

When Section B ran on GitHub or GitLab, create each configured label the tracker lacks (`gh label create` / `glab label create`).

Write the docs from the seed templates in this folder:

- [issue-tracker-github.md](./issue-tracker-github.md), [issue-tracker-gitlab.md](./issue-tracker-gitlab.md), [issue-tracker-local.md](./issue-tracker-local.md): the chosen tracker
- [triage-labels.md](./triage-labels.md): label mapping (only with `triage`)
- [domain.md](./domain.md): domain consumer rules
- [models.md](./models.md): the model for each tier and subagent task

Trim each template to this repo before writing:

- Fill in placeholders such as `<owner>/<repo>`.
- `<!-- if: prs -->` blocks: keep only when the PR/MR flag is on. `<!-- if: wayfinder -->`: only when `wayfinder` is installed. `<!-- if: multi-context -->`: only for the multi-context layout. Drop the markers either way.
- Version-tagged forms (`[gh 2.94+]` / `[gh <2.94]`): keep only the one matching the installed version, without its tag.
- Swap in the repo's real glossary and ADR paths where they differ from the defaults.

For "other" trackers, write `docs/agents/issue-tracker.md` from the user's description, covering the same operations as the GitHub template.

### 5. Done

Tell the user setup is complete and which engineering skills now read these files. They can edit `docs/agents/*.md` directly; re-run this skill to switch trackers, turn on PR triage, pick up a newly installed `wayfinder`, or start over.
