#!/usr/bin/env python3
"""MCP harness server (`re`) for a Revenant RE project (game-agnostic).

Exposes Revenant's reverse-engineering toolkit as read-only MCP tools (surfaced
to the agent as `mcp__re__<tool>`) so a coding agent can do deep IL2CPP
and xLua reverse engineering: discover types, fetch ISIL assembly, build
evidence packets, trace xrefs, analyse control flow, and explore the decompiled
Lua. The target package, version and architecture are auto-detected
(see re_status); nothing here is specific to a particular apk.

Launched by the agent via the project's .mcp.json (written by `revenant init`):

    { "mcpServers": { "re": { "command": "revenant-mcp" } } }

The project root is resolved from the cwd the agent launches the server in (it
walks up to the revenant.toml marker; see config.workspace_root), so the server
finds the binary, indices and Lua of whichever project it runs in.

Index-dependent tools degrade gracefully: if the Cpp2IL output is missing they
return a one-line instruction instead of raising.
"""
from __future__ import annotations

import os

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations

from . import config, csharp, lua
from .binary import find_global_metadata, find_libil2cpp
from .cfg import branch_summary, build_cfg_report
from .disasm import evidence_report, simple_disasm_report
from .image import ARCH_ARM32, ARCH_ARM64, image_arch
from .fields import scan_field_accesses
from .indices import VERSIONS, load_version, resolve_version, lookup_rva
from .metadata import Il2CppMetadata
from .reports import find_asm_by_rva
from .search import search_symbols
from .xrefs import callgraph as _callgraph
from .xrefs import find_xrefs

VERSION = config.DEFAULT_VERSION


def _cpp2il_out() -> str:
    return os.path.join(config.refs_dir(), VERSION, "cpp2il_out")


def _load_indices() -> bool:
    """Load Cpp2IL indices for the default version if present."""
    out = _cpp2il_out()
    has_index = os.path.exists(os.path.join(out, "rva_index.json"))
    has_isil = os.path.isdir(os.path.join(out, "IsilDump"))
    if os.path.isdir(out) and (has_index or has_isil):
        try:
            load_version(VERSION, out, verbose=False)
            return True
        except Exception:
            return False
    return False


_INDICES_OK = _load_indices()

_NO_INDEX = (
    "Indices not built. From the project root run:\n"
    "  revenant prepare\n"
    "(or one step: revenant prepare --only run-cpp2il / --only build-indices)\n"
    "Then restart this MCP server (the agent reconnects on next launch)."
)

# The other reason a tool has nothing to say, and it is not this one. Kept apart
# because the remedies are opposites: `_NO_INDEX` means the data is missing here,
# `_NO_PROJECT` means *here* is the wrong place to be looking (#69).
_PROJECT_ROOT = config.project_marker_root()


def _no_project() -> str:
    """Why this server can answer nothing, and what to do -- naming the projects.

    A day of nine-game work ran with the server started at a repository root
    holding nine prepared projects. Every index-backed tool answered "indices
    not built -- run `revenant prepare`", which is false about all nine, and the
    rounds that believed it wrote down "this game does not have that". A tool
    that cannot tell "no data" from "wrong directory" turns the second into the
    first, and the first reads like a finding.
    """
    here = os.getcwd()
    lines = [
        f"No Revenant project here: no {config.PROJECT_MARKER} in {here} or any parent.",
        "This server resolves the project from the directory it was started in, so "
        "nothing below is missing -- it was never in scope.",
    ]
    nearby = config.nearest_projects(here)
    if nearby:
        lines.append("")
        lines.append(f"Projects one level down: {', '.join(nearby)}")
        lines.append(f"Start the agent inside one (`cd {nearby[0]}`), or set "
                     f"REVENANT_PROJECT to its path, then restart this server.")
    else:
        lines.append("Start the agent inside a project directory, or set "
                     "REVENANT_PROJECT to its path, then restart this server.")
    return "\n".join(lines)


def _unavailable() -> str:
    """The reason no index-backed answer is possible, or "" when one is.

    One helper rather than a check per tool, because the failure this exists for
    is a tool that forgot to have one.
    """
    if not _PROJECT_ROOT:
        return _no_project()
    if not _INDICES_OK:
        return _NO_INDEX
    return ""


_NO_DIFFABLE = (
    "DiffableCs C# stubs not present. Generate them with a Cpp2IL diffable-cs pass "
    "(--output-as diffable-cs --use-processor attributeinjector,nativemethoddetector,stablenamer), "
    "then restart this server."
)

mcp = FastMCP("re")
RO = ToolAnnotations(readOnlyHint=True)


def _safe(fn, *args, **kwargs) -> str:
    try:
        result = fn(*args, **kwargs)
        return result if isinstance(result, str) else str(result)
    except FileNotFoundError as exc:
        return f"Not found: {exc}"
    except Exception as exc:  # surface a clean message, never a stack trace
        return f"Error: {type(exc).__name__}: {exc}"


def _isil_root() -> str:
    vd = resolve_version(VERSION)
    return os.path.join(vd.root, "IsilDump", "Assembly-CSharp")


# ── Discovery ────────────────────────────────────────────────────────────────

@mcp.tool(annotations=RO)
def re_search(query: str, limit: int = 25) -> str:
    """Search the IL2CPP index by class / type / method / signature name.

    The entry point for discovery: returns matching methods with their RVA
    addresses (use those with re_find_asm / re_evidence). Query by a class,
    method, or namespace fragment (e.g. "Board", "Inventory", "OnClick").
    """
    if (why := _unavailable()):
        return why
    return _safe(search_symbols, query, VERSION, limit)


@mcp.tool(annotations=RO)
def re_type_info(type_name: str) -> str:
    """Structural info for a C# type: base class, fields (with byte offsets),
    method signatures, and the DiffableCs file path.

    Pass a class name or fully-qualified `Namespace.Class`. Read the reported
    .cs file (built-in read_file) to see each method's [Address(RVA=...)], or
    use re_search to resolve a method name to its RVA. Use the field offsets
    here as the `type_name` argument to re_evidence for field-aware analysis.
    """
    if (why := _unavailable()):
        return why
    try:
        vd = resolve_version(VERSION)
        meta = csharp.parse_type_metadata(vd, type_name)
    except Exception as exc:
        return f"Error: {type(exc).__name__}: {exc}"
    if meta is None:
        return f"Type not found in DiffableCs: {type_name!r}. {_NO_DIFFABLE}"
    kind = getattr(meta, "kind", "class")
    attrs = getattr(meta, "attributes", ())
    # Surface xLua exposure / notable markers; hide the ubiquitous [Token].
    notable = [a for a in attrs if a not in {"Token"}]
    header = (
        f"{kind.capitalize()}: {meta.namespace + '.' if meta.namespace else ''}{meta.class_name}"
        + (f" : {meta.base_type}" if meta.base_type else "")
    )
    lines = [header]
    if notable:
        lines.append(f"  attributes: {', '.join('[' + a + ']' for a in notable)}")
    lines.append(f"DiffableCs file: {meta.file}  (read_file this for [Address(RVA=...)] per method)")

    if kind == "enum":
        lines.append("")
        lines.append(f"Enum members ({len(meta.enum_members)}):")
        for name, value in meta.enum_members:
            lines.append(f"  {value:>6} = {name}")
        return "\n".join(lines)

    lines.append("")
    lines.append(f"Fields ({len(meta.fields)}):")
    for f in sorted(meta.fields, key=lambda x: x.offset):
        cv = f"  = {f.const_value}" if getattr(f, "const_value", "") else ""
        lines.append(f"  +0x{f.offset:<5X} {f.type_name} {f.name}{cv}")
    lines.append("")
    lines.append(f"Methods ({len(meta.methods)}):")
    for m in meta.methods:
        lines.append(f"  {m.return_type} {m.name}{m.signature}  (line {m.line})")
    return "\n".join(lines)


# ── Lua game logic (xLua) ────────────────────────────────────────────────────

@mcp.tool(annotations=RO)
def re_lua_list(query: str = "", limit: int = 200) -> str:
    """List the game's Lua scripts (the actual gameplay logic lives in Lua).

    For this xLua title, Assembly-CSharp is mostly engine/binding glue; the
    game rules, board logic, UI and activities are Lua. Scripts are decompiled
    into lua/<version>/ (run `revenant lua-extract` first). Pass a
    substring `query` (e.g. "Board", "Merge", "Activity") to filter by module
    name. Read a script's source with re_lua_source.
    """
    if not _PROJECT_ROOT:
        return _no_project()
    names = lua.list_scripts(VERSION, query, limit)
    if not names:
        root = lua.lua_out_dir(VERSION)
        if not os.path.isdir(root):
            return ("Lua not extracted yet. Run from the project root:\n"
                    "  revenant lua-extract")
        return f"No Lua scripts match {query!r}."
    # The total, not just what fits. A list that stops at the limit and does not
    # say so reads as the whole set, and "there are N of them" then goes into a
    # note as a counted fact (#69). Every other listing tool here prints `n/N`.
    total = len(lua.list_scripts(VERSION, query, 0))
    shown = f"{len(names)}/{total}" if total > len(names) else f"{len(names)}"
    head = f"{shown} Lua script(s)" + (f" matching {query!r}" if query else "") + ":"
    tail = (f"\n  ... {total - len(names)} more; increase limit"
            if total > len(names) else "")
    return head + "\n" + "\n".join("  " + n for n in names) + tail


@mcp.tool(annotations=RO)
def re_lua_source(name: str) -> str:
    """Decompiled source of one Lua script by module name (e.g.
    "Board.Model.Board.BaseBoardModel"). Use re_lua_list to discover names."""
    if not _PROJECT_ROOT:
        return _no_project()
    src = lua.get_source(name, VERSION)
    if src is None:
        return (f"Not found: {name}. Use re_lua_list to see available modules "
                f"(or run `revenant lua-extract` if none are extracted).")
    return src


@mcp.tool(annotations=RO)
def re_lua_grep(pattern: str, limit: int = 100) -> str:
    """Regex-search the decompiled Lua tree -> `module:line: text`.

    The main way to find game logic across the ~2300 scripts by CONTENT (a
    function, message, config key, or `CS.Type` call) rather than module name.
    `pattern` is a Python regex, case-insensitive.
    """
    if not _PROJECT_ROOT:
        return _no_project()
    return _safe(lua.lua_grep, pattern, VERSION, limit)


@mcp.tool(annotations=RO)
def re_lua_refs(name: str) -> str:
    """Lua cross-references. For a module name (e.g. "Board.Model.Board.ItemManager"):
    its requires, who requires it, and the functions it defines. For a function
    name: where it is defined (use re_lua_grep for call sites)."""
    if not _PROJECT_ROOT:
        return _no_project()
    return _safe(lua.lua_refs, name, VERSION)


# ── Managed source: the scaffold and the recovered hot-update C# ────────────
#
# Four of the nine titles end with their business logic as C# text. The Lua
# side has had five tools since the start; this is the same set for C#, over
# `src/<version>/` (the scaffold) and `src-hotupdate/<version>/` (source
# recovered from the hot-update assemblies). Both are searched and every result
# says which root it came from, because a stub and a shipped body answer
# different questions.
#
# Every phrase here comes from `csharp`. The CLI prints the same strings: the
# first cut spelled them twice, and the two spellings had already diverged --
# one validated `source` and reported its cap, the other did neither.

def _cs_ready(source: str) -> str:
    """"" when a C# query can run, else what to say instead.

    A misspelt `source` is rejected rather than filtered on: `"scafold"` matches
    no root, and answering "nothing found" reports our own mistake as the
    tree's content.
    """
    if not csharp.source_roots(VERSION):
        return csharp.NO_SOURCE
    return csharp.check_source(source)


@mcp.tool(annotations=RO)
def re_cs_list(query: str = "", limit: int = 200, source: str = "") -> str:
    """List the game's C# source files across both source roots.

    `src/<version>/` is the scaffold (`revenant seed-src`), stubs with bodies
    stripped. `src-hotupdate/<version>/` is source recovered from the
    hot-update assemblies -- the shipped bodies. Pass a substring `query` to
    filter, or `source` ("scaffold" | "hotupdate") to restrict to one root.
    Names come back as `root/path`, which is what re_cs_source takes. A capped
    listing says so; `limit=0` means all.
    """
    if not _PROJECT_ROOT:
        return _no_project()
    problem = _cs_ready(source)
    if problem:
        return problem
    found = csharp.list_sources(VERSION, query, which=source)
    return csharp.list_report(found, query, max(0, limit))


@mcp.tool(annotations=RO)
def re_cs_source(name: str, source: str = "") -> str:
    """Source of one C# file, by `root/path`, by path, or by type name.

    A name present in both roots comes back as a list rather than a pick: one
    is the stub and the other the shipped body, and choosing for you would
    answer a question you did not ask. Say which with `source`.
    """
    if not _PROJECT_ROOT:
        return _no_project()
    problem = _cs_ready(source)
    if problem:
        return problem
    hits = csharp.find_source(name, VERSION, which=source)
    return csharp.source_report(name, hits)


@mcp.tool(annotations=RO)
def re_cs_grep(pattern: str, limit: int = 100, source: str = "") -> str:
    """Regex-search the C# source roots -> `root/path:line: text`.

    The way to find managed logic by CONTENT across both roots. `pattern` is a
    Python regex, case-insensitive. This reads the source tree; re_search and
    re_xrefs read the IL2CPP indices, which do not cover it.
    """
    if not _PROJECT_ROOT:
        return _no_project()
    return _safe(csharp.cs_grep, pattern, VERSION, limit, None, source)


@mcp.tool(annotations=RO)
def re_cs_refs(symbol: str, limit: int = 100, source: str = "") -> str:
    """Where a C# name is declared and where it is mentioned, per source root.

    Whole-identifier, so `ItemConfExtra` is not a hit for `ItemConf`. Text, not
    a resolved call graph: comments, string literals and a same-named type in
    another namespace all count, and the answer says so. re_xrefs resolves RVAs;
    this reads source.
    """
    if not _PROJECT_ROOT:
        return _no_project()
    return _safe(csharp.cs_refs, symbol, VERSION, limit, None, source)


@mcp.tool(annotations=RO)
def re_lua_bridge(query: str = "") -> str:
    """Navigate the C#<->Lua (xLua) bridge.

    With a `CS.<Namespace>.<Type>` reference or a C# type name: resolve it to
    the C# side (DiffableCs + RVAs via re_search), report whether it is
    Lua-exposed (an xLua Wrap class exists), and list the Lua scripts that use
    it. With no query: list the C# types Lua references, ranked by script count.
    Bridge the other way (C# driving Lua) via LuaManager.CSharpCallLuaMethod —
    re_xrefs its RVA for the C# call sites.
    """
    if not _PROJECT_ROOT:
        return _no_project()
    from .bridge import lua_bridge
    return _safe(lua_bridge, query, VERSION)


# ── Assembly (ISIL) ──────────────────────────────────────────────────────────

@mcp.tool(annotations=RO)
def re_find_asm(rva: str) -> str:
    """ISIL assembly for the method at an RVA (8-digit hex, e.g. 0x0065D5AC).

    ISIL is Cpp2IL's architecture-independent IR and is the primary input for
    reconstruction (preferred over raw disasm). Resolve names to RVAs with
    re_search first. If the method has branches, call re_cfg next for its
    control-flow structure before deciding loop-vs-if scope.
    """
    if (why := _unavailable()):
        return why
    body = _safe(find_asm_by_rva, rva, VERSION)
    try:
        n_branch, n_loop = branch_summary(rva, VERSION)
        if n_branch:
            loops = f", {n_loop} loop(s)" if n_loop else ""
            body += (
                f"\n\n[control flow] {n_branch} branch(es){loops} — call "
                f"re_cfg({rva}) for basic blocks and which code runs unconditionally."
            )
    except Exception:
        pass
    return body


@mcp.tool(annotations=RO)
def re_cfg(rva: str) -> str:
    """Control-flow structure of the method at an RVA: basic blocks, loops,
    and which code runs UNCONDITIONALLY vs is guarded by a branch.

    Call this for ANY method with branches BEFORE deciding loop-vs-if scope.
    Reads the same disassembly as re_find_asm and reports: basic blocks with
    their terminators/successors; loops (header + body + back-edge); the
    'always-executed' set (blocks that post-dominate the entry, i.e. run on
    every path — code there is NOT inside any guard); and, per conditional
    branch, where the two paths rejoin and exactly which blocks it guards.

    Key rule it encodes: a backward conditional branch is a loop back-edge; a
    forward conditional branch whose target is the loop's fall-through exit is
    a loop-entry pre-test, NOT a guard over later statements. Trust the
    always-executed set for what is unconditional — do not infer it by hand.
    """
    if (why := _unavailable()):
        return why
    return _safe(build_cfg_report, rva, VERSION)


@mcp.tool(annotations=RO)
def re_lookup(rva: str) -> str:
    """Resolve an RVA address to its owning method name and signature."""
    if (why := _unavailable()):
        return why
    return _safe(lookup_rva, rva, VERSION)


@mcp.tool(annotations=RO)
def re_xrefs(rva: str, limit: int = 50) -> str:
    """Cross-references: call sites (BL) that target the method at this RVA.

    Use to find who invokes a method and map data flow into a subsystem.
    """
    if (why := _unavailable()):
        return why
    return _safe(find_xrefs, rva, VERSION, limit)


@mcp.tool(annotations=RO)
def re_callgraph(rva: str, limit: int = 20) -> str:
    """Direct callers and callees for the method at an RVA."""
    if (why := _unavailable()):
        return why
    return _safe(_callgraph, rva, VERSION, limit)


@mcp.tool(annotations=RO)
def re_field_scan(offset: str, limit: int = 50, filter: str = "") -> str:
    """Scan IsilDump for memory accesses at a struct field offset.

    `offset` is hex (e.g. "0x18") or decimal. Optional `filter` is a path
    substring/regex to narrow to certain assemblies. Use to confirm a field
    is read/written and where.
    """
    if (why := _unavailable()):
        return why
    root = _isil_root()
    if not os.path.isdir(root):
        return f"IsilDump root not found at {root}. {_NO_INDEX}"
    try:
        off = int(offset, 0)
    except ValueError:
        return f"Bad offset {offset!r}; use hex like 0x18 or a decimal."
    return _safe(scan_field_accesses, root, off, limit, filter)


# ── Raw binary (no index required) ───────────────────────────────────────────

@mcp.tool(annotations=RO)
def re_disasm(rva: str, byte_count: int = 256, mode: str = "") -> str:
    """Raw disassembly at an RVA (architecture auto-detected from the ELF).

    Works without indices (reads the IL2CPP binary directly). Detects ARM64 vs ARM32
    automatically; for ARM32 the ARM/Thumb decoder is chosen by quality score.
    `mode` forces a decoder: "arm", "thumb", or "" for auto.
    """
    if not _PROJECT_ROOT:
        return _no_project()
    return _safe(simple_disasm_report, rva, VERSION, byte_count, (mode or None))


@mcp.tool(annotations=RO)
def re_evidence(rva: str, byte_count: int = 256, mode: str = "", type_name: str = "") -> str:
    """Self-contained evidence packet for LLM reconstruction at an RVA.

    Includes disassembly plus, when `type_name` is given and DiffableCs is
    present, field-access / condition / mutation analysis against that type's
    offset map. NOTE: the field-semantics layer is ARM64-tuned; on ARM32 treat
    those inferences as best-effort and verify against re_find_asm (ISIL).
    """
    if not _PROJECT_ROOT:
        return _no_project()
    field_map = None
    if type_name and _INDICES_OK:
        try:
            field_map = csharp.fields_for_type(type_name, VERSION)
        except Exception:
            field_map = None
    return _safe(evidence_report, rva, VERSION, byte_count, field_map, (mode or None))


@mcp.tool(annotations=RO)
def re_find_binary() -> str:
    """Locate the extracted IL2CPP binary: path, source (which package/member), size."""
    if not _PROJECT_ROOT:
        return _no_project()
    try:
        loc = find_libil2cpp()
    except FileNotFoundError as exc:
        return f"Not found: {exc}"
    size = os.path.getsize(loc.path)
    return f"IL2CPP binary\n  path:   {loc.path}\n  source: {loc.source}\n  size:   {size:,} bytes ({size/1024/1024:.1f} MB)"


@mcp.tool(annotations=RO)
def re_find_metadata() -> str:
    """Locate global-metadata.dat and print its header (sanity, version, strings)."""
    if not _PROJECT_ROOT:
        return _no_project()
    try:
        loc = find_global_metadata()
        meta = Il2CppMetadata(loc.path)
    except FileNotFoundError as exc:
        return f"Not found: {exc}"
    except Exception as exc:
        return f"Error: {type(exc).__name__}: {exc}"
    return (
        f"global-metadata.dat\n  path:   {loc.path}\n  source: {loc.source}\n"
        f"  sanity: 0x{meta.sanity:08X}\n  version: {meta.version}\n"
        f"  string literals: {meta.string_literal_count}"
    )


@mcp.tool(annotations=RO)
def re_status() -> str:
    """Harness self-check: what is extracted/indexed and which tools are live."""
    # Before anything else, because everything after this reads a *detected*
    # identity, and detection has generic fallbacks. With no project to detect
    # from, the fallbacks render as a real target -- `com.unknown.il2cppgame
    # v0.0.0, architecture unknown` -- and the one tool whose whole job is to
    # say what is set up becomes the one that most convincingly lies (#69).
    if not _PROJECT_ROOT:
        return _no_project()
    out = _cpp2il_out()
    has_isil = os.path.isdir(os.path.join(out, "IsilDump"))
    has_index = os.path.exists(os.path.join(out, "rva_index.json"))
    has_diffable = os.path.isdir(os.path.join(out, "DiffableCs"))
    try:
        bin_ok = bool(find_libil2cpp())
    except Exception:
        bin_ok = False
    n_entries = 0
    if _INDICES_OK and VERSION in VERSIONS:
        try:
            n_entries = len(getattr(VERSIONS[VERSION], "rva_index", {}))
        except Exception:
            n_entries = 0
    arch = "unknown"
    try:
        if bin_ok:
            detected = image_arch(find_libil2cpp().path)
            arch = {ARCH_ARM32: "arm32", ARCH_ARM64: "arm64"}.get(detected, detected)
    except Exception:
        pass
    try:
        lua_st = lua.status(VERSION)
    except Exception:
        lua_st = {"extracted": 0, "lua_bundles_in_apk": 0, "decompiler": False}
    lua_line = (
        f"yes ({lua_st['extracted']:,} scripts)" if lua_st["extracted"]
        else (f"NO ({lua_st['lua_bundles_in_apk']} lua bundles in apk; run: revenant lua-extract)"
              if lua_st["lua_bundles_in_apk"] else "no xLua bundles detected")
    )
    lines = [
        f"IL2CPP RE harness — {config.PACKAGE} v{VERSION}",
        f"  architecture           : {arch}",
        f"  IL2CPP binary extracted: {'yes' if bin_ok else 'NO (run: revenant find-binary)'}",
        f"  indices loaded         : {'yes' if _INDICES_OK else 'NO'} ({n_entries:,} RVA entries)",
        f"  IsilDump               : {'yes' if has_isil else 'no'}",
        f"  rva/asm index          : {'yes' if has_index else 'no'}",
        f"  DiffableCs C# stubs     : {'yes' if has_diffable else 'no'}",
        f"  Lua game logic (xLua)  : {lua_line}",
        "",
        "Always-on tools (raw binary): re_disasm, re_evidence, re_find_binary, re_find_metadata",
        f"Index tools (need Cpp2IL)   : re_search, re_find_asm, re_cfg, re_lookup, re_xrefs, re_callgraph, re_field_scan {'[LIVE]' if _INDICES_OK else '[needs build]'}",
        f"DiffableCs tools            : re_type_info {'[LIVE]' if has_diffable else '[needs diffable-cs pass]'}",
        f"Lua tools (xLua game code)  : re_lua_list, re_lua_source, re_lua_grep, re_lua_refs, re_lua_bridge {'[LIVE]' if lua_st['extracted'] else '[run lua-extract]'}",
    ]
    return "\n".join(lines)


def main() -> None:
    """Console-script entry (revenant-mcp); also `python -m revenant.mcp_server`."""
    mcp.run()


if __name__ == "__main__":
    main()
