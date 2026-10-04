# -*- coding: utf-8 -*-
"""update_kb_circle.py — 把"索敌口径=范围外接圆"写入分层登记与结论索引。"""
import io
import sys

sys.stdout.reconfigure(encoding='utf-8')
ROOT = r'C:\Users\23922\Documents\ds_harness\ak\knowledge\04_数据对应与核验'

# ---- 1) 分层登记：新增 L2-08；L1-08 改状态 ----
p = ROOT + r'\60_问题登记_按工作层级.md'
s = io.open(p, encoding='utf-8').read()
if 'L2-08' not in s:
    add = (
        '| L2-08 | **★我方索敌口径（中心距 ≤ 范围外接圆半径）** | ⚠️ **数据判定完成，待用户裁决** | '
        '1-1 数据判定：「索敌 = 中心距 ≤ **攻击范围区域的外接圆半径**」，半径**由范围表导出**'
        '（2 格 ⇒ √(1.5²+0.5²) = **1.5811**）。四口径对照：用户指定口径下 `猎狗` 链 **+25 帧**／'
        '伤害均 **4.50**／最大 **25**；本口径 **−1 帧**／伤害均 **2.06**／最大 **7**；'
        'tol 扫描显示 **1.5811 是数据极值点**。⚠️ **与用户 2026-09-15 明确指定的'
        '「方格范围 + 受击判定体积」语义冲突** ⇒ 默认仍用用户口径，本口径以 '
        '`targeting_model="range_circumradius"` 提供；详见 `61_索敌口径判定_范围外接圆.md` |\n'
    )
    s = s.replace('| L1-08 |', add + '| L1-08 |', 1)
s = s.replace('| L1-08 | **★两观测仍不能同时满足（真正的 OPEN）** | ❌ **OPEN** |',
              '| L1-08 | **★两观测仍不能同时满足** | ⚠️ **已定位到 L2-08（索敌口径）** |')
io.open(p, 'w', encoding='utf-8').write(s)
print('60 分层登记已更新')

# ---- 2) 结论索引：追加 A26 ----
p2 = ROOT + r'\00_结论索引.md'
s2 = io.open(p2, encoding='utf-8').read()
if 'A26' not in s2:
    line = (
        '| A26 | **★★索敌口径 = 中心距 ≤ 攻击范围区域的外接圆半径**'
        '（半径由范围表导出：2 格 ⇒ 1.5811） | 1-1 两条链（猎狗pro 正面 / 猎狗 斜向） | '
        '`cmp_target_models.py`、`sweep_tol_circum.py` | ✅ 两条链同时成立（−3~0 帧与 −1 帧），'
        '伤害平均 4.50→2.06、最大 25→7；tol 扫描显示 1.5811 为数据极值点 | '
        '⚠️ 与用户既有指定语义冲突，**待裁决**；见 `61_索敌口径判定_范围外接圆.md` |\n'
    )
    s2 = s2.rstrip('\n') + '\n' + line
    io.open(p2, 'w', encoding='utf-8').write(s2)
    print('00 结论索引已追加 A26')
else:
    print('A26 已存在，跳过')

# ---- 3) 任务台账 ----
p3 = r'C:\Users\23922\Documents\ds_harness\management\tasks_registry.md'
s3 = io.open(p3, encoding='utf-8').read()
lines = s3.split('\n')
i = next(k for k, l in enumerate(lines) if l.startswith('| T-052 |'))
row = lines[i]
parts = [
 '【第116轮】★★★★★**索敌口径判定的稳健性检验完成 + 知识库沉淀**：',
 '①**★稳健性检验（新增 `sim/draft/sweep_tol_circum.py`）**：扫描索敌半径 tol ∈ [1.0, 2.2] ——',
 '**曲线的极小值恰落在"由范围表导出的 1.5811"**（伤害平均 2.06、最大 7），两侧单调变差',
 '（1.5 ⇒ 2.69；1.62 ⇒ 2.31；1.7 ⇒ 3.67；2.0 ⇒ 8.60）',
 '⇒ **该值不是搜索出来的，而是几何导出且恰为数据极值** ⇒ 支持"外接圆半径"的**机制性**解释，而非拟合巧合 ✓✓；',
 '②**新知识文档 `knowledge/04/61_索敌口径判定_范围外接圆.md`**：完整记录',
 '问题来源（两条链对同一余量要求相反）、**被证伪的四个候选**（受击半径/路径/干员半径外扩/prefab 逐敌差异）、',
 '四口径同场对照表、tol 扫描稳健性表、语义层面的思考，以及**与用户既有指定的冲突标注**；',
 '③**分层登记更新**：新增 **`L2-08 ★我方索敌口径`**（数据判定完成、**待用户裁决**），',
 '并把 **`L1-08` 从 "❌ OPEN" 改为 "⚠️ 已定位到 L2-08（索敌口径）"** ✓；',
 '④**结论索引追加 `A26`**（含证据脚本与"待裁决"标注）✓；',
 '⑤**实现现状**：`targeting_model="range_circumradius"` 已实现（`Battle.range_circumradius(u)`），',
 '**默认仍为`用户指定`的 `grid_plus_hit_volume`**，未擅自更改；',
 '⑥**回归（默认未变，全绿）**：`verify_semantics` A1~A9 ✅、`replay_verify5` 16/16、`replay_axis` 18/18；',
 '⑦**合规**：纯本地模拟计算与只读本机资源；未登录、未消耗资源、未读改游戏文件/内存。 |',
]
entry = ''.join(parts)
lines[i] = row[:-1] + entry
io.open(p3, 'w', encoding='utf-8').write('\n'.join(lines))
print('任务台账第116轮已写入, len =', len(lines[i]))
