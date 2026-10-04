# -*- coding: utf-8 -*-
"""append_t052_cardrec.py — 记录"借用头像库做卡片识别"的摸底与结论。"""
import sys

sys.stdout.reconfigure(encoding='utf-8')
p = r'C:\Users\23922\Documents\ds_harness\management\tasks_registry.md'
s = open(p, encoding='utf-8').read()
lines = s.split('\n')
i = next(k for k, l in enumerate(lines) if l.startswith('| T-052 |'))
row = lines[i]
assert row.endswith('|'), row[-20:]

entry = (
 '【第91轮】★★★★**按用户指示借用 PRTS+/MAA 现成识别工程：找到头像库与干员名映射；实测"半身立绘 vs 脸缩略图"不匹配，并定位到更合适的资产（MAA 的字符 OCR 模型）**：'
 '①**用户指示**：「尝试借鉴 **prts+ 或 maa 已有的识别工程**，识别**干员名对应的头像文件库**，这在 2 者 resource 中均可找到」'
 '（此前我绕道"读卡片费用数字"选卡，属绕远路）；'
 '②**★PRTS+ 侧资产（已找到）**：'
 '`_internal\\resource\\operator_mapping.json` = **927 条「干员名 → [char_id]」**'
 '（如 `"月见夜": ["char_283_midn"]`、`"芬": ["char_123_fang"]`，编队 11 人全部命中）；'
 '`_internal\\resource\\avatar\\char_xxx.png` = **720 张 180×180 方形图**；'
 '③**MAA 侧资产**：`resource/Arknights-Tile-Pos/`（**4177 个**逐关"格子位置+view"JSON，与 PRTS+ 的 map 同构）、'
 '**`resource/copilot/`（作业/轴表自动战斗工程）**、`resource/onnx/`、**`resource/PaddleCharOCR/`（干员名 OCR 模型）**；'
 '④**新增 `code/vision/plugins/recognize/operator_card.py`（头像库卡片识别器）**：'
 '从 `find_cards` 取卡 → 裁卡面 → 与头像库做**零均值归一化互相关**；'
 '因卡片是**脸部特写**而立绘是**半身**，加**立绘内滑窗**（窗边长 45%/60%/80%/100%）取最相似区域；'
 '⑤**实测（离线，用已存实机截图）**：'
 '**(a)** 直接在 **720 人**里选：分数 0.55~0.67 但 **top1−top2 边际仅 0.001~0.03（噪声）**，结果多为编队外干员 ✗；'
 '**(b)** **把候选集限制到"编队 11 人"**（`candidates_from_names`）后边际显著改善：'
 '**卡缇 0.085、安赛尔 0.045、泡普卡 0.055、香草 0.053**（可信），但**芬 0.001、克洛丝 0.003、史都华德 0.001** 仍属噪声；'
 '⑥**结论与下一步（已定位）**：根因是**资产类型不匹配**（`avatar/*.png` 是半身立绘，而战斗卡片用的是**脸部/图标缩略图**）'
 '⇒ 应改用**真正的卡片缩略图资产**，或直接借用 **MAA 的 `PaddleCharOCR`/`onnx`（干员名 OCR 模型）**'
 '—— 后者正是用户所指"已有的识别工程"，下一轮优先试；'
 '⑦**合规**：只读本机 PRTS+/MAA 资源与已存截图；未登录、未消耗资源、未读改游戏文件/内存。 |'
)

lines[i] = row[:-1] + entry
open(p, 'w', encoding='utf-8').write('\n'.join(lines))
print('ok; new row length =', len(lines[i]))
