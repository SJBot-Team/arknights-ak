# -*- coding: utf-8 -*-
"""t200g_marshal.py — 从 prts+ 的 3.9 pyc 里粗提字符串/整数常量。

判据：pyc=16 字节头（magic+e3 00 00 00 / flags / mtime / size）。
3.9 marshal 串型：'s'(bytes,4字节长) 'u'(unicode,4字节长) 'z'(short ascii,4字节长)
'i'/'l'(4字节 int) 'g'(double) 'a'/'A'(float) 'g'。数组型后有 '0' 分隔。
"""
import sys, json

TAGS_STR = {0x73: 's', 0x75: 'u', 0x7a: 'z'}
TAGS_INT = {0x69: 'i', 0x6c: 'l'}


def scan(path, minlen=2):
    d = open(path, 'rb').read()
    n = len(d)
    i = 16
    out = []
    while i < n:
        c = d[i]
        if c in TAGS_STR:
            ln = int.from_bytes(d[i + 1:i + 5], 'little')
            if 0 < ln <= 4096 and i + 5 + ln <= n:
                raw = d[i + 5:i + 5 + ln]
                try:
                    s = raw.decode('utf-8')
                    if len(s) >= minlen and all(ch.isprintable() or ch in '\n\r\t' for ch in s):
                        out.append(('str', s))
                        i += 5 + ln
                        continue
                except UnicodeDecodeError:
                    pass
        elif c in TAGS_INT:
            v = int.from_bytes(d[i + 1:i + 5], 'little', signed=True)
            out.append(('int', v))
            i += 5
            continue
        elif c == 0x67:
            out.append(('float', None))
            i += 9
            continue
        elif c == 0x61 or c == 0x41:
            out.append(('float', None))
            i += 9
            continue
        i += 1
    return out


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    p = sys.argv[1]
    items = scan(p)
    seen = set()
    for kind, v in items:
        k = (kind, v)
        if k in seen:
            continue
        seen.add(k)
        if kind == 'str':
            print(f'{kind}\t{v}')
        elif kind == 'int' and abs(v) < 100000:
            print(f'{kind}\t{v}')
