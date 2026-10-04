# -*- coding: utf-8 -*-
"""把「人工补注」（ak\\glossary\\90_人工补注.tsv）套用到批量表上。

为什么需要它：批量表是 `glossary_build.py` **生成**的，直接手改 tsv 会在下次重跑时被覆盖。
本脚本把 90_人工补注.tsv 当作**持久真源**，在生成之后把第 4/5/6 列（一句话说明 / 知识库地址 / 玩家俗称）填回去。**幂等**。

用法：
  python glossary_backfill.py            # 干跑：只报告将写入多少行
  python glossary_backfill.py --apply    # 实际写入（原地修改 0*.tsv，写入前备份到 ak\\.tmp\\）
"""
import argparse
import csv
import os
import shutil
import sys
import time

AK = r'C:\Users\23922\Documents\ds_harness\ak'
G = os.path.join(AK, 'glossary')
OVERLAY = os.path.join(G, '90_人工补注.tsv')
TMP = os.path.join(AK, '.tmp')
TABLES = ['01_干员.tsv', '01a_装置与陷阱.tsv', '02_干员名别名.tsv', '03_敌人.tsv',
          '04_关卡.tsv', '05_枚举词典.tsv', '06_攻击范围.tsv', '07_职业与分支.tsv',
          '08_PRTS_Buff事件.tsv', '09_模组与天赋.tsv']


def load_overlay():
    rows = []
    with open(OVERLAY, encoding='utf-8') as f:
        for line in f:
            if not line.strip() or line.startswith('#'):
                continue
            cells = line.rstrip('\n').split('\t')
            if cells[0] == '代码层ID':
                continue
            if len(cells) < 4:
                continue
            rows.append({
                'id': cells[0].strip(),
                'meaning': cells[1].strip(),
                'address': cells[2].strip(),
                'slang': cells[3].strip(),
                'note': cells[4].strip() if len(cells) > 4 else '',
            })
    return rows


def main():
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass
    ap = argparse.ArgumentParser()
    ap.add_argument('--apply', action='store_true')
    a = ap.parse_args()

    overlay = load_overlay()
    by_id = {r['id']: r for r in overlay if r['id']}
    print(f'补注条目 {len(overlay)} 条（唯一 ID {len(by_id)} 个）')

    # 规则校验：说明与地址必须成对
    bad = [r['id'] for r in overlay if bool(r['meaning']) != bool(r['address'])]
    if bad:
        print(f'  [!] 违反"说明/地址成对"规则的行：{bad}（这些行不会被套用）')

    total_filled = 0
    for name in TABLES:
        path = os.path.join(G, name)
        if not os.path.exists(path):
            continue
        with open(path, encoding='utf-8') as f:
            rows = [l.rstrip('\n').split('\t') for l in f if l.strip()]
        header, body = rows[0], rows[1:]
        changed = 0
        for r in body:
            if len(r) < 7:
                continue
            # 支持两种写法：① 直接用「代码层ID」；② 用「分类.键」（枚举表专用，如 abnormal.STUNNED）
            o = by_id.get(r[2])
            if not o and len(r) > 7 and r[7]:
                o = by_id.get(f'{r[7]}.{r[2]}')
            if not o:
                continue
            # 「说明 / 地址」必须成对（用户 2026-09-23 规则）；「俗称」可单独存在
            before = (r[3], r[4], r[5])
            if o['meaning'] and o['address']:
                r[3] = o['meaning']
                r[4] = o['address']
            elif o['meaning'] or o['address']:
                print(f'  [!] {o["id"]}: 说明/地址不成对，已跳过该两列')
            if o['slang'] and o['slang'] != '—':
                r[5] = o['slang']
            if (r[3], r[4], r[5]) != before:
                changed += 1
        if changed:
            total_filled += changed
            print(f'  {name}: 将回填 {changed} 行')
            if a.apply:
                os.makedirs(TMP, exist_ok=True)
                shutil.copy2(path, os.path.join(TMP, f'{name}.before_backfill_{time.strftime("%H%M%S")}'))
                with open(path, 'w', encoding='utf-8', newline='\n') as f:
                    f.write('\t'.join(header) + '\n')
                    for r in body:
                        f.write('\t'.join(r) + '\n')
        else:
            print(f'  {name}: 无需回填（或该表无匹配 ID）')

    print(f'合计待回填 {total_filled} 行' + ('（已写入）' if a.apply else '（干跑，未写入；加 --apply 生效）'))
    # 未被任何表命中的补注
    ids_in_tables = set()
    for name in TABLES:
        p = os.path.join(G, name)
        if not os.path.exists(p):
            continue
        with open(p, encoding='utf-8') as f:
            next(f, None)
            for l in f:
                c = l.rstrip('\n').split('\t')
                if len(c) > 2:
                    ids_in_tables.add(c[2])
                    if len(c) > 7 and c[7]:          # 枚举表：同时登记「分类.键」
                        ids_in_tables.add(f'{c[7]}.{c[2]}')
    orphan = [i for i in by_id if i not in ids_in_tables]
    if orphan:
        print(f'  [!] 补注里有 {len(orphan)} 个 ID 不在任何表中：{orphan[:10]}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
