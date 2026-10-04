"""Lua game-logic extraction for xLua IL2CPP games.

For this title the gameplay is written in Lua (xLua), not C#. The Lua ships as
encrypted, packed AssetBundles; Assembly-CSharp is mostly the engine/binding
layer. This module recovers the Lua source end to end:

    AssetBundle (TextAsset blob)
      -> XOR-decrypt with Crypt.key            [Crypt.CryptBytesParallel]
      -> LuaFilePack container -> {name: chunk} [LuaFilePack.Unpack]
      -> normalize xLua Lua 5.3 header          [for a stock decompiler]
      -> unluac -> readable Lua source

The decryption key and container layout below are GAME-SPECIFIC data that were
reversed from Assembly-CSharp using the `re` tools (RVAs cited inline). For a
different xLua game, re-reverse its Crypt/loader/pack classes and swap these
constants -- the mechanism (Addressables TextAsset -> XOR -> custom pack ->
Lua 5.x bytecode) is the reusable part.

Reversed from (v3.91.0, ARM32):
  - Crypt.key                @ Crypt.cs (const string)
  - Crypt.CryptBytesParallel @ 0x94CD14  (NativeArray parallel-for XOR)
  - Crypt.CryptBytesJob.Execute @ 0x953EC4  (array[i] ^= keys[i % len])
  - LuaFilePack.Unpack       @ 0x94CDEC  (int32 count; then per entry:
                                           int16 nameLen, name, int32 dataLen, chunk)
  - LuaLoader.LoadMainLayersAsync @ 0x94C6B4 (load -> CryptBytesParallel -> Unpack)
"""

from __future__ import annotations

import io
import os
import re
import struct
import subprocess
import zipfile
from dataclasses import dataclass

from . import config

# ── Per-game decode parameters (read from revenant.toml [lua]) ────────────────
#
# These are reversed per game with the C# `re` tools (find the Lua loader: the
# XOR key is usually a const, the container is its pack/unpack pair). Configure
# them in the project's revenant.toml, e.g.:
#
#   [lua]
#   xor_key   = "...const key from the Crypt class..."
#   container = "luafilepack"   # or "raw" (one Lua chunk per TextAsset)
#   size_t    = 4               # xLua Lua 5.3 quirk; stock Lua 5.3 = 8
#
_LUA_MAGIC = b"\x1bLua"   # Lua signature prefix (a version byte follows)


def lua_cfg() -> dict:
    return config.project_config().get("lua", {})


def crypt_key() -> bytes:
    """Repeating-XOR key for the Lua blobs, from revenant.toml [lua].xor_key."""
    k = lua_cfg().get("xor_key", "")
    if not k:
        raise ValueError(
            "Lua xor_key not configured. Reverse the game's Lua loader / Crypt "
            "class with the re tools, then set [lua].xor_key in revenant.toml."
        )
    return k.encode("utf-8") if isinstance(k, str) else bytes(k)


# Set only while `_report_size_t_suspicion` tries the other value; it exists so
# that trial does not have to rewrite the project's revenant.toml to ask a
# question about it.
_LUA_CFG_OVERRIDE: dict = {}


def _size_t() -> int:
    if "size_t" in _LUA_CFG_OVERRIDE:
        return int(_LUA_CFG_OVERRIDE["size_t"])
    return int(lua_cfg().get("size_t", 8))   # stock Lua 5.3 = 8; some xLua builds = 4


def _container() -> str:
    return str(lua_cfg().get("container", "luafilepack")).lower()


def is_lua_bundle_entry(name: str) -> bool:
    """Heuristic: an APK entry that is an AssetBundle holding packed Lua."""
    low = name.lower()
    return low.endswith(".bundle") and "lua" in low


# ── Decrypt + unpack ─────────────────────────────────────────────────────────

def decrypt(data: bytes, key: bytes | None = None) -> bytes:
    """Repeating-key XOR (the game's whole-blob cipher; symmetric)."""
    key = key if key is not None else crypt_key()
    kl = len(key)
    return bytes(b ^ key[i % kl] for i, b in enumerate(data))


def unpack(packfile: bytes) -> dict[str, bytes]:
    """Parse a decrypted container blob into {script_name: lua_bytecode}.

    "luafilepack" layout (little-endian): int32 count, then count x
    (int16 nameLen, name, int32 dataLen, chunk).
    """
    out: dict[str, bytes] = {}
    o = 0
    (count,) = struct.unpack_from("<i", packfile, o)
    o += 4
    for _ in range(count):
        (nlen,) = struct.unpack_from("<h", packfile, o)
        o += 2
        name = packfile[o:o + nlen].decode("utf-8", "replace")
        o += nlen
        (dlen,) = struct.unpack_from("<i", packfile, o)
        o += 4
        out[name] = packfile[o:o + dlen]
        o += dlen
    return out


def _bundle_text_assets(data: bytes) -> list[tuple[str, bytes]]:
    """Return (m_Name, raw m_Script bytes) for every TextAsset in a bundle."""
    import UnityPy
    env = UnityPy.load(io.BytesIO(data))
    blobs: list[tuple[str, bytes]] = []
    for obj in env.objects:
        if obj.type.name != "TextAsset":
            continue
        d = obj.read()
        s = d.m_Script
        raw = s.encode("utf-8", "surrogateescape") if isinstance(s, str) else bytes(s)
        blobs.append((getattr(d, "m_Name", "") or "TextAsset", raw))
    return blobs


def extract_scripts(apk_path: str = "") -> dict[str, bytes]:
    """Extract every Lua chunk from every Lua bundle in the APK.

    Returns {script_name: lua_bytecode}. Names are the original dotted module
    paths (e.g. "Board.Model.Base.Matrix").
    """
    if not apk_path:
        apk_path = _base_apk()
    container = _container()
    scripts: dict[str, bytes] = {}
    with zipfile.ZipFile(apk_path) as zf:
        members = [n for n in zf.namelist() if is_lua_bundle_entry(n)]
        for member in sorted(members):
            data = zf.read(member)
            for ta_name, blob in _bundle_text_assets(data):
                dec = decrypt(blob)
                if not dec[:4]:
                    continue
                if container == "raw":
                    # One Lua chunk per TextAsset (no pack container).
                    if dec[:4] == _LUA_MAGIC:
                        scripts[ta_name] = dec
                    continue
                try:
                    chunks = unpack(dec)
                except (struct.error, ValueError):
                    continue
                # Sanity: a real Lua pack is mostly Lua chunks.
                if sum(1 for v in chunks.values() if v[:4] == _LUA_MAGIC) < max(1, len(chunks) // 2):
                    continue
                scripts.update(chunks)
    return scripts


# ── Decompilation (unluac on a normalized header) ────────────────────────────

def normalize_luac(chunk: bytes) -> bytes:
    """Rewrite an xLua Lua 5.3 header to the stock layout a decompiler expects.

    Some xLua builds set the header `format` byte to 1 and omit the `size_t`
    size field (writing int/Instruction/Integer/Number = 04 04 08 08). Stock
    Lua 5.3.x wants format 0 and int/size_t/Instruction/Integer/Number. The
    inserted size_t comes from [lua].size_t (xLua = 4: long-string lengths are
    32-bit; inserting 8 desyncs any chunk with a string >254 bytes). The body
    is otherwise standard Lua 5.3 bytecode, so only the header needs fixing.
    Returns the chunk unchanged when it isn't a non-stock Lua 5.3 header.
    """
    if chunk[:4] != _LUA_MAGIC or chunk[4] != 0x53:
        return chunk                  # not Lua 5.3; nothing to normalize
    if chunk[5] == 0x00:
        return chunk                  # already stock
    head = bytearray(chunk[:12])      # sig(4) ver(1) format(1) LUAC_DATA(6)
    head[5] = 0x00                    # format -> 0
    sizes = chunk[12:16]              # int, Instruction, Integer, Number
    fixed = bytes([sizes[0], _size_t() & 0xFF, sizes[1], sizes[2], sizes[3]])
    return bytes(head) + fixed + chunk[16:]


def unluac_jar() -> str:
    """Path to the bundled Lua decompiler (override with $REVENANT_UNLUAC)."""
    env = os.environ.get("REVENANT_UNLUAC")
    if env:
        return env
    import importlib.resources as resources
    return str(resources.files("revenant").joinpath("vendor", "unluac.jar"))


def have_decompiler() -> bool:
    if not os.path.exists(unluac_jar()):
        return False
    try:
        subprocess.run(["java", "-version"], capture_output=True, timeout=15)
        return True
    except (OSError, subprocess.SubprocessError):
        return False


_LUAJIT_MAGIC = b"\x1bLJ"   # LuaJIT bytecode (a version byte follows)


def ljd2_binary() -> str:
    """Path to a luajit-decompiler-v2 `ljd2` binary ($REVENANT_LJD2), or ""."""
    return os.environ.get("REVENANT_LJD2", "")


def decompile_luajit(chunk: bytes, timeout: int = 120) -> tuple[bool, str]:
    """Decompile one LuaJIT chunk via ljd2. Returns (ok, text).

    unluac cannot read LuaJIT bytecode (`\\x1bLJ`, a different container from
    stock Lua). luajit-decompiler-v2 can; it is not vendored (upstream is
    Windows-only and the port is a compiled binary), so point $REVENANT_LJD2 at
    a build. docs/playbooks has the macOS build recipe.
    """
    ljd2 = ljd2_binary()
    if not ljd2:
        return False, ("LuaJIT bytecode (\\x1bLJ): unluac cannot read it. Build "
                       "luajit-decompiler-v2 (see docs/playbooks) and set "
                       "$REVENANT_LJD2 to the ljd2 binary.")
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        src = os.path.join(tmp, "chunk.luajit")
        out = os.path.join(tmp, "out")
        os.makedirs(out, exist_ok=True)
        with open(src, "wb") as f:
            f.write(chunk)
        try:
            r = subprocess.run([ljd2, src, "-f", "-s", "-o", out],
                               capture_output=True, timeout=timeout)
        except (OSError, subprocess.SubprocessError) as exc:
            return False, f"ljd2 failed: {exc}"
        produced = [os.path.join(dp, fn) for dp, _d, fs in os.walk(out) for fn in fs]
        if r.returncode == 0 and produced:
            with open(produced[0], encoding="utf-8", errors="replace") as f:
                return True, f.read()
        return False, (r.stderr or b"").decode("utf-8", "replace").strip() or "ljd2 produced nothing"


def decompile(chunk: bytes, timeout: int = 60) -> tuple[bool, str]:
    """Decompile one Lua chunk to source. Returns (ok, text).

    Routes LuaJIT bytecode to ljd2 and stock Lua 5.3 to unluac -- the two ship
    different containers, and the family is read off the magic.
    """
    if chunk[:3] == _LUAJIT_MAGIC:
        return decompile_luajit(chunk, timeout=max(timeout, 120))
    if not os.path.exists(unluac_jar()):
        return False, "unluac.jar not vendored at tools/vendor/unluac.jar"
    norm = normalize_luac(chunk)
    import tempfile
    with tempfile.NamedTemporaryFile(suffix=".luac", delete=False) as tf:
        tf.write(norm)
        path = tf.name
    try:
        r = subprocess.run(
            ["java", "-jar", unluac_jar(), path],
            capture_output=True, timeout=timeout,
        )
        if r.returncode == 0:
            # exit 0 with empty output == a valid (near-)empty module.
            return True, r.stdout.decode("utf-8", "replace") or "-- (empty module)\n"
        return False, (r.stderr or b"").decode("utf-8", "replace").strip() or "decompile failed"
    except subprocess.TimeoutExpired:
        return False, "decompile timed out"
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass


def chunk_strings(chunk: bytes, min_len: int = 4) -> list[str]:
    """Dependency-free fallback: printable strings embedded in a chunk
    (Lua constants -> identifiers, messages, field names)."""
    out, cur = [], bytearray()
    for b in chunk:
        if 0x20 <= b < 0x7F:
            cur.append(b)
        else:
            if len(cur) >= min_len:
                out.append(cur.decode("ascii"))
            cur = bytearray()
    if len(cur) >= min_len:
        out.append(cur.decode("ascii"))
    return out


# ── Extraction to a browsable tree ───────────────────────────────────────────

def _name_to_path(name: str) -> str:
    """Dotted module name -> relative file path (Board.Model.X -> Board/Model/X)."""
    safe = re.sub(r"[^\w.\-/]", "_", name)
    return safe.replace(".", os.sep) + ".lua"


@dataclass
class ExtractReport:
    total: int = 0                 # Lua chunks found
    decompiled: int = 0
    bytecode_only: int = 0
    out_dir: str = ""


def _workers() -> int:
    """Default decompiler concurrency. Each call is its own JVM, so the
    bottleneck is process startup rather than the CPU doing the work."""
    return min(16, (os.cpu_count() or 4))


def lua_out_dir(version: str = "") -> str:
    return os.path.join(config.workspace_root(), "lua", version or config.detect_version())


def _write_one(item, out_dir: str, version: str, can_decompile: bool,
               keep_bytecode: bool) -> tuple[bool, str]:
    """Decompile/emit one script named by a dotted module path."""
    name, chunk = item
    return _write_chunk(chunk, os.path.join(out_dir, _name_to_path(name)),
                        name, version, can_decompile, keep_bytecode)


def _write_chunk(chunk: bytes, dst: str, name: str, version: str,
                 can_decompile: bool, keep_bytecode: bool) -> tuple[bool, str]:
    """Decompile/emit one chunk to `dst`; `(wrote real source, why not)`.

    The destination is the caller's, because the two sources name their output
    differently and only one of them may say so. A package pack carries dotted
    module names and `_name_to_path` turns them into directories; a pulled
    directory already *is* a path, and routing it through dots and back is
    lossy -- `a/b.lua` and `a.b.lua` collided, and the report counted two while
    one file survived.

    The reason comes back rather than being thrown away, because the caller
    that wants to report it would otherwise decompile the chunk a second time
    to ask -- and on 3,608 files that is a second JVM per file.
    """
    os.makedirs(os.path.dirname(dst) or ".", exist_ok=True)
    wrote_src, why = False, ""
    if can_decompile:
        ok, text = decompile(chunk)
        why = "" if ok else text
        if ok:
            with open(dst, "w", encoding="utf-8") as f:
                f.write(f"-- decompiled from xLua Lua 5.3 bytecode: {name}\n")
                f.write(f"-- source: {version} addressables lua pack\n\n{text}")
            wrote_src = True
    if not wrote_src:
        with open(dst, "w", encoding="utf-8") as f:
            f.write(f"-- NOT decompiled ({name}); embedded string constants only.\n")
            f.write("-- Vendor tools/vendor/unluac.jar + a JRE and re-run lua-extract.\n\n")
            for s in chunk_strings(chunk):
                f.write(f"-- {s}\n")
    if keep_bytecode:
        with open(dst[:-4] + ".luac", "wb") as f:
            f.write(chunk)
    return wrote_src, why


def extract_to_tree(version: str = "", decompile_src: bool = True,
                    keep_bytecode: bool = False, verbose: bool = False,
                    workers: int = 0) -> ExtractReport:
    """Extract + decompile every Lua script into lua/<version>/<path>.lua.

    Decompilation is parallelized (each unluac call is a separate JVM); default
    worker count scales with the CPU since the bottleneck is JVM startup.
    """
    import concurrent.futures as cf
    version = version or config.detect_version()
    out_dir = lua_out_dir(version)
    scripts = extract_scripts()
    rep = ExtractReport(total=len(scripts), out_dir=out_dir)
    can_decompile = decompile_src and have_decompiler()
    items = sorted(scripts.items())
    workers = workers or _workers()
    if not can_decompile or workers <= 1:
        for it in items:
            ok, _why = _write_one(it, out_dir, version, can_decompile, keep_bytecode)
            rep.decompiled += ok
            rep.bytecode_only += (not ok)
            if verbose:
                print(f"  {it[0]}")
        return rep
    with cf.ThreadPoolExecutor(max_workers=workers) as ex:
        futs = {ex.submit(_write_one, it, out_dir, version, True, keep_bytecode): it[0]
                for it in items}
        done = 0
        for fut in cf.as_completed(futs):
            ok, _why = fut.result()
            rep.decompiled += ok
            rep.bytecode_only += (not ok)
            done += 1
            if verbose and done % 200 == 0:
                print(f"  {done}/{rep.total} ...")
    build_lua_index(version)          # refresh the grep/xref/bridge index
    if can_decompile and rep.bytecode_only:
        _report_size_t_suspicion(scripts, rep)
    return rep


def _report_size_t_suspicion(scripts: dict, rep: "ExtractReport") -> None:
    """When chunks failed, say whether `[lua] size_t` is the reason.

    The header this normalizes *omits* the size_t field, so there is nothing in
    the file to compare a configured value against -- the only way to know it is
    wrong is that the parse desyncs, and a desynced parse fails as
    `BufferUnderflow` on some chunks and reads fine on the rest. The symptom is
    therefore "these few modules will not decompile", which reads as a property
    of those modules rather than of one number in `revenant.toml`.

    One title spent the day with three chunks unexplained and 1,584 fine; the
    value was 8 where the build wanted 4, and changing it took the count to
    1,587/1,587. So this does what a person would: try the other value on a
    handful of the failures and say whether it helps (#69).
    """
    import sys
    other = 4 if _size_t() == 8 else 8
    failed = [(name, blob) for name, blob in sorted(scripts.items())
              if blob[:4] == _LUA_MAGIC][: max(1, min(24, rep.bytecode_only))]
    if not failed:
        return
    # The override's own prior state, not the configured value: restoring the
    # latter leaves the override permanently set, which is a process-wide change
    # made by a diagnostic that was supposed to ask a question and leave.
    saved = _LUA_CFG_OVERRIDE.get("size_t")
    rescued = 0
    try:
        _LUA_CFG_OVERRIDE["size_t"] = other
        for _name, blob in failed:
            ok, _text = decompile(normalize_luac(blob))
            rescued += ok
    except Exception:
        return
    finally:
        if saved is None:
            _LUA_CFG_OVERRIDE.pop("size_t", None)
        else:
            _LUA_CFG_OVERRIDE["size_t"] = saved
    if not rescued:
        return
    print(
        f"revenant: {rep.bytecode_only} of {rep.total} chunks did not decompile, "
        f"and {rescued} of the {len(failed)} retried decompile cleanly with\n"
        f"          [lua] size_t = {other} instead of {_size_t()}. That is a "
        f"configuration mismatch, not a property of those modules:\n"
        f"          set `size_t = {other}` under [lua] in revenant.toml and "
        f"re-run `revenant lua-extract`.",
        file=sys.stderr,
    )


# ── a directory of Lua already on disk ──────────────────────────────────────
#
# `lua-extract` is a chain -- pull from the package, decrypt, unpack, decompile
# -- and its entry is welded to the package: `extract_scripts()` opens the APK.
# One title's 3,608 `.lua` came off a CDN and sit in a directory, so the last
# link of that chain had to be run by hand. The same disease `extract-scenes`
# had: the capability is here and the entry point knows one kind of input.
#
# Only the decompiling link. Decryption and unpacking are the package's
# problem; a file already on disk has been through both, and requiring
# `[lua] xor_key` for a plaintext tree would gate a command on a fact it does
# not use.


@dataclass
class DecompileReport:
    """What one directory yielded. Its own type, not `ExtractReport`.

    Three of these counts cannot occur on the package path at all -- a Lua pack
    holds Lua and nothing else -- and a shared record whose fields half the
    producers never set gives a reader no way to tell "zero" from "not
    measured".
    """
    out_dir: str = ""
    chunks: int = 0          # Lua bytecode found
    decompiled: int = 0
    bytecode_only: int = 0   # a chunk no decompiler read; strings written instead
    source_copied: int = 0   # already-plain `.lua`, copied through unchanged
    other: int = 0           # not Lua bytecode and not a `.lua` file
    unreadable: int = 0      # we could not open it -- our gap, not the file's
    collisions: tuple = ()   # inputs whose destination was already written
    why: tuple = ()          # distinct reasons a chunk did not decompile


def is_lua_chunk(data: bytes) -> bool:
    """Whether a blob is Lua bytecode, by magic -- stock 5.3 or LuaJIT.

    Never by extension: a CDN names files whatever it likes, and the same tree
    holds catalogues and hashes.
    """
    return data[:4] == _LUA_MAGIC or data[:3] == _LUAJIT_MAGIC


def decompile_tree(src_dir: str, out_dir: str = "", version: str = "",
                   keep_bytecode: bool = False, verbose: bool = False,
                   workers: int = 0) -> DecompileReport:
    """Decompile a directory of Lua already on disk into `out_dir`.

    The relative path is kept exactly, so a tree fetched from a CDN keeps the
    paths the CDN used -- `main.9f2a.lua` stays one file rather than becoming
    `main/9f2a.lua`. `out_dir` defaults to `lua/<version>/`, which is where
    `lua-list` / `lua-grep` / `lua-refs` look; pulling a tree and then not
    being able to search it is half an answer, which is also why plain `.lua`
    source is copied through rather than merely counted.

    Files are sorted into four buckets and every one of them is reported:
    bytecode, plain `.lua` source, anything else, and what we could not read.
    That last is kept apart on purpose -- an unreadable file is our gap, and
    filing it under "not Lua" reports it as the file's content.

    A directory that is not there raises: it is a different fact from a
    directory holding no Lua, and `os.walk` returns the same nothing for both.
    """
    import concurrent.futures as cf
    import shutil
    if not os.path.isdir(src_dir):
        raise FileNotFoundError(f"no such directory: {src_dir}")
    version = version or config.detect_version()
    out_dir = out_dir or lua_out_dir(version)
    rep = DecompileReport(out_dir=out_dir)
    why: list[str] = []
    chunks: list[tuple[str, bytes, str]] = []      # (label, data, destination)
    taken: dict[str, str] = {}                     # destination -> first input
    collisions: list[str] = []

    def claim(rel: str, dst: str) -> bool:
        """Whether `rel` gets `dst`, recording a second claimant rather than
        overwriting: two inputs landing on one path is a lost file, and a count
        that includes both is a number nothing on disk backs."""
        if dst in taken:
            collisions.append(f"{rel} -> {os.path.relpath(dst, out_dir)} "
                              f"(already written from {taken[dst]})")
            return False
        taken[dst] = rel
        return True

    for dirpath, dirnames, filenames in os.walk(src_dir):
        dirnames[:] = sorted(dirnames)
        for filename in sorted(filenames):
            path = os.path.join(dirpath, filename)
            rel = os.path.relpath(path, src_dir)
            try:
                with open(path, "rb") as f:
                    data = f.read()
            except OSError as exc:
                why.append(f"{rel}: {type(exc).__name__}: {exc}")
                rep.unreadable += 1
                continue
            if is_lua_chunk(data):
                dst = os.path.join(out_dir, os.path.splitext(rel)[0] + ".lua")
                if claim(rel, dst):
                    chunks.append((rel, data, dst))
                continue
            # Not bytecode. A `.lua` here is source somebody already decompiled
            # or shipped plain; it is copied so the query commands can see it.
            # The extension decides only whether to COPY -- never whether the
            # file is Lua, which is what the magic above answered.
            if rel.lower().endswith(".lua"):
                dst = os.path.join(out_dir, rel)
                if claim(rel, dst):
                    os.makedirs(os.path.dirname(dst) or ".", exist_ok=True)
                    shutil.copyfile(path, dst)
                    rep.source_copied += 1
                continue
            rep.other += 1

    rep.chunks = len(chunks)
    # Asked once, not once per file. Without either decompiler this would be
    # 3,608 doomed JVM launches, and the answer is the same every time.
    can_decompile = have_decompiler() or bool(ljd2_binary())
    if not can_decompile and chunks:
        why.append("no decompiler available: vendor unluac.jar with a JRE, "
                   "and/or set $REVENANT_LJD2 for LuaJIT bytecode")

    def one(item):
        rel, data, dst = item
        ok, reason = _write_chunk(data, dst, rel, version, can_decompile,
                                  keep_bytecode)
        if reason:
            why.append(reason)
        return ok

    if chunks:
        with cf.ThreadPoolExecutor(max_workers=max(1, workers or _workers())) as ex:
            for ok in ex.map(one, chunks):
                rep.decompiled += ok
                rep.bytecode_only += (not ok)
    if rep.decompiled or rep.source_copied:
        build_lua_index(version, root=out_dir)    # index what actually landed
    rep.collisions = tuple(collisions)
    rep.why = tuple(dict.fromkeys(why))
    if verbose:
        print(f"  {rep.decompiled}/{rep.chunks} decompiled into {out_dir}")
    return rep


# ── Read-only query surface (for the MCP server / CLI) ───────────────────────

def list_scripts(version: str = "", query: str = "", limit: int = 100) -> list[str]:
    """List extracted script module names, optionally filtered by substring.

    `limit <= 0` means every match, which is how a caller asks "how many are
    there really" -- needed to print `shown/total` rather than a count that
    silently is the limit (#69).
    """
    root = lua_out_dir(version)
    if not os.path.isdir(root):
        return []
    names = []
    q = query.lower()
    for dirpath, _dirs, files in os.walk(root):
        for fn in files:
            if not fn.endswith(".lua"):
                continue
            rel = os.path.relpath(os.path.join(dirpath, fn), root)
            mod = rel[:-4].replace(os.sep, ".")
            if not q or q in mod.lower():
                names.append(mod)
    names.sort()
    return names if limit <= 0 else names[:limit]


def get_source(name: str, version: str = "") -> str | None:
    """Return the decompiled source for a script module name (or None)."""
    root = lua_out_dir(version)
    rel = name.replace(".", os.sep) + ".lua"
    path = os.path.join(root, rel)
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        return f.read()


def status(version: str = "") -> dict:
    """Summary for re_status: is the Lua extracted, how much."""
    version = version or config.detect_version()
    root = lua_out_dir(version)
    n = 0
    if os.path.isdir(root):
        for _dp, _d, files in os.walk(root):
            n += sum(1 for f in files if f.endswith(".lua"))
    try:
        apk = _base_apk()
        with zipfile.ZipFile(apk) as zf:
            bundles = sum(1 for x in zf.namelist() if is_lua_bundle_entry(x))
    except Exception:
        bundles = 0
    return {
        "version": version, "out_dir": root, "extracted": n,
        "lua_bundles_in_apk": bundles, "decompiler": have_decompiler(),
    }


def _base_apk() -> str:
    from .assets import find_base_apk
    located = find_base_apk()
    if not located:
        raise FileNotFoundError(
            "No archive with a bundle tree found. For an xapk run `revenant extract-apks` "
            "first; an ipa is read directly and needs no extraction step."
        )
    return located[0]


# ── Static index over the decompiled Lua tree (grep / xref / bridge) ──────────

_REQUIRE_RE = re.compile(r"""require\s*\(?\s*["']([^"']+)["']""")
_DEFINE_RE = re.compile(r"^\s*(?:local\s+)?function\s+([A-Za-z_][\w.:]*)", re.MULTILINE)
_CS_USE_RE = re.compile(r"\bCS\.([A-Za-z_][\w.]*)")


def _index_path(version: str, root: str = "") -> str:
    return os.path.join(root or lua_out_dir(version), ".lua_index.json")


def build_lua_index(version: str = "", root: str = "") -> dict:
    """Scan a decompiled Lua tree into a static index and cache it beside it.

    Per module: requires / defines (function names) / cs_uses (CS.* types).
    Plus reverse maps: required_by, cs_type -> modules, def -> modules.

    `root` is the tree to index, defaulting to `lua/<version>/`. It has to be a
    parameter: `lua-decompile --out DIR` writes into DIR, and indexing the
    default tree instead both left DIR unsearchable and stamped an empty index
    into a directory nothing had written -- which is how a run artifact reached
    a commit.
    """
    import json
    version = version or config.detect_version()
    root = root or lua_out_dir(version)
    modules: dict[str, dict] = {}
    required_by: dict[str, list[str]] = {}
    cs_index: dict[str, list[str]] = {}
    def_index: dict[str, list[str]] = {}
    for dirpath, _dirs, files in os.walk(root):
        for fn in sorted(files):
            if not fn.endswith(".lua"):
                continue
            rel = os.path.relpath(os.path.join(dirpath, fn), root)
            mod = rel[:-4].replace(os.sep, ".")
            try:
                with open(os.path.join(dirpath, fn), "r", encoding="utf-8", errors="replace") as f:
                    text = f.read()
            except OSError:
                continue
            requires = sorted(set(_REQUIRE_RE.findall(text)))
            defines = sorted(set(_DEFINE_RE.findall(text)))
            cs_uses = sorted(set("CS." + m for m in _CS_USE_RE.findall(text)))
            modules[mod] = {"requires": requires, "defines": defines, "cs_uses": cs_uses}
            for r in requires:
                required_by.setdefault(r, []).append(mod)
            for c in cs_uses:
                cs_index.setdefault(c, []).append(mod)
            for d in defines:
                def_index.setdefault(d, []).append(mod)
    index = {
        "version": version, "module_count": len(modules), "modules": modules,
        "required_by": required_by, "cs_index": cs_index, "def_index": def_index,
    }
    try:
        os.makedirs(root, exist_ok=True)
        with open(_index_path(version, root), "w", encoding="utf-8") as f:
            json.dump(index, f)
    except OSError:
        pass
    return index


def load_lua_index(version: str = "", rebuild: bool = False) -> dict:
    """Load the cached Lua index, building it on first use."""
    import json
    version = version or config.detect_version()
    path = _index_path(version)
    if not rebuild and os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (OSError, ValueError):
            pass
    return build_lua_index(version)


def lua_grep(pattern: str, version: str = "", limit: int = 100,
             ignore_case: bool = True) -> str:
    """Regex search across the decompiled Lua tree -> module:line: text."""
    version = version or config.detect_version()
    root = lua_out_dir(version)
    if not os.path.isdir(root):
        return "Lua not extracted. Run: revenant lua-extract"
    try:
        rx = re.compile(pattern, re.IGNORECASE if ignore_case else 0)
    except re.error as exc:
        return f"Bad regex {pattern!r}: {exc}"
    hits: list[str] = []
    total = 0
    for dirpath, _dirs, files in os.walk(root):
        for fn in sorted(files):
            if not fn.endswith(".lua"):
                continue
            rel = os.path.relpath(os.path.join(dirpath, fn), root)
            mod = rel[:-4].replace(os.sep, ".")
            try:
                with open(os.path.join(dirpath, fn), "r", encoding="utf-8", errors="replace") as f:
                    for ln, line in enumerate(f, 1):
                        if rx.search(line):
                            total += 1
                            if len(hits) < limit:
                                hits.append(f"  {mod}:{ln}: {line.strip()}")
            except OSError:
                continue
    if not total:
        return f"No Lua lines match {pattern!r}."
    head = f"{min(limit, total)}/{total} Lua line(s) matching {pattern!r}:"
    return head + "\n" + "\n".join(hits)


def lua_refs(name: str, version: str = "") -> str:
    """Cross-references for a Lua module name or a function name."""
    version = version or config.detect_version()
    idx = load_lua_index(version)
    if not idx.get("modules"):
        return "Lua not extracted/indexed. Run: revenant lua-extract"
    mods = idx["modules"]
    if name in mods:
        m = mods[name]
        rb = sorted(idx.get("required_by", {}).get(name, []))
        out = [f"Lua module: {name}"]
        out.append(f"  requires ({len(m['requires'])}): " + (", ".join(m["requires"]) if m["requires"] else "(none)"))
        out.append(f"  required_by ({len(rb)}): " + (", ".join(rb) if rb else "(none)"))
        out.append(f"  defines ({len(m['defines'])}): " + (", ".join(m["defines"]) if m["defines"] else "(none)"))
        if m["cs_uses"]:
            out.append(f"  cs_uses ({len(m['cs_uses'])}): " + ", ".join(m["cs_uses"]))
        return "\n".join(out)
    # Treat as a function/symbol name.
    defs = idx.get("def_index", {}).get(name, [])
    out = [f"Lua symbol: {name}"]
    out.append(f"  defined in ({len(defs)}): " + (", ".join(sorted(defs)) if defs else "(none)"))
    out.append("  call sites: use re_lua_grep(\"" + re.escape(name) + "\") for usages.")
    if not defs:
        out.append("  (not a known module or top-level function; try re_lua_grep)")
    return "\n".join(out)
