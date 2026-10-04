# -*- coding: utf-8 -*-
"""t200g_dis2.py — 精炼版：只反汇编指定函数。"""
import importlib.util
import io
import sys

sys.stdout.reconfigure(encoding='utf-8')
BASE = r'C:\Users\23922\Documents\ds_harness\ak\.tmp'
sys.path.insert(0, BASE)

import t200g_dis9 as D  # noqa: E402


def collect(rec, out):
    out.append(rec)
    for c in rec.consts:
        if hasattr(c, 'co_code'):
            collect(c, out)
    return out


def dis_one(rec, f, path):
    pad = ''
    f.write(f'=== {path}  argcount={rec.argcount} nlocals={rec.nlocals} '
            f'co_code={len(rec.co_code)}B\n')
    f.write(f'  consts={[("<code %s>" % c.name) if hasattr(c, "co_code") else c for c in rec.consts]}\n')
    f.write(f'  names={list(rec.names)}\n')
    f.write(f'  varnames={list(rec.varnames)}\n')
    co = rec.co_code
    i = 0
    while i < len(co) - 1:
        op = co[i]
        nm = D.OPNAME.get(op, f'<op{op}>')
        if op in D.NOARG:
            f.write(f'{i:5d} {nm}\n')
            i += 2
            continue
        arg = co[i + 1] | (co[i + 2] << 8) if i + 2 < len(co) else co[i + 1]
        f.write(f'{i:5d} {nm:<22}{arg:6d}{D.arg_ann(rec, nm, arg)}\n')
        i += 2 + 2 * D.CACHE_ENTRIES.get(op, 0)


if __name__ == '__main__':
    src, want = sys.argv[1], sys.argv[2]
    dst = sys.argv[3]
    rec, off, ln = D.rd.load(src)
    allc = collect(rec, [])
    print('code objects:', [c.name for c in allc])
    hits = [c for c in allc if c.name == want]
    print('hits:', [(c.name, c.argcount, len(c.co_code)) for c in hits])
    with io.open(dst, 'w', encoding='utf-8') as f:
        for c in hits:
            dis_one(c, f, want)
    print('wrote', dst)
