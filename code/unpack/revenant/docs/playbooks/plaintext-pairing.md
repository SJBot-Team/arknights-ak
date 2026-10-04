# Recover a key stream from a plaintext/ciphertext pair

Verified on: Merge Cooking, Mystery Town (CDPH outer XOR).

When you hold the same data in two forms — the ciphertext on disk and the
plaintext in memory — and they correspond byte for byte, the key stream falls
out directly:

    keystream = cipher XOR plain

No code is reversed. Confirm the key repeats (rather than being a one-time pad)
with [period-detection](period-detection.md): if `cipher XOR plain` has a short
period, you have a repeating-XOR key of that length and can decrypt the rest of
the container offline.

This is how CDPH's 16-byte outer XOR was recovered — a getter body whose
plaintext was already known, paired against its on-disk ciphertext, gave the
key with no disassembly.

## When it applies

- The transform is XOR-like (byte-wise, position-dependent, no diffusion).
- You can obtain the same region in both forms — e.g. a method body you can read
  from a memory dump and also locate in the packaged container.

## When it does not

- Block ciphers with diffusion (a one-byte plaintext change alters many
  ciphertext bytes): pairing gives you nothing reusable. Emulate the cipher
  instead — see [emulate-dont-reimplement](emulate-dont-reimplement.md).
