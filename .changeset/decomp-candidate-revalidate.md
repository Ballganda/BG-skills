---
"bg-skills": patch
---

Decomp skills (in progress): a contract change is measured before its tag moves.

- **Candidate ref**: a branch named `c/<slug>` holds a proposed change to paths a tag freezes. `revalidate --candidate c/<slug>` accepts only such a branch, alone (no `--ref`, no `--header`), skips the frozen check for it, and lets it change any path frozen by the `decomp-setup` or `decomp-start` tag.
- **Judged by its own copy**: the tool checks the candidate out in a clean worktree and runs that tree's copy of `decomp.py` there, so the candidate's tool, adapters, manifest, and contract judge it.
- **Records nothing**: no ledger line, no status change. Exit 0 when every matched ticket still matches, nonzero with the regressed tickets listed when one does not (a matched ticket the candidate no longer holds is listed too), and 6 when a matched ticket could not be rebuilt on this machine, even when regressions are listed as well. A ticket already `regressed` on the integration branch does not count against the candidate.
- **One change flow** in [LAYOUT.md](../skills/in-progress/decomp-standards/LAYOUT.md): change on `c/<slug>`, run the candidate revalidation and show the user, merge and move the tag on their go-ahead, then a plain `revalidate` to record the outcome. `decomp-setup`, `decomp-start`, and the provisioning document reference it in place of their own orderings.
