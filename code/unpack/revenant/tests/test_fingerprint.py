"""The fingerprint is an observation list (ADR-0002, #28).

One test per observation, and one for the shape of the whole: no verdict field
survives. The seam is `fingerprint.collect` on a synthetic package, plus the
CLI for the human and JSON renderings.
"""

from __future__ import annotations

import json
import struct
import zipfile

import pytest

from revenant import fingerprint as _fp
from tests import fixtures as fx


@pytest.fixture
def project(tmp_path, monkeypatch):
    from revenant.init import init_project
    root = tmp_path / "proj"
    init_project(str(root), quiet=True)
    monkeypatch.setenv("REVENANT_PROJECT", str(root))
    from revenant import config
    config._PROJECT_CONFIG_CACHE.clear()
    config._IDENTITY_CACHE.clear()
    config.set_platform(None)
    yield root
    config._PROJECT_CONFIG_CACHE.clear()


def _metadata_with_literals(literals: list[str]) -> bytes:
    """Plaintext metadata whose string-literal table holds exactly `literals`."""
    data = b"".join(s.encode() for s in literals)
    entries = bytearray()
    at = 0
    for s in literals:
        entries += struct.pack("<II", len(s.encode()), at)
        at += len(s.encode())
    header_len = 24 + 64
    lit_off = header_len
    data_off = lit_off + len(entries)
    header = fx.METADATA_MAGIC + struct.pack("<I", 29)
    # Sizes in bytes, as the real header has them -- not counts.
    header += struct.pack("<IIII", lit_off, len(entries), data_off, len(data))
    header += bytes(header_len - len(header))
    return bytes(header) + bytes(entries) + data


def _apk(tmp_path, elf: bytes, metadata: bytes, extra: dict | None = None) -> str:
    path = str(tmp_path / "game.apk")
    fx.write_apk(path, elf, metadata)
    if extra:
        with zipfile.ZipFile(path, "a") as z:
            for name, blob in extra.items():
                z.writestr(name, blob)
    return path


def _elf_with(tmp_path, *strings: bytes) -> bytes:
    base = open(fx.write_elf(str(tmp_path / "_e.bin")), "rb").read()
    return base + b"\0".join(strings) + b"\0"


def test_the_fingerprint_has_no_verdict_fields(tmp_path):
    fp = _fp.collect(_apk(tmp_path, _elf_with(tmp_path), fx.fake_metadata()))
    out = fp.to_json()
    for verdict in ("corpus", "corpus_reason", "scripting", "baseline", "identity_signals",
                    "native_vendors", "third_party_sdks"):
        assert verdict not in out, f"{verdict} is a judgement, not an observation"
    for judge in ("decide_corpus", "same_origin", "classify_provenance", "narrow",
                  "SAME_ORIGIN_THRESHOLD"):
        assert not hasattr(_fp, judge)


def test_markers_seen_lists_every_marker_with_zero_hits_included(tmp_path):
    """The wiped-marker case: zeros next to the siblings, no verdict to flip."""
    elf = _elf_with(tmp_path, b"HybridCLR", b"HybridCLR", b"InterpreterImage")
    fp = _fp.collect(_apk(tmp_path, elf, fx.fake_metadata()))
    by_marker = {m.marker: m for m in fp.markers("hybridclr")}
    assert set(by_marker) == {"HybridCLR", "InterpreterImage", "LoadMetadataForAOTAssembly"}
    assert by_marker["HybridCLR"].hits[_fp.WHERE_BINARY] == 2
    assert by_marker["LoadMetadataForAOTAssembly"].hits[_fp.WHERE_BINARY] == 0
    assert all(m.total == 0 for m in fp.markers("ifix"))
    # A wiped table is all zeros, and still listed.
    assert [m.total for m in fp.markers("xlua")] == [0, 0, 0]


def test_markers_are_counted_where_they_were_looked_for(tmp_path):
    fp = _fp.collect(_apk(tmp_path, _elf_with(tmp_path), fx.fake_metadata(),
                          {"lib/arm64-v8a/libxlua.so": b"\0", "classes.dex": b"Lcom/HybridCLR/Loader;hybridclr"}))
    xlua = {m.marker: m for m in fp.markers("xlua")}
    assert xlua["xlua"].hits[_fp.WHERE_MEMBERS] == 1
    assert xlua["xlua"].hits[_fp.WHERE_BINARY] == 0
    hybrid = {m.marker: m for m in fp.markers("hybridclr")}
    assert hybrid["HybridCLR"].hits[_fp.WHERE_DEX] == 1


def test_declared_assemblies_are_cross_checked_against_the_metadata_both_ways(tmp_path):
    manifest = json.dumps({"names": ["Game.dll", "UnityEngine.dll", "Hot.Update.dll"],
                           "types": [16, 16, 16]})
    metadata = fx.fake_metadata() + b"Game.dll\0UnityEngine.dll\0"
    fp = _fp.collect(_apk(tmp_path, _elf_with(tmp_path), metadata,
                          {"assets/bin/Data/ScriptingAssemblies.json": manifest}))
    assert fp.declared_assemblies == ["Game.dll", "UnityEngine.dll", "Hot.Update.dll"]
    assert fp.assemblies_in_metadata == ["Game.dll", "UnityEngine.dll"]
    assert fp.assemblies_absent == ["Hot.Update.dll"]
    assert fp.business_assemblies_absent() == ["Hot.Update.dll"]


def test_the_absent_assemblies_note_is_a_fact_not_a_gate(tmp_path):
    fp = _fp.Fingerprint(declared_assemblies=["Hot.Update.dll", "UnityEngine.UI.dll"],
                         assemblies_absent=["Hot.Update.dll", "UnityEngine.UI.dll"])
    text = _fp.format_text(fp)
    assert "do not exist in the corpus about to be searched: Hot.Update.dll" in text
    # Engine assemblies are stripped routinely; they are listed but not in the note.
    assert "UnityEngine.UI.dll" in text
    assert "searched: Hot.Update.dll, UnityEngine.UI.dll" not in text
    for word in ("hot_update_assembly", "corpus :", "verdict"):
        assert word not in text


def test_bytes_literals_come_from_the_metadata_string_heap(tmp_path):
    metadata = _metadata_with_literals(["common_c_md.bytes", "common_c_ut.bytes",
                                        "common_c_vw.bytes", "not_this", "x.bytesy"])
    assert _fp.collect_bytes_literals(metadata) == [
        "common_c_md.bytes", "common_c_ut.bytes", "common_c_vw.bytes"]
    fp = _fp.collect(_apk(tmp_path, _elf_with(tmp_path), metadata))
    assert fp.bytes_literals == ["common_c_md.bytes", "common_c_ut.bytes", "common_c_vw.bytes"]


def test_bytes_literals_fall_back_to_a_text_sweep_on_a_blob_without_a_header():
    blob = b"garbage\0dlc/pack_01.bytes\0more\0"
    assert _fp.collect_bytes_literals(blob) == ["dlc/pack_01.bytes"]


def test_bytes_literals_prefer_the_recovered_metadata_over_the_package_copy(project, tmp_path):
    """A packed title ships ciphertext; the literals are in `_binaries/`."""
    (project / "_binaries").mkdir(exist_ok=True)
    (project / "_binaries" / "abc-global-metadata.dat").write_bytes(
        _metadata_with_literals(["recovered.bytes"]))
    fp = _fp.collect(_apk(project, _elf_with(tmp_path), fx.fake_metadata() + b"packaged.bytes\0"))
    assert fp.bytes_literals == ["recovered.bytes"]
    assert "_binaries" in fp.metadata_source


def test_build_paths_are_listed_as_found_not_ranked(tmp_path):
    elf = _elf_with(tmp_path,
                    b"/Users/ci/jenkins/workspace/Game/build",
                    b"/Users/ci/firebase/sdk/build/x",
                    b"/Applications/Unity/Hub/Editor/2022/Unity.app/Contents")
    fp = _fp.collect(_apk(tmp_path, elf, fx.fake_metadata()))
    assert fp.build_paths == sorted(fp.build_paths)
    assert fp.build_paths_total == 3
    assert "/Users/ci/firebase/sdk/build/x" in fp.build_paths
    for gone in ("_THIRD_PARTY_BUILD", "_UNINFORMATIVE_PATH", "_PROJECT_HINT"):
        assert not hasattr(_fp, gone)


def test_native_exports_are_listed_raw_without_a_vendor_name(tmp_path):
    fp = _fp.collect(_apk(tmp_path, _elf_with(tmp_path), fx.fake_metadata(), {
        "lib/arm64-v8a/libmystery.so": b"\0Java_com_vendor_sdk_Native_init\0Java_com_vendor_sdk_Native_stop\0",
    }))
    assert fp.native_exports["lib/arm64-v8a/libmystery.so"] == [
        "Java_com_vendor_sdk_Native_init", "Java_com_vendor_sdk_Native_stop"]
    assert not hasattr(_fp, "_native_vendor")


def test_dex_packages_are_four_segments_deep(tmp_path):
    dex = b"Lcom/google/android/gms/ads/AdView;Lcom/google/android/play/core/X;Lcom/a/b;"
    fp = _fp.collect(_apk(tmp_path, _elf_with(tmp_path), fx.fake_metadata(), {"classes.dex": dex}))
    assert fp.dex_packages == ["com/google/android/gms", "com/google/android/play"]


def test_domains_and_unity_version_are_read_from_the_package(tmp_path):
    fp = _fp.collect(_apk(tmp_path, _elf_with(tmp_path),
                          fx.fake_metadata() + b"https://cdn.example.com/x https://api.example.net"))
    assert fp.domains == ["https://api.example.net", "https://cdn.example.com"]
    assert fp.unity_version == "2022.3.62f2"


def test_the_json_carries_totals_next_to_every_capped_list(tmp_path):
    fp = _fp.collect(_apk(tmp_path, _elf_with(tmp_path, b"XLua"), fx.fake_metadata()))
    out = json.loads(json.dumps(fp.to_json()))
    for key in ("build_paths", "dex_packages", "domains"):
        assert f"{key}_total" in out
    assert next(m for m in out["markers_seen"] if m["marker"] == "XLua")["hits"]["binary"] == 1


def test_a_wiped_marker_leaves_zeros_and_the_absent_note_and_no_verdict(tmp_path):
    """The case that motivated #28: a packer erased the marker strings while
    the manifest still declares business assemblies the metadata lacks. The
    old gate said `il2cpp` and let a zero-hit scan through; now the reader
    sees all-zero markers, a non-empty difference, and the note -- and decides.
    """
    manifest = json.dumps({"names": ["Game.Core.dll"], "types": [16]})
    fp = _fp.collect(_apk(tmp_path, _elf_with(tmp_path), fx.fake_metadata(),
                          {"assets/bin/Data/ScriptingAssemblies.json": manifest}))
    assert all(m.total == 0 for m in fp.markers_seen)
    assert fp.assemblies_absent == ["Game.Core.dll"]
    text = _fp.format_text(fp)
    assert "do not exist in the corpus about to be searched: Game.Core.dll" in text
    assert "hybridclr  HybridCLR=0/0/0" in text
    assert "corpus         :" not in text and "il2cpp" not in text


def test_fingerprint_does_not_create_a_ledger_in_a_project_without_a_pack(project, tmp_path, monkeypatch):
    """Ledgers are the frozen scan family's; a core command leaves no trace of it."""
    from revenant import cli
    fx.write_apk(str(project / "game.apk"), _elf_with(tmp_path), fx.fake_metadata())
    monkeypatch.chdir(project)
    assert cli.main(["fingerprint"]) == 0
    assert not (project / ".revenant" / "scan").exists()


def test_signing_certs_are_digested_as_an_observation(tmp_path):
    """Which signer, never whether the signer is right (ADR-0002).

    A mirror that repackages a build has to resign it, so the digest is how a
    resigning shows up; two packages sharing one were signed by the same key.
    """
    def certs(where, block):
        d = tmp_path / where
        d.mkdir()
        fp = _fp.collect(_apk(d, _elf_with(tmp_path), fx.fake_metadata(), {
            "META-INF/BNDLTOOL.RSA": block,
            "META-INF/MANIFEST.MF": b"Manifest-Version: 1.0\n",   # not a cert block
        }))
        return fp

    fp = certs("a", b"\x30\x82fake-pkcs7-block")
    assert list(fp.signing_certs) == ["META-INF/BNDLTOOL.RSA"], "only cert blocks, not the manifest"
    digest = fp.signing_certs["META-INF/BNDLTOOL.RSA"]
    assert len(digest) == _fp.CERT_DIGEST_CHARS
    assert all(c in "0123456789abcdef" for c in digest)

    same = certs("b", b"\x30\x82fake-pkcs7-block")
    assert same.signing_certs["META-INF/BNDLTOOL.RSA"] == digest, "same key -> same digest"
    other = certs("c", b"\x30\x82a-different-signer")
    assert other.signing_certs["META-INF/BNDLTOOL.RSA"] != digest, "resigned -> different digest"

    # Observation only: no verdict field appears anywhere.
    out = fp.to_json()
    assert "signer_trusted" not in out and "repackaged" not in out
