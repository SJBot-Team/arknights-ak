# -*- coding: utf-8 -*-
"""append_round36.py — 第三十六轮：抓屏遮挡问题（窗口抓屏抓到的是最上层窗口）+ 验收判据。"""
import io
import sys

sys.stdout.reconfigure(encoding='utf-8')

DOC = r'C:\Users\23922\Documents\ds_harness\ak\knowledge\04_数据对应与核验\41_模拟器与自动打图_首版实现.md'
REG = r'C:\Users\23922\Documents\ds_harness\management\tasks_registry.md'

DOC_SEC = '''
### 7.58 【重要】窗口抓屏会被遮挡：抓到的是"最上层窗口"，不是游戏

#### 现象与误判
两轮里反复出现「费用数字**恒定**读同一个值（8/9）、置信度恒定」「费用条恒定满格」，
我一直按"识别坏了/丢首位/坐标错"去查。真相是**抓到的根本不是游戏画面**：
录下来的帧里赫然是 **DSH 对话窗口的文本**（"stage-entry sequ…"、"foregrounded"…）。

#### 原理
- `BetterCam/dxcam` 的 `grab(region=...)` 抓的是**桌面合成结果**——屏幕那块区域上**最上层窗口**的内容；
- 所以只要 DSH GUI / 浏览器盖在模拟器上面，抓到的就是**那个窗口**；
- `PrintWindow(PW_RENDERFULLCONTENT)` 本可绕开遮挡，但**对硬件加速的模拟器窗口返回全黑**
  （实测 `mean≈1~2` ⇒ 判定不可用），退回区域抓屏；
- `SetForegroundWindow` 返回 True **不代表真的置顶**（前台锁 + 本 GUI 很可能是 TOPMOST），实测仍抓到 GUI。

#### 与之对照：adb 抓屏是**遮挡无关**的
`adb exec-out screencap` 直接读模拟器帧缓冲，盖不盖窗口都不影响 ⇒ 这就是为什么
同一套 ROI 在 **adb 截图**上一直是对的（费用读 20 ✓），而换成**窗口抓屏**就读出恒定值。

#### 由此得到两条硬结论
1. **帧级快路径的前提是"模拟器可见"**：0.16ms 的窗口抓屏只有在模拟器未被遮挡时才有意义；
   在"DSH 一直盖在上面"的工作方式下，它的可用性被高估了（延时数据本身没问题，前提没满足）。
2. **验收判据必须包含"画面在变"**：新增自检——连拍 2s，要求
   ①费用数字出现**至少 2 个不同值**（或费用条相位出现 ≥3 个不同相位），
   ②否则判定"抓到了错误窗口/静止画面"并**报错而不是继续跑**。
   这个判据能一次性拦住本轮 + 上一轮所有的"恒定值"陷阱。

#### 待选方案（下一轮定）
| 方案 | 遮挡无关 | 速度 | 说明 |
|---|---|---|---|
| adb screencap | ✅ | 742ms ❌ | 只能做慢速校验/兜底 |
| 桌面区域抓屏（现用） | ❌ | 0.16ms | 需保证模拟器**可见**（不可被遮挡） |
| PrintWindow | 理论 ✅ | 快 | 实测硬件加速窗口返回全黑，不可用 |
| **Windows Graphics Capture（WGC）** | ✅ | 快 | 首选待验证：需 `windows-capture` 包或 WinRT 互操作 |
| 让用户把模拟器置于可见处 | ✅ | 0.16ms | 最省事，但要求人配合，不能作为自动化前提 |
'''

REG_ADD = (
    ' **第三十六轮（★窗口抓屏被遮挡：抓到的是最上层窗口）**：'
    '①**真因**：`BetterCam.grab(region=)` 抓的是**桌面合成结果**（该区域最上层窗口），'
    'DSH 对话窗口盖在模拟器上时抓到的就是 **DSH 的文本**（录下的帧里能直接看到聊天文字）；'
    '`PrintWindow(PW_RENDERFULLCONTENT)` 对硬件加速模拟器窗口**返回全黑**（mean≈1~2）不可用，'
    '`SetForegroundWindow` 返回 True 也不代表真的置顶（前台锁/TOPMOST）⇒ 区域抓屏仍拿到 GUI；'
    '②这解释了连续两轮"费用数字恒定读同一值、置信度恒定""费用条恒定满格"——**不是识别坏了**，'
    '而是**画面根本不是游戏**；对照之下 adb screencap 是**遮挡无关**的（直接读帧缓冲），'
    '所以同一套 ROI 在 adb 截图上一直正确（费用读 20 ✓）；'
    '③**两条硬结论**：(a) 0.16ms 的窗口抓屏快路径**只有在模拟器可见时才成立**，'
    '此前测的延时数据没错、但前提没满足；(b) **验收判据必须含"画面在变"**——'
    '连拍 2s 要求费用数字出现 ≥2 个不同值（或费用条相位 ≥3 个不同相位），否则报错停止，'
    '该判据可一次性拦住两轮的"恒定值"陷阱；'
    '④**新增/修改**：`plugins/capture/emu_window.py`（窗口客户区定位 + PrintWindow 尝试 + 置前台兜底）、'
    '`apps/enter_drill.py`（**状态自适应**进关：先判界面再决定点哪里，替代写死的固定点击序列）；'
    '⑤**断点**：下一轮验证 **Windows Graphics Capture（WGC）**（`windows-capture` 包或 WinRT 互操作）'
    '作为遮挡无关的快路径；并把"画面在变"自检接进所有实机采样脚本；'
    '⑥合规：仅演习，未消耗理智。 | 2026-09-14 |'
)

s = io.open(DOC, encoding='utf-8').read()
anchor = '### 7.56 本轮新增/修改文件'
if anchor not in s:
    raise SystemExit('doc anchor not found')
s = s.replace(anchor, DOC_SEC + '\n### 7.59 本轮新增/修改文件', 1)
io.open(DOC, 'w', encoding='utf-8', newline='').write(s)
print('文档已追加 §7.58')

r = io.open(REG, encoding='utf-8').read()
ra = '\n\n## 冲突记录'
if ra not in r:
    raise SystemExit('registry anchor not found')
r = r.replace(ra, REG_ADD + ra, 1)
io.open(REG, 'w', encoding='utf-8', newline='').write(r)
print('台账已追加第三十六轮')
