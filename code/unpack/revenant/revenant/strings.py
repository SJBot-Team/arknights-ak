"""Metadata string literals, bucketed by what they look like.

The IL2CPP `global-metadata.dat` string-literal table is the game's `#US`
heap: every C# string literal, in one place, before any disassembly. Four of
eight real projects carried a byte-identical `dump_strlit.py` to read it and
split out the high-signal subsets -- URLs, analytics event names, dotted
config keys, format strings, feature flags, resource paths. Same script, four
copies, so it lives here (#32).

Bucketing is by shape only. A string can land in more than one bucket, and a
bucket says "looks like", not "is": `analytics-events` is snake_case tokens
with one to six underscores, which also catches enum-ish constants. The counts
are a first map of the game, not a conclusion.
"""

from __future__ import annotations

import json
import os
import re
import struct
from dataclasses import dataclass, field

METADATA_SANITY = 0xFAB11BAF

BUCKETS: tuple[tuple[str, re.Pattern], ...] = (
    ("urls", re.compile(r"https?://|\bwss?://|\.com/|\.cn/|api\.|cdn\.", re.I)),
    ("analytics-events", re.compile(r"^[a-z0-9]+(_[a-z0-9]+){1,6}$")),
    ("config-keys", re.compile(r"^[A-Za-z][A-Za-z0-9]*(\.[A-Za-z][A-Za-z0-9]*){1,5}$")),
    ("format-strings", re.compile(r"\{\d\}|\{[a-zA-Z_]+\}")),
    ("flags-toggles", re.compile(r"^(is|has|enable|disable|use|allow|show|force)[A-Z_]", re.I)),
    ("paths-addresses", re.compile(r"^[A-Za-z0-9_\-]+(/[A-Za-z0-9_\-. ]+){1,8}$")),
)
MIN_LEN, MAX_LEN = 4, 399   # `3 < len < 400`, as the source script had it

_CTRL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")


def escape(text: str) -> str:
    """One literal per line: escape what would break the line."""
    text = text.replace("\\", "\\\\").replace("\n", "\\n").replace("\r", "\\r").replace("\t", "\\t")
    return _CTRL.sub(lambda m: "\\x%02x" % ord(m.group()), text)


@dataclass
class StringDump:
    metadata_version: int = 0
    literals: list = field(default_factory=list)   # every string literal, table order
    names: list = field(default_factory=list)      # the metadata name heap
    buckets: dict = field(default_factory=dict)    # bucket -> sorted unique hits

    def stats(self) -> dict:
        return {
            "metadata_version": self.metadata_version,
            "string_literals": len(self.literals),
            "literal_bytes": sum(len(s.encode("utf-8", "replace")) for s in self.literals),
            "metadata_names": len(self.names),
            "buckets": {name: len(hits) for name, hits in self.buckets.items()},
        }


def read_literals(data: bytes) -> tuple[int, list[str], list[str]]:
    """(metadata version, string literals, name heap) from a plaintext metadata blob.

    Header fields after the sanity/version pair are byte offsets and sizes:
    stringLiteralOffset/Size, stringLiteralDataOffset/Size, stringOffset/Size.
    """
    if len(data) < 32:
        raise ValueError("metadata blob too small")
    sanity, version = struct.unpack_from("<II", data, 0)
    if sanity != METADATA_SANITY:
        raise ValueError(f"not plaintext IL2CPP metadata (sanity 0x{sanity:08X})")
    lit_off, lit_size, data_off, data_size, s_off, s_size = struct.unpack_from("<6i", data, 8)
    literals = []
    for i in range(lit_size // 8):
        length, idx = struct.unpack_from("<ii", data, lit_off + i * 8)
        literals.append(data[data_off + idx: data_off + idx + length].decode("utf-8", "replace"))
    names = [x.decode("utf-8", "replace") for x in data[s_off: s_off + s_size].split(b"\x00") if x]
    return version, literals, names


def bucket(literals: list[str]) -> dict:
    out = {}
    for name, rx in BUCKETS:
        out[name] = sorted({s for s in literals if MIN_LEN <= len(s) <= MAX_LEN and rx.search(s)})
    return out


def dump(metadata_path: str) -> StringDump:
    with open(metadata_path, "rb") as f:
        data = f.read()
    version, literals, names = read_literals(data)
    return StringDump(metadata_version=version, literals=literals, names=names, buckets=bucket(literals))


def write_dump(sd: StringDump, out_dir: str) -> dict:
    """The same files the project scripts wrote, so notes that cite them still resolve."""
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, "string-literals.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(escape(s) for s in sd.literals) + "\n")
    with open(os.path.join(out_dir, "metadata-names.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(sd.names) + "\n")
    for name, hits in sd.buckets.items():
        with open(os.path.join(out_dir, f"lit-{name}.txt"), "w", encoding="utf-8") as f:
            f.write("\n".join(escape(s) for s in hits) + "\n")
    stats = sd.stats()
    with open(os.path.join(out_dir, "_stats.json"), "w", encoding="utf-8") as f:
        json.dump(stats, f, indent=1)
    return stats
