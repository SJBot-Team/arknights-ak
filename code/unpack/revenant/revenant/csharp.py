"""DiffableCs C# metadata extraction.

Parses the decompiled C# stub files produced by tools like il2cppdumper
to extract type metadata, field layouts (with offsets), and method signatures.

Based on match3-core-sketch csharp_metadata.py methodology.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass

from .indices import (
    VersionData,
    first_index_match,
    normalize_rva,
    resolve_version,
    split_qualified_class,
)


@dataclass(frozen=True)
class FieldInfo:
    """A C# field with its memory offset."""
    owner: str
    name: str
    type_name: str
    offset: int
    file: str
    line: int
    const_value: str = ""   # literal for `const`/static-readonly fields, if present


@dataclass(frozen=True)
class MethodInfo:
    """A C# method."""
    owner: str
    name: str
    return_type: str
    signature: str
    line: int


@dataclass(frozen=True)
class TypeMetadata:
    """Metadata for a C# type, including its fields and methods."""
    type_name: str
    namespace: str
    class_name: str
    base_type: str
    file: str
    fields: tuple[FieldInfo, ...]
    methods: tuple[MethodInfo, ...]
    kind: str = "class"                              # class | struct | interface | enum
    enum_members: tuple[tuple[str, str], ...] = ()   # (name, value) for enums
    attributes: tuple[str, ...] = ()                 # type-level attributes, e.g. LuaCallCSharp


# Regex patterns for parsing DiffableCs output
NAMESPACE_RE = re.compile(r"^\s*namespace\s+(?P<namespace>[\w.]+)\s*;")
CLASS_RE = re.compile(
    r"^\s*(?:(?:public|private|internal|protected|abstract|sealed|static|partial)\s+)*"
    r"(?:class|struct|interface)\s+(?P<name>[A-Za-z_<>][\w`<>]*)"
    r"(?:\s*:\s*(?P<bases>[^{]+))?"
)
FIELD_OFFSET_RE = re.compile(r'FieldOffset\(Offset\s*=\s*"(?P<offset>0x[0-9A-Fa-f]+|\d+)"\)')
ADDRESS_RE = re.compile(
    r'\[Address\(RVA\s*=\s*"0x(?P<rva>[0-9A-Fa-f]+)".*?Length\s*=\s*"(?P<length>0x[0-9A-Fa-f]+|\d+)"\)\]'
)
ENUM_RE = re.compile(
    r"^\s*(?:(?:public|private|internal|protected)\s+)*enum\s+(?P<name>[A-Za-z_]\w*)"
    r"(?:\s*:\s*(?P<base>[\w.]+))?"
)
ENUM_MEMBER_RE = re.compile(r"^\s*(?P<name>[A-Za-z_]\w*)\s*=\s*(?P<value>-?\w[\w<x]*)\s*,?\s*$")
ATTRIBUTE_RE = re.compile(r"^\s*\[(?P<attr>[A-Za-z_][\w.]*)")
CONST_VALUE_RE = re.compile(r"=\s*(?P<value>.+?)\s*;\s*(?://.*)?$")
COMMENT_OFFSET_RE = re.compile(r"//\s*Field offset:\s*(?P<offset>0x[0-9A-Fa-f]+|\d+)")
BACKING_FIELD_RE = re.compile(r"^<(?P<property>.+)>k__BackingField$")
METHOD_DECL_RE = re.compile(
    r"^\s*(?P<prefix>(?:(?:public|private|internal|protected|override|virtual|abstract|static|sealed|readonly|extern)\s+)*)"
    r"(?P<return>[A-Za-z_][\w.`<>?,\[\]]*)\s+"
    r"(?P<name>[A-Za-z_][\w.<>]*)\s*"
    r"\((?P<params>[^)]*)\)\s*\{"
)

FIELD_MODIFIERS = {
    "public", "private", "protected", "internal",
    "readonly", "static", "const", "volatile", "new", "unsafe",
}


# ── Helpers ─────────────────────────────────────────────────────────────────

def diffablecs_root(vd: VersionData) -> str:
    """Return the DiffableCs root directory for a version."""
    # Try cpp2il_out/DiffableCs first (standard cpp2il output layout)
    cpp2il_path = os.path.join(vd.root, "cpp2il_out", "DiffableCs")
    if os.path.isdir(cpp2il_path):
        return cpp2il_path
    # Fallback to legacy path
    return os.path.join(vd.root, "DiffableCs", "Assembly-CSharp")


def cs_path_for_entry(vd: VersionData, entry_file: str) -> str:
    """Absolute path for a DiffableCs entry file."""
    return os.path.join(diffablecs_root(vd), entry_file)


def _field_name(raw_name: str) -> str:
    m = BACKING_FIELD_RE.match(raw_name)
    return m.group("property") if m else raw_name


def _parse_field_declaration(line: str) -> tuple[str, str, str] | None:
    declaration = line.split("//", 1)[0].strip()
    if ";" not in declaration:
        return None
    declaration = declaration.split(";", 1)[0].strip()
    if "=" in declaration:
        declaration = declaration.split("=", 1)[0].strip()
    if not declaration:
        return None
    parts = declaration.split()
    while parts and parts[0] in FIELD_MODIFIERS:
        parts.pop(0)
    if len(parts) < 2:
        return None
    raw_name = parts[-1].strip()
    type_name = " ".join(parts[:-1]).strip()
    if not raw_name:
        return None
    return type_name, raw_name, _field_name(raw_name)


def _parse_method_declaration(line: str) -> tuple[str, str, str] | None:
    if "(" not in line or ")" not in line or "{" not in line:
        return None
    if any(line.lstrip().startswith(p) for p in ("if ", "for ", "while ", "switch ", "catch ")):
        return None
    m = METHOD_DECL_RE.match(line)
    if not m:
        return None
    name = m.group("name")
    if name in {"get", "set", "add", "remove"}:
        return None
    return m.group("return"), name, line.strip()


# ── Type Metadata ──────────────────────────────────────────────────────────

_TYPE_METADATA_CACHE: dict[tuple[str, str], TypeMetadata | None] = {}


def _find_cs_file(vd: VersionData, type_name: str) -> tuple[str | None, str | None]:
    """Find the DiffableCs file for a qualified type name."""
    ns, cls = split_qualified_class(type_name)
    # Try direct path
    if ns:
        rel = os.path.join(*ns.split("."), cls + ".cs")
    else:
        rel = cls + ".cs"
    path = os.path.join(diffablecs_root(vd), rel)
    if os.path.exists(path):
        return path, None

    # Search through rva_index for the file path
    for entry in vd.rva_index.values():
        if entry.get("class") == type_name:
            path2 = cs_path_for_entry(vd, entry["file"])
            if os.path.exists(path2):
                return path2, entry["file"]
    return None, None


def parse_type_metadata(vd: VersionData, type_name: str) -> TypeMetadata | None:
    """Parse type metadata from DiffableCs C# files."""
    key = (vd.root, type_name)
    if key in _TYPE_METADATA_CACHE:
        return _TYPE_METADATA_CACHE[key]

    file_path, _ = _find_cs_file(vd, type_name)
    if not file_path:
        _TYPE_METADATA_CACHE[key] = None
        return None

    try:
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
    except OSError:
        _TYPE_METADATA_CACHE[key] = None
        return None

    enum_meta = _parse_enum(lines, type_name, file_path)
    if enum_meta is not None:
        _TYPE_METADATA_CACHE[key] = enum_meta
        return enum_meta

    namespace = ""
    class_name = split_qualified_class(type_name)[1]
    base_type = ""
    fields: list[FieldInfo] = []
    methods: list[MethodInfo] = []
    attributes: list[str] = []
    pending_attrs: list[str] = []
    kind = "class"
    started = False
    opened = False
    brace_depth = 0
    pending_offset: int | None = None
    pending_line = 0

    for idx, line in enumerate(lines, start=1):
        ns_match = NAMESPACE_RE.match(line)
        if ns_match:
            namespace = ns_match.group("namespace")

        if not started:
            attr_match = ATTRIBUTE_RE.match(line)
            if attr_match:
                pending_attrs.append(attr_match.group("attr"))
            cls_match = CLASS_RE.match(line)
            if not cls_match:
                continue
            class_name = cls_match.group("name")
            kw = line.lstrip().split()
            kind = next((k for k in ("interface", "struct", "class") if k in kw), "class")
            bases = cls_match.group("bases") or ""
            first_base = bases.split(",", 1)[0].strip()
            if first_base:
                base_type = first_base
            attributes = pending_attrs
            started = True

        brace_depth += line.count("{") - line.count("}")
        if brace_depth > 0:
            opened = True
        if not started or brace_depth < 1:
            if started and opened and brace_depth <= 0:
                break
            continue

        if brace_depth == 1:
            # const / static-readonly fields carry their literal inline and use
            # a `//Field offset:` comment (no [FieldOffset] attribute).
            code0 = line.split("//", 1)[0]
            if ("=" in code0 and ";" in code0
                    and (" const " in f" {code0} " or "readonly" in code0)):
                parsed_c = _parse_field_declaration(line)
                cm = CONST_VALUE_RE.search(code0)
                if parsed_c and cm:
                    type_t, _raw, clean_name = parsed_c
                    co = COMMENT_OFFSET_RE.search(line)
                    fields.append(FieldInfo(
                        owner=type_name, name=clean_name, type_name=type_t,
                        offset=int(co.group("offset"), 0) if co else 0,
                        file=file_path, line=idx, const_value=cm.group("value").strip(),
                    ))
                    pending_offset = None
                    continue

            ofs_match = FIELD_OFFSET_RE.search(line)
            if ofs_match:
                pending_offset = int(ofs_match.group("offset"), 0)
                pending_line = idx
                continue

            if pending_offset is not None:
                parsed = _parse_field_declaration(line)
                if parsed:
                    type_t, raw_name, clean_name = parsed
                    cval = ""
                    code = line.split("//", 1)[0]
                    if " const " in f" {code} " or "readonly" in code:
                        cm = CONST_VALUE_RE.search(code)
                        if cm:
                            cval = cm.group("value").strip()
                    fields.append(FieldInfo(
                        owner=type_name,
                        name=clean_name,
                        type_name=type_t,
                        offset=pending_offset,
                        file=file_path,
                        line=idx,
                        const_value=cval,
                    ))
                    pending_offset = None
                elif idx - pending_line > 4:
                    pending_offset = None

            parsed_method = _parse_method_declaration(line)
            if parsed_method:
                ret, mname, sig = parsed_method
                methods.append(MethodInfo(
                    owner=type_name,
                    name=mname,
                    return_type=ret,
                    signature=sig,
                    line=idx,
                ))

    full_type = f"{namespace}.{class_name}" if namespace else class_name
    result = TypeMetadata(
        type_name=full_type,
        namespace=namespace,
        class_name=class_name,
        base_type=base_type,
        file=file_path,
        fields=tuple(fields),
        methods=tuple(methods),
        kind=kind,
        attributes=tuple(attributes),
    )
    _TYPE_METADATA_CACHE[key] = result
    return result


def _parse_enum(lines: list[str], type_name: str, file_path: str) -> TypeMetadata | None:
    """If the file declares an enum, parse its members; else return None."""
    namespace = ""
    pending_attrs: list[str] = []
    for idx, line in enumerate(lines):
        ns_match = NAMESPACE_RE.match(line)
        if ns_match:
            namespace = ns_match.group("namespace")
        attr_match = ATTRIBUTE_RE.match(line)
        if attr_match:
            pending_attrs.append(attr_match.group("attr"))
        em = ENUM_RE.match(line)
        if not em:
            if CLASS_RE.match(line):
                return None  # a class/struct/interface, not an enum
            continue
        name = em.group("name")
        base = em.group("base") or "int"
        members: list[tuple[str, str]] = []
        for body in lines[idx + 1:]:
            mm = ENUM_MEMBER_RE.match(body)
            if mm:
                members.append((mm.group("name"), mm.group("value")))
            elif "}" in body:
                break
        full = f"{namespace}.{name}" if namespace else name
        return TypeMetadata(
            type_name=full, namespace=namespace, class_name=name,
            base_type=base, file=file_path, fields=(), methods=(),
            kind="enum", enum_members=tuple(members), attributes=tuple(pending_attrs),
        )
    return None


def enum_members(type_name: str, version: str = "") -> list[tuple[str, str]]:
    """Return (name, value) pairs for an enum type, or [] if not an enum."""
    vd = resolve_version(version or None)
    meta = parse_type_metadata(vd, type_name)
    return list(meta.enum_members) if meta and meta.kind == "enum" else []


def fields_for_type(
    type_name: str,
    version: str = "",
    *,
    include_bases: bool = True,
) -> dict[int, FieldInfo]:
    """Return a field-offset map for a DiffableCs type."""
    vd = resolve_version(version or None)
    fields: dict[int, FieldInfo] = {}
    seen: set[str] = set()

    def visit(current: str) -> None:
        if not current or current in seen:
            return
        seen.add(current)
        meta = parse_type_metadata(vd, current)
        if not meta:
            return
        if include_bases and meta.base_type:
            visit(meta.base_type)
        for f in meta.fields:
            fields[f.offset] = f

    visit(type_name)
    return fields


def methods_for_type(
    type_name: str,
    version: str = "",
) -> list[MethodInfo]:
    """Return methods for a type from DiffableCs."""
    vd = resolve_version(version or None)
    meta = parse_type_metadata(vd, type_name)
    if not meta:
        return []
    return list(meta.methods)


# ── the managed source tree: list / get / grep / refs ───────────────────────
#
# Four of the nine titles end with their business logic as C# *text*: two ship
# HybridCLR hot-update assemblies, two ship IFix patches, and in both cases what
# a reader finally has is a directory of `.cs`. The Lua side has had five
# commands for that shape since the start (`lua-list` / `lua-get` / `lua-grep` /
# `lua-refs` / `lua-bridge`); the C# side had none, so reading it meant dropping
# out of the harness into bare `rg`. `search` / `lookup` / `xrefs` do not help:
# they read the IL2CPP indices, and a source tree is not in them.
#
# Two roots, treated alike and never merged silently. `src/<version>/` is the
# scaffold `seed-src` lays down -- stubs, with bodies stripped.
# `src-hotupdate/<version>/` is source recovered from the hot-update assemblies
# -- the shipped bodies. To a reader both are "this game's C#", so one set of
# commands covers both; but which root a file came from decides whether a body
# is real, so every line of output says which.
#
# Not bounded the way discovery is. `table list` sweeps directories nobody
# named, so its depth and directory caps are what keep a query cheap; here the
# reader named the tree and asked for it to be searched, and a `cs-grep` that
# quietly stopped three levels down would be answering a different question.
# What *is* reported is every cap that does bite: the hit limits, per bucket.

SCAFFOLD_ROOT = "src"               # what `seed-src` lays down
HOTUPDATE_ROOT = "src-hotupdate"    # source recovered from the hot-update side

# (directory, label). The label is what output prints, because "src" and
# "src-hotupdate" are directory names and the reader is asking a different
# question: is this a stub or the shipped body.
#
# `src/` is revenant's own -- `seed-src` writes it, so revenant may name it.
# `src-hotupdate/` is not: nothing here produces it, and where a project lands
# its recovered source is a fact about that project, which CONTEXT.md's bar
# keeps out of revenant. It is the default because every project that has one
# spells it this way, and `[csharp] roots` REPLACES the list for a project that
# does not -- the same escape `[tables] dirs` gives discovery.
SOURCE_ROOTS = ((SCAFFOLD_ROOT, "scaffold"), (HOTUPDATE_ROOT, "hotupdate"))

CS_SUFFIX = ".cs"


@dataclass(frozen=True)
class SourceRoot:
    label: str      # "scaffold" | "hotupdate", or the directory for a configured root
    rel: str        # project-relative, e.g. "src/1.0"
    path: str       # absolute


@dataclass(frozen=True)
class SourceFile:
    root: str       # the root's label
    name: str       # path under the root, `/`-separated, without ".cs"
    path: str       # absolute

    @property
    def label(self) -> str:
        """`scaffold/Game/Shop` -- the handle every command prints and takes."""
        return f"{self.root}/{self.name}"


def _project_root(root: str | None) -> str:
    from . import config
    return os.path.abspath(root) if root else config.workspace_root()


def configured_roots(root: str | None = None, cfg: dict | None = None) -> tuple:
    """`[csharp] roots` as (directory, label) pairs, or () when unset.

    Setting it REPLACES the built-in pair, the way `[tables] dirs` replaces the
    sweep: a project whose recovered source lands somewhere else is stating a
    fact about itself, and revenant guessing a second name would be inventing
    one of the conventions its own bar keeps out.
    """
    from . import config
    if cfg is None:
        cfg = config.load_config(_project_root(root))
    named = ((cfg or {}).get("csharp") or {}).get("roots") or ()
    if isinstance(named, str):
        named = [named]
    return tuple((str(d), str(d).rstrip("/").rsplit("/", 1)[-1]) for d in named)


def declared_roots(root: str | None = None, cfg: dict | None = None) -> tuple:
    """Every C# source root this project declares, as (directory, label) pairs.

    The one place `[csharp] roots` and the built-in pair are composed. Three
    callers want that composition -- `source_roots`, `check_source` and
    `table refs` -- and each used to spell it out, which is three chances for
    one of them to search a list the others do not. That is not hypothetical:
    the copy in `refs` read `src/` alone, so for a release a title whose table
    loading lives in the hot-update bodies was reported as unsearchable.

    Declared, not present. A root that is missing is exactly what a caller
    reporting "cannot check" has to name, so the filtering lives one level up
    in `source_roots`, and no version is resolved here -- naming the roots is
    not reading them, and `check_source` is a typo check that must stay cheap.
    """
    return configured_roots(root, cfg) or SOURCE_ROOTS


def source_roots(version: str = "", root: str | None = None,
                 cfg: dict | None = None) -> tuple[SourceRoot, ...]:
    """The C# source roots that are actually there, in listing order.

    "There" means holding at least one `.cs`, not merely existing. A `src/`
    with nothing in it means `seed-src` never ran, and reporting that as a root
    with no files turns our own missing input into "this game has no C#" --
    the same line `table refs` draws for an empty corpus.
    """
    from . import config
    base = _project_root(root)
    version = version or config.detect_version()
    found = []
    for directory, label in declared_roots(root, cfg):
        rel = os.path.join(directory, version)
        path = os.path.join(base, rel)
        if os.path.isdir(path) and _holds_cs(path):
            found.append(SourceRoot(label=label, rel=rel, path=path))
    return tuple(found)


def _holds_cs(path: str) -> bool:
    for _dirpath, _dirnames, filenames in os.walk(path):
        if any(fn.endswith(CS_SUFFIX) for fn in filenames):
            return True
    return False


NO_SOURCE = (f"No C# source tree. The scaffold comes from `revenant seed-src` "
             f"({SCAFFOLD_ROOT}/<version>/); recovered hot-update source goes "
             f"in {HOTUPDATE_ROOT}/<version>/ (or wherever `[csharp] roots` "
             f"says).")


def root_hint(directory: str) -> str:
    """What to do about one source root that is not there.

    An action in every case, because the slot it fills is one -- a reader told
    a corpus could not be searched is owed the move that would fix it, and a
    description sitting in that slot reads as an excuse. The three actions
    differ in kind: `src/` is revenant's own, so there is a command; nothing
    here produces `src-hotupdate/`, so the move is to recover it, and naming a
    revenant command for it would invent the convention CONTEXT.md's bar keeps
    out; anything else was declared by the project, so the move is to put the
    source where the key says or fix the key.

    Beside `SOURCE_ROOTS` rather than at the caller: the list of roots and what
    to say about each missing one are the same fact, and `refs` already learnt
    what it costs to keep a second copy of this list.
    """
    if directory == SCAFFOLD_ROOT:
        return "revenant seed-src"
    if directory == HOTUPDATE_ROOT:
        return "recover it from the hot-update assemblies; nothing here writes it"
    return f"[csharp] roots points at {directory}/; put the source there or fix the key"


def check_source(which: str, root: str | None = None,
                 cfg: dict | None = None) -> str:
    """"" if `which` names a root, else the complaint to print.

    A typo is rejected rather than filtered on. `--from scafold` matches no
    root, and answering "nothing found" to a misspelt name reports our own
    mistake as the tree's content. Shared by the CLI and the MCP tools, because
    the surface that skipped this check is the surface that had the bug.
    """
    if not which:
        return ""
    known = [label for _d, label in declared_roots(root, cfg)]
    if which in known:
        return ""
    return f"no source root named {which!r}; this project has: {', '.join(known)}"


def _walk(where: SourceRoot):
    for dirpath, dirnames, filenames in os.walk(where.path):
        dirnames[:] = sorted(d for d in dirnames if not d.startswith("."))
        for filename in sorted(filenames):
            if not filename.endswith(CS_SUFFIX):
                continue
            path = os.path.join(dirpath, filename)
            name = os.path.relpath(path, where.path)[:-len(CS_SUFFIX)]
            yield SourceFile(root=where.label, name=name.replace(os.sep, "/"),
                             path=path)


def list_sources(version: str = "", query: str = "", limit: int = 0,
                 root: str | None = None, which: str = "",
                 roots=None) -> tuple[SourceFile, ...]:
    """Every `.cs` under the source roots, optionally filtered by substring.

    `which` restricts to one root by label. `limit` of 0 means all; a caller
    that passes one must report it, because a listing silently short of the
    tree reads exactly like a small tree -- which is why `list_report` exists
    and why nothing prints this result raw.

    `roots` lets a caller that already resolved them hand them in. Resolving
    costs a walk per root, and `cs_grep` used to pay for three.
    """
    out = []
    for where in (source_roots(version, root) if roots is None else roots):
        if which and where.label != which:
            continue
        for found in _walk(where):
            if not query or query.lower() in found.name.lower():
                out.append(found)
    out.sort(key=lambda f: (f.root, f.name))
    return tuple(out[:limit]) if limit else tuple(out)


# `class Foo`, `struct Foo`, ... -- used both to label a declaration line and to
# find the file that declares a type whose file is named something else.
_TYPE_DECL = r"\b(?:class|struct|interface|enum|record|delegate)\s+{name}\b"


def find_source(name: str, version: str = "", root: str | None = None,
                which: str = "") -> tuple[SourceFile, ...]:
    """Every source file a handle names -- all of them, never a pick.

    A handle is a path under a root (`Game/Shop`), a full label
    (`scaffold/Game/Shop`), or a type name (`Shop`). A name present in both
    roots is the interesting case, not an inconvenience: one is the stub and
    the other is the shipped body, so both come back and the caller says which.

    A type name is tried against the file name first, because the scaffold is
    one file per type; when that misses, the files that *declare* that type are
    read for. Filename matching alone answers nothing for a type renamed on the
    way out, or for the second type in a file -- both normal in recovered
    source, and both would come back as "not found".
    """
    wanted = name[:-len(CS_SUFFIX)] if name.endswith(CS_SUFFIX) else name
    head, _sep, rest = wanted.partition("/")
    every = list_sources(version, root=root, which=which)
    if rest and head in {f.root for f in every}:
        which, wanted = head, rest
        every = tuple(f for f in every if f.root == which)
    exact = [f for f in every if f.name == wanted]
    if exact:
        return tuple(exact)
    by_file = [f for f in every if f.name.rsplit("/", 1)[-1] == wanted]
    if by_file:
        return tuple(by_file)
    if not re.fullmatch(r"[A-Za-z_]\w*", wanted):
        return ()
    declares = re.compile(_TYPE_DECL.format(name=re.escape(wanted)))
    return tuple(f for f in every
                 if any(declares.search(line) for _n, line in _lines(f)))


def read_source(found: SourceFile) -> str:
    with open(found.path, encoding="utf-8", errors="replace") as f:
        return f.read()


def list_report(found, query: str = "", limit: int = 0) -> str:
    """The listing, phrased once, cap included.

    One wording for the CLI and the MCP tool. Two spellings is how the MCP side
    came to report a capped listing as the whole tree while the CLI did not.
    """
    if not found:
        return f"No C# file matches {query!r}." if query else NO_SOURCE
    shown = found[:max(0, limit)] if limit else found
    head = (f"{len(shown)} of {len(found)} C# file(s)" if len(shown) < len(found)
            else f"{len(found)} C# file(s)")
    if query:
        head += f" matching {query!r}"
    roots = len({f.root for f in shown})
    return (f"{head} in {roots} root(s):\n" +
            "\n".join("  " + f.label for f in shown))


def source_report(name: str, hits) -> str:
    """The answer to `cs-get`: the source, or why there is not exactly one.

    Ambiguity is an answer, not a failure to pick. A name in the scaffold and
    in the recovered hot-update source is the case worth seeing -- one is the
    stub, the other the shipped body.
    """
    if len(hits) == 1:
        return read_source(hits[0])
    if not hits:
        return f"Not found: {name}. `cs-list` shows what there is."
    return (f"{name} names {len(hits)} files; say which:\n" +
            "\n".join("  " + h.label for h in hits))


def cs_grep(pattern: str, version: str = "", limit: int = 200,
            root: str | None = None, which: str = "",
            ignore_case: bool = True) -> str:
    """Regex search across the C# source roots -> `root/name:line: text`."""
    roots = source_roots(version, root)
    if not roots:
        return NO_SOURCE
    complaint = check_source(which, root)
    if complaint:
        return complaint
    try:
        rx = re.compile(pattern, re.IGNORECASE if ignore_case else 0)
    except re.error as exc:
        return f"Bad regex {pattern!r}: {exc}"
    limit = max(0, limit)
    hits, total = [], 0
    for found in list_sources(version, which=which, roots=roots):
        for line_no, line in _lines(found):
            if not rx.search(line):
                continue
            total += 1
            if len(hits) < limit:
                hits.append(f"  {found.label}:{line_no}: {line.strip()}")
    if not total:
        return f"No C# lines match {pattern!r}."
    head = f"{len(hits)}/{total} C# line(s) matching {pattern!r}:"
    return head + "\n" + "\n".join(hits)


def _lines(found: SourceFile):
    try:
        with open(found.path, encoding="utf-8", errors="replace") as f:
            yield from enumerate(f, 1)
    except OSError:
        return


# What a line has to look like for the symbol to be *declared* on it rather than
# used. The rule that matters: in a declaration the symbol is in the NAME
# position, which means a type token stands in front of it. Without that, the
# same shapes match uses -- `private ItemConf _cfg;` declares `_cfg`, not
# `ItemConf`, and `Reward(1, 2);` is a call, not a method declaration. Both were
# filed as declarations before, which inverts the split `refs` exists to make.
#
# Keywords that make the shape an expression are excluded by name: `return
# Foo(x);` and `new ItemConf();` put a word in front of the symbol too.
_NOT_A_TYPE = ("return", "new", "throw", "await", "yield", "case", "typeof",
               "sizeof", "default", "is", "as", "in", "out", "ref", "when",
               "using", "namespace", "else", "do")

_TYPE_TOKEN = (r"(?<![\w.])(?!(?:" + "|".join(_NOT_A_TYPE) + r")\b)"
               r"[A-Za-z_][\w.]*(?:<[^<>]*>)?(?:\[\])?\s+")

_DECL_SHAPES = (
    _TYPE_DECL,                                     # a type by that name
    _TYPE_TOKEN + r"{name}\s*\(",                    # a method by that name
    _TYPE_TOKEN + r"{name}\s*(?:[;=]|=>|\{{)",        # a field, property or local
)

REFS_CAVEAT = (
    "Text, not a resolved call graph: comments and string literals count, an "
    "unrelated type of the same name in another namespace counts, and an "
    "overload cannot be told from its siblings. Declared-vs-mentioned is "
    "decided by the shape of the one line, so a signature split across lines "
    "can land in the wrong column. `xrefs` resolves; this reads.")


def cs_refs(symbol: str, version: str = "", limit: int = 200,
            root: str | None = None, which: str = "") -> str:
    """Where a C# name is declared and where it is mentioned, per root.

    Whole-identifier, because `ItemConfExtra` is a different name and counting
    it turns a zero into a one. Declarations are separated from mentions
    because "where does this come from" is the question `refs` is asked -- and
    both counts are of everything found, not of what the limit left, because a
    truncated count printed as a total is the bug that reads as an answer.
    """
    from .refs import word_pattern
    roots = source_roots(version, root)
    if not roots:
        return NO_SOURCE
    complaint = check_source(which, root)
    if complaint:
        return complaint
    if not symbol.strip():
        return "Usage: cs-refs <TypeName | MemberName>"
    pattern = word_pattern([symbol])
    decls = [re.compile(shape.format(name=re.escape(symbol)))
             for shape in _DECL_SHAPES]
    limit = max(0, limit)
    buckets = {"declared": ([], 0), "mentioned": ([], 0)}
    for found in list_sources(version, which=which, roots=roots):
        for line_no, line in _lines(found):
            if not pattern or not pattern.search(line):
                continue
            key = "declared" if any(d.search(line) for d in decls) else "mentioned"
            shown, seen = buckets[key]
            if len(shown) < limit:
                shown.append(f"  {found.label}:{line_no}: {line.strip()}")
            buckets[key] = (shown, seen + 1)
    total = sum(seen for _shown, seen in buckets.values())
    if not total:
        searched = ", ".join(r.rel for r in roots)
        return f"No mention of {symbol!r} in {searched}."
    out = [f"C# symbol: {symbol}  ({total} line(s) across {len(roots)} root(s))"]
    for key in ("declared", "mentioned"):
        shown, seen = buckets[key]
        count = f"{len(shown)} of {seen}" if len(shown) < seen else str(seen)
        out.append(f"{key} ({count}):" if seen or key == "mentioned"
                   else f"{key} (0): not declared in any source root here")
        out += shown
    if not buckets["declared"][1]:
        out[1] = "declared (0): not declared in any source root here"
    out.append(REFS_CAVEAT)
    return "\n".join(out)
