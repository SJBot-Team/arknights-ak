# -*- coding: utf-8 -*-
"""update_t052_round33.py — 写入 T-052 第三十三轮（帧级时钟 + 时延预算实测）。"""
import io
import sys

sys.stdout.reconfigure(encoding='utf-8')

P = r'C:\Users\23922\Documents\ds_harness\management\tasks_registry.md'
ADD = (
    ' **第三十三轮（用户给出两种帧级计时法 → 实现 + 帧级精度回归 + 时延预算实测）**：'
    '①**收到用户 2026-09-14 的关键输入**：方法1「费用条相位+费用整数格」——费用快满时故意消耗让条保持跳动，'
    '数条满了几次、当前条长是第几帧；方法2「待部署时间十分位（计时器干员）」——开局 0 帧暂停、部署 3 名、隔 1 帧撤退，'
    '每 3 帧过 0.1s，三名干员十分位错开后**每帧至少一个跳**，用"有没有跳"判断是否过了一帧；'
    '并明确要求：识别/响应精度要高，可借鉴 PRTS+ 并优化，且**读内存违规**、必须走外部计时+图像识别等合规路线；'
    '②**实现** `code/vision/plugins/clock/frame_clock.py`：`bar_phase()`（纯函数求条内帧偏移）、'
    '`CostLatticeClock`（方法1，含**净消耗账本**与顶上限 `stalled` 检测）、`RedeployTenthsClock`（方法2，多数表决+丢读退化）、'
    '`WallRateClock`（墙钟×HUD 倍速，暂停不计时）、`FrameClock`（优先级融合、强制单调、输出残差）；'
    '并接进 `make_clock(source="frame_clock")`，自动与外部尺子（方法4）串接；'
    '③**帧级精度回归** `apps/test_frame_clock.py` 全 PASS：费用条 30 个相位 **30/30 精确**（5 档噪声下最大偏差 0 帧）；'
    '费用格+相位 **300 帧逐帧恢复误差 0 帧**；不做消耗记账恰好偏 300 帧（=10 费×30）⇒ **账本不可省**；'
    '条停住后 `stalled=True`；十分位法 **300 帧误差 0 帧**、随机丢读 5% 只退化为滞后（13 次丢读→滞后 13 帧）**不产生错帧**；'
    '融合的回退/单调/残差均正确；'
    '④**时延预算实测** `apps/bench_frame_budget.py`（一帧 33.3ms）：'
    'adb 路线 = screencap **742ms** + tap **37.6ms** ≈ **780ms ≈ 23.5 帧 ❌**；'
    '窗口路线 = BetterCam/DXGI 抓屏 **0.16ms** + 识别 0.03~0.17ms + SendInput 点击 **1.9ms** ≈ **2.1ms ≈ 0.06 帧 ✅**，'
    '一帧还剩 31.2ms ⇒ **同帧可叠加 ≈17 次操作**；'
    '**结论：帧级执行只能走"窗口抓屏+本机注入"，adb 天然慢 370 倍不可能做帧级**（也解释了 PRTS+ 为何限定 MuMu12+键鼠方案）；'
    '识别本身完全不是瓶颈，瓶颈在采集/注入链路与暂停-恢复协议；'
    '⑤**其他合规精确帧方案评估表**（已写入文档）：暂停批处理协议（PRTS+ 核心手法，恢复时机仍需方法1/2 对齐）、'
    '部署冷却环/技能环相位、敌人位移量化、音效对齐、外部尺子；**读内存明确排除（违规）**；'
    '⑥回归全绿：vision 侧 ruler_clock/costbar_axis/frame_clock/skill_ready/nav_flow 全 PASS；'
    '文档 `knowledge/04/41` 新增 §7.55/§7.56。 | 2026-09-14 |'
)

s = io.open(P, encoding='utf-8').read()
anchor = '\n\n## 冲突记录'
if anchor not in s:
    raise SystemExit('anchor not found')
s = s.replace(anchor, ADD + anchor, 1)
io.open(P, 'w', encoding='utf-8', newline='').write(s)
print('T-052 已追加第三十三轮；行数 =', len(s.splitlines()))
