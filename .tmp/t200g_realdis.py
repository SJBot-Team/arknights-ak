# -*- coding: utf-8 -*-
"""t200g_realdis.py — 用真 Python 3.11 的 dis 反汇编 prts+ 的 code 对象。

用法：python t200g_realdis.py <pyc> <out.txt>
说明：先用自写反序列化器读出 CodeRec（因为 3.11 的 marshal.loads 读不了别的版本头），
再用 (co_code, (), ()) 造一个临时函数让 `dis` 自己走缓存表，从而**用官方表**判定布局版本。
"""
import importlib.util
import io
import sys
import types

sys.stdout.reconfigure(encoding='utf-8')
BASE = r'C:\Users\23922\Documents\ds_harness\ak\.tmp'
sys.path.insert(0, BASE)
import t200g_read as RD  # noqa: E402


def collect(rec, out):
    out.append(rec)
    for c in rec.consts:
        if hasattr(c, 'co_code'):
            collect(c, out)
    return out


def main(src, dst):
    rec, off, ln = RD.load(src)
    buf = io.StringIO()
    buf.write(f'src={src}\n')
    for c in collect(rec, []):
        buf.write(f'\n===== {c.name}  argcount={c.argcount} nlocals={c.nlocals} '
                  f'co_code={len(c.co_code)}B\n')
        code = bytes(c.co_code)
        try:
            fn = types.FunctionType(code, {}, c.name)
            buf.write(f'  -- dis（3.11 官方表，caches=True）--\n')
            buf.write(_dis_text(fn))
        except Exception as e:
            buf.write(f'  !! dis 失败: {type(e).__name__}: {e}\n')
    open(dst, 'w', encoding='utf-8').write(buf.getvalue())
    print('wrote', dst)


def _dis_text(fn):
    import dis as _d
    out = io.StringIO()
    _d.dis(fn, file=out)
    return out.getvalue()


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
