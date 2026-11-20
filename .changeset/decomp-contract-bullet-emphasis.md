---
"bg-skills": patch
---

Decomp skills (in progress): `contract-keys` reads a contract bullet whatever Markdown emphasis it carries (spec #186, finding 1).

- **Bullets.** A bold, italic or backtick name or value reads like a plain one, with the colon inside or outside the emphasis (`- **Permuter:** not allowed`, `- **Template search**: allowed`).
- **Unchanged.** An old permuter line is still read as the template-search line, and a line that says neither allowed nor not allowed still stops with the same message.
