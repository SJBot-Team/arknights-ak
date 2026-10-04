"""FlatBuffers: shape without a schema, the schema out of the generated code,
and the data decoded against it.

The symmetric half of `protobuf.py`. A protobuf message at least numbers its
fields on the wire; a FlatBuffers table carries no names *and* no types -- a
vtable says "slot 3 lives at this offset" and stops there. The `.fbs` never
ships. So a title whose whole numeric layer is FlatBuffers reads as megabytes of
anonymous slots until the schema is put back.

Three layers, each usable on its own:

**1. Walk it with no schema at all** (`walk`, `strings`). The encoding is
self-describing about *shape*: the slot count and which slots are set come
straight out of the vtable, and a string is recognisable by its length word and
its NUL. Types are not encoded, so they are inferred -- by trying each reading
and keeping the ones that stay inside the buffer and land on a plausible object.
Everything this layer says about a type is marked `inferred`; that is the whole
reason the flag exists.

**2. Recover the schema from the shipped code** (`recover_schema`). Each
generated class's `SerializeToBuffer` writes the slots one after another, and
its ISIL has a fixed shape:

    031 Move W1, 4                          <- StartObject(4)
    033 Call FlatBufferBuilder.StartObject
    034 Move W2, [X20+40]                   <- the value comes from this+0x28
    036 Move W1, W31                        <- W31 reads as zero: slot 0
    039 Call FlatBufferBuilder.AddInt       <- and the call names the type

Nothing is guessed: the `Add*` method name *is* the type, and `this + 0x28` is
the join key onto the reconstructed C# (`private CurrencyId m_id; //Field
offset: 0x28`). This is the same shape `pb-tags` uses to pull field numbers out
of a `MergeFrom` switch. Declaration order is *not* usable as a fallback -- one
reference title declares one field but calls `StartObject(3)`, and another's
three fields land on slots 0, 2 and 3, because a base class's own table is
nested rather than flattened and its position moves from class to class.

A **union** is two slots, not one: for `x:Any` the generator emits `x_type`
holding the member tag and `x` holding the value, giving the type slot the lower
id. Recovery pairs them structurally -- the serialiser reads the field once and
hands it to two *different* helpers, which is what tells a union apart from the
other way one read reaches two slots -- and `Reader` returns them as the one
field they are, `{"type": [...], "value": ...}`.

The tag is not a label printed beside the value: it *selects* the class the
value is decoded as, per element for a repeated union. So the member list is
what turns a union from a probe into a concrete type, and it is a list of
concrete class names that is not in the buffer -- the caller's `union_members`,
like `guid_types` and `containers`. Without it the tags are still reported as
numbers, the values are probed, and `Reader.notes` says that is why.

**3. Decode against the recovered schema** (`Reader`). With slot names and
declared types a number comes out labelled or not at all. One thing stays
inferred even here: a slot typed `offset` holds a relative pointer and the
encoding does not say whether the target is a string, a vector or a table. The
declared C# type decides it where it resolves; where it does not, the target is
probed the way layer 1 does and the value is marked.

No game facts (#50): the generated classes' namespace, the database root types,
which `.bin` holds which root, and any container-type convention
(`SomeTable<X>` meaning "a one-slot table wrapping the item vector") are the
caller's -- passed in as directories, bytes, a schema object and `containers=`.
"""

from __future__ import annotations

import json
import os
import re
import struct
from dataclasses import dataclass, field

# The marker that prefixes any value this module had to probe rather than read
# off a declared type. "looks like a string" and "is declared a string" are two
# different claims and must not print the same.
INFERRED = "?"


# ── layer 1: the encoding, with no schema ───────────────────────────────────


class Buffer:
    """Bounds-checked little-endian reads. Every accessor answers None off the
    end rather than raising: half of type inference *is* the out-of-range."""

    def __init__(self, data: bytes):
        self.d = data
        self.n = len(data)

    def u8(self, p: int):
        return self.d[p] if 0 <= p < self.n else None

    def i16(self, p: int):
        return struct.unpack_from("<h", self.d, p)[0] if 0 <= p <= self.n - 2 else None

    def u16(self, p: int):
        return struct.unpack_from("<H", self.d, p)[0] if 0 <= p <= self.n - 2 else None

    def i32(self, p: int):
        return struct.unpack_from("<i", self.d, p)[0] if 0 <= p <= self.n - 4 else None

    def u32(self, p: int):
        return struct.unpack_from("<I", self.d, p)[0] if 0 <= p <= self.n - 4 else None

    def f32(self, p: int):
        return struct.unpack_from("<f", self.d, p)[0] if 0 <= p <= self.n - 4 else None

    def root(self) -> int:
        """The root table offset: a plain uoffset at the start of the buffer."""
        return self.u32(0) or 0


def vtable_header(buf: Buffer, table: int) -> tuple[int, int | None]:
    """(declared slot count, vtable position); the position is None if not one.

    The header alone, because that is all most callers need: `as_table` asks
    only *whether* a position is a table, and built the whole offset list to
    find out. A probe runs it over bytes that are usually not a table, where the
    declared length is arbitrary, so that list could be 32,765 entries nobody
    reads. See `research/flatbuffers-read-profile.md` for what that cost.

    Split, not tightened: rejecting implausible vtables outright would be a
    different set of answers, and this is a speed change, not a behaviour one.
    A count can therefore come back *negative* -- a `vt_len` of 2 clears every
    guard here and yields -1 -- and callers must treat that as this module
    always has, which is as a truthy "yes, a table".
    """
    soffset = buf.i32(table)
    if soffset is None:
        return 0, None
    vt = table - soffset
    if not (0 <= vt < buf.n - 4):
        return 0, None
    vt_len = buf.u16(vt)
    if not vt_len or vt_len % 2 or vt + vt_len > buf.n:
        return 0, None
    return (vt_len - 4) // 2, vt


def vtable(buf: Buffer, table: int) -> tuple[int, list]:
    """(declared slot count, [absolute field position or None]) for one table."""
    slots, vt = vtable_header(buf, table)
    # `<= 0`, not `not slots`: a declared length of 2 yields -1, which is truthy
    # and would reach `struct` as a negative repeat count. The loop this replaced
    # ran `range(-1)` and produced an empty list, so an empty list is the answer.
    if slots <= 0 or vt is None:
        return slots, []
    # One unpack for the whole offset array rather than one call per slot: the
    # bytes are contiguous and `struct` already knows how to read a run of them.
    # In bounds by construction -- `vt + vt_len <= n` and `vt_len == 4 + 2*slots`.
    offsets = struct.unpack_from(f"<{slots}H", buf.d, vt + 4)
    return slots, [table + off if off else None for off in offsets]


def as_string(buf: Buffer, pos: int, limit: int = 120):
    """A string field holds a relative offset to `<u32 len><bytes><NUL>`."""
    rel = buf.u32(pos)
    if not rel:
        return None
    at = pos + rel
    if not (0 <= at <= buf.n - 4):
        return None
    ln = buf.u32(at)
    if ln is None or ln > buf.n - at - 4 or ln > 1 << 20:
        return None
    raw = buf.d[at + 4:at + 4 + ln]
    if buf.u8(at + 4 + ln) != 0:
        return None
    try:
        s = raw.decode("utf-8")
    except UnicodeDecodeError:
        return None
    if any(ord(c) < 9 for c in s):
        return None
    return s[:limit]


def as_vector(buf: Buffer, pos: int):
    """(count, start of the element area) if the slot reads as a vector."""
    rel = buf.u32(pos)
    if not rel:
        return None
    at = pos + rel
    if not (0 <= at <= buf.n - 4):
        return None
    count = buf.u32(at)
    if count is None or count > (buf.n - at) or count > 1 << 22:
        return None
    return count, at + 4


def as_table(buf: Buffer, pos: int):
    """A table field holds a relative offset to another table."""
    rel = buf.u32(pos)
    if not rel:
        return None
    at = pos + rel
    if not (0 <= at < buf.n - 4):
        return None
    slots, _vt = vtable_header(buf, at)
    return at if slots else None


@dataclass(frozen=True)
class Reading:
    """What a slot's bytes could be, and how confidently.

    `inferred` is always True out of layer 1 -- nothing there has a declared
    type to compare against. It is the field that keeps "this looks like a
    string" from being written down as "this is a string".
    """

    kind: str          # string | vector | table | scalar
    value: object      # str | (count, element kind) | table offset | {width: value}
    inferred: bool = True

    @property
    def marker(self) -> str:
        """The one-line form, prefixed so an inferred value never reads as read."""
        if self.kind == "string":
            return f"{INFERRED}string:{self.value}"
        if self.kind == "vector":
            return f"{INFERRED}vector[{self.value[0]}]"
        if self.kind == "table":
            return f"{INFERRED}table@0x{self.value:x}"
        widths = self.value if isinstance(self.value, dict) else {}
        return f"{INFERRED}scalar:{widths.get('i32', self.value)}"


def probe(buf: Buffer, pos: int) -> Reading:
    """Every reading the slot supports, most specific first. A guess, labelled."""
    s = as_string(buf, pos)
    if s is not None:
        return Reading("string", s)
    vec = as_vector(buf, pos)
    tab = as_table(buf, pos)
    if vec and vec[0] > 0:
        # A vector of tables and a vector of scalars start identically; probe
        # the first element to tell them apart.
        first = as_table(buf, vec[1]) or as_string(buf, vec[1])
        return Reading("vector", (vec[0], "table/string" if first else "scalar"))
    if tab:
        return Reading("table", tab)
    widths = {"i32": buf.i32(pos), "u8": buf.u8(pos), "i16": buf.i16(pos)}
    f = buf.f32(pos)
    if f is not None and abs(f) < 1e7 and (abs(f) > 1e-4 or f == 0.0):
        widths["f32"] = f
    return Reading("scalar", widths)


@dataclass(frozen=True)
class Slot:
    index: int
    pos: int
    reading: Reading


@dataclass
class TableShape:
    offset: int
    slots: int                                  # what the vtable declares
    present: list = field(default_factory=list)  # only the slots that are set
    children: list = field(default_factory=list)  # nested TableShape


def walk(data: bytes, table: int | None = None, max_depth: int = 1) -> TableShape:
    """The shape of a table and, to `max_depth`, of the tables under it."""
    buf = Buffer(data)
    return _walk(buf, buf.root() if table is None else table, 0, max_depth, set())


def _walk(buf: Buffer, table: int, depth: int, max_depth: int, seen: set) -> TableShape:
    slots, fields = vtable(buf, table)
    shape = TableShape(offset=table, slots=slots)
    seen.add(table)
    for i, pos in enumerate(fields):
        if pos is None:
            continue
        shape.present.append(Slot(i, pos, probe(buf, pos)))
        if depth < max_depth:
            sub = as_table(buf, pos)
            if sub and sub not in seen:
                shape.children.append(_walk(buf, sub, depth + 1, max_depth, seen))
    return shape


_PRINTABLE_RUN = re.compile(rb"[\x20-\x7e]{3,}")


def strings(data: bytes) -> list:
    """Every well-formed FlatBuffers string in the buffer, in address order.

    Scanned by structure, not by the usual printable-run heuristic: a candidate
    counts only when the four bytes before it are its own length and the byte
    after it is NUL. That drops the false hits a plain `strings` produces on
    packed numeric vectors.
    """
    buf = Buffer(data)
    out, pos = [], 0
    while True:
        m = _PRINTABLE_RUN.search(data, pos)
        if not m:
            return out
        start = m.start()
        pos = start + 1
        if start < 4:
            continue
        ln = buf.u32(start - 4)
        if ln is None or start + ln > buf.n:
            continue
        if buf.u8(start + ln) != 0:
            continue
        try:
            out.append((start, data[start:start + ln].decode("utf-8")))
        except UnicodeDecodeError:
            continue


# ── layer 2: the schema, out of the generated code ──────────────────────────

# The Add* method name *is* the type. Nothing here is inferred.
ADD_TYPES = {
    "AddInt": "int32", "AddUint": "uint32", "AddBool": "bool",
    "AddFloat": "float32", "AddLong": "int64", "AddDouble": "float64",
    "AddOffset": "offset", "AddShort": "int16", "AddUshort": "uint16",
    "AddByte": "uint8", "AddSbyte": "int8",
}

TYPE_LINE = re.compile(r"^Type: (\S+)")
METHOD = re.compile(r"^Method: (.+)$")
# ISIL rows look like `\t034 Move W2, [X20+40]`
ROW = re.compile(r"^\s*(\d+) (.*)$")
REG = r"([WXSDVQ])(\d+)"
LOAD = re.compile(rf"^Move {REG}, \[{REG}([+-]\d+)?\]$")
STORE = re.compile(rf"^Move \[{REG}([+-]\d+)?\], {REG}$")
MOVE_REG = re.compile(rf"^Move {REG}, {REG}$")
MOVE_IMM = re.compile(rf"^Move {REG}, (\d+)$")
ADD_IMM = re.compile(rf"^Add {REG}, {REG}, (\d+)$")
CALL = re.compile(r"^Call ([^,]+)(?:, (.*))?$")
CALL_ADDR = re.compile(r"^0x([0-9A-Fa-f]+)$")
ARG_REG = re.compile(REG)

# Register 31 is deliberately spelled twice: in ARM64 the same encoding is the
# zero register in a value position and the stack pointer in an address one. The
# code never has to tell them apart by the constant -- the operand position it is
# matched in already has -- so the two names are there to say which role is meant
# at each site, not to compare differently.
ZERO_REG = ("g", 31)
SP_REG = ("g", 31)
THIS_REG = ("g", 0)    # X0 on entry

SERIALIZER = "SerializeToBuffer"
BUILDER_MARK = "FlatBufferBuilder.StartObject"
SERIALIZER_SIG = f"System.Int32 {SERIALIZER}"


def _reg(letter: str, num: str):
    """W/X are the general file; S/D/V/Q are the FP file. S0 is not W0."""
    return ("v" if letter in "SDVQ" else "g", int(num))


def parse_isil(text: str) -> list:
    """(signature, [(index, op)]) per method block in one Cpp2IL IsilDump file."""
    out, sig, rows, in_isil = [], None, [], False
    for line in text.splitlines():
        m = METHOD.match(line)
        if m:
            if sig:
                out.append((sig, rows))
            sig, rows, in_isil = m.group(1), [], False
            continue
        if line.strip() == "ISIL:":
            in_isil = True
            continue
        if line.strip() == "Disassembly:":
            in_isil = False
            continue
        if in_isil:
            r = ROW.match(line)
            if r:
                rows.append((int(r.group(1)), r.group(2).strip()))
    if sig:
        out.append((sig, rows))
    return out


def trace_slots(rows) -> tuple:
    """Slots written by one `SerializeToBuffer` body, plus the declared count.

    A single forward pass carrying, per register and per stack slot, where the
    value came from. Provenance is `("field", offset)`, `("base", callee)`,
    `("thiscall", addr)` or None. A call propagates the provenance of whichever
    argument had one -- the generated helpers (CreateVector,
    SerializeRepeatedReference) take the field and hand back the offset to
    store, so the field that offset *describes* survives the call.

    Two shapes make the naive version miss a third of the slots:

      - the base class's table is not kept in a register. It goes
        `Call Base.SerializeToBuffer` -> `ObjectOffset..ctor(&stack, W0)` ->
        `Move W2, [X31+12]`, so the stack slot has to be modelled too.
      - `AddFloat` passes its value in the FP file (`Move S0, [X20+44]` then
        `Call AddFloat, X0, X1, V0, V1`). S0 is not W0, and the value is not
        always the third *general* register -- so the value register is read
        off the call's own argument list rather than assumed.
    """
    prov, imm, stack = {}, {}, {}
    this_regs = {THIS_REG}
    nslots, slots = None, []
    pending = []            # stack offsets taken as `&out` since the last call

    def define(dst, is_this=False, wide=True):
        """Redefining a register ends whatever it used to alias.

        X0 holds `this` on entry but is also the return register, so leaving it
        in the alias set forever makes every call result look like `this`. Once
        that happens a later `[Xn]` load reads as field 0, which is truthy, and
        it wins the provenance race against the real field argument -- 17 of one
        reference class's 20 slots went unresolved exactly this way.

        `wide` is what keeps that from over-correcting. `this` is a 64-bit
        pointer, so it only ever lives in an X register; a write to the W half
        is a different, 32-bit variable that the compiler parked in the same
        register on a branch this linear pass also walks. One class reuses W20
        for a string offset on the null-string path while X20 still holds `this`
        on the path that reaches the Add -- killing the alias there loses both
        of its slots.
        """
        if is_this:
            this_regs.add(dst)
        elif wide:
            this_regs.discard(dst)

    for _, op in rows:
        m = ADD_IMM.match(op)
        if m:
            dst, src, off = (_reg(m.group(1), m.group(2)),
                             _reg(m.group(3), m.group(4)), int(m.group(5)))
            if src == SP_REG:
                prov[dst] = ("stackaddr", off)
                pending.append(off)
            elif src in this_regs:
                # Address-of an inline struct field, not a load: a `TimeSpan` or
                # a `Vector2Int` sits in the object, so the generated code calls
                # through `&this->field`. The slot still describes that field.
                prov[dst] = ("field", off)
            else:
                prov[dst] = None
            imm.pop(dst, None)
            define(dst)
            continue
        m = STORE.match(op)
        if m:
            base, off = _reg(m.group(1), m.group(2)), int(m.group(3) or 0)
            src = _reg(m.group(4), m.group(5))
            if base == SP_REG:
                stack[off] = None if src == ZERO_REG else prov.get(src)
            continue
        m = LOAD.match(op)
        if m:
            dst = _reg(m.group(1), m.group(2))
            base, off = _reg(m.group(3), m.group(4)), int(m.group(5) or 0)
            if base == SP_REG:
                prov[dst] = stack.get(off)
            elif base in this_regs:
                prov[dst] = ("field", off)
            else:
                prov[dst] = None
            imm.pop(dst, None)
            define(dst, wide=m.group(1) not in "WS")
            continue
        m = MOVE_REG.match(op)
        if m:
            dst, src = _reg(m.group(1), m.group(2)), _reg(m.group(3), m.group(4))
            wide = m.group(1) not in "WS"
            if src == ZERO_REG:
                # W31 in a value position is the zero register, not a variable.
                imm[dst], prov[dst] = 0, None
                define(dst, wide=wide)
            else:
                # A copy always takes the source's provenance, including None.
                # Keeping the old value when the source has none would close the
                # last two unresolved slots on the reference title -- and corrupt
                # 1,511 others, because stale provenance then leaks across every
                # branch. Two honest gaps beat 1,511 confident errors.
                prov[dst] = prov.get(src)
                define(dst, is_this=src in this_regs, wide=wide)
                if src in imm:
                    imm[dst] = imm[src]
                else:
                    imm.pop(dst, None)
            continue
        m = MOVE_IMM.match(op)
        if m:
            dst = _reg(m.group(1), m.group(2))
            imm[dst] = int(m.group(3))
            prov[dst] = None
            define(dst, wide=m.group(1) not in "WS")
            continue
        m = CALL.match(op)
        if not m:
            continue
        callee, args = m.group(1).strip(), m.group(2) or ""
        argregs = [_reg(l, n) for l, n in ARG_REG.findall(args)]
        short = callee.rsplit(".", 1)[-1]
        ret = ("g", 0)

        if short == "StartObject":
            nslots = imm.get(("g", 1))
        elif short in ADD_TYPES:
            # Args are (builder, slot, value, default); read the value register
            # off the list so the FP-file calls resolve like the rest.
            value = argregs[2] if len(argregs) > 2 else ("g", 2)
            slots.append({"slot": imm.get(("g", 1)),
                          "type": ADD_TYPES[short],
                          "source": prov.get(value)})
        elif short == SERIALIZER:
            prov[ret] = ("base", callee.rsplit(".", 1)[0])
            imm.pop(ret, None)
            define(ret)
        else:
            # A call carries provenance forward two ways. Normally the result
            # describes whichever argument had provenance -- the helpers
            # (CreateVector, SerializeReference) take the field and hand back the
            # offset that stands for it. But some write through a pointer
            # instead: `ObjectOffset..ctor(&stack, base)` parks the base table's
            # offset, and one config class unwraps each identified variable with
            # `helper(field, &stack)` and reads the float back out. Both are the
            # same shape once stack addresses are provenance.
            carried = next((prov[a] for a in argregs
                            if prov.get(a) and prov[a][0] != "stackaddr"), None)
            if carried is not None and carried[0] == "thiscall":
                # Remember which helper consumed it. A generic container calls
                # the same `GetItems()` twice and feeds the results to
                # `SerializeRepeatedUnion` and `SerializeRepeatedUnionTypes` --
                # the FlatBuffers union pattern, values in one slot and type tags
                # in the next. Without this both slots read `GetItems()` and the
                # pair is indistinguishable.
                helper = CALL_ADDR.match(callee)
                if helper:
                    carried = ("thiscall", carried[1], int(helper.group(1), 16))
            # `thiscall` always carries a helper slot, None when there was none,
            # so the reader never has to ask how long the tuple is.
            if carried is None:
                # No argument carries a field, but one of them *is* `this`: the
                # value comes from an accessor. A generic container reaches its
                # items through `GetItems()` rather than loading the field
                # inline, which is what generic sharing does to every container
                # type. Record the callee so the field can be read out of it.
                target = CALL_ADDR.match(callee)
                if target and any(a in this_regs for a in argregs):
                    carried = ("thiscall", int(target.group(1), 16), None)
            # `pending`, not just the listed arguments: Cpp2IL's ISIL prints an
            # incomplete argument list, and the out-param pointer is exactly what
            # it tends to drop -- `Call 0x3E1B9A8, X0` names only the value,
            # never the `Add X1, X31, 8` that receives the result. Any stack
            # address taken since the previous call is a candidate.
            outparams = sorted({prov[a][1] for a in argregs
                                if prov.get(a) and prov[a][0] == "stackaddr"}
                               | set(pending))
            for off in outparams:
                stack[off] = carried
            # A call that writes an out-param returns void or a status, not the
            # value -- claiming otherwise would name the next slot wrongly.
            result = None if outparams else carried
            # A call returns in X0 *or* in V0 depending on the return type, and
            # ISIL does not say which -- `TimeSpan.get_TotalSeconds` hands back a
            # double in D0 with nothing written to X0. Marking both is safe: only
            # the register the callee actually returned in gets read, and a stale
            # FP provenance would otherwise survive into the next AddFloat.
            for r in (ret, ("v", 0)):
                prov[r] = result
                imm.pop(r, None)
            define(ret)
        pending.clear()
        # Every call clobbers the argument registers' immediates.
        for r in (("g", 1), ("g", 2), ("g", 3), ("v", 0), ("v", 1)):
            imm.pop(r, None)
    return nslots, slots


# Matched against the line with its leading tabs stripped; the caller checks the
# indent separately, so one pattern serves every nesting level.
FIELD_DECL = re.compile(
    r"^(?:\[[^\]]*\]\s*)?(?:private|public|internal|protected)\s+"
    r"(?:static\s+|readonly\s+)*(.+?)\s+(\w+);\s*//Field offset: (0x[0-9A-Fa-f]+)")
CLASS_DECL = re.compile(
    r"^(?:public|private|internal|protected)\s+"
    r"(?:sealed\s+|abstract\s+|static\s+)*class\s+(\w+)"
    r"(?:<[^>]*>)?(?:\s*:\s*(.+))?")


def csharp_fields(text: str, nested=()) -> tuple:
    """(declared base, [{name, cs_type, offset}]) for one class in the file.

    `nested` names a class nested inside the outer one -- Cpp2IL writes those to
    their own `X_NestedType_Y.txt` on the ISIL side, but the C# keeps `Y` inside
    `X.cs`, one indent level deeper. Reading the wrong level is not merely
    empty, it is wrong: on the reference title `DepthComponent` and its nested
    `Definition` both declare `m_layer`, at 0x18 and 0x48 respectively.

    Indentation is the nesting: the target class's own fields sit at
    `len(nested) + 1` tabs, and anything deeper belongs to a compiler-generated
    type (`<>c` and friends) holding delegate caches, not data.
    """
    want_depth = len(nested) + 1
    base, fields = None, []
    entered = []            # class names on the path down to the target
    for line in text.splitlines():
        stripped = line.lstrip("\t")
        indent = len(line) - len(stripped)
        c = CLASS_DECL.match(stripped)
        if c:
            name = c.group(1)
            if indent == len(entered) and (
                    (indent == 0) or (indent <= len(nested) and name == nested[indent - 1])):
                entered = entered[:indent] + [name]
                if indent == want_depth - 1:
                    base = (c.group(2) or "").split(",")[0].strip() or None
            continue
        if len(entered) != want_depth or indent != want_depth:
            continue
        f = FIELD_DECL.match(stripped)
        # `<x>k__BackingField` is the compiler's; `__p` is FlatBuffers' own Table
        # handle from IFlatbufferObject. Neither is ever a serialised field, and
        # leaving `__p` in the list shifted every type-order match in one generic
        # wrapper by one -- naming the version string `__p`.
        if f and not f.group(2).startswith(("<", "__")):
            fields.append({"name": f.group(2), "cs_type": f.group(1).strip(),
                           "offset": int(f.group(3), 16)})
    return base, fields


MAX_BASE_DEPTH = 12


def index_sources(src_root: str) -> dict:
    """Class stem -> .cs path, for following a base chain across files."""
    index: dict = {}
    for dirpath, _, names in os.walk(src_root):
        for name in names:
            if not name.endswith(".cs"):
                continue
            stem, path = name[:-3], os.path.join(dirpath, name)
            # Keyed by the exact stem, backtick and all. Folding `Table` and
            # ``Table`1`` together makes both ambiguous, and the base chain then
            # stops at the very class it needed to climb. A name genuinely
            # claimed by two files resolves to neither: a wrong base is a wrong
            # offset, and a wrong offset is a wrong name.
            index[stem] = None if stem in index and index[stem] != path else path
    return index


def guid_types(cs_index: dict, roots) -> list:
    """Class names that are really a raw GUID reference, found by base chain.

    Some framework types serialise as a 16-byte GUID vector rather than as a
    table, and anything whose base chain reaches one of them is one too. Derived
    rather than hardcoded: the roster grows with the game, and a stale
    hand-written list fails silently. `roots` is the caller's -- which types
    those are is a fact about that CMS, not about FlatBuffers.
    """
    found = set(roots)
    for _ in range(MAX_BASE_DEPTH):          # transitive closure, bounded
        grew = False
        for name, path in cs_index.items():
            bare = name.split("`")[0]
            if bare in found or not path:
                continue
            base, _ = csharp_fields(_read(path))
            if base and base.split("<")[0].strip() in found:
                found.add(bare)
                grew = True
        if not grew:
            break
    return sorted(found)


def _read(path: str) -> str:
    with open(path, encoding="utf-8", errors="replace") as f:
        return f.read()


def read_with_bases(cs_path: str, nested, cs_index: dict) -> tuple:
    """(base, {offset: field}, [ordered fields], [own fields]), inheritance included.

    A class only lists its own fields, but IL2CPP lays the base's out in the same
    object and `SerializeToBuffer` reads them at their absolute offsets. A
    generic container is the clean case: its own file declares one field at 0x0,
    while the slot it serialises comes from a field at 0x58 in its base. Without
    walking up, that slot has no name.

    The child is read last so it wins any offset collision.
    """
    chain, seen = [], set()
    path, sub = cs_path, nested
    for _ in range(MAX_BASE_DEPTH):
        if not path or path in seen or not os.path.exists(path):
            break
        seen.add(path)
        base, fields = csharp_fields(_read(path), sub)
        chain.append((base, fields))
        if not base:
            break
        # A generic base is indexed under the bare name, and a base is never a
        # nested type here.
        path, sub = cs_index.get(base.split("<")[0].strip()), ()
    if not chain:
        return None, {}, [], []
    by_offset: dict = {}
    for _, fields in reversed(chain):
        by_offset.update({f["offset"]: f for f in fields})
    # Declaration order, base first -- the order the serialiser writes slots in,
    # which is all the type-order fallback has to go on.
    ordered = [f for _, fields in reversed(chain) for f in fields]
    return chain[0][0], by_offset, ordered, chain[0][1]


def load_rva_index(isil_root: str) -> dict:
    """RVA -> {class, file, signature}, as Cpp2IL wrote it beside the dumps."""
    path = os.path.join(os.path.dirname(isil_root.rstrip(os.sep)), "rva_index.json")
    if not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def accessor_name(addr: int, rva_index: dict, via=None):
    """{name, returns} for a call target, straight out of Cpp2IL's rva index.

    `via` is the helper that consumed the result, appended when it is what tells
    two otherwise identical slots apart.
    """
    entry = rva_index.get(f"{addr:08X}")
    if not entry:
        return None
    sig = entry["signature"]
    returns, _, rest = sig.partition(" ")
    name = rest.split("(")[0] + "()" if rest else sig
    helper = rva_index.get(f"{via:08X}") if via else None
    if helper:
        short = helper["signature"].split("(")[0].rsplit(" ", 1)[-1]
        name = f"{name} -> {short}"
    return {"name": name, "returns": returns}


def accessor_field(addr: int, isil_root: str, rva_index: dict, cache: dict):
    """The field a one-line accessor on `this` reads, or None.

    Deliberately shallow: one call deep, and only when the callee does nothing
    but load from `this`. A generic container's `GetItems()` is the shape --
    generic sharing forces container types to go through an accessor instead of
    touching the field inline, which is the whole reason those slots had no
    provenance. Following further would start guessing at real logic.
    """
    key = f"{addr:08X}"
    if key in cache:
        return cache[key]
    cache[key] = None
    entry = rva_index.get(key)
    if not entry:
        return None
    path = os.path.join(isil_root, entry["file"])
    if not os.path.exists(path):
        return None
    for sig, rows in parse_isil(_read(path)):
        if sig == entry["signature"]:
            cache[key] = _first_this_field(rows)
            return cache[key]
    return None


def _first_this_field(rows):
    """The offset of the first field the body reads off `this`.

    Two forms, both present: a direct `Move X0, [X20+40]`, and an address
    computation `Add X19, X20, 136` followed by `Move X0, [X19]`. `this` is also
    usually copied out of X0 first, so the alias has to be followed here exactly
    as in the main trace.
    """
    aliases, addrs = {THIS_REG}, {}
    for _, op in rows:
        m = MOVE_REG.match(op)
        if m:
            dst, src = _reg(m.group(1), m.group(2)), _reg(m.group(3), m.group(4))
            (aliases.add if src in aliases else aliases.discard)(dst)
            if src in addrs:
                addrs[dst] = addrs[src]
            else:
                addrs.pop(dst, None)
            continue
        m = ADD_IMM.match(op)
        if m:
            dst, src = _reg(m.group(1), m.group(2)), _reg(m.group(3), m.group(4))
            if src in aliases or src in addrs:
                addrs[dst] = addrs.get(src, 0) + int(m.group(5))
            else:
                addrs.pop(dst, None)
            aliases.discard(dst)
            continue
        m = LOAD.match(op)
        if m:
            base = _reg(m.group(3), m.group(4))
            if base in aliases:
                return int(m.group(5) or 0)
            if base in addrs:
                return addrs[base]
            aliases.discard(_reg(m.group(1), m.group(2)))
    return None


# Which declared C# types can sit behind a given FlatBuffers slot type. Used only
# for generic classes, where Cpp2IL has no offsets to join on.
TYPE_FITS = {
    "int64": ("long", "int64", "datetime"),
    "int32": ("int", "int32", "enum", "uint"),
    "bool": ("bool", "boolean"),
    "float32": ("float", "single"),
    "float64": ("double",),
    "int16": ("short", "int16"),
    "uint8": ("byte",),
}


def _fits(fb_type: str, cs_type: str) -> bool:
    """Whether a declared type could be what this slot holds."""
    bare = cs_type.replace("Nullable<", "").replace(">", "").strip().lower()
    if fb_type == "offset":
        # Anything by reference: strings, arrays, nested tables, DateTime
        # (serialised through a helper), and the generic parameter itself.
        return bare not in sum(TYPE_FITS.values(), ())
    return any(bare.endswith(x) for x in TYPE_FITS.get(fb_type, ()))


def match_by_order(slots, fields, taken) -> dict:
    """Pair leftover slots with declared fields by type, in declaration order.

    A fallback for generic classes only. Cpp2IL writes `Field offset: 0x0` for
    every field of a generic class -- it cannot compute a layout that IL2CPP
    specialises per instantiation -- so the offset join that resolves the other
    1,500 classes has nothing to join on here.

    What survives is the order the fields are declared in and their types, and
    the generated serialiser writes slots in that same order. This pairs them
    greedily, skipping any field whose type cannot sit behind the slot.

    Weaker evidence than the offset join, and labelled `type-order` in the
    output so a reader can tell the two apart.
    """
    free = [f for f in fields if f["name"] not in taken]
    out, i = {}, 0
    for s in sorted(slots, key=lambda x: x["slot"]):
        while i < len(free) and not _fits(s["type"], free[i]["cs_type"]):
            i += 1
        if i >= len(free):
            break
        out[s["slot"]] = free[i]
        i += 1
    return out


@dataclass
class Recovery:
    """The recovered schema, plus what it could not account for."""

    classes: dict = field(default_factory=dict)     # fqn -> {slots, base, fields}
    unresolved: list = field(default_factory=list)  # [(fqn, slot, fb type)]
    guid_types: list = field(default_factory=list)

    def to_dict(self) -> dict:
        """The JSON form a `Schema` reads back. Slot keys become strings there."""
        return {
            "classes": {fqn: {**entry,
                              "fields": {str(k): v for k, v in entry["fields"].items()},
                              **({"unions": {str(k): str(v) for k, v
                                             in entry["unions"].items()}}
                                 if entry.get("unions") else {})}
                        for fqn, entry in self.classes.items()},
            "guid_types": list(self.guid_types),
        }

    def summary(self) -> dict:
        mapped = sum(len(v["fields"]) for v in self.classes.values())
        unions = sum(len(v.get("unions") or ()) for v in self.classes.values())
        named = sum(1 for v in self.classes.values()
                    for f in v["fields"].values() if f["name"] != BASE_SLOT)
        return {"classes": len(self.classes),
                "slots_declared": sum(v["slots"] or 0 for v in self.classes.values()),
                "slots_written": mapped, "slots_named": named,
                "unions_paired": unions,
                "unresolved": len(self.unresolved)}


BASE_SLOT = "(base)"


# ── unions: the tag slot and the value slot are one field ───────────────────
#
# A FlatBuffers union is two slots. For `x:Any`, the generator emits `x_type`
# holding the member tag and `x` holding the value, and gives the type slot the
# id *before* the value slot -- a fact about the format, checkable against
# upstream, not a naming rule about any title.
#
# Which two slots is structural too: the serialiser reads the field once and
# feeds it to two helpers, so the pair is the pair of slots that came from the
# same source. Nothing here reads a method name to decide it, because "a helper
# whose name ends in Types is the tag half" would be exactly the kind of
# infer-semantics-from-a-name rule that stays in the projects.

def pair_unions(sources: dict) -> dict:
    """`{value slot: tag slot}` for the union pairs among `{slot: (read, helper)}`.

    Pure, so the rule can be pinned without an ISIL dump.

    Two slots pair when they came from **one read** handed to **two different
    helpers**. Both halves of that matter. "One read, two slots" alone is not a
    union -- this file already documents the other case, an identified variable
    serialising as its reference plus its resolved inline value, "both tracing
    back to the same offset" -- and pairing those would hand a real field a
    fabricated tag and swallow its other half. The helper is what tells them
    apart, which is why `trace_slots` records it: without it "both slots read
    `GetItems()` and the pair is indistinguishable".

    So a slot with no helper never pairs, and neither does a third slot off the
    same read: which two of three go together is not something the shape says,
    and choosing would invent a field.
    """
    by_read: dict = {}
    for slot, source in sorted(sources.items()):
        read, helper = (source or (None, None))
        if read is not None and helper is not None:
            by_read.setdefault(read, []).append((slot, helper))
    out = {}
    for pairs in by_read.values():
        if len(pairs) != 2:
            continue
        (low, low_helper), (high, high_helper) = sorted(pairs)
        if low_helper == high_helper or low == high:
            continue
        out[high] = low          # the generator gives the type slot the lower id
    return out


def recover_schema(isil_dir: str, src_dir: str, *, rva_index=None,
                   guid_roots=()) -> Recovery:
    """Recover every generated table class's schema from the shipped code.

    `isil_dir` is Cpp2IL's `IsilDump` tree, `src_dir` the reconstructed C#
    (`revenant seed-src` output) whose paths mirror it. `rva_index` is Cpp2IL's
    `rva_index.json` -- a dict, a path, or None to look for it beside the dumps.

    `guid_roots` names the types that serialise as a raw 16-byte GUID vector
    rather than as a table; anything whose base chain reaches one is one too.
    Empty by default and never guessed: a list of concrete class names is a game
    fact, and this module holds none.
    """
    if rva_index is None:
        rva_index = load_rva_index(isil_dir)
    elif isinstance(rva_index, str):
        with open(rva_index, encoding="utf-8") as f:
            rva_index = json.load(f)
    cs_index = index_sources(src_dir)
    acc_cache: dict = {}
    out = Recovery(guid_types=guid_types(cs_index, guid_roots))

    for path in _isil_files(isil_dir):
        text = _read(path)
        if BUILDER_MARK not in text:
            continue
        type_line = TYPE_LINE.match(text)
        if not type_line:
            continue
        fqn = type_line.group(1)
        body = next((rows for sig, rows in parse_isil(text)
                     if sig.startswith(SERIALIZER_SIG)), None)
        if body is None:
            continue
        nslots, slots = trace_slots(body)

        # The C# beside it names the fields. Its path mirrors the ISIL path,
        # except that Cpp2IL gives a nested type its own `X_NestedType_Y.txt`
        # while the C# leaves `Y` inside `X.cs` -- so the suffix is peeled off
        # and becomes the path to the class within the file.
        stem, nested = os.path.relpath(path, isil_dir)[:-4], []
        while "_NestedType_" in stem:
            stem, _, inner = stem.rpartition("_NestedType_")
            nested.insert(0, inner)
        cs_base, by_offset, fields_all, own_fields = read_with_bases(
            os.path.join(src_dir, stem + ".cs"), tuple(nested), cs_index)

        entry = {"slots": nslots, "base": cs_base, "fields": {}}
        leftover = []
        # What each slot's value was read from, before resolution renames it.
        # Two slots off one source are a union pair, and that is the only thing
        # this is kept for.
        sources: dict = {}
        for s in slots:
            if s["slot"] is None:
                continue
            src = s["source"]
            if src and src[0] == "thiscall":
                # (what was read, which helper consumed it). A field loaded
                # inline has no helper and so never pairs -- see `pair_unions`.
                sources[s["slot"]] = (src[1], src[2])
            if src and src[0] == "thiscall":
                # Resolve the accessor to the field it reads, then fall through
                # as if the load had been inline.
                target = rva_index.get(f"{src[1]:08X}") or {}
                if SERIALIZER in target.get("signature", ""):
                    # Not an accessor at all: the base class's own serialiser,
                    # reached by address because generic sharing hid the name.
                    entry["fields"][s["slot"]] = {
                        "name": BASE_SLOT, "fb_type": s["type"],
                        "cs_type": target.get("class", "?")}
                    continue
                off = accessor_field(src[1], isil_dir, rva_index, acc_cache)
                if off is not None and off in by_offset:
                    src = ("field", off)
                else:
                    # No declared field at that offset. For generic containers
                    # this is not a miss but the truth: IL2CPP specialises their
                    # layout at runtime, so `GetItems()` reads 0x88 in an object
                    # whose shared C# stops at 0x80. The accessor's own name is
                    # then the most precise thing that can honestly be said.
                    src = ("accessor", accessor_name(src[1], rva_index, src[2]))
            if src and src[0] == "field" and src[1] in by_offset:
                f = by_offset[src[1]]
                entry["fields"][s["slot"]] = {
                    "name": f["name"], "fb_type": s["type"],
                    "cs_type": f["cs_type"], "offset": f["offset"]}
            elif src and src[0] == "accessor" and src[1]:
                entry["fields"][s["slot"]] = {
                    "name": src[1]["name"], "fb_type": s["type"],
                    "cs_type": src[1]["returns"], "via": "accessor"}
            elif src and src[0] == "base":
                entry["fields"][s["slot"]] = {
                    "name": BASE_SLOT, "fb_type": s["type"], "cs_type": src[1]}
            else:
                leftover.append(s)

        # Gate on genericity, not on the offsets: a class that inherits from a
        # non-generic base has real offsets for the inherited half and zeroes for
        # its own, so an all-zero test never fires for it.
        if leftover and fields_all and "`" in os.path.basename(stem):
            named = {f["name"] for f in entry["fields"].values()}
            for slot, f in match_by_order(leftover, fields_all, named).items():
                entry["fields"][slot] = {
                    "name": f["name"], "cs_type": f["cs_type"],
                    "fb_type": next(s["type"] for s in leftover if s["slot"] == slot),
                    "via": "type-order"}
            leftover = [s for s in leftover if s["slot"] not in entry["fields"]]
        # Last resort, and only when the answer is forced: exactly one slot left,
        # exactly one declared field nobody claimed, and their types agree. That
        # is not a guess but a closed system. If a class has cache fields or
        # several loose ends the count is not 1 and this stays silent.
        if len(leftover) == 1 and own_fields:
            claimed = {f.get("offset") for f in entry["fields"].values()}
            # Own fields only. When a slot holds `(base)`, the base's fields are
            # serialised inside that nested table, so they are not candidates for
            # a slot here.
            free = [f for f in own_fields if f["offset"] not in claimed]
            if len(free) == 1 and _fits(leftover[0]["type"], free[0]["cs_type"]):
                entry["fields"][leftover[0]["slot"]] = {
                    "name": free[0]["name"], "cs_type": free[0]["cs_type"],
                    "fb_type": leftover[0]["type"], "offset": free[0]["offset"],
                    "via": "elimination"}
                leftover = []
        # The pair is recorded whether or not both halves resolved to a name:
        # an unresolved union should read as one field nobody could name, not as
        # two unrelated slots nobody could name.
        unions = pair_unions(sources)
        if unions:
            # One place records the pairing. Mirroring it onto each field too
            # would be a second copy to keep in step, and `Schema.unions` is
            # what the reader asks.
            entry["unions"] = unions
        out.unresolved.extend((fqn, s["slot"], s["type"]) for s in leftover)
        out.classes[fqn] = entry
    return out


def _isil_files(isil_dir: str):
    for dirpath, _, names in os.walk(isil_dir):
        for name in sorted(names):
            if name.endswith(".txt"):
                yield os.path.join(dirpath, name)


# ── layer 3: decoding against the recovered schema ──────────────────────────

SCALARS = {"int32": ("<i", 4), "uint32": ("<I", 4), "int64": ("<q", 8),
           "uint64": ("<Q", 8), "float32": ("<f", 4), "float64": ("<d", 8),
           "int16": ("<h", 2), "uint16": ("<H", 2), "int8": ("<b", 1),
           "uint8": ("<B", 1), "bool": ("<B", 1)}
GENERIC = re.compile(r"^([\w.]+)<(.+)>$")
ARRAY = re.compile(r"^(.+)\[\]$")
GUID_BYTES = 16


def _short(name: str) -> str:
    return name.split("<")[0].rsplit(".", 1)[-1].split("`")[0]


@dataclass
class Schema:
    """A recovered schema, keyed for lookup by the short class name."""

    classes: dict = field(default_factory=dict)     # fqn -> {slots, base, fields}
    guid_types: set = field(default_factory=set)
    by_short: dict = field(default_factory=dict)
    # {union type name: [class per tag value]}, supplied by the caller. Empty by
    # default and never guessed -- see `union_member`.
    union_members: dict = field(default_factory=dict)

    @classmethod
    def from_dict(cls, doc: dict) -> "Schema":
        classes = doc.get("classes", doc)
        normalised = {
            fqn: {**entry, "fields": {int(k): v for k, v in (entry.get("fields") or {}).items()}}
            for fqn, entry in classes.items()}
        normalised = {fqn: {**e, "unions": {int(k): int(v) for k, v
                                            in (e.get("unions") or {}).items()}}
                      for fqn, e in normalised.items()}
        schema = cls(classes=normalised, guid_types=set(doc.get("guid_types") or ()),
                     union_members=dict(doc.get("union_members") or {}))
        for fqn in normalised:
            short = _short(fqn)
            # An ambiguous short name resolves to nothing rather than to the
            # wrong class: a mislabelled number is worse than an unlabelled one.
            schema.by_short[short] = None if short in schema.by_short else fqn
        return schema

    @classmethod
    def from_recovery(cls, recovery: Recovery) -> "Schema":
        return cls.from_dict(recovery.to_dict())

    def spec(self, cls_name: str):
        fqn = self.by_short.get(_short(cls_name)) if cls_name else None
        return self.classes.get(fqn) if fqn else None

    def fields(self, cls_name: str) -> dict:
        """{slot index: field descriptor} for a class; empty when unknown."""
        return (self.spec(cls_name) or {}).get("fields", {})

    def unions(self, cls_name: str) -> dict:
        """`{value slot: tag slot}` for this class's union fields."""
        return (self.spec(cls_name) or {}).get("unions", {})

    def union_members_of(self, union: str):
        """`(members, complaint)` -- the class per tag value for a union type.

        The member list is a list of concrete class names, which CONTEXT.md's
        bar calls a game fact, and it is not in the buffer either -- so it is
        the caller's to supply, like `guid_types` and `containers`. Without it
        the tags are still reported, they just are not named and the values
        cannot be decoded as anything.

        Validated because it is hand-written JSON. A string is iterable and
        would otherwise hand back single characters as member names, which is an
        invented class name -- the one thing worse than no name at all.
        """
        if not union:
            return [], ""
        raw = (self.union_members or {}).get(union)
        if raw is None:
            return [], (f"no union_members for {union!r}, so its tags are numbers "
                        f"and its values cannot be decoded")
        if not isinstance(raw, (list, tuple)) or not all(isinstance(m, str) for m in raw):
            return [], (f"union_members[{union!r}] is not a list of class names, "
                        f"so it was ignored")
        return list(raw), ""


def element_type(cs_type: str, guid_types, containers) -> tuple:
    """(kind, class) for a declared C# type: what the offset points at.

    A free function rather than a `Reader` method because two callers want it
    without a buffer: the reader decoding a slot, and anyone asking the schema
    what a root's rows are *called* -- a question about the declaration, not
    about any bytes.
    """
    if cs_type in ("string", "System.String"):
        return "string", None
    # Arrays first: `Ref<X>[]` is a vector of references, not one reference.
    # Testing the head name before the `[]` reads the whole array as a single
    # GUID and silently drops every element.
    m = ARRAY.match(cs_type)
    if m:
        return "vector", m.group(1).strip()
    if _short(cs_type) in guid_types:
        return "guid", None
    m = GENERIC.match(cs_type)
    if m:
        outer = m.group(1).rsplit(".", 1)[-1]
        if any(outer.startswith(c) for c in containers):
            # Not a vector itself: a one-slot table wrapping the item vector.
            return "container", m.group(2).split(",")[0].strip()
    return "table", cs_type


def row_class(schema: "Schema | None", spec: str, containers=()) -> str:
    """What one row of `Root[#Field]` is called, per the schema. "" when unclear.

    Not the root class. `fb_roots` names the *container* -- `Game.CMS.ItemDb`
    holds a vector of `Game.CMS.Item`, and it is the element name that codegen
    puts on the row type and that the scaffold therefore mentions. Searching for
    the root instead answers a question nobody asked.

    Several vectors and no `#Field` is unclear, not a guess: picking one would
    hand back a class name the rows are not, and a wrong name counts as a zero
    exactly like a right name that is absent.
    """
    root, _sep, wanted = spec.partition("#")
    if schema is None or not root.strip():
        return ""
    found = []
    for meta in schema.fields(root.strip()).values():
        if meta.get("fb_type") in SCALARS:
            continue
        kind, inner = element_type(meta.get("cs_type", "") or "",
                                   schema.guid_types, containers)
        if kind in ("vector", "container") and inner:
            found.append((meta.get("name", ""), inner))
    if wanted:
        return next((cls for name, cls in found if name == wanted), "")
    return found[0][1] if len(found) == 1 else ""


class Reader:
    """Decode a buffer against a schema.

    `containers` names the generic outer types whose single slot wraps the item
    vector (`SomeTable<X>` -> a vector of X). That is a convention of whichever
    CMS generated the code, not of FlatBuffers, so it is the caller's to state.
    """

    def __init__(self, data: bytes, schema: Schema, *, containers=(),
                 max_depth: int = 3, limit: int = 5):
        self.buf = Buffer(data)
        self.schema = schema
        self.containers = tuple(containers)
        self.max_depth = max_depth
        self.limit = limit
        # (path, probed kind) for every value this run had to guess at.
        self.inferred: list = []
        # What stopped a field being read fully, in words. `inferred` says a
        # value was guessed; this says why nothing better was available.
        self.notes: list = []

    # -- raw reads ----------------------------------------------------------

    def scalar(self, pos: int, kind: str):
        fmt, size = SCALARS[kind]
        if not (0 <= pos <= self.buf.n - size):
            return None
        v = struct.unpack_from(fmt, self.buf.d, pos)[0]
        return bool(v) if kind == "bool" else v

    def string(self, pos: int):
        return as_string(self.buf, pos, limit=1 << 20)

    def guid(self, pos: int):
        """The 16 bytes, whichever of the two shapes the reference took.

        A reference reached from a field is the GUID vector itself, but the same
        type as a vector element is a one-slot table wrapping that vector.
        Following whatever is actually there beats picking one and returning
        None for half the corpus.
        """
        vec = as_vector(self.buf, pos)
        if vec and vec[0] == GUID_BYTES:
            return self.buf.d[vec[1]:vec[1] + GUID_BYTES].hex()
        table = self.deref(pos)
        if table is None:
            return None
        _n, slots = vtable(self.buf, table)
        if not slots or slots[0] is None:
            return None
        inner = as_vector(self.buf, slots[0])
        if not inner or inner[0] != GUID_BYTES:
            return None
        return self.buf.d[inner[1]:inner[1] + GUID_BYTES].hex()

    def deref(self, pos: int):
        rel = self.buf.u32(pos)
        return pos + rel if rel else None

    def slots(self, table: int) -> list:
        return vtable(self.buf, table)[1]

    def present(self, table: int | None = None) -> set:
        """Which slot indices this table actually sets. Declared != written."""
        at = self.buf.root() if table is None else table
        return {i for i, pos in enumerate(self.slots(at)) if pos is not None}

    # -- typed reads --------------------------------------------------------

    def element_type(self, cs_type: str) -> tuple:
        """(kind, class) for a declared C# type: what the offset points at."""
        return element_type(cs_type, self.schema.guid_types, self.containers)

    def _probe(self, pos: int, path: str) -> str:
        reading = probe(self.buf, pos)
        self.inferred.append((path, reading.kind))
        return reading.marker

    def read(self, root_class: str, table: int | None = None) -> dict:
        """Decode the root table (or `table`) as `root_class`.

        A root class the schema does not know is a caller mistake, not a slot to
        probe: every value under it would come back guessed, which reads as a
        decode that found nothing rather than as a wrong root.
        """
        if self.schema.spec(root_class) is None:
            raise KeyError(f"no class named {root_class!r} in this schema")
        return self.read_table(self.buf.root() if table is None else table,
                               root_class, 0, "")

    def read_table(self, table: int, cls: str, depth: int, path: str):
        spec = self.schema.spec(cls)
        if spec is None:
            # No schema for this class. Decoding it as a table anyway invents a
            # vtable out of whatever bytes are there, which is how a wrong number
            # gets a confident name.
            return self._probe(table, path)
        out: dict = {}
        unions = self.schema.unions(cls)
        tag_slots = {tag: value for value, tag in unions.items() if tag != value}
        positions = self.slots(table)
        for i, pos in enumerate(positions):
            if i in tag_slots:
                # Read with its value half, below. On its own it is a number
                # with no meaning -- reporting it as a field is what made a
                # union look like two unrelated slots.
                continue
            meta = spec.get("fields", {}).get(i)
            if i in unions:
                # Before the `pos is None` skip, deliberately: a union with a
                # tag and no value is still a field, and skipping it here would
                # drop the tag too -- both halves gone, which is worse than the
                # two loose slots this replaced.
                name = (meta or {}).get("name") or f"slot{i}?"
                out[name] = self.read_union(positions, i, unions[i], meta,
                                            name, depth, path)
                continue
            if pos is None:
                continue
            if meta is None:
                out[f"slot{i}?"] = self._probe(pos, _join(path, f"slot{i}?"))
                continue
            name = meta["name"]
            if name in out:
                # One C# field can occupy two slots: an identified variable
                # serialises as the reference plus its resolved inline value,
                # both tracing back to the same offset. Keeping only the last
                # would silently drop half of every such record.
                name = f"{name}@{i}"
            here = _join(path, name)
            if meta["fb_type"] in SCALARS:
                out[name] = self.scalar(pos, meta["fb_type"])
                continue
            kind, inner = self.element_type(meta.get("cs_type", "") or "")
            if kind == "string":
                out[name] = self.string(pos)
            elif kind == "guid":
                out[name] = self.guid(pos)
            elif depth >= self.max_depth:
                out[name] = "..."
            elif kind == "vector":
                out[name] = self.read_vector(pos, inner, depth, here)
            elif kind == "container":
                out[name] = self.read_container(pos, inner, depth, here)
            elif self.schema.spec(inner) is None:
                # `offset` says "a relative pointer" and nothing more; the
                # declared type was supposed to say what it points at, and did
                # not resolve. Probe it and say so.
                out[name] = self._probe(pos, here)
            else:
                sub = self.deref(pos)
                out[name] = (self.read_table(sub, inner, depth + 1, here)
                             if sub else None)
        return out

    def read_union(self, positions: list, value_slot: int, tag_slot: int,
                   meta, name: str, depth: int, path: str):
        """One union field, read as the pair it is: the tag decides the value.

        This is what the pairing is *for*. A union's value slot is an offset and
        the encoding says nothing about what it points at -- only the tag does,
        and only against the member list. So the tag is not a label to print
        beside a probed value: it selects the class the value is decoded as,
        per element for a repeated union, and that is the difference between a
        concrete type and one more `?`.

        Anything that stops it says so in `notes` rather than by changing shape:
        the field always comes back `{"type": [...], "value": ...}` so a census
        sees one column whether or not the union resolved.
        """
        here = _join(path, name)
        tag_pos = positions[tag_slot] if 0 <= tag_slot < len(positions) else None
        value_pos = positions[value_slot] if 0 <= value_slot < len(positions) else None
        tags, repeated, cut = self.read_tags(tag_pos)
        members, complaint = self.schema.union_members_of(self.union_type(meta))
        if complaint:
            self.notes.append(f"{here}: {complaint}")
        if tag_pos is None:
            self.notes.append(f"{here}: its tag slot ({tag_slot}) is not set in this "
                              f"table, so nothing says what the value is")
        if cut:
            self.notes.append(f"{here}: only the first {self.limit} of {cut} tags "
                              f"were read")
        if meta is None:
            self.notes.append(f"{here}: neither slot resolved to a field name; "
                              f"the pair is slots {tag_slot} and {value_slot}")
            self.inferred.append((here, "union"))

        named = [members[t] if 0 <= t < len(members) else t for t in tags]
        if value_pos is None:
            # The tag is still worth having, and dropping the field entirely --
            # which is what skipping the tag slot alone would do -- loses it.
            self.notes.append(f"{here}: its value slot ({value_slot}) is not set")
            return {"type": named, "value": None}
        if repeated:
            return {"type": named,
                    "value": self.read_union_vector(value_pos, tags, members,
                                                    depth, here)}
        member = members[tags[0]] if tags and 0 <= tags[0] < len(members) else ""
        return {"type": named, "value": self.member(value_pos, member, depth, here)}

    def union_type(self, meta) -> str:
        """The union's own type name: a repeated union is keyed by its element."""
        declared = (meta or {}).get("cs_type", "") or ""
        array = ARRAY.match(declared)
        return _short((array.group(1) if array else declared).strip())

    def read_union_vector(self, pos: int, tags: list, members: list,
                          depth: int, path: str):
        """A vector of union values, each decoded as the class *its own* tag names.

        Not `read_vector`, which decodes every element as one class. That is the
        whole point of a union: element 0 and element 1 need not be the same
        thing.
        """
        vec = as_vector(self.buf, pos)
        if not vec:
            return None
        count, start = vec
        shown = min(count, self.limit)
        if count != len(tags):
            self.notes.append(f"{path}: {count} values but {len(tags)} tags; "
                              f"the halves disagree, so the extra are probed")
        items = []
        for i in range(shown):
            tag = tags[i] if i < len(tags) else -1
            member = members[tag] if 0 <= tag < len(members) else ""
            items.append(self.member(start + i * 4, member, depth, f"{path}[{i}]"))
        if count > shown:
            items.append(f"... {count - shown} more")
        return items

    def member(self, pos: int, cls: str, depth: int, path: str):
        """One union value, as the class its tag named. Probed when nothing did."""
        if cls and self.schema.spec(cls) is None:
            # Named but unknown: the member list and the class list disagree,
            # which is a different repair from "no member list at all".
            self.notes.append(f"{path}: the tag names {cls!r} and the schema has "
                              f"no such class, so the value was probed")
        if not cls or self.schema.spec(cls) is None:
            return self._probe(pos, path)
        if depth >= self.max_depth:
            return "..."
        sub = self.deref(pos)
        return self.read_table(sub, cls, depth + 1, path) if sub else None

    def read_tags(self, pos):
        """`(tags, repeated, cut)` -- the union's member tags.

        Both spellings exist and the buffer says which, so nothing has to be
        configured: a repeated union's tag slot holds a vector of bytes, a
        single union's holds one. `cut` is the true count when the vector was
        longer than the limit, so the caller can say so rather than returning a
        short list that reads as a short union.
        """
        if pos is None:
            return [], False, 0
        vec = as_vector(self.buf, pos)
        if vec:
            count, start = vec
            shown = min(count, self.limit)
            return ([self.buf.d[start + i] for i in range(shown)], True,
                    count if count > shown else 0)
        one = self.scalar(pos, "uint8")
        return ([] if one is None else [one]), False, 0

    def read_container(self, pos: int, inner, depth: int, path: str):
        wrapper = self.deref(pos)
        slots = self.slots(wrapper) if wrapper else []
        if not slots or slots[0] is None:
            return None
        return self.read_vector(slots[0], inner, depth, path)

    def read_vector(self, pos: int, cls, depth: int, path: str):
        vec = as_vector(self.buf, pos)
        if not vec:
            return None
        count, start = vec
        # Elements get the same type resolution as fields do. Without it a vector
        # of references comes back as a row of unresolved tables: the right
        # count, none of the identities.
        kind, inner = self.element_type(cls) if cls else ("table", cls)
        items, shown = [], min(count, self.limit)
        for i in range(shown):
            at = start + i * 4
            here = f"{path}[{i}]"
            if kind == "string":
                items.append(self.string(at))
            elif kind == "guid":
                items.append(self.guid(at))
            elif kind == "container":
                items.append(self.read_container(at, inner, depth + 1, here))
            elif self.schema.spec(inner or cls) is None:
                items.append(self._probe(at, here))
            else:
                sub = self.deref(at)
                items.append(self.read_table(sub, inner or cls, depth + 1, here)
                             if sub else None)
        if count > shown:
            items.append(f"... {count - shown} more")
        return items


def _join(path: str, name: str) -> str:
    return f"{path}.{name}" if path else name
