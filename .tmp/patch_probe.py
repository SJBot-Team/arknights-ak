# -*- coding: utf-8 -*-
"""把 probe_videos.py 的输出文件名改成 ASCII（v00..v06）"""
import io
import sys

sys.stdout.reconfigure(encoding='utf-8')
p = r'C:\Users\23922\Documents\ds_harness\ak\.tmp\probe_videos.py'
s = io.open(p, encoding='utf-8').read()
old = "    name = os.path.splitext(os.path.basename(v))[0].replace(' ', '_')"
new = "    name = 'v%02d' % VIDS.index(v)"
assert old in s, 'pattern not found'
s = s.replace(old, new)
io.open(p, 'w', encoding='utf-8').write(s)
print('patched ok')
