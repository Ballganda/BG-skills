# Eval summary (grill and reply cases)

Run 2026-11-12T19:34:02.865Z, Claude Code 2.1.322, plugin bg-skills@1.3.2. Score 1, cases passed 3/3, cost $3.78.

Token and round figures are means over the with-plugin runs. Total tokens = input + cache write + cache read + output.

| Case | Score (without) | Graders passed | Total tokens | Input | Cache write | Cache read | Output (mean) | Output per run | Rounds | Questions | Glossary writes | ADR writes |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| grill-adr-worthy | 1 (n/a) | adr-only-when-all-three 5/5<br>no-adr-for-trivial-decisions 5/5 | 48058 | 9 | 10204 | 34766 | 3080 | 3020, 2767, 3164, 2956, 3492 | 1.0 | 8.2 | 0, 0, 0, 0, 0 | 0, 0, 0, 0, 2 |
| grill-small-feature | 1 (n/a) | numbered-with-recommendations 5/5<br>whole-frontier 5/5 | 37904 | 8 | 8001 | 28415 | 1480 | 1663, 1339, 1438, 1529, 1431 | 1.0 | 5.4 | 0, 0, 0, 0, 0 | 0, 0, 0, 0, 0 |
| grill-term-clash | 1 (n/a) | clash-called-out 5/5<br>glossary-written-inline 5/5 | 73282 | 12 | 10780 | 59783 | 2706 | 3019, 2479, 2559, 2697, 2777 | 1.0 | 9.2 | 1, 1, 1, 1, 1 | 0, 0, 0, 0, 0 |
