# -*- coding: utf-8 -*-
"""把 doc41 的「7.7 录像费用轨迹」小节移到「7.8 本轮新增/修改文件」之前，保持编号顺序"""
import io
import sys

sys.stdout.reconfigure(encoding='utf-8')
P = r'C:\Users\23922\Documents\ds_harness\ak\knowledge\04_数据对应与核验\41_模拟器与自动打图_首版实现.md'
s = io.open(P, encoding='utf-8').read()
h_video = '### 7.7 录像费用轨迹自动读取（工具 + 全片结果）'
h_files = '### 7.8 本轮新增/修改文件'
i_v = s.index(h_video)
i_f = s.index(h_files)
assert i_v > i_f, '顺序与预期不符'
# 视频小节从 i_v 到「复现：apps/test_ruler_clock.py 段 E」段落结束
i_end = s.index('### 7.8 本轮新增/修改文件', i_v) if '### 7.8' in s[i_v:] else len(s)
video_block = s[i_v:i_end].rstrip() + '\n\n'
rest = s[:i_v] + s[i_end:]
i_f2 = rest.index(h_files)
out = rest[:i_f2] + video_block + rest[i_f2:]
io.open(P, 'w', encoding='utf-8').write(out)
print([l for l in out.splitlines() if l.startswith('### 7.') or l.startswith('## 八')])
