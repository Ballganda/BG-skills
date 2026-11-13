# Toolchain signals

Check every signal for the target's format. Record each as present (with the value) or absent.

## PE (Windows `.exe`, `.dll`)

| Signal | Where | Tells you |
| --- | --- | --- |
| Machine | COFF header | x86 (`0x14c`), x64 (`0x8664`), ARM64 (`0xaa64`) |
| Linker version | optional header, major.minor | Visual Studio generation (14.x is VS 2015 to 2022; the minor narrows the release). Linker and compiler can differ: confirm the compiler separately |
| OS and subsystem versions | optional header | Minimum OS the toolchain targeted, a rough era |
| Rich header | between the DOS stub and `PE\0\0`, XOR-masked | Every compiler and linker build that touched the file, with object counts per tool. Near proof when present; when stripped, say so |
| Debug directory | data directory 6 | CodeView `RSDS` record: PDB path (build machine paths, project names) and age; POGO record means profile-guided optimisation |
| Debug `feat` record | debug directory, `feat` entry | Object counts of C and C++ objects, and of objects built with `/GS`. A non-zero `/GS` count means the security cookie was on for those objects |
| Debug `coffgrp` and POGO records | debug directory, `coffgrp` and POGO entries | `LTCG` in the coffgrp record means the build used link-time code generation (`/GL` with `/LTCG`); `PGU` in the POGO record means a profile-guided update build (`/LTCG:PGUpdate`) |
| Timestamp | COFF header | Build time, unless reproducible builds replaced it with a hash |
| Imports | import table | Runtime DLL name and version (`msvcr71`, `msvcr80`, `msvcr90`, `msvcr100`, `vcruntime140`); none means the runtime is statically linked |
| Load config | data directory 10 | Security cookie address (`/GS`), CFG table (`/guard:cf`), the structure's size (grows with toolchain versions) |
| SafeSEH table | load config, SEH handler table (32-bit only) | Present means the image was linked with `/SAFESEH`; absent means it was not, or it has no SEH handlers |
| Exception handling | `.pdata` (x64), handler names in code | `__CxxFrameHandler3` versus `__CxxFrameHandler4` (VS 2019 and later default on x64); `/EHsc` versus `/EHa` |
| FuncInfo EH flags | FuncInfo structures (`__ehfuncinfo$...`) | The `EHFlags` bit for async exceptions: set under `/EHa`, clear under `/EHsc`. Check the bit against a known `/EHa` and a known `/EHsc` object before you trust it |
| RTTI | `.rdata` strings `.?AV<name>@@` | Class names, so struct and class work later has anchors |
| Assert and log strings | `.rdata` | Source file paths and names: evidence for unit boundaries |
| Runtime functions | code | `__security_check_cookie`, `__chkstk`, `_RTC_*` (debug runtime checks, `/RTC`), `__guard_check_icall_fptr` |
| Prologue shape | code | `push ebp; mov ebp, esp` everywhere suggests no `/Oy`; mixed suggests `/O2` with frame pointer omission; hot-patch `mov edi, edi` means `/hotpatch` |
| Instruction set | code | `/arch:SSE` (SSE1 scalar single with x87 doubles) shows `movss` and `addss` with doubles still on x87 (`fld` and `fstp` on qwords); SSE2 shows scalar double ops (`movsd`, `mulsd`); IA32 shows no SSE float ops at all. `rep movs` versus unrolled copies (`/O1` versus `/O2`) |
| Padding and `mov edi, edi` | padding between functions, function prologues | A split between user code and runtime: count each pattern per region. User objects and the static runtime often differ here, so use the split to separate the regions, not as a version signal |
| Vendor signature over Rich header | where the Rich header should sit | A vendor signature blob (protector or packer tag) can overwrite the Rich header. A missing Rich header does not prove Microsoft tools did not build the file: check for the blob first |
| Cross-function signals | code | Calls with non-standard conventions or arguments in odd registers, and inlining across what look like different units, suggest whole-program optimisation (`/GL`, `/LTCG`): flag it, it changes how matching works |

## ELF (Linux, many consoles)

| Signal | Where | Tells you |
| --- | --- | --- |
| `.comment` section | strings | `GCC: (...) <version>`, `clang version <version>`, one per contributing compiler |
| `.note.gnu.build-id`, `.note.ABI-tag` | notes | Build id, target ABI |
| `.gnu.version_r` | version needs | Minimum glibc and libstdc++ versions: an era |
| `.debug_*` | DWARF | `DW_AT_producer` holds the exact compiler and often the flags |
| Symbols | `.symtab`, `.dynsym` | Function names, mangling scheme |
| Code idioms | code | `endbr64` (`-fcf-protection`), `__stack_chk_fail` (`-fstack-protector`), frame pointer use, `-fPIC` thunks |

## Other formats

Mach-O: `LC_BUILD_VERSION` and `LC_VERSION_MIN_*` (SDK and tool versions), `__LINKEDIT` signature. Console and embedded formats: identify the format first, then look for compiler strings, runtime library signatures, and the SDK's known linker map patterns. When a format is not covered here, record that and research it from primary sources.
