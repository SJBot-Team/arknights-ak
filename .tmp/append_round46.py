# -*- coding: utf-8 -*-
"""append_round46.py — 第 46 轮：官方像素↔帧标定表接入 + 导航与判据修复 + 方法论口径纠正。"""
import io
import os
import shutil
import sys

sys.stdout.reconfigure(encoding='utf-8')

DOC = r'C:\Users\23922\Documents\ds_harness\ak\knowledge\04_数据对应与核验\41_模拟器与自动打图_首版实现.md'
REG = r'C:\Users\23922\Documents\ds_harness\management\tasks_registry.md'
DST = r'E:\__file\ak_kb\kb'

SEC = '''
### 7.78 【用户点明】费用尺的"像素长度 ↔ 精确帧"标定表：已找到并接入

用户 2026-09-14 指出："费用尺应当包含完整的费用条相对长度与精确帧的比对信息，可以直接用来参考，
遇到问题再实测修改。" 按此在本地 CostRuler 副本里找到了标定档：

`D:\\__soft\\ak\\cost_ruler\\ArknightsCostBarRuler\\calibration\\profile_1767884246_30f_1920x1080.json`
```json
{"detection_mode":"single","profiles":[{"total_frames":30,"pixel_map":{
 "0":0,"6":1,"13":2,"19":3,"25":4,"31":5,"38":6,"44":7,"50":8,"56":9,"63":10,"69":11,"75":12,
 "81":13,"87":14,"94":15,"100":16,"106":17,"112":18,"119":19,"125":20,"131":21,"137":22,
 "144":23,"150":24,"156":25,"162":26,"169":27,"175":28,"180":29}}],
 "screen_width":1920,"screen_height":1080}
```
同目录另有 `profile_1769254296_60f_1920x1080.json`（`total_frames: 60`，3px→2帧、6→3…），
以及配置 `type: mumu`、`frame_display_mode: 0_to_n`。

**关键推论与自校验**：该表的最大键是 **180px**，即费用条总宽 180px（每帧约 6.2px）。
而我在自己 MuMu 1920×1080 上实测的条亮列范围是 **1739–1919 = 180px** —— **完全吻合** ✓
⇒ 条左端 `BAR_LEFT_X_1920 = 1739`、总宽 `BAR_WIDTH_PX_1920 = 180` 可直接采用。

**已接入**：`plugins/clock/frame_clock.py` 增加 `PIXEL_MAP_30F` / `PIXEL_MAP_60F` 常量与
`frame_from_width(px, pixel_map)`，**由"比例×30"的线性近似改为查表**（表本身是非线性的：每帧 6~7px 不等）。
`phase_precision_test.py` 的相位计算已改走查表，并把条 ROI 对齐到 `(1739, 805, 1919, 818)`。

### 7.79 导航与判据修复（本轮实测踩到的四个坑）

| 坑 | 现象 | 修复 |
|---|---|---|
| ①窗口失去前台 → 游戏挂起 | 点击后画面变化**精确 0.0**、adb 帧缓冲恒定 | `bring_to_front` 改为**强制跳层**：`SW_RESTORE` → `SetWindowPos(HWND_TOPMOST)` → `SetWindowPos(HWND_NOTOPMOST)` → `SetForegroundWindow`；四种手段（含 `AttachThreadInput` 破解前台锁）实测**都报"置前成功"**，随后点击普遍恢复生效（变化量 40~180） |
| ②章节跑偏 | 游戏停在 **EPISODE 09** 地图，于是 H12-4 坐标全是空点、`squad` 判据误命中 | 实测底部导航：**章节标签** `(1734,983)`（EPISODE 10）点击**有效**、**▶ 右箭头** `(1801,983)`；先前猜的 `(1603,983)` 其实是**当前高亮的 EPISODE 09**（点了当然没反应） |
| ③"开始行动后没有等加载" | 点"开始行动"生效（变化 101）后又继续判界面 → 把**刚进的战斗退出去** | 点"开始行动(编队)"成功后进入**等待战斗 HUD**循环（≤30s） |
| ④结算画面的"点击继续"坐标错 | 提示文字在**底部**而不是中央 | 结算/加载的继续点击由 `(960,540)` 改为 `(960,988)` |

### 7.80 判据纠错：**"能读到数字" ≠ "在战斗"**

脚本一度报告"已在战斗（费用 56/57，conf 0.94）"，实际画面是**「任务失败 / MISSION FAILED」结算画面**——
高置信度数字可以来自**任何 UI**（EPISODE 编号、节点编号、理智值…）。
⇒ 已把"是否在战斗"的判据改为 **战斗 HUD 特征**：顶部中央那根**红色敌人计数条**
（ROI `[10:72, 900:1380]`，红色像素占比 > 0.05），并新增**结算画面判定**
（中央偏左 `[250:400, 300:700]` 的高亮占比 > 0.12）走"点击继续"分支。

### 7.81 【用户给的验证口径】图像识别只用于确定"事件发生在哪一帧"

用户 2026-09-14 明确："由于动画层表现不严格对齐游戏底层储存的数据，单位的实际坐标和动画位置的关系
是不能统一被确定的，后续同模拟环境验证时，通过图像识别，我们仅可以确定事件是在哪一帧发生的，
以此对游戏实机同游戏解包信息、模拟环境做比对获取信息，比如，单位出生的精确帧、血条变动即造成伤害的精确帧、
攻击力面板等变化的精确帧等，核实事件发生的精确时间。坐标的实机检验很困难，这也是通过游戏解包尝试搭建
精确模拟环境的必要原因之一。"

⇒ 这条**改变了验收口径**，应作为后续所有实机比对的准则：
- **能（且只应）用图像识别的**：事件的**精确帧**——单位出生、血条变动（=造成伤害的那一帧）、
  面板/费用变化等，用它们与"解包数据 + 模拟环境"预测的事件帧**逐一对齐**；
- **不应指望图像识别的**：单位实际坐标、动画位置；坐标只能由解包数据 + 模拟环境给出，
  实机坐标检验因动画层与逻辑层不对齐而不可靠。

### 7.82 本轮未完成（断点）
导航仍不够稳：多次运行中仍会出现"连续三次点击 0.0"——
最可能是**画面处于加载/过渡状态时点击本就无效**（我此前用"快速重试"应对，应当改为"先等画面稳定再点"）。
⇒ 下一步：给导航加**稳定等待**（连续 N 帧差异 < 阈值即认为该界面已加载完成）再执行点击；
之后才可能拿到成对的「相位 ↔ 墙钟」样本，完成 §7.70 的精度比对与 §7.62 的暂停闭环。
'''

s = io.open(DOC, encoding='utf-8').read()
anchor = '### 7.77 本轮新增/修改文件'
if anchor not in s:
    raise SystemExit('doc anchor not found')
s = s.replace(anchor, SEC + '\n### 7.83 本轮新增/修改文件', 1)
io.open(DOC, 'w', encoding='utf-8', newline='').write(s)
print('文档已追加 §7.78~§7.82')

r = io.open(REG, encoding='utf-8').read()
ra = '\n\n## 冲突记录'
add = (' **第四十六轮（官方像素↔帧标定表接入；导航与判据修复；方法论口径纠正）**：'
       '①**用户点明"费用尺应含完整的费用条相对长度与精确帧的比对信息"** → 在本地 CostRuler 副本里找到 '
       '`calibration/profile_1767884246_30f_1920x1080.json` 的 **`pixel_map`（0px→0帧 … 180px→29帧）**，'
       '另有 60 帧版本；**自校验**：表最大键 180px = 费用条总宽，与我方实测条亮列 1739–1919（=180px）**完全吻合** ⇒ '
       '已接入 `frame_clock.PIXEL_MAP_30F` + `frame_from_width()`，**由"比例×30"线性近似改为查表**，'
       '条 ROI 对齐 `(1739,805,1919,818)`；'
       '②**导航四个坑与修复**：(a) 窗口失去前台→游戏挂起（点击后画面精确 0.0）⇒ `bring_to_front` 改**强制跳层**'
       '（RESTORE→TOPMOST→NOTOPMOST→SetForegroundWindow；含 AttachThreadInput 破解前台锁），四法实测均"置前成功"，'
       '随后点击普遍恢复生效（变化量 40~180）；(b) 章节跑偏（游戏在 EPISODE 09）⇒ 实测**章节标签 (1734,983)** 与 '
       '**▶ (1801,983)** 有效，先前猜的 (1603,983) 其实是当前高亮的 EPISODE 09；(c) 点"开始行动"后**必须等待战斗 HUD**'
       '（否则会把刚进的战斗退出去，实测踩到）；(d) 结算"点击继续"坐标由中央改**底部 (960,988)**；'
       '③**判据纠错**："能读到数字 ≠ 在战斗"——曾把「任务失败」结算画面读成"费用 56/57 conf 0.94"；'
       '已改用**战斗 HUD 红条**（ROI [10:72,900:1380] 红色占比>0.05）判定战斗、并新增结算画面分支；'
       '④**用户给的验证口径（重要，改变后续验收准则）**：动画层与底层数据不严格对齐 ⇒ 图像识别**只能确定"事件发生在哪一帧"**'
       '（出生精确帧、血条变动=造成伤害的精确帧、面板变化精确帧…），用它与解包数据/模拟环境比对；'
       '**单位实际坐标与动画位置无法用图像统一确定**，坐标实机检验很困难，这正是必须靠解包搭建精确模拟环境的原因之一；'
       '⑤**断点**：导航仍不够稳（多次"连续三次点击 0.0"，最可能是**加载/过渡画面时点击本就无效**，应改为'
       '"先等画面稳定再点"而非快速重试）⇒ 下一步给导航加**稳定等待**，之后才能拿到成对「相位↔墙钟」样本，'
       '完成精度比对与暂停闭环；⑥合规：仅 adb/窗口接口与普通注入，不碰游戏内存；仅演习，未消耗理智。 | 2026-09-14 |')
r = r.replace(ra, add + ra, 1)
io.open(REG, 'w', encoding='utf-8', newline='').write(r)
print('台账已追加第四十六轮')

for f, sub in ((DOC, r'knowledge\04_数据对应与核验'), (REG, 'management')):
    shutil.copy2(f, os.path.join(DST, sub, os.path.basename(f)))
for f in ('frame_clock.py',):
    shutil.copy2(os.path.join(r'C:\Users\23922\Documents\ds_harness\ak\code\vision\plugins\clock', f),
                 os.path.join(DST, 'code', 'vision', 'plugins', 'clock', f))
for f in ('phase_precision_test.py', 'force_foreground.py'):
    shutil.copy2(os.path.join(r'C:\Users\23922\Documents\ds_harness\ak\code\vision\apps', f),
                 os.path.join(DST, 'code', 'vision', 'apps', f))
shutil.copy2(r'C:\Users\23922\Documents\ds_harness\ak\code\vision\plugins\capture\emu_window.py',
             os.path.join(DST, 'code', 'vision', 'plugins', 'capture', 'emu_window.py'))
print('同步完成')
