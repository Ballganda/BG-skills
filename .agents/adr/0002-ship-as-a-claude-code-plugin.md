# Ship the skill set as a plugin from this repo's own marketplace

BG-skills ships its promoted skills as a **plugin** from this repo's own marketplace, `Ballganda/BG-skills`, as `bg-skills@bg-skills`. Claude Code, Codex, Copilot CLI and VS Code all install from it. A plugin is a read-only, always-current bundle the user subscribes to, rather than files they copy and own. The install wording lives in [.agents/install-block.md](../install-block.md), which is the single source for every command named here.

## The constraint: bucketed skills

Skills live in bucket folders under `skills/`, some **promoted** (shipped) and some not; [CLAUDE.md](../../CLAUDE.md#buckets) is the one place that lists them. The plugin must expose only the promoted set, which spans more than one bucket folder.

- A single skills path can't express that. Pointing it at `./skills/` would also ship `misc/`, `in-progress/` and `deprecated/`.
- A curated flat folder of **symlinks** into the buckets doesn't work either: Codex copies the plugin tree into its cache and **drops symlinks**, so the skills arrive empty.

So `.claude-plugin/plugin.json` lists the promoted skills as an **explicit `skills` array** of skill-directory paths. It names each promoted skill and excludes everything else. Codex and Copilot read the same `.claude-plugin/` manifests, so one manifest serves every plugin route.

## Decision

- **Managed installs from this repo's marketplace.** `.claude-plugin/marketplace.json` makes the repo its own single-plugin marketplace. Claude Code, Codex, Copilot CLI and VS Code each add `Ballganda/BG-skills` and install `bg-skills@bg-skills` (VS Code installs from the repo URL). Claude Code and Copilot need a one-time auto-update opt-in; Codex and VS Code update by default.
- **Gemini per bucket.** Gemini CLI doesn't read `.claude-plugin`, and its `--path` takes one folder, so it installs once per promoted bucket. These are copies and don't update themselves.
- **skills.sh as the manual fallback.** Every other agent, and anyone who wants editable files, uses `npx skills@latest add Ballganda/BG-skills`. Updates are manual.
- **The plugin and skills.sh are exclusive.** Installing both gives every skill twice, so the docs say "pick one".

## Invariants this creates

- Every promoted skill has an entry in `.claude-plugin/plugin.json`'s `skills` array, and no unpromoted skill does.
- `plugin.json`'s `version` tracks `package.json`'s. Managed routes reinstall only when that field changes. `npm run version` keeps it in step by running `scripts/sync-plugin-version.mjs`, and the Release workflow runs `npm run version`. `marketplace.json` has no `version` field, so it can't drift.

## Root layout and the validation gate

The plugin stays at the repo root. `claude plugin validate . --strict` fails on two warnings: `CLAUDE.md` at the plugin root (maintainer context, not loaded for users) and a missing icon. Moving the plugin into a `plugin/` subfolder would clear the first, but it would change every path and break installs by repo path, for a benefit that only a directory submission needs. This repo ships through `claude plugin marketplace add Ballganda/BG-skills`, which plain validation covers.

So the gate is `claude plugin validate .` without `--strict`, and the `CLAUDE.md` warning is expected. If a directory listing is ever wanted, split a publish repo from this maintainer repo rather than nesting the plugin.
