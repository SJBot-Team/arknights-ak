# -*- coding: utf-8 -*-
"""修正 doc41 小节编号（7.6 缺失）"""
import io
import sys

sys.stdout.reconfigure(encoding='utf-8')
P = r'C:\Users\23922\Documents\ds_harness\ak\knowledge\04_数据对应与核验\41_模拟器与自动打图_首版实现.md'
s = io.open(P, encoding='utf-8').read()
s = s.replace('### 7.8 本轮新增/修改文件', '### 7.7 本轮新增/修改文件')
s = s.replace('### 7.7 两端时序交叉验证', '### 7.6 两端时序交叉验证')
s = s.replace('§7.7', '§7.6')
io.open(P, 'w', encoding='utf-8').write(s)
print([l for l in s.splitlines() if l.startswith('### 7.')])
print('§7.6 引用次数:', s.count('§7.6'))
