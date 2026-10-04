# -*- coding: utf-8 -*-
"""append_t052_sameframe.py — 追加"同帧多操作（冻结模式）"一轮到 T-052 行。"""
import sys

sys.stdout.reconfigure(encoding='utf-8')
p = r'C:\Users\23922\Documents\ds_harness\management\tasks_registry.md'
s = open(p, encoding='utf-8').read()
lines = s.split('\n')
i = next(k for k, l in enumerate(lines) if l.startswith('| T-052 |'))
row = lines[i]
assert row.endswith('|'), row[-20:]

entry = (
 '【第69轮】★★★★**实现目标②的「同帧多操作（操作前先步进/暂停定位帧再执行）」**：'
 '①**先摸底**：查得现有能力 —— `plugins/action/deploy.py` 已有 `ensure_paused/pause/resume/frame_of`、'
 '`plugins/action/win_input.py` 已有 `key_down/key_up`（F 键语义 = 按下暂停/松开恢复）；'
 '但 `axis_runner` 只**统计**同帧组（`group_same_frame`）而**未实现**"同帧内连续下发"'
 '⇒ 顺序执行会把同帧的第二条挤到下一帧；'
 '②**新增 `plugins/clock/frame_lock.py`（冻结控制器）**：三种模式 —— '
 '**`sim`**（dry-run/离线：不注入任何输入，只记录"冻结帧"，**完全可离线回归**）、'
 '**`win`**（Windows 注入：`key_down(pause_key)` 冻结 → 必要时按 `step_key` 步进对齐相位 → `key_up` 恢复）、'
 '**`adb`**（点暂停按钮坐标；过帧用按键事件）；缺参数**报错而不静默降级**；'
 '③**改 `plugins/task/axis_runner.py`**：新增配置 `same_frame_mode`（默认 `sequential` 保持不变）与 `freeze` 段；'
 '`freeze` 模式下把**同一目标帧的连续操作归为一组** ⇒ **一次冻结内连续下发**（冻结→步进→执行→恢复）；'
 '每条记录新增可审计字段 `group_id/group_size/frozen/frozen_frame/frozen_mode/frozen_steps`，'
 '返回体新增 `same_frame_mode/frozen_groups/frozen_ops/frozen_mismatch`；'
 '④**新增回归 `code/vision/apps/test_same_frame.py`（合成轴表：两条部署同帧 411）**：'
 '**冻结模式** `frozen_groups=1、frozen_ops=2、两条同 group_id`、`frozen_frame` 一致且 = 411、'
 '`frozen_mismatch=0`；**顺序模式无回归**（`frozen` 全 False）；并显式断言"冻结模式下两条 target_frame 完全相同"'
 '—— 这正是冻结模式存在的理由；'
 '⑤**配置落地**：`code/vision/configs/axis_1-1.json` 增加 `same_frame_mode`（保持 `sequential`，因 1-1 轴表无同帧组）'
 '与 `freeze` 段（`mode=sim`，实机前须改 win/adb 并标定按键/坐标）；'
 '⑥**文档**：`ak/axis/README.md` 新增 **§五 同帧多操作**（配置样例、行为、可审计字段、已验证结果、'
 '**实机前置条件**：F=按下暂停/松开恢复、ADB keyevent 无法触发 MuMu 宏、0 帧选中需宏）；'
 '`00_结论索引.md` 新增 **B31**；'
 '⑦**回归（两侧）**：打图侧 `test_axis_runner` **2/2、目标帧 [10,411]、0 迟到**；`test_same_frame` 全通过；'
 '模拟侧 `replay_axis` 18/18、`replay_verify5` 16/16（平均 2.19）、`verify_semantics` A1~A9 全通过；'
 '⑧**合规**：全程 **dry-run + 虚拟时钟 + `mode=sim`**，**未加载输入后端、未截图、未注入、未登录**；'
 '未触碰游戏文件/内存。 |'
)

lines[i] = row[:-1] + entry
open(p, 'w', encoding='utf-8').write('\n'.join(lines))
print('ok; new row length =', len(lines[i]))
