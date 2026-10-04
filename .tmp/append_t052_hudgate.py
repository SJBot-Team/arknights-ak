# -*- coding: utf-8 -*-
"""append_t052_hudgate.py — 追加"战斗 HUD 门控 + 费用条通道诊断"到 T-052 行。"""
import sys

sys.stdout.reconfigure(encoding='utf-8')
p = r'C:\Users\23922\Documents\ds_harness\management\tasks_registry.md'
s = open(p, encoding='utf-8').read()
lines = s.split('\n')
i = next(k for k, l in enumerate(lines) if l.startswith('| T-052 |'))
row = lines[i]
assert row.endswith('|'), row[-20:]

entry = (
 '【第75轮】★★★★★**实现"战斗 HUD 门控"并接入费用条时钟；顺带诊断出"实机费用条通道尚未打通"**：'
 '①**新增 `code/vision/plugins/recognize/battle_hud.py::BattleHudGate`**：三路信号 —— '
 '**A 底部待部署卡片行**（`Deployer.find_cards`，≥7 段）、**B 费用数字 ROI 亮字形**（≥2%）、'
 '**C 顶部 `ENEMY x/N` 亮像素**（≥1%）；**三者全部成立**才判"在战斗中"；'
 '②**新增回归 `apps/test_battle_hud.py`（本机 9 个实机截图样本，全部通过）**：'
 '战斗中 4 例（live_07/23/08/11）全判 True；非战斗 5 例（**任务失败 live_24**、行动结束 live_26、'
 '关卡详情 live_02、编队 live_03、主界面 live_home）全判 False；'
 '并含**端到端佐证**：失败页上 `CostBarRecognizer` 给出 `frame=26` 的伪读数，而门控判为"非战斗" ⇒ 被拦下；'
 '★过程中发现"只要求 A+其中一路"会把**主界面**误判为战斗（其底部也有一排按钮被分成 6 段、'
 '费用 ROI 处也有亮字）⇒ 收紧为**三路全需**；'
 '③**把门控接入 `plugins/clock/cost_ruler.py::CostBarClock`**：默认 `require_battle=True`'
 '（spec 可关），不在战斗中则 `ok=False`、**绝对帧不推进**；'
 '新增回归 `apps/test_clock_gate.py`（全部通过）：非战斗 3 例被拦下且 `elapsed` 不推进；'
 '战斗 2 例正常放行；**反证**——关闭门控后同一失败页的伪读数（frame=26）会被当有效读数采信；'
 '④**★★更深一层的诊断（重要，修正既有认知）**：对实机战斗截图逐项核对发现 —— '
 '**(a)** `CostBarRecognizer` 返回 **`fill_px=1920`、`roi_w=1920`**（= **整幅宽度**）'
 '⇒ **传入的 ROI 未被应用**；**(b)** `total_frames=None` 且 `frame=30` ⇒ **无标定文件时的默认值**；'
 '**(c)** 配置里引用的标定文件 `D:\\__soft\\ak\\ArknightsCostBarRuler-v2.3.2\\...\\profile_30fps.json` '
 '**经 Test-Path 确认并不存在**；'
 '**(d)** 直接按亮度量测：实机费用条**轨道 x≈1740→1872、y≈809–817**，当前**填充 ≈44%**（≈帧 13），'
 '与识别器给出的"满条(30)"**明显不符**；'
 '⇒ **结论：实机侧"费用条像素→帧"通道尚未真正打通**；'
 '**我们此前用于构建"视频↔游戏帧轴"的是自写的视频侧费用条测量**（`apps/video_hud_scan.py` 等，'
 '并有费用数字通道交叉验证），**与本插件不是同一套代码**，不可混为一谈；'
 '⑤**下一步（已明确）**：**(a)** 修 `CostBarRecognizer` 的 ROI 解析（当前 `roi_w=1920` 说明未生效）；'
 '**(b)** 用实测几何**直接生成 30fps 标定**（`pixel_map`：0px→帧0、132px→帧30；'
 '或按实测轨道长与 180px 口径统一）；**(c)** 用"填充比例 ↔ 费用数字跳变"两端对齐验证；'
 '**(d)** 再回到用户流程的第①步（满条计数）与②③④（子弹时间/过帧/暂停定位）；'
 '⑥**合规**：仅图形界面级点击与截图 + 只读识别；未登录、未消耗理智、未读改游戏文件/内存。 |'
)

lines[i] = row[:-1] + entry
open(p, 'w', encoding='utf-8').write('\n'.join(lines))
print('ok; new row length =', len(lines[i]))
