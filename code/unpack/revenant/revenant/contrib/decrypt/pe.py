"""Wrap a header-stripped .NET image in a minimal PE so a decompiler can open it.

A recovered CDPH container is an assembly with its PE headers removed: RVAs
address the image directly, so file offset == RVA throughout. A loadable file
is then a matter of laying PE headers over the first page (nothing references
RVAs that low) and synthesising the CLI header the metadata directory needs.
The CLI header itself has to live inside the section -- a PE reader resolves
RVAs through the section table only -- so it is appended past the image.

`wrap_pe(image) -> bytes`. Raises if there is no metadata root.
"""

from __future__ import annotations

import struct

HEADERS = 0x1000
SECTION_ALIGN = 0x1000
FILE_ALIGN = 0x200


def wrap_pe(image: bytes) -> bytes:
    image = bytearray(image)
    meta = image.find(b"BSJB")
    if meta < 0:
        raise ValueError("no metadata root (BSJB) in image")
    meta_size = len(image) - meta

    cor20 = struct.pack(
        "<IHHIIIIIIIIIIIIIIII",
        72, 2, 5,                 # cb, runtime major/minor
        meta, meta_size,          # MetaData RVA/size
        1,                        # Flags: ILONLY
        0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
    )

    dos = bytearray(0x80)
    dos[0:2] = b"MZ"
    struct.pack_into("<I", dos, 0x3C, 0x80)

    cor20_rva = (len(image) + 15) & ~15
    image.extend(b"\x00" * (cor20_rva - len(image)))
    image.extend(b"\x00" * 72)
    size_of_image = (len(image) + SECTION_ALIGN - 1) & ~(SECTION_ALIGN - 1)

    coff = struct.pack("<IHHIIIHH", 0x00004550, 0x14C, 1, 0, 0, 0, 0xE0, 0x2102)
    opt = struct.pack("<HBBIIIIIIIIIHHHHHHIIIIHHIIIIII",
                      0x10B, 8, 0, len(image), 0, 0, 0, HEADERS, HEADERS,
                      0x10000000, SECTION_ALIGN, FILE_ALIGN, 4, 0, 0, 0, 4, 0,
                      0, size_of_image, HEADERS, 0, 3, 0,
                      0x100000, 0x1000, 0x100000, 0x1000, 0, 16)
    dirs = bytearray(16 * 8)
    struct.pack_into("<II", dirs, 14 * 8, cor20_rva, len(cor20))
    section = struct.pack("<8sIIIIIIHHI", b".text\0\0\0",
                          len(image) - HEADERS, HEADERS, len(image) - HEADERS, HEADERS,
                          0, 0, 0, 0, 0x60000020)

    head = bytearray(HEADERS)
    head[0:len(dos)] = dos
    p = 0x80
    for chunk in (coff, opt, dirs, section):
        head[p:p + len(chunk)] = chunk
        p += len(chunk)

    out = bytearray(image)
    out[0:HEADERS] = head
    out[cor20_rva:cor20_rva + len(cor20)] = cor20
    return bytes(out)
