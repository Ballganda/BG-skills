---
"bg-skills": minor
---

`code-review` keeps its smell list in `SMELLS.md` and hands the Standards reviewer its path instead of pasting it. Both axes run as the `reviewer` role with a fresh context window, on the Standards review and Spec review models from `docs/agents/models.md` (Sonnet and the top model by default). Each reviewer reports one line per finding, `hard or judgement | location | rule or spec line | finding`, in place of the old word limits, and the two axes are still reported under separate headings. The static check fails if `code-review` instructs pasting the smell list, drops the finding format, or brings back a word limit.
