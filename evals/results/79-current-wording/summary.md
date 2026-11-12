# Eval summary (grill and reply cases)

Run 2026-11-12T18:50:11.708Z, Claude Code 2.1.322, plugin bg-skills@1.3.2. Score 0.25, cases passed 0/2, cost $2.24.

Token and round figures are means over the with-plugin runs. Total tokens = input + cache write + cache read + output.

| Case | Score (without) | Graders passed | Total tokens | Input | Cache write | Cache read | Output (mean) | Output per run | Rounds | Questions | Glossary writes | ADR writes |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| reply-status | 0.5 (n/a) | detail-one-fact-per-line 0/5<br>outcome-first 5/5 | 49020 | 9 | 9466 | 38596 | 949 | 766, 1136, 1113, 815, 913 | 0.0 | 0.0 | 0, 0, 0, 0, 0 | 0, 0, 0, 0, 0 |
| reply-status-no-line | 0 (n/a) | detail-one-fact-per-line 0/1<br>outcome-first 0/1 | 55162 | 10 | 6602 | 47492 | 1058 | 1058 | 0.0 | 0.0 | 0 | 0 |
