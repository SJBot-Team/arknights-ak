# -*- coding: utf-8 -*-
"""把知识库里提到过的关卡代号 ↔ 批量表里的关卡文件对上，生成「补注候选」清单（只读，不改任何表）。"""
import collections
import csv
import os
import re
import sys

sys.stdout.reconfigure(encoding='utf-8')
A = r'C:\Users\23922\Documents\ds_harness\ak'
G = os.path.join(A, 'glossary')
KB = os.path.join(A, 'knowledge')

# 1) 批量表：代号 -> 文件名 / 关卡名
rows = list(csv.reader(open(os.path.join(G, '04_关卡.tsv'), encoding='utf-8'), delimiter='\t'))[1:]
by_code = {}
for r in rows:
    if len(r) > 8 and r[8]:
        by_code.setdefault(r[8], (r[2], r[7]))
print(f'关卡表：{len(rows)} 条，带代号 {len(by_code)} 个')

# 2) 知识库里提到的关卡代号 -> 出现文件
pat = re.compile(r'(?<![\w-])((?:H|S|GT|CE|LS|AP|PR|SK|CA|TB)?\d{1,2}-\d{1,2})(?![\w-])')
mention = collections.defaultdict(collections.Counter)
for root, dirs, files in os.walk(KB):
    dirs[:] = [d for d in dirs if d not in ('.venv', '__pycache__')]
    for fn in files:
        if not fn.endswith('.md'):
            continue
        p = os.path.join(root, fn)
        try:
            txt = open(p, encoding='utf-8').read()
        except Exception:
            continue
        for m in pat.finditer(txt):
            code = m.group(1)
            if code in by_code:
                mention[code][fn[:2]] += 1
print(f'知识库提到的、且表里存在的代号：{len(mention)} 个\n')
for code, c in sorted(mention.items(), key=lambda kv: -sum(kv[1].values()))[:25]:
    fn, name = by_code[code]
    files = '、'.join(f'{k}({v})' for k, v in c.most_common(4))
    print(f'  {code:7} {name:12} {fn[:46]:48} 提及: {files}')
