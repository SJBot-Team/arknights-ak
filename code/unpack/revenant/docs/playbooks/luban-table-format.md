# Luban binary table format

Verified on: upstream Luban (【源码确认】: `Luban.Core/Serialization/ByteBuf.cs`,
`Luban.CSharp/Templates/cs-bin/*.sbn` and `BinaryUnderlyingDeserializeVisitor.cs`
at `focus-creative-games/luban@main`). **Not yet 【实包确认】** — see "What is
still unproven" at the end, which is the part to read before trusting a decode.

Luban is a configuration pipeline: designers edit sheets, it generates loader
code into the game plus one binary blob per table. `revenant/luban.py` reads the
blobs; the outer container and its key stay in the project.

## The wire format

Two byte orders in one buffer. Getting this backwards is the usual way a
hand-written decoder produces numbers that look plausible and are not.

**Integers are a big-endian prefix varint** — not protobuf's little-endian
continuation-bit scheme. The lead byte's high bits give the total length:

| lead | bytes | value |
|---|---|---|
| `< 0x80` | 1 | the lead byte |
| `< 0xc0` | 2 | `(lead & 0x3f) << 8` \| next |
| `< 0xe0` | 3 | `(lead & 0x1f) << 16` \| next two, big-endian |
| `< 0xf0` | 4 | `(lead & 0x0f) << 24` \| next three, big-endian |
| `0xf0` | 5 | next four, big-endian; the lead carries no payload |

`long` continues the same ladder through `0xf8`, `0xfc`, `0xfe` and `0xff` to
nine bytes. `int` and `long` are these read as two's complement, so **-1 costs
five bytes**.

**`sint`/`slong` are a bit rotation, not zigzag — and upstream's own comment says
otherwise.** The block above `WriteSint` describes zigzag (`(x >>> 1) ^ -(n&1)`)
and the code beneath it reads

```csharp
public int ReadSint() { uint x = ReadUint(); return (int)((x >> 1) ^ ((x & 1) << 31)); }
```

which moves the low bit back to the sign position and leaves the rest alone;
`WriteSint` is the matching rotate-left, so the pair is self-consistent and the
comment is simply wrong. Trust the code. Decoded as zigzag, every positive comes
back right and every negative comes back wrong — `-1` reads as `-2147483648`,
`-127` as `-2147483522` — and nothing in the output looks broken. This costs
Luban the usual benefit: under a rotation `-1` still takes five bytes, while
`-2147483648` takes one.

**Floats are little-endian IEEE**, and `fint` / `fshort` / `flong` are
fixed-width little-endian. One buffer, both orders.

Everything else is built from those:

- `string`, `bytes` — a size (a varint `uint`) then that many bytes, UTF-8.
- `list` / `set` / `array` — a size then that many elements.
- `map` — a size then that many key-value pairs, key first.
- a nullable field — a `bool`, then the value if it was true.
- a bean — its fields in declaration order, **the parent's first**: the
  generated constructor chains to `base(_buf)` before reading its own.
- a polymorphic bean — an `int` type id (`__ID__` in the generated class) and
  then that concrete bean's fields.
- a table file — a size, then that many rows. Nothing else: no magic, no
  version, no field names.

## Why you need the schema, and where it comes from

None of the above is self-describing. The blob has no field names and no types,
so one wrong type desynchronises everything after it and the rows keep coming
out looking like numbers. A decoder without a schema is guessing.

The schema is in the package too, in the loader Luban generated: each table has
an `XxxTable(ByteBuf _buf)` constructor and each row type an `XxxConf(ByteBuf
_buf)` constructor, whose statements are the read order. Write it out as JSON —
`revenant luban-read` with no `--schema` prints the shape — and keep it in the
project, because bean names and field lists are facts about one title.

Two checks that the schema is right, in order of strength:

1. **Leftover bytes.** `read_table` reports `trailing`; anything nonzero means
   the schema is short a field and the rows after it are shifted. `table list`
   reports it as an error on that table, not a footnote.
2. **Spot-check a known row** against the game's UI or a sheet. Leftover bytes
   catch a schema that is too short; they do not catch two adjacent fields whose
   types happen to be the same width and swapped.

## The container is the project's

Both titles wrap the blob, differently, so `read_table` takes a `container`
callable and revenant ships none:

- **Mystery Town** — a byte-wise XOR. The key is derived from the pixels of an
  image inside the package (`Startup/Textures/icon`, `pixels[4..19]` as
  greyscale), so it is fully recoverable offline.
- **Merge Cooking** — a four-byte header (`"HEY"` + `0x01`) then a body whose
  transform is described below.

In a project, that is a Python file exposing `decode(data: bytes) -> bytes`,
pointed at by `[tables] luban_container`; `[tables] luban_schema` points at the
JSON. With both set, `revenant table list` reads the blobs like any other table.

## What is still unproven

Two gaps, stated plainly because the decode is worthless if either is wrong and
neither is visible in the output.

**The format has not been run against a shipped blob.** Everything above is read
off Luban's own source and pinned by tests over synthetic bytes. That makes it a
faithful transcription of upstream, not evidence about either title: a game on a
forked or older Luban could differ, and the way that shows up is a header-stage
failure or leftover bytes, not silence. First real decode should record which
Luban version the game shipped.

**Merge Cooking's body transform is a resemblance, not a finding.** The key is a
plaintext `byte[16]` constant in `ConfigManager.cs` and is in hand. The
algorithm at `AOT.Init.Step.OnExit` (RVA `0x01C8074C`) is *assumed* to be XXTEA
on the strength of one signature — `ToByteArray(UInt32[], bool includeLength)`,
which is XXTEA's characteristic pair. That is a shape, and several ciphers
share it.

To settle it, read the routine rather than pattern-match the signature:

```bash
revenant find-asm 0x01C8074C
```

and check for XXTEA's constants and structure — the delta `0x9E3779B9`, the
`(z >> 5 ^ y << 2) + (y >> 3 ^ z << 4)` mixing shape, and a round count of
`6 + 52/n`. If they are there it is XXTEA and `revenant.contrib.decrypt.xxtea`
decodes it with the key already in hand. If they are not, this is a different
cipher and the resemblance was the `UInt32[]` round trip, which any word-based
block cipher shows.

Until that read happens, Merge Cooking's numbers stay out of reach on the input
side (`out_of_reach` / `input_missing`, in the four-state vocabulary) — not
because a tool is missing, but because one analysis step has not been done.
Mystery Town has no such gap and should be decoded first.
