## Buckets

Skills live in `skills/<bucket>/`. **Promoted** (shipped in the plugin): `engineering/` (code work), `productivity/` (non-code workflow). Not promoted: `misc/` (rarely used), `in-progress/` (public beta, feedback wanted), `deprecated/` (retired).

## Skill lifecycle

On adding, renaming, removing, or moving a skill between buckets:

- **Promoted only:** list it in the top-level `README.md` (name linked to `SKILL.md`) and in `.claude-plugin/plugin.json`'s `skills`. Unpromoted skills appear in neither.
- **Bucket `README.md`:** one line, name linked to `SKILL.md`. Promoted READMEs and the top-level one group under **User-invoked** / **Model-invoked**; others use a flat list.
- **Docs page** (promoted only, also on behaviour change): follow [.agents/writing-docs.md](./.agents/writing-docs.md).
- **[`skill-map`](./skills/engineering/skill-map/SKILL.md):** update for any user-reachable skill, including changes to how it fits the flows.
- **Links:** re-run `scripts/link-skills.sh`.

Invocation type: [.agents/invocation.md](./.agents/invocation.md). Install commands: copy verbatim from [.agents/install-block.md](./.agents/install-block.md). After touching `plugin.json` or `marketplace.json`, run `claude plugin validate . --strict` ([ADR 0002](./.agents/adr/0002-ship-as-a-claude-code-plugin.md)).

## Writing rules

- No em-dashes in any prose (skills, docs, READMEs, changelog, ADRs, changesets, code comments). Rewrite the sentence with a comma, colon, period, parentheses, or conjunction; never substitute blindly.
- A skill that dispatches a subagent says to start it with a fresh context window: some harnesses (Codex) fork by default, and a fork inherits the context the subagent should escape.

## Agent skills

### Issue tracker

GitHub Issues on `Ballganda/BG-skills`, via the `gh` CLI. See `docs/agents/issue-tracker.md`.

### Triage labels

Canonical names, unchanged. See `docs/agents/triage-labels.md`. Issues are judged against [`SCOPE.md`](./SCOPE.md).

### Domain docs

Single-context: `GLOSSARY.md` at the root and ADRs in `.agents/adr/`. See `docs/agents/domain.md`.
