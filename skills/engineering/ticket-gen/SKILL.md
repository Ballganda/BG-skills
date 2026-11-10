---
name: ticket-gen
description: Break a plan, spec, or conversation into tracer-bullet tickets with blocking edges, published to the configured tracker.
disable-model-invocation: true
---

# To Tickets

Break a plan, spec, or conversation into **tickets**: tracer-bullet vertical slices, each declaring the tickets that **block** it. If no issue tracker or triage labels are configured, tell the user to run `/bg-setup`.

## Process

### 1. Gather context

Work from the conversation. If the user passes a reference (spec path, issue number or URL) that wasn't written in this session, fetch its full body and comments once.

### 2. Explore (optional)

Explore only the modules the tickets touch, and skip this when the conversation already covered them. Use the glossary vocabulary and respect ADRs in the area. Look for prefactoring that makes the change easy.

### 3. Draft vertical slices

<vertical-slice-rules>

- Each slice cuts a narrow but COMPLETE path through every layer (schema, API, UI, tests): vertical, NOT a horizontal slice of one layer
- A completed slice is demoable or verifiable on its own
- Each slice is sized to fit in a single fresh context window
- Any prefactoring comes first

</vertical-slice-rules>

Give each ticket one **tier**, which picks the model that builds it:

- **Mechanical**: rename, config, docs, copy of an existing pattern.
- **Standard**: one module, a clear seam, tests that describe it.
- **Hard**: crosses modules, a new seam, concurrency, or an unclear spec.

Give each ticket its **blocking edges**: the tickets that must complete before it can start. No blockers means it can start immediately.

**Wide refactors** are the exception: one mechanical change (rename a column, retype a shared symbol) whose **blast radius** breaks call sites across the codebase, so no vertical slice can land green. Sequence it **expand–contract**:

- Expand: add the new form beside the old, so nothing breaks.
- Migrate: move call sites in batches sized by blast radius (per package, per directory), each its own ticket blocked by the expand, CI green throughout.
- Contract: delete the old form in a ticket blocked by every migrate batch.
- If batches can't stay green alone, they share an integration branch and all block a final integrate-and-verify ticket; green is promised only there.

### 4. Quiz the user

Present a numbered list; per ticket: **Title**, **Tier**, **Blocked by**, **What it delivers** (the end-to-end behaviour). Ask in one line: is the granularity right, are the edges genuine gates, should any merge or split? Say the user can change any ticket's tier. Iterate until approved.

### 5. Publish

Publish in dependency order (blockers first), using the tracker doc's operations:

- **Local files**: one file per ticket at `.scratch/<feature-slug>/issues/<NN>-<slug>.md`, numbered from `01`, using the local template. Never one combined file.
- **Real tracker**: one issue per ticket, using the issue template. Use native blocking links where available, otherwise the "Blocked by" section. If the source was an existing issue, make each ticket its sub-issue. Apply `ready-for-agent` unless told otherwise.

The **frontier** is every ticket whose blockers are all done. Do NOT close or modify any parent issue.

End the closing message with this line: Always start a new chat before `/implement`.

Acceptance criteria are testable checks only; never restate What to build. No file paths or code snippets, except a prototype snippet that encodes a decision more precisely than prose (trimmed, noted as from a prototype).

<local-ticket-template>

# <NN>: <Ticket title>

**What to build:** the end-to-end behaviour, from the user's perspective.

**Tier:** Mechanical, Standard, or Hard.

**Blocked by:** numbers/titles of gating tickets, or "None (can start immediately)".

**Status:** ready-for-agent

- [ ] Acceptance criterion

</local-ticket-template>

<issue-template>

## Parent

Reference to the parent issue (omit if none).

## Tier

Mechanical, Standard, or Hard.

## What to build

The end-to-end behaviour, from the user's perspective.

## Acceptance criteria

- [ ] Criterion

## Blocked by

- Each blocking ticket, or "None (can start immediately)". Omit when blockers are native links.

</issue-template>
