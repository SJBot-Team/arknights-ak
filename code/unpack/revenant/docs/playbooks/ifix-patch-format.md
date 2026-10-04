# IFix (InjectFix) patch file format

Verified on: Tasty Travels, Hotel Legacy (【实包确认】: shipped
`asmdef_fat_runtime.patch.bytes`), against upstream IFix (【源码确认】).

An IFix patch is a plain `BinaryWriter` stream of eleven sections. It is not
encrypted — from `Hotfix.HotfixManager` the chain
`DownloadHandler.data → MemoryStream → PatchManager.Load` has no decryption
call — so the bytes parse as-is. `revenant.contrib.decrypt.IFixPatch.parse`
walks it; this is what the sections are.

## Section layout

1. magic (u64) + bridge type (string)
2. external types (count, then strings)
3. method slots: each is a list of `(opcode, operand)` instruction pairs plus
   exception handlers
4. external methods (`MethodRef` each — see below)
5. strings
6. fields (`isNew`, declaring type, name)
7. VM static fields
8. anonymous closures — **not self-describing**: how many ints follow each
   interface depends on reflecting that interface in the host assembly
9. bridge type / IDMAP suffix
10. the fix table: `(MethodRef, method-slot)` per fixed method
11. new-field names

Because section 8 cannot be walked without the host assembly, when in-order
parsing fails, locate section 10 by brute force: try to parse it, then 11, and
accept the offset that lands exactly on EOF. Its syntax is constrained enough
that a false match is implausible.

## MethodRef

`(isGeneric, declaringTypeId, name, params)`, every id range-checked so a wrong
guess raises instead of silently mis-parsing. Params are type ids, or strings
for generic parameters.

## Opcodes are shuffled per build

IFix's build runs `ShuffleInstruction.cs`, so the opcode values are permuted per
build and the magic is randomised. The disassembler must take its opcode map
from the game's own `IFix.Core.Code` enum (dump it from the stubs) rather than
from upstream IFix — keep that map as a project file (`opcodes.json`).

## Mounting

Not runtime replacement: IL is injected pre-build and the runtime fills an
array. Each patchable method body begins with a slot-id constant, an
`IsPatched(id)` check, and a `GetPatch(id)` call; `IDMAP0` is the full slot
table. On Tasty Travels the shipped patch fixed two methods
(`ActivitySevenDayTask.WhenUpdate`, `UISevenDayTaskEntry.RefreshInfo`), 141 and
32 instructions — the parser reproduces exactly that.
