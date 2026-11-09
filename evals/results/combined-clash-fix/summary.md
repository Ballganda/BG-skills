# /grill eval summary

Run 2026-11-09T05:40:31.600Z, Claude Code 2.1.319, plugin bg-skills@1.3.2. Score 1, cases passed 3/3, cost $5.09.

Token and round figures are means over the with-plugin runs. Total tokens = input + cache write + cache read + output.

| Case | Score (without) | Graders passed | Total tokens | Input | Cache write | Cache read | Output | Rounds | Questions | Glossary writes | ADR writes |
|---|---|---|---|---|---|---|---|---|---|---|---|
| grill-adr-worthy | 1 (0.5) | adr-only-when-all-three 3/3<br>no-adr-for-trivial-decisions 3/3 | 74981 | 12 | 11949 | 59216 | 3804 | 1.0 | 9.3 | 0, 0, 0 | 2, 2, 2 |
| grill-small-feature | 1 (0) | numbered-with-recommendations 3/3<br>whole-frontier 3/3 | 36346 | 8 | 7464 | 27505 | 1369 | 1.0 | 5.7 | 0, 0, 0 | 0, 0, 0 |
| grill-term-clash | 1 (0.8333333333333334) | clash-called-out 3/3<br>glossary-written-inline 3/3 | 70552 | 12 | 11076 | 56541 | 2922 | 1.0 | 9.7 | 1, 1, 1 | 0, 0, 0 |
