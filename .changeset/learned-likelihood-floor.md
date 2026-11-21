---
"bg-skills": patch
---

Decomp skills (in progress): a ticket stays searchable however many template rounds keep the same choice points (spec #228).

- **Floor.** No likelihood a round learned is kept below 0.01. Before, a belief that fell every round reached 0.0 after about 8 rounds, and every later `search` of the ticket died of a division by zero.
- **Reading.** A kept likelihood that is zero, negative, not a number, or not finite is read as 0.01, so a `learned.json` written by the older tool stops no search.
- **Frozen choice points.** A choice point that is inert when the round ends learns nothing from that round: it keeps the likelihoods it began with. Before, its first alternative was ranked down for every candidate that scored worse than the baseline.
- **Collected report.** A `search` call that collected a background search and then prints no summary (a refusal, or an error nothing caught) prints `{"background": <its report>}` on standard output. The error message and the exit code are unchanged.
- **Layout document.** The rows on learning across rounds state the floor, the reading rule and the frozen rule; the background rows state the report line.
