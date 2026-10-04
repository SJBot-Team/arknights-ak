# -*- coding: utf-8 -*-
"""append_t052_slice.py — 追加"逐帧切片六项必需字段补全 + 审计回归"到 T-052 行。"""
import sys

sys.stdout.reconfigure(encoding='utf-8')
p = r'C:\Users\23922\Documents\ds_harness\management\tasks_registry.md'
s = open(p, encoding='utf-8').read()
lines = s.split('\n')
i = next(k for k, l in enumerate(lines) if l.startswith('| T-052 |'))
row = lines[i]
assert row.endswith('|'), row[-20:]

entry = (
 '【第82轮】★★★★**逐帧切片六项必需字段补全并加"有值"回归（目标①）**：'
 '①**先审计（新增 `sim/draft/audit_slice.py`）**：对 1-1 复刻的 300 帧切片逐键统计 —— '
 '顶层已有 `f/cost/life/ops/units/rng_state/rng_draws`；单位级已有 '
 '`hp/max_hp/x/y/atk/df/res/base_attack_time/attack_speed/atk_interval_frames/move_speed/...`；'
 '对照目标①「操作/血量/坐标/攻速/移速/随机判定」**发现三处缺口**：'
 '**(a) 移速**只有 `move_speed`（**上限**），**缺"当前速度向量"** ⇒ 无法复现轨迹、'
 '无法核对"出生初速为 0 的加速过程"；**(b) 攻速**只有 `interval/attack_speed`，'
 '**缺"前摇剩余/剩余冷却"** ⇒ 无法核对"前摇 18 帧后命中"这类事件帧；'
 '**(c) 随机判定**只有 `rng_state/rng_draws`（累计），**切片里看不到"本帧判了什么"**；'
 '②**补全**（`ak_sim/engine.py::_record_frame`）：单位级新增 **`vx` / `vy` / `v_abs`**（当前速度与速率）、'
 '**`atk_windup_left`**（前摇剩余；无前摇时 None）、**`atk_cd_frames`**（剩余冷却）；'
 '顶层新增 **`rng_events`**（本帧随机判定明细，经 `_rng_frame_events()`，'
 '有 `frame_events()` 用明细、否则退化为抽取次数）；'
 '③**★过程中自查出一处"假补全"并修正**：首版把字段写成 `attack_windup_frames`，'
 '而实际属性名是 **`attack_windup_left`** ⇒ 该字段**恒为 0**（"字段在但没值"）'
 '⇒ 修正为 `attack_windup_left`；'
 '④**新增回归 `sim/draft/test_slice_fields.py`（全部通过）**：'
 '不只断言"字段存在"，而是断言**在合适帧上取到非平凡值** —— '
 '**操作**：帧 10 切片含 deploy；**血量**：存在 hp<max_hp（372 条，例 1312/1325）；'
 '**坐标**：敌人 x 有 115 个不同值（在移动）；'
 '**攻速**：`atk_interval_frames>0`、`attack_speed>0`、且 **386 帧**上 `atk_windup_left` 非 None（取值 0..5+）；'
 '**移速**：`v_abs` 有 30 个不同值，且序列正是**加速过程** '
 '`[0.2533, 0.4391, 0.5753, 0.6753, 0.7485, 0.8022, …] → 停止后 0.0` '
 '（对应"出生初速为 0、按 steeringFactor 逼近上限"的惯性实现）；'
 '**随机判定**：`rng_state`/`rng_draws`/`rng_events` 三键齐备；'
 '⑤**回归**：`replay_verify5` **16/16、平均 2.19 帧、最大 7**（切片补字段**未影响任何标定结论**）；'
 '⑥**合规**：纯本地模拟计算，未触碰游戏文件/内存、未登录、未消耗资源。 |'
)

lines[i] = row[:-1] + entry
open(p, 'w', encoding='utf-8').write('\n'.join(lines))
print('ok; new row length =', len(lines[i]))
