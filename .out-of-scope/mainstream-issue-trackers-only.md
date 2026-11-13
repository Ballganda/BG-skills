# Issue tracker integrations: GitHub, GitLab and local markdown only

`bg-setup` offers first-class support for exactly three issue trackers, one per seed template in `skills/engineering/bg-setup/`:

- **GitHub** (`issue-tracker-github.md`, via `gh`)
- **GitLab** (`issue-tracker-gitlab.md`, via `glab`)
- **Local markdown** (`issue-tracker-local.md`, files under `.scratch/`)

Requests to add a first-class backend for any other tracker are out of scope. That includes Jira, Linear, Azure DevOps, Trello, YouTrack, and new agent-focused trackers.

## Why this is out of scope

Every issue-tracker backend hard-codes a CLI shape into the skills (commands, flags, output parsing). Each new backend is permanent maintenance surface, because it has to keep working as the tool's CLI evolves, and it has to keep being tested against `/spec-gen`, `/ticket-gen`, `/triage`, and friends. BG-skills runs on GitHub, so that's the backend that can actually be kept correct. GitLab is close enough in shape to ride along, and local markdown needs no CLI at all.

Popularity doesn't change this. Jira is widely used and has an official CLI (`acli`), and it still isn't getting a template: it's a backend this repo doesn't run, with its own link semantics, workflow states and CLI quirks to keep tested. The cost lands on the maintainer whether or not the tool is mainstream.

Every other tracker goes through the **Other** option in `/bg-setup`: you describe your workflow in a paragraph and the skill records it as prose in `docs/agents/issue-tracker.md`. That file is yours. If you've refined a Jira or Linear workflow that works, keep it in your own repo or publish it, and point the setup at it.
