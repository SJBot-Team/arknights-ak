# -*- coding: utf-8 -*-
"""Extract printable ASCII/UTF-8 string runs from a .pyc / marshalled blob."""
import sys, re, io, os

def strings(blob, minlen=4):
    out = []
    for m in re.finditer(rb'[\x20-\x7e]{%d,}' % minlen, blob):
        out.append(m.group().decode('ascii'))
    # also UTF-8 CJK runs
    for m in re.finditer(rb'(?:[\xe4-\xe9][\x80-\xbf]{2}){%d,}' % 2, blob):
        try:
            out.append(m.group().decode('utf-8'))
        except Exception:
            pass
    return out

if __name__ == '__main__':
    src = sys.argv[1]
    dst = sys.argv[2]
    blob = open(src, 'rb').read()
    with io.open(dst, 'w', encoding='utf-8') as f:
        for s in strings(blob):
            f.write(s + '\n')
    print('wrote', dst, len(blob))
