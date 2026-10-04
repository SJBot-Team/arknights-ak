"""Protobuf schemas out of Cpp2IL stubs, and field numbers out of the binary.

Two real projects (Hotel Legacy, Tasty Travels; both CenturyGame conf codegen)
carried the same two scripts (#32):

**Schema from stubs.** Google.Protobuf codegen leaves `XxxFieldNumber` const
fields and typed instance fields (`RepeatedField<T>`, `MapField<K,V>`) in the
C# stubs, so a message's field numbers, names and wire kinds can be read off
the DiffableCs output without running anything. With that schema the game's
`$CGF$` config tables decode straight to JSON.

**Field numbers from the parser.** The newer `ProtoBaseProxy` codegen drops the
`FieldNumber` consts, and the field order in the stub does not follow the
field numbers. But the generated `ProxyInternalMergeFrom` is a binary-search
switch on the wire tag with a rigid shape:

    cmp  w0, #TAG ; b.eq HANDLER      -> HANDLER decodes that tag
    cmp  w0, #TAG ; b.ne DEFAULT      -> the fall-through decodes that tag
    HANDLER:  ... str w0, [x20, #FIELD_OFFSET]

so `tag >> 3` is the field number and `[x20, #off]` looks the field up in the
stub's `[FieldOffset]`. Disassembling every MergeFrom with capstone recovered
5,943 of 6,006 fields (98.95%) on the reference title, and a wire-type
consistency check across all of them found zero conflicts.

Nothing here knows a game: no table names, no keys, no offsets. ARM64 only for
the recovery pass; that is what both reference titles ship.
"""

from __future__ import annotations

import json
import os
import re
import struct
from dataclasses import dataclass, field

# ── schema from stubs ───────────────────────────────────────────────────────

FIELDNUM_RE = re.compile(r"public const int (\w+)FieldNumber = (\d+);")
INSTFIELD_RE = re.compile(r"private (?:readonly )?([\w<>\[\], `.]+?) (\w+_);\s*//Field offset")
CLASS_RE = re.compile(r"public sealed class (\w+) : IMessage")
ENUM_RE = re.compile(r"public enum (\w+)")
ENUMVAL_RE = re.compile(r"^\t(\w+) = (-?\d+),?$", re.M)

PRIMITIVE = {
    "int": ("varint", "int32"), "Int32": ("varint", "int32"),
    "long": ("varint", "int64"), "Int64": ("varint", "int64"),
    "uint": ("varint", "uint32"), "UInt32": ("varint", "uint32"),
    "ulong": ("varint", "uint64"), "UInt64": ("varint", "uint64"),
    "bool": ("varint", "bool"), "Boolean": ("varint", "bool"),
    "float": ("fixed32", "float"), "Single": ("fixed32", "float"),
    "double": ("fixed64", "double"), "Double": ("fixed64", "double"),
    "string": ("bytes", "string"), "String": ("bytes", "string"),
    "ByteString": ("bytes", "bytes"),
}


def split_generic(text: str) -> list[str]:
    depth, cur, out = 0, "", []
    for ch in text:
        if ch == "," and depth == 0:
            out.append(cur)
            cur = ""
            continue
        if ch == "<":
            depth += 1
        elif ch == ">":
            depth -= 1
        cur += ch
    out.append(cur)
    return [x.strip() for x in out]


def describe_field(name: str, ctype: str) -> dict:
    """One field descriptor from a declared C# type: map, repeated or single.

    Public because a project that recovers its own field numbers has to build
    the same descriptors -- one title's script was reaching into a private name
    to do it, which is the tell that the absorbed half stopped a function short
    (#50). `Schema.from_recovered` is the entry that removes the need.
    """
    ctype = ctype.strip().replace("`1", "").replace("`2", "")
    if ctype.startswith("MapField<"):
        key, value = split_generic(ctype[len("MapField<"):-1])
        return {"name": name, "kind": "map", "key": key, "value": value}
    if ctype.startswith("RepeatedField<"):
        return {"name": name, "kind": "repeated", "ctype": ctype[len("RepeatedField<"):-1].strip()}
    return {"name": name, "kind": "single", "ctype": ctype}


@dataclass
class Schema:
    """Messages and enums read off a directory of Cpp2IL stubs."""

    messages: dict = field(default_factory=dict)   # name -> {num: field descriptor}
    enums: dict = field(default_factory=dict)      # name -> {value: name}

    @classmethod
    def from_stubs(cls, stub_dir: str) -> "Schema":
        schema = cls()
        for fn in sorted(os.listdir(stub_dir)):
            if not fn.endswith(".cs"):
                continue
            with open(os.path.join(stub_dir, fn), encoding="utf-8", errors="replace") as f:
                text = f.read()
            for m in ENUM_RE.finditer(text):
                schema.enums.setdefault(m.group(1), {int(v): n for n, v in ENUMVAL_RE.findall(text)})
            cm = CLASS_RE.search(text)
            if not cm:
                continue
            nums = {n.lower(): int(v) for n, v in FIELDNUM_RE.findall(text)}
            fields = {}
            for ctype, iname in INSTFIELD_RE.findall(text):
                base = iname[:-1]
                num = nums.get(base.lower())
                if num is not None:
                    fields[num] = describe_field(base, ctype)
            schema.messages[cm.group(1)] = fields
        return schema

    @classmethod
    def from_recovered(cls, stub_dir: str, recovered: dict) -> "Schema":
        """A schema whose field numbers come from `recover_schema`, enums from the stubs.

        The newer codegen drops the `FieldNumber` consts, so `from_stubs` cannot
        number the fields; `recover_schema` reads them out of the parser instead.
        The enums are still declared in the stubs and are not recovered, so the
        two halves are joined here rather than in each project's script.

        Field numbers arrive as ints from `recover_schema` and as strings once
        they have been through JSON; both are accepted.
        """
        schema = cls.from_stubs(stub_dir)
        schema.messages = {
            name: {int(num): describe_field(fd["name"], fd["ctype"])
                   for num, fd in fields.items()}
            for name, fields in recovered.items()
        }
        return schema

    def kind_of(self, ctype: str) -> str:
        if ctype in PRIMITIVE:
            return "primitive"
        if ctype in self.enums and ctype not in self.messages:
            return "enum"
        if ctype in self.messages:
            return "message"
        return "unknown"

    def to_proto(self) -> str:
        lines = []
        for name in sorted(self.enums):
            lines.append(f"enum {name} {{")
            for v, n in sorted(self.enums[name].items()):
                lines.append(f"  {n} = {v};")
            lines.append("}\n")
        for name in sorted(self.messages):
            lines.append(f"message {name} {{")
            for num in sorted(self.messages[name]):
                fd = self.messages[name][num]
                if fd["kind"] == "map":
                    lines.append(f"  map<{fd['key']}, {fd['value']}> {fd['name']} = {num};")
                elif fd["kind"] == "repeated":
                    lines.append(f"  repeated {fd['ctype']} {fd['name']} = {num};")
                else:
                    lines.append(f"  {fd['ctype']} {fd['name']} = {num};")
            lines.append("}\n")
        return "\n".join(lines)


# ── wire decoding ───────────────────────────────────────────────────────────

def read_varint(b: bytes, i: int) -> tuple[int, int]:
    r = s = 0
    while True:
        x = b[i]
        i += 1
        r |= (x & 0x7F) << s
        if not x & 0x80:
            return r, i
        s += 7


def parse_fields(b: bytes):
    """Yield (field number, wire type, payload)."""
    i, n = 0, len(b)
    while i < n:
        key, i = read_varint(b, i)
        fn, wt = key >> 3, key & 7
        if wt == 0:
            v, i = read_varint(b, i)
            yield fn, wt, v
        elif wt == 1:
            yield fn, wt, b[i:i + 8]
            i += 8
        elif wt == 2:
            ln, i = read_varint(b, i)
            yield fn, wt, b[i:i + ln]
            i += ln
        elif wt == 5:
            yield fn, wt, b[i:i + 4]
            i += 4
        else:
            raise ValueError(f"bad wire type {wt}")


def _scalar(schema: Schema, ctype: str, wt: int, payload):
    kind = schema.kind_of(ctype)
    if kind == "enum":
        v = payload if wt == 0 else int.from_bytes(payload, "little")
        return schema.enums[ctype].get(v, v)
    if kind == "message":
        return decode_message(schema, ctype, payload)
    _wire, pt = PRIMITIVE.get(ctype, ("bytes", "bytes"))
    if pt == "string":
        return payload.decode("utf-8", "replace")
    if pt == "bytes":
        return payload.hex()
    if pt == "bool":
        return bool(payload)
    if pt == "float":
        return round(struct.unpack("<f", payload)[0], 6)
    if pt == "double":
        return struct.unpack("<d", payload)[0]
    if pt in ("int32", "int64"):
        v = payload if wt == 0 else int.from_bytes(payload, "little")
        if v >= (1 << 63):
            v -= 1 << 64
        elif pt == "int32" and v >= (1 << 31):
            v -= 1 << 32
        return v
    return payload


def _unpack_packed(schema: Schema, ctype: str, payload: bytes):
    _wire, pt = PRIMITIVE.get(ctype, (None, None))
    out, i = [], 0
    if pt in ("int32", "int64", "uint32", "uint64", "bool") or schema.kind_of(ctype) == "enum":
        while i < len(payload):
            v, i = read_varint(payload, i)
            out.append(_scalar(schema, ctype, 0, v))
    elif pt == "float":
        for j in range(0, len(payload), 4):
            out.append(round(struct.unpack("<f", payload[j:j + 4])[0], 6))
    elif pt == "double":
        for j in range(0, len(payload), 8):
            out.append(struct.unpack("<d", payload[j:j + 8])[0])
    else:
        return None
    return out


def decode_message(schema: Schema, name: str, data: bytes) -> dict:
    spec = schema.messages.get(name)
    if spec is None:
        return {"__raw__": data.hex()}
    out: dict = {}
    for fn, wt, payload in parse_fields(data):
        fd = spec.get(fn)
        if fd is None:
            out.setdefault(f"field_{fn}", []).append(payload if wt == 0 else payload.hex())
            continue
        if fd["kind"] == "map":
            kv = {}
            for kfn, kwt, kpl in parse_fields(payload):
                if kfn == 1:
                    kv["k"] = _scalar(schema, fd["key"], kwt, kpl)
                elif kfn == 2:
                    kv["v"] = _scalar(schema, fd["value"], kwt, kpl)
            out.setdefault(fd["name"], {})[str(kv.get("k"))] = kv.get("v")
        elif fd["kind"] == "repeated":
            lst = out.setdefault(fd["name"], [])
            if wt == 2 and schema.kind_of(fd["ctype"]) != "message" and \
                    PRIMITIVE.get(fd["ctype"], (None, None))[1] not in ("string", "bytes"):
                vals = _unpack_packed(schema, fd["ctype"], payload)
                if vals is not None:
                    lst.extend(vals)
                    continue
            lst.append(_scalar(schema, fd["ctype"], wt, payload))
        else:
            out[fd["name"]] = _scalar(schema, fd["ctype"], wt, payload)
    return out


# ── a directory of tables, decoded in one pass ──────────────────────────────

DECODED = "ok"
NO_SCHEMA = "no-schema"
DECODE_ERROR = "error"


@dataclass
class TableResult:
    table: str
    status: str
    size: int
    data: dict | None = None
    detail: str = ""


@dataclass
class DecodeReport:
    results: list = field(default_factory=list)

    @property
    def tally(self) -> dict:
        out: dict = {}
        for r in self.results:
            out[r.status] = out.get(r.status, 0) + 1
        return out

    def decoded(self) -> list:
        return [r for r in self.results if r.status == DECODED]


def decode_tables(schema: Schema, pb_dir: str, suffix: str = ".pb") -> DecodeReport:
    """Decode every `<Message><suffix>` in a directory, one entry per file.

    Two titles wrapped the same loop around `decode_message`. Three statuses have
    to be told apart because the follow-up differs: a table with no schema needs
    the schema widened, one that raised needs its bytes looked at, and neither is
    a decode. One bad table never stops the batch.

    Nothing is written here. Where the JSON lands, what an index file records and
    how a "row" is counted are facts about the title's table layout and stay with
    the caller (#50).
    """
    report = DecodeReport()
    for name in sorted(os.listdir(pb_dir)):
        if not name.endswith(suffix):
            continue
        table = name[:-len(suffix)]
        with open(os.path.join(pb_dir, name), "rb") as f:
            data = f.read()
        if table not in schema.messages:
            report.results.append(TableResult(table, NO_SCHEMA, len(data)))
            continue
        try:
            decoded = decode_message(schema, table, data)
        except Exception as exc:
            report.results.append(
                TableResult(table, DECODE_ERROR, len(data), detail=f"{type(exc).__name__}: {exc}"))
            continue
        report.results.append(TableResult(table, DECODED, len(data), data=decoded))
    return report


# ── field numbers from the parser (ARM64, capstone) ─────────────────────────

FIELD_RE = re.compile(
    r'\[FieldOffset\(Offset = "(0x[0-9A-Fa-f]+)"\)\]\s*\n'
    r"(?:\s*\[[^\]]*\]\s*\n)*"
    r"\s*public (?:readonly )?([\w<>\[\], `.]+?) (\w+); *//Field offset", re.M)
MERGEFROM_RE = re.compile(
    r'\[Address\(RVA = "(0x[0-9A-Fa-f]+)", Offset = "(0x[0-9A-Fa-f]+)", Length = "(0x[0-9A-Fa-f]+)"\)\]\s*\n'
    r"(?:\s*\[[^\]]*\]\s*\n)*"
    r"\s*public virtual void ProxyInternalMergeFrom\(ref ParseContext input\)")
PROXY_CLASS_RE = re.compile(r"public sealed class (\w+) : ProtoBaseProxy")
_X20_ACCESS = re.compile(r"\[x20(?:, #(0x[0-9a-f]+|\d+))?\]")
_HANDLER_WINDOW = 24


@dataclass
class ProxyStub:
    name: str
    fields: dict            # offset -> (name, ctype)
    merge_from: tuple | None   # (file offset, length) of ProxyInternalMergeFrom


def parse_proxy_stub(path: str) -> ProxyStub | None:
    with open(path, encoding="utf-8", errors="replace") as f:
        text = f.read()
    cm = PROXY_CLASS_RE.search(text)
    if not cm:
        return None
    fields = {int(off, 16): (name, ctype.strip()) for off, ctype, name in FIELD_RE.findall(text)}
    mm = MERGEFROM_RE.search(text)
    merge = (int(mm.group(2), 16), int(mm.group(3), 16)) if mm else None
    return ProxyStub(cm.group(1), fields, merge)


def recover_field_numbers(md, blob: bytes, start: int, length: int, field_offsets) -> dict:
    """{field number: field offset} for one MergeFrom body. `md` is a capstone ARM64 disassembler."""
    insns = list(md.disasm(blob[start:start + length], start))
    by_addr = {i.address: n for n, i in enumerate(insns)}
    handlers: dict = {}          # handler address -> tag
    last_cmp = None
    for n, insn in enumerate(insns):
        if insn.mnemonic == "cmp" and insn.op_str.startswith("w0, #"):
            try:
                last_cmp = int(insn.op_str.split("#")[1], 0)
            except ValueError:
                last_cmp = None
        elif insn.mnemonic in ("b.eq", "b.ne") and last_cmp is not None:
            target = int(insn.op_str.lstrip("#"), 0)
            if insn.mnemonic == "b.eq":
                handlers.setdefault(target, last_cmp)
            elif n + 1 < len(insns):
                handlers.setdefault(insns[n + 1].address, last_cmp)
    out: dict = {}
    for addr, tag in handlers.items():
        n = by_addr.get(addr)
        if n is None:
            continue
        for insn in insns[n:n + _HANDLER_WINDOW]:
            m = _X20_ACCESS.search(insn.op_str)
            if m and insn.mnemonic.startswith(("str", "ldr", "stur", "ldur")):
                off = int(m.group(1), 0) if m.group(1) else 0
                if off in field_offsets:
                    out.setdefault(tag >> 3, off)
                    break
            if insn.mnemonic in ("b", "ret"):
                break
    return out


def recover_schema(stub_dir: str, binary_path: str) -> tuple[dict, dict]:
    """(schema, stats): field numbers for every ProtoBaseProxy message in `stub_dir`."""
    from capstone import CS_ARCH_ARM64, CS_MODE_LITTLE_ENDIAN, Cs
    with open(binary_path, "rb") as f:
        blob = f.read()
    md = Cs(CS_ARCH_ARM64, CS_MODE_LITTLE_ENDIAN)
    schema: dict = {}
    stats = {"classes": 0, "no_method": 0, "fields_total": 0, "fields_mapped": 0,
             "full": 0, "partial": 0}
    for fn in sorted(os.listdir(stub_dir)):
        if not fn.endswith(".cs"):
            continue
        stub = parse_proxy_stub(os.path.join(stub_dir, fn))
        if stub is None:
            continue
        stats["classes"] += 1
        stats["fields_total"] += len(stub.fields)
        if stub.merge_from is None or not stub.fields:
            stats["no_method"] += 1
            continue
        got = recover_field_numbers(md, blob, stub.merge_from[0], stub.merge_from[1], set(stub.fields))
        mapped = {}
        for num, off in got.items():
            name, ctype = stub.fields[off]
            mapped[num] = {"name": name, "ctype": ctype, "offset": off}
        covered = {v["offset"] for v in mapped.values()}
        stats["fields_mapped"] += len(covered)
        stats["full" if covered == set(stub.fields) else "partial"] += 1
        schema[stub.name] = mapped
    return schema, stats


def dump_json(obj, path: str) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=1, ensure_ascii=False)
