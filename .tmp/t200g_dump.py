# -*- coding: utf-8 -*-
"""t200g_dump.py — 用 marshal9 的 Reader 完整倾倒 code 对象树（常量 + 名字）。

用法：python t200g_dump.py <pyc> <out.txt>
"""
import importlib.util
import io
import sys

sys.stdout.reconfigure(encoding='utf-8')
spec = importlib.util.spec_from_file_location(
    'm9', r'C:\Users\23922\Documents\ds_harness\ak\.tmp\marshal9.py')
m9 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m9)


def walk(rec, f, depth=0, path='<module>'):
    pad = '  ' * depth
    f.write(f'{pad}CODE {path} argcount={rec.argcount} flags={rec.flags:#x} '
            f'nlocals={rec.nlocals}\n')
    f.write(f'{pad}  names={list(rec.names)}\n')
    f.write(f'{pad}  varnames={list(rec.varnames)}\n')
    for c in rec.consts:
        if isinstance(c, m9.CodeRec):
            walk(c, f, depth + 1, f'{path}.{c.name}')
        else:
            f.write(f'{pad}  const {c!r}\n')


if __name__ == '__main__':
    src, dst = sys.argv[1], sys.argv[2]
    d = open(src, 'rb').read()
    rec = m9.Reader(d).r_object()
    with io.open(dst, 'w', encoding='utf-8') as f:
        f.write(f'src={src} len={len(d)}\n')
        walk(rec, f)
    print('wrote', dst)
