# -*- coding: utf-8 -*-
"""append_round50.py — 第 50 轮：MAA 模板界面判定器交付；模拟器渲染停止（第 3 次）与请求。"""
import io
import os
import shutil
import sys

sys.stdout.reconfigure(encoding='utf-8')

DOC = r'C:\Users\23922\Documents\ds_harness\ak\knowledge\04_数据对应与核验\41_模拟器与自动打图_首版实现.md'
REG = r'C:\Users\23922\Documents\ds_harness\management\tasks_registry.md'
DST = r'E:\__file\ak_kb\kb'

SEC = '''
### 7.97 【交付】用 MAA 模板做界面判定与按钮定位（替代亮度阈值 + 硬编坐标）

我此前用"右下角白色占比 > 0.10"判界面、并硬编"开始行动 = (1710,990)/(1675,792)"这类**随界面变化**的坐标，
反复误命中。本轮改成 **MAA 模板匹配**，判据来自游戏自己的图标。

**判定表（用 8 张真实帧标定，阈值 0.75/0.80）**

| 界面 | 命中锚点 | 分数 |
|---|---|---|
| 战斗 | `BattleFlag/BattleOfficiallyBegin` | **0.99**（另：HpFlag 0.95、CostFlag 0.88、KillsFlag 0.87、OpersFlag 0.80） |
| 编队（含「开始行动」） | `StartButton/BattleStartNormal` / `BattleStartAdverse` | **0.99 / 0.98** |
| 关卡详情 / 关卡地图 / 收藏列表 | 仅 `ReturnButton/Return` | 0.99 |
| 任务失败结算 / 加载 | **无命中** | —— |

**落地**：`plugins/recognize/ui_state.py` → `UiState.classify(frame)` 返回
`{state: battle|squad|viewport|unknown, hits, start_point}`，
其中编队界面会**用模板位置直接给出「开始行动」的点击点**。
**自检 8/8 全部通过**，例如：
```
OK  battle_in.png   → battle   证据={BattleOfficiallyBegin:0.99, HpFlag:0.95, CostFlag:0.88, KillsFlag:0.87, OpersFlag:0.80}
OK  battle_ready.png→ squad    点击点(1655, 759)  证据={BattleStartNormal:0.99}
OK  diag_battle_0.png→ unknown （任务失败结算，无锚点命中）
```
⇒ 注意 (1655,759) 与我硬编的 (1675,792) 不同：**模板匹配给的位置才是实测中心**。

### 7.98 【环境阻塞·第 3 次】模拟器渲染停止，且此次无法用窗口操作恢复

现象：判据全 0、点击全无效、`adb` 两帧差异 **精确 0.0**（帧缓冲冻结）。诊断与尝试：

| 检查/手段 | 结果 |
|---|---|
| 窗口状态 | `MuMuPlayer`(client 1920×1080) **未最小化、且已是前台窗口** |
| `render_wnd` | 从 `MuMuManager info` 取到 **`render_wnd=0x00770C30`**（另有 `main_wnd`）；该窗口**可见、未最小化** |
| `ShowWindow(SW_SHOW)` + `BringWindowToTop` + `SetForegroundWindow`（对 main/render 两个窗口） | 渲染**仍未恢复** |
| `SendInput` 点击标题栏 | 无效 |
| `SendInput` 点击客户区 | 无效 |
| `MuMuManager info` | `player_state=start_finished`、`is_android_started=true`、`is_process_started=true`（实例"正常"） |

⇒ 属于**渲染层挂起**。**可行恢复是重启模拟器实例，但重启可能触发游戏重新登录**，
而用户明确要求"登录需逐次同意"，**故我不擅自重启**。

**附带发现（有价值）**：MuMu 的**渲染窗口与主窗口是两个不同 HWND**（可由
`MuMuManager.exe info -v 0` 的 `render_wnd` 取得）——这解释了此前 WGC 抓窗口拿到**全黑**：
我枚举到的是容器/主窗口，**真正的渲染面在 `render_wnd`**。
⇒ 将来若重启 WGC 方案，应把 `render_wnd` 作为捕获目标（届时需在渲染正常时验证）。

### 7.99 断点
1. **实机相位精度验收**（|误差| ≤ 2 帧）仍待跑：脚本 `apps/instant_sample.py` / `apps/auto_sample_v2.py`
   已就绪，且**界面判定已升级为 `UiState`**；只差"渲染恢复 + 把游戏带到含「演习」的关卡详情"。
2. **请求用户**：请在设备前**重启 MuMu 模拟器**（或确认是否授权我重启实例，注意可能需重新登录）；
   恢复后即可直接跑上述脚本。
3. 不依赖渲染的后续可做项：把 `UiState` 接进全部实机脚本；用 MAA 的 `render_wnd` 重试 WGC。
'''

s = io.open(DOC, encoding='utf-8').read()
anchor = '### 7.96 本轮新增/修改文件'
if anchor not in s:
    raise SystemExit('doc anchor not found')
s = s.replace(anchor, SEC + '\n### 7.100 本轮新增/修改文件', 1)
io.open(DOC, 'w', encoding='utf-8', newline='').write(s)
print('文档已追加 §7.97~§7.99')

r = io.open(REG, encoding='utf-8').read()
ra = '\n\n## 冲突记录'
add = (' **第五十轮（MAA 模板界面判定器交付；模拟器渲染停止第 3 次）**：'
       '①**交付 `plugins/recognize/ui_state.py`**：把界面判定从"亮度阈值"升级为 **MAA 模板匹配**，'
       '并用 8 张真实帧标定出判定表——战斗：`BattleOfficiallyBegin` **0.99**（+HpFlag 0.95/CostFlag 0.88/'
       'KillsFlag 0.87/OpersFlag 0.80）；编队：`BattleStartNormal` **0.99**/`BattleStartAdverse` 0.98；'
       '详情/地图/收藏列表：仅 `Return` 0.99；结算/加载：**无命中**；'
       '**自检 8/8 通过**，且编队界面由模板位置**直接给出「开始行动」点击点 (1655,759)**'
       '（与我硬编的 (1675,792) 不同——模板给的才是实测中心）；'
       '②**环境阻塞（第 3 次）**：判据全 0、点击全无效、adb 两帧差异**精确 0.0**；诊断显示窗口**未最小化且已是前台**，'
       '`render_wnd` 也**可见未最小化**，对其做 ShowWindow/BringWindowToTop/SetForegroundWindow 与'
       '两处 SendInput 点击**均无法恢复**，而 `MuMuManager info` 报实例 `start_finished`/android 已启动 ⇒ '
       '**渲染层挂起**；**可行恢复是重启实例，但可能触发重新登录**（用户要求登录逐次同意）⇒ **不擅自重启**；'
       '③**附带发现**：MuMu 的**渲染窗口与主窗口是不同 HWND**（`MuMuManager info` 的 `render_wnd`）——'
       '这解释了此前 WGC 抓窗口全黑（枚举到的是容器窗口，真渲染面在 render_wnd），将来重试 WGC 应以它为捕获目标；'
       '④**断点**：实机相位精度验收（|误差|≤2 帧）仍待跑——`instant_sample.py`/`auto_sample_v2.py` 已就绪且'
       '界面判定已升级为 `UiState`，只差"渲染恢复 + 把游戏带到含「演习」的关卡详情"；'
       '**需用户重启模拟器**（或授权我重启，注意可能需重新登录）；'
       '⑤合规：全程仅演习、未消耗理智；仅 adb/窗口/OCR/普通注入，不碰游戏内存。 | 2026-09-14 |')
r = r.replace(ra, add + ra, 1)
io.open(REG, 'w', encoding='utf-8', newline='').write(r)
print('台账已追加第五十轮')

shutil.copy2(DOC, os.path.join(DST, 'knowledge', '04_数据对应与核验', '41_模拟器与自动打图_首版实现.md'))
shutil.copy2(REG, os.path.join(DST, 'management', 'tasks_registry.md'))
for rel in (r'code\vision\plugins\recognize\ui_state.py', r'code\vision\apps\auto_sample_v2.py'):
    src = os.path.join(r'C:\Users\23922\Documents\ds_harness\ak', rel)
    shutil.copy2(src, os.path.join(DST, rel))
print('同步完成')
