---
"bg-skills": patch
---

Decomp skills (in progress): `search` runs a template's candidates as a parallel, deadline-driven block (spec #162).

- **Workers.** Candidates build on worker threads, one adapter process each, in a scratch folder per worker.
- **No shell.** `search` starts the build and diff adapters without the host's shell, and falls back to it for a command that needs one. `check`, `verify`, and `link` keep the shell.
- **End reasons.** A block ends on `match`, `abort-buildfail`, `exhausted`, `plateau`, or `deadline`. The deadline has a floor (10 seconds and 200 builds) and a ceiling (the last round's model latency, at most 60 seconds).
- **Hangs.** An adapter run that outlasts 10 times the median compile time is killed as a whole process tree (a Job Object on Windows, a process group elsewhere) and counts as a build-fail.
- **Overrides.** `"search"` in `.decomp/local.json` overrides any block constant for this machine.
- **Summary.** `counts` gains `workers`, `wall_s`, `killed`, and `shell`.
