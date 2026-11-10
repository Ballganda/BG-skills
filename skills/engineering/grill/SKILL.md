---
name: grill
description: A relentless interview to sharpen a plan or design, which also creates docs (ADR's and glossary) as we go.
disable-model-invocation: true
---

Call the Skill tool twice, for "grilling" and "domain-modeling".

Write only what domain-modeling writes (`GLOSSARY.md`, ADRs): no code, config, or skill edits. Never invoke `spec-gen`, `ticket-gen`, or `implement`.

The grilling closing question is also the hand-off: shared understanding reached; ready to turn it into a spec? Type `/spec-gen` when ready. End that closing message with this line: Stay in this session for `/spec-gen`. Then stop. A "yes" changes nothing: wait for the user to type `/spec-gen`.

If the user asks you to build or implement mid-session, don't build and don't claim shared understanding: name the branches still open, then ask whether to turn what's settled into a spec now or keep going. Type `/spec-gen` when ready. Then wait.
