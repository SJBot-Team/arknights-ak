# -*- coding: utf-8 -*-
"""fix_kb_collider.py — 用本轮"逐敌实测"更正知识库中的碰撞半径记录（旧口径有误）。"""
import io
import sys

sys.stdout.reconfigure(encoding='utf-8')

# ---- 1) 更正 knowledge/04/16 ----
p = r'C:\Users\23922\Documents\ds_harness\ak\knowledge\04_数据对应与核验\16_客户端AB与gamedata差异及碰撞半径.md'
s = io.open(p, encoding='utf-8').read()
old = ('- **敌人**：半径分布 0.1（2037 个）/0.5（124）/1.0（1028）/1.5（84）/2.0（313）/2.5（78）/3.0（36）…'
       '（小怪小半径，精英/BOSS 大半径）')
new = ('- **敌人**：★**2026-09-15 以"逐敌 GameObject 根上的 Collider2D"重测（口径更正）** —— '
       '**2123 个敌人**（38 个 bundle 全解析成功）的实测分布为：\n'
       '  - **`0.1`：2070 个（97.5%）**、`0.09`：1、`0.25`：6、`0.3`：18、`0.35`：1、`0.4`：2、'
       '**`1.48`：2**（`enemy_2119_dyshhj*`）\n'
       '  - ⇒ **原作中"敌人受击半径≈0.1"几乎是普遍实情**，仅极少数例外；\n'
       '  - ⚠️ **旧记录（0.1/0.5/1.0/1.5/2.0/2.5/3.0…，计数上千）口径有误**：'
       '那是把 **非敌人对象/子树/胶囊体**一并计入的结果，**不能用于"逐敌半径"**；\n'
       '  - 数据与可复现脚本：**`ak/data/derived/enemy_colliders.json`**、'
       '**`ak/scripts/export_all_enemy_radii.py`**（UnityPy + `scripts/ak_lz4ak.py` 的 LZ4AK 解压器）。')
if old in s:
    s = s.replace(old, new)
    print('16 号文档：旧的半径分布已更正')
else:
    # 容错：按行前缀替换
    lines = s.split('\n')
    for i, l in enumerate(lines):
        if l.startswith('- **敌人**：半径分布'):
            lines[i] = new
            print('16 号文档：按行前缀更正')
            break
    s = '\n'.join(lines)
io.open(p, 'w', encoding='utf-8').write(s)

# ---- 2) 更新 enemy_hit_radius.json 的数据来源说明 ----
p2 = r'C:\Users\23922\Documents\ds_harness\ak\data\derived\enemy_hit_radius.json'
import json
d = json.load(open(p2, encoding='utf-8'))
d['source']['bulk_export'] = ('ak/data/derived/enemy_colliders.json（2123 个敌人的逐敌 Collider2D 实测；'
                              '生成脚本 ak/scripts/export_all_enemy_radii.py）')
d['note'] = ('逐敌半径以客户端实测为准；**全体分布为 0.1(2070)/0.09(1)/0.25(6)/0.3(18)/0.35(1)/0.4(2)/1.48(2)**，'
             '故"默认 0.1"在原作中近乎实情。1-1 的三种猎狗实测均为 0.1 ✅（与本表一致）。')
json.dump(d, open(p2, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print('enemy_hit_radius.json 的来源说明已更新')

# ---- 3) 任务台账 ----
p3 = r'C:\Users\23922\Documents\ds_harness\management\tasks_registry.md'
s3 = io.open(p3, encoding='utf-8').read()
lines = s3.split('\n')
i = next(k for k, l in enumerate(lines) if l.startswith('| T-052 |'))
row = lines[i]
parts = [
 '【第117轮】★★★★★**批量导出"逐敌实测碰撞半径"（2123 个敌人），并更正知识库中的旧口径记录**：',
 '①**新增 `ak/scripts/export_all_enemy_radii.py`**（UnityPy 1.25.3 + 本仓库 `ak_lz4ak` 的 LZ4AK 解压器）',
 '⇒ **38/38 个 `enm_pfb_*.ab` 全部解析成功**，导出 **2123 个敌人**的逐敌 `Collider2D` 到 '
 '**`ak/data/derived/enemy_colliders.json`**（含 type/radius/size/offset/is_trigger 与按半径分组的索引）；',
 '②**★实测半径分布**（按"敌人 GameObject 根上的 Collider2D"统计）：',
 '**`0.1`：2070 个（97.5%）**、`0.09`：1、`0.25`：6、`0.3`：18、`0.35`：1、`0.4`：2、'
 '**`1.48`：2**（`enemy_2119_dyshhj*`）'
 '⇒ **原作中"敌人受击半径≈0.1"几乎是普遍实情**，仅极少数例外 ✓；',
 '**★三种猎狗（`enemy_1000_gopro` / `_2` / `_3`）实测均为 `radius=0.1, offset=(0,0), is_trigger=True`** '
 '—— 与第107/115轮的结论一致 ✓（再次确认"0.8 拟合值"是错的）；',
 '③**★更正知识库 `knowledge/04/16`**：旧记录「半径分布 0.1(2037)/0.5(124)/1.0(1028)/1.5(84)/2.0(313)/'
 '2.5(78)/3.0(36)」**口径有误** —— 那是把**非敌人对象/子树/胶囊体**一并计入的结果，'
 '**不能用于"逐敌半径"**；已按本轮逐敌实测取代，并写明可复现脚本与数据文件路径；',
 '④**`ak/data/derived/enemy_hit_radius.json`** 的来源说明同步更新（指向批量导出的数据文件）；',
 '⑤**意义**：**"受击判定体积"这一语义（②）从此有了逐敌的客户端实测底座**，'
 '不再依赖"一律 0.1"的近似或任何标定反推 ⇒ 也为后续 >0.1 的特殊敌人（0.25/0.3/0.35/0.4/1.48）'
 '准备了数据；',
 '⑥**合规**：只读本机客户端 AB 备份与本地计算；未登录、未消耗资源、未读改运行中游戏的文件或内存。 |',
]
entry = ''.join(parts)
lines[i] = row[:-1] + entry
io.open(p3, 'w', encoding='utf-8').write('\n'.join(lines))
print('任务台账第117轮已写入, len =', len(lines[i]))
