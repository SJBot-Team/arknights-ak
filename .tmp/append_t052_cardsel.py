# -*- coding: utf-8 -*-
"""append_t052_cardsel.py — 记录"结构性选卡已验证 + 卡片像素定位与更优识别通道"。"""
import sys

sys.stdout.reconfigure(encoding='utf-8')
p = r'C:\Users\23922\Documents\ds_harness\management\tasks_registry.md'
s = open(p, encoding='utf-8').read()
lines = s.split('\n')
i = next(k for k, l in enumerate(lines) if l.startswith('| T-052 |'))
row = lines[i]
assert row.endswith('|'), row[-20:]

entry = (
 '【第96轮】★★★★★**结构性选卡端到端落地：`CardPlan` 导出 → 离线验证与实机逐项一致；并查明卡片像素定位与更优识别通道**：'
 '①**导出**：`sim/draft/card_index.py --export` ⇒ `ak/data/derived/card_plan.json`'
 '（含 `squad` 费用表、`order` 费用升序名单、`costs_sorted`、`talent_cost`）'
 '—— 打图侧为独立 venv，**用 JSON 交互避免跨环境导入**；'
 '②**★离线验证（新增 `apps/verify_card_index.py`）**：'
 '对实机截图 `axisdep_D6.png`（芬已部署）—— 计划 `order` 去掉已部署者后的**费用序列 = '
 '[9,9,9,13,14,15,15,16,16,17]**，与**实机目视卡片费用逐项一致** ✅；'
 '`月见夜` 位次 = 4（该位次费用 14 ✓）；'
 '③**接入 `apps/axis_deploy_live.py`**：按 `axis yaml` 的 **`op` 名** → `card_index_for()` 定位卡片位次 '
 '（不再读费用数字、不再做头像识别）；'
 '④**★新发现的坑与对策**：`Deployer.find_cards` **分段不稳**（同一张 10 卡截图，'
 '一次检出 10 段、另一次只检出 **7** 段；最左一张常被漏检）⇒ 直接按"第 idx 段"取卡会**错位**；'
 '新增 `fit_card_grid()`：以"卡行 x 范围 + 张数 n"为初值、用检测值做**最小二乘**拟合等间距网格；'
 '但实测**当最左卡被漏检时拟合会整体错位**（得中心 317…1926，末位越界）⇒ **仍需更稳的锚点**；'
 '⑤**★★下一步更优通道（已确认可行）**：**点选卡片会弹出干员详情面板，面板上「干员名」是大号清晰文字**'
 '（本项目实机多次见到，如面板标题「芬」）⇒ **用"点卡→读面板名"来确认卡片身份**，'
 '比卡片缩略图匹配可靠得多；可配 **MAA 的 `PaddleCharOCR`**（Arknights 专用 rec 模型 + `keys.txt`）读取；'
 '⑥**另备锚点方案**：用**卡片上的费用数字标签位置**或**职业图标**做锚（等间距网格的起点可靠化）；'
 '⑦**合规**：只读本机资源与已存截图；未登录、未消耗资源、未读改游戏文件/内存。 |'
)

lines[i] = row[:-1] + entry
open(p, 'w', encoding='utf-8').write('\n'.join(lines))
print('ok; new row length =', len(lines[i]))
