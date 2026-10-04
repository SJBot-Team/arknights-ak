# -*- coding: utf-8 -*-
"""axis_io.py — **共用轴表**的读写与转换（模拟器 / 打图端 / 校验器共用）。

## 为什么
用户需求明确要求「与模拟**共用易读易改的轴表**」。
本模块把"一份 YAML"变成三方共用的唯一事实来源：
- **模拟器**：`axis_to_deploy_plan()` → 逐帧部署计划；
- **打图端**：同样的 `deploys` 段 → 逐步操作（帧号 → 暂停态定位后执行）；
- **校验器**：`expect` 段 → 与实机/模拟事件对轴；`video_axis` 段 → 视频帧 ↔ 游戏帧换算。

## 轴表格式（见 `ak/axis/1-1.yaml`）
```
stage / stage_code / level / squad / deploys / expect / video_axis
```
- `deploys[].at`：`{frame: N}` 或 `{sec: X}`（frame 优先）
- `deploys[].cell`：标定表记法（字母=row+1、数字=col+1）
- `expect[]`：`{frame, kind∈spawn|dmg|kill|block, victim, src, note}`

## 用法
```python
from axis_io import load_axis, axis_to_deploy_plan, cells_letter_to_rc
ax = load_axis('1-1')
plan = axis_to_deploy_plan(ax)          # {frame: [(char_id, (row,col), dir, cost)]}
```
"""
from __future__ import annotations

import os
import sys
from typing import Any

import yaml

sys.stdout.reconfigure(encoding='utf-8')

# 轴表目录：ak/axis/  （本文件位于 ak/sim/draft/ ⇒ 上溯 3 级到 ak）
AXIS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))), 'axis')


def axis_path(name: str) -> str:
    if name.endswith(('.yaml', '.yml')):
        return os.path.join(AXIS_DIR, name)
    return os.path.join(AXIS_DIR, name + '.yaml')


def load_axis(name: str) -> dict[str, Any]:
    """按关卡名（如 `1-1`）载入轴表。"""
    p = axis_path(name)
    if not os.path.exists(p):
        raise FileNotFoundError(f'轴表不存在：{p}')
    with open(p, encoding='utf-8') as f:
        return yaml.safe_load(f)


def at_to_frame(at: dict) -> int:
    """`{frame: N}` / `{sec: X}` → 游戏帧（1 秒 = 30 帧）。"""
    if at is None:
        raise ValueError('缺少 at')
    if 'frame' in at and at['frame'] is not None:
        return int(at['frame'])
    if 'sec' in at and at['sec'] is not None:
        return int(round(float(at['sec']) * 30))
    raise ValueError(f'at 需要 frame 或 sec：{at}')


def cells_letter_to_rc(tile: str, rows: int | None = None) -> tuple[int, int]:
    """标定表格子（Excel 宏表口径）→ **(row, col)**。

    ★口径（用户 2026-09-15 更正）：**列：左到右从 1 开始**；**行：下到上从 A 开始**
    ⇒ 字母 A = **最下面**一行。而本模拟器/地图数据用的是 **mapData 行（自上而下，row 0 在屏幕上方）**
    ⇒ 需翻转：`row = (rows − 1) − (字母序号)`。

    例（1-1，7 行）：`D6 → (row 3, col 5)`（中间走廊，翻转前后相同）；
    **`F4 → (row 1, col 3)`（屏幕上方）**、**`B4 → (row 5, col 3)`（屏幕下方）**。

    `rows` 省略时按 7 行（1-1）处理；调用方应尽量传入实际行数。
    """
    t = tile.strip().upper()
    letters = ''.join(ch for ch in t if ch.isalpha())
    digits = ''.join(ch for ch in t if ch.isdigit())
    li = 0
    for ch in letters:
        li = li * 26 + (ord(ch) - ord('A') + 1)
    li -= 1
    row = (int(rows) - 1 - li) if rows else li
    return row, int(digits) - 1


def squad_by_name(ax: dict) -> dict[str, dict]:
    return {m.get('name') or m['id']: m for m in (ax.get('squad') or [])}


def axis_to_deploy_plan(ax: dict) -> dict[int, list[tuple]]:
    """轴表 → `{帧: [(char_id, (row,col), dir, cost)]}`（模拟器直接可用）。"""
    name2m = squad_by_name(ax)
    plan: dict[int, list[tuple]] = {}
    for d in (ax.get('deploys') or []):
        f = at_to_frame(d.get('at'))
        m = name2m.get(d.get('op'))
        if m is None:
            raise KeyError(f'轴表里的干员 {d.get("op")!r} 不在 squad 中')
        plan.setdefault(f, []).append((m['id'], cells_letter_to_rc(d['cell']),
                                       d.get('dir') or '右',
                                       d.get('cost', m.get('cost_override'))))
    return plan


def axis_expect_table(ax: dict) -> list[dict]:
    """`expect` 段 → 校验器用的对应表。

    序号 `n` 的取法：
    - 轴表里**显式写了 `n:`** ⇒ 用它（★用于"该组更早还有未标注事件"的情形，
      例如 1-1 的「461 猎狗命中芬」实为该组第 1 次，第 0 次在帧 418 但标定未标）；
    - 否则按 `(kind, victim, src)` 自动累计。
    """
    seen: dict[tuple, int] = {}
    out = []
    for e in (ax.get('expect') or []):
        key = (e.get('kind'), e.get('victim'), e.get('src'))
        auto = seen.get(key, 0)
        seen[key] = auto + 1
        out.append({'frame': int(e['frame']), 'kind': e['kind'], 'victim': e.get('victim'),
                    'src': e.get('src'), 'n': int(e['n']) if e.get('n') is not None else auto,
                    'note': e.get('note')})
    return out


def video_to_game(ax: dict, video_frame: int, dump: dict[int, float] | None = None):
    """视频帧 → 游戏帧。

    - 若给了逐帧 dump（`{视频帧: 游戏帧}`），直接查表（最准）；
    - 否则用 `video_axis.anchors` 做**最近锚点 + 段内 1:1** 的近似。
    """
    if dump:
        return dump.get(video_frame)
    anchors = ((ax.get('video_axis') or {}).get('anchors')) or []
    if not anchors:
        return None
    best = min(anchors, key=lambda a: abs(int(a['video']) - video_frame))
    return int(best['game']) + (video_frame - int(best['video']))


def load_axis_dump(ax: dict) -> dict[int, float]:
    """载入 `video_axis.full_dump`（`.tmp/axis_full.jsonl`）为 `{视频帧: 游戏帧}`。"""
    import json
    rel = (ax.get('video_axis') or {}).get('full_dump')
    if not rel:
        return {}
    root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    p = os.path.join(root, *rel.replace('\\', '/').split('/'))
    if not os.path.exists(p):
        return {}
    out = {}
    for line in open(p, encoding='utf-8'):
        r = json.loads(line)
        out[int(r['f'])] = float(r['B'])
    return out


# ---------------------------------------------------------------- 打图端桥接
def axis_to_runner_ops(ax: dict) -> list[dict]:
    """共用轴表 → **打图端执行器**（`code/vision/apps/run_axis.py`）的 `ops` 列表。

    ★两套费用语义（**不要混**，本轮实测踩过）：
    - 打图端 `ops[].cost` = **费用锚点**（该时刻 HUD 的**显示费用**），配合 `foff`（费用内帧）
      反推绝对帧：`帧 = (显示费用 − 初始费用 + 净累计消耗) × 每费帧数 + foff`；
    - 我们轴表里的 `cost` = **单位部署费用**（模拟器扣费用）。
    ⇒ 因此本函数把 `cost_anchor` 写成打图端的 `cost`，并把 `frame % 30` 写成 `foff`；
      单位部署费用另存 `unit_cost` 供查阅（也进配置的 `unit_costs`）。

    打图端既有格式（见 `ak/data/derived/axis_h12-4_cyberplastic.json`）：
      `{"op":"deploy","unit":"令","coord":"C12","dir":"上","cost":11,"foff":15,"abs_seconds":1.5}`
    """
    ops: list[dict] = []
    init = float((ax.get('level') or {}).get('initial_cost') or 10)
    spent = 0.0
    for d in (ax.get('deploys') or []):
        f = at_to_frame(d.get('at'))
        ucost = d.get('cost', (squad_by_name(ax).get(d.get('op')) or {}).get('cost_override'))
        anchor = d.get('cost_anchor')
        if anchor is None:      # 未显式给出 ⇒ 按"初始费用 + 自然回费 − 已消耗"推
            anchor = int(init + f // 30 - spent)
        ops.append({'op': 'deploy', 'unit': d.get('op'), 'coord': d.get('cell'),
                    'dir': d.get('dir') or '右',
                    'cost': int(anchor),           # ← 打图端语义：费用锚点（显示费用）
                    'foff': f % 30,                # ← 费用内帧相位
                    'unit_cost': ucost,            # ← 单位部署费用（查阅用）
                    'frame': f, 'abs_seconds': f / 30.0})
        if ucost:
            spent += float(ucost)
    for s in (ax.get('skills') or []):
        f = at_to_frame(s.get('at'))
        ops.append({'op': s.get('op') or 'skill', 'unit': s.get('op_name') or s.get('unit'),
                    'foff': f % 30, 'frame': f, 'abs_seconds': f / 30.0})
    ops.sort(key=lambda o: o['frame'])
    return ops


def axis_to_derived(ax: dict) -> dict:
    """共用轴表 → 打图端"派生轴表"结构（`{level, timebase, seed, meta, ops}`）。"""
    return {
        'level': ax.get('stage'),
        'timebase': 'frame',                 # ★统一以游戏帧为准（1 秒 = 30 帧）
        'seed': (ax.get('level') or {}).get('random_seed', 0),
        'meta': {
            'source': 'ak/axis/%s.yaml（共用轴表）' % ax.get('stage'),
            'note': '由 axis_io.axis_to_derived 生成；帧号=游戏帧（进入游戏第一帧为 0）',
            'video_axis_anchors': ((ax.get('video_axis') or {}).get('anchors')) or [],
        },
        'ops': axis_to_runner_ops(ax),
    }
