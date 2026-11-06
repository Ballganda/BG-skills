---
name: to-spec
description: "Turn the current conversation into a spec and publish it to the project issue tracker: no interview, just synthesis of what you've already discussed."
disable-model-invocation: true
---

Synthesize the current conversation and codebase understanding into a spec. Do NOT interview the user. If no issue tracker or triage labels are configured, tell the user to run `/setup-matt-pocock-skills`.

## Process

1. Explore only the modules this spec touches, and skip this when the conversation already covered them. Use the project's glossary vocabulary and respect ADRs in the area.
2. Sketch the test seams: prefer existing seams, use the highest seam possible, and propose new ones as high as you can. Fewer is better; one is ideal. Confirm the seams with the user.
3. Write the spec from the template, then publish it to the issue tracker with the `ready-for-agent` triage label.

## Template

Omit any section with nothing to say.

<spec-template>

## Problem Statement

The problem, from the user's perspective.

## Solution

The solution, from the user's perspective.

## User Stories

A numbered list: `As an <actor>, I want a <feature>, so that <benefit>`. One story per distinct behaviour or actor goal. Cover every behaviour; never restate one.

## Implementation Decisions

Decisions made: modules built or modified and their interfaces, technical clarifications, architecture, schema changes, API contracts, specific interactions.

No file paths or code snippets; they go stale. Exception: a prototype snippet that encodes a decision more precisely than prose (state machine, reducer, schema, type shape) goes inline in its decision, trimmed to the decision-rich parts, noted as from a prototype.

## Testing Decisions

Which modules are tested, at which seams, and prior art (similar tests in the codebase).

## Out of Scope

What this spec excludes.

## Further Notes

Anything else.

</spec-template>
