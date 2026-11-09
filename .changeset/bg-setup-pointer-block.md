---
"bg-skills": minor
---

`bg-setup` writes a leaner `## Agent skills` block: a list of up to three pointers (`- Issue tracker:`, `- Triage labels:`, `- Domain docs:`) instead of three `###` sections, and only the tracker line carries a summary (host and repo). On a re-run, setup rewrites only the lines with those prefixes, lists any other lines in the block, and asks "Keep these N lines you added?" Kept lines stay unchanged in their own paragraph below the list. An older `###`-style block is converted to the list. No marker comments are added.
