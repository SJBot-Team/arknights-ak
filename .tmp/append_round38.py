# -*- coding: utf-8 -*-
"""append_round38.py — 第三十八轮：暂停驱动协议 + CostRuler 借鉴点。"""
import io
import sys

sys.stdout.reconfigure(encoding='utf-8')

DOC = r'C:\Users\23922\Documents\ds_harness\ak\knowledge\04_数据对应与核验\41_模拟器与自动打图_首版实现.md'
REG = r'C:\Users\23922\Documents\ds_harness\management\tasks_registry.md'

DOC_SEC = '''
### 7.62 【用户纠正·概念性】暂停才是帧级精度的来源；并借鉴 CostRuler 的实现

#### 用户 2026-09-14 的指正（本轮最重要的修正）
> 考虑到图像识别无法避免的延迟，可能的游戏卡顿导致的游戏与外部时间误差，一般玩家视角认为，
> **当游戏暂停时，图像识别到的精确帧数才严格等同于当前游戏时间。**

这条把我前面几轮的思路纠正过来了：
- 我此前把"帧级精度"当成**速度问题**（测出窗口抓屏 0.16ms、单次识别→注入 2.1ms、一帧还能叠 17 次操作），
  并据此说"帧级执行可行"。**带宽充裕是真的，但那不是精度的来源。**
- 真正的精度来源是**暂停**：暂停 ⇒ 逻辑时间冻结 ⇒ 识别/决策/注入的延迟**不再进入误差**；
  注入的操作在**恢复那一帧**生效。于是唯一需要对齐的是**恢复瞬间**，而它可以用
  **游戏内量**（费用条相位、待部署十分位）对齐 ⇒ **天然免疫卡顿与外部时钟漂移**。
- 这也解释了两件事：①PRTS+ 为什么重度依赖"暂停/子弹时间 + 同帧批量操作"；
  ②CostRuler 为什么敢用截图链路（config 里还专门有 `screenshot_delay_ms` 补偿）——它工作在暂停下。

#### 借鉴 CostRuler 的实现（本地 `D:\\__soft\\ak\\ArknightsCostBarRuler-v2.3.2`，Rust 写的）
从它的 `config.json` / 日志读到的关键实现点：
| 发现 | 对我们的意义 |
|---|---|
| `ruler_core::capture::mumu` → `MuMu connect(device_id=127.0.0.1:16384)` → **`MuMu connected: display_id=2, dimensions=1920x1080`** | **它有专门的 MuMu display 通道**——既不是 adb screencap、也不是会被遮挡的桌面抓屏。**这正是我这几轮缺的那条路** |
| `WARN Windows capture: WGC unavailable (Invalid target client size: 0x0); falling back to GDI` | 与 §7.60 的黑帧**同源**（客户区 0×0）；它选择退回 **GDI**，我应照做而不是硬啃 WGC |
| `screenshot_delay_ms: 4.303166` | 采集延迟补偿项，值得照搬思路 |
| `calibration/profile_*.json`: `{format_version:4, required:1.0}`、`frame_display_mode: "0_to_n-1"`、`ui_scaler` | 它的标定只存"每帧所需像素/阈值"这类**少量标量**，配合 `0..n-1` 的帧显示口径 —— 我们的 `bar_phase` 正是同一模型 |
| `ruler-app` 在 **`ws://127.0.0.1:2606/`** 暴露快照 + HTTP 兜底 | 我们已有的 `RulerClock`(WS/HTTP) 就是对接它 ⇒ **PC 端/MuMu 端的精确费用尺可以是现成的第三方实现**，不必自研 |

⇒ 行动项：**优先把 CostRuler 的 MuMu display 通道接起来**（它已经在本机跑过、日志证明可用），
比自己继续攻 WGC 划算得多。

#### 本轮落地：`plugins/clock/paused_protocol.py`
把"暂停=精确帧"写成可复用协议：
- `pause()`：发暂停键并**确认暂停遮罩真的出现**（确认不上就返回 False，**绝不"以为暂停了"**）；
- `frames()`：暂停期间读到的帧号 = 严格游戏时间；
- `stage()/commit()`：暂停期间排队并注入**同帧多操作**（快慢无所谓）；
- `resume_at(target_phase)`：等到**费用条相位**与目标相差 ≥6 帧才恢复（避开恢复瞬间跨费用结算的 ±1 帧歧义）；
- `same_frame_batch(actions, phase)`：一步到位。
离线自检 PASS（合成时钟验证：暂停→注入 2 条→相位对齐恢复，状态机与注入顺序均正确）。
'''

REG_ADD = (
    ' **第三十八轮（用户纠正：暂停才是帧级精度来源；借鉴 CostRuler）**：'
    '①**用户 2026-09-14 指正**：图像识别有不可避免的延迟、游戏卡顿会让游戏内时间与外部墙钟漂移，'
    '因此"**只有暂停时，识别到的帧数才严格等于游戏时间**"；'
    '②这修正了我前几轮的思路：我把帧级精度当**速度问题**（测出 0.16ms 抓屏、单次识别→注入 2.1ms、一帧可叠 17 次操作）'
    '并据此宣称"帧级可行"——**带宽充裕属实，但那不是精度来源**；精度来源是**暂停**（逻辑时间冻结 ⇒ 延迟不进误差，'
    '注入在恢复那一帧生效），唯一要对齐的是**恢复瞬间**，而它可用**游戏内量**（费用条相位/待部署十分位）对齐 ⇒ 免疫卡顿与时钟漂移；'
    '③**借鉴 CostRuler 实现**（本地 `D:\\__soft\\ak\\ArknightsCostBarRuler-v2.3.2`，Rust）：'
    '**(a) 它有专门的 MuMu display 通道**（日志 `MuMu connected: display_id=2, dimensions=1920x1080`，'
    'device_id=127.0.0.1:16384）——既非 adb screencap 也非会被遮挡的桌面抓屏，**正是我缺的那条路**；'
    '(b) 它同样撞上 WGC（`Invalid target client size: 0x0`）并**退回 GDI**，我应该照做；'
    '(c) `screenshot_delay_ms` 延迟补偿；(d) 标定只存少量标量（`required` 等）+ `0_to_n-1` 帧口径，与我们的 `bar_phase` 同模型；'
    '(e) 它在 `ws://127.0.0.1:2606/` 暴露快照，**我们的 `RulerClock` 已在对接** ⇒ 费用尺可直接复用第三方实现；'
    '④**落地**：新增 `code/vision/plugins/clock/paused_protocol.py`——暂停（**确认遮罩真的出现**，否则判失败）→'
    '冻结帧号 → 排队注入同帧多操作 → **按费用条相位对齐恢复**（要求距目标相位 ≥6 帧，避开跨费用结算的 ±1 帧歧义）；'
    '离线自检 PASS；⑤**下一轮**：接通 CostRuler 的 MuMu display 通道（日志证明本机可用），替代自研 WGC；'
    '并把"画面在变"自检与暂停协议接到所有实机脚本；⑥合规：仅窗口/模拟器接口与普通注入，不碰游戏内存；仅演习，未消耗理智。 | 2026-09-14 |'
)

s = io.open(DOC, encoding='utf-8').read()
anchor = '### 7.61 本轮新增/修改文件'
if anchor not in s:
    raise SystemExit('doc anchor not found')
s = s.replace(anchor, DOC_SEC + '\n### 7.63 本轮新增/修改文件', 1)
io.open(DOC, 'w', encoding='utf-8', newline='').write(s)
print('文档已追加 §7.62')

r = io.open(REG, encoding='utf-8').read()
ra = '\n\n## 冲突记录'
if ra not in r:
    raise SystemExit('registry anchor not found')
r = r.replace(ra, REG_ADD + ra, 1)
io.open(REG, 'w', encoding='utf-8', newline='').write(r)
print('台账已追加第三十八轮')
