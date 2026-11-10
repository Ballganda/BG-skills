---
name: decomp-setup
description: Agree a byte-for-byte decomp contract with the user and set up the private project that enforces it. Does no decomp.
disable-model-invocation: true
argument-hint: "Path to the target binary"
---

Set up a decomp project: a private repo, a **contract** every later agent can work from without asking a question, and the tooling that enforces it. This skill reconstructs nothing. It ends when the pipeline check passes and the `decomp-setup` tag is set; then tell the user to run `/decomp-start`.

Call the Skill tool with `decomp-standards` first: its goal, guardrails, and layout are what this setup serves.

## 1. Project

- Get the target binary's path. Hash it (SHA-256) and note its size.
- Agree the project folder with the user (default: a sibling of the current project, `<target>-decomp`). Create it as a new git repo with `main` as the integration branch and no remote until the user names a **private** one. Add `.decomp/` to `.gitignore`, and a `.gitattributes` of `* text=auto eol=lf` plus `expected/** binary`, so line-ending conversion can never alter an expected byte.
- Ask whether the user knows of other editions of the same product. One whose code is the same can be accepted beside this one, and one known to be wrong gets a message: see Editions in [PROVISION.md](PROVISION.md).
- The target stays where it is: the contract records its hash and size, and `.decomp/local.json` records its path on this machine. Nothing from it ever goes into a public repo.

## 2. Identify

Start a background subagent with a fresh context window. Tell it to call the Skill tool with `decomp-identify`, give it the target path and the project folder, and have it write `IDENTIFY.md` there. While it runs, grill the decisions that do not depend on the compiler.

## 3. Grill the contract

Call the Skill tool twice, for `grilling` and `domain-modeling`. The design tree is every heading of [CONTRACT.md](CONTRACT.md). The user usually does not know the compiler, flags, or tools: those questions carry the recommendation from `IDENTIFY.md` with its evidence and confidence, so the user decides from facts. A low-confidence identification stays an open question until a probe or the user settles it.

Record each hard-to-reverse decision (scope, a departure from the default relocation policy, fakematch rule, an accepted edition) as an ADR.

**Done when** a `decomp-match` writer could start on any ticket without asking a single question, and a `/decomp-run` coordinator could pick, escalate, and verify without one.

## 4. Toolchain

Follow [PROVISION.md](PROVISION.md). `IDENTIFY.md` names the tools the target needs and which of them this machine lacks. For each missing tool the user chooses: they install it themselves, or you download and unpack it into the project after they approve the exact files and sources. Either way the result is recorded in `toolchain.json`, and `python tools/decomp.py doctor` must pass before you go on.

Then run the probes `IDENTIFY.md` could only list, and settle every question the grilling left open on them.

## 5. Write the system

- `DECOMP.md` from [CONTRACT.md](CONTRACT.md), every section filled.
- `decomp.json`: `integration_branch`, the adapter commands (`inventory`, `build`, `diff`, `disasm`), `pragma_allow` and `attribute_allow` (regexes: a `#pragma` line, or an attribute as written from its keyword to its closing bracket, passes only when one matches), `banned`, `compiler` (the default compiler's tool name), `unit_compilers` (unit id to tool name, only with evidence), and `github` (`enabled`, `repo`).
- `tools/decomp.py`: copy [scripts/decomp.py](scripts/decomp.py) unchanged.
- The four adapters in `tools/`, built to the adapter contracts in `decomp-standards`' layout. They reach the target and the tools through `DECOMP_TARGET` and `DECOMP_TOOL_<NAME>`, never an absolute path, run every tool through the wrapper, and start scripts with `"{python}" "{tools}/<script>"`. The `build` adapter compiles with the tool `{compiler}` names. The `diff` adapter applies the layout's default relocation policy, reading `{symbols}`, and nothing looser.
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

Every box ticked, each with the command you ran and its output: that is the completion criterion. Record the results and the Unix time in `DECOMP.md`.

## 7. Freeze

Commit, then tag `decomp-setup`. Tell the user to run `/decomp-start`.

## Changing the contract later

A new machine needs no contract change: write its `.decomp/local.json`, run `provision` with the user's approval of the recorded sources, then `doctor`.

Accepting another edition, or marking one known-wrong, is a contract change like any other. Prove every `differs` entry by comparing the two editions first.

Only on the user's request: grill the change, write a dated ADR, then update the contract through the [change flow](../decomp-standards/LAYOUT.md#change-flow). The `decomp-setup` tag moves only after the candidate revalidation, on the user's go-ahead. Report every regression, from the candidate run and from the plain `revalidate` that ends the flow.
