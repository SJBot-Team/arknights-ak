# Emulate the protector's VM instead of reimplementing it

Verified on: Merge Cooking, Mystery Town (CDPH block cipher).

A bytecode-VM protector decrypts method bodies through hundreds of opcode
handlers. Understanding all of them is a large job that the next build
invalidates. Loading `libil2cpp.so` under Unicorn and running the protector's
own VM reproduces the transform exactly, byte for byte with the runtime, and
survives handler reshuffles.

`revenant.contrib.decrypt.SegmentedImage` maps the ELF's PT_LOAD segments the
way the loader would (every segment at its virtual address), which is the one
shared prerequisite. `find_dispatcher` locates the VM by the *shape* of its
dispatch sequence rather than its address.

`decrypt_blocks` is the loop on top of both: it writes each block to the
wrapper's scratch address, sets the argument registers, runs from the entry to
the return, and reads the result back. The emulator is an argument — a Unicorn
instance has the four methods it calls, and revenant imports none of it — so a
project supplies the instance, the addresses, the block size and the bytes that
must be in memory first (`preload`), and gets back the output plus which blocks
did not run. A block that aborts is recorded and the rest still run, because a
57 MB blob is thousands of blocks.

## The two facts that stay in the project

- **The jump table.** The opcode dispatch table is often blank in the file and
  filled by the protector at init; it has to be read once from a live process,
  then reused. Keep it as a project file (`jumptbl.json`), not in the shared
  module.
- **The entry address and key layout.** The wrapper RVA and the (program, key,
  body, length, chunk) argument layout are per-build. Pass them in.

If the package is packed, feed the emulator the module image dumped from the
process rather than the on-disk file.
