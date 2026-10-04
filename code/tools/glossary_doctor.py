# -*- coding: utf-8 -*-
"""名词对照「体检」：一次跑完所有结构与规则校验，输出可直接贴进汇报的摘要。

用法：python glossary_doctor.py        （只读，不改任何文件）
检查项：
  1. 每张 tsv 的**列数一致性**与行数
  2. **拼音覆盖率**（第 1 列）
  3. **说明/地址成对性**（第 4/5 列：要么都有、要么都没有）
  4. **overlay 孤儿**（`90_人工补注.tsv` 里指向不存在 ID 的行）
  5. **overlay 自身**：说明 XOR 地址的行（违反"成对"规则）
  6. **重复 ID**（同一张表里主键重复）
"""
import csv
import os
import sys

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
G = r'C:\Users\23922\Documents\ds_harness\ak\glossary'
OVERLAY = os.path.join(G, '90_人工补注.tsv')


def load_tsv(name):
    p = os.path.join(G, name)
    rows = [l.rstrip('\n').split('\t') for l in open(p, encoding='utf-8') if l.strip()]
    return rows[0], rows[1:]


def main():
    tables = sorted(f for f in os.listdir(G) if f.endswith('.tsv') and not f.startswith('90_'))
    all_ids = set()
    problems = []
    print(f'{"表":24} {"行":>5} {"列":>4} {"拼音":>7} {"说明":>5} {"俗称":>5}')
    print('-' * 62)
    for t in tables:
        header, rows = load_tsv(t)
        widths = sorted(set(len(r) for r in rows))
        pinyin = sum(1 for r in rows if r and r[0].strip())
        mean = sum(1 for r in rows if len(r) > 3 and r[3].strip())
        slang = sum(1 for r in rows if len(r) > 5 and r[5].strip())
        print(f'{t:24} {len(rows):>5} {"/".join(map(str, widths)):>4} {pinyin:>7} {mean:>5} {slang:>5}')
        if len(widths) != 1:
            problems.append(f'{t}: 列数不一致 {widths}')
        for i, r in enumerate(rows, 2):
            if len(r) > 4:
                if bool(r[3].strip()) != bool(r[4].strip()):
                    problems.append(f'{t}:{i} 说明/地址不成对（{r[2]}）')
                all_ids.add(r[2])
                if len(r) > 7 and r[7]:
                    all_ids.add(f'{r[7]}.{r[2]}')
        ids = [r[2] for r in rows if len(r) > 2]
        # 主键唯一性只在"ID 是主键"的表上检；02 是别名表（多名对一 ID）、05 要用「分类.键」
        if t.startswith('05_'):
            ids = [f'{r[7]}.{r[2]}' for r in rows if len(r) > 7]
        if t.startswith('02_'):
            ids = []
        dup = {x for x in ids if ids.count(x) > 1} if 0 < len(ids) < 4000 else set()
        if dup:
            problems.append(f'{t}: 重复主键 {sorted(dup)[:5]}')

    # overlay
    if os.path.exists(OVERLAY):
        orows = []
        for line in open(OVERLAY, encoding='utf-8'):
            if not line.strip() or line.startswith('#') or line.startswith('代码层ID'):
                continue
            c = line.rstrip('\n').split('\t')
            orows.append(c + [''] * (5 - len(c)))
        orphan = [c[0] for c in orows if c[0] and c[0] not in all_ids]
        xor = [c[0] for c in orows if bool(c[1].strip()) != bool(c[2].strip())]
        print(f'\noverlay: {len(orows)} 条；孤儿 {len(orphan)}；说明/地址 XOR {len(xor)}')
        if orphan:
            problems.append(f'overlay 孤儿 ID：{orphan[:8]}')
        if xor:
            problems.append(f'overlay 说明/地址不成对：{xor[:8]}')

    print('\n' + ('✅ 全部检查通过' if not problems else '❌ 发现问题：'))
    for p in problems:
        print('  - ' + p)
    return 1 if problems else 0


if __name__ == '__main__':
    sys.exit(main())
