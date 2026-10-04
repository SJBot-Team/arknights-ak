"""lz4ak 独立版 —— 明日方舟 LZ4AK 解压（算法源自 Ark-Unpacker，BSD-3，Harry Huang）"""
from typing import Union

import lz4.block

ByteString = Union[bytes, bytearray, memoryview]


def _read_extra_length(data: ByteString, cur_pos: int, max_pos: int) -> tuple[int, int]:
    l = 0
    while cur_pos < max_pos:
        b = data[cur_pos]
        l += b
        cur_pos += 1
        if b != 0xFF:
            break
    return l, cur_pos


def decompress_lz4ak(compressed_data: ByteString, uncompressed_size: int) -> bytes:
    """Decompress LZ4AK block (token 高低 4 位互换后按标准 LZ4 解压)。"""
    ip = 0
    op = 0
    fixed = bytearray(compressed_data)
    size = len(fixed)

    while ip < size:
        token = fixed[ip]
        literal_length = token & 0xF
        match_length = (token >> 4) & 0xF
        fixed[ip] = (literal_length << 4) | match_length
        ip += 1

        if literal_length == 0xF:
            l, ip = _read_extra_length(fixed, ip, size)
            literal_length += l
        ip += literal_length
        op += literal_length
        if op >= uncompressed_size:
            break

        offset = (fixed[ip] << 8) | fixed[ip + 1]
        fixed[ip] = offset & 0xFF
        fixed[ip + 1] = (offset >> 8) & 0xFF
        ip += 2
        if match_length == 0xF:
            l, ip = _read_extra_length(fixed, ip, size)
            match_length += l
        match_length += 4
        op += match_length

    return lz4.block.decompress(bytes(fixed), uncompressed_size)
