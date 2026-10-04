"""XXTEA (Corrected Block TEA) as CenturyGame titles ship it, plus the `$CGF$`
container header that wraps their config tables.

The transform holds no game fact, which is the bar (#50). Two titles (Hotel
Legacy, Tasty Travels) carried a byte-identical `xxtea.py` under `res/_tools/`,
and the chain that script starts -- decrypt `$CGF$`, rebuild the protobuf
schema, decode to JSON -- already had its downstream half in the harness
(`pb-schema`, `pb-tags`). Having the upstream half live in two project
directories and the downstream half here is what #47 calls half a chain inside
and half outside; this is the upstream half moving in.

What stays in the project: **the key**, the directory conventions, and the file
naming. Those are facts about a title. What moved: the transform itself and the
one shape judgement -- "does this blob announce itself as a `$CGF$` container".

The variant matters. This matches `CenturyGame.Core.Utilities.DwarfUtility`,
which is the canonical xxtea-dotnet arrangement:

    Decrypt(data, key) = ToByteArray(Decrypt(ToUInt32Array(data, False),
                                             ToUInt32Array(FixKey(key), False)), True)

so the plaintext length rides in the last word (`include_length` on the way
out, not on the way in), and a key shorter or longer than 16 bytes is padded or
truncated rather than rejected. Get either end wrong and decryption still
"works" -- it returns wrong bytes, or `None` from the length check.
"""

from __future__ import annotations

DELTA = 0x9E3779B9
M = 0xFFFFFFFF

# The five bytes a CenturyGame config table starts with, then two bytes the
# loader skips before the ciphertext. Recognising the container is a shape
# judgement (it holds for every table in both titles); the key that opens it is
# not, and is never baked in here.
CGF_MAGIC = b"$CGF$"
CGF_HEADER = len(CGF_MAGIC) + 2


def fix_key(key: bytes) -> bytes:
    """A 16-byte key: shorter keys are zero-padded, longer ones truncated."""
    if len(key) == 16:
        return key
    out = bytearray(16)
    out[: min(16, len(key))] = key[:16]
    return bytes(out)


def to_uint32_array(data: bytes, include_length: bool) -> list[int]:
    """Little-endian words, optionally with the byte length appended."""
    n = (len(data) + 3) // 4
    if include_length:
        arr = [0] * (n + 1)
        arr[n] = len(data)
    else:
        arr = [0] * n
    for i, b in enumerate(data):
        arr[i >> 2] |= b << ((i & 3) << 3)
    return arr


def to_byte_array(data: list[int], include_length: bool) -> bytes | None:
    """Words back to bytes. None when `include_length` and the length is absurd.

    That None is the only integrity signal XXTEA has: a wrong key produces a
    last word that does not agree with the block count, and the caller learns
    the decryption failed instead of receiving noise.
    """
    n = len(data) << 2
    if include_length:
        m = data[-1]
        n -= 4
        if m < n - 3 or m > n:
            return None
        n = m
    out = bytearray(n)
    for i in range(n):
        out[i] = (data[i >> 2] >> ((i & 3) << 3)) & 0xFF
    return bytes(out)


def _mx(sum_: int, y: int, z: int, p: int, e: int, k: list[int]) -> int:
    return ((((z >> 5) ^ ((y << 2) & M)) + ((y >> 3) ^ ((z << 4) & M))) & M) ^ (
        (((sum_ ^ y) & M) + ((k[(p & 3) ^ e] ^ z) & M)) & M
    )


def _decrypt_words(v: list[int], k: list[int]) -> list[int]:
    n = len(v) - 1
    if n < 1:
        return v
    y = v[0]
    q = 6 + 52 // (n + 1)
    sum_ = (q * DELTA) & M
    while sum_ != 0:
        e = (sum_ >> 2) & 3
        p = n
        while p > 0:
            z = v[p - 1]
            v[p] = y = (v[p] - _mx(sum_, y, z, p, e, k)) & M
            p -= 1
        z = v[n]
        v[0] = y = (v[0] - _mx(sum_, y, z, 0, e, k)) & M
        sum_ = (sum_ - DELTA) & M
    return v


def _encrypt_words(v: list[int], k: list[int]) -> list[int]:
    n = len(v) - 1
    if n < 1:
        return v
    z = v[n]
    sum_ = 0
    q = 6 + 52 // (n + 1)
    while q > 0:
        sum_ = (sum_ + DELTA) & M
        e = (sum_ >> 2) & 3
        for p in range(n):
            y = v[p + 1]
            v[p] = z = (v[p] + _mx(sum_, y, z, p, e, k)) & M
        y = v[0]
        v[n] = z = (v[n] + _mx(sum_, y, z, n, e, k)) & M
        q -= 1
    return v


def decrypt(data: bytes, key: bytes | str) -> bytes | None:
    """Plaintext, or None when the key does not fit the ciphertext."""
    if not data:
        return data
    if isinstance(key, str):
        key = key.encode("utf-8")
    return to_byte_array(
        _decrypt_words(to_uint32_array(data, False), to_uint32_array(fix_key(key), False)),
        True,
    )


def encrypt(data: bytes, key: bytes | str) -> bytes:
    """The inverse of `decrypt`. Here so the transform can be tested both ways."""
    if not data:
        return data
    if isinstance(key, str):
        key = key.encode("utf-8")
    return to_byte_array(
        _encrypt_words(to_uint32_array(data, True), to_uint32_array(fix_key(key), False)),
        False,
    )


def cgf_body(raw: bytes) -> bytes | None:
    """The ciphertext inside a `$CGF$` container, or None if it is not one.

    An empty body is a real case -- both titles ship tables that decrypt to
    nothing -- so this returns `b""` for those and None only for "not a
    container", which are different answers to different questions.
    """
    if not raw.startswith(CGF_MAGIC):
        return None
    return raw[CGF_HEADER:]
