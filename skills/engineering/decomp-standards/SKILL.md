---
name: decomp-standards
description: Shared rules for byte-for-byte decompilation: the acceptance criterion, guardrails, size tiers, mismatch categories, and the project's files and records. Use when reconstructing, verifying, auditing, or repairing a decomp function, or when another decomp skill needs these rules.
---

# Decomp Standards

## The goal

Recover source that, compiled with the compiler and build configuration in the project's **contract** (`DECOMP.md`), produces machine code identical to the original, byte for byte, for every in-scope function.

A function is **matched** only when the project tool has recorded it: a clean build, an exact byte comparison against the original, and a passed audit. Matching behaviour, a matching algorithm, a clean build, or a near match counts for nothing. The original binary is the authority, the contract is the constraint, the byte comparison is the test.

## Guardrails

Read [GUARDRAILS.md](GUARDRAILS.md) before you write, audit, or repair any source. They hold for every project, and no contract loosens them.

## Size tiers

Size runs from a function's first byte to the end of its last instruction: trailing alignment padding excluded, and jump tables or literal pools the compiler places inside the function included.

| Tier | Size |
| --- | --- |
| TINY | 25 B or less |
| SMALL | 26 to 256 B |
| MEDIUM | 257 to 511 B |
| LARGE | 512 B or more |

The contract maps each tier to a model and an attempt budget.

## Time

Every record uses Unix time in seconds.

## Commits

Every commit a decomp skill makes ends with the harness's attribution lines. This covers the coordinator's ledger commits, a writer's source commits, and `decomp-reference`'s repair commits. A commit without them is wrong, whichever skill made it.

## Mismatch categories

Tag every failed attempt with exactly one, the one that best explains the first differing instruction:

| Category | The first difference comes from |
| --- | --- |
| `build-fail` | the source does not compile, for a reason local to it |
| `reference-gap` | a missing or wrong shared declaration (field, type, signature, convention) or symbol map entry |
| `signedness` | signed versus unsigned: sign or zero extension, the compare, the shift (on x86: `movsx`/`movzx`, `jl`/`jb`, `sar`/`shr`) |
| `width` | integer promotion, truncation, or operand size |
| `operator` | a comparison, arithmetic, or logical operator |
| `control-flow` | branch or loop shape: inverted condition, `for`/`while`/`do`, `switch` lowering |
| `statement-order` | the order of statements or side effects |
| `expression-shape` | how one expression is split, nested, or parenthesised |
| `register-allocation` | the same instructions in different registers |
| `stack-layout` | local variable order, size, or count |
| `data-layout` | a field offset or structure size |
| `calling-convention` | argument passing, stack cleanup, `this` passing |
| `inlining` | a call the original inlined, or an inline the original called |
| `optimization` | compiler behaviour no source change in the function reaches (suspect the contract's flags) |
| `unit-order` | the position of the function or its data within its unit |
| `unknown` | none of the above |

## Project files

Layout, ticket format, statuses, records, and tool commands: [LAYOUT.md](LAYOUT.md).
