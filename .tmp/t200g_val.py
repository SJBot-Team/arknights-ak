# -*- coding: utf-8 -*-
"""t200g_val.py — 校验 op39 表：用已知语义的字节码模式做自检。

自检 A（calc_view 顶层）：期望 `IMPORT_NAME` 紧跟 `STORE_NAME`，且 names[1]=='np'。
自检 B：统计所有出现的 opcode 编号，若出现 '<n>' 未知名 ⇒ 表错位。
自检 C：`LOAD_CONST` 的 arg 必须 < len(consts)。
"""
import importlib.util
import sys

sys.stdout.reconfigure(encoding='utf-8')
base = r'C:\Users\23922\Documents\ds_harness\ak\.tmp'


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


op39 = _load('op39', base + r'\t200g_op39.py')
rd = _load('rd', base + r'\t200g_read.py')

rec, off, ln = rd.load(base + r'\pyz\src_logic_calc_view.pyc')
print('top names:', list(rec.names))
co = rec.co_code
for SKIP in (0, 1):
  print(f'===== 跳过前 {SKIP} 字节 =====')
  i = SKIP
  print('--- 前 22 条指令（表自检） ---')
  n = 0
  while i + 1 < len(co) and n < 22:
    op = co[i]
    name = op39.OPNAME[op] if op < 256 else '?'
    if op39.has_arg(op):
        arg = co[i + 1] | (co[i + 2] << 8) if i + 2 < len(co) else co[i + 1]
        ann = ''
        if name == 'LOAD_CONST':
            ann = f'  const={rec.consts[arg]!r}' if arg < len(rec.consts) else f'  !!const[{arg}]越界'
        elif name in ('LOAD_NAME', 'STORE_NAME', 'LOAD_ATTR', 'STORE_ATTR', 'LOAD_METHOD'):
            ann = f'  name={rec.names[arg]!r}' if arg < len(rec.names) else f'  !!name[{arg}]越界'
        elif name in ('LOAD_FAST', 'STORE_FAST'):
            ann = f'  var={rec.varnames[arg]!r}' if arg < len(rec.varnames) else f'  !!var[{arg}]越界'
        print(f'{i:4d} {name:<24}{arg:5d}{ann}')
        i += 2
    else:
        print(f'{i:4d} {name}')
        i += 1
    n += 1
  from collections import Counter
  cnt = Counter(); bad = Counter(); i = SKIP
  while i + 1 < len(co):
      op = co[i]
      nm = op39.OPNAME[op] if op < 256 else '?'
      cnt[nm] += 1
      if nm.startswith('<'):
          bad[nm] += 1
      i += 2 if op39.has_arg(op) else 1
  print('未知:', dict(bad))
  print('前 20:', cnt.most_common(20))

