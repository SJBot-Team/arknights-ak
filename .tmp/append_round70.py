# -*- coding: utf-8 -*-
"""append_round70.py — 第 70 轮：打通 PRTS+ 运行链路（参数/路径），失败点定位到编队不匹配。"""
import io
import os
import shutil
import sys

sys.stdout.reconfigure(encoding='utf-8')

DOC = r'C:\Users\23922\Documents\ds_harness\ak\knowledge\04_数据对应与核验\41_模拟器与自动打图_首版实现.md'
REG = r'C:\Users\23922\Documents\ds_harness\management\tasks_registry.md'
DST = r'E:\__file\ak_kb\kb'

SEC = '''
### 7.171 【打通】赛博塑料（PRTS+）的运行链路与失败点定位

用户 2026-09-14 切换好界面并授权直接运行，且提示"**注意选择干员界面开始的选项**"。
本轮把它的运行方式与失败点都查清了：

#### (1) 命令行接口（`--help` 暴露）
```
usage: prts+.exe [-h] [--xlsm XLSM] [--debug] [--autoenter]
```
- `--xlsm <路径>`：传入轴表（**必须**，否则它试图打开 `None` 而报错）；
- **`--autoenter`：从"干员界面（编队）"开始自动进关** ← 即用户提示的那个选项；
- `--debug`：调试输出。

#### (2) 中文路径问题
首次运行报 `Excel file not found, opening E:\\__file\\������\\...` ——
**PowerShell 传参把中文路径打坏了**。解决：把轴表复制到**纯 ASCII 路径**
`D:\\__soft\\ak\\prts_plan_h124.xlsm`（副本，避免污染原表；PRTS+ 会写「运行结果」列）。

#### (3) 运行现象（在**演习中的战斗**里，零理智风险）
```
INFO  - Found the game window with handle 7801904, parent handle 983350.    ← 抓我们的 render_wnd
WARN  - Excel file not found, opening D:\\__soft\\ak\\prts_plan_h124.xlsm    ← 路径已正确传入
ERROR - Could not find a good matching avatar for 令, with max_val: 0.6118546
ERROR - Error occurred: 当前未在待部署区找到干员。
```
- **它确实成功加载了轴表**（`opening ...prts_plan_h124.xlsm`）✓；
- **失败点在编队**：它要在**待部署区**匹配轴表里第一个干员**「令」的头像**，
  最高匹配度只有 **0.61**（未达其阈值）⇒ 报"未在待部署区找到干员"。
- 当前这局的编队（从截图看费用 3/8/8/10/20 的粉色、棕色、灰蓝、蓝色、金发干员）
  **不含令**，因此它的整条流程无法开始。

#### (4) 结论与需要的前提
**PRTS+ 能跑通的前提是"编队与轴表一致"**（轴表第一个干员是令、随后蕾缪安、弦惊…）。
⇒ 需要把编队换成**作者那套（含令、蕾缪安）**并进入战斗（**演习**即可，零理智风险），
之后它才能开始按轴表操作；届时即可**并排读它的内部计时（绝对时间/帧数）与我们的图像识别结果**，
直接观察"费用满时它怎么记"（用户猜测：比实际跳动次数多记一秒）。

### 7.172 本轮新增
`sim/draft/drive_prts_plus.py`（交互式驱动与日志捕获，备用）。

### 7.173 断点
1. **需要用户把编队换成"含令、蕾缪安"的作者编队并进入演习**（或授权在实战中运行）；
2. 一旦其流程能跑起来，即可做"**它的计时 vs 我们的识别**"并排对照，
   验证"费用满 ⇒ 多记/少记一次"的方向；
3. 可先备好对照脚本：读 Excel 的「费用/帧数/绝对时间」列 + 同时用费用尺读画面相位，
   两者对齐到同一帧序列。
'''

s = io.open(DOC, encoding='utf-8').read()
anchor = '### 7.170 本轮新增/修改文件'
if anchor not in s:
    raise SystemExit('doc anchor not found')
s = s.replace(anchor, SEC + '\n### 7.174 本轮新增/修改文件', 1)
io.open(DOC, 'w', encoding='utf-8', newline='').write(s)
print('文档已追加 §7.171~§7.173')

r = io.open(REG, encoding='utf-8').read()
ra = '\n\n## 冲突记录'
add = (' **第七十轮（打通 PRTS+ 运行链路；失败点定位到编队不匹配）**：'
       '①**命令行接口查明**：`usage: prts+.exe [-h] [--xlsm XLSM] [--debug] [--autoenter]`，'
       '其中 **`--autoenter` 即用户提示的"从干员界面（编队）开始自动进关"**；'
       '②**中文路径问题**：PowerShell 传参把中文路径打坏（`E:\\__file\\������\\...`）⇒ '
       '把轴表复制到 **ASCII 路径 `D:\\__soft\\ak\\prts_plan_h124.xlsm`**（副本，避免污染原表）后它成功加载；'
       '③**运行现象**（在**演习中的战斗**里，零理智风险）：`Found the game window with handle 7801904`（= 我们的 render_wnd ✓）、'
       '`Excel file not found, opening D:\\__soft\\ak\\prts_plan_h124.xlsm`（路径已正确传入 ✓）；'
       '**失败点**：`Could not find a good matching avatar for 令, with max_val: 0.6118546` → '
       '`当前未在待部署区找到干员。` ⇒ 它要在**待部署区**匹配轴表第一个干员**「令」的头像**，'
       '而当前编队不含令（最高匹配 0.61 未达阈值），整条流程无法开始；'
       '④**结论**：**PRTS+ 跑通的前提是"编队与轴表一致"**（令→蕾缪安→弦惊…）⇒ '
       '需把编队换成作者那套（含令、蕾缪安）并进入战斗（**演习**即可、零理智风险），'
       '之后才能并排读它的内部计时（绝对时间/帧数）与我们的图像识别结果、观察"费用满时它怎么记"；'
       '⑤新增 `sim/draft/drive_prts_plus.py`（交互式驱动与日志捕获，备用）；'
       '⑥合规：全程在**演习**中运行，未消耗理智；未触碰游戏内存/文件。 | 2026-09-14 |')
r = r.replace(ra, add + ra, 1)
io.open(REG, 'w', encoding='utf-8', newline='').write(r)
print('台账已追加第七十轮')

shutil.copy2(DOC, os.path.join(DST, 'knowledge', '04_数据对应与核验', '41_模拟器与自动打图_首版实现.md'))
shutil.copy2(REG, os.path.join(DST, 'management', 'tasks_registry.md'))
shutil.copy2(r'C:\Users\23922\Documents\ds_harness\ak\sim\draft\drive_prts_plus.py',
             os.path.join(DST, 'sim', 'draft', 'drive_prts_plus.py'))
print('同步完成')
