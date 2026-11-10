---
"bg-skills": patch
---

Decomp skills (in progress): `decomp-setup` gains a skill upgrade section.

- **Skill upgrade**: running `/decomp-setup` on an existing decomp project diffs the project's copy of the project tool against the skill's. When they differ, the project is upgraded as a contract change: an ADR, a fresh copy of the tool, the contract files the newer skills require (the manifest, adapters rewired to the environment variables), and the pipeline check run again, carried through the layout's change flow so the tag moves only after the candidate revalidation and the user's go-ahead.
- **One trigger**: only the user starts an upgrade. No other skill compares the copies or warns.
