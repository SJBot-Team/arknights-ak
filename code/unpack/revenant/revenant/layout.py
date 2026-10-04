"""Where things live inside a game package -- as data, not as code paths.

apk, xapk and ipa differ in exactly three ways: which path patterns hold the
binary/metadata/bundles, how deep the nesting goes, and where the app identity
is written. None of that needs a different code path, so there is one nested
unzipper and one table rather than three extractors.

The table also owns identity (package name and version), because the package
locator has always fed two consumers -- artifact extraction and identity -- and
splitting them would mean two places to teach about a new package format.
"""

from __future__ import annotations

import fnmatch
import io
import json
import os
import plistlib
import zipfile
from dataclasses import dataclass, field
from typing import Callable, Iterator

PLATFORM_ANDROID = "android"
PLATFORM_IOS = "ios"


@dataclass(frozen=True)
class PackageLayout:
    kind: str
    platform: str
    suffixes: tuple[str, ...]
    # Ordered, highest-priority first. Globs, matched against archive members.
    binary_paths: tuple[str, ...]
    metadata_paths: tuple[str, ...]
    bundle_roots: tuple[str, ...]
    # No `lua_roots`. It was declared here and read by nothing, the fourth time
    # a path this table holds had no consumer (#41, #45, #47). Unlike
    # `bundle_roots` -- where a root has to be picked because everything
    # downstream joins paths onto it -- and `ggm_paths` -- exact files -- Lua
    # bundles are found by *shape* across the whole archive
    # (`lua.is_lua_bundle_entry`), which needs no root. The field had no
    # consumer because it had no job, so it is gone rather than wired up:
    # narrowing the search to a root list would lose scripts that sit outside
    # it, which is a regression bought with tidiness.
    ggm_paths: tuple[str, ...]
    # Archives nested one level down (xapk is a zip of apks). None if flat.
    nested_glob: str | None = None
    # Inner archives whose name contains these are opened first.
    nested_priority: tuple[str, ...] = ()
    # Where package/version live, and how to read them.
    identity_paths: tuple[str, ...] = ()
    identity_kind: str = ""          # "xapk-manifest" | "plist" | ""
    extra: dict = field(default_factory=dict)


ANDROID_BINARY_PATHS = (
    "lib/arm64-v8a/libil2cpp.so",
    "lib/armeabi-v7a/libil2cpp.so",
    "lib/x86_64/libil2cpp.so",
)
ANDROID_METADATA_PATHS = (
    "assets/bin/Data/Managed/Metadata/global-metadata.dat",
    "bin/Data/Managed/Metadata/global-metadata.dat",
    "global-metadata.dat",
)
ANDROID_BUNDLE_ROOTS = (
    "assets/aa/android",
    "assets/aa/Android",
    "assets/Bundles/Android",
)
ANDROID_GGM = (
    "assets/bin/Data/globalgamemanagers",
    "assets/bin/Data/data.unity3d",
)

APK = PackageLayout(
    kind="apk",
    platform=PLATFORM_ANDROID,
    suffixes=(".apk",),
    binary_paths=ANDROID_BINARY_PATHS,
    metadata_paths=ANDROID_METADATA_PATHS,
    bundle_roots=ANDROID_BUNDLE_ROOTS,
    ggm_paths=ANDROID_GGM,
)

# `.apks` as the mirrors serve it is the same shape as `.xapk`: a base apk
# beside `config.*.apk` splits, with a `manifest.json` carrying the package
# name. Observed on one such file, so the claim is about what mirrors hand out,
# not about the format in general -- bundletool's own output carries `toc.pb`
# and `splits/*.apk` with no manifest, which this layout still reads (the
# nested glob finds the splits and identity falls back to the base apk).
# One layout serves both; the kind stays "xapk" because that is what every path
# and probe below is named for, and the suffix is not a fact anything reads.
XAPK = PackageLayout(
    kind="xapk",
    platform=PLATFORM_ANDROID,
    suffixes=(".xapk", ".apks"),
    binary_paths=ANDROID_BINARY_PATHS,
    metadata_paths=ANDROID_METADATA_PATHS,
    bundle_roots=ANDROID_BUNDLE_ROOTS,
    ggm_paths=ANDROID_GGM,
    nested_glob="*.apk",
    nested_priority=("arm64", "base"),
    identity_paths=("manifest.json",),
    identity_kind="xapk-manifest",
)

# The framework pattern comes first on purpose: an ipa's top-level binary is the
# launch shell, and both files are Mach-O, so magic cannot separate them. Path
# is the only thing that can, and `Frameworks/*.framework/*` is a fixed Unity
# output layout rather than a guess. Picking "the largest Mach-O" would work
# today and break on the first package that ships a fat shell -- size is a proxy
# variable, and this map has already had to walk back two of those.
IPA = PackageLayout(
    kind="ipa",
    platform=PLATFORM_IOS,
    suffixes=(".ipa",),
    binary_paths=(
        "Payload/*.app/Frameworks/UnityFramework.framework/UnityFramework",
        "Payload/*.app/Frameworks/*.framework/*",
        "Payload/*.app/*",
    ),
    metadata_paths=(
        "Payload/*.app/Data/Managed/Metadata/global-metadata.dat",
        "Payload/*.app/Data/il2cpp_data/Metadata/global-metadata.dat",
        "Payload/*.app/*/Data/Managed/Metadata/global-metadata.dat",
    ),
    bundle_roots=(
        "Payload/*.app/Data/Raw/aa/iOS",
        "Payload/*.app/Data/Raw/aa/ios",
        "Payload/*.app/Data/Raw/Bundles/iOS",
        "Payload/*.app/Data/Raw",
    ),
    ggm_paths=(
        "Payload/*.app/Data/globalgamemanagers",
        "Payload/*.app/Data/data.unity3d",
    ),
    identity_paths=("Payload/*.app/Info.plist",),
    identity_kind="plist",
)

LAYOUTS: tuple[PackageLayout, ...] = (XAPK, APK, IPA)

# Preference when a project holds several packages and no platform is pinned.
# Android first keeps existing projects behaving exactly as before.
_PREFERENCE = ("xapk", "apk", "ipa")


def layout_for(path: str) -> PackageLayout | None:
    """The layout for a package file, by extension. None if not a package."""
    lower = path.lower()
    for layout in LAYOUTS:
        if any(lower.endswith(suffix) for suffix in layout.suffixes):
            return layout
    return None


def find_packages(root: str) -> list[tuple[str, PackageLayout]]:
    """Every game package sitting in a directory, in preference order."""
    try:
        names = sorted(os.listdir(root))
    except OSError:
        return []
    found: list[tuple[str, PackageLayout]] = []
    for name in names:
        layout = layout_for(name)
        if layout:
            found.append((os.path.join(root, name), layout))
    found.sort(key=lambda pair: _PREFERENCE.index(pair[1].kind))
    return found


def _matches(member: str, patterns: tuple[str, ...]) -> int | None:
    """Index of the first pattern a member matches, or None."""
    for index, pattern in enumerate(patterns):
        if fnmatch.fnmatchcase(member, pattern):
            return index
    return None


def iter_archives(package_path: str, layout: PackageLayout) -> Iterator[tuple[str, zipfile.ZipFile]]:
    """Yield (description, open archive) for the package and any nested ones.

    The outer archive always comes first -- an xapk keeps its manifest there --
    then any inner archives, priority names first so the arm64 split is searched
    before the leftovers.

    Lazy on purpose: the outer zip is opened from the path rather than slurped,
    and inner archives are only materialised if the caller keeps iterating. A
    package is routinely a gigabyte, and identity is read at import time.
    """
    base = os.path.basename(package_path)
    with zipfile.ZipFile(package_path) as outer:
        yield base, outer
        if not layout.nested_glob:
            return
        inner_names = [
            n for n in sorted(outer.namelist())
            if fnmatch.fnmatchcase(n.lower(), layout.nested_glob)
        ]

        def rank(name: str) -> int:
            lowered = name.lower()
            for index, token in enumerate(layout.nested_priority):
                if token in lowered:
                    return index
            return len(layout.nested_priority)

        for inner in sorted(inner_names, key=rank):
            with zipfile.ZipFile(io.BytesIO(outer.read(inner))) as nested:
                yield f"{base}!{inner}", nested


def find_in_package(
    package_path: str,
    layout: PackageLayout,
    patterns: tuple[str, ...],
    accept: Callable[[bytes], bool] | None = None,
    on_reject: Callable[[str, bytes], None] | None = None,
) -> tuple[str, bytes] | None:
    """First member matching `patterns` (in pattern order) that `accept` allows.

    Pattern order is priority order, which is how an ipa's real framework wins
    over its launch shell. `on_reject` sees candidates that matched a path but
    failed `accept` -- that is how encrypted metadata gets quarantined instead
    of silently ignored.
    """
    best: tuple[int, str, bytes] | None = None
    for archive_desc, archive in iter_archives(package_path, layout):
        for member in archive.namelist():
            index = _matches(member, patterns)
            if index is None:
                continue
            data = archive.read(member)
            source = f"{archive_desc}!{member}"
            if accept is not None and not accept(data):
                if on_reject is not None:
                    on_reject(source, data)
                continue
            if best is None or index < best[0]:
                best = (index, source, data)
            if index == 0:
                return best[1], best[2]
    if best is None:
        return None
    return best[1], best[2]


def list_members(package_path: str, layout: PackageLayout, patterns: tuple[str, ...]) -> list[str]:
    """Every member matching any of `patterns`, across nesting."""
    out: list[str] = []
    for archive_desc, archive in iter_archives(package_path, layout):
        for member in sorted(archive.namelist()):
            if _matches(member, patterns) is not None:
                out.append(f"{archive_desc}!{member}")
    return out


def read_identity(package_path: str, layout: PackageLayout) -> dict:
    """`{package, version}` read from the package, or {} when unavailable.

    A bare apk has neither an xapk manifest nor an Info.plist -- its identity
    lives in binary AndroidManifest.xml, which is not worth a parser here. Such
    projects keep falling back to the version dirs on disk, as before.
    """
    if not layout.identity_paths or not layout.identity_kind:
        return {}
    hit = find_in_package(package_path, layout, layout.identity_paths)
    if not hit:
        return {}
    _source, data = hit
    try:
        if layout.identity_kind == "xapk-manifest":
            parsed = json.loads(data)
            return {
                "package": parsed.get("package_name") or "",
                "version": parsed.get("version_name") or "",
            }
        if layout.identity_kind == "plist":
            parsed = plistlib.loads(data)
            return {
                "package": parsed.get("CFBundleIdentifier") or "",
                "version": (
                    parsed.get("CFBundleShortVersionString")
                    or parsed.get("CFBundleVersion")
                    or ""
                ),
            }
    except Exception:
        return {}
    return {}
