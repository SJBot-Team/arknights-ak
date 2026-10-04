"""Map an ELF's PT_LOAD segments for emulation.

Running the protector's own VM under Unicorn reproduces its transform exactly,
which is far cheaper than reimplementing a few hundred opcode handlers -- and
it keeps working when the packer changes the handlers between builds. The one
shared prerequisite is loading the image the way the loader would: every
PT_LOAD segment at its virtual address. That parse is here; the emulation loop,
the entry address, the key layout and the jump-table fill-in are the project's
(they are per-build facts).
"""

from __future__ import annotations

import struct
from dataclasses import dataclass


@dataclass
class Segment:
    vaddr: int
    memsz: int
    offset: int
    filesz: int


class SegmentedImage:
    """An ELF64's loadable segments, with file<->virtual address mapping."""

    def __init__(self, data: bytes):
        if data[:4] != b"\x7fELF":
            raise ValueError("not an ELF image")
        self.data = data
        phoff = struct.unpack_from("<Q", data, 0x20)[0]
        phentsize, phnum = struct.unpack_from("<HH", data, 0x36)
        self.segments: list[Segment] = []
        for i in range(phnum):
            o = phoff + i * phentsize
            if struct.unpack_from("<I", data, o)[0] != 1:   # PT_LOAD
                continue
            p_offset, p_vaddr, _pa, p_filesz, p_memsz = struct.unpack_from("<QQQQQ", data, o + 8)
            self.segments.append(Segment(p_vaddr, p_memsz, p_offset, p_filesz))
        if not self.segments:
            raise ValueError("no PT_LOAD segments")

    @property
    def image_size(self) -> int:
        """Bytes needed to hold every segment at its virtual address."""
        return max(s.vaddr + s.memsz for s in self.segments)

    def file_to_vaddr(self, file_off: int) -> int | None:
        for s in self.segments:
            if s.offset <= file_off < s.offset + s.filesz:
                return s.vaddr + (file_off - s.offset)
        return None

    def vaddr_to_file(self, vaddr: int) -> int | None:
        for s in self.segments:
            if s.vaddr <= vaddr < s.vaddr + s.filesz:
                return s.offset + (vaddr - s.vaddr)
        return None

    def map_into(self, write, base: int = 0) -> None:
        """Write each segment's file bytes to `write(base + vaddr, bytes)`.

        `write` is typically `uc.mem_write` from a Unicorn instance whose
        memory was mapped to at least `image_size` from `base`.
        """
        for s in self.segments:
            write(base + s.vaddr, self.data[s.offset:s.offset + s.filesz])
