# /grill eval summary

Run 2026-11-09T04:36:40.225Z, Claude Code 2.1.319, plugin bg-skills@1.3.2. Score 0.888888888888889, cases passed 1/3, cost $3.72.

Token and round figures are means over the with-plugin runs. Total tokens = input + cache write + cache read + output.

| Case | Score (without) | Graders passed | Total tokens | Input | Cache write | Cache read | Output | Rounds | Questions | Glossary writes | ADR writes |
|---|---|---|---|---|---|---|---|---|---|---|---|
| grill-adr-worthy | 1 (0.5) | adr-only-when-all-three 3/3<br>no-adr-for-trivial-decisions 3/3 | 58818 | 10 | 11502 | 44006 | 3300 | 1.0 | 7.7 | 0, 0, 0 | 1, 0, 2 |
| grill-small-feature | 0.8333333333333334 (0.16666666666666666) | numbered-with-recommendations 3/3<br>whole-frontier 2/3 | 36983 | 8 | 7786 | 27822 | 1367 | 1.0 | 6.0 | 0, 0, 0 | 0, 0, 0 |
| grill-term-clash | 0.8333333333333334 (1) | clash-called-out 2/3<br>glossary-written-inline 3/3 | 69041 | 12 | 10390 | 55986 | 2654 | 1.0 | 9.0 | 1, 1, 1 | 0, 0, 0 |
