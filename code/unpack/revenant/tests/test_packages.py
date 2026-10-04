"""Package layer: one table, three formats, artifacts keyed by version+platform.

Everything here drives the real code against synthetic packages in a tmp
project, and asserts what ends up on disk or comes back from a lookup. No mocks.
"""

from __future__ import annotations

import importlib
import os

import pytest

from tests import fixtures as fx


@pytest.fixture
def project(tmp_path, monkeypatch):
    """A initialised project, with the toolkit rooted at it."""
    from revenant.init import init_project
    root = tmp_path / "proj"
    init_project(str(root), quiet=True)
    monkeypatch.setenv("REVENANT_PROJECT", str(root))
    monkeypatch.delenv("REVENANT_PLATFORM", raising=False)
    _reset_caches()
    yield root
    _reset_caches()


def _reset_caches():
    from revenant import config
    config._PROJECT_CONFIG_CACHE.clear()
    config._IDENTITY_CACHE.clear()
    config.set_platform(None)


def _elf_bytes(tmp_path):
    return open(fx.write_elf(str(tmp_path / "_elf.bin")), "rb").read()


def _macho_bytes(tmp_path, **kw):
    return open(fx.write_macho(str(tmp_path / "_macho.bin"), **kw), "rb").read()


# ── locating the binary across the three formats ────────────────────────────

def test_finds_binary_in_apk(project, tmp_path):
    from revenant import binary
    fx.write_apk(str(project / "game.apk"), _elf_bytes(tmp_path), fx.fake_metadata())
    located = binary.find_libil2cpp()
    assert open(located.path, "rb").read(4) == b"\x7fELF"
    assert "libil2cpp.so" in located.source


def test_finds_binary_in_xapk_across_the_nesting(project, tmp_path):
    from revenant import binary
    fx.write_xapk(str(project / "game.xapk"), _elf_bytes(tmp_path), fx.fake_metadata())
    located = binary.find_libil2cpp()
    assert open(located.path, "rb").read(4) == b"\x7fELF"
    # source records both levels: outer package, inner split, member
    assert located.source.count("!") == 2


def test_finds_framework_not_launch_shell_in_ipa(project, tmp_path):
    """Both binaries are Mach-O, so only the path can pick the real one.

    The shell here is a *different* Mach-O (arm32) so a wrong pick is
    unambiguous rather than accidentally right.
    """
    from revenant import binary
    shell = _macho_bytes(tmp_path, cputype=fx.CPU_TYPE_ARM)
    framework = open(fx.write_macho(str(tmp_path / "_fw.bin")), "rb").read()
    fx.write_ipa(str(project / "game.ipa"), framework, fx.fake_metadata(), shell_bytes=shell)

    located = binary.find_libil2cpp()
    assert "UnityFramework.framework/UnityFramework" in located.source
    from revenant import image
    assert image.image_arch(located.path) == image.ARCH_ARM64  # not the arm32 shell


def test_no_package_says_so(project):
    from revenant import binary
    with pytest.raises(FileNotFoundError, match="No game package"):
        binary.find_libil2cpp()


# ── identity comes from the same table ──────────────────────────────────────

def test_identity_from_xapk_manifest(project, tmp_path):
    from revenant import config
    fx.write_xapk(str(project / "game.xapk"), _elf_bytes(tmp_path), fx.fake_metadata(),
                  package="com.acme.merge", version="9.9.9")
    _reset_caches()
    assert config.detect_package() == "com.acme.merge"
    assert config.detect_version() == "9.9.9"


def test_an_apks_is_read_as_the_split_package_it_is(project, tmp_path):
    """`.apks` is Google's split format, `.xapk` a mirror's repackaging of it.

    Structurally the same -- base apk beside `config.*.apk`, a `manifest.json`
    carrying the package name -- so one layout serves both. The ninth title
    arrived as `.apks` and `layout_for` returned None (#39).
    """
    from revenant import config, layout
    path = str(project / "game.apks")
    fx.write_xapk(path, _elf_bytes(tmp_path), fx.fake_metadata(),
                  package="com.acme.split", version="0.81.0")
    _reset_caches()
    lay = layout.layout_for(path)
    assert lay is not None and lay.kind == "xapk"
    assert layout.read_identity(path, lay) == {"package": "com.acme.split", "version": "0.81.0"}
    assert config.detect_package() == "com.acme.split"
    # And the nesting still resolves, so the binary is reachable inside it.
    from revenant.binary import find_libil2cpp
    assert find_libil2cpp(str(project))


def test_identity_from_ipa_info_plist(project, tmp_path):
    from revenant import config
    fx.write_ipa(str(project / "game.ipa"), _macho_bytes(tmp_path), fx.fake_metadata(),
                 package="com.acme.ios", version="7.7.7")
    _reset_caches()
    assert config.detect_package() == "com.acme.ios"
    assert config.detect_version() == "7.7.7"


def test_platform_follows_the_package(project, tmp_path):
    from revenant import config
    fx.write_ipa(str(project / "game.ipa"), _macho_bytes(tmp_path), fx.fake_metadata())
    _reset_caches()
    assert config.detect_platform() == "ios"


def test_unity_version_read_from_either_platform(project, tmp_path):
    from revenant import config
    fx.write_ipa(str(project / "game.ipa"), _macho_bytes(tmp_path), fx.fake_metadata())
    _reset_caches()
    assert config.detect_unity_version() == "2022.3.62f2"


# ── artifacts are keyed by (version, platform) ──────────────────────────────

def test_android_artifact_dir_keeps_its_historical_name(project):
    """Existing Android-only projects must keep working with no migration."""
    from revenant import config
    _reset_caches()
    assert config.version_dir_name("3.91.0", "android") == "3.91.0"
    assert config.version_ref_dir("3.91.0", "android").endswith("_refs/3.91.0")


def test_ios_artifact_dir_is_separate(project):
    from revenant import config
    assert config.version_dir_name("3.91.0", "ios") == "3.91.0-ios"


def test_two_platforms_do_not_overwrite_each_other(project):
    """The silent failure this change exists to remove.

    Same version, two platforms: the artifact directories must be distinct, or
    the second `prepare` quietly replaces the first project's indices and every
    later query runs against a mix of the two.
    """
    from revenant import config
    android = config.version_ref_dir("1.0.0", "android")
    ios = config.version_ref_dir("1.0.0", "ios")
    assert android != ios

    for path in (android, ios):
        os.makedirs(os.path.join(path, "cpp2il_out"), exist_ok=True)
        with open(os.path.join(path, "cpp2il_out", "marker.txt"), "w") as f:
            f.write(os.path.basename(path))

    for path in (android, ios):
        with open(os.path.join(path, "cpp2il_out", "marker.txt")) as f:
            assert f.read() == os.path.basename(path)


def test_version_discovery_does_not_mix_platforms(project):
    from revenant import config
    os.makedirs(os.path.join(config.refs_dir(), "1.0.0", "cpp2il_out"))
    os.makedirs(os.path.join(config.refs_dir(), "2.0.0-ios", "cpp2il_out"))
    assert config._refs_versions("android") == ["1.0.0"]
    assert config._refs_versions("ios") == ["2.0.0"]


def test_pinned_platform_selects_the_package(project, tmp_path):
    """A project holding both packages resolves by the pin, not by luck."""
    from revenant import config
    fx.write_apk(str(project / "game.apk"), _elf_bytes(tmp_path), fx.fake_metadata(),
                 package="com.acme.android")
    fx.write_ipa(str(project / "game.ipa"), _macho_bytes(tmp_path), fx.fake_metadata(),
                 package="com.acme.ios")
    _reset_caches()
    assert config.detect_platform() == "android"      # Android preferred by default

    config.set_platform("ios")
    _reset_caches()
    config.set_platform("ios")
    assert config.detect_platform() == "ios"
    assert config.package_path().endswith(".ipa")


# ── metadata: quarantine, and the decryptor hook ────────────────────────────

def test_plaintext_metadata_is_found(project, tmp_path):
    from revenant import binary
    fx.write_apk(str(project / "game.apk"), _elf_bytes(tmp_path), fx.fake_metadata())
    located = binary.find_global_metadata()
    assert open(located.path, "rb").read(4) == fx.METADATA_MAGIC


def test_encrypted_metadata_is_quarantined_and_named_as_such(project, tmp_path):
    """Kept, not deleted -- the ciphertext is what you reverse the loader with.

    And the error has to say "encrypted", because handing the blob to Cpp2IL
    produces a crash that mentions nothing of the sort.
    """
    from revenant import binary
    fx.write_apk(str(project / "game.apk"), _elf_bytes(tmp_path),
                 fx.fake_metadata(plaintext=False, xor_key=0x5A))
    with pytest.raises(FileNotFoundError, match="encrypted"):
        binary.find_global_metadata()

    quarantined = binary.metadata_candidates()
    assert quarantined, "the ciphertext must survive on disk"
    assert all(p.endswith(binary.QUARANTINE_SUFFIX) for p, _ in quarantined)


def test_project_decryptor_unlocks_the_metadata(project, tmp_path):
    from revenant import binary, config
    fx.write_apk(str(project / "game.apk"), _elf_bytes(tmp_path),
                 fx.fake_metadata(plaintext=False, xor_key=0x5A))
    (project / "tools").mkdir(exist_ok=True)
    (project / "tools" / "dec.py").write_text(
        "def decrypt(data: bytes) -> bytes:\n"
        "    return bytes(b ^ 0x5A for b in data)\n"
    )
    (project / "revenant.toml").write_text(
        '[metadata]\ndecryptor = "tools/dec.py"\n'
    )
    _reset_caches()

    located = binary.find_global_metadata()
    assert open(located.path, "rb").read(4) == fx.METADATA_MAGIC
    assert "decrypted" in located.source


def test_a_wrong_decryptor_is_reported_as_a_decryption_failure(project, tmp_path):
    """Distinguishing "decryption is wrong" from "format is unknown" matters."""
    from revenant import binary
    fx.write_apk(str(project / "game.apk"), _elf_bytes(tmp_path),
                 fx.fake_metadata(plaintext=False, xor_key=0x5A))
    (project / "tools").mkdir(exist_ok=True)
    (project / "tools" / "dec.py").write_text(
        "def decrypt(data: bytes) -> bytes:\n"
        "    return bytes(b ^ 0x11 for b in data)\n"   # wrong key
    )
    (project / "revenant.toml").write_text('[metadata]\ndecryptor = "tools/dec.py"\n')
    _reset_caches()

    with pytest.raises(FileNotFoundError, match="algorithm is not right yet"):
        binary.find_global_metadata()


def test_a_raising_decryptor_names_itself(project, tmp_path):
    from revenant import binary
    fx.write_apk(str(project / "game.apk"), _elf_bytes(tmp_path),
                 fx.fake_metadata(plaintext=False, xor_key=0x5A))
    (project / "tools").mkdir(exist_ok=True)
    (project / "tools" / "dec.py").write_text(
        "def decrypt(data: bytes) -> bytes:\n    raise ValueError('nope')\n")
    (project / "revenant.toml").write_text('[metadata]\ndecryptor = "tools/dec.py"\n')
    _reset_caches()

    with pytest.raises(RuntimeError, match="decryptor raised"):
        binary.find_global_metadata()


def test_a_missing_decryptor_file_is_a_clear_error(project, tmp_path):
    from revenant import config
    (project / "revenant.toml").write_text('[metadata]\ndecryptor = "tools/nope.py"\n')
    _reset_caches()
    with pytest.raises(FileNotFoundError, match="does not exist"):
        config.load_metadata_decryptor()


# ── bundle discovery follows the platform ───────────────────────────────────

def test_bundle_root_resolves_a_glob_on_ios(project, tmp_path):
    """iOS bundle roots contain the app name, which is not known ahead of time."""
    import zipfile
    from revenant import assets
    path = str(project / "game.ipa")
    fx.write_ipa(path, _macho_bytes(tmp_path), fx.fake_metadata(), app="Merge")
    with zipfile.ZipFile(path, "a") as z:
        z.writestr("Payload/Merge.app/Data/Raw/aa/iOS/thing.bundle", b"x")
    _reset_caches()

    found = assets.find_bundle_source()
    assert found is not None
    archive, root = found
    assert archive.endswith("game.ipa")
    assert root == "Payload/Merge.app/Data/Raw/aa/iOS"


def test_the_ggm_finder_reads_every_path_the_layout_declares(project):
    """Same shape as the .gitignore test above: the paths are a fact of `layout`,
    so this reads them from there instead of keeping a second copy. #47's defect
    was a declared path with no consumer -- `ggm_paths` had been in the table all
    along and nothing looked at it."""
    from revenant import assets, layout

    assert assets.GGM_PATHS is layout.ANDROID_GGM, "one table, not a second copy"
    for lay in layout.LAYOUTS:
        assert lay.ggm_paths, f"{lay.kind} declares no baked-in serialized files"
        for pattern in lay.ggm_paths:
            assert os.path.basename(pattern) in ("globalgamemanagers", "data.unity3d"), pattern


def test_the_baked_in_serialized_files_are_found_through_the_layout(project, tmp_path):
    """An ipa keeps them under `Payload/<App>.app/Data/`, so the finder has to
    resolve a glob -- the same reason `bundle_roots` cannot be plain prefixes."""
    from revenant import assets
    path = str(project / "game.ipa")
    fx.write_ipa(path, _macho_bytes(tmp_path), fx.fake_metadata(), app="Merge")
    _reset_caches()

    found = list(assets.iter_ggm_sources())
    assert [label for label, _ in found] == ["game.ipa!Payload/Merge.app/Data/globalgamemanagers"]
    assert found[0][1], "the member's bytes come back with it"


def test_a_broken_config_is_reported_not_swallowed(project, capsys):
    """Silently ignoring it makes every symptom point at the wrong file.

    A malformed revenant.toml used to leave the project behaving exactly as if
    it had no config -- the Lua key, the enabled packs and the pinned platform
    all disappearing at once, with nothing said.
    """
    (project / "revenant.toml").write_text('[lua]\nxor_key = "a"\n\n[lua]\nsize_t = 8\n')
    _reset_caches()
    from revenant import config
    assert config.project_config() == {}
    err = capsys.readouterr().err
    assert "not valid TOML" in err and "inactive" in err


def test_the_generated_gitignore_covers_every_package_suffix_the_layout_reads(project):
    """A format the harness accepts but git does not ignore lands in the repo.

    #39 taught the layout `.apks`; the template still only had `*.apk`, which
    does not match it, and a 270 MB package was staged on the first real cold
    start (#41). The suffix list is a fact of `layout`, so this reads it from
    there rather than keeping a second copy.
    """
    import fnmatch
    from revenant import layout

    patterns = [ln.strip() for ln in (project / ".gitignore").read_text().splitlines()
                if ln.strip() and not ln.startswith("#")]
    suffixes = {s for lay in layout.LAYOUTS for s in lay.suffixes}
    assert suffixes, "the layout table should declare package suffixes"
    for suffix in sorted(suffixes):
        name = f"game{suffix}"
        assert any(fnmatch.fnmatch(name, pat) for pat in patterns), (
            f"{name} is a package the layout reads but .gitignore does not ignore")


def test_the_generated_gitignore_keeps_res_tools_tracked_but_still_hides_extracts(project):
    """The per-project scripts under res/_tools/ are cited by notes, so they ship.

    Asked of real git rather than of a pattern matcher: the failure this guards
    (#45) is precisely a case where the rules *read* correct and git disagreed.
    """
    import subprocess

    def git(*args):
        return subprocess.run(("git", "-C", str(project)) + args,
                              capture_output=True, text=True)

    if git("init", "-q").returncode != 0:
        pytest.skip("no usable git")
    (project / "res" / "_tools").mkdir(parents=True, exist_ok=True)
    (project / "res" / "_tools" / "fetch.py").write_text("# cited by notes\n")
    (project / "res" / "bundles").mkdir(parents=True, exist_ok=True)
    (project / "res" / "bundles" / "a.bundle").write_bytes(b"UnityFS")

    git("add", "-A")
    staged = set(git("diff", "--cached", "--name-only").stdout.split())
    assert "res/_tools/fetch.py" in staged, (
        "res/_tools/ holds the scripts notes cite; it must reach the repo")
    assert "res/bundles/a.bundle" not in staged, (
        "extracted bundles are regenerable and must stay out")


def _dead_negations(patterns):
    """Negations that can never fire: their parent is excluded as a whole dir."""
    bare_dirs = {p.rstrip("/") for p in patterns
                 if p.endswith("/") and not p.startswith("!") and "*" not in p}
    dead = []
    for negation in [p for p in patterns if p.startswith("!")]:
        parts = negation[1:].strip("/").split("/")
        ancestors = {"/".join(parts[:i]) for i in range(1, len(parts))}
        dead += [(negation, blocker) for blocker in sorted(ancestors & bare_dirs)]
    return dead


def test_no_negation_in_the_generated_gitignore_sits_under_a_bare_excluded_dir(project):
    """`res/` + `!res/_tools/` looks like it works and does nothing.

    git stops descending at an excluded directory, so a negation for something
    inside one is never evaluated -- which is how every project's res/_tools/
    stayed untracked while 18 note citations pointed at those scripts (#45).
    The parent has to be excluded as `res/*` for git to judge entries one by
    one. This reads the template's own rules, so it catches the next such pair
    too, not just this one.
    """
    patterns = [ln.strip() for ln in (project / ".gitignore").read_text().splitlines()
                if ln.strip() and not ln.startswith("#")]
    assert any(p.startswith("!") for p in patterns), (
        "with no negation left this check would pass by having nothing to judge")
    dead = _dead_negations(patterns)
    assert not dead, "; ".join(
        f"{neg} never applies: {blocker}/ excludes the whole directory, so git "
        f"never looks inside it -- exclude it as {blocker}/* instead"
        for neg, blocker in dead)


def test_the_dead_negation_check_recognises_the_shape_it_was_written_for():
    """The reverse of the rule above: it must fail the pair that shipped (#45)."""
    assert _dead_negations(["res/", "!res/_tools/"]) == [("!res/_tools/", "res")]
    assert _dead_negations(["res/*", "!res/_tools/"]) == []


def test_the_layout_no_longer_declares_a_lua_root_nobody_reads():
    """The sibling of the `ggm_paths` test above, settled the other way.

    #41, #45 and #47 were each "the table holds a path and nothing reads it";
    `lua_roots` was the fourth. It was deleted rather than connected: unlike
    `bundle_roots` -- where a root must be picked because everything downstream
    joins paths onto it -- and `ggm_paths` -- exact file names -- Lua bundles
    are found by *shape* across the whole archive (`lua.is_lua_bundle_entry`),
    which needs no root. The field had no consumer because it had no job, and
    narrowing the search to a root list would lose scripts sitting outside it.
    """
    import dataclasses
    from revenant import layout

    declared = {f.name for f in dataclasses.fields(layout.PackageLayout)}
    assert "lua_roots" not in declared
    for lay in layout.LAYOUTS:
        assert not hasattr(lay, "lua_roots"), lay.kind
