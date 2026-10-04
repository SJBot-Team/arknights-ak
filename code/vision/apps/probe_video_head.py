# -*- coding: utf-8 -*-
"""probe_video_head.py — 扫录像开头，判断它是否是"初始 10 费 + 立刻 −10（令部署）"的那一局

## 判别依据
作者轴表前半段：**令 @1.5s 部署（10 费）** ⇒ 录像开头应出现：
  ① 开局费用 = **10**（H12-4 初始费用）；
  ② 约 1.5 逻辑秒（2X 下 ≈ 22 视频帧）处费用**下降 10**。
若某份录像满足这两点，就很可能与作者轴表配对，可做逐条事件对齐；
否则只能用于验证识别/计时口径（§7.150）。

用法：python apps/probe_video_head.py <视频1> [视频2 ...]
"""
from __future__ import annotations

import os
import sys

import cv2

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding='utf-8')

from plugins.recognize.cost_number import CostNumberRecognizer       # noqa: E402

TMP = r'C:\Users\23922\Documents\ds_harness\ak\.tmp'
TPL = os.path.join(TMP, 'tpl_h124.json')
NUM_ROI = (1795, 730, 1915, 805)
MIN_CONF = 0.85
HEAD = 900          # 扫开头多少帧


def probe(path, rec, head=HEAD):
    cap = cv2.VideoCapture(path)
    if not cap.isOpened():
        print('打不开:', path); return None
    fps = cap.get(cv2.CAP_PROP_FPS)
    spec = {'roi': list(NUM_ROI), 'templates': TPL}
    seq = []
    for fr in range(head):
        ok, img = cap.read()
        if not ok:
            break
        if img.shape[1] != 1920 or img.shape[0] != 1080:
            img = cv2.resize(img, (1920, 1080), interpolation=cv2.INTER_LINEAR)
        ms = rec.run(img, spec, None, (0, 0))
        c = None
        if ms and float(ms[0].extra.get('confidence', 0.0)) >= MIN_CONF:
            c = int(ms[0].extra['cost'])
        seq.append(c)
    cap.release()
    # 变化点
    chg = []
    prev = None
    for i, c in enumerate(seq):
        if c is None:
            continue
        if prev is not None and c != prev:
            chg.append((i, prev, c))
        prev = c
    return {'fps': fps, 'head': len(seq), 'first': next((c for c in seq if c is not None), None),
            'changes': chg}


def main():
    paths = sys.argv[1:]
    if not paths:
        d = r'E:\MUMU共享文件夹\VideoRecords\H12-4\双'
        paths = [os.path.join(d, f) for f in sorted(os.listdir(d))
                 if f.startswith('明日方舟') and f.endswith('.mp4')]
    rec = CostNumberRecognizer()
    for p in paths:
        r = probe(p, rec)
        if r is None:
            continue
        NF = 15.0 if r['fps'] < 40 else 30.0     # 2X 下 1 逻辑秒 = 15 视频帧
        print(f'\n=== {os.path.basename(p)}  fps={r["fps"]:.2f}  扫 {r["head"]} 帧 ===')
        print(f'   开局费用 = {r["first"]}')
        print('   费用变化（前 12 次）：')
        for i, a, b in r['changes'][:12]:
            tag = ''
            if b < a:
                tag = f'   ★消耗 {b-a}（部署）@ {i/NF:.2f} 逻辑秒'
            print(f'      帧{i:>4} ({i/NF:6.2f} 逻辑秒)  {a} → {b}{tag}')
        first_drop = next(((i, a - b) for i, a, b in r['changes'] if b < a), None)
        if first_drop:
            i, dc = first_drop
            match = (r['first'] == 10 and abs(dc - 10) <= 1 and i / NF <= 6)
            print(f'   ⇒ 首次消耗 {dc} @ {i/NF:.2f} 逻辑秒；'
                  f'{"★与作者轴表(令@1.5s,10费)高度吻合，可用于逐条对齐" if match else "与作者轴表不符（仅供口径验证）"}')
        else:
            print('   ⇒ 开头无消耗（不是作者那一局的起手）')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
