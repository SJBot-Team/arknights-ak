# -*- coding: utf-8 -*-
"""live_clock_probe.py — ★实机验证「费用条满次数 = 绝对时间」这条基准。

## 依据（用户 2026-09-15 给出的 PRTS+ 方案第①步）
> 「**统计费用条满的次数以记录绝对时间**」

即：费用条每满一次 = 1 秒 = **30 帧**；相位给出条内帧 ⇒ 绝对帧 = 满条次数×30 + 相位。
本脚本在**实机**上连续采样费用条，验证：
1. `CostBarRecognizer` 能否稳定读出**条内相位** `frame_in_cost`（0..29）；
2. 相位是否按 **~30 帧/秒**推进（1X 速度）；
3. **回绕（满条）是否被正确计数** ⇒ 累计绝对帧与墙钟是否一致。

安全：只截图 + 只读识别；**不注入任何输入**（纯观察）。
"""
from __future__ import annotations

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding='utf-8')

from plugins.capture.emu_window import make_capture        # noqa: E402
from plugins.recognize.cost_bar import CostBarRecognizer    # noqa: E402


def main() -> int:
    dur = float(sys.argv[1]) if len(sys.argv) > 1 else 3.0
    cap = make_capture('adb')
    rec = CostBarRecognizer()
    print(f'采样 {dur:.1f}s（费用条相位 + 满条计数）')
    print(f'{"t(s)":>6} {"相位":>5} {"fill_px":>8} {"满条次":>6} {"绝对帧":>7} {"墙钟×30":>8}  说明')
    t0 = time.perf_counter()
    prev, wraps = None, 0
    first = None
    rows = []
    fills = []
    while time.perf_counter() - t0 < dur:
        fr = cap.grab()
        ms = rec.run(fr.image, {}, None, fr.origin)
        wall = time.perf_counter() - t0
        if not ms:
            print(f'{wall:>6.2f} {"--":>5} {"--":>8} {"--":>6} {"--":>7} {wall * 30:>8.1f}  未识别')
            time.sleep(0.05)
            continue
        m = ms[0]
        ph = int(m.extra.get('frame', 0))
        fpx = int(m.extra.get('fill_px', 0))
        cycle = int(m.extra.get('total_frames', 30) or 30)
        if prev is not None and ph < prev:
            wraps += 1
        prev = ph
        fills.append(fpx)
        if first is None:
            first = (wall, ph)
        absf = wraps * cycle + ph
        note = '← 满条回绕' if (len(rows) and rows[-1][1] is not None and ph < rows[-1][1]) else ''
        rows.append((wall, ph))
        print(f'{wall:>6.2f} {ph:>5} {fpx:>8} {wraps:>6} {absf:>7} {wall * 30:>8.1f}  {note}')
        time.sleep(0.05)
    if fills:
        fs = sorted(fills)
        p95 = fs[int(0.95 * (len(fs) - 1))]
        print(f'\nfill_px: 最小 {fs[0]} / 中位 {fs[len(fs) // 2]} / p95 {p95} / **最大 {fs[-1]}**'
              f'（{len(fs)} 次采样）')
        print('★ 满条时的真实像素长度 ≈ 最大值 ⇒ 建议 `bar_px` 取该值（当前默认 '
              f'{int(rec.DEFAULT_BAR_PX)}）')
    if len(rows) >= 2 and first:
        span = rows[-1][0] - first[0]
        adv = (wraps * 30 + rows[-1][1]) - first[1]
        print(f'\n跨度 {span:.2f}s；相位推进 {adv} 帧 ⇒ **{adv / span:.1f} 帧/秒**'
              f'（1X 应为 30.0）；满条 {wraps} 次')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
