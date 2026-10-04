---
description: Deep-decompile one IL2CPP method from assembly to verified C#
argument-hint: <Namespace.Class.Method> [rva]
---
Deep-decompile the method `$1` (optional RVA: `$2`) for this IL2CPP target. Follow the `re` skill. Call `re_status` first for the version and architecture; use that `<version>` in paths below.

1. Resolve the RVA: if `$2` is given use it; else `re_search` for `$1` (or `re_type_info` on the class, then read its DiffableCs `.cs` for the `[Address(RVA=...)]`).
2. Ensure the `src/<version>/...` scaffold for the class exists (scaffold from `re_type_info` first if missing).
3. `re_find_asm(rva)` for the ISIL; resolve `bl`/call targets with `re_lookup`. Use `re_evidence(rva, type_name=<Class>)` for field-access hints (on ARM32: best-effort, verify against ISIL).
4. If the method has branches, `re_cfg(rva)` for the control-flow structure — basic blocks, loops, and the always-executed set. Use it (not eyeballing) to decide loop-vs-if scope: code in always-executed blocks runs unconditionally and must not be wrapped in an `if`; a forward conditional branch that skips a loop body is a loop pre-test, not a guard over the statements after the loop.
5. For a complex method, write `decompiled/<NsPath>/<Class>.<Method>.c` (interleaved C with asm comments + Business Intent), then derive idiomatic C#.
6. Edit the method body into `src/<version>/...` with inline RVA citations. Every behavioural claim carries a bracketed tier on the same line as its citation — `{{tier:disassembly}}` for what you read in the instructions, `{{tier:managed_code}}` for what the C# stubs and metadata establish, `{{tier:structural}}` for the rest. No completeness markers: nothing is settled except by a cited instruction.

Report: the reconstructed C#, the tier per claim, and files written.
