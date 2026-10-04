"""Channel 1 of the merge-games-re backflow: code that carries no game fact,
with the game-specific facts left behind in the projects.

The bar is "does this hold a game fact"; it is stated once, in
`docs/adr/0004-what-qualifies-to-move-into-revenant.md`.

Seams: `strings`, `protobuf`, `flatbuffers`, `assets.bundle_payload`,
`contrib.*` directly, on synthetic inputs. The real-corpus reproduction
(dump_strlit bucket counts, recover_tags 5943/6006, fbschema's 4,854 slots, the
by-script histogram) is checked by hand against the projects and recorded in the
tickets; here we pin the mechanics.
"""

from __future__ import annotations

import hashlib
import json
import os
import struct
import zipfile

from revenant import protobuf as _pb
from revenant import strings as _strings


def _metadata(literals, names=(b"Foo", b"Bar")):
    """A plaintext metadata blob with a string-literal table and a name heap."""
    data = b"".join(s.encode() for s in literals)
    entries = bytearray()
    at = 0
    for s in literals:
        entries += struct.pack("<ii", len(s.encode()), at)
        at += len(s.encode())
    name_heap = b"\x00".join(names) + b"\x00"
    header_len = 32
    lit_off = header_len
    data_off = lit_off + len(entries)
    s_off = data_off + len(data)
    header = struct.pack("<II", _strings.METADATA_SANITY, 29)
    header += struct.pack("<6i", lit_off, len(entries), data_off, len(data), s_off, len(name_heap))
    header += bytes(header_len - len(header))
    return header + bytes(entries) + data + name_heap


# ── strings ─────────────────────────────────────────────────────────────────

def test_string_literals_and_names_are_read_from_the_table():
    blob = _metadata(["https://cdn.example.com/x", "shop_open_click", "Game.Config.Level"],
                     names=[b"SomeType", b"AnotherType"])
    version, literals, names = _strings.read_literals(blob)
    assert version == 29
    assert literals == ["https://cdn.example.com/x", "shop_open_click", "Game.Config.Level"]
    assert names == ["SomeType", "AnotherType"]


def test_buckets_are_by_shape_and_a_string_can_land_in_several():
    literals = [
        "https://cdn.example.com/a",   # urls
        "level_up_click",              # analytics-events
        "Game.Config.MaxLevel",        # config-keys
        "you have {0} coins",          # format-strings
        "isTutorialDone",              # flags-toggles
        "ui/panel/main",               # paths-addresses
        "hi",                          # too short, no bucket
    ]
    buckets = _strings.bucket(literals)
    assert buckets["urls"] == ["https://cdn.example.com/a"]
    assert "level_up_click" in buckets["analytics-events"]
    assert "Game.Config.MaxLevel" in buckets["config-keys"]
    assert "you have {0} coins" in buckets["format-strings"]
    assert "isTutorialDone" in buckets["flags-toggles"]
    assert "ui/panel/main" in buckets["paths-addresses"]
    assert all("hi" not in hits for hits in buckets.values())


def test_a_non_plaintext_blob_is_rejected():
    import pytest
    with pytest.raises(ValueError):
        _strings.read_literals(b"\x00" * 64)


def test_the_dump_writes_the_files_notes_cite(tmp_path):
    sd = _strings.StringDump(
        metadata_version=29, literals=["a_b_c", "plain"], names=["N"],
        buckets=_strings.bucket(["a_b_c", "plain"]))
    stats = _strings.write_dump(sd, str(tmp_path))
    assert (tmp_path / "string-literals.txt").exists()
    assert (tmp_path / "metadata-names.txt").exists()
    assert (tmp_path / "lit-analytics-events.txt").exists()
    assert stats["string_literals"] == 2


# ── protobuf schema from stubs ──────────────────────────────────────────────

_STUB = '''
public sealed class LevelConf : IMessage
{
    public const int IdFieldNumber = 1;
    public const int NameFieldNumber = 2;
    public const int RewardsFieldNumber = 3;
    public const int TableFieldNumber = 4;
    private int id_; //Field offset
    private string name_; //Field offset
    private RepeatedField<int> rewards_; //Field offset
    private MapField<int, string> table_; //Field offset
}
'''


def test_schema_reads_field_numbers_names_and_wire_kinds_from_stubs(tmp_path):
    (tmp_path / "LevelConf.cs").write_text(_STUB)
    schema = _pb.Schema.from_stubs(str(tmp_path))
    fields = schema.messages["LevelConf"]
    assert fields[1] == {"name": "id", "kind": "single", "ctype": "int"}
    assert fields[2]["ctype"] == "string"
    assert fields[3] == {"name": "rewards", "kind": "repeated", "ctype": "int"}
    assert fields[4] == {"name": "table", "kind": "map", "key": "int", "value": "string"}


def test_schema_round_trips_a_message_it_encoded(tmp_path):
    (tmp_path / "LevelConf.cs").write_text(_STUB)
    schema = _pb.Schema.from_stubs(str(tmp_path))
    # id=7 (tag 0x08), name="lv" (tag 0x12), rewards=[1,2] packed (tag 0x1a)
    blob = bytes([0x08, 7, 0x12, 2]) + b"lv" + bytes([0x1a, 2, 1, 2])
    decoded = _pb.decode_message(schema, "LevelConf", blob)
    assert decoded == {"id": 7, "name": "lv", "rewards": [1, 2]}


def test_to_proto_emits_map_repeated_and_scalar(tmp_path):
    (tmp_path / "LevelConf.cs").write_text(_STUB)
    proto = _pb.Schema.from_stubs(str(tmp_path)).to_proto()
    assert "map<int, string> table = 4;" in proto
    assert "repeated int rewards = 3;" in proto
    assert "int id = 1;" in proto


def test_an_unknown_field_number_is_kept_not_dropped(tmp_path):
    (tmp_path / "LevelConf.cs").write_text(_STUB)
    schema = _pb.Schema.from_stubs(str(tmp_path))
    blob = bytes([0x08, 7, 0x40, 99])   # field 8, varint 99, not in the schema
    decoded = _pb.decode_message(schema, "LevelConf", blob)
    assert decoded["id"] == 7
    assert decoded["field_8"] == [99]


# ── protobuf field numbers from a MergeFrom switch (ARM64) ──────────────────

def test_field_numbers_are_recovered_from_a_binary_search_switch():
    """The recover_tags shape: `cmp w0,#tag; b.eq H; H: str w0,[x20,#off]`.

    Assemble a tiny ARM64 MergeFrom for two fields and confirm tag>>3 maps to
    the stub's [FieldOffset]. This is the mechanism recover_tags used to pull
    5,943/6,006 fields on the reference title.
    """
    from capstone import CS_ARCH_ARM64, CS_MODE_LITTLE_ENDIAN, Cs

    def cmp_w0(imm):      # cmp w0, #imm  == subs wzr, w0, #imm
        return 0x7100001F | (imm << 10)

    def b_eq(delta):      # b.eq . + delta   (delta in bytes, /4 into imm19)
        return 0x54000000 | (((delta // 4) & 0x7FFFF) << 5)

    def str_x20(off):     # str w0, [x20, #off]
        return 0xB9000280 | ((off // 4) << 10)

    # layout: [0]cmp 8  [1]b.eq ->H1(+16)  [2]cmp 16  [3]b.eq ->H2(+12)
    #         [4]ret    [5]H1: str [x20,#0x10]  [6]ret  [7]H2: str [x20,#0x20] [8]ret
    words = [cmp_w0(8), b_eq(16), cmp_w0(16), b_eq(16), 0xD65F03C0,
             str_x20(0x10), 0xD65F03C0, str_x20(0x20), 0xD65F03C0]
    blob = b"".join(struct_word(w) for w in words)
    md = Cs(CS_ARCH_ARM64, CS_MODE_LITTLE_ENDIAN)
    got = _pb.recover_field_numbers(md, blob, 0, len(blob), {0x10, 0x20})
    assert got == {1: 0x10, 2: 0x20}   # tag 8>>3 == field 1, tag 16>>3 == field 2


def struct_word(w: int) -> bytes:
    return struct.pack("<I", w)


_PROXY_STUB = '''
public sealed class OrderConf : ProtoBaseProxy
{
    [FieldOffset(Offset = "0x10")]
    public int Id; //Field offset
    [FieldOffset(Offset = "0x20")]
    public string Name; //Field offset
    [Address(RVA = "0x1000", Offset = "0x0", Length = "0x24")]
    public virtual void ProxyInternalMergeFrom(ref ParseContext input)
}
'''


def test_a_proxy_stub_yields_its_fields_and_mergefrom_slice(tmp_path):
    (tmp_path / "OrderConf.cs").write_text(_PROXY_STUB)
    stub = _pb.parse_proxy_stub(str(tmp_path / "OrderConf.cs"))
    assert stub.name == "OrderConf"
    assert stub.fields == {0x10: ("Id", "int"), 0x20: ("Name", "string")}
    assert stub.merge_from == (0x0, 0x24)   # file offset, length


# ── protobuf: a batch of tables, and a schema from recovered field numbers ──

_ENUM_STUB = '''
public enum Rarity
{
	Common = 0,
	Rare = 1,
}

public sealed class OrderConf : ProtoBaseProxy
{
    [FieldOffset(Offset = "0x10")]
    public int Id; //Field offset
}
'''


def test_a_batch_of_tables_decodes_and_one_bad_table_does_not_stop_the_rest(tmp_path):
    """What `decode_all.py` and `decode_tt.py` both wrapped around the decoder.

    Three statuses have to be told apart, because the follow-up differs: a table
    with no schema needs the schema widened, one that raised needs the bytes
    looked at, and neither is a decode.
    """
    stubs, pbs = tmp_path / "stubs", tmp_path / "pb"
    stubs.mkdir()
    pbs.mkdir()
    (stubs / "LevelConf.cs").write_text(_STUB)
    (stubs / "ShopConf.cs").write_text(_STUB.replace("LevelConf", "ShopConf"))
    schema = _pb.Schema.from_stubs(str(stubs))
    (pbs / "LevelConf.pb").write_bytes(bytes([0x08, 7, 0x12, 2]) + b"lv")
    (pbs / "ShopConf.pb").write_bytes(bytes([0x0F]))     # wire type 7 does not exist
    (pbs / "GhostConf.pb").write_bytes(b"\x08\x01")      # no stub declares it
    (pbs / "notes.txt").write_bytes(b"not a table")

    report = _pb.decode_tables(schema, str(pbs))
    assert report.tally == {"ok": 1, "no-schema": 1, "error": 1}
    by_table = {r.table: r for r in report.results}
    assert by_table["LevelConf"].data == {"id": 7, "name": "lv"}
    assert by_table["ShopConf"].data is None and "wire type" in by_table["ShopConf"].detail
    assert by_table["GhostConf"].size == 2
    assert "notes" not in by_table, "only the .pb files are tables"


def test_recovered_field_numbers_reach_a_schema_through_a_public_entry(tmp_path):
    """`decode_tt.py` had to call `protobuf._describe` to build this, which is
    the tell that the absorbed half stopped one function short (#50)."""
    (tmp_path / "OrderConf.cs").write_text(_ENUM_STUB)
    recovered = {"OrderConf": {1: {"name": "Id", "ctype": "int", "offset": 0x10},
                               "2": {"name": "Kind", "ctype": "Rarity", "offset": 0x14}}}
    schema = _pb.Schema.from_recovered(str(tmp_path), recovered)
    assert schema.messages["OrderConf"][1] == {"name": "Id", "kind": "single", "ctype": "int"}
    assert schema.messages["OrderConf"][2]["name"] == "Kind", "string keys count too"
    assert schema.enums["Rarity"] == {0: "Common", 1: "Rare"}, "enums still come from the stubs"
    # the field numbers won, not the stub's own reading of the class
    assert _pb.decode_message(schema, "OrderConf", bytes([0x08, 3, 0x10, 1])) == \
        {"Id": 3, "Kind": "Rare"}
    assert callable(_pb.describe_field), "the name projects need is public"


# ── FlatBuffers: shape without a schema ─────────────────────────────────────

def _fb_buffer() -> bytes:
    """A root table with a scalar, a string and a vector, laid out by hand.

    Written byte by byte rather than through a builder library, because the
    claim under test is that the walk needs nothing but the encoding -- a
    fixture built by the same library that reads it would not test that.
    """
    buf = bytearray(0x4C)
    struct.pack_into("<I", buf, 0x00, 0x20)             # root uoffset
    struct.pack_into("<5H", buf, 0x10, 10, 16, 4, 8, 12)  # vtable: len, table len, 3 slots
    struct.pack_into("<i", buf, 0x20, 0x20 - 0x10)      # soffset back to the vtable
    struct.pack_into("<i", buf, 0x24, 42)               # slot 0: a scalar
    struct.pack_into("<I", buf, 0x28, 0x30 - 0x28)      # slot 1: -> string
    struct.pack_into("<I", buf, 0x2C, 0x3C - 0x2C)      # slot 2: -> vector
    struct.pack_into("<I", buf, 0x30, 6)                # string length
    buf[0x34:0x3B] = b"energy\x00"                      # NUL-terminated, as FlatBuffers writes
    struct.pack_into("<I", buf, 0x3C, 3)                # vector count
    struct.pack_into("<3i", buf, 0x40, 7, 8, 9)
    return bytes(buf)


def test_a_flatbuffers_table_gives_up_its_shape_and_strings_with_no_schema():
    from revenant import flatbuffers as fb
    shape = fb.walk(_fb_buffer())
    assert shape.slots == 3, "the vtable states the slot count even with no names"
    assert {s.index: s.reading.kind for s in shape.present} == \
        {0: "scalar", 1: "string", 2: "vector"}
    by_index = {s.index: s.reading for s in shape.present}
    assert by_index[1].value == "energy"
    assert by_index[2].value == (3, "scalar"), "count and probed element kind"
    assert by_index[0].value["i32"] == 42


def test_every_type_this_layer_reports_is_labelled_as_inferred():
    """The distinction the ticket is built on: a probed type and a declared type
    are not the same claim, and only the schema layer can make the second."""
    from revenant import flatbuffers as fb
    shape = fb.walk(_fb_buffer())
    assert all(s.reading.inferred for s in shape.present)


def test_strings_are_found_by_their_length_word_not_by_printable_runs():
    from revenant import flatbuffers as fb
    assert fb.strings(_fb_buffer()) == [(0x34, "energy")]


# ── FlatBuffers: the schema, recovered from the generated code ──────────────

_FB_ISIL = """Type: Game.CMS.CurrencyDefinition

Method: System.Int32 SerializeToBuffer(FlatBufferBuilder builder)
\tISIL:
\t\t000 Move X20, X0
\t\t001 Move W1, 2
\t\t002 Call FlatBufferBuilder.StartObject
\t\t003 Move W2, [X20+40]
\t\t004 Move W1, W31
\t\t005 Call FlatBufferBuilder.AddInt, X0, X1, W2, W3
\t\t006 Move X2, [X20+48]
\t\t007 Move W1, 1
\t\t008 Call FlatBufferBuilder.AddOffset, X0, X1, X2, X3
\t\t009 Move W2, [X9+8]
\t\t010 Move W1, 5
\t\t011 Call FlatBufferBuilder.AddBool, X0, X1, W2, W3
\t\t012 Call FlatBufferBuilder.EndObject
\tDisassembly:
\t\t0x0 nop
"""

_FB_CS = """public sealed class CurrencyDefinition : CmsItem
{
\tprivate int m_id; //Field offset: 0x28
\tprivate string m_name; //Field offset: 0x30
}
"""


def _fb_stubs(tmp_path):
    isil, src = tmp_path / "IsilDump", tmp_path / "src"
    (isil / "Game").mkdir(parents=True)
    (src / "Game").mkdir(parents=True)
    (isil / "Game" / "CurrencyDefinition.txt").write_text(_FB_ISIL)
    (src / "Game" / "CurrencyDefinition.cs").write_text(_FB_CS)
    return str(isil), str(src)


def test_a_flatbuffers_slot_takes_its_type_from_the_add_call_and_its_name_from_the_offset(tmp_path):
    """Neither half is inferred: `AddInt` *is* the type, and `this+0x28` is the
    join key onto the reconstructed C# field. Same shape as `pb-tags`."""
    from revenant import flatbuffers as fb
    recovered = fb.recover_schema(*_fb_stubs(tmp_path))
    entry = recovered.classes["Game.CMS.CurrencyDefinition"]
    assert entry["slots"] == 2, "StartObject states it; declaration order does not"
    assert entry["fields"][0] == {"name": "m_id", "fb_type": "int32",
                                  "cs_type": "int", "offset": 0x28}
    assert entry["fields"][1]["name"] == "m_name"
    assert entry["fields"][1]["fb_type"] == "offset"
    assert entry["base"] == "CmsItem"


def test_a_slot_whose_source_was_not_traced_is_listed_not_dropped(tmp_path):
    """Coverage has to be readable off the output. A slot that silently vanishes
    reads as a schema that is complete."""
    from revenant import flatbuffers as fb
    recovered = fb.recover_schema(*_fb_stubs(tmp_path))
    assert recovered.unresolved == [("Game.CMS.CurrencyDefinition", 5, "bool")]
    assert 5 not in recovered.classes["Game.CMS.CurrencyDefinition"]["fields"]


# ── FlatBuffers: decoding against the recovered schema ──────────────────────

def _fb_schema(extra_type="Game.Unknown"):
    from revenant import flatbuffers as fb
    return fb.Schema.from_dict({"classes": {"Game.CMS.CurrencyDefinition": {
        "slots": 3, "base": None, "fields": {
            "0": {"name": "m_id", "fb_type": "int32", "cs_type": "int"},
            "1": {"name": "m_name", "fb_type": "offset", "cs_type": "string"},
            "2": {"name": "m_extra", "fb_type": "offset", "cs_type": extra_type}}}}})


def test_a_declared_schema_puts_names_and_real_types_on_the_numbers():
    from revenant import flatbuffers as fb
    reader = fb.Reader(_fb_buffer(), _fb_schema(extra_type="string"))
    doc = reader.read("CurrencyDefinition")
    assert doc["m_id"] == 42, "declared int32, not a probed guess"
    assert doc["m_name"] == "energy"


def test_an_offset_slot_the_declared_type_cannot_place_falls_back_to_probing():
    """`offset` says "a relative pointer" and nothing more. When the declared C#
    type does not resolve, the target is probed the way the no-schema layer does
    -- and the value says so, so a reader can tell the two apart."""
    from revenant import flatbuffers as fb
    reader = fb.Reader(_fb_buffer(), _fb_schema())
    doc = reader.read("CurrencyDefinition")
    assert doc["m_extra"] == "?vector[3]"
    assert reader.inferred == [("m_extra", "vector")]
    assert doc["m_id"] == 42 and reader.inferred == [("m_extra", "vector")], \
        "a declared read is not logged as inferred"


def test_a_slot_the_schema_does_not_declare_at_all_is_kept_and_marked():
    from revenant import flatbuffers as fb
    schema = fb.Schema.from_dict({"classes": {"X.CurrencyDefinition": {
        "slots": 3, "fields": {"0": {"name": "m_id", "fb_type": "int32", "cs_type": "int"}}}}})
    reader = fb.Reader(_fb_buffer(), schema)
    doc = reader.read("CurrencyDefinition")
    assert doc["m_id"] == 42
    assert doc["slot1?"] == "?string:energy"
    assert [path for path, _ in reader.inferred] == ["slot1?", "slot2?"]


def test_a_container_type_is_the_callers_convention_not_the_encodings():
    """`CorvusTable<X>` -> "a one-slot table wrapping the item vector" is a fact
    about one CMS, so the roster is injected; with none given, the same buffer
    reads as a plain table."""
    from revenant import flatbuffers as fb
    schema = fb.Schema.from_dict({"classes": {"X.Db": {"slots": 1, "fields": {
        "0": {"name": "m_items", "fb_type": "offset", "cs_type": "Corvus.Wrap<Thing>"}}}}})
    assert fb.Reader(_fb_buffer(), schema).element_type("Corvus.Wrap<Thing>") == ("table", "Corvus.Wrap<Thing>")
    wrapped = fb.Reader(_fb_buffer(), schema, containers=("Wrap",))
    assert wrapped.element_type("Corvus.Wrap<Thing>") == ("container", "Thing")


# ── assets: the UnityFS-prefix skip ─────────────────────────────────────────

def test_a_bundle_with_a_wrapper_prefix_finds_the_unityfs_stream():
    from revenant import assets
    real = b"UnityFS\x00the rest of the stream"
    assert assets.bundle_payload(b"\x00" * 32 + real) == real
    assert assets.bundle_payload(real) == real


# ── contrib/decrypt: importable, shape-based, no game facts ──────────────────

def _elf64(segments, extra=b""):
    """A minimal ELF64 with the given PT_LOAD segments (vaddr, file_bytes)."""
    ehsize, phentsize = 64, 56
    phnum = len(segments)
    body = bytearray()
    phdrs = bytearray()
    file_cursor = ehsize + phentsize * phnum
    for vaddr, data in segments:
        pad = (file_cursor - len(body) - (ehsize + phentsize * phnum))
        seg_off = ehsize + phentsize * phnum + len(body)
        phdrs += struct.pack("<IIQQQQQQ", 1, 5, seg_off, vaddr, vaddr,
                             len(data), len(data), 0x1000)
        body += data
    header = bytearray(ehsize)
    header[0:4] = b"\x7fELF"
    header[4] = 2
    header[5] = 1
    struct.pack_into("<Q", header, 0x20, ehsize)     # e_phoff
    struct.pack_into("<H", header, 0x36, phentsize)
    struct.pack_into("<H", header, 0x38, phnum)
    return bytes(header) + bytes(phdrs) + bytes(body)


def test_segmented_image_maps_pt_load_and_translates_addresses():
    from revenant.contrib.decrypt import SegmentedImage
    elf = _elf64([(0x1000, b"AAAA"), (0x8000, b"BBBBBB")])
    img = SegmentedImage(elf)
    assert len(img.segments) == 2
    assert img.image_size == 0x8000 + 6
    fo = img.vaddr_to_file(0x8000)
    assert elf[fo:fo + 6] == b"BBBBBB"
    assert img.file_to_vaddr(fo) == 0x8000

    written = {}
    img.map_into(lambda addr, data: written.__setitem__(addr, data), base=0x40000000)
    assert written[0x40000000 + 0x1000] == b"AAAA"


def test_find_dispatcher_matches_by_shape_not_address():
    from revenant.contrib.decrypt import find_dispatcher
    from revenant.contrib.decrypt.findvm import LDRB_W9_X0_POST1, BR_X10
    # ldrb w9,[x0],#1 ; adr x10,#0 ; ldrh ; add ; br x10 ; then junk
    dispatch = struct.pack("<6I", LDRB_W9_X0_POST1, 0x1000000A, 0x787B6909, 0x8B0B294A,
                           BR_X10, 0)
    elf = _elf64([(0x5000, b"\x00" * 16 + dispatch)])
    found = find_dispatcher(elf)
    assert len(found) == 1
    assert found[0].fetch_vaddr == 0x5000 + 16
    assert found[0].handler_base == 0x5000 + 16 + 4    # adr immediate 0


def test_wrap_pe_produces_an_openable_pe_over_a_stripped_image():
    from revenant.contrib.decrypt import wrap_pe
    image = b"\x00" * 0x1200 + b"BSJB" + b"metadata-root-tables" * 8
    out = wrap_pe(image)
    assert out[:2] == b"MZ"
    assert out[0x80:0x84] == b"PE\x00\x00"
    assert b"BSJB" in out            # the metadata survived
    import pytest
    with pytest.raises(ValueError):
        wrap_pe(b"no metadata here")


def test_xxtea_matches_the_reference_implementation_byte_for_byte():
    """A vector from the C `xxtea` library (xxtea-py 2.0.0, cffi build), not from
    this code -- a round-trip alone would pass for any self-consistent variant,
    and CenturyGame's arrangement (length on encrypt, key fixed to 16 bytes) is
    exactly the part that is easy to get subtly wrong."""
    from revenant.contrib.decrypt import xxtea
    data, key = b"Hello World! test vector", b"1234567890"
    reference = bytes.fromhex("35be5f4faa4bf806c8eba16d20c68e9895bbaafa28938b52d66fe027")
    assert xxtea.encrypt(data, key) == reference
    assert xxtea.decrypt(reference, key) == data
    assert xxtea.decrypt(reference, "1234567890") == data      # str keys too


def test_xxtea_round_trips_and_a_short_key_is_padded_not_rejected():
    from revenant.contrib.decrypt import xxtea
    blob = bytes(range(256)) * 3
    assert xxtea.decrypt(xxtea.encrypt(blob, b"k" * 32), b"k" * 32) == blob
    assert xxtea.fix_key(b"abc") == b"abc" + bytes(13)
    assert xxtea.fix_key(b"x" * 20) == b"x" * 16
    # a 10-byte key and the same key zero-padded to 16 are the same key
    assert xxtea.encrypt(blob, b"1234567890") == xxtea.encrypt(blob, b"1234567890" + bytes(6))


def test_a_wrong_key_is_reported_rather_than_returning_noise():
    """The length word is XXTEA's only integrity signal; losing it would turn a
    failed decryption into plausible garbage."""
    from revenant.contrib.decrypt import xxtea
    cipher = xxtea.encrypt(b"some config table", b"right key")
    assert xxtea.decrypt(cipher, b"wrong key") is None


def test_the_cgf_container_is_recognised_and_a_non_container_is_not():
    from revenant.contrib.decrypt import xxtea
    body = b"ciphertext-bytes"
    assert xxtea.cgf_body(xxtea.CGF_MAGIC + b"\x01\x00" + body) == body
    assert xxtea.cgf_body(xxtea.CGF_MAGIC + b"\x01\x00") == b""     # an empty table
    assert xxtea.cgf_body(b"UnityFS\x00not a config table") is None


# ── assets: the type census and the baked-in serialized files ────────────────

class _FakeType:
    def __init__(self, name):
        self.name = name


class _FakeObject:
    def __init__(self, type_name, path_id=1, **attrs):
        self.type = _FakeType(type_name)
        self.path_id = path_id
        self._attrs = attrs

    def read(self):
        return type("Read", (), self._attrs)()


class _FakeEnv:
    def __init__(self, objects):
        self.objects = objects
        self.cabs = {}


def _loader(mapping):
    """A stand-in for UnityPy.load: payload head -> environment."""
    def load(stream):
        data = stream.read() if hasattr(stream, "read") else stream
        for head, env in mapping.items():
            if data.startswith(head):
                return env
        raise ValueError("unparseable bundle")
    return load


def test_the_type_census_counts_objects_without_unpacking_anything():
    from revenant import assets
    env = _FakeEnv([_FakeObject("Texture2D"), _FakeObject("Texture2D"),
                    _FakeObject("MonoBehaviour"), _FakeObject("TextAsset")])
    members = [("a.bundle", b"UnityFS-a" + b"\x00" * 8),
               ("b.bundle", b"UnityFS-b" + b"\x00" * 8)]
    census = assets.type_census(
        members, load=_loader({b"UnityFS-a": env, b"UnityFS-b": _FakeEnv([_FakeObject("Mesh")])}))
    assert census.parsed == 2
    assert census.type_counts == {"Texture2D": 2, "MonoBehaviour": 1, "TextAsset": 1, "Mesh": 1}
    assert census.per_member["b.bundle"] == {"Mesh": 1}
    assert census.errors == []


def test_the_census_records_unreadable_members_instead_of_dying():
    from revenant import assets
    members = [("plain.txt", b"not a bundle at all"),
               ("broken.bundle", b"UnityFS-x junk")]
    census = assets.type_census(members, load=_loader({}))
    assert census.parsed == 0
    assert [name for name, _ in census.errors] == ["plain.txt", "broken.bundle"]
    assert "no UnityFS signature" in census.errors[0][1]


def test_the_census_honours_a_limit():
    from revenant import assets
    env = _FakeEnv([_FakeObject("Texture2D")])
    members = [(f"{i}.bundle", b"UnityFS-a") for i in range(5)]
    census = assets.type_census(members, load=_loader({b"UnityFS-a": env}), limit=2)
    assert census.parsed == 2


def _bundle_apk(path, members):
    with zipfile.ZipFile(path, "w") as zf:
        for name, data in members.items():
            zf.writestr(name, data)
    return str(path)


def test_the_census_takes_the_group_names_list_bundles_prints(tmp_path):
    """`list-bundles` reports a flat Addressables tree under `(root)`, so that
    is the group a reader types back. Pasting it into a path made the census
    look for a directory called `(root)` and report an empty package."""
    from revenant import assets
    apk = _bundle_apk(tmp_path / "g.apk", {
        "assets/aa/Android/flat.bundle": b"UnityFS-a",
        "assets/aa/Android/Env/nested.bundle": b"UnityFS-b"})
    load = _loader({b"UnityFS-a": _FakeEnv([_FakeObject("TextAsset")]),
                    b"UnityFS-b": _FakeEnv([_FakeObject("Mesh")])})
    root = assets.census_package(apk, "assets/aa/Android", assets.ROOT_GROUP, load=load)
    assert root.type_counts == {"TextAsset": 1}, "the flat member, not the nested one"
    nested = assets.census_package(apk, "assets/aa/Android", "Env", load=load)
    assert nested.type_counts == {"Mesh": 1}
    every = assets.census_package(apk, "assets/aa/Android", load=load)
    assert every.type_counts == {"TextAsset": 1, "Mesh": 1}


def test_the_census_does_not_let_one_group_pull_in_its_neighbour(tmp_path):
    """`Env` must not drag in `Env2`: a group is a path segment, not a prefix."""
    from revenant import assets
    apk = _bundle_apk(tmp_path / "n.apk", {
        "assets/aa/Android/Env/a.bundle": b"UnityFS-a",
        "assets/aa/Android/Env2/b.bundle": b"UnityFS-b"})
    census = assets.census_package(
        apk, "assets/aa/Android", "Env",
        load=_loader({b"UnityFS-a": _FakeEnv([_FakeObject("TextAsset")]),
                      b"UnityFS-b": _FakeEnv([_FakeObject("Mesh")])}))
    assert census.type_counts == {"TextAsset": 1}


def test_a_baked_in_serialized_file_exports_its_textassets(tmp_path):
    """`data.unity3d` carries what the build put in Resources/. On one title
    that is the whole numeric layer, and it was invisible to the harness."""
    from revenant import assets
    env = _FakeEnv([_FakeObject("TextAsset", path_id=7, m_Name="LevelTable", m_Script=b"rows"),
                    _FakeObject("TextAsset", path_id=8, m_Name="ItemTable", m_Script=b"more")])
    reports = assets.extract_ggm(
        str(tmp_path),
        sources=[("base.apk!assets/bin/Data/data.unity3d", b"UnityFS-ggm payload")],
        load=_loader({b"UnityFS-ggm": env}))
    out = tmp_path / assets.GGM_GROUP / "data.unity3d"
    assert (out / "TextAsset" / "LevelTable.bytes").read_bytes() == b"rows"
    assert (out / "TextAsset" / "ItemTable.bytes").read_bytes() == b"more"
    assert reports[0].exported["TextAsset"] == 2
    manifest = json.loads((out / "_bundle.json").read_text())
    assert manifest["bundle"] == "data.unity3d"
    assert manifest["object_counts"] == {"TextAsset": 2}


def test_every_exported_object_gets_its_own_file(tmp_path):
    """The count in the manifest has to equal the files on disk.

    Same-named objects are disambiguated with the path id truncated to seven
    digits, which two objects can share; the second one silently overwrote the
    first. On a real bundle (Travel Town, 18,741 MonoBehaviours in one folder)
    that lost four files while the manifest still claimed all of them, so a
    note quoting the manifest was quoting a number nothing on disk backed.
    """
    from revenant import assets
    ids = [1, 10_000_001, 20_000_001]      # identical once truncated
    env = _FakeEnv([_FakeObject("TextAsset", path_id=i, m_Name="Table", m_Script=b"x")
                    for i in ids])
    reports = assets.extract_ggm(
        str(tmp_path), sources=[("base.apk!assets/bin/Data/data.unity3d", b"UnityFS-x")],
        load=_loader({b"UnityFS-x": env}))
    written = list((tmp_path / assets.GGM_GROUP / "data.unity3d" / "TextAsset").iterdir())
    assert len(written) == len(ids) == reports[0].exported["TextAsset"]


def test_a_serialized_file_is_not_cut_at_a_stray_signature(tmp_path):
    """`globalgamemanagers` is not a UnityFS container at all.

    The wrapper-prefix skip searches the whole blob for the signature, so a
    serialized file that merely happens to contain those seven bytes somewhere
    in its middle would be handed to UnityPy beheaded. Only a signature in the
    header is a wrapper; anything deeper is data.
    """
    from revenant import assets
    seen = {}

    def load(stream):
        seen["data"] = stream.read()
        return _FakeEnv([_FakeObject("TextAsset", m_Name="Settings", m_Script=b"v")])

    blob = b"GGM-serialized" + b"\x00" * 4000 + assets.UNITYFS + b"\x00" * 100
    assets.extract_ggm(
        str(tmp_path), sources=[("base.apk!assets/bin/Data/globalgamemanagers", blob)],
        load=load)
    assert seen["data"] == blob, "the whole file, not the tail after a stray signature"


def test_an_unloadable_serialized_file_is_reported_not_raised(tmp_path):
    from revenant import assets
    reports = assets.extract_ggm(
        str(tmp_path), sources=[("base.apk!assets/bin/Data/data.unity3d", b"junk")],
        load=_loader({}))
    assert reports[0].exported == {}
    assert "load base.apk!" in reports[0].errors[0]


def test_the_ggm_finder_reads_the_paths_the_layout_declares(tmp_path, monkeypatch):
    """The #41 / #45 / #47 shape: the layout knows, the consumer must read it."""
    from revenant import assets, layout
    apks = tmp_path / "_apks"
    apks.mkdir()
    with zipfile.ZipFile(apks / "com.example.game.apk", "w") as zf:
        zf.writestr("assets/bin/Data/data.unity3d", b"UnityFS-ggm")
        zf.writestr("assets/aa/android/some.bundle", b"UnityFS-bundle")
    monkeypatch.setattr(assets, "apks_dir", lambda: str(apks))
    monkeypatch.setattr(assets, "workspace_root", lambda: str(tmp_path))
    found = list(assets.iter_ggm_sources())
    assert [label for label, _ in found] == ["com.example.game.apk!assets/bin/Data/data.unity3d"]
    assert assets.GGM_PATHS is layout.ANDROID_GGM, "one table, not a second copy"


def test_a_package_without_baked_in_data_yields_no_ggm_sources(tmp_path, monkeypatch):
    from revenant import assets
    apks = tmp_path / "_apks"
    apks.mkdir()
    with zipfile.ZipFile(apks / "com.example.game.apk", "w") as zf:
        zf.writestr("assets/aa/android/some.bundle", b"UnityFS-bundle")
    monkeypatch.setattr(assets, "apks_dir", lambda: str(apks))
    monkeypatch.setattr(assets, "workspace_root", lambda: str(tmp_path))
    assert list(assets.iter_ggm_sources()) == []


def test_a_pinned_prefix_locates_the_archive_that_holds_it(tmp_path, monkeypatch):
    """What `extract_ab.py` needed and `extract-scenes` could not do: point at an
    in-package path the layout does not know."""
    from revenant import assets
    apks = tmp_path / "_apks"
    apks.mkdir()
    with zipfile.ZipFile(apks / "com.example.game.apk", "w") as zf:
        zf.writestr("assets/Custom/Path/thing.bundle", b"UnityFS-x")
    monkeypatch.setattr(assets, "apks_dir", lambda: str(apks))
    monkeypatch.setattr(assets, "workspace_root", lambda: str(tmp_path))
    assert assets.find_bundle_source() is None, "no known root in this package"
    located = assets.find_bundle_source("assets/Custom/Path")
    assert located is not None and located[1] == "assets/Custom/Path"
    assert assets.find_bundle_source("assets/Nowhere") is None


def test_the_unity_version_fallback_has_an_exit(monkeypatch):
    """Both project scripts took it from `UNITY_VER=`; without an equivalent,
    a bundle whose files carry no version string cannot be read at all."""
    import UnityPy
    from revenant import assets
    # UnityPy's config is process-wide, so restore it: a version left pinned
    # here would silently apply to every test that runs after this one.
    monkeypatch.setattr(UnityPy.config, "FALLBACK_UNITY_VERSION",
                        UnityPy.config.FALLBACK_UNITY_VERSION, raising=False)
    monkeypatch.delenv(assets.UNITY_VERSION_ENV, raising=False)
    assert assets.set_unity_version(None) is None
    monkeypatch.setenv(assets.UNITY_VERSION_ENV, "2022.3.62f1")
    assert assets.set_unity_version() == "2022.3.62f1"
    assert UnityPy.config.FALLBACK_UNITY_VERSION == "2022.3.62f1"
    assert assets.set_unity_version("2021.3.1f1") == "2021.3.1f1"   # argument wins
    assert UnityPy.config.FALLBACK_UNITY_VERSION == "2021.3.1f1"


# ── contrib/fetch: the remote-acquisition skeleton ──────────────────────────

def _entries(*names):
    from revenant.contrib import fetch
    return [fetch.Entry(name=n, url=f"https://example.invalid/{n}") for n in names]


def test_the_fetch_skeleton_writes_bodies_and_counts_by_status(tmp_path):
    from revenant.contrib import fetch
    bodies = {"https://example.invalid/a": b"UnityFS-a", "https://example.invalid/b": b"UnityFS-b"}

    def get(url):
        return bodies[url]

    result = fetch.fetch_all(_entries("a", "b"), get, str(tmp_path), workers=1)
    assert (tmp_path / "a").read_bytes() == b"UnityFS-a"
    assert result.tally == {"ok": 2}
    assert result.total_bytes == 18
    assert result.ok()


def test_a_truncated_file_is_not_skipped_on_resume(tmp_path):
    """The failure this skeleton exists to prevent: a half-written file has the
    right name and a non-zero size, so "does it exist" calls it done for ever."""
    from revenant.contrib import fetch
    good, truncated = tmp_path / "good.bundle", tmp_path / "bad.bundle"
    good.write_bytes(b"UnityFS" + b"\x00" * 100)
    truncated.write_bytes(b"\x00" * 40)          # the tail of a cut-off download
    calls = []

    def get(url):
        calls.append(url)
        return b"UnityFS" + b"\x00" * 100

    complete = fetch.magic_check(b"UnityFS")
    result = fetch.fetch_all(_entries("good.bundle", "bad.bundle"), get, str(tmp_path),
                             accept=complete, complete=complete, complete_window=2048,
                             workers=1)
    assert result.tally == {"skip": 1, "ok": 1}
    assert calls == ["https://example.invalid/bad.bundle"], "only the broken one refetched"
    assert truncated.read_bytes().startswith(b"UnityFS")


def test_a_body_lands_at_its_name_only_once_it_is_whole(tmp_path):
    """A kill mid-write must not leave half a file under the real name.

    The magic check reads the head, so a download cut off at the tail -- the
    shape an interrupted multi-gigabyte pull actually has -- still starts with
    `UnityFS` and would be skipped for ever. Bodies are built beside the
    destination and moved onto it, so a partial one is never named as done.
    """
    from revenant.contrib import fetch
    (tmp_path / "a.bundle.part").write_bytes(b"UnityFS" + b"\x00" * 20)   # last run died here
    check = fetch.magic_check(b"UnityFS")
    result = fetch.fetch_all(_entries("a.bundle"), lambda url: b"UnityFS" + b"\x00" * 100,
                             str(tmp_path), accept=check, complete=check,
                             complete_window=2048, workers=1)
    assert result.tally == {"ok": 1}, "a leftover part file is not a finished download"
    assert len((tmp_path / "a.bundle").read_bytes()) == 107
    assert [p.name for p in tmp_path.iterdir()] == ["a.bundle"], "no part file left behind"


def test_without_a_completeness_check_nothing_is_trusted(tmp_path):
    """The default must not be "a file with that name exists"."""
    from revenant.contrib import fetch
    (tmp_path / "a").write_bytes(b"whatever")
    result = fetch.fetch_all(_entries("a"), lambda url: b"fresh", str(tmp_path), workers=1)
    assert result.tally == {"ok": 1}
    assert (tmp_path / "a").read_bytes() == b"fresh"


def test_a_digest_check_resumes_on_content_not_on_name(tmp_path):
    from revenant.contrib import fetch
    body = b"lua bytecode"
    digest = hashlib.md5(body).hexdigest()
    entries = [fetch.Entry("Game.lua", "https://example.invalid/Game.lua", {"md5": digest}),
               fetch.Entry("Other.lua", "https://example.invalid/Other.lua", {"md5": digest})]
    (tmp_path / "Game.lua").write_bytes(body)
    (tmp_path / "Other.lua").write_bytes(b"stale content")
    check = fetch.digest_check()
    result = fetch.fetch_all(entries, lambda url: body, str(tmp_path),
                             accept=check, complete=check, workers=1)
    assert result.tally == {"skip": 1, "ok": 1}
    assert (tmp_path / "Other.lua").read_bytes() == body


def test_a_body_that_fails_the_check_is_rejected_not_written(tmp_path):
    from revenant.contrib import fetch
    result = fetch.fetch_all(_entries("a"), lambda url: b"<html>404 page</html>",
                             str(tmp_path), accept=fetch.magic_check(b"UnityFS"), workers=1)
    assert result.tally == {"rejected": 1}
    assert not (tmp_path / "a").exists()
    assert not result.ok()
    assert result.failures[0].entry.name == "a"


def test_retries_are_bounded_and_an_unretryable_answer_stops_at_once(tmp_path):
    from revenant.contrib import fetch
    attempts = {"flaky": 0, "gone": 0}

    def get(url):
        name = url.rsplit("/", 1)[-1]
        attempts[name] += 1
        if name == "gone":
            raise fetch.Unretryable("http404")
        raise OSError("connection reset")

    result = fetch.fetch_all(_entries("flaky", "gone"), get, str(tmp_path),
                             workers=1, retries=3, sleep=lambda _s: None)
    assert attempts == {"flaky": 3, "gone": 1}
    assert result.tally == {"error": 1, "http404": 1}
    assert "connection reset" in result.failures[0].detail or \
           "connection reset" in result.failures[1].detail


def test_the_survey_sizes_everything_and_reads_no_bodies():
    """A survey exists to cost a run before committing to it: it must not need
    the body, and `survey` is given no output directory to write one into."""
    import inspect
    from revenant.contrib import fetch
    headers = {
        "https://example.invalid/a": {"Content-Range": "bytes 0-0/1048576", "Content-Length": "1"},
        "https://example.invalid/b": {"Content-Length": "2048"},
    }
    result = fetch.survey(_entries("a", "b"), lambda url: headers[url], workers=1)
    assert result.total_bytes == 1048576 + 2048
    assert result.tally == {"ok": 2}
    assert "out_dir" not in inspect.signature(fetch.survey).parameters


def test_a_probe_that_answers_no_length_is_a_failure_not_a_zero():
    """The mistake this survey exists to catch: asking with HEAD, which comes
    back without a length once the CDN redirects to storage. Counting that as
    a successful zero makes a whole run cost nothing on paper."""
    from revenant.contrib import fetch
    result = fetch.survey(_entries("a", "b"), lambda url: {}, workers=1)
    assert result.tally == {"no-size": 2}
    assert not result.ok()
    assert "no length" in result.failures[0].detail


def test_progress_is_reported_as_entries_finish_not_only_at_the_end(tmp_path):
    """An unattended pull of a thousand bundles that prints nothing for forty
    minutes cannot be told from a hung one. Both project scripts printed a line
    every N; rewriting them onto the skeleton is what showed it had no way to
    (#50)."""
    from revenant.contrib import fetch
    seen = []
    result = fetch.fetch_all(_entries("a", "b", "c"), lambda url: b"body", str(tmp_path),
                             workers=1, on_outcome=lambda i, o, run: seen.append(
                                 (i, o.entry.name, dict(run.tally))))
    assert [name for _i, name, _t in seen] == ["a", "b", "c"], "in entry order"
    assert [i for i, _n, _t in seen] == [1, 2, 3]
    assert seen[-1][2] == {"ok": 3} == dict(result.tally), "the running tally is the final one"


def test_the_survey_reports_progress_the_same_way():
    from revenant.contrib import fetch
    seen = []
    fetch.survey(_entries("a", "b"), lambda url: {"Content-Length": "10"},
                 workers=1, on_outcome=lambda i, o, run: seen.append(i))
    assert seen == [1, 2]


def test_content_range_beats_content_length_on_a_ranged_probe():
    """A ranged GET answers `Content-Length: 1`; taking that would size every
    entry at one byte, which is how a HEAD-based survey reads as zero."""
    from revenant.contrib import fetch
    assert fetch.size_from_headers({"Content-Range": "bytes 0-0/900", "Content-Length": "1"}) == 900
    assert fetch.size_from_headers({"Content-Length": "900"}) == 900
    assert fetch.size_from_headers({}) == 0
    assert fetch.RANGE_PROBE_HEADERS == {"Range": "bytes=0-0"}


def test_frida_recipes_bake_in_no_addresses_of_their_own():
    from revenant.contrib.decrypt import reload_recipe, write_protect_recipe
    wp = write_protect_recipe("Module.base.add(0x1000)", 0x2000)
    assert "setExceptionHandler" in wp and "Module.base.add(0x1000)" in wp and "2000" not in wp[:0]
    rl = reload_recipe("libil2cpp.so", 0x32a8840)
    assert "0x32a8840" in rl and "libil2cpp.so" in rl


# ── contrib/cache: route B, reading what the client already downloaded ──────

def test_a_cached_response_body_starts_after_the_header_block():
    from revenant.contrib import cache
    raw = (b"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\n"
           b"Content-Length: 8\r\n\r\n" + b'{"a": 1}')
    assert cache.response_body(raw) == b'{"a": 1}'
    headers, body = cache.parse_response(raw)
    assert headers == {"content-type": "application/json", "content-length": "8"}
    assert body == b'{"a": 1}', "the status line is not a header"


def test_a_cached_entry_with_no_headers_is_returned_whole():
    from revenant.contrib import cache
    assert cache.response_body(b'{"a": 1}') == b'{"a": 1}'
    assert cache.parse_response(b'{"a": 1}') == ({}, b'{"a": 1}')


def test_a_blank_line_inside_the_body_is_not_mistaken_for_the_header_break():
    """Cutting at the first `\\r\\n\\r\\n` beheads any body that holds one --
    CRLF-terminated pretty-printed JSON does. The prefix has to read as headers
    before it is treated as any."""
    from revenant.contrib import cache
    body = b'{\r\n  "a": 1\r\n\r\n  "b": 2\r\n}'
    assert cache.response_body(body) == body
    wrapped = b"HTTP/1.1 200 OK\r\nX-Cache: HIT\r\n\r\n" + body
    assert cache.response_body(wrapped) == body


def test_a_directory_of_loose_bundles_exports_the_tree_a_packaged_bundle_gets(tmp_path):
    """Route B's bundles are plain UnityFS. Re-implementing the export tree for
    them is how the two drift apart, so `export_env` is called, not copied."""
    from revenant import assets
    from revenant.contrib import cache
    src, out = tmp_path / "cached_bundles", tmp_path / "out"
    (src / "1728203541611_bakery").mkdir(parents=True)
    (src / "1728203541611_bakery" / "a.bundle").write_bytes(b"UnityFS-a")
    (src / "loose.bundle").write_bytes(b"UnityFS-b")
    (src / "notes.txt").write_bytes(b"not a bundle")

    env_a = _FakeEnv([_FakeObject("TextAsset", path_id=1, m_Name="Recipe", m_Script=b"rows")])
    env_b = _FakeEnv([_FakeObject("TextAsset", path_id=2, m_Name="Root", m_Script=b"x")])
    reports = cache.export_bundle_dir(
        str(src), str(out), load=_loader({b"UnityFS-a": env_a, b"UnityFS-b": env_b}))

    by_name = {r.name: r for r in reports}
    assert by_name["a.bundle"].group == "1728203541611_bakery", "the content id survives"
    assert (out / "1728203541611_bakery" / "a.bundle" / "TextAsset" / "Recipe.bytes"
            ).read_bytes() == b"rows"
    assert by_name["loose.bundle"].group == assets.ROOT_GROUP, "a bundle at the top level"
    assert os.path.exists(os.path.join(by_name["loose.bundle"].out_dir, "_bundle.json"))
    assert by_name["notes.txt"].errors == ["notes.txt: no UnityFS signature"]
    assert by_name["notes.txt"].exported == {}
    assert not os.path.exists(by_name["notes.txt"].out_dir), "nothing exported, nothing written"


# ── LuaJIT decompilation routing ────────────────────────────────────────────

def test_luajit_bytecode_routes_to_ljd2_and_reports_when_absent(monkeypatch):
    from revenant import lua
    monkeypatch.delenv("REVENANT_LJD2", raising=False)
    ok, msg = lua.decompile(b"\x1bLJ\x02\x00rest of the chunk")
    assert not ok
    assert "LuaJIT" in msg and "REVENANT_LJD2" in msg


def test_stock_lua_does_not_route_to_ljd2(monkeypatch, tmp_path):
    """A `\\x1bLua` chunk goes to unluac, never the LuaJIT path."""
    from revenant import lua
    calls = []
    monkeypatch.setattr(lua, "decompile_luajit", lambda *a, **k: calls.append(a) or (True, ""))
    monkeypatch.setattr(lua, "unluac_jar", lambda: str(tmp_path / "nope.jar"))
    lua.decompile(b"\x1bLua\x53\x00")
    assert not calls


# ── tables: the corpus, and which reader read each table (#56) ──────────────

def _write(path, payload) -> str:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f)
    return path


def _blob(path: str, data: bytes) -> str:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        f.write(data)
    return path


def _rows(n: int, **extra) -> dict:
    return {str(1000 + i): dict({"id": 1000 + i, "name": f"row{i}"}, **extra) for i in range(n)}


# reader dispatch -- a pure function over one parsed value, so every shape the
# nine titles ship can be pinned without a file on disk.

def test_a_single_wrapper_key_is_unwrapped_to_the_id_map():
    from revenant import tables as _t
    reader, rows, wrapper = _t.dispatch({"items": _rows(3)})
    assert reader == _t.READER_JSON_IDMAP
    assert wrapper == "items"
    assert [r["id"] for r in rows] == [1000, 1001, 1002]


def test_a_bare_id_map_needs_no_wrapper():
    from revenant import tables as _t
    reader, rows, wrapper = _t.dispatch(_rows(2))
    assert (reader, wrapper, len(rows)) == (_t.READER_JSON_IDMAP, "", 2)


def test_a_row_array_reads_as_rows_wrapped_or_not():
    from revenant import tables as _t
    bare = _t.dispatch([{"id": 1}, {"id": 2}])
    wrapped = _t.dispatch({"config": [{"id": 1}, {"id": 2}]})
    assert bare == (_t.READER_JSON_ROWS, [{"id": 1}, {"id": 2}], "")
    assert wrapped == (_t.READER_JSON_ROWS, [{"id": 1}, {"id": 2}], "config")


def test_a_one_row_table_is_not_mistaken_for_a_wrapper():
    """`{"1001": {...}}` is an id map holding one row, not a wrapper around a
    row -- the give-away is that unwrapping it does not leave a table."""
    from revenant import tables as _t
    reader, rows, wrapper = _t.dispatch({"1001": {"id": 1001, "cost": 5}})
    assert (reader, wrapper) == (_t.READER_JSON_IDMAP, "")
    assert rows == [{"id": 1001, "cost": 5}]


def test_an_empty_table_reads_as_zero_rows_rather_than_raising():
    from revenant import tables as _t
    assert _t.dispatch({"items": []})[1] == []
    assert _t.dispatch({})[1] == []


def test_a_json_file_that_is_not_a_table_says_so():
    from revenant import tables as _t
    import pytest
    for value in ({"version": 3, "built": "yes"}, "a string", 7):
        with pytest.raises(_t.TableError):
            _t.dispatch(value)


def test_fields_are_the_union_across_rows_in_first_seen_order():
    from revenant import tables as _t
    assert _t.fields([{"id": 1, "cost": 2}, {"id": 3, "tier": 4}]) == ("id", "cost", "tier")


# corpus discovery -- bounded, automatic, overridable.

def test_the_two_json_shapes_are_each_found_as_a_corpus(tmp_path):
    from revenant import tables as _t
    root = str(tmp_path)
    _write(os.path.join(root, "res", "conf-json", "ItemConfig.json"), {"items": _rows(4)})
    _write(os.path.join(root, "res", "remote", "config", "ab_test.json"), [{"k": "v"}])
    found = _t.discover(root, cfg={})
    assert [c.rel for c in found.corpora] == [os.path.join("res", "conf-json"),
                                              os.path.join("res", "remote", "config")]
    assert all(c.source == _t.SOURCE_FOUND for c in found.corpora)
    assert [t.name for t in found.tables()] == ["ItemConfig", "ab_test"]
    assert [_t.read(t).reader for t in found.tables()] == [_t.READER_JSON_IDMAP, _t.READER_JSON_ROWS]


def test_discovery_never_leaves_the_extraction_roots(tmp_path):
    """`_refs/` is 655 MB of IsilDump and `src/` is the whole scaffold. Neither
    is a place config tables land, and neither is a place a query command may
    walk."""
    from revenant import tables as _t
    root = str(tmp_path)
    _write(os.path.join(root, "_refs", "1.0", "rva_index.json"), {"a": {"b": 1}})
    _write(os.path.join(root, "src", "1.0", "types.json"), {"a": {"b": 1}})
    _write(os.path.join(root, "res", "conf-json", "Item.json"), {"items": _rows(1)})
    assert [c.rel for c in _t.discover(root, cfg={}).corpora] == [os.path.join("res", "conf-json")]


def test_the_sweep_stops_at_a_fixed_depth_and_says_what_it_did_not_open(tmp_path):
    from revenant import tables as _t
    root = str(tmp_path)
    reachable = os.path.join(root, "res", "a", "b", "c", "Deep.json")
    beyond = os.path.join(root, "res", "a", "b", "c", "d", "Deeper.json")
    _write(reachable, {"items": _rows(1)})
    _write(beyond, {"items": _rows(1)})
    found = _t.discover(root, cfg={})
    assert [t.name for t in found.tables()] == ["Deep"]
    assert any("depth" in line for line in found.gaps), found.gaps


def test_the_sweep_is_capped_and_reports_the_cap_rather_than_going_quiet(tmp_path, monkeypatch):
    from revenant import tables as _t
    monkeypatch.setattr(_t, "MAX_DIRS", 2)
    root = str(tmp_path)
    for name in ("aa", "bb", "cc", "dd"):
        _write(os.path.join(root, "res", name, "T.json"), {"items": _rows(1)})
    found = _t.discover(root, cfg={})
    assert len(found.corpora) < 4
    assert any("directories" in line for line in found.gaps), found.gaps


def test_configured_directories_replace_the_sweep(tmp_path):
    """#50's lesson is that nobody remembers to configure it, so the sweep is
    the default -- but a project whose tables land somewhere unusual must be
    able to say so, and be believed."""
    from revenant import tables as _t
    root = str(tmp_path)
    _write(os.path.join(root, "res", "conf-json", "Swept.json"), {"items": _rows(1)})
    _write(os.path.join(root, "elsewhere", "deep", "down", "here", "Named.json"), [{"id": 1}])
    found = _t.discover(root, cfg={"tables": {"dirs": ["elsewhere/deep/down/here"]}})
    assert [t.name for t in found.tables()] == ["Named"]
    assert [c.source for c in found.corpora] == [_t.SOURCE_CONFIGURED]


def test_a_configured_directory_that_is_not_there_is_reported(tmp_path):
    from revenant import tables as _t
    found = _t.discover(str(tmp_path), cfg={"tables": {"dirs": ["res/gone"]}})
    assert found.corpora == ()
    assert any("res/gone" in line for line in found.missing), found.missing


# the two shapes with no reader yet: recognised, counted, and never read as empty.

def test_lua_and_binary_tables_are_recognised_beside_the_json_they_sit_with(tmp_path):
    from revenant import tables as _t
    root = str(tmp_path)
    corpus = os.path.join(root, "res", "conf")
    _write(os.path.join(corpus, "Item.json"), {"items": _rows(1)})
    _blob(os.path.join(corpus, "Level.bytes"), b"\x01\x02luban")
    with open(os.path.join(corpus, "Order.lua"), "w", encoding="utf-8") as f:
        f.write("return {}")
    by_name = {t.name: t for t in _t.discover(root, cfg={}).tables()}
    assert by_name["Level"].shape == _t.SHAPE_BINARY
    assert by_name["Order"].shape == _t.SHAPE_LUA
    # #58 read the last shape that had no reader, so the table that listed
    # them is gone rather than left empty. What remains is the distinction that
    # still applies: a blob this project named no reader for.
    assert not hasattr(_t, "PENDING_READERS")
    blob = _t.TableData(by_name["Level"])
    assert _t.UNCLAIMED in blob.label
    assert _t.TableData(by_name["Order"]).label == "-"


def test_a_shape_with_no_reader_raises_instead_of_reading_zero_rows(tmp_path):
    """An undecoded table reported as an empty one is the failure #59 names:
    "this table is empty" and "we cannot read this table" are different facts."""
    from revenant import tables as _t
    import pytest
    root = str(tmp_path)
    corpus = os.path.join(root, "res", "conf")
    _write(os.path.join(corpus, "Item.json"), {"items": _rows(1)})
    _blob(os.path.join(corpus, "Level.bytes"), b"\x01\x02luban")
    binary = next(t for t in _t.discover(root, cfg={}).tables() if t.shape == _t.SHAPE_BINARY)
    with pytest.raises(_t.TableError) as exc:
        _t.rows(binary)
    assert "#59" in str(exc.value)


def test_a_directory_of_extracted_blobs_alone_is_not_a_corpus(tmp_path):
    """`res/` holds hundreds of thousands of extracted TextAssets. A folder of
    `.bytes` with nothing readable beside it is extraction output, not a table
    corpus -- claiming it would put the count of "tables in this project" off
    by three orders of magnitude."""
    from revenant import tables as _t
    root = str(tmp_path)
    blobs = os.path.join(root, "res", "TextAsset")
    os.makedirs(blobs)
    for i in range(5):
        _blob(os.path.join(blobs, f"asset{i}.bytes"), b"\x00\x01")
    assert _t.discover(root, cfg={}).corpora == ()


# reading a table by name, path, or handle.

def test_rows_unwraps_the_wrapper_key_every_note_unwraps_by_hand(tmp_path):
    from revenant import tables as _t
    root = str(tmp_path)
    path = _write(os.path.join(root, "res", "conf-json", "Item.json"), {"items": _rows(3)})
    assert [r["id"] for r in _t.rows(path)] == [1000, 1001, 1002]
    assert [r["id"] for r in _t.rows("Item", root=root, cfg={})] == [1000, 1001, 1002]


def test_two_tables_with_one_name_are_reported_rather_than_guessed(tmp_path):
    from revenant import tables as _t
    import pytest
    root = str(tmp_path)
    _write(os.path.join(root, "res", "a", "Item.json"), {"items": _rows(1)})
    _write(os.path.join(root, "res", "b", "Item.json"), {"items": _rows(2)})
    with pytest.raises(_t.TableError) as exc:
        _t.rows("Item", root=root, cfg={})
    assert "res/a" in str(exc.value).replace(os.sep, "/")
    assert "res/b" in str(exc.value).replace(os.sep, "/")


def test_an_unparsable_file_is_reported_with_its_reason(tmp_path):
    from revenant import tables as _t
    root = str(tmp_path)
    corpus = os.path.join(root, "res", "conf-json")
    _write(os.path.join(corpus, "Item.json"), {"items": _rows(1)})
    with open(os.path.join(corpus, "Broken.json"), "w", encoding="utf-8") as f:
        f.write('{"items": {')
    broken = next(t for t in _t.discover(root, cfg={}).tables() if t.name == "Broken")
    data = _t.read(broken)
    assert data.error and data.reader == ""
    assert data.rows == () and data.fields == ()
    assert data.label == "-", "no reader claimed it, and none is pending"


def test_a_file_that_is_no_kind_of_table_is_refused_by_its_name(tmp_path):
    """Not "we have no reader for it yet" -- that is a claim about a table, and
    a `.txt` is not one. The sweep skips these, so reading one by path must not
    quietly promote it to an undecoded binary table."""
    from revenant import tables as _t
    import pytest
    path = os.path.join(str(tmp_path), "notes.txt")
    with open(path, "w", encoding="utf-8") as f:
        f.write("not a table")
    with pytest.raises(_t.TableError) as exc:
        _t.rows(path)
    assert "not a table file" in str(exc.value)


def test_a_directory_that_will_not_open_is_reported_not_read_as_empty(tmp_path):
    from revenant import tables as _t
    root = str(tmp_path)
    _write(os.path.join(root, "res", "conf-json", "Item.json"), {"items": _rows(1)})
    locked = os.path.join(root, "res", "locked")
    os.makedirs(locked)
    os.chmod(locked, 0o000)
    try:
        found = _t.discover(root, cfg={})
    finally:
        os.chmod(locked, 0o755)
    assert [t.name for t in found.tables()] == ["Item"]
    assert any("locked" in line and "could not be read" in line for line in found.gaps), \
        found.gaps


def test_the_entry_cap_reads_the_same_files_on_every_run(tmp_path, monkeypatch):
    """Which files a capped listing keeps must not be filesystem order: a
    listing that changes between two runs over an unchanged directory is not
    one anybody can act on."""
    from revenant import tables as _t
    monkeypatch.setattr(_t, "MAX_ENTRIES", 3)
    root = str(tmp_path)
    for i in range(9):
        _write(os.path.join(root, "res", "conf", f"T{i}.json"), {"items": _rows(1)})
    first = [t.name for t in _t.discover(root, cfg={}).tables()]
    assert first == ["T0", "T1", "T2"], "the first three by name, not by readdir order"
    assert first == [t.name for t in _t.discover(root, cfg={}).tables()]
    assert any("past the first 3" in line for line in _t.discover(root, cfg={}).gaps)


def test_discovery_reads_the_config_of_the_project_it_was_handed(tmp_path, monkeypatch):
    """`discover(root=X)` with no cfg must read X's revenant.toml. Answering
    with the ambient project's `[tables] dirs` sends the sweep somewhere that
    has nothing to do with the directory the caller named."""
    from revenant import config
    from revenant import tables as _t
    other, root = tmp_path / "ambient", tmp_path / "asked-about"
    for project in (other, root):
        project.mkdir()
    (other / "revenant.toml").write_text('[tables]\ndirs = ["res/theirs"]\n')
    (root / "revenant.toml").write_text('[tables]\ndirs = ["res/ours"]\n')
    _write(str(root / "res" / "ours" / "Ours.json"), {"items": _rows(1)})
    _write(str(root / "res" / "theirs" / "Theirs.json"), {"items": _rows(1)})
    monkeypatch.setenv("REVENANT_PROJECT", str(other))
    config._PROJECT_CONFIG_CACHE.clear()
    try:
        assert [t.name for t in _t.discover(str(root)).tables()] == ["Ours"]
    finally:
        config._PROJECT_CONFIG_CACHE.clear()


# ── luban: the binary table format (#59) ────────────────────────────────────
#
# The encoder below is transcribed from Luban's `ByteBuf.Write*`, independently
# of the decoder under test, which is transcribed from its `Read*`. A round trip
# through both therefore catches a slip in either -- and the byte vectors in
# `test_the_varint_ladder_matches_the_bytes_luban_writes` are hand-computed from
# the writer's source, so a matching pair of slips cannot pass unseen.

def _uint(x: int) -> bytes:
    if x < 0x80:
        return bytes([x])
    if x < 0x4000:
        return bytes([(x >> 8) | 0x80, x & 0xFF])
    if x < 0x20_0000:
        return bytes([(x >> 16) | 0xC0, (x >> 8) & 0xFF, x & 0xFF])
    if x < 0x1000_0000:
        return bytes([(x >> 24) | 0xE0, (x >> 16) & 0xFF, (x >> 8) & 0xFF, x & 0xFF])
    return bytes([0xF0]) + x.to_bytes(4, "big")


def _ulong(x: int) -> bytes:
    if x < 0x1000_0000:
        return _uint(x)
    if x < 0x8_0000_0000:
        return bytes([(x >> 32) | 0xF0]) + (x & 0xFFFFFFFF).to_bytes(4, "big")
    if x < 0x400_0000_0000:
        return bytes([(x >> 40) | 0xF8]) + (x & 0xFF_FFFFFFFF).to_bytes(5, "big")
    if x < 0x2_0000_0000_0000:
        return bytes([(x >> 48) | 0xFC]) + (x & 0xFFFF_FFFFFFFF).to_bytes(6, "big")
    if x < 0x100_0000_0000_0000:
        return bytes([0xFE]) + (x & 0xFFFFFF_FFFFFFFF).to_bytes(7, "big")
    return bytes([0xFF]) + (x & 0xFFFFFFFF_FFFFFFFF).to_bytes(8, "big")


def _lb_int(x: int) -> bytes:
    return _uint(x & 0xFFFFFFFF)


def _lb_long(x: int) -> bytes:
    return _ulong(x & 0xFFFFFFFFFFFFFFFF)


def _lb_str(s: str) -> bytes:
    raw = s.encode("utf-8")
    return _uint(len(raw)) + raw


def _lb_float(x: float) -> bytes:
    return struct.pack("<f", x)


def _lb_list(items) -> bytes:
    return _uint(len(items)) + b"".join(items)


def _schema(beans: dict, tables: dict | None = None):
    from revenant import luban
    return luban.Schema.from_json({"beans": beans, "tables": tables or {}})


_ITEM = {
    "ItemConf": {"fields": [
        {"name": "id", "type": "int"},
        {"name": "name", "type": "string"},
        {"name": "cost", "type": "float"},
    ]},
}


def _item_row(id_: int, name: str, cost: float) -> bytes:
    return _lb_int(id_) + _lb_str(name) + _lb_float(cost)


# the wire format

def test_the_varint_ladder_matches_the_bytes_luban_writes():
    """Hand-computed from `ByteBuf.WriteUint`, one vector per branch boundary.
    Luban's varint is big-endian with the length in the lead byte's high bits --
    read it as protobuf's little-endian continuation scheme and every number
    comes out wrong."""
    from revenant import luban
    vectors = {
        0x00: b"\x00",
        0x7F: b"\x7f",
        0x80: b"\x80\x80",
        0x3FFF: b"\xbf\xff",
        0x4000: b"\xc0\x40\x00",
        0x1FFFFF: b"\xdf\xff\xff",
        0x200000: b"\xe0\x20\x00\x00",
        0xFFFFFFF: b"\xef\xff\xff\xff",
        0x10000000: b"\xf0\x10\x00\x00\x00",
        0xFFFFFFFF: b"\xf0\xff\xff\xff\xff",
    }
    for value, raw in vectors.items():
        assert _uint(value) == raw, f"encoder disagrees at 0x{value:x}"
        buf = luban.ByteBuf(raw)
        assert buf.read_uint() == value, f"decoder disagrees at 0x{value:x}"
        assert buf.remaining == 0, f"0x{value:x} did not consume its bytes exactly"


def test_a_negative_int_is_five_bytes_and_comes_back_signed():
    from revenant import luban
    assert _lb_int(-1) == b"\xf0\xff\xff\xff\xff"
    assert luban.ByteBuf(_lb_int(-1)).read_int() == -1
    assert luban.ByteBuf(_lb_int(-2147483648)).read_int() == -2147483648


def test_the_long_ladder_reaches_nine_bytes():
    from revenant import luban
    for value in (0, 1, 0x0FFF_FFFF, 0x1_0000_0000, 0x7F_FFFF_FFFF,
                  0x3FF_FFFF_FFFF, 0x1_FFFF_FFFF_FFFF, 0xFF_FFFF_FFFF_FFFF,
                  0x7FFF_FFFF_FFFF_FFFF):
        assert luban.ByteBuf(_ulong(value)).read_ulong() == value, hex(value)
    assert luban.ByteBuf(_lb_long(-3)).read_long() == -3


def test_floats_are_little_endian_while_integers_are_big():
    """One buffer, two byte orders. This is the trap the format sets."""
    from revenant import luban
    assert _lb_float(1.5) == b"\x00\x00\xc0\x3f"
    buf = luban.ByteBuf(_uint(0x4000) + _lb_float(1.5))
    assert buf.read_uint() == 0x4000
    assert buf.read_float() == 1.5


def test_a_string_is_a_size_then_utf8():
    from revenant import luban
    buf = luban.ByteBuf(_lb_str("能量") + _lb_str(""))
    assert buf.read_string() == "能量"
    assert buf.read_string() == ""


def _sint(x: int) -> bytes:
    """Luban's `WriteSint`: rotate left by one, then the varint. Not zigzag."""
    u = x & 0xFFFFFFFF
    return _uint(((u << 1) & 0xFFFFFFFF) ^ (u >> 31))


def test_sint_is_a_rotation_and_not_the_zigzag_its_own_comment_claims():
    """Upstream's comment above `WriteSint` describes zigzag and the code beside
    it rotates. Transcribe the comment and every negative decodes wrong while
    every positive decodes right, which is the shape of bug that ships."""
    from revenant import luban
    for value, raw in {0: b"\x00", 1: b"\x02", 127: b"\x80\xfe",
                       -1: b"\xf0\xff\xff\xff\xff",
                       -127: b"\xf0\xff\xff\xff\x03",
                       -2147483648: b"\x01",
                       2147483647: b"\xf0\xff\xff\xff\xfe"}.items():
        assert _sint(value) == raw, f"encoder disagrees at {value}"
        assert luban.ByteBuf(raw).read_sint() == value, f"decoder disagrees at {value}"

    def zigzag(v):
        return (v >> 1) ^ -(v & 1)

    assert zigzag(0xFFFFFFFF) != -1, "the reading that looks right and is not"


def test_slong_rotates_over_sixty_four_bits():
    from revenant import luban
    def enc(x):
        u = x & 0xFFFFFFFFFFFFFFFF
        return _ulong(((u << 1) & 0xFFFFFFFFFFFFFFFF) ^ (u >> 63))
    for value in (0, 1, -1, -127, 2**62, -(2**63), 2**63 - 1):
        assert luban.ByteBuf(enc(value)).read_slong() == value, value


def test_fixed_width_scalars_are_little_endian():
    from revenant import luban
    assert luban.ByteBuf(struct.pack("<i", -7)).read_fint() == -7
    assert luban.ByteBuf(struct.pack("<q", -7)).read_flong() == -7
    assert luban.ByteBuf(struct.pack("<h", -7)).read_fshort() == -7


# whole tables

def test_a_table_is_a_row_count_then_that_many_beans():
    from revenant import luban
    blob = _uint(2) + _item_row(1001, "Energy", 1.5) + _item_row(1002, "Coin", 2.0)
    out = luban.read_table(blob, _schema(_ITEM), "ItemConf")
    assert out.rows == ({"id": 1001, "name": "Energy", "cost": 1.5},
                        {"id": 1002, "name": "Coin", "cost": 2.0})
    assert out.fields == ("id", "name", "cost")
    assert out.trailing == 0


def test_an_empty_table_reads_as_no_rows():
    from revenant import luban
    out = luban.read_table(_uint(0), _schema(_ITEM), "ItemConf")
    assert out.rows == () and out.trailing == 0


def test_a_parents_fields_are_read_before_the_childs():
    """The generated constructor chains to `base(_buf)` first. A schema that
    forgets the parent decodes every derived row one field-set out of step."""
    from revenant import luban
    schema = _schema({
        "Base": {"fields": [{"name": "id", "type": "int"}]},
        "Derived": {"parent": "Base", "fields": [{"name": "extra", "type": "string"}]},
    })
    blob = _uint(1) + _lb_int(7) + _lb_str("x")
    out = luban.read_table(blob, schema, "Derived")
    assert out.rows == ({"id": 7, "extra": "x"},)


def test_containers_are_a_size_then_their_elements():
    from revenant import luban
    schema = _schema({"C": {"fields": [
        {"name": "nums", "type": "list<int>"},
        {"name": "drops", "type": "map<int,string>"},
    ]}})
    blob = (_uint(1)
            + _lb_list([_lb_int(3), _lb_int(4)])
            + _uint(2) + _lb_int(1) + _lb_str("a") + _lb_int(2) + _lb_str("b"))
    out = luban.read_table(blob, schema, "C")
    assert out.rows == ({"nums": [3, 4], "drops": {1: "a", 2: "b"}},)


def test_a_nullable_field_is_a_flag_and_then_maybe_a_value():
    from revenant import luban
    schema = _schema({"N": {"fields": [{"name": "note", "type": "string",
                                        "nullable": True}]}})
    blob = _uint(2) + b"\x01" + _lb_str("here") + b"\x00"
    out = luban.read_table(blob, schema, "N")
    assert out.rows == ({"note": "here"}, {"note": None})


def test_an_abstract_bean_reads_a_type_id_however_the_field_spells_it():
    """`bean:Base` and `dynamic:Base` are the same on the wire: the generated
    `DeserializeBase` switches on a type id exactly when Base is abstract. Read
    `bean:` as plain fields and the id is eaten as the first field."""
    from revenant import luban
    schema = _schema({
        "RewardBase": {"abstract": True, "fields": []},
        "Coins": {"parent": "RewardBase", "id": 11,
                  "fields": [{"name": "amount", "type": "int"}]},
        "Row": {"fields": [{"name": "reward", "type": "bean:RewardBase"}]},
    })
    blob = _uint(1) + _lb_int(11) + _lb_int(500)
    assert luban.read_table(blob, schema, "Row").rows == ({"reward": {"amount": 500}},)


def test_a_concrete_bean_field_reads_no_type_id():
    from revenant import luban
    schema = _schema({
        "Detail": {"fields": [{"name": "amount", "type": "int"}]},
        "Row": {"fields": [{"name": "detail", "type": "bean:Detail"}]},
    })
    assert luban.read_table(_uint(1) + _lb_int(500), schema, "Row").rows == (
        {"detail": {"amount": 500}},)


def test_a_polymorphic_field_reads_its_type_id_first():
    from revenant import luban
    schema = _schema({
        "RewardBase": {"abstract": True, "fields": []},
        "Coins": {"parent": "RewardBase", "id": 11,
                  "fields": [{"name": "amount", "type": "int"}]},
        "Item": {"parent": "RewardBase", "id": 22,
                 "fields": [{"name": "item_id", "type": "int"}]},
        "Row": {"fields": [{"name": "reward", "type": "dynamic:RewardBase"}]},
    })
    blob = _uint(2) + _lb_int(11) + _lb_int(500) + _lb_int(22) + _lb_int(9001)
    out = luban.read_table(blob, schema, "Row")
    assert out.rows == ({"reward": {"amount": 500}}, {"reward": {"item_id": 9001}})


def test_an_unknown_type_id_names_the_ids_the_schema_does_know():
    from revenant import luban
    import pytest
    schema = _schema({
        "B": {"abstract": True, "fields": []},
        "C": {"parent": "B", "id": 11, "fields": [{"name": "n", "type": "int"}]},
        "Row": {"fields": [{"name": "r", "type": "dynamic:B"}]},
    })
    with pytest.raises(luban.LubanError) as exc:
        luban.read_table(_uint(1) + _lb_int(99) + _lb_int(1), schema, "Row")
    assert "99" in str(exc.value) and "11" in str(exc.value)


# failing loudly, at the right stage

def test_a_still_encrypted_blob_fails_at_the_header_not_at_row_four_million():
    """`_index.json`'s rule, one layer down: say which step broke. A nonsense
    row count is the offset or the key, and pointing at a row sends the reader
    to the schema instead."""
    from revenant import luban
    import pytest
    with pytest.raises(luban.LubanError) as exc:
        luban.read_table(b"\xf0\x7f\xff\xff\xff" + b"\x00" * 8, _schema(_ITEM), "ItemConf")
    assert exc.value.stage == luban.STAGE_HEADER
    assert "encrypted" in str(exc.value)


def test_a_row_that_runs_off_the_end_says_which_row_and_which_field():
    from revenant import luban
    import pytest
    blob = _uint(2) + _item_row(1001, "Energy", 1.5) + _lb_int(1002) + _lb_str("Coin")
    with pytest.raises(luban.LubanError) as exc:
        luban.read_table(blob, _schema(_ITEM), "ItemConf")
    assert exc.value.stage == luban.STAGE_ROW
    assert "row 1 of 2" in str(exc.value) and "cost" in str(exc.value)


def test_a_container_that_throws_is_reported_as_the_container_step():
    from revenant import luban
    import pytest

    def container(_data):
        raise ValueError("bad key")

    with pytest.raises(luban.LubanError) as exc:
        luban.read_table(b"\x00", _schema(_ITEM), "ItemConf", container=container)
    assert exc.value.stage == luban.STAGE_CONTAINER
    assert "bad key" in str(exc.value)


def test_the_container_callable_gets_the_shipped_bytes_and_its_output_is_decoded():
    from revenant import luban
    plain = _uint(1) + _item_row(1, "x", 0.5)
    shipped = b"HEY\x01" + bytes(b ^ 0x5A for b in plain)
    out = luban.read_table(
        shipped, _schema(_ITEM), "ItemConf",
        container=lambda d: bytes(b ^ 0x5A for b in d[4:]))
    assert out.rows == ({"id": 1, "name": "x", "cost": 0.5},)


def test_leftover_bytes_are_reported_because_they_mean_the_schema_is_short():
    """A schema missing a field decodes rows that look fine and are not. The
    only signal is that the blob did not run out when the rows did."""
    from revenant import luban
    short = _schema({"ItemConf": {"fields": [{"name": "id", "type": "int"}]}})
    blob = _uint(1) + _item_row(1001, "Energy", 1.5)
    out = luban.read_table(blob, short, "ItemConf")
    assert out.rows == ({"id": 1001},)
    assert out.trailing == len(_lb_str("Energy")) + 4


def test_a_bean_the_schema_does_not_have_says_so():
    from revenant import luban
    import pytest
    with pytest.raises(luban.LubanError) as exc:
        luban.read_table(_uint(1), _schema(_ITEM), "NoSuchConf")
    assert "NoSuchConf" in str(exc.value)


def test_a_parent_chain_that_loops_is_refused_rather_than_hung():
    from revenant import luban
    import pytest
    schema = _schema({"A": {"parent": "B", "fields": []},
                      "B": {"parent": "A", "fields": []}})
    with pytest.raises(luban.LubanError) as exc:
        luban.read_table(_uint(1), schema, "A")
    assert "loops" in str(exc.value)


def test_a_schema_is_read_from_the_json_a_project_writes_by_hand():
    from revenant import luban
    schema = _schema({"Base": {"abstract": True, "fields": []},
                      "A": {"parent": "Base", "id": 3, "fields": [
                          {"name": "x", "type": "int"},
                          {"name": "y", "type": "string", "nullable": True}]}},
                     tables={"tba": "A"})
    assert [f.name for f in schema.fields_of("A")] == ["x", "y"]
    assert schema.fields_of("A")[1].nullable
    assert schema.tables == {"tba": "A"}
    assert schema.bean_for_id(3) == "A"
    assert schema.bean("Base").abstract


# luban tables inside the #56 corpus

_LUBAN_SCHEMA = {
    "beans": {"ItemConf": {"fields": [
        {"name": "id", "type": "int"},
        {"name": "name", "type": "string"},
        {"name": "cost", "type": "float"},
    ]}},
    "tables": {"tbitem": "ItemConf"},
}


def _luban_project(tmp_path, *, schema=None, blob=None, container=""):
    """A project whose corpus holds one JSON table and one Luban blob."""
    root = str(tmp_path)
    corpus = os.path.join(root, "res", "conf")
    _write(os.path.join(corpus, "Item.json"), {"items": _rows(1)})
    _blob(os.path.join(corpus, "tbitem.bytes"),
          blob if blob is not None else _uint(1) + _item_row(1001, "Energy", 1.5))
    cfg = {"tables": {}}
    if schema is not None:
        _write(os.path.join(root, "luban.json"), schema)
        cfg["tables"]["luban_schema"] = "luban.json"
    if container:
        path = os.path.join(root, "container.py")
        with open(path, "w", encoding="utf-8") as f:
            f.write(container)
        cfg["tables"]["luban_container"] = "container.py"
    return root, cfg


def _luban_table(root, cfg):
    from revenant import tables as _t
    found = _t.discover(root, cfg=cfg)
    table = next(t for t in found.tables() if t.shape == _t.SHAPE_BINARY)
    return table, _t.readers_for(root, cfg=cfg)


def test_a_luban_blob_is_read_once_the_project_names_a_schema(tmp_path):
    from revenant import tables as _t
    root, cfg = _luban_project(tmp_path, schema=_LUBAN_SCHEMA)
    table, readers = _luban_table(root, cfg)
    data = _t.read(table, readers)
    assert data.reader == _t.READER_LUBAN
    assert data.rows == ({"id": 1001, "name": "Energy", "cost": 1.5},)
    assert data.fields == ("id", "name", "cost")
    assert data.error == ""


def test_a_binary_table_stays_unread_when_no_schema_is_configured(tmp_path):
    from revenant import tables as _t
    root, cfg = _luban_project(tmp_path)
    table, readers = _luban_table(root, cfg)
    data = _t.read(table, readers)
    assert data.reader == "" and data.rows == ()
    assert "#59" in data.error and "luban_schema" in data.error
    # not "(#59)": both binary readers exist, so this is this project's gap,
    # not revenant's, and the label must not point at a ticket that is closed
    assert data.label == f"binary ({_t.UNCLAIMED})"


def test_a_schema_that_does_not_cover_this_file_says_so(tmp_path):
    """Per file, not per project: a schema describing four of a corpus's five
    blobs must say which one it does not."""
    from revenant import tables as _t
    schema = dict(_LUBAN_SCHEMA, tables={"tbother": "ItemConf"})
    root, cfg = _luban_project(tmp_path, schema=schema)
    table, readers = _luban_table(root, cfg)
    data = _t.read(table, readers)
    assert data.reader == "" and "tbitem" in data.error
    # ...and it names which configured reader declined, because a binary corpus
    # can hold more than one framework and only one of them was asked.
    assert "luban_schema" in data.error


def test_a_short_schema_reports_misalignment_rather_than_rows_that_look_fine(tmp_path):
    """Rows come out and they are wrong. Leftover bytes are the only signal,
    so they are an error on the table, not a footnote."""
    from revenant import tables as _t
    schema = {"beans": {"ItemConf": {"fields": [{"name": "id", "type": "int"}]}},
              "tables": {"tbitem": "ItemConf"}}
    root, cfg = _luban_project(tmp_path, schema=schema)
    table, readers = _luban_table(root, cfg)
    data = _t.read(table, readers)
    assert data.reader == _t.READER_LUBAN
    assert "misaligned" in data.error and "left over" in data.error


def test_the_container_hook_is_the_projects_code(tmp_path):
    """Merge Cooking prefixes four bytes, Mystery Town XORs the lot. Neither
    belongs in revenant, so the project writes `decode` and revenant calls it."""
    from revenant import tables as _t
    plain = _uint(1) + _item_row(7, "x", 0.5)
    shipped = b"HEY\x01" + bytes(b ^ 0x5A for b in plain)
    root, cfg = _luban_project(
        tmp_path, schema=_LUBAN_SCHEMA, blob=shipped,
        container="def decode(data):\n    return bytes(b ^ 0x5A for b in data[4:])\n")
    table, readers = _luban_table(root, cfg)
    data = _t.read(table, readers)
    assert data.rows == ({"id": 7, "name": "x", "cost": 0.5},)


def test_a_container_that_throws_is_reported_on_the_table_not_raised(tmp_path):
    from revenant import tables as _t
    root, cfg = _luban_project(
        tmp_path, schema=_LUBAN_SCHEMA,
        container="def decode(data):\n    raise ValueError('wrong key')\n")
    table, readers = _luban_table(root, cfg)
    data = _t.read(table, readers)
    assert data.reader == "" and "container" in data.error and "wrong key" in data.error


def test_a_schema_path_that_has_moved_is_a_note_not_a_dead_listing(tmp_path):
    """One key pointing at a moved file must not cost the other four corpora
    their listing."""
    from revenant import tables as _t
    root, _cfg = _luban_project(tmp_path)
    readers = _t.readers_for(root, cfg={"tables": {"luban_schema": "gone.json"}})
    assert readers.luban_schema is None
    assert any("gone.json" in note for note in readers.notes), readers.notes


def test_a_container_hook_that_has_moved_is_a_note_too(tmp_path):
    from revenant import tables as _t
    root, _cfg = _luban_project(tmp_path)
    readers = _t.readers_for(root, cfg={"tables": {"luban_container": "gone.py"}})
    assert readers.luban_container is None
    assert any("gone.py" in note for note in readers.notes), readers.notes


# ── table census: what is actually in a field (#57) ─────────────────────────

def _census(rows, top=5):
    from revenant import tables as _t
    return {s.name: s for s in _t.census(rows, top=top)}


def test_census_reports_fill_distinct_and_the_common_values():
    from revenant import tables as _t
    rows = [{"id": i, "cost": 31 if i < 8 else 10000001} for i in range(10)]
    stats = _census(rows)
    assert [s.name for s in _t.census(rows)] == ["id", "cost"]
    assert (stats["cost"].present, stats["cost"].distinct) == (10, 2)
    assert stats["cost"].top[0] == ("31", 8)
    assert stats["cost"].top[1] == ("10000001", 2)
    assert stats["id"].distinct == 10


def test_a_value_distribution_shows_an_id_masquerading_as_a_quantity():
    """The case that named this ticket: `MergeTapCost.cost` read as "how much
    you pay" for half a day, when 652 rows hold one value and 141 hold eight-
    digit item ids. A quantity does not look like that."""
    rows = ([{"cost": 31}] * 652) + ([{"cost": 10000001}] * 141) + [{"cost": 7}]
    stat = _census(rows)["cost"]
    assert stat.top[0] == ("31", 652)
    assert stat.distinct == 3
    assert stat.present == 794


def test_a_field_missing_from_a_row_is_not_the_same_as_a_null_in_it():
    """Two different facts: nobody filled this column, versus the column is
    there and empty. Collapsing them loses which one to go and look at."""
    rows = [{"a": 1}, {"a": None}, {"b": 2}]
    stat = _census(rows)["a"]
    assert (stat.present, stat.null, stat.rows) == (2, 1, 3)
    assert _census(rows)["b"].present == 1


def test_top_values_are_truncated_and_say_how_many_were_left():
    rows = [{"v": i} for i in range(50)]
    stat = _census(rows, top=3)
    assert len(stat["v"].top) == 3
    assert stat["v"].truncated == 47
    assert stat["v"].distinct == 50


def test_a_numeric_string_is_not_printed_as_a_number():
    """`"31"` and `31` are different findings about a column, and a census that
    renders both as `31` hides the one worth knowing."""
    rows = [{"v": 31}, {"v": "31"}]
    stat = _census(rows)["v"]
    assert stat.distinct == 2
    assert {value for value, _count in stat.top} == {"31", '"31"'}


def test_true_is_not_counted_as_one():
    """Python makes `True == 1` and `hash(True) == hash(1)`; a census that keys
    on the value alone silently merges a flag column with a count column."""
    rows = [{"v": True}, {"v": 1}]
    stat = _census(rows)["v"]
    assert stat.distinct == 2


def test_an_int_and_a_float_of_the_same_value_stay_apart():
    rows = [{"v": 1}, {"v": 1.0}]
    assert _census(rows)["v"].distinct == 2


def test_unhashable_values_are_counted_by_what_they_render_as():
    """Protobuf-JSON and Luban rows both hold lists and nested objects. A census
    that dies on the first one is no use on the corpus it was written for."""
    rows = [{"drops": [1, 2]}, {"drops": [1, 2]}, {"drops": {"a": 1}}]
    stat = _census(rows)["drops"]
    assert stat.distinct == 2
    assert stat.top[0] == ("[1, 2]", 2)


def test_a_long_value_is_elided_so_one_field_stays_one_line():
    rows = [{"v": "x" * 200}]
    shown = _census(rows)["v"].top[0][0]
    assert len(shown) < 60 and shown.endswith("…")


def test_an_empty_table_censuses_to_nothing_rather_than_blowing_up():
    from revenant import tables as _t
    assert _t.census([]) == ()


def test_a_one_row_table_is_fine():
    stat = _census([{"a": 1}])["a"]
    assert (stat.rows, stat.present, stat.distinct) == (1, 1, 1)


def test_rows_that_share_no_fields_all_get_a_line():
    from revenant import tables as _t
    rows = [{"a": 1}, {"b": 2}, {"c": 3}]
    stats = _t.census(rows)
    assert [s.name for s in stats] == ["a", "b", "c"]
    assert all(s.present == 1 and s.rows == 3 for s in stats)


def test_rows_that_are_not_objects_have_no_fields_to_count():
    """A `json-rows` table can be an array of scalars. That is not a census
    failure, it is a table with no columns."""
    from revenant import tables as _t
    assert _t.census([1, 2, 3]) == ()


def test_two_long_values_sharing_a_prefix_are_two_values(tmp_path):
    """The display elides at 40 characters; the count must not. Keying on the
    elided text merges genuinely different drop tables into one value and
    reports a `distinct` that is quietly too low -- the same class of silent
    undercount the bounded sweep exists to avoid."""
    rows = [{"drops": [10000001, 10000002, 10000003, 10000004, n]} for n in (1, 2)]
    stat = _census(rows)["drops"]
    assert stat.distinct == 2
    assert len(stat.top) == 2
    assert all(shown.endswith("…") for shown, _count in stat.top), "still elided to read"
    # ...and since the two print alike, the line says they are not the same value
    assert "differ past the cut" in stat.values


def test_nested_objects_differing_past_the_elision_stay_apart():
    rows = [{"o": {"prefix_padding_padding_padding_xxxx": n}} for n in range(4)]
    assert _census(rows)["o"].distinct == 4


def test_the_left_over_count_is_derived_from_what_was_actually_shown():
    """`truncated` used to be computed from the requested `top` rather than from
    the values emitted, so the two numbers could disagree in the same line."""
    from revenant import tables as _t
    rows = [{"v": i} for i in range(10)]
    for top in (0, 1, 3, 10, 25):
        stat = _t.census(rows, top=top)[0]
        assert stat.truncated == stat.distinct - len(stat.top), top


def test_a_negative_top_shows_nothing_rather_than_everything():
    """Python's `ranked[:-1]` drops the last element instead of clamping, which
    turned `--top -1` into "print all 1,499 values on one line" -- defeating the
    one guarantee this command makes about staying readable."""
    from revenant import tables as _t
    rows = [{"v": i} for i in range(50)]
    stat = _t.census(rows, top=-1)[0]
    assert stat.top == ()
    assert stat.truncated == 50


def test_a_field_stat_phrases_its_own_columns():
    rows = [{"v": 1}, {"v": 1}, {"w": 2}]
    stat = _census(rows)["v"]
    assert stat.filled == "2/3  67%"
    assert stat.values == "1 ×2"
    assert _census(rows, top=0)["v"].values == "(+1 more)"


# ── FlatBuffers: reading a big table without walking bogus vtables (#60) ────

def _bump_u16(monkeypatch, fb):
    """Count every `u16` read, so a test can assert on work rather than time."""
    reads = []
    original = fb.Buffer.u16

    def counted(self, p):
        reads.append(p)
        return original(self, p)

    monkeypatch.setattr(fb.Buffer, "u16", counted)
    return reads


def test_asking_whether_bytes_are_a_table_does_not_walk_a_declared_vtable(monkeypatch):
    """A probe runs `as_table` over bytes that are usually not a table, where
    the declared vtable length is arbitrary. Building the offset list to answer
    a yes/no question walked up to 32,765 slots per call; the cost is in
    `research/flatbuffers-read-profile.md`. Asserted as work, not wall clock."""
    from revenant import flatbuffers as fb
    blob = bytearray(70000)
    struct.pack_into("<I", blob, 0x100, 0x40)       # a pointer to 0x140
    struct.pack_into("<i", blob, 0x140, -0x40)      # soffset -> vtable at 0x180
    struct.pack_into("<H", blob, 0x180, 0xFFFE)     # declaring 32,765 slots
    reads = _bump_u16(monkeypatch, fb)
    answer = fb.as_table(fb.Buffer(bytes(blob)), 0x100)
    assert answer == 0x140, "same answer as before -- this is a speed change"
    assert len(reads) < 100, f"{len(reads)} u16 reads to answer a yes/no question"


def test_a_vtable_shorter_than_its_own_header_yields_an_empty_list(monkeypatch):
    """`vt_len` of 2 clears every guard -- non-zero, even, inside the buffer --
    and yields a slot count of **-1**, which is truthy. The loop this replaced
    ran `range(-1)` and produced an empty list; a batched read hands the -1 to
    `struct` as a repeat count and raises. Same inputs, same answers, including
    the malformed ones a probe meets constantly."""
    from revenant import flatbuffers as fb
    blob = bytearray(64)
    struct.pack_into("<i", blob, 0x20, 0x20 - 0x10)   # table 0x20, vtable 0x10
    struct.pack_into("<H", blob, 0x10, 2)             # a two-byte vtable
    buf = fb.Buffer(bytes(blob))
    assert fb.vtable_header(buf, 0x20) == (-1, 0x10)
    assert fb.vtable(buf, 0x20) == (-1, [])
    # ...and `as_table` still reads it as a table, because -1 is truthy and that
    # is what this module has always done with it.
    struct.pack_into("<I", blob, 0x1C, 4)
    assert fb.as_table(fb.Buffer(bytes(blob)), 0x1C) == 0x20


def test_a_vtable_ending_exactly_at_the_buffer_end_is_still_read_whole():
    """The batched read is in bounds by construction; the case that proves it is
    the one with no slack left."""
    from revenant import flatbuffers as fb
    blob = bytearray(0x30)
    struct.pack_into("<i", blob, 0x20, 0x20 - 0x28)   # vtable at 0x28
    struct.pack_into("<4H", blob, 0x28, 8, 12, 4, 8)  # vt_len 8 -> ends at 0x30
    buf = fb.Buffer(bytes(blob))
    assert fb.vtable(buf, 0x20) == (2, [0x24, 0x28])
    assert fb.vtable_header(buf, 0x20)[0] == 2


def test_asking_whether_bytes_are_a_table_does_not_walk_a_declared_vtable(monkeypatch):
    """A probe runs `as_table` over bytes that are usually not a table, where
    the declared vtable length is arbitrary. `0xfffe` passes every bounds check
    on a buffer over 64 KB, and building the offset list to answer a yes/no
    question walked 32,765 slots -- 9 million `u16` reads for 11 thousand
    lookups, and 98% of the time to read a table."""
    from revenant import flatbuffers as fb
    blob = bytearray(70000)
    struct.pack_into("<I", blob, 0x100, 0x40)       # a pointer to 0x140
    struct.pack_into("<i", blob, 0x140, -0x40)      # soffset -> vtable at 0x180
    struct.pack_into("<H", blob, 0x180, 0xFFFE)     # declaring 32,765 slots
    reads = []
    original = fb.Buffer.u16
    monkeypatch.setattr(fb.Buffer, "u16",
                        lambda self, p: (reads.append(p), original(self, p))[1])
    answer = fb.as_table(fb.Buffer(bytes(blob)), 0x100)
    assert answer == 0x140, "same answer as before -- this is a speed change"
    assert len(reads) <= 4, f"{len(reads)} u16 reads to answer a yes/no question"


def test_the_offset_list_is_what_reading_each_slot_one_at_a_time_gives():
    """`vtable` reads its offsets in one `unpack_from` now; the property that
    has to survive is that the batch and the slot-by-slot loop agree."""
    from revenant import flatbuffers as fb
    buf = fb.Buffer(_fb_buffer())
    slots, out = fb.vtable(buf, 0x20)
    declared, vt = fb.vtable_header(buf, 0x20)
    assert declared == slots
    by_hand = [(0x20 + off if off else None)
               for off in (buf.u16(vt + 4 + i * 2) for i in range(slots))]
    assert out == by_hand
    assert out == [0x24, 0x28, 0x2C], "and those are the positions it always gave"


def test_a_position_that_is_not_a_table_is_still_not_a_table():
    from revenant import flatbuffers as fb
    buf = fb.Buffer(b"\x00" * 64)
    assert fb.vtable_header(buf, 0) == (0, None)
    assert fb.vtable(buf, 0) == (0, [])
    assert fb.as_table(buf, 0) is None


# ── the FlatBuffers corpus: a CMS library read as tables (#62) ──────────────

from tests.fixtures import FB_SCHEMA as _FB_SCHEMA, flatbuffers_rows as _fb_rows_buffer


def _fb_project(tmp_path, *, schema=None, roots=None, blob=None, containers=None):
    root = str(tmp_path)
    corpus = os.path.join(root, "res", "cms-embedded")
    _write(os.path.join(corpus, "Other.json"), {"items": _rows(1)})
    _blob(os.path.join(corpus, "currencies.bin"),
          blob if blob is not None else _fb_rows_buffer())
    section = {}
    if schema is not None:
        _write(os.path.join(root, "cms.json"), schema)
        section["fb_schema"] = "cms.json"
    if roots is not None:
        section["fb_roots"] = roots
    if containers is not None:
        section["fb_containers"] = containers
    return root, {"tables": section}


def _fb_table(root, cfg):
    from revenant import tables as _t
    found = _t.discover(root, cfg=cfg)
    table = next(t for t in found.tables() if t.shape == _t.SHAPE_BINARY)
    return table, _t.readers_for(root, cfg=cfg)


def test_a_flatbuffers_blob_reads_as_rows_once_the_project_names_its_root(tmp_path):
    from revenant import tables as _t
    root, cfg = _fb_project(tmp_path, schema=_FB_SCHEMA,
                            roots={"currencies": "Game.CMS.Db"})
    table, readers = _fb_table(root, cfg)
    data = _t.read(table, readers)
    assert data.reader == _t.READER_FB
    assert data.rows == ({"Id": 100, "Name": "item_0"},
                         {"Id": 101, "Name": "item_1"},
                         {"Id": 102, "Name": "item_2"})
    assert data.fields == ("Id", "Name")
    assert data.error == ""


def test_two_vectors_in_one_root_is_a_question_only_the_project_can_answer(tmp_path):
    """Which slot holds "the rows" is a fact about that title's CMS, not about
    FlatBuffers. Picking one would read a different table than the reader meant."""
    from revenant import tables as _t
    schema = json.loads(json.dumps(_FB_SCHEMA))
    schema["classes"]["Game.CMS.Db"]["fields"]["1"] = {
        "name": "Codes", "fb_type": "offset", "cs_type": "int[]"}
    root, cfg = _fb_project(tmp_path, schema=schema,
                            roots={"currencies": "Game.CMS.Db"},
                            blob=_fb_rows_buffer(second_vector=True))
    table, readers = _fb_table(root, cfg)
    data = _t.read(table, readers)
    assert data.reader == "" and "2 fields" in data.error
    assert "Game.CMS.Db#<field>" in data.error, "and it says how to answer it"


def test_naming_the_field_picks_the_vector(tmp_path):
    from revenant import tables as _t
    schema = json.loads(json.dumps(_FB_SCHEMA))
    schema["classes"]["Game.CMS.Db"]["fields"]["1"] = {
        "name": "Codes", "fb_type": "offset", "cs_type": "int[]"}
    root, cfg = _fb_project(tmp_path, schema=schema,
                            roots={"currencies": "Game.CMS.Db#Items"},
                            blob=_fb_rows_buffer(second_vector=True))
    table, readers = _fb_table(root, cfg)
    data = _t.read(table, readers)
    assert data.reader == _t.READER_FB
    assert [r["Id"] for r in data.rows] == [100, 101, 102]


def test_a_field_the_root_does_not_have_lists_the_ones_it_does(tmp_path):
    from revenant import tables as _t
    root, cfg = _fb_project(tmp_path, schema=_FB_SCHEMA,
                            roots={"currencies": "Game.CMS.Db#Nope"})
    table, readers = _fb_table(root, cfg)
    data = _t.read(table, readers)
    assert "Nope" in data.error and "Items" in data.error


def test_a_root_class_the_schema_does_not_have_says_so(tmp_path):
    from revenant import tables as _t
    root, cfg = _fb_project(tmp_path, schema=_FB_SCHEMA,
                            roots={"currencies": "Game.CMS.Missing"})
    table, readers = _fb_table(root, cfg)
    assert "Missing" in _t.read(table, readers).error


def test_roots_without_a_schema_are_refused_rather_than_probed(tmp_path):
    """Decoding against no schema probes every slot, which is a page of `?`
    markers dressed up as a table."""
    from revenant import tables as _t
    root, cfg = _fb_project(tmp_path, roots={"currencies": "Game.CMS.Db"})
    readers = _t.readers_for(root, cfg=cfg)
    assert any("no usable fb_schema" in n for n in readers.notes), readers.notes
    # ...and the roots stay, so the corpus does not vanish along with them: the
    # blob is still listed, still counted, and says why it went unread.
    assert readers.fb_roots, "clearing these would un-claim a .bin-only corpus"
    found = _t.discover(root, cfg=cfg)
    table = next(t for t in found.tables() if t.shape == _t.SHAPE_BINARY)
    assert "fb_schema" in _t.read(table, readers).error


def test_a_blob_no_configured_reader_claims_names_the_ones_asked(tmp_path):
    from revenant import tables as _t
    root, cfg = _fb_project(tmp_path, schema=_FB_SCHEMA, roots={"elsewhere": "Game.CMS.Db"})
    table, readers = _fb_table(root, cfg)
    data = _t.read(table, readers)
    assert "currencies" in data.error and "fb_roots" in data.error


def test_with_nothing_configured_a_blob_names_both_routes(tmp_path):
    from revenant import tables as _t
    root, cfg = _fb_project(tmp_path)
    table, readers = _fb_table(root, cfg)
    data = _t.read(table, readers)
    assert "#59" in data.error and "#62" in data.error


def test_a_probed_value_keeps_its_marker_through_a_census(tmp_path):
    """The point of the marker: a census of a FlatBuffers table has to show
    which columns were guessed at, so a reader knows to drop those a tier."""
    from revenant import tables as _t
    thin = {"classes": {"Game.CMS.Db": _FB_SCHEMA["classes"]["Game.CMS.Db"],
                        "Game.CMS.Item": {"slots": 2, "fields": {
                            0: {"name": "Id", "fb_type": "offset", "cs_type": "Mystery"}}}}}
    root, cfg = _fb_project(tmp_path, schema=thin, roots={"currencies": "Game.CMS.Db"})
    table, readers = _fb_table(root, cfg)
    data = _t.read(table, readers)
    stats = {s.name: s for s in _t.census(data.rows)}
    assert all(v.startswith('"?') for v, _c in stats["Id"].top), stats["Id"].top
    assert "slot1?" in stats, "and an undeclared slot is named as one"


def test_a_directory_of_only_blobs_is_a_corpus_once_the_project_claims_one(tmp_path):
    """A CMS library is a directory of `.bin` and nothing else. The rule that
    keeps `res/`'s extracted TextAssets out would keep it out too -- unless the
    project has already said, in `fb_roots`, that one of those files is a table.
    That statement is the evidence the JSON sniff stands in for."""
    from revenant import tables as _t
    root = str(tmp_path)
    cms = os.path.join(root, "res", "cms-embedded")
    _blob(os.path.join(cms, "currencies.bin"), _fb_rows_buffer())
    _blob(os.path.join(cms, "recipes.bin"), _fb_rows_buffer())
    _write(os.path.join(root, "cms.json"), _FB_SCHEMA)

    unclaimed = _t.discover(root, cfg={})
    assert unclaimed.corpora == (), "extraction output until something says otherwise"

    cfg = {"tables": {"fb_schema": "cms.json",
                      "fb_roots": {"currencies": "Game.CMS.Db"}}}
    found = _t.discover(root, cfg=cfg)
    assert [c.rel for c in found.corpora] == [os.path.join("res", "cms-embedded")]
    # both blobs are listed: the corpus is the directory, and the one nothing
    # claims still gets a line saying so rather than vanishing from the count
    assert sorted(t.name for t in found.tables()) == ["currencies", "recipes"]
    readers = _t.readers_for(root, cfg=cfg)
    by_name = {t.name: _t.read(t, readers) for t in found.tables()}
    assert by_name["currencies"].reader == _t.READER_FB
    assert by_name["recipes"].reader == "" and "recipes" in by_name["recipes"].error


def test_status_counting_files_never_runs_the_projects_own_code(tmp_path):
    """`claimed_names` is what discovery needs, and `status` calls discovery on
    every visit. Building the readers instead would import and execute the
    title's container hook to answer "how many files are there"."""
    from revenant import tables as _t
    root = str(tmp_path)
    _write(os.path.join(root, "res", "conf", "Item.json"), {"items": _rows(1)})
    bomb = os.path.join(root, "boom.py")
    with open(bomb, "w", encoding="utf-8") as f:
        f.write("raise SystemExit('the container hook ran during a count')\n")
    cfg = {"tables": {"luban_container": "boom.py"}}
    assert _t.claimed_names(root, cfg) == set()
    found = _t.discover(root, cfg=cfg)          # must not import boom.py
    assert [t.name for t in found.tables()] == ["Item"]


def test_claimed_names_reads_the_luban_map_without_loading_a_reader(tmp_path):
    from revenant import tables as _t
    root = str(tmp_path)
    _write(os.path.join(root, "luban.json"),
           {"beans": {"A": {"fields": []}}, "tables": {"tbitem": "A"}})
    cfg = {"tables": {"luban_schema": "luban.json", "fb_roots": {"cms": "X"}}}
    assert _t.claimed_names(root, cfg) == {"tbitem", "cms"}


def test_a_schema_that_will_not_load_leaves_the_claim_intact(tmp_path):
    """Otherwise the corpus vanishes with the schema: a `.bin`-only directory
    stops qualifying and its tables leave the count instead of being listed as
    unread, which is the one thing this module refuses to do."""
    from revenant import tables as _t
    root = str(tmp_path)
    cms = os.path.join(root, "res", "cms-embedded")
    _blob(os.path.join(cms, "currencies.bin"), _fb_rows_buffer())
    with open(os.path.join(root, "broken.json"), "w", encoding="utf-8") as f:
        f.write("{not json")
    cfg = {"tables": {"fb_schema": "broken.json",
                      "fb_roots": {"currencies": "Game.CMS.Db"}}}
    found = _t.discover(root, cfg=cfg)
    assert [t.name for t in found.tables()] == ["currencies"], "still a corpus"
    readers = _t.readers_for(root, cfg=cfg)
    assert any("broken.json" in n for n in readers.notes), readers.notes


def test_a_row_that_reads_like_the_truncation_marker_is_still_a_row(tmp_path):
    """Truncation is decided by the length, not by the look of the last value:
    `read_vector` shows `min(count, limit)` items plus at most one marker, so
    `limit + 1` happens exactly when it cut. Sniffing the string would drop a
    real last row whose text happens to match."""
    from revenant import tables as _t
    root = str(tmp_path)
    cms = os.path.join(root, "res", "cms")
    _blob(os.path.join(cms, "t.bin"),
          _fb_rows_buffer(3, names=["a", "b", "... 9 more"]))
    _write(os.path.join(root, "cms.json"), _FB_SCHEMA)
    cfg = {"tables": {"fb_schema": "cms.json", "fb_roots": {"t": "Game.CMS.Db"}}}
    table = _t.discover(root, cfg=cfg).tables()[0]
    data = _t.read(table, _t.readers_for(root, cfg=cfg))
    assert len(data.rows) == 3 and data.partial == ""
    assert data.rows[-1]["Name"] == "... 9 more"


def test_a_partial_read_still_hands_back_its_rows(tmp_path):
    """A cut table's values are sound and only its count is short, so `rows()`
    returns them. An `error` is different and still refuses."""
    from revenant import tables as _t
    table = Table = _t.Table(name="x", path="/nowhere", corpus="res", shape="binary")
    cut = _t.TableData(table, reader=_t.READER_FB, rows=({"a": 1},),
                       partial="only the first 2 rows were read")
    broken = _t.TableData(table, error="could not decode")
    assert cut.rows and not cut.error
    assert broken.error and not broken.partial


def test_a_vector_of_numbers_is_not_a_vector_of_rows(tmp_path):
    from revenant import tables as _t
    root = str(tmp_path)
    cms = os.path.join(root, "res", "cms")
    _blob(os.path.join(cms, "t.bin"), _fb_rows_buffer(second_vector=True))
    schema = json.loads(json.dumps(_FB_SCHEMA))
    schema["classes"]["Game.CMS.Db"]["fields"]["1"] = {
        "name": "Codes", "fb_type": "offset", "cs_type": "int[]"}
    _write(os.path.join(root, "cms.json"), schema)
    cfg = {"tables": {"fb_schema": "cms.json",
                      "fb_roots": {"t": "Game.CMS.Db#Codes"}}}
    table = _t.discover(root, cfg=cfg).tables()[0]
    data = _t.read(table, _t.readers_for(root, cfg=cfg))
    assert "vector of values, not of rows" in data.error


def test_a_file_both_readers_claim_is_refused_rather_than_raced(tmp_path):
    """Whichever ran first would win and print rows from the wrong decoder,
    with nothing in the output saying a choice was made."""
    from revenant import tables as _t
    root = str(tmp_path)
    cms = os.path.join(root, "res", "cms")
    _blob(os.path.join(cms, "t.bin"), _fb_rows_buffer())
    _write(os.path.join(root, "cms.json"), _FB_SCHEMA)
    _write(os.path.join(root, "luban.json"),
           {"beans": {"A": {"fields": [{"name": "n", "type": "int"}]}},
            "tables": {"t": "A"}})
    cfg = {"tables": {"fb_schema": "cms.json", "luban_schema": "luban.json",
                      "fb_roots": {"t": "Game.CMS.Db"}}}
    table = _t.discover(root, cfg=cfg).tables()[0]
    data = _t.read(table, _t.readers_for(root, cfg=cfg))
    assert data.reader == "" and "two readers claim" in data.error


# ── FlatBuffers unions: the tag slot and the value slot are one field (#61) ──

def test_one_read_handed_to_two_helpers_is_a_union_pair():
    """Structural, not by name. The serialiser reads the field once and hands
    it to two different helpers; FlatBuffers gives the type slot the lower id."""
    from revenant import flatbuffers as fb
    assert fb.pair_unions({0: (0x10, 0xAA), 1: (0x10, 0xBB)}) == {1: 0}


def test_an_inline_field_read_twice_is_not_a_union():
    """The case this file already documents: an identified variable serialises
    as its reference plus its resolved inline value, both off the same offset.
    Two slots, one read, and not a union -- pairing them would hand a real field
    a fabricated tag and swallow the other half. No helper, no pair."""
    from revenant import flatbuffers as fb
    assert fb.pair_unions({0: (0x28, None), 1: (0x28, None)}) == {}
    assert fb.pair_unions({0: (0x28, 0xAA), 1: (0x28, 0xAA)}) == {}, "one helper twice"


def test_a_read_reaching_three_slots_is_not_guessed_at():
    from revenant import flatbuffers as fb
    assert fb.pair_unions({0: (1, 0xA), 1: (1, 0xB), 2: (1, 0xC)}) == {}


def _union_buffer(tags=(1, 2), values=2) -> bytes:
    """A root whose slot 0 is a vector of union tags and slot 1 the values."""
    out = bytearray(b"\x00\x00\x00\x00")
    item_vt = len(out)
    out += struct.pack("<3H", 6, 8, 4)
    root_vt = len(out)
    out += struct.pack("<4H", 8, 12, 4, 8)
    root = len(out)
    out += b"\x00" * 12
    tagvec = len(out)
    out += struct.pack("<I", len(tags)) + bytes(tags)
    while len(out) % 4:
        out.append(0)
    valvec = len(out)
    out += b"\x00" * (4 + values * 4)
    items = []
    for _ in range(values):
        items.append(len(out))
        out += b"\x00" * 8
    struct.pack_into("<I", out, 0, root)
    struct.pack_into("<i", out, root, root - root_vt)
    struct.pack_into("<I", out, root + 4, tagvec - (root + 4))
    struct.pack_into("<I", out, root + 8, valvec - (root + 8))
    struct.pack_into("<I", out, valvec, values)
    for i, pos in enumerate(items):
        struct.pack_into("<I", out, valvec + 4 + i * 4, pos - (valvec + 4 + i * 4))
        struct.pack_into("<i", out, pos, pos - item_vt)
        struct.pack_into("<i", out, pos + 4, 700 + i)
    return bytes(out)


def _single_union_buffer(tag=1) -> bytes:
    """The canonical union: a `ubyte` tag slot and one value offset."""
    out = bytearray(b"\x00\x00\x00\x00")
    item_vt = len(out)
    out += struct.pack("<3H", 6, 8, 4)
    root_vt = len(out)
    out += struct.pack("<4H", 8, 12, 4, 8)
    root = len(out)
    out += b"\x00" * 12
    item = len(out)
    out += b"\x00" * 8
    struct.pack_into("<I", out, 0, root)
    struct.pack_into("<i", out, root, root - root_vt)
    out[root + 4] = tag                                   # a bare byte, not a vector
    struct.pack_into("<I", out, root + 8, item - (root + 8))
    struct.pack_into("<i", out, item, item - item_vt)
    struct.pack_into("<i", out, item + 4, 900)
    return bytes(out)


_COINS = {"slots": 1, "fields": {0: {"name": "Amount", "fb_type": "int32",
                                     "cs_type": "int"}}}
_UNION_CLASSES = {
    "Game.Slot": {"slots": 2, "unions": {1: 0}, "fields": {
        1: {"name": "Rewards", "fb_type": "offset", "cs_type": "Game.Reward[]"}}},
    "Game.Coins": _COINS,
    "Game.Item": {"slots": 1, "fields": {0: {"name": "ItemId", "fb_type": "int32",
                                             "cs_type": "int"}}},
}
_MEMBERS = {"Reward": ["None", "Game.Coins", "Game.Item"]}


def test_each_union_element_decodes_as_the_class_its_own_tag_names():
    """The point of pairing. The value slot is an offset and the encoding says
    nothing about what it points at -- only the tag does. Element 0 and element
    1 need not be the same class, which is what a union is."""
    from revenant import flatbuffers as fb
    schema = fb.Schema.from_dict({"classes": _UNION_CLASSES, "union_members": _MEMBERS})
    out = fb.Reader(_union_buffer((1, 2)), schema).read("Game.Slot")
    assert set(out) == {"Rewards"}, "one field, not a loose tag slot beside it"
    assert out["Rewards"]["type"] == ["Game.Coins", "Game.Item"]
    assert out["Rewards"]["value"] == [{"Amount": 700}, {"ItemId": 701}]
    assert not any(str(v).startswith(fb.INFERRED)
                   for v in out["Rewards"]["value"]), "concrete, not probed"


def test_the_canonical_single_union_decodes_too():
    """A `ubyte` tag and one offset -- the shape a non-repeated union has, and
    the one that fell through to a probe."""
    from revenant import flatbuffers as fb
    schema = fb.Schema.from_dict({
        "classes": {**_UNION_CLASSES,
                    "Game.Slot": {"slots": 2, "unions": {1: 0}, "fields": {
                        1: {"name": "Reward", "fb_type": "offset",
                            "cs_type": "Game.Reward"}}}},
        "union_members": _MEMBERS})
    out = fb.Reader(_single_union_buffer(2), schema).read("Game.Slot")
    assert out["Reward"] == {"type": ["Game.Item"], "value": {"ItemId": 900}}


def test_without_a_member_list_the_tags_are_numbers_and_it_says_why():
    from revenant import flatbuffers as fb
    schema = fb.Schema.from_dict({"classes": _UNION_CLASSES})
    reader = fb.Reader(_union_buffer((1, 2)), schema)
    out = reader.read("Game.Slot")
    assert out["Rewards"]["type"] == [1, 2], "reported, just not named"
    assert any("union_members" in n and "Reward" in n for n in reader.notes), reader.notes


def test_a_member_list_that_is_not_a_list_of_names_is_refused():
    """Hand-written JSON. A string is iterable and would hand back single
    characters as class names, which is worse than no name at all."""
    from revenant import flatbuffers as fb
    for bad in ("Game.Coins", {"1": "Game.Coins"}, [1, 2]):
        schema = fb.Schema.from_dict({"classes": _UNION_CLASSES,
                                      "union_members": {"Reward": bad}})
        reader = fb.Reader(_union_buffer((1, 1)), schema)
        out = reader.read("Game.Slot")
        assert out["Rewards"]["type"] == [1, 1], bad
        assert any("not a list of class names" in n for n in reader.notes), bad


def test_a_tag_past_the_member_list_stays_a_number():
    from revenant import flatbuffers as fb
    schema = fb.Schema.from_dict({"classes": _UNION_CLASSES,
                                  "union_members": {"Reward": ["None", "Game.Coins"]}})
    out = fb.Reader(_union_buffer((1, 9)), schema).read("Game.Slot")
    assert out["Rewards"]["type"] == ["Game.Coins", 9], "no invented member name"
    assert out["Rewards"]["value"][1].startswith(fb.INFERRED), "and its value is probed"


def test_an_unnamed_pair_is_one_field_and_says_what_is_missing():
    """The case the ticket is about. It still reads as one field, in the same
    shape as a resolved one so a census sees one column, and the reason is
    stated rather than left for a reader to infer from two `?`."""
    from revenant import flatbuffers as fb
    schema = fb.Schema.from_dict({"classes": {
        "Game.Slot": {"slots": 2, "unions": {1: 0}, "fields": {}}}})
    reader = fb.Reader(_union_buffer((1, 2)), schema)
    out = reader.read("Game.Slot")
    assert list(out) == ["slot1?"], "one entry for the pair"
    assert out["slot1?"]["type"] == [1, 2], "and the tags are still there"
    assert any("slots 0 and 1" in n for n in reader.notes), reader.notes
    assert [kind for _p, kind in reader.inferred].count("union") == 1


def test_a_missing_value_slot_keeps_the_tag_instead_of_dropping_the_field():
    """Skipping the tag slot is right only because the value half reports it.
    With no value half, saying nothing would lose the tag data too -- worse than
    what this ticket replaced."""
    from revenant import flatbuffers as fb
    blob = bytearray(_union_buffer((1, 2)))
    struct.pack_into("<H", blob, 0x10, 0)             # unset the value slot
    schema = fb.Schema.from_dict({"classes": _UNION_CLASSES, "union_members": _MEMBERS})
    reader = fb.Reader(bytes(blob), schema)
    out = reader.read("Game.Slot")
    assert out["Rewards"]["type"] == ["Game.Coins", "Game.Item"]
    assert out["Rewards"]["value"] is None
    assert any("value slot" in n for n in reader.notes), reader.notes


def test_halves_of_different_lengths_are_reported_not_papered_over():
    from revenant import flatbuffers as fb
    schema = fb.Schema.from_dict({"classes": _UNION_CLASSES, "union_members": _MEMBERS})
    reader = fb.Reader(_union_buffer((1,), values=2), schema)
    reader.read("Game.Slot")
    assert any("disagree" in n for n in reader.notes), reader.notes


def test_a_union_slot_paired_with_itself_is_not_a_union():
    from revenant import flatbuffers as fb
    schema = fb.Schema.from_dict({"classes": {
        "Game.Slot": {"slots": 2, "unions": {1: 1}, "fields": {
            1: {"name": "Rewards", "fb_type": "offset", "cs_type": "int"}}}}})
    out = fb.Reader(_union_buffer(), schema).read("Game.Slot")
    assert "Rewards" in out, "the field survives rather than being skipped as a tag"


def test_the_inferred_marker_still_prefixes_a_probed_union_value():
    """`?` means the type was probed, not declared. Pairing makes fewer slots
    need probing; it does not change what the prefix claims."""
    from revenant import flatbuffers as fb
    schema = fb.Schema.from_dict({"classes": {
        "Game.Slot": {"slots": 2, "unions": {1: 0}, "fields": {}}}})
    out = fb.Reader(_union_buffer(), schema).read("Game.Slot")
    assert all(v.startswith(fb.INFERRED) for v in out["slot1?"]["value"])


def test_a_member_naming_a_class_the_schema_lacks_says_which_repair_is_needed():
    """"No member list" and "the member list and the class list disagree" are
    two different fixes, so they are two different notes."""
    from revenant import flatbuffers as fb
    schema = fb.Schema.from_dict({
        "classes": _UNION_CLASSES,
        "union_members": {"Reward": ["None", "Game.Nowhere"]}})
    reader = fb.Reader(_union_buffer((1, 1)), schema)
    out = reader.read("Game.Slot")
    assert out["Rewards"]["type"] == ["Game.Nowhere", "Game.Nowhere"]
    assert all(str(v).startswith(fb.INFERRED) for v in out["Rewards"]["value"])
    assert any("no such class" in n for n in reader.notes), reader.notes


def test_recovery_carries_the_pairing_all_the_way_into_the_schema(tmp_path):
    """End to end, not just the pure rule: ISIL where one accessor feeds two
    different helpers must come out of `recover_schema` with `unions` set, and
    `Schema.from_dict` must read it back."""
    from revenant import flatbuffers as fb
    isil, src = tmp_path / "IsilDump", tmp_path / "src"
    (isil / "Game").mkdir(parents=True)
    (src / "Game").mkdir(parents=True)
    (isil / "Game" / "Slot.txt").write_text(
        "Type: Game.Slot\n\n"
        "Method: System.Int32 SerializeToBuffer(FlatBufferBuilder builder)\n"
        "\tISIL:\n"
        "\t\t000 Move X20, X0\n"
        "\t\t001 Move W1, 2\n"
        "\t\t002 Call FlatBufferBuilder.StartObject\n"
        "\t\t003 Move X1, X20\n"
        "\t\t004 Call 0x00A00000, X1\n"                   # GetItems()
        "\t\t005 Call 0x00B00000, X0\n"                   # -> the tag helper
        "\t\t006 Move X2, X0\n"
        "\t\t007 Move W1, W31\n"
        "\t\t008 Call FlatBufferBuilder.AddOffset, X0, X1, X2, X3\n"
        "\t\t009 Move X1, X20\n"
        "\t\t010 Call 0x00A00000, X1\n"                   # the same read
        "\t\t011 Call 0x00C00000, X0\n"                   # -> a different helper
        "\t\t012 Move X2, X0\n"
        "\t\t013 Move W1, 1\n"
        "\t\t014 Call FlatBufferBuilder.AddOffset, X0, X1, X2, X3\n"
        "\t\t015 Call FlatBufferBuilder.EndObject\n"
        "\tDisassembly:\n\t\t0x0 nop\n")
    (src / "Game" / "Slot.cs").write_text("public sealed class Slot\n{\n}\n")
    recovered = fb.recover_schema(str(isil), str(src), rva_index={})
    assert recovered.classes["Game.Slot"]["unions"] == {1: 0}
    assert recovered.summary()["unions_paired"] == 1
    again = fb.Schema.from_dict(json.loads(json.dumps(recovered.to_dict())))
    assert again.unions("Game.Slot") == {1: 0}


# ── table diff: what two tables actually disagree about (#63) ───────────────

def _diff(a, b, **kw):
    from revenant import tables as _t
    return _t.diff(a, b, **kw)


def test_field_names_align_across_codegen_styles():
    """Hotel Legacy and Tasty Travels are the same game with different codegen.
    Compared literally, eight core tables came back "all different"; aligned,
    the currency table matched row for row."""
    from revenant import tables as _t
    a = [{"costId": 1, "goldAmount": 10}]
    b = [{"CostId": 1, "Gold_Amount": 10}]
    assert _diff(a, b).fields_only_in_a == ("costId", "goldAmount")
    aligned = _diff(a, b, normalize_names=True)
    assert aligned.fields_only_in_a == () and aligned.fields_only_in_b == ()
    assert aligned.changed == () and aligned.same == 1
    assert _t.normalize_name("Gold_Amount") == _t.normalize_name("goldAmount")


def test_a_column_whose_two_sides_hold_different_kinds_is_not_counted_as_content():
    """The 929-row case: one side's tag was never recovered, so its bytes render
    as hex strings. `costId: [1]` against `["01"]` is a decoding difference, and
    reporting it as 929 differing rows is a confident wrong answer."""
    a = [{"id": i, "costId": [1]} for i in range(929)]
    b = [{"id": i, "costId": ["01"]} for i in range(929)]
    out = _diff(a, b)
    assert out.changed == (), "not one row counted as a content difference"
    assert len(out.incomparable) == 1
    column = out.incomparable[0]
    assert column.field == "costId"
    assert column.rows == 929
    assert "list[str]" in column.b_kinds and "list[int]" in column.a_kinds


def test_a_real_value_difference_is_still_reported():
    out = _diff([{"id": 1, "cost": 5}], [{"id": 1, "cost": 7}])
    assert out.same == 0
    assert [(c.key, c.field, c.a, c.b) for c in out.changed] == [(1, "cost", 5, 7)]
    assert out.incomparable == ()


def test_rows_on_one_side_only_are_the_useful_by_product():
    """FAT's two titles got a feature-difference list out of this without
    reading a line of code."""
    out = _diff([{"id": 1}, {"id": 2}], [{"id": 2}, {"id": 3}])
    assert out.only_in_a == (1,) and out.only_in_b == (3,)
    assert out.same == 1


def test_the_key_is_the_first_field_that_identifies_a_row_on_both_sides():
    """Structural: a field whose values are unique and present throughout. Not
    "the one called id" -- inferring meaning from a name is a game fact."""
    from revenant import tables as _t
    a = [{"tier": 1, "sku": "x"}, {"tier": 1, "sku": "y"}]
    b = [{"tier": 1, "sku": "x"}, {"tier": 2, "sku": "y"}]
    out = _t.diff(a, b)
    assert out.key_field == "sku", "tier repeats on side A, so it cannot key it"


def test_with_no_field_identifying_a_row_it_falls_back_to_position_and_says_so():
    a = [{"v": 1}, {"v": 1}]
    b = [{"v": 1}, {"v": 2}]
    out = _diff(a, b)
    assert out.key_field == ""
    assert out.changed and out.changed[0].key == 1, "the row index"


def test_an_explicit_key_wins_over_the_detected_one():
    a = [{"sku": "x", "n": 1}]
    b = [{"sku": "x", "n": 2}]
    assert _diff(a, b, key="sku").changed[0].field == "n"


def test_a_key_no_row_has_is_refused_rather_than_silently_ignored():
    from revenant import tables as _t
    import pytest
    with pytest.raises(_t.TableError) as exc:
        _t.diff([{"a": 1}], [{"a": 1}], key="nope")
    assert "nope" in str(exc.value)


def test_two_empty_tables_are_the_same_and_do_not_blow_up():
    out = _diff([], [])
    assert out.same == 0 and out.changed == () and out.only_in_a == ()


def test_one_empty_side_is_all_additions():
    out = _diff([], [{"id": 7}])
    assert out.only_in_b == (7,) and out.only_in_a == ()


def test_a_field_missing_from_a_row_is_not_a_value_difference_of_none():
    """Absent and null are different facts here too."""
    from revenant import tables as _t
    out = _diff([{"id": 1, "x": 1}], [{"id": 1}])
    assert [(c.field, c.a, c.b) for c in out.changed] == [("x", 1, _t.MISSING)]
    assert repr(_t.MISSING) == "(absent)"


def test_the_absent_marker_cannot_collide_with_a_real_value():
    """A sentinel that compares equal to real data turns a genuine difference
    into a match, which is the whole failure this command exists to avoid."""
    from revenant import tables as _t
    out = _diff([{"id": 1, "x": "(absent)"}], [{"id": 1}])
    assert len(out.changed) == 1 and out.same == 0
    assert out.changed[0].a == "(absent)" and out.changed[0].b is _t.MISSING


def test_normalising_names_that_collide_is_reported_not_silently_merged():
    from revenant import tables as _t
    out = _t.diff([{"costId": 1, "cost_id": 2}], [{"CostId": 1}],
                  normalize_names=True)
    assert any("costId" in n and "cost_id" in n for n in out.notes), out.notes


def test_ordinary_type_widening_is_not_called_incomparable():
    """`int` against `float` is two numbers that compare fine. Calling it a
    decode mismatch would suppress real differences and count them as "the
    same" -- this ticket's own trap, inverted into a confident identical."""
    out = _diff([{"id": i, "cost": i} for i in range(5)],
                [{"id": i, "cost": i + 0.5} for i in range(5)])
    assert out.incomparable == ()
    assert out.same == 0 and len(out.changed) == 5


def test_a_row_differing_only_in_an_incomparable_column_is_neither_same_nor_changed():
    out = _diff([{"id": i, "c": [1]} for i in range(9)],
                [{"id": i, "c": ["01"]} for i in range(9)])
    assert out.same == 0, "not one of them is known to be the same"
    assert out.undetermined == 9
    assert out.changed == ()


def test_a_table_of_bare_values_still_compares(tmp_path):
    """A `json-rows` table can be an array of scalars -- a shape `dispatch`
    really produces. Skipping them printed "3 rows" and then nothing at all."""
    from revenant import tables as _t
    out = _t.diff([1, 2, 3], [1, 2, 4])
    assert out.same == 2
    assert [(c.key, c.a, c.b) for c in out.changed] == [(2, 3, 4)]


def test_a_key_only_one_side_has_is_refused_rather_than_half_applied():
    """Otherwise one side keys on the field and the other falls back to row
    indexes, so a key gets matched against an index."""
    from revenant import tables as _t
    import pytest
    with pytest.raises(_t.TableError) as exc:
        _t.diff([{"sku": "x"}], [{"id": 1}], key="sku")
    assert "side B" in str(exc.value)


def test_an_unhashable_key_is_refused_with_a_message_not_a_traceback():
    from revenant import tables as _t
    import pytest
    with pytest.raises(_t.TableError) as exc:
        _t.diff([{"k": [1]}], [{"k": [1]}], key="k")
    assert "cannot identify a row" in str(exc.value)


def test_duplicate_keys_are_reported_rather_than_quietly_dropped():
    out = _diff([{"k": 1, "v": 1}, {"k": 1, "v": 2}], [{"k": 1, "v": 2}], key="k")
    assert any("share a 'k'" in n for n in out.notes), out.notes


def test_rows_missing_the_key_are_left_out_and_said_so():
    out = _diff([{"k": 1}, {"v": 9}], [{"k": 1}], key="k")
    assert any("no 'k'" in n for n in out.notes), out.notes


def test_rows_of_a_path_in_another_project_uses_that_projects_keys(tmp_path):
    """`read_any`'s rule is not `diff`'s alone. A note reaching for another
    title's table through the documented importable surface must not decode one
    game's bytes against another game's schema."""
    from revenant import config, tables as _t
    here, there = tmp_path / "here", tmp_path / "there"
    for project in (here, there):
        (project / "res" / "conf").mkdir(parents=True)
        (project / "revenant.toml").write_text("")
    _write(str(there / "res" / "conf" / "Item.json"), {"items": _rows(2)})
    monkey = os.environ.get("REVENANT_PROJECT")
    os.environ["REVENANT_PROJECT"] = str(here)
    config._PROJECT_CONFIG_CACHE.clear()
    try:
        assert _t.project_root_of(str(there / "res" / "conf" / "Item.json")) == str(there)
        assert len(_t.rows(str(there / "res" / "conf" / "Item.json"))) == 2
    finally:
        if monkey is None:
            os.environ.pop("REVENANT_PROJECT", None)
        else:
            os.environ["REVENANT_PROJECT"] = monkey
        config._PROJECT_CONFIG_CACHE.clear()


# ── table refs: how often a table is named, per corpus (#64) ────────────────

def test_each_corpus_is_counted_on_its_own_and_never_summed():
    """Four of nine titles have tables whose columns read perfectly and whose
    reference count is zero. One number across corpora would hide which corpus
    was even searchable."""
    from revenant import refs as _r
    text = [("src/A.cs", "var t = ItemConf.Load();\nItemConf.Rows();\n"),
            ("src/B.cs", "// nothing here\n")]
    out = _r.count_names(text, ("ItemConf",))
    assert out.total == 2 and out.files == 1


def test_both_the_table_name_and_the_row_class_are_searched():
    """Codegen usually names them differently, so searching one finds nothing
    and the answer looks like zero."""
    from revenant import refs as _r
    out = _r.count_names([("a.cs", "tbItem loaded\nItemConf row\n")],
                         ("tbItem", "ItemConf"))
    assert out.by_name == {"tbItem": 1, "ItemConf": 1}
    assert out.total == 2


def test_which_of_the_two_names_was_hit_is_reported():
    """`by_name` is the fact the two-name search rests on: a total of 4 that is
    all row class and no table name is a different situation from an even split,
    and counting them and never showing them makes the argument unfalsifiable."""
    from dataclasses import replace as _replace
    from revenant import refs as _r
    out = _r.count_names([("a.cs", "ItemConf x\nItemConf y\n")],
                         ("tbItem", "ItemConf"))
    printed = "\n".join(_r.refs_report(_replace(out, corpus="scaffold")))
    assert "by name: ItemConf 2, tbItem 0" in printed, (
        "the name that scored nothing is the half that says the count is all "
        "row class")


def test_a_name_inside_a_longer_word_is_not_a_reference():
    from revenant import refs as _r
    out = _r.count_names([("a.cs", "ItemConfExtra\nMyItemConf\n")], ("ItemConf",))
    assert out.total == 0


def test_a_site_that_names_many_tables_is_marked_as_one_that_names_many():
    """Hollywood Merge's `TableParser` reads override rows before parsing any
    table, so a hit there is not a reference to *this* table. Reported as a
    fact about the site -- not as a verdict about the table."""
    from revenant import refs as _r
    loader = "for (var n in new[]{" + ",".join(f'"T{i}"' for i in range(12)) + "})"
    out = _r.count_names([("Loader.cs", loader + "\nT3.Load();\n"),
                          ("Use.cs", "T3.Rows();\n")],
                         ("T3",), all_names={f"T{i}" for i in range(12)})
    assert out.total == 3, "twice in the loader, once at the use site"
    assert out.shared == 2, "the loader's hits are separated from the specific one"
    assert out.specific == 1


def test_a_table_named_only_by_a_general_handler_has_no_specific_reference():
    """The case the whole split exists for, and the one that had no test: every
    mention is inside the file that names every table, so `specific` is 0 while
    `total` is not -- and the two must not print the same."""
    from revenant import refs as _r
    from dataclasses import replace as _replace
    loader = "".join(f'Load("T{i}");\n' for i in range(12))
    out = _r.count_names([("Loader.cs", loader)], ("T3",),
                         all_names={f"T{i}" for i in range(12)})
    assert out.total == 1 and out.shared == 1 and out.specific == 0
    line = _r.refs_line(_replace(out, corpus="scaffold"))
    assert "0 where the file names this table alone" in line
    for verdict in ("dead", "unused", "orphan", "abandoned"):
        assert verdict not in line.lower(), verdict


def test_too_few_known_tables_to_place_a_hit_says_so_rather_than_going_quiet():
    """`_names_many` cannot fire below MANY_TABLES other names, so in a small
    project a loader hit and a specific hit print identically. Silence there
    reads as "we checked and it is specific", which is the one thing this
    command must never imply."""
    from revenant import refs as _r
    out = _r.count_names([("Loader.cs", "Load(\"T1\");\n")], ("T1",),
                         all_names={"T1", "T2"})
    assert out.shared == 0
    assert any("cannot be told from" in c for c in out.caveats), out.caveats
    assert any("cannot be told from" in line for line in _r.refs_report(out))


def test_a_corpus_that_is_not_there_says_so_rather_than_reporting_zero():
    """`lint`'s `no-index` rule, one layer down: reporting our own missing
    input as the author's zero is not an answer."""
    from revenant import refs as _r
    out = _r.Refs(corpus="lua", available=False, why="no extracted Lua tree")
    assert out.total == 0 and not out.available
    assert _r.refs_line(out) == "lua              cannot check -- no extracted Lua tree"


def _scaffold_of(root: str, names=("Item",), version: str = "1.0"):
    """The scaffold's `Refs`, which is the first of the project's C# roots."""
    from revenant import refs as _r
    return _r._csharp_refs(names, root, version, frozenset())[0]


def test_a_tree_that_exists_but_holds_nothing_is_not_a_zero_either(tmp_path):
    """`lint` keys `no-index` on whether anything loaded, not on whether a
    directory exists. An empty `src/<version>/` means seeding never ran, and
    "0 mentions" would report our own missing input as the author's answer."""
    from revenant import refs as _r
    (tmp_path / "src" / "1.0").mkdir(parents=True)
    (tmp_path / "lua" / "1.0").mkdir(parents=True)
    (tmp_path / "src" / "1.0" / "notes.txt").write_text("not a scaffold\n")
    out = _scaffold_of(str(tmp_path))
    assert not out.available and "holds no .cs files" in out.why
    assert "seed-src" in out.why, "and what to run about it"
    assert "0 mentions" not in _r.refs_line(out)


def test_a_tree_that_is_there_and_holds_files_is_counted(tmp_path):
    deep = tmp_path / "src" / "1.0" / "Game"
    deep.mkdir(parents=True)
    (deep / "Shop.cs").write_text("Item.Rows();\n")
    out = _scaffold_of(str(tmp_path))
    assert out.available and out.total == 1
    assert out.sites == ("Game/Shop.cs",)


def test_the_two_csharp_roots_are_two_corpora_and_are_never_summed(tmp_path):
    """`src/` holds stubs and `src-hotupdate/` holds the shipped bodies, so a
    mention in one is not the same finding as a mention in the other. Merging
    them would also hide which root was searchable at all -- the same reason
    the metadata and Lua counts stay apart."""
    from revenant import refs as _r
    for where, text in (("src", "class Item {}\n"),
                        ("src-hotupdate", "Item.Rows();\n")):
        deep = tmp_path / where / "1.0"
        deep.mkdir(parents=True)
        (deep / "A.cs").write_text(text)
    out = _r._csharp_refs(("Item",), str(tmp_path), "1.0", frozenset())
    assert [c.corpus for c in out] == ["scaffold", "hotupdate"]
    assert [c.total for c in out] == [1, 1]


def test_a_hot_update_root_that_is_not_there_names_no_command_to_run(tmp_path):
    """`seed-src` writes `src/`, so there is something to run about it missing.
    Nothing here produces `src-hotupdate/`, and naming a command for it would
    invent the convention CONTEXT.md's bar keeps out of revenant."""
    from revenant import refs as _r
    _scaffold, hotupdate = _r._csharp_refs(("Item",), str(tmp_path), "1.0",
                                           frozenset())
    assert not hotupdate.available
    assert "src-hotupdate/1.0/" in hotupdate.why
    assert "revenant " not in hotupdate.why, hotupdate.why


def test_one_composition_of_the_csharp_root_list_serves_every_caller():
    """The three callers that want the list -- `source_roots`, `check_source`
    and `table refs` -- each used to compose it, which is how `refs` came to
    read `src/` alone. Pinned by identity, because a copy that happens to agree
    today is the shape the drift came back in."""
    import inspect
    from revenant import csharp as _cs, refs as _r
    for where in (_cs.source_roots, _cs.check_source, _r._csharp_refs):
        body = inspect.getsource(where)
        assert "declared_roots" in body, where.__name__
        assert "SOURCE_ROOTS" not in body, f"{where.__name__} composes its own"


def test_the_csharp_roots_come_from_csharp_and_not_from_a_second_list(tmp_path):
    """`[csharp] roots` replaces the built-in pair. Restating the pair here is
    a second place for `table refs` to search where `cs-refs` does not."""
    from revenant import refs as _r
    (tmp_path / "revenant.toml").write_text('[csharp]\nroots = ["decomp"]\n')
    deep = tmp_path / "decomp" / "1.0"
    deep.mkdir(parents=True)
    (deep / "A.cs").write_text("Item.Rows();\n")
    from revenant import config
    config._PROJECT_CONFIG_CACHE.clear()
    out = _r._csharp_refs(("Item",), str(tmp_path), "1.0", frozenset())
    config._PROJECT_CONFIG_CACHE.clear()
    assert [c.corpus for c in out] == ["decomp"]
    assert out[0].total == 1


def test_the_file_cap_is_reported_rather_than_quietly_taken(tmp_path, monkeypatch):
    """The module's own rule: a query that covered less than it was asked to
    must not read like one that found nothing there."""
    from revenant import refs as _r
    monkeypatch.setattr(_r, "REF_MAX_FILES", 2)
    deep = tmp_path / "src" / "1.0"
    deep.mkdir(parents=True)
    for i in range(5):
        (deep / f"F{i}.cs").write_text("Item.Rows();\n")
    out = _r._csharp_refs(("Item",), str(tmp_path), "1.0", frozenset())[0]
    assert out.total == 2, "two files read, so two mentions"
    assert any("first 2 files" in c for c in out.caveats), out.caveats


def test_the_corpus_is_counted_one_file_at_a_time(tmp_path):
    """A real `src/<version>/` is tens of thousands of files. Counting reads a
    stream of (label, text), so nothing holds the corpus at once."""
    from revenant import refs as _r
    live = []

    def documents():
        for i in range(4):
            live.append(i)
            yield f"F{i}.cs", "Item.Rows();\n"
            assert len(live) == i + 1

    out = _r.count_names(documents(), ("Item",))
    assert out.total == 4


def test_one_metadata_blob_is_not_reported_as_two_files():
    """The literals and the type names are two sections of one artefact."""
    from revenant import refs as _r
    out = _r.Refs(corpus="metadata", total=3, files=2, unit="section",
                  by_name={"Item": 3})
    line = _r.refs_line(out)
    assert "in 2 sections" in line and "files" not in line


def test_a_single_mention_is_a_mention():
    from revenant import refs as _r
    line = _r.refs_line(_r.Refs(corpus="scaffold", total=1, files=1,
                                by_name={"Item": 1}))
    assert "1 mention in 1 file" in line


def test_the_site_list_says_how_many_it_did_not_show():
    from revenant import refs as _r
    out = _r.Refs(corpus="scaffold", total=9, files=9, by_name={"Item": 9},
                  sites=tuple(f"F{i}.cs" for i in range(9)))
    printed = "\n".join(_r.refs_report(out, limit=3))
    assert printed.count(".cs") == 3
    assert "... 6 more sites" in printed


def test_a_negative_limit_shows_nothing_rather_than_all_but_one():
    """`ranked[:-1]` is the bug this repo has now written down three times."""
    from revenant import refs as _r
    out = _r.Refs(corpus="scaffold", total=3, files=3, by_name={"Item": 3},
                  sites=("A.cs", "B.cs", "C.cs"))
    printed = "\n".join(_r.refs_report(out, limit=-1))
    assert "A.cs" not in printed
    assert "... 3 more sites" in printed


def test_a_real_zero_is_reported_as_a_zero_and_not_as_a_verdict():
    from revenant import refs as _r
    line = _r.refs_line(_r.Refs(corpus="scaffold", available=True))
    assert "0" in line
    for verdict in ("dead", "unused", "orphan", "never"):
        assert verdict not in line.lower(), verdict


def test_no_output_of_this_command_calls_a_table_dead():
    """The rule the ticket is built on: a zero is a fact, "this table is dead"
    is a judgement and belongs in a note."""
    from revenant import refs as _r
    lines = [_r.refs_line(_r.Refs(corpus="scaffold", available=True)),
             _r.refs_line(_r.Refs(corpus="metadata", available=True, total=3,
                                  files=2, shared=3, by_name={"X": 3})),
             _r.refs_line(_r.Refs(corpus="lua", available=False, why="not extracted")),
             _r.REFS_FOOTER]
    joined = " ".join(lines).lower()
    for verdict in ("dead", "unused", "orphan", "abandoned"):
        assert verdict not in joined, verdict


def test_the_footer_says_that_comments_and_strings_are_counted_too():
    """`// Item` and `var s = "Item"` are both mentions. Counting them is a
    choice, and an undisclosed choice is what makes a number look like more than
    it is."""
    from revenant import refs as _r
    assert "comments" in _r.REFS_FOOTER and "string literals" in _r.REFS_FOOTER


# ── the row class a schema declares (#64) ───────────────────────────────────

def test_a_flatbuffers_root_names_its_rows_not_itself():
    """`fb_roots` names the container -- `ItemDb` holds a vector of `Item`, and
    it is `Item` the codegen puts on the row type and the scaffold mentions.
    Searching for the root answers a question nobody asked."""
    from revenant import flatbuffers as _fb
    schema = _fb.Schema.from_dict({"classes": {
        "Game.CMS.ItemDb": {"fields": {0: {"name": "items", "fb_type": "offset",
                                           "cs_type": "Game.CMS.Item[]"}}},
        "Game.CMS.Item": {"fields": {}}}})
    assert _fb.row_class(schema, "Game.CMS.ItemDb") == "Game.CMS.Item"


def test_a_root_with_two_vectors_and_no_field_named_gives_no_row_class():
    """A guess would hand back a class the rows are not, and a wrong name counts
    as a zero exactly like a right name that is absent."""
    from revenant import flatbuffers as _fb
    schema = _fb.Schema.from_dict({"classes": {"Db": {"fields": {
        0: {"name": "items", "fb_type": "offset", "cs_type": "Item[]"},
        1: {"name": "recipes", "fb_type": "offset", "cs_type": "Recipe[]"}}}}})
    assert _fb.row_class(schema, "Db") == ""
    assert _fb.row_class(schema, "Db#recipes") == "Recipe"


def test_a_cms_container_wrapper_still_names_the_element():
    from revenant import flatbuffers as _fb
    schema = _fb.Schema.from_dict({"classes": {"Db": {"fields": {
        0: {"name": "items", "fb_type": "offset",
            "cs_type": "Game.CmsTable<Game.Item>"}}}}})
    assert _fb.row_class(schema, "Db", containers=("CmsTable",)) == "Game.Item"


def test_a_reader_with_no_schema_at_all_names_no_row_class():
    from revenant import flatbuffers as _fb
    assert _fb.row_class(None, "Db") == ""
    assert _fb.row_class(_fb.Schema.from_dict({"classes": {}}), "") == ""


# ── the managed-source query surface: cs-list / cs-get / cs-grep / cs-refs (#48) ──
#
# Four of the nine titles end with their business logic as C# text -- two
# HybridCLR, two IFix -- and the Lua side has had five commands for that shape
# since the start while the C# side had none. `search` / `lookup` / `xrefs` do
# not help: they read the IL2CPP indices, and a source tree is not in them.

def _cs_tree(tmp_path, scaffold=(), hotupdate=()):
    for where, files in (("src", scaffold), ("src-hotupdate", hotupdate)):
        for rel, text in files:
            path = tmp_path / where / "1.0" / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text)
    return str(tmp_path)


def test_both_source_roots_are_listed_and_each_says_which_it_came_from(tmp_path):
    """The scaffold and the recovered hot-update source are both "this game's
    C#" to a reader, so one set of commands covers both -- but which root a file
    came from decides whether a body is real, and merging them without saying
    would hide that."""
    from revenant import csharp
    root = _cs_tree(tmp_path, scaffold=[("Game/Shop.cs", "class Shop { }\n")],
                    hotupdate=[("Game/Deal.cs", "class Deal { }\n")])
    found = csharp.list_sources(version="1.0", root=root)
    assert [(f.root, f.name) for f in found] == [
        ("hotupdate", "Game/Deal"), ("scaffold", "Game/Shop")]


def test_a_name_in_both_roots_is_reported_as_both_and_not_silently_one(tmp_path):
    """A type in the scaffold *and* in the recovered hot-update source is the
    interesting case: one is the stub, the other the shipped body. Picking
    either without saying answers a question the reader did not ask."""
    from revenant import csharp
    root = _cs_tree(tmp_path,
                    scaffold=[("Game/Shop.cs", "class Shop { }  // stub\n")],
                    hotupdate=[("Game/Shop.cs", "class Shop { Buy(); }\n")])
    hits = csharp.find_source("Game/Shop", version="1.0", root=root)
    assert sorted(h.root for h in hits) == ["hotupdate", "scaffold"]
    one = csharp.find_source("Game/Shop", version="1.0", root=root,
                             which="hotupdate")
    assert len(one) == 1 and "Buy()" in csharp.read_source(one[0])


def test_a_full_label_picks_the_root_it_names(tmp_path):
    """`scaffold/Game/Shop` is what the listing printed, so it has to be a
    handle the other commands take back."""
    from revenant import csharp
    root = _cs_tree(tmp_path, scaffold=[("Game/Shop.cs", "stub\n")],
                    hotupdate=[("Game/Shop.cs", "body\n")])
    hits = csharp.find_source("hotupdate/Game/Shop", version="1.0", root=root)
    assert len(hits) == 1 and hits[0].root == "hotupdate"


def test_a_bare_type_name_resolves_to_the_file_that_holds_it(tmp_path):
    """Nobody types a path. Notes and `lookup` output name the type."""
    from revenant import csharp
    root = _cs_tree(tmp_path,
                    scaffold=[("Game/Deep/ShopController.cs", "class X {}\n")])
    hits = csharp.find_source("ShopController", version="1.0", root=root)
    assert len(hits) == 1 and hits[0].name == "Game/Deep/ShopController"


def test_grep_says_which_root_and_which_line(tmp_path):
    from revenant import csharp
    root = _cs_tree(tmp_path, scaffold=[("A.cs", "one\ncoinReward = 5;\n")],
                    hotupdate=[("B.cs", "coinReward = 9;\n")])
    out = csharp.cs_grep("coinReward", version="1.0", root=root)
    assert "hotupdate/B:1:" in out and "scaffold/A:2:" in out
    assert "2/2" in out, "shown out of total, the shape lua-grep uses"


def test_refs_separates_where_a_symbol_is_declared_from_where_it_is_used(tmp_path):
    """A `refs` that only string-matches cannot answer "where does this come
    from", which is the question it is asked."""
    from revenant import csharp
    root = _cs_tree(tmp_path, scaffold=[
        ("Game/ItemConf.cs", "public class ItemConf {\n  int id;\n}\n"),
        ("Game/Shop.cs", "var c = ItemConf.Rows();\n")])
    out = csharp.cs_refs("ItemConf", version="1.0", root=root)
    assert "declared" in out and "scaffold/Game/ItemConf:1" in out
    assert "scaffold/Game/Shop:1" in out


def test_a_symbol_inside_a_longer_identifier_is_not_a_reference(tmp_path):
    from revenant import csharp
    root = _cs_tree(tmp_path, scaffold=[
        ("A.cs", "ItemConfExtra x;\nvar y = MyItemConf;\n")])
    out = csharp.cs_refs("ItemConf", version="1.0", root=root)
    assert "no mention" in out.lower(), out


def test_refs_says_it_is_text_and_not_a_resolved_call_graph(tmp_path):
    """A comment, a string literal and an unrelated type in another namespace
    all match. Saying so is the difference between a count and a claim."""
    from revenant import csharp
    root = _cs_tree(tmp_path, scaffold=[("A.cs", "ItemConf x;\n")])
    out = csharp.cs_refs("ItemConf", version="1.0", root=root)
    assert "text" in out.lower() and "namespace" in out.lower()


def test_no_source_tree_at_all_says_what_to_run_rather_than_listing_nothing(tmp_path):
    """An empty list reads as "this game has no C#". The scaffold not being
    seeded is our missing input -- the same line `table refs` draws."""
    from revenant import csharp
    root = str(tmp_path)
    assert csharp.source_roots(version="1.0", root=root) == ()
    out = csharp.cs_grep("anything", version="1.0", root=root)
    assert "seed-src" in out and "src-hotupdate" in out


def test_a_root_that_exists_but_holds_no_cs_is_not_counted_as_a_root(tmp_path):
    """Same rule one level in: a directory is not a source tree."""
    from revenant import csharp
    (tmp_path / "src" / "1.0").mkdir(parents=True)
    (tmp_path / "src" / "1.0" / "readme.txt").write_text("hi\n")
    assert csharp.source_roots(version="1.0", root=str(tmp_path)) == ()


def test_a_field_or_parameter_of_this_type_is_a_use_not_a_declaration(tmp_path):
    """The split inverted on the first review. In a declaration the symbol is
    in the NAME position -- `private ItemConf _cfg;` declares `_cfg`, and
    filing it under `ItemConf`'s declarations makes every consumer of a widely
    used type look like its definition site."""
    from revenant import csharp
    root = _cs_tree(tmp_path, scaffold=[("A.cs",
        "private ItemConf _cfg;\n"
        "public void Use(ItemConf c) { }\n"
        "public ItemConf Config;\n"
        "var x = ItemConf.Rows();\n")])
    out = csharp.cs_refs("ItemConf", version="1.0", root=root)
    assert "declared (0)" in out, out
    assert "mentioned (4)" in out, out


def test_a_call_site_is_not_a_method_declaration(tmp_path):
    """`Reward(1, 2);` is what a call looks like in decompiled C#, and it has
    the same shape as a declaration minus the return type. Filing calls under
    "declared" empties the caller list, which is what `refs` is asked for."""
    from revenant import csharp
    root = _cs_tree(tmp_path, scaffold=[("A.cs",
        "Reward(1, 2);\n"
        "shop.Reward();\n"
        "return Reward(x);\n"
        "var r = new Reward();\n")])
    out = csharp.cs_refs("Reward", version="1.0", root=root)
    assert "declared (0)" in out, out
    assert "mentioned (4)" in out, out


def test_the_real_declaration_shapes_are_still_found(tmp_path):
    """The reverse test: tightening the rule must not empty the other column."""
    from revenant import csharp
    root = _cs_tree(tmp_path, scaffold=[
        ("T.cs", "public class Reward {\n}\n"),
        ("M.cs", "public int Reward(int a) { }\n"),
        ("F.cs", "private static List<int> Reward = null;\n"),
        ("P.cs", "public Reward[] Rewards { get; }\n")])
    out = csharp.cs_refs("Reward", version="1.0", root=root)
    assert "declared (3)" in out, out
    assert "scaffold/T:1" in out and "scaffold/M:1" in out and "scaffold/F:1" in out
    assert "mentioned (1)" in out, "the property is typed Reward, not named it"


def test_refs_counts_everything_it_found_even_when_it_shows_less(tmp_path):
    """A truncated count printed as a total reads as an answer. `cs_grep` had
    this right (`2/15`); `cs_refs` printed `declared (2)` of fifteen."""
    from revenant import csharp
    root = _cs_tree(tmp_path, scaffold=[
        (f"F{i}.cs", "public class Reward { }\nvar r = Reward.Get();\n")
        for i in range(6)])
    out = csharp.cs_refs("Reward", version="1.0", root=root, limit=2)
    assert "declared (2 of 6)" in out and "mentioned (2 of 6)" in out, out
    assert "12 line(s)" in out, "the header counts everything, not what fitted"


def test_a_zero_limit_shows_nothing_and_still_counts(tmp_path):
    from revenant import csharp
    root = _cs_tree(tmp_path, scaffold=[("A.cs", "public class Reward { }\n")])
    out = csharp.cs_refs("Reward", version="1.0", root=root, limit=0)
    assert "declared (0 of 1)" in out and "scaffold/A:1" not in out


def test_a_type_renamed_away_from_its_file_is_still_found(tmp_path):
    """Filename matching alone answers nothing for recovered source, where a
    file can hold several types or be named after none of them."""
    from revenant import csharp
    root = _cs_tree(tmp_path, scaffold=[
        ("Renamed.cs", "public class TotallyDifferent { }\n"),
        ("Pair.cs", "class Alpha { }\nclass Beta { }\n")])
    assert [f.name for f in csharp.find_source("TotallyDifferent",
                                               version="1.0", root=root)] == ["Renamed"]
    assert [f.name for f in csharp.find_source("Beta",
                                               version="1.0", root=root)] == ["Pair"]


def test_the_file_name_wins_over_a_declaration_elsewhere(tmp_path):
    """The scaffold is one file per type, so the cheap answer is the right one
    and the tree is only read when it misses."""
    from revenant import csharp
    root = _cs_tree(tmp_path, scaffold=[
        ("Shop.cs", "public class Shop { }\n"),
        ("Other.cs", "class Shop { }  // a partial elsewhere\n")])
    assert [f.name for f in csharp.find_source("Shop", version="1.0",
                                               root=root)] == ["Shop"]


def test_a_listing_that_showed_less_than_it_found_says_so(tmp_path):
    from revenant import csharp
    root = _cs_tree(tmp_path, scaffold=[(f"F{i}.cs", "x\n") for i in range(5)])
    found = csharp.list_sources(version="1.0", root=root)
    assert "5 C# file(s)" in csharp.list_report(found)
    assert "2 of 5 C# file(s)" in csharp.list_report(found, limit=2)


def test_a_source_root_name_that_does_not_exist_is_named_as_such(tmp_path):
    from revenant import csharp
    assert csharp.check_source("") == ""
    assert csharp.check_source("scaffold", root=str(tmp_path)) == ""
    complaint = csharp.check_source("scafold", root=str(tmp_path))
    assert "scafold" in complaint and "scaffold, hotupdate" in complaint


# ── a directory of bundles as a source, and gzip TextAssets (#48) ──────────
#
# Travel Town pulled 204 bundles off a device, Love & Pies fetched 1,259 (872
# MB) from a CDN, and each wrote its own "walk it, find UnityFS, export by
# type" script -- while `contrib.cache.export_bundle_dir` already did that,
# through the same `assets.export_blob` a packaged bundle goes through. What
# was missing was a command that took a directory.

def test_a_missing_download_directory_is_not_an_empty_one(tmp_path):
    """`os.walk` over a path that is not there returns the same nothing as a
    directory holding nothing, so a typo would be reported as the download's
    content -- the line this repo keeps drawing."""
    from revenant.contrib import cache
    import pytest
    with pytest.raises(FileNotFoundError):
        cache.export_bundle_dir(str(tmp_path / "nope"), str(tmp_path / "out"))


def test_a_directory_of_bundles_exports_through_the_packaged_path(tmp_path):
    """Story 2: the pulled bundles and the packaged ones go through one
    implementation, so the counts from the two sides are comparable."""
    from revenant.contrib import cache
    src = tmp_path / "pulled"
    (src / "nested").mkdir(parents=True)
    (src / "a.bundle").write_bytes(b"UnityFS-a")
    (src / "nested" / "b.bundle").write_bytes(b"HDR!" + b"UnityFS-b")
    (src / "__info").write_bytes(b"not a bundle")
    reports = cache.export_bundle_dir(
        str(src), str(tmp_path / "res"),
        load=_loader({b"UnityFS-a": _FakeEnv([_FakeObject(
                          "TextAsset", path_id=7, m_Name="Level", m_Script=b"rows")]),
                      b"UnityFS-b": _FakeEnv([_FakeObject(
                          "TextAsset", path_id=8, m_Name="Deep", m_Script=b"x")])}))
    assert (tmp_path / "res" / "root" / "a.bundle" / "TextAsset"
            / "Level.bytes").read_bytes() == b"rows"
    loaded = [r for r in reports if r.exported]
    assert {r.name for r in loaded} == {"a.bundle", "b.bundle"}
    assert [r.name for r in reports if not r.exported] == ["__info"], (
        "a non-bundle is counted, not hidden")


def test_a_gzip_textasset_is_written_both_ways(tmp_path):
    """Seven of Love & Pies' 26 CMS libraries are gzipped JSON, and after
    export they were a blob nothing identified. The raw bytes stay exactly as
    they were -- notes cite their size and md5 -- and the unpacked form lands
    beside them under a name that says what it is."""
    import gzip
    from revenant import assets
    payload = b'{"m_variants": []}'
    env = _FakeEnv([_FakeObject("TextAsset", path_id=3, m_Name="Experiments",
                                m_Script=gzip.compress(payload))])
    reports = assets.extract_ggm(
        str(tmp_path),
        sources=[("base.apk!assets/bin/Data/data.unity3d", b"UnityFS-g")],
        load=_loader({b"UnityFS-g": env}))
    out = tmp_path / assets.GGM_GROUP / "data.unity3d" / "TextAsset"
    assert (out / "Experiments.bytes").read_bytes() == gzip.compress(payload)
    assert (out / "Experiments.bytes.gunzip").read_bytes() == payload
    assert reports[0].exported["TextAsset"] == 1
    assert reports[0].unpacked["TextAsset"] == 1
    assert "gunzip" not in json.dumps(dict(reports[0].exported)), (
        "`exported` keys are Unity type names and go into the manifest as such")


def test_a_textasset_that_is_not_gzip_is_not_unpacked(tmp_path):
    """The reverse test: the tempting implementation tries every TextAsset and
    swallows the failure, which turns a decision into a coincidence."""
    from revenant import assets
    env = _FakeEnv([_FakeObject("TextAsset", path_id=4, m_Name="Plain", m_Script=b"rows")])
    reports = assets.extract_ggm(
        str(tmp_path), sources=[("base.apk!assets/bin/Data/data.unity3d", b"UnityFS-p")],
        load=_loader({b"UnityFS-p": env}))
    out = tmp_path / assets.GGM_GROUP / "data.unity3d" / "TextAsset"
    assert [p.name for p in sorted(out.iterdir())] == ["Plain.bytes"]
    assert reports[0].errors == []


def test_a_truncated_gzip_keeps_the_raw_bytes_and_reports_the_failure(tmp_path):
    """A blob whose magic says gzip and whose body will not inflate is a fact
    worth printing. Silently dropping it loses the only signal that this file
    is not what its header claims -- and the raw bytes must survive either way."""
    import gzip
    from revenant import assets
    broken = gzip.compress(b"payload")[:12]
    env = _FakeEnv([_FakeObject("TextAsset", path_id=5, m_Name="Cut", m_Script=broken)])
    reports = assets.extract_ggm(
        str(tmp_path), sources=[("base.apk!assets/bin/Data/data.unity3d", b"UnityFS-t")],
        load=_loader({b"UnityFS-t": env}))
    out = tmp_path / assets.GGM_GROUP / "data.unity3d" / "TextAsset"
    assert (out / "Cut.bytes").read_bytes() == broken
    assert not (out / "Cut.bytes.gunzip").exists()
    assert any("Cut" in e and "gzip" in e for e in reports[0].errors), reports[0].errors
    assert reports[0].exported["TextAsset"] == 1, "the raw export still counts"


def test_a_bundle_that_loads_and_exports_nothing_countable_still_loaded(tmp_path):
    """A bundle holding only AnimationClips writes its names file and
    increments nothing, so a caller partitioning on `exported` calls it "not a
    bundle" -- our own gap reported as the file's content."""
    from revenant.contrib import cache
    src = tmp_path / "pulled"
    src.mkdir()
    (src / "anim.bundle").write_bytes(b"UnityFS-a")
    env = _FakeEnv([_FakeObject("AnimationClip", path_id=1, m_Name="Idle")])
    reports = cache.export_bundle_dir(str(src), str(tmp_path / "res"),
                                      load=_loader({b"UnityFS-a": env}))
    assert reports[0].loaded and not reports[0].exported
    assert (tmp_path / "res" / "root" / "anim.bundle" / "AnimationClip.txt").exists()


def test_one_unreadable_file_does_not_lose_the_batch(tmp_path):
    """The caller is pointing at 1,259 files pulled off a CDN. The function's
    own docstring promises an unreadable entry is recorded, not raised."""
    from revenant.contrib import cache
    src = tmp_path / "pulled"
    src.mkdir()
    bad = src / "locked"
    bad.write_bytes(b"UnityFS-a")
    (src / "good.bundle").write_bytes(b"UnityFS-a")
    bad.chmod(0o000)
    try:
        env = _FakeEnv([_FakeObject("TextAsset", path_id=1, m_Name="T", m_Script=b"x")])
        reports = cache.export_bundle_dir(str(src), str(tmp_path / "res"),
                                          load=_loader({b"UnityFS-a": env}))
    finally:
        bad.chmod(0o644)
    assert {r.name for r in reports} == {"locked", "good.bundle"}
    assert any(r.loaded for r in reports), "the readable one still got through"
    locked = next(r for r in reports if r.name == "locked")
    assert not locked.loaded and any("locked" in e for e in locked.errors)


def test_a_bundle_in_a_dot_directory_is_not_dropped(tmp_path):
    """A dot-directory filter was added here and asked for by nobody. Unity's
    own caches live under dot-directories, and a dot-*file* at the root was
    counted all along -- the two were inconsistent and neither was printed."""
    from revenant.contrib import cache
    src = tmp_path / "pulled"
    (src / ".cache").mkdir(parents=True)
    (src / ".cache" / "hidden.bundle").write_bytes(b"UnityFS-a")
    env = _FakeEnv([_FakeObject("TextAsset", path_id=1, m_Name="T", m_Script=b"x")])
    reports = cache.export_bundle_dir(str(src), str(tmp_path / "res"),
                                      load=_loader({b"UnityFS-a": env}))
    assert [r.name for r in reports] == ["hidden.bundle"]
    assert reports[0].loaded


# ── lua-decompile <dir>: Lua already on disk (#48 gap nine) ─────────────────
#
# `lua-extract` is a chain -- pull from the package, decrypt, unpack,
# decompile -- and its entry is welded to the package: `extract_scripts()`
# opens the APK. One title's 3,608 `.lua` came off a CDN and sit in a
# directory, so that last link had to be run by hand. Same disease as
# `extract-scenes` only opening archives: the capability is here and the entry
# knows one kind of input.

def _fake_decompile(mapping):
    """Stand-in for `lua.decompile`: chunk -> (ok, text)."""
    def decompile(chunk, timeout=60):
        for head, answer in mapping.items():
            if chunk.startswith(head):
                return answer
        return False, "unknown chunk"
    return decompile


def test_a_tree_of_bytecode_is_decompiled_in_place(tmp_path, monkeypatch):
    from revenant import lua
    src = tmp_path / "pulled"
    (src / "Board").mkdir(parents=True)
    (src / "a.lua").write_bytes(b"\x1bLua53-a")
    (src / "Board" / "b.lua").write_bytes(b"\x1bLJ\x02-b")
    monkeypatch.setattr(lua, "decompile", _fake_decompile(
        {b"\x1bLua": (True, "return 1\n"), b"\x1bLJ": (True, "return 2\n")}))
    rep = lua.decompile_tree(str(src), out_dir=str(tmp_path / "out"))
    assert (tmp_path / "out" / "a.lua").read_text().endswith("return 1\n")
    assert (tmp_path / "out" / "Board" / "b.lua").read_text().endswith("return 2\n")
    assert rep.chunks == 2 and rep.decompiled == 2


def test_the_family_is_read_off_the_magic_not_the_extension(tmp_path, monkeypatch):
    """Story 22: LuaJIT goes to ljd2 and stock Lua to unluac without the reader
    having to sort them. A CDN hands back whatever names it likes."""
    from revenant import lua
    src = tmp_path / "pulled"
    src.mkdir()
    (src / "no-extension").write_bytes(b"\x1bLJ\x02-x")
    (src / "stock.bin").write_bytes(b"\x1bLua53-y")
    seen = []

    def decompile(chunk, timeout=60):
        seen.append(chunk[:3])
        return True, "ok\n"

    monkeypatch.setattr(lua, "decompile", decompile)
    rep = lua.decompile_tree(str(src), out_dir=str(tmp_path / "out"))
    assert sorted(seen) == [b"\x1bLJ", b"\x1bLu"]
    assert rep.chunks == 2


def test_a_file_that_is_not_a_lua_chunk_is_counted_not_hidden(tmp_path, monkeypatch):
    """A pulled directory holds catalogues and hashes too. Skipping them
    quietly leaves no way to tell "no Lua here" from "I only looked at some"."""
    from revenant import lua
    src = tmp_path / "pulled"
    src.mkdir()
    (src / "chunk.lua").write_bytes(b"\x1bLua53-a")
    (src / "catalog.json").write_text('{"x": 1}')
    monkeypatch.setattr(lua, "decompile", _fake_decompile({b"\x1bLua": (True, "ok\n")}))
    rep = lua.decompile_tree(str(src), out_dir=str(tmp_path / "out"))
    assert rep.chunks == 1 and rep.decompiled == 1
    assert rep.other == 1
    assert not (tmp_path / "out" / "catalog.json").exists()


def test_already_decompiled_source_is_copied_through_not_decompiled(tmp_path, monkeypatch):
    """A tree can hold plain Lua source already. Feeding it to a decompiler
    would fail on every file and read as "this tree is broken" -- and merely
    counting it leaves exactly the readable half of a pulled tree invisible to
    `lua-grep`, which is the half answer the default output directory exists
    to avoid."""
    from revenant import lua
    src = tmp_path / "pulled"
    (src / "deep").mkdir(parents=True)
    (src / "deep" / "plain.lua").write_text("Config = {}\nprint('hi')\n")
    monkeypatch.setattr(lua, "decompile", _fake_decompile({}))
    rep = lua.decompile_tree(str(src), out_dir=str(tmp_path / "out"))
    assert rep.source_copied == 1 and rep.chunks == 0 and rep.other == 0
    assert (tmp_path / "out" / "deep" / "plain.lua").read_text() == \
        "Config = {}\nprint('hi')\n"


def test_a_dot_in_a_file_name_does_not_split_it_into_directories(tmp_path, monkeypatch):
    """The first cut routed the relative path through a dotted module name and
    back, so `a/b.lua` and `a.b.lua` landed on one file: the report counted two
    and one survived. CDN trees are full of `main.9f2a.lua`."""
    from revenant import lua
    src = tmp_path / "pulled"
    (src / "a").mkdir(parents=True)
    (src / "a" / "b.lua").write_bytes(b"\x1bLua53-one")
    (src / "a.b.lua").write_bytes(b"\x1bLua53-two")
    monkeypatch.setattr(lua, "decompile",
                        lambda chunk, timeout=60: (True, chunk.decode("latin-1")))
    rep = lua.decompile_tree(str(src), out_dir=str(tmp_path / "out"))
    assert rep.chunks == 2 and rep.decompiled == 2 and rep.collisions == ()
    assert "one" in (tmp_path / "out" / "a" / "b.lua").read_text()
    assert "two" in (tmp_path / "out" / "a.b.lua").read_text()


def test_two_inputs_landing_on_one_path_are_reported_not_overwritten(tmp_path, monkeypatch):
    """`x.lua` and `x.luac` both want `x.lua`. A count that includes both is a
    number nothing on disk backs -- the same failure the bundle export had."""
    from revenant import lua
    src = tmp_path / "pulled"
    src.mkdir()
    (src / "x.lua").write_bytes(b"\x1bLua53-one")
    (src / "x.luac").write_bytes(b"\x1bLua53-two")
    monkeypatch.setattr(lua, "decompile",
                        lambda chunk, timeout=60: (True, chunk.decode("latin-1")))
    rep = lua.decompile_tree(str(src), out_dir=str(tmp_path / "out"))
    assert rep.chunks == 1, "only the one that got the destination is counted"
    assert len(rep.collisions) == 1 and "x.luac" in rep.collisions[0]
    assert len(list((tmp_path / "out").rglob("*.lua"))) == 1


def test_an_unreadable_file_is_our_gap_not_the_file_s_content(tmp_path, monkeypatch):
    from revenant import lua
    src = tmp_path / "pulled"
    src.mkdir()
    bad = src / "locked"
    bad.write_bytes(b"\x1bLua53-x")
    bad.chmod(0o000)
    try:
        rep = lua.decompile_tree(str(src), out_dir=str(tmp_path / "out"))
    finally:
        bad.chmod(0o644)
    assert rep.unreadable == 1 and rep.other == 0 and rep.chunks == 0
    assert any("locked" in why for why in rep.why)


def test_the_index_is_built_for_the_tree_that_was_written(tmp_path, monkeypatch):
    """`--out DIR` wrote into DIR and indexed `lua/<version>/` instead, which
    left DIR unsearchable and stamped an empty index into a directory nothing
    had written -- that is how a run artifact reached a commit."""
    from revenant import lua
    src = tmp_path / "pulled"
    src.mkdir()
    (src / "a.lua").write_bytes(b"\x1bLua53-a")
    monkeypatch.setattr(lua, "decompile",
                        lambda chunk, timeout=60: (True, 'require("Other")\n'))
    out = tmp_path / "elsewhere"
    lua.decompile_tree(str(src), out_dir=str(out))
    index = json.loads((out / ".lua_index.json").read_text())
    assert index["module_count"] == 1
    assert "a" in index["modules"]


def test_a_chunk_that_will_not_decompile_keeps_its_strings(tmp_path, monkeypatch):
    """The same fallback `lua-extract` writes: embedded constants beat an empty
    file, and the file says which it is."""
    from revenant import lua
    src = tmp_path / "pulled"
    src.mkdir()
    (src / "bad.lua").write_bytes(b"\x1bLJ\x02" + b"SomeIdentifier\x00")
    monkeypatch.setattr(lua, "decompile", _fake_decompile(
        {b"\x1bLJ": (False, "$REVENANT_LJD2 is not set")}))
    monkeypatch.setattr(lua, "have_decompiler", lambda: True)
    rep = lua.decompile_tree(str(src), out_dir=str(tmp_path / "out"))
    written = (tmp_path / "out" / "bad.lua").read_text()
    assert "NOT decompiled" in written and "SomeIdentifier" in written
    assert rep.decompiled == 0 and rep.bytecode_only == 1
    assert any("REVENANT_LJD2" in why for why in rep.why), rep.why


def test_no_decompiler_at_all_is_asked_once_not_per_file(tmp_path, monkeypatch):
    """Without either decompiler, 3,608 files meant 3,608 doomed JVM launches
    for an answer that does not change."""
    from revenant import lua
    src = tmp_path / "pulled"
    src.mkdir()
    for i in range(3):
        (src / f"f{i}.lua").write_bytes(b"\x1bLua53-x")
    monkeypatch.setattr(lua, "have_decompiler", lambda: False)
    monkeypatch.setattr(lua, "ljd2_binary", lambda: "")
    monkeypatch.setattr(lua, "decompile", _fake_decompile({}))
    rep = lua.decompile_tree(str(src), out_dir=str(tmp_path / "out"))
    assert rep.bytecode_only == 3 and rep.decompiled == 0
    assert any("no decompiler available" in why for why in rep.why), rep.why


def test_a_missing_source_directory_is_not_an_empty_one(tmp_path):
    from revenant import lua
    import pytest
    with pytest.raises(FileNotFoundError):
        lua.decompile_tree(str(tmp_path / "nope"), out_dir=str(tmp_path / "out"))


# ── the A/B experiment roster (#48 gap seven, second half) ──────────────────
#
# Everything about an experiment ships in the package -- which experiments
# exist, which items each one touches, which fields it changes, and both
# values. Only "which variant is this player in" is server-side. So the roster
# is readable, and reading it was a project script.

def test_the_roster_names_every_item_and_field_an_experiment_touches():
    from revenant.contrib import experiments
    doc = {"m_variants": [
        {"m_itemGuid": "aaaa", "m_jsonPatch": '{"cost": [10, 8]}'},
        {"m_itemGuid": "bbbb", "m_jsonPatch": '{"reward": {"coins": [100, 150]}}'},
    ]}
    roster = experiments.read_roster(doc)
    assert [(c.item_guid, c.field, c.control, c.test) for c in roster.changes] == [
        ("aaaa", "cost", 10, 8),
        ("bbbb", "reward.coins", 100, 150)]
    assert roster.items == ("aaaa", "bbbb")


def test_the_patch_may_arrive_already_decoded():
    """CMS ships it as a JSON string; an exporter that already parsed it hands
    back the object. Refusing one of the two shapes reads as an empty roster."""
    from revenant.contrib import experiments
    doc = {"m_variants": [{"m_itemGuid": "a", "m_jsonPatch": {"cost": [1, 2]}}]}
    assert len(experiments.read_roster(doc).changes) == 1


def test_variants_are_found_wherever_they_are_nested():
    from revenant.contrib import experiments
    doc = {"root": {"config": {"m_variants": [
        {"m_itemGuid": "a", "m_jsonPatch": '{"x": [1, 2]}'}]}}}
    assert len(experiments.read_roster(doc).changes) == 1


def test_a_leaf_that_is_not_a_control_test_pair_is_reported_not_dropped():
    """The pair shape is what makes a patch readable as an experiment. A leaf
    that is not one is something this parser does not understand, and dropping
    it silently would report a partial roster as a whole one."""
    from revenant.contrib import experiments
    doc = {"m_variants": [{"m_itemGuid": "a", "m_jsonPatch":
                           '{"cost": [1, 2], "note": "hand-tuned", "tiers": [1, 2, 3]}'}]}
    roster = experiments.read_roster(doc)
    assert [c.field for c in roster.changes] == ["cost"]
    assert sorted(u.field for u in roster.unpaired) == ["note", "tiers"]


def test_a_patch_that_will_not_parse_is_reported_against_its_item():
    from revenant.contrib import experiments
    doc = {"m_variants": [{"m_itemGuid": "a", "m_jsonPatch": "{not json"},
                          {"m_itemGuid": "b", "m_jsonPatch": '{"x": [1, 2]}'}]}
    roster = experiments.read_roster(doc)
    assert len(roster.changes) == 1, "the readable variant still comes through"
    assert any("a" in note for note in roster.notes)


def test_a_document_with_no_variants_says_so_rather_than_returning_empty():
    """"This CMS blob holds no experiments" and "this parser did not recognise
    it" are different facts."""
    from revenant.contrib import experiments
    roster = experiments.read_roster({"something": "else"})
    assert roster.changes == () and roster.items == ()
    assert any("m_variants" in note for note in roster.notes)


def test_the_roster_never_says_what_a_guid_means():
    """Which guid is which item is a game fact and stays in the project. The
    parser returns the guid; naming it is the reader's."""
    from revenant.contrib import experiments
    doc = {"m_variants": [{"m_itemGuid": "aaaa", "m_jsonPatch": '{"cost": [1, 2]}'}]}
    text = experiments.format_roster(experiments.read_roster(doc))
    assert "aaaa" in text
    for verdict in ("buff", "nerf", "better", "worse", "improve"):
        assert verdict not in text.lower(), verdict


def test_a_list_of_objects_is_not_one_change_with_two_arms():
    """`{"rewards": [{"coins": [1,2]}, {"gems": [3,4]}]}` came back as a single
    change whose control and test were whole objects -- an experiment arm
    nobody wrote. A pair is two *scalars*; anything else is structure this
    parser does not understand and says so."""
    from revenant.contrib import experiments
    doc = {"m_variants": [{"m_itemGuid": "a", "m_jsonPatch":
                           '{"rewards": [{"coins": [1,2]}, {"gems": [3,4]}]}'}]}
    roster = experiments.read_roster(doc)
    assert roster.changes == ()
    assert [u.field for u in roster.unpaired] == ["rewards"]


def test_a_patch_that_is_a_list_is_reported_rather_than_left_nameless():
    """A list has no field names in it, so its entries could only come back
    nameless -- `a  : [1, 2] -> [3, 4]`, which is what it used to print."""
    from revenant.contrib import experiments
    doc = {"m_variants": [{"m_itemGuid": "a", "m_jsonPatch": "[[1,2],[3,4]]"}]}
    roster = experiments.read_roster(doc)
    assert roster.changes == () and roster.unpaired == ()
    assert any("no way to name" in note for note in roster.notes)


def test_two_variant_lists_do_not_merge_into_one_roster():
    """Story 19 wants "which experiments"; flattening every list into one
    bucket reports two rosters as a single one twice the size."""
    from revenant.contrib import experiments
    doc = {"live": {"m_variants": [{"m_itemGuid": "a", "m_jsonPatch": '{"x":[1,2]}'}]},
           "staged": {"m_variants": [{"m_itemGuid": "b", "m_jsonPatch": '{"y":[3,4]}'}]}}
    roster = experiments.read_roster(doc)
    assert sorted(roster.groups) == ["live.m_variants", "staged.m_variants"]
    assert {c.group for c in roster.changes} == set(roster.groups)
    assert "in 2 list(s)" in experiments.format_roster(roster)


def test_a_variant_with_no_item_guid_is_reported_not_blanked():
    """It printed `across 0 item(s)` with a blank guid column, which reads as a
    name we chose not to print rather than one that was not there."""
    from revenant.contrib import experiments
    doc = {"m_variants": [{"m_jsonPatch": '{"x": [1, 2]}'}]}
    roster = experiments.read_roster(doc)
    assert roster.changes[0].item_guid == "(no guid)"
    assert any("no m_itemGuid" in note for note in roster.notes)


def test_the_three_field_names_are_the_callers():
    """Concrete names in one middleware's schema are a game fact by ADR-0004,
    so they arrive as an argument -- the same way `contrib.fetch` takes its
    HTTP call. The defaults are a convenience, not knowledge claimed here."""
    from revenant.contrib import experiments
    doc = {"variants": [{"guid": "a", "patch": '{"cost": [1, 2]}'}]}
    keys = experiments.RosterKeys(variants="variants", item="guid", patch="patch")
    roster = experiments.read_roster(doc, keys)
    assert [(c.item_guid, c.field) for c in roster.changes] == [("a", "cost")]
    assert experiments.read_roster(doc).changes == (), "the defaults find nothing"


def test_the_header_names_every_bucket_not_only_the_one_that_worked():
    from revenant.contrib import experiments
    doc = {"m_variants": [{"m_itemGuid": "a", "m_jsonPatch":
                           '{"ok": [1, 2], "odd": "text"}'},
                          {"m_itemGuid": "b", "m_jsonPatch": "{not json"}]}
    head = experiments.format_roster(experiments.read_roster(doc)).splitlines()[0]
    assert "1 field change(s)" in head
    assert "not control/test pairs" in head and "could not be read" in head


def test_a_document_nested_past_the_limit_stops_instead_of_exhausting_the_stack():
    from revenant.contrib import experiments
    doc = {"m_variants": [{"m_itemGuid": "a", "m_jsonPatch": '{"x": [1, 2]}'}]}
    for _ in range(experiments.MAX_DEPTH + 50):
        doc = {"wrap": doc}
    roster = experiments.read_roster(doc)          # must not raise
    assert any("m_variants" in note for note in roster.notes)


# ── the block-decryption driver (#48 gap three) ────────────────────────────
#
# `SegmentedImage` maps the image and `find_dispatcher` locates the VM; what
# neither does is run the protector's own wrapper over a blob, block by block,
# and collect the output. Two titles each have a copy of that loop, and both
# docstrings say the addresses differ and the rest of the routine does not.
#
# The emulator is injected -- the same handle `contrib.fetch` gives its HTTP
# call. Unicorn satisfies the four methods used, and revenant does not import
# it.

class _FakeEmulator:
    """Four methods, the ones a Unicorn instance already has."""

    def __init__(self, transform=None, fail_on=()):
        self.mem = {}
        self.regs = {}
        self.runs = []
        self._transform = transform or (lambda b: bytes(x ^ 0xFF for x in b))
        self._fail_on = set(fail_on)

    def mem_write(self, addr, data):
        for i, b in enumerate(bytes(data)):
            self.mem[addr + i] = b

    def mem_read(self, addr, size):
        return bytes(self.mem.get(addr + i, 0) for i in range(size))

    def reg_write(self, reg, value):
        self.regs[reg] = value

    def emu_start(self, begin, until, timeout=0, count=0):
        self.runs.append((begin, until, dict(self.regs)))
        if len(self.runs) - 1 in self._fail_on:
            raise RuntimeError("emulation aborted")
        at, size = self.regs["x0"], self.regs["x1"]
        self.mem_write(at, self._transform(self.mem_read(at, size)))


def _wrapper(**kw):
    from revenant.contrib.decrypt import Wrapper
    base = dict(entry=0x1000, ret=0x1004, body=0x40000, argv=("x0", "x1"))
    base.update(kw)
    return Wrapper(**base)


def test_the_blob_is_driven_through_the_wrapper_block_by_block():
    from revenant.contrib.decrypt import decrypt_blocks
    emu = _FakeEmulator()
    blob = bytes(range(32))
    out = decrypt_blocks(emu, blob, _wrapper(), block_size=16)
    assert out.plaintext == bytes(b ^ 0xFF for b in blob)
    assert out.blocks == 2 and out.failed == ()
    assert [run[:2] for run in emu.runs] == [(0x1000, 0x1004)] * 2


def test_each_block_is_written_where_the_wrapper_expects_it():
    from revenant.contrib.decrypt import decrypt_blocks
    emu = _FakeEmulator()
    decrypt_blocks(emu, b"abcd", _wrapper(body=0x99000), block_size=2)
    assert all(run[2]["x0"] == 0x99000 for run in emu.runs)
    assert [run[2]["x1"] for run in emu.runs] == [2, 2]


def test_a_short_final_block_is_passed_at_its_real_length():
    """Padding it to the block size would hand the wrapper bytes the file does
    not have, and the extra plaintext would look like content."""
    from revenant.contrib.decrypt import decrypt_blocks
    emu = _FakeEmulator()
    out = decrypt_blocks(emu, b"abcde", _wrapper(), block_size=2)
    assert [run[2]["x1"] for run in emu.runs] == [2, 2, 1]
    assert len(out.plaintext) == 5


def test_the_fixed_arguments_come_before_the_block():
    """`(program, key, body, length)` is the layout one build uses; which
    registers and which fixed values are per-build, so both are passed in."""
    from revenant.contrib.decrypt import decrypt_blocks
    emu = _FakeEmulator()
    emu.regs["x2"] = emu.regs["x3"] = 0

    class _Emu(_FakeEmulator):
        def emu_start(self, begin, until, timeout=0, count=0):
            self.runs.append((begin, until, dict(self.regs)))
            at, size = self.regs["x2"], self.regs["x3"]
            self.mem_write(at, bytes(x ^ 0xFF for x in self.mem_read(at, size)))

    emu = _Emu()
    out = decrypt_blocks(emu, b"ab", _wrapper(argv=("x0", "x1", "x2", "x3")),
                         block_size=2, fixed=(0x7000, 0x8000))
    assert emu.runs[0][2]["x0"] == 0x7000 and emu.runs[0][2]["x1"] == 0x8000
    assert out.plaintext == b"\x9e\x9d"


def test_a_block_that_aborts_is_reported_and_the_rest_still_run():
    """A 57 MB blob is thousands of blocks. Dying on one loses every block
    after it, and the reader cannot tell a broken build from a broken block."""
    from revenant.contrib.decrypt import decrypt_blocks
    emu = _FakeEmulator(fail_on=(1,))
    out = decrypt_blocks(emu, b"aabbcc", _wrapper(), block_size=2)
    assert out.blocks == 3 and out.failed == (1,)
    assert len(out.plaintext) == 6, "the failed block's bytes are still placed"
    assert out.plaintext[2:4] == b"bb", "left as ciphertext, not zeroed"
    assert any("block 1" in note for note in out.notes)


def test_the_failed_bytes_are_left_as_they_were_not_as_zeros():
    """Zeroing a failed block makes a hole that reads as data. The ciphertext
    is what we actually have for it, and the count says how many."""
    from revenant.contrib.decrypt import decrypt_blocks
    emu = _FakeEmulator(fail_on=(0,))
    out = decrypt_blocks(emu, b"xy", _wrapper(), block_size=2)
    assert out.plaintext == b"xy" and out.failed == (0,)


def test_a_block_size_that_cannot_work_is_refused_up_front():
    from revenant.contrib.decrypt import decrypt_blocks
    import pytest
    for bad in (0, -16):
        with pytest.raises(ValueError):
            decrypt_blocks(_FakeEmulator(), b"ab", _wrapper(), block_size=bad)


def test_too_few_registers_for_the_arguments_is_refused_up_front():
    """`argv` shorter than fixed + (address, length) would silently drop an
    argument and the wrapper would read whatever was in the register."""
    from revenant.contrib.decrypt import decrypt_blocks
    import pytest
    with pytest.raises(ValueError):
        decrypt_blocks(_FakeEmulator(), b"ab", _wrapper(argv=("x0",)),
                       block_size=2, fixed=(0x7000,))


def test_nothing_here_imports_unicorn():
    """Story 7: a project without Unicorn installed must not be affected."""
    import pathlib
    from revenant.contrib import decrypt
    root = pathlib.Path(decrypt.__file__).parent
    for path in root.glob("*.py"):
        assert "import unicorn" not in path.read_text(), path.name


def test_the_timeout_reaches_the_emulator():
    """A wrong entry address runs forever otherwise, and a hang on block 1 of
    several thousand is the least readable failure available."""
    from revenant.contrib.decrypt import decrypt_blocks
    seen = []

    class _Emu(_FakeEmulator):
        def emu_start(self, begin, until, timeout=0, count=0):
            seen.append(timeout)
            super().emu_start(begin, until)

    decrypt_blocks(_Emu(), b"ab", _wrapper(), block_size=2, timeout=5_000_000)
    assert seen == [5_000_000]


def test_an_emulator_written_to_the_documented_signature_works():
    """The docstring said `emu_start(begin, until)` and the code passed a
    timeout, so an emulator written to the contract failed every block -- and
    `except Exception` filed our own contract error as the data's problem."""
    from revenant.contrib.decrypt import decrypt_blocks

    class _ByTheBook:
        def __init__(self):
            self.mem, self.regs = {}, {}

        def mem_write(self, address, data):
            for i, b in enumerate(bytes(data)):
                self.mem[address + i] = b

        def mem_read(self, address, size):
            return bytes(self.mem.get(address + i, 0) for i in range(size))

        def reg_write(self, register, value):
            self.regs[register] = value

        def emu_start(self, begin, until, timeout):
            at, size = self.regs["x0"], self.regs["x1"]
            self.mem_write(at, bytes(b ^ 0xFF for b in self.mem_read(at, size)))

    out = decrypt_blocks(_ByTheBook(), b"ab", _wrapper(), block_size=2)
    assert out.plaintext == bytes(b ^ 0xFF for b in b"ab") and out.failed == ()


def test_an_emulator_missing_a_method_is_refused_before_any_block_runs():
    from revenant.contrib.decrypt import EmulatorContract, decrypt_blocks
    import pytest

    class _Partial(_FakeEmulator):
        mem_read = None

    with pytest.raises(EmulatorContract) as caught:
        decrypt_blocks(_Partial(), b"ab", _wrapper(), block_size=2)
    assert "mem_read" in str(caught.value)


def test_a_contract_error_is_raised_not_filed_as_a_bad_block():
    """Every remaining block would fail the same way, so thousands of identical
    "block failed" lines would report our gap as the file's content."""
    from revenant.contrib.decrypt import EmulatorContract, decrypt_blocks
    import pytest

    class _WrongArity(_FakeEmulator):
        def emu_start(self, begin, until):     # no timeout
            pass

    with pytest.raises(EmulatorContract):
        decrypt_blocks(_WrongArity(), b"abcd", _wrapper(), block_size=2)


def test_a_short_read_back_is_a_failed_block_not_a_shifted_result():
    """Slice-assigning a short read into the bytearray shrinks it, so every
    later block lands at the wrong offset -- verified: an 8-byte blob came back
    7 bytes long with nothing marked failed."""
    from revenant.contrib.decrypt import decrypt_blocks

    class _Short(_FakeEmulator):
        def mem_read(self, addr, size):
            return super().mem_read(addr, size - 1)

    out = decrypt_blocks(_Short(), b"abcdefgh", _wrapper(), block_size=4)
    assert len(out.plaintext) == 8
    assert out.failed == (0, 1)
    assert any("read back" in note for note in out.notes)


def test_a_wrapper_that_writes_somewhere_else_is_read_from_there():
    """One `body` for input and output would hand back the ciphertext for a
    wrapper that does not decrypt in place, with nothing saying so."""
    from revenant.contrib.decrypt import decrypt_blocks

    class _Elsewhere(_FakeEmulator):
        def emu_start(self, begin, until, timeout=0, count=0):
            at, size = self.regs["x0"], self.regs["x1"]
            self.mem_write(0x50000, bytes(b ^ 0xFF for b in self.mem_read(at, size)))

    out = decrypt_blocks(_Elsewhere(), b"ab", _wrapper(out=0x50000), block_size=2)
    assert out.plaintext == bytes(b ^ 0xFF for b in b"ab")


def test_the_bytes_that_must_be_in_memory_first_are_an_argument():
    """The jump table is blank in the file and read once from a live process;
    the program and key blocks are per-build too. The ticket calls all of them
    inputs, and without a seam a caller had to `mem_write` them out of band."""
    from revenant.contrib.decrypt import decrypt_blocks
    emu = _FakeEmulator()
    decrypt_blocks(emu, b"ab", _wrapper(), block_size=2,
                   preload={0x70000: b"\x01\x02", 0x80000: b"key"})
    assert emu.mem_read(0x70000, 2) == b"\x01\x02"
    assert emu.mem_read(0x80000, 3) == b"key"


def test_a_string_argv_is_refused_rather_than_read_one_character_at_a_time():
    from revenant.contrib.decrypt import decrypt_blocks
    import pytest
    with pytest.raises(ValueError) as caught:
        decrypt_blocks(_FakeEmulator(), b"ab", _wrapper(argv="x0"), block_size=2)
    assert "not a string" in str(caught.value)


# ── Lua table literals as config tables (#58) ──────────────────────────────
#
# Two xLua titles keep their config as Lua tables that `lua-extract` has
# already decompiled. Reading them is what makes `table list` / `table census`
# say the same thing on nine titles instead of seven.

def test_a_lua_return_table_of_rows_reads_as_rows():
    from revenant import luatable
    text = """
    return {
      [1] = { id = 1, name = "Order", cost = 3.5, ok = true },
      [2] = { id = 2, name = "Ship", cost = 0, ok = false },
    }
    """
    value = luatable.parse(text)
    assert value == {1: {"id": 1, "name": "Order", "cost": 3.5, "ok": True},
                     2: {"id": 2, "name": "Ship", "cost": 0, "ok": False}}


def test_an_array_style_table_keeps_its_order():
    from revenant import luatable
    assert luatable.parse("return { {id=1}, {id=2}, {id=3} }") == {
        1: {"id": 1}, 2: {"id": 2}, 3: {"id": 3}}


def test_a_table_assigned_to_a_local_and_returned_is_found():
    """Decompiled config comes out both ways depending on the decompiler."""
    from revenant import luatable
    text = "local Config = { [7] = { v = 1 } }\nreturn Config\n"
    assert luatable.parse(text) == {7: {"v": 1}}


def test_the_lua_values_that_appear_in_config_all_parse():
    from revenant import luatable
    text = r"""return { a = "q\"uote", b = 'single', c = [[long
line]], d = -12, e = 0x1F, f = 1e3, g = nil, h = {1, 2}, i = true }"""
    out = luatable.parse(text)
    assert out["a"] == 'q"uote' and out["b"] == "single"
    assert out["c"] == "long\nline"
    assert out["d"] == -12 and out["e"] == 31 and out["f"] == 1000.0
    assert "g" not in out, "nil is absent, not None -- Lua has no key for it"
    assert out["h"] == {1: 1, 2: 2} and out["i"] is True


def test_comments_are_skipped_including_the_long_form():
    from revenant import luatable
    text = """
    -- a line comment with a { brace in it
    return {           --[[ and a long
    one spanning lines ]] [1] = { v = 1 },   -- trailing
    }
    """
    assert luatable.parse(text) == {1: {"v": 1}}


def test_a_file_that_is_not_a_table_says_so_rather_than_returning_empty():
    from revenant import luatable
    import pytest
    for text in ("local x = require('other')\nreturn x\n",
                 "return 42\n", "", "-- only a comment\n"):
        with pytest.raises(luatable.LuaError):
            luatable.parse(text)


def test_an_unterminated_table_is_an_error_not_a_short_read():
    """Stopping at the end of the input and handing back what was parsed would
    report a truncated file as a smaller table."""
    from revenant import luatable
    import pytest
    with pytest.raises(luatable.LuaError):
        luatable.parse("return { [1] = { v = 1 },")


def test_a_deeply_nested_table_stops_instead_of_exhausting_the_stack():
    from revenant import luatable
    import pytest
    with pytest.raises(luatable.LuaError):
        luatable.parse("return " + "{" * 500 + "}" * 500)


def test_a_function_valued_field_is_reported_not_silently_dropped():
    """A module returning behaviour is not a config table, and a parser that
    skipped what it could not read would call it one with fewer columns."""
    from revenant import luatable
    import pytest
    with pytest.raises(luatable.LuaError) as caught:
        luatable.parse("return { [1] = { go = function() end } }")
    assert "function" in str(caught.value)


def test_a_directory_of_only_lua_config_is_a_corpus(tmp_path):
    """`lua/<version>/Data/Config` holds no JSON, and until now a directory
    qualified only when something in it sniffed as JSON -- so the two titles
    whose config is Lua had no corpus at all."""
    from revenant import tables as _t
    conf = os.path.join(str(tmp_path), "lua", "1.0", "Data", "Config")
    os.makedirs(conf)
    for name in ("Order", "Item"):
        with open(os.path.join(conf, f"{name}.lua"), "w", encoding="utf-8") as f:
            f.write("return { [1] = { id = 1, cost = 2 } }\n")
    found = _t.discover(str(tmp_path), cfg={})
    assert [c.rel for c in found.corpora] == [os.path.join("lua", "1.0", "Data", "Config")]
    assert {t.name for t in found.tables()} == {"Order", "Item"}


def test_a_tree_of_lua_modules_is_not_mistaken_for_a_corpus(tmp_path):
    """The reverse test, and the one that matters: `lua/<version>/` is the
    whole decompiled game. A sniff that called every directory of `.lua` a
    corpus would report thousands of gameplay modules as unreadable tables."""
    from revenant import tables as _t
    code = os.path.join(str(tmp_path), "lua", "1.0", "Board")
    os.makedirs(code)
    for name, body in (("Model", "local M = {}\nfunction M.run() end\nreturn M\n"),
                       ("View", "local base = require('Board.Model')\nreturn {}\n")):
        with open(os.path.join(code, f"{name}.lua"), "w", encoding="utf-8") as f:
            f.write(body)
    assert _t.discover(str(tmp_path), cfg={}).corpora == ()


def test_a_lua_config_table_reads_as_rows_and_fields(tmp_path):
    from revenant import tables as _t
    conf = os.path.join(str(tmp_path), "lua", "1.0", "Config")
    os.makedirs(conf)
    path = os.path.join(conf, "Order.lua")
    with open(path, "w", encoding="utf-8") as f:
        f.write("return {\n [11] = { id = 11, cost = 3, name = 'a' },\n"
                " [12] = { id = 12, cost = 4 },\n}\n")
    data = _t.read(_t.Table(name="Order", path=path, corpus="c", shape=_t.SHAPE_LUA))
    assert data.reader == _t.READER_LUA and data.error == ""
    assert len(data.rows) == 2
    assert data.fields == ("id", "cost", "name"), "first-seen order, as JSON does"


def test_a_lua_module_that_is_not_config_reports_why(tmp_path):
    """"This table is empty" and "we cannot read this table" are different
    facts -- the line #59 drew and this reader is held to."""
    from revenant import tables as _t
    path = os.path.join(str(tmp_path), "M.lua")
    with open(path, "w", encoding="utf-8") as f:
        f.write("return { run = function() end }\n")
    data = _t.read(_t.Table(name="M", path=path, corpus="c", shape=_t.SHAPE_LUA))
    assert data.rows == () and "function" in data.error


def test_a_lua_corpus_says_its_counts_are_per_file():
    """One title ships 62 `OrderFixedConfig_*.lua` of which 47 load, so summing
    the files overstates the rows by 34%. Which of them the game loads is a
    fact about that game's loader, so the count says it is of files -- the
    alternative is a confident number that is wrong."""
    from revenant import tables as _t
    assert "loadable" in _t.LUA_VARIANT_CAVEAT
    for verdict in ("dead", "unused", "duplicate"):
        assert verdict not in _t.LUA_VARIANT_CAVEAT.lower(), verdict


def test_the_table_that_is_returned_is_the_one_that_is_read():
    """It anchored on the first `{` in the file, so a config defining defaults
    before the real table came back as the defaults -- one row instead of two
    hundred, confidently and with nothing saying so."""
    from revenant import luatable
    text = ("local Defaults = { [0] = { id = 0, cost = 0 } }\n"
            "local Config = { [1] = {id=1,cost=5}, [2] = {id=2,cost=7} }\n"
            "return Config\n")
    assert luatable.parse(text) == {1: {"id": 1, "cost": 5},
                                    2: {"id": 2, "cost": 7}}


def test_a_module_with_behaviour_is_an_error_not_an_empty_table():
    """`local M = {}` + functions + `return M` handed back `{}`, which reads as
    a table with no rows rather than as a file that is not a table."""
    from revenant import luatable
    import pytest
    for text in ("local M = {}\nfunction M.run() end\nreturn M\n",
                 "local m = require('other')\nreturn { [1] = { v = m } }\n"):
        with pytest.raises(luatable.LuaError) as caught:
            luatable.parse(text)
        assert "not a Lua config table" in str(caught.value)


def test_the_word_function_inside_a_string_does_not_make_it_code():
    """The reverse test: the keyword scan runs over a copy with strings and
    comments blanked, or a config row saying "function" would be refused."""
    from revenant import luatable
    text = 'return { [1] = { note = "function", kind = "require" } }\n'
    assert luatable.parse(text) == {1: {"note": "function", "kind": "require"}}


def test_a_boolean_key_is_refused_rather_than_eating_a_row():
    """Python's `True == 1`, so `{ 5, [true] = 9 }` came back as `{1: 9}` --
    the array element silently replaced."""
    from revenant import luatable
    import pytest
    with pytest.raises(luatable.LuaError):
        luatable.parse("return { 5, [true] = 9 }")


def test_a_duplicate_key_is_refused_rather_than_shortening_the_table():
    from revenant import luatable
    import pytest
    with pytest.raises(luatable.LuaError):
        luatable.parse("return { [1] = {v=1}, [1] = {v=2} }")


def test_an_out_of_range_decimal_escape_is_refused():
    from revenant import luatable
    import pytest
    with pytest.raises(luatable.LuaError):
        luatable.parse(r'return { a = "\300" }')
    assert luatable.parse(r'return { a = "\65" }') == {"a": "A"}


def test_the_whitespace_escape_is_honoured():
    from revenant import luatable
    assert luatable.parse('return { a = "x\\z   \n   y" }') == {"a": "xy"}


def test_an_unknown_escape_is_refused_rather_than_dropping_the_backslash():
    from revenant import luatable
    import pytest
    with pytest.raises(luatable.LuaError):
        luatable.parse(r'return { a = "\q" }')


def test_a_class_with_a_table_constant_is_not_a_config_corpus(tmp_path):
    """The sniff matched any nested literal, so an ordinary decompiled class
    with a constant was listed as a two-row table -- not merely unreadable,
    but *read*, which is worse."""
    from revenant import tables as _t
    code = os.path.join(str(tmp_path), "lua", "1.0", "UI")
    os.makedirs(code)
    for name, body in (
            ("UIPanel", "local UIPanel = {}\nUIPanel.LAYERS = { hud = { z = 1 } }\n"
                        "function UIPanel.show() end\nreturn UIPanel\n"),
            ("Dispatcher", "local D = { listeners = {}, queue = {} }\n"
                           "function D.emit() end\nreturn D\n")):
        with open(os.path.join(code, f"{name}.lua"), "w", encoding="utf-8") as f:
            f.write(body)
    assert _t.discover(str(tmp_path), cfg={}).corpora == ()


def test_positional_rows_are_recognised_as_a_corpus(tmp_path):
    """The other direction: `return { {1,"a"}, {2,"b"} }` is a real config
    shape and the first sniff missed it, so the corpus was invisible."""
    from revenant import tables as _t
    conf = os.path.join(str(tmp_path), "lua", "1.0", "Conf")
    os.makedirs(conf)
    with open(os.path.join(conf, "Rows.lua"), "w", encoding="utf-8") as f:
        f.write('return { {id=1, n="a"}, {id=2, n="b"} }\n')
    found = _t.discover(str(tmp_path), cfg={})
    assert [c.rel for c in found.corpora] == [os.path.join("lua", "1.0", "Conf")]


def test_an_empty_lua_table_is_zero_rows_not_an_unreadable_file(tmp_path):
    """Empty JSON reads as 0 rows; empty Lua said "not a table". That inverts
    the rule this module is built on -- "this table is empty" and "we cannot
    read this table" are different facts, and both directions matter."""
    from revenant import tables as _t
    path = os.path.join(str(tmp_path), "Empty.lua")
    with open(path, "w", encoding="utf-8") as f:
        f.write("return {}\n")
    data = _t.read(_t.Table(name="Empty", path=path, corpus="c", shape=_t.SHAPE_LUA))
    assert data.reader == _t.READER_LUA and data.error == "" and data.rows == ()


def test_bytes_that_are_not_utf8_are_reported_not_replaced(tmp_path):
    """`errors="replace"` turned undecodable bytes into U+FFFD and read them as
    content, four functions below the JSON reader that reports them."""
    from revenant import tables as _t
    path = os.path.join(str(tmp_path), "Bad.lua")
    with open(path, "wb") as f:
        f.write(b"return { [1] = { n = '\xff\xfe' } }\n")
    data = _t.read(_t.Table(name="Bad", path=path, corpus="c", shape=_t.SHAPE_LUA))
    assert data.rows == () and "not UTF-8" in data.error


def test_the_count_caveat_rides_on_every_lua_read(tmp_path):
    """It reached `table list` only, and the overstatement it warns about
    happens when somebody sums -- which is `census` and `rows()`."""
    from revenant import tables as _t
    path = os.path.join(str(tmp_path), "Order.lua")
    with open(path, "w", encoding="utf-8") as f:
        f.write("return { [1] = { id = 1 } }\n")
    data = _t.read(_t.Table(name="Order", path=path, corpus="c", shape=_t.SHAPE_LUA))
    assert data.partial == _t.LUA_VARIANT_CAVEAT


# ── a wrong [lua] size_t looks like "these modules will not decompile" (#69) ──

def test_a_size_t_mismatch_is_named_rather_than_left_as_failed_chunks(monkeypatch, capsys):
    """The header xLua writes *omits* the size_t field, so there is nothing in
    the file to check a configured value against -- the only evidence it is
    wrong is that some chunks desync and fail. That reads as a property of those
    modules. One title spent a day with three chunks unexplained and 1,584 fine;
    the value was 8 where the build wanted 4, and 4 took it to 1,587/1,587.

    So the report tries the other value on the failures and says whether it
    helps, which is what a person does by hand.
    """
    from revenant import lua

    # Two chunks that only "decompile" when size_t is 4 -- the shape of the bug,
    # without needing a JVM or real bytecode.
    blobs = {"a": lua._LUA_MAGIC + b"\x53\x01" + b"x" * 20,
             "b": lua._LUA_MAGIC + b"\x53\x01" + b"y" * 20}
    monkeypatch.setattr(lua, "lua_cfg", lambda: {"size_t": 8})
    monkeypatch.setattr(lua, "decompile", lambda chunk, timeout=60: (lua._size_t() == 4, ""))

    rep = lua.ExtractReport(total=2, out_dir="")
    rep.bytecode_only = 2
    lua._report_size_t_suspicion(blobs, rep)

    err = capsys.readouterr().err
    assert "size_t = 4" in err, err
    assert "configuration mismatch" in err
    # And the trial must not leave the overridden value behind.
    assert lua._size_t() == 8


def test_no_size_t_advice_when_the_other_value_does_not_help(monkeypatch, capsys):
    """Chunks fail for many reasons. Advice that fires on all of them is noise,
    and worse, it sends people to change a setting that was already right."""
    from revenant import lua
    blobs = {"a": lua._LUA_MAGIC + b"\x53\x01" + b"x" * 20}
    monkeypatch.setattr(lua, "lua_cfg", lambda: {"size_t": 4})
    monkeypatch.setattr(lua, "decompile", lambda chunk, timeout=60: (False, "broken"))

    rep = lua.ExtractReport(total=1, out_dir="")
    rep.bytecode_only = 1
    lua._report_size_t_suspicion(blobs, rep)
    assert "size_t" not in capsys.readouterr().err


# ── Cpp2IL's float immediates cannot be read literally (#69) ─────────────────

def test_a_round_constant_arriving_with_a_2_32_tail_is_marked():
    """`fmov #5.0` reaches IsilDump as `4.000000000232831`: the round number
    plus an epsilon on the order of 2^-32, which is a 32-bit float widened
    through a 64-bit read. One repository's nine games carried this as a rule in
    a person's head -- "a long decimal tail probably means a round number".
    """
    from revenant.reports import annotate_float_immediates
    out = annotate_float_immediates("fmov s0, #4.000000000232831\n"
                                    "fmul s1, s0, #8.000000000465661\n")
    assert "4.000000000232831 -- almost certainly 4" in out
    assert "8.000000000465661 -- almost certainly 8" in out
    # Marked, never rewritten: which round number it should be is a guess, and a
    # silently corrected constant cannot be checked by the reader.
    assert "fmov s0, #4.000000000232831" in out
    assert "revenant disasm" in out


def test_an_honest_float_is_left_alone():
    """A constant that is genuinely fractional must not be called suspect --
    advice that fires on everything is advice nobody reads."""
    from revenant.reports import annotate_float_immediates
    for honest in ("mov x0, #3.500000\n", "fmov s0, #0.333333333\n",
                   "fmov s0, #1.618033988\n"):
        assert "Suspect float" not in annotate_float_immediates(honest), honest


def test_a_listing_with_no_floats_is_returned_unchanged():
    from revenant.reports import annotate_float_immediates
    text = "ldr x0, [x1, #0x18]\nbl 0x010FC478\n"
    assert annotate_float_immediates(text) == text
