---
"bg-skills": patch
---

Decomp skills (in progress): a tool with no executable can be pinned by a file.

- **Banner file**: a tool entry in `toolchain.json` may name `banner_file`, a path relative to the tool's root, in place of `banner_cmd`. `decomp.py` reads the file itself, in whatever encoding it holds, and `doctor` passes when `banner` is a substring of its contents. This pins a platform SDK made of headers without a host-specific command.
- **One pin per tool**: `doctor` exits 6 and names the tool when it has both `banner_file` and `banner_cmd`, or neither, and names the file when a banner file is missing.
- **Banner command docs**: the provisioning document says manifest commands run through the host shell (`cmd.exe` on Windows) and that `{root}` is a native path continued with the host's separator. Its example banner command now goes through the wrapper, as the rule beside it requires.
