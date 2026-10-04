"""Locate a bytecode-VM dispatcher by the shape of its dispatch sequence.

The address of the protector's VM changes every build; the instruction shape
does not. The CDPH dispatcher fetches an opcode, indexes a halfword jump table
and branches:

    ldrb w9, [x0], #1        ; fetch opcode
    adr  x10, <handler_base>
    ldrh w11, [x8, x9, lsl #1]
    add  x10, x10, x11, lsl #2
    br   x10

Matching those encodings (the `adr` immediate masked off) pins the dispatcher,
its handler base and -- when the adrp/add that builds the table pointer sits
just above -- the jump-table address, in one linear scan. Tuned on one family;
pass your own encodings for another.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass

from .emulator import SegmentedImage

LDRB_W9_X0_POST1 = 0x38401409     # ldrb w9, [x0], #1
BR_X10 = 0xD61F0140               # br x10


@dataclass
class Dispatcher:
    fetch_vaddr: int              # the ldrb (opcode fetch)
    handler_base: int             # adr target
    jump_table: int | None        # adrp/add target, if resolved


def _adr_immediate(word: int) -> int | None:
    """Signed 21-bit ADR immediate, or None if `word` is not `adr x10, .`."""
    if (word & 0x9F00001F) != (0x10000000 | 10):
        return None
    imm = (((word >> 5) & 0x7FFFF) << 2) | ((word >> 29) & 3)
    return imm - (1 << 21) if imm & (1 << 20) else imm


def _adrp_page(word: int) -> int | None:
    if (word & 0x9F000000) != 0x90000000:
        return None
    page = (((word >> 5) & 0x7FFFF) << 2) | ((word >> 29) & 3)
    return page - (1 << 21) if page & (1 << 20) else page


def find_dispatcher(data: bytes,
                    fetch_word: int = LDRB_W9_X0_POST1,
                    branch_word: int = BR_X10) -> list[Dispatcher]:
    """Every dispatcher-shaped site in an ELF image, by encoding not address."""
    image = SegmentedImage(data)
    out: list[Dispatcher] = []
    needle = struct.pack("<I", fetch_word)
    i = -1
    while True:
        i = data.find(needle, i + 1)
        if i < 0:
            break
        window = data[i:i + 24]
        if len(window) < 24:
            break
        words = struct.unpack("<6I", window)
        if branch_word not in (words[4], words[5]):
            continue
        vaddr = image.file_to_vaddr(i)
        if vaddr is None:
            continue
        imm = _adr_immediate(words[1])
        if imm is None:
            continue
        handler_base = vaddr + 4 + imm
        jump_table = None
        if i >= 8:
            adrp, add = struct.unpack("<2I", data[i - 8:i])
            page = _adrp_page(adrp)
            if page is not None and (add & 0xFFC00000) == 0x91000000:
                jump_table = (((vaddr - 8) & ~0xFFF) + (page << 12)) + ((add >> 10) & 0xFFF)
        out.append(Dispatcher(fetch_vaddr=vaddr, handler_base=handler_base, jump_table=jump_table))
    return out
