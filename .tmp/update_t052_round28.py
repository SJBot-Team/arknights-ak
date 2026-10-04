# -*- coding: utf-8 -*-
"""update_t052_round28.py — 把第 28 轮（行坐标轴根因）写入 T-052 台账。"""
import io
import sys

sys.stdout.reconfigure(encoding='utf-8')

P = r'C:\Users\23922\Documents\ds_harness\management\tasks_registry.md'
ADD = (
    ' **第二十八轮（★根因：行坐标轴反了）**：'
    '①从「召唤物 AoE 一次都不触发」一路追到**地图行序搞反**：逐帧统计弦惊四格内敌人几乎全 0 → '
    '敌人占格热力图热点在 (6,4)~(6,8)/(2,1)~(5,4)，与弦惊落点几乎不重叠 → 8 种变换**没有一种**能让全部召唤物落在热点上 → '
    '转而发现「敌人 28s 就走到蓝门、且穿墙走直线」；'
    '②**用关卡自身的门/传送点地块定位根因**：`tile_start` 在 map 数组 (3,0)/(6,0)/(7,0) 而 `routes.startPosition.row=5/2/1`'
    '（恰为 H-1-i）、`tile_end` 在 (0,8)/(0,10)/(0,11) 而 `endPosition=(8,8)/(8,10)/(8,11)`、'
    '`tile_telout`(3,4)↔`APPEAR_AT_POS`(5,4)、`tile_telin`(7,11)↔检查点(1,11)，且实机截图里两个应急储备**并排**出现在屏幕第 3 行'
    '（数据 row=5）⇒ **`mapData.map` 存储行序与关卡 row 相反**；修法：`BattleMap.__init__` 里 `reversed(raw)` 建格点，'
    '此后模拟内部 (row,col) ≡ 关卡坐标，轴表变换随之从 `rc_rowflip` 改为 **`rc_normal`**（`S.COORD_TRANSFORM`）；'
    '③**连带修复**：寻路不再允许穿墙（旧代码把障碍记为有限代价 OBSTACLE_COST=1000，9×13 小图上必然抄近路穿墙）、'
    '斜向贴角卡死（新增 `nav_step_target` 吸附 + `_try_step` 贴墙滑行，此前 9 只敌人永久卡在 (2,1)）、'
    '检查点类型只认 MOVE（补齐 WAIT_FOR_SECONDS/DISAPPEAR/APPEAR_AT_POS 状态机，传送路线 (1,11)→(5,4) 打通）、'
    '应急储备改为「不阻挡/不被敌人攻击、只影响寻路、我方可以打掉换费用上限」（此前敌人把储备拆了，24.7s 白送 +10 上限）、'
    '装置被摧毁后从寻路障碍移除；④**指标诚实化**：`continue_after_fail=True` 会复活战场，'
    '「生命 1/漏怪 61/WIN」是假象，`case_summary` 改为**先跑严格模式**报真实战果；'
    '⑤**修复后现状**：严格模式 **FAIL 生命 0/3 @43.7s**（35 出怪/0 击杀/3 漏怪），对轴模式 50/50 触发、10 击杀、'
    '令 54 次出手、蕾缪安 40 次、上限 53；召唤物 AoE **已经会触发**（某弦惊在令技能窗口内邻格有敌 156 帧、峰值 3 只）；'
    '⑥**遗留断点**：敌人流量时间线仍未与作者记录对齐（需查 WAIT_FOR_SECONDS 与波次 preDelay 是否重复计时——'
    '门口 (1,0) 累计占用 932s；以及 moveSpeed × moveMultiplier=0.5 的实际乘算），弦惊落地仍被费用上限推迟 400~900 帧；'
    '⑦全部回归绿：sim 技能 4/4、案例顺延 PASS、vision costbar/nav_flow/ruler_clock/skill_ready/selftest 全 PASS；'
    '⑧文档：`knowledge/04/41` 新增 §7.45（含两个坐标空间的对照表）、执行端 `configs/axis_h12-4.json` 加坐标空间警示。 '
    '| 2026-09-14 |'
)

s = io.open(P, encoding='utf-8').read()
anchor = ' | 2026-09-14 |\n\n## 冲突记录'
if anchor not in s:
    raise SystemExit('anchor not found')
s = s.replace(anchor, ' | 2026-09-14 |' + ADD + '\n\n## 冲突记录', 1)
io.open(P, 'w', encoding='utf-8', newline='').write(s)
print('T-052 已追加第二十八轮；文件行数 =', len(s.splitlines()))
