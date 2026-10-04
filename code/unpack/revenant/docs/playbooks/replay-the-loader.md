# Replay the loader to materialise a container the game never fully loads

Verified on: Mystery Town (CDPH TypeDef table), Merge Cooking (container rebuild).

The process only ever decrypts what it executes, so a memory dump of a running
game is incomplete: method bodies that were never called are still ciphertext.
The complete copy comes from decrypting the on-disk container offline; the
metadata tables, which the runtime decrypts in full at load time, come from the
memory image. A fully materialised container is the two spliced together.

For containers the game never loads at all, drive the runtime to do it:
`revenant.contrib.decrypt.reload_recipe(module, create_rva)` emits a Frida
script that recreates the image, calls the loader, then calls the post-load
fix-up the runtime does through the image's vtable slot — without that last
call the assembly parses structurally but every name lookup runs off the end of
the string heap.

## Lazy decryption has to be driven

Some tables are decrypted lazily. CDPH's TypeDef table, for instance, is
decrypted row by row on first access via a vtable slot; a bulk offline pass has
to call that slot for every row explicitly, or the rows it never touched stay
encrypted.

## Project-specific inputs

The `create` RVA, the vtable slot offsets (load, post-load fix-up), and the
container's on-disk vs in-memory boundary are per-build facts. The recipe takes
them as parameters.
