# Models

Each ticket carries a tier (set by `ticket-gen`), and each subagent task has a model. Skills read this file to pick the model; edit the names to match your harness.

## The rule

A subagent's model follows the kind of work it does, whatever model the session runs on:

1. Locate or collect, where the caller can check the result: the Mechanical model.
2. Produce something a tool can check (tests pass, bytes match): the tier for that difficulty, one tier higher on a failed attempt.
3. Interpret, with no mechanical check: the Standard model.
4. Judgment that decisions depend on (design, spec review, toolchain inference): the Hard model.

| Tier | Use for | Model |
| --- | --- | --- |
| Mechanical | rename, config, docs, copy of an existing pattern | Haiku |
| Standard | one module, a clear seam, tests that describe it | Sonnet |
| Hard | crosses modules, a new seam, concurrency, unclear spec | <top model> |

| Subagent task | Kind of work | Model |
| --- | --- | --- |
| Exploration | locating files, tests, commands, definitions | the Mechanical model |
| Locating | looking up a fact the caller can check | the Mechanical model |
| Research | gathering sources, then weighing them | the Standard model |
| Interpreting exploration | judging code with no mechanical check | the Standard model |
| Design | producing a design that decisions depend on | the Hard model |
| Toolchain identification | inferring a toolchain from evidence | the Hard model |
| Reference repair | repairing declarations, checked by `revalidate` | the Standard model, one tier higher after a failed `revalidate` |
| Merging | combining branches | the Standard model |
| Standards review | checking code against the repo's standards | the Standard model |
| Spec review | checking code against the spec | the Hard model |
