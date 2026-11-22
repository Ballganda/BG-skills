# Contributing

Every issue is judged against the bar in [`SCOPE.md`](./SCOPE.md). Read it first.

## Where each request goes

| You have | Go to |
| --- | --- |
| A bug in a skill | [Bug issue](https://github.com/Ballganda/BG-skills/issues/new?template=bug.yml) |
| A change to an existing skill | [Idea or feedback issue](https://github.com/Ballganda/BG-skills/issues/new?template=idea.yml) |
| A question, or "how do I...?" | [Discussions: Q&A](https://github.com/Ballganda/BG-skills/discussions/categories/q-a) |
| An idea for a new skill, or a skill to donate | [Discussions: Ideas](https://github.com/Ballganda/BG-skills/discussions/categories/ideas) |
| Support for another harness or issue tracker | [Discussions: Ideas](https://github.com/Ballganda/BG-skills/discussions/categories/ideas), after you read [`.out-of-scope/`](./.out-of-scope) |

Pull requests are open to collaborators only, so describe the fix in an issue instead.

## Issues written with AI

Agents are welcome to help, but you post the issue, so you own it:

- **One problem per issue.** Several findings from one session are several issues, or none.
- **Short.** If it does not fit on one screen, cut it.
- **Repro first.** The steps that show the problem come before any analysis.
- **No pasted specs.** No full proposals, plans, or rewritten `SKILL.md` files. Describe the problem; the fix is ours to design.
- **Not your project's issues.** If your agent files the specs or tickets for your own project here, it has the wrong repo. Run `/bg-setup` in your project.

## Checks

Any run that may outlast the tool timeout (120 seconds by default) is waited for in one way: start it with the harness's background option, redirect its output to a file, and wait for the completion notification. Do not sleep, poll the file, or re-run the command in the foreground.

Run `npm run check` before a change is ready. It checks the skills and runs the skill-check, implement and Replies-line tests. It may outlast the tool timeout, so wait for it as the rule above says.

Also run `npm run test:decomp` (the same as `python scripts/test-decomp.py`) when a change touches the decomp skills (`skills/engineering/decomp-*`) or `scripts/test-decomp.py`. A full run takes minutes, longer than the default 120-second tool timeout, so wait for it as the rule above says; while iterating, pass filters (`python scripts/test-decomp.py <filter> ...`) to run only the cases they select: a full case name selects that case alone, and any other filter selects the names holding it as a run of whole words; a filter that selects nothing exits 2, and `--list` prints the selected names without running them. The cases are not in `npm run check`, which runs only the runner's own tests and the runner's `--list` (it fails on a module-level name bound twice), so this is the one place the rule is stated.

No CI runs these checks, so the author runs them. Before a pull request merges, its author runs `npm run check` and the full `npm run test:decomp` on the branch tip, on their own machine, and the pull request's Evidence names the machine and the result.

On Windows, never pass script text (Python, Node or shell) through a shell heredoc: Git Bash rewrites backslashes and quotes inside it, so the script fails or edits the wrong text. Write the script to a file with the file-writing tool and run that file. To edit source that holds backslash escapes, use the edit tool, not a script. A script that rewrites a file opens it with newline translation off, for reading and for writing (in Python, `open(path, newline="")`), so line endings stay as they were.

## Releasing

Releases are cut locally, by the maintainer, from main. No CI workflow runs them.

Run `npm run release`. It versions with the pending changesets, commits the result as "chore: version skills" (no co-author line), tags it `v` plus the new version, pushes main and the tag, and publishes a GitHub release whose notes are the new version's section of `CHANGELOG.md`. It needs the `gh` CLI signed in, and a token for the changelog generator.

Run `npm run release -- --dry-run` first: it prints the version it would cut, the changesets it would consume and its steps, and changes nothing. `--skip-publish` does everything but the GitHub release.

It refuses, names the cause, exits non-zero and changes nothing when the checkout is not on main, is dirty, is not level with `origin/main`, or has no pending changeset. A failure after the commit names the failed step and the commands that finish the release by hand.
