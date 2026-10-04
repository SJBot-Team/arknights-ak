"""Scene / AssetBundle extraction for Unity IL2CPP games.

Unpacks Unity AssetBundles into a tidy, per-type tree under res/. For each
bundle it produces:
  res/<group>/<bundle>/
    _bundle.json            inventory: scene path(s), object-type counts, sizes
    _hierarchy.txt          GameObject scene tree (roots -> children)
    Texture2D/<name>.png
    Sprite/<name>.png
    AudioClip/<name>.wav
    Mesh/<name>.obj
    MonoBehaviour/<name>.json   typetree dump (scene logic / config data)
    TextAsset/<name>.bytes
    VideoClip/<name>.mp4
    AnimationClip.txt       names only (binary clip export is out of scope)

Bundle layout is auto-detected from the base APK. Two layouts are supported:
  - Classic AssetBundles:  assets/Bundles/Android/<Group>/<bundle>
  - Unity Addressables:    assets/aa/android/<...>/<bundle>   (flat or nested)
so this works for both older AssetBundle games and modern Addressables games
(Gossip Harbor ships Addressables under assets/aa/android/).

Depends on UnityPy (+ texture2ddecoder / astc_encoder_py / Pillow for textures)
for `extract-scenes`; `list-bundles` works without UnityPy.
"""

from __future__ import annotations

import fnmatch
import gzip
import io
import json
import os
import re
import zipfile
import zlib
from collections import Counter
from dataclasses import dataclass, field

from . import layout as _layout
from .config import PACKAGE, apks_dir, workspace_root

# Base APK that carries the bundle tree (not the per-ABI native split).
BASE_APK = f"{PACKAGE}.apk"

# Bundle roots now live in the layout table, per platform -- iOS puts them under
# Data/Raw inside the .app, Android under assets/aa. Kept as a module constant
# for the Android default so existing callers keep working.
BUNDLE_ROOTS = _layout.ANDROID_BUNDLE_ROOTS

# The serialized files Unity bakes into the player itself: `globalgamemanagers`
# on older builds, `data.unity3d` since 2021. The layout has declared both for
# as long as it has existed; nothing read them, so a title that ships its whole
# numeric layer in Resources/ looked empty to the harness (#47).
GGM_PATHS = _layout.ANDROID_GGM

# Where a ggm/data.unity3d export lands, as a group name under res/.
GGM_GROUP = "_ggm"

# UnityPy needs an engine version to parse a serialized file that does not carry
# one, and guesses wrong on newer builds. Both project scripts took it from a
# `UNITY_VER=` environment variable; this is the same exit, under the harness's
# own prefix, with `--unity-version` on the command line above it.
UNITY_VERSION_ENV = "REVENANT_UNITY_VERSION"

# Default scene group for `extract-scenes` when none is given. This is a guess
# for grouped layouts; for Addressables (flat) pass a group from `list-bundles`.
MAIN_STORYLINE_GROUP = "MetaScenes"

# Marker used by list_bundles for files that sit directly under the root
# (no <Group>/ segment), as is common with Addressables.
ROOT_GROUP = "(root)"

_SANITIZE = re.compile(r"[^A-Za-z0-9._-]+")


def safe_name(name: str, fallback: str) -> str:
    """A name safe to write to disk, or `fallback` when nothing survives.

    Public because anything writing into the same export tree has to name its
    directories the same way, or the two trees quietly diverge -- `contrib.cache`
    builds one for a directory of loose bundles.
    """
    name = (name or "").strip()
    name = _SANITIZE.sub("_", name).strip("._") or fallback
    return name[:120]


def _unique(used: set[str], stem: str, ext: str, path_id: int) -> str:
    """Return a filename unique within a folder; disambiguate with path_id.

    The truncated path id is not itself unique -- two objects in one folder can
    share its last seven digits, and on a real bundle four did, so four exports
    overwrote each other while the manifest still counted them. Keep going
    until the name is actually free.
    """
    candidate = f"{stem}{ext}"
    if candidate not in used:
        used.add(candidate)
        return candidate
    short = abs(path_id) % 10_000_000
    candidate = f"{stem}_{short}{ext}"
    serial = 2
    while candidate in used:
        candidate = f"{stem}_{short}_{serial}{ext}"
        serial += 1
    used.add(candidate)
    return candidate


def _json_default(value):
    if isinstance(value, (bytes, bytearray)):
        return f"<{len(value)} bytes>"
    return str(value)


def set_unity_version(version: str | None = None) -> str | None:
    """Pin UnityPy's fallback engine version; returns what was applied, if any.

    A bundle whose serialized files carry no version string is unreadable
    without one, and UnityPy's built-in default is older than the builds these
    titles ship. Explicit argument wins over the environment.
    """
    version = version or os.environ.get(UNITY_VERSION_ENV) or ""
    if not version:
        return None
    import UnityPy
    UnityPy.config.FALLBACK_UNITY_VERSION = version
    return version


# ──────────────────────────────────────────────────────────────────────────


def _detect_bundle_root(zf: zipfile.ZipFile, roots: tuple[str, ...] | None = None) -> str | None:
    """First bundle root present in an archive, resolved to a concrete path.

    Roots come from the layout table and may be globs (an ipa's live under
    `Payload/<AppName>.app/`, and the app name is not known ahead of time), so
    the glob is resolved against a real member and the concrete prefix returned
    -- everything downstream joins paths onto it.
    """
    names = zf.namelist()
    for pattern in roots or BUNDLE_ROOTS:
        depth = len(pattern.split("/"))
        for name in names:
            if fnmatch.fnmatchcase(name, pattern + "/*"):
                return "/".join(name.split("/")[:depth])
    return None


def _holds_prefix(zf: zipfile.ZipFile, prefix: str) -> bool:
    """Whether an archive has any regular member under a pinned prefix."""
    prefix = prefix.rstrip("/")
    return any(name.startswith(prefix + "/") or name == prefix
               for name in zf.namelist())


def find_bundle_source(bundle_root: str | None = None) -> tuple[str, str] | None:
    """Locate the archive carrying a bundle tree: (archive_path, bundle_root).

    Extracted APKs win when present (that is the xapk path, and reading a split
    apk beats re-reading a multi-gigabyte package). An ipa has no inner apks, so
    the project package itself is searched next, using its own bundle roots.

    `bundle_root` pins an in-package prefix instead of detecting one, which is
    how a title whose data sits outside the known roots gets read without
    teaching the layout a one-off path (#47). The archive is then whichever one
    actually holds members under that prefix.
    """
    candidates = [
        os.path.join(apks_dir(), BASE_APK),
        os.path.join(workspace_root(), "_apks", BASE_APK),
    ]
    adir = apks_dir()
    if os.path.isdir(adir):
        candidates.extend(
            os.path.join(adir, name)
            for name in sorted(os.listdir(adir))
            if name.lower().endswith(".apk")
        )
    seen: set[str] = set()
    for full in candidates:
        if full in seen or not os.path.exists(full):
            continue
        seen.add(full)
        try:
            with zipfile.ZipFile(full) as zf:
                if bundle_root:
                    if _holds_prefix(zf, bundle_root):
                        return full, bundle_root
                    continue
                root = _detect_bundle_root(zf, _layout.ANDROID_BUNDLE_ROOTS)
                if root:
                    return full, root
        except zipfile.BadZipFile:
            continue

    for path, lay in _layout.find_packages(workspace_root()):
        try:
            with zipfile.ZipFile(path) as zf:
                if bundle_root:
                    if _holds_prefix(zf, bundle_root):
                        return path, bundle_root
                    continue
                root = _detect_bundle_root(zf, lay.bundle_roots)
                if root:
                    return path, root
        except (zipfile.BadZipFile, OSError):
            continue
    return None


# The command is still `revenant list-bundles`; an ipa is not an apk, but the
# callers only ever wanted "the archive with the bundles in it".
find_base_apk = find_bundle_source


def _looks_like_bundle(name: str) -> bool:
    """Heuristic: a regular file that is an AssetBundle (not a catalog/link)."""
    if name.endswith("/"):
        return False
    base = os.path.basename(name).lower()
    if base in ("catalog.json", "settings.json", "addressableslink"):
        return False
    if base.endswith((".json", ".hash")):
        return False
    return True


def list_bundles(apk_path: str, group: str | None = None,
                 bundle_root: str | None = None) -> list[tuple[str, str, int]]:
    """Return (group, bundle_name, size) for every AssetBundle in the APK.

    Works for both grouped (<root>/<Group>/<bundle>) and flat (<root>/<bundle>,
    Addressables) layouts. Flat files are reported under group == ROOT_GROUP.
    """
    out: list[tuple[str, str, int]] = []
    with zipfile.ZipFile(apk_path) as zf:
        root = bundle_root or _detect_bundle_root(zf)
        if not root:
            return out
        prefix = root + "/"
        for info in zf.infolist():
            name = info.filename
            if not name.startswith(prefix) or not _looks_like_bundle(name):
                continue
            rel = name[len(prefix):]
            parts = rel.split("/")
            if len(parts) >= 2:
                g, b = parts[0], "/".join(parts[1:])
            else:
                g, b = ROOT_GROUP, parts[0]
            if group and g != group:
                continue
            out.append((g, b, info.file_size))
    return sorted(out)


@dataclass
class Census:
    """What is inside a set of bundles, by object type. Nothing is unpacked."""

    type_counts: Counter = field(default_factory=Counter)
    per_member: dict = field(default_factory=dict)    # member -> {type: count}
    errors: list = field(default_factory=list)        # (member, reason)
    parsed: int = 0


def type_census(members, load=None, limit: int | None = None) -> Census:
    """Enumerate object types across bundles without exporting anything.

    `members` is an iterable of `(name, data)` -- what walking a zip hands you.
    `load` is the bundle loader (UnityPy.load by default), injected so the walk
    itself can be tested on synthetic input.

    This is the missing middle rung: `list-bundles` gives names and sizes,
    `extract-scenes` gives type counts but only after unpacking gigabytes. Two
    titles carried the same `ab_probe.py` to answer "is there anything in here
    worth unpacking" first (#47).
    """
    if load is None:
        import UnityPy
        load = UnityPy.load

    census = Census()
    for name, data in members:
        if limit is not None and census.parsed >= limit:
            break
        if data.find(UNITYFS) < 0:
            census.errors.append((name, "no UnityFS signature"))
            continue
        try:
            env = load(io.BytesIO(bundle_payload(data)))
            local: Counter = Counter()
            for obj in env.objects:
                local[obj.type.name] += 1
        except Exception as exc:
            census.errors.append((name, f"{type(exc).__name__}: {exc}"))
            continue
        census.type_counts.update(local)
        census.per_member[name] = dict(local)
        census.parsed += 1
    return census


def census_package(apk_path: str, bundle_root: str, group: str | None = None,
                   limit: int | None = None, load=None) -> Census:
    """`type_census` over the bundles `list_bundles` would list.

    Group selection goes through `list_bundles` rather than a path prefix, so
    the census answers the group names a reader has just been shown -- a flat
    Addressables tree is `(root)`, which is not a directory -- and so `Env`
    cannot drag in `Env2`.
    """
    entries = list_bundles(apk_path, group, bundle_root)
    with zipfile.ZipFile(apk_path) as zf:
        names = [_member_path(bundle_root, g, b) for g, b, _ in entries]
        return type_census(((n, zf.read(n)) for n in names), load=load, limit=limit)


# ──────────────────────────────────────────────────────────────────────────


@dataclass
class BundleReport:
    group: str
    name: str
    size: int
    out_dir: str
    scene_paths: list[str] = field(default_factory=list)
    type_counts: Counter = field(default_factory=Counter)
    exported: Counter = field(default_factory=Counter)
    errors: list[str] = field(default_factory=list)
    # Whether the blob parsed at all. Separate from `exported` being non-empty,
    # because a bundle can load and export nothing countable -- a bundle holding
    # only AnimationClips writes `AnimationClip.txt` and increments nothing --
    # and a caller partitioning on `exported` calls that "not a bundle". Our own
    # gap reported as the file's content, which is `lint`'s `no-index` rule.
    loaded: bool = False
    # Forms written *beside* an export rather than instead of it: the inflated
    # copy of a gzipped TextAsset. Not in `exported`, whose keys are Unity type
    # names and go into the manifest as such -- `TextAsset.gunzip` there would
    # be a type that does not exist.
    unpacked: Counter = field(default_factory=Counter)


def _member_path(bundle_root: str, group: str, name: str) -> str:
    """Reconstruct the in-APK member path for a (group, name) pair."""
    if group == ROOT_GROUP:
        return f"{bundle_root}/{name}"
    return f"{bundle_root}/{group}/{name}"


def _build_hierarchy(env) -> str:
    """Render the scene's GameObject tree from Transform parent/child links."""
    transforms = {}
    go_name = {}
    for obj in env.objects:
        if obj.type.name in ("Transform", "RectTransform"):
            try:
                t = obj.read()
                transforms[obj.path_id] = t
            except Exception:
                continue
        elif obj.type.name == "GameObject":
            try:
                go_name[obj.path_id] = obj.read().m_Name or "(unnamed)"
            except Exception:
                go_name[obj.path_id] = "(unnamed)"

    def name_of(transform) -> str:
        try:
            return go_name.get(transform.m_GameObject.path_id, "(unknown)")
        except Exception:
            return "(unknown)"

    children_of: dict[int, list[int]] = {}
    has_parent: set[int] = set()
    for pid, t in transforms.items():
        kids = []
        try:
            for child_ptr in getattr(t, "m_Children", []) or []:
                cpid = child_ptr.path_id
                kids.append(cpid)
                has_parent.add(cpid)
        except Exception:
            pass
        children_of[pid] = kids

    roots = [pid for pid in transforms if pid not in has_parent]
    lines: list[str] = []

    def walk(pid: int, depth: int) -> None:
        t = transforms.get(pid)
        if t is None:
            return
        lines.append("  " * depth + name_of(t))
        if depth > 200:
            return
        for cpid in children_of.get(pid, []):
            walk(cpid, depth + 1)

    for root in sorted(roots, key=lambda p: name_of(transforms[p]).lower()):
        walk(root, 0)
    return "\n".join(lines)


UNITYFS = b"UnityFS"

# How far in a wrapper header may push the signature. The observed prefix is
# 32 bytes; the cap is what keeps the search from turning a stray occurrence
# deep inside a file into a truncation -- `globalgamemanagers` is not a UnityFS
# container at all, and beheading it at some byte in its middle would look like
# a parse failure rather than a mistake here (#47).
WRAPPER_WINDOW = 1024


def bundle_payload(data: bytes) -> bytes:
    """The UnityFS stream inside a bundle member, skipping any wrapper header.

    Two real projects (Hollywood Merge, Travel Town) ship bundles with a
    prefix in front of the `UnityFS` signature; UnityPy wants the signature
    at offset 0. Found and skipped here rather than in a project script (#32).
    A signature past the header window is data, not a wrapper, and is left be.
    """
    at = data.find(UNITYFS, 0, WRAPPER_WINDOW)
    return data[at:] if at > 0 else data


def _mono_script_names(env) -> dict:
    """path_id -> `Namespace.Class` for every MonoScript in the bundle."""
    out: dict = {}
    for obj in env.objects:
        if obj.type.name != "MonoScript":
            continue
        try:
            r = obj.read()
            out[obj.path_id] = f"{r.m_Namespace}.{r.m_ClassName}".strip(".")
        except Exception:
            continue
    return out


def extract_bundle(apk_path: str, group: str, name: str, res_root: str,
                   bundle_root: str | None = None,
                   dump_hierarchy: bool = True, verbose: bool = False,
                   by_script: bool = False) -> BundleReport:
    """Extract one bundle into res/<group>/<name>/.

    `by_script` files each MonoBehaviour under its resolved MonoScript class
    (`MonoBehaviour/<Namespace.Class>/<name>.json`) and records a per-class
    histogram in `_bundle.json` -- the shape typed ScriptableObject data has
    when you want to read all of one kind at once.
    """
    import UnityPy

    if bundle_root is None:
        with zipfile.ZipFile(apk_path) as zf:
            bundle_root = _detect_bundle_root(zf) or BUNDLE_ROOTS[0]
    member = _member_path(bundle_root, group, name)
    with zipfile.ZipFile(apk_path) as zf:
        data = zf.read(member)

    safe_group = safe_name(group, "group")
    out_dir = os.path.join(res_root, safe_group, safe_name(name, "bundle"))
    os.makedirs(out_dir, exist_ok=True)
    report = BundleReport(group=group, name=name, size=len(data), out_dir=out_dir)

    env = UnityPy.load(io.BytesIO(bundle_payload(data)))
    return export_env(env, report, dump_hierarchy=dump_hierarchy, by_script=by_script)


def export_env(env, report: BundleReport, *, dump_hierarchy: bool = True,
               by_script: bool = False) -> BundleReport:
    """Export every object in a loaded environment into `report.out_dir`.

    Split out of `extract_bundle` so the same per-type tree can be written for
    anything UnityPy can load -- a bundle out of the package, or the serialized
    files Unity bakes into the player (`data.unity3d`), which the layout has
    always declared and nothing read (#47).
    """
    out_dir = report.out_dir
    os.makedirs(out_dir, exist_ok=True)
    used_names: dict[str, set[str]] = {}
    anim_clip_names: list[str] = []
    scripts = _mono_script_names(env) if by_script else {}
    script_histogram: Counter = Counter()

    def slot(kind: str) -> set[str]:
        return used_names.setdefault(kind, set())

    for obj in env.objects:
        tname = obj.type.name
        report.type_counts[tname] += 1
        try:
            if tname == "AssetBundle":
                d = obj.read()
                for entry in d.m_Container:
                    path = entry[0] if isinstance(entry, (tuple, list)) else entry
                    report.scene_paths.append(path)

            elif tname in ("Texture2D", "Sprite"):
                d = obj.read()
                img = d.image
                if img is None:
                    continue
                stem = safe_name(getattr(d, "m_Name", ""), tname)
                folder = os.path.join(out_dir, tname)
                os.makedirs(folder, exist_ok=True)
                fn = _unique(slot(tname), stem, ".png", obj.path_id)
                img.save(os.path.join(folder, fn))
                report.exported[tname] += 1

            elif tname == "AudioClip":
                d = obj.read()
                samples = getattr(d, "samples", {}) or {}
                folder = os.path.join(out_dir, "AudioClip")
                os.makedirs(folder, exist_ok=True)
                for sname, sbytes in samples.items():
                    stem = safe_name(os.path.splitext(sname)[0]
                                 or getattr(d, "m_Name", ""), "AudioClip")
                    fn = _unique(slot("AudioClip"), stem, ".wav", obj.path_id)
                    with open(os.path.join(folder, fn), "wb") as f:
                        f.write(sbytes)
                    report.exported["AudioClip"] += 1

            elif tname == "Mesh":
                d = obj.read()
                obj_text = d.export()
                if not obj_text:
                    continue
                stem = safe_name(getattr(d, "m_Name", ""), "Mesh")
                folder = os.path.join(out_dir, "Mesh")
                os.makedirs(folder, exist_ok=True)
                fn = _unique(slot("Mesh"), stem, ".obj", obj.path_id)
                with open(os.path.join(folder, fn), "w") as f:
                    f.write(obj_text)
                report.exported["Mesh"] += 1

            elif tname == "TextAsset":
                d = obj.read()
                script = getattr(d, "m_Script", b"")
                raw = script.encode("utf-8", "surrogateescape") if isinstance(script, str) else bytes(script)
                stem = safe_name(getattr(d, "m_Name", ""), "TextAsset")
                folder = os.path.join(out_dir, "TextAsset")
                os.makedirs(folder, exist_ok=True)
                fn = _unique(slot("TextAsset"), stem, ".bytes", obj.path_id)
                with open(os.path.join(folder, fn), "wb") as f:
                    f.write(raw)
                report.exported["TextAsset"] += 1
                _write_gunzipped(folder, fn, raw, report)

            elif tname == "MonoBehaviour":
                tree = obj.read_typetree()
                stem = safe_name(tree.get("m_Name") if isinstance(tree, dict) else "", "")
                if not stem:
                    stem = safe_name(_mono_script_name(obj, tree), "MonoBehaviour")
                folder = os.path.join(out_dir, "MonoBehaviour")
                if by_script:
                    ptr = (tree.get("m_Script") or {}) if isinstance(tree, dict) else {}
                    cls = scripts.get(ptr.get("m_PathID"), f"unknown_{ptr.get('m_PathID')}")
                    script_histogram[cls] += 1
                    folder = os.path.join(folder, safe_name(cls, "unknown"))
                os.makedirs(folder, exist_ok=True)
                fn = _unique(slot(folder), stem, ".json", obj.path_id)
                with open(os.path.join(folder, fn), "w") as f:
                    json.dump(tree, f, indent=1, ensure_ascii=False, default=_json_default)
                report.exported["MonoBehaviour"] += 1

            elif tname == "VideoClip":
                d = obj.read()
                vbytes = _read_video_bytes(env, d)
                if not vbytes:
                    continue
                stem = safe_name(getattr(d, "m_Name", ""), "VideoClip")
                ext = os.path.splitext(getattr(d, "m_OriginalPath", "") or "")[1] or ".mp4"
                folder = os.path.join(out_dir, "VideoClip")
                os.makedirs(folder, exist_ok=True)
                fn = _unique(slot("VideoClip"), stem, ext, obj.path_id)
                with open(os.path.join(folder, fn), "wb") as f:
                    f.write(vbytes)
                report.exported["VideoClip"] += 1

            elif tname == "AnimationClip":
                d = obj.read()
                anim_clip_names.append(getattr(d, "m_Name", "") or "(unnamed)")

        except Exception as exc:  # keep going; record what failed
            report.errors.append(f"{tname}#{obj.path_id}: {exc}")

    if anim_clip_names:
        with open(os.path.join(out_dir, "AnimationClip.txt"), "w") as f:
            f.write("\n".join(sorted(anim_clip_names)))

    if dump_hierarchy:
        try:
            tree_text = _build_hierarchy(env)
            if tree_text:
                with open(os.path.join(out_dir, "_hierarchy.txt"), "w") as f:
                    f.write(tree_text)
        except Exception as exc:
            report.errors.append(f"hierarchy: {exc}")

    manifest = {
        "group": report.group,
        "bundle": report.name,
        "compressed_size": report.size,
        "scene_paths": report.scene_paths,
        "object_counts": dict(report.type_counts.most_common()),
        "exported_counts": dict(report.exported),
        "unpacked_counts": dict(report.unpacked),
        "errors": report.errors[:50],
    }
    if by_script:
        manifest["script_histogram"] = dict(script_histogram.most_common())
    with open(os.path.join(out_dir, "_bundle.json"), "w") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)

    return report


# A TextAsset that is gzip, and the suffix the unpacked form takes.
#
# Seven of one title's 26 CMS libraries are gzipped JSON rather than
# FlatBuffers, and `extract-scenes` wrote them out as an opaque blob with
# nothing saying so -- a reader had to run `file` over the tree to find out.
# The magic decides, not the extension: the names come off a CDN and mean
# nothing. The raw bytes are written unchanged either way, because notes cite
# their size and md5; the unpacked form lands beside them under the same name
# plus what was done to it.
GZIP_MAGIC = b"\x1f\x8b"
GUNZIP_SUFFIX = ".gunzip"


def _write_gunzipped(folder: str, fn: str, raw: bytes, report: BundleReport) -> None:
    """Write the inflated form beside a gzipped TextAsset. Never the only copy.

    A blob whose magic says gzip and whose body will not inflate is reported
    rather than dropped: it is the one signal that the file is not what its
    header claims, and a silent skip makes a truncated download read like a
    plain text asset.
    """
    if not raw.startswith(GZIP_MAGIC):
        return
    try:
        plain = gzip.decompress(raw)
    except (OSError, EOFError, zlib.error) as exc:
        report.errors.append(f"gzip {fn}: {type(exc).__name__}: {exc}")
        return
    with open(os.path.join(folder, fn + GUNZIP_SUFFIX), "wb") as f:
        f.write(plain)
    report.unpacked["TextAsset"] += 1


def default_loader(load=None, unity_version: str | None = None):
    """The injected loader, or UnityPy with the version fallback resolved.

    Every caller that exports a blob needs the same three lines, and getting the
    version pin wrong is silent -- a bundle whose files carry no version string
    simply fails to parse.
    """
    if load is not None:
        return load
    set_unity_version(unity_version)
    import UnityPy
    return UnityPy.load


def export_blob(data: bytes, report: BundleReport, load, *, label: str = "",
                dump_hierarchy: bool = False, by_script: bool = False) -> BundleReport:
    """Load one blob and export it, recording a load failure on the report.

    The ring around `export_env`: two callers export a blob that did not come out
    of a package -- the serialized files baked into the player, and a directory of
    bundles the client downloaded -- and writing that ring twice is how the two
    export trees drift apart (#50).
    """
    try:
        env = load(io.BytesIO(bundle_payload(data)))
    except Exception as exc:
        report.errors.append(f"load {label or report.name}: {type(exc).__name__}: {exc}")
        return report
    report.loaded = True
    return export_env(env, report, dump_hierarchy=dump_hierarchy, by_script=by_script)


def iter_ggm_sources(root: str | None = None):
    """Yield `(label, data)` for each serialized player file the layout declares.

    `globalgamemanagers` and `data.unity3d` hold whatever the build baked into
    `Resources/` -- on one real title that is the entire numeric layer, 57.6 MB
    of TextAssets, which the harness could not see at all because
    `find_bundle_source` only ever looked at bundle roots (#47).

    Extracted apks are searched first (same order `find_bundle_source` uses),
    then the packages themselves through the layout. The first source to offer
    a given file name wins, so a base apk and the package it came out of do not
    both yield it.
    """
    root = root or workspace_root()
    seen: set[str] = set()

    def scan(desc: str, archive: zipfile.ZipFile, patterns: tuple[str, ...]):
        """Every match in one archive, each file name yielded only once."""
        for pattern in patterns:
            for member in sorted(n for n in archive.namelist()
                                 if fnmatch.fnmatchcase(n, pattern)):
                key = os.path.basename(member)
                if key in seen:
                    continue
                seen.add(key)
                yield f"{desc}!{member}", archive.read(member)

    adir = apks_dir()
    apks = ([os.path.join(adir, n) for n in sorted(os.listdir(adir))
             if n.lower().endswith(".apk")] if os.path.isdir(adir) else [])
    for apk in apks:
        try:
            with zipfile.ZipFile(apk) as zf:
                yield from scan(os.path.basename(apk), zf, GGM_PATHS)
        except (zipfile.BadZipFile, OSError):
            continue

    for path, lay in _layout.find_packages(root):
        try:
            for desc, archive in _layout.iter_archives(path, lay):
                yield from scan(desc, archive, lay.ggm_paths)
        except (zipfile.BadZipFile, OSError):
            continue


def extract_ggm(res_root: str | None = None, *, sources=None, load=None,
                by_script: bool = False, dump_hierarchy: bool = False,
                unity_version: str | None = None) -> list[BundleReport]:
    """Export the baked-in serialized files into res/_ggm/<file>/.

    Same per-type tree as a bundle export, so a TextAsset baked into the player
    lands beside one that came out of a bundle. Hierarchy dumping is off by
    default here: `data.unity3d` carries the built-in scenes, and their trees
    are large and not what anyone opens this for.
    """
    load = default_loader(load, unity_version)
    if res_root is None:
        res_root = os.path.join(workspace_root(), "res")

    reports: list[BundleReport] = []
    for label, data in (sources if sources is not None else iter_ggm_sources()):
        name = os.path.basename(label.split("!")[-1])
        out_dir = os.path.join(res_root, GGM_GROUP, safe_name(name, "ggm"))
        report = BundleReport(group=GGM_GROUP, name=name, size=len(data), out_dir=out_dir)
        before = len(report.errors)
        export_blob(data, report, load, label=label,
                    dump_hierarchy=dump_hierarchy, by_script=by_script)
        if len(report.errors) > before and not report.exported:
            os.makedirs(out_dir, exist_ok=True)
        reports.append(report)
    return reports


def _read_video_bytes(env, video_clip) -> bytes | None:
    """Pull the embedded movie out of a VideoClip's streamed .resource CAB."""
    ext = getattr(video_clip, "m_ExternalResources", None)
    if ext is None:
        return None
    source = getattr(ext, "m_Source", "") or ""
    offset = int(getattr(ext, "m_Offset", 0) or 0)
    size = int(getattr(ext, "m_Size", 0) or 0)
    if not source or size <= 0:
        return None
    key = os.path.basename(source).lower()
    reader = env.cabs.get(key)
    if reader is None:
        return None
    reader.Position = offset
    return reader.read_bytes(size)


def _mono_script_name(obj, tree) -> str:
    """Best-effort MonoBehaviour script class name for filename use."""
    try:
        script_ptr = obj.read().m_Script
        script = script_ptr.read()
        return getattr(script, "m_ClassName", "") or ""
    except Exception:
        return ""


def extract_group(group: str | None = MAIN_STORYLINE_GROUP, res_root: str | None = None,
                  bundles: list[str] | None = None, dump_hierarchy: bool = True,
                  verbose: bool = False, by_script: bool = False,
                  bundle_root: str | None = None,
                  unity_version: str | None = None) -> list[BundleReport]:
    """Extract every bundle in a group; `group=None` means every group.

    Extracting the whole tree in one run is what `extract_ab.py` did with a
    bare in-package prefix, and what a title whose data is spread over a dozen
    groups needs (#47).
    """
    set_unity_version(unity_version)
    located = find_base_apk(bundle_root)
    if not located:
        raise FileNotFoundError(
            "Base APK with a known bundle root not found in _apks/. "
            "Run `revenant prepare --only extract-apks` first."
        )
    apk, bundle_root = located
    if res_root is None:
        res_root = os.path.join(workspace_root(), "res")

    available = list_bundles(apk, group, bundle_root)
    if not available:
        where = "any group" if group is None else f"group {group!r}"
        raise ValueError(f"No bundles found for {where} in {os.path.basename(apk)}")

    wanted = set(bundles) if bundles else None
    reports: list[BundleReport] = []
    for g, name, _size in available:
        if wanted and name not in wanted:
            continue
        if verbose:
            print(f"  extracting {g}/{name} ...")
        reports.append(
            extract_bundle(apk, g, name, res_root, bundle_root=bundle_root,
                           dump_hierarchy=dump_hierarchy, verbose=verbose,
                           by_script=by_script)
        )
    return reports
