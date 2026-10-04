# HybridCLR runtime loading

Verified on: Mystery Town, Merge Cooking (【实包确认】), against the upstream
`focus-creative-games/hybridclr` source (【源码确认】).

How a HybridCLR title loads its hot-update code, from the reverse-engineer's
side. The point of writing it down: it tells you exactly what to look for in a
memory dump and where the plaintext assembly is.

## Where the DLL comes from

The managed side calls `System.Reflection.Assembly.Load(byte[])`, which reaches
the icall `System.AppDomain::LoadAssemblyRaw` and lands in
`hybridclr/metadata/Assembly.cpp` `Assembly::LoadMetadataForAOTAssembly` /
`Create`. 【源码确认】 The bytes handed in **must already be a standard PE +
ECMA-335 image** — HybridCLR parses them with a standard reader and has no
built-in decryption whatsoever (`HybridCLRSettings.cs` has no encrypt/decrypt
field). So if the on-disk `.bytes` is encrypted, the decryption is the game's,
applied before `Assembly.Load`, and the plaintext PE exists in memory.

## The plaintext is always in memory, and stays

`InterpreterImage` holds a `RawImage` whose `_imageData` is the whole DLL, kept
as a raw pointer that method bodies index into. 【源码确认】 It is never freed —
`MethodBodyCache::ShrinkMethodBodyCache` releases only the `MethodBody`
descriptors, not the image. So a dump taken any time after first load contains
the complete plaintext assembly.

## Standard RE move

Hook `Assembly::Create` (anchor on the strings in `Assembly.cpp`), capture the
`(data, len)` it receives, and write it out — that is the plaintext PE, ready
for a decompiler. The `LoadMetadataForAOTAssembly` marker string is one of the
`hybridclr` fingerprint markers `revenant fingerprint` counts.

## Where the DLL is packaged

`HybridCLRSettings.cs` points at `hotUpdateDllCompileOutputRootDir` /
`externalHotUpdateAssemblyFullNames`; in the shipped package the hot-update
assemblies are the `*.bytes` resources named in the metadata string heap — see
[find-hot-update-code-by-bytes-literals](find-hot-update-code-by-bytes-literals.md).
