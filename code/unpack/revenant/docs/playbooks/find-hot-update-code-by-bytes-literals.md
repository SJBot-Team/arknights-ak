# Find hot-update code by the `.bytes` literals, not the manifest difference

Verified on: Mystery Town (3 real hot-update assemblies), and the manifest-diff
noise measured across all eight titles.

To find where a title's business code lives, two static signals are available:

1. **Manifest minus metadata.** `ScriptingAssemblies.json` lists the assemblies
   the game declares; `global-metadata.dat` lists the ones compiled into the
   IL2CPP binary. The difference contains the hot-update assemblies — but also a
   lot of noise. On Mystery Town, 33 declared-but-absent assemblies were only 4
   real hot-update DLLs; the rest were shader asmdefs (4), editor/analyzer
   asmdefs (5), managed-stripped libraries (16), and project-only-never-shipped
   (4).
2. **`*.bytes` string literals in the metadata heap.** A hot-update loader names
   the byte resource it loads as a string literal. On Mystery Town these are
   exactly three (`common_c_{md,ut,vw}.bytes`) — the manifest had a fourth
   (`dc`), which never loads and so is not in the metadata.

The literals win: they name what the runtime actually goes to load, with none
of the difference's noise.

## How to read them

`revenant fingerprint` lists both — the manifest difference (with the "declared
game assemblies that do not exist in the corpus" note) and the `bytes_literals`,
read from the recovered plaintext metadata. Prefer the literals; use the
difference as a wider, noisier net. The resource-manifest's own addressable
entries ending in `.bytes` are a third, equally direct signal.
