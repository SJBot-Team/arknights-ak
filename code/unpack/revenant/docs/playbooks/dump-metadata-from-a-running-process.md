# Take global-metadata.dat out of a running process

Verified on: Merge Cooking, Mystery Town (CDPH-packed metadata).

A hardened title ships `global-metadata.dat` as ciphertext, and reversing the
loader's decryption is the thorough answer. It is not the fast one. The runtime
decrypts the file into its own address space before anything else works, so ten
minutes with an emulator gets the plaintext without reading a line of the
decryptor — and if you later write the decryptor anyway, this is what you check
it against.

`revenant import-metadata` is the last step and has been here all along; it
even skips a container header on its own. The four steps in front of it were
written down in two notes and nowhere else, so the third packed title would
have meant reading a note to reconstruct them. That is what this file is for.

## Before you start

Three preconditions, all of which have cost a wasted install:

- **An arm64 system image.** The game ships arm64 native code. An x86_64
  emulator image either refuses the APK or runs it under translation where the
  memory map is not the one you want. Check with `adb shell getprop
  ro.product.cpu.abi` before installing anything.
- **A userdebug (or rooted) build.** Reading `/proc/<pid>/maps` and `/proc/<pid>/mem`
  for another process needs root. A Play-store emulator image does not have it;
  a plain AOSP image does.
- **Whether the title's anti-cheat refuses to run under an emulator.** Some do.
  If the game exits at the splash screen, this route is closed and
  [write-protect-to-locate-a-decryptor](write-protect-to-locate-a-decryptor.md)
  is the one to read next — it works on a real device.

## The four steps

Numbers below are illustrative; read yours out of the map.

```bash
# 1. the game's pid, once it is past the loading screen
adb shell pidof -s com.example.game

# 2. where the decrypted metadata is. Il2Cpp maps it as an anonymous region,
#    so it is found by the name of the file the loader opened, or -- when the
#    loader wipes the name -- by size, against the .dat in the APK.
adb shell su -c "grep -i global-metadata /proc/<pid>/maps"

# 3. carve exactly that range. `skip_bytes,count_bytes` exist so that bs can
#    stay a real block size -- with bs=1 the same 46 MB is ~3000x slower,
#    which is the difference between this being a ten-minute route and not.
adb shell su -c "dd if=/proc/<pid>/mem of=/data/local/tmp/meta.bin \
    bs=65536 skip=$((0x7f1a2b3000)) count=$((0x2c00000)) iflag=skip_bytes,count_bytes"
adb pull /data/local/tmp/meta.bin

# 4. into the project
revenant import-metadata meta.bin
```

`import-metadata` sanity-checks the image and repairs a container header if it
finds one, so a carve that starts a few bytes early is usually still accepted —
and rejected loudly rather than quietly installed when it is not.

## When step 2 finds nothing

The loader may open the file, decrypt into a fresh anonymous mapping and drop
the name. Then the region is unnamed and you match on **size**: the plaintext is
the same length as the `global-metadata.dat` in the package, so

```bash
unzip -l game.apk | grep global-metadata     # the length to look for
adb shell su -c "cat /proc/<pid>/maps" > maps.txt
```

Then filter on the host rather than on the device. `awk`'s `strtonum` is a gawk
extension — it is absent from BSD awk and from the toybox awk on the device, so
the one-liner that looks obvious fails with `calling undefined function`:

```bash
python3 - maps.txt <<'EOF'
import sys
want = 0x2c00000                      # the length from the line above
for line in open(sys.argv[1]):
    lo, _, hi = line.split()[0].partition("-")
    size = int(hi, 16) - int(lo, 16)
    # Mappings are page-granular, so the region is the file length rounded up.
    if 0 <= size - want < 4096:
        print(line, end="")
EOF
```

Two regions of that size is the normal case — one is the mapped ciphertext.
`revenant import-metadata` tells them apart: the plaintext passes its sanity
check and the ciphertext does not, so carve both and let it decide rather than
guessing.

## What this does not give you

The metadata only. Method bodies in a CDPH-packed title are still encrypted in
`libil2cpp.so` and want
[emulate-dont-reimplement](emulate-dont-reimplement.md); the IL layer wants
[write-protect-to-locate-a-decryptor](write-protect-to-locate-a-decryptor.md).
And a dump is a snapshot of one build: it does not survive the next version, so
a title you will revisit still earns the decryptor written as a
`[metadata] decryptor` module in the project.

## Why this is prose and not a command

Everything above touches a device. `revenant` has no device surface — no adb,
no emulator, no Frida driver — and this ticket did not open one. The step that
is deterministic and offline (accepting the carved image, repairing its header,
checking it is really metadata) is the one that is a command.
