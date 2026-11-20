---
"bg-skills": patch
---

Decomp skills (in progress): a template round that adds nothing is no attempt (spec #186, finding 8).

- **No choice point.** `search` refuses a file with no choice point before any build. The message says a template needs a choice point and that a plain compile is `check`'s job.
- **Repeat.** A round whose candidates were all served from the result cache, as when an unchanged template is run again, returns its summary with `"repeat": true`. It adds no record to the check trail, does not count towards the advice to stop after 2 rounds with no new best score, and starts no background search.
- A round that builds even one new candidate counts as before.
