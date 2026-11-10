---
"bg-skills": minor
---

The plugin ships four restricted agents (`implementer`, `explorer`, `reviewer`, `merger`), each with a default model and only the tools its role needs. `implement` starts each subagent by role with a fresh context window and overrides its model from `docs/agents/models.md`: the implementer gets its ticket's tier model (no tier means Standard; no models doc means the defaults). A failed ticket is retried once on the next tier's model, then reported; a failed Hard ticket is not retried. Subagents report in fixed one-line formats instead of a word limit, the implementer's with an optional lesson field, and you can ask the orchestrator to explain any report in plain language. Harnesses without agent definitions get the same roles through a general subagent. The static check fails if an agent loses its model or tool list, or `implement` loses a report format.
