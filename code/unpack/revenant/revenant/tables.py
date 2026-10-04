"""Config tables: what a project has, and which reader read each one.

A **table** is one decoded configuration table -- rows and fields -- whatever it
was shipped as. `pb-schema`, `fb-read` and `extract-scenes` open the container
and stop; every piece of economy analysis happens after that, and across 53
analysis notes it happened in hand-written Python (86 `json.load`, 72 `glob`, 60
`Counter`). This module is the seam those notes were missing: find the tables,
say which reader claims each, and hand back rows with the wrapper key already
off.

Four landing spots are recognised. Two are read here -- the id-to-row map a
protobuf-JSON dump produces, and the bare row array a remote-config dump
produces. A binary blob goes to `revenant.luban` or `revenant.flatbuffers`
depending on which the project said it is, one file at a time, so a corpus only
half described says which half. A Lua table constructor goes to
`revenant.luatable` -- two titles keep their config that way and `lua-extract`
has already decompiled it. Nothing unread comes back as an empty table:
"this table is empty" and "we cannot read this table" are different facts.

Nothing here knows a directory name, a file-naming rule, or a wrapper key from
any particular title -- those are game facts and stay in the projects
(`contrib/__init__.py`). Discovery works on **shape**: a directory holding files
that parse as tables.

What it costs is bounded on purpose, because `status` and `table list` are
queries and a real project has 655 MB of IsilDump in `_refs/` and hundreds of
thousands of extracted files under `res/`. Measured on a synthetic `res/` of
180,300 files in 361 directories: 0.3 s for a full sweep, with the
directory cap reported as reached. Every cap that bites is printed -- a query
that silently covered less than it was asked to reads exactly like one that
found nothing there.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field as _field
from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:                       # imported lazily at run time: a listing
    from .flatbuffers import Schema as FbSchema
    from .luban import Schema           # of JSON tables must not pay for it

# ── shapes and readers ──────────────────────────────────────────────────────
# Two vocabularies, because two different things know two different amounts.
#
# A *shape* is what a file is, and discovery can tell it from the name alone.
# A *reader* is what claimed the content, and only parsing decides that. The
# JSON shape covers two readers -- which one a file gets is the whole question
# `table list` answers, and the only place a misread ever shows up.
SHAPE_JSON = "json"
SHAPE_LUA = "lua"
SHAPE_BINARY = "binary"

READER_JSON_IDMAP = "json-idmap"    # {wrapper?: {id: row}} -- protobuf-JSON dumps
READER_JSON_ROWS = "json-rows"      # {wrapper?: [row, ...]} -- bare JSON dumps
READER_LUA = "lua-table"            # a Lua table constructor, already decompiled
READER_LUBAN = "luban"              # a Luban blob the project named a schema for
READER_FB = "flatbuffers"           # a FlatBuffers blob the project named a root for

# Every shape has a reader: JSON here, binary in `luban`/`flatbuffers`, Lua in
# `luatable`. The table that used to list the shapes waiting on a ticket is
# gone with the last of them (#58) rather than left empty with five branches
# nothing can reach. The distinction it drew survives where it still applies:
# `UNCLAIMED` is a blob this project named no reader for, which is a fact about
# the project and not a gap in revenant.
UNCLAIMED = "unclaimed"     # a reader exists; this project named none for it

EXTENSIONS = {
    ".json": SHAPE_JSON,
    ".lua": SHAPE_LUA,
    ".bytes": SHAPE_BINARY,
    ".bin": SHAPE_BINARY,
}

SOURCE_FOUND = "found"
SOURCE_CONFIGURED = "configured"

# Where extraction lands. Not the whole project: `_refs/` is the IsilDump,
# `src/` is the scaffold, `_apks/` and `_binaries/` are packages -- none of them
# is a place config tables land, and all of them are places a query command must
# not walk.
# `lua/` is here because two titles keep their config as Lua tables that
# `lua-extract` has already decompiled there. It is the same bounded sweep --
# `lua/<version>/Data/Config` is three levels, which is the depth cap exactly.
CORPUS_ROOTS = ("res", "decompiled", "lua")

# Directories never entered: a project's own scripts (`TOOL_DIRS` already reads
# those) and build litter.
SKIP_DIRS = {"_tools", "__pycache__", "node_modules"}

MAX_DEPTH = 3           # levels below a root; `res/remote/config` is two
MAX_DIRS = 400          # directories opened per sweep
MAX_ENTRIES = 5000      # names read from any one directory
SNIFF_FILES = 8         # files sniffed before deciding a directory is a corpus
SNIFF_BYTES = 512       # bytes read per sniff


class TableError(Exception):
    """A table could not be read, and why."""


@dataclass(frozen=True)
class Table:
    name: str        # the file stem, which is what a note calls the table
    path: str        # absolute
    corpus: str      # the corpus directory, project-relative
    shape: str       # SHAPE_JSON | SHAPE_LUA | SHAPE_BINARY


@dataclass(frozen=True)
class Corpus:
    rel: str         # project-relative directory
    path: str        # absolute
    tables: tuple    # Table, by file name
    source: str      # SOURCE_FOUND | SOURCE_CONFIGURED


@dataclass(frozen=True)
class TableData:
    table: Table
    reader: str = ""     # the reader that claimed it; "" when none could
    rows: tuple = ()
    fields: tuple = ()
    wrapper: str = ""    # the top-level key that was unwrapped, "" if none
    error: str = ""      # why it could not be read; "" when it was
    # Rows that are right as far as they go. Separate from `error` because the
    # two want opposite handling: `rows()` refuses an error and hands back a
    # partial read, since the values in it are sound and only the count is short.
    partial: str = ""

    @property
    def label(self) -> str:
        """What to print in a reader column: the reader, or why there is none.

        One place decides this. Three sites used to phrase the answer their own
        way, which is three chances for the listing and the error to disagree
        about a table.
        """
        if self.reader:
            return self.reader
        if self.table.shape == SHAPE_BINARY:
            return f"{SHAPE_BINARY} ({UNCLAIMED})"
        return "-"


@dataclass(frozen=True)
class Discovery:
    corpora: tuple = ()
    gaps: tuple = ()        # coverage this sweep did not get, and why
    missing: tuple = ()     # configured directories that are not there

    def tables(self) -> tuple:
        return tuple(t for c in self.corpora for t in c.tables)


# ── reader dispatch ─────────────────────────────────────────────────────────

def _tabular(value) -> bool:
    """Whether a value is already a table: rows in a list, or rows by id."""
    if isinstance(value, list):
        return True
    return isinstance(value, dict) and all(isinstance(v, dict) for v in value.values())


def unwrap(value):
    """`(payload, wrapper_key)` -- the two lines every note wrote by hand.

    A single top-level key is a wrapper only when taking it off leaves a table.
    That is what keeps `{"1001": {...}}` -- an id map holding one row -- from
    being read as a wrapper around a bare row: unwrapping it leaves a row, and a
    row is not a table.
    """
    if isinstance(value, dict) and len(value) == 1:
        key, inner = next(iter(value.items()))
        if _tabular(inner):
            return inner, key
    return value, ""


def dispatch(value):
    """`(reader, rows, wrapper)` for one parsed JSON value.

    Pure, so every shape the corpus ships can be pinned without a file. Raises
    `TableError` when the value is not a table at all -- a build stamp or a
    version manifest sitting in the same directory is not a zero-row table.
    """
    payload, wrapper = unwrap(value)
    if isinstance(payload, list):
        return READER_JSON_ROWS, list(payload), wrapper
    if _tabular(payload):
        return READER_JSON_IDMAP, list(payload.values()), wrapper
    kind = type(payload).__name__
    if isinstance(payload, dict):
        offenders = sorted(k for k, v in payload.items() if not isinstance(v, dict))[:3]
        raise TableError(f"not a table: top-level keys map to values, not rows "
                         f"({', '.join(str(o) for o in offenders)})")
    raise TableError(f"not a table: top level is a {kind}")


def fields(rows) -> tuple:
    """The union of the rows' keys, in the order they are first seen."""
    seen: dict = {}
    for row in rows:
        if isinstance(row, dict):
            for key in row:
                seen.setdefault(key, None)
    return tuple(seen)


# ── reading one table ───────────────────────────────────────────────────────

@dataclass(frozen=True)
class Readers:
    """What this project brought that a built-in reader cannot supply itself.

    Passed in rather than looked up inside `read()`, so reading a table handed
    in from somewhere never depends on which project happens to be ambient.
    """
    luban_schema: "Schema | None" = None
    luban_container: "Callable[[bytes], bytes] | None" = None
    fb_schema: "FbSchema | None" = None
    fb_roots: dict = _field(default_factory=dict)   # name -> "Root" | "Root#Field"
    fb_containers: tuple = ()        # the CMS generic wrapper names, a game fact
    notes: tuple = ()                # why something configured is not usable

    def luban_bean(self, table: Table) -> str:
        """The bean a Luban schema says this file's rows are, or ""."""
        schema = self.luban_schema
        if schema is None:
            return ""
        return schema.tables.get(table.name, "")

    def fb_root(self, table: Table) -> str:
        """The root this project says the file holds, or "". """
        return (self.fb_roots or {}).get(table.name, "")

    def claims(self, table: Table) -> str:
        """Which binary reader this project pointed at the file, or ""."""
        luban, fb = self.luban_bean(table), self.fb_root(table)
        if luban and fb:
            return "both"
        return READER_LUBAN if luban else (READER_FB if fb else "")

    def row_class(self, table: Table) -> str:
        """What one row of this table is called, when a schema says. "" when none.

        Searched alongside the file's own name because codegen usually names
        them differently -- looking for only one finds nothing, and nothing
        reads as zero. Answered from the declaration, so no bytes are decoded
        to get it: asking what a row is *called* is not asking to read one.

        Here rather than beside the readers because it is the same question
        `luban_bean` and `fb_root` answer -- what this project said about this
        file -- and a third `reader ==` cascade elsewhere is a third place to
        forget a reader.
        """
        claimed = self.claims(table)
        if claimed == READER_LUBAN:
            return self.luban_bean(table)
        if claimed == READER_FB:
            from . import flatbuffers as _fb
            return _fb.row_class(self.fb_schema, self.fb_root(table),
                                 self.fb_containers)
        return ""


def claimed_names(root: str | None = None, cfg: dict | None = None) -> set:
    """Table names this project has already declared are tables.

    Discovery needs these because a CMS library is a directory of `.bin` and
    nothing else -- no JSON to sniff, and the rule that keeps `res/`'s hundreds
    of thousands of extracted TextAssets from counting as a corpus would keep
    this one out too. A project naming a file in `fb_roots`, or in a Luban
    schema's `tables` map, is the evidence that sniff stands in for.

    Deliberately not `readers_for()`. This runs on every `revenant status`, and
    building the readers would import and execute the project's own container
    hook -- running a title's Python to answer "how many files are there" is not
    a trade a status query gets to make. Reading two small JSON files is.
    """
    from . import config
    root = os.path.abspath(root or config.workspace_root())
    if cfg is None:
        cfg = config.load_config(root)
    section = (cfg or {}).get("tables") or {}
    names = {str(k) for k in (section.get("fb_roots") or {})}
    rel = section.get("luban_schema")
    if rel:
        path = rel if os.path.isabs(rel) else os.path.join(root, rel)
        try:
            with open(path, encoding="utf-8") as f:
                names |= {str(k) for k in (json.load(f).get("tables") or {})}
        except Exception:                     # noqa: BLE001 - readers_for reports it
            pass
    return names


def readers_for(root: str | None = None, cfg: dict | None = None) -> Readers:
    """Build the project-supplied readers from `[tables]`. Never raises.

    A misconfigured hook is reported as a note and the shapes it would have
    read stay unread -- a listing that dies because one key points at a moved
    file tells you nothing about the other four corpora.
    """
    from . import config
    root = os.path.abspath(root or config.workspace_root())
    if cfg is None:
        cfg = config.load_config(root)
    section = (cfg or {}).get("tables") or {}
    schema: "Schema | None" = None
    container: "Callable[[bytes], bytes] | None" = None
    notes: list = []
    rel = section.get("luban_schema")
    if rel:
        from . import luban as _luban
        path = rel if os.path.isabs(rel) else os.path.join(root, rel)
        try:
            schema = _luban.load_schema(path)
        except Exception as exc:                  # noqa: BLE001 - report, don't die
            notes.append(f"[tables] luban_schema = {rel!r} could not be loaded: {exc}")
    fb_schema = None
    fb_roots = {str(k): str(v) for k, v in (section.get("fb_roots") or {}).items()}
    fb_rel = section.get("fb_schema")
    if fb_rel:
        from . import flatbuffers as _fb
        path = fb_rel if os.path.isabs(fb_rel) else os.path.join(root, fb_rel)
        try:
            with open(path, encoding="utf-8") as f:
                fb_schema = _fb.Schema.from_dict(json.load(f))
        except Exception as exc:                  # noqa: BLE001 - report, don't die
            notes.append(f"[tables] fb_schema = {fb_rel!r} could not be loaded: {exc}")
    if fb_roots and fb_schema is None:
        # The roots stay. Clearing them would un-claim the directory, and a
        # `.bin`-only corpus would stop being a corpus at all -- its tables gone
        # from the count rather than listed as unread, which is the one thing
        # this module refuses to do. `_read_flatbuffers` refuses instead, per
        # file: decoding against no schema probes every slot, which is a page of
        # `?` markers dressed up as a table.
        notes.append(f"[tables] fb_roots names {len(fb_roots)} "
                     f"{plural(len(fb_roots), 'root')} but no usable fb_schema, "
                     f"so those blobs stay unread")
    try:
        container = config.load_project_callable(
            section.get("luban_container"), "decode",
            "[tables] luban_container", root=root)
    except Exception as exc:                      # noqa: BLE001 - report, don't die
        notes.append(f"{exc}")
    containers = tuple(str(c) for c in (section.get("fb_containers") or ()))
    return Readers(luban_schema=schema, luban_container=container,
                   fb_schema=fb_schema, fb_roots=fb_roots,
                   fb_containers=containers, notes=tuple(notes))


def read(table: Table, readers: Readers | None = None) -> TableData:
    """Read a table. Reports its failure in `.error` rather than raising.

    `read` is what a listing wants -- one unreadable file must not take the
    listing down with it. `rows()` is what a caller wanting the data wants, and
    it raises.
    """
    if table.shape == SHAPE_BINARY:
        return _read_binary(table, readers or Readers())
    if table.shape == SHAPE_LUA:
        return _read_lua(table)
    if table.shape != SHAPE_JSON:
        return TableData(table, error=f"no reader for {table.shape} tables")
    try:
        with open(table.path, encoding="utf-8") as f:
            value = json.load(f)
    except (OSError, UnicodeDecodeError) as exc:
        return TableData(table, error=f"cannot read the file: {exc}")
    except json.JSONDecodeError as exc:
        return TableData(table, error=f"not valid JSON: {exc}")
    try:
        reader, row_list, wrapper = dispatch(value)
    except TableError as exc:
        return TableData(table, error=str(exc))
    return TableData(table, reader=reader, rows=tuple(row_list),
                     fields=fields(row_list), wrapper=wrapper)


def _read_lua(table: Table) -> TableData:
    """A Lua table constructor `lua-extract` already decompiled.

    Only reads. Decryption and unpacking are `lua-extract`'s, and a config tree
    on disk has been through both -- the same split `lua-decompile` makes.
    """
    from . import luatable
    try:
        with open(table.path, encoding="utf-8") as f:
            text = f.read()
    except OSError as exc:
        return TableData(table, error=f"cannot read the file: {exc}")
    except UnicodeDecodeError as exc:
        # Not replaced with U+FFFD. Bytes we cannot decode are bytes we did not
        # read, and substituting a placeholder reports them as content -- the
        # JSON reader four functions up says so and this one used to not.
        return TableData(table, error=f"not UTF-8: {exc}")
    try:
        value = luatable.parse(text)
    except luatable.LuaError as exc:
        return TableData(table, error=str(exc))
    payload, wrapper = unwrap(value)
    if not _tabular(payload):
        return TableData(table, error="not a table: this Lua file holds values, "
                                      "not rows")
    rows = list(payload.values())
    # Carried on every read, so the count is qualified wherever it is consumed
    # -- `census`, `diff`, `rows()` -- and not only in the listing. The
    # overstatement this warns about happens when somebody sums.
    return TableData(table, reader=READER_LUA, rows=tuple(rows),
                     fields=fields(rows), wrapper=wrapper,
                     partial=LUA_VARIANT_CAVEAT)


def _read_binary(table: Table, readers: Readers) -> TableData:
    """A blob, routed to whichever reader this project said claims it.

    A binary corpus can hold more than one framework -- one title's `res/` has
    Luban tables and another's has a FlatBuffers CMS library -- so the file that
    nothing claims says exactly that, rather than blaming whichever reader
    happened to be asked first.
    """
    claimed = readers.claims(table)
    if claimed == "both":
        return TableData(table, error=f"two readers claim {table.name!r}: it is in "
                                      f"the Luban schema's `tables` map and in "
                                      f"[tables] fb_roots; remove it from one")
    if claimed == READER_LUBAN:
        return _read_luban(table, readers)
    if claimed == READER_FB:
        return _read_flatbuffers(table, readers)
    configured = [name for name, on in
                  (("luban_schema", readers.luban_schema is not None),
                   ("fb_roots", bool(readers.fb_roots))) if on]
    if not configured:
        return TableData(table, error="no reader for binary tables until this "
                                      "project says what they are: set [tables] "
                                      "luban_schema (#59) or fb_roots (#62)")
    return TableData(table, error=f"nothing claims {table.name!r}: "
                                  f"{' and '.join(configured)} "
                                  f"{'do' if len(configured) > 1 else 'does'} "
                                  f"not list it")


FB_MAX_ROWS = 200_000       # a vector longer than this is reported, not silently cut
FB_MAX_DEPTH = 4            # nested tables inside a row, before "..."
FB_ROOT_FIELD = "#"         # `RootClass#Field` picks the vector when several fit


def _read_flatbuffers(table: Table, readers: Readers) -> TableData:
    """A FlatBuffers blob, decoded against the schema recovered from the game.

    What the project supplies is the part revenant cannot know: which root class
    a given `.bin` holds, and the generic wrapper names its CMS uses. Both are
    facts about one title -- the same split `fbread.py` was already making by
    hand, moved from a script into two config keys.
    """
    from . import flatbuffers as _fb
    schema = readers.fb_schema
    if schema is None:                        # `fb_root` is empty without one
        return TableData(table, error="[tables] fb_schema is not set")
    spec = readers.fb_root(table)
    root, _sep, wanted = spec.partition(FB_ROOT_FIELD)
    try:
        with open(table.path, "rb") as f:
            blob = f.read()
    except OSError as exc:
        return TableData(table, error=f"cannot read the file: {exc}")
    try:
        reader = _fb.Reader(blob, schema, containers=readers.fb_containers,
                            max_depth=FB_MAX_DEPTH, limit=FB_MAX_ROWS)
        decoded = reader.read(root)
    except KeyError as exc:
        return TableData(table, error=f"the schema has no class {exc}")
    except Exception as exc:                  # noqa: BLE001 - report, don't die
        return TableData(table, error=f"could not decode as {root!r}: {exc}")
    rows, problem = _fb_rows(decoded, wanted, root)
    if problem:
        return TableData(table, error=problem)
    # What the decoder could not settle -- an unnamed union pair, a missing
    # member list. Not an error: the rows are there and these say which parts
    # of them are less than they look.
    partial = "; ".join(reader.notes[:3]) if reader.notes else ""
    if len(reader.notes) > 3:
        partial += f"; and {len(reader.notes) - 3} more"
    # `read_vector` appends its "... N more" marker exactly when it cut the
    # vector, so the *length* decides this, not the look of the last element:
    # it shows `min(count, limit)` items plus at most that one marker, hence
    # `limit + 1` if and only if the vector was longer than the limit. Reading
    # the string instead would drop a real last row whose value happens to read
    # like the marker.
    if len(rows) == FB_MAX_ROWS + 1:
        partial = (f"only the first {FB_MAX_ROWS:,} rows were read; this table is "
                   f"longer than `table` reads in one go")
        rows = rows[:-1]
    return TableData(table, reader=READER_FB, rows=tuple(rows),
                     fields=fields(rows), partial=partial)


def _fb_rows(decoded: dict, wanted: str, root: str):
    """`(rows, problem)` -- the vector inside a decoded root that holds the rows.

    A CMS root is a table whose slots hold the item vectors, so which slot is
    "the rows" is a question about that title, not about FlatBuffers. One
    list-valued field answers it on its own; several do not, and guessing would
    pick a different table than the reader meant.
    """
    if not isinstance(decoded, dict):
        return [], f"{root} did not decode as a table"
    if wanted:
        value = decoded.get(wanted)
        if value is None:
            known = ", ".join(sorted(decoded)) or "nothing"
            return [], f"{root} has no field {wanted!r} (it has {known})"
        if not isinstance(value, list):
            return [], f"{root}.{wanted} is not a vector, so it is not rows"
        return _rows_or_values(value, f"{root}.{wanted}")
    holders = [k for k, v in decoded.items() if isinstance(v, list)]
    if len(holders) == 1:
        return _rows_or_values(decoded[holders[0]], f"{root}.{holders[0]}")
    if not holders:
        return [], f"no field of {root} holds a vector, so it has no rows"
    return [], (f"{len(holders)} fields of {root} hold vectors "
                f"({', '.join(sorted(holders))}); say which with "
                f"`{root}{FB_ROOT_FIELD}<field>`")


def _rows_or_values(vector: list, where: str):
    """`(rows, problem)` -- a vector of tables is rows; a vector of numbers is not.

    Said here rather than left to the census, which would otherwise report "its
    rows are values, not objects" about a field that was never rows to begin
    with. The reader picked the wrong vector, and that is what to tell them.
    """
    if vector and not any(isinstance(v, dict) for v in vector):
        return [], (f"{where} is a vector of values, not of rows "
                    f"({len(vector)} of them); name the vector that holds the rows")
    return vector, ""


def _read_luban(table: Table, readers: Readers) -> TableData:
    """A Luban blob, against the schema this project named."""
    schema = readers.luban_schema
    bean = readers.luban_bean(table)
    if schema is None or not bean:            # unreachable; narrows the type
        return TableData(table, error="[tables] luban_schema does not cover this file")
    from . import luban as _luban
    try:
        with open(table.path, "rb") as f:
            blob = f.read()
    except OSError as exc:
        return TableData(table, error=f"cannot read the file: {exc}")
    try:
        out = _luban.read_table(blob, schema, bean,
                                container=readers.luban_container)
    except _luban.LubanError as exc:
        return TableData(table, error=str(exc))
    # Rows came out and they are not to be trusted: the schema ran out before
    # the blob did, so everything after the missing field is shifted.
    return TableData(table, reader=READER_LUBAN, rows=out.rows,
                     fields=out.fields, error=misaligned(out))


# ── diff: what two tables actually disagree about ───────────────────────────
#
# Comparing tables across two titles has produced the wrong answer twice, in
# opposite directions, and both times the report looked confident:
#
#   * the same game with different codegen (`costId` against `CostId`) came back
#     as eight core tables "all different"; aligned, the currency table matched
#     row for row and the exchange ladder matched rung for rung;
#   * a field whose tag was never recovered rendered its bytes as hex strings,
#     so `[1]` met `["01"]` and the report said 929 rows differ. After decoding
#     the varint, all 929 rows were identical.
#
# The first is what `normalize_names` fixes. The second cannot be fixed here --
# it is a decoding problem -- but it must not be *reported* as content, so a
# column whose two sides hold different kinds of value comes out separately,
# marked, and is not counted among real differences.

class _Absent:
    """A field this row does not have -- distinct from one holding null.

    An object rather than a string: `"(absent)"` is a value a real table can
    hold, and a sentinel that compares equal to real data turns a genuine
    difference into a match.
    """

    def __repr__(self) -> str:
        return "(absent)"


MISSING = _Absent()

# The column a table of bare values gets, so rows that are not objects still
# compare rather than disappearing.
VALUE_FIELD = "(value)"


@dataclass(frozen=True)
class Change:
    key: object             # the row's key, or its index when nothing keys it
    field: str
    a: object
    b: object


@dataclass(frozen=True)
class Incomparable:
    """A column whose two sides are not the same kind of thing."""
    field: str
    rows: int               # rows where the two sides disagree in this column
    a_kinds: tuple = ()
    b_kinds: tuple = ()


@dataclass(frozen=True)
class Diff:
    key_field: str = ""     # "" when nothing identified a row and position was used
    only_in_a: tuple = ()
    only_in_b: tuple = ()
    fields_only_in_a: tuple = ()
    fields_only_in_b: tuple = ()
    changed: tuple = ()
    incomparable: tuple = ()
    same: int = 0           # rows present on both sides with nothing to report
    # Rows whose only disagreement is in a column nothing can compare. Not
    # "the same", which is what counting them as such would claim.
    undetermined: int = 0
    notes: tuple = ()


def show(value) -> str:
    """One value, short enough to read in a report. Same elision as `census`."""
    return _census_show(value)


def decode_warning(column: Incomparable) -> str:
    """Why a column's differences are not content, said once for every caller.

    The sentence this whole command exists for, so it lives with the data and
    not in one printer -- the same reason `misaligned` does.
    """
    return (f"{column.field}: A holds {'/'.join(column.a_kinds)}, B holds "
            f"{'/'.join(column.b_kinds)}; {column.rows} "
            f"{plural(column.rows, 'row')} differ here and are NOT counted as "
            f"content -- this reads as a decoding difference, not a content one")


def alignment(found: "Diff") -> str:
    """How rows were matched up, in words."""
    if found.key_field:
        return f"keyed on {found.key_field!r}"
    return ("no field identifies a row on both sides, so rows are matched by "
            "position")


def normalize_name(name: str) -> str:
    """A field name reduced to what two codegens agree on.

    `costId`, `CostId` and `cost_id` are one field written three ways. Case and
    separators are all that differ, so both go.
    """
    return "".join(c for c in str(name).lower() if c.isalnum())


def _textual(kind: str) -> bool:
    """Whether a value's shape is text, at whatever depth.

    The one distinction that matters for incomparability: an unrecovered tag
    renders its bytes as strings, so `[1]` meets `["01"]`. Everything else --
    `int` against `float`, `int` against `bool` -- is ordinary widening between
    two things that compare perfectly well, and calling those incomparable
    would hide real differences instead of decode noise.
    """
    return kind == "str" or (kind.startswith("list[") and set(
        kind[5:-1].split("|")) <= {"str", ""})


def _kind(value) -> str:
    """A value's shape, deep enough to tell `[1]` from `["01"]`."""
    if isinstance(value, (list, tuple)):
        inner = sorted({_kind(v) for v in value})
        return f"list[{'|'.join(inner)}]" if inner else "list[]"
    if isinstance(value, dict):
        return "object"
    if isinstance(value, bool):
        return "bool"
    return type(value).__name__


def key_field_for(rows_a, rows_b, fields_common) -> str:
    """The first common field that identifies a row on both sides, or "".

    Structural: present in every row and never repeated. Deliberately not "the
    one called id" -- reading meaning out of a field name is the kind of rule
    CONTEXT.md's bar keeps in the projects, and a table whose key is `sku` is as
    common as one whose key is `id`.
    """
    for name in fields_common:
        if all(_identifies(rows, name) for rows in (rows_a, rows_b)):
            return name
    return ""


def _identifies(rows, name) -> bool:
    seen = set()
    for row in rows:
        if not isinstance(row, dict) or name not in row:
            return False
        try:
            if row[name] in seen:
                return False
            seen.add(row[name])
        except TypeError:            # unhashable: cannot identify anything
            return False
    return True


def diff(rows_a, rows_b, *, key: str = "", normalize_names: bool = False) -> Diff:
    """Compare two tables' rows. Pure, so both traps can be pinned without files."""
    notes: list = []
    a_names = _name_map(rows_a, normalize_names, "A", notes)
    b_names = _name_map(rows_b, normalize_names, "B", notes)
    rows_a = [_renamed(r, a_names) for r in rows_a]
    rows_b = [_renamed(r, b_names) for r in rows_b]

    fields_a, fields_b = _fields_of(rows_a), _fields_of(rows_b)
    common = [f for f in fields_a if f in set(fields_b)]
    if key:
        key = normalize_name(key) if normalize_names else key
        for side, rows in (("A", rows_a), ("B", rows_b)):
            if rows and not _has(rows, key):
                # `or` would let one side key on the field and the other fall
                # back to row indexes, silently matching a key against an index.
                raise TableError(f"no row on side {side} has a field {key!r}")
        key_used = key
    else:
        # With one side empty there is nothing in common to key on, but the
        # other side's rows still have identities worth naming in the report.
        candidates = common if (rows_a and rows_b) else (fields_a or fields_b)
        key_used = key_field_for(rows_a, rows_b, candidates)

    index_a = _by_key(rows_a, key_used, "A", notes)
    index_b = _by_key(rows_b, key_used, "B", notes)
    only_a = tuple(k for k in index_a if k not in index_b)
    only_b = tuple(k for k in index_b if k not in index_a)
    shared = [k for k in index_a if k in index_b]

    # Which columns are not comparable at all, decided over the whole table
    # rather than row by row: one row of `[1]` against `["01"]` says nothing,
    # the same mismatch in 929 rows says the decoders disagree.
    # Incomparable is a narrow claim: one side holds text where the other holds
    # something else. That is what an unrecovered tag looks like. `int` against
    # `float` is not that -- it is two numbers that compare fine, and marking it
    # would suppress real differences, which is this ticket's own trap inverted.
    kinds_a = {f: _kinds_of(rows_a, f) for f in common}
    kinds_b = {f: _kinds_of(rows_b, f) for f in common}
    broken = set()
    for f in common:
        if not (kinds_a[f] and kinds_b[f]) or (kinds_a[f] & kinds_b[f]):
            continue
        text_a = all(_textual(k) for k in kinds_a[f])
        text_b = all(_textual(k) for k in kinds_b[f])
        if text_a != text_b:
            broken.add(f)

    changed, mismatch = [], {f: 0 for f in broken}
    same = undetermined = 0
    for k in shared:
        row_a, row_b = index_a[k], index_b[k]
        differing, suppressed = [], False
        for f in fields_a + tuple(f for f in fields_b if f not in set(fields_a)):
            va = row_a.get(f, MISSING)
            vb = row_b.get(f, MISSING)
            if va is not MISSING and vb is not MISSING and va == vb:
                continue
            if va is MISSING and vb is MISSING:
                continue
            if f in broken:
                mismatch[f] += 1
                suppressed = True
                continue
            differing.append(Change(key=k, field=f, a=va, b=vb))
        changed.extend(differing)
        if differing:
            continue
        # Neither the same nor different: its only disagreement is in a column
        # nothing can compare. Counting it as "the same" is the confident wrong
        # answer in the other direction.
        if suppressed:
            undetermined += 1
        else:
            same += 1
    incomparable = tuple(Incomparable(field=f, rows=mismatch[f],
                                      a_kinds=tuple(sorted(kinds_a[f])),
                                      b_kinds=tuple(sorted(kinds_b[f])))
                         for f in sorted(broken))
    return Diff(key_field=key_used, only_in_a=only_a, only_in_b=only_b,
                fields_only_in_a=tuple(f for f in fields_a if f not in set(fields_b)),
                fields_only_in_b=tuple(f for f in fields_b if f not in set(fields_a)),
                changed=tuple(changed), incomparable=incomparable,
                same=same, undetermined=undetermined, notes=tuple(notes))


def _name_map(rows, normalize: bool, side: str, notes: list) -> dict:
    """`{original: compared-as}`. Collisions are reported, never merged silently."""
    if not normalize:
        return {}
    out, seen = {}, {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        for name in row:
            if name in out:
                continue
            norm = normalize_name(name)
            if norm in seen and seen[norm] != name:
                notes.append(f"side {side}: {name!r} normalises onto {seen[norm]!r}, "
                             f"which is already taken, so {name!r} was compared "
                             f"under its own name and the two stayed apart")
                continue
            seen[norm] = name
            out[name] = norm
    return out


def _renamed(row, names: dict):
    if not names or not isinstance(row, dict):
        return row
    return {names.get(k, k): v for k, v in row.items()}


def _fields_of(rows) -> tuple:
    """`fields()`, plus the synthetic column a table of bare values gets."""
    out = fields(rows)
    if any(not isinstance(r, dict) for r in rows):
        out = out + (VALUE_FIELD,) if VALUE_FIELD not in out else out
    return out


def _has(rows, name) -> bool:
    return any(isinstance(r, dict) and name in r for r in rows)


def _kinds_of(rows, field_name) -> set:
    return {_kind(r[field_name]) for r in rows
            if isinstance(r, dict) and field_name in r and r[field_name] is not None}


def _by_key(rows, key_used: str, side: str, notes: list) -> dict:
    """`{key: row}`, or by position when no field keys the table.

    Never a mix of the two. A row missing the key would otherwise get an integer
    index and be matched against the other side's row whose key *is* that
    integer, which is a comparison of two unrelated rows reported as a
    difference.
    """
    out, dropped, keyless = {}, 0, 0
    for i, row in enumerate(rows):
        if not isinstance(row, dict):
            # Rows that are values rather than objects: a `json-rows` table can
            # be an array of scalars. Compared by position, so they are not
            # dropped -- silence about them is what CONTEXT.md's "empty" versus
            # "unreadable" rule forbids.
            out[i] = {VALUE_FIELD: row}
            continue
        if not key_used:
            out[i] = row
            continue
        if key_used not in row:
            keyless += 1
            continue
        try:
            if row[key_used] in out:
                dropped += 1
            out[row[key_used]] = row
        except TypeError:
            raise TableError(
                f"side {side}: {key_used!r} holds {type(row[key_used]).__name__} "
                f"values, which cannot identify a row") from None
    if dropped:
        notes.append(f"side {side}: {dropped} rows share a {key_used!r} with an "
                     f"earlier row and only the last of each was compared")
    if keyless:
        notes.append(f"side {side}: {keyless} rows have no {key_used!r} and were "
                     f"left out rather than matched by position")
    return out


# ── census: what is actually in a field ─────────────────────────────────────

CENSUS_TOP = 5          # values shown per field before truncating
CENSUS_WIDTH = 40       # characters of one rendered value before eliding


@dataclass(frozen=True)
class FieldStat:
    name: str
    rows: int = 0        # rows in the table
    present: int = 0     # rows where the key is there at all
    null: int = 0        # of those, how many hold nothing
    distinct: int = 0
    top: tuple = ()      # ((rendered value, count), ...), commonest first
    truncated: int = 0   # distinct values not in `top`

    @property
    def fill(self) -> float:
        return self.present / self.rows if self.rows else 0.0

    @property
    def filled(self) -> str:
        """The fill column, phrased here rather than at each printer."""
        return f"{self.present}/{self.rows} {self.fill * 100:3.0f}%"

    @property
    def values(self) -> str:
        """The value column, including what it had to leave out."""
        text = " · ".join(f"{value} ×{count}" for value, count in self.top)
        if self.truncated:
            text = f"{text}  (+{self.truncated} more)" if text \
                else f"(+{self.truncated} more)"
        # Counting is exact and the display is elided, so two distinct values
        # can print the same. Better to say they are two than to leave a reader
        # deciding whether the census repeated itself.
        rendered = [value for value, _count in self.top]
        if len(set(rendered)) != len(rendered):
            text += "  (values shown alike differ past the cut)"
        return text


def census(rows, top: int = CENSUS_TOP) -> tuple:
    """Per field: how many rows have it, how many values it takes, which recur.

    The first thing done to every unfamiliar table, and across 53 economy notes
    it was written out by hand each time -- most of the 60 hand-rolled
    `Counter`s. It is also how a column gets read correctly: a `cost` where one
    value covers 652 rows and the rest are eight-digit numbers is a resource id,
    not a quantity, and the distribution says so at a glance where the field
    name does not.

    Facts only, no verdicts. It reports what the values are and how they are
    spread; deciding that a column is an id, or dead, or wrong, is the reader's
    and belongs in a note.
    """
    total = len(rows)
    # Clamped, not trusted: Python's `ranked[:-1]` drops the last element rather
    # than clamping, so a negative would print every value on one line -- the
    # one thing this command promises not to do.
    top = max(0, top)
    out = []
    for name in fields(rows):
        present = null = 0
        counts: dict = {}
        shown: dict = {}
        for row in rows:
            if not isinstance(row, dict) or name not in row:
                continue
            present += 1
            value = row[name]
            if value is None:
                null += 1
            key = _census_key(value)
            counts[key] = counts.get(key, 0) + 1
            shown.setdefault(key, _census_show(value))
        ranked = sorted(counts.items(), key=lambda kv: (-kv[1], shown[kv[0]]))
        head = tuple((shown[key], count) for key, count in ranked[:top])
        out.append(FieldStat(
            name=name, rows=total, present=present, null=null,
            distinct=len(counts), top=head,
            # From what was actually emitted, so the count and the list in one
            # line cannot disagree about the same field.
            truncated=len(counts) - len(head),
        ))
    return tuple(out)


def _census_key(value):
    """A key that separates values a reader would want separated.

    Typed, because Python does not separate them on its own: `True == 1` and
    they hash alike, so a flag column and a count column merge into one row of
    output with no sign that they were two. `1` and `1.0` likewise -- and a
    column holding both is a fact about the export worth seeing.

    Lists and objects are keyed by their **full** rendering: protobuf-JSON and
    Luban rows are full of them, and a census that raises on the first one is no
    use on the corpus it was written for. Full, because keying on the elided
    display text instead merges any two structures sharing a 39-character prefix
    -- two different drop tables become one value seen twice, and `distinct`
    comes out quietly too low. Eliding is a display concern and stays one.
    """
    if isinstance(value, (str, int, float, bool)) or value is None:
        return type(value).__name__, value
    return "json", _dump(value)


def _dump(value) -> str:
    try:
        return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)
    except (TypeError, ValueError):
        return str(value)


def _census_show(value) -> str:
    """One value, short enough that a field stays one line.

    Strings keep their quotes: `"31"` and `31` are different findings about a
    column, and rendering both as `31` hides the one worth having.
    """
    if value is None:
        text = "null"
    elif isinstance(value, str):
        text = json.dumps(value, ensure_ascii=False)
    elif isinstance(value, bool):
        text = "true" if value else "false"
    elif isinstance(value, (int, float)):
        text = repr(value)
    else:
        text = _dump(value)
    if len(text) > CENSUS_WIDTH:
        return text[:CENSUS_WIDTH - 1] + "…"
    return text


def misaligned(decoded) -> str:
    """Why leftover bytes matter, said once for every caller that reports them.

    Nonzero `trailing` is the only signal there is that a Luban schema is short
    a field: the rows still decode, and every one after the gap is shifted. Both
    the listing and `luban-read` say it in these words.
    """
    if not decoded.trailing:
        return ""
    return (f"{decoded.trailing} bytes were left over -- the schema for "
            f"{decoded.bean!r} is short a field, so these rows are misaligned")


def project_root_of(path: str) -> str:
    """The project a path belongs to: the nearest ancestor holding the marker.

    Cross-project comparison needs it. A table in another title reads with
    *that* title's `[tables]` keys -- its schema, its container, its roots -- and
    reading it with the ambient project's would decode one game's bytes against
    another game's schema, which produces rows rather than an error.
    """
    from . import config
    cur = os.path.dirname(os.path.abspath(path))
    while True:
        if os.path.exists(os.path.join(cur, config.PROJECT_MARKER)):
            return cur
        parent = os.path.dirname(cur)
        if parent == cur:
            return os.path.dirname(os.path.abspath(path))
        cur = parent


def resolve_any(handle) -> Table:
    """The `Table` a handle names -- resolved, not read.

    What `read_any` does up to the point of opening the file. A caller that
    wants the table's *name*, corpus or row class has no business decoding
    200k rows to get them, and a file whose bytes will not decode still has a
    name worth answering about.
    """
    if isinstance(handle, Table):
        return handle
    text = str(handle)
    if os.path.isfile(text):
        return resolve(text, root=project_root_of(text))
    return resolve(text, claimed=claimed_names())


def read_any(handle) -> TableData:
    """Read a table named by a path, from whichever project owns that path."""
    if isinstance(handle, Table):
        root = project_root_of(handle.path)
        return read(handle, readers_for(root))
    text = str(handle)
    if os.path.isfile(text):
        root = project_root_of(text)
        return read(resolve(text, root=root), readers_for(root))
    return read(resolve(text, claimed=claimed_names()), readers_for())


def rows(table, root: str | None = None, cfg: dict | None = None) -> list:
    """The rows of a table, wrapper key already off.

    Takes a `Table`, a path, or the name a note calls it by. The rows are the
    values of an id map, without the id folded in: the key is the map's, and
    deciding it is really the row's `id` would be a naming rule about one title.

    A path into another project is read with *that* project's keys, the same as
    `read_any` -- one caller getting this right and the rest not is how a note
    ends up decoding one game's bytes against another game's schema.
    """
    if root is None and cfg is None and os.path.isfile(str(table)):
        data = read_any(str(table))
    else:
        readers = readers_for(root=root, cfg=cfg)
        data = read(resolve(table, root=root, cfg=cfg,
                            claimed=claimed_names(root, cfg)), readers)
    if data.error:
        raise TableError(f"{data.table.name}: {data.error}")
    return list(data.rows)


def resolve(table, root: str | None = None, cfg: dict | None = None,
            claimed: set | None = None) -> Table:
    """A `Table` from a handle, a path, or a name. Ambiguous names raise."""
    if isinstance(table, Table):
        return table
    text = str(table)
    if os.path.isfile(text):
        return _table_at(os.path.abspath(text), root)
    found = discover(root, cfg=cfg, claimed=claimed)
    hits = [t for t in found.tables() if t.name == text]
    if len(hits) == 1:
        return hits[0]
    if not hits:
        raise TableError(f"no table named {text!r} in "
                         f"{len(found.corpora)} corpus/corpora "
                         f"(`revenant table list` shows what there is)")
    where = ", ".join(t.corpus for t in hits)
    raise TableError(f"{len(hits)} tables are named {text!r} ({where}); "
                     f"pass the path instead")


def _table_at(path: str, root: str | None) -> Table:
    """A `Table` for a path handed in directly. Unknown extensions raise.

    The same `EXTENSIONS` answer the sweep uses, and the same verdict: a file
    the sweep would not have picked up is not silently called a binary table
    here, because that turns "this is not a table file" into "we have no reader
    for it yet", which is a different and much more interesting claim.
    """
    from . import config
    ext = os.path.splitext(path)[1].lower()
    shape = EXTENSIONS.get(ext)
    if shape is None:
        known = ", ".join(sorted(EXTENSIONS))
        raise TableError(f"{os.path.basename(path)}: {ext or 'no extension'} is not a "
                         f"table file ({known})")
    directory = os.path.dirname(path)
    base = os.path.abspath(root or config.workspace_root())
    rel = os.path.relpath(directory, base)
    if rel.startswith(os.pardir):
        rel = directory
    return Table(name=os.path.splitext(os.path.basename(path))[0], path=path,
                 corpus=rel, shape=shape)


# ── discovery ───────────────────────────────────────────────────────────────

def configured_dirs(cfg: dict) -> list:
    """`[tables] dirs` from revenant.toml. Empty when unset."""
    section = (cfg or {}).get("tables") or {}
    raw = section.get("dirs") or []
    if isinstance(raw, str):
        raw = [raw]
    return [str(d) for d in raw]


def discover(root: str | None = None, cfg: dict | None = None,
             claimed: set | None = None) -> Discovery:
    """The table corpora this project has.

    Configured directories replace the sweep rather than adding to it -- a
    project that says where its tables are is answering the question, and a
    sweep running anyway would answer it a second way. But the sweep is the
    default and the configuration is optional: #50's lesson is that a feature
    depending on someone remembering to configure it does not get used.
    """
    from . import config
    root = os.path.abspath(root or config.workspace_root())
    # This root's configuration, not the ambient project's: a caller that named
    # a directory is asking about that project, and answering with another
    # project's `[tables] dirs` would send the sweep somewhere unrelated.
    if cfg is None:
        cfg = config.load_config(root)
    if claimed is None:
        claimed = claimed_names(root, cfg)
    named = configured_dirs(cfg)
    if named:
        return _configured(root, named, claimed)
    return _sweep(root, claimed)


def _configured(root: str, named: list, claimed: set) -> Discovery:
    corpora, missing, gaps = [], [], []
    for rel in named:
        directory = rel if os.path.isabs(rel) else os.path.join(root, rel)
        if not os.path.isdir(directory):
            missing.append(f"{rel}: [tables] dirs points at it, and it is not there")
            continue
        listing = _listdir(directory)
        gaps.extend(listing.gap(rel))
        corpus = _corpus_from(root, directory, listing.files,
                              SOURCE_CONFIGURED, claimed)
        if corpus is not None:
            corpora.append(corpus)
        else:
            missing.append(f"{rel}: [tables] dirs points at it, and it holds no tables")
    return Discovery(tuple(corpora), tuple(gaps), tuple(missing))


def _sweep(root: str, claimed: set) -> Discovery:
    """Breadth-first over the extraction roots, under three caps.

    Every cap that bit is reported, and so is every directory that would not
    open. A query that silently covered less than it was asked to reads exactly
    like one that found nothing there.
    """
    corpora, gaps = [], []
    opened, deep = 0, 0
    capped = False
    for rel_root in CORPUS_ROOTS:
        start = os.path.join(root, rel_root)
        if not os.path.isdir(start):
            continue
        queue = [(start, 0)]
        while queue:
            directory, depth = queue.pop(0)
            if opened >= MAX_DIRS:
                capped = True
                break
            opened += 1
            listing = _listdir(directory)
            gaps.extend(listing.gap(os.path.relpath(directory, root)))
            corpus = _corpus_from(root, directory, listing.files,
                                  SOURCE_FOUND, claimed)
            if corpus is not None:
                corpora.append(corpus)
            if depth >= MAX_DEPTH:
                deep += len(listing.subdirs)
                continue
            queue.extend((os.path.join(directory, n), depth + 1) for n in listing.subdirs)
        if capped:
            break
    if capped:
        gaps.append(f"the sweep stopped after opening {MAX_DIRS} directories; "
                    f"set [tables] dirs to point at the ones that matter")
    if deep:
        gaps.append(f"depth cap: {deep} {plural(deep, 'directory', 'directories')} more than "
                    f"{MAX_DEPTH} levels under {'/, '.join(CORPUS_ROOTS)}/ went unopened; "
                    f"set [tables] dirs to reach them")
    corpora.sort(key=lambda c: c.rel)
    return Discovery(tuple(corpora), tuple(gaps), ())


@dataclass(frozen=True)
class _Listing:
    files: tuple = ()        # (name, path) for files, sorted, capped
    subdirs: tuple = ()      # directory names worth descending into, sorted
    over: int = 0            # entries dropped by MAX_ENTRIES
    error: str = ""          # why the directory would not open

    def gap(self, rel: str) -> list:
        """The lines this listing owes the caller. Empty when it saw everything."""
        if self.error:
            return [f"{rel}: could not be read ({self.error})"]
        if self.over:
            return [f"{rel}: {self.over} entries past the first {MAX_ENTRIES} "
                    f"were not looked at"]
        return []


def _listdir(directory: str) -> _Listing:
    """One directory, read once.

    `scandir` already knows file-or-directory from the read itself, so this
    keeps that answer instead of handing back names for the caller to `stat`
    again -- on a real `res/` that second pass was the whole cost of the sweep.

    Names are collected in full and sorted before the cap applies. Capping
    during the read would leave *which* entries survive up to filesystem order,
    and a listing that changes between two runs over an unchanged directory is
    not a listing anyone can act on.
    """
    files, subdirs = [], []
    try:
        with os.scandir(directory) as it:
            for entry in it:
                try:
                    if entry.is_dir():
                        if entry.name not in SKIP_DIRS and not entry.name.startswith("."):
                            subdirs.append(entry.name)
                    elif entry.is_file():
                        files.append((entry.name, entry.path))
                except OSError:
                    continue
    except OSError as exc:
        return _Listing(error=str(exc))
    files.sort()
    subdirs.sort()
    over = max(0, len(files) - MAX_ENTRIES)
    return _Listing(tuple(files[:MAX_ENTRIES]), tuple(subdirs), over)


def _corpus_from(root: str, directory: str, files: tuple, source: str,
                 claimed: 'set | frozenset' = frozenset()):
    """A `Corpus` for this directory, or None when it holds no tables.

    A found corpus needs one file that sniffs as JSON, or one this project has
    already named as a table (`claimed`). Otherwise the Lua and binary shapes
    are picked up beside something readable but do not qualify a directory on
    their own: `res/` holds hundreds of thousands of extracted TextAssets, and a
    folder of `.bytes` is extraction output until something says otherwise. A
    configured directory is taken at its word.
    """
    entries = []
    rel = os.path.relpath(directory, root)
    for name, path in files:
        shape = EXTENSIONS.get(os.path.splitext(name)[1].lower())
        if shape is None:
            continue
        entries.append(Table(name=os.path.splitext(name)[0], path=path,
                             corpus=rel, shape=shape))
    if not entries:
        return None
    if (source == SOURCE_FOUND and not _sniffs_as_json(entries)
            and not _sniffs_as_lua(entries)
            and not any(e.name in claimed for e in entries)):
        return None
    return Corpus(rel=rel, path=directory, tables=tuple(entries), source=source)


# What a Lua config file looks like in its first few hundred bytes: a table
# holding tables, and no code. `lua/<version>/` is the whole decompiled game,
# so a directory of `.lua` is gameplay source until something in it has that
# shape -- and it is a shape, not a name.
#
# Both halves are needed. The nested constructor alone matches any class with a
# table constant (`UIPanel.LAYERS = { hud = { z = 1 } }`), which was listed as a
# two-row table; `function` and `require` are what say the file is behaviour.
_LUA_NESTED = re.compile(r"\{[^{}]{0,400}?\{", re.S)
_LUA_CODE = re.compile(r"\b(?:function|require)\b")

# One title ships 62 `OrderFixedConfig_*.lua` and the game loads 47 of them;
# summing every file overstates the rows by 34%. Which ones load is a fact
# about that game's loader, so the count says what it counted.
LUA_VARIANT_CAVEAT = (
    "Lua rows are counted per file. A title that ships variants of one table "
    "as several files loads only some of them, and which is a fact about its "
    "loader -- so this is a count of files read, not of loadable tables.")


def _sniffs_as_lua(entries: list) -> bool:
    """Whether any of the first few Lua files opens like a table of rows.

    A prefix read, not a parse, the same as `_sniffs_as_json`: this decides
    whether a directory is worth listing, and `read()` decides what each file
    actually is.
    """
    looked = 0
    for table in entries:
        if table.shape != SHAPE_LUA:
            continue
        if looked >= SNIFF_FILES:
            break
        looked += 1
        try:
            with open(table.path, encoding="utf-8", errors="replace") as f:
                head = f.read(SNIFF_BYTES * 4)
        except OSError:
            continue
        if _LUA_NESTED.search(head) and not _LUA_CODE.search(head):
            return True
    return False


def _sniffs_as_json(entries: list) -> bool:
    """Whether any of the first few JSON files opens like JSON.

    A prefix read, not a parse: this decides whether a directory is worth
    listing, and `status` calls it. What each file actually *is* is decided in
    `read()`, where the file is parsed and the answer is printed.
    """
    looked = 0
    for table in entries:
        if table.shape != SHAPE_JSON:
            continue
        if looked >= SNIFF_FILES:
            break
        looked += 1
        try:
            with open(table.path, "rb") as f:
                head = f.read(SNIFF_BYTES).lstrip()
        except OSError:
            continue
        if head[:1] in (b"{", b"["):
            return True
    return False


def plural(count: int, one: str, many: str = "") -> str:
    """`one` when there is one of them, else `many` (default: `one` + s)."""
    return one if count == 1 else (many or one + "s")


def tally(found: Discovery) -> str:
    """"N files in M corpora" -- the size of a corpus, phrased once.

    Files, not tables, and it says so. Discovery does not parse: `status` runs
    on every visit and a real corpus is thousands of files, so how many of them
    are really tables is a question only `table list` has opened them to answer.
    Both callers say it in these words so the two can never quietly differ.
    """
    n, m = len(found.tables()), len(found.corpora)
    return (f"{n} {plural(n, 'file')} in "
            f"{m} {plural(m, 'corpus', 'corpora')}")


def summary(found: Discovery) -> str:
    """One line for `revenant status`: how much there is, and where."""
    tables = found.tables()
    if not tables:
        return "none found (point [tables] dirs at them if they are elsewhere)"
    where = ", ".join(c.rel for c in found.corpora[:3])
    if len(found.corpora) > 3:
        where += f", +{len(found.corpora) - 3} more"
    return f"{tally(found)} ({where})  (revenant table list reads them)"
