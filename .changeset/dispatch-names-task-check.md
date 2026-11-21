---
"bg-skills": minor
---

The skill check now fails, with file and line, on a paragraph or list item that holds "fresh context window" (a subagent dispatch) in a skill file or a file it links and names no models doc task, so no later skill lets a subagent silently inherit its caller's model. `research` now runs its background agent on the models doc's Research task (default the Standard model), and `code-review`, `implement` (its merger and implementer dispatches) and `chief-of-staff` name their task or tier model in the same paragraph. The check recognises the writing rule's own sentence, the paragraph that introduces `implement`'s role table, a single-fresh-context-window slice size, and a dispatch on the Ticket's tier model.
