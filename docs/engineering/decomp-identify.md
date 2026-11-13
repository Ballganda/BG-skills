## What it does

`decomp-identify` works out what built a binary: its format, architecture, compiler, compiler version, and build flags. It writes the investigation to `IDENTIFY.md` in the decomp project, with ranked candidates, a probe for each, and the exact toolchain a matching build needs.

Every conclusion rests on evidence it observed and can show you. It keeps **facts** (a command and its output) apart from **inferences** (a conclusion that names its facts and carries a confidence of `high`, `medium`, or `low`), and never passes one off as the other. The stakes are why: in a byte-for-byte decomp a wrong compiler makes every later attempt worthless, and you usually do not know the compiler yourself, so the skill hands you evidence to decide from rather than a guess to trust.

## When to reach for it

Type `/decomp-identify`, or the agent reaches for it automatically when a task fits. In practice it is started for you: `/decomp-setup` runs it in a background subagent while it grills you on the decisions that do not depend on the compiler.

Reach for it when a decomp target's toolchain is unknown or in doubt:

| Your situation | Where to go |
| --- | --- |
| A new target, and nobody knows what compiled it | `/decomp-setup`, which starts `decomp-identify` for you |
| `decomp-run` stopped on `EARLY-WARNING`: the contract's compiler or flags look wrong | Rerun `/decomp-setup`, which can start `decomp-identify` again |
| You only want to know what built a binary, without setting up a project | `/decomp-identify` on its own |
| The compiler is settled and the question is one function's bytes | [decomp-match](./decomp-match.md) |

## Prerequisites

It writes `IDENTIFY.md` into the decomp project folder, so it needs that folder and the target's path. Probes need the candidate toolchain installed; without it, a probe is listed for later rather than run.

## Evidence, not a verdict

The skill reads the binary only. It works through every **signal** its format carries (for a Windows PE: the linker version, the Rich header, the debug directory, the runtime DLL in the imports, the security cookie, prologue shapes, the instruction set) and records each as present or absent. An absent signal is evidence too: a stripped Rich header is worth saying.

From the signals it ranks **candidates**, each a compiler version plus a flag set with the evidence for it and against it. Each candidate gets a **probe**: the cheapest experiment that would confirm or kill it, such as compiling a snippet with the candidate and comparing its prologue to the target's. A statically linked runtime is dated by a probe too: its functions are compared with the static runtime libraries of the candidate toolset and the SDK. When only a neighbour version is installed, a probe on it counts as partial evidence, labelled with that version.

`IDENTIFY.md` then carries three things the rest of the decomp project depends on:

| Section | What it feeds |
| --- | --- |
| Toolchain requirements | Each tool's exact version, its version string, its official source, and whether this machine has it |
| Toolset to install | Each tool with its exact installer component id. `decomp-setup`'s provisioning step works from this list |
| Exclusion signals | Statically linked runtime and third-party library code, with addresses. These are the first candidates to drop out of scope |
| Unknowns | What is still open, each with what would settle it |

When the signals differ between regions of the code, it lists a second compiler build with the address ranges it covers: some units were built with it.

## Common questions

**Will it install the compiler it finds?**

No. It downloads nothing and copies nothing out of the target. When a required tool is missing or the wrong version, its reply names the recommended toolchain, one line per tool, and gives you two ways forward: you install it yourself, or you ask the agent to. Either way the install happens in `decomp-setup`'s provisioning step, which gets your approval for each file and records the result in `toolchain.json`.

**What happens when it is not sure?**

The candidate says so, with `medium` or `low` confidence and the probe that would settle it. `decomp-setup` treats a low-confidence identification as an open question until a probe or you settle it, so an uncertain compiler never quietly becomes the contract.

**It used to be in `in-progress/`. Where is it now?**

`engineering/`. It graduated with the rest of the decomp skills and now ships in the plugin. Its behaviour did not change on the move.

## It's working if

- Every claim in `IDENTIFY.md` either quotes a command and its output, or names the facts it rests on and a confidence.
- Signals that were looked for and not found are listed as absent, not left out.
- Every candidate comes with a probe you could run.
- Each required tool has a status on your machine: installed with its version string, wrong version, or missing.
- The reply is short: the top candidate, its confidence, and the path to `IDENTIFY.md`.

## Where it fits

`decomp-identify` is a step inside the run-once setup of a decomp project:

```txt
decomp-setup (decomp-identify) → decomp-start → decomp-run
```

[decomp-setup](./decomp-setup.md) starts it and turns its recommendation into contract questions, then provisions the toolchain it names. [decomp-run](./decomp-run.md) sends you back to it, through setup, when the early warning says the contract's compiler is suspect. When you are unsure which skill fits, [skill-map](./skill-map.md) routes you.
