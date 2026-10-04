## Practice

Hand-written: judgement about doing the work well, which no code can generate.
It ships with Revenant and is folded into this file at render time, so an
upgrade carries it to every project — it is not a per-project copy.

### Assembly is the territory

`re_find_asm` (ISIL) is the primary reconstruction input and the source of
truth. The DiffableCs `.cs` is a map: real names, real field offsets, no method
bodies.

`Disassembly` and `ISIL` are **different abstraction layers, not two views of
the same thing**. Disassembly answers "what bytes are at this address"; ISIL
answers "what does this method do". When a body has been outlined, the
disassembly at its entry is just the init prologue. Reconstruct from ISIL.

### Read the control flow before writing any branch

For any method with branches, call `re_cfg(rva)` before writing loops or `if`s.
Do not rebuild the CFG by eye. Take the loop bodies, the reconvergence points,
and especially the **always-executed set** from the tool.

**Loop pre-test versus a real guard.** A *backward* conditional branch is a loop
back-edge. A *forward* conditional branch whose target equals the loop's
fall-through exit is a **loop-entry pre-test** — it gates the loop body only,
not the statements after the loop. Those later statements are in the
always-executed set and must not be wrapped in the guard.

This is not a hypothetical. A benchmark of 20 reconstructions found this rule
was what stopped a real error on the most complex sample in the set.

### A placeholder is correct behaviour, not a defect

When something genuinely cannot be recovered from the input — a string literal
that exists only as a metadata slot address, a branch whose comparison the
lifter dropped — leave a marked placeholder and say so. Do not invent a
plausible value.

Any text comparison will score a placeholder worse than a fabrication. It is
worth far more. Declaring failure is a usable signal; a confident wrong answer
is not.

<!-- extension:packs -->
### Zero hits are a result

A probe that matches nothing has told you something, and the ledger records it.
Before calling any cell "checked, genuinely absent", hold the probe vocabulary
against how *this* game names things (`revenant naming-stats`). A zero hit can
mean the word list is wrong rather than the system missing — across two
teardowns, 6 of 8 one-sided slots turned out to be coverage holes, not real
differences between the games.
<!-- /extension:packs -->

### Cross-references see only direct calls

`re_xrefs` / `re_callgraph` see direct `bl`/`b` call sites only. Virtual,
interface and delegate dispatch go through vtables and icalls and are invisible.
**A count of zero does not mean unused.** Confirm through the registration site
or the calling subsystem.

A string proves presence; the call graph proves use. Two names sitting in the
same binary is not evidence that one drives the other — three vendor
attributions in one prior study were wrong for exactly this reason.

### The fingerprint observes; you decide

`revenant fingerprint` lists what was looked for and what was found — marker
hits per table (zeros included), declared assemblies against the metadata and
their difference, `*.bytes` literals in the string heap, build paths, native
exports, dex packages. It does not name the stack or score same-origin: read
the list and judge. A wiped marker shows as a zero next to its siblings; a
declared game assembly the metadata lacks is stated as a fact, and if the
business code lives there every IL2CPP probe returns zero.

### Lua-first on a scripted title

When `re_status` reports Lua, the gameplay is in Lua and the C# side is engine,
framework and bridge glue. Answer game-rule, board, economy and UI-flow
questions from the decompiled scripts.

- **Find by content**: `re_lua_grep("<regex>")` searches every script and
  returns `module:line: text`. Use `re_lua_list` when you already know the name.
- **Cross the bridge**: Lua reaches C# via `CS.<Namespace>.<Type>`; C# drives
  Lua via `LuaManager.CSharpCallLuaMethod`. `re_lua_bridge("CS.X.Y")` resolves a
  type to its RVA and to the scripts that use it. Going the other way, take
  xrefs on the `CSharpCallLuaMethod` RVA.

### Architecture caveat

On a 32-bit (ARM32) target, `re_evidence`'s field / condition / mutation
inference is ARM64-tuned and best-effort only — verify against `re_find_asm`.
Raw mnemonics from `re_disasm` are correct on both; pass `mode="arm"` or
`"thumb"` to force the decoder.

### Output conventions

- Identifiers, code and reconstructed C#: English. Prose follows the project.
  No emoji, no `---` rules in notes.
- Findings go to `notes/<arch|core|elem|rule>-NN-<slug>.md`, and every note needs
  a data-sources section (`## 数据来源`, `## 来源` or `## 证据索引`) — `revenant lint`
  has nowhere to look without it. Tag each claim with a bracketed tier from the
  table above, on the same line as the RVA, symbol or file it rests on.
- A note that reaches a conclusion carries a `## 复现命令` section: the exact
  commands that produced it, so a reader can re-run them. `revenant lint`
  warns when one is missing. Provenance markers (`【源码确认】` for what upstream
  source shows, `【实包确认】` for what the shipped package shows) sharpen a claim.
- Recurring decryption and hot-update methods are written up in Revenant's
  `docs/playbooks/`; reach for one before re-deriving an approach.
- Cross-version and cross-platform work matches **by name, never by RVA**.
  Addresses do not survive either axis.
