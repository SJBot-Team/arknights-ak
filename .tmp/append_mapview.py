# -*- coding: utf-8 -*-
"""append_mapview.py — 记录：地图可视化（ASCII）落地。"""
import io
import os
import shutil
import sys

sys.stdout.reconfigure(encoding='utf-8')

REG = r'C:\Users\23922\Documents\ds_harness\management\tasks_registry.md'
DST = r'E:\__file\ak_kb\kb'

ADD = (' **P1 续：关卡地图可视化（ASCII）落地 2026-09-15**：'
       '新增 `ak_sim/mapview.py`（也是需求 6「理想目标」中地图可视界面的第一步）：'
       '把 tile 网格渲染成带**列标 A/B/C…、行标 1/2/3…** 的 ASCII 图（`^`=高台/远程可部署、'
       '`.`=地面/近战可部署、`#`=不可部署），并列出**路线**（起止点、检查点数）与**出怪**'
       '（波次、preDelay、数量、routeIndex 及其起点格）。'
       '**关键修正**：`mapData.map` 里的整数是 `mapData.tiles` 的**直接索引**（实测 1-1：code 0~62、tiles 63 个），'
       '初版误按 `tileKey` 匹配导致全格显示 `?`，已改为直接索引；tile 的可用字段实测为 '
       '`tileKey / heightType / buildableType / passableMask / playerSideMask / blackboard / effects`。'
       '**验证（1-1，7×9）**：渲染结果与关卡实际布局吻合——第 4 行整行可部署的横向通道、'
       'C 列与 F 列为纵向通道、其余多为墙或高台；'
       '**且出怪时刻与事件帧互相印证**：出怪表 `wave0 preDelay=3.0s → 猎狗pro route1(A4)`，'
       '与事件时间线的「帧 90 @3.0s spawn 猎狗pro」**精确一致**（3.0s × 30 = 90 帧）。'
       '**本轮（P1）累计交付**：通用场景加载 `scenario.py`、批量探明台账 `stage_survey.py`、'
       '通用试跑 `run_stage.py`（含随机数可控性自检，已验证同 seed 多次运行结果逐位一致）、'
       '逐帧切片补全（`engine.py::_record_frame`，单位 31 字段 + 顶层 ops/rng_draws）、'
       '事件帧框架 `events.py`（extract/summarize/compare/to_reference_format）、地图可视化 `mapview.py`；'
       '并抓取补全**第 1 章 12 关**关卡数据。'
       '**下一步（断点）**：(a) 用 `mapview` 的坐标 + 第 1 章关卡**排一个最小轴**（部署/技能/撤退各若干），'
       '跑出事件时间线作为基线；(b) 把 `compare_events` 接上视频识别事件；'
       '(c) 打图侧继续找第 1 章进关入口；(d) 地图可视化向图形界面演进（需求 6 理想目标）。'
       '合规：仅本地计算与公开仓库抓取；未触碰游戏文件/内存。 | 2026-09-15 |')

r = io.open(REG, encoding='utf-8').read()
ra = '\n\n## 冲突记录'
r = r.replace(ra, ADD + ra, 1)
io.open(REG, 'w', encoding='utf-8', newline='').write(r)
print('台账已记录')

d = os.path.join(DST, r'sim\draft\ak_sim\mapview.py')
os.makedirs(os.path.dirname(d), exist_ok=True)
shutil.copy2(r'C:\Users\23922\Documents\ds_harness\ak\sim\draft\ak_sim\mapview.py', d)
shutil.copy2(REG, os.path.join(DST, 'management', 'tasks_registry.md'))
print('同步完成')
