# Decomp toolchains are provisioned from a recorded manifest

`decomp-setup` first said the user installs every tool and the agent never downloads one. That kept the agent away from fetching executables, but it left the hardest part of setup (finding a twenty-year-old compiler, at the exact build, with its headers) to the person least likely to know how, and it recorded nothing a second machine could repeat. f3decomp, a working byte-matching project, does the opposite: a pinned vendor URL with size and hash, a script that unpacks only the compiler, and a checker that refuses any other compiler or target on every run.

We now do the same, with the user's choice kept:

- `decomp-identify` names the required tools and reports which are missing. It still downloads nothing.
- `decomp-setup` asks, per tool, whether the user installs it or the agent does. The agent downloads only files the user approved from that list, only from the vendor's official source, and unpacks them into the project's `.decomp/` folder instead of installing them.
- `toolchain.json` records each tool's source, size, hash, unpack steps, required files, and version banner, and is frozen with the contract. Machine paths live in the uncommitted `.decomp/local.json`.
- `decomp.py doctor` runs before every `check`, `verify`, and `revalidate`, and refuses to build when the target's hash or any tool's banner differs.

Consequences: the agent can fetch and run vendor binaries, so the approval list and the hash comparison are the safeguards, and a hash recorded from a first download pins the file without vouching for it. A tool with no official source stays the user's to supply.
