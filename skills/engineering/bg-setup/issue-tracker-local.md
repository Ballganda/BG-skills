# Issue tracker: Local Markdown

Issues and specs live as markdown files under `.scratch/`.

## Conventions

- One feature per directory: `.scratch/<feature-slug>/`; the spec is `spec.md` inside it.
- **Create** (also "publish to the issue tracker"): a new file under `.scratch/<feature-slug>/`, creating the directory if needed. Tickets are one file each at `issues/<NN>-<slug>.md`, numbered from `01`, never one combined file.
- **Read** (also "fetch the relevant ticket"): the file at the referenced path; the user normally passes the path or number.
- **Triage state**: a `Status:` line near the top (role strings in `triage-labels.md`).
- **Blocking**: a `Blocked by: NN, NN` line near the top. A ticket is unblocked when every file it lists is `resolved`.
- **Comment**: append under a `## Comments` heading at the bottom of the file.

<!-- if: wayfinder -->
## Wayfinding operations

Used by `/wayfinder`. The **map** is a file with one **child** file per ticket.

- **Map**: `.scratch/<effort>/map.md` (the Notes / Decisions-so-far / Fog body).
- **Child ticket**: `.scratch/<effort>/issues/NN-<slug>.md` with the question in the body, a `Type:` line (`research`/`prototype`/`grilling`/`task`), and a `Status:` line (`claimed`/`resolved`).
- **Frontier**: files in `.scratch/<effort>/issues/` that are open, unblocked, and unclaimed; lowest number wins.
- **Claim**: set `Status: claimed` and save before any work.
- **Resolve**: append the answer under `## Answer`, set `Status: resolved`, then append a context pointer (gist + link) to Decisions-so-far in `map.md`.
<!-- end -->
