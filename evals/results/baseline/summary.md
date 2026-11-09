# /grill eval summary

Run 2026-11-09T04:25:39.423Z, Claude Code 2.1.319, plugin bg-skills@1.3.2. Score 1, cases passed 3/3, cost $3.68.

Token and round figures are means over the with-plugin runs. Total tokens = input + cache write + cache read + output.

| Case | Score (without) | Graders passed | Total tokens | Input | Cache write | Cache read | Output | Rounds | Questions | Glossary writes | ADR writes |
|---|---|---|---|---|---|---|---|---|---|---|---|
| grill-adr-worthy | 1 (0.5) | adr-only-when-all-three 3/3<br>no-adr-for-trivial-decisions 3/3 | 64950 | 11 | 11760 | 49886 | 3293 | 1.0 | 8.7 | 0, 0, 0 | 1, 2, 1 |
| grill-small-feature | 1 (0.16666666666666666) | numbered-with-recommendations 3/3<br>whole-frontier 3/3 | 38111 | 8 | 8256 | 28277 | 1571 | 1.0 | 6.0 | 0, 0, 0 | 0, 0, 0 |
| grill-term-clash | 1 (1) | clash-called-out 3/3<br>glossary-written-inline 3/3 | 71060 | 12 | 10868 | 57283 | 2896 | 1.0 | 8.3 | 1, 1, 1 | 0, 0, 0 |
