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
4. The original's disassembly: the `disasm` adapter command from `decomp.json`, with the ticket's `expected` and `address`.
5. The unit's source file, and the shared headers it includes.
6. `python tools/decomp.py similar <id>`: the closest solved functions. Read their source as guidance, not as a substitute for reading this one.

## 2. Separate known from unknown

List every type, field, callee, global, and calling convention the function touches. Next to each, write where it comes from: a shared header, or an address and instruction in the disassembly.

A callee or global also needs its address in `symbols.json`: without it the diff cannot prove your call reaches the right target.

If any is missing from the headers or the symbol map, or contradicts them, **stop**: report a `gap` naming the declaration and the evidence. A local stand-in would hide the gap from every other function that needs the same declaration.

## 3. Write

Write the function in the unit's source file, at its address-order position, directly under `// @decomp <id>`. Change nothing else in the file except adding includes the function needs.

## 4. Loop

Run `python tools/decomp.py check <id>` and read the result:

- **Exit 6, `ENVIRONMENT:` lines**: the machine's target or toolchain differs from the contract, this machine's edition holds the function differently, or the unit's compiler is not provisioned. Nothing you write fixes it: stop and report it in `note`, with `local: build-fail`.
- **`build-fail`**: fix your own source. If the error is a missing or wrong shared declaration, that is a `gap`: stop.
- **`guardrail`**: the scan quotes the line and names the rule. Rewrite it within the guardrails: a trigraph, a line continuation, or a `%:` directive is refused whatever it spells, so write the plain form.
- **`differ`**: open the diff report and find the **first** differing instruction. Read [MISMATCH.md](MISMATCH.md) for its category, write two or three ranked hypotheses (each with the change it predicts will remove the difference), then make **one** change per iteration. Progress is a falling `differ_bytes`; a change that does not lower it is reverted, unless it moves the first difference later.
- **`bytes-match`**: done.

Stop at a local `bytes-match` or when the contract's attempt budget for this tier is spent. Each `check` run is one attempt.

## 5. Commit and report

Commit only the unit's source file to your branch. Your local result does not count: the coordinator's clean `verify` and an auditor decide. Reply in at most 60 words, exactly these lines:

```
ticket: <id>
local: bytes-match | differ <n>B | build-fail | gap
category: <one mismatch category, or none>
note: <what you tried and what it showed, under 15 words>
lesson: <instruction pattern> => <source idiom>, or none
gap: <declaration, evidence address and instruction>, or none
```

Give a lesson only when your match depended on an idiom you would want to know next time.
