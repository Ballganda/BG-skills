---
"bg-skills": patch
---

Decomp skills can now build the toolchain environment. `decomp-identify` adds a Toolchain requirements section (each tool's exact version, official source, and whether this machine has it) and offers two routes when one is missing: the user installs it, or the agent does. `decomp-setup` gains a provisioning step ([PROVISION.md](../skills/engineering/decomp-setup/PROVISION.md)) that records every tool in a frozen `toolchain.json`. `decomp.py` gains `provision` (download, compare size and SHA-256, unpack into `.decomp/toolchain/`) and `doctor` (target hash, required files, version banners), and runs the `doctor` checks before every `check`, `verify`, and `revalidate`. Adapters now find the target and tools through `DECOMP_TARGET` and `DECOMP_TOOL_<NAME>`.
