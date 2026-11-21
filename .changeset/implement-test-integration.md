---
"bg-skills": patch
---

Implement: the orchestrator can test the integration branch tip (spec #218).

- **Script.** `test --integration COMMAND` runs the command at the integration branch tip, in the worktree that has the branch checked out or a temporary one, with the usual `test: pass` or `test: fail` line and exit codes. The log is `integration@N.log`, so a second run keeps the first. A dirty integration checkout exits 4, and `test` on a merged Ticket exits 2 with a message naming the option.
- **Skill and docs.** The command table lists the new form, the merge step runs it once after the last merge of the batch with the project's full suite command and reports a failure in the final reply, and the implementer step points at the project's own rule for waiting on a long run.
