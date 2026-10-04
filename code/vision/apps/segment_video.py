# -*- coding: utf-8 -*-
"""segment_video.py — ★自动把标定视频切成"运行段 / 暂停段"，并标出段界

## 依据（上轮发现）
视频内的**相位相同、费用不同**（帧434：费用10/相位11.14；帧620：费用2/相位11.14）
⇒ 视频包含**多段**（多次战斗或素材拼接）⇒ 必须先分段再在段内建立映射。

## 方法（只用轻量的相位检测，OCR 只在需要时调用）
- 逐帧读**费用条填充**（HSV + 列投影，~ms 级）；
- 相位**恒定** ⇒ 暂停；相位**递增** ⇒ 运行；
- 连续同状态合并成段，并记录每段的起止帧、相位范围；
- 对每个"段起点/终点"抽帧做一次费用 OCR（用于判读该段状态）。

用法：
    python apps/segment_video.py <video> [end_frame]
"""
from __future__ import annotations

import json
import os
import sys

import cv2

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding='utf-8')

from apps.self_read_hud import read_cost_bar, read_cost_number   # noqa: E402

TMP = r'C:\Users\23922\Documents\ds_harness\ak\.tmp'


def main():
    vid = sys.argv[1] if len(sys.argv) > 1 else r'E:\MUMU共享文件夹\VideoRecords\1-1标定.mp4'
    end = int(sys.argv[2]) if len(sys.argv) > 2 else 4000
    cap = cv2.VideoCapture(vid)
    if not cap.isOpened():
        print('打不开视频')
        return 1
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    end = min(end, total)
    print(f'分段扫描 {os.path.basename(vid)}  帧 0~{end}（共 {total}）')

    rows = []
    f = 0
    while f < end:
        ok, img = cap.read()
        if not ok:
            break
        fill, totalpx, ratio, tick = read_cost_bar(img)
        rows.append((f, fill, tick))
        f += 1
    cap.release()

    # ★改进判据（依上一轮教训）：
    #   (1) `填充px == 0` 视为"读不到"，**剔除**后用前后有效值确定位置；
    #   (2) 用"**每帧相位增量**"判定：正常运行 ≈1.07 tick/帧；
    #       RUN   : 增量 ≥ 0.7 tick/帧
    #       PAUSE : 连续 ≥8 帧增量 < 0.35 tick/帧
    valid = [(f, tick) for (f, fill, tick) in rows if fill > 0]
    print(f'有效相位读数 {len(valid)}/{len(rows)} 帧（已剔除"读不到"的帧）')

    # 逐有效点算"每帧增量"（跨秒时 +30）
    pts = []
    for i in range(1, len(valid)):
        f0, t0 = valid[i - 1]
        f1, t1 = valid[i]
        df = max(1, f1 - f0)
        d = t1 - t0
        if d < -3:            # 跨秒归零
            d += 30.0
        pts.append((f1, d / df, f1 - f0))

    # 状态序列（按帧推进）
    state_of = {}
    f = 0
    idx = 0
    while f < end:
        while idx < len(pts) and pts[idx][0] <= f:
            idx += 1
        rate = pts[idx - 1][1] if idx > 0 else 0.0
        gap = pts[idx - 1][2] if idx > 0 else 1
        # 跨度大（读数缺失）=> 无法判定，标为 UNKNOWN
        state_of[f] = 'UNKNOWN' if gap > 12 else ('RUN' if rate >= 0.7 else 'PAUSE')
        f += 1

    segs = []
    cur = None
    for f in range(end):
        st = state_of[f]
        if cur is None or cur['state'] != st:
            if cur:
                cur['f1'] = f - 1
                segs.append(cur)
            cur = {'state': st, 'f0': f}
    if cur:
        cur['f1'] = end - 1
        segs.append(cur)
    # 合并"过短（<5 帧）的非 RUN 段"到前一段
    merged = []
    for s in segs:
        if merged and s['state'] != 'RUN' and (s['f1'] - s['f0']) < 5:
            merged[-1]['f1'] = s['f1']
        else:
            merged.append(dict(s))
    segs = merged
    # 记录每段相位范围
    tickmap = {f: t for (f, fill, t) in rows}
    for s in segs:
        ts = [tickmap.get(f) for f in range(s['f0'], s['f1'] + 1) if tickmap.get(f)]
        s['t0'] = min(ts) if ts else None
        s['t1'] = max(ts) if ts else None

    print(f'\n共 {len(merged)} 段：')
    print(f'{"#":>3} {"状态":>6} {"起始帧":>7} {"结束帧":>7} {"帧数":>6} {"相位起":>7} {"相位止":>7}')
    for i, s in enumerate(merged):
        n = s['f1'] - s['f0'] + 1
        print(f'{i:>3} {s["state"]:>6} {s["f0"]:>7} {s["f1"]:>7} {n:>6} '
              f'{s["t0"]:>7} {s["t1"]:>7}')

    # 对每个"运行段"的起点抽帧读费用（判读该段状态）
    cap = cv2.VideoCapture(vid)
    print('\n各运行段的起点费用：')
    for s in merged:
        if s['state'] != 'RUN':
            continue
        cap.set(cv2.CAP_PROP_POS_FRAMES, s['f0'])
        cap.read()
        for _ in range(min(40, s['f1'] - s['f0'])):
            ok, img = cap.read()
            if not ok:
                break
        if ok:
            c = read_cost_number(img)
            print(f'  运行段 @帧 {s["f0"]}~{s["f1"]}: 费用 ≈ {c}')
    cap.release()

    out = os.path.join(TMP, 'segments.json')
    json.dump({'segments': merged, 'n_frames': len(rows)},
              open(out, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(f'\n分段结果已存 {out}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
