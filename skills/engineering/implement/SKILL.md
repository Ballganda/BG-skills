---
name: implement
description: "Implement a piece of work based on a spec or set of tickets."
disable-model-invocation: true
---

Implement the work the user points to: a spec, a Ticket, or the plan in the conversation. For a Ticket reference, fetch it from the issue tracker and state its title first; if the reference is ambiguous, ask.

- Call the Skill tool with "tdd" at pre-agreed seams where possible.
- Typecheck and run the single relevant test file as you go; run the full suite once at the end.
- Commit to the current branch. Don't review: review is a separate stage, so suggest `/code-review` when done.
