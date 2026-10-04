# -*- coding: utf-8 -*-
"""t200g_realdis2.py — 用 3.11 真 `dis` 反汇编（手动拼 CodeType 的正确字段）。

pyc 是**别的版本**编的 ⇒ 不能 marshal.loads；这里自己造一个最小可用的 3.11 code 对象：
只喂 (co_code, (), ())，`dis` 会用 3.11 的 `_inline_cache_entries` 自走缓存 ⇒
若字节码也是 3.11，反汇编就完全正确；若不是，会立刻暴露（出现垃圾指令）。
"""
import dis
import importlib.util
import io
import sys
import types

sys.stdout.reconfigure(encoding='utf-8')
BASE = r'C:\Users\23922\Documents\ds_harness\ak\.tmp'
sys.path.insert(0, BASE)
import t200g_read as RD  # noqa: E402


def mk(code: bytes, name: str):
    # 3.11 CodeType 位置参数（17 项）：
    # argcount, posonlyargcount, kwonlyargcount, nlocals, stacksize, flags,
    # codestring, constants, names, varnames, filename, name, qualname,
    # firstlineno, linetable, exceptiontable, freevars, cellvars
    return types.CodeType(
        0, 0, 0, 0, 1, 0, code, (), (), (), '<x>', name, name, 1, b'', (), (), (),
    )


def collect(rec, out):
    out.append(rec)
    for c in rec.consts:
        if hasattr(c, 'co_code'):
            collect(c, out)
    return out


src, dst = sys.argv[1], sys.argv[2]
rec, off, ln = RD.load(src)
buf = io.StringIO()
for c in collect(rec, []):
    buf.write(f'\n===== {c.name} argcount={c.argcount} nlocals={c.nlocals} '
              f'co_code={len(c.co_code)}B\n')
    try:
        fn = types.FunctionType(mk(bytes(c.co_code), c.name), {}, c.name)
        dis.dis(fn, file=buf)
    except Exception as e:
        buf.write(f'  !! {type(e).__name__}: {e}\n')
open(dst, 'w', encoding='utf-8').write(buf.getvalue())
print('wrote', dst)
