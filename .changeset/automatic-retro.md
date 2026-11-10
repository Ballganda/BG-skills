---
"bg-skills": minor
---

`retro` is now model-invoked, in its frontmatter and its Codex metadata, with a model-facing description. `implement` calls it at the end of a run when at least one implementer reported a lesson, passing the lesson lines; retro works from those lines and the files they point to, without reading session logs, and a run with no lessons skips it. `diagnosing-bugs` calls it in the live session once a fix lands. Called by either skill, retro only lists suggestions in the final report and changes nothing. Typing `/retro` works as before. The skill map describes the automatic retro, and the static check fails if retro's frontmatter and Codex metadata stop agreeing that it is model-invoked.
