# -*- coding: utf-8 -*-
r"""t200_shadow_probe.py — **步进过帧 + 逐帧抓图**，用于自研探测"敌人影子生成帧 / 血条变化帧"（T-200c 第 4 项）

用户 2026-09-29 指示：
> 打图端先进关时缓，**步进过帧确定敌人影子生成的时间**（prts+/MAA 中没有现成识别，自己探索可行实现），
> 再部署干员尝试定位不同单位血条，**步进过帧确认血量变化的具体帧数**。

做法：`ensure_paused`（战斗内 + 两次读数相同）→ 循环
   ①读帧（`read_cost()` → cost/tick）②截图存档 ③`resume` 一小步 ④`pause`
每张图以"读到的帧号"命名，便于事后对齐；输出 `frames.jsonl`。

用法：python t200_shadow_probe.py --start-frame 0 --end-frame 150 [--step 0.16]
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time

import cv2

VISION = r'C:\Users\23922\Documents\ds_harness\ak\code\vision'
sys.path.insert(0, VISION)
from plugins.action.deploy import Deployer                    # noqa: E402
from plugins.capture.emu_window import make_capture           # noqa: E402

ADB = r'D:\__soft\MuMu Player 12\shell\adb.exe'
DEV = '127.0.0.1:16384'
OUT = r'C:\Users\23922\Documents\ds_harness\ak\.tmp\shadow_seq'


def tap(x, y):
    subprocess.run([ADB, '-s', DEV, 'shell', 'input', 'tap', str(int(x)), str(int(y))],
                   capture_output=True)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--start-frame', type=int, default=0)
    ap.add_argument('--end-frame', type=int, default=150)
    ap.add_argument('--step', type=float, default=0.16)
    ap.add_argument('--start-battle', action='store_true', help='先点「开始行动」再暂停')
    a = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)

    d = Deployer(make_capture('adb'), ADB, DEV)
    if a.start_battle:
        tap(1655, 770)                      # 开始行动
        time.sleep(5.6)
        for _ in range(3):
            ok, info = d.ensure_paused()
            print('pause ->', ok, info)
            if ok:
                break
    ok, info = d.ensure_paused()
    print('ensure_paused =', ok, info)
    if not ok:
        print('★ 未处于「战斗且暂停」，中止')
        return 2

    rc = d.read_cost()
    f = d.frame_of(rc['cost'], rc['tick'])
    print(f'起始帧 = {f}（cost={rc["cost"]} tick={rc["tick"]}）')

    recs = []
    guard = 0
    while f is not None and f < a.end_frame and guard < 400:
        guard += 1
        path = os.path.join(OUT, f'sh_{f:04d}.png')
        subprocess.run([ADB, '-s', DEV, 'shell', 'screencap', '-p', '/sdcard/s.png'],
                       capture_output=True)
        subprocess.run([ADB, '-s', DEV, 'pull', '/sdcard/s.png', path], capture_output=True)
        recs.append({'frame': f, 'cost': rc['cost'], 'tick': rc['tick'], 'file': path})
        # 步进：恢复一小步 → 暂停
        d.resume()
        time.sleep(a.step)
        tap(1877, 76)
        time.sleep(0.28)
        rc = d.read_cost()
        nf = d.frame_of(rc['cost'], rc['tick'])
        if nf is None:
            time.sleep(0.2)
            rc = d.read_cost()
            nf = d.frame_of(rc['cost'], rc['tick'])
        if nf == f:                          # 没推进 ⇒ 再点一次暂停/恢复
            d.resume(); time.sleep(a.step); tap(1877, 76); time.sleep(0.25)
            rc = d.read_cost(); nf = d.frame_of(rc['cost'], rc['tick'])
        f = nf

    jsonl = os.path.join(OUT, 'frames.jsonl')
    with open(jsonl, 'w', encoding='utf-8') as fh:
        for r in recs:
            fh.write(json.dumps(r, ensure_ascii=False) + '\n')
    print(f'共抓 {len(recs)} 帧 → {OUT}（frames.jsonl）')
    print(f'帧范围：{recs[0]["frame"] if recs else "-"} … {recs[-1]["frame"] if recs else "-"}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
