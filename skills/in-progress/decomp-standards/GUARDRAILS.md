# Guardrails

The project tool (`tools/decomp.py`) enforces every rule a script can check; the **auditor** checks the rest. A violation fails the attempt, whatever the bytes say.

1. **One file.** A writer changes exactly one file: its ticket's `source`. Everything else is **guarded**: shared headers, the symbol map, expected bytes, the target binary, `tools/`, `decomp.json`, `toolchain.json`, `DECOMP.md`, tickets, the ledger, `PATTERNS.md`, `OPEN.md`. The tool rejects a branch that touches any of them.
2. **No assembly, ever.** No inline assembly in any form, even where the original used it: no `__asm`, `_asm`, `asm`, `_emit`, `__declspec(naked)`, no `.asm` or `.s` file, no machine code stored as data. A function that can only be written in assembly is `asm-origin` and out of scope.
3. **The contract's compiler and flags.** The tools are the ones `toolchain.json` pins, on the target it pins: when the tool reports an environment failure (exit 6), stop and report it. No other compiler, version, or copy of the target stands in. No per-function or per-file option, `#pragma`, or attribute that changes code generation unless the contract's allowlist names it. `__pragma` and `_Pragma` are held to the same allowlist. No form that hides a directive from a reader of the line: no trigraph, no backslash line continuation, no `%:` digraph directive. The tool refuses these outright, in the source and in every project header it includes.
4. **Bytes straight from the compiler.** No editing objects, no post-processing, no linker or section tricks that place bytes.
5. **Evidence-backed declarations.** Every field, type, signature, and calling convention comes from the shared headers or from evidence in the binary, and every symbol's address from the symbol map. When one is missing or wrong, stop and report a `reference-gap`: the shared fix belongs to `decomp-reference`, never to a local copy in the unit file.
6. **The tool records matches.** Statuses, ledger lines, and match claims come only from `tools/decomp.py`. A report cites the attempt id the tool printed.
7. **Codegen steering is declared.** A construct written only to steer the compiler (a dummy variable, a needless `volatile`, permuter output) is allowed only as far as the contract's fakematch rule allows, and carries a `// fakematch: <why>` comment.
8. **Scope belongs to the user.** What is in scope, the compiler, and the flags change only through `/decomp-setup`, recorded in a dated ADR.

## Auditor checklist

The auditor receives the source diff and this file, nothing else. It is the second line behind the tool's own scan.

Fail the attempt, quoting the offending line and the rule number, if the diff:

- contains assembly in any spelling, or bytes that look like machine code (rule 2);
- adds a `#pragma`, `__pragma`, `_Pragma`, `__declspec`, attribute, or compiler option outside the contract's allowlist (rule 3);
- contains a trigraph (`??=`, `??/`, and the rest) anywhere, a backslash that ends a line (alone or before spaces or tabs), or a line that starts with the digraph `%:` (rule 3);
- defines a struct, class, typedef, or extern that a shared header should own, or redeclares one with different members (rule 5);
- contains a steering construct without a `// fakematch:` comment, or more steering than the contract's fakematch rule allows (rule 7);
- edits anything outside the one function marked for this ticket, other than adding includes the function needs;
- claims a match in a comment.

Reply with exactly one line: `pass`, or `fail: rule <n>: <quoted line>`.
