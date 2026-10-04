# -*- coding: utf-8 -*-
"""probe_projectile.py — 查"弹道/投射物"相关字段（远程攻击的命中时机依赖它）

## 依用户 2026-09-15 的补充
> 「远程攻击需要考虑是否为存在弹道的远程攻击。如果为弹道，**子弹出现的位置
>  （同干员不同皮肤可能不同）**、**子弹和敌人的追击过程**均需要被考虑。」

**⟹ 对本方模拟器的直接含义**：
- **近战（如芬）**：出手 → （前摇）→ 立即命中；
- **远程（如月见夜）**：出手 → （前摇）→ **生成子弹（位置依干员/皮肤）** →
  **子弹飞向目标（追击过程，含飞行时间）** → **到达才结算命中**。
⇒ 因此"远程命中"的时刻会**晚于出手**，且**与距离相关**；
这正是标定「438 月见夜 远程命中」这类事件不能被"出手帧"直接代表的原因。

## 本脚本
在数据层查找承载"弹道"的字段（如 `projectileId`、`launchProjectile`、`projectile` 等），
并检查干员/皮肤的差异来源（`skin_table` / `characterPrefabKey` / `phases`）。
"""
from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding='utf-8')

from ak_sim import data as D            # noqa: E402

MIDN = 'char_283_midn'      # 月见夜（远程命中出现在标定表里）
FANG = 'char_123_fang'

WORDS = ('projectile', 'bullet', 'missile', 'shoot', 'launch', 'arrow', 'trajectory',
         'fly', 'speed', 'range')


def scan(obj, prefix='', depth=0, maxd=5, out=None):
    if out is None:
        out = []
    if depth > maxd:
        return out
    if isinstance(obj, dict):
        for k, v in obj.items():
            path = f'{prefix}.{k}' if prefix else k
            if any(w in k.lower() for w in WORDS):
                out.append((path, v))
            scan(v, path, depth + 1, maxd, out)
    elif isinstance(obj, list) and obj and depth < maxd:
        scan(obj[0], f'{prefix}[0]', depth + 1, maxd, out)
    return out


def main():
    print('=== 一、干员表：弹道相关字段 ===')
    ct = D.load_table('character_table.json')
    for cid, label in ((MIDN, '月见夜(远程)'), (FANG, '芬(近战)')):
        c = ct.get(cid)
        print(f'\n  [{label}] {cid}')
        hits = scan(c)
        if not hits:
            print('    （未找到 projectile/bullet 等字段）')
        for p, v in hits[:12]:
            print(f'    {p} = {str(v)[:100]}')

    print('\n=== 二、技能/天赋里的弹道字段（月见夜）===')
    for tbl_name in ('skill_table.json', 'character_table.json'):
        try:
            t = D.load_table(tbl_name)
        except Exception as e:
            print(f'  [{tbl_name}] 失败 {e}')
            continue
        s = json.dumps(t, ensure_ascii=False)
        for kw in ('projectileId', 'launchProjectile', 'projectile', 'Projectile'):
            n = s.count(kw)
            if n:
                print(f'  [{tbl_name}] 含 "{kw}" {n} 处')
                i = s.find(kw)
                print(f'      示例: …{s[max(0,i-60):i+90]}…')

    print('\n=== 三、皮肤表（验证"子弹位置依皮肤"的来源）===')
    for tbl_name in ('skin_table.json', 'charword_table.json'):
        try:
            t = D.load_table(tbl_name)
            n = len(t) if hasattr(t, '__len__') else '?'
            print(f'  [{tbl_name}] 可读，键/条目数 {n}')
        except Exception as e:
            print(f'  [{tbl_name}] 读取失败: {e}')

    print('\n=== 四、模拟器当前是否处理弹道 ===')
    import inspect
    from ak_sim.engine import Battle
    src = inspect.getsource(Battle)
    for kw in ('projectile', 'bullet', 'flying_dmg', 'pending_damage'):
        cnt = src.lower().count(kw)
        print(f'  {kw}: {cnt} 处')


if __name__ == '__main__':
    main()
