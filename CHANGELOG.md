# bg-skills

## 2.0.0

### Major Changes

- [#29](https://github.com/Ballganda/BG-skills/pull/29) [`9b21514`](https://github.com/Ballganda/BG-skills/commit/9b21514a400700513ffb4a4d15051205c07cace9) Thanks [@Ballganda](https://github.com/Ballganda)! - The plugin is now `bg-skills`, a fork of mattpocock/skills, and four skills are renamed to nouns: `to-spec` is `spec-gen`, `to-tickets` is `ticket-gen`, `setup-matt-pocock-skills` is `bg-setup`, and `ask-matt` is `skill-map`. Claude Code installs from this repo's own marketplace instead of `claude-plugins-official`: see [Installation](https://github.com/Ballganda/BG-skills#installation-30-second-setup) in the README. Docs live in the repo with relative links; nothing is published to a website.

- [#29](https://github.com/Ballganda/BG-skills/pull/29) [`a47a8e7`](https://github.com/Ballganda/BG-skills/commit/a47a8e72263ba4d1d819736627f6a9629ba6120f) Thanks [@Ballganda](https://github.com/Ballganda)! - `grill-with-docs` is renamed to `grill`, the standard entry point of the build chain: `grill → spec-gen → ticket-gen → implement → code-review`. Behaviour is unchanged. Type `/grill` where you used to type `/grill-with-docs`.

### Minor Changes

- [`2ac956c`](https://github.com/Ballganda/BG-skills/commit/2ac956c190d9da845a1b5107a299dd3133cf6520) Thanks [@Ballganda](https://github.com/Ballganda)! - `retro` is now model-invoked, in its frontmatter and its Codex metadata, with a model-facing description. `implement` calls it at the end of a run when at least one implementer reported a lesson, passing the lesson lines; retro works from those lines and the files they point to, without reading session logs, and a run with no lessons skips it. `diagnosing-bugs` calls it in the live session once a fix lands. Called by either skill, retro only lists suggestions in the final report and changes nothing. Typing `/retro` works as before. The skill map describes the automatic retro, and the static check fails if retro's frontmatter and Codex metadata stop agreeing that it is model-invoked.

- [#29](https://github.com/Ballganda/BG-skills/pull/29) [`c6a2212`](https://github.com/Ballganda/BG-skills/commit/c6a22124e693186ea49780f11249628635e36095) Thanks [@Ballganda](https://github.com/Ballganda)! - `bg-setup` writes a leaner `## Agent skills` block: a list of up to three pointers (`- Issue tracker:`, `- Triage labels:`, `- Domain docs:`) instead of three `###` sections, and only the tracker line carries a summary (host and repo). On a re-run, setup rewrites only the lines with those prefixes, lists any other lines in the block, and asks "Keep these N lines you added?" Kept lines stay unchanged in their own paragraph below the list. An older `###`-style block is converted to the list. No marker comments are added.

- [#97](https://github.com/Ballganda/BG-skills/pull/97) [`ef20364`](https://github.com/Ballganda/BG-skills/commit/ef20364dcbaae4459e13228bd4c9ab8a9ff1c282) Thanks [@Ballganda](https://github.com/Ballganda)! - `bg-setup` writes a `- Replies:` line into the `## Agent skills` block, a rule that shapes every reply to the user: an "Understood:" line, the outcome in one sentence, then bullets of one fact each, with each offer of further work and each of two or more decisions as a numbered item carrying a recommendation. Repos that are already set up get the rule by re-running `/bg-setup`, which adds the line when it is missing and asks before rewriting an edited one.

- [`f9240e3`](https://github.com/Ballganda/BG-skills/commit/f9240e3085d038b1311cdba9d574a1da9831f674) Thanks [@Ballganda](https://github.com/Ballganda)! - `code-review` keeps its smell list in `SMELLS.md` and hands the Standards reviewer its path instead of pasting it. Both axes run as the `reviewer` role with a fresh context window, on the Standards review and Spec review models from `docs/agents/models.md` (Sonnet and the top model by default). Each reviewer reports one line per finding, `hard or judgement | location | rule or spec line | finding`, in place of the old word limits, and the two axes are still reported under separate headings. The static check fails if `code-review` instructs pasting the smell list, drops the finding format, or brings back a word limit.

- [`6e1fc34`](https://github.com/Ballganda/BG-skills/commit/6e1fc344e669d0b36617dc71fb96795803d6909d) Thanks [@Ballganda](https://github.com/Ballganda)! - Each creation-flow skill now ends its closing message with one line about the next step: `/grill` says to stay in the session for `/spec-gen`, `/spec-gen` says to clear or start a new chat before `/ticket-gen` if your context is over 150k, and `/ticket-gen` and `/implement` say to always start a new chat before `/implement` and `/code-review`. The skill map's context advice matches, and the skill map and README name `/grill` as where the creation flow starts. A new `npm run check-skills` static check keeps the boundary lines from drifting.

- [#29](https://github.com/Ballganda/BG-skills/pull/29) [`76abc55`](https://github.com/Ballganda/BG-skills/commit/76abc5510ba1c06378c7bd8899c19c9f3789d6bc) Thanks [@Ballganda](https://github.com/Ballganda)! - `grill` now ends with one closing question that is also the hand-off: shared understanding reached, ready to turn it into a spec? Type `/spec-gen` when ready. It then waits for you to type it. During the session it writes only `GLOSSARY.md` and ADRs, never invokes `spec-gen`, `ticket-gen`, or `implement`, and answers a mid-session "just build it" with the closing question.

- [#29](https://github.com/Ballganda/BG-skills/pull/29) [`dcc2710`](https://github.com/Ballganda/BG-skills/commit/dcc27108367d2487532483583120443a2dbf8dcb) Thanks [@Ballganda](https://github.com/Ballganda)! - `grilling` now ends with one explicit closing confirmation, asked as its own question once the frontier is empty. Answers to a round ("yes", "agree all") never end the session; the agent asks the next round instead. Every skill built on it (`grill-me`, `grill`, `triage`, `wayfinder`, `improve-codebase-architecture`) gets the stricter rule.

- [`cc8d31c`](https://github.com/Ballganda/BG-skills/commit/cc8d31c949ec2f00d84a131b80e19c46331aabd2) Thanks [@Ballganda](https://github.com/Ballganda)! - `implement` now drives a bundled Python 3 script for the mechanical steps of a ticket run: integration branch, readiness, worktrees, testing, merging, recording failures, and cleanup, each one command with a one-line result. The skill gets shorter, and a run can resume in a new chat from `status`. Readiness is read from local and GitHub trackers; on other trackers the orchestrator computes it and passes ticket ids to `start`. Without Python 3 the skill tells you to install it and stops. Work described in chat does not use the script.

- [#29](https://github.com/Ballganda/BG-skills/pull/29) [`9b21514`](https://github.com/Ballganda/BG-skills/commit/9b21514a400700513ffb4a4d15051205c07cace9) Thanks [@Ballganda](https://github.com/Ballganda)! - `implement` now always runs as an orchestrator, even for a single ticket: it never implements in its own context, and hands every unit of work to an implementer subagent started with a fresh context window. It takes a Ticket batch (a label or milestone, the next N ready tickets, or both; default next 1), runs up to 3 implementers at once on one integration branch, merges clean branches itself, and suggests `code-review` rather than running it. Work described in chat with no tickets is a batch of one, handed to a single implementer. `implement-spec` is removed and folded into `implement`; its docs page stays, marked archived.

- [#215](https://github.com/Ballganda/BG-skills/pull/215) [`ffc0499`](https://github.com/Ballganda/BG-skills/commit/ffc04990648bfbf34a99d719bf5c7d505f482929) Thanks [@Ballganda](https://github.com/Ballganda)! - A pull request closes only its spec. `implement` closes each ticket as it merges into the integration branch, with a comment naming the branch and the merge commit, lists the tickets in the draft PR body without closing keywords, updates an open PR for a review-fix batch, and marks the PR ready only when every sub-issue of the spec is closed. `ticket-gen` makes tickets from a review of an open PR sub-issues of that PR's spec. The `bg-setup` tracker templates and this repo's tracker doc gain a Closing work section, and `pr` follows it.

- [`38a03b8`](https://github.com/Ballganda/BG-skills/commit/38a03b8f38d562084aff64a3ae1d0552bda283f7) Thanks [@Ballganda](https://github.com/Ballganda)! - Graduate the **decomp skills** out of `in-progress/` into the **Engineering** bucket, so they ship in the plugin ([#100](https://github.com/Ballganda/BG-skills/issues/100)). The flow `decomp-setup` → `decomp-start` → `decomp-run` is user-invoked; `decomp-identify`, `decomp-spec-gen`, `decomp-ticket-gen`, `decomp-match`, `decomp-reference`, and `decomp-standards` are model-invoked. Each has a docs page under `docs/engineering/`, and `skill-map` routes to the decompilation flow.

- [`d8823bd`](https://github.com/Ballganda/BG-skills/commit/d8823bd6ea7a8346098a55fff52cc348427ea1e3) Thanks [@Ballganda](https://github.com/Ballganda)! - The plugin ships four restricted agents (`implementer`, `explorer`, `reviewer`, `merger`), each with a default model and only the tools its role needs. `implement` starts each subagent by role with a fresh context window and overrides its model from `docs/agents/models.md`: the implementer gets its ticket's tier model (no tier means Standard; no models doc means the defaults). A failed ticket is retried once on the next tier's model, then reported; a failed Hard ticket is not retried. Subagents report in fixed one-line formats instead of a word limit, the implementer's with an optional lesson field, and you can ask the orchestrator to explain any report in plain language. Harnesses without agent definitions get the same roles through a general subagent. The static check fails if an agent loses its model or tool list, or `implement` loses a report format.

- [`35da757`](https://github.com/Ballganda/BG-skills/commit/35da75706d51c2ad8313534ebc067b8cf4be77cd) Thanks [@Ballganda](https://github.com/Ballganda)! - `ticket-gen` assigns each ticket a tier (Mechanical, Standard, Hard) while drafting, shows it in the quiz where you can change it, and writes it into both ticket templates. `bg-setup` asks which model serves each tier (defaults Haiku, Sonnet, top model) and each subagent task (exploration, merging, Standards review, Spec review), offers the harness's smallest, middle and largest models elsewhere, writes `docs/agents/models.md`, and points to it from the `## Agent skills` block. The static check fails if either template loses its tier field or `bg-setup` stops writing the models doc.

- [#29](https://github.com/Ballganda/BG-skills/pull/29) [`4421652`](https://github.com/Ballganda/BG-skills/commit/4421652993435557764441b6559b214c65f23241) Thanks [@Ballganda](https://github.com/Ballganda)! - Cut token usage in the core workflow skills. `improve-codebase-architecture` drops its Tailwind/Mermaid HTML report for an ID'd markdown candidate list (with a Test seam field) that carries straight into `/spec-gen`. `implement` now works one Ticket batch per run (a label, the next N ready tickets, or both; default next 1), caps implementers at 3, merges clean branches itself, and no longer runs `code-review`: review is its own stage. `spec-gen` writes one user story per distinct behaviour, drops the generic good-test boilerplate, omits empty sections, and explores only the modules it touches. `code-review` checks a fixed list of standards files instead of searching the repo, verifies the diff with `--stat` only, and passes the spec to its sub-agent by reference. `ticket-gen` skips refetching a spec written in the same session, explores only touched modules, compresses its wide-refactor rule and templates, and requires acceptance criteria to be testable checks that never restate What to build.

- [#29](https://github.com/Ballganda/BG-skills/pull/29) [`dd1b585`](https://github.com/Ballganda/BG-skills/commit/dd1b585d3fb813bf2b3b2d3f0789a4e5d7508cd8) Thanks [@Ballganda](https://github.com/Ballganda)! - `bg-setup` writes leaner `docs/agents/` files, which every engineering skill reads on every run. The tracker seed templates are now conditional: the PR (or MR) triage section is written only when "PRs as a request surface" is on, the Wayfinding section only when `wayfinder` is installed, and setup checks `gh --version` once to write only the matching sub-issue and blocking commands instead of the "2.94+ / older `gh`" pairs. Every tracker operation now sits in one Operations list (create, read, list, sub-issue or parent link, blocking, count open blockers, comment, labels, close), the GitLab template gains the "never file into upstream" guard, and the domain template drops both file-tree diagrams, keeping its reading rules and writing the multi-context layout only in a monorepo. The skill's own prose is compressed with every step and branch kept.

### Patch Changes

- [#1363](https://github.com/mattpocock/skills/pull/1363) [`5ae4816`](https://github.com/Ballganda/BG-skills/commit/5ae481693d13b37d4d2c2c92d0b66d299c93e695) Thanks [@mattpocock](https://github.com/mattpocock)! - `chief-of-staff` now looks for a shared wiki before starting its own. It also runs `retro` on about one in five of its subagents' sessions, the ones where something went wrong first, and acts on the findings itself, and runs `spec-gen`, `ticket-gen` and `implement` for large chunks of work, reading each skill by relative path so they can stay user-invoked.

- [`02fe22d`](https://github.com/Ballganda/BG-skills/commit/02fe22d0f57d0af66fa51fd7053013cf8aa92be3) Thanks [@Ballganda](https://github.com/Ballganda)! - Decomp skills (in progress): the project tool runs the `inventory` and `disasm` adapters itself.

  - **`inventory [--redo]`** runs the full environment check, then the `inventory` adapter with `DECOMP_TARGET` and every `DECOMP_TOOL_<NAME>` set. It exits 6 and writes nothing when the target is not an accepted edition. Once the `decomp-start` tag exists it refuses, naming the redo flow, unless `--redo` is passed.
  - **`disasm <ticket id>`** fills the expected file and address from the ticket and runs the `disasm` adapter with the same environment, after the cached environment check `check` uses.
  - **Adapters run only through the project tool.** The layout says so, `decomp-start`, `decomp-match`, and `decomp-reference` call the new commands, and the pipeline check runs the inventory through the tool. An adapter no longer needs a lookup of the machine file.

- [#217](https://github.com/Ballganda/BG-skills/pull/217) [`4185340`](https://github.com/Ballganda/BG-skills/commit/4185340ef87fba79967be8ceec676a587130384f) Thanks [@Ballganda](https://github.com/Ballganda)! - Decomp skills (in progress): the two adapter notices are stated in full once per ticket, then by name (spec [#208](https://github.com/Ballganda/BG-skills/issues/208)).

  - **Name.** The empty-report line gains the name `no-instruction-diff`, written at the start of its sentence as `no-object-identity` is.
  - **Once per ticket.** The first round of a ticket in which a condition holds states its notice in full; a later round of the same ticket names it. A round without the condition clears its record, so a returning condition is stated in full again. `release` clears both records, and a repeat round or a collected background match follows the same rule.
  - **Layout and skills.** The layout document describes both forms, `decomp-match` reads a bare name as the earlier notice still holding, and `decomp-setup` names its two upgrade signs by these names.

- [#217](https://github.com/Ballganda/BG-skills/pull/217) [`68822cc`](https://github.com/Ballganda/BG-skills/commit/68822cc2ee2467736d8b87e3b7dad45415c11b84) Thanks [@Ballganda](https://github.com/Ballganda)! - Decomp skills (in progress): a collected background search says why it ended, so the next one that builds nothing explains itself (spec [#206](https://github.com/Ballganda/BG-skills/issues/206), after finding 6 of spec [#186](https://github.com/Ballganda/BG-skills/issues/186)).

  - **End reasons.** A collected report's `end` now tells three cases apart. `stopped`: the collecting call cut the search short while it was working. `error`: it died, and the report's `error` holds the error's text, or says that the process was gone and left no report. `killed`: it would not go within the 10-second stop bound, or it was still alive after its budget plus that bound, and the report then holds `overrun`.
  - **Seconds against budget.** The report and the kept log's `collected:` line hold `ran_s`, the seconds from the search's start to its collection, and `budget_s`.
  - **Traceback.** A background search that dies of an error writes a `died of an error:` line to its log, followed by the traceback of an error nothing caught.
  - **Heartbeat removal.** A call that cannot remove its own heartbeat as it leaves the slot pool still does not fail, but keeps a line with the heartbeat's name and the error. The background search it then starts copies that line into its log at its start.
  - **Call time.** The summary's counts and the performance record gain `collect_s`: the seconds the call spent collecting the ticket's background search. It sits beside `call_s` and is part of it.
  - **Closing rule for the finding.** The finding is confirmed when one kept log (`.decomp/search/<ticket id>/background.log`, named by the report's `log`) names a cause. It is closed as not reproduced after 30 collected background searches on the real project with none reporting `tried: 0`. The result is reported on spec [#206](https://github.com/Ballganda/BG-skills/issues/206).

- [#216](https://github.com/Ballganda/BG-skills/pull/216) [`906ed60`](https://github.com/Ballganda/BG-skills/commit/906ed605db4227e622c5ef3a5fa30d45f9a189b2) Thanks [@Ballganda](https://github.com/Ballganda)! - Decomp skills (in progress): a background search that built nothing leaves its log, and does not yield to its own caller (spec [#186](https://github.com/Ballganda/BG-skills/issues/186), finding 6).

  - **Kept log.** A collected background report with `tried: 0` names `log`: the search's log is kept as `.decomp/search/<ticket id>/background.log`, in place of the last kept one. A search that tried candidates keeps none.
  - **What the log holds.** The search writes a line when it starts, when it is ready, when the foreground searches it waits on change, and when it ends. The collecting call adds what it saw: the search's files, its heartbeat's age, whether it was killed, and the foreground heartbeats in the pool.
  - **Its own caller.** A background search no longer waits on a heartbeat left in the pool under the name of the call that started it. It still yields its slots to every other foreground block.
  - **Bounded stop.** Stopping a background search waits for its process to be gone for no longer than 10 seconds, then kills its process tree once more and returns what the search had written. No host command the stop runs is waited for past that bound.

- [`8d6bcde`](https://github.com/Ballganda/BG-skills/commit/8d6bcde0bb87c964beb577a33a32fe03f6795648) Thanks [@Ballganda](https://github.com/Ballganda)! - Decomp skills (in progress): a tool with no executable can be pinned by a file.

  - **Banner file**: a tool entry in `toolchain.json` may name `banner_file`, a path relative to the tool's root, in place of `banner_cmd`. `decomp.py` reads the file itself, in whatever encoding it holds, and `doctor` passes when `banner` is a substring of its contents. This pins a platform SDK made of headers without a host-specific command.
  - **One pin per tool**: `doctor` exits 6 and names the tool when it has both `banner_file` and `banner_cmd`, or neither, and names the file when a banner file is missing.
  - **Banner command docs**: the provisioning document says manifest commands run through the host shell (`cmd.exe` on Windows) and that `{root}` is a native path continued with the host's separator. Its example banner command now goes through the wrapper, as the rule beside it requires.

- [`47934ee`](https://github.com/Ballganda/BG-skills/commit/47934ee7342234fb7e1be0b49d9851266f0a1820) Thanks [@Ballganda](https://github.com/Ballganda)! - Decomp skills (in progress): a contract change is measured before its tag moves.

  - **Candidate ref**: a branch named `c/<slug>` holds a proposed change to paths a tag freezes. `revalidate --candidate c/<slug>` accepts only such a branch, alone (no `--ref`, no `--header`), skips the frozen check for it, and lets it change any path frozen by the `decomp-setup` or `decomp-start` tag.
  - **Judged by its own copy**: the tool checks the candidate out in a clean worktree and runs that tree's copy of `decomp.py` there, so the candidate's tool, adapters, manifest, and contract judge it.
  - **Records nothing**: no ledger line, no status change. Exit 0 when every matched ticket still matches, nonzero with the regressed tickets listed when one does not (a matched ticket the candidate no longer holds is listed too), and 6 when a matched ticket could not be rebuilt on this machine, even when regressions are listed as well. A ticket already `regressed` on the integration branch does not count against the candidate.
  - **One change flow** in [LAYOUT.md](../skills/engineering/decomp-standards/LAYOUT.md): change on `c/<slug>`, run the candidate revalidation and show the user, merge and move the tag on their go-ahead, then a plain `revalidate` to record the outcome. `decomp-setup`, `decomp-start`, and the provisioning document reference it in place of their own orderings.

- [#216](https://github.com/Ballganda/BG-skills/pull/216) [`7ac3d2e`](https://github.com/Ballganda/BG-skills/commit/7ac3d2e5eb78b234c17c21d2aac190dfd6a930da) Thanks [@Ballganda](https://github.com/Ballganda)! - Decomp skills (in progress): `contract-keys` reads a contract bullet whatever Markdown emphasis it carries (spec [#186](https://github.com/Ballganda/BG-skills/issues/186), finding 1).

  - **Bullets.** A bold, italic or backtick name or value reads like a plain one, with the colon inside or outside the emphasis (`- **Permuter:** not allowed`, `- **Template search**: allowed`).
  - **Unchanged.** An old permuter line is still read as the template-search line, and a line that says neither allowed nor not allowed still stops with the same message.

- [#216](https://github.com/Ballganda/BG-skills/pull/216) [`30e42ec`](https://github.com/Ballganda/BG-skills/commit/30e42ec75d9cb3ec1e1b412073c3d49cb21143c3) Thanks [@Ballganda](https://github.com/Ballganda)! - Decomp skills (in progress): a deadline block finishes its last pass (spec [#186](https://github.com/Ballganda/BG-skills/issues/186)).

  - **Last pass.** When a `search` block reaches its deadline with no more candidates left in the space than it runs workers, it builds them and ends `exhausted`, with no `continues_s` and no background search.
  - **Bounded.** A hung compile in the last pass is still killed by the hang limit. With more candidates left than workers, the block ends `deadline` as before.

- [#217](https://github.com/Ballganda/BG-skills/pull/217) [`773dec6`](https://github.com/Ballganda/BG-skills/commit/773dec6d78a0cbb9d735a006d5c08b4019e24cbf) Thanks [@Ballganda](https://github.com/Ballganda)! - Decomp skills (in progress): a speed flag's streak is counted over the blocks that could have raised it.

  - **A block that measured nothing is passed over.** For the four measured flags, a block that built fewer than 2 candidates per worker (a cached repeat, a short matching block) neither adds to the streak nor ends it.
  - **A block of another unit is passed over.** The streak is counted over the same compiler and the same unit, so two writers on two units no longer keep the notice from showing.
  - **The notice says "in 3 blocks in a row of this unit".** The once-per-streak rule and the threshold of 3 are unchanged.

- [#216](https://github.com/Ballganda/BG-skills/pull/216) [`0cc84e1`](https://github.com/Ballganda/BG-skills/commit/0cc84e1f17cdfb2eea55f89f043aea8a16c21af4) Thanks [@Ballganda](https://github.com/Ballganda)! - Decomp skills (in progress): a `search` block's regression flags measure what their names say (spec [#186](https://github.com/Ballganda/BG-skills/issues/186), findings 2, 7 and 10).

  - **`slow-compile`** compares a block with earlier blocks of the same compiler and the same unit, once 3 exist, and its notice names the unit's history. A unit with heavier headers no longer sends the user to the antivirus and power settings.
  - **`io-jitter`** compares the block's p95 compile time with the block's own median. It reads no history.
  - **`scorer-bound`** counts the diff adapter run with scoring, so a slow adapter is flagged.
  - **`expander-starved`** counts the workers' wait for a candidate only up to the last candidate handed out. A small space that ends `exhausted` on many workers raises nothing. `idle_frac` in the performance log holds that share.

- [`ef49818`](https://github.com/Ballganda/BG-skills/commit/ef49818ca7f8d656f556c93b6d14a23216554ee2) Thanks [@Ballganda](https://github.com/Ballganda)! - Decomp skills close four gaps found against a working byte-matching project. The guardrail scan now refuses the forms that hide a directive (trigraphs, backslash line continuations, `%:` digraph directives) and holds `__pragma` and `_Pragma` to the pragma allowlist. `toolchain.json` can accept several target editions, recognise one by probes (hashes of chosen byte ranges), name known-wrong editions with a message, and list the functions an edition holds differently; `check` and `verify` exit 6 on those. Projects gain a symbol map (`symbols.json`), guarded from writers and repaired by `decomp-reference`, and [LAYOUT.md](../skills/engineering/decomp-standards/LAYOUT.md) states a default relocation policy that masks a relocated operand only when its target is proven. Provisioning gains host prerequisites checked by `doctor`, unpack steps that run a project script (`{tools}`), one tool wrapper, and a per-unit compiler (`compiler`, `unit_compilers`, `{compiler}`). `scripts/test-decomp.py` tests `decomp.py` against a scratch project.

- [`9c2fed4`](https://github.com/Ballganda/BG-skills/commit/9c2fed4d077a66a0041c3317de315a024365867b) Thanks [@Ballganda](https://github.com/Ballganda)! - Decomp skills (in progress): the guardrail scan follows every include.

  - **Include chain**: the scan covers each project file a source includes, directly or through another header, beside the source or under `include/`, in whatever letter case the name is written. Before, only headers named directly under `include/` were scanned.
  - **Hidden includes refused**: an `#include` whose file a macro names, an absolute path, and a path that climbs out of the project are guardrail violations.
  - **`revalidate --header`** rebuilds every ticket that reaches the header through any chain of includes.

- [#217](https://github.com/Ballganda/BG-skills/pull/217) [`95b7d44`](https://github.com/Ballganda/BG-skills/commit/95b7d4463292101bfbad99c2075ea6a72611d655) Thanks [@Ballganda](https://github.com/Ballganda)! - Decomp skills (in progress): parallel Tickets stop conflicting in the layout reference and the block call. No behaviour of the decomp tool and no fact in the reference changes.

  - **The layout reference** keeps short tables for lookup and gives each command, path and record with detail its own section, where every fact is one bullet on one line. Existing anchors keep their names.
  - **The skills check** fails when any line of the layout reference is over 300 characters, naming the file, the line and its length.
  - **The template-search block runner** takes one options value with named fields in place of ten positional arguments, so a new option adds a field and not an edit to every call.

- [`d03e244`](https://github.com/Ballganda/BG-skills/commit/d03e2445c13cb552c2859ced525f0448ac04e42a) Thanks [@Ballganda](https://github.com/Ballganda)! - Decomp skills (in progress): the `link` command and its milestones (spec [#39](https://github.com/Ballganda/BG-skills/issues/39)).

  - **`link`** links the whole binary from the reconstructed source plus raw blocks of the target, compares it with the edition on this machine, and records a `link` event.
  - **Link milestone.** The contract's Tracking section holds a milestone size beside the revalidation interval, as a percentage or a byte count (`link_milestone` in `decomp.json`), defaulting to 5% of the in-scope bytes with a floor of 16 KB. `report` prints a `milestone:` line: `due` when the in-scope bytes of units fully matched since the last recorded link reach it, never when the link is unavailable.
  - **`/decomp-run`** runs the link after revalidation when a milestone is due, and always when the state is `finished`. The finish message states the link result, or that a whole-binary link is not available for this target.

- [#134](https://github.com/Ballganda/BG-skills/pull/134) [`74e451e`](https://github.com/Ballganda/BG-skills/commit/74e451eb5936f7b6479096f6326c632d00c2bd23) Thanks [@Ballganda](https://github.com/Ballganda)! - Decomp skills (in progress): writers and the coordinator stage named paths only, and `verify` says so when a branch carries ticket or ledger files. `decomp-match` and `decomp-run` forbid `git commit -a` and `git add -A`; a `guardrail` rejection for files under `tickets/` or `ledger/` names them as status files committed too broadly.

- [#134](https://github.com/Ballganda/BG-skills/pull/134) [`b4500bb`](https://github.com/Ballganda/BG-skills/commit/b4500bb16f678e29cbf281138c8c2fe2bd9b4fb6) Thanks [@Ballganda](https://github.com/Ballganda)! - Decomp skills (in progress): `decomp.py next` lists ready tickets strictly smallest first (tier, then size, then address), with no started-unit priority and no injected large ticket. `next --first <id> --reason <text>` lists a ready ticket first and records an `out-of-order` event.

- [#217](https://github.com/Ballganda/BG-skills/pull/217) [`644e9ae`](https://github.com/Ballganda/BG-skills/commit/644e9ae8a04bca5dd75ba0185a917d7300359c4c) Thanks [@Ballganda](https://github.com/Ballganda)! - Decomp skills (in progress): a block no longer holds workers for the opening sweep when nothing can be frozen (spec [#210](https://github.com/Ballganda/BG-skills/issues/210)).

  - **No identity, no wait.** When hashing falls back to the function's bytes and the first diffed candidate carried no `function_sha256`, a free worker takes the next candidate of the rest of the space without waiting for the sweep's results.
  - **Unchanged with identity.** Where objects are repeatable or a diff result carried `function_sha256`, the rest still waits for the sweep and inert choice points are frozen.
  - **`idle_frac`.** The layout says the wait for the sweep is part of it, and absent when the round has no object identity.

- [#216](https://github.com/Ballganda/BG-skills/pull/216) [`fdbd66b`](https://github.com/Ballganda/BG-skills/commit/fdbd66bbd3b79d977f626f6a69c42426e9671be6) Thanks [@Ballganda](https://github.com/Ballganda)! - Decomp skills (in progress): one choice can span two places in a template (spec [#186](https://github.com/Ballganda/BG-skills/issues/186), finding 12).

  - **Paired use.** `PERM_VAR(name, a, b, ...)`, a name with no `@` followed by alternatives, pairs with the earlier `PERM_VAR(@name, ...)` and expands to its own alternative at the index that one picked. It is no choice point: it adds nothing to the space, the limit of 12, or the choice code.
  - **Refusals.** A paired use with another number of alternatives is refused with both counts, one before its definition as a back reference is, and one with a label, kind, or likelihood.
  - **Steering.** A steering tag on a paired alternative makes that pick steering, and its line in the winner carries its own `fakematch:` comment.
  - **`PERM_VAR(@name)`** with no alternatives is refused with a message naming `PERM_VAR(name)` and `PERM_VAR(name, a, b, ...)`.
  - **Docs.** `decomp-standards`' grammar table and `decomp-match`'s template step name the paired form.

- [#216](https://github.com/Ballganda/BG-skills/pull/216) [`0ac8bf1`](https://github.com/Ballganda/BG-skills/commit/0ac8bf1560a9f5985ab68726230b4ad71974faf0) Thanks [@Ballganda](https://github.com/Ballganda)! - Decomp skills (in progress): calibration skips the single-function probe when there is too little to cut (spec [#186](https://github.com/Ballganda/BG-skills/issues/186)).

  - **Skip.** When the bodies of the other marked functions hold fewer characters together than `probe_min_chars`, the probe builds nothing and its calibration record is `skipped`, with the count in its `reason`.
  - **Threshold.** `probe_min_chars` joins the block constants `local.json` can override. Its default, 2,000 characters, is an estimate and has not been measured.

- [#216](https://github.com/Ballganda/BG-skills/pull/216) [`9442372`](https://github.com/Ballganda/BG-skills/commit/9442372af30d4904f3ab4ac2952249ebb6a1cbaa) Thanks [@Ballganda](https://github.com/Ballganda)! - Decomp skills (in progress): a repeat round is no round in the performance log or the block ceiling.

  - **Marked in the log.** A repeat's block record carries `repeat: true` and the number of the last counted round, so no two counted rounds share a number.
  - **Ceiling kept.** A repeat no longer writes the round-end time, so the next block's ceiling runs from the last counted round and an accidental repeat does not shorten it to the floor.

- [`a0f682f`](https://github.com/Ballganda/BG-skills/commit/a0f682f7ced5f3b5ef9a2a18e6dba9ecf2e72462) Thanks [@Ballganda](https://github.com/Ballganda)! - Decomp skills (in progress): fixes from the review of the toolchain and guardrail work, aimed at targets beyond 32-bit x86 and MSVC.

  - **Guardrail scan**: comments and string literals are set aside before matching, so neither hides code nor trips the scan. Attributes in every spelling (`__attribute__`, `__declspec`, `[[...]]`) are held to a new `attribute_allow` list, naked functions and section placement are refused in GCC, Clang, and Metrowerks spellings too, and token pasting is refused.
  - **Functions named by key**: a ticket id and expected file use a function's key, by default its address, so overlays, modules, and banks that share an address get distinct tickets. 64-bit addresses and `bank:offset` addresses work, and `PATTERNS.md` accepts their ticket ids.
  - **Hosts**: a prerequisite or tool entry can be limited to some systems with `hosts`. Commands use `{python}` and `{tools}`, in adapters as well as in the manifest.
  - **Per-unit compilers**: a compiler this machine lacks stops only the units built with it. `revalidate` no longer accepts a repair when it had to skip a matched ticket.
  - **Provisioning**: `provision` names a missing host prerequisite, and compares a file already downloaded without silently replacing it.
  - **Robustness**: tool output in any encoding, locks shared by every worktree, block-comment markers, and git older than 2.31.

- [`4b52c8e`](https://github.com/Ballganda/BG-skills/commit/4b52c8ea2a1bbcfac94b87c67cb9a8545ac47e0a) Thanks [@Ballganda](https://github.com/Ballganda)! - Decomp skills (in progress): two mismatches found on a real project.

  - **`verify --category none`**: a writer that matched reports `category: none`, and `verify` stopped on it as an unknown category. It now reads `none` as no category.
  - **Reference lock**: `decomp-run` took the `reference` lock before starting the repair subagent, and `decomp-reference` stops when the lock is already held, so no repair could run. The repair subagent now takes the lock, and the coordinator only releases it.

- [#216](https://github.com/Ballganda/BG-skills/pull/216) [`aa16867`](https://github.com/Ballganda/BG-skills/commit/aa1686794360d4c331750d161e58f722c8c09315) Thanks [@Ballganda](https://github.com/Ballganda)! - Decomp skills (in progress): `search` keeps searching between rounds (spec [#162](https://github.com/Ballganda/BG-skills/issues/162)).

  - **Background search.** When a block ends on a plateau or at its deadline with time left under the ceiling, `search` returns its summary, with `continues_s`, and leaves a detached process searching the same template on. It inherits no standard handle, so the call returns at once.
  - **Reported on the next call.** The next `search` for the ticket stops it and reports it under `background`. When it found a natural match, the call returns that match and drops the new template, with no new attempt.
  - **Stopping.** `search <id> --stop` and `release` end it with every process it started (its Job Object on Windows, its process tree elsewhere). Its liveness is a heartbeat file.
  - **Yielding.** A background search starts no build while a foreground block is running on this machine, so the block has its compile slots back within one compile.
  - **Override.** `"background": 0` under `"search"` in `.decomp/local.json` turns it off.

- [#216](https://github.com/Ballganda/BG-skills/pull/216) [`6494bc7`](https://github.com/Ballganda/BG-skills/commit/6494bc725377e86c0e7d5385addb3b5f9f220b5e) Thanks [@Ballganda](https://github.com/Ballganda)! - Decomp skills (in progress): `search` probes three faster ways to build before a ticket's first block, and keeps one only if it is faster and byte-identical (spec [#162](https://github.com/Ballganda/BG-skills/issues/162)).

  - **Single-function build.** The body of every other marked function is cut from the candidate. A match found this way is built once more as the full unit.
  - **Batching.** An optional `build_batch` adapter compiles 4 to 16 candidates in one compiler call.
  - **Resolved compiler.** An optional `build_resolve` adapter hands over the compiler's argument list and environment. The probe records whether running it directly is faster and byte-identical. No block uses it: adopting it needs an ADR.
  - **Records.** Each probe writes one calibration record to `.decomp/perf.jsonl`. The summary's `counts` add `single_function` and `batch`.
  - **Block constants.** `probe_gain` and `probe_runs` join the overrides in `local.json`.

- [#216](https://github.com/Ballganda/BG-skills/pull/216) [`2775e36`](https://github.com/Ballganda/BG-skills/commit/2775e36686edaceaa4c91a6261ec880243d65914) Thanks [@Ballganda](https://github.com/Ballganda)! - Decomp skills (in progress): a round's counts say what they measure, and report the whole call (spec [#186](https://github.com/Ballganda/BG-skills/issues/186), finding 11).

  - **`call_s`.** The search summary's `counts` and the block's performance record gain `call_s`, the seconds of the whole `search` call: calibration, probes, and the block. It is never smaller than `wall_s`, which stays the block's seconds alone.
  - **Layout.** `LAYOUT.md` says that `budget` is the estimate made when sampling began and that `compiled` can pass it, and that `best_score_end` is the block's own best and can be worse than `best_score_start`.
  - No field is renamed.

- [#216](https://github.com/Ballganda/BG-skills/pull/216) [`cc9d0fd`](https://github.com/Ballganda/BG-skills/commit/cc9d0fddd58200d8712c49f0678079b79e88415d) Thanks [@Ballganda](https://github.com/Ballganda)! - Decomp skills (in progress): `search` reads the full template grammar and skips repeated work (spec [#162](https://github.com/Ballganda/BG-skills/issues/162)).

  - **Grammar.** Labels, kinds, likelihoods, `PERM_VAR`, `PERM_ONCE`, `PERM_INT`, `PERM_LINESWAP`, and `PERM_IGNORE`, with limits the tool enforces.
  - **Sweep.** A round tries the baseline, then each one-choice change, and freezes a choice point no alternative changes (`inert`). The summary adds `effects`.
  - **Dedupe and cache.** A candidate is built once per round, and scores persist in `.decomp/search-cache.json` across rounds. `first_differ` from the `diff` adapter centres the summary's window.

- [#216](https://github.com/Ballganda/BG-skills/pull/216) [`cc9d0fd`](https://github.com/Ballganda/BG-skills/commit/cc9d0fddd58200d8712c49f0678079b79e88415d) Thanks [@Ballganda](https://github.com/Ballganda)! - Decomp skills (in progress): `search` learns across rounds and advises when to stop (spec [#162](https://github.com/Ballganda/BG-skills/issues/162)).

  - **Mutation and crossover.** A later block of a template also builds candidates from the best earlier ones, with a bandit sharing picks between sampling, mutation, and crossover.
  - **History.** Attempts the ledger recorded raise the likelihood of the kinds that fixed a category before, and the summary's `history` line says so.
  - **Stop.** The summary's `stop` advises giving up when every choice point is inert or 2 rounds in a row brought no new best score.
  - **Performance log.** `.decomp/perf.jsonl` records each block and raises regression flags, shown to the user after 3 in a row.

- [#216](https://github.com/Ballganda/BG-skills/pull/216) [`650c6ba`](https://github.com/Ballganda/BG-skills/commit/650c6ba67880dcdd620b1febb8da5ffc47f644c9) Thanks [@Ballganda](https://github.com/Ballganda)! - Decomp skills (in progress): `search` runs a template's candidates as a parallel, deadline-driven block (spec [#162](https://github.com/Ballganda/BG-skills/issues/162)).

  - **Workers.** Candidates build on worker threads, one adapter process each, in a scratch folder per worker.
  - **No shell.** `search` starts the build and diff adapters without the host's shell, and falls back to it for a command that needs one. `check`, `verify`, and `link` keep the shell.
  - **End reasons.** A block ends on `match`, `abort-buildfail`, `exhausted`, `plateau`, or `deadline`. The deadline has a floor (10 seconds and 200 builds) and a ceiling (the last round's model latency, at most 60 seconds).
  - **Hangs.** An adapter run that outlasts 10 times the median compile time is killed as a whole process tree (a Job Object on Windows, a process group elsewhere) and counts as a build-fail.
  - **Overrides.** `"search"` in `.decomp/local.json` overrides any block constant for this machine.
  - **Summary.** `counts` gains `workers`, `wall_s`, `killed`, and `shell`.

- [#216](https://github.com/Ballganda/BG-skills/pull/216) [`071e95e`](https://github.com/Ballganda/BG-skills/commit/071e95ebffb3a6da76a51a3abffc8933a791d884) Thanks [@Ballganda](https://github.com/Ballganda)! - Decomp skills (in progress): `search` samples a template too large for one block, best-first from priors (spec [#162](https://github.com/Ballganda/BG-skills/issues/162)).

  - **Budget.** A block works out how many compiles it fits from its compile rate and deadline. A space that fits is still tried whole, most likely first.
  - **Sampling.** A larger space is picked one candidate at a time by seeded Thompson sampling over each alternative's likelihood, updated after every scored candidate. At least 20 percent of picks are exploratory and aim at pairs of alternatives not yet tried together. At equal likelihood a natural alternative ranks above a steering one.
  - **Priors.** An alternative written as the closest matched functions from `similar` are written gets a higher likelihood, beside the writer's own and the project history.
  - **Slow compilers.** With a budget under 100 compiles, sampling opens with a pairwise covering sample, likeliest first.
  - **Summary.** `pairs` names up to 3 pairs of alternatives whose joint effect differs from the sum of their single effects. A sampled block's `counts` add `budget`, `pairwise`, `sampled`, and `explored`.
  - **Block constants.** `budget` and `seed` join the overrides in `local.json`.
  - **`LAYOUT.md`** documents the sampling, the constants, and the new summary fields.

- [#216](https://github.com/Ballganda/BG-skills/pull/216) [`22d04c8`](https://github.com/Ballganda/BG-skills/commit/22d04c86adefd04b7b8951f18939040dacc60529) Thanks [@Ballganda](https://github.com/Ballganda)! - Decomp skills (in progress): a `search` block tunes its own worker count and watches a reference compile (spec [#162](https://github.com/Ballganda/BG-skills/issues/162)).

  - **Tuning.** Every 2 seconds a block compares its unique compiles per second with the tick before. A gain above 5 percent adds a worker; a loss above 10 percent, or a p95 compile time above 2 times the median, takes one back. The count stays between half the starting count and the search's share of the slot pool. A `workers` set in `local.json` is kept as it is.
  - **Reference compile.** Every 30 seconds the block recompiles the baseline. A run more than 30 percent over the block's first compiles halves the worker count and raises `contention-or-throttle`.
  - **Starved blocks.** A block the slot pool holds below its worker floor for over half its time raises `starved-by-writers`.
  - **Performance log.** A block record's `workers_min`, `workers_max`, and `workers_end` now move, and it gains `unit`, `workers_floor`, `starved_frac`, `t_ref_base_ms`, and `t_ref_max_ms`.
  - **Block constants.** `tune_s`, `tune_gain`, `tune_loss`, `tune_spread`, and `reference_s` join the overrides in `local.json`.
  - **`LAYOUT.md`** documents the tuning, the reference compile, the constants, and the two flags.

- [#216](https://github.com/Ballganda/BG-skills/pull/216) [`cc9d0fd`](https://github.com/Ballganda/BG-skills/commit/cc9d0fddd58200d8712c49f0678079b79e88415d) Thanks [@Ballganda](https://github.com/Ballganda)! - Decomp skills (in progress): searches on one machine share a pool of compile slots (spec [#162](https://github.com/Ballganda/BG-skills/issues/162)).

  - **Pool.** `.decomp/slots/` holds one slot per physical core. A worker holds a slot only while it builds, and a search divides the slots by the active writers.
  - **Reclaim.** A slot whose holder stops its heartbeat for 30 seconds is taken back.
  - **Wine.** On Wine hosts a block keeps one wineserver running across its builds.

- [#216](https://github.com/Ballganda/BG-skills/pull/216) [`a546b0c`](https://github.com/Ballganda/BG-skills/commit/a546b0c805bfa696ae7a6c4fa90583627913229d) Thanks [@Ballganda](https://github.com/Ballganda)! - Decomp skills (in progress): `search` finds the closest solved functions from the matches ledger.

  - **Fewer files read.** The similar-function bonus takes its candidates from `ledger/matches.jsonl` and reads only those ticket files, so a round no longer reads every ticket of the project. On a trial project with 24,932 tickets that scan was 7.4 s of an 8.4 s cached round. A background search uses the same path.
  - **Same ranking.** The bonus and its order are unchanged. A matched ticket whose file or expected bytes cannot be read is left out, as is one that has since regressed.
  - **A ticket marked matched by hand gives no bonus.** Only a match that `audit pass` recorded in the ledger counts.

- [#216](https://github.com/Ballganda/BG-skills/pull/216) [`5977b50`](https://github.com/Ballganda/BG-skills/commit/5977b50e0b0d014923381b66e039e8ab2b9885c0) Thanks [@Ballganda](https://github.com/Ballganda)! - Decomp skills (in progress): `/decomp-setup` asks the diff adapter for what template search needs (spec [#186](https://github.com/Ballganda/BG-skills/issues/186), findings 3 and 4, project side).

  - **Adapter contract.** The layout document asks for one report line per instruction with its offset, on 32-bit and 64-bit targets alike: a disassembler prints 8-digit or 16-digit addresses by target.
  - **Setup.** Where the contract allows template search, the diff adapter prints `first_differ` and `function_sha256`. Where it does not, both stay optional.
  - **Pipeline check.** One new box, ticked only when template search is allowed: for a build known to differ, the diff result carries both fields and the report holds more than its header line.
  - **Skill upgrade.** It adds the same to an existing project's diff adapter where template search is allowed, as a contract change with its ADR. The signs that it is due are the `search` summary's two notice lines: no object identity, and no instruction diff.

- [#217](https://github.com/Ballganda/BG-skills/pull/217) [`898c1cf`](https://github.com/Ballganda/BG-skills/commit/898c1cf5da2e47b2032d20a87f5e1ea13dc95dd2) Thanks [@Ballganda](https://github.com/Ballganda)! - Decomp skills (in progress): `similar` takes the solved functions from the matches ledger, as `search` does.

  - **Fewer files read.** `similar` reads only the tickets `ledger/matches.jsonl` names and the ticket asked about, so its cost no longer grows with the open tickets. On a trial project with 24,932 tickets the scan was about 7.4 s.
  - **One answer.** `similar` and the bonus of `search` rank the same functions. The output line, its order and `--n` are unchanged.
  - **A damaged ticket no longer stops it.** A matched ticket whose file or expected bytes cannot be read is left out. `similar` on a ticket with no expected bytes prints nothing and passes.
  - **A ticket marked matched by hand is no longer listed.** Only a match that `audit pass` recorded in the ledger counts.

- [`6cb5fe6`](https://github.com/Ballganda/BG-skills/commit/6cb5fe6e2923fb6acd57c651d40ebad4a8260f6b) Thanks [@Ballganda](https://github.com/Ballganda)! - Decomp skills (in progress): `decomp-setup` gains a skill upgrade section.

  - **Skill upgrade**: running `/decomp-setup` on an existing decomp project diffs the project's copy of the project tool against the skill's. When they differ, the project is upgraded as a contract change: an ADR, a fresh copy of the tool, the contract files the newer skills require (the manifest, adapters rewired to the environment variables), and the pipeline check run again, carried through the layout's change flow so the tag moves only after the candidate revalidation and the user's go-ahead. The candidate revalidation is started with the skill's copy of the tool, since an older project's copy has no `--candidate`.
  - **One trigger**: only the user starts an upgrade. No other skill compares the copies or warns.

- [`48cab59`](https://github.com/Ballganda/BG-skills/commit/48cab59c50cad79bbb5c5b4c4ec8e8a6c5d5f057) Thanks [@Ballganda](https://github.com/Ballganda)! - Add nine in-progress `decomp-*` skills for byte-for-byte binary reconstruction: `decomp-setup` (contract and enforcing project, no decomp), `decomp-identify` (compiler and flags from the binary), `decomp-start` with `decomp-spec-gen` and `decomp-ticket-gen` (inventory, unit specs, function tickets), `decomp-run` (separate writer, tool, and auditor roles, automatic proven-lesson capture), `decomp-match` (one function to an exact match), `decomp-reference` (shared declaration repair under a lock, rejected on any regression), and `decomp-standards` (guardrails, size tiers, mismatch categories, layout). `decomp-setup` ships `decomp.py`, the project tool that alone records matches. Existing skills are unchanged.

- [#216](https://github.com/Ballganda/BG-skills/pull/216) [`e50acac`](https://github.com/Ballganda/BG-skills/commit/e50acac7ee7d93e0700e05eabeb4b018bb5c3692) Thanks [@Ballganda](https://github.com/Ballganda)! - Decomp skills (in progress): the project tool decides when template search may start (spec [#162](https://github.com/Ballganda/BG-skills/issues/162)).

  - **Check trail.** Every `check` run and every template round appends one record to `.decomp/trail.jsonl` (ticket, result, `differ_bytes`, category, time). It stays on this machine and is never committed.
  - **`check <id> --category <c>`** takes the writer's mismatch category and refuses one outside the list.
  - **The gate.** `check`'s JSON gains `search_open` and `search_reason`. Template search opens on a latest category of `register-allocation`, `statement-order`, or `expression-shape`, or after 3 attempts with no fall in `differ_bytes`. It stays closed for TINY tickets and for the stop-or-report categories. `search` refuses with the reason while it is closed.
  - **`verify --template-round`** marks the attempt as a template round: its evidence file gains the round's best candidate and winning kinds. The fields of `attempts.jsonl` are unchanged.
  - **`LAYOUT.md`** documents the trail, the gate, the argument, the JSON fields, and the flag.

- [#216](https://github.com/Ballganda/BG-skills/pull/216) [`3cd75e8`](https://github.com/Ballganda/BG-skills/commit/3cd75e871c75cb9cc775b8d5ba4a833e312f4777) Thanks [@Ballganda](https://github.com/Ballganda)! - Decomp skills (in progress): `search` reads natural and steering alternatives under the contract's fakematch rule (spec [#162](https://github.com/Ballganda/BG-skills/issues/162)).

  - **Steering tag.** An alternative led by `/* steer: <why> */` is steering. Every other alternative is natural.
  - **Refusal.** A template holding a steering alternative is refused, with nothing built, when `fakematch` is `forbidden`.
  - **Natural first.** A natural match ends the round. A match that needs steering keeps the round going for a natural one, then drops each steering choice it does not need.
  - **Winner.** Each surviving steering line carries a `fakematch: <why>` comment.

- [#216](https://github.com/Ballganda/BG-skills/pull/216) [`2b7f5b1`](https://github.com/Ballganda/BG-skills/commit/2b7f5b17eec9489d4a479d1bdba3bfccca204c49) Thanks [@Ballganda](https://github.com/Ballganda)! - Decomp skills (in progress): the project tool gains `search`, the first slice of template search (spec [#162](https://github.com/Ballganda/BG-skills/issues/162)).

  - **`search <id> <template file>`** tries every candidate of a template (the unit's source with `PERM_GENERAL` choice points), each built in a scratch copy of the unit's folder layout, and stops at the first exact match. It prints a JSON summary capped at about 600 tokens: the best choice code, a diff window, counts, and the end reason (`match` or `exhausted`). On a match it writes the winner as plain C outside the tree.
  - **`search <id> --detail '<choice code>'`** prints one candidate's score and source.
  - **Refusals.** Exit 6 when `doctor`'s checks fail, and a refusal with the reason when the contract disallows template search. It records nothing: the unit, the ledger, and frozen files are unchanged.
  - **`LAYOUT.md`** documents the command, the template, and the summary.

- [`21bda12`](https://github.com/Ballganda/BG-skills/commit/21bda126d4816b12780ea051a62d98cf461de423) Thanks [@Ballganda](https://github.com/Ballganda)! - Decomp skills can now build the toolchain environment. `decomp-identify` adds a Toolchain requirements section (each tool's exact version, official source, and whether this machine has it) and offers two routes when one is missing: the user installs it, or the agent does. `decomp-setup` gains a provisioning step ([PROVISION.md](../skills/engineering/decomp-setup/PROVISION.md)) that records every tool in a frozen `toolchain.json`. `decomp.py` gains `provision` (download, compare size and SHA-256, unpack into `.decomp/toolchain/`) and `doctor` (target hash, required files, version banners), and runs the `doctor` checks before every `check`, `verify`, and `revalidate`. Adapters now find the target and tools through `DECOMP_TARGET` and `DECOMP_TOOL_<NAME>`.

- [#216](https://github.com/Ballganda/BG-skills/pull/216) [`1811634`](https://github.com/Ballganda/BG-skills/commit/1811634e8f11eb60837ba23ba16bce93cffcd8cb) Thanks [@Ballganda](https://github.com/Ballganda)! - Decomp skills (in progress): template search reads a missing object identity as unknown (spec [#186](https://github.com/Ballganda/BG-skills/issues/186), finding 3).

  - **Counts.** When the compiler's objects differ between two compiles and the diff adapter prints no `function_sha256`, the summary's `unique_objects` and `object_hits` and the performance record's `unique_objects` are `null`, not zero.
  - **Notice.** That summary carries one `no-object-identity` line: object dedupe and the inert freeze are off, and the fix is a diff adapter that prints `function_sha256`, through `/decomp-setup`'s upgrade.
  - **Layout document.** It says when the two counts are `null`, and that the plateau rule then rests on the best score alone.

- [#216](https://github.com/Ballganda/BG-skills/pull/216) [`8d93d2b`](https://github.com/Ballganda/BG-skills/commit/8d93d2b3f1941738be994ad2d5f92db9a0b4fc43) Thanks [@Ballganda](https://github.com/Ballganda)! - Decomp skills (in progress): the `search` summary's diff window no longer hides that text is missing (spec [#186](https://github.com/Ballganda/BG-skills/issues/186), finding 4).

  - **Cut mark.** A report line longer than the window width of 120 characters is cut inside the width and ends in ` ...`. A shorter line is unchanged.
  - **Empty report.** When the best candidate's report holds fewer than 2 lines, the summary's `notice` says in one line that the diff report holds no instruction diff, and names the diff adapter as the fix.

- [`b62c541`](https://github.com/Ballganda/BG-skills/commit/b62c541de5289560ba43b2128e952966ba54e919) Thanks [@Ballganda](https://github.com/Ballganda)! - `domain-modeling` is about half as long. One behaviour is clarified: a term that clashes with `GLOSSARY.md` is called out even when you handed the naming to the agent, which then says which name it picked. Everything else is unchanged: terms are still challenged and written to `GLOSSARY.md` inline, files are still created lazily, ADRs are still offered only when all three tests hold, and the glossary and ADR format files still load only when an entry or ADR is written.

- [#97](https://github.com/Ballganda/BG-skills/pull/97) [`cb58530`](https://github.com/Ballganda/BG-skills/commit/cb585303d7d3bdd5c4187072da6b243f2486d86d) Thanks [@Ballganda](https://github.com/Ballganda)! - Skills and docs pages say "final reply", not "final report", for the message to the user: `implement`, `retro`, `skill-map` and `diagnosing-bugs`. A subagent's return stays a report. `triage`'s recommend step now opens with the category and state call in one line, then numbered points the maintainer can answer one by one, each with its recommendation.

- [`3f4ae1e`](https://github.com/Ballganda/BG-skills/commit/3f4ae1ea65bd05d5f54d041294e217e2228b975f) Thanks [@Ballganda](https://github.com/Ballganda)! - `grilling` is shorter (2,385 to 1,544 chars) and its rounds are tighter: brief question bodies, one-line recommendations, a recommendation on every question (a best guess where only the user knows), and one opening line per decision the user handed the agent, saying what it chose and why. Measured by the `/grill` eval suite: lower tokens on every case, every grader still passing.

- [#29](https://github.com/Ballganda/BG-skills/pull/29) [`7560ecf`](https://github.com/Ballganda/BG-skills/commit/7560ecf71d75bc4dad568aac329123501308247b) Thanks [@Ballganda](https://github.com/Ballganda)! - `implement`'s chat-work path no longer points its implementer at worktree steps it never set up: the worktree check and the integration-branch merge in step 4 are now marked as applying to Ticket batches only. The README and bucket READMEs drop the upstream author's first-person voice, and the `wait-what` docs page gains its Common questions section.

- [#215](https://github.com/Ballganda/BG-skills/pull/215) [`bafd5e1`](https://github.com/Ballganda/BG-skills/commit/bafd5e199fb7b939b57acc60ba711be2629cacf3) Thanks [@Ballganda](https://github.com/Ballganda)! - `implement` now settles one set of commit attribution lines per run and puts them on every commit: implementer commits, merger commits, and the script's merge commits.

- [#215](https://github.com/Ballganda/BG-skills/pull/215) [`f32cc07`](https://github.com/Ballganda/BG-skills/commit/f32cc07643da413d3bd82b3ef2f876b6aa5c2a38) Thanks [@Ballganda](https://github.com/Ballganda)! - `implement` finds a working Python 3 by trying `python3`, `python`, then `py`, instead of stopping when a broken `python3` alias fails. It also starts the integration branch from the branch a spec builds on when that work is not yet in the default branch: the base is stated with the batch, and `begin` names it in its reply.

- [#1342](https://github.com/mattpocock/skills/pull/1342) [`a496f55`](https://github.com/Ballganda/BG-skills/commit/a496f5513d4a4cf889bc48e189e579f4b0bdf6aa) Thanks [@mattpocock](https://github.com/mattpocock)! - `implement` now uses a fresh implementer subagent for each ticket, instead of reusing an earlier implementer.

- [`e22866c`](https://github.com/Ballganda/BG-skills/commit/e22866cff001c5831920c950e59f73b914aa21db) Thanks [@Ballganda](https://github.com/Ballganda)! - The plugin validation gate is now plain `claude plugin validate .` instead of `--strict`. The maintainer `CLAUDE.md` at the plugin root triggers an expected warning that no longer blocks work. ADR 0002 records why the plugin stays at the repo root.

- [`ebbaedc`](https://github.com/Ballganda/BG-skills/commit/ebbaedc595748518f5046c009f4d9b801950973a) Thanks [@Ballganda](https://github.com/Ballganda)! - The plugin has an icon in the plugin menu: a stick figure beating a dead horse, as flat line art on an off-white square. `scripts/draw-icon.py` draws it with Pillow into `.claude-plugin/icon.png` (1024 px square), and rerunning the script reproduces the committed PNG. The static check fails if the icon is missing, not square, outside 512 to 2048 px on a side, or over 2 MB.

- [`802f095`](https://github.com/Ballganda/BG-skills/commit/802f095759b75af6b4a78ec59b49143460e6627b) Thanks [@Ballganda](https://github.com/Ballganda)! - `retro` takes its mode from the caller (User-typed, Lesson-line, Diagnosing-bugs), with User-typed the default. `implement` resolves the tickets, runs retro if any lesson came back, then writes the final report and cleans up; `diagnosing-bugs` keeps retro inside its done checklist. The static check reads every skill through one shared reader, fails any skill whose frontmatter and Codex metadata disagree on invocation, and fails any skill with no `agents/openai.yaml`. `software-factory` gets Codex metadata that keeps it user-invoked. The skill-map, retro and implement docs pages match their skills again.

- [`f309c1e`](https://github.com/Ballganda/BG-skills/commit/f309c1ea20cd427752b0a638e5bebc669b388c5e) Thanks [@Ballganda](https://github.com/Ballganda)! - New user-facing doc `docs/session-floor.md` explains what makes up a session's starting token count (the harness system prompt, connector tool definitions, and installed skill descriptions, with the split marked as an inference), what to turn off to lower it (unused connectors and plugins), and how to view the context breakdown with `/context`. The doc is linked from the README under a new Guides section.

- [`b893b52`](https://github.com/Ballganda/BG-skills/commit/b893b528afe58d9b50cff0c3c0e42d24daa9629e) Thanks [@Ballganda](https://github.com/Ballganda)! - Shorter skill descriptions, enforced by `check-skills`.

  - **Limits**: a user-invoked skill's description is at most 20 words, a model-invoked one's at most 40. `scripts/check-skills.mjs` fails on any skill over its limit, in every bucket.
  - **Trimmed**: twelve descriptions shortened. Model-invoked ones still say when to use them.

- [#1316](https://github.com/mattpocock/skills/pull/1316) [`4ae2317`](https://github.com/Ballganda/BG-skills/commit/4ae2317ddb22b046e26455e4f9c9b3aaaf62212d) Thanks [@mattpocock](https://github.com/mattpocock)! - Add `software-factory`, an in-progress user-invoked reference skill: a glossary for designing a software factory (tasks, runs, runners, triggers, and the services they plug into), example tasks grouped by the problem they solve, surveys of the products that fill each slot (ticket trackers, git hosts, runners, observability platforms), and the questions that finish a design. Call it alongside a grilling session.

- [#216](https://github.com/Ballganda/BG-skills/pull/216) [`1299ebc`](https://github.com/Ballganda/BG-skills/commit/1299ebc5ac3dc41bf38033eea1ef2a1d308398c6) Thanks [@Ballganda](https://github.com/Ballganda)! - Decomp skills (in progress): the contract's permuter line becomes a template-search line (spec [#162](https://github.com/Ballganda/BG-skills/issues/162)).

  - **Contract.** "Template search: allowed or not" replaces "Permuter: allowed or not", with an ADR. `decomp.json` gains `template_search` and `fakematch` keys that mirror the contract.
  - **`doctor`** prints both rules, and names the skill upgrade when a project's `decomp.json` lacks the keys.
  - **`contract-keys`** prints the keys an upgrade writes, reading an old permuter line as the template-search line.
  - **Guardrail rule 7** names template-search steering instead of permuter output.

## 1.3.2

### Patch Changes

- [#1194](https://github.com/mattpocock/skills/pull/1194) [`b645f47`](https://github.com/mattpocock/skills/commit/b645f47de3e17ed3bf60586c9bebb8092e0f79fd) Thanks [@mattpocock](https://github.com/mattpocock)! - `ask-matt` now reads a skill's `SKILL.md` before stating what it does or recommending a step be skipped, instead of trusting its own one-line summaries ([#614](https://github.com/mattpocock/skills/issues/614)).

- [#1304](https://github.com/mattpocock/skills/pull/1304) [`5beb35b`](https://github.com/mattpocock/skills/commit/5beb35b040e3de97e54fa9e386d7e42d15c295c2) Thanks [@mattpocock](https://github.com/mattpocock)! - `chief-of-staff` now keeps its memory in an LLM wiki (an `index.md` plus one page per topic, maintained through ingest, query and lint) and writes it as a historical record: every claim is dated, and every claim about code cites the commit it was true at.

- [#1208](https://github.com/mattpocock/skills/pull/1208) [`3da8c01`](https://github.com/mattpocock/skills/commit/3da8c01116264675eeefbd6e9d59c734de9095cc) Thanks [@mattpocock](https://github.com/mattpocock)! - `code-review` now searches the repo for standards files and always hands `CODING_STANDARDS.md` / `CONTRIBUTING.md` to the Standards sub-agent ([#1065](https://github.com/mattpocock/skills/issues/1065)), runs both sub-agents in the foreground and uses their returned reports ([#1073](https://github.com/mattpocock/skills/issues/1073)), and resolves the issue tracker through the provided tracker doc instead of a hard-coded path ([#937](https://github.com/mattpocock/skills/issues/937)).

- [#1209](https://github.com/mattpocock/skills/pull/1209) [`f3fc563`](https://github.com/mattpocock/skills/commit/f3fc5632f401156837ee3872f14fe33ccf1024ea) Thanks [@mattpocock](https://github.com/mattpocock)! - `diagnosing-bugs` Phase 5 now has the agent `diff` a forced mutation against a pristine copy before trusting the red, so an edit that silently changed nothing can't pass as a failing test ([#955](https://github.com/mattpocock/skills/issues/955)).

- [#1187](https://github.com/mattpocock/skills/pull/1187) [`e0efb6e`](https://github.com/mattpocock/skills/commit/e0efb6e7435ebb420d8a25d6816ed1ebaa2d23d2) Thanks [@mattpocock](https://github.com/mattpocock)! - Fixed the GitHub tracker template's external-PR listing, which failed on `authorAssociation` ([#468](https://github.com/mattpocock/skills/issues/468), thanks @lofi-coding). Re-run `/setup-matt-pocock-skills` to refresh `docs/agents/issue-tracker.md`.

- [#1169](https://github.com/mattpocock/skills/pull/1169) [`59db609`](https://github.com/mattpocock/skills/commit/59db609eb1e18aaf59b63284d0e52255aff0c63c) Thanks [@mattpocock](https://github.com/mattpocock)! - The GitHub issue tracker template that `setup-matt-pocock-skills` writes now tells agents to file issues only into the user's own repo, never into `mattpocock/skills`, and to check the target repo before the first `gh issue create`. Agents working in a clone or fork of this repo had filed their specs and tickets here ([#541](https://github.com/mattpocock/skills/issues/541) to [#550](https://github.com/mattpocock/skills/issues/550)).

- [#1193](https://github.com/mattpocock/skills/pull/1193) [`95249b0`](https://github.com/mattpocock/skills/commit/95249b0b49782349740fd9b8c6ce32b4e59e497a) Thanks [@mattpocock](https://github.com/mattpocock)! - `grilling` words each question so "yes" accepts the recommended answer, so agreeing never means answering "no" ([#706](https://github.com/mattpocock/skills/issues/706)).

- [#1184](https://github.com/mattpocock/skills/pull/1184) [`4f4e943`](https://github.com/mattpocock/skills/commit/4f4e9433bbb7c4957ef33b1ea26686fb7c2a4cf4) Thanks [@mattpocock](https://github.com/mattpocock)! - `handoff` now names where the OS temp directory is (`$TMPDIR`, else `/tmp`; `%TEMP%` on Windows), so agents stop guessing ([#272](https://github.com/mattpocock/skills/issues/272)).

- [#1189](https://github.com/mattpocock/skills/pull/1189) [`e48341a`](https://github.com/mattpocock/skills/commit/e48341a3d412cfeba4b9a79d3fd0331fc376ba82) Thanks [@mattpocock](https://github.com/mattpocock)! - `implement` now calls the Skill tool for `tdd` and `code-review` instead of bare `/skill` prose, matching [#878](https://github.com/mattpocock/skills/issues/878).

- [#1196](https://github.com/mattpocock/skills/pull/1196) [`6d6a5b9`](https://github.com/mattpocock/skills/commit/6d6a5b9072f47ee7ba1d972d8ce0ee98b7ed4394) Thanks [@mattpocock](https://github.com/mattpocock)! - `implement` fetches a passed ticket reference from the issue tracker and states its title before starting, asking when the reference is ambiguous ([#700](https://github.com/mattpocock/skills/issues/700)).

- [#1228](https://github.com/mattpocock/skills/pull/1228) [`ed0de59`](https://github.com/mattpocock/skills/commit/ed0de59eb5de8c2730a650cc69f588ffa64c1040) Thanks [@mattpocock](https://github.com/mattpocock)! - `setup-matt-pocock-skills` now wires up a git remote before writing a GitHub/GitLab tracker that nothing can reach ([#1201](https://github.com/mattpocock/skills/issues/1201)), and offers to `git mv` a legacy `CONTEXT.md` / `CONTEXT-MAP.md` to its `GLOSSARY` name ([#1176](https://github.com/mattpocock/skills/issues/1176)). The GitHub template comments before closing ([#873](https://github.com/mattpocock/skills/issues/873)), reads a PR's body as well as its comments ([#1138](https://github.com/mattpocock/skills/issues/1138)), moves **Blocking** into Conventions with the native `gh` flags ([#855](https://github.com/mattpocock/skills/issues/855)), and names the command that counts open blockers ([#1118](https://github.com/mattpocock/skills/issues/1118)). The GitLab template lists MRs with `-O json` and names the frontier query's command ([#1143](https://github.com/mattpocock/skills/issues/1143)). Re-run `/setup-matt-pocock-skills` to refresh `docs/agents/`.

- [#1197](https://github.com/mattpocock/skills/pull/1197) [`5b7cade`](https://github.com/mattpocock/skills/commit/5b7cade4d68947f34dae71326a0ce89f09e22c9c) Thanks [@mattpocock](https://github.com/mattpocock)! - `setup-matt-pocock-skills` now creates missing triage labels on GitHub/GitLab ([#616](https://github.com/mattpocock/skills/issues/616)), fixes the GitLab template's `glab` commands ([#635](https://github.com/mattpocock/skills/issues/635)), reads GitHub issues with `--json` so labels and body come through ([#733](https://github.com/mattpocock/skills/issues/733)), and names the "Label in our tracker" column in `triage-labels.md` ([#801](https://github.com/mattpocock/skills/issues/801)). Re-run `/setup-matt-pocock-skills` to refresh `docs/agents/`.

- [#1341](https://github.com/mattpocock/skills/pull/1341) [`7739eae`](https://github.com/mattpocock/skills/commit/7739eaed7f8f3915437a8def198a6d0d7206dbc7) Thanks [@mattpocock](https://github.com/mattpocock)! - Skills that dispatch subagents (`implement-spec`, `code-review`, `codebase-design`, `improve-codebase-architecture`, `wayfinder`, `research`, `grilling`, `chief-of-staff`) now say to start each one with a fresh context window rather than forking the current conversation, which some harnesses (Codex) do by default and which throws away the clean context a subagent exists for.

- [#1192](https://github.com/mattpocock/skills/pull/1192) [`3f59913`](https://github.com/mattpocock/skills/commit/3f599139104dfceabc7754eeb91319802f85e042) Thanks [@mattpocock](https://github.com/mattpocock)! - `tdd` now gives each proposed seam a one-line note on what it catches and what it misses, so choosing between seams is no longer a guess ([#607](https://github.com/mattpocock/skills/issues/607)).

- [#1183](https://github.com/mattpocock/skills/pull/1183) [`ad5400b`](https://github.com/mattpocock/skills/commit/ad5400b930b297b0c0cb231ff1ffe42a7da666aa) Thanks [@mattpocock](https://github.com/mattpocock)! - `teach` quizzes vary which position holds the correct answer ([#611](https://github.com/mattpocock/skills/issues/611)).

- [#1183](https://github.com/mattpocock/skills/pull/1183) [`ad5400b`](https://github.com/mattpocock/skills/commit/ad5400b930b297b0c0cb231ff1ffe42a7da666aa) Thanks [@mattpocock](https://github.com/mattpocock)! - `teach` writes its workspace to the directory you ran it in, not the skill folder ([#377](https://github.com/mattpocock/skills/issues/377)).

- [#1188](https://github.com/mattpocock/skills/pull/1188) [`cffab50`](https://github.com/mattpocock/skills/commit/cffab50350e3d96688f63f890f4d7ca0e6007cfe) Thanks [@mattpocock](https://github.com/mattpocock)! - `to-tickets` makes each ticket a sub-issue of its source issue (the GitHub tracker template now gives the command), and omits `## Blocked by` when blockers are native edges. Re-run `/setup-matt-pocock-skills` to refresh `docs/agents/issue-tracker.md`. Thanks @richardwhatever ([#554](https://github.com/mattpocock/skills/issues/554)) and @adamslowe ([#262](https://github.com/mattpocock/skills/issues/262)).

- [#1181](https://github.com/mattpocock/skills/pull/1181) [`8295b8e`](https://github.com/mattpocock/skills/commit/8295b8e10d4cdb6cce772a56dda7b7c37075074d) Thanks [@mattpocock](https://github.com/mattpocock)! - `wayfinder` no longer labels maps or tickets `ready-for-agent` ([#518](https://github.com/mattpocock/skills/issues/518)), writes cross-references only with real issue ids ([#507](https://github.com/mattpocock/skills/issues/507)), opens no PR from research branches ([#576](https://github.com/mattpocock/skills/issues/576)), and resolves each ticket as the type its label names ([#625](https://github.com/mattpocock/skills/issues/625)). Thanks @jcwayne, @baob, @rynz and @sponge-b0b.

- [#1237](https://github.com/mattpocock/skills/pull/1237) [`49dd158`](https://github.com/mattpocock/skills/commit/49dd158d1076134a641b33efb035946536778336) Thanks [@mattpocock](https://github.com/mattpocock)! - `wizard` template fixes: `_existing` decodes a double-quoted `.env` value, so Enter-keeps-current no longer stores the quotes ([#1220](https://github.com/mattpocock/skills/issues/1220)); stages run inside `run_wizard`, so editing the script mid-run can't kill it ([#1142](https://github.com/mattpocock/skills/issues/1142)); `_clear` falls back to ANSI when `tput clear` fails ([#1081](https://github.com/mattpocock/skills/issues/1081)); `write_env` sets the shell variable too ([#1041](https://github.com/mattpocock/skills/issues/1041)); drop the unused `RED` ([#1003](https://github.com/mattpocock/skills/issues/1003)).

- [#1198](https://github.com/mattpocock/skills/pull/1198) [`868c4cf`](https://github.com/mattpocock/skills/commit/868c4cf20cb7e08bc805c388ff1f305dbedd261a) Thanks [@mattpocock](https://github.com/mattpocock)! - `wizard` template fixes: `ask` uses Readline so arrow keys move the cursor ([#741](https://github.com/mattpocock/skills/issues/741)); `write_env` single-quotes values so spaces, `#`, `$` and quotes survive `source` and dotenv ([#770](https://github.com/mattpocock/skills/issues/770)); `open_url` prints the open-it-yourself warning when no browser opener exists ([#774](https://github.com/mattpocock/skills/issues/774)); `write_env` writes through a symlinked `.env` and keeps an existing file's mode ([#811](https://github.com/mattpocock/skills/issues/811)); `ask` and `ask_secret` fail at EOF instead of looping ([#852](https://github.com/mattpocock/skills/issues/852)).

## 1.3.1

### Patch Changes

- [#1121](https://github.com/mattpocock/skills/pull/1121) [`c5b9869`](https://github.com/mattpocock/skills/commit/c5b98691982c4f0d3a5e40ab09566b3b84721e00) Thanks [@mattpocock](https://github.com/mattpocock)! - `ask-matt` no longer says `diagnosing-bugs` hands off to `improve-codebase-architecture` from a post-mortem; that step was removed. It now points you at `/retro` once the fix is in, to ask what would have prevented the bug, and at `/improve-codebase-architecture` where the finding is a missing seam. The `diagnosing-bugs` docs page drops the same stale hand-off. Thanks @Ygilany for spotting it ([#1117](https://github.com/mattpocock/skills/issues/1117)).

## 1.3.0

### Minor Changes

- [#1120](https://github.com/mattpocock/skills/pull/1120) [`2aecca1`](https://github.com/mattpocock/skills/commit/2aecca12ea9ff047f76c8178cb64dfeafd192abe) Thanks [@mattpocock](https://github.com/mattpocock)! - Graduate **`implement-spec`** into the **Engineering** bucket, so it ships in the Claude Code plugin, gets a docs page, and is routed by `ask-matt` as the parallel alternative to per-ticket `implement`.

  `implement-spec` (user-invoked) implements a whole spec in one run. It reads the tickets as a **task graph**, runs implementer subagents in their own worktrees across the ready **frontier**, and lands everything on one **integration branch**, closing out with `code-review`. Ahead of graduating:

  - The goal is now the integration branch, not a PR. A draft PR opens only when the issue tracker closes work through PRs or you ask for one, and only after the first merge (a branch with no commits ahead of main can't open one). Without a PR, the tickets are resolved the way the tracker closes work.
  - It points at the issue tracker like its siblings, telling you to run `/setup-matt-pocock-skills` when none has been provided, rather than silently defaulting to `gh`.
  - Each implementer confirms its worktree is based on the integration branch, builds its ticket with `tdd`, and merges the integration tip into its own branch before reporting done, so each merge is a fast-forward.

- [#1120](https://github.com/mattpocock/skills/pull/1120) [`2aecca1`](https://github.com/mattpocock/skills/commit/2aecca12ea9ff047f76c8178cb64dfeafd192abe) Thanks [@mattpocock](https://github.com/mattpocock)! - Graduate **`pr`** into the **Engineering** bucket, so it ships in the Claude Code plugin, gets a docs page, and is routed by `ask-matt` as the PR-body close-out.

  `pr` (model-invoked) is the shape a pull request body should take: a summary as the smallest visual that makes the change clear (pseudocode, a call tree, a file tree, Mermaid, a diff), before/after evidence that it works, and a merge-danger call (one-way or two-way door, plus blast radius). The Summary visuals are adapted from Dex Horthy's `show-me`, credited in the skill's `CREDITS.md`.

- [#1120](https://github.com/mattpocock/skills/pull/1120) [`2aecca1`](https://github.com/mattpocock/skills/commit/2aecca12ea9ff047f76c8178cb64dfeafd192abe) Thanks [@mattpocock](https://github.com/mattpocock)! - Graduate **`retro`** into the **Engineering** bucket, so it ships in the Claude Code plugin, gets a docs page, and is routed by `ask-matt` as the last step of the main flow, after `code-review`.

  `retro` (user-invoked) looks back at a coding session and suggests changes to the agent's environment rather than the code: navigation pointers, automated checks, coding standards, steering files, tool economy, information access. It classifies each coding-standards finding first: a mechanical violation gets a deterministic check (a linter rule, a pre-commit hook, or a CI job), and `CODING_STANDARDS.md` is kept for genuine judgement calls. A repo with no guardrail at all is a finding in its own right.

- [#1120](https://github.com/mattpocock/skills/pull/1120) [`daa01d8`](https://github.com/mattpocock/skills/commit/daa01d8aa68ad5c61b68970ec2018d0ce9567be6) Thanks [@mattpocock](https://github.com/mattpocock)! - Remove the **`resolving-merge-conflicts`** skill. It's no longer needed, and nothing replaces it: the agent works through an in-progress merge or rebase conflict without a dedicated skill. It leaves the Claude Code plugin, the README and the `ask-matt` router. Its docs page at `https://aihero.dev/skills-resolving-merge-conflicts` stays up, marked archived.

- [#1120](https://github.com/mattpocock/skills/pull/1120) [`006a52b`](https://github.com/mattpocock/skills/commit/006a52be23e0178375e083e30535fa8224471f3e) Thanks [@mattpocock](https://github.com/mattpocock)! - Rename the `CONTEXT.md`/`CONTEXT-MAP.md` domain-doc convention to `GLOSSARY.md`/`GLOSSARY-MAP.md` everywhere the skills read and write it (`domain-modeling`, `grill-with-docs`, `improve-codebase-architecture`, `setup-matt-pocock-skills`, `triage`, `tdd`, `diagnosing-bugs`, `ask-matt`, `codebase-design`, `wait-what`, `pr`), plus the docs pages and this repo's own root glossary.

  If you have an existing `CONTEXT.md` (or `CONTEXT-MAP.md`) from before this change, `git mv` it to the new name: the skills only look for `GLOSSARY.md`/`GLOSSARY-MAP.md` going forward.

### Patch Changes

- [#848](https://github.com/mattpocock/skills/pull/848) [`f02e2ed`](https://github.com/mattpocock/skills/commit/f02e2ed3624d031272f8547742d23bf6bca8b072) Thanks [@mattpocock](https://github.com/mattpocock)! - domain-modeling: trigger on discussing codebase terminology and on writing or editing a GLOSSARY.md or an ADR directly, replacing the narrower "pin down domain terminology or a ubiquitous language" / "record an architectural decision" phrasing. Also drops the "another skill needs to maintain the domain model" caveat, since that's the invoking skill's job to state explicitly, not this description's.

- [#911](https://github.com/mattpocock/skills/pull/911) [`4f28947`](https://github.com/mattpocock/skills/commit/4f289474bad013fe2be8f8769d733f59d9103d6b) Thanks [@mattpocock](https://github.com/mattpocock)! - Quote the `description` front matter in `to-spec`, `code-review`, `setup-matt-pocock-skills`, `writing-fragments`, `writing-shape`, and `wait-what`. An unquoted colon-space left over from the em-dash sweep in [#905](https://github.com/mattpocock/skills/issues/905) made each block invalid YAML, so `skills.sh` skipped all six during discovery and they couldn't be listed or installed via `npx skills`.

- [#917](https://github.com/mattpocock/skills/pull/917) [`85f83d3`](https://github.com/mattpocock/skills/commit/85f83d3fde1d3a90d5c9a657f6998c79a6c37308) Thanks [@mattpocock](https://github.com/mattpocock)! - grilling: update the round template so consecutive questions are separated by a horizontal rule (`---`) instead of running together.

- [#879](https://github.com/mattpocock/skills/pull/879) [`d419977`](https://github.com/mattpocock/skills/commit/d419977fe07d9e1607d3523f3579310bbb076b93) Thanks [@mattpocock](https://github.com/mattpocock)! - grilling: remove em-dashes from `SKILL.md`, replacing them with colons and semicolons so the instructions read as plain text.

- [#905](https://github.com/mattpocock/skills/pull/905) [`e6e9577`](https://github.com/mattpocock/skills/commit/e6e957797d8cceb5b351c0dc840369523f9fb8fb) Thanks [@mattpocock](https://github.com/mattpocock)! - Remove every em-dash from the repo's prose (docs, `SKILL.md` files, ADRs, `README.md`, scripts, JSON/YAML metadata), hand-rewriting each sentence with a comma, colon, period, parentheses, or conjunction rather than mechanically substituting the character. `CLAUDE.md`/`AGENTS.md` now says not to reintroduce them.

- [#878](https://github.com/mattpocock/skills/pull/878) [`e3e547b`](https://github.com/mattpocock/skills/commit/e3e547b57d549110a0aa6ff40fd7b871c01c76c9) Thanks [@mattpocock](https://github.com/mattpocock)! - Standardize cross-skill invocation on an explicit "call the Skill tool" instruction instead of bare `/skill`-style prose, across `code-review`, `diagnosing-bugs`, `grill-with-docs`, `grill-me`, `improve-codebase-architecture`, `tdd`, `to-spec`, `to-tickets`, `triage`, and `wayfinder`.

  - A skill that names another skill in prose ("run the `/grilling` skill") does not reliably cause it to load. This is the documented rough edge behind `grill-with-docs`'s most-reported problem. Naming the tool directly (`Call the Skill tool with "grilling"`) is intended to raise the hit rate. Dropping the leading `/` also makes the instruction harness-neutral rather than less: it no longer assumes Claude Code's trigger syntax.
  - A step needing more than one skill now says so as multiple calls ("Call the Skill tool twice, for `grilling` and `domain-modeling`"), not one call carrying two names.
  - Documents the convention in `.agents/invocation.md` for future skills to follow.

- [#880](https://github.com/mattpocock/skills/pull/880) [`1dab982`](https://github.com/mattpocock/skills/commit/1dab98299c3b81f560026c01b7ebf55ed5d91373) Thanks [@mattpocock](https://github.com/mattpocock)! - Stop skills from trying to reach user-invoked skills through the Skill tool: fix cross-skill references that violated the "no other skill can call it" invariant in `.agents/invocation.md`, in `to-spec`, `wayfinder`, `to-tickets`, `triage`, `code-review`, and `diagnosing-bugs`.

  - `to-spec`, `wayfinder`, `to-tickets`, `triage`, and `code-review` each carried a precondition ("...run `/setup-matt-pocock-skills` if not") that PR [#878](https://github.com/mattpocock/skills/issues/878) rewrote into a literal `Call the Skill tool with "setup-matt-pocock-skills"` instruction. `setup-matt-pocock-skills` is user-invoked, so none of these skills (user-invoked or model-invoked) can call it. Reworded all five as instructions for the agent to tell the human to run it instead.
  - `diagnosing-bugs`'s Phase 6 post-mortem hand off to `improve-codebase-architecture` (also user-invoked) the same way, from an autonomous, often-unattended bug-fixing flow with no human in the loop to catch the failed call. Removed the hand-off outright rather than softening it, since it rarely fired in practice. Phase 6 is now "Cleanup" only; the mechanical checklist is untouched.
  - Added a carve-out paragraph to `.agents/invocation.md`'s "Dependencies between them" section: the `Call the Skill tool with "name"` convention only applies when the named skill is model-invoked. This is the section PR [#878](https://github.com/mattpocock/skills/issues/878) introduced without reconciling it against the user-invoked/model-invoked invariant stated eight lines above it; the gap is most of why this bug reached six call sites instead of one.

  Fixes [#453](https://github.com/mattpocock/skills/issues/453).

- [#904](https://github.com/mattpocock/skills/pull/904) [`594f0f8`](https://github.com/mattpocock/skills/commit/594f0f83188921a60d45d63d6cdac509de20df2c) Thanks [@mattpocock](https://github.com/mattpocock)! - wait-what: follow `GLOSSARY-MAP.md` to the right `GLOSSARY.md` when a repo indexes multiple contexts that way instead of keeping a single root `GLOSSARY.md`.

## 1.2.3

### Patch Changes

- [#779](https://github.com/mattpocock/skills/pull/779) [`efce423`](https://github.com/mattpocock/skills/commit/efce423018fc6468a3239621f1c1bcaacc723801) Thanks [@mattpocock](https://github.com/mattpocock)! - Make `diagnosing-bugs` redact secrets.

  - Add a **Redact** section to `SKILL.md`. The skill has the agent show commands, outputs and captured artifacts; the section makes redaction the first move on each — write `<REDACTED>`, build loops against env vars so the credential stays in the environment, and quote only the signal-carrying lines of a captured artifact.
  - The Phase 1 completion criterion said "paste the invocation and its output". It now says show it redacted, and Phase 1 asks the user for a **redacted** captured artifact.
  - Note in `scripts/hitl-loop.template.sh` that `capture` prints its value back to the terminal, so it takes observations while signing in stays a `step`.

- [#781](https://github.com/mattpocock/skills/pull/781) [`14bfbbd`](https://github.com/mattpocock/skills/commit/14bfbbd8654a8d2910299e1a004c19c1979687d8) Thanks [@mattpocock](https://github.com/mattpocock)! - Drop Claude Code's tool and agent-type names from the subagent-dispatch instructions in `code-review`, `codebase-design`, and `improve-codebase-architecture`, so the step is followable on Codex and other harnesses.

- [#783](https://github.com/mattpocock/skills/pull/783) [`c0fd1e9`](https://github.com/mattpocock/skills/commit/c0fd1e973e040347d424e09934099f1bd6c2dee0) Thanks [@mattpocock](https://github.com/mattpocock)! - wizard: remove the time estimate. The template drops `TOTAL_MINUTES` and the time-remaining display, `stage` takes a name only, and progress is counted in stages.

## 1.2.2

### Patch Changes

- [#766](https://github.com/mattpocock/skills/pull/766) [`4aaccb5`](https://github.com/mattpocock/skills/commit/4aaccb58d40559d7e3c59a029b2290ae5ba538de) Thanks [@mattpocock](https://github.com/mattpocock)! - Make `writing-for-agents` model-invokable in Codex again.

  - Drop `policy.allow_implicit_invocation: false` from `agents/openai.yaml`. Codex filtered the skill out of the model-visible skills list, so its description could not trigger it — only an explicit `$writing-for-agents` mention worked.
  - Update the stale `interface.display_name` and `interface.short_description`, which still named the old `writing-great-skills` skill.
  - Move the skill from the **User-invoked** list to the **Model-invoked** list in `README.md` and `skills/productivity/README.md`.

## 1.2.0

### Minor Changes

- [#551](https://github.com/mattpocock/skills/pull/551) [`697d4ce`](https://github.com/mattpocock/skills/commit/697d4ce9742da558fd1ba6697c8e9775e2e302dd) Thanks [@mattpocock](https://github.com/mattpocock)! - Add Codex metadata alongside each skill's Claude Code frontmatter so the set works in both harnesses without generated copies.

  - Add an `agents/openai.yaml` beside every `SKILL.md` with Codex UI metadata (`interface.display_name`, `interface.short_description`).
  - Mark every user-invoked skill with `policy.allow_implicit_invocation: false`, the Codex analog of `disable-model-invocation: true`, so Codex excludes it from implicit invocation while explicit `$skill` invocation still works.
  - Document the dual-harness invocation model in `.agents/invocation.md`, `CLAUDE.md`, and the promoted-bucket READMEs.
  - Add `AGENTS.md` as a symlink to `CLAUDE.md` so Codex reads the same repo instructions.

- [#593](https://github.com/mattpocock/skills/pull/593) [`0f2bdbd`](https://github.com/mattpocock/skills/commit/0f2bdbdb06220d2df3718b8f0483157c6c8a8600) Thanks [@mattpocock](https://github.com/mattpocock)! - Graduate **`to-questionnaire`** out of `in-progress/` into the **Productivity** bucket, so it ships in the plugin. It turns a decision you can't answer alone into a Markdown questionnaire for the one person who can — filled in async, or worked through together in a meeting.

  Its defining move is that it grills you about the **send**, not the subject: a normal grilling session interrogates the topic, which is exactly what you can't answer here, so the interview asks only who the questionnaire is going to and what you need back, then aims every question at the gap between the two.

  Now wired as a promoted skill — plugin entry, top-level + Productivity READMEs under **User-invoked**, a docs page at `docs/productivity/to-questionnaire.md`, and a Standalone route in `ask-matt` framing it as the inverse of `/grill-me` (mine someone else, not yourself).

- [#680](https://github.com/mattpocock/skills/pull/680) [`b3376f8`](https://github.com/mattpocock/skills/commit/b3376f8d39848dd08572ec2667da4739a67c8c04) Thanks [@mattpocock](https://github.com/mattpocock)! - Graduate **`wizard`** out of `in-progress/` into the **Engineering** bucket, so it ships in the plugin — and make it model-invoked. It generates an interactive bash script that walks a human through a manual procedure — third-party setup, a one-off migration, an A→B state transition — opening each URL, saying what to click, capturing the values, and writing them into `.env` files and GitHub Actions secrets.

  The delightful UX is pre-solved by the bundled `template.sh` (progress with time-remaining, confirmation gates, cross-platform URL opening including WSL, hidden secret entry, idempotent `.env` upserts, `gh secret`/`gh variable` writes with graceful degradation, closing skip summary). Everything above the `STAGES` marker is a fixed library that's never hand-edited — the skill's job is only to scope the procedure and author its **stages**.

  Engineering rather than Productivity: it reads `.env*`, `docker-compose*`, framework config and every `secrets.*`/`vars.*` reference in `.github/workflows/` to scope itself, writes CI secrets, and verifies its output with `bash -n` and `shellcheck`.

  Because it is model-invoked, the agent can reach for it the moment it hits a step only a human can perform, instead of dumping numbered instructions into the chat and hoping you follow them. Typing `/wizard` works exactly as before — model-invocation only ever _adds_ the agent's reach. The description is written as the pointer that decides when it fires: what it produces, four trigger branches (provisioning infrastructure, setting up credentials or CI secrets, walking an unfamiliar third-party dashboard, a one-off migration or cutover), and an explicit non-trigger — don't invoke it for steps the agent can perform itself. Work an agent can do, an agent should do; the wizard is for the clicks, approvals and dashboard trips you would not hand to one. The stage-list confirmation before a line is written now doubles as the proposal when the agent fires it mid-build.

  Now wired as a promoted skill — plugin entry, top-level + Engineering READMEs under **Model-invoked**, a docs page at `docs/engineering/wizard.md`, and a Standalone route in `ask-matt` for the steps only a human can take. Model-invocation also puts it out of the reach of [#693](https://github.com/mattpocock/skills/issues/693), which drops user-invoked skills from the listing on Claude's desktop and web surfaces.

- [#763](https://github.com/mattpocock/skills/pull/763) [`77d207e`](https://github.com/mattpocock/skills/commit/77d207ef03219cc603e2832e1159cbdd1c91818e) Thanks [@mattpocock](https://github.com/mattpocock)! - Reshape the **`prototype`** skill around two ideas: the demo is **a single shareable HTML file**, and the prototype is **a primary source**.

  The logic branch now produces one self-contained file (plain HTML/CSS/JS, no build, no server) instead of a terminal app — a non-developer can open it by double-click and drive it in their own domain language: a labelled state panel, always-available free-play buttons, and a set of tabbed **guided walkthroughs**, each a scenario with the ordered buttons to press underneath it. The portable pure-logic module still lifts into the real code; the HTML shell is the throwaway.

  Throwaway no longer means deleted. Rather than being removed once it has answered its question, the prototype is captured as runnable evidence on a throwaway branch (`prototype/<name>`) out of main, with a context pointer to it left on the implementation issue — so the main branch keeps only the validated decision while the exploration stays findable. The answer (verdict + question) is still captured durably in an issue/ADR/commit.

- [#536](https://github.com/mattpocock/skills/pull/536) [`42a5b70`](https://github.com/mattpocock/skills/commit/42a5b70fcacc7baff1977b13f3919fb2f63af14e) Thanks [@mattpocock](https://github.com/mattpocock)! - Ship the skill set as a native **Claude Code plugin**, listed in Claude Code's official marketplace. You can now subscribe to the promoted skills as a managed, read-only bundle instead of copying editable files:

  ```bash
  claude plugins install mattpocock-skills
  ```

  Or, from inside a session:

  ```
  /plugin install mattpocock-skills
  ```

  There is no marketplace to add first — the official marketplace is configured by default.

  `.claude-plugin/plugin.json` carries the full plugin metadata (version, description, author, license, keywords) and the explicit list of promoted skills. `skills.sh` remains the universal installer (and the path for Codex and other harnesses today); a native Codex plugin is deferred — see `.agents/adr/0002-ship-as-a-claude-code-plugin.md` for why.

- [#751](https://github.com/mattpocock/skills/pull/751) [`355fa74`](https://github.com/mattpocock/skills/commit/355fa7420b418af838998f7ec4365ceda1c8dfcc) Thanks [@mattpocock](https://github.com/mattpocock)! - Add **`wait-what`** — a one-word corrective for model verbosity. Type it the moment a message doesn't land, and the agent re-pitches it: a little context, ASD-STE100 Simplified Technical English, and the ubiquitous language from your `CONTEXT.md`. User-invoked, three lines long.

  The mechanism is the name. Concision skills fail by growing — a 400-line skill still leaves the model verbose — so this one is a single precise leading word and nothing else. Names that describe the _output_ (`/tldr`, `/no-fluff`) make the model clip words and lose you further; naming the _listener's_ state asks for both halves at once, fewer words **and** the context you were missing. It also reuses the leading words already in your global `CLAUDE.md`, so the skill, `CLAUDE.md` and every `CONTEXT.md` reach for the same tokens.

  It repairs one message; it doesn't prevent the next one. The cure for jargon is a shared language built upfront with `/grill-with-docs`; this is what you reach for when you don't have one yet.

- [#763](https://github.com/mattpocock/skills/pull/763) [`77d207e`](https://github.com/mattpocock/skills/commit/77d207ef03219cc603e2832e1159cbdd1c91818e) Thanks [@mattpocock](https://github.com/mattpocock)! - Name the `/wayfinder` unit a **decision ticket**, and burn research tickets down with subagents.

  People kept reading a wayfinder ticket as an ordinary _implementation_ ticket — a slice of a build to execute — when wayfinder uses them as **decision tickets**: questions whose resolution is a decision. The skill description and its opening line now introduce the term (and say what makes it one), with the `ask-matt` / engineering README blurbs and the docs page matching — while "ticket" stays the everyday word once the term is established. `CONTEXT.md` records **Decision ticket** as a domain term, so the "avoid: ticket" guidance no longer contradicts wayfinder's deliberate use of the word.

  Research tickets are no longer parked for a separately-launched session. Research stays a real ticket type — it's a genuine shared blocker that downstream decisions hang on, and that dependency is exactly what the frontier's blocking edges exist to render. What changes is how it's resolved: because research is AFK, charting doesn't stop and read it. After creating the tickets, the charting session fires a `/research` subagent for each research ticket to burn it down in parallel, capturing the findings on a throwaway `research/<name>` branch with a context pointer. Research tickets are the one exception to _one ticket per session_.

- [#763](https://github.com/mattpocock/skills/pull/763) [`77d207e`](https://github.com/mattpocock/skills/commit/77d207ef03219cc603e2832e1159cbdd1c91818e) Thanks [@mattpocock](https://github.com/mattpocock)! - **Breaking:** rename **`writing-great-skills`** → **`writing-for-agents`**, restructure it, and add a new leading word.

  The reference now covers any document an agent consumes — skills, `AGENTS.md` / `CLAUDE.md`, docs reached by a pointer — not just skills. `GLOSSARY.md` is merged into `SKILL.md` (one authoritative treatment per term; the `_Avoid_` synonym lists and the standalone Predictability definition are gone); the skill-only mechanics (frontmatter, model- vs user-invoked, router skills, the invocation cut of splitting) are disclosed to a new `SKILL-MECHANICS.md`. The skill is now **model-invoked**: it fires when creating or editing skills or modifying `AGENTS.md`/`CLAUDE.md`. `ask-matt`'s pointer updated. Reinstall under the new name; the old name is gone (no alias).

  The pruning section gains **cache**. Single source of truth now reaches past the document into the environment — `package.json` scripts, config files, directory layout, `--help` output are themselves authoritative, so a doc that restates them is a cache of a lookup, earning its load only when the lookup is expensive. The positive target: cache what the agent cannot find by looking (unwritten conventions, the reason behind a choice, gotchas no config confesses), and leave one-file, one-command lookups to the environment, where they cannot go stale.

- [#533](https://github.com/mattpocock/skills/pull/533) [`45afd80`](https://github.com/mattpocock/skills/commit/45afd8074a8b7de5fe073845d080fa9dd6c429fa) Thanks [@mattpocock](https://github.com/mattpocock)! - Add a YAGNI scoping filter to the **`improve-codebase-architecture`** skill's Explore step. Instead of scanning the whole repo evenly, it now scopes to where change is actually landing: if you name a direction it takes it, otherwise it reads the last ~20 commit messages to bias exploration toward actively-developed paths. A deepening opportunity in code nobody touches is a refactor you'll never cash in — the leverage only pays off where you keep editing — so the report stops tidying dormant corners of the repo.

### Patch Changes

- [#763](https://github.com/mattpocock/skills/pull/763) [`77d207e`](https://github.com/mattpocock/skills/commit/77d207ef03219cc603e2832e1159cbdd1c91818e) Thanks [@mattpocock](https://github.com/mattpocock)! - Sharpen `/ask-matt` — the router now covers phase boundaries, the two wayfinder mistakes, and two skills it never mentioned.

  **Phase boundaries.** A **phase** is a chunk of work inside a session — the grilling, the implementation, the QA — and the boundary between two of them is where you decide what to do with the context you've built. The two-bullet `Crossing sessions` section is replaced by a decision tree carrying all five options in order (**continue**, `/clear`, `/handoff`, **subagent**, `/compact`), with the reasoning disclosed in a new `PHASE-BOUNDARIES.md`. Three fixes come with it:

  - **`/handoff` was oversold.** It read as the general bridge between context windows. It's narrow: you need it only when something has to _travel_ — a new harness, a new directory, a colleague, or a side task forked mid-phase. What it buys is portability.
  - **`/compact` is the default, not the first reach.** It sits at the bottom of the tree, after the four cheaper or more precise questions above it. Starting there produces a session that's confidently wrong about whatever the summary flattened.
  - **Two branches were missing entirely.** **Continue** is the one to rule out first — it's the only move that keeps the conversation as a primary source rather than a summary of one — and a **subagent** handles anything scoped tightly enough to run AFK.

  Context hygiene's escape hatch now says `/compact` rather than `/handoff` (same harness, same directory, at a boundary — the handoff clause doesn't apply), and the smart zone figure is updated from ~120k to ~150k tokens.

  **Wayfinder routing.** The two mistakes people most often make with the heaviest, most cognitively demanding flow:

  - **Over-reaching for it.** It's slower and denser than a single grill, so it's flagged as the heaviest flow and reserved for the idea that genuinely won't fit one session — a well-scoped feature belongs on `/grill-with-docs`, not here.
  - **Losing the way at the handoff.** When the map clears, wayfinder hands off, it doesn't build: merge onto the main flow at `/to-spec` (which collapses the map's linked decisions into a buildable plan) rather than looping the map straight into `/implement`. Straight-to-`/implement` is only for efforts that turned out genuinely small.

  **Missing routes.** `/grilling` and `/resolving-merge-conflicts` were absent from the router altogether and are now in it, and `grill-me` splits from `grill-with-docs` on whether you are in a working directory.

- [#502](https://github.com/mattpocock/skills/pull/502) [`44eed54`](https://github.com/mattpocock/skills/commit/44eed545186ffd0263e8004867750b80cfddd215) Thanks [@mattpocock](https://github.com/mattpocock)! - Make `/setup-matt-pocock-skills` friendlier and align the local-markdown tracker with the current spec.

  - **Triage labels** are now asked about only when the `triage` skill is installed, and then as a single recommended-yes question ("keep the default triage labels?") instead of an override interrogation. When `triage` isn't installed, the section — and `docs/agents/triage-labels.md` — are skipped.
  - **External PRs as a request surface** is no longer a setup question. The GitHub/GitLab templates still carry the flag, defaulted off; a user can flip it in `docs/agents/issue-tracker.md` later.
  - **Domain docs** default to single-context without asking; multi-context is only offered when the repo shows monorepo signals.
  - **Local-markdown tickets** are now one file per ticket under `.scratch/<feature>/issues/<NN>-<slug>.md` — never a single combined `tickets.md`. `/to-tickets` and the local issue-tracker template now agree, and the spec file is `spec.md` (not `PRD.md`) to match `/to-spec`.

  Docs pages for `setup-matt-pocock-skills` and `to-tickets` re-synced.

- [#532](https://github.com/mattpocock/skills/pull/532) [`170ad48`](https://github.com/mattpocock/skills/commit/170ad48655825783d0193e850e31a9aac957bb95) Thanks [@mattpocock](https://github.com/mattpocock)! - Reword **`grilling`** for general use. Its description and body no longer scope the interview to a software plan: "this plan" → "this", "enact the plan" → "act on it", and "exploring the codebase" → "exploring the environment". The technique is unchanged; it now reads as a stress-test of any plan, decision, or idea.

- [#593](https://github.com/mattpocock/skills/pull/593) [`a4b2009`](https://github.com/mattpocock/skills/commit/a4b2009a1a3ac9575506c10b4c84f08f9bba7a38) Thanks [@mattpocock](https://github.com/mattpocock)! - Rework **`grilling`** from one-question-at-a-time to round-by-round. It now maps the decision tree and asks the whole **frontier** — every question whose prerequisites are already settled — in a single numbered round, then recomputes the frontier from the user's answers and asks the next round. Same 13 questions land in ~3 rounds instead of 13. Facts the environment can answer are dispatched to background sub-agents so research never blocks the round: only questions downstream of a running exploration wait for it. The session ends when the frontier is empty.

  Every question in a round is emitted in one fixed shape — `❓ **Q1** - **<title>**`, then the body (prose or multiple choices), then the recommendation on its own `➡️` line. A round reads as a scannable numbered list with each recommendation visually separated from the question, so you can answer by number instead of quoting questions back.

  `grill-me`, `grill-with-docs` and `triage` run the frontier a round at a time as well — `triage`'s grill step and `grilling`'s Codex `short_description` now say so instead of describing the old rhythm. The opt-out for one-question-at-a-time (a line in your global `CLAUDE.md`) is unchanged.

- [#752](https://github.com/mattpocock/skills/pull/752) [`c66bdee`](https://github.com/mattpocock/skills/commit/c66bdeeee002d81e3f8b21403c07f9a0d7bea6da) Thanks [@mattpocock](https://github.com/mattpocock)! - Remove six skills from the repo. None of them was in the Claude Code plugin, but all six were installable through [skills.sh](https://skills.sh/mattpocock/skills), which serves every skill in the repo — so this is what leaves that listing, and where each one went.

  Four retired skills, each already absorbed by a skill that does the job better:

  - **`ubiquitous-language`** → **`/domain-modeling`**, which builds and maintains the whole domain model rather than dumping a glossary from one conversation.
  - **`design-an-interface`** → **`/codebase-design`**. Nothing is lost: the "design it twice" technique — parallel sub-agents generating radically different designs, from Ousterhout — ships inside that skill as `DESIGN-IT-TWICE.md`.
  - **`qa`** → **`/triage`** and **`/to-tickets`**.
  - **`request-refactor-plan`** → **`/to-spec`** and **`/improve-codebase-architecture`**.

  And two that were only ever mine — tied to my own machine and never meant for anyone else. The `personal/` bucket goes with them:

  - **`edit-article`**
  - **`obsidian-vault`**, which hardcoded a path to my own Obsidian vault.

  `skills/deprecated/` stays as a bucket, now empty. `skills/in-progress/` is unchanged and is now described for what it actually is: a beta channel, published on purpose, installable one skill at a time through skills.sh.

- [#734](https://github.com/mattpocock/skills/pull/734) [`a2f9333`](https://github.com/mattpocock/skills/commit/a2f9333669ff53db762c87ecda5a15442060a3be) Thanks [@mattpocock](https://github.com/mattpocock)! - Finish the `to-prd` → `to-spec` rename: "spec" is now the only term in the shipped text.

  - **`to-spec`** no longer opens with "you may know this document as a PRD" — the parenthetical is dropped from the skill and its docs page. The local-markdown tracker template drops the same hedge.
  - **`code-review`** talks about the originating issue/spec rather than issue/PRD, in its frontmatter description, its two-axis summary, and the spec-source search order. Both READMEs re-synced.
  - **The GitHub and GitLab tracker templates** now say "Issues and specs for this repo live as GitHub/GitLab issues" — they had been left on "PRDs" when the local template was updated, so the stale term propagated into every repo they were written into.
  - **`docs/engineering/research.md`** pointed at `https://aihero.dev/skills-to-prd`, a dead slug for the renamed skill; it now links `to-spec` like the other nineteen docs pages do.

  The CHANGELOG and existing changesets still name PRDs where they document the rename itself, which is correct.

## 1.1.0

### Minor Changes

- [#406](https://github.com/mattpocock/skills/pull/406) [`930a450`](https://github.com/mattpocock/skills/commit/930a450089f77a49af09001d955db8452a4b867d) Thanks [@mattpocock](https://github.com/mattpocock)! - Bring the **`ask-matt`** router up to date with the full skill set. It now maps five skills it was missing: **`tdd`** (woven into the main flow as the red-green engine `implement` drives), **`diagnosing-bugs`** (a new "Something's broken" on-ramp — there was previously no route for a bug), **`domain-modeling`** and **`codebase-design`** (a new "Vocabulary underneath" section), and **`grilling`** (the shared interview primitive). `prototype` is fleshed out as a standalone and the description broadens from "user-invoked skills" to "the skills". A maintenance rule is added to `CLAUDE.md` so any future skill add/rename/remove or flow change triggers an `ask-matt` re-check, beside the existing docs-page re-sync rule.

- [#464](https://github.com/mattpocock/skills/pull/464) [`639df6e`](https://github.com/mattpocock/skills/commit/639df6e7386dfddc739b2aecdeff37a876f2483b) Thanks [@mattpocock](https://github.com/mattpocock)! - Promote and harden **`code-review`**. The in-progress **`review`** skill is renamed to **`code-review`** and moved from `in-progress/` into `engineering/`: it now ships in the plugin, is listed in the top-level and Engineering READMEs (Model-invoked), and has a docs page at `docs/engineering/code-review.md`. The `/implement` skill and docs point at `/code-review`.

  It also gains an always-on **Fowler smell baseline** on its Standards axis — a curated ~12 high-signal "Bad Smells in Code" (Mysterious Name, Duplicated Code, Feature Envy, Data Clumps, Primitive Obsession, Repeated Switches, Shotgun Surgery, Divergent Change, Speculative Generality, Message Chains, Middle Man, Refused Bequest) inlined into `SKILL.md` as a fixed baseline alongside whatever the repo documents, not a new third axis. Two binding rules keep it safe: a documented repo standard overrides the baseline, and every smell is reported as a judgement call, never a hard violation.

- [#464](https://github.com/mattpocock/skills/pull/464) [`639df6e`](https://github.com/mattpocock/skills/commit/639df6e7386dfddc739b2aecdeff37a876f2483b) Thanks [@mattpocock](https://github.com/mattpocock)! - Sharpen **`grilling`** on two fronts.

  **A confirmation gate.** The agent won't enact the plan until you confirm the shared understanding has been reached — turning the skill's existing "shared understanding" completion criterion into an explicit stop-gate. The `description` also recruits the pretrained **`grill`** leading word ("Grill the user relentlessly") to sharpen invocation, and the docs page is re-synced.

  **Facts vs. decisions.** Grilling now splits _facts_ (look them up — explore the codebase) from _decisions_ (put each one to the human and wait for their answer). The old blanket line — "if a question can be answered by exploring the codebase, explore the codebase instead" — was written for the live-human case, but once another skill runs grilling inside a resolve-the-ticket frame it read as license to answer _decisions_ autonomously too. Separating the two keeps a grilling agent from racing ahead and answering its own questions.

- [#463](https://github.com/mattpocock/skills/pull/463) [`af6d692`](https://github.com/mattpocock/skills/commit/af6d6922c3e2b5288eef155346cbe319e4ed3bd0) Thanks [@mattpocock](https://github.com/mattpocock)! - Add two adjacent Steering failure modes to **`writing-great-skills`**, both about how language you think of as "off" still steers the agent. **Negation** — the _elephant_ — is steering by prohibition: naming what _not_ to do drags the forbidden behaviour into context and makes it _more_ available, not less (_don't think of an elephant_), so the cure is to prompt the **positive**. **Negative Space** — the void — is blindness to the steering done by what you leave _out_: every decision a skill declines is delegated to the agent's priors rather than left neutral, so the cure is to read a draft for its silences and decide each omission deliberately (fill it, or leave it open as a real **branch**). Kept as two entries, not one — they carry different diagnostics and different cures — each a full `GLOSSARY.md` entry plus a `SKILL.md` failure-mode bullet, matching how every other failure mode is carried.

- [`850873c`](https://github.com/mattpocock/skills/commit/850873cd73d5f81826ebf512ad35d2b1e113001f) Thanks [@mattpocock](https://github.com/mattpocock)! - Make the **`prototype`** skill model-invoked, so the agent can reach for it autonomously (and other skills can too). Its description is rewritten around the leading word _prototype_ — throwaway code that answers a design question — with one trigger per branch (state/logic sanity-check, or UI exploration).

- [#409](https://github.com/mattpocock/skills/pull/409) [`0d74d01`](https://github.com/mattpocock/skills/commit/0d74d01cbc64ca27778a49b38599f70c534e76a0) Thanks [@mattpocock](https://github.com/mattpocock)! - Add the **`research`** skill — a small, model-invoked skill that spins up a **background agent** to investigate a question against **primary sources** (official docs, source code, specs, first-party APIs), then leaves a single cited Markdown file wherever the repo keeps such notes. It's delegable reading legwork: you keep working while it reads, and get back a document to grill, plan, or design against. Listed in the top-level and Engineering READMEs (Model-invoked), added to `.claude-plugin/plugin.json`, given a docs page at `docs/engineering/research.md`, and routed as a Standalone in `ask-matt`.

- [#469](https://github.com/mattpocock/skills/pull/469) [`a0329ba`](https://github.com/mattpocock/skills/commit/a0329ba95751f58566ed7ab484475917a68f1629) Thanks [@mattpocock](https://github.com/mattpocock)! - Split the **`to-issues`** skill into a lean **Process** and a **Reference** section, and teach it to handle a **wide refactor** — a single mechanical change (like renaming a column) whose **blast radius** fans across the whole codebase, breaking thousands of call sites at once so no vertical slice can land green. The drafting step now points at two co-located reference blocks: the **Vertical slice rules** for ordinary tracer bullets, and **Wide refactors**, which slices the change by **expand–contract** (expand the new form beside the old, migrate call sites in batches sized by blast radius, then contract the old form away) so CI stays green batch to batch — or, when it can't, only at a final integrate-and-verify issue. The issue body template moves into Reference too.

- [#464](https://github.com/mattpocock/skills/pull/464) [`386d4ff`](https://github.com/mattpocock/skills/commit/386d4ff719a7c420ad1454232d0436b01f1b8c17) Thanks [@mattpocock](https://github.com/mattpocock)! - Unify the planning skills. **`to-prd` is renamed to `to-spec`** — "spec" is now the single through-line term (it still opens with "you may know this document as a PRD" for discoverability). **`to-plan` and `to-issues` are merged into one `to-tickets` skill, and `to-issues` is deleted.**

  `to-tickets` breaks a plan, spec, or conversation into a set of **tickets** — tracer-bullet vertical slices, each declaring its **blocking edges**. That one artifact reads two ways depending on the tracker `/setup-matt-pocock-skills` configured: a **local file** (`tickets.md`) writes the edges as text and you work it top-to-bottom by hand; a **real tracker** writes them as native blocking links, so any ticket whose blockers are done is on the frontier and several agents can run at once. The edges live in the ticket either way — the medium only decides whether anything acts on them in parallel.

  Publishing prefers the tracker's **native sub-issues** for parent → slice and **native blocking edges** for `Blocked by` where the tracker supports them, keeping the `## Parent` / `## Blocked by` body sections as the fallback. The "What to build" template points at where a `/prototype`'s code lives rather than inlining a snippet from it.

  `ask-matt`'s main flow now routes `idea → /to-spec → /to-tickets → /implement`, and there are human-facing docs pages at `docs/engineering/to-spec.md` and `docs/engineering/to-tickets.md`.

- [#464](https://github.com/mattpocock/skills/pull/464) [`0557d57`](https://github.com/mattpocock/skills/commit/0557d57579d9b3d39839fdaf8d4a6542b17539ce) Thanks [@mattpocock](https://github.com/mattpocock)! - Settle wayfinder's place in the docs as a **situational on-ramp**, not the new main entry flow — the grill-led _idea → ship_ chain stays the front door (crowning wayfinder as the default spine is a v2-sized move, not a 1.1). The **`ask-matt`** router now names wayfinder's concrete triggers — a greenfield project or a huge feature build, too big for one session — and the two grill front doors (**`grill-me`**, **`grill-with-docs`**) signpost _up_ to wayfinder for the effort that's too big to hold in one session, so the on-ramp is discoverable from where a reader actually starts.

- [#464](https://github.com/mattpocock/skills/pull/464) [`639df6e`](https://github.com/mattpocock/skills/commit/639df6e7386dfddc739b2aecdeff37a876f2483b) Thanks [@mattpocock](https://github.com/mattpocock)! - Graduate and reframe **`wayfinder`** — the skill for planning a huge chunk of work, more than one agent session can hold. It moves out of `in-progress/` into `engineering/` (plugin entry, top-level + Engineering READMEs under **User-invoked**, a docs page at `docs/engineering/wayfinder.md`, and a route in `ask-matt`), landing as a mature skill. The rename and reframe that got it there:

  - **`decision-mapping` is renamed to `wayfinder`**, invoked as `/wayfinder`. "Decision map" was jargony and inaccurate — only one ticket type is actually a decision. The reframe charts a route through a foggy problem instead, giving one coherent leading-word frame — **fog of war**, **frontier**, **the map** — rather than an invented term layered on top.
  - **Destination as the leading word.** Wayfinding finds the _way_ to a destination; it doesn't charge at building it. Naming the destination is the first act of charting — it fixes the scope and shapes every ticket — so the map gains a `## Destination` field every session orients to, and triage pins it before any ticket exists.
  - **Plan, don't do.** The map produces **decisions, not deliverables**; it's done when nothing is left to decide before someone builds the thing. An effort can override this in its Notes.
  - **The map is an index, not a store.** A decision lives in exactly one place — its ticket — so the map only gists and links, never restates; graduating fog into a ticket clears the graduated patch so nothing lingers in two places.
  - **Collaborative by default.** The map moves off a local Markdown file onto the repo's issue tracker: a single `wayfinder:map` issue whose tickets are its child issues — one shared URL the team can watch. Sessions load the map at low resolution and zoom into tickets on demand. Wayfinder stays tracker-agnostic (GitHub, GitLab, local-markdown) behind a pointer in `docs/agents/issue-tracker.md`, and `setup-matt-pocock-skills` seeds the "Wayfinding operations" section.
  - **Claim by assignment, not a label.** A session claims a ticket by assigning it to the driving dev — the assignee _is_ the claim — freeing the label vocabulary to `wayfinder:<type>` alone.
  - **Native blocking.** Blocking prefers the tracker's native dependency relationship, which renders the frontier visually in the tracker's own UI so the human sees what's takeable without opening the map. GitHub and GitLab templates spell out the native recipe, with a body-convention fallback.
  - **Fog vs. out of scope, split.** Two plainly-named map sections — `## Not yet specified` (in-scope fog that graduates as the frontier advances) and `## Out of scope` (work ruled beyond the destination, closed, never graduating) — so beyond-destination work no longer reads as takeable frontier.
  - **A fourth `task` ticket type.** For literal manual work that blocks a decision (provisioning access, moving data, signing up for a service) — the one type that _does_ rather than decides, earning its place by unblocking a decision.
  - **HITL / AFK ticket classification.** Every ticket type is **HITL** (human in the loop — grilling, prototype) or **AFK** (agent alone — research; task is either). A HITL ticket only resolves through the live exchange, so "wait for the human" falls out of the label — a grilling agent that answers its own questions has, by definition, broken HITL. (This fixes students' reports of `/wayfinder` grilling _itself_ instead of the human.)
  - **No-fog early exit restored.** If the opening breadth-first grilling surfaces no fog, the journey is small enough for one session — so it stops and asks how you'd like to proceed rather than building a map nobody needs.

### Patch Changes

- [#464](https://github.com/mattpocock/skills/pull/464) [`639df6e`](https://github.com/mattpocock/skills/commit/639df6e7386dfddc739b2aecdeff37a876f2483b) Thanks [@mattpocock](https://github.com/mattpocock)! - Reshape **`tdd`** into a reference-only skill and add a missing anti-pattern.

  **Reference-only.** The red → green → refactor loop is anchored by leading words the model already holds, so the step-by-step Workflow was largely restating the loop. Dropped the Workflow and per-cycle checklist; folded their one durable idea — vertical slices / tracer bullets — into the Anti-patterns section and a short Rules-of-the-loop list. Introduced **seam** as the leading word for where tests go: test only at pre-agreed seams, confirmed with the user before any test is written. Also dropped the refactor stage — TDD is now red → green; refactoring belongs to the review stage, so the refactor rule and `refactoring.md` moved out (its home is `code-review`).

  **Tautological tests.** Added the tautological-test anti-pattern: a test whose assertion is recomputed the way the code computes it passes by construction and gives zero confidence — distinct from the implementation-coupling anti-pattern already covered. Added as a peer at the same sites: a Philosophy principle (expected values must come from an independent source of truth), a checklist gate, and a BAD/GOOD example pair in `tests.md`.

- [`e00eadb`](https://github.com/mattpocock/skills/commit/e00eadb4bb32c3d5a631ead1a5ed5d6a7c5f74e2) Thanks [@mattpocock](https://github.com/mattpocock)! - Extend the **`triage`** skill to triage external pull requests, treating a PR as an issue with attached code that runs through the same roles and state machine. PRs flow inline alongside issues (gated by a per-repo setup toggle), discovery surfaces only external PRs, the bug-only "reproduce" step is generalized into a single "verify the claim" step, and a redundancy check resolves already-implemented requests to `wontfix` without polluting the out-of-scope knowledge base. `setup-matt-pocock-skills` gains the PRs-as-a-request-surface toggle for GitHub/GitLab.

- [#472](https://github.com/mattpocock/skills/pull/472) [`d869d45`](https://github.com/mattpocock/skills/commit/d869d45afc32beab1c2d1350f8de5e81589512cd) Thanks [@mattpocock](https://github.com/mattpocock)! - Fix **`wayfinder`** hardcoding the issue-tracker doc path, which broke the indirection the rest of the suite relies on.

  `to-issues`, `to-prd`, and `triage` never name a path — they resolve the tracker through the `### Issue tracker` block that `setup-matt-pocock-skills` writes into `CLAUDE.md` / `AGENTS.md`, which points at the tracker doc wherever it lives. Wayfinder instead pinned the literal `docs/agents/issue-tracker.md`, so in a repo that keeps its agent docs elsewhere it silently fell back to the local-markdown tracker — even one whose `CLAUDE.md` clearly declares GitHub issues. It now resolves the doc via that same pointer and reads its "Wayfinding operations" section by name, keeping the indirection consistent across the suite.

## 1.0.1

### Patch Changes

- [`d20ee26`](https://github.com/mattpocock/skills/commit/d20ee2684e2a9442698ac3c1e0f2c5b68c4cf296) Thanks [@mattpocock](https://github.com/mattpocock)! - Make the **`teach`** skill reuse-first. Lessons are now built from reusable **components** in `./assets/` — stylesheets, quiz widgets, simulators, diagram helpers. Reuse is the default: the agent reads `./assets/` before authoring a lesson, builds from what's there, and extracts anything new and reusable into a component rather than inlining it.

## 1.0.0

### Major Changes

- [`47bde84`](https://github.com/mattpocock/skills/commit/47bde84da032afb2e5058f997f3bbca47d321dbd) Thanks [@mattpocock](https://github.com/mattpocock)! - Add the **`ask-matt`** skill — a user-invoked router that points you at the right skill or flow for your situation.

  **Breaking:** `ask-matt` routes over the other user-invoked skills in this repo, so it expects them to be installed.

- [`47bde84`](https://github.com/mattpocock/skills/commit/47bde84da032afb2e5058f997f3bbca47d321dbd) Thanks [@mattpocock](https://github.com/mattpocock)! - Add the shared design skills and rewire existing skills onto them.

  - New **`codebase-design`** skill — the deep-module vocabulary (module, interface, depth, seam, adapter) and the principles for putting a lot of behaviour behind a small interface. The language that previously lived in `improve-codebase-architecture/LANGUAGE.md` now lives here, generalized for reuse across skills.
  - New **`domain-modeling`** skill — actively build and sharpen a project's domain model, stress-testing terms against the glossary and keeping `CONTEXT.md` and ADRs current.
  - `improve-codebase-architecture` now draws its architecture vocabulary from `/codebase-design` and its domain model from `/domain-modeling`.
  - `tdd` now leans on `/codebase-design` for interface-design guidance — its inline `deep-modules.md` / `interface-design.md` notes were removed in favour of the shared skill.
  - `grill-with-docs` now builds the domain model inline via `/domain-modeling`.

  **Breaking:** these skills now depend on the new `codebase-design` / `domain-modeling` skills, so you must install them too.

- [`47bde84`](https://github.com/mattpocock/skills/commit/47bde84da032afb2e5058f997f3bbca47d321dbd) Thanks [@mattpocock](https://github.com/mattpocock)! - Remove the **`caveman`** and **`zoom-out`** skills.

  - `caveman` was a duplicate of another skill I was testing and was never meant to be public.
  - `zoom-out` went unused in practice, so it's been removed from the repo.

  **Breaking:** both skills have been removed.

- [`47bde84`](https://github.com/mattpocock/skills/commit/47bde84da032afb2e5058f997f3bbca47d321dbd) Thanks [@mattpocock](https://github.com/mattpocock)! - Rename the **`diagnose`** skill to **`diagnosing-bugs`**.

  **Breaking:** invoke it as `/diagnosing-bugs` — the old `/diagnose` name no longer exists.

- [`47bde84`](https://github.com/mattpocock/skills/commit/47bde84da032afb2e5058f997f3bbca47d321dbd) Thanks [@mattpocock](https://github.com/mattpocock)! - Replace **`write-a-skill`** with **`writing-great-skills`**.

  - Removed `write-a-skill`.
  - Added `writing-great-skills` (plus its `GLOSSARY.md`) — a reference for writing and editing skills well: the vocabulary and principles that make a skill predictable, hunting no-ops down to the sentence level.
  - Exposed `grilling` as a model-invoked skill — the reusable interview loop behind `grill-me` and `grill-with-docs`.

  **Breaking:** `write-a-skill` has been removed; use `writing-great-skills` instead.

### Minor Changes

- [`47bde84`](https://github.com/mattpocock/skills/commit/47bde84da032afb2e5058f997f3bbca47d321dbd) Thanks [@mattpocock](https://github.com/mattpocock)! - Add the **`resolving-merge-conflicts`** skill — a loop for resolving an in-progress git merge or rebase conflict. Standalone, with no dependencies on other skills.

- [`47bde84`](https://github.com/mattpocock/skills/commit/47bde84da032afb2e5058f997f3bbca47d321dbd) Thanks [@mattpocock](https://github.com/mattpocock)! - Rename the skill taxonomy from **Commands / Skills** to **User-invoked / Model-invoked** across the docs, and add `docs/invocation.md` defining the split: user-invoked skills are reachable only when you type them and exist to orchestrate; model-invoked skills can also be reached automatically when the task fits. A user-invoked skill may invoke model-invoked skills, but never another user-invoked one.

### Patch Changes

- [`47bde84`](https://github.com/mattpocock/skills/commit/47bde84da032afb2e5058f997f3bbca47d321dbd) Thanks [@mattpocock](https://github.com/mattpocock)! - Tighten the **`review`** skill: fail-fast ref check, single-sourced rules, and no-op cuts.
