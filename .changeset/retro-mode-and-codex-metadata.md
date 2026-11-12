---
"bg-skills": patch
---

`retro` takes its mode from the caller (User-typed, Lesson-line, Diagnosing-bugs), with User-typed the default. `implement` resolves the tickets, runs retro if any lesson came back, then writes the final report and cleans up; `diagnosing-bugs` keeps retro inside its done checklist. The static check reads every skill through one shared reader, fails any skill whose frontmatter and Codex metadata disagree on invocation, and fails any skill with no `agents/openai.yaml`. `software-factory` gets Codex metadata that keeps it user-invoked. The skill-map, retro and implement docs pages match their skills again.
