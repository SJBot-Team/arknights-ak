"""Locate and extract the IL2CPP binary and metadata from a game package.

Handles apk, xapk and ipa through one nested unzipper driven by the layout
table -- the differences between the three are path patterns and nesting depth,
which are data, not control flow.

Based on the extraction methodology from match3-core-sketch/tools/rm_re/.
"""

from __future__ import annotations

import fnmatch
import hashlib
import os
import zipfile
from dataclasses import dataclass

from . import layout as _layout
from .config import binaries_dir
from .image import sniff_format

# Kept for callers that still refer to the canonical Android locations.
ANDROID_LIB_PATH = _layout.ANDROID_BINARY_PATHS[0]
ANDROID_METADATA_PATH = _layout.ANDROID_METADATA_PATHS[0]

METADATA_MAGIC = b"\xAF\x1B\xB1\xFA"


@dataclass(frozen=True)
class BinaryLocation:
    """Describes a located binary or metadata file."""
    path: str
    source: str  # original source description (e.g. "file.apk!path")


def _cache_path(data: bytes, suffix: str) -> str:
    digest = hashlib.sha1(data).hexdigest()[:16]
    return os.path.join(binaries_dir(), f"{digest}-{suffix}")


def _cache(data: bytes, suffix: str) -> str:
    out_path = _cache_path(data, suffix)
    if not os.path.exists(out_path) or os.path.getsize(out_path) != len(data):
        tmp_path = f"{out_path}.{os.getpid()}.tmp"
        with open(tmp_path, "wb") as f:
            f.write(data)
        os.replace(tmp_path, out_path)
    return out_path


def _looks_like_binary(path_or_data) -> bool:
    """True for an ELF or a Mach-O, by magic."""
    if isinstance(path_or_data, bytes):
        return sniff_format(path_or_data[:8]) is not None
    try:
        with open(path_or_data, "rb") as f:
            return sniff_format(f.read(8)) is not None
    except OSError:
        return False


def _looks_like_metadata(path_or_data) -> bool:
    if isinstance(path_or_data, bytes):
        return path_or_data[:4] == METADATA_MAGIC
    try:
        with open(path_or_data, "rb") as f:
            return f.read(4) == METADATA_MAGIC
    except OSError:
        return False


# Candidates that fail the sanity check are renamed out of the `*-global-metadata.dat`
# namespace: the Cpp2IL runner globs for that name, and feeding it an encrypted
# blob crashes Cpp2IL with an error that says nothing about encryption. They are
# kept (not deleted) — the ciphertext is exactly what you need to reverse the
# loader's decryption routine.
QUARANTINE_SUFFIX = ".unrecognized"


def _quarantine(data: bytes, source: str) -> str:
    """Park an unrecognised metadata blob where the Cpp2IL glob will not see it."""
    dest = _cache_path(data, "global-metadata.dat") + QUARANTINE_SUFFIX
    if not os.path.exists(dest) or os.path.getsize(dest) != len(data):
        tmp = f"{dest}.{os.getpid()}.tmp"
        with open(tmp, "wb") as f:
            f.write(data)
        os.replace(tmp, dest)
    return dest


def metadata_candidates(root: str | None = None) -> list[tuple[str, bytes]]:
    """Quarantined metadata candidates: (path, first 4 bytes). Empty if none."""
    base = root or _workspace_root()
    out = []
    cache = os.path.join(base, "_binaries")
    for name in sorted(os.listdir(cache) if os.path.isdir(cache) else []):
        if not name.endswith(QUARANTINE_SUFFIX):
            continue
        full = os.path.join(cache, name)
        try:
            with open(full, "rb") as f:
                out.append((full, f.read(4)))
        except OSError:
            continue
    return out


def _workspace_root() -> str:
    """The project root where the game package / extracted data live."""
    from .config import workspace_root
    return workspace_root()


def _packages(root: str | None) -> list[tuple[str, _layout.PackageLayout]]:
    """Packages to search, honouring a pinned platform when one is configured."""
    from .config import selected_platform
    wanted = selected_platform()
    seen: set[str] = set()
    out: list[tuple[str, _layout.PackageLayout]] = []
    for base in [r for r in [root, _workspace_root()] if r]:
        for path, lay in _layout.find_packages(base):
            if path in seen:
                continue
            if wanted and lay.platform != wanted:
                continue
            seen.add(path)
            out.append((path, lay))
    return out


def find_libil2cpp(root: str | None = None) -> BinaryLocation:
    """Find or extract the IL2CPP binary (ELF on Android, Mach-O on iOS).

    Searches direct paths under `root`, then inside any package in the project.
    Inside an ipa the path patterns are ordered so the real UnityFramework wins
    over the launch shell; magic only confirms "this is a Mach-O", it does not
    disambiguate, because both files pass it.
    """
    if root:
        for candidate in [
            os.path.join(root, "lib", "arm64-v8a", "libil2cpp.so"),
            os.path.join(root, "libil2cpp.so"),
            os.path.join(root, "UnityFramework"),
        ]:
            if os.path.exists(candidate) and _looks_like_binary(candidate):
                return BinaryLocation(path=candidate, source=candidate)

    packages = _packages(root)
    for package_path, lay in packages:
        hit = _layout.find_in_package(
            package_path, lay, lay.binary_paths, accept=_looks_like_binary
        )
        if hit:
            source, data = hit
            return BinaryLocation(path=_cache(data, "libil2cpp.so"), source=source)

    if not packages:
        raise FileNotFoundError(
            "No game package (.apk / .xapk / .apks / .ipa) found in the project directory."
        )
    raise FileNotFoundError(
        "No IL2CPP binary found inside "
        + ", ".join(os.path.basename(p) for p, _ in packages)
    )


def _decrypt_hook():
    """The project's metadata decryptor, if one is configured. None otherwise."""
    from .config import load_metadata_decryptor
    return load_metadata_decryptor()


def find_global_metadata(root: str | None = None) -> BinaryLocation:
    """Find, extract, or decrypt global-metadata.dat.

    A packed title ships ciphertext, so the plaintext can only come from outside
    the package -- dumped from a running process, or produced by the project's
    own decryptor. Once it is in _binaries/ it must win, or every later run
    re-extracts the encrypted copy and reports failure with the answer already
    on disk.
    """
    for base in [r for r in [root, _workspace_root()] if r]:
        cache = os.path.join(base, "_binaries")
        if not os.path.isdir(cache):
            continue
        for name in sorted(os.listdir(cache)):
            if not name.endswith("-global-metadata.dat"):
                continue
            full = os.path.join(cache, name)
            if _looks_like_metadata(full):
                return BinaryLocation(path=full, source=full)

    if root:
        for candidate in [
            os.path.join(root, ANDROID_METADATA_PATH),
            os.path.join(root, "global-metadata.dat"),
        ]:
            if os.path.exists(candidate):
                return BinaryLocation(path=candidate, source=candidate)

    rejected: list[tuple[str, bytes]] = []

    def _note_reject(source: str, data: bytes) -> None:
        rejected.append((source, data))

    packages = _packages(root)
    for package_path, lay in packages:
        hit = _layout.find_in_package(
            package_path, lay, lay.metadata_paths,
            accept=_looks_like_metadata, on_reject=_note_reject,
        )
        if hit:
            source, data = hit
            return BinaryLocation(path=_cache(data, "global-metadata.dat"), source=source)

    # Everything that matched a metadata path but was not plaintext: try the
    # project's decryptor, and quarantine whatever is left.
    decrypt = _decrypt_hook()
    for source, data in rejected:
        if decrypt is not None:
            try:
                plain = decrypt(data)
            except Exception as exc:
                raise RuntimeError(
                    f"The project's metadata decryptor raised on {source}: "
                    f"{type(exc).__name__}: {exc}\n"
                    "This is a decryption failure, not a format problem — the file "
                    "was found and handed to your decrypt() unchanged."
                ) from exc
            if _looks_like_metadata(plain):
                return BinaryLocation(
                    path=_cache(plain, "global-metadata.dat"),
                    source=f"{source} (decrypted by the project's decryptor)",
                )
        _quarantine(data, source)

    bad = metadata_candidates(root)
    if bad:
        lines = [f"  {p}  (magic {m.hex()}, expected af1bb1fa)" for p, m in bad]
        hint = (
            "A decryptor is configured but its output still is not plaintext "
            "metadata — the algorithm is not right yet.\n"
            if decrypt is not None else
            "Reverse the loader's metadata decryption (start from il2cpp_init / "
            "the packer's init in the IL2CPP binary), then either drop the "
            "plaintext at _binaries/<hash>-global-metadata.dat or point "
            "[metadata] decryptor in revenant.toml at a module exposing "
            "decrypt(bytes) -> bytes.\n"
        )
        raise FileNotFoundError(
            "global-metadata.dat was found in the package but is not plaintext "
            "IL2CPP metadata — it looks encrypted or packed:\n"
            + "\n".join(lines) + "\n" + hint
        )
    if not packages:
        raise FileNotFoundError(
            "No game package (.apk / .xapk / .apks / .ipa) found in the project directory."
        )
    raise FileNotFoundError(
        "No global-metadata.dat found inside "
        + ", ".join(os.path.basename(p) for p, _ in packages)
    )


def extract_all_apks(package_path: str | None = None) -> list[str]:
    """Extract the inner archives of a nested package into _apks/."""
    if package_path is None:
        from .config import package_path as _package_path
        package_path = _package_path()
    if not package_path:
        return []
    lay = _layout.layout_for(package_path)
    if not lay or not lay.nested_glob:
        return []

    from .config import apks_dir as _apks_dir
    extracted: list[str] = []
    with zipfile.ZipFile(package_path) as outer:
        for name in outer.namelist():
            if not fnmatch.fnmatchcase(name.lower(), lay.nested_glob):
                continue
            data = outer.read(name)
            out_path = os.path.join(_apks_dir(), os.path.basename(name))
            if not os.path.exists(out_path) or os.path.getsize(out_path) != len(data):
                with open(out_path, "wb") as f:
                    f.write(data)
            extracted.append(out_path)
    return extracted


_INTERESTING = ("libil2cpp", "global-metadata", "managed", "metadata", "unityframework")


def list_package_contents(package_path: str, prefix: str = "") -> list[str]:
    """List interesting members of a package, across nesting."""
    lay = _layout.layout_for(package_path)
    if not lay:
        return []
    results: list[str] = []
    for archive_desc, archive in _layout.iter_archives(package_path, lay):
        for name in sorted(archive.namelist()):
            if prefix and not name.startswith(prefix):
                continue
            if any(kw in name.lower() for kw in _INTERESTING):
                info = archive.getinfo(name)
                label = name if archive_desc == os.path.basename(package_path) else f"{archive_desc}!{name}"
                results.append(f"{label:70s} {info.file_size:>10d}")
    return results


# Back-compat alias for the older name (the step is now `revenant prepare --only ls-apk`).
list_apk_contents = list_package_contents
