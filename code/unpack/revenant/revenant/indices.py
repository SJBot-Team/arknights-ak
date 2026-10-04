"""RVA index loading and symbol lookup.

Manages pre-built JSON indices that map RVAs to method/class information.
Indices are produced by running a cpp2il dumper on the IL2CPP binary.

Based on match3-core-sketch indices.py methodology.
"""

from __future__ import annotations

import json
import os
import re
import sys
from dataclasses import dataclass, field

from .config import DEFAULT_VERSION


@dataclass
class VersionData:
    """Data for one game version."""
    root: str
    rva_index: dict = field(default_factory=dict)
    asm_index: dict = field(default_factory=dict)


VERSIONS: dict[str, VersionData] = {}


def load_version(name: str, root: str, verbose: bool = False) -> None:
    """Load pre-built JSON indices for a single version."""
    vd = VersionData(root=root)

    # Try cpp2il_out root first, then index/ subdir
    for path_suffix in ["", "index"]:
        rva_path = os.path.join(root, path_suffix, "rva_index.json")
        if os.path.exists(rva_path):
            with open(rva_path, "r", encoding="utf-8") as f:
                vd.rva_index = json.load(f)
            break

    for path_suffix in ["", "index"]:
        asm_path = os.path.join(root, path_suffix, "asm_index.json")
        if os.path.exists(asm_path):
            with open(asm_path, "r", encoding="utf-8") as f:
                vd.asm_index = json.load(f)
            break

    VERSIONS[name] = vd
    if verbose:
        count = len(vd.rva_index) + len(vd.asm_index)
        print(f"  Loaded version '{name}': {count:,} index entries from {root}", file=sys.stderr)


def resolve_version(version: str | None = None) -> VersionData:
    """Resolve a version name to its data, falling back to default."""
    if version and version in VERSIONS:
        return VERSIONS[version]
    if DEFAULT_VERSION in VERSIONS:
        return VERSIONS[DEFAULT_VERSION]
    if VERSIONS:
        return next(iter(VERSIONS.values()))
    raise RuntimeError("No versions loaded. Use load_version() first.")


def normalize_rva(rva: str) -> str:
    """Normalize RVA to uppercase without 0x prefix."""
    return rva.strip().upper().replace("0X", "")


def looks_like_rva(value: str) -> bool:
    return bool(re.fullmatch(r"0x[0-9A-Fa-f]+|[0-9A-Fa-f]{5,}", value.strip()))


def split_qualified_class(type_name: str) -> tuple[str, str]:
    """Split a fully-qualified type name into namespace and class name."""
    type_name = type_name.strip()
    if "." not in type_name:
        return "", type_name
    namespace, class_name = type_name.rsplit(".", 1)
    return namespace, class_name


def rva_key_variants(rva: str) -> list[str]:
    """Return index key variants for RVA strings with inconsistent leading zeroes."""
    raw = normalize_rva(rva)
    stripped = raw.lstrip("0") or "0"
    padded8 = stripped.zfill(8)
    variants = []
    for candidate in (raw, stripped, padded8):
        if candidate not in variants:
            variants.append(candidate)
    return variants


def format_rva(rva: str) -> str:
    """Format an RVA string to canonical 8-digit hex."""
    stripped = normalize_rva(rva).lstrip("0") or "0"
    return "0x" + stripped.zfill(8).upper()


def display_signature(signature: str) -> str:
    """Format indexed signatures without misleading stub bodies."""
    return re.sub(r"\s*\{\s*\}\s*$", "", signature.strip())


def first_index_match(index: dict, rva: str) -> tuple[str | None, dict | None]:
    """Find the first index entry matching an RVA across key variants."""
    for key in rva_key_variants(rva):
        entry = index.get(key)
        if entry:
            return key, entry
    return None, None


def find_method_name_by_rva(rva: str, vd: VersionData | None = None) -> str | None:
    """Look up a method signature by RVA using pre-built indices."""
    if vd is None:
        vd = resolve_version(None)
    key = normalize_rva(rva)

    _, entry = first_index_match(vd.asm_index, key)
    if entry:
        return f"{entry['type']}: {entry['method']}"

    _, entry = first_index_match(vd.rva_index, key)
    if entry:
        return f"{entry['class']}: {display_signature(entry['signature'])}"

    return None


def lookup_rva(address: str, version: str = "") -> str:
    """Look up what method lives at a given RVA address."""
    vd = resolve_version(version or None)
    key = normalize_rva(address)
    parts = [f"[version={version or DEFAULT_VERSION}]"]

    asm_key, asm_entry = first_index_match(vd.asm_index, key)
    if asm_entry:
        parts.append(
            f"IsilDump: {asm_entry['type']}.{asm_entry['method']}"
            f" (rva-key: 0x{asm_key}, file: {asm_entry['file']})"
        )

    rva_key, rva_entry = first_index_match(vd.rva_index, key)
    if rva_entry:
        parts.append(
            f"DiffableCs: {rva_entry['class']}"
            f" | {display_signature(rva_entry['signature'])}"
            f" (rva-key: 0x{rva_key}, file: {rva_entry['file']}:{rva_entry['line']})"
        )

    if len(parts) == 1:
        return f"No exact indexed method found at RVA {format_rva(key)}"
    return f"RVA {format_rva(key)}:\n" + "\n".join(parts)


def available_versions_hint() -> str:
    """Return a hint string listing available versions."""
    if not VERSIONS:
        return ""
    return f" (available: {', '.join(sorted(VERSIONS.keys()))})"
