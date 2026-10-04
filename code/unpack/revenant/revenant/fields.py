"""Field offset scanning over IsilDump text assemblies.

Finds memory accesses (LDR/STR) at specific field offsets across
all IsilDump method bodies, useful for understanding field usage patterns.

Based on match3-core-sketch fields.py methodology.
"""

from __future__ import annotations

import os
import re
from collections import defaultdict

from .config import DEFAULT_VERSION
from .indices import resolve_version

# ARM64 memory opcodes
MEMORY_OPS = {
    "LDR", "LDRB", "LDRH", "LDRSW", "LDUR", "LDURB", "LDURH",
    "STR", "STRB", "STRH", "STUR", "STURB", "STURH",
    "LDP", "STP",
}
WRITE_PREFIXES = ("STR", "STUR", "STP")

FIELD_LINE_RE = re.compile(
    r"\b(?P<op>LDR|LDRB|LDRH|LDRSW|LDUR|LDURB|LDURH|STR|STRB|STRH|STUR|STURB|STURH|LDP|STP)\b"
    r".*\[(?P<base>[XW]\d+|X31|SP)"
    r"(?:\s*(?:\+|, #|-)\s*(?P<offset>0x[0-9A-Fa-f]+|\d+))?",
    re.IGNORECASE,
)


def _normalize_offset(offset: str) -> int:
    raw = offset.strip().lower()
    if raw.startswith("0x"):
        return int(raw, 16)
    return int(raw, 10)


def _access_direction(op: str) -> str:
    return "write" if op.upper().startswith(WRITE_PREFIXES) else "read"


# What scanning by byte offset can and cannot see. This searches for a literal
# displacement in LDR/STR, so it finds fields reached as `this + 0x18` and
# nothing else. A field inside a container -- a List<T>, a Dictionary, a boxed
# struct -- is reached through the container's own storage, at an offset that
# has nothing to do with the field, so the scan comes back empty on a field that
# is read constantly. A day of nine-game work read one of those empties as "no
# one reads this" and only caught it by switching to a full-text read (#69).
_OFFSET_CAVEAT = (
    "  (coverage: matches a literal +offset in LDR/STR, so it sees fields\n"
    "   reached directly off an object pointer. Fields held inside containers\n"
    "   (List/Dictionary/array elements, boxed structs) are reached through\n"
    "   the container's storage at an unrelated offset and do NOT appear\n"
    "   here -- zero matches is not evidence the field is unused. For those,\n"
    "   read the type's methods (re_type_info, then the DiffableCs file).)"
)


def scan_field_accesses(
    root: str,
    target_offset: int,
    limit: int = 50,
    path_filter: str = "",
) -> str:
    """Scan IsilDump files for memory accesses at a given field offset.

    Args:
        root: IsilDump root directory.
        target_offset: Field offset to search for (in hex or decimal).
        limit: Max results to return.
        path_filter: Optional regex to filter file paths.

    Returns:
        Formatted report of matching accesses.
    """
    if not os.path.isdir(root):
        return f"IsilDump root not found: {root}"

    path_re = re.compile(path_filter, re.IGNORECASE) if path_filter else None
    rows: list[tuple[str, int, str, str, str, str]] = []
    total = 0

    for dirpath, dirnames, filenames in os.walk(root):
        dirnames.sort()
        for filename in sorted(filenames):
            if not filename.endswith(".txt"):
                continue
            full_path = os.path.join(dirpath, filename)
            if path_re and not path_re.search(full_path):
                continue
            try:
                with open(full_path, "r", encoding="utf-8", errors="replace") as f:
                    lines = f.readlines()
            except OSError:
                continue

            for idx, line in enumerate(lines):
                m = FIELD_LINE_RE.search(line)
                if not m:
                    continue
                op = m.group("op").upper()
                if op not in MEMORY_OPS:
                    continue
                offset_str = m.group("offset")
                if offset_str is None:
                    continue
                if _normalize_offset(offset_str) != target_offset:
                    continue

                total += 1
                if len(rows) >= limit:
                    continue
                direction = _access_direction(op)
                # extract method name from surrounding context
                method = _find_method_name(lines, idx)
                rows.append((full_path, idx + 1, method, op, direction, line.rstrip()))

    out = [
        f"Field offset +0x{target_offset:X}: {len(rows)}/{total} accesses",
        _OFFSET_CAVEAT,
    ]
    if path_filter:
        out.append(f"filter: /{path_filter}/")

    if not rows:
        return "\n".join(out + ["(no matches)"])

    for num, (path, lineno, method, op, direction, line) in enumerate(rows, 1):
        out.append("")
        out.append(f"{num:02d}. {method}  [{direction} via {op}]")
        out.append(f"    {path}:{lineno}")
        out.append(f"    {line}")

    if total > len(rows):
        out.append(f"\n... {total - len(rows)} more; increase limit ({limit}) to see more")
    return "\n".join(out)


def _find_method_name(lines: list[str], line_index: int) -> str:
    """Walk backwards from a line to find the enclosing method name."""
    for idx in range(line_index, -1, -1):
        if lines[idx].startswith("Method: "):
            return lines[idx].removeprefix("Method: ").strip()
    return "unknown"
