"""Luban binary tables: rows and fields out of a `.bytes` a game ships.

Luban (`focus-creative-games/luban`) is a configuration pipeline: designers edit
sheets, it generates loader code plus one binary blob per table. Two of the nine
titles ship their numbers this way and nothing here could read them, so every
economy dimension for both said "the numbers layer is missing" -- about twenty
cells, on the two titles whose *code* reads best of all nine.

This module sits beside `protobuf.py` and `flatbuffers.py`, and splits the way
`contrib.decrypt.xxtea` did: **the table format is universal and lives here; the
outer container and its key are facts about one title and stay in the project.**
A caller hands in plaintext bytes, or a `container` callable that turns the
shipped bytes into them.

## The format, from the source

Transcribed from `Luban.Core/Serialization/ByteBuf.cs` and the `cs-bin`
templates at `focus-creative-games/luban@main`, not from a guess:

- Integers are a **big-endian prefix varint**, not protobuf's little-endian
  continuation-bit scheme. The lead byte's high bits give the length: `< 0x80`
  is one byte holding the value, `< 0xc0` two with six payload bits in the lead,
  `< 0xe0` three with five, `< 0xf0` four with four, and `0xf0` a lead of pure
  tag plus four big-endian bytes. `long` extends the same ladder to nine.
- `float` and `double` are plain IEEE **little-endian**; `fint`/`fshort`/`flong`
  are fixed-width little-endian. So one buffer mixes both byte orders, which is
  correct and is the first thing a hand-written decoder gets wrong.
- `string` and `bytes` are a size (a `uint`) then that many bytes, UTF-8.
- `list`/`set`/`array` are a size then that many elements; `map` is a size then
  that many key-value pairs.
- A nullable field is a `bool` and then the value if it was true.
- A bean is its fields in declaration order, **parent's first** -- the generated
  constructor chains to `base(_buf)` before reading its own.
- A polymorphic bean is an `int` type id and then that concrete bean.
- A table file is a size and then that many rows.

## Why a schema is required

None of that is self-describing: the bytes carry no field names and no types.
A decoder without a schema is not reading a table, it is guessing at one, and a
single wrong type desynchronises everything after it. So `read_table` takes a
`Schema`, and the project supplies it -- written from the loader Luban generated
into the game, which ships in the package beside the blob. See "where the schema
comes from" at the foot of this module for why it is the project's and not
revenant's.

Failures say which stage failed -- container, header, row, field -- because
"could not decrypt", "the row count is nonsense" and "field 7 of row 412 ran off
the end" send you to three different places. Nothing here returns an empty table
for a blob it could not read.
"""

from __future__ import annotations

import json
import re
import struct
from dataclasses import dataclass, field as _field

# Where a decode gave up. The whole point of naming them: a failed container is
# the project's key or header, a failed header is usually the wrong offset, and
# a failed field is the schema disagreeing with the bytes.
STAGE_SCHEMA = "schema"
STAGE_CONTAINER = "container"
STAGE_HEADER = "header"
STAGE_ROW = "row"
STAGE_FIELD = "field"


class LubanError(Exception):
    """A decode that stopped, and where."""

    def __init__(self, stage: str, message: str, offset: int = -1, path: str = ""):
        self.stage = stage
        self.message = message
        self.offset = offset
        self.path = path
        where = f" at byte {offset}" if offset >= 0 else ""
        at = f" ({path})" if path else ""
        super().__init__(f"{stage}{at}: {message}{where}")

    def at(self, path: str) -> "LubanError":
        """The same failure, told where in the row it happened.

        The readers that run out of bytes are the primitives, and a primitive
        does not know it is field `cost` of `ItemConf` -- only its caller does.
        So the path is attached on the way out, by the frame that knows it, and
        only when nothing deeper has already named a more specific one.
        """
        if self.path:
            return self
        return LubanError(self.stage, self.message, self.offset, path)


class ByteBuf:
    """A reader over Luban's wire format. Positional, forward-only."""

    def __init__(self, data: bytes):
        self.data = data
        self.pos = 0

    @property
    def remaining(self) -> int:
        return len(self.data) - self.pos

    def _take(self, n: int, what: str) -> bytes:
        if self.remaining < n:
            raise LubanError(STAGE_FIELD,
                             f"{what} wants {n} bytes and {self.remaining} are left",
                             self.pos)
        chunk = self.data[self.pos:self.pos + n]
        self.pos += n
        return chunk

    # ── the varint ladder ───────────────────────────────────────────────────

    def read_uint(self) -> int:
        """Luban's prefix varint, 1 to 5 bytes, big-endian payload."""
        head = self._take(1, "uint")[0]
        if head < 0x80:
            return head
        if head < 0xC0:
            rest = self._take(1, "uint")
            return ((head & 0x3F) << 8) | rest[0]
        if head < 0xE0:
            rest = self._take(2, "uint")
            return ((head & 0x1F) << 16) | (rest[0] << 8) | rest[1]
        if head < 0xF0:
            rest = self._take(3, "uint")
            return ((head & 0x0F) << 24) | (rest[0] << 16) | (rest[1] << 8) | rest[2]
        rest = self._take(4, "uint")
        return int.from_bytes(rest, "big")

    def read_ulong(self) -> int:
        """The same ladder, extended to nine bytes."""
        head = self._take(1, "ulong")[0]
        if head < 0x80:
            return head
        if head < 0xC0:
            return ((head & 0x3F) << 8) | self._take(1, "ulong")[0]
        if head < 0xE0:
            rest = self._take(2, "ulong")
            return ((head & 0x1F) << 16) | int.from_bytes(rest, "big")
        if head < 0xF0:
            rest = self._take(3, "ulong")
            return ((head & 0x0F) << 24) | int.from_bytes(rest, "big")
        if head < 0xF8:
            rest = self._take(4, "ulong")
            return ((head & 0x07) << 32) | int.from_bytes(rest, "big")
        if head < 0xFC:
            rest = self._take(5, "ulong")
            return ((head & 0x03) << 40) | int.from_bytes(rest, "big")
        if head < 0xFE:
            rest = self._take(6, "ulong")
            return ((head & 0x01) << 48) | int.from_bytes(rest, "big")
        if head < 0xFF:
            # The lead byte carries no payload here: the writer emits a bare
            # 0xfe and the reader's `(h & 0x01) << 24` is commented out in the
            # source. Transcribed as written, not as it looks like it should be.
            rest = self._take(7, "ulong")
            return int.from_bytes(rest, "big")
        return int.from_bytes(self._take(8, "ulong"), "big")

    # ── primitives ──────────────────────────────────────────────────────────

    def read_bool(self) -> bool:
        return self._take(1, "bool")[0] != 0

    def read_byte(self) -> int:
        return self._take(1, "byte")[0]

    def read_short(self) -> int:
        head = self._take(1, "short")[0]
        if head < 0x80:
            return head
        if head < 0xC0:
            return ((head & 0x3F) << 8) | self._take(1, "short")[0]
        if head == 0xFF:
            return _as_signed(int.from_bytes(self._take(2, "short"), "big"), 16)
        raise LubanError(STAGE_FIELD, f"0x{head:02x} is not a short lead byte", self.pos - 1)

    def read_int(self) -> int:
        return _as_signed(self.read_uint(), 32)

    def read_long(self) -> int:
        return _as_signed(self.read_ulong(), 64)

    def read_sint(self) -> int:
        """Luban's signed int: the bits rotated right by one. **Not zigzag.**

        Worth the warning, because upstream sets the trap itself. The comment
        block above `WriteSint` describes zigzag -- `(x >>> 1) ^ -(n & 1)` --
        and the code beneath it does something else:

            public int ReadSint()
            { uint x = ReadUint(); return (int)((x >> 1) ^ ((x & 1) << 31)); }

        That moves the low bit back to the sign position and leaves the rest
        alone, and `WriteSint` is the matching rotate-left, so the pair is
        self-consistent and the comment is simply wrong. The code is what ran
        when the blob was written.

        Read as zigzag, every negative comes back wrong and every positive comes
        back right: -1 decodes as -2147483648, -127 as -2147483522. Nothing
        about the output looks broken.
        """
        x = self.read_uint()
        return _as_signed((x >> 1) ^ ((x & 1) << 31), 32)

    def read_slong(self) -> int:
        """The same rotation over 64 bits."""
        x = self.read_ulong()
        return _as_signed((x >> 1) ^ ((x & 1) << 63), 64)

    def read_fshort(self) -> int:
        return struct.unpack("<h", self._take(2, "fshort"))[0]

    def read_fint(self) -> int:
        return struct.unpack("<i", self._take(4, "fint"))[0]

    def read_flong(self) -> int:
        return struct.unpack("<q", self._take(8, "flong"))[0]

    def read_float(self) -> float:
        return struct.unpack("<f", self._take(4, "float"))[0]

    def read_double(self) -> float:
        return struct.unpack("<d", self._take(8, "double"))[0]

    def read_size(self) -> int:
        """A count. Upstream's own name for a `uint` used as a length, kept so
        the container and string readers below read like the loader they were
        transcribed from."""
        return self.read_uint()

    def read_string(self) -> str:
        n = self.read_size()
        if n == 0:
            return ""
        return self._take(n, "string").decode("utf-8", errors="replace")

    def read_bytes(self) -> bytes:
        n = self.read_size()
        return self._take(n, "bytes") if n else b""


def _as_signed(value: int, bits: int) -> int:
    limit = 1 << (bits - 1)
    return value - (1 << bits) if value >= limit else value


# Type name -> the reader that consumes it. `datetime` is a long on the wire;
# `enum` is an int. Both are here because that is what the generated loader
# calls, and this table is a transcription of that loader, not a type system.
PRIMITIVES = {
    "bool": ByteBuf.read_bool,
    "byte": ByteBuf.read_byte,
    "short": ByteBuf.read_short,
    "int": ByteBuf.read_int,
    "long": ByteBuf.read_long,
    "float": ByteBuf.read_float,
    "double": ByteBuf.read_double,
    "string": ByteBuf.read_string,
    "bytes": ByteBuf.read_bytes,
    "datetime": ByteBuf.read_long,
    "enum": ByteBuf.read_int,
    "sint": ByteBuf.read_sint,
    "slong": ByteBuf.read_slong,
    "fshort": ByteBuf.read_fshort,
    "fint": ByteBuf.read_fint,
    "flong": ByteBuf.read_flong,
}


# ── the schema ──────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class Field:
    name: str
    type: str
    nullable: bool = False


@dataclass(frozen=True)
class Bean:
    name: str
    fields: tuple = ()
    parent: str = ""
    id: int | None = None      # the generated `__ID__`, for polymorphic dispatch
    abstract: bool = False


@dataclass
class Schema:
    beans: dict = _field(default_factory=dict)     # name -> Bean
    tables: dict = _field(default_factory=dict)    # data file stem -> bean name
    _by_id: dict = _field(default_factory=dict)

    def __post_init__(self):
        self._by_id = {b.id: b.name for b in self.beans.values() if b.id is not None}

    def bean(self, name: str) -> Bean:
        if name not in self.beans:
            near = ", ".join(sorted(self.beans)[:6]) or "nothing"
            raise LubanError(STAGE_SCHEMA,
                             f"the schema has no bean named {name!r} (it knows {near})")
        return self.beans[name]

    def fields_of(self, name: str) -> list:
        """A bean's fields, its parent's first -- the order the loader reads.

        The generated constructor chains to `base(_buf)` before reading its own
        fields, so a schema that lists only a bean's own fields decodes every
        derived row one field-set out of step.
        """
        seen, chain = set(), []
        cursor = name
        while cursor:
            if cursor in seen:
                raise LubanError(STAGE_SCHEMA,
                                 f"{name}: its parent chain loops at {cursor!r}")
            seen.add(cursor)
            bean = self.bean(cursor)
            chain.append(bean)
            cursor = bean.parent
        out = []
        for bean in reversed(chain):
            out.extend(bean.fields)
        return out

    def bean_for_id(self, type_id: int) -> str:
        if type_id not in self._by_id:
            known = ", ".join(str(i) for i in sorted(self._by_id)[:6])
            raise LubanError(STAGE_FIELD,
                             f"no bean has the type id {type_id} (the schema knows {known})")
        return self._by_id[type_id]

    @classmethod
    def from_json(cls, obj: dict) -> "Schema":
        beans = {}
        for name, body in (obj.get("beans") or {}).items():
            fields = tuple(Field(name=f["name"], type=f["type"],
                                 nullable=bool(f.get("nullable")))
                           for f in body.get("fields") or [])
            beans[name] = Bean(name=name, fields=fields,
                               parent=body.get("parent") or "",
                               id=body.get("id"),
                               abstract=bool(body.get("abstract")))
        return cls(beans=beans, tables=dict(obj.get("tables") or {}))


# ── decoding ────────────────────────────────────────────────────────────────

_CONTAINER_RE = re.compile(r"^(list|set|array)<(.+)>$")
_MAP_RE = re.compile(r"^map<(.+?),(.+)>$")


def read_value(buf: ByteBuf, type_name: str, schema: Schema, path: str = ""):
    """One value of a declared type. Raises `LubanError` with the field path."""
    type_name = type_name.strip()
    prim = PRIMITIVES.get(type_name)
    if prim is not None:
        return prim(buf)
    if type_name.startswith("bean:"):
        # Whether a type id precedes the fields is a property of the *bean*, not
        # of how the field spells it: the generated `DeserializeFoo` switches on
        # `ReadInt()` exactly when `Foo` is abstract. So an abstract bean gets
        # the id read here even when the schema wrote the plain `bean:` form --
        # skipping it would eat the id as the first field and shift the row.
        name = type_name[5:]
        if schema.bean(name).abstract:
            return _read_dynamic(buf, name, schema, path)
        return read_bean(buf, name, schema, path)
    if type_name.startswith("dynamic:"):
        return _read_dynamic(buf, type_name[8:], schema, path)
    m = _CONTAINER_RE.match(type_name)
    if m:
        n = buf.read_size()
        return [read_value(buf, m.group(2), schema, f"{path}[{i}]") for i in range(n)]
    m = _MAP_RE.match(type_name)
    if m:
        n = buf.read_size()
        out = {}
        for i in range(n):
            key = read_value(buf, m.group(1), schema, f"{path}[{i}].key")
            out[key] = read_value(buf, m.group(2), schema, f"{path}[{i}].value")
        return out
    raise LubanError(STAGE_FIELD, f"unknown type {type_name!r}", buf.pos, path)


def _read_dynamic(buf: ByteBuf, base: str, schema: Schema, path: str) -> dict:
    """A type id, then the concrete bean it names."""
    type_id = buf.read_int()
    return read_bean(buf, schema.bean_for_id(type_id), schema, path)


def read_bean(buf: ByteBuf, name: str, schema: Schema, path: str = "") -> dict:
    """One bean, its parent's fields first."""
    row = {}
    for f in schema.fields_of(name):
        where = f"{path}.{f.name}" if path else f.name
        try:
            if f.nullable and not buf.read_bool():
                row[f.name] = None
                continue
            row[f.name] = read_value(buf, f.type, schema, where)
        except LubanError as exc:
            raise exc.at(where) from None
    return row


@dataclass(frozen=True)
class Decoded:
    bean: str
    rows: tuple = ()
    trailing: int = 0        # bytes left over; nonzero means the schema is wrong

    @property
    def fields(self) -> tuple:
        seen: dict = {}
        for row in self.rows:
            for key in row:
                seen.setdefault(key, None)
        return tuple(seen)


def read_table(data: bytes, schema: Schema, bean: str, container=None) -> Decoded:
    """Decode a whole table file: a row count, then that many beans.

    `container` is the project's: a callable taking the shipped bytes and
    returning the plaintext Luban blob. Decryption schemes and header layouts
    are facts about one title -- Merge Cooking prefixes four bytes, Mystery Town
    XORs the lot -- so revenant runs the caller's and reports where it stood if
    it throws, rather than shipping a guess about either.
    """
    # The schema first, before a byte is touched. A bean name that is not in the
    # schema is not a fact about the blob, and reporting it as one ("the row
    # count is nonsense") sends the reader to the offset and the key -- two
    # places that are fine.
    schema.fields_of(bean)
    if container is not None:
        try:
            data = container(data)
        except Exception as exc:                  # noqa: BLE001 - the caller's code
            raise LubanError(STAGE_CONTAINER,
                             f"the project's container callable raised {exc!r}") from exc
    buf = ByteBuf(data)
    try:
        count = buf.read_size()
    except LubanError as exc:
        raise LubanError(STAGE_HEADER, "the row count runs past the end of the blob "
                                       "(wrong offset, or still encrypted?)") from exc
    # A row is at least one byte, so a count past what is left cannot be right.
    # Catching it here says "header", which is where to look; letting it run
    # would say "row 4,000,000 field 2", which is not.
    if count > buf.remaining:
        raise LubanError(STAGE_HEADER,
                         f"the row count is {count} and only {buf.remaining} bytes "
                         f"are left (wrong offset, or still encrypted?)", buf.pos)
    rows = []
    for index in range(count):
        try:
            rows.append(read_bean(buf, bean, schema))
        except LubanError as exc:
            raise LubanError(STAGE_ROW,
                             f"row {index} of {count} stopped in "
                             f"{exc.path or 'its first field'}: {exc.message}",
                             exc.offset) from exc
    return Decoded(bean=bean, rows=tuple(rows), trailing=buf.remaining)


# ── where the schema comes from ─────────────────────────────────────────────
#
# The project, and deliberately not revenant. A schema is a list of concrete
# bean names and their fields, which is precisely what CONTEXT.md's bar calls a
# game fact ("具体的类名与命名空间清单"). It is written by reading the title's own
# decompiled `XxxTable(ByteBuf _buf)` constructor -- the loader shipped with the
# game, so the shape of every blob is in the package next to the blob.
#
# Recovering it automatically from that constructor is the `pb-schema` move and
# is worth its own ticket. It is not this one: nothing above needs it, and a
# recoverer this ticket could not check against a real decompiled build would be
# a guess wearing a tool's clothes.

def load_schema(path: str) -> Schema:
    """A schema from a JSON file in the project. See `SCHEMA_DOC`."""
    with open(path, encoding="utf-8") as f:
        return Schema.from_json(json.load(f))


SCHEMA_DOC = """\
{
  "beans": {
    "ItemConf": {
      "parent": "",              // "" or a base bean; the parent's fields read first
      "id": 1234,                // the generated `__ID__`, only for polymorphic beans
      "fields": [
        {"name": "id",     "type": "int"},
        {"name": "name",   "type": "string"},
        {"name": "cost",   "type": "list<int>"},
        {"name": "drops",  "type": "map<int,string>"},
        {"name": "detail", "type": "bean:DetailConf"},
        {"name": "reward", "type": "dynamic:RewardBase"},   // reads a type id first
        {"name": "note",   "type": "string", "nullable": true}
      ]
    }
  },
  "tables": {"tbitem": "ItemConf"}   // data file stem -> the bean its rows are
}

Types: bool byte short int long float double string bytes datetime enum
       sint slong fshort fint flong
       list<T> set<T> array<T> map<K,V> bean:Name dynamic:Name
"""
