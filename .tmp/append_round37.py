# -*- coding: utf-8 -*-
"""append_round37.py — 第三十七轮：WGC 后端接入（已装包）、黑帧现象与下一步。"""
import io
import sys

sys.stdout.reconfigure(encoding='utf-8')

DOC = r'C:\Users\23922\Documents\ds_harness\ak\knowledge\04_数据对应与核验\41_模拟器与自动打图_首版实现.md'
REG = r'C:\Users\23922\Documents\ds_harness\management\tasks_registry.md'

DOC_SEC = '''
### 7.60 WGC（Windows Graphics Capture）后端接入：已装包、能开流，但拿到全黑帧

承接 §7.58「桌面区域抓屏会被遮挡、PrintWindow 对硬件加速窗口返回全黑」，本轮验证第三条路：
**Windows Graphics Capture**（窗口级捕获，理论遮挡无关）。

- **依赖已就位**：`windows-capture 2.0.1` 已装进 vision venv（API 为回调式：
  `WindowsCapture(window_name=/window_hwnd=)` + `@cap.event on_frame_arrived` + `start()`）。
- **接入方式**：`plugins/capture/emu_window.py` 新增 `WgcCapture`（后台线程持续更新"最新帧"，
  对上层暴露同步 `grab()`）+ `make_capture('wgc')` 工厂（WGC 不可用自动退回区域抓屏）。
- **踩到的坑 1**：`window_name='MuMuPlayer'` 会**首帧超时**——WGC 的 `window_name` 需要**精确标题**，
  子串匹配拿不到流 ⇒ 改为先用自家 Win32 枚举求出 HWND，再用 `window_hwnd=` 打开。
- **踩到的坑 2（当前卡点）**：用 HWND 打开后**能出帧、尺寸也对（1920×1080），但像素全黑（mean = 0.0）**。
  最可能的原因：我枚举到的是**容器/父窗口**，真正的 D3D 渲染面在**子窗口**上，
  WGC 抓父窗口自然只有空背景。
- **下一步**：(a) `EnumChildWindows` 找到客户区为 1920×1080 的**渲染子窗口**再喂给 WGC；
  (b) 或改用另一个候选窗口（`MuMu模拟器12` 宿主）；(c) 两者都不行则回到"保证模拟器可见"这一前提，
  并把这条前提写进执行器启动检查。

#### 与之配套的**强制自检**（本轮写进规程）
任何实机采集脚本在开始采样前必须先做 **"画面在变" 校验**：
连拍 2s，要求费用数字出现 **≥2 个不同值**（或费用条相位 ≥3 个不同相位）；
**全黑帧、静止帧、抓到别的窗口**都会在这一步被拦住并报错退出。
这条判据能一次性覆盖 §7.58 与 §7.60 两类坑，避免再次把"画面不对"误判成"识别坏了"。
'''

REG_ADD = (
    ' **第三十七轮（WGC 后端接入；黑帧卡点）**：'
    '①装好 `windows-capture 2.0.1`（vision venv），新增 `WgcCapture`（回调式 API → 后台线程更新最新帧、'
    '对上层暴露同步 `grab()`）与 `make_capture()` 工厂（WGC 不可用自动退回桌面区域抓屏）；'
    '②**坑1**：`window_name=` 子串匹配会首帧超时（WGC 需要精确标题）⇒ 改为自家 Win32 枚举求 HWND 后用 `window_hwnd=`；'
    '③**坑2（卡点）**：用 HWND 能出流、尺寸 1920×1080 正确，但**像素全黑 mean=0.0** —— '
    '极可能枚举到的是**容器/父窗口**，真渲染面在子窗口上 ⇒ 下一步用 `EnumChildWindows` 找 1920×1080 的渲染子窗口，'
    '或改试 `MuMu模拟器12` 宿主窗口；都不行则回到"保证模拟器可见"前提并写进执行器启动检查；'
    '④**配套强制自检（已写进规程）**：任何实机采样前先做"画面在变"校验——连拍 2s 要求费用数字出现 ≥2 个不同值'
    '（或费用条相位 ≥3 个不同相位），全黑/静止/抓错窗口一律报错退出，一次性覆盖 §7.58/§7.60 两类坑；'
    '⑤合规：仅窗口捕获 API 与普通窗口操作，不碰游戏内存；仅演习，未消耗理智。 | 2026-09-14 |'
)

s = io.open(DOC, encoding='utf-8').read()
anchor = '### 7.59 本轮新增/修改文件'
if anchor not in s:
    raise SystemExit('doc anchor not found')
s = s.replace(anchor, DOC_SEC + '\n### 7.61 本轮新增/修改文件', 1)
io.open(DOC, 'w', encoding='utf-8', newline='').write(s)
print('文档已追加 §7.60')

r = io.open(REG, encoding='utf-8').read()
ra = '\n\n## 冲突记录'
if ra not in r:
    raise SystemExit('registry anchor not found')
r = r.replace(ra, REG_ADD + ra, 1)
io.open(REG, 'w', encoding='utf-8', newline='').write(r)
print('台账已追加第三十七轮')
