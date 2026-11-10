---
"bg-skills": minor
---

`implement` now drives a bundled Python 3 script for the mechanical steps of a ticket run: integration branch, readiness, worktrees, testing, merging, recording failures, and cleanup, each one command with a one-line result. The skill gets shorter, and a run can resume in a new chat from `status`. Readiness is read from local and GitHub trackers; on other trackers the orchestrator computes it and passes ticket ids to `start`. Without Python 3 the skill tells you to install it and stops. Work described in chat does not use the script.
