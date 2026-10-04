# -*- coding: utf-8 -*-
"""verify_phase_video.py — 用录像检验费用条相位识别的**长期精度**（精度 vs 时间跨度）

## 原理
2X 下 1 视频帧 = 2 逻辑帧，故相位理论值满足 `phase(frame) = (2*frame + C) mod 30`。
在一个**无封顶**的连续段内，用首帧定出常数 C，然后统计全段残差：
- 残差小且不漂移 ⇒ 相位推进速率稳定 ⇒ **相位可作为绝对计时**；
- 按"每 40 帧一段"分别统计，还能看出是否存在系统漂移。

用法：python apps/verify_phase_video.py [scan_json] [起始帧] [结束帧]
"""
from __future__ import annotations

import json
import os
import statistics
import sys

sys.stdout.reconfigure(encoding='utf-8')

TMP = r'C:\Users\23922\Documents\ds_harness\ak\.tmp'


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(TMP, 'video_scan_明日方舟(128).json')
    f_a = int(sys.argv[2]) if len(sys.argv) > 2 else 12
    f_b = int(sys.argv[3]) if len(sys.argv) > 3 else 281
    d = json.load(open(path, encoding='utf-8'))
    rows = {r[0]: (r[1], r[3]) for r in d['rows']}
    seg = [(f, rows[f][0], rows[f][1]) for f in range(f_a, f_b)
           if f in rows and rows[f][1] is not None]
    if not seg:
        print('该区间无有效样本'); return 1
    print(f'段内样本 {len(seg)} 帧（帧 {f_a}~{f_b}，费用 {seg[0][1]}~{seg[-1][1]}）')

    f0, _c0, s0 = seg[0]
    C = (s0 - 2 * f0) % 30
    res = []
    for f, c, s in seg:
        exp = (2 * f + C) % 30
        dif = (s - exp) % 30
        dif = dif - 30 if dif > 15 else dif
        res.append((f, c, s, exp, dif))
    ds = [r[4] for r in res]
    print(f'残差（实测 − 理论）：均值 {statistics.mean(ds):+.3f}  中位 {statistics.median(ds):+.1f}  '
          f'标准差 {statistics.pstdev(ds):.2f}  范围 [{min(ds)}, {max(ds)}]')
    for lim in (0, 1, 2, 3):
        k = sum(1 for x in ds if abs(x) <= lim)
        print(f'  |残差| <= {lim} 帧：{k}/{len(ds)} = {100*k/len(ds):5.1f}%')

    print('\n分段残差（每 40 帧一段，检查漂移）：')
    for i in range(0, len(res), 40):
        ch = res[i:i + 40]
        if not ch:
            continue
        dds = [x[4] for x in ch]
        print(f'  帧 {ch[0][0]:>4}~{ch[-1][0]:>4}  费用 {ch[0][1]}~{ch[-1][1]}  '
              f'残差均值 {statistics.mean(dds):+5.2f}  最大 {max(abs(v) for v in dds)}')

    span = seg[-1][0] - seg[0][0]
    print(f'\n结论提示：本段跨 {span} 视频帧 = {span*2} 逻辑帧 = {span*2/30:.1f} 逻辑秒；'
          f'若残差全程保持在 ±2 帧内且分段均值无趋势，则相位推进速率稳定、可用于绝对计时。')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
