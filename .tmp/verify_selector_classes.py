# -*- coding: utf-8 -*-
"""把 PRTS「选择器」页列出的选择器类名，逐个到 dump.cs 里核对是否存在（PRTS→代码 的一次强校验）。只读。"""
import re
import sys

sys.stdout.reconfigure(encoding='utf-8')
DUMP = r'E:\__file\ak_kb\client_res\il2cpp\dump\dump.cs'
PAGE = r'C:\Users\23922\Documents\ds_harness\ak\_raw\prts\调零修罗\机制页_选择器.txt'

text = open(PAGE, encoding='utf-8').read()
names = sorted(set(re.findall(r'<code>([A-Za-z][A-Za-z0-9_]*(?:Selector|Validator)[A-Za-z0-9_]*)</code>', text)))
print(f'PRTS 页里出现的 *Selector/*Validator 类名 {len(names)} 个')

dump = open(DUMP, encoding='utf-8', errors='replace').read()
hit, miss = [], []
for n in names:
    pat = re.compile(r'\b(?:class|struct)\s+' + re.escape(n) + r'\b')
    m = pat.search(dump)
    (hit if m else miss).append(n)
print(f'\n✅ dump.cs 命中 {len(hit)}：')
for n in hit:
    print('   ', n)
print(f'\n❌ 未命中 {len(miss)}：')
for n in miss:
    print('   ', n)
