---
name: code-review
description: Review changes since a fixed point on Standards and Spec, in parallel sub-agents. Use when the user wants to review a branch, a PR, or work in progress.
---

Two-axis review of the diff between `HEAD` and a fixed point:

- **Standards**: does the code conform to this repo's documented coding standards?
- **Spec**: does the code faithfully implement the originating issue / spec?

Each axis runs in its own parallel reviewer subagent with a fresh context window, so neither can mask the other. If no issue tracker is configured, tell the user to run `/bg-setup`.

## Process

### 1. Pin the fixed point

Use the user's fixed point (SHA, branch, tag, `main`, `HEAD~5`, ...); if none was given, ask. Verify with `git rev-parse <fixed-point>` and `git diff --stat <fixed-point>...HEAD`: a bad ref or empty diff stops here. Don't read the full diff yourself; the reviewers do. The diff command is `git diff <fixed-point>...HEAD` (three-dot, against the merge-base); the commit list is `git log <fixed-point>..HEAD --oneline`.

### 2. Locate the spec

First match wins: issue references in the commit messages (`#123`, `Closes #45`, GitLab `!67`); a path the user passed; a spec under `docs/`, `specs/`, or `.scratch/` matching the branch or feature; otherwise ask. Confirm it exists but don't fetch its body; pass the reference. If the user says there's none, skip the Spec reviewer.

### 3. List the standards sources

Check only: `CLAUDE.md`, `AGENTS.md`, `CODING_STANDARDS.md`, `CONTRIBUTING.md`, `docs/agents/*`, and files those link to as coding standards. No repo-wide search.

The Standards axis also uses the **smell baseline** in [SMELLS.md](./SMELLS.md), which sits under the repo's standards. Don't read it yourself; the Standards reviewer does.

### 4. Spawn both reviewers in parallel

Issue both calls together, in the foreground. Start each as the **reviewer** role with a fresh context window: on Claude Code, the plugin agent `bg-skills:reviewer` with its model overridden at dispatch; on a harness without agent definitions, a general subagent on that model, given the finding format below. Read the models from the models doc (`docs/agents/models.md`, linked from the `## Agent skills` block): Standards gets the Standards review model, Spec the Spec review model. If the repo has no models doc, use the defaults: Standards on Sonnet, Spec on the top model.

Both reviewers report one line per finding, nothing else, with no word limit:

`hard or judgement | location | rule or spec line | finding`

**Standards** prompt: the diff command, the commit list, the standards-file paths, the absolute path to this skill's `SMELLS.md`, the finding format, and: "Find (a) every place the diff violates a documented standard, citing the file and the rule; and (b) any smell from `SMELLS.md`, naming the smell. Documented-standard breaches can be hard; smells are always judgement, and a documented repo standard overrides the baseline. Skip anything tooling enforces."

**Spec** prompt: the diff command, the commit list, the spec reference (fetch it via the tracker doc's workflow), the finding format, and: "Find (a) requirements the spec asked for that are missing or partial; (b) behaviour in the diff that wasn't asked for (scope creep); (c) requirements that look implemented but where the implementation looks wrong. Quote the spec line in the rule column."

### 5. Aggregate

Present the finding lines under `## Standards` and `## Spec`, verbatim. Never merge or rerank across axes: code can follow every standard yet implement the wrong thing, or the reverse. Note a skipped Spec axis. End with one line: findings per axis and the worst issue _within each axis_, no cross-axis winner.
