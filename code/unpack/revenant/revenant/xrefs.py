"""Cross-reference and call graph helpers for IsilDump assemblies.

Finds which methods call/branch to a given RVA, and lists callees
for a given method RVA.

Based on match3-core-sketch xrefs.py methodology.
"""

from __future__ import annotations

import os
import re

from .config import DEFAULT_VERSION
from .indices import find_method_name_by_rva, format_rva, normalize_rva, resolve_version


def find_xrefs(
    address: str,
    version: str = "",
    limit: int = 50,
    mnemonic: str = "BL",
    root: str = "",
) -> str:
    """Find IsilDump references (cross-references) to an RVA.

    Args:
        address: Target RVA (hex string).
        version: Game version identifier.
        limit: Max results to return.
        mnemonic: Filter by mnemonic (default "BL" for call sites).
        root: Override IsilDump root directory.

    Returns:
        Formatted report of callers.
    """
    vd = resolve_version(version or None) if not root else None
    if not root and vd:
        root = os.path.join(vd.root, "IsilDump", "Assembly-CSharp")

    if not os.path.isdir(root):
        return f"IsilDump root not found: {root}"

    stripped = normalize_rva(address).lstrip("0") or "0"
    ref_re = re.compile(rf"\b{re.escape(mnemonic)}\s+0x0*{re.escape(stripped)}\b", re.IGNORECASE)

    rows: list[tuple[str, int, str, str]] = []
    total = 0

    for dirpath, dirnames, filenames in os.walk(root):
        dirnames.sort()
        for filename in sorted(filenames):
            if not filename.endswith(".txt"):
                continue
            full_path = os.path.join(dirpath, filename)
            try:
                with open(full_path, "r", encoding="utf-8", errors="replace") as f:
                    lines = f.readlines()
            except OSError:
                continue

            for idx, line in enumerate(lines):
                if not ref_re.search(line):
                    continue
                total += 1
                if len(rows) >= limit:
                    continue
                method = _find_method_name(lines, idx)
                rows.append((full_path, idx + 1, method, line.rstrip()))

    target = format_rva(address)
    out = [
        f"[{mnemonic}] xrefs to {target}: {len(rows)}/{total}",
    ]
    if not rows:
        out.append(_VIRTUAL_CAVEAT)
        return "\n".join(out)

    for num, (path, lineno, method, line) in enumerate(rows, 1):
        out.append("")
        out.append(f"{num:02d}. {method}")
        out.append(f"    {path}:{lineno}")
        out.append(f"    {line}")

    if total > len(rows):
        out.append(f"\n... {total - len(rows)} more; increase limit")
    # Always, not only when the count is low. The reading that needs correcting
    # -- "these are the call sites" -- is made just as confidently off twelve
    # hits as off zero, and the caveat that only prints on zero is the one
    # nobody has read by the time it matters.
    out.append(_VIRTUAL_CAVEAT)
    return "\n".join(out)


# Only DIRECT bl/b call sites are visible in IsilDump text. Everything else that
# can reach a method reaches it some other way, and none of those ways leave a
# BL behind. The list is spelled out rather than summarised as "indirect calls":
# a day of nine-game work read "0 callers" as "dead code" and had to derive the
# escape routes by hand, once per game. A tool that cannot see something can at
# least say what it cannot see (#69).
_VIRTUAL_CAVEAT = (
    "  (coverage: only direct BL/B call sites inside IsilDump are indexed.\n"
    "   Invisible here, and therefore NOT evidence of being unused: virtual\n"
    "   and interface dispatch, delegates and callbacks, hot-update\n"
    "   assemblies (HybridCLR / IFix patches), the xLua bridge, and the\n"
    "   Android DEX and native layers. Zero hits means 'no direct call in\n"
    "   this image', never 'unused'.)"
)


def callgraph(address: str, version: str = "", limit: int = 20, root: str = "") -> str:
    """Print direct callers and callees for a method RVA."""
    vd = resolve_version(version or None) if not root else None
    if not root and vd:
        root = os.path.join(vd.root, "IsilDump", "Assembly-CSharp")
    target = format_rva(address)

    out = [f"Callgraph for {target}"]
    hint = find_method_name_by_rva(address)
    if hint:
        out.append(f"Target: {hint}")
    out.append("")

    out.append("--- Direct callers ---")
    out.append(find_xrefs(address, version, limit=limit, mnemonic="BL", root=root))

    out.append("")
    out.append("--- External call/branch targets ---")
    callees = _extract_callees(address, root)
    if not callees:
        out.append("No external targets found.")
    else:
        out.append(f"showing {min(limit, len(callees))} of {len(callees)}"
                   if len(callees) > limit else f"{len(callees)} target(s)")
        for mnemonic, target_rva in callees[:limit]:
            hint = find_method_name_by_rva(target_rva) or "unknown"
            out.append(f"  {format_rva(target_rva):<12} {mnemonic:<2} {hint}")
        if len(callees) > limit:
            out.append(f"  ... {len(callees) - limit} more; increase limit")

    return "\n".join(out)


def _extract_callees(address: str, root: str) -> list[tuple[str, str]]:
    """Extract external BL/B targets from a method's IsilDump block."""
    stripped = normalize_rva(address).lstrip("0") or "0"
    target_lower = stripped.lower()

    # Find the method block in IsilDump files
    method_code = ""
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames.sort()
        for filename in sorted(filenames):
            if not filename.endswith(".txt"):
                continue
            full_path = os.path.join(dirpath, filename)
            try:
                with open(full_path, "r", encoding="utf-8", errors="replace") as f:
                    content = f.read()
            except OSError:
                continue

            # Look for method blocks containing the target RVA
            blocks = content.split("\nMethod: ")
            for block in blocks:
                if re.search(rf"\b0x0*{re.escape(target_lower)}\b", block, re.IGNORECASE):
                    method_code = "Method: " + block
                    break
            if method_code:
                break
        if method_code:
            break

    if not method_code:
        return []

    # Extract range
    range_match = re.search(r"\[0x([0-9A-Fa-f]+)\s*-\s*0x([0-9A-Fa-f]+)\]", method_code)
    start = end = None
    if range_match:
        start = int(range_match.group(1), 16)
        end = int(range_match.group(2), 16)

    # Find all BL/B targets outside the method range
    targets: list[tuple[str, str]] = []
    for m in re.finditer(r"\b(BL|B)\s+0x([0-9A-Fa-f]{5,})\b", method_code, re.IGNORECASE):
        mnemonic = m.group(1).upper()
        target = m.group(2).upper()
        tgt_int = int(target, 16)
        if start is not None and end is not None and start <= tgt_int < end:
            continue
        row = (mnemonic, target)
        if row not in targets:
            targets.append(row)
    return targets


def _find_method_name(lines: list[str], line_index: int) -> str:
    for idx in range(line_index, -1, -1):
        if lines[idx].startswith("Method: "):
            return lines[idx].removeprefix("Method: ").strip()
    return "unknown"
