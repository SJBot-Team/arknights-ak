# -*- coding: utf-8 -*-
"""measure_11.py — ★实测"11 张卡"的待部署区几何（进战斗后立即抓图 + 宽域搜索）。

做法：自动导航进 1-1 演习 → 立即抓图并存为 `row11.png` →
用**已知第一位干员（按费用升序，芬 8 费 ⇒ 卡#0）的头像**在整行区域
（x 100..1900, y 900..1080）做**宽域扫描**，找出 NCC 峰值位置 ⇒ 得到第 0 张卡的中心与头像宽度；
若峰值可信，再按等差推算整行并输出 pitch。
"""
from __future__ import annotations

import json
import os
import sys

import cv2
import numpy as np

VISION = r'C:\Users\23922\Documents\ds_harness\ak\code\vision'
sys.path.insert(0, VISION)
sys.path.insert(0, os.path.join(VISION, 'apps'))
sys.stdout.reconfigure(encoding='utf-8')

from plugins.capture.emu_window import make_capture                 # noqa: E402
from plugins.recognize.battle_hud import BattleHudGate              # noqa: E402
from plugins.recognize.operator_card import OperatorCardMatcher, _ncc  # noqa: E402
import nav_to_drill                                                 # noqa: E402

TMP = r'C:\Users\23922\Documents\ds_harness\ak\.tmp'
SQUAD = ['卡缇', '安赛尔', '芬', '泡普卡', '安德切尔', '月见夜',
         '斑点', '香草', '玫兰莎', '克洛丝', '史都华德']


def main() -> int:
    cap, gate = make_capture('adb'), BattleHudGate()
    if not gate.check(cap.grab().image)['in_battle']:
        print('不在战斗 → 自动导航')
        if nav_to_drill.main() != 0:
            return 1
    img = cap.grab().image
    p = os.path.join(TMP, 'row11.png')
    cv2.imwrite(p, img)
    m = OperatorCardMatcher(candidates=SQUAD)
    av, al = m.lib['芬']
    print(f'已存 row11.png；用「芬」头像在整行扫描（x 100..1900, y 900..1080）')
    best = (-9.0, None, None)
    for half in (60, 70, 80, 90, 100):
        for cx in range(100, 1901, 6):
            for y0 in (905, 920, 935):
                patch = img[y0:y0 + 170, cx - half:cx + half]
                if patch.shape[0] < 100 or patch.shape[1] < 40:
                    continue
                p2 = cv2.resize(patch, (av.shape[1], av.shape[0]),
                                interpolation=cv2.INTER_AREA)
                # y 带不同则裁掉头像对应高度比例
                s = _ncc(p2, av, al)
                if s > best[0]:
                    best = (s, (cx, y0, half), patch.shape)
    print(f'最佳 NCC = {best[0]:.4f}  位置/参数 = {best[1]}')
    if best[1]:
        cx, y0, half = best[1]
        patch = img[y0:y0 + 170, cx - half:cx + half]
        cv2.imwrite(os.path.join(TMP, 'row11_first.png'),
                    np.hstack([cv2.resize(patch, (180, 240)),
                               cv2.resize(av, (180, 240))]))
        print('已输出 row11_first.png（左=卡#0 最佳匹配区，右=芬头像）')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
