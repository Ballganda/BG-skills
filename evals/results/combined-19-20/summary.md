# /grill eval summary

Run 2026-11-09T05:10:23.730Z, Claude Code 2.1.319, plugin bg-skills@1.3.2. Score 1, cases passed 3/3, cost $3.79.

Token and round figures are means over the with-plugin runs. Total tokens = input + cache write + cache read + output.

| Case | Score (without) | Graders passed | Total tokens | Input | Cache write | Cache read | Output | Rounds | Questions | Glossary writes | ADR writes |
|---|---|---|---|---|---|---|---|---|---|---|---|
| grill-adr-worthy | 1 (0.5) | adr-only-when-all-three 3/3<br>no-adr-for-trivial-decisions 3/3 | 52380 | 9 | 11062 | 37939 | 3370 | 1.0 | 10.0 | 0, 0, 0 | 0, 1, 1 |
| grill-small-feature | 1 (0) | numbered-with-recommendations 3/3<br>whole-frontier 3/3 | 36340 | 8 | 7442 | 27486 | 1404 | 1.0 | 6.3 | 0, 0, 0 | 0, 0, 0 |
| grill-term-clash | 1 (1) | clash-called-out 3/3<br>glossary-written-inline 3/3 | 67556 | 12 | 9863 | 54954 | 2727 | 1.0 | 9.7 | 1, 1, 1 | 0, 0, 0 |
