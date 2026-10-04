# -*- coding: utf-8 -*-
"""append_t052_nameocr.py — ★记录"名称 OCR 识别通道打通（含 ROI/psm 标定与验证）"。"""
import sys

sys.stdout.reconfigure(encoding='utf-8')
p = r'C:\Users\23922\Documents\ds_harness\management\tasks_registry.md'
s = open(p, encoding='utf-8').read()
lines = s.split('\n')
i = next(k for k, l in enumerate(lines) if l.startswith('| T-052 |'))
row = lines[i]
assert row.endswith('|'), row[-20:]

entry = (
 '【第98轮】★★★★★★**干员识别通道打通：读"详情面板名称"的 OCR（含 ROI/psm 标定与实机样本验证）**：'
 '①**依据（用户"借鉴 MAA 实现"的指示）**：MAA 战斗资源含 '
 '`template/Battle/Formation/BattleFormationOCRNameFlag.png` ⇒ **MAA 走 OCR 读名称**，而非匹配头像；'
 '本项目实机亦确认：**点选卡片会弹出干员详情面板，面板标题即大号干员名**；'
 '②**★ROI/psm 标定过程（本轮）**：'
 '初版凭印象取 ROI(60,190,260,268) ⇒ OCR 得 `\'振|丨,\'` 等噪声；'
 '**裁出左侧整块面板（`panel_left.png`）目视定位**，实测「芬」位于原图 ≈**(30..80, 268..312)**；'
 '改为候选 ROI 后实测：**`ROI(20,250,150,330)` + `--psm 6` ⇒ `\'芬imm。mm\'`（含名称）**，'
 '而 **`--psm 7`（单行）全部失败**（得 `\'5\'`/`\'艾\'`）；'
 '③**新增 `code/vision/plugins/recognize/operator_name.py`**：'
 '`read_selected_name(img, candidates)` —— 对 **2 个 ROI × 2 个 psm(6/4)** 组合做 tesseract OCR，'
 '与**候选名单做"包含匹配"**（原始输出有噪声，如 `\'芬imm。mm\'`、`\'儿芬__\'`，但名称在串内），'
 '取最长匹配者；另提供 `read_selected_name_debug()` 便于排查；'
 '④**★实机样本验证（全部正确）**：`live_08_select.png`（芬面板）→ **\'芬\'** ✅；'
 '`live_13_deploy_fang.png`（芬面板）→ **\'芬\'** ✅；'
 '`live_11_final.png`（**未选中任何卡片**）→ **None** ✅（**无误报**）；'
 '⑤**⇒ 卡片选人流程定型（自校验）**：'
 '**(a)** 用费用升序算**候选位次**（`card_plan.json`，可快速定位、但同费用不唯一）；'
 '**(b)** **点卡 → OCR 面板名 → 确认**；若不符则点下一张（最多 n 次）；'
 '**(c)** 确认后执行**两段式拖拽部署**；'
 '⇒ **不依赖头像模板匹配**（该路已实测不可行：头像为"脸部特写"、卡片为"半身"，NCC≈0），'
 '也不单独依赖费用（练度/同费用/局内变动，用户已指出）；'
 '⑥**后续可选升级**：把 tesseract 换成 **MAA `PaddleCharOCR`**（`rec/inference.onnx` + `keys.txt`，'
 '需 `onnxruntime`）以进一步提升鲁棒性；'
 '⑦**合规**：只读本机资源与已存截图；未登录、未消耗资源、未读改游戏文件/内存。 |'
)

lines[i] = row[:-1] + entry
open(p, 'w', encoding='utf-8').write('\n'.join(lines))
print('ok; new row length =', len(lines[i]))
