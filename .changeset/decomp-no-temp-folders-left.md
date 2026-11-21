---
"bg-skills": patch
---

Decomp skills (in progress): no decomp command leaves a folder in the system temp folder (spec #219).

- **One temp parent.** Every temp folder the tool makes sits under one folder in the system temp folder, `decomp-<project folder name>-<8 hex digits>`. A command removes what it made before it exits, on success, a refusal, an error and an interrupt, and removes the parent once it is empty.
- **Sweep.** Every command first removes the entries of that parent older than one day, which a killed command left. A younger entry may belong to a running command and stays.
- **Held files.** Removing a temp folder tries again for 2 seconds while a file in it is held, then leaves it to the sweep. Before, a file held in the object folder on Windows ended `check` with a traceback.
- **`check` report.** The diff report is `.decomp/check/<ticket id>/diff.txt`: one path per ticket, replaced by the ticket's next `check`, and present (empty) when the diff did not run.
- **Winning source.** A round's `winner` is `.decomp/search/<ticket id>/winner/<source file name>`, and a collected background search's is under `winner-background/`. `release` removes a ticket's report and winning sources.
- **`revalidate`** uses one report path for the whole run. **`sync`** removes each issue body file after the `gh` call that used it. A temp worktree leaves git's worktree list as well as the disk, also on an error exit.
- **Test harness.** After every case, the runner checks that the temp folder given to the tool holds nothing the tool made.
- **Leftovers of earlier versions.** The tool does not clean them: they sit outside the new parent. With no decomp command running, these folders in the system temp folder are safe to delete by hand: `decomp-obj-*`, `decomp-rep-*`, `decomp-gh-*`, `decomp-winner-*`, `decomp-link-*`, `decomp-search-*`, `decomp-background-*` and `decomp-wt-*`. After deleting a `decomp-wt-*` folder, run `git worktree prune` in the project so git stops listing it.
