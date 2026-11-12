## What it does

`decomp-setup` starts a byte-for-byte decompilation project. It takes a target binary and produces three things: a private git repo, a **contract** (`DECOMP.md`), and the tooling that enforces it. The contract fixes the target, the exact compiler and flags, the scope, the matching policies, and the models for each size tier. It has to be complete enough that every later agent can work from it without asking you a question.

It reconstructs nothing. No function is decompiled during setup. The run ends when a pipeline check proves the tooling can build, compare, and refuse a cheat, and the `decomp-setup` tag freezes the result. Run on a project that already exists, it does a different job: it upgrades that project to the current skills, and runs none of the setup steps again.

## When to reach for it

You invoke this by typing `/decomp-setup`, and the agent won't reach for it on its own. Give it the path to a target binary, or to an existing decomp project.

| You have… | What it does |
| --- | --- |
| A binary and no decomp project yet | Sets up a new project, through to the frozen contract |
| A project set up by an older version of the skills | Upgrades it as a contract change, measured before the tag moves |
| A project that wants a different flag, scope, or accepted edition | Changes the contract, on your request only, through the same measured flow |
| A new machine for an existing project | Nothing to change: it provisions the recorded toolchain and checks it |

To turn a set-up project into tickets, use [decomp-start](./decomp-start.md). To work the tickets, use [decomp-run](./decomp-run.md).

## Prerequisites

- **The target binary**, on this machine. It stays where it is: the contract records its hash and size, and a never-committed `.decomp/local.json` records its path.
- **Python 3**, for the project tool `tools/decomp.py`, which the skill copies into the project.
- **A private remote, if any.** The project starts with no remote. Nothing from the target, its bytes, or the reconstructed source ever goes into a public repo.
- **Host prerequisites the contract names**, such as an archive tool or a compatibility layer. You install these; the tool checks their versions.

## The contract

The contract is the whole point of setup. It is grilled with you heading by heading, but you are usually not the one who knows the compiler. A background subagent runs [decomp-identify](./decomp-identify.md) on the binary while the grilling covers the decisions that don't depend on it. Toolchain questions then arrive with a recommendation, its evidence, and a confidence. A low-confidence identification stays open until a probe or you settle it. Every hard-to-reverse decision (scope, a relocation policy departure, the fakematch rule, an accepted edition) gets an ADR.

The contract is done when a writer could start any ticket, and a coordinator could pick, escalate, and verify, without asking you a single question.

## Provisioning and the pipeline check

Every tool the contract names is pinned in a frozen `toolchain.json`: its exact version banner, the files a build needs, and where it came from. For each missing tool you choose who installs it:

- **You install it**, and the manifest records where.
- **The agent downloads and unpacks it** into the project, after you approve the exact files and sources. Size and SHA-256 are checked on every download.

`decomp.py doctor` then has to pass. It checks the target's edition, each host prerequisite, and each tool's files and banner, and the tool runs it before every build or comparison afterwards. Exit 6 always means the machine differs from the contract, never the source.

The pipeline check proves the system works before anything depends on it, in a throwaway clone so nothing reaches the real records. A stub function has to build and match its own bytes, and differ from a real function. The scan has to refuse inline assembly, an unlisted pragma, and the other hidden-directive forms. The inventory has to account for the target's code. A link made from raw blocks alone has to reproduce the original's hash. Where the format cannot be linked whole, the contract records why instead.

## Common questions

**These skills used to be in `in-progress/`. Where are they now?**

`engineering/`. The decomp skills graduated out of the beta bucket and now ship in the plugin with the rest of the promoted set, so they no longer need an individual install.

**My project was set up with older skills. How do I bring it up to date?**

Run `/decomp-setup` on the project folder. It diffs the project's `tools/decomp.py` against the skill's copy; identical means current, and it stops. A difference means an upgrade: a fresh copy of the tool and whatever contract files the newer skills require (the manifest, rewired adapters, the link adapter), on a `c/<slug>` branch with an ADR, with the pipeline check run again. The upgrade keeps every decision the contract already made: same compiler, flags, scope, and policies. You are the only trigger. No other skill compares the copies or warns you.

**I want to change a flag (or the scope) after tickets exist. Will that wipe my matches?**

No change lands unmeasured. The change goes on a candidate branch, and `revalidate --candidate` rebuilds every matched ticket with the candidate's own tool and contract, recording nothing. You see the regressions before you decide, and the tag moves only on your go-ahead. A regression doesn't block the change, because a corrected flag can break matches on purpose. The plain `revalidate` after the merge records what broke.

**My target can't be linked back into a whole binary. Is setup blocked?**

No. Where the format or linker cannot place raw blocks at fixed offsets or reproduce the headers, the project gets no `link` adapter, and the contract records the reason and its evidence. Per-function matching works the same. There is no patched-original fallback.

**I have a second copy of the product, a store re-release. Can it be used?**

If its code is the same, the contract can accept it as another edition, recognised by hashes of chosen byte ranges. Any function it holds differently is listed, and those tickets can't be verified on that edition. An edition known to be wrong gets a message instead, telling whoever holds it what to do. Adding either one later is a contract change.

## It's working if

- No source is written during setup, and the run ends by telling you to run `/decomp-start`.
- Compiler and flag questions come with evidence and a confidence from the identification, not a request for you to know them.
- You approve exact download sources and hashes before anything is fetched.
- `DECOMP.md` lists every pipeline check box with the command that ran it, its output, and a Unix time.
- A second `/decomp-setup` on the same, current project says it is current and changes nothing.

## Where it fits

`decomp-setup` is the run-once setup at the head of the decomp chain:

```txt
decomp-setup → decomp-start → decomp-run
```

Its neighbours are [decomp-identify](./decomp-identify.md), which it starts to find the compiler from the binary, and [decomp-start](./decomp-start.md), which reads the frozen contract to build the inventory and tickets. The rules the contract serves live in [decomp-standards](./decomp-standards.md). [skill-map](./skill-map.md) is the router over the whole set.
