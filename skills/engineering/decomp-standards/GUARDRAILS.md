# Guardrails

The project tool (`tools/decomp.py`) enforces every rule a script can check; the **auditor** checks the rest. A violation fails the attempt, whatever the bytes say.

1. **One file.** A writer changes exactly one file: its ticket's `source`. Everything else is **guarded**: shared headers, the symbol map, expected bytes, the target binary, `tools/`, `decomp.json`, `toolchain.json`, `DECOMP.md`, tickets, the ledger, `PATTERNS.md`, `OPEN.md`. The tool rejects a branch that touches any of them.
2. **No assembly, ever.** No inline assembly in any form, even where the original used it: no `__asm`, `_asm`, `asm`, `__asm__`, `_emit`, no naked function or section placement in any compiler's spelling (`__declspec(naked)`, `__attribute__((naked))`, `[[gnu::naked]]`, `__attribute__((section(...)))`, `__declspec(allocate(...))`), no `.asm` or `.s` file, no machine code stored as data. A function that can only be written in assembly is `asm-origin` and out of scope.
3. **The contract's compiler and flags.** The tools are the ones `toolchain.json` pins, on the target it pins: when the tool reports an environment failure (exit 6), stop and report it. No other compiler, version, or copy of the target stands in. No per-function or per-file option or `#pragma` unless the contract's pragma allowlist names it, and no attribute (`__attribute__`, `__declspec`, `[[...]]`) unless its attribute allowlist does. `__pragma` and `_Pragma` are held to the pragma allowlist. An attribute opens and closes on one line. No form that hides a directive or a keyword from a reader of the line: no trigraph, no backslash line continuation, no `%:` digraph, no token pasting (`##`), no `#include` whose file a macro names. An `#include` names a file inside the project or a toolchain header, never an absolute path or one that climbs out of the project. The tool refuses these outright, in the source and in every project file it includes, directly or through another header.
4. **Bytes straight from the compiler.** No editing objects, no post-processing, no linker or section tricks that place bytes.
5. **Evidence-backed declarations.** Every field, type, signature, and calling convention comes from the shared headers or from evidence in the binary, and every symbol's address from the symbol map. When one is missing or wrong, stop and report a `reference-gap`: the shared fix belongs to `decomp-reference`, never to a local copy in the unit file.
6. **The tool records matches.** Statuses, ledger lines, and match claims come only from `tools/decomp.py`. A report cites the attempt id the tool printed.
7. **Codegen steering is declared.** A construct written only to steer the compiler (a dummy variable, a needless `volatile`, permuter output) is allowed only as far as the contract's fakematch rule allows, and carries a `fakematch: <why>` comment.
8. **Scope belongs to the user.** What is in scope, the compiler, and the flags change only through `/decomp-setup`, recorded in a dated ADR.

## Auditor checklist

The auditor receives the source diff and this file, nothing else. It is the second line behind the tool's own scan.

Fail the attempt, quoting the offending line and the rule number, if the diff:

- contains assembly in any spelling, or bytes that look like machine code (rule 2);
- adds a `#pragma`, `__pragma`, `_Pragma`, `__declspec`, `__attribute__`, `[[...]]` attribute, or compiler option outside the contract's allowlists (rule 3);
- contains a trigraph (`??=`, `??/`, and the rest) anywhere, a backslash that ends a line (alone or before spaces or tabs), the digraph `%:`, or token pasting (`##`) (rule 3);
- adds an `#include` that names its file through a macro, by an absolute path, or by a path that leaves the project (rule 3);
- defines a struct, class, typedef, or extern that a shared header should own, or redeclares one with different members (rule 5);
- contains a steering construct without a `fakematch:` comment, or more steering than the contract's fakematch rule allows (rule 7);
- edits anything outside the one function marked for this ticket, other than adding includes the function needs;
- claims a match in a comment.

Reply with exactly one line: `pass`, or `fail: rule <n>: <quoted line>`.
