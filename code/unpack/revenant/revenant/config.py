"""Configuration and path resolution for a Unity/IL2CPP RE workspace.

Game-agnostic: the app identity (package, version, name, Unity version) is
auto-detected from the workspace XAPK's manifest.json / globalgamemanagers,
with generic fallbacks -- so the same toolkit and the agent harness work for
any IL2CPP game dropped into the project, with no hardcoded apk-specific values.
"""

from __future__ import annotations

import io
import json
import os
import re
import zipfile
from typing import Callable, cast

VERSION_FILE = "version.txt"
PROJECT_MARKER = "revenant.toml"   # written by `revenant init`; marks a project root

# Generic fallbacks, used only when nothing can be auto-detected.
_FALLBACK_PACKAGE = "com.unknown.il2cppgame"
_FALLBACK_VERSION = "0.0.0"
_FALLBACK_UNITY = "2022.3.0f1"

GLOBAL_OPTIONS_WITH_VALUES = {"--root", "--version", "--extra-root", "--platform"}
GLOBAL_FLAGS = {"--verbose", "--allow-legacy-env"}


def _find_workspace_root() -> str:
    """Resolve the PROJECT directory (where _apks/_refs/lua/... live).

    The package code is installed separately from the working data, so the root
    is the project dir, not this file's location:
      1. $REVENANT_PROJECT if it points at a directory;
      2. the nearest ancestor of CWD containing revenant.toml (the init marker);
      3. CWD.
    """
    env = os.environ.get("REVENANT_PROJECT")
    if env and os.path.isdir(env):
        return os.path.abspath(env)
    cur = os.getcwd()
    while True:
        if os.path.exists(os.path.join(cur, PROJECT_MARKER)):
            return cur
        parent = os.path.dirname(cur)
        if parent == cur:
            break
        cur = parent
    return os.getcwd()


def workspace_root() -> str:
    return _find_workspace_root()


def project_marker_root() -> str:
    """The project directory a `revenant.toml` actually marks, or "".

    `workspace_root()` answers CWD when it finds no marker, which is right for
    `init` (it is about to write one) and wrong for everything that reads. The
    difference has to be askable, because the two states produce the same paths
    and utterly different meanings: under a real project `_refs/` is missing
    data, under no project it is a directory that was never supposed to exist.

    A whole day of nine-game work was run from a repository root holding nine
    projects. Every index-backed tool answered "indices not built -- run
    `revenant prepare`" about projects that were fully prepared, and the rounds
    that believed it recorded "this game does not have that" (#69).
    """
    env = os.environ.get("REVENANT_PROJECT")
    if env and os.path.isdir(env):
        return os.path.abspath(env) if os.path.exists(
            os.path.join(env, PROJECT_MARKER)) else ""
    cur = os.getcwd()
    while True:
        if os.path.exists(os.path.join(cur, PROJECT_MARKER)):
            return cur
        parent = os.path.dirname(cur)
        if parent == cur:
            return ""
        cur = parent


def nearest_projects(start: str = "", limit: int = 12) -> list:
    """Directories one level under `start` that are projects. For saying so.

    A repository holding nine of them is the case this exists for: "you are not
    in a project" is only half an answer when the other half -- which nine, by
    name -- is one `listdir` away.
    """
    start = os.path.abspath(start or os.getcwd())
    out = []
    try:
        for name in sorted(os.listdir(start)):
            if name.startswith(".") or name.startswith("_"):
                continue
            full = os.path.join(start, name)
            if os.path.isdir(full) and os.path.exists(os.path.join(full, PROJECT_MARKER)):
                out.append(name)
    except OSError:
        return []
    return out[:limit]


def up_to_repo_root(root: str) -> list[str]:
    """`root` and each parent up to the one holding `.git`, nearest first.

    The one place that decides what "above this project" means. Claude Code
    stops looking for project skills at the repository root, so the shared
    harness search stops there (#51); the note sweep across sibling projects
    stops there too (#53). Two different features, one boundary -- revenant may
    not mean two things by "one level up".

    Just `[root]` when no `.git` is found: without a repository there is nothing
    bounding the walk, and reading a stranger's directory to decide what this
    project has is worse than missing a shared copy.
    """
    root = os.path.abspath(root)
    chain = [root]
    directory = root
    while not os.path.exists(os.path.join(directory, ".git")):
        parent = os.path.dirname(directory)
        if parent == directory:
            return [root]
        directory = parent
        chain.append(directory)
    return chain


def repo_root_of(start: str) -> str:
    """The git repository root above `start`, or `start` when there is none."""
    return up_to_repo_root(start)[-1]


# One sentence for one kind of fact: this thing is not any one project's. It
# lives beside `up_to_repo_root` because it is the same boundary said in words
# -- the `_tools/` alarm (#50), the generated harness (#51) and the repository
# root's own `notes/` (#67) all name things that sit above a project, and three
# phrasings that happen to match today would not stay matched.
SHARED_TAG = "shared with the projects beside this one, not part of it"


def shared_label(what: str) -> str:
    """`what`, tagged as belonging to the layer above rather than this project."""
    return f"{what} ({SHARED_TAG})"


_PROJECT_CONFIG_CACHE: dict[str, dict] = {}


def project_config() -> dict:
    """Parse the project's revenant.toml (cached). {} if absent."""
    return load_config(workspace_root())


def load_config(root: str) -> dict:
    """Parse the revenant.toml of a named project (cached). {} if absent.

    Takes the root rather than assuming the ambient one, so a caller working on
    a directory it was handed reads *that* project's configuration. Silently
    answering with the current project's keys is the kind of wrong answer that
    looks like a correct one.
    """
    if root in _PROJECT_CONFIG_CACHE:
        return _PROJECT_CONFIG_CACHE[root]
    path = os.path.join(root, PROJECT_MARKER)
    cfg: dict = {}
    if os.path.exists(path):
        import tomllib
        try:
            with open(path, "rb") as f:
                cfg = tomllib.load(f)
        except tomllib.TOMLDecodeError as exc:
            # Say so, loudly. Swallowing this makes the project behave exactly as
            # if it had no config -- the Lua key, the enabled packs and the
            # pinned platform all vanish at once, and every symptom points
            # somewhere other than the file that is actually broken.
            import sys
            print(
                f"revenant: {path} is not valid TOML and was ignored: {exc}\n"
                f"          Everything configured in it (Lua keys, enabled packs, "
                f"platform, metadata decryptor) is currently inactive.",
                file=sys.stderr,
            )
        except OSError as exc:
            import sys
            print(f"revenant: cannot read {path}: {exc}", file=sys.stderr)
    _PROJECT_CONFIG_CACHE[root] = cfg
    return cfg


# Platform pinned for this process, set by the CLI's --platform. `None` means
# "not pinned"; the package present in the project decides.
_PINNED_PLATFORM: str | None = None


def set_platform(platform: str | None) -> None:
    """Pin the platform for this process (the CLI's --platform)."""
    global _PINNED_PLATFORM
    _PINNED_PLATFORM = platform or None


def selected_platform() -> str | None:
    """The pinned platform, from --platform, $REVENANT_PLATFORM, or revenant.toml.

    None when nothing is pinned, which is the common case: a project usually
    holds one package and its platform is not ambiguous.
    """
    if _PINNED_PLATFORM:
        return _PINNED_PLATFORM
    env = os.environ.get("REVENANT_PLATFORM")
    if env:
        return env
    value = project_config().get("platform")
    return value or None


def find_packages() -> list:
    """Game packages in the project root, in preference order."""
    from .layout import find_packages as _find
    return _find(workspace_root())


def package_path() -> str | None:
    """The package this project is working on, honouring a pinned platform."""
    wanted = selected_platform()
    for path, lay in find_packages():
        if wanted and lay.platform != wanted:
            continue
        return path
    return None


# Kept so existing callers and docs keep working; a project may now hold an ipa.
xapk_path = package_path


def _package_and_layout():
    wanted = selected_platform()
    for path, lay in find_packages():
        if wanted and lay.platform != wanted:
            continue
        return path, lay
    return None, None


def detect_platform() -> str:
    """Platform of the package this project is working on. Defaults to android.

    Defaulting to android (rather than "unknown") is what keeps artifact paths
    for existing Android-only projects byte-identical after this change.
    """
    from .layout import PLATFORM_ANDROID
    wanted = selected_platform()
    if wanted:
        return wanted
    _path, lay = _package_and_layout()
    return lay.platform if lay else PLATFORM_ANDROID


_IDENTITY_CACHE: dict[str, dict] = {}


def _read_identity() -> dict:
    """`{package, version}` from the project's package. Best-effort, cached."""
    path, lay = _package_and_layout()
    if not path or not lay:
        return {}
    if path in _IDENTITY_CACHE:
        return _IDENTITY_CACHE[path]
    from .layout import read_identity
    try:
        found = read_identity(path, lay)
    except Exception:
        found = {}
    _IDENTITY_CACHE[path] = found
    return found


def platform_suffix(platform: str | None = None) -> str:
    """Artifact-directory suffix for a platform.

    Android gets the empty suffix so `_refs/<version>/` keeps its historical
    name and existing projects need no migration; every other platform is
    suffixed. The asymmetry lives here and nowhere else.
    """
    from .layout import PLATFORM_ANDROID
    resolved = platform or detect_platform()
    return "" if resolved == PLATFORM_ANDROID else f"-{resolved}"


def version_dir_name(version: str, platform: str | None = None) -> str:
    """The `_refs/` directory name for a (version, platform) pair."""
    return f"{version}{platform_suffix(platform)}"


def _split_version_dir(name: str) -> tuple[str, str]:
    """Inverse of version_dir_name: 'X-ios' -> ('X', 'ios'), 'X' -> ('X', 'android')."""
    from .layout import LAYOUTS, PLATFORM_ANDROID
    for plat in sorted({lay.platform for lay in LAYOUTS} - {PLATFORM_ANDROID}):
        if name.endswith(f"-{plat}"):
            return name[: -len(plat) - 1], plat
    return name, PLATFORM_ANDROID


def _refs_versions(platform: str | None = None) -> list[str]:
    """Version names under _refs/ for a platform, preferring built ones."""
    want = platform or detect_platform()
    root = os.path.join(workspace_root(), "_refs")
    with_out: list[str] = []
    others: list[str] = []
    try:
        for name in sorted(os.listdir(root)):
            p = os.path.join(root, name)
            if not os.path.isdir(p):
                continue
            version, plat = _split_version_dir(name)
            if plat != want:
                continue
            (with_out if os.path.isdir(os.path.join(p, "cpp2il_out")) else others).append(version)
    except OSError:
        pass
    return with_out or others


def detect_package() -> str:
    """Package name from the project's package, else fallback."""
    return _read_identity().get("package") or _FALLBACK_PACKAGE


def detect_version() -> str:
    """Version from the package, else a built _refs/ dir, else fallback.

    Silent: identity is computed eagerly at import, so this must not warn (it
    would fire on `revenant init`, before a package is dropped in). Actionable
    "no package found" guidance lives in `revenant status` / init output, where
    a fallback to 0.0.0 actually matters.
    """
    v = _read_identity().get("version")
    if v:
        return v
    built = _refs_versions()
    return built[0] if built else _FALLBACK_VERSION


def detect_unity_version() -> str:
    """Unity version from globalgamemanagers in the package, else fallback."""
    path, lay = _package_and_layout()
    if not path or not lay:
        return _FALLBACK_UNITY
    pat = re.compile(rb"(\d{4}\.\d+\.\d+[a-z]\d+)")
    from .layout import find_in_package
    try:
        hit = find_in_package(path, lay, lay.ggm_paths)
    except Exception:
        return _FALLBACK_UNITY
    if not hit:
        return _FALLBACK_UNITY
    m = pat.search(hit[1][:4096])
    return m.group(1).decode() if m else _FALLBACK_UNITY


def load_metadata_decryptor():
    """The project's metadata decryptor, or None.

    Configured as `[metadata] decryptor = "some_module.py"` in revenant.toml,
    relative to the project root. The module must expose
    `decrypt(bytes) -> bytes`.

    Deliberately code and not config: hardening schemes vary by vendor and by
    game, so a built-in decryptor library would be pretending we can enumerate
    vendors. (This does not contradict domain packs refusing plugin hooks --
    slots and probes are declarative data; a decryption routine is code.)
    """
    section = project_config().get("metadata") or {}
    return load_project_callable(section.get("decryptor"), "decrypt",
                                 "[metadata] decryptor")


def load_project_callable(rel: str | None, func: str, setting: str,
                          root: str | None = None) -> "Callable[[bytes], bytes] | None":
    """A named function from a Python file in the project. None when unset.

    The convention for anything revenant must run but must not contain: the
    project writes the code, revenant calls it. Used by the metadata decryptor
    and by the Luban container, which are the same shape of problem -- a scheme
    that varies by vendor and by title, where a bundled library would be
    pretending we can enumerate vendors.
    """
    if not rel:
        return None
    base = root or workspace_root()
    path = rel if os.path.isabs(rel) else os.path.join(base, rel)
    if not os.path.exists(path):
        raise FileNotFoundError(
            f"{setting} points at {rel}, which does not exist (looked in {path})"
        )
    import importlib.util
    module_name = "_revenant_" + re.sub(r"[^A-Za-z0-9]", "_", setting)
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load {setting} at {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    fn = getattr(module, func, None)
    if not callable(fn):
        raise RuntimeError(
            f"{rel} does not expose a callable `{func}(data: bytes) -> bytes`"
        )
    # A hook loaded from a file the project wrote: the signature is a contract
    # stated here and checked by the call, not something the loader can prove.
    return cast("Callable[[bytes], bytes]", fn)


def _app_name_from_package(package: str) -> str:
    seg = package.split(".")[-1] if package else ""
    seg = re.sub(r"[^A-Za-z0-9]+", "-", seg).strip("-").lower()
    return seg or "il2cpp-game"


# Resolved identity (auto-detected at import; the manifest read is cheap).
PACKAGE = detect_package()
DEFAULT_VERSION = detect_version()
APP_NAME = _app_name_from_package(PACKAGE)

# Environment-variable prefix derived from APP_NAME, e.g. <APPNAME>_<VER>_ROOT
ENV_PREFIX = re.sub(r"[^A-Za-z0-9]", "_", APP_NAME).upper()

# Engine / SDK / framework assembly name prefixes (case-insensitive), excluded
# from the "game code" selection. Game assemblies (Assembly-CSharp*, the
# publisher's namespaces, __Generated, ...) are everything that does NOT match.
# Heuristic, not exhaustive -- tune per project. Different games bundle
# different third-party plugins compiled as their own assemblies.
ENGINE_ASSEMBLY_PREFIXES = (
    # Engine / BCL
    "unityengine", "unity.", "system", "mscorlib", "mono.", "netstandard",
    "microsoft.", "newtonsoft", "i18n", "icsharpcode", "protobuf", "websocket",
    # Common third-party SDKs / plugins (ads, analytics, social, lua, share, ...)
    "google", "firebase", "googleplaygames", "googlemobileads", "admob",
    "facebook", "applovin", "maxsdk", "ironsource", "adjust", "appsflyer",
    "gameanalytics", "bytedance", "photon", "exitgames", "dotween", "spine",
    "tmpro", "nativeshare", "mikulua", "tolua", "xlua",
)


def is_game_assembly(name: str) -> bool:
    """True if an assembly dir name looks like game code (not engine/3rd-party).

    Heuristic: keep everything that does not start with a known engine/SDK
    prefix. Adjust ENGINE_ASSEMBLY_PREFIXES per project as needed.
    """
    return not name.lower().startswith(ENGINE_ASSEMBLY_PREFIXES)


def apks_dir() -> str:
    """Directory where extracted APKs are cached."""
    path = os.path.join(workspace_root(), "_apks")
    os.makedirs(path, exist_ok=True)
    return path


def binaries_dir() -> str:
    """Directory where extracted libil2cpp.so and metadata are cached."""
    path = os.path.join(workspace_root(), "_binaries")
    os.makedirs(path, exist_ok=True)
    return path


def refs_dir() -> str:
    """Directory for reference data (indices, IsilDump, DiffableCs)."""
    path = os.path.join(workspace_root(), "_refs")
    os.makedirs(path, exist_ok=True)
    return path


def version_ref_dir(version: str, platform: str | None = None) -> str:
    """Artifact directory for a (version, platform) pair.

    Two-dimensional on purpose. Preparing an apk and then an ipa in the same
    project used to overwrite the first set of indices with no warning, and iOS
    and Android metadata are not byte-identical (#3), so RVAs and indices do not
    survive the mix-up -- a silent wrong answer with nothing to notice.
    """
    return os.path.join(refs_dir(), version_dir_name(version, platform))


def env_key_for_version(version: str) -> str:
    return ENV_PREFIX + "_" + re.sub(r"[^A-Za-z0-9]", "_", version).upper() + "_ROOT"


def find_root(version: str = DEFAULT_VERSION, allow_legacy_env: bool = False) -> str:
    """Find a reverse-engineering root directory for a given version."""
    env_keys = [env_key_for_version(version)]
    if allow_legacy_env:
        env_keys.extend(["GH_RE_ROOT", ENV_PREFIX + "_RE_ROOT"])

    for key in env_keys:
        env_root = os.environ.get(key)
        if env_root:
            return env_root

    parent = os.path.dirname(workspace_root())
    candidates = [
        os.path.join(parent, f"{APP_NAME}-re-{version}"),
        version_ref_dir(version),
        binaries_dir(),
    ]
    for candidate in candidates:
        if os.path.isdir(candidate):
            return candidate
    return binaries_dir()


def normalize_global_args(argv: list[str]) -> list[str]:
    """Allow root/version flags before or after the subcommand."""
    globals_first: list[str] = []
    rest: list[str] = []
    index = 0
    while index < len(argv):
        arg = argv[index]
        if arg == "--":
            rest.extend(argv[index:])
            break

        option_with_inline_value = next(
            (option for option in GLOBAL_OPTIONS_WITH_VALUES if arg.startswith(option + "=")),
            None,
        )
        if option_with_inline_value:
            globals_first.append(arg)
            index += 1
            continue

        if arg in GLOBAL_OPTIONS_WITH_VALUES:
            globals_first.append(arg)
            if index + 1 >= len(argv):
                index += 1
                continue
            globals_first.append(argv[index + 1])
            index += 2
            continue

        if arg in GLOBAL_FLAGS:
            globals_first.append(arg)
            index += 1
            continue

        rest.append(arg)
        index += 1

    return globals_first + rest
