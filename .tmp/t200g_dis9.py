# -*- coding: utf-8 -*-
"""t200g_dis9.py — prts+ 字节码反汇编器（**Python 3.9** opcode 表 + inline CACHE）。

表已用真实字节码校验：
  模块头 `64 00 64 01 6c 00 5a 01` = LOAD_CONST 0 / LOAD_CONST 1 / IMPORT_NAME 0 / STORE_NAME 1
  子函数头 `74 00 6a 01 64 01 1b 00 7d 02` = LOAD_GLOBAL 0 / LOAD_ATTR 1 / LOAD_CONST 1 /
                                        INPLACE_TRUE_DIVIDE 0 / STORE_FAST 2
  ⇒ LOAD_CONST=100, LOAD_NAME=101, IMPORT_NAME=108, STORE_NAME=90,
    LOAD_GLOBAL=116, LOAD_ATTR=106, STORE_FAST=125, INPLACE_TRUE_DIVIDE=27
"""
import importlib.util
import io
import sys

sys.stdout.reconfigure(encoding='utf-8')
BASE = r'C:\Users\23922\Documents\ds_harness\ak\.tmp'

OPNAME = {
    1: 'POP_TOP', 2: 'ROT_TWO', 3: 'ROT_THREE', 4: 'DUP_TOP', 5: 'DUP_TOP_TWO',
    6: 'ROT_FOUR', 9: 'NOP', 10: 'UNARY_POSITIVE', 11: 'UNARY_NEGATIVE',
    12: 'UNARY_NOT', 15: 'UNARY_INVERT', 16: 'BINARY_MATRIX_MULTIPLY',
    17: 'INPLACE_MATRIX_MULTIPLY', 19: 'BINARY_POWER', 20: 'BINARY_MULTIPLY',
    21: 'BINARY_MODULO', 22: 'BINARY_ADD', 23: 'BINARY_SUBTRACT',
    24: 'BINARY_SUBSCR', 25: 'BINARY_FLOOR_DIVIDE', 26: 'INPLACE_FLOOR_DIVIDE',
    27: 'BINARY_TRUE_DIVIDE', 28: 'INPLACE_TRUE_DIVIDE',
    50: 'GET_AITER', 51: 'GET_ANEXT', 52: 'BEFORE_ASYNC_WITH', 53: 'BEGIN_FINALLY',
    54: 'END_ASYNC_FOR', 55: 'INPLACE_ADD', 56: 'INPLACE_SUBTRACT',
    57: 'INPLACE_MULTIPLY', 58: 'INPLACE_MODULO', 59: 'STORE_SUBSCR',
    60: 'DELETE_SUBSCR', 61: 'BINARY_LSHIFT', 62: 'BINARY_RSHIFT',
    63: 'BINARY_AND', 64: 'BINARY_XOR', 65: 'BINARY_OR', 66: 'INPLACE_POWER',
    67: 'GET_ITER', 68: 'GET_YIELD_FROM_ITER', 69: 'PRINT_EXPR',
    70: 'LOAD_BUILD_CLASS', 71: 'YIELD_FROM', 72: 'GET_AWAITABLE',
    75: 'INPLACE_LSHIFT', 76: 'INPLACE_RSHIFT', 77: 'INPLACE_AND',
    78: 'INPLACE_XOR', 79: 'INPLACE_OR', 80: 'WITH_CLEANUP_START',
    81: 'WITH_CLEANUP_FINISH', 83: 'RETURN_VALUE', 84: 'IMPORT_STAR',
    85: 'SETUP_ANNOTATIONS', 86: 'YIELD_VALUE', 87: 'ASYNC_GEN_WRAP',
    88: 'PREP_RERAISE_STAR', 89: 'POP_EXCEPT',
    90: 'STORE_NAME', 91: 'DELETE_NAME', 92: 'UNPACK_SEQUENCE', 93: 'FOR_ITER',
    94: 'UNPACK_EX', 95: 'STORE_ATTR', 96: 'DELETE_ATTR', 97: 'STORE_GLOBAL',
    98: 'DELETE_GLOBAL', 100: 'LOAD_CONST', 101: 'LOAD_NAME', 102: 'BUILD_TUPLE',
    103: 'BUILD_LIST', 104: 'BUILD_SET', 105: 'BUILD_MAP', 106: 'LOAD_ATTR',
    107: 'COMPARE_OP', 108: 'IMPORT_NAME', 109: 'IMPORT_FROM', 110: 'JUMP_FORWARD',
    111: 'JUMP_IF_FALSE_OR_POP', 112: 'JUMP_IF_TRUE_OR_POP', 113: 'JUMP_ABSOLUTE',
    114: 'POP_JUMP_IF_FALSE', 115: 'POP_JUMP_IF_TRUE', 116: 'LOAD_GLOBAL',
    119: 'SETUP_FINALLY', 120: 'LOAD_FAST', 121: 'STORE_FAST', 122: 'DELETE_FAST',
    124: 'LOAD_CLOSURE', 125: 'LOAD_DEREF', 126: 'STORE_DEREF', 127: 'DELETE_DEREF',
    130: 'RAISE_VARARGS', 131: 'CALL_FUNCTION', 132: 'MAKE_FUNCTION',
    133: 'BUILD_SLICE', 134: 'LOAD_CLOSURE', 135: 'LOAD_DEREF', 136: 'STORE_DEREF',
    137: 'DELETE_DEREF', 141: 'CALL_FUNCTION_KW', 142: 'CALL_FUNCTION_EX',
    143: 'SETUP_ASYNC_WITH', 155: 'FORMAT_VALUE', 156: 'BUILD_CONST_KEY_MAP',
    157: 'BUILD_STRING',
    160: 'LOAD_METHOD', 161: 'CALL_METHOD', 162: 'LIST_EXTEND', 163: 'SET_UPDATE',
    164: 'DICT_MERGE', 165: 'DICT_UPDATE',
}
# 无参数指令集合（3.9）
NOARG = {1, 2, 3, 4, 5, 6, 9, 10, 11, 12, 15, 16, 17, 19, 20, 21, 22, 23, 24, 25,
         26, 27, 28, 50, 51, 52, 53, 54, 55, 56, 57, 58, 59, 60, 61, 62, 63, 64, 65,
         66, 67, 68, 69, 70, 71, 72, 75, 76, 77, 78, 79, 80, 81, 83, 84,
         85, 86, 87, 88, 89, 173 if False else 89}
# 3.9 inline cache 数（按 CPython 3.9 `_PyOpcode_Caches`）
CACHE_ENTRIES = {
    106: 4,   # LOAD_ATTR
    95: 4,    # STORE_ATTR
    116: 5,   # LOAD_GLOBAL
    107: 2,   # COMPARE_OP
    92: 1,    # UNPACK_SEQUENCE
    93: 1,    # FOR_ITER
    24: 4,    # BINARY_SUBSCR
    59: 1,    # STORE_SUBSCR
    160: 4,   # LOAD_METHOD
    161: 4,   # CALL_METHOD
    131: 4,   # CALL_FUNCTION
    141: 4,   # CALL_FUNCTION_KW
    142: 4,   # CALL_FUNCTION_EX
    111: 1, 112: 1,
}


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


rd = _load('rd', BASE + r'\t200g_read.py')


def is_code(o):
    return hasattr(o, 'co_code')


def find(rec, want, out):
    if rec.name == want:
        out.append(rec)
    for c in rec.consts:
        if is_code(c):
            find(c, want, out)
    return out


def arg_ann(rec, nm, arg):
    try:
        if nm in ('LOAD_CONST',):
            return f'   const={rec.consts[arg]!r}'
        if nm in ('LOAD_NAME', 'STORE_NAME', 'DELETE_NAME', 'LOAD_ATTR', 'STORE_ATTR',
                  'DELETE_ATTR', 'IMPORT_NAME', 'IMPORT_FROM', 'LOAD_GLOBAL',
                  'LOAD_METHOD', 'CALL_METHOD'):
            return f'   name={rec.names[arg]!r}'
        if nm in ('LOAD_FAST', 'STORE_FAST', 'DELETE_FAST'):
            return f'   var={rec.varnames[arg]!r}'
        if nm in ('LOAD_DEREF', 'STORE_DEREF', 'DELETE_DEREF'):
            allv = list(rec.cellvars) + list(rec.freevars)
            return f'   cell/free={allv[arg]!r}'
        if nm == 'COMPARE_OP':
            return f'   cmp={["<","<=","==","!=",">",">="][arg] if arg < 6 else arg}'
    except IndexError:
        return f'   !!越界[{arg}]'
    return ''


def dis(rec, f, depth=0, path='<module>'):
    pad = '  ' * depth
    co = rec.co_code
    f.write(f'{pad}=== {path}  argcount={rec.argcount} nlocals={rec.nlocals} '
            f'co_code={len(co)}B\n')
    i = 0
    ext = 0
    while i < len(co) - 1:
        op = co[i]
        nm = OPNAME.get(op)
        if nm is None:
            f.write(f'{pad}{i:5d} <op{op}>\n')
            i += 2
            continue
        if op in NOARG:
            f.write(f'{pad}{i:5d} {nm}\n')
            i += 2
            continue
        arg = co[i + 1] | (co[i + 2] << 8) if i + 2 < len(co) else co[i + 1]
        arg |= ext
        ext = 0
        f.write(f'{pad}{i:5d} {nm:<22}{arg:6d}{arg_ann(rec, nm, arg)}\n')
        i += 2 + 2 * CACHE_ENTRIES.get(op, 0)
    for c in rec.consts:
        if is_code(c):
            dis(c, f, depth + 1, f'{path}.{c.name}')


if __name__ == '__main__':
    src = sys.argv[1]
    want = sys.argv[2] if len(sys.argv) > 2 else None
    dst = sys.argv[3] if len(sys.argv) > 3 else src + ('.%s.dis.txt' % want if want else '.dis.txt')
    rec, off, ln = rd.load(src)
    with io.open(dst, 'w', encoding='utf-8') as f:
        if want:
            for r in find(rec, want, []):
                dis(r, f)
        else:
            dis(rec, f)
    print('wrote', dst)
