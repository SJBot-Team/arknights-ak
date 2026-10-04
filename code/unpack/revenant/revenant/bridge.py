"""C# <-> Lua bridge navigation for xLua games.

The gameplay is Lua; the engine/binding layer is C#. Lua reaches into C# via
`CS.<Namespace>.<Type>` (xLua runtime), and C# drives Lua via
`LuaManager.CSharpCallLuaMethod(scriptName, funcName, argv)`. xLua generates a
`<TypeNoDots>Wrap.cs` class for every C# type it exposes to Lua.

This module ties the two layers the harness now spans:
  - resolve `CS.X.Y` (or a C# type name) to the C# side (DiffableCs + RVAs),
    report whether it is Lua-exposed (a Wrap class exists), and list the Lua
    scripts that use it (from the Lua static index's cs_index);
  - with no query, list the Lua-used C# surface, ranked by how many scripts
    reference each type.

Reuses: indices/resolve_version, search.search_symbols, csharp.parse_type_metadata,
lua.load_lua_index.
"""

from __future__ import annotations

import os
import re

from . import config, csharp, lua
from .indices import resolve_version, format_rva
from .search import search_symbols


def _diffable_dir(vd) -> str:
    return os.path.join(vd.root, "DiffableCs")


def _wrap_dir(vd) -> str:
    return os.path.join(_diffable_dir(vd), "Assembly-CSharp", "XLua", "CSObjectWrap")


def _wrap_exists(vd, type_full: str) -> str | None:
    """Return the Wrap .cs filename if a Lua wrapper exists for the type."""
    wdir = _wrap_dir(vd)
    if not os.path.isdir(wdir):
        return None
    bare = re.sub(r"[.+]", "", type_full)            # UnityEngine.Color -> UnityEngineColor
    cand = bare + "Wrap.cs"
    if os.path.exists(os.path.join(wdir, cand)):
        return cand
    # Case-insensitive / suffix fallback (handles odd nested-type spellings).
    low = (bare + "wrap.cs").lower()
    for fn in os.listdir(wdir):
        if fn.lower() == low:
            return fn
    return None


def _strip_cs(query: str) -> str:
    """CS.Namespace.Type[:member] -> Namespace.Type (best-effort type part)."""
    q = query.strip()
    if q.lower().startswith("cs."):
        q = q[3:]
    q = q.split(":", 1)[0]          # drop a :method suffix
    return q.strip(". ")


def lua_bridge(query: str = "", version: str = "") -> str:
    version = version or config.detect_version()
    vd = resolve_version(version or None)
    idx = lua.load_lua_index(version)
    cs_index: dict = idx.get("cs_index", {})

    if not query.strip() or query.strip() in {"--list", "-l"}:
        return _list_surface(vd, cs_index)

    type_full = _strip_cs(query)
    out = [f"Bridge: {query}  ->  C# type {type_full}"]

    # C# side: resolve to a type + representative RVAs.
    meta = None
    try:
        meta = csharp.parse_type_metadata(vd, type_full)
    except Exception:
        meta = None
    if meta is not None:
        full = (meta.namespace + "." if meta.namespace else "") + meta.class_name
        out.append(f"  C#: {full}" + (f" : {meta.base_type}" if meta.base_type else ""))
        out.append(f"  DiffableCs: {meta.file}  ({len(meta.methods)} methods, {len(meta.fields)} fields)")
    else:
        out.append("  C#: type not found in DiffableCs by exact name; nearest matches:")
    # A few RVAs via the symbol index (works even when metadata is absent).
    sym = search_symbols(type_full.replace(".", " "), version, limit=5)
    rvas = [ln.strip() for ln in sym.splitlines()[1:6]]
    for ln in rvas:
        out.append("    " + ln)

    # Lua-exposed?
    wrap = _wrap_exists(vd, type_full)
    out.append(f"  Lua-exposed: {'YES (' + wrap + ')' if wrap else 'no Wrap class found'}")

    # Lua usage sites (from cs_index): exact CS.<type> and members under it.
    key = "CS." + type_full
    users: set[str] = set()
    for cs_key, mods in cs_index.items():
        if cs_key == key or cs_key.startswith(key + "."):
            users.update(mods)
    out.append(f"  used by {len(users)} Lua script(s)" + (":" if users else "."))
    for m in sorted(users)[:30]:
        out.append("    " + m)
    if len(users) > 30:
        out.append(f"    ... and {len(users) - 30} more (re_lua_grep for the call sites)")
    return "\n".join(out)


def _list_surface(vd, cs_index: dict) -> str:
    """List the C# types Lua actually references, ranked by script count."""
    if not cs_index:
        return ("No Lua index. Run: revenant lua-extract "
                "(then the bridge reads the cs_index).")
    # Collapse member accesses to their owning type prefix when a Wrap exists;
    # otherwise keep the referenced path. Rank by number of using scripts.
    ranked = sorted(cs_index.items(), key=lambda kv: (-len(kv[1]), kv[0]))
    out = [f"Lua-used C# surface: {len(cs_index)} CS.* references "
           f"(top by script count; [exposed]=Wrap class present):"]
    for cs_key, mods in ranked[:60]:
        type_full = _strip_cs(cs_key)
        tag = " [exposed]" if _wrap_exists(vd, type_full) else ""
        out.append(f"  {len(mods):3d}  {cs_key}{tag}")
    out.append("\nResolve one with re_lua_bridge(\"CS.<Namespace>.<Type>\").")
    return "\n".join(out)
