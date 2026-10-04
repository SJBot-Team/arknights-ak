# -*- coding: utf-8 -*-
"""append_t052_marec.py — 记录"MAA/PRTS+ 资产摸底 + 卡片识别两条路均受阻的实测结论"。"""
import sys

sys.stdout.reconfigure(encoding='utf-8')
p = r'C:\Users\23922\Documents\ds_harness\management\tasks_registry.md'
s = open(p, encoding='utf-8').read()
lines = s.split('\n')
i = next(k for k, l in enumerate(lines) if l.startswith('| T-052 |'))
row = lines[i]
assert row.endswith('|'), row[-20:]

entry = (
 '【第92轮】★★★★**MAA/PRTS+ 识别工程摸底完成；"卡片识别"两条路均经实测受阻，并给出可行替代路径**：'
 '①**★MAA 侧资产清单（本轮新增查明）**：'
 '`resource/PaddleCharOCR/det/inference.onnx`(2.4MB) + **`rec/inference.onnx`(9.0MB) + `rec/keys.txt`(285B)** '
 '—— **Arknights 专用文本检测/识别模型（含字符集）**；'
 '**`resource/onnx/operators_det.onnx`(12.2MB)**（**干员检测**）、`skill_ready_cls.onnx`、`deploy_direction_cls.onnx`；'
 '**`resource/copilot/`（作业/轴表自动战斗工程）**、`resource/minitouch/`（自带触摸注入）、'
 '`resource/Arknights-Tile-Pos/`（4177 个逐关"格子位置+view"JSON，与 PRTS+ 的 map 同构）；'
 '②**★路 1：头像库模板匹配 —— 实测不可行**：'
 '新增 `apps/../.tmp/validate_card_match.py` 用**已知顺序的编队截图**（`live_03_squad.png`，'
 '真值顺序 卡缇/安赛尔/芬/泡普卡/安德切尔/月见夜/斑点/香草/玫兰莎/克洛丝/史都华德）做真值验证：'
 '彩色三通道零均值归一化互相关 + 立绘内多尺度滑窗（0.40~1.00）× 候选集限制到编队 11 人 ⇒ '
 '**命中仅 2/11 = 18%**（且反复误判为 安德切尔/香草）⇒ '
 '**根因**：战斗卡片用的是**脸部特写缩略图**，而 `avatar/*.png` 是**半身立绘**，'
 '渲染/裁切/光照差异超出朴素互相关的分辨能力；'
 '③**路 2：读卡片上的费用数字 —— 大数字可行、小标签需另建模板**：'
 '既有 `tpl_h124.json`（视频自举）对**右下大费用数字**有效（本轮多次读得 7/16/21/22/32/99），'
 '但对**卡片上方的小号费用标签**在多个候选 ROI（cx±26/32/40 × y 880~946）下**全部读错**'
 '（读数如 61/870/164/74…）⇒ **小号数字需按其实际字号另行自举模板**；'
 '④**卡片名为何不能用 OCR**：战斗卡片行的**下半部分（含干员名）被屏幕下缘裁掉**，'
 '故 `PaddleCharOCR` 无法直接读卡片名；'
 '⑤**⇒ 可行替代路径（下一轮，按性价比排序）**：'
 '**(a)** 用**卡片小号费用**先按费用分桶（本编队里 芬=8、月见夜=14 **唯一** ⇒ 直接定人），'
 '  重复费用者仅剩 2~3 人再用头像匹配分辨（候选少 ⇒ 边际大）；'
 '**(b)** 试 MAA 的 **`onnx/operators_det.onnx`**（干员检测模型）看其能否直接给出卡片/干员类别；'
 '**(c)** 参考 **MAA `copilot`** 的作业执行实现（它解决同一问题："按作业把指定干员部署到指定格"）；'
 '⑥**合规**：只读本机 MAA/PRTS+ 资源与已存截图；未登录、未消耗资源、未读改游戏文件/内存。 |'
)

lines[i] = row[:-1] + entry
open(p, 'w', encoding='utf-8').write('\n'.join(lines))
print('ok; new row length =', len(lines[i]))
