# -*- coding: utf-8 -*-
"""update_t052b.py — 按管理协作规则：更新 T-052 状态 + 登记新成果到 outputs_inventory。"""
import io
import sys

sys.stdout.reconfigure(encoding='utf-8')

REG = r'C:\Users\23922\Documents\ds_harness\management\tasks_registry.md'
INV = r'C:\Users\23922\Documents\ds_harness\management\outputs_inventory.md'

new_result = (
    '状态：进行中。**里程碑**：①模拟器 1-1 标定对局复刻成功（帧10 部署芬@(3,5)、帧411 部署月见夜@(3,3)，'
    '**149× 实时**、单帧 0.22ms）；②**模拟器事件帧与实机标定吻合 0~5 帧**（帧298 命中 ⇒ damage@298 差 0）；'
    '③**坐标映射确定** `row=字母序号−1 / col=数字−1`（1-1 与 h12-4 互证）；'
    '④**费用相位修正**（引擎改为 `f%30==29` 增长 ⇒ 增长落在每秒第 0 帧；配合 `cost=8` 覆盖芬后 **Δ 全归零**）；'
    '⑤**实机↔模拟器帧级对照差异 0 帧**；⑥打图线：费用尺相位帧级精度（三重验证）、流速识别（1X/2X）、'
    '过帧宏（1X:T=1.03 帧、2X:T=2.08 帧）、**关卡外严格照 MAA 走通到 1-1 演习**、'
    '卡片/绿格检测、暂停可靠确认、PRTS+ 源码与云迹宏参数提取；'
    '**断点**：实机"部署落格提交"仍未复现（点选已稳定触发绿格，已排除输入通道问题）；'
    '**已建机制**：分层汇报/结论索引/注意力纠偏/反重复清单/信息查找链条'
)

s = io.open(REG, encoding='utf-8').read()
lines = s.splitlines()
done = False
for i, ln in enumerate(lines):
    if ln.startswith('| T-052 '):
        parts = ln.split('|')
        if len(parts) >= 8:
            parts[2] = ' 进行中 '
            parts[6] = ' ' + new_result + ' '
            parts[7] = ' 2026-09-15 '
            lines[i] = '|'.join(parts)
            done = True
        break
if done:
    io.open(REG, 'w', encoding='utf-8', newline='').write('\n'.join(lines) + '\n')
    print('T-052 已更新')
else:
    print('★未找到 T-052 行')

inv = io.open(INV, encoding='utf-8').read()
rows = (
    '| **战斗模拟器（ak_sim）** | `ak\\sim\\draft\\ak_sim\\`（engine/scenario/events/mapview/stage_survey/'
    'run_stage/compare_deploy） | 定点数学(Q32.32)逐帧战斗模拟：寻路/阻挡/仇恨/伤害/费用/技能/逐帧切片(31字段)/'
    '可控RNG；**149× 实时**、单帧 0.22ms；事件帧提取与比对 | AK 模拟会话（T-052） | ✅ 可用 |\n'
    '| **打图输入与识别插件** | `ak\\code\\vision\\plugins\\action\\`（win_input/deploy/calc_view） | '
    '**Windows 层注入**（SendMessage/PostMessage/真实鼠标；key_down/key_up）；卡片动态检测、绿格检测、'
    '暂停确认 `ensure_paused`；3D 投影坐标映射 | AK 模拟会话（T-052） | ✅ 可用 |\n'
    '| **打图辅助应用** | `ak\\code\\vision\\apps\\`（speed_probe/card_probe/replay_11calib/scan_video_events） | '
    '流速识别(1X/2X)、过帧标定、卡片位置可视化、1-1 标定对局复刻、视频事件扫描 | AK 模拟会话（T-052） | ✅ 可用 |\n'
    '| **结论索引与专题文档** | `ak\\knowledge\\04_数据对应与核验\\00_结论索引.md`、`51~55_*.md` | '
    '结论索引（模拟/打图/互验/待办 四线）、划火柴与过帧标定、PRTS+ 部署实现剖析、工作前提与五项机制 | '
    'AK 模拟会话（T-052） | ✅ 可用 |\n'
)
if 'T-052）' not in inv:
    anchor = '| **Dsh 桌面语义控制**'
    idx = inv.find(anchor)
    if idx >= 0:
        end = inv.find('\n', idx)
        inv = inv[:end + 1] + rows + inv[end + 1:]
        io.open(INV, 'w', encoding='utf-8', newline='').write(inv)
        print('outputs_inventory 已登记 4 项新成果')
    else:
        print('★未找到锚点')
else:
    print('outputs_inventory 已有登记')
