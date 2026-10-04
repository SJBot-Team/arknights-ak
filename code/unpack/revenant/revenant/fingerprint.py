"""Cold start, step one: a package-level list of observations.

Purely static, and it runs **before Cpp2IL** -- no class names, no index. That
ordering is the point. "How do I find the hotspots in a new game" assumes the
first move happens on an index; the move that actually works happens the moment
you open the package.

This module **observes and does not judge** (ADR-0002). It used to: a table of
marker strings decided "this is HybridCLR" and that verdict stood as a hard
gate in front of the breadth scan. One packer wiped one string and the gate
failed in the dangerous direction -- it let a scan through that hit zero on
every slot and reported the game as having none of it. The same-origin score
and the build-path ranking were tuned after looking at eight titles' results,
which is fitting the ruler to the things it measured. Both are gone. What is
left is a list of things that were looked for, what was found, and where; the
agent reads it and decides what stack this is and which known title it is
like. Verdict fields (a corpus verdict, a scripting scheme, a vendor name, a
same-origin score) do not appear in the output on purpose.

The method comes from a cross-game study that fingerprinted eight competitors
with eleven reproducible commands. Four traps it recorded are reproduced here
rather than rediscovered:

1. macOS `strings` cannot do wide characters and silently voids the whole call,
   so .NET `#US` heaps (UTF-16LE) must be decoded explicitly.
2. Package names from a dex must be taken 4-5 segments deep; three segments
   collapses AdMob/Play Games/Play Integrity into `com/google/android` and
   produces a fake "this game has no ads" table.
3. The assembly manifest and the metadata must be cross-checked -- in the
   manifest but not the metadata means stripped, unused, or loaded from
   somewhere else; the difference is listed, not interpreted.
4. Native library vendors must never be guessed from the file name. The
   exported symbols are listed as they are; naming the vendor is the reader's.

One observation the study's roadmap rated above the manifest difference for
"where does the business code live": the `*.bytes` literals in the metadata
string heap. A title that loads hot-update assemblies names them there, and a
recovered metadata lists exactly those (three, on the reference title).
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import struct
from dataclasses import dataclass, field

from . import layout as _layout

BUILD_PATH = re.compile(rb"(?:/Users/|/home/|/Applications/|[A-Za-z]:\\\\)[\x20-\x7e]{4,120}")
URL = re.compile(rb"https?://[a-zA-Z0-9._-]+\.[a-z]{2,6}")
UNITY_VERSION = re.compile(rb"(\d{4}\.\d+\.\d+[a-z]\d+)")
DEX_TYPE = re.compile(rb"L([a-z]{2,4}/[A-Za-z0-9_]+(?:/[A-Za-z0-9_]+){1,4});")
JAVA_EXPORT = re.compile(rb"Java_[A-Za-z0-9_]{4,120}")
# A literal that names a file (`common_c_md.bytes`, `hotfix/x.patch.bytes`,
# `shaders/{0}.bytes`). Suffix-only literals (`.bytes`, `*.lua.bytes`) are the
# loader's extension check, not a file, and are dropped.
BYTES_LITERAL = re.compile(r"(?<![A-Za-z0-9_./{}\-])[A-Za-z0-9_{}][A-Za-z0-9_./{}\-]{0,95}\.bytes\b")

# The marker tables. These are the strings that were *searched for*; every
# entry is reported with its hit count, zero included, so a wiped marker shows
# up as a zero next to its siblings instead of silently changing a verdict.
# Counted case-sensitively everywhere: `XLua` and `xlua` are two searches.
MARKER_TABLES: dict[str, tuple[bytes, ...]] = {
    "hybridclr": (b"HybridCLR", b"InterpreterImage", b"LoadMetadataForAOTAssembly"),
    "ifix": (b"IFix.ILFixInterfaceBridge", b"IFix.IL"),
    "xlua": (b"XLua", b"xlua", b"LuaEnv"),
    "tolua": (b"tolua", b"ToLua", b"LuaState"),
}

# Where a marker was looked for. `members` is the archive's file list (a
# `libxlua.so` is a member name, not a byte string inside the binary).
WHERE_BINARY = "binary"
WHERE_DEX = "dex"
WHERE_MEMBERS = "members"

# Caps on what is kept; every capped list carries its total alongside.
MAX_BUILD_PATHS = 40
MAX_DOMAINS = 40
MAX_DEX_PACKAGES = 120
MAX_EXPORTS_PER_LIB = 40
MAX_LIBS_READ = 30            # native libraries opened for exports
MAX_LIB_BYTES_READ = 8_000_000
MAX_BYTES_LITERALS = 60
MAX_SIGNING_CERTS = 8
# How much of each certificate digest to keep. Enough to compare two packages
# or two versions; it identifies a signer, it is not a secret.
CERT_DIGEST_CHARS = 16
# Rows shown per list in the human report.
SHOW_ABSENT = 20
SHOW_DEX = 30
SHOW_EXPORTS = 5
SHOW_NOTE = 6


@dataclass
class MarkerSeen:
    """One marker string from one table: what was searched, hits per place."""

    table: str
    marker: str
    hits: dict = field(default_factory=dict)   # where -> count

    @property
    def total(self) -> int:
        return sum(self.hits.values())

    def to_json(self) -> dict:
        return {"table": self.table, "marker": self.marker, "hits": dict(self.hits)}


@dataclass
class Fingerprint:
    """The observation list. Every field is something that was seen, not decided."""

    package: str = ""
    version: str = ""
    platform: str = ""
    kind: str = ""                       # apk | xapk | ipa
    unity_version: str = ""
    build_paths: list = field(default_factory=list)          # as found, deduplicated, sorted
    build_paths_total: int = 0                               # before the cap
    markers_seen: list = field(default_factory=list)         # [MarkerSeen], zero hits included
    declared_assemblies: list = field(default_factory=list)  # ScriptingAssemblies.json, type 16
    assemblies_in_metadata: list = field(default_factory=list)
    assemblies_absent: list = field(default_factory=list)    # declared minus in_metadata
    bytes_literals: list = field(default_factory=list)       # `*.bytes` in the metadata string heap
    metadata_source: str = ""                                # which metadata copy was read
    native_libs: list = field(default_factory=list)
    native_exports: dict = field(default_factory=dict)       # lib -> [Java_* symbols], as found
    signing_certs: dict = field(default_factory=dict)        # META-INF cert member -> sha256 prefix
    dex_packages: list = field(default_factory=list)         # 4-segment package prefixes
    dex_packages_total: int = 0
    domains: list = field(default_factory=list)
    domains_total: int = 0
    asset_pipeline: list = field(default_factory=list)
    section_names: list = field(default_factory=list)

    def markers(self, table: str) -> list:
        return [m for m in self.markers_seen if m.table == table]

    def marker_hits(self, table: str) -> int:
        return sum(m.total for m in self.markers(table))

    def business_assemblies_absent(self) -> list:
        """Declared *game* assemblies the metadata does not contain.

        The one fact-shaped hint this module offers, and it is a filter, not a
        verdict: engine and SDK assemblies are stripped routinely when unused,
        so those are left out or every title looks like it hides its code.
        """
        from .config import is_game_assembly
        return [n for n in self.assemblies_absent if is_game_assembly(n)]

    def absent_note(self) -> str:
        """The one sentence about that list, worded once, used by the report and
        by the scan's warning so the two cannot drift apart. "" when empty."""
        absent = self.business_assemblies_absent()
        if not absent:
            return ""
        return (
            f"{len(absent)} declared game assemblies do not exist in the corpus about "
            f"to be searched: {', '.join(absent[:SHOW_NOTE])}"
            + (" ..." if len(absent) > SHOW_NOTE else "")
        )

    def to_json(self) -> dict:
        return {
            "package": self.package, "version": self.version,
            "platform": self.platform, "kind": self.kind,
            "unity_version": self.unity_version,
            "build_paths": self.build_paths,
            "build_paths_total": self.build_paths_total,
            "markers_seen": [m.to_json() for m in self.markers_seen],
            "declared_assemblies": self.declared_assemblies,
            "assemblies_in_metadata": self.assemblies_in_metadata,
            "assemblies_absent": self.assemblies_absent,
            "business_assemblies_absent": self.business_assemblies_absent(),
            "bytes_literals": self.bytes_literals,
            "metadata_source": self.metadata_source,
            "signing_certs": self.signing_certs,
            "native_libs": self.native_libs,
            "native_exports": self.native_exports,
            "dex_packages": self.dex_packages,
            "dex_packages_total": self.dex_packages_total,
            "domains": self.domains,
            "domains_total": self.domains_total,
            "asset_pipeline": self.asset_pipeline,
            "section_names": self.section_names,
        }


def _decode_both(data: bytes) -> str:
    """latin-1 and utf-16-le, because a .NET string heap is the latter.

    Trap 1 from the study: the platform `strings` cannot see UTF-16LE and does
    not tell you it failed, which is how a whole class of user strings goes
    missing without a trace.
    """
    out = data.decode("latin-1", errors="ignore")
    try:
        out += "\n" + data.decode("utf-16-le", errors="ignore")
    except Exception:
        pass
    return out


def _members(package_path: str, lay) -> list[str]:
    names: list[str] = []
    for _desc, archive in _layout.iter_archives(package_path, lay):
        names.extend(archive.namelist())
    return names


def _read_first(package_path: str, lay, patterns) -> bytes | None:
    hit = _layout.find_in_package(package_path, lay, tuple(patterns))
    return hit[1] if hit else None


def collect_markers(binary: bytes, members: list[str], dex_blobs: list[bytes]) -> list[MarkerSeen]:
    """Every marker of every table, counted in every place it was looked for."""
    out: list[MarkerSeen] = []
    for table, markers in MARKER_TABLES.items():
        for marker in markers:
            seen = MarkerSeen(table=table, marker=marker.decode("latin-1"))
            seen.hits[WHERE_BINARY] = binary.count(marker) if binary else 0
            seen.hits[WHERE_DEX] = sum(blob.count(marker) for blob in dex_blobs)
            needle = marker.decode("latin-1")
            seen.hits[WHERE_MEMBERS] = sum(1 for n in members if needle in n)
            out.append(seen)
    return out


def collect_declared_assemblies(package_path: str, lay) -> list[str]:
    """Assemblies the game itself ships (`type == 16` in the Unity manifest)."""
    raw = _read_first(package_path, lay, [
        "assets/bin/Data/ScriptingAssemblies.json",
        "Payload/*.app/Data/ScriptingAssemblies.json",
    ])
    if not raw:
        return []
    try:
        parsed = json.loads(raw)
        return [n for n, t in zip(parsed.get("names", []), parsed.get("types", [])) if t == 16]
    except Exception:
        return []


def collect_native_exports(package_path: str, lay, libs: list[str]) -> dict:
    """`Java_*` exported symbols per native library, as found (trap 4).

    Bounded: at most MAX_LIBS_READ libraries are opened, MAX_LIB_BYTES_READ
    bytes each; the first copy of a name wins across split archives.
    """
    out: dict = {}
    opened = 0
    wanted = {n for n in libs if n.endswith(".so")}
    for _desc, archive in _layout.iter_archives(package_path, lay):
        for name in archive.namelist():
            if name not in wanted or name in out or opened >= MAX_LIBS_READ:
                continue
            opened += 1
            try:
                with archive.open(name) as handle:
                    data = handle.read(MAX_LIB_BYTES_READ)
            except Exception:
                continue
            hits = sorted({m.group(0).decode("latin-1") for m in JAVA_EXPORT.finditer(data)})
            out[name] = hits[:MAX_EXPORTS_PER_LIB]
    return {k: v for k, v in out.items() if v}


def collect_signing_certs(package_path: str, lay) -> dict:
    """`META-INF/*.{RSA,DSA,EC}` certificate blocks, digested.

    An observation, not a verdict (ADR-0002): the digest says *which* signer,
    never *whether* the signer is right. Two uses it serves, both the reader's
    to make -- a mirror that repackages a build has to resign it, so a digest
    differing from another copy of the same version is a resigning; and two
    packages sharing a digest were signed by the same key, which is a harder
    same-origin signal than a shared decryption key.
    """
    out: dict = {}
    for _desc, archive in _layout.iter_archives(package_path, lay):
        for name in sorted(archive.namelist()):
            upper = name.upper()
            if not upper.startswith("META-INF/") or not upper.endswith((".RSA", ".DSA", ".EC")):
                continue
            if name in out or len(out) >= MAX_SIGNING_CERTS:
                continue
            try:
                blob = archive.read(name)
            except Exception:
                continue
            out[name] = hashlib.sha256(blob).hexdigest()[:CERT_DIGEST_CHARS]
    return out


def collect_bytes_literals(metadata: bytes) -> list[str]:
    """`*.bytes` string literals in a metadata blob that name a file.

    Read from the string-literal table when the header parses (plaintext
    metadata), otherwise from a text sweep of the raw bytes -- an obfuscated
    heap still often keeps its literals in the clear. Suffix-only literals
    (`.bytes`, `*.lua.bytes`) are the loader's extension check and are dropped.
    """
    found: set[str] = set()
    try:
        from .metadata import METADATA_SANITY
        if len(metadata) >= 24 and struct.unpack_from("<I", metadata, 0)[0] == METADATA_SANITY:
            # Header fields are byte sizes, not counts: stringLiteralOffset,
            # stringLiteralSize, stringLiteralDataOffset, stringLiteralDataSize.
            lit_off, lit_size, data_off, data_size = struct.unpack_from("<IIII", metadata, 8)
            for i in range(min(lit_size // 8, 2_000_000)):
                length, idx = struct.unpack_from("<II", metadata, lit_off + i * 8)
                if idx + length > data_size or length > 4096:
                    continue
                text = metadata[data_off + idx: data_off + idx + length].decode("utf-8", "replace")
                if text.endswith(".bytes") and BYTES_LITERAL.fullmatch(text):
                    found.add(text)
    except Exception:
        found = set()
    if not found:
        found = set(BYTES_LITERAL.findall(_decode_both(metadata)))
    return sorted(found)[:MAX_BYTES_LITERALS]


def _recovered_metadata() -> tuple[bytes, str] | None:
    """The plaintext metadata the project has recovered, if any.

    On a packed title the copy inside the package is ciphertext; the literals
    and the assembly names can only be read from the copy in `_binaries/`
    (dumped from a process, or written by the project's decryptor). Read-only:
    nothing here extracts, decrypts or quarantines -- that is `find-metadata`.
    A project holding several packages shares one `_binaries/`; the report
    names the file it read so the reader can tell.
    """
    try:
        from .binary import _looks_like_metadata
        from .config import workspace_root
        cache = os.path.join(workspace_root(), "_binaries")
    except Exception:
        return None
    if not os.path.isdir(cache):
        return None
    for name in sorted(os.listdir(cache)):
        full = os.path.join(cache, name)
        if name.endswith("-global-metadata.dat") and _looks_like_metadata(full):
            with open(full, "rb") as f:
                return f.read(), full
    return None


def _is_plaintext_metadata(blob: bytes) -> bool:
    from .metadata import METADATA_SANITY
    return len(blob) >= 24 and struct.unpack_from("<I", blob, 0)[0] == METADATA_SANITY


def collect(package_path: str, lay=None, deep: bool = True) -> Fingerprint:
    """Fingerprint one package. Static only -- never runs the game."""
    lay = lay or _layout.layout_for(package_path)
    if lay is None:
        raise ValueError(f"{package_path} is not a recognised game package")

    fp = Fingerprint(kind=lay.kind, platform=lay.platform)
    identity = _layout.read_identity(package_path, lay)
    fp.package = identity.get("package", "")
    fp.version = identity.get("version", "")

    members = _members(package_path, lay)
    fp.native_libs = sorted({
        n for n in members if n.endswith(".so") or "/Frameworks/" in n
    })[:80]
    fp.asset_pipeline = sorted({
        root for root in lay.bundle_roots
        if any(n.startswith(root.split("*")[0]) for n in members)
    }) or sorted({n.split("/")[2] for n in members if n.count("/") > 2 and "aa" in n})[:6]

    ggm = _read_first(package_path, lay, lay.ggm_paths)
    if ggm:
        match = UNITY_VERSION.search(ggm[:4096])
        if match:
            fp.unity_version = match.group(1).decode()

    binary = _read_first(package_path, lay, lay.binary_paths) if deep else None
    if binary:
        fp.build_paths, fp.build_paths_total = collect_build_paths(binary)
        fp.section_names = collect_section_names(binary)

    # Everything read out of the metadata prefers the recovered plaintext copy
    # (`_binaries/`, dumped or decrypted) over the copy in the package, which
    # on a packed title is ciphertext and would make every check below read
    # "nothing found".
    metadata: bytes | None = None
    if deep:
        recovered = _recovered_metadata()
        if recovered:
            metadata, fp.metadata_source = recovered
        else:
            metadata = _read_first(package_path, lay, lay.metadata_paths)
            if metadata and _is_plaintext_metadata(metadata):
                fp.metadata_source = "package"
            elif metadata:
                fp.metadata_source = ("package copy, not plaintext metadata -- "
                                      "everything below it is a text sweep of ciphertext")
    if metadata:
        domains = sorted({m.group(0).decode("latin-1") for m in URL.finditer(metadata)})
        fp.domains, fp.domains_total = domains[:MAX_DOMAINS], len(domains)
        fp.bytes_literals = collect_bytes_literals(metadata)

    dex_blobs: list[bytes] = []
    if lay.platform == _layout.PLATFORM_ANDROID and deep:
        for _desc, archive in _layout.iter_archives(package_path, lay):
            for name in archive.namelist():
                if name.startswith("classes") and name.endswith(".dex"):
                    dex_blobs.append(archive.read(name))
            if dex_blobs:
                break
    packages: set[str] = set()
    for blob in dex_blobs:
        # Trap 2: 4-5 segments deep, or AdMob and friends vanish into
        # `com/google/android` and the table lies about ad integration.
        for match in DEX_TYPE.finditer(blob):
            segments = match.group(1).decode("latin-1").split("/")
            if len(segments) >= 4:
                packages.add("/".join(segments[:4]))
    fp.dex_packages, fp.dex_packages_total = sorted(packages)[:MAX_DEX_PACKAGES], len(packages)

    fp.markers_seen = collect_markers(binary or b"", members, dex_blobs)
    fp.signing_certs = collect_signing_certs(package_path, lay)
    if deep:
        fp.native_exports = collect_native_exports(package_path, lay, fp.native_libs)

    # Trap 3: the manifest against the metadata. Listed both ways plus the
    # difference; the reader decides what an absence means. Whole-name match,
    # or `Game.dll` would be found inside `MyGame.dll`.
    fp.declared_assemblies = collect_declared_assemblies(package_path, lay)
    if fp.declared_assemblies and metadata:
        fp.assemblies_in_metadata = [
            n for n in fp.declared_assemblies
            if re.search(rb"(?<![A-Za-z0-9_.])" + re.escape(n.encode("utf-8")) + rb"(?![A-Za-z0-9_])",
                         metadata)
        ]
        fp.assemblies_absent = [
            n for n in fp.declared_assemblies if n not in fp.assemblies_in_metadata
        ]

    return fp


def collect_build_paths(binary: bytes) -> tuple[list[str], int]:
    """Build-machine paths, as found: deduplicated, trimmed after the project
    root markers, alphabetical. No ranking -- the study's most informative
    dimension is left for the reader to weigh, because the ranking that used
    to sit here was tuned on the eight titles it was then applied to.

    Returns (paths, total_before_cap).
    """
    paths = {m.group(0).decode("latin-1", "ignore") for m in BUILD_PATH.finditer(binary)}
    trimmed: set[str] = set()
    for path in paths:
        for cut in ("Il2CppOutputProject", "libil2cpp", "/Library/", "/Unity.app"):
            if cut in path:
                path = path.split(cut)[0]
        path = path.rstrip("/")
        if 8 < len(path) < 120:
            trimmed.add(path)
    ordered = sorted(trimmed)
    return ordered[:MAX_BUILD_PATHS], len(ordered)


def collect_section_names(binary: bytes) -> list[str]:
    """Section/segment names, which is how packers announce themselves.

    A packer leaves its own sections behind (`.nep_export_*` and the like), and
    that is the cheapest packing signal available. Must be read from the copy
    inside the package: a binary recovered from a memory dump is already
    unpacked and will not show them.
    """
    names: list[str] = []
    try:
        if binary[:4] == b"\x7fELF":
            is64 = binary[4] == 2
            endian = "<" if binary[5] == 1 else ">"
            if is64:
                shoff = struct.unpack_from(f"{endian}Q", binary, 40)[0]
                shentsize = struct.unpack_from(f"{endian}H", binary, 58)[0]
                shnum = struct.unpack_from(f"{endian}H", binary, 60)[0]
                shstrndx = struct.unpack_from(f"{endian}H", binary, 62)[0]
            else:
                shoff = struct.unpack_from(f"{endian}I", binary, 32)[0]
                shentsize = struct.unpack_from(f"{endian}H", binary, 46)[0]
                shnum = struct.unpack_from(f"{endian}H", binary, 48)[0]
                shstrndx = struct.unpack_from(f"{endian}H", binary, 50)[0]
            if not shoff or shstrndx >= shnum:
                return []
            str_hdr = shoff + shstrndx * shentsize
            str_off = struct.unpack_from(f"{endian}Q" if is64 else f"{endian}I",
                                         binary, str_hdr + (24 if is64 else 16))[0]
            for i in range(min(shnum, 200)):
                at = shoff + i * shentsize
                name_off = struct.unpack_from(f"{endian}I", binary, at)[0]
                end = binary.index(b"\0", str_off + name_off)
                names.append(binary[str_off + name_off:end].decode("latin-1"))
        else:
            from .image import MachOImage
            image = MachOImage("<memory>", binary)
            names = [name for name, *_ in image._sections]
    except Exception:
        return []
    return [n for n in names if n][:60]


def format_text(fp: Fingerprint) -> str:
    """The human-read report: what was looked for, what was found, where."""
    lines = [
        f"package          : {fp.package} {fp.version} ({fp.kind}/{fp.platform})",
        f"unity            : {fp.unity_version or '(not found)'}",
        f"metadata read    : {fp.metadata_source or '(none)'}",
        "",
        f"build paths      : {len(fp.build_paths)} shown of {fp.build_paths_total} found in the binary",
    ]
    lines += [f"  {p}" for p in fp.build_paths]
    lines.append("")
    lines.append("markers seen     : (table / marker: binary, dex, members)")
    for table in MARKER_TABLES:
        cells = ", ".join(
            f"{m.marker}={m.hits.get(WHERE_BINARY, 0)}/{m.hits.get(WHERE_DEX, 0)}/{m.hits.get(WHERE_MEMBERS, 0)}"
            for m in fp.markers(table)
        )
        lines.append(f"  {table:10s} {cells}")
    lines.append("")
    lines.append(
        f"assemblies       : {len(fp.declared_assemblies)} declared, "
        f"{len(fp.assemblies_in_metadata)} named in metadata, {len(fp.assemblies_absent)} absent"
    )
    lines += [f"  absent: {n}" for n in fp.assemblies_absent[:SHOW_ABSENT]]
    if len(fp.assemblies_absent) > SHOW_ABSENT:
        lines.append(f"  ... {len(fp.assemblies_absent) - SHOW_ABSENT} more")
    if fp.absent_note():
        lines.append(f"  note: {fp.absent_note()}")
    lines.append("")
    lines.append(f"bytes literals   : {len(fp.bytes_literals)}")
    lines += [f"  {b}" for b in fp.bytes_literals]
    lines.append("")
    lines.append("signing certs    : " + (", ".join(
        f"{name.split('/')[-1]}={digest}" for name, digest in fp.signing_certs.items()) or "(none)"))
    lines.append("")
    lines.append(f"native libs      : {len(fp.native_libs)}; exports read from {len(fp.native_exports)}")
    for lib, syms in fp.native_exports.items():
        lines.append(f"  {lib}: {', '.join(syms[:SHOW_EXPORTS])}" + (" ..." if len(syms) > SHOW_EXPORTS else ""))
    lines.append("")
    lines.append(f"dex packages     : {len(fp.dex_packages)} shown of {fp.dex_packages_total}")
    lines += [f"  {p}" for p in fp.dex_packages[:SHOW_DEX]]
    if len(fp.dex_packages) > SHOW_DEX:
        lines.append(f"  ... {len(fp.dex_packages) - SHOW_DEX} more")
    lines.append("")
    lines.append(f"domains          : {len(fp.domains)} shown of {fp.domains_total}: {', '.join(fp.domains) or '(none)'}")
    lines.append(f"section names    : {', '.join(fp.section_names) or '(none)'}")
    lines.append(f"asset pipeline   : {', '.join(fp.asset_pipeline) or '(none)'}")
    return "\n".join(lines)
