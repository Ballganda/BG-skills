---
name: code-review
description: "Review the changes since a fixed point (commit, branch, tag, or merge-base) along two axes: Standards (does the code follow this repo's documented coding standards?) and Spec (does the code match what the originating issue/spec asked for?). Runs both reviews in parallel sub-agents and reports them side by side. Use when the user wants to review a branch, a PR, work-in-progress changes, or asks to \"review since X\"."
---

Two-axis review of the diff between `HEAD` and a fixed point:

- **Standards**: does the code conform to this repo's documented coding standards?
- **Spec**: does the code faithfully implement the originating issue / spec?

Each axis runs in its own parallel sub-agent with a fresh context window, so neither can mask the other. If no issue tracker is configured, tell the user to run `/bg-setup`.

## Process

### 1. Pin the fixed point

Use the user's fixed point (SHA, branch, tag, `main`, `HEAD~5`, ...); if none was given, ask. Verify with `git rev-parse <fixed-point>` and `git diff --stat <fixed-point>...HEAD`: a bad ref or empty diff stops here. Don't read the full diff yourself; the sub-agents do. The diff command is `git diff <fixed-point>...HEAD` (three-dot, against the merge-base); the commit list is `git log <fixed-point>..HEAD --oneline`.

### 2. Locate the spec

First match wins: issue references in the commit messages (`#123`, `Closes #45`, GitLab `!67`); a path the user passed; a spec under `docs/`, `specs/`, or `.scratch/` matching the branch or feature; otherwise ask. Confirm it exists but don't fetch its body; pass the reference. If the user says there's none, skip the Spec sub-agent.

### 3. List the standards sources

Check only: `CLAUDE.md`, `AGENTS.md`, `CODING_STANDARDS.md`, `CONTRIBUTING.md`, `docs/agents/*`, and files those link to as coding standards. No repo-wide search.

The Standards axis also carries this **smell baseline** (Fowler, _Refactoring_ ch.3). A documented repo standard always overrides it, and each smell is a labelled judgement call ("possible Feature Envy"), never a hard violation. Skip anything tooling already enforces.

- **Mysterious Name**: a function, variable, or type whose name doesn't reveal what it does or holds. → rename it; if no honest name comes, the design's murky.
- **Duplicated Code**: the same logic shape appears in more than one hunk or file in the change. → extract the shared shape, call it from both.
- **Feature Envy**: a method that reaches into another object's data more than its own. → move the method onto the data it envies.
- **Data Clumps**: the same few fields or params keep travelling together (a type wanting to be born). → bundle them into one type, pass that.
- **Primitive Obsession**: a primitive or string standing in for a domain concept that deserves its own type. → give the concept its own small type.
- **Repeated Switches**: the same `switch`/`if`-cascade on the same type recurs across the change. → replace with polymorphism, or one map both sites share.
- **Shotgun Surgery**: one logical change forces scattered edits across many files in the diff. → gather what changes together into one module.
- **Divergent Change**: one file or module is edited for several unrelated reasons. → split so each module changes for one reason.
- **Speculative Generality**: abstraction, parameters, or hooks added for needs the spec doesn't have. → delete it; inline back until a real need shows.
- **Message Chains**: long `a.b().c().d()` navigation the caller shouldn't depend on. → hide the walk behind one method on the first object.
- **Middle Man**: a class or function that mostly just delegates onward. → cut it, call the real target direct.
- **Refused Bequest**: a subclass or implementer that ignores or overrides most of what it inherits. → drop the inheritance, use composition.

### 4. Spawn both sub-agents in parallel

Issue both calls together, in the foreground.

**Standards** prompt: the diff command, the commit list, the standards-file paths, the smell baseline pasted in full (it has no other access to it), and: "Report, per file/hunk where relevant, (a) every place the diff violates a documented standard: cite the standard (file + the rule); and (b) any baseline smell you spot: name it and quote the hunk. Distinguish hard violations from judgement calls: documented-standard breaches can be hard, but baseline smells are always judgement calls, and a documented repo standard overrides the baseline. Skip anything tooling enforces. Under 400 words."

**Spec** prompt: the diff command, the commit list, the spec reference (fetch it via the tracker doc's workflow), and: "Report: (a) requirements the spec asked for that are missing or partial; (b) behaviour in the diff that wasn't asked for (scope creep); (c) requirements that look implemented but where the implementation looks wrong. Quote the spec line for each finding. Under 400 words."

### 5. Aggregate

Present the reports under `## Standards` and `## Spec`, verbatim or lightly cleaned. Never merge or rerank across axes: code can follow every standard yet implement the wrong thing, or the reverse. Note a skipped Spec axis. End with one line: findings per axis and the worst issue _within each axis_, no cross-axis winner.
