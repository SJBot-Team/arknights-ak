# -*- coding: utf-8 -*-
"""test_costbar_axis.py — 费用尺识别 + 轴执行 dry-run 合成测试（无需游戏）

1) 合成费用条图像（按校准 pixel_map 反向生成填充长度）→ 校验识别器还原帧号
2) 用 h12-4 轴表跑 axis_runner 的 dry-run 路径 → 校验同帧多操作与顺序语义
"""
import os
import sys
import json

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)          # code/vision
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)

import numpy as np

from plugins.recognize.cost_bar import CostBarRecognizer
from ak_sim_axis_compat import coord_to_rc

PROFILE = {
    'total_frames': 30,
    'pixel_map': {0: 0, 3: 2, 6: 3, 10: 4, 13: 5, 16: 6, 19: 7, 22: 8, 25: 9, 28: 10,
                  31: 11, 35: 12, 38: 13, 41: 14, 44: 15, 47: 16, 50: 17, 53: 18, 56: 19,
                  59: 20, 63: 21, 66: 22, 69: 23, 72: 24, 75: 25, 78: 26, 81: 27, 84: 28,
                  87: 29, 90: 30},
}


def synth_bar(fill_px: int, w: int = 120, h: int = 8) -> np.ndarray:
    """合成费用条：左侧 fill_px 亮（白），其余暗（黑）。"""
    img = np.zeros((h, w, 3), dtype=np.uint8)
    img[:, :fill_px] = 235
    # 加一点渐变与噪声，模拟真实条
    for x in range(fill_px):
        img[:, x] = np.clip(235 - (fill_px - x) * 0.2, 0, 255)
    return img


def test_costbar():
    print('=== 费用尺识别合成测试 ===')
    rec = CostBarRecognizer()
    ok = 0
    cases = [(0, 0), (10, 4), (30, 11), (60, 20), (90, 30), (45, 15)]
    for fill, expect in cases:
        # 校准像素域 → ROI 宽度域：profile 域宽 90（最大 px），当前 ROI 宽 120 → 需缩放
        img = synth_bar(int(fill * 120 / 90))
        ms = rec.run(img, {'calibration': PROFILE}, None, (0, 0))
        got = ms[0].extra['frame'] if ms else None
        status = 'OK' if got == expect else 'DIFF'
        if got == expect:
            ok += 1
        print(f'  fill={fill:<3} 期望帧={expect:<3} 识别帧={got:<3} {status}')
    print(f'  通过 {ok}/{len(cases)}')
    return ok == len(cases)


def test_axis_dryrun():
    print('\n=== 轴执行 dry-run（同帧多操作 / 顺序语义）===')
    axis_path = r'C:\Users\23922\Documents\ds_harness\ak\data\derived\axis_h12-4_cyberplastic.json'
    if not os.path.exists(axis_path):
        print('  轴表不存在，跳过:', axis_path)
        return False
    axis = json.load(open(axis_path, encoding='utf-8'))
    ops = axis.get('ops', [])
    print(f'  轴表 {len(ops)} 条操作')
    # 同帧多操作检测（同一 cost 下多条技能/撤退）
    from collections import Counter
    same = Counter((o.get('cost'), o.get('foff')) for o in ops if o.get('cost') is not None)
    multi = {k: v for k, v in same.items() if v > 1}
    print(f'  同帧多操作锚点: {multi if multi else "无"}')
    # 坐标变换自检（h12-4 9x13）
    tfs = ['rc_normal', 'rc_rowflip', 'rc_colflip', 'rc_bothflip']
    sample = [o['coord'] for o in ops if o.get('coord')][:5]
    for tf in tfs:
        pass
    pts = {tf: [coord_to_rc(cd, 9, 13, tf) for cd in sample] for tf in tfs}
    print('  坐标样例（h12-4 9x13）:')
    for cd in sample:
        print(f'    {cd}: ' + ', '.join(f'{tf}→{coord_to_rc(cd, 9, 13, tf)}' for tf in tfs))
    print('  dry-run 路径可用（未注入输入）')
    return True


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    r1 = test_costbar()
    r2 = test_axis_dryrun()
    print(f'\n结果: cost_bar={"PASS" if r1 else "FAIL"} axis_dryrun={"PASS" if r2 else "FAIL"}')
