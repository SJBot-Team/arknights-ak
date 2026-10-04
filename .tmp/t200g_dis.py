# -*- coding: utf-8 -*-
"""t200g_dis.py — prts+ PYZ 字节码反汇编器（Python 3.11 opcode 表 + inline cache）。

用法：python t200g_dis.py <pyc> "<函数名>" [out.txt]
"""
import importlib.util
import io
import sys

sys.stdout.reconfigure(encoding='utf-8')
BASE = r'C:\Users\23922\Documents\ds_harness\ak\.tmp'


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


rd = _load('rd', BASE + r'\t200g_read.py')
OP = _load('op311', BASE + r'\t200g_op311.py')
CACHE = OP.CACHE_ENTRIES
HASARG = OP.HASARG


def is_code(o):
    return hasattr(o, 'co_code')


def find(rec, want, out):
    if rec.name == want:
        out.append(rec)
    for c in rec.consts:
        if is_code(c):
            find(c, want, out)
    return out


def dis(rec, f, depth=0, path='<module>'):
    pad = '  ' * depth
    co = rec.co_code
    f.write(f'{pad}=== {path}  argcount={rec.argcount} nlocals={rec.nlocals} '
            f'co_code={len(co)}B\n')
    f.write(f'{pad}  consts={[("<code %s>" % c.name) if is_code(c) else c for c in rec.consts]}\n')
    f.write(f'{pad}  names={list(rec.names)}\n')
    f.write(f'{pad}  varnames={list(rec.varnames)}\n')
    i = 0
    ext = 0
    while i < len(co):
        op = co[i]
        nm = OP.OPNAME[op]
        if op == 144:
            if i + 2 >= len(co):
                break
            ext = (ext | co[i + 1] | (co[i + 2] << 8)) << 8 if False else (
                co[i + 1] | (co[i + 2] << 8))
            f.write(f'{pad}{i:5d} EXTENDED_ARG {ext}\n')
            i += 2
            continue
        if op in HASARG:
            arg = co[i + 1] | (co[i + 2] << 8) if i + 2 < len(co) else 0
            ann = ''
            if nm in ('LOAD_CONST', 'KW_NAMES'):
                ann = f'   const={rec.consts[arg]!r}' if arg < len(rec.consts) else f'   !!const[{arg}]'
            elif nm in ('LOAD_NAME', 'STORE_NAME', 'DELETE_NAME', 'LOAD_ATTR',
                        'STORE_ATTR', 'DELETE_ATTR', 'IMPORT_NAME', 'IMPORT_FROM',
                        'LOAD_GLOBAL', 'LOAD_METHOD', 'CALL_METHOD', 'LOAD_METHOD_SUPER',
                        'LOAD_ATTR_SUPER'):
                ann = f'   name={rec.names[arg]!r}' if arg < len(rec.names) else f'   !!name[{arg}]'
            elif nm in ('LOAD_FAST', 'STORE_FAST', 'DELETE_FAST'):
                ann = f'   var={rec.varnames[arg]!r}' if arg < len(rec.varnames) else f'   !!var[{arg}]'
            elif nm in ('LOAD_DEREF', 'STORE_DEREF', 'LOAD_CLASSDEREF', 'DELETE_DEREF',
                        'MAKE_CELL'):
                allv = list(rec.cellvars) + list(rec.freevars)
                ann = f'   cell/free={allv[arg]!r}' if arg < len(allv) else f'   !!cf[{arg}]'
            elif nm == 'COMPARE_OP':
                cmps = ['<', '<=', '==', '!=', '>', '>=']
                ann = f'   op={cmps[arg] if arg < len(cmps) else arg}'
            elif nm == 'BINARY_OP':
                ops = ['+', '&', '//', '<<', '@', '*', '%', '|', '**', '>>', '-', '/', '^']
                ann = f'   op={ops[arg] if arg < len(ops) else arg}'
            nxt = 2 + 2 * CACHE.get(nm, 0)
            f.write(f'{pad}{i:5d} {nm:<26}{arg:6d}{ann}\n')
            i += nxt
        else:
            f.write(f'{pad}{i:5d} {nm}\n')
            i += 2
    for c in rec.consts:
        if is_code(c):
            dis(c, f, depth + 1, f'{path}.{c.name}')


if __name__ == '__main__':
    src = sys.argv[1]
    want = sys.argv[2] if len(sys.argv) > 2 else None
    dst = sys.argv[3] if len(sys.argv) > 3 else src + ('.%s.txt' % want if want else '.dis.txt')
    rec, off, ln = rd.load(src)
    with io.open(dst, 'w', encoding='utf-8') as f:
        if want:
            for r in find(rec, want, []):
                dis(r, f)
        else:
            dis(rec, f)
    print('wrote', dst)
