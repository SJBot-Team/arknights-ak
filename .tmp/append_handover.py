# -*- coding: utf-8 -*-
"""append_handover.py — 交接：按用户已定口径修正验收方式 + 资产索引。"""
import io
import os
import shutil
import sys

sys.stdout.reconfigure(encoding='utf-8')

ACC = r'C:\Users\23922\Documents\ds_harness\ak\knowledge\04_数据对应与核验\42_验收对照_模拟与打图.md'
IDX = r'C:\Users\23922\Documents\ds_harness\ak\knowledge\04_数据对应与核验\45_资产索引_可复用工具与脚本.md'
REG = r'C:\Users\23922\Documents\ds_harness\management\tasks_registry.md'
DST = r'E:\__file\ak_kb\kb'

ACC_SEC = '''

---

## 十三、验收口径修正（依用户 2026-09-14 的明确口径）

用户已明确：

> 由于动画层表现不严格对齐游戏底层储存的数据，单位的实际坐标和动画位置的关系是不能统一被确定的。
> 后续同模拟环境验证时，通过图像识别，我们**仅可以确定事件是在哪一帧发生的**，以此对游戏实机同游戏解包信息、
> 模拟环境做比对获取信息，比如单位出生的精确帧、血条变动即造成伤害的精确帧、攻击力面板等变化的精确帧等。
> **坐标的实机检验很困难**，这也是通过游戏解包尝试搭建精确模拟环境的必要原因之一。

⇒ 本表此前若含"用图像检验坐标/位置"的设想，**一律作废**，改为按下表口径验收：

| 需求 | 修正后的验收方式（事件帧口径） |
|---|---|
| 1.2 坐标/阻挡/碰撞 | **不再用实机图像检验坐标**；改为：① 解包数据自洽性（`tile_*` 与 start/end/telin/telout 互证、坐标合法率）；② 模拟器内的阻挡/碰撞行为与解包地图一致 |
| 1.1 寻路 | **事件帧**：出怪帧 / 漏怪帧（判负帧）与实机锚定测量比对（已完成：42.0/44.5/51.5 vs 44.3/46.0/51.5） |
| 1.3 仇恨 / 1.4 伤害 | **事件帧**：血条变动帧（=造成伤害的帧）、击杀帧、面板数值变化帧 |
| 2.1 费用尺 | **事件帧**：费用条相位→帧（已完成三重验证）；上限突破事件帧（平民进点/箱子被摧毁） |
| 2.2 同帧多操作 | 验证"同一帧内多个操作生效"——用**暂停驱动**（`paused_protocol`）在实机上验证 |
| 2.6 自动进关 | 事件帧 + 界面语义（`UiState` 模板命中）而非坐标匹配 |

**一句话**：**能（且只应）用图像识别的，是"事件发生在哪一帧"；坐标与动画位置不参与实机验收。**
'''

IDX_MD = '''# 资产索引：可复用工具与脚本（下次直接接续用）

> 2026-09-14 阶段收工整理。避免下次重复建设。

## 一、采集通道（`ak/code/vision/plugins/capture/`）
| 文件 | 用途 | 关键点 |
|---|---|---|
| `emu_window.py` | 三条采集通道 + 窗口定位 | `make_capture('adb')` = **adb display 2**（**遮挡无关**，~600ms）；`EmuWindowCapture` = 桌面区域抓屏（**会被上层窗口遮挡**）；`WgcCapture`（对硬件加速窗口返回全黑）；`bring_to_front()` 强制跳层 |
| `render_guard.py` | 实机**强制前置** | `assert_rendering()`：画面完全静止（差异 0.0）即判"未渲染"并退出；注意**静止界面**（如关卡详情，差异 0.0004）会误判，需放宽或改用 `UiState` 语义判定 |
| `wgc_render.py` | 以 `render_wnd` 为目标的 WGC | 目标句柄由 `MuMuManager.exe info -v 0` 的 `render_wnd` 取得；实测首帧超时（疑似子窗口） |

## 二、识别（`plugins/recognize/`）
| 文件 | 用途 |
|---|---|
| `cost_number.py` | 费用数字识别（**必须带置信度阈值 ≥0.85**；低置信度会误把按钮笔画当数字） |
| `maa_anchor.py` | **MAA 模板锚点**（帧缩到 1280×720 匹配后 ×1.5 换回）；已验证 `BattleOfficiallyBegin` 0.99、`BattleCostFlag` 0.88 等 |
| `ui_state.py` | **界面判定**（battle / squad / viewport / unknown）+ 编队「开始行动」按钮的模板定位点击点 |

## 三、时钟与协议（`plugins/clock/`）
| 文件 | 用途 |
|---|---|
| `frame_clock.py` | 费用条相位（**官方 `pixel_map` 查表**）、`signed_phase_delta()`、`frames_between()`（**算帧数必须用它**，不能 mod 30） |
| `cost_timeline.py` | **费用时间轴**：相位（秒内）+ 上限锚点（跨越封顶）；锚点后按新原点重算 |
| `bar_sanity.py` | 采样序列**自检**（费用非递减、填充不异常缩小、跳变、帧数≥30）——防止 ROI 失效时静默产出无效结论 |
| `paused_protocol.py` | **暂停驱动协议**：暂停（须确认遮罩）→ 冻结帧号 → 排队同帧多操作 → **按相位对齐恢复** |

## 四、导航（`plugins/nav/auto_enter.py`）
- `AutoEnter`：依赖注入式导航；**只点「演习」/编队「开始行动」/「继续」/关卡节点**，
  用 `UiState` 语义判"点击是否生效"（**不能用像素差异**——地图动画会骗过它）。

## 五、应用脚本（`ak/code/vision/apps/`）
| 脚本 | 用途 |
|---|---|
| `enter_and_pause.py` | 走演习进关并**在战斗开始后立刻暂停**（PRTS+ 要求在"第一秒内"暂停） |
| `prts_side_by_side.py` | 进关→暂停→**局内启动 PRTS+(--debug)**→同时逐帧识别→按时间戳并排对照 |
| `run_prts_compare.py` | 运行 PRTS+ 并同时采图对照（含 GameTime 解析） |
| `scan_video_events.py` | **录像逐帧扫描**（1600×900 缩放到 1920×1080 复用 ROI）：费用/相位/COST 提示/倍率 |
| `verify_phase_video.py` / `verify_phase_segments.py` | 录像基准验证相位精度（18 秒跨度 99.6%≤2 帧、无漂移） |
| `analyze_cost_timer.py` | 由费用变化帧重建"PRTS+ 口径计时器"，判定倍率/封顶段 |
| `probe_video_head.py` | 扫录像开头判断是否"初始 10 费 + 令@1.5s"那一局 |
| `test_*.py` | 离线回归：`test_frame_clock`(4/4)、`test_ruler_clock`(7/7)、`test_costbar_axis`(2/2)、`test_skill_ready`(3/3)、`test_nav_flow`(4/4)、`test_paused_protocol`(5/5)、`test_auto_enter`(4/4)、`test_frames_between`、`test_bar_sanity` |

## 六、模拟器侧脚本（`ak/sim/draft/`）
| 脚本 | 用途 |
|---|---|
| `case_summary.py` | 案例总览（严格模式 / 对轴模式） |
| `probe_first_dragon.py` | 首条弦惊最早落地时刻（账本 + 参数化实跑） |
| `probe_ceiling_events.py` | **费用上限锚点**：全部非 spawn 事件 + 成功部署 + deploy_failed 首末 |
| `probe_cost_tick.py` | 检验"满一次=30 帧"、列封顶段、量化"满N次=N秒"的误差 |
| `analyze_plan_feasibility.py` | 逐条对照"PRTS+ 计划时刻"与"费用何时真的够" |
| `dump_cyberplastic_timing.py` | 读轴表里 PRTS+ 的计时列（费用/帧数/绝对时间）+ 中转站状态 |
| `drive_prts_plus.py` | 交互式驱动 PRTS+ 并捕获输出（备用） |

## 七、PRTS+（赛博塑料）使用要点
- 命令：`prts+.exe --xlsm <路径> [--debug] [--autoenter]`；
- **路径必须是纯 ASCII**（中文会被 PowerShell 传参打坏）；
- `--autoenter` = **局外自动进关**（它只识别**关卡内待部署区**的干员，不识别局外编队界面）；
- **无需 `--autoenter` 时**：须让游戏已在**战斗中**，且**在第一秒内暂停**（它按费用条相对长度定位秒内帧）；
- 关键日志：`Setting initial tick to N`、`Get action: Action(cost,tick,time,...)`、
  `Performing action`、`Too much time, resuming and entering bullet time`、`Game time mismatch`；
- 已知限制：**费用封顶时它等不到目标 tick ⇒ 计时停住、流程卡死**（H12-4 上限 20，必然发生）。
'''


def main():
    s = io.open(ACC, encoding='utf-8').read()
    if '验收口径修正' in s:
        print('验收对照表已有该节，跳过')
    else:
        io.open(ACC, 'a', encoding='utf-8').write(ACC_SEC)
        print('已追加验收口径修正到 42 号文档')

    io.open(IDX, 'w', encoding='utf-8').write(IDX_MD)
    print('已写出资产索引:', IDX)

    r = io.open(REG, encoding='utf-8').read()
    ra = '\n\n## 冲突记录'
    add = (' **第七十四轮（交接整理：验收口径修正 + 资产索引）**：用户已收工待定方向，本轮只做巩固性工作：'
           '①**按用户口径修正验收方式**（写入 `knowledge/04/42` §十三）：'
           '**坐标的实机检验不可行**（动画层与逻辑层不对齐）⇒ 一律改为**事件帧口径**——'
           '能且只应用图像识别确定"事件发生在哪一帧"（单位出生、血条变动=造成伤害、面板变化、上限突破）；'
           '并逐项给出修正后的验收方式（1.2 改用解包自洽+模拟器行为；1.1/1.3/1.4/2.1 用事件帧；'
           '2.2 用暂停驱动在实机验证；2.6 用界面语义而非坐标匹配）；'
           '②**新增 `knowledge/04/45_资产索引_可复用工具与脚本.md`**：把采集通道、识别、时钟与协议、导航、'
           '应用脚本、模拟器侧脚本、PRTS+ 使用要点（含 ASCII 路径、`--autoenter` 语义、"第一秒内暂停"、'
           '封顶会卡死等）整理成索引，供下次直接接续、避免重复建设；'
           '③不推进新方向（等用户整理出的修改方向）；'
           '④合规：仅整理文档与索引；未触碰游戏、未消耗理智。 | 2026-09-14 |')
    r = r.replace(ra, add + ra, 1)
    io.open(REG, 'w', encoding='utf-8', newline='').write(r)
    print('台账已追加第七十四轮')

    for f, sub in ((ACC, r'knowledge\04_数据对应与核验'), (IDX, r'knowledge\04_数据对应与核验'),
                   (REG, 'management')):
        shutil.copy2(f, os.path.join(DST, sub, os.path.basename(f)))
    print('同步完成')


if __name__ == '__main__':
    main()
