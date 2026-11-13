---
name: decomp-setup
description: Agree a byte-for-byte decomp contract and set up its private project, or upgrade an existing one. Does no decomp.
disable-model-invocation: true
argument-hint: "Path to the target binary, or to an existing decomp project"
---

Set up a decomp project, or bring an existing one up to date. A project is a private repo, a **contract** every later agent can work from without asking a question, and the tooling that enforces it. This skill reconstructs nothing.

Call the Skill tool with `decomp-standards` first: its goal, guardrails, and layout are what this setup serves.

Then take one branch:

- **New project** (the user gives a target binary, and no decomp project holds it yet): steps 1 to 7. It ends when the pipeline check passes and the `decomp-setup` tag is set; then tell the user to run `/decomp-start`.
- **Existing project** (the folder holds `DECOMP.md` and `tools/decomp.py`): go to [Skill upgrade](#skill-upgrade). Steps 1 to 7 are not run again.

## 1. Project

- Get the target binary's path. Hash it (SHA-256) and note its size.
- Agree the project folder with the user (default: a sibling of the current project, `<target>-decomp`). Create it as a new git repo with `main` as the integration branch and no remote until the user names a **private** one. Add `.decomp/` to `.gitignore`, and a `.gitattributes` of `* text=auto eol=lf` plus `expected/** binary`, so line-ending conversion can never alter an expected byte.
- Ask whether the user knows of other editions of the same product. One whose code is the same can be accepted beside this one, and one known to be wrong gets a message: see Editions in [PROVISION.md](PROVISION.md).
- **Existing folder** (the user names a folder that already exists, for example an empty repo with a remote): accept it only when it is empty or already a decomp project; anything else stops, and you ask for another folder. If the folder has a remote, confirm with the user that the remote is **private** before anything is pushed.
- Keep the hash and size until step 5 writes them into `DECOMP.md` § Target. Nothing else holds them yet.
- The target stays where it is: the contract records its hash and size, and `.decomp/local.json` records its path on this machine. Nothing from it ever goes into a public repo.
- End step 1 with a first commit of `.gitignore` and `.gitattributes` on `main`, so the frozen-path check has history from the start.

## 2. Identify

Before you start the subagent, list the installed compilers, linkers, SDKs, and analysis tools on this machine, each with its version string, and put that list in the brief.

Start a background subagent with a fresh context window. Tell it to call the Skill tool with `decomp-identify`, give it the target path, the project folder, and the list, and have it write `IDENTIFY.md` there. In the brief, say that Python packages and analysis tools are installed by the user, never downloaded by the subagent, and that an installed neighbour version may serve as a partial probe.

While it runs, grill the decisions under the `[independent]` headings of CONTRACT.md. Each heading there is tagged `[needs IDENTIFY]` or `[independent]`: the first kind waits for `IDENTIFY.md`.

## 3. Grill the contract

Call the Skill tool twice, for `grilling` and `domain-modeling`. The design tree is every heading of [CONTRACT.md](CONTRACT.md). The user usually does not know the compiler, flags, or tools: those questions carry the recommendation from `IDENTIFY.md` with its evidence and confidence, so the user decides from facts. A low-confidence identification stays an open question until a probe or the user settles it.

Record each hard-to-reverse decision (scope, a departure from the default relocation policy, fakematch rule, an accepted edition) as an ADR.

**Done when** a `decomp-match` writer could start on any ticket without asking a single question, and a `/decomp-run` coordinator could pick, escalate, and verify without one.

## 4. Toolchain

Step 4 may start once the compiler and flags questions are settled; the other grilling rounds stay open alongside it.

Follow [PROVISION.md](PROVISION.md). `IDENTIFY.md` names the tools the target needs and which of them this machine lacks. For each missing tool the user chooses: they install it themselves, or you download and unpack it into the project after they approve the exact files and sources. Either way the result is recorded in `toolchain.json`, and `python tools/decomp.py doctor` must pass before you go on.

Then run the probes `IDENTIFY.md` could only list, and settle every question the grilling left open on them.

## 5. Write the system

- `DECOMP.md` from [CONTRACT.md](CONTRACT.md), every section filled.
- `decomp.json`: `integration_branch`, the adapter commands (`inventory`, `build`, `diff`, `disasm`, `link`, or `link_unavailable` with its reason when the link cannot be made), `pragma_allow` and `attribute_allow` (regexes: a `#pragma` line, or an attribute as written from its keyword to its closing bracket, passes only when one matches), `banned`, `compiler` (the default compiler's tool name), `unit_compilers` (unit id to tool name, only with evidence), and `github` (`enabled`, `repo`).
- `tools/decomp.py`: copy [scripts/decomp.py](scripts/decomp.py) unchanged.
- The five adapters in `tools/` (four when the link is unavailable), built to the adapter contracts in `decomp-standards`' layout. They reach the target and the tools through `DECOMP_TARGET` and `DECOMP_TOOL_<NAME>`, never an absolute path, run every tool through the wrapper, and start scripts with `"{python}" "{tools}/<script>"`. The `build` adapter compiles with the tool `{compiler}` names. The `diff` adapter applies the layout's default relocation policy, reading `{symbols}`, and nothing looser. The `link` adapter links with the contract's linker and flags, placing raw blocks at their file offsets and reproducing the headers. When the format or linker cannot do that, write no `link` adapter: set `link_unavailable` in `decomp.json` to the reason, and record the reason and its evidence in the contract's Matching section. There is no patched-original fallback.
- `symbols.json`: `{}` until `inventory` seeds it.
- Empty `PATTERNS.md` (header only) and `OPEN.md`.

## 6. Pipeline check

Prove the system works without reconstructing anything. Run every check in a throwaway clone of the project, so its records never reach the real ledger. Set `DECOMP_LOCAL` to the real project's `.decomp` folder, so the clone uses the provisioned toolchain:

- [ ] `doctor` passes and prints the edition.
- [ ] `doctor` exits 6 when `DECOMP_TARGET` points at any other file, and `verify` then records nothing.
- [ ] A stub unit (one trivial function under an `@decomp` marker comment) builds.
- [ ] The stub diffed against its own compiled bytes reports `match`.
- [ ] The stub diffed against a real function's bytes from the target reports a nonzero `differ_bytes`.
- [ ] The stub calling a function the symbol map places at another address than the original's operand reports `differ`, and the report names the symbol and both addresses.
- [ ] The stub calling a function the symbol map does not hold reports `differ`, and the report names the symbol.
- [ ] The stub with one extra instruction after a matching body reports `differ`.
- [ ] `verify` rejects a branch that touches a guarded path (try `symbols.json`), a source containing `__asm`, a `#pragma` outside the allowlist, a trigraph, a backslash line continuation, a `%:` directive, a `__pragma` outside the allowlist, token pasting, a naked function and an unlisted attribute in this compiler's own spelling, and assembly on a line after a string literal that holds `//`, each with result `guardrail`.
- [ ] A source whose only banned words sit inside a string literal or a comment passes the scan.
- [ ] A build whose compiler prints a message outside ASCII (in the tool's own encoding) still reports its result.
- [ ] Each tool's banner prints through the wrapper, and a build through it leaves no process waiting.
- [ ] `verify` refuses to run after a frozen path is edited on the integration branch.
- [ ] `python tools/decomp.py inventory` runs on the target, and its byte total for in-scope functions is no larger than the target's executable sections, and no two functions share a key.
- [ ] `python tools/decomp.py link` with every function left as a raw block (no source unit linked) prints `link: pass`, and the output's SHA-256 equals the target's. Run it after `inventory`, and before the tag. Where the link is unavailable, `link` exits 7 and prints the recorded reason instead, and the contract holds that reason and its evidence.

Every box ticked, each with the command you ran and its output: that is the completion criterion. Record the results and the Unix time in `DECOMP.md`.

## 7. Freeze

Commit, then tag `decomp-setup`. Tell the user to run `/decomp-start`.

## Changing the contract later

A new machine needs no contract change: write its `.decomp/local.json`, run `provision` with the user's approval of the recorded sources, then `doctor`.

Accepting another edition, or marking one known-wrong, is a contract change like any other. Prove every `differs` entry by comparing the two editions first.

Only on the user's request: grill the change, write a dated ADR, then update the contract through the change flow in `decomp-standards`' layout. The `decomp-setup` tag moves only after the candidate revalidation, on the user's go-ahead. Report every regression, from the candidate run and from the plain `revalidate` that ends the flow.

## Skill upgrade

An existing project keeps the copy of the project tool it was set up with. The user running `/decomp-setup` on that project is the only trigger for bringing it up to date.

**Detect.** Diff the integration branch's `tools/decomp.py` against this skill's [scripts/decomp.py](scripts/decomp.py), ignoring line endings. The tool carries no version constant: the diff is the whole test.

- **Identical**: the project is current. Tell the user so and stop, unless they asked for a contract change (see [Changing the contract later](#changing-the-contract-later)).
- **Different**: tell the user the project was set up by another version of the skills, and upgrade it as below.

**Upgrade.** A skill upgrade is a contract change. It goes through the change flow in `decomp-standards`' layout, and the candidate branch holds all of this:

- A dated ADR: the upgrade, and each contract file it adds or rewrites.
- `tools/decomp.py`: a fresh copy of [scripts/decomp.py](scripts/decomp.py), unchanged.
- Every file steps 4 and 5 require, in the form they require it. Compare the project against those two steps line by line, and add or rewrite what falls short. On a project from older skills that is usually:
  - `toolchain.json` (the manifest) and this machine's `.decomp/local.json`, written by [PROVISION.md](PROVISION.md) from the tools the project already builds with, plus the wrapper.
  - The adapters, rewired to `DECOMP_TARGET` and `DECOMP_TOOL_<NAME>` and the wrapper, holding no absolute path and no lookup of their own.
  - The `link` adapter (step 5), with its `link` command in `decomp.json`, or `link_unavailable` with the reason and evidence in the contract. Setup before the link existed lacks both: write them here, and add the blocks-only link line to the contract's pipeline check.
  - `decomp.json` keys and `symbols.json`.
  - `DECOMP.md` sections [CONTRACT.md](CONTRACT.md) has gained.
- The pipeline check (step 6) run again in full, in a throwaway clone of the candidate branch, with its results and the Unix time recorded in `DECOMP.md`. Where the `decomp-start` tag exists, the clone's inventory box runs `inventory --redo`. That needs no further go-ahead: the user started the upgrade, and the run writes only to the clone, which is discarded, so nothing in the project is overwritten. The clone's `inventory.json` and `expected/` must equal the frozen ones byte for byte. A difference is a fault in the rewired adapter to fix here, never an inventory redo slipped in with the upgrade.

The upgrade carries the contract's decisions over unchanged: same compiler, flags, scope, and policies. Where the newer skills need a decision the contract never made, grill that one decision as in step 3 and record it in the ADR.

**Candidate revalidation.** Run it with this skill's copy of the tool, from the project root with the integration branch checked out: `python <this skill's folder>/scripts/decomp.py revalidate --candidate c/<slug>`. The integration branch's `tools/decomp.py` may predate `--candidate`. The copy that starts the run only checks the branch name and hands the candidate to the candidate's own `tools/decomp.py`, which does the rebuild, so the result is the one the flow asks for. After the merge, the plain `revalidate` runs from `tools/decomp.py` as usual.

**Done when** every pipeline check box is ticked on the candidate branch and the change flow has run to its end, reported as in [Changing the contract later](#changing-the-contract-later).
