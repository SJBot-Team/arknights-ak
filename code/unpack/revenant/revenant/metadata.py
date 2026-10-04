"""global-metadata.dat parser for Unity IL2CPP.

Minimal parser for the IL2CPP metadata file typically found at
assets/bin/Data/Managed/Metadata/global-metadata.dat inside the APK.

Supports string literal lookups and metadata usage decoding.
Based on match3-core-sketch static_data.py methodology.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass

from .binary import find_global_metadata

METADATA_SANITY = 0xFAB11BAF

METADATA_USAGE_TYPES = {
    1: "type-info",
    2: "il2cpp-type",
    3: "method-def",
    4: "field-info",
    5: "string-literal",
    6: "method-ref",
}


@dataclass(frozen=True)
class MetadataUsage:
    """Decoded IL2CPP metadata usage encoded pointer value."""
    encoded: int
    usage_type: int
    index: int

    @property
    def usage_name(self) -> str:
        return METADATA_USAGE_TYPES.get(self.usage_type, f"unknown-{self.usage_type}")


class Il2CppMetadata:
    """Minimal global-metadata.dat parser for string literal lookups."""

    def __init__(self, path: str):
        with open(path, "rb") as f:
            self.data = f.read()
        if len(self.data) < 24:
            raise ValueError(f"metadata file too small: {path}")
        self.sanity, self.version = struct.unpack_from("<II", self.data, 0)
        if self.sanity != METADATA_SANITY:
            raise ValueError(
                f"metadata sanity mismatch in {path}: 0x{self.sanity:08X}"
            )
        # IL2CPP metadata header layout:
        #   0: sanity (4)
        #   4: version (4)
        #   8: stringLiteralOffset (4)
        #  12: stringLiteralCount (4)
        #  16: stringLiteralDataOffset (4)
        #  20: stringLiteralDataCount (4)
        (
            self.string_literal_offset,
            self.string_literal_count,
            self.string_literal_data_offset,
            self.string_literal_data_count,
        ) = struct.unpack_from("<IIII", self.data, 8)

    def string_literal(self, index: int) -> str | None:
        """Look up a string literal by index."""
        entry_offset = self.string_literal_offset + index * 8
        if entry_offset < 0 or entry_offset + 8 > self.string_literal_offset + self.string_literal_count * 8:
            return None
        length, data_idx = struct.unpack_from("<II", self.data, entry_offset)
        data_offset = self.string_literal_data_offset + data_idx
        data_end = data_offset + length
        if data_idx < 0 or data_end > self.string_literal_data_offset + self.string_literal_data_count:
            return None
        return self.data[data_offset:data_end].decode("utf-8", errors="replace")


def decode_metadata_usage(encoded: int) -> MetadataUsage:
    """Decode an IL2CPP metadata usage encoded pointer value.

    Bit layout:
      bits [31:29] = usage type (3 bits)
      bits [28:1]  = index (28 bits)
      bit  [0]     = unused
    """
    usage_type = (encoded >> 29) & 0x7
    index = (encoded >> 1) & ((1 << 28) - 1)
    return MetadataUsage(encoded=encoded, usage_type=usage_type, index=index)


def metadata_string_lookup(
    encoded_value: int,
    metadata_path: str | None = None,
) -> str:
    """Look up a string from a metadata usage encoded value."""
    usage = decode_metadata_usage(encoded_value)
    if usage.usage_type != 5:
        return f"<not a string-literal usage: {usage.usage_name}>"

    if metadata_path is None:
        meta_loc = find_global_metadata()
        metadata_path = meta_loc.path

    metadata = Il2CppMetadata(metadata_path)
    value = metadata.string_literal(usage.index)
    if value is None:
        return f"<string index {usage.index} out of range>"
    return value
