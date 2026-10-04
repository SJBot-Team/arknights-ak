# -*- coding: utf-8 -*-
"""t200g_disbytes.py — 用 3.11 的 `dis._get_instructions_bytes` 直接反汇编字节串。

`dis._get_instructions_bytes(code, lasti=-1)` 在 3.11 里会自己按 `_inline_cache_entries`
步进缓存，因此可以不构造真 code 对象。
"""
import dis
import importlib.util
import io
import sys

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


def render(code_bytes, names, varnames, consts, argcount):
    """打印每条指令；用 names/varnames/consts 做注解。"""
    out = []
    try:
        instrs = list(dis._get_instructions_bytes(bytes(code_bytes)))
    except Exception as e:
        return [f'  !! {type(e).__name__}: {e}']
    for ins in instrs:
        a = ins.arg
        ann = ''
        if ins.opname in ('LOAD_CONST', 'RETURN_CONST', 'KW_NAMES') and a is not None:
            ann = f'   const={consts[a]!r}' if a < len(consts) else f'   !!const[{a}]'
        elif ins.opname in ('LOAD_NAME', 'STORE_NAME', 'LOAD_ATTR', 'STORE_ATTR',
                            'IMPORT_NAME', 'IMPORT_FROM', 'LOAD_GLOBAL', 'LOAD_METHOD',
                            'CALL_METHOD', 'DELETE_NAME', 'LOAD_METHOD_SUPER'):
            ann = f'   name={names[a]!r}' if a is not None and a < len(names) else f'   !!name[{a}]'
        elif ins.opname in ('LOAD_FAST', 'STORE_FAST', 'DELETE_FAST'):
            ann = f'   var={varnames[a]!r}' if a is not None and a < len(varnames) else f'   !!var[{a}]'
        out.append(f'  {ins.offset:5d} {ins.opname:<28}{a if a is not None else "":>6}{ann}')
    return out


src, dst = sys.argv[1], sys.argv[2]
rec, off, ln = RD.load(src)
buf = io.StringIO()
for c in collect(rec, []):
    buf.write(f'\n===== {c.name} argcount={c.argcount} nlocals={c.nlocals} '
              f'co_code={len(c.co_code)}B\n')
    for line in render(c.co_code, c.names, c.varnames, c.consts, c.argcount):
        buf.write(line + '\n')
open(dst, 'w', encoding='utf-8').write(buf.getvalue())
print('wrote', dst)
