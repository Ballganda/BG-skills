---
"bg-skills": minor
---

A pull request closes only its spec. `implement` closes each ticket as it merges into the integration branch, with a comment naming the branch and the merge commit, lists the tickets in the draft PR body without closing keywords, updates an open PR for a review-fix batch, and marks the PR ready only when every sub-issue of the spec is closed. `ticket-gen` makes tickets from a review of an open PR sub-issues of that PR's spec. The `bg-setup` tracker templates and this repo's tracker doc gain a Closing work section, and `pr` follows it.
