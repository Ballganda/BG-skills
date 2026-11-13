# Changes to `misc/` skills

The skills under `skills/misc/` (`git-guardrails-claude-code`, `migrate-to-shoehorn`, `scaffold-exercises`, `setup-pre-commit`, and anything else that lands there) are frozen. Bug reports, feature requests and PRs against them are closed.

## Why this is out of scope

`misc/` is where skills go when they are kept around but rarely used. They aren't promoted: they don't ship in the Claude Code plugin, they have no docs page, and nobody here runs them day to day, so there is no way to tell whether a fix is right or to notice when one breaks something else. Maintaining them at the same bar as the promoted skills would cost the same as a promoted skill for a fraction of the use.

They stay in the repo, unmaintained, because they still work for some people as-is. If one doesn't work for you, install it with skills.sh and fix your copy: the files are yours to edit.

If a `misc/` skill is promoted back into `engineering/` or `productivity/` later, it's back in scope from that point.
