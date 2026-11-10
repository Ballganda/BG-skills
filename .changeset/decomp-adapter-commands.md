---
"bg-skills": patch
---

Decomp skills (in progress): the project tool runs the `inventory` and `disasm` adapters itself.

- **`inventory [--redo]`** runs the full environment check, then the `inventory` adapter with `DECOMP_TARGET` and every `DECOMP_TOOL_<NAME>` set. It exits 6 and writes nothing when the target is not an accepted edition. Once the `decomp-start` tag exists it refuses, naming the redo flow, unless `--redo` is passed.
- **`disasm <ticket id>`** fills the expected file and address from the ticket and runs the `disasm` adapter with the same environment, after the cached environment check `check` uses.
- **Adapters run only through the project tool.** The layout says so, `decomp-start`, `decomp-match`, and `decomp-reference` call the new commands, and the pipeline check runs the inventory through the tool. An adapter no longer needs a lookup of the machine file.
