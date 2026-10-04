# -*- coding: utf-8 -*-
"""t200g_strscan.py — 从 prts+ 的 3.9 pyc 里提取可读字符串常量（启发式）。

只输出"看起来像常量表内容"的 4 字节长度前缀串，避免把二进制误当整数打印。
"""
import sys


def scan(path):
    d = open(path, 'rb').read()
    n = len(d)
    out = []
    for i in range(16, n - 5):
        c = d[i]
        if c not in (0x73, 0x75, 0x7A):
            continue
        ln = int.from_bytes(d[i + 1:i + 5], 'little')
        if not (1 <= ln <= 4096) or i + 5 + ln > n:
            continue
        raw = d[i + 5:i + 5 + ln]
        try:
            s = raw.decode('utf-8')
        except UnicodeDecodeError:
            continue
        if not all(ch.isprintable() or ch in '\n\r\t' for ch in s):
            continue
        # 过滤纯数字/纯符号噪声（长度前缀常巧合）
        if not any(ch.isalpha() for ch in s):
            continue
        out.append(s)
    return out


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    seen = set()
    for p in sys.argv[1:]:
        print(f'===== {p}')
        for s in scan(p):
            if s in seen:
                continue
            seen.add(s)
            print(repr(s))
