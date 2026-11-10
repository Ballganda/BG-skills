---
"bg-skills": minor
---

`ticket-gen` assigns each ticket a tier (Mechanical, Standard, Hard) while drafting, shows it in the quiz where you can change it, and writes it into both ticket templates. `bg-setup` asks which model serves each tier (defaults Haiku, Sonnet, top model) and each subagent task (exploration, merging, Standards review, Spec review), offers the harness's smallest, middle and largest models elsewhere, writes `docs/agents/models.md`, and points to it from the `## Agent skills` block. The static check fails if either template loses its tier field or `bg-setup` stops writing the models doc.
