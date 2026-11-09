---
name: decomp-identify
description: Investigate a binary to find its format, architecture, compiler, version, and build flags, from evidence in the file. Use when a decomp target's toolchain is unknown, when decomp-setup needs IDENTIFY.md, or when small functions keep failing to match and the contract's compiler is in doubt.
---

Find out what built a binary, from the binary. The user usually does not know, and a wrong compiler makes every later attempt worthless, so every conclusion rests on evidence you observed and can show.

## Rules

- **Fact or inference.** A fact is something you observed: the command and its output. An inference is a conclusion drawn from facts, naming them and carrying a confidence (`high`, `medium`, `low`). Never present an inference as a fact.
- **Read only.** Copy nothing from the target into any public place. Download nothing: when a probe needs a toolchain that is not installed, list it as a probe for later.
- **Primary sources.** When a conclusion depends on a vendor fact (which product shipped linker 14.38, which version introduced a runtime function), call the Skill tool with `research` and cite what it finds.

## Steps

1. **Container.** Format, architecture, bitness, sections with sizes, entry point, timestamp, imports, exports, and every header field that carries a toolchain version. Use [SIGNALS.md](SIGNALS.md) for what each format carries.
2. **Toolchain signatures.** Work through every signal in SIGNALS.md for this format. Note the ones that are absent, and why that matters (a stripped header is evidence too).
3. **Runtime and libraries.** Is the runtime library linked dynamically (named in imports) or statically (recognisable functions inside)? Its version narrows the compiler. Statically linked runtime and third-party library code is the first candidate for exclusion.
4. **Code idioms.** Sample functions across the code section and read their prologues, epilogues, calls, and stack checks for the flag signals in SIGNALS.md: optimisation level, frame pointer use, security checks, exception model, instruction set, inlining, whole-program optimisation.
5. **Rank candidates.** Each candidate is a compiler version plus a flag set, with the evidence for it and against it.
6. **Probes.** For each candidate, the cheapest experiment that would confirm or kill it: compile a snippet with the candidate and compare an idiom (prologue shape, security check, exception handler) to the target. Run a probe only when the toolchain is already installed; otherwise list it with what to install.

## Output

Write `IDENTIFY.md` in the project folder:

```markdown
# Identify: <target>
Target: <path>, SHA-256 <hash>, <size> B. Investigated <Unix time>.

## Facts
- <fact>: `<command>` gave `<output, trimmed>`

## Inferences
- <inference> (<confidence>): from <facts>

## Candidates
1. <compiler version> + <flags>: for <evidence>; against <evidence>

## Probes
- <probe>: confirms <candidate> if <observation>; needs <tool, installed or not>

## Exclusion signals
- <runtime or library code found>, at <addresses>, from <evidence>

## Unknowns
- <what is still unknown, and what would settle it>
```

**Done when** every signal in SIGNALS.md for this format is recorded as present or absent, every candidate has a probe, and every unknown names what would settle it. Reply to whoever started you with the top candidate, its confidence, and the path to `IDENTIFY.md`, in under 60 words.
