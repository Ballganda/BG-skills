---
"bg-skills": patch
---

Decomp skills (in progress): the `search` summary's diff window no longer hides that text is missing (spec #186, finding 4).

- **Cut mark.** A report line longer than the window width of 120 characters is cut inside the width and ends in ` ...`. A shorter line is unchanged.
- **Empty report.** When the best candidate's report holds fewer than 2 lines, the summary's `notice` says in one line that the diff report holds no instruction diff, and names the diff adapter as the fix.
