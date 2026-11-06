---
"bg-skills": minor
---

`implement` now always runs as an orchestrator, even for a single ticket: it never implements in its own context, and hands every unit of work to an implementer subagent started with a fresh context window. It takes a Ticket batch (a label or milestone, the next N ready tickets, or both; default next 1), runs up to 3 implementers at once on one integration branch, merges clean branches itself, and suggests `code-review` rather than running it. Work described in chat with no tickets is a batch of one, handed to a single implementer. `implement-spec` is removed and folded into `implement`; its docs page stays, marked archived.
