# Issue tracker: GitLab

Issues and specs live as GitLab issues in `<group>/<project>`. Use [`glab`](https://gitlab.com/gitlab-org/cli); inside a clone it infers the project from `git remote -v`.

File issues only into the user's own project, never into an upstream it was forked from: before the first `glab issue create` of a session, check `glab repo view` and confirm with the user if it is not their project.

## Operations

- **Create** (also "publish to the issue tracker"): `glab issue create --title "..." --description "..."`, with a heredoc for multi-line descriptions.
- **Read** (also "fetch the relevant ticket"): `glab issue view <n> --comments` (`-F json` for machine-readable output).
- **List**: `glab issue list -O json`, plus `--label` filters.
- **Parent link**: put `Part of #<parent>` at the top of the child description and link it: `glab issue create --linked-issues <parent> --link-type relates_to ...`.
- **Blocking**: GitLab's native blocking link (UI-visible, canonical), posted as a quick action: `glab issue note <child> --message "/blocked_by #<blocker>"`. It is a Premium/Ultimate feature; on the free tier, put `Blocked by: #<n>, #<n>` at the top of the description. A ticket is unblocked when every blocker is closed.
- **Count open blockers**: `glab api projects/:id/issues/<iid>/links`, counting `is_blocked_by` links to open issues (or open issues in the `Blocked by` line); 0 means startable.
- **Comment**: `glab issue note <n> --message "..."` (GitLab calls comments "notes").
- **Labels**: `glab issue update <n> --label "..."` / `--unlabel "..."` (comma-separate or repeat for several).
- **Close**: `glab issue note <n> --message "<why>"`, then `glab issue close <n>` (`close` takes no comment).
- **Merge requests**: `glab mr create` / `view` / `note` / ..., shaped like `gh pr ...` with `mr` for `pr` and `note --message` for `comment --body`.

**MRs as a request surface: no.** (`/triage` reads this flag. To turn it on, re-run `/setup-matt-pocock-skills` and answer yes.)

<!-- if: prs -->
## MR triage

MRs run through the same labels and states as issues:

- **Read**: `glab mr view <n> --comments` and `glab mr diff <n>`.
- **List external MRs**: `glab mr list -O json`, keeping only MRs whose author is not a project member or owner.
- **Comment / label / close**: `glab mr note`, `glab mr update --label` / `--unlabel`, `glab mr close`.

GitLab numbers issues and MRs separately, so `#42` is unambiguous once you know which surface is meant.
<!-- end -->

<!-- if: wayfinder -->
## Wayfinding operations

Used by `/wayfinder`. The **map** is one issue; its **child** issues are the tickets.

- **Map**: an issue labelled `wayfinder:map` holding the Notes / Decisions-so-far / Fog body: `glab issue create --label wayfinder:map ...`. (On tiers with native epics an epic may hold the map; a labelled issue works everywhere.)
- **Child ticket**: linked to the map (see **Parent link**), labelled `wayfinder:<type>` (`research`/`prototype`/`grilling`/`task`).
- **Frontier**: the map's children from `glab api projects/:id/issues/<map>/links`, kept if open and carrying a `wayfinder:<type>` label, minus any with an open blocker (see **Count open blockers**) or an assignee; first in map order wins.
- **Claim**: `glab issue update <n> --assignee @me`, the session's first write.
- **Resolve**: note the answer, close the issue (see **Close**), then append a context pointer (gist + link) to the map's Decisions-so-far.
<!-- end -->
