"""Drive a protector's own block-decryption wrapper, one block at a time.

`SegmentedImage` maps the image the way the loader would and `find_dispatcher`
locates the VM by shape. What neither does is the part both packed titles
actually wrote by hand: set up the wrapper's arguments, run it over the blob
block by block, and collect the output. Two projects have a copy of that loop
and both docstrings say the same thing -- the addresses differ, the rest of the
routine does not.

**The emulator is injected**, the same handle `contrib.fetch` gives its HTTP
call. Four methods are used, with exactly these signatures -- which are
Unicorn's, so a `Uc` instance satisfies them as it is:

    mem_write(address, data)                    -> None
    mem_read(address, size)                     -> bytes
    reg_write(register, value)                  -> None
    emu_start(begin, until, timeout)            -> None

They are checked before the first block runs. A caller whose object is missing
one, or whose `emu_start` takes fewer arguments, gets that said plainly rather
than several thousand identical "block failed" lines -- our own contract error
reported as the data's problem is the mistake `lint` calls `no-index`.

Nothing is imported here, so a project without Unicorn installed is unaffected
and the loop is testable by injecting an executor that transforms bytes in
Python.

**What stays in the project**, because all of it is per build: the wrapper's
entry and return addresses, which registers carry which argument and in what
order, the scratch addresses, the block size, and the bytes that have to be in
memory first -- the program block, the key block, and the jump table, which is
usually blank in the file and has to be read once from a live process. All of
them are arguments; `preload` is where the bytes go.
`docs/playbooks/emulate-dont-reimplement.md` is the method; this is the loop
under it.

**Provenance.** The `(program, key, body, length)` argument layout and the
block-at-a-time shape are transcribed from the two projects' scripts, which ran
against real packages. The loop *here* has only been run against a synthetic
executor -- no packed image is in this repository.
"""

from __future__ import annotations

from dataclasses import dataclass

# The four methods and how many arguments each is called with. Checked up
# front rather than discovered on block 1 of several thousand.
CONTRACT = (("mem_write", 2), ("mem_read", 2), ("reg_write", 2), ("emu_start", 3))


@dataclass(frozen=True)
class Wrapper:
    """Where the block routine is and how it is called. Per build, so: input.

    `argv` names the registers carrying the arguments, in the wrapper's own
    order. The last two receive the block's address and its length; the ones
    before them receive `fixed` -- on the build this was written from, that is
    the program block and the key block.

    `out` is where the plaintext is read back from, which is usually `body`
    because these wrappers decrypt in place. A wrapper that writes somewhere
    else is why it is a separate field: reading back from `body` would hand
    back the ciphertext and nothing would say so.
    """
    entry: int              # where the routine starts
    ret: int                # where the emulator stops
    body: int               # scratch address a block is written to
    argv: tuple             # register names, in the wrapper's argument order
    out: int | None = None  # where to read the result; None means `body`

    @property
    def result_at(self) -> int:
        return self.body if self.out is None else self.out


@dataclass(frozen=True)
class BlockResult:
    """What came back, and what did not.

    `plaintext` is the blob with every block that ran without error replaced by
    what the wrapper left at `result_at`. A block that ran without error is not
    proof it was decrypted -- only that nothing raised and the expected number
    of bytes came back. Whether the output is plaintext is the reader's call,
    and the usual check is whether the result parses as what it should be.
    """
    plaintext: bytes
    blocks: int = 0
    failed: tuple = ()      # indices whose run raised; their bytes are unchanged
    notes: tuple = ()


class EmulatorContract(TypeError):
    """The injected object does not offer what this module calls."""


def check_emulator(emu) -> None:
    """Raise unless `emu` offers the four methods, before any block runs."""
    missing = [name for name, _n in CONTRACT if not callable(getattr(emu, name, None))]
    if missing:
        raise EmulatorContract(
            f"the emulator is missing {', '.join(missing)}; this module calls "
            + ", ".join(f"{name}({n} args)" for name, n in CONTRACT))


def decrypt_blocks(emu, blob: bytes, wrapper: Wrapper, *, block_size: int,
                   fixed: tuple = (), preload=(), timeout: int = 0) -> BlockResult:
    """Run `wrapper` over `blob` in `block_size` pieces; collect the output.

    `preload` is `{address: bytes}` written once before the first block -- the
    program block, the key block, the jump table. `timeout` is passed to
    `emu_start` as Unicorn takes it (microseconds; 0 means no limit). Pass one:
    a wrong entry address otherwise hangs on block 1 of several thousand, which
    is the least readable failure available.

    A block that raises is recorded and the rest still run. A 57 MB blob is
    thousands of blocks, and stopping at the first failure loses everything
    after it while leaving no way to tell one bad block from a wrong address.
    """
    if block_size <= 0:
        raise ValueError(f"block_size must be positive, not {block_size}")
    if isinstance(wrapper.argv, str):
        raise ValueError("argv is a sequence of register names, not a string; "
                         f"{wrapper.argv!r} would be read one character at a time")
    if len(wrapper.argv) != len(fixed) + 2:
        raise ValueError(
            f"{len(wrapper.argv)} register(s) in argv but {len(fixed) + 2} "
            f"argument(s) to pass ({len(fixed)} fixed, then the block's address "
            f"and length); a short argv leaves the wrapper reading whatever was "
            f"in the register")
    check_emulator(emu)
    for address, data in dict(preload).items():
        emu.mem_write(address, data)

    out = bytearray(blob)
    failed, notes = [], []
    count = 0
    for index, start in enumerate(range(0, len(blob), block_size)):
        block = blob[start:start + block_size]
        count += 1
        # At its real length, never padded to the block size: padding hands the
        # wrapper bytes the file does not have, and the extra output coming
        # back would look like content.
        emu.mem_write(wrapper.body, block)
        for name, value in zip(wrapper.argv, tuple(fixed) + (wrapper.body, len(block))):
            emu.reg_write(name, value)
        try:
            emu.emu_start(wrapper.entry, wrapper.ret, timeout)
        except (TypeError, AttributeError) as exc:
            # Not a bad block. The injected object does not do what this module
            # calls, and every remaining block would fail the same way -- so it
            # is raised once instead of filed thousands of times as data.
            raise EmulatorContract(
                f"emu_start(begin, until, timeout) did not work: {exc}") from exc
        except Exception as exc:            # noqa: BLE001 - report, don't stop
            failed.append(index)
            notes.append(f"block {index} at 0x{start:x}: "
                         f"{type(exc).__name__}: {exc}")
            continue
        got = emu.mem_read(wrapper.result_at, len(block))
        if len(got) != len(block):
            # Slice-assigning a short read into the bytearray would *shrink*
            # it, so every later block would land at the wrong offset and the
            # result would be quietly wrong from here on.
            failed.append(index)
            notes.append(f"block {index} at 0x{start:x}: read back "
                         f"{len(got)} byte(s), expected {len(block)}")
            continue
        out[start:start + len(block)] = got
    if failed:
        notes.append(f"{len(failed)} of {count} block(s) did not run; their "
                     f"bytes are unchanged")
    return BlockResult(plaintext=bytes(out), blocks=count,
                       failed=tuple(failed), notes=tuple(notes))
