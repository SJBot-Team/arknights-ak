# -*- coding: utf-8 -*-
"""append_acceptance_r45.py — 验收对照表补「第 40~51 轮状态更新」。"""
import io
import os
import shutil
import sys

sys.stdout.reconfigure(encoding='utf-8')

DOC = r'C:\Users\23922\Documents\ds_harness\ak\knowledge\04_数据对应与核验\42_验收对照_模拟与打图.md'
REG = r'C:\Users\23922\Documents\ds_harness\management\tasks_registry.md'
DST = r'E:\__file\ak_kb\kb'

SEC = '''

---

## 十二、第 40~51 轮状态更新（2026-09-14 晚）

> 本节取代第十一节的同项标注。凡与前面冲突者以本节为准。

### 12.1 打图端（需求 2.1~2.6）

| 需求 | 本阶段新增证据 | 状态 |
|---|---|---|
| 2.1 费用尺帧级识别 | **官方标定表已接入**：从 CostRuler 的 `calibration/profile_*_30f_1920x1080.json` 取到 **`pixel_map`（像素长度↔精确帧）**，条宽 180px，与我方实测亮列 1739–1919 **完全吻合**；`frame_clock.frame_from_width()` 由"比例×30"改为**查表**。离线回归：相位 30/30 精确、费用格+相位 300 帧零误差、十分位 300 帧零误差 | 🟡 **离线充分；实机闭环未验证**（渲染阻塞） |
| 2.2 同帧多操作 | `paused_protocol` **边界测试 5/5 PASS**：暂停未确认必失败、恢复超时必须保持状态、多批注入顺序、恢复点必须距相位边界 ≥6 帧 | 🟡 离线 ✅；实机待验证 |
| 2.3 与模拟共用轴表 | 两端同 `resolve_frames` 语义；`test_ruler_clock` 的 G_case_milestones 逐条对过作者轴表 | ✅ |
| 2.4 PC/模拟器通用 | 采集通道：窗口抓屏 / **adb display 2**（遮挡无关，596ms）/ 外部尺子 WS-HTTP(2606)；**新增发现 MuMu 的 `render_wnd` 与主窗口是两个 HWND**（此前 WGC 全黑即因抓到容器窗口），并落地 `plugins/capture/wgc_render.py`（待渲染恢复后验证） | 🟡 通道具备，WGC 支路待验证 |
| 2.5 虚拟鼠标隔离 | `input:` 插件 + SendInput/DirectInput/PostMessage/adb 四后端 | ✅ |
| 2.6 自动启动→选关→选人出战 | **OCR 驱动导航**（读"12-4/开始行动/演习"文字再点击，MAA `ClickStageName` 思路）+ **`UiState` 模板界面判定**（战斗 `BattleOfficiallyBegin` 0.99、编队 `BattleStartNormal` 0.99 且直接给出按钮点击点）；实机已达成**"演习 → 编队 → 开始行动 → 进入战斗"** | 🟡 分段可用，端到端仍受渲染阻塞 |

### 12.2 模拟器侧（需求 1.1~1.7）
维持第十一节的 ✅ 结论（关键根因已修、并以实机锚定测量反向验证：首漏 42.0/44.5/51.5s vs 实机 44.3/46.0/51.5s）。

### 12.3 本阶段新增的两条硬约束（已写进脚本）
1. **渲染闸门**：任何实机脚本先做"画面在变"校验（阈值 0.005），不通过即退出——
   因为渲染停止时 adb 帧缓冲会**精确冻结**（差异 0.0），一切画面判断都失真。
2. **零延迟采样**：精度验收必须"进战斗后立即采样"——费用上限仅 20，进战斗起 10 秒就满；
   任何额外扫描/截图（实测 36 秒）都会错过窗口，甚至因无部署而判负。

### 12.4 唯一硬阻塞
模拟器**渲染层挂起**（窗口未最小化、已是前台、`render_wnd` 亦可见，但 ShowWindow/BringWindowToTop/
SetForegroundWindow 与 SendInput 点击均无法恢复；`MuMuManager info` 仍报 `start_finished`）。
**恢复需重启实例，而重启可能触发游戏重新登录**（用户要求登录逐次同意）⇒ 等用户决定。
恢复后即可跑 `apps/instant_sample.py` / `apps/auto_sample_v2.py` 完成 2.1 的实机验收。
'''

s = io.open(DOC, encoding='utf-8').read()
if '第 40~51 轮状态更新' in s:
    print('本节已存在，跳过')
else:
    io.open(DOC, 'a', encoding='utf-8').write(SEC)
    print('已追加 §十二')

r = io.open(REG, encoding='utf-8').read()
ra = '\n\n## 冲突记录'
add = (' **第四十五轮（验收状态更新 + WGC render_wnd 支路）**：渲染仍冻结 ⇒ 继续离线工作；'
       '①**验收对照表补「第 40~51 轮状态更新」**（`knowledge/04/42` §十二）：逐项给出本阶段新证据——'
       '2.1 费用尺**已接入官方 pixel_map 标定表**（条宽 180px 与实测 1739–1919 完全吻合），'
       '离线回归全绿但**实机闭环未验证**；2.2 暂停协议**边界测试 5/5**；2.3 共用轴表 ✅；'
       '2.4 三通道具备 + **新发现 MuMu `render_wnd` 与主窗口是两个 HWND**（WGC 此前全黑之因）；'
       '2.5 ✅；2.6 **OCR 导航 + UiState 模板判定**（战斗 0.99、编队 0.99 且直接给出按钮点击点）'
       '已达成"演习→编队→开始行动→进战斗"；'
       '②**新增 `plugins/capture/wgc_render.py`**：以 `MuMuManager info` 的 `render_wnd` 为 WGC 捕获目标；'
       '实测**首帧超时**（WGC 仅支持顶层窗口，render_wnd 很可能是子窗口）⇒ 代码就绪，待渲染恢复后重验；'
       '③**两条硬约束写进脚本**：渲染闸门（画面在变校验，不通过即退出）、零延迟采样（进战斗立即采，'
       '因上限 20 只有 10 秒窗口，扫描 36 秒会错过甚至判负）；'
       '④**唯一硬阻塞**：模拟器渲染层挂起，各种窗口操作与点击均无法恢复，`MuMuManager info` 仍报 start_finished；'
       '恢复需重启实例而可能触发重新登录（用户要求登录逐次同意）⇒ 等用户决定；'
       '⑤合规：全程仅演习、理智未消耗；不碰游戏内存。 | 2026-09-14 |')
r = r.replace(ra, add + ra, 1)
io.open(REG, 'w', encoding='utf-8', newline='').write(r)
print('台账已追加第四十五轮')

shutil.copy2(DOC, os.path.join(DST, 'knowledge', '04_数据对应与核验', '42_验收对照_模拟与打图.md'))
shutil.copy2(REG, os.path.join(DST, 'management', 'tasks_registry.md'))
shutil.copy2(r'C:\Users\23922\Documents\ds_harness\ak\code\vision\plugins\capture\wgc_render.py',
             os.path.join(DST, 'code', 'vision', 'plugins', 'capture', 'wgc_render.py'))
print('同步完成')
