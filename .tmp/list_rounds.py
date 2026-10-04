# -*- coding: utf-8 -*-
"""list_rounds.py — 列出任务台账中的轮次标记（用于工作链条的层级关系）。"""
import io
import re
import sys

sys.stdout.reconfigure(encoding='utf-8')
s = io.open(r'C:\Users\23922\Documents\ds_harness\management\tasks_registry.md',
            encoding='utf-8').read()
for m in re.finditer(r'【第(\d+)轮】(.{0,95})', s):
    txt = m.group(2).replace('\n', ' ')
    print('{:>4}  {}'.format(m.group(1), txt))
