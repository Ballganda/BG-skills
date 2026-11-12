# BG Skills

A collection of agent skills (slash commands and behaviors) loaded by Claude Code. Skills are organized into buckets and consumed by per-repo configuration emitted by `/bg-setup`.

## Language

**Issue tracker**:
The tool that hosts a repo's issues: GitHub Issues, Linear, a local `.scratch/` markdown convention, or similar. Skills like `ticket-gen`, `spec-gen`, and `triage` read from and write to it.
_Avoid_: backlog manager, backlog backend, issue host

**Issue**:
A single tracked unit of work inside an **Issue tracker**: a bug, task, spec, or slice produced by `ticket-gen`.
_Avoid_: ticket (use only when quoting external systems that call them tickets, for a **Ticket**, or for a **Decision ticket**, see below)

**Decision ticket**:
A `wayfinder` unit: a child **Issue** of a `wayfinder:map` holding a *question* whose resolution is a decision, not a slice of a build to execute. The **decision** qualifier is what keeps it distinct from an implementation ticket; `wayfinder` introduces the term, then uses "ticket".

**Ticket**:
An **Issue** produced by `ticket-gen`: a tracer-bullet vertical slice that declares the Tickets blocking it.
_Avoid_: task, story, slice (as a noun for the Issue)

**Ticket batch**:
The set of **Tickets** one `implement` run is allowed to work: those carrying a given label or milestone, or the next N ready Tickets (N defaults to 1). Nothing outside the batch is touched.
_Avoid_: group, wave, sprint

**Triage role**:
A canonical state-machine label applied to an **Issue** during triage (e.g. `needs-triage`, `ready-for-afk`). Each role maps to a real label string in the **Issue tracker** via `docs/agents/triage-labels.md`.

**Reply**:
Any message the main agent writes to the user in chat.
_Avoid_: report, final report, response

**Report**:
A subagent's fixed-format return to the agent that started it.
_Avoid_: reply, summary

## Relationships

- An **Issue tracker** holds many **Issues**
- An **Issue** carries one **Triage role** at a time
- A **Decision ticket** is an **Issue** (a child of a `wayfinder:map`)
- A **Ticket** is an **Issue**; a **Ticket batch** holds one or more **Tickets**
- A subagent sends a **Report** to its caller; the main agent sends a **Reply** to the user

## Flagged ambiguities

- "backlog" was previously used to mean both the *tool* hosting issues and the *body of work* inside it. Resolved: the tool is the **Issue tracker**; "backlog" is no longer used as a domain term.
- "report" was used for both a subagent's return and the agent's closing message to the user ("final report"). Resolved: the first is a **Report**, the second is a **Reply**.
- "backlog backend" / "backlog manager". Resolved: collapsed into **Issue tracker**.
