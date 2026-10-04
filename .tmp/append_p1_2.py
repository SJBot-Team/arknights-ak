# -*- coding: utf-8 -*-
"""append_p1_2.py — 记录：逐帧切片补全 + 事件帧框架。"""
import io
import os
import shutil
import sys

sys.stdout.reconfigure(encoding='utf-8')

REG = r'C:\Users\23922\Documents\ds_harness\management\tasks_registry.md'
DST = r'E:\__file\ak_kb\kb'

ADD = (' **P1 续：逐帧切片补全（需求 1.6）+ 事件帧提取比对框架（需求 1.5）2026-09-15**：'
       '①**逐帧切片补全**（改 `ak_sim/engine.py::_record_frame`）：'
       '顶层新增 **`ops`（本帧发生的操作，顺序即执行顺序 ⇒ 直接支撑「同帧多操作」验证）** 与 '
       '**`rng_draws`（累计随机抽取次数，帧间差=本帧判定次数）**；'
       '单位字段从 12 个补到 **31 个**：新增 name/atk/df/res/base_attack_time/attack_speed/'
       'atk_interval_frames/move_speed/block_cnt/weight/flying/route_index/hidden/is_operator/'
       'is_token/skill_active/sp_raw/buffs/talents —— **对照需求 1.6 全部覆盖**：'
       '操作✅(`ops`)、血量✅、坐标✅、**攻速✅**(attack_speed+atk_interval_frames+base_attack_time)、'
       '**移速✅**(move_speed，实测猎狗pro=1.9)、**随机判定✅**(rng_state+rng_draws)；'
       '落盘仍由 `dump_frames(path, fmt, include_units)` 支持「可选择存储」；'
       '（修掉了初版把 sp 键写两次会覆盖 skill_charge 语义的问题，改名 sp_raw）；'
       '②**新增 `ak_sim/events.py`：事件帧提取与比对框架**（对应需求 1.5 预置验证定位，'
       '与用户「以事件发生的精确帧判定准确性」的口径），提供三个能力：'
       '(a) **extract_events(frames)** 导出统一事件时间线：spawn / damage_first / damage / despawn / '
       'escape / kill / death / cost_up / cost_spend / deploy / retreat / skill / cost_cap_up / '
       'life_change / civilian_arrived；(b) **compare_events(sim, ref, tol)** 把模拟事件与参考事件'
       '逐条配对，输出 matched（含帧差）/ missing / extra / max_diff；'
       '(c) **to_reference_format(events, path)** 导出**参考事件表**（帧号+秒+类型+单位+待填备注），'
       '供用户/视频识别填写真实帧 —— 正是用户所说「之后我会手动定位交给你一个便于识别核对的精确轴、'
       '标记事件发生的准确帧」所需的接收格式；'
       '③**实测（1-1，空轴 1800 帧）**：事件 88 条，类型统计 '
       'cost_up=59 / spawn=13 / despawn=8 / escape=8；'
       '**cost_up 严格每 30 帧 +1**（1.0/2.0/3.0…10.0s）⇒ 与既有结论「费用条满一次 = 30 帧」**完全一致**；'
       'spawn 事件带 key/name/hp/x/y（帧90 @3.0s 猎狗pro enemy_1000_gopro_2 hp1700 x0.509 y3.5；'
       '帧360 @12.0s 猎狗 hp820）；escape 带 life 变化（帧327 @10.9s life→9）；'
       '④**下一步（断点）**：(a) 用第 1 章关卡**排一个最小轴**并跑出事件时间线（用户指定的练手路径）；'
       '(b) 把 compare_events 接上「视频识别事件」（`apps/scan_video_events.py` 已有费用/相位识别，可扩展出生/血条）；'
       '(c) 打图侧继续找第 1 章进关入口；'
       '⑤合规：仅本地计算与公开数据仓库抓取；未触碰游戏文件/内存。 | 2026-09-15 |')

r = io.open(REG, encoding='utf-8').read()
ra = '\n\n## 冲突记录'
r = r.replace(ra, ADD + ra, 1)
io.open(REG, 'w', encoding='utf-8', newline='').write(r)
print('台账已记录')

for rel in (r'sim\draft\ak_sim\engine.py', r'sim\draft\ak_sim\events.py'):
    d = os.path.join(DST, rel)
    os.makedirs(os.path.dirname(d), exist_ok=True)
    shutil.copy2(os.path.join(r'C:\Users\23922\Documents\ds_harness\ak', rel), d)
shutil.copy2(REG, os.path.join(DST, 'management', 'tasks_registry.md'))
print('同步完成')
