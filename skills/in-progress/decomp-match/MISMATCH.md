# Mismatch guide

Start from the **first** differing instruction: later differences are often its echoes. A difference of one or two instructions can still come from a misunderstanding. Correct the source so the compiler produces the bytes on its own; never steer it with constructs outside the guardrails.

| Category | Check | Source levers |
| --- | --- | --- |
| `signedness` | `movsx`/`movzx`, `jl`/`jb`, `jg`/`ja`, `sar`/`shr`, `idiv`/`div`, `imul`/`mul` | Signedness of the variable, the field, the parameter, or the return type; an unsigned constant suffix |
| `width` | Operand size (`al`/`ax`/`eax`), extra `and`/`movzx` after a load, missing truncation | `char`/`short`/`int`/`long` choice, `bool` versus `int`, casts on the expression rather than the result, `enum` underlying size |
| `operator` | `<` versus `<=` (shows as `jl`/`jle`, or an off-by-one constant), `!=` versus `>`, `&&` evaluation order | The written comparison and constant; `x < 10` and `x <= 9` can compile differently |
| `control-flow` | Inverted branch, block order, a loop test at the top versus the bottom, a jump table versus a compare chain | Swap the `if`/`else` bodies, negate the condition, `for`/`while`/`do`, early `return` versus a single exit, `switch` case order and density, `goto` only if the evidence shows irreducible flow |
| `statement-order` | Same instructions, different order; stores before or after a call | Reorder statements; split or merge declarations with initialisers |
| `expression-shape` | Same operations, different association or temporaries | Parenthesise differently, split into a named temporary, inline a temporary, `a = b = c` chains, compound assignment |
| `register-allocation` | Same instructions, other registers | Declaration order of locals, a variable reused versus a fresh one, its scope; often the last difference to fall. Check the contract's fakematch rule before steering |
| `stack-layout` | Different `[ebp-x]`/`[esp+x]` offsets, frame size | Order, count, and size of locals; arrays and structs on the stack; a variable that the original kept in a register |
| `data-layout` | Different field offset or structure size | A `reference-gap`: stop and report it |
| `calling-convention` | `ret N`, caller cleanup, `ecx` as `this`, register arguments | Member function versus free function, `__stdcall`/`__cdecl`/`__fastcall`/`__thiscall` from the shared declaration. A wrong declaration is a `reference-gap` |
| `inlining` | A `call` where the original has a body, or the reverse | Write the helper `inline` or `static`, or call it out of line. A helper's definition belongs in its own unit or a shared header |
| `optimization` | Code shape that no change to this function affects | Suspect the contract's flags. Record it and stop; the coordinator watches for a recurring pattern |
| `unit-order` | The function's bytes match, but its references or alignment differ | Its position in the unit, or a `static` or global defined in the wrong place |
| `build-fail` | The compiler's first error | Your own syntax or types; a missing shared declaration is a `reference-gap` |

## Relocated operands

The diff masks a relocated operand only when its target is proven to be the original's. Two lines in the report are not ordinary byte differences:

| The report says | It means | Do |
| --- | --- | --- |
| Unresolved symbol `<name>` | Neither the symbol map nor a matched function in this object gives `<name>` an address, so the operand cannot be proven | Stop and report a `gap`: the symbol, and the address the original's operand holds. Category `reference-gap` |
| `<offset>`: `<name>` resolves to `<address>`, the original holds `<other address>` | Your code refers to another callee or global than the original | Find what lives at the original's address (the symbol map, `inventory.json`) and call or reference that. If the map's address for `<name>` is the wrong one, that is a `gap` |
| Bytes after the function are not padding | Your function is longer than the original, or its extent differs from the ticket's size | Treat the extra instructions as the first difference |

A string or floating-point literal at another address with identical bytes is not a difference: the linker chooses which pooled copy survives.
