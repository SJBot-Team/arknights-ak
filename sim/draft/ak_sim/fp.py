# -*- coding: utf-8 -*-
"""
fp.py — Q32.32 定点数（复刻游戏内 FP，见 knowledge/04/29、33）

依据（T1，反汇编确认）：
  - 局内数学为 Q32.32 定点：ONE = 2**32，64 位整数存储
  - 逻辑步长 = FP.FromFloat(0.03333330154418945f)（Unity TimeManager 实读）
  - 浮点→定点 = 单精度乘 2^32 后向零截断（mulss + cvttss2si）
  - 三角走查表 SinLut/TanLut/AcosLut（LUT_SIZE=205887），与 libm 不等
  - FastMul（op_Multiply, RVA 0x54E2200）舍入细节未最终核对（标 🟡）

本模块目标：给模拟器提供与游戏一致的定点运算原语。未复刻项以 TODO 标注，
以便后续用 dump.cs 反汇编结果替换。
"""
from __future__ import annotations

import math
import struct

ONE = 1 << 32
MASK64 = (1 << 64) - 1
SIGN64 = 1 << 63

# 逻辑步长（Unity TimeManager 实读值）
FIXED_DELTA_TIME_F32 = 0.03333330154418945
FPS = 30


def _f32(x: float) -> float:
    """按 IEEE-754 单精度舍入（模拟 C# float）。"""
    return struct.unpack('<f', struct.pack('<f', x))[0]


def from_float(x: float) -> int:
    """FP.FromFloat：单精度 × 2^32，向零截断。"""
    if x == 0:
        return 0
    x32 = _f32(x)
    v = x32 * ONE
    # cvttss2si 语义：向零截断
    return int(v) if v >= 0 else -int(-v)


def from_int(x: int) -> int:
    return x << 32


def to_float(v: int) -> float:
    """FP → float（用于输出/记录）。"""
    return v / ONE


def to_int(v: int) -> int:
    """FP → int（向零截断）。"""
    return int(v / ONE) if v >= 0 else -int(-v / ONE)


def _wrap64(v: int) -> int:
    return v & MASK64


def _as_signed(v: int) -> int:
    v &= MASK64
    return v - (1 << 64) if v & SIGN64 else v


def add(a: int, b: int) -> int:
    return _as_signed(a + b)


def sub(a: int, b: int) -> int:
    return _as_signed(a - b)


def mul(a: int, b: int) -> int:
    """Q32.32 乘法：(a*b) >> 32，带符号；低位截断（FastMul 近似）。

    TODO(🟡): FastMul 的部分积舍入方式待反汇编核对（knowledge/04/31 §2.3）。
    """
    p = _as_signed(a) * _as_signed(b)
    return _as_signed(p >> 32)


def div(a: int, b: int) -> int:
    """Q32.32 除法：(a<<32)/b，向零截断。"""
    if b == 0:
        raise ZeroDivisionError('FP division by zero')
    n = _as_signed(a) << 32
    q = abs(n) // abs(_as_signed(b))
    return _as_signed(q if (n >= 0) == (_as_signed(b) >= 0) else -q)


def mul_int(a: int, n: int) -> int:
    return _as_signed(_as_signed(a) * n)


# ---------------- 查表三角（近似复刻） ----------------
LUT_SIZE = 205887
_TWO_PI = 2 * math.pi
# 游戏查表格点 ≈ 2π/LUT_SIZE；此处用线性插值近似（🟡 精确表未取得）


def sin(v: int) -> int:
    return from_float(math.sin(to_float(v)))


def cos(v: int) -> int:
    return from_float(math.cos(to_float(v)))


def atan2(y: int, x: int) -> int:
    return from_float(math.atan2(to_float(y), to_float(x)))


def sqrt(v: int) -> int:
    f = to_float(v)
    if f <= 0:
        return 0
    return from_float(math.sqrt(f))


def length(x: int, y: int) -> int:
    f = math.hypot(to_float(x), to_float(y))
    return from_float(f)


# ---------------- 常用常量 ----------------
FRAME_TIME = from_float(FIXED_DELTA_TIME_F32)   # 一帧的 FP 时长
ZERO = 0
HALF = ONE >> 1
TWO = 2 << 32


def frames_to_fp(n_frames: int) -> int:
    """n 帧 → FP 时间（逐帧累加，避免浮点误差）。"""
    return _as_signed(FRAME_TIME * n_frames)


def fp_seconds_to_frames_ceil(seconds_fp: int) -> int:
    """秒(FP) → 帧数（向上取整；攻击间隔帧化规则 K-004）。"""
    return (seconds_fp + FRAME_TIME - 1) // FRAME_TIME


def fp_to_frames_floor(seconds_fp: int) -> int:
    return seconds_fp // FRAME_TIME


if __name__ == '__main__':
    import sys
    print('ONE =', ONE)
    v = from_float(1.5)
    print('from_float(1.5) =', v, 'to_float =', to_float(v))
    print('mul(1.5, 2.0) =', to_float(mul(from_float(1.5), from_float(2.0))))
    print('FRAME_TIME =', FRAME_TIME, 'to_float =', to_float(FRAME_TIME))
    print('1s in frames =', fp_to_frames_floor(from_int(1)))
