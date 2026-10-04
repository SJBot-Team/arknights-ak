# -*- coding: utf-8 -*-
"""t200g_dis11.py — prts+ 字节码反汇编器（**Python 3.11** opcode 表 + inline CACHE）。

判据（真实字节码逐条核对，`calc_view.transform_map_to_view`）：
  `74 00` → LOAD_GLOBAL 0（全局 `math`）
  `6a 01` → LOAD_ATTR 1（`.pi`）
  `64 01` → LOAD_CONST 1（= 180）
  `1b 00` → BINARY_FLOOR_DIVIDE 0
  `7d 02` → STORE_FAST 2（= DEGREE）
  `7a 30` → INPLACE_TRUE_DIVIDE 0x30
  `02 00` → PUSH_NULL；`83 02` → CALL 2
  ⇒ 与 co_varnames[2]='DEGREE'、co_consts[1]=180 完全自洽。
"""
import io
import sys

sys.stdout.reconfigure(encoding='utf-8')
BASE = r'C:\Users\23922\Documents\ds_harness\ak\.tmp'
sys.path.insert(0, BASE)
import t200g_read as RD  # noqa: E402

OPNAME = {
    0: 'CACHE', 1: 'POP_TOP', 2: 'PUSH_NULL', 3: 'NOP', 4: 'UNARY_POSITIVE',
    5: 'UNARY_NEGATIVE', 6: 'UNARY_NOT', 7: 'UNARY_INVERT', 8: 'BINARY_SUBSCR',
    9: 'BINARY_SLICE', 10: 'STORE_SLICE', 11: 'BINARY_LSHIFT', 12: 'BINARY_RSHIFT',
    13: 'BINARY_AND', 14: 'BINARY_XOR', 15: 'BINARY_OR', 16: 'INPLACE_ADD',
    17: 'INPLACE_SUBTRACT', 18: 'INPLACE_MULTIPLY', 19: 'INPLACE_MODULO',
    20: 'STORE_SUBSCR', 21: 'BINARY_ADD', 22: 'BINARY_SUBTRACT', 23: 'BINARY_MULTIPLY',
    24: 'BINARY_MODULO', 25: 'BINARY_POWER', 26: 'BINARY_TRUE_DIVIDE',
    27: 'BINARY_FLOOR_DIVIDE', 28: 'BINARY_OP', 29: 'INPLACE_FLOOR_DIVIDE',
    30: 'INPLACE_TRUE_DIVIDE', 31: 'PRECALL', 32: 'CALL', 33: 'KW_NAMES',
    34: 'DELETE_SUBSCR', 35: 'GET_ITER', 36: 'GET_YIELD_FROM_ITER', 37: 'PRINT_EXPR',
    38: 'LOAD_BUILD_CLASS', 39: 'GET_AWAITABLE', 40: 'LOAD_ASSERTION_ERROR',
    41: 'RETURN_GENERATOR', 42: 'GET_AITER', 43: 'GET_ANEXT', 44: 'BEFORE_ASYNC_WITH',
    45: 'BEFORE_WITH', 46: 'END_ASYNC_FOR', 47: 'STORE_NAME', 48: 'DELETE_NAME',
    49: 'UNPACK_SEQUENCE', 50: 'UNPACK_EX', 51: 'STORE_ATTR', 52: 'DELETE_ATTR',
    53: 'STORE_GLOBAL', 54: 'DELETE_GLOBAL', 55: 'LOAD_CONST', 56: 'LOAD_NAME',
    57: 'BUILD_TUPLE', 58: 'BUILD_LIST', 59: 'BUILD_SET', 60: 'BUILD_MAP',
    61: 'LOAD_ATTR', 62: 'COMPARE_OP', 63: 'IMPORT_NAME', 64: 'IMPORT_FROM',
    65: 'JUMP_FORWARD', 66: 'POP_JUMP_FORWARD_IF_FALSE',
    67: 'POP_JUMP_FORWARD_IF_TRUE', 68: 'POP_JUMP_BACKWARD_IF_FALSE',
    69: 'POP_JUMP_BACKWARD_IF_TRUE', 70: 'POP_JUMP_FORWARD_IF_NONE',
    71: 'POP_JUMP_BACKWARD_IF_NONE', 72: 'POP_JUMP_FORWARD_IF_NOT_NONE',
    73: 'POP_JUMP_BACKWARD_IF_NOT_NONE', 74: 'JUMP_BACKWARD',
    75: 'POP_JUMP_BACKWARD_IF_NOT_NONE', 76: 'POP_JUMP_BACKWARD_IF_NONE',
    77: 'POP_JUMP_FORWARD_IF_NOT_NONE', 78: 'POP_JUMP_FORWARD_IF_NONE',
    79: 'LIST_APPEND', 80: 'SET_ADD', 81: 'MAP_ADD', 82: 'LOAD_FAST',
    83: 'STORE_FAST', 84: 'DELETE_FAST', 85: 'MAKE_CELL', 86: 'LOAD_CLOSURE',
    87: 'LOAD_DEREF', 88: 'STORE_DEREF', 89: 'DELETE_DEREF', 90: 'COPY_FREE_VARS',
    91: 'RETURN_VALUE', 92: 'RETURN_CONST', 93: 'SETUP_ANNOTATIONS', 94: 'POP_BLOCK',
    95: 'POP_EXCEPT', 96: 'RERAISE', 97: 'PUSH_EXC_INFO', 98: 'CHECK_EXC_MATCH',
    99: 'CHECK_EG_MATCH', 100: 'WITH_EXCEPT_START', 101: 'LOAD_METHOD',
    102: 'CALL_METHOD', 103: 'RAISE_VARARGS', 104: 'CALL_FUNCTION',
    105: 'MAKE_FUNCTION', 106: 'BUILD_SLICE', 107: 'BINARY_SUBSCR_GETITEM',
    108: 'CALL_FUNCTION_EX', 109: 'LOAD_METHOD_SUPER', 110: 'LOAD_ATTR_SUPER',
    111: 'PUSH_EXC_INFO', 112: 'RETURN_CONST', 144: 'EXTENDED_ARG',
    116: 'LOAD_GLOBAL', 117: 'IS_OP', 118: 'CONTAINS_OP', 119: 'RERAISE',
    120: 'COPY', 121: 'BINARY_OP_ADAPTIVE', 122: 'BINARY_OP_ADD_UNICODE',
    123: 'BINARY_OP_INPLACE_ADD_UNICODE', 124: 'BINARY_SUBSCR_ADAPTIVE',
    125: 'BINARY_SUBSCR_DICT', 126: 'BINARY_SUBSCR_LIST_INT',
    127: 'BINARY_SUBSCR_TUPLE_INT', 128: 'CALL_ADAPTIVE', 129: 'CALL_FUNCTION_EX',
    130: 'CALL_PY_WITH_DEFAULTS', 131: 'COMPARE_OP_ADAPTIVE',
    132: 'COMPARE_OP_FLOAT_JUMP', 133: 'COMPARE_OP_INT_JUMP',
    134: 'COMPARE_OP_STR_JUMP', 135: 'FOR_ITER_ADAPTIVE', 136: 'FOR_ITER_LIST',
    137: 'FOR_ITER_TUPLE', 138: 'JUMP_BACKWARD_ADAPTIVE',
    139: 'JUMP_BACKWARD_NO_INTERRUPT', 140: 'LOAD_ATTR_ADAPTIVE',
    141: 'LOAD_ATTR_INSTANCE_VALUE', 142: 'LOAD_ATTR_MODULE',
    143: 'LOAD_ATTR_SLOT', 145: 'LOAD_ATTR_WITH_HINT', 146: 'LOAD_FAST__LOAD_FAST',
    147: 'LOAD_FAST__LOAD_CONST', 148: 'LOAD_GLOBAL_ADAPTIVE',
    149: 'LOAD_GLOBAL_BUILTIN', 150: 'LOAD_GLOBAL_MODULE',
    151: 'LOAD_METHOD_ADAPTIVE', 152: 'LOAD_METHOD_CLASS',
    153: 'LOAD_METHOD_MODULE', 154: 'LOAD_METHOD_NO_DICT',
    155: 'LOAD_METHOD_OBJECT', 156: 'LOAD_METHOD_WITH_DICT',
    157: 'LOAD_METHOD_WITH_VALUES', 158: 'PRECALL_ADAPTIVE',
    159: 'PRECALL_BOUND_METHOD', 160: 'PRECALL_BUILTIN_CLASS',
    161: 'PRECALL_BUILTIN_FAST_WITH_KEYWORDS', 162: 'PRECALL_METHOD_DESCRIPTOR_FAST_WITH_KEYWORDS',
    163: 'PRECALL_NO_KW_BUILTIN_FAST', 164: 'PRECALL_NO_KW_BUILTIN_O',
    165: 'PRECALL_NO_KW_IS', 166: 'PRECALL_NO_KW_LEN',
    167: 'PRECALL_NO_KW_LIST_APPEND', 168: 'PRECALL_NO_KW_METHOD_DESCRIPTOR_FAST',
    169: 'PRECALL_NO_KW_METHOD_DESCRIPTOR_NOARGS',
    170: 'PRECALL_NO_KW_METHOD_DESCRIPTOR_O', 171: 'PRECALL_NO_KW_STR_1',
    172: 'PRECALL_NO_KW_TUPLE_1', 173: 'PRECALL_NO_KW_TYPE_1',
    174: 'PRECALL_PYFUNC', 175: 'RESUME', 176: 'STORE_ATTR_ADAPTIVE',
    177: 'STORE_ATTR_INSTANCE_VALUE', 178: 'STORE_ATTR_SLOT',
    179: 'STORE_ATTR_WITH_HINT', 180: 'STORE_FAST__LOAD_FAST',
    181: 'STORE_FAST__STORE_FAST', 182: 'STORE_SUBSCR_ADAPTIVE',
    183: 'STORE_SUBSCR_DICT', 184: 'STORE_SUBSCR_LIST_INT', 185: 'UNPACK_SEQUENCE_ADAPTIVE',
    186: 'UNPACK_SEQUENCE_LIST', 187: 'UNPACK_SEQUENCE_TUPLE',
    188: 'UNPACK_SEQUENCE_TWO_TUPLE', 189: 'BINARY_OP_MULTIPLY_INT',
    190: 'BINARY_OP_ADD_INT', 191: 'BINARY_OP_SUBTRACT_INT',
    192: 'BINARY_OP_MULTIPLY_FLOAT', 193: 'BINARY_OP_ADD_FLOAT',
    194: 'BINARY_OP_SUBTRACT_FLOAT',
}
CACHE_ENTRIES = {
    8: 4, 20: 1, 49: 1, 51: 4, 61: 4, 62: 2, 31: 1, 32: 4, 56: 5, 28: 1,
    101: 10, 102: 10, 104: 4, 108: 4, 74: 1, 68: 1, 69: 1, 71: 1, 73: 1,
}
HASARG = set(range(256)) - {
    0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20,
    21, 22, 23, 24, 25, 26, 27, 29, 30, 34, 35, 36, 37, 38, 39, 40, 41, 42, 43,
    44, 45, 46, 79, 80, 81, 85, 86, 87, 88, 89, 91, 93, 94, 95, 96, 97, 98, 99,
    100, 103, 105, 106, 107, 109, 110, 111,
}
# LOAD_CONST/RETURN_CONST/KW_NAMES 用常量表；LOAD_* 名字类用 names；…（LOAD_DEREF 用 cell+free）
CONST_OPS = {55, 92, 33}
NAME_OPS = {47, 48, 56, 51, 52, 53, 54, 61, 63, 64, 101, 102, 109, 110}
VAR_OPS = {82, 83, 84}
DEREF_OPS = {87, 88, 89, 85}
CMP = ['<', '<=', '==', '!=', '>', '>=']
BINOP = ['+', '&', '//', '<<', '@', '*', '%', '|', '**', '>>', '-', '/', '^',
         '+=', '&=', '//=', '<<=', '@=', '*=', '%=', '|=', '**=', '>>=', '-=', '/=', '^=']


def is_code(o):
    return hasattr(o, 'co_code')


def collect(rec, out):
    out.append(rec)
    for c in rec.consts:
        if is_code(c):
            collect(c, out)
    return out


def ann(rec, nm, arg):
    try:
        if nm in ('LOAD_CONST', 'RETURN_CONST', 'KW_NAMES') or (nm == 'KW_NAMES'):
            return f'   const={rec.consts[arg]!r}'
        if nm in ('STORE_NAME', 'DELETE_NAME', 'LOAD_NAME', 'LOAD_ATTR', 'STORE_ATTR',
                  'DELETE_ATTR', 'STORE_GLOBAL', 'DELETE_GLOBAL', 'IMPORT_NAME',
                  'IMPORT_FROM', 'LOAD_METHOD', 'CALL_METHOD', 'LOAD_GLOBAL',
                  'LOAD_METHOD_SUPER', 'LOAD_ATTR_SUPER'):
            return f'   name={rec.names[arg]!r}'
        if nm in ('LOAD_FAST', 'STORE_FAST', 'DELETE_FAST'):
            return f'   var={rec.varnames[arg]!r}'
        if nm in ('LOAD_DEREF', 'STORE_DEREF', 'DELETE_DEREF', 'MAKE_CELL',
                  'LOAD_CLOSURE'):
            allv = list(rec.cellvars) + list(rec.freevars)
            return f'   cell/free={allv[arg]!r}'
        if nm == 'COMPARE_OP':
            return f'   cmp={CMP[arg] if arg < len(CMP) else arg}'
        if nm == 'BINARY_OP':
            return f'   op={BINOP[arg] if arg < len(BINOP) else arg}'
    except IndexError:
        return f'   !!越界[{arg}]'
    return ''


def dis(rec, f, label):
    co = rec.co_code
    f.write(f'=== {label}  argcount={rec.argcount} nlocals={rec.nlocals} '
            f'co_code={len(co)}B\n')
    f.write(f'  consts={[("<code %s>" % c.name) if is_code(c) else c for c in rec.consts]}\n')
    f.write(f'  names={list(rec.names)}\n')
    f.write(f'  varnames={list(rec.varnames)}\n')
    i = 0
    while i < len(co) - 1:
        op = co[i]
        nm = OPNAME.get(op, f'<op{op}>')
        arg = co[i + 1] | (co[i + 2] << 8) if i + 2 < len(co) else co[i + 1]
        if op in HASARG:
            f.write(f'{i:5d} {nm:<28}{arg:6d}{ann(rec, nm, arg)}\n')
            i += 2 + 2 * CACHE_ENTRIES.get(op, 0)
        else:
            f.write(f'{i:5d} {nm}\n')
            i += 2
    for c in rec.consts:
        if is_code(c):
            f.write('\n')
            dis(c, f, f'{label}.{c.name}')


if __name__ == '__main__':
    src = sys.argv[1]
    dst = sys.argv[2]
    rec, off, ln = RD.load(src)
    with io.open(dst, 'w', encoding='utf-8') as f:
        dis(rec, f, '<module>')
    print('wrote', dst)
