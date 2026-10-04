# -*- coding: utf-8 -*-
"""t200g_dis39.py — 用**真 Python 3.9** 的 dis 完整反汇编 prts+ 的 code 树。"""
import dis
import io
import sys

sys.path.insert(0, r'C:\Users\23922\Documents\ds_harness\ak\.tmp')
import t200g_read as RD  # noqa: E402


def collect(rec, out):
    out.append(rec)
    for c in rec.consts:
        if hasattr(c, 'co_code'):
            collect(c, out)
    return out


def main(src, dst, want=None):
    rec, off, ln = RD.load(src)
    buf = io.StringIO()
    for c in collect(rec, []):
        if want and c.name != want:
            continue
        buf.write(f'\n{"=" * 70}\n===== {c.name}  argcount={c.argcount} '
                  f'nlocals={c.nlocals} co_code={len(c.co_code)}B\n')
        buf.write(f'  consts={[("<code %s>" % x.name) if hasattr(x, "co_code") else x for x in c.consts]}\n')
        buf.write(f'  names={list(c.names)}\n')
        if c.varnames:
            buf.write(f'  varnames={list(c.varnames)}\n')
        d = io.StringIO()
        dis.dis(bytes(c.co_code), file=d)
        buf.write(d.getvalue())
    open(dst, 'w', encoding='utf-8').write(buf.getvalue())
    print('wrote', dst)


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else None)
