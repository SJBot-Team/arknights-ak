"""Repairs for packed titles: importing a dumped metadata image, and making a
protected libil2cpp.so parseable by Cpp2IL.

A packed game ships ciphertext, so plaintext metadata can only come from a
running process. What comes out of memory is usually *almost* a valid file, and
a protected ELF usually *almost* parses — both need small, well-understood
repairs that are easy to get subtly wrong by hand.
"""
from __future__ import annotations

import collections
import hashlib
import math
import struct

METADATA_SANITY = 0xFAB11BAF

# A v31 header is sanity + version + 31 (offset, size) pairs = 256 bytes, so the
# first section starts at exactly 256. That self-identifying shape is what lets
# a zeroed header be recognised and rebuilt.
_V31_PAIRS = 31
_V31_HEADER = 8 + _V31_PAIRS * 8


def repair_metadata(data: bytes) -> tuple[bytes, list[str]]:
    """Repair a metadata image dumped from process memory.

    Returns the repaired bytes plus a list of what was repaired. Raises
    ValueError if the image is not recognisably IL2CPP metadata.
    """
    notes: list[str] = []
    if len(data) < _V31_HEADER:
        raise ValueError(f"too small to be metadata: {len(data)} bytes")

    # A dump usually starts at the container, not the metadata: the packer's own
    # header sits in front. Find where the metadata actually begins rather than
    # making the caller work it out.
    start = _find_metadata_start(data)
    if start:
        notes.append(f"skipped a {start}-byte container header")
    out = bytearray(data[start:])

    sanity, _version = struct.unpack_from("<II", out, 0)
    if sanity != METADATA_SANITY:
        # Some protections zero sanity+version once the runtime has parsed them.
        # The section table survives and identifies itself: the pairs are
        # contiguous and the first offset equals the header size.
        first_offset = struct.unpack_from("<I", out, 8)[0]
        if first_offset != _V31_HEADER:
            raise ValueError(
                f"not IL2CPP metadata: sanity is 0x{sanity:08X} and the first section "
                f"starts at {first_offset}, not {_V31_HEADER}"
            )
        cursor = first_offset
        for i in range(_V31_PAIRS):
            off, size = struct.unpack_from("<II", out, 8 + i * 8)
            if off != cursor or off + size > len(out):
                raise ValueError(
                    f"section {i} breaks the chain: expected offset {cursor}, got {off}"
                )
            cursor = off + size
        struct.pack_into("<II", out, 0, METADATA_SANITY, _V31_PAIRS)
        notes.append(f"rebuilt a zeroed sanity+version header (version {_V31_PAIRS})")
        end = cursor
    else:
        end = max(
            struct.unpack_from("<I", out, 8 + i * 8)[0] + struct.unpack_from("<I", out, 12 + i * 8)[0]
            for i in range(_V31_PAIRS)
        )

    if len(out) > end:
        notes.append(f"trimmed {len(out) - end:,} bytes of page padding")
        out = out[:end]

    # Pages the process never touched fault in from the file as ciphertext —
    # reading /proc/pid/mem does not run the app's own decrypt path. A
    # high-entropy page inside a string region sends Cpp2IL reading off the end
    # of the file, so zero them: that costs the values they held, which is
    # cheaper than losing the run.
    ciphertext = [
        p for p in range(len(out) // 4096)
        if _looks_like_ciphertext(out[p * 4096:(p + 1) * 4096])
    ]
    for p in ciphertext:
        out[p * 4096:(p + 1) * 4096] = b"\x00" * 4096
    if ciphertext:
        shown = ", ".join(hex(p * 4096) for p in ciphertext[:4])
        notes.append(
            f"zeroed {len(ciphertext)} page(s) the process never decrypted "
            f"({shown}{', ...' if len(ciphertext) > 4 else ''})"
        )
    return bytes(out), notes


def repair_elf_for_analysis(data: bytes) -> tuple[bytes, list[str]]:
    """Make a protected ELF survive Cpp2IL's symbol parsing.

    LibCpp2IL reads dynamic symbol names at `DT_STRTAB + nameOffset` as a *raw
    file offset*, but DT_STRTAB holds a virtual address. That is harmless while
    the two coincide; protected binaries often carry a large delta between them,
    and then every symbol name read lands past the end of the file and the run
    dies in ElfFile.ProcessSymbols.

    Rather than rewrite offsets the rest of the file depends on, mirror the
    string table at the address the buggy arithmetic will actually read, and pad
    so an unterminated trailing name cannot run off the end. The result is for
    analysis only — it is no longer a loadable library.
    """
    from io import BytesIO
    from elftools.elf.elffile import ELFFile

    notes: list[str] = []
    out = bytearray(data)
    elf = ELFFile(BytesIO(data))

    loads = [
        (s.header.p_vaddr, s.header.p_filesz, s.header.p_offset)
        for s in elf.iter_segments() if s.header.p_type == "PT_LOAD"
    ]

    def to_raw(vaddr: int) -> int | None:
        for va, size, off in loads:
            if va <= vaddr < va + size:
                return off + (vaddr - va)
        return None

    dynamic = elf.get_section_by_name(".dynamic")
    if dynamic is None:
        return bytes(out), notes
    tags = {}
    for tag in dynamic.iter_tags():
        if tag.entry.d_tag in ("DT_STRTAB", "DT_STRSZ"):
            tags[tag.entry.d_tag] = tag.entry.d_val if tag.entry.d_tag == "DT_STRSZ" else tag.entry.d_ptr

    strtab_va, strsz = tags.get("DT_STRTAB"), tags.get("DT_STRSZ")
    if strtab_va is not None and strsz:
        raw = to_raw(strtab_va)
        if raw is not None and raw != strtab_va:
            need = strtab_va + strsz + 1
            if len(out) < need:
                out.extend(b"\x00" * (need - len(out)))
            out[strtab_va:strtab_va + strsz] = data[raw:raw + strsz]
            notes.append(
                f"mirrored .dynstr at 0x{strtab_va:X} (vaddr) — it lives at 0x{raw:X} "
                f"in the file, a delta of 0x{strtab_va - raw:X}"
            )

    if not notes:
        # Even without the delta, a name at the very end with no terminator
        # ends the run; a page of padding is free insurance.
        out.extend(b"\x00" * 4096)
        notes.append("appended 4 KB of padding so a trailing symbol name terminates")
    return bytes(out), notes


def _find_metadata_start(data: bytes, window: int = 0x10000) -> int:
    """Offset where the IL2CPP metadata begins, skipping any container header."""
    limit = min(len(data) - _V31_HEADER, window)
    magic = struct.pack("<I", METADATA_SANITY)
    for off in range(0, limit, 4):
        if data[off:off + 4] == magic:
            return off
        # A wiped header still betrays itself: first section at exactly 256.
        if data[off:off + 8] == b"\x00" * 8 and struct.unpack_from("<I", data, off + 8)[0] == _V31_HEADER:
            return off
    return 0


def _looks_like_ciphertext(page: bytes) -> bool:
    if not page:
        return False
    counts = collections.Counter(page)
    n = len(page)
    entropy = -sum((c / n) * math.log2(c / n) for c in counts.values())
    return entropy > 7.5


def cache_name(data: bytes, suffix: str) -> str:
    return hashlib.sha256(data).hexdigest()[:16] + suffix
