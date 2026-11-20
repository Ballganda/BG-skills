---
name: decomp-match
description: Reconstruct one decomp ticket's function so the contract's compiler emits the original bytes exactly. Use when given a decomp ticket to solve, or when asked to match, decompile, or reconstruct one function.
---

You are a writer. Recover the source that makes the original compiler emit this function's bytes, exactly. Work from the machine code: the function's apparent purpose does not decide its implementation.

Call the Skill tool with `decomp-standards` first. Its guardrails bind every line you write.

## 1. Gather

Read, in this order:

1. The ticket. Its notes are earlier attempts on this function: never repeat an approach a note records without new evidence.
2. `DECOMP.md`'s Toolchain and Matching sections, including the fakematch rule.
3. `PATTERNS.md`: proven idioms for this compiler.
4. The original's disassembly: `python tools/decomp.py disasm <id>`.
5. The unit's source file, and the shared headers it includes.
6. `python tools/decomp.py similar <id>`: the closest solved functions. Read their source as guidance, not as a substitute for reading this one.

## 2. Separate known from unknown

List every type, field, callee, global, and calling convention the function touches. Next to each, write where it comes from: a shared header, or an address and instruction in the disassembly.

A callee or global also needs its address in `symbols.json`: without it the diff cannot prove your call reaches the right target.

If any is missing from the headers or the symbol map, or contradicts them, **stop**: report a `gap` naming the declaration and the evidence. A local stand-in would hide the gap from every other function that needs the same declaration.

## 3. Write

Write the function in the unit's source file, at its place in the contract's function order, directly under its `@decomp <id>` marker comment. Change nothing else in the file except adding includes the function needs.

## 4. Loop

Run `python tools/decomp.py check <id> --category <c>` and read the result. `<c>` is your reading of the first difference, one of the mismatch categories: leave it off only on a first run, before you have read a difference. The tool keeps it in the check trail and decides from it whether the template step below is open:

- **Exit 6, `ENVIRONMENT:` lines**: the machine's target or toolchain differs from the contract, this machine's edition holds the function differently, or the unit's compiler is not provisioned. Nothing you write fixes it: stop and report it in `note`, with `local: build-fail`.
- **`build-fail`**: fix your own source. If the error is a missing or wrong shared declaration, that is a `gap`: stop.
- **`guardrail`**: the scan quotes the line and names the rule. Rewrite it within the guardrails: a trigraph, a line continuation, a `%:` digraph, or token pasting is refused whatever it spells, so write the plain form. An attribute outside the contract's allowlist is refused too: if the evidence shows the original used it, that is a `gap` for the contract, not yours to add.
- **`differ`**: open the diff report and find the **first** differing instruction. Read [MISMATCH.md](MISMATCH.md) for its category, write two or three ranked hypotheses (each with the change it predicts will remove the difference), then make **one** change per iteration. Progress is a falling `differ_bytes`; a change that does not lower it is reverted, unless it moves the first difference later. When the JSON says `search_open` is true, take the template step instead of a single change.
- **`bytes-match`**: done.

### Template step

`search_open` true means a template round is allowed: the tool judged that small source variations may fix what is left. A `search_reason` says why. When it is false, `search` refuses, so keep making single changes.

1. Copy the unit's source file to a template file outside the project tree. Keep the `@decomp <id>` marker.
2. Turn each hypothesis into a choice point where its change goes: `PERM_GENERAL(@label kind, %0.6 alt, %0.3 alt, ...)`. The label names the choice and stays stable across rounds. The kind is the lever from [MISMATCH.md](MISMATCH.md) (`decl-order`, `stmt-order`, `loop-form`, `temp-type`, `signedness`, `width`, `operator`, `expression-shape`, `branch-order`, `inlining`, or `other`). The `%` likelihood is your ranking of the hypotheses. Write the original spelling as the first alternative. `PERM_LINESWAP`, `PERM_ONCE`, `PERM_INT`, `PERM_VAR`, and `PERM_IGNORE` are in [LAYOUT.md](../decomp-standards/LAYOUT.md).
3. Write only alternatives you can justify from the disassembly. The tool never invents a change, and a pile of guesses wastes the round. Lead an alternative with `/* steer: <why> */` only when it is a construct written to steer the compiler; every other alternative is natural. The tool prefers natural matches, and refuses a template holding steering when the contract's fakematch rule is `forbidden`. Each steering line that survives into the winner carries a `fakematch:` comment, so the guardrail scan accepts it.
4. Run `python tools/decomp.py search <id> <template file>`. It tries the candidates and prints one JSON line: `end`, `best`, `window`, `counts`, and on a match `winner`.
5. On `end: match`, copy the `winner` file's function into the unit's source file, then run `check` as usual. A search result is never a match claim: the winner still goes through `check`, the coordinator's `verify`, and the audit.
6. Otherwise read `best` and `window`, plus `effects` (which choice points moved the score and by how much), `inert` (points no alternative changes: leave them out next round), `pairs` (alternatives that help only together), and `history` (which kind fixed this category before on this compiler: raise that kind's likelihoods). When `stop` is present, follow it and report the ticket as stuck. Then edit the template by label: drop what did not help, add alternatives for the first difference that remains. Fetch one candidate's source with `search <id> --detail '<choice code>'`.
7. `continues_s` in the summary means the tool keeps searching that template in the background while you write the next one. The next `search` call reports it under `background`, in the old template's choice codes. When that report holds `discarded`, the old template matched: the summary is its match, your new template was not searched, and step 5 applies. To give up on a template round, run `search <id> --stop`.

A template round is one attempt. A summary with `repeat: true` is not one: every candidate came from the result cache, so the round told you nothing new and costs nothing. Do not run an unchanged template again; change it first. A file with no choice point is refused: a plain compile is `check`'s job. When a round leaves the best `differ_bytes` no lower than the one before, stop and report the ticket as stuck in `note`: do not run a third plateau round.

Stop at a local `bytes-match` or when the contract's attempt budget for this tier is spent. Each `check` run and each template round is one attempt.

## 5. Commit and report

Commit only the unit's source file to your branch: stage it by name (`git add <source>`), never `git commit -a` or `git add -A`, so no ticket or ledger file rides along. Your local result does not count: the coordinator's clean `verify` and an auditor decide. Reply in at most 60 words, exactly these lines:

```
ticket: <id>
local: bytes-match | differ <n>B | build-fail | gap
category: <one mismatch category, or none>
attempt: <single | template>
note: <what you tried and what it showed, under 15 words>
lesson: <instruction pattern> => <source idiom>, or none
gap: <declaration, evidence address and instruction>, or none
```

`attempt` is `template` when your last attempt was a template round, so the coordinator can pass it to `verify`; otherwise `single`. Give a lesson only when your match depended on an idiom you would want to know next time.
