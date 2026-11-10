---
"bg-skills": patch
---

Decomp skills (in progress): fixes from the review of the toolchain and guardrail work, aimed at targets beyond 32-bit x86 and MSVC.

- **Guardrail scan**: comments and string literals are set aside before matching, so neither hides code nor trips the scan. Attributes in every spelling (`__attribute__`, `__declspec`, `[[...]]`) are held to a new `attribute_allow` list, naked functions and section placement are refused in GCC, Clang, and Metrowerks spellings too, and token pasting is refused.
- **Functions named by key**: a ticket id and expected file use a function's key, by default its address, so overlays, modules, and banks that share an address get distinct tickets. 64-bit addresses and `bank:offset` addresses work, and `PATTERNS.md` accepts their ticket ids.
- **Hosts**: a prerequisite or tool entry can be limited to some systems with `hosts`. Commands use `{python}` and `{tools}`, in adapters as well as in the manifest.
- **Per-unit compilers**: a compiler this machine lacks stops only the units built with it. `revalidate` no longer accepts a repair when it had to skip a matched ticket.
- **Provisioning**: `provision` names a missing host prerequisite, and compares a file already downloaded without silently replacing it.
- **Robustness**: tool output in any encoding, locks shared by every worktree, block-comment markers, and git older than 2.31.
