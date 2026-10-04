# -*- coding: utf-8 -*-
"""append_round47.py — 第 47 轮：端到端打通 + MAA/OCR 资源接入 + 封顶静止实机复现。"""
import io
import os
import shutil
import sys

sys.stdout.reconfigure(encoding='utf-8')

DOC = r'C:\Users\23922\Documents\ds_harness\ak\knowledge\04_数据对应与核验\41_模拟器与自动打图_首版实现.md'
REG = r'C:\Users\23922\Documents\ds_harness\management\tasks_registry.md'
DST = r'E:\__file\ak_kb\kb'

SEC = '''
### 7.84 【用户建议】借用 MAA 的现成实现与资源：已接入并验证

用户 2026-09-14 指出"实机操作时，游戏内的导航和识别可以参考借助 MAA 的现成实现和资源"。
本机 `D:\\__soft\\MAA\\resource\\` 有完整资源，实测**直接复用有效**：

#### (1) MAA 的 ROI 是权威坐标（基准 1280×720，本机帧 1920×1080 ⇒ ×1.5）
| MAA 任务 | ROI @1280 | 中心 @1920 | 用途 |
|---|---|---|---|
| `BattleStartPre`（OCR「开始行动/作战/突袭/试炼…」） | `[1000,600,280,120]` | **(1710, 990)** | 「开始行动」按钮 |
| `BattleOfficiallyBegin` | `[1165,20,75,65]` | (1803, 78) | 战斗正式开始标志 |
| `BattleQuickFormation` | `[816,0,404,149]` | (1527, 111) | 快捷编队 |
| `EnterChooseLevelOfDifficulty` | `[0,598,131,122]` | (97, 988) | 选择难度 |

**实测修正**：我此前把「开始行动」点成 `(1659,766)`（那是 `BattleStart` 的 ROI 中心），**y 偏 224px**；
按 MAA 的 `BattleStartPre` 改为 `(1710,990)` 后**点击立即生效**（变化量 48~49）。

#### (2) MAA 模板在**我方实机帧**上直接可用（已用三张真实帧验证）
| 模板 | 命中分 | 位置(1920) |
|---|---|---|
| `Battle/BattleFlag/BattleOfficiallyBegin.png` | **0.995** | (1813, 81) —— 与 ROI 换算 (1803,78) 吻合 |
| `Battle/BattleFlag/BattleCostFlag.png` | **0.880** | **(1772, 776)** —— 正是费用区，与我的 ROI 一致 |
| `Battle/BattleFlag/BattleKillsFlag.png` | 0.853 | (760, 46) —— 击杀数标志 |

⇒ 已落地 `plugins/recognize/maa_anchor.py`（把帧缩到 1280×720 后用 MAA 模板匹配 + ROI，
再 ×1.5 换回帧坐标），并用 `BattleOfficiallyBegin`（0.995）替代我手写的"战斗 HUD 红条"判据。

#### (3) 章节图标模板 `StageNavigation/Episode/NN@EnterEpisodeNew.png` **不适用**
三张完全不同的画面都误命中"第 10 章"（score 0.79~0.887）——章节图标彼此太像，
且 MAA 的 Episode 模板对应的是**另一种界面的章节徽标**，而本机关卡地图底部是**文字标签**
"◀ EPISODE 04 | 当前进度 EPISODE 05 | EPISODE 06"。
⇒ 章节识别应走 **OCR**（MAA 自己的 `ClickStageName` 也是 OcrDetect 全屏找关卡名再点击）。

#### (4) Windows OCR 可用（作为导航的"眼睛"）
`windows_computer_use_ocr` 对 MuMu 窗口直接可用，实测读到：
`EPISODE 04/05/06`、`当前进度`、`OPERATION`、`5-1`、`124/210`(理智) 等，并给出**逐词屏幕坐标**。
**关键校准**：底部章节标签的屏幕 y ≈ 1072~1090（→ 帧 y ≈ 1009~1027），
而我此前一直点帧 y=983（**偏高 26~44px**，落在标签边缘 ⇒ 时好时坏）。

### 7.85 端到端流程打通（导航坐标全部校准）
用"OCR 定位 + adb 点击"逐步把视图校准到 EPISODE 11/12/13，**12-4 节点清晰可见**：
- **12-4 节点 = (1734, 460)**（此前用的 (953,812) 完全错位 —— 这是连续多轮"点击全部落空"的根因）
- 「演习」= **(1441, 983)**；「开始行动」= **(1710, 990)**（MAA 权威值）

修正后 `phase_precision_test.py` 一次跑通全链路：
```
已把模拟器拉到前台（保证渲染）
渲染校验（画面在变）：通过
    → 点 开始行动(编队) (1710,990)：画面变化 48.6 生效
   → 战斗 HUD 已出现（费用 20）
  采样0..7: 费用=20 conf=0.962 相位=29 比例=1.000
```

### 7.86 【实机复现】费用封顶 ⇒ 费用条彻底静止（用户方法一的前提被实测确认）
上述 8 帧采样全部是 `费用 20 / 相位 29 / 比例 1.000`——**恒定**：
该局费用上限就是 20，**条填满后完全不动**，因此"逐对比较"全部落到"封顶，相位不可用"分支，
**没有产生有效样本**。这与 §7.68 的结论一致，也正好印证用户所说：
> "当费用快满时，消耗它，使费用条保持跳动……"

⇒ **下一步（明确）**：在采样窗口内**故意消耗**（部署一个便宜干员，或部署+撤退返还 50%），
把费用从 20 拉回 ~10，制造 10 秒的"条在跳动"窗口，再采 8~10 帧做相位↔墙钟比对（目标 |误差| ≤ 2 帧）。
'''

s = io.open(DOC, encoding='utf-8').read()
anchor = '### 7.83 本轮新增/修改文件'
if anchor not in s:
    raise SystemExit('doc anchor not found')
s = s.replace(anchor, SEC + '\n### 7.87 本轮新增/修改文件', 1)
io.open(DOC, 'w', encoding='utf-8', newline='').write(s)
print('文档已追加 §7.84~§7.86')

r = io.open(REG, encoding='utf-8').read()
ra = '\n\n## 冲突记录'
add = (' **第四十七轮（★端到端打通；借用 MAA 资源；封顶静止实机复现）**：'
       '①**按用户建议借用 MAA 资源**（`D:\\__soft\\MAA\\resource`）：'
       '(a) **MAA 的 ROI 是权威坐标**（基准 1280×720，本机 1920×1080 ⇒ ×1.5）——`BattleStartPre` '
       '`[1000,600,280,120]` → **「开始行动」= (1710,990)**；我此前点 (1659,766)（那是 `BattleStart` 的 ROI 中心）'
       '**y 偏 224px**，改后**点击立即生效**（变化量 48~49）；'
       '(b) **MAA 模板在我方实机帧上直接可用**（三张真实帧验证）：`BattleOfficiallyBegin` **0.995** @ (1813,81)、'
       '`BattleCostFlag` **0.880** @ (1772,776)（正是费用区）、`BattleKillsFlag` 0.853；'
       '已落地 `plugins/recognize/maa_anchor.py`（帧缩到 1280×720 匹配 MAA 模板 + ROI，再 ×1.5 换回）并接管"是否在战斗"判据；'
       '(c) 章节图标模板 `NN@EnterEpisodeNew.png` **不适用**（三张不同画面都误命中第 10 章，且底部其实是文字标签）'
       '⇒ 章节识别走 OCR（MAA 自己的 `ClickStageName` 也是 OcrDetect 全屏找关卡名）；'
       '②**Windows OCR 可用**并给出逐词屏幕坐标，据此校准：底部章节标签帧 y ≈ 1009~1027（我此前点 y=983，**偏高 26~44px**）；'
       '③**端到端打通**：用 OCR 定位 + adb 点击把视图校准到 EPISODE 11/12/13 后，**12-4 节点真实位置 = (1734,460)**'
       '（此前用的 (953,812) 完全错位 —— 这是连续多轮"点击全部落空"的**根因**）；「演习」= (1441,983)、'
       '「开始行动」= (1710,990)；修正后 `phase_precision_test.py` 一次跑通：置前台→渲染校验→点开始行动(生效 48.6)→'
       '**战斗 HUD 出现（费用 20）**→采样 8 帧；'
       '④**实机复现了用户方法一的前提**：8 帧采样全为 `费用20/相位29/比例1.000` **恒定** ⇒ '
       '该局上限 20、**条填满后彻底静止**，"逐对比较"全部落入"封顶不可用"分支，**未产生有效样本** —— '
       '与 §7.68 结论一致，印证"快满时要故意消耗让条保持跳动"；'
       '⑤**下一步**：在采样窗口内故意消耗（部署便宜干员或部署+撤退返还 50%），把费用从 20 拉回 ~10 制造 10s 跳动窗口，'
       '再采 8~10 帧做相位↔墙钟比对（目标 |误差| ≤ 2 帧）；'
       '⑥合规：仅 adb/窗口接口、Windows OCR（屏幕文字）与普通鼠标注入，**不碰游戏内存**；仅演习。 | 2026-09-14 |')
r = r.replace(ra, add + ra, 1)
io.open(REG, 'w', encoding='utf-8', newline='').write(r)
print('台账已追加第四十七轮')

shutil.copy2(DOC, os.path.join(DST, 'knowledge', '04_数据对应与核验', '41_模拟器与自动打图_首版实现.md'))
shutil.copy2(REG, os.path.join(DST, 'management', 'tasks_registry.md'))
for f, sub in (('maa_anchor.py', r'code\vision\plugins\recognize'),
               ('phase_precision_test.py', r'code\vision\apps'),
               ('force_foreground.py', r'code\vision\apps'),
               ('frame_clock.py', r'code\vision\plugins\clock')):
    shutil.copy2(os.path.join(r'C:\Users\23922\Documents\ds_harness\ak', sub.replace('\\', os.sep), f),
                 os.path.join(DST, sub, f))
print('同步完成')
