"""Synthetic binary and package fixtures.

Hand-built rather than trimmed from real games, because the cases that matter
most are ones a real binary will not hand you on demand -- chiefly an address
that sits inside a Mach-O segment but outside every section, which is where
segment-mapping and section-mapping disagree.

Everything here is a few hundred bytes to a few KB. No real game package is ever
used as a test fixture.
"""

from __future__ import annotations

import json
import os
import plistlib
import struct
import zipfile

# Layout shared by the ELF and the Mach-O fixture, so the two can be compared
# directly at the same addresses.
LOAD_VADDR = 0x1000
LOAD_FILEOFF = 0x1000
LOAD_SIZE = 0x400          # the whole mapped range, file-backed in both formats
TEXT_SIZE = 0x200          # Mach-O: only the first half is covered by a section

ADDR_IN_TEXT = 0x1040      # covered by a section in both formats
ADDR_IN_GAP = 0x1250       # inside the segment, outside every section
ADDR_UNMAPPED = 0x9000     # outside everything

EM_AARCH64 = 183
EM_ARM = 40
CPU_TYPE_ARM64 = 0x0100000C
CPU_TYPE_ARM = 12

METADATA_MAGIC = b"\xAF\x1B\xB1\xFA"


def _body(size: int, seed: int = 0x11) -> bytes:
    """Deterministic filler so reads can be asserted byte-for-byte."""
    return bytes((seed + i) & 0xFF for i in range(size))


def write_elf(path: str, machine: int = EM_AARCH64) -> str:
    """A minimal ELF64 with one PT_LOAD covering LOAD_VADDR..+LOAD_SIZE.

    The whole range is file-backed, so ADDR_IN_GAP resolves here -- ELF has no
    notion of sections at load time and hands back the padding. That is correct
    ELF behaviour, and the point of the contrast with the Mach-O fixture.
    """
    ehsize, phentsize = 64, 56
    header = bytearray(ehsize)
    header[0:4] = b"\x7fELF"
    header[4] = 2                                    # ELFCLASS64
    header[5] = 1                                    # ELFDATA2LSB
    header[6] = 1                                    # EV_CURRENT
    struct.pack_into("<H", header, 16, 3)            # e_type = ET_DYN
    struct.pack_into("<H", header, 18, machine)
    struct.pack_into("<I", header, 20, 1)            # e_version
    struct.pack_into("<Q", header, 32, ehsize)       # e_phoff
    struct.pack_into("<H", header, 52, ehsize)       # e_ehsize
    struct.pack_into("<H", header, 54, phentsize)
    struct.pack_into("<H", header, 56, 1)            # e_phnum

    phdr = bytearray(phentsize)
    struct.pack_into("<I", phdr, 0, 1)               # PT_LOAD
    struct.pack_into("<I", phdr, 4, 0x1 | 0x4)       # PF_X | PF_R
    struct.pack_into("<Q", phdr, 8, LOAD_FILEOFF)
    struct.pack_into("<Q", phdr, 16, LOAD_VADDR)
    struct.pack_into("<Q", phdr, 24, LOAD_VADDR)
    struct.pack_into("<Q", phdr, 32, LOAD_SIZE)      # p_filesz
    struct.pack_into("<Q", phdr, 40, LOAD_SIZE)      # p_memsz
    struct.pack_into("<Q", phdr, 48, 0x1000)

    blob = bytearray(LOAD_FILEOFF + LOAD_SIZE)
    blob[0:ehsize] = header
    blob[ehsize:ehsize + phentsize] = phdr
    blob[LOAD_FILEOFF:LOAD_FILEOFF + LOAD_SIZE] = _body(LOAD_SIZE)

    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "wb") as f:
        f.write(blob)
    return path


def write_macho(path: str, cputype: int = CPU_TYPE_ARM64, with_zerofill: bool = True) -> str:
    """A minimal 64-bit Mach-O whose __TEXT segment is wider than its sections.

    `__TEXT` spans LOAD_VADDR..+LOAD_SIZE, but `__text` only covers the first
    TEXT_SIZE bytes. ADDR_IN_GAP therefore falls inside the segment and outside
    every section -- the case that must raise rather than resolve.
    """
    sec_size, seg_cmd_size = 80, 72
    nsects = 2 if with_zerofill else 1
    cmdsize = seg_cmd_size + sec_size * nsects
    mach_header = 32

    hdr = bytearray(mach_header)
    struct.pack_into("<I", hdr, 0, 0xFEEDFACF)
    struct.pack_into("<i", hdr, 4, cputype)
    struct.pack_into("<i", hdr, 8, 0)                # cpusubtype
    struct.pack_into("<I", hdr, 12, 6)               # MH_DYLIB
    struct.pack_into("<I", hdr, 16, 1)               # ncmds
    struct.pack_into("<I", hdr, 20, cmdsize)
    struct.pack_into("<I", hdr, 24, 0)               # flags

    seg = bytearray(seg_cmd_size)
    struct.pack_into("<I", seg, 0, 0x19)             # LC_SEGMENT_64
    struct.pack_into("<I", seg, 4, cmdsize)
    seg[8:8 + 6] = b"__TEXT"
    struct.pack_into("<Q", seg, 24, LOAD_VADDR)      # vmaddr
    struct.pack_into("<Q", seg, 32, LOAD_SIZE)       # vmsize
    struct.pack_into("<Q", seg, 40, LOAD_FILEOFF)    # fileoff
    struct.pack_into("<Q", seg, 48, LOAD_SIZE)       # filesize
    struct.pack_into("<i", seg, 56, 0x5)             # maxprot  = READ|EXECUTE
    struct.pack_into("<i", seg, 60, 0x5)             # initprot = READ|EXECUTE
    struct.pack_into("<I", seg, 64, nsects)
    struct.pack_into("<I", seg, 68, 0)               # flags

    sections = bytearray()

    text = bytearray(sec_size)
    text[0:6] = b"__text"
    text[16:22] = b"__TEXT"
    struct.pack_into("<Q", text, 32, LOAD_VADDR)     # addr
    struct.pack_into("<Q", text, 40, TEXT_SIZE)      # size -- deliberately short
    struct.pack_into("<I", text, 48, LOAD_FILEOFF)   # offset
    struct.pack_into("<I", text, 64, 0x80000400)     # PURE_INSTRUCTIONS|SOME_INSTRUCTIONS
    sections += text

    if with_zerofill:
        bss = bytearray(sec_size)
        bss[0:5] = b"__bss"
        bss[16:22] = b"__DATA"
        struct.pack_into("<Q", bss, 32, LOAD_VADDR + LOAD_SIZE)   # addr, past __TEXT
        struct.pack_into("<Q", bss, 40, 0x100)                    # size
        struct.pack_into("<I", bss, 48, 0)                        # offset: none
        struct.pack_into("<I", bss, 64, 0x1)                      # S_ZEROFILL
        sections += bss

    blob = bytearray(LOAD_FILEOFF + LOAD_SIZE)
    blob[0:mach_header] = hdr
    blob[mach_header:mach_header + seg_cmd_size] = seg
    blob[mach_header + seg_cmd_size:mach_header + cmdsize] = sections
    blob[LOAD_FILEOFF:LOAD_FILEOFF + LOAD_SIZE] = _body(LOAD_SIZE)

    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "wb") as f:
        f.write(blob)
    return path


def write_fat_macho(path: str) -> str:
    """A fat/universal header, which the image layer must refuse with advice."""
    blob = bytearray(64)
    struct.pack_into(">I", blob, 0, 0xCAFEBABE)
    struct.pack_into(">I", blob, 4, 2)
    with open(path, "wb") as f:
        f.write(blob)
    return path


def fake_metadata(plaintext: bool = True, xor_key: int = 0) -> bytes:
    """A global-metadata.dat blob: valid magic, then filler. Optionally XORed."""
    header = bytearray(METADATA_MAGIC + struct.pack("<I", 29) + bytes(64))
    if plaintext:
        return bytes(header)
    return bytes(b ^ xor_key for b in header)


# ── package fixtures ────────────────────────────────────────────────────────

ANDROID_LIB = "lib/arm64-v8a/libil2cpp.so"
ANDROID_META = "assets/bin/Data/Managed/Metadata/global-metadata.dat"
GGM = "assets/bin/Data/globalgamemanagers"


def _ggm_blob(unity: str = "2022.3.62f2") -> bytes:
    return b"\x00" * 20 + unity.encode() + b"\x00" * 64


def write_apk(path: str, elf_bytes: bytes, metadata: bytes, package: str = "com.example.game",
              version: str = "1.2.3", unity: str = "2022.3.62f2") -> str:
    with zipfile.ZipFile(path, "w") as z:
        z.writestr(ANDROID_LIB, elf_bytes)
        z.writestr(ANDROID_META, metadata)
        z.writestr(GGM, _ggm_blob(unity))
        z.writestr("AndroidManifest.json", json.dumps(
            {"package_name": package, "version_name": version}))
    return path


def write_xapk(path: str, elf_bytes: bytes, metadata: bytes, package: str = "com.example.game",
               version: str = "1.2.3", unity: str = "2022.3.62f2") -> str:
    """XAPK: a zip of APKs plus a manifest -- one nesting level deeper than APK.

    Also serves `.apks`, which has the same shape (see `layout.XAPK`); pass a
    path ending in `.apks` to produce one.
    """
    base = os.path.join(os.path.dirname(path), "_base.apk.tmp")
    arm = os.path.join(os.path.dirname(path), "_arm64.apk.tmp")
    with zipfile.ZipFile(base, "w") as z:
        z.writestr(ANDROID_META, metadata)
        z.writestr(GGM, _ggm_blob(unity))
    with zipfile.ZipFile(arm, "w") as z:
        z.writestr(ANDROID_LIB, elf_bytes)
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("manifest.json", json.dumps(
            {"package_name": package, "version_name": version}))
        z.write(base, f"{package}.apk")
        z.write(arm, f"config.arm64_v8a.apk")
    os.remove(base)
    os.remove(arm)
    return path


def write_ipa(path: str, framework_bytes: bytes, metadata: bytes, package: str = "com.example.game",
              version: str = "1.2.3", app: str = "Game", shell_bytes: bytes | None = None) -> str:
    """IPA carrying two Mach-O binaries: the launch shell and the real framework.

    Magic alone cannot tell them apart -- both are Mach-O -- so path
    disambiguation is the only thing that picks the framework.
    """
    root = f"Payload/{app}.app"
    fw = f"{root}/Frameworks/UnityFramework.framework/UnityFramework"
    with zipfile.ZipFile(path, "w") as z:
        z.writestr(f"{root}/{app}", shell_bytes if shell_bytes is not None else framework_bytes)
        z.writestr(fw, framework_bytes)
        z.writestr(f"{root}/Info.plist", plistlib.dumps({
            "CFBundleIdentifier": package,
            "CFBundleShortVersionString": version,
            "CFBundleName": app,
        }))
        z.writestr(f"{root}/Data/Managed/Metadata/global-metadata.dat", metadata)
        z.writestr(f"{root}/Data/globalgamemanagers", _ggm_blob())
    return path


# ── FlatBuffers: a CMS library's shape ──────────────────────────────────────

def flatbuffers_rows(rows: int = 3, second_vector: bool = False,
                     names=None) -> bytes:
    """A root table holding a vector of item tables -- what a CMS `.bin` is.

    Laid out by hand, like the ELF and Mach-O above and for the same reason: a
    fixture built by a builder library would not test that the reader needs
    nothing but the encoding. `second_vector` adds a second, scalar vector to
    the root, which is the case where "which vector is the rows" stops having
    an obvious answer.
    """
    out = bytearray(b"\x00\x00\x00\x00")
    item_vt = len(out)
    out += struct.pack("<4H", 8, 12, 4, 8)          # 2 slots: i32, string
    root_vt = len(out)
    out += (struct.pack("<4H", 8, 12, 4, 8) if second_vector
            else struct.pack("<3H", 6, 8, 4))
    root = len(out)
    out += b"\x00" * (12 if second_vector else 8)
    vec = len(out)
    out += b"\x00" * (4 + rows * 4)
    other = len(out)
    if second_vector:
        out += struct.pack("<2i", 1, 7)
    items, strs = [], []
    for _ in range(rows):
        items.append(len(out))
        out += b"\x00" * 12
    for i in range(rows):
        while len(out) % 4:
            out.append(0)
        strs.append(len(out))
        text = (names[i] if names else f"item_{i}").encode()
        out += struct.pack("<I", len(text)) + text + b"\x00"

    struct.pack_into("<I", out, 0, root)
    struct.pack_into("<i", out, root, root - root_vt)
    struct.pack_into("<I", out, root + 4, vec - (root + 4))
    if second_vector:
        struct.pack_into("<I", out, root + 8, other - (root + 8))
    struct.pack_into("<I", out, vec, rows)
    for i, pos in enumerate(items):
        struct.pack_into("<I", out, vec + 4 + i * 4, pos - (vec + 4 + i * 4))
        struct.pack_into("<i", out, pos, pos - item_vt)
        struct.pack_into("<i", out, pos + 4, 100 + i)
        struct.pack_into("<I", out, pos + 8, strs[i] - (pos + 8))
    return bytes(out)


FB_SCHEMA = {"classes": {
    "Game.CMS.Db": {"slots": 1, "fields": {
        0: {"name": "Items", "fb_type": "offset", "cs_type": "Game.CMS.Item[]"}}},
    "Game.CMS.Item": {"slots": 2, "fields": {
        0: {"name": "Id", "fb_type": "int32", "cs_type": "int"},
        1: {"name": "Name", "fb_type": "offset", "cs_type": "string"}}},
}}
