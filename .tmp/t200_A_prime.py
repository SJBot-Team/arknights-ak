# -*- coding: utf-8 -*-
r"""A′ 落地：给 04 域每篇头部加一行「主题归属」（虚拟分组，**文件不动**）。

主题别名（写进 `00_Agent入口 §〇` 与 `04/00_目录.md §三之二`）：
  04A 取数/解包 ｜ 04B 读代码/反汇编 ｜ 04C 机制结论 ｜ 04D 模拟环境
  04E 实机与打图 ｜ 04F 社区/外部口径 ｜ 04G 元/索引/审计

用法：python t200_A_prime.py [--write]
"""
from __future__ import annotations

import glob
import io
import os
import re
import sys

sys.stdout.reconfigure(encoding='utf-8')

D = r'C:\Users\23922\Documents\ds_harness\ak\knowledge\04_数据对应与核验'
THEMES = {
    '04A': ('取数 / 解包流程', {'15', '16', '26', '27', '30', '32', 'OpenBachelorS'}),
    '04B': ('读代码 / 反汇编', {'29', '33', '35', '40', '63', '63a', '63b', '66', '66a'}),
    '04C': ('机制结论（代码层）', {'34', '36', '37', '38', '39', '55', '56', '57', '58',
                                  '61', '65', '67', '67a', '68', '69', '70', '74', '78'}),
    '04D': ('模拟环境', {'31', '41', '41a', '41b', '41c', '41d', '41e', '41f', '42', '43',
                         '44', '46', '50', '71', '73', '77'}),
    '04E': ('实机 / 打图操作', {'48', '49', '51', '52', '53', '59', '64', '64a', '64b',
                                '72', '75', '76', '79'}),
    '04F': ('社区 / 外部口径', {'23', '28', '47', '54', '54a', '54b', '54c', '54d', '54e'}),
    '04G': ('元 / 索引 / 审计', {'00', '01', '45', '60', '62'}),
}
NUM2THEME = {}
for tag, (_, nums) in THEMES.items():
    for n in nums:
        NUM2THEME[n] = tag


def theme_of(fname: str):
    m = re.match(r'^(\d{2}[a-z]?)_', fname)
    if m:
        return NUM2THEME.get(m.group(1))
    if fname.startswith('OpenBachelorS'):
        return '04A'
    return None


def main() -> int:
    write = '--write' in sys.argv
    files = sorted(glob.glob(os.path.join(D, '*.md')))
    unmapped, changed = [], 0
    for p in files:
        base = os.path.basename(p)
        tag = theme_of(base)
        if tag is None:
            unmapped.append(base)
            continue
        name = THEMES[tag][0]
        line = f'> 主题：**{tag} {name}**（本域按主题的虚拟分组，索引见 `04/00_目录.md §三之二`；文件路径未变）'
        lines = io.open(p, encoding='utf-8').read().split('\n')
        if any(l.startswith('> 主题：') for l in lines[:12]):
            continue
        # 插到 H1 之后
        idx = next((i for i, l in enumerate(lines) if l.lstrip('\ufeff').startswith('# ')), None)
        if idx is None:
            unmapped.append(base + '（无 H1）')
            continue
        lines.insert(idx + 1, line)
        if write:
            io.open(p, 'w', encoding='utf-8').write('\n'.join(lines))
        changed += 1
    print(f'{"已写入" if write else "[干跑]"}：{len(files)} 篇，需加主题行 {changed} 篇')
    if unmapped:
        print('★未映射（需人工归主题）：')
        for u in unmapped:
            print('   ', u)
    # 主题计数
    cnt = {}
    for p in files:
        t = theme_of(os.path.basename(p))
        cnt[t] = cnt.get(t, 0) + 1
    print('主题分布：' + ' ｜ '.join(f'{k}×{v}' for k, v in sorted(cnt.items(), key=lambda x: str(x[0]))))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
