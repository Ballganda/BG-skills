---
"bg-skills": patch
---

Decomp skills (in progress): `search` finds the closest solved functions from the matches ledger.

- **Fewer files read.** The similar-function bonus takes its candidates from `ledger/matches.jsonl` and reads only those ticket files, so a round no longer reads every ticket of the project. On a trial project with 24,932 tickets that scan was 7.4 s of an 8.4 s cached round. A background search uses the same path.
- **Same ranking.** The bonus and its order are unchanged. A matched ticket whose file or expected bytes cannot be read is left out, as is one that has since regressed.
- **A ticket marked matched by hand gives no bonus.** Only a match that `audit pass` recorded in the ledger counts.
