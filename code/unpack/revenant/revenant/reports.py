"""User-facing reports composed from RE primitives.

Provides high-level commands for looking up methods, viewing assembly,
and exploring call targets.

Based on match3-core-sketch reports.py methodology.
"""

from __future__ import annotations

import os
import re

from .config import DEFAULT_VERSION
from .indices import (
    VERSIONS,
    first_index_match,
    format_rva,
    lookup_rva,
    normalize_rva,
    resolve_version,
    split_qualified_class,
)


# Cpp2IL renders some float immediates through a 64-bit read of a 32-bit value,
# so a literal `5.0` in the source arrives as `4.000000000232831` -- the round
# number plus an epsilon on the order of 2^-32, which is the low word leaking
# into the mantissa. Observed across one repository's nine games as
# 8.000000000465661, 4.000000000232831, 2.0000000002328306, 16.00000000325963.
#
# Not corrected, only marked. Which round number it "should" be is a guess, and
# a tool that quietly rewrites a constant is worse than one that prints a bad
# one: the reader can check a marked value against `revenant disasm`, and cannot
# check one that was silently changed. A day of nine-game work carried this in a
# person's head as "a long decimal tail probably means a round number" (#69).
_FLOAT_LITERAL = re.compile(r"(?<![\w.])(\d+\.\d{6,})(?![\w.])")
_EPSILON = 1e-7


def _suspect_floats(text: str) -> list:
    """Round-number-plus-epsilon literals in this listing, in order of first use."""
    seen, out = set(), []
    for raw in _FLOAT_LITERAL.findall(text):
        if raw in seen:
            continue
        try:
            value = float(raw)
        except ValueError:
            continue
        nearest = round(value)
        if nearest == value or not nearest:
            continue
        if abs(value - nearest) / abs(nearest) < _EPSILON:
            seen.add(raw)
            out.append((raw, nearest))
    return out


def annotate_float_immediates(text: str) -> str:
    """Append a note naming every float immediate that cannot be what it says."""
    suspects = _suspect_floats(text)
    if not suspects:
        return text
    lines = [text, "", "Suspect float immediates (Cpp2IL widens a 32-bit float "
             "through a 64-bit read, so a round constant arrives with a 2^-32 tail):"]
    for raw, nearest in suspects[:12]:
        lines.append(f"  {raw} -- almost certainly {nearest}")
    if len(suspects) > 12:
        lines.append(f"  ... {len(suspects) - 12} more")
    lines.append("  Not corrected here, because which round number it should be "
                 "is a guess. Confirm against `revenant disasm <rva>`.")
    return "\n".join(lines)


def find_asm_by_rva(address: str, version: str = "") -> str:
    """Find IsilDump assembly code for a method by RVA."""
    return annotate_float_immediates(_find_asm_by_rva(address, version))


def _find_asm_by_rva(address: str, version: str = "") -> str:
    vd = resolve_version(version or None)
    key = normalize_rva(address)

    # Try asm_index first
    asm_key, asm_entry = first_index_match(vd.asm_index, key)
    if asm_entry:
        file_path = _asm_file_path(asm_entry["file"], vd)
        if os.path.exists(file_path):
            method_code = _extract_method_code(file_path, asm_key)
            if method_code:
                return (
                    f"[version={version or DEFAULT_VERSION}] "
                    f"{asm_entry['type']}.{asm_entry['method']}\n"
                    f"Found in: {file_path}\n\n{method_code}"
                )

    # Try rva_index to locate the file
    _, rva_entry = first_index_match(vd.rva_index, key)
    if rva_entry:
        ns, cls = split_qualified_class(rva_entry["class"])
        return _find_asm_in_file(ns, cls, key, vd, version)

    return f"No method found at RVA {format_rva(key)}{' — try building indices first' if not VERSIONS else ''}"


def find_asm(namespace: str, class_name: str, address: str, version: str = "") -> str:
    """Find IsilDump assembly code by namespace/class and RVA."""
    vd = resolve_version(version or None)
    key = normalize_rva(address)
    return _find_asm_in_file(namespace, class_name, key, vd, version)


def _find_asm_in_file(namespace: str, class_name: str, rva: str, vd, version: str) -> str:
    il_files = _find_isil_files(vd, namespace, class_name)
    if not il_files:
        return f"No IsilDump files found for {namespace}.{class_name}"

    for file_path in il_files:
        method_code = _extract_method_code(file_path, rva)
        if method_code:
            return (
                f"[version={version or DEFAULT_VERSION}] Found in: {file_path}\n\n{method_code}"
            )
    return f"No method with RVA 0x{rva} found in {namespace}.{class_name}"


def slice_method(
    address: str,
    filter_expr: str = "",
    version: str = "",
    context: int = 4,
) -> str:
    """Show a slice of IsilDump assembly around an RVA with optional filtering."""
    vd = resolve_version(version or None)
    key = normalize_rva(address)
    asm_key, asm_entry = first_index_match(vd.asm_index, key)
    if not asm_entry:
        return f"No IsilDump entry for RVA {format_rva(key)}"

    file_path = _asm_file_path(asm_entry["file"], vd)
    if not os.path.exists(file_path):
        return f"IsilDump file missing: {file_path}"

    method_code = _extract_method_code(file_path, asm_key)
    if not method_code:
        return f"Method block not found in {file_path}"

    lines = method_code.split("\n")
    filter_lower = filter_expr.lower() if filter_expr else ""
    out = [
        f"[version={version or DEFAULT_VERSION}] Method slice: "
        f"{asm_entry['type']}.{asm_entry['method']}",
        f"RVA: {format_rva(asm_key)}  file: {file_path}",
        "",
    ]
    for i, line in enumerate(lines):
        if filter_lower and filter_lower not in line.lower():
            continue
        prefix = "  "
        out.append(f"{prefix}{line}")

    return "\n".join(out)


def find_asm_batch_by_rva(addresses: list[str], version: str = "") -> str:
    """Find IsilDump assembly for a batch of RVAs."""
    results = [f"[version={version or DEFAULT_VERSION}]"]
    for addr in addresses:
        result = find_asm_by_rva(addr, version)
        results.append(f"\n=== {format_rva(addr)} ===\n{result}")
    return "\n".join(results)


# ── Internal Helpers ───────────────────────────────────────────────────────

def _isil_root(vd) -> str:
    """Return the IsilDump directory (parent of all assembly subdirectories)."""
    return os.path.join(vd.root, "IsilDump")


def _asm_file_path(file_name: str, vd) -> str:
    """Resolve IsilDump file path, searching across assembly subdirectories."""
    root = _isil_root(vd)
    # Direct path (for flat layout or already-resolved paths)
    direct = os.path.join(root, file_name)
    if os.path.exists(direct):
        return direct
    # Search in all assembly subdirectories
    if os.path.isdir(root):
        for entry in sorted(os.listdir(root)):
            candidate = os.path.join(root, entry, file_name)
            if os.path.exists(candidate):
                return candidate
    return direct


def _find_isil_files(vd, namespace: str, class_name: str) -> list[str]:
    """Find IsilDump .txt files for a class."""
    if namespace:
        rel = os.path.join(*namespace.split("."), class_name)
    else:
        rel = class_name
    base = os.path.join(_isil_root(vd), rel)
    txt = base + ".txt"
    if os.path.exists(txt):
        return [txt]
    base_dir = os.path.dirname(base)
    if os.path.exists(base_dir):
        return [
            os.path.join(base_dir, f)
            for f in sorted(os.listdir(base_dir))
            if f.startswith(class_name) and f.endswith(".txt")
        ]
    return []


def _extract_method_code(file_path: str, target_rva: str) -> str | None:
    """Extract a single method's assembly block from an IsilDump file."""
    try:
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
    except OSError:
        return None

    target_lower = target_rva.lower()
    target_variants = [
        target_lower,
        target_lower.lstrip("0") or "0",
        target_lower.zfill(8),
    ]

    def has_target(block: str) -> bool:
        import re
        return any(
            re.search(rf"Disassembly:\s*\n\s*0x{re.escape(v)}\b", block, re.IGNORECASE)
            for v in target_variants
        )

    # Split into per-method blocks and return only the one whose disassembly
    # starts at the target RVA. blocks[0] is the file header (no "Method:").
    blocks = content.split("\nMethod: ")
    for block in blocks[1:]:
        candidate = "Method: " + block
        if has_target(candidate):
            return candidate
    # Header-less single-method file: fall back to the whole content.
    if "\nMethod: " not in content and has_target(content):
        return content
    return None
