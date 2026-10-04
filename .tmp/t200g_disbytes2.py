# -*- coding: utf-8 -*-
"""t200g_disbytes2.py — 用 3.11 官方缓存表手工步进反汇编（避免 _get_instructions_bytes 的长度校验）。"""
import dis
import importlib.util
import io
import sys

sys.stdout.reconfigure(encoding='utf-8')
BASE = r'C:\Users\23922\Documents\ds_harness\ak\.tmp'
sys.path.insert(0, BASE)
import t200g_read as RD  # noqa: E402

OP = dis.opname
CACHE = {i: n for i, n in enumerate(dis._inline_cache_entries) if n}
HASARG = set(dis.hasarg) if hasattr(dis, 'hasarg') else set(dis.hasnargs)
HASARG |= set(dis.hasconst) | set(dis.hasname) | set(dis.haslocal) | set(dis.hasfree) | set(dis.hascompare) | set(dis.hasjrel) | set(dis.hasjabs)
HASARG -= {OP.index('CACHE'), OP.index('POP_TOP'), OP.index('PUSH_NULL'), OP.index('NOP'),
           OP.index('RETURN_VALUE'), OP.index('RETURN_GENERATOR'), OP.index('PRINT_EXPR'),
           OP.index('GET_ITER'), OP.index('GET_YIELD_FROM_ITER'), OP.index('BEFORE_WITH'),
           OP.index('BEFORE_ASYNC_WITH'), OP.index('END_ASYNC_FOR'), OP.index('POP_BLOCK'),
           OP.index('POP_EXCEPT'), OP.index('RERAISE'), OP.index('PUSH_EXC_INFO'),
           OP.index('CHECK_EXC_MATCH'), OP.index('CHECK_EG_MATCH'),
           OP.index('WITH_EXCEPT_START'), OP.index('SETUP_ANNOTATIONS'),
           OP.index('LOAD_BUILD_CLASS'), OP.index('GET_AWAITABLE'), OP.index('GET_AITER'),
           OP.index('GET_ANEXT'), OP.index('LOAD_ASSERTION_ERROR'), OP.index('LIST_APPEND'),
           OP.index('SET_ADD'), OP.index('MAP_ADD'), OP.index('MAKE_CELL'),
           OP.index('COPY_FREE_VARS'), OP.index('LOAD_CLOSURE'),
           OP.index('LOAD_DEREF'), OP.index('STORE_DEREF'), OP.index('DELETE_DEREF')}
CMP = ['<', '<=', '==', '!=', '>', '>=']
BINOP = ['+', '&', '//', '<<', '@', '*', '%', '|', '**', '>>', '-', '/', '^']


def collect(rec, out):
    out.append(rec)
    for c in rec.consts:
        if hasattr(c, 'co_code'):
            collect(c, out)
    return out


def dis_one(c, buf):
    co = bytes(c.co_code)
    names, vars_, consts = c.names, c.varnames, c.consts
    buf.write(f'\n===== {c.name}  argcount={c.argcount} nlocals={c.nlocals} '
              f'co_code={len(co)}B\n')
    buf.write(f'  consts={[("<code %s>" % x.name) if hasattr(x, "co_code") else x for x in consts]}\n')
    buf.write(f'  names={list(names)}\n')
    i = 0
    while i < len(co) - 1:
        op = co[i]
        nm = OP[op]
        arg = None
        if op in HASARG:
            arg = co[i + 1] | (co[i + 2] << 8) if i + 2 < len(co) else co[i + 1]
        ann = ''
        if arg is not None:
            try:
                if nm in ('LOAD_CONST', 'RETURN_CONST', 'KW_NAMES'):
                    ann = f'   const={consts[arg]!r}'
                elif nm in ('LOAD_NAME', 'STORE_NAME', 'DELETE_NAME', 'LOAD_ATTR',
                            'STORE_ATTR', 'DELETE_ATTR', 'IMPORT_NAME', 'IMPORT_FROM',
                            'LOAD_GLOBAL', 'LOAD_METHOD', 'CALL_METHOD', 'STORE_GLOBAL',
                            'DELETE_GLOBAL', 'LOAD_METHOD_SUPER', 'LOAD_ATTR_SUPER'):
                    ann = f'   name={names[arg]!r}'
                elif nm in ('LOAD_FAST', 'STORE_FAST', 'DELETE_FAST'):
                    ann = f'   var={vars_[arg]!r}'
                elif nm == 'COMPARE_OP':
                    ann = f'   cmp={CMP[arg] if arg < len(CMP) else arg}'
                elif nm == 'BINARY_OP':
                    ann = f'   op={BINOP[arg] if arg < len(BINOP) else arg}'
            except IndexError:
                ann = f'   !!越界[{arg}]'
        buf.write(f'  {i:5d} {nm:<30}{"" if arg is None else arg:>6}{ann}\n')
        i += 2 + 2 * CACHE.get(op, 0)
    for x in consts:
        if hasattr(x, 'co_code'):
            dis_one(x, buf)


src, dst = sys.argv[1], sys.argv[2]
rec, off, ln = RD.load(src)
buf = io.StringIO()
buf.write(f'# 3.11 官方缓存表（仅列出非零项）：{ {OP[k]: v for k, v in CACHE.items()} }\n')
for c in collect(rec, []):
    dis_one(c, buf)
open(dst, 'w', encoding='utf-8').write(buf.getvalue())
print('wrote', dst)
