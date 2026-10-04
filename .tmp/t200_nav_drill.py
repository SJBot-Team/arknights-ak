# -*- coding: utf-8 -*-
r"""t200_nav_drill.py — **状态自适应进入 1-1 演习并暂停**（T-200c）

改写自 `apps\enter_drill.py`（原为 h12-4），只改三处坐标：
  · 关卡节点 = 1-1 (947,518)      · 「演习」(1487,995)    · 「开始行动」(1655,770)
并把"暂停"改成 **点一次 → 用 `ensure_paused()` 校验**（★偶数次连点会又恢复运行，本轮踩过）。

用法：python t200_nav_drill.py
"""
from __future__ import annotations

import os
import subprocess
import sys
import time

VISION = r'C:\Users\23922\Documents\ds_harness\ak\code\vision'
sys.path.insert(0, VISION)

from plugins.action.deploy import Deployer                      # noqa: E402
from plugins.capture.emu_window import make_capture             # noqa: E402
from plugins.recognize.cost_number import CostNumberRecognizer  # noqa: E402

ADB = r'D:\__soft\MuMu Player 12\shell\adb.exe'
DEV = '127.0.0.1:16384'
NUM_ROI = (1795, 730, 1915, 805)
TPL = r'C:\Users\23922\Documents\ds_harness\ak\.tmp\tpl_h124.json'

TAP_NODE = (947, 518)      # 1-1 节点
TAP_DRILL = (1487, 995)    # 演习
TAP_START = (1655, 770)    # 开始行动
ROI_START = (1580, 700, 1760, 850)
ROI_DRILL = (1420, 960, 1560, 1035)
MIN_CONF = 0.85


def sh(*a):
    return subprocess.run([ADB, '-s', DEV, *a], capture_output=True)


def tap(x, y):
    sh('shell', 'input', 'tap', str(int(x)), str(int(y)))


def bright_ratio(img, roi, thr=200):
    x0, y0, x1, y1 = roi
    g = img[y0:y1, x0:x1]
    g = g[..., :3].mean(axis=2) if g.ndim == 3 else g
    return float((g > thr).mean())


def main() -> int:
    cam = make_capture('adb')
    rec = CostNumberRecognizer()
    spec = {'roi': list(NUM_ROI), 'templates': TPL}
    d = Deployer(cam)

    def cost():
        img = cam.grab().image
        ms = rec.run(img, spec, None, (0, 0))
        if not ms:
            return None, img
        conf = float(ms[0].extra.get('confidence', 0.0))
        return (int(ms[0].extra['cost']) if conf >= MIN_CONF else None), img

    for step in range(14):
        c, img = cost()
        if c is not None:
            print(f'  [{step}] = battle（费用读数 {c}）')
            break
        if bright_ratio(img, ROI_START) > 0.02:
            st = 'squad'
        elif bright_ratio(img, ROI_DRILL) > 0.02:
            st = 'detail'
        else:
            st = 'map'
        print(f'  [{step}] 判定 = {st}')
        tap(*(TAP_START if st == 'squad' else TAP_DRILL if st == 'detail' else TAP_NODE))
        time.sleep(1.3)
    else:
        print('★ 14 步内没进到战斗')
        return 2

    # ---- 暂停：点一次 → 校验 ----
    for i in range(4):
        ok, info = d.ensure_paused()
        print(f'  [pause {i}] ensure_paused={ok} {info}')
        if ok:
            rc = d.read_cost()
            print(f'  ⇒ 已暂停：cost={rc["cost"]} tick={rc["tick"]} '
                  f'帧={d.frame_of(rc["cost"], rc["tick"])}')
            return 0
    print('★ 未能确认暂停')
    return 3


if __name__ == '__main__':
    raise SystemExit(main())
