## Buckets

Skills live in `skills/<bucket>/`. **Promoted** (shipped in the plugin): `engineering/` (code work), `productivity/` (non-code workflow). Not promoted: `misc/` (rarely used), `in-progress/` (public beta, feedback wanted), `deprecated/` (retired).

## Skill lifecycle

On adding, renaming, removing, or moving a skill between buckets:

- **Promoted only:** list it in the top-level `README.md` (name linked to `SKILL.md`) and in `.claude-plugin/plugin.json`'s `skills`. Unpromoted skills appear in neither.
- **Bucket `README.md`:** one line, name linked to `SKILL.md`. Promoted READMEs and the top-level one group under **User-invoked** / **Model-invoked**; others use a flat list.
- **Docs page** (promoted only, also on behaviour change): follow [.agents/writing-docs.md](./.agents/writing-docs.md).
- **[`skill-map`](./skills/engineering/skill-map/SKILL.md):** update for any user-reachable skill, including changes to how it fits the flows.
- **Links:** re-run `scripts/link-skills.sh`.

Invocation type: [.agents/invocation.md](./.agents/invocation.md). Install commands: copy verbatim from [.agents/install-block.md](./.agents/install-block.md). After touching `plugin.json` or `marketplace.json`, run `claude plugin validate .`: the `CLAUDE.md` warning at the plugin root is expected and does not block work, and strict mode is not a gate ([ADR 0002](./.agents/adr/0002-ship-as-a-claude-code-plugin.md)).

## Writing rules

- No em-dashes in any prose (skills, docs, READMEs, changelog, ADRs, changesets, code comments). Rewrite the sentence with a comma, colon, period, parentheses, or conjunction; never substitute blindly.
- A skill that dispatches a subagent says to start it with a fresh context window: some harnesses (Codex) fork by default, and a fork inherits the context the subagent should escape.

## Agent skills

- Issue tracker: GitHub Issues on `Ballganda/BG-skills` via `gh`. See `docs/agents/issue-tracker.md`.
- Triage labels: see `docs/agents/triage-labels.md`.
- Domain docs: see `docs/agents/domain.md`.
- Replies: to the user in chat. First line, when the message gave an instruction, decision or correction beyond a bare "yes": "Understood: <your interpretation>". Next line: the outcome, in one sentence. Then bullets, each a short clause holding exactly one fact; a reason, example or consequence gets its own bullet. Number them when the user answers per item. Each offer of further work is its own numbered item with a recommendation that "yes" accepts, as is each of two or more decisions. Use a table to compare items across attributes, a code block for code. Write prose when the user asks for an explanation. A subagent's Report follows its caller's format.

Issues are judged against [`SCOPE.md`](./SCOPE.md).
