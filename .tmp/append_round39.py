# -*- coding: utf-8 -*-
"""append_round39.py — 第三十九轮：MuMu display 通道验证 + 「暂停下慢采集也够用」的结论。"""
import io
import sys

sys.stdout.reconfigure(encoding='utf-8')

DOC = r'C:\Users\23922\Documents\ds_harness\ak\knowledge\04_数据对应与核验\41_模拟器与自动打图_首版实现.md'
REG = r'C:\Users\23922\Documents\ds_harness\management\tasks_registry.md'

DOC_SEC = '''
### 7.64 【结论】暂停协议下"慢采集"完全够用：adb display 通道即为合规的遮挡无关采集

#### 实测：CostRuler 的 MuMu 通道，以及我们自己的等价方案
启动本机 CostRuler（`D:\\__soft\\ak\\ArknightsCostBarRuler-v2.3.2`）后，它**自动以 MuMu 模式连上**：

```
creating capture backend: type=MuMu, instance_index=0, device_id=Some("127.0.0.1:16384"), window_handle=None
MuMu connected: display_id=2, dimensions=1920x1080
```

⇒ **MuMu 有独立的 display 通道**（display 2 = 游戏画面，1920×1080），这正是 §7.58/§7.60 里我缺的、
既**遮挡无关**又快的采集路径。（它的费用尺 worker/API 仍需一次 GUI 交互才启动，`2606` 未监听、probe 为 None，
所以本轮没有直接借用它的输出。）

**但我们不必依赖它**——同一条通道可以用 adb 直接走：

```bash
adb -s 127.0.0.1:16384 exec-out screencap -p -d 2
```

实测：**1920×1080、真实游戏画面（均值 85.9，非黑）、596 ms/帧、遮挡无关**（直读模拟器帧缓冲）。
`dumpsys SurfaceFlinger --display-id` 也确认了 MuMu 暴露 display 0/1/2 三个 display。

#### 这条实测把前几轮的思路纠正过来了
- 我此前把"帧级精度"绑在**采集速度**上（一路追 WGC、PrintWindow、0.16ms 快路径），
  但用户 §7.62 的提醒已经指出正确方向：**暂停时游戏时间冻结，识别延迟不进入误差**。
- 结合本轮实测：**596 ms/帧在暂停协议下完全可接受**——因为我方在暂停期间有任意长的外部时间，
  慢的只是"看"，而"看"的结果对应的是**同一个冻结帧**。
- ⇒ **合规、遮挡无关、帧精确的最小可行组合** = `adb -d 2` 采集 + `paused_protocol` 暂停协议 +
  **费用条相位/待部署十分位对齐恢复**。WGC、MuMu 内部 IPC、第三方 ruler 都变成**可选优化**，而非前提。

#### 下一步（闭环验证）
用 `-d 2` 采集做一次真实的**帧级操作闭环**：
暂停 → 读费用条相位得到严格帧号 → 注入同帧多操作 → 在目标相位恢复 → 用下一个相位值反推"实际过了几帧"，
与轴表目标帧比对（误差应为 0～1 帧）。这条闭环一旦通过，"费用尺帧级识别 + 同帧多操作"即告成立。
'''

REG_ADD = (
    ' **第三十九轮（MuMu display 通道实测；结论：暂停下慢采集也够用）**：'
    '①启动本机 CostRuler 后它**自动以 MuMu 模式连上**：`type=MuMu, device_id=127.0.0.1:16384` → '
    '`MuMu connected: display_id=2, dimensions=1920x1080` ⇒ 证实 **MuMu 有独立 display 通道**'
    '（display 2 = 游戏画面），正是 §7.58/§7.60 缺的"既遮挡无关又快"的路径；'
    '但它自己的费用尺 worker/API 仍需一次 GUI 交互才启动（2606 未监听、probe=None），故本轮未借用其输出；'
    '②**不依赖它的等价方案**：`adb -s 127.0.0.1:16384 exec-out screencap -p -d 2` 实测 **1920×1080 真实画面、'
    '遮挡无关、596ms/帧**（`dumpsys SurfaceFlinger --display-id` 确认 MuMu 暴露 display 0/1/2）；'
    '③**思路纠正**：前几轮把"帧级精度"绑在**采集速度**上（一路追 WGC/PrintWindow/0.16ms 快路径）是错的；'
    '结合用户 §7.62 的提醒（暂停时游戏时间冻结、识别延迟不进误差），**596ms 在暂停协议下完全够用** ⇒ '
    '**合规+遮挡无关+帧精确的最小可行组合 = adb -d 2 采集 + paused_protocol 暂停协议 + 费用条相位/十分位对齐恢复**，'
    'WGC／MuMu 内部 IPC／第三方 ruler 降级为**可选优化**而非前提；'
    '④**下一轮闭环验证**：暂停 → 读相位取严格帧号 → 注入同帧多操作 → 目标相位恢复 → 用下一相位反推实际帧数并与轴表目标比对'
    '（误差应 0~1 帧）；通过即"费用尺帧级识别 + 同帧多操作"成立；'
    '⑤合规说明：仅使用 adb/窗口接口与普通注入，不碰游戏内存；仅演习，未消耗理智；'
    'ruler-app 为验证第三方方案而临时启动，验证后已关闭，其 config 已备份为 `config.json.bak_r38`。 | 2026-09-14 |'
)

s = io.open(DOC, encoding='utf-8').read()
anchor = '### 7.63 本轮新增/修改文件'
if anchor not in s:
    raise SystemExit('doc anchor not found')
s = s.replace(anchor, DOC_SEC + '\n### 7.65 本轮新增/修改文件', 1)
io.open(DOC, 'w', encoding='utf-8', newline='').write(s)
print('文档已追加 §7.64')

r = io.open(REG, encoding='utf-8').read()
ra = '\n\n## 冲突记录'
if ra not in r:
    raise SystemExit('registry anchor not found')
r = r.replace(ra, REG_ADD + ra, 1)
io.open(REG, 'w', encoding='utf-8', newline='').write(r)
print('台账已追加第三十九轮')
