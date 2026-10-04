"""Binary image layer: one interface, two formats, deliberately different errors.

The load-bearing test here is `test_gap_address_resolves_on_elf_but_raises_on_macho`
-- everything else guards its edges.
"""

from __future__ import annotations

import pytest

from revenant import image
from tests import fixtures as fx


def _elf(tmp_path, **kw):
    return fx.write_elf(str(tmp_path / "libil2cpp.so"), **kw)


def _macho(tmp_path, **kw):
    return fx.write_macho(str(tmp_path / "UnityFramework"), **kw)


# ── the asymmetry this layer exists for ─────────────────────────────────────

def test_gap_address_resolves_on_elf_but_raises_on_macho(tmp_path):
    """Same address, same layout numbers, deliberately different outcomes.

    ADDR_IN_GAP is inside the mapped range in both files. ELF maps by segment
    and hands back the padding -- correct for ELF. Mach-O maps by section and
    must raise, because a plausible-looking wrong answer is worse than an error:
    garbage bytes still disassemble and would land in an evidence packet.
    """
    elf_path, macho_path = _elf(tmp_path), _macho(tmp_path)

    mapping = image.map_rva_to_file_offset(elf_path, fx.ADDR_IN_GAP)
    assert mapping.file_offset == fx.ADDR_IN_GAP

    with pytest.raises(image.ImageError, match="not covered by any section"):
        image.map_rva_to_file_offset(macho_path, fx.ADDR_IN_GAP)


def test_macho_does_not_fall_back_to_segment_mapping(tmp_path):
    """Guard against a well-meaning 'best effort' fallback creeping back in."""
    macho_path = _macho(tmp_path)
    img = image.open_image(macho_path)
    assert img.format == image.FORMAT_MACHO
    # The gap address is inside the segment; if any segment-based fallback
    # existed, this would resolve instead of raising.
    with pytest.raises(image.ImageError):
        img.map_rva(fx.ADDR_IN_GAP)


# ── behaviour shared by both formats ────────────────────────────────────────

@pytest.mark.parametrize("build", ["elf", "macho"])
def test_reads_the_right_bytes(tmp_path, build):
    path = _elf(tmp_path) if build == "elf" else _macho(tmp_path)
    mapping, data = image.read_rva_bytes(path, fx.ADDR_IN_TEXT, 16)
    expected_offset = fx.LOAD_FILEOFF + (fx.ADDR_IN_TEXT - fx.LOAD_VADDR)
    assert mapping.file_offset == expected_offset
    assert data == fx._body(fx.LOAD_SIZE)[
        fx.ADDR_IN_TEXT - fx.LOAD_VADDR:fx.ADDR_IN_TEXT - fx.LOAD_VADDR + 16
    ]


@pytest.mark.parametrize("build", ["elf", "macho"])
def test_unmapped_address_raises(tmp_path, build):
    path = _elf(tmp_path) if build == "elf" else _macho(tmp_path)
    with pytest.raises(image.ImageError):
        image.map_rva_to_file_offset(path, fx.ADDR_UNMAPPED)


@pytest.mark.parametrize("build", ["elf", "macho"])
def test_short_read_raises(tmp_path, build):
    path = _elf(tmp_path) if build == "elf" else _macho(tmp_path)
    with pytest.raises(image.ImageError, match="Short read"):
        image.read_rva_bytes(path, fx.ADDR_IN_TEXT, fx.LOAD_SIZE * 4)


@pytest.mark.parametrize("build", ["elf", "macho"])
def test_executable_region_is_reported(tmp_path, build):
    path = _elf(tmp_path) if build == "elf" else _macho(tmp_path)
    assert image.map_rva_to_file_offset(path, fx.ADDR_IN_TEXT).is_executable


# ── architecture crosses the seam as a property, not a header read ──────────

def test_arch_from_elf(tmp_path):
    assert image.image_arch(_elf(tmp_path)) == image.ARCH_ARM64
    assert image.image_arch(fx.write_elf(str(tmp_path / "arm32.so"), machine=fx.EM_ARM)) == image.ARCH_ARM32


def test_arch_from_macho(tmp_path):
    assert image.image_arch(_macho(tmp_path)) == image.ARCH_ARM64
    arm32 = fx.write_macho(str(tmp_path / "fw32"), cputype=fx.CPU_TYPE_ARM)
    assert image.image_arch(arm32) == image.ARCH_ARM32


def test_arch_of_a_non_binary_is_unknown_not_a_crash(tmp_path):
    junk = tmp_path / "notabinary"
    junk.write_bytes(b"hello world")
    assert image.image_arch(str(junk)) == image.ARCH_UNKNOWN


# ── the mapping description is read by agents ───────────────────────────────

ELF_ONLY_VOCABULARY = ["PT_LOAD", "PF_X", "p_vaddr", "e_machine", "segment"]


def test_macho_mapping_description_carries_no_elf_vocabulary(tmp_path):
    """Regression guard: this string goes into evidence packets an agent reads.

    Printing 'PT_LOAD #2' on a Mach-O is not cosmetic -- it asserts a structure
    the file does not have, and nothing downstream would catch it.
    """
    text = image.format_mapping(image.map_rva_to_file_offset(_macho(tmp_path), fx.ADDR_IN_TEXT))
    for word in ELF_ONLY_VOCABULARY:
        assert word not in text, f"{word!r} leaked into a Mach-O mapping description"
    assert "__TEXT,__text" in text


def test_elf_mapping_description_names_the_segment(tmp_path):
    text = image.format_mapping(image.map_rva_to_file_offset(_elf(tmp_path), fx.ADDR_IN_TEXT))
    assert "LOAD#0" in text
    assert "executable" in text


# ── format detection and refusals ───────────────────────────────────────────

def test_zerofill_section_has_no_file_backing(tmp_path):
    path = _macho(tmp_path, with_zerofill=True)
    with pytest.raises(image.ImageError, match="no file backing"):
        image.map_rva_to_file_offset(path, fx.LOAD_VADDR + fx.LOAD_SIZE + 0x10)


def test_fat_macho_is_refused_with_advice(tmp_path):
    path = fx.write_fat_macho(str(tmp_path / "fat"))
    with pytest.raises(image.ImageError, match="lipo -thin"):
        image.open_image(path)


def test_unknown_format_is_refused(tmp_path):
    junk = tmp_path / "junk.bin"
    junk.write_bytes(b"\x00" * 128)
    with pytest.raises(image.ImageError, match="neither an ELF nor a Mach-O"):
        image.open_image(str(junk))


def test_sniff_format(tmp_path):
    assert image.sniff_format(open(_elf(tmp_path), "rb").read(64)) == image.FORMAT_ELF
    assert image.sniff_format(open(_macho(tmp_path), "rb").read(64)) == image.FORMAT_MACHO
    assert image.sniff_format(b"not a binary at all") is None


def test_reparse_after_the_file_changes(tmp_path):
    """The image cache keys on mtime+size, so a rebuilt binary is not stale."""
    path = str(tmp_path / "swap.bin")
    fx.write_elf(path)
    assert image.open_image(path).format == image.FORMAT_ELF
    fx.write_macho(path)
    assert image.open_image(path).format == image.FORMAT_MACHO
