#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""ak_hash.py —— 明日方舟局内状态哈希（HashCodeBuilder）的精确复刻

结论来源：`knowledge/04_数据对应与核验/34_随机数与确定性复刻.md` §七
  HashCodeBuilder  (dump.cs 103520, TypeDefIndex 1367)
    FLOAT_MULTIPLIER = 10000
    m_curHash : uint @ 0x10
    Append(int)    RVA 0x1AF8EC0  → m_curHash = (v + (h<<6) + (h>>2) + 0x9E3779B9) ^ h
    Append(float)  RVA 0x1AF9140  → 先 ×10000.0f（单精度）再取整，并入上式
    Append(string) RVA 0x1AF9020  → 逐字符 h=(h<<4)+c + g&0xF0000000 折叠，再并入上式
    GetCombinedHash() RVA 0x4EA8B0 → return m_curHash

注意：所有运算按 uint32 回绕；浮点先经 float32 乘 10000 再向零截断。
"""
import struct
import sys

sys.stdout.reconfigure(encoding="utf-8")

MASK32 = 0xFFFFFFFF
GOLDEN = 0x9E3779B9          # 2654435769 = 2^32 / φ
FLOAT_MULTIPLIER_F32 = 10000.0


def _f32(x: float) -> float:
    """按 IEEE-754 单精度舍入（模拟 C# 的 float 运算）。"""
    return struct.unpack("<f", struct.pack("<f", x))[0]


def _u32(x: int) -> int:
    return x & MASK32


class HashCodeBuilder:
    def __init__(self):
        self.m_curHash = 0

    def Clear(self):
        self.m_curHash = 0

    def GetCombinedHash(self) -> int:
        return self.m_curHash

    # --- 主混合公式 ---
    def _mix(self, value: int):
        h = self.m_curHash
        self.m_curHash = _u32((_u32(value) + _u32(h << 6) + (h >> 2) + GOLDEN) ^ h)

    def Append(self, value):
        """按 C# 重载分派。"""
        if isinstance(value, bool):
            self._mix(1 if value else 0)
        elif isinstance(value, int):
            if value < 0:
                self._mix(value & MASK32)          # int → uint
            else:
                self.AppendInt(value)
        elif isinstance(value, float):
            self.AppendFloat(value)
        elif isinstance(value, str):
            self.AppendString(value)
        elif isinstance(value, (tuple, list)) and len(value) in (2, 3):
            for comp in value:
                self.AppendFloat(comp)
        else:
            raise TypeError(f"不支持的哈希分量类型: {type(value)}")

    def AppendInt(self, value: int):
        self._mix(value)

    def AppendUInt(self, value: int):
        self._mix(value)

    def AppendLong(self, value: int):
        u = value & 0xFFFFFFFFFFFFFFFF
        self._mix(u & MASK32)
        self._mix((u >> 32) & MASK32)

    def AppendFloat(self, value: float):
        # mulss ×10000.0f → cvtss2sd → 取整 → 并入整数公式
        scaled = _f32(_f32(value) * _f32(FLOAT_MULTIPLIER_F32))
        self._mix(int(scaled))          # 向零截断

    def AppendString(self, s: str):
        h = 0
        for ch in s:
            h = _u32((h << 4) + ord(ch))
            g = h & 0xF0000000
            if g:
                h = _u32(h ^ (g >> 24))
                h = _u32(h & (~g & MASK32))
        self._mix(h)

    def AppendChar(self, c: str):
        self._mix(ord(c))

    def AppendByte(self, b: int):
        self._mix(b & 0xFF)


if __name__ == "__main__":
    b = HashCodeBuilder()
    b.AppendInt(12345)
    print(f"Append(int 12345)          -> 0x{b.GetCombinedHash():08X}")
    b.Clear()
    b.AppendFloat(1.5)
    print(f"Append(float 1.5)          -> 0x{b.GetCombinedHash():08X}  (= 15000 的量化为 15000)")
    b.Clear()
    b.AppendString("char_002_amiya")
    print(f'Append(str "char_002_amiya")-> 0x{b.GetCombinedHash():08X}')
    b.Clear()
    b.AppendFloat(3.14159)
    b.AppendInt(7)
    b.AppendString("tile")
    print(f"混合序列                    -> 0x{b.GetCombinedHash():08X}")
