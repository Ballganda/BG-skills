# /grill eval summary

Run 2026-11-09T04:49:51.547Z, Claude Code 2.1.319, plugin bg-skills@1.3.2. Score 1, cases passed 3/3, cost $4.22.

Token and round figures are means over the with-plugin runs. Total tokens = input + cache write + cache read + output.

| Case | Score (without) | Graders passed | Total tokens | Input | Cache write | Cache read | Output | Rounds | Questions | Glossary writes | ADR writes |
|---|---|---|---|---|---|---|---|---|---|---|---|
| grill-adr-worthy | 1 (0.5) | adr-only-when-all-three 3/3<br>no-adr-for-trivial-decisions 3/3 | 57221 | 10 | 10374 | 43731 | 3106 | 1.0 | 9.0 | 0, 0, 0 | 2, 1, 0 |
| grill-small-feature | 1 (0.16666666666666666) | numbered-with-recommendations 3/3<br>whole-frontier 3/3 | 37367 | 8 | 7970 | 28037 | 1353 | 1.0 | 5.3 | 0, 0, 0 | 0, 0, 0 |
| grill-term-clash | 1 (1) | clash-called-out 3/3<br>glossary-written-inline 3/3 | 70192 | 12 | 10951 | 56526 | 2703 | 1.0 | 8.7 | 1, 1, 1 | 0, 0, 0 |
