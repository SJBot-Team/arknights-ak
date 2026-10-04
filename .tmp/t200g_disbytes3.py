# -*- coding: utf-8 -*-
"""t200g_disbytes3.py — 3.11 手工步进反汇编（极简：只靠 dis.opname + _inline_cache_entries）。"""
import dis
import importlib.util
import io
import sys

sys.stdout.reconfigure(encoding='utf-8')
BASE = r'C:\Users\23922\Documents\ds_harness\ak\.tmp'
sys.path.insert(0, BASE)
import t200g_read as RD  # noqa: E402

OP = list(dis.opname)
CACHE = [n for n in dis._inline_cache_entries]
# 3.11：无参数指令（其余都带 2 字节参数）
NOARG = {OP.index(n) for n in [
    'CACHE', 'POP_TOP', 'PUSH_NULL', 'NOP', 'UNARY_POSITIVE', 'UNARY_NEGATIVE',
    'UNARY_NOT', 'UNARY_INVERT', 'BINARY_SUBSCR', 'BINARY_SLICE', 'STORE_SLICE',
    'BINARY_LSHIFT', 'BINARY_RSHIFT', 'BINARY_AND', 'BINARY_XOR', 'BINARY_OR',
    'INPLACE_ADD', 'INPLACE_SUBTRACT', 'INPLACE_MULTIPLY', 'INPLACE_MODULO',
    'BINARY_ADD', 'BINARY_SUBTRACT', 'BINARY_MULTIPLY', 'BINARY_MODULO',
    'BINARY_POWER', 'BINARY_TRUE_DIVIDE', 'BINARY_FLOOR_DIVIDE', 'BINARY_OP',
    'INPLACE_FLOOR_DIVIDE', 'INPLACE_TRUE_DIVIDE', 'DELETE_SUBSCR', 'GET_ITER',
    'GET_YIELD_FROM_ITER', 'PRINT_EXPR', 'LOAD_BUILD_CLASS', 'GET_AWAITABLE',
    'LOAD_ASSERTION_ERROR', 'RETURN_GENERATOR', 'GET_AITER', 'GET_ANEXT',
    'BEFORE_ASYNC_WITH', 'BEFORE_WITH', 'END_ASYNC_FOR', 'LIST_APPEND', 'SET_ADD',
    'MAP_ADD', 'MAKE_CELL', 'LOAD_CLOSURE', 'LOAD_DEREF', 'STORE_DEREF',
    'DELETE_DEREF', 'COPY_FREE_VARS', 'RETURN_VALUE', 'SETUP_ANNOTATIONS',
    'POP_EXCEPT', 'RERAISE', 'PUSH_EXC_INFO', 'CHECK_EXC_MATCH', 'CHECK_EG_MATCH',
    'WITH_EXCEPT_START', 'LOAD_METHOD_SUPER', 'LOAD_ATTR_SUPER', 'CACHE2',
    'CACHE3', 'CACHE4',
] if n in OP}
CMP = ['<', '<=', '==', '!=', '>', '>=']
BINOP = ['+', '&', '//', '<<', '@', '*', '%', '|', '**', '>>', '-', '/', '^',
         '+=', '&=', '//=', '<<=', '@=', '*=', '%=', '|=', '**=', '>>=', '-=', '/=', '^=']
NAMEOPS = {'LOAD_NAME', 'STORE_NAME', 'DELETE_NAME', 'LOAD_ATTR', 'STORE_ATTR',
           'DELETE_ATTR', 'IMPORT_NAME', 'IMPORT_FROM', 'LOAD_GLOBAL', 'LOAD_METHOD',
           'CALL_METHOD', 'STORE_GLOBAL', 'DELETE_GLOBAL', 'LOAD_METHOD_SUPER',
           'LOAD_ATTR_SUPER'}
CONSTOPS = {'LOAD_CONST', 'RETURN_CONST', 'KW_NAMES'}
VAROPS = {'LOAD_FAST', 'STORE_FAST', 'DELETE_FAST'}


def collect(rec, out):
    out.append(rec)
    for c in rec.consts:
        if hasattr(c, 'co_code'):
            collect(c, out)
    return out


def dis_one(c, buf):
    co = bytes(c.co_code)
    buf.write(f'\n===== {c.name}  argcount={c.argcount} nlocals={c.nlocals} '
              f'co_code={len(co)}B\n')
    buf.write(f'  consts={[("<code %s>" % x.name) if hasattr(x, "co_code") else x for x in c.consts]}\n')
    buf.write(f'  names={list(c.names)}\n')
    buf.write(f'  varnames={list(c.varnames)}\n')
    i = 0
    while i < len(co) - 1:
        op = co[i]
        nm = OP[op]
        arg = None if op in NOARG else (co[i + 1] | (co[i + 2] << 8) if i + 2 < len(co) else co[i + 1])
        ann = ''
        if arg is not None:
            try:
                if nm in CONSTOPS:
                    ann = f'   const={c.consts[arg]!r}'
                elif nm in NAMEOPS:
                    ann = f'   name={c.names[arg]!r}'
                elif nm in VAROPS:
                    ann = f'   var={c.varnames[arg]!r}'
                elif nm == 'COMPARE_OP':
                    ann = f'   cmp={CMP[arg] if arg < len(CMP) else arg}'
                elif nm == 'BINARY_OP':
                    ann = f'   op={BINOP[arg] if arg < len(BINOP) else arg}'
            except IndexError:
                ann = f'   !!越界[{arg}]'
        buf.write(f'  {i:5d} {nm:<28}{"" if arg is None else arg:>6}{ann}\n')
        i += 2 + 2 * CACHE[op]
    for x in c.consts:
        if hasattr(x, 'co_code'):
            dis_one(x, buf)


if __name__ == '__main__':
    rec, off, ln = RD.load(sys.argv[1])
    buf = io.StringIO()
    for c in collect(rec, []):
        dis_one(c, buf)
    open(sys.argv[2], 'w', encoding='utf-8').write(buf.getvalue())
    print('wrote', sys.argv[2])
