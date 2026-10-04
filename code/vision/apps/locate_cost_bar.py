# -*- coding: utf-8 -*-
"""locate_cost_bar.py — 用「真画面 + 帧间差分」定位费用条 ROI（方法1 的标定步骤）

为什么这样标：费用条每 30 帧回绕一次、时刻在动；而它周围的 UI（费用数字、MAX 标签、
"剩余可放置角色"）是静态的 ⇒ **两帧差分**能把"在动的那条细横条"单独凸显出来。

采集用 `adb exec-out screencap -p -d 2`（§7.64 实测：遮挡无关、真画面、596ms/帧）。
配合用户 §7.62 的提醒：**暂停时游戏时间冻结，采集慢无所谓**；但本条定位需要"条在动"，
所以必须在**非暂停**下采两帧（若条顶到上限停住，就要先用"故意消耗"让它继续跳）。
"""
from __future__ import annotations

import os
import subprocess
import sys
import time

import cv2
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding='utf-8')

ADB = r'D:\__soft\MuMu Player 12\shell\adb.exe'
DEV = '127.0.0.1:16384'
TMP = r'C:\Users\23922\Documents\ds_harness\ak\.tmp'
NUM_ROI = (1795, 730, 1915, 805)
TPL = os.path.join(TMP, 'tpl_h124.json')
# 费用区搜索范围：右下角（数字下方到"剩余可放置角色"之间）
SEARCH = (1650, 700, 1920, 900)


def shot(path):
    t0 = time.perf_counter()
    with open(path, 'wb') as f:
        subprocess.run([ADB, '-s', DEV, 'exec-out', 'screencap', '-p', '-d', '2'],
                       stdout=f, stderr=subprocess.DEVNULL)
    return time.perf_counter() - t0


def main():
    a = os.path.join(TMP, 'bar_a.png')
    b = os.path.join(TMP, 'bar_b.png')
    dt1 = shot(a)
    time.sleep(0.9)
    dt2 = shot(b)
    ia, ib = cv2.imread(a), cv2.imread(b)
    if ia is None or ib is None:
        print('截图失败')
        return 2
    print(f'两帧采集耗时 {dt1*1000:.0f}ms / {dt2*1000:.0f}ms，形状 {ia.shape}')

    # 费用数字是否读得到（判断是否在战斗画面上）
    try:
        from plugins.recognize.cost_number import CostNumberRecognizer
        rec = CostNumberRecognizer()
        spec = {'roi': list(NUM_ROI), 'templates': TPL}
        for tag, img in (('帧A', ia), ('帧B', ib)):
            ms = rec.run(img, spec, None, (0, 0))
            print(f'  {tag} 费用数字 = {ms[0].extra["cost"] if ms else None}')
    except Exception as e:
        print('  费用数字识别异常:', e)

    x0, y0, x1, y1 = SEARCH
    ga = cv2.cvtColor(ia[y0:y1, x0:x1], cv2.COLOR_BGR2GRAY).astype('float32')
    gb = cv2.cvtColor(ib[y0:y1, x0:x1], cv2.COLOR_BGR2GRAY).astype('float32')
    diff = np.abs(ga - gb)
    row = diff.mean(axis=1)
    print('\n逐行"帧间差分"能量（只列 > 3 的行；行号是绝对 y）：')
    cand = []
    for i, v in enumerate(row):
        if v > 3.0:
            cand.append((y0 + i, round(float(v), 2)))
            print(f'   y={y0+i:4d}  diff={v:6.2f}')
    if not cand:
        print('   （无显著变化 ⇒ 费用条此刻是静止的：可能顶在上限。需要先"故意消耗"让它跳）')

    # 把候选行合并成带状区域，并测每带的"横向连续性"（条是一整条横线）
    if cand:
        ys = [c[0] for c in cand]
        bands = []
        s = ys[0]
        prev = ys[0]
        for y in ys[1:]:
            if y - prev > 2:
                bands.append((s, prev))
                s = y
            prev = y
        bands.append((s, prev))
        print('\n候选条带与横向特征：')
        for (ya, yb) in bands:
            seg = diff[ya - y0:yb - y0 + 1, :].mean(axis=0)
            frac = float((seg > seg.max() * 0.5).mean())     # 变化覆盖的横向比例
            print(f'   y∈[{ya},{yb}]  横向覆盖 {frac*100:5.1f}%  峰值 {seg.max():6.2f}'
                  f'  {"← 像费用条（长横条）" if frac > 0.55 else ""}')
    print(f'\n（搜索框 {SEARCH}；可用于把 ROI 缩小到具体条带后写进配置）')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
