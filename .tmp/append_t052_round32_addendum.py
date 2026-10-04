# -*- coding: utf-8 -*-
"""append_t052_round32_addendum.py — 给第三十二轮补上「首条龙 38.8s 的费用账本」。"""
import io
import sys

sys.stdout.reconfigure(encoding='utf-8')

P = r'C:\Users\23922\Documents\ds_harness\management\tasks_registry.md'
OLD = '文档 `knowledge/04/41` 新增 §7.53/§7.54。 | 2026-09-14 |'
NEW = (
    '文档 `knowledge/04/41` 新增 §7.53/§7.54；'
    '⑨**首条龙 38.8s 而非 29.0s 的费用账本**：令(10)+蕾缪安(20) 在上限 20 下把费用清零，'
    '按 +1/s 回费到弦惊价 18 要等到 38.0s，模拟器 38.8s 正是「最早可负担时刻」；'
    '29.0s 那一刻日志为 `need=18, have=9` ⇒ 作者那一下同样放不下，'
    '再次印证「记录时刻 = 按键意图、工具会等费用」；第三条龙作者 83.0s 与模拟 83.0s 完全吻合。 | 2026-09-14 |'
)

s = io.open(P, encoding='utf-8').read()
if OLD not in s:
    raise SystemExit('anchor not found')
s = s.replace(OLD, NEW, 1)
io.open(P, 'w', encoding='utf-8', newline='').write(s)
print('registry 补充完成')
