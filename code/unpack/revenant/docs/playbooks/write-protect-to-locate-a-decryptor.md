# Locate an in-place decryptor by write-protecting its target

Verified on: Merge Cooking, Mystery Town (CDPH IL layer).

A container that is decrypted in place, one record at a time, gives up its
decryptor if you make the container read-only: the first write into it faults,
and the faulting PC is the decrypting instruction. On the fault, un-protect just
that page and continue, so the game keeps running and later writes on other
pages still get caught.

`revenant.contrib.decrypt.write_protect_recipe(base_expr, size)` emits the
Frida script for this — you supply the region base and size; nothing is baked
in.

## The startup trap

`Process.setExceptionHandler` is itself detected by some anti-cheat during
startup. Two ways around it, both observed:

- Attach a few seconds after launch and hook only cold functions — the 5-second
  window survives where installing an exception handler at startup dies.
- Arm the probe after the game is fully running, when the check has passed.

## Follow-on

Once you have the decryptor's PC, you usually do not need to understand it:
drive the runtime to decrypt the whole container
([replay-the-loader](replay-the-loader.md)), or emulate the cipher
([emulate-dont-reimplement](emulate-dont-reimplement.md)).
