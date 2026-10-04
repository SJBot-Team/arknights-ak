# -*- coding: utf-8 -*-
"""append_t052_locate.py — 记录"按名字直接定位卡片（判别性扫描）"。"""
import sys

sys.stdout.reconfigure(encoding='utf-8')
p = r'C:\Users\23922\Documents\ds_harness\management\tasks_registry.md'
s = open(p, encoding='utf-8').read()
lines = s.split('\n')
i = next(k for k, l in enumerate(lines) if l.startswith('| T-052 |'))
row = lines[i]
assert row.endswith('|'), row[-20:]

entry = (
 '【第103轮】★★★★★**根治"卡数/几何"脆性：改为"逐位置扫描 + 判别性分数"直接定位目标干员卡片**：'
 '①**问题**：上一轮实机 11 张卡时头像识别错位（把芬判在卡#3）。本轮先试三种几何方案，**全部脆弱**：'
 '**(a)** 写死 `X_LEFT/pitch`（10 张标定）⇒ 11 张时 pitch 变 165 而失准；'
 '**(b)** 半宽随 pitch 自适应（`pitch×0.47`）⇒ 仍不够；'
 '**(c)** **自动检测卡片列**（列亮度阈值分段）⇒ 10 张只检出 **7 列**（较暗的头像落到阈值下）✗；'
 '**(d)** 用多个已知位次干员的头像做宽域扫描再最小二乘拟合 `x=x0+pitch·i` ⇒ '
 '实测 `芬`(位次0)=228、`月见夜`(位次5)=940、`泡普卡`(位次10)=1832，'
 '两段算出的 pitch 分别是 142 与 178，**互相矛盾** ⇒ 拟合不可靠 ✗；'
 '②**★最终方案（新增 `operator_card.py::locate_operator_card`）**：'
 '**在待部署区整行逐位置扫描"目标干员自己的头像"**（半宽 70/80/90/100 × x 100..1900 步长 4 × y 905..1075），'
 '评分用**判别性分数** `disc = NCC(本人) − max NCC(他人)` —— '
 '既能定位、又天然排除"在错误的卡上匹配到别人"的情形；'
 '**实测（11 张实机截图 `row11.png`）**：芬 x=228 **disc=0.279**、克洛丝 x=408 **disc=0.227**、'
 '月见夜 x=940 **disc=0.189**、泡普卡 x=1832 **disc=0.171**；'
 '另一张实机截图同样全部为正（卡缇 0.218、史都华德 0.226）'
 '⇒ **判别分稳定为正且达 0.17~0.28** ⇒ **不依赖任何 pitch/几何假设**即可可靠识别 ✓；'
 '③**保留的辅助**：`read_selected_name`（名称 OCR，第98轮）作**二次自校验**；'
 '`detect_card_columns`/`identify_deploy_row`/`identify_squad_grid` 保留（编队页仍用其逐卡对齐方案，10/11）；'
 '④**⇒ 待部署区识别链路（当前最优）**：'
 '**`locate_operator_card`（判别性扫描，主判据）→ 若 `disc` 低于阈值则点卡用名称 OCR 复核 → 两段式部署**；'
 '⑤**合规**：仅界面级点击/拖拽与截图 + 只读识别（本机 PRTS+ 资源）；'
 '未登录、全程演习未消耗理智、未读改游戏文件/内存。 |'
)

lines[i] = row[:-1] + entry
open(p, 'w', encoding='utf-8').write('\n'.join(lines))
print('ok; new row length =', len(lines[i]))
