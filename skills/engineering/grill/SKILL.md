---
name: grill
description: A relentless interview to sharpen a plan or design, which also creates docs (ADR's and glossary) as we go.
disable-model-invocation: true
---

Call the Skill tool twice, for "grilling" and "domain-modeling".

Write only what domain-modeling writes (`GLOSSARY.md`, ADRs): no code, config, or skill edits. Never invoke `spec-gen`, `ticket-gen`, or `implement`.

The grilling closing question is also the hand-off: shared understanding reached; ready to turn it into a spec? Type `/spec-gen` when ready. Then stop. A "yes" changes nothing: wait for the user to type `/spec-gen`.

If the user asks you to build or implement mid-session, answer with the closing question instead.
