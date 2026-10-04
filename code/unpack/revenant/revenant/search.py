"""Symbol search over RVA indices.

Search pre-built indices by class/type/method/signature/file name.

Based on match3-core-sketch search.py methodology.
"""

from __future__ import annotations

import re

from .config import DEFAULT_VERSION
from .indices import VERSIONS, display_signature, format_rva, normalize_rva, resolve_version


def search_symbols(
    query: str,
    version: str = "",
    limit: int = 25,
    mode: str = "all",
) -> str:
    """Search pre-built indices by class/type/method/signature/file.

    Args:
        query: Space-separated search terms.
        version: Game version identifier.
        limit: Maximum results to return.
        mode: "all" (all terms must match) or "any" (any term matches).

    Returns:
        Formatted search results.
    """
    vd = resolve_version(version or None)
    terms = [t.lower() for t in query.split() if t.strip()]
    if not terms:
        return "Provide at least one search term."
    if mode not in {"all", "any"}:
        return f"Unknown search mode {mode!r}"

    rows: list[tuple[int, str, str, str, str]] = []

    def score(haystack: str) -> int:
        hay = haystack.lower()
        matches = [t for t in terms if t in hay]
        if mode == "all" and len(matches) != len(terms):
            return 0
        if mode == "any" and not matches:
            return 0
        s = 1
        if len(matches) == len(terms):
            s += 5
        s += len(matches) * 2
        for t in matches:
            s += min(len(t) // 4, 6)
            if re.search(rf"\b{re.escape(t)}\b", hay):
                s += 3
            else:
                s += 1
        return s

    for rva, entry in vd.asm_index.items():
        label = f"{entry.get('type', '')}.{entry.get('method', '')}"
        haystack = f"{label} {entry.get('file', '')}"
        s = score(haystack)
        if s:
            rows.append((s, rva, "IsilDump", label, entry.get("file", "")))

    for rva, entry in vd.rva_index.items():
        label = f"{entry.get('class', '')} | {display_signature(entry.get('signature', ''))}"
        haystack = f"{label} {entry.get('file', '')}"
        s = score(haystack)
        if s:
            rows.append((s, rva, "DiffableCs", label, entry.get("file", "")))

    # Collapse rows that point at the same method (same canonical RVA appears in
    # both asm_index and rva_index, and under leading-zero key variants). Keep
    # the best-scored row, prefer the DiffableCs label (it carries the full
    # signature), and merge the source tags.
    best: dict[str, list] = {}
    for s, rva, source, label, file_path in rows:
        key = format_rva(rva)
        cur = best.get(key)
        if cur is None:
            best[key] = [s, key, {source}, label, file_path, source]
            continue
        cur[2].add(source)
        if source == "DiffableCs" or s > cur[0]:
            cur[0] = max(cur[0], s)
            if source == "DiffableCs":
                cur[3], cur[4], cur[5] = label, file_path, source
            elif cur[5] != "DiffableCs":
                cur[3], cur[4], cur[5] = label, file_path, source
        else:
            cur[0] = max(cur[0], s)

    deduped = [
        (v[0], v[1], "+".join(sorted(v[2])), v[3], v[4])
        for v in best.values()
    ]
    deduped.sort(key=lambda r: (-r[0], r[3], r[1]))
    if not deduped:
        return f"No symbols matched {query!r}"

    out = [
        f"[version={version or DEFAULT_VERSION}] matches for {query!r} "
        f"(mode={mode}): {min(limit, len(deduped))}/{len(deduped)}"
    ]
    for _, rva, source, label, file_path in deduped[:limit]:
        out.append(f"  {rva:<12} {source:<18} {label}  ({file_path})")
    return "\n".join(out)
