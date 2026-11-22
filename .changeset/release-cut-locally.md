---
"bg-skills": patch
---

Releases are cut locally and CI no longer runs them. `npm run release` refuses unless the checkout is on a clean main level with the remote and a changeset is pending; it then versions, commits "chore: version skills", tags, pushes and publishes the GitHub release. `npm run release -- --dry-run` shows what it would do first. The contributor guide has a section on releasing.
