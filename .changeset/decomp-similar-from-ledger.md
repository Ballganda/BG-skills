---
"bg-skills": patch
---

Decomp skills (in progress): `similar` takes the solved functions from the matches ledger, as `search` does.

- **Fewer files read.** `similar` reads only the tickets `ledger/matches.jsonl` names and the ticket asked about, so its cost no longer grows with the open tickets. On a trial project with 24,932 tickets the scan was about 7.4 s.
- **One answer.** `similar` and the bonus of `search` rank the same functions. The output line, its order and `--n` are unchanged.
- **A damaged ticket no longer stops it.** A matched ticket whose file or expected bytes cannot be read is left out. `similar` on a ticket with no expected bytes prints nothing and passes.
- **A ticket marked matched by hand is no longer listed.** Only a match that `audit pass` recorded in the ledger counts.
