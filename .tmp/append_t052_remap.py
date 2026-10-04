# -*- coding: utf-8 -*-
"""append_t052_remap.py — 追加"格点映射修正（col 镜像）+ PRTS+ Excel 口径核对"到 T-052 行。"""
import sys

sys.stdout.reconfigure(encoding='utf-8')
p = r'C:\Users\23922\Documents\ds_harness\management\tasks_registry.md'
s = open(p, encoding='utf-8').read()
lines = s.split('\n')
i = next(k for k, l in enumerate(lines) if l.startswith('| T-052 |'))
row = lines[i]
assert row.endswith('|'), row[-20:]

entry = (
 '【第85轮】★★★★★**用户指正：格点映射镜像错误（部署到的是 D4 而非 D6）—— 已按"出怪格子"重新映射并核对 PRTS+ 的 Excel 口径**：'
 '①**用户观察**：「你完成了部署操作，但**你读取的格子和我宣称的 D6 格子不相同**。'
 '**按出怪格子重新映射**，同时**检查 prts+ 如何读取 excel 宏表的格子**」；'
 '②**★根因（col 方向镜像）**：原映射 `x = 1556 − 124.5·col` **令 x 随 col 递减**，'
 '导致 **D6 与 D4 的像素互换**；实机部署落在 (934,502)，按正确口径那其实是 **D4** —— 与用户观察完全一致；'
 '③**★决定性证据一（出怪格子）**：新增 `sim/draft/dump_routes_1_1.py` 打印 1-1 的 routes —— '
 '**route1/3/6/7/8/9/11/13/14: `start=(row3,col0) → end=(row3,col8)`**（横向走廊，自 col0 进入、col8 退出）；'
 '而实机观测敌人**自左向右移动** ⇒ **x 必须随 col 递增**；'
 '④**★决定性证据二（tile 起终点）**：新增 `sim/draft/dump_start_end.py` —— '
 '`tile_start` = **(0,4)、(3,0)**，`tile_end` = **(3,8)、(6,5)**'
 '（`tile_end` 位置与实机画面上的**蓝色终点标记**（右侧 x≈1648、下方 ≈(1080,909)）吻合）；'
 '⑤**★决定性证据三（绿格原点）**：实机绿格 6 连 x=807…1431 + 额外格 (1057,364)；'
 '额外格必为"与 6 连排同列、上一行"的 **road** 格，而 1-1 中只有 **col 4** 在 r1/r2 是 road '
 '⇒ `(1057 − 4×124.5) = 559` = **col 0 的像素**；'
 '⑥**★修正后的唯一真源（新增 `code/vision/plugins/action/grid_px.py`）**：'
 '**`x(col) = 559 + 124.5·col`、`y(row) = 502 + 138·(row−3)`**（row 0 在屏幕上方）'
 '⇒ **D6 = (row3,col5) → (1182,502)**、**D4 = (row3,col3) → (932,502)**；'
 '**自检 11/11 通过**：6 连绿格逐格重投影误差 ≤1px、额外绿格 (2,4)→(1057,364) 完全命中且属 road、'
 'route1 的 x 递增（559→1555，与实机敌人向右移动一致）、D6/D4 像素正确；'
 '⑦**★PRTS+ 如何读 Excel 宏表的格子（用户第二问）**：其实现为 '
 '`code/vision/ak_sim_axis_compat.coord_to_rc(coord, rows, cols, transform)` —— '
 '**字母 = 行**（A→0，支持多字母 26 进制）、**数字 = 列**（1→0），再按 `coord_transform` 施加翻转；'
 '共 8 种变换 `{rc,cr}_{normal,rowflip,colflip,bothflip}`；'
 '**1-1 对应 `rc_normal`**（字母 A = mapData row 0 = 屏幕最上方；数字 1 = col 0 = 屏幕最左）；'
 '该口径与我方 `axis_io.cells_letter_to_rc` 一致 ⇒ **此前错误只在"格→像素"这一步，不在"格子命名"**；'
 '⑧**已接入**：`deploy_two_step.py` / `test_deploy_channels.py` / `bullet_time_probe.py` / '
 '`enemy_track_live.py` 全部改为引用 `grid_px`（消除硬编码），语法校验通过；'
 '⑨**合规**：仅本地计算/只读关卡数据与界面级操作；未登录、未消耗理智、未读改游戏文件/内存。 |'
)

lines[i] = row[:-1] + entry
open(p, 'w', encoding='utf-8').write('\n'.join(lines))
print('ok; new row length =', len(lines[i]))
