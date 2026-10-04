# Playbooks

Reusable reverse-engineering methods, one per file. Each was used on more than
one real title before it was written down; the "Verified on" line at the top of
each playbook says which. A method that worked on only one game stays in that
game's notes until a second title needs it — a playbook is a claim that the
method generalises, and that claim needs two data points.

One narrow exception, added with [luban-table-format](luban-table-format.md):
a **format reference transcribed from an upstream open-source project** may land
before any real package confirms it, because the claim it makes is about that
upstream and is checkable there rather than being a method that might not
generalise. It still says so in its "Verified on" line — 【源码确认】 with no
【实包确认】 — and names what a first real decode would settle. A method with one
title behind it still waits in that game's notes.

These are prose, not code, and the two-title rule above applies to *methods*
only. Code is admitted on a different bar -- whether it holds a game fact, with
no recurrence requirement -- and both bars, plus why they differ, are recorded
in [ADR-0004](../adr/0004-what-qualifies-to-move-into-revenant.md). The
importable machinery some of these lean on lives in `revenant/contrib/`; the
commands they cite are the ones `revenant help` lists. Provenance inside a playbook uses the same markers the notes do:
`【源码确认】` for what an upstream source shows, `【实包确认】` for what a shipped
package shows.

## Decryption and cold start

- [plaintext-pairing](plaintext-pairing.md) — recover a key stream from a
  ciphertext/plaintext pair, no code reversed.
- [write-protect-to-locate-a-decryptor](write-protect-to-locate-a-decryptor.md)
  — make the target read-only and read the faulting PC.
- [dump-metadata-from-a-running-process](dump-metadata-from-a-running-process.md)
  — let the runtime decrypt `global-metadata.dat` and carve it out of memory.
- [emulate-dont-reimplement](emulate-dont-reimplement.md) — run the protector's
  own VM under Unicorn instead of porting its handlers.
- [replay-the-loader](replay-the-loader.md) — let the runtime materialise a
  container the game never fully loads.
- [period-detection](period-detection.md) — confirm or refute a repeating-XOR
  key by residue-class statistics.
- [find-hot-update-code-by-bytes-literals](find-hot-update-code-by-bytes-literals.md)
  — the `*.bytes` string literals beat the assembly-manifest difference.
- [same-origin-by-project-fingerprints](same-origin-by-project-fingerprints.md)
  — build paths and addressable GUIDs, not shared keys.
- [luajit-decompilation](luajit-decompilation.md) — build and wire up
  luajit-decompiler-v2 so `lua-extract` handles `\x1bLJ` bytecode.

## Getting at the content

- [remote-content-routes](remote-content-routes.md) — fetch it from the CDN or
  read the client's cache; which one a title leaves open, and why a survey pass
  comes first.

## Format references

- [hybridclr-loading](hybridclr-loading.md) — how HybridCLR loads a hot-update
  assembly, and where the plaintext PE is in memory.
- [ifix-patch-format](ifix-patch-format.md) — the on-disk layout of an IFix
  patch and how to walk it.
- [luban-table-format](luban-table-format.md) — the binary config-table layout,
  why a schema is required, and the one analysis step Merge Cooking still owes.
