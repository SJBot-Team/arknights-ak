"""Format-neutral binary image: read bytes at an RVA, and know the architecture.

Replaces the ELF-only mapper. Two implementations sit behind one interface --
ELF (Android `libil2cpp.so`) and Mach-O (iOS `UnityFramework`) -- so `disasm`,
`cfg` and the evidence packets never learn which format they are reading.

The two formats do NOT map addresses the same way, and the difference is not
cosmetic:

- **ELF maps by PT_LOAD segment.** A segment is a coarse, page-aligned range; an
  address inside it that no real content covers still resolves, to a file offset
  holding padding.
- **Mach-O maps by section.** Cpp2IL's own Mach-O reader throws
  `Could not find section for virtual address ...` for addresses above the last
  section, and that throw is the *correct* behaviour.

Mapping Mach-O by segment (as the ported vita `ios_macho.py` did) would silently
hand back a garbage offset instead of raising. Garbage bytes still disassemble
into something plausible, which then lands in an evidence packet and gets tagged
with an evidence tier. **A visible error beats a plausible lie**, so the Mach-O
implementation here maps by section and raises when nothing covers the address.
"""

from __future__ import annotations

import os
import struct
from dataclasses import dataclass

ARCH_ARM64 = "arm64"
ARCH_ARM32 = "arm32"
ARCH_UNKNOWN = "unknown"

FORMAT_ELF = "elf"
FORMAT_MACHO = "macho"

# ELF program-header flags
_PF_X = 0x1

# ELF e_machine (elf.h)
_EM_ARM = 40
_EM_AARCH64 = 183

# Mach-O magics
_MH_MAGIC_64 = 0xFEEDFACF
_MH_MAGIC_32 = 0xFEEDFACE
_FAT_MAGICS = (0xCAFEBABE, 0xBEBAFECA, 0xCAFEBABF, 0xBFBAFECA)

# Mach-O cputype (mach/machine.h)
_CPU_TYPE_ARM = 12
_CPU_TYPE_ARM64 = 0x0100000C

# Mach-O load commands
_LC_SEGMENT = 0x1
_LC_SEGMENT_64 = 0x19

# Mach-O section types (flags & SECTION_TYPE) that occupy VM but not the file
_ZEROFILL_TYPES = (0x1, 0xC, 0x12)  # S_ZEROFILL, S_GB_ZEROFILL, S_THREAD_LOCAL_ZEROFILL
_SECTION_TYPE_MASK = 0xFF

# Mach-O section attributes
_S_ATTR_PURE_INSTRUCTIONS = 0x80000000
_S_ATTR_SOME_INSTRUCTIONS = 0x00000400

# VM protection bits (mach/vm_prot.h)
_VM_PROT_EXECUTE = 0x4


@dataclass(frozen=True)
class RegionMapping:
    """How an RVA maps to a file offset, in format-neutral terms.

    `region_name` is whatever the format calls the thing that covered the
    address -- `LOAD#2` for ELF, `__TEXT,__text` for Mach-O. It is printed into
    evidence packets that an agent reads, so it must never carry vocabulary from
    the wrong format.
    """

    rva: int
    file_offset: int
    region_name: str
    region_vaddr: int
    region_offset: int
    region_filesz: int
    region_memsz: int
    is_executable: bool


class ImageError(ValueError):
    """A binary image could not be parsed, or an address could not be mapped."""


class Image:
    """A parsed binary image. Subclasses provide the per-format mapping."""

    format: str = ""

    def __init__(self, path: str, data: bytes) -> None:
        self.path = path
        self._data = data

    @property
    def arch(self) -> str:
        raise NotImplementedError

    def map_rva(self, rva: int) -> RegionMapping:
        raise NotImplementedError

    def read_rva(self, rva: int, size: int) -> tuple[RegionMapping, bytes]:
        mapping = self.map_rva(rva)
        chunk = self._data[mapping.file_offset:mapping.file_offset + size]
        if len(chunk) < size:
            raise ImageError(
                f"Short read at RVA 0x{rva:X}: got {len(chunk)} bytes, wanted {size}"
            )
        return mapping, chunk


class ElfImage(Image):
    """ELF, mapped by PT_LOAD segment."""

    format = FORMAT_ELF

    def __init__(self, path: str, data: bytes) -> None:
        super().__init__(path, data)
        if data[:4] != b"\x7fELF":
            raise ImageError(f"Not an ELF file: {path}")
        self._is_64 = data[4] == 2
        self._endian = "<" if data[5] == 1 else ">"
        self._machine = struct.unpack_from(f"{self._endian}H", data, 18)[0]
        self._segments = self._parse_segments()

    @property
    def arch(self) -> str:
        if self._machine == _EM_AARCH64:
            return ARCH_ARM64
        if self._machine == _EM_ARM:
            return ARCH_ARM32
        return ARCH_UNKNOWN

    def _parse_segments(self) -> list[tuple[int, int, int, int, int, int]]:
        """(index, vaddr, offset, filesz, memsz, flags) for each PT_LOAD."""
        d, e = self._data, self._endian
        if self._is_64:
            phoff = struct.unpack_from(f"{e}Q", d, 32)[0]
            phentsize = struct.unpack_from(f"{e}H", d, 54)[0]
            phnum = struct.unpack_from(f"{e}H", d, 56)[0]
        else:
            phoff = struct.unpack_from(f"{e}I", d, 28)[0]
            phentsize = struct.unpack_from(f"{e}H", d, 42)[0]
            phnum = struct.unpack_from(f"{e}H", d, 44)[0]

        out = []
        for index in range(phnum):
            at = phoff + index * phentsize
            if at + phentsize > len(d):
                break
            p_type = struct.unpack_from(f"{e}I", d, at)[0]
            if p_type != 1:  # PT_LOAD
                continue
            if self._is_64:
                flags = struct.unpack_from(f"{e}I", d, at + 4)[0]
                offset, vaddr = struct.unpack_from(f"{e}QQ", d, at + 8)
                filesz, memsz = struct.unpack_from(f"{e}QQ", d, at + 32)
            else:
                offset, vaddr = struct.unpack_from(f"{e}II", d, at + 4)
                filesz, memsz = struct.unpack_from(f"{e}II", d, at + 16)
                flags = struct.unpack_from(f"{e}I", d, at + 24)[0]
            out.append((index, vaddr, offset, filesz, memsz, flags))
        return out

    def map_rva(self, rva: int) -> RegionMapping:
        for index, vaddr, offset, filesz, memsz, flags in self._segments:
            if not (vaddr <= rva < vaddr + memsz):
                continue
            delta = rva - vaddr
            if delta >= filesz:
                raise ImageError(
                    f"RVA 0x{rva:X} maps into memory with no file backing "
                    f"(delta=0x{delta:X} >= filesz=0x{filesz:X})"
                )
            return RegionMapping(
                rva=rva,
                file_offset=offset + delta,
                region_name=f"LOAD#{index}",
                region_vaddr=vaddr,
                region_offset=offset,
                region_filesz=filesz,
                region_memsz=memsz,
                is_executable=bool(flags & _PF_X),
            )
        raise ImageError(f"RVA 0x{rva:X} is not covered by any loadable segment")


class MachOImage(Image):
    """Mach-O, mapped by section -- see the module docstring for why."""

    format = FORMAT_MACHO

    def __init__(self, path: str, data: bytes) -> None:
        super().__init__(path, data)
        magic = struct.unpack_from("<I", data, 0)[0] if len(data) >= 4 else 0
        if magic in _FAT_MAGICS:
            raise ImageError(
                f"{path} is a fat/universal Mach-O. Extract the arm64 slice first "
                f"(lipo -thin arm64 <file> -output <file>.arm64)."
            )
        if magic not in (_MH_MAGIC_64, _MH_MAGIC_32):
            raise ImageError(f"Not a Mach-O file: {path}")
        self._is_64 = magic == _MH_MAGIC_64
        self._cputype = struct.unpack_from("<i", data, 4)[0]
        self._sections = self._parse_sections()

    @property
    def arch(self) -> str:
        if self._cputype == _CPU_TYPE_ARM64:
            return ARCH_ARM64
        if self._cputype == _CPU_TYPE_ARM:
            return ARCH_ARM32
        return ARCH_UNKNOWN

    def _parse_sections(self) -> list[tuple[str, int, int, int, int, bool]]:
        """(name, addr, size, offset, section_flags, executable) for each section.

        Segments themselves are deliberately NOT recorded: mapping by segment is
        exactly the bug this class exists to avoid.
        """
        d = self._data
        ncmds = struct.unpack_from("<I", d, 16)[0]
        at = 32 if self._is_64 else 28
        out: list[tuple[str, int, int, int, int, bool]] = []

        for _ in range(ncmds):
            if at + 8 > len(d):
                break
            cmd, cmdsize = struct.unpack_from("<II", d, at)
            if cmdsize == 0:
                break
            want = _LC_SEGMENT_64 if self._is_64 else _LC_SEGMENT
            if cmd == want:
                if self._is_64:
                    initprot = struct.unpack_from("<i", d, at + 60)[0]
                    nsects = struct.unpack_from("<I", d, at + 64)[0]
                    sec_at = at + 72
                    sec_size = 80
                else:
                    initprot = struct.unpack_from("<i", d, at + 44)[0]
                    nsects = struct.unpack_from("<I", d, at + 48)[0]
                    sec_at = at + 56
                    sec_size = 68
                seg_exec = bool(initprot & _VM_PROT_EXECUTE)
                for _s in range(nsects):
                    if sec_at + sec_size > len(d):
                        break
                    sectname = d[sec_at:sec_at + 16].split(b"\0")[0].decode("utf-8", "replace")
                    segname = d[sec_at + 16:sec_at + 32].split(b"\0")[0].decode("utf-8", "replace")
                    # section_64: addr@32 size@40 offset@48 align@52 reloff@56
                    #             nreloc@60 flags@64  (size 80)
                    # section:    addr@32 size@36 offset@40 align@44 reloff@48
                    #             nreloc@52 flags@56  (size 68)
                    if self._is_64:
                        addr, size = struct.unpack_from("<QQ", d, sec_at + 32)
                        offset = struct.unpack_from("<I", d, sec_at + 48)[0]
                        flags = struct.unpack_from("<I", d, sec_at + 64)[0]
                    else:
                        addr, size = struct.unpack_from("<II", d, sec_at + 32)
                        offset = struct.unpack_from("<I", d, sec_at + 40)[0]
                        flags = struct.unpack_from("<I", d, sec_at + 56)[0]
                    executable = seg_exec or bool(
                        flags & (_S_ATTR_PURE_INSTRUCTIONS | _S_ATTR_SOME_INSTRUCTIONS)
                    )
                    out.append((f"{segname},{sectname}", addr, size, offset, flags, executable))
                    sec_at += sec_size
            at += cmdsize
        return out

    def map_rva(self, rva: int) -> RegionMapping:
        for name, addr, size, offset, flags, executable in self._sections:
            if not (addr <= rva < addr + size):
                continue
            if (flags & _SECTION_TYPE_MASK) in _ZEROFILL_TYPES:
                raise ImageError(
                    f"RVA 0x{rva:X} lands in {name}, which occupies memory but "
                    f"has no file backing"
                )
            return RegionMapping(
                rva=rva,
                file_offset=offset + (rva - addr),
                region_name=name,
                region_vaddr=addr,
                region_offset=offset,
                region_filesz=size,
                region_memsz=size,
                is_executable=executable,
            )
        # Deliberately an error, not a best-effort segment fallback. An address
        # inside a segment but outside every section is exactly the case that
        # would otherwise yield a plausible-looking wrong answer.
        raise ImageError(f"RVA 0x{rva:X} is not covered by any section")


def sniff_format(data: bytes) -> str | None:
    """Identify a binary image by magic. None if it is neither ELF nor Mach-O."""
    if data[:4] == b"\x7fELF":
        return FORMAT_ELF
    if len(data) >= 4:
        magic = struct.unpack_from("<I", data, 0)[0]
        if magic in (_MH_MAGIC_64, _MH_MAGIC_32) or magic in _FAT_MAGICS:
            return FORMAT_MACHO
    return None


_CACHE: dict[tuple[str, int, int], Image] = {}


def open_image(path: str) -> Image:
    """Open a binary image, dispatching on magic. Parsed images are cached."""
    try:
        stat = os.stat(path)
        key = (os.path.abspath(path), stat.st_mtime_ns, stat.st_size)
    except OSError as exc:
        raise ImageError(f"Cannot open {path}: {exc}") from exc
    cached = _CACHE.get(key)
    if cached is not None:
        return cached

    with open(path, "rb") as f:
        data = f.read()
    fmt = sniff_format(data)
    if fmt == FORMAT_ELF:
        image: Image = ElfImage(path, data)
    elif fmt == FORMAT_MACHO:
        image = MachOImage(path, data)
    else:
        raise ImageError(f"{path} is neither an ELF nor a Mach-O binary")

    _CACHE[key] = image
    return image


def map_rva_to_file_offset(binary_path: str, rva: int) -> RegionMapping:
    """Map a virtual RVA to a file offset in a binary image."""
    return open_image(binary_path).map_rva(rva)


def read_rva_bytes(binary_path: str, rva: int, size: int) -> tuple[RegionMapping, bytes]:
    """Read `size` bytes at `rva` from a binary image."""
    return open_image(binary_path).read_rva(rva, size)


def read_u64_at_rva(binary_path: str, rva: int) -> tuple[RegionMapping, int]:
    """Read a little-endian uint64 at an RVA."""
    mapping, data = read_rva_bytes(binary_path, rva, 8)
    return mapping, struct.unpack("<Q", data)[0]


def image_arch(binary_path: str) -> str:
    """Architecture of a binary image: 'arm64', 'arm32', or 'unknown'."""
    try:
        return open_image(binary_path).arch
    except ImageError:
        return ARCH_UNKNOWN


def format_mapping(mapping: RegionMapping) -> str:
    """Human-readable mapping description. Read by agents -- keep it neutral."""
    exec_flag = "executable" if mapping.is_executable else "non-executable"
    return (
        f"RVA 0x{mapping.rva:08X} -> file offset 0x{mapping.file_offset:X} "
        f"({mapping.region_name}, vaddr=0x{mapping.region_vaddr:X}, "
        f"offset=0x{mapping.region_offset:X}, size=0x{mapping.region_filesz:X}, "
        f"vmsize=0x{mapping.region_memsz:X}, {exec_flag})"
    )
