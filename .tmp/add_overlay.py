# -*- coding: utf-8 -*-
"""往 overlay 追加一条人工补注（避免在命令行里处理制表符/中文引号）。"""
import sys

p = r'C:\Users\23922\Documents\ds_harness\ak\glossary\90_人工补注.tsv'
line = '\t'.join([
    'uniequip_003_huang',
    '煌的模组「稍后回来」：**天赋覆写名＝紧急除颤** —— 一次 **50% 生命上限治疗** + 锁定（阈值 50% 生命、8s；潜 2 为 9s），实测自 battle_equip_table 的 blackboard',
    '03/29 §二·实例①',
    '紧急除颤、稍后回来',
    'blackboard: huang_t_1[heal].hp_ratio=0.5；QQ 群「带了一次回血」已被数据证实',
])
with open(p, 'a', encoding='utf-8', newline='\n') as f:
    f.write(line + '\n')
print('已追加 1 行；当前行数:', sum(1 for _ in open(p, encoding='utf-8')))
