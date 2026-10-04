#!/usr/bin/env python3
"""Build rva_index.json and asm_index.json from IsilDump .txt files.

Each .txt file contains method blocks:
    Type: <class>
    ...
    Method: <signature>
    Disassembly:
        0x<RVA> <mnemonic> ...
"""

from __future__ import annotations

import json
import os
import re
import sys

METHOD_RE = re.compile(r"^Method:\s*(.+)$")
TYPE_RE = re.compile(r"^Type:\s*(.+)$")
DISASM_FIRST_RE = re.compile(r"^\s*0x([0-9A-Fa-f]+)\b")


def build_indices(isil_root: str, output_dir: str) -> int:
    """Index the ISIL dump; returns the number of methods indexed."""
    rva_index: dict[str, dict] = {}
    asm_index: dict[str, dict] = {}

    txt_files = []
    for dirpath, dirnames, filenames in os.walk(isil_root):
        dirnames.sort()
        for fn in sorted(filenames):
            if fn.endswith(".txt"):
                txt_files.append(os.path.join(dirpath, fn))

    print(f"Scanning {len(txt_files)} .txt files...")

    for file_path in txt_files:
        rel_path = os.path.relpath(file_path, isil_root)
        try:
            with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                lines = f.readlines()
        except OSError:
            continue

        current_type = ""
        current_method = ""
        in_disasm = False
        method_entry_rva = ""

        for line in lines:
            # Type header
            type_match = TYPE_RE.match(line)
            if type_match:
                current_type = type_match.group(1).strip()
                continue

            # Method header
            method_match = METHOD_RE.match(line)
            if method_match:
                # If we had a previous method, store it
                if current_method and method_entry_rva:
                    _store_entry(asm_index, rva_index, method_entry_rva, rel_path, current_type, current_method)

                current_method = method_match.group(1).strip()
                in_disasm = False
                method_entry_rva = ""
                continue

            # Disassembly section
            if line.strip() == "Disassembly:":
                in_disasm = True
                continue

            if in_disasm:
                disasm_match = DISASM_FIRST_RE.match(line)
                if disasm_match and not method_entry_rva:
                    method_entry_rva = disasm_match.group(1).upper().zfill(8)
                    in_disasm = False

        # Store last method
        if current_method and method_entry_rva:
            _store_entry(asm_index, rva_index, method_entry_rva, rel_path, current_type, current_method)

    os.makedirs(output_dir, exist_ok=True)

    asm_path = os.path.join(output_dir, "asm_index.json")
    with open(asm_path, "w", encoding="utf-8") as f:
        json.dump(asm_index, f, indent=1, sort_keys=True)
    print(f"Wrote {len(asm_index)} entries to {asm_path}")

    rva_path = os.path.join(output_dir, "rva_index.json")
    with open(rva_path, "w", encoding="utf-8") as f:
        json.dump(rva_index, f, indent=1, sort_keys=True)
    print(f"Wrote {len(rva_index)} entries to {rva_path}")
    return len(asm_index)


def _store_entry(
    asm_index: dict,
    rva_index: dict,
    entry_rva: str,
    rel_path: str,
    class_name: str,
    method_sig: str,
) -> None:
    """Store an entry under multiple key variants."""
    base_class = class_name
    rva_key = entry_rva
    rva_stripped = rva_key.lstrip("0") or "0"

    asm_entry = {
        "file": rel_path,
        "type": base_class,
        "method": method_sig,
    }
    rva_entry = {
        "class": base_class,
        "signature": method_sig,
        "file": rel_path,
        "line": 0,
    }

    for key in (rva_key, rva_stripped):
        if key not in asm_index:
            asm_index[key] = asm_entry
        if key not in rva_index:
            rva_index[key] = rva_entry


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: build_indices.py <isil_root> <output_dir>")
        sys.exit(1)
    build_indices(sys.argv[1], sys.argv[2])
