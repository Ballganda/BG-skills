# New skill proposals and contributions

This repo does not take proposals or contributions for new skills, including ones that arrive with a ready branch or a fork.

## Why this is out of scope

The catalog is the set of skills the maintainer uses day to day, and it's deliberately small. Every skill is permanent maintenance surface: it has to stay in step with the others, with the docs pages, with `skill-map`'s routing map, and with the plugin manifest. The shorter and fewer the skills, the cheaper they are to keep correct.

The rule applied to the maintainer's own ideas applies here too: if you can compose the behaviour from existing skills, it doesn't get a new skill. Most proposals are a specific workflow built out of grilling, `spec-gen`, `ticket-gen`, `implement` and friends, and that composition belongs in your own prompts or your own skills.

You're very welcome to publish a skill yourself. skills.sh makes that straightforward, and nothing here needs to know about it.

This covers *new* skills only. A concrete failure in an existing skill is judged against the bar in [`SCOPE.md`](../SCOPE.md) like any other issue.
