# -*- coding: utf-8 -*-
"""append_t052_module.py — 记录"头像识别正式模块化 + 接入执行链；11 张几何待标定"。"""
import sys

sys.stdout.reconfigure(encoding='utf-8')
p = r'C:\Users\23922\Documents\ds_harness\management\tasks_registry.md'
s = open(p, encoding='utf-8').read()
lines = s.split('\n')
i = next(k for k, l in enumerate(lines) if l.startswith('| T-052 |'))
row = lines[i]
assert row.endswith('|'), row[-20:]

entry = (
 '【第102轮】★★★★**头像识别正式模块化并接入执行链；实机部署成功但"11 张卡"几何需单独标定**：'
 '①**重写 `code/vision/plugins/recognize/operator_card.py`**（旧失败版备份为 `operator_card_v1_failed.py`）：'
 '按已验证路线实现 —— `OperatorCardMatcher`（PRTS+ `operator_mapping.json` + `avatar/*.png`，'
 '**alpha 掩膜 NCC** 只在 `alpha>32` 像素上比较）+ 三套几何：'
 '**`identify_deploy_row`**（战斗待部署区；中心 `x=139+pitch·(i+0.5)`、`pitch=(1959−139)/n`、'
 '头像区 `y 912..1078`、**半宽随 pitch 自适应 `pitch×0.47`**、每卡 x 局部搜索 ±48）、'
 '**`identify_squad_grid`**（编队页两行；**逐卡对齐搜索**，缺了会从 10/11 掉到 9/11）、`rank`（通用排名）；'
 '**实测**：编队页 **10/11**、战斗待部署区（10 张参考图）**8/10**（NCC 0.31~0.62、边际 0.04~0.23）；'
 '②**新增 `apps/card_select.py::select_card_by_avatar()`**：**单次截屏**即可定位目标干员卡片'
 '（不需点击扫描），并在 `apps/axis_deploy_live.py` 中接入为**首选通道**，'
 '失败再退回第98轮的「**名称 OCR 自校验扫描**」；'
 '③**★实机端到端结果（1-1 演习，全新一场）**：自动导航 7 步进战斗 → 头像识别定位 → 两段式部署 '
 '⇒ **费用 34 → 24，脚本判定「按轴表部署成功」**（确有单位被部署）；'
 '④**但发现问题：11 张卡的实机几何与 10 张参考图不同** —— '
 '在 11 张时头像识别的分数普遍偏低（0.08~0.61）、边际极小（0.003~0.14），'
 '且把「芬」判在**卡#3**（按费用升序应在**卡#0**）⇒ **识别不可靠**；'
 '根因：11 张时 `pitch=165.5`（10 张时 182），卡片更窄，'
 '我的 `X_LEFT/X_RIGHT/头像区 y/半宽` 都是从 **10 张**参考图标的定'
 '（已把半宽改为随 pitch 自适应，但仍不够）⇒ **需按 11 张实机截图单独标定几何**；'
 '⑤**下一步**：**(a)** 存一张**11 张卡的实机截图**（进战斗后立即抓），'
 '用 `measure_row2.py` 式的**宽域搜索**量出 11 张的 `X_LEFT/X_RIGHT/头像 y/半宽`（或按卡框边缘自动检测）；'
 '**(b)** 复跑并目标"战斗区 11/11"；**(c)** 再做「头像识别 + 名称 OCR」双通道互证后的端到端部署；'
 '⑥**合规**：仅界面级点击/拖拽与截图 + 只读识别（本机 PRTS+ 资源）；'
 '未登录、全程演习未消耗理智、未读改游戏文件/内存。 |'
)

lines[i] = row[:-1] + entry
open(p, 'w', encoding='utf-8').write('\n'.join(lines))
print('ok; new row length =', len(lines[i]))
