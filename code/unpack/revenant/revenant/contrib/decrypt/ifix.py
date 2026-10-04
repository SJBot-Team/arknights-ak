"""Walk an IFix hot-patch file and list what it fixes.

An IFix patch is a plain BinaryWriter stream of eleven sections (see the
project's ref-02 note for the field-by-field layout). Section 7 (anonymous
closures) is not self-describing -- how many ints follow each interface depends
on reflecting that interface in the host assembly -- so when it cannot be walked
in order, the fix table (section 10) is located by brute force instead; its
syntax is constrained enough that a false match is implausible.

Opcode values are shuffled per build, so the disassembler takes the opcode map
from the game's own `IFix.Core.Code` enum rather than from upstream IFix. The
map, and the patch file, are inputs; nothing game-specific lives here.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass, field


class Reader:
    def __init__(self, data: bytes, pos: int = 0):
        self.d, self.p = data, pos

    def u8(self) -> int:
        v = self.d[self.p]
        self.p += 1
        return v

    def i32(self) -> int:
        v = struct.unpack_from("<i", self.d, self.p)[0]
        self.p += 4
        return v

    def u64(self) -> int:
        v = struct.unpack_from("<Q", self.d, self.p)[0]
        self.p += 8
        return v

    def string(self) -> str:
        n = s = 0
        while True:
            b = self.d[self.p]
            self.p += 1
            n |= (b & 0x7F) << s
            if not b & 0x80:
                break
            s += 7
        v = self.d[self.p:self.p + n].decode("utf-8", "replace")
        self.p += n
        return v


def bare(aqn: str) -> str:
    """Just the type name, without assembly or version."""
    return aqn.split(",")[0]


@dataclass
class MethodRef:
    decl_type: int
    name: str
    params: list           # ints (type ids) or strings (generic params)


def _read_methodref(r: Reader, ntypes: int) -> MethodRef:
    """Read a MethodRef, validating every id so a wrong guess fails loudly."""
    generic = r.u8()
    if generic not in (0, 1):
        raise ValueError("isGenericInstance")
    decl = r.i32()
    if not 0 <= decl < ntypes:
        raise ValueError("declaringTypeId")
    name = r.string()
    if not name or len(name) > 200 or not all(32 <= ord(c) < 127 for c in name):
        raise ValueError("methodName")
    if generic:
        n = r.i32()
        if not 0 <= n <= 32:
            raise ValueError("genericArgCount")
        for _ in range(n):
            if not 0 <= r.i32() < ntypes:
                raise ValueError("genericArg")
    n = r.i32()
    if not 0 <= n <= 64:
        raise ValueError("paramCount")
    params: list = []
    for _ in range(n):
        if generic and r.u8():
            params.append(r.string())
        else:
            t = r.i32()
            if not 0 <= t < ntypes:
                raise ValueError("paramType")
            params.append(t)
    return MethodRef(decl, name, params)


@dataclass
class IFixPatch:
    magic: int = 0
    bridge_type: str = ""
    types: list = field(default_factory=list)
    methods: list = field(default_factory=list)     # [(code, eh)] per slot
    externs: list = field(default_factory=list)      # [MethodRef]
    strings: list = field(default_factory=list)
    fields: list = field(default_factory=list)       # [(decl, name)]
    fixes: list = field(default_factory=list)        # [(MethodRef, method_slot)]

    @classmethod
    def parse(cls, data: bytes) -> "IFixPatch":
        r = Reader(data)
        p = cls(magic=r.u64())
        p.bridge_type = bare(r.string())
        p.types = [r.string() for _ in range(r.i32())]
        nt = len(p.types)
        for _ in range(r.i32()):
            code = [(r.i32(), r.i32()) for _ in range(r.i32())]
            eh = [tuple(r.i32() for _ in range(6)) for _ in range(r.i32())]
            p.methods.append((code, eh))
        p.externs = [_read_methodref(r, nt) for _ in range(r.i32())]
        p.strings = [r.string() for _ in range(r.i32())]
        for _ in range(r.i32()):
            isnew, decl, name = r.u8(), r.i32(), r.string()
            if isnew:
                r.i32(), r.i32()
            p.fields.append((decl, name))
        for _ in range(r.i32()):        # section 6: VM static fields
            r.i32(), r.i32()
        p.fixes = cls._read_fixes(r, data, nt)
        return p

    @staticmethod
    def _read_fixes(r: Reader, data: bytes, ntypes: int) -> list:
        """Section 7 in order if it is walkable, else brute-force section 10."""
        nanon = r.i32()
        try:
            for _ in range(nanon):
                for _ in range(r.i32()):
                    r.i32()
                r.i32(), r.i32()
                if r.i32() != 0:
                    raise ValueError("interfaceCount != 0 (section 7 not self-describing)")
                for _ in range(r.i32()):
                    r.i32()
            r.string()                  # section 8
            r.string()                  # section 9: IDMAP suffix
            return [(_read_methodref(r, ntypes), r.i32()) for _ in range(r.i32())]
        except Exception:
            _off, fixes = _find_fix_table(data, r.p, ntypes)
            return fixes or []


def _find_fix_table(data: bytes, start: int, ntypes: int):
    """Locate section 10 by trying to parse it, then 11, and land exactly on EOF."""
    for off in range(start, len(data) - 8):
        try:
            p = Reader(data, off)
            n = p.i32()
            if not 1 <= n <= 500:
                continue
            got = [(_read_methodref(p, ntypes), p.i32()) for _ in range(n)]
            nnew = p.i32()
            if not 0 <= nnew <= 500:
                continue
            for _ in range(nnew):
                p.string()
            if p.p == len(data):
                return off, got
        except Exception:
            continue
    return None, None
