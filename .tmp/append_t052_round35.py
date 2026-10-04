# -*- coding: utf-8 -*-
"""append_t052_round35.py — 写入 T-052 第三十五轮（★桌面坐标系 vs 帧缓冲坐标系）。"""
import io
import sys

sys.stdout.reconfigure(encoding='utf-8')

P = r'C:\Users\23922\Documents\ds_harness\management\tasks_registry.md'
ADD = (
    ' **第三十五轮（★根因：抓屏抓的是桌面、ROI 却标在帧缓冲坐标系）**：'
    '①**现象**：实机在线循环里费用数字**恒定读出同一个值（8）且置信度恒定 0.328**、费用条恒定 `fill=1.000`；'
    '看起来像"识别坏了/丢首位"，但其实是**坐标系错位**；'
    '②**根因**：BetterCam/dxcam 默认抓**整个桌面**（本机 2560×1600），而所有 ROI 都是在**模拟器帧缓冲坐标**'
    '（1920×1080，来自 adb screencap）下标定的 ⇒ ROI 打到无关像素上，稳定匹配到某个静态白块；'
    '③**修复**：新增 `code/vision/plugins/capture/emu_window.py`——用 Win32 找到模拟器**客户区**窗口'
    '（本机 `MuMuPlayer` 在桌面 (2,63)、1920×1080），只抓这块区域 ⇒ 与 adb 帧缓冲**逐像素对齐**，'
    '既有 ROI 全部可直接复用；'
    '④**窗口选择的坑**：枚举会同时看到「宿主窗口（带边框 1920×1143）」和「渲染客户区（1920×1080）」，'
    '必须优先选**尺寸正好等于帧缓冲**的那个，否则整幅图会差 63px 顶部边框；'
    '⑤新增**自标注回归** `apps/selflabel_cost_capture.py`：自由回费窗口里 显示费用 = 10 + floor(t)，'
    '于是每帧的标签由时间自己给出（避免人工读错标签——上一轮我就是用抽样图重建标签，结果标签本身不可靠）；'
    '同时新增 `apps/diag_cost_digits.py`（用已有实机帧做逐帧字形切分诊断）；'
    '⑥断点：最后一次运行 40s 内未读到费用数字（导航未进到战斗，脚本缺状态自适应）⇒ '
    '下一轮先把进关序列做成**状态自适应**（按当前界面分支），再跑自标注回归拿到"两位数字识别准确率"的真数字，'
    '然后用"故意消耗让费用条保持跳动"定位费用条 ROI，最后在线验证相位 30 帧回绕；'
    '⑦合规：仅演习，未消耗理智。 | 2026-09-14 |'
)

s = io.open(P, encoding='utf-8').read()
anchor = '\n\n## 冲突记录'
if anchor not in s:
    raise SystemExit('anchor not found')
s = s.replace(anchor, ADD + anchor, 1)
io.open(P, 'w', encoding='utf-8', newline='').write(s)
print('T-052 已追加第三十五轮；行数 =', len(s.splitlines()))
