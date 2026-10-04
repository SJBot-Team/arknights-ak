# -*- coding: utf-8 -*-
"""compare_latter_half.py — ★工作流第 3 步的**可复现产物**：
把「视频侧（图像识别）击破数变化帧」与「模拟器 kill/despawn 帧」放在**同一条游戏帧轴**上对照。

## 输入
- 视频侧：`ak/code/vision/apps/video_kill_counter.py` 的输出 JSONL
  （`--axis` 已把每帧映射到游戏帧 `B`；只取"值发生变化的帧"）
- 模拟器侧：本脚本自己跑 1-1 的复刻（帧10 部署芬、帧411 部署月见夜）

## 输出
- 对照表：第 n 次击杀的 视频侧游戏帧 / 模拟器帧 / 偏差
- 计数器读数序列（自动把明显的 OCR 误读按"单调不减 + 分母 33"纠正）
"""
from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding='utf-8')

from ak_sim.engine import Battle              # noqa: E402
from ak_sim.scenario import Scenario          # noqa: E402

STAGE = '1-1'
FANG, MIDN = 'char_123_fang', 'char_283_midn'
DEPLOYS = [(10, FANG, 'D6', '左', 8), (411, MIDN, 'D4', '上', None)]
FRAMES = 1510
KC = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                  '..', '..', '.tmp', 'kc_full.jsonl')


def to_rc(tile):
    return ord(tile[0]) - 65, int(tile[1:]) - 1


def video_kills():
    """从计数器扫描结果里提取"值变化"的游戏帧序列（含 OCR 误读纠正）。

    ★纠正规则（由放大图逐字核对得到的地面真值反推）：
    本片计数器真值序列为 `0,1,2,3,4,5,6,7`，而字形识别把 **`5` 稳定误读成 `9`**
    （且该误读会连续出现在多个变化帧上）。因此：
    1. **同一原串连续出现** ⇒ 视为"同一个计数状态"，只取第一次（否则一个误读会吃掉多个增量）；
    2. `v == prev + 1` ⇒ 直接接受；
    3. `v > prev + 1` ⇒ 判为误读，**钳到 `prev + 1`** 并接受（保留该帧的时间信息）；
    4. `v <= prev` ⇒ 判为误读，丢弃。
    """
    path = os.path.abspath(KC)
    if not os.path.exists(path):
        print(f'（缺视频侧数据 {path}，请先跑 apps/video_kill_counter.py）')
        return []
    rows = [json.loads(l) for l in open(path, encoding='utf-8')]
    out, prev, last_raw = [], 0, None
    for r in rows:
        s = (r.get('raw') or '').strip()
        if '/' not in s:
            continue
        num, den = s.split('/', 1)
        if den != '33' or not num.isdigit():
            continue
        if s == last_raw:
            continue                      # 同一状态（含误读的连续重复）
        v = int(num)
        if v > 33:
            continue
        if v == prev + 1:
            prev = v
            last_raw = s
            out.append((prev, r['f'], r.get('B')))
        elif v > prev + 1:
            prev = prev + 1
            last_raw = s
            out.append((prev, r['f'], r.get('B')))
    return out


def sim_kills():
    sc = Scenario(STAGE)
    b = Battle(sc.stage_code, seed=0, record=True, record_every=1, max_frames=FRAMES)
    plan = {}
    for f, char, tile, direc, cov in DEPLOYS:
        plan.setdefault(f, []).append((char, to_rc(tile), direc, cov))
    kill_frames, uid_name = [], {}
    for _ in range(FRAMES):
        b.tick()
        if b.frame in plan:
            for char, (r, c), direc, cov in plan[b.frame]:
                b.deploy(char, r, c, direction={'左': '左', '上': '上'}[direc],
                         elite=2, level=90, potential=6, trust=200,
                         skill_index=0, skill_level=7, cost=cov)
    for l in b.logs:
        if l.kind == 'kill':
            kill_frames.append(l.frame)
            uid_name[l.frame] = l.detail.get('tgt')
    return kill_frames, uid_name


def main():
    vk = video_kills()
    sk, names = sim_kills()
    print('★视频侧（图像识别「ENEMY x/33」计数器）')
    print(f'{"击破数":>5} {"视频帧":>7} {"游戏帧B":>9}')
    for v, f, bb in vk:
        print(f'{v:>5} {f:>7} {("%.1f" % bb) if bb is not None else "-":>9}')
    print(f'\n★模拟器侧 kill 帧（1-1 复刻，{FRAMES} 帧）: {sk}')
    print('  目标:', ', '.join(f'{f}:{n}' for f, n in names.items()))

    print('\n★对照（第 n 次击杀）')
    print(f'{"#":>3} {"视频侧游戏帧":>12} {"模拟器帧":>9} {"偏差":>7}')
    vs = [bb for _v, _f, bb in vk if bb is not None and bb > 0]
    n = min(len(vs), len(sk))
    for i in range(n):
        print(f'{i + 1:>3} {vs[i]:>12.1f} {sk[i]:>9} {sk[i] - vs[i]:>+7.0f}')
    if n:
        diffs = [abs(sk[i] - vs[i]) for i in range(n)]
        print(f'  平均|偏差| {sum(diffs) / n:.1f} 帧；≤10 帧 {sum(1 for d in diffs if d <= 10)}/{n}')
    print('\n注：第 1 次击杀在视频侧只能被"计数器已为 1"约束（更早的读数被 OCR 读成 "/33"），')
    print('    故其游戏帧是**上界**；其余各次为变化帧，精度 ±2 帧。')


if __name__ == '__main__':
    main()
