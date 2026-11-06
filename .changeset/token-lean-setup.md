---
"bg-skills": minor
---

`bg-setup` writes leaner `docs/agents/` files, which every engineering skill reads on every run. The tracker seed templates are now conditional: the PR (or MR) triage section is written only when "PRs as a request surface" is on, the Wayfinding section only when `wayfinder` is installed, and setup checks `gh --version` once to write only the matching sub-issue and blocking commands instead of the "2.94+ / older `gh`" pairs. Every tracker operation now sits in one Operations list (create, read, list, sub-issue or parent link, blocking, count open blockers, comment, labels, close), the GitLab template gains the "never file into upstream" guard, and the domain template drops both file-tree diagrams, keeping its reading rules and writing the multi-context layout only in a monorepo. The skill's own prose is compressed with every step and branch kept.
