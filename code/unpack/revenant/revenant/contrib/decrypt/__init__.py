"""Decryptor machinery for packed titles (#32).

None of it is game-specific once the addresses are pulled out, which is the bar
(#50); that four packed titles in merge-games-re needed the same handful of
moves is how it was noticed, not why it qualifies:

- `find_dispatcher` locates a bytecode VM by the *shape* of its dispatch
  sequence, not its address (which changes every build).
- `SegmentedImage` maps an ELF's PT_LOAD segments the way an emulator needs,
  so the protector's own VM can be run under Unicorn instead of reimplemented.
- `decrypt_blocks` drives the protector's own block wrapper over a blob and
  collects the output, with the emulator injected -- the loop both packed
  titles wrote by hand under two docstrings saying the addresses differ and
  the routine does not.
- `write_protect_recipe` is the Frida script that finds an in-place decryptor
  by write-protecting its target and reading back the faulting PC.
- `wrap_pe` lays PE headers over a header-stripped .NET image so a decompiler
  can open it.
- `IFixPatch` walks an IFix hot-patch file (opcode map supplied per build).
- `xxtea` is the CenturyGame config-table transform and its `$CGF$` container
  header -- the upstream half of a chain whose downstream half (`pb-schema`,
  `pb-tags`) was absorbed in #32 and left the other half in two projects (#47).

Addresses, keys, jump tables and opcode maps are inputs, never baked in.
"""

from .findvm import Dispatcher, find_dispatcher
from .emulator import SegmentedImage
from .blocks import BlockResult, EmulatorContract, Wrapper, decrypt_blocks
from .frida import write_protect_recipe, reload_recipe
from .pe import wrap_pe
from .ifix import IFixPatch, MethodRef
from . import xxtea
from .xxtea import CGF_MAGIC, cgf_body

__all__ = [
    "Dispatcher", "find_dispatcher", "SegmentedImage",
    "BlockResult", "EmulatorContract", "Wrapper", "decrypt_blocks",
    "write_protect_recipe", "reload_recipe", "wrap_pe", "IFixPatch", "MethodRef",
    "xxtea", "CGF_MAGIC", "cgf_body",
]
