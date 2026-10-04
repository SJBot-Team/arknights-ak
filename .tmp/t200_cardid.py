# -*- coding: utf-8 -*-
r"""t200_cardid.py — 诊断：待部署区**卡心几何**与**头像匹配**哪个环节出问题。

模块 `operator_card.py` 记录的战斗待部署区几何：
    x = 139 + pitch·(i+0.5)，pitch = (1959−139)/n，y = 1007，头像区 x±85、y 912..1078
本脚本对 n=10/11/12 各算一遍卡心，逐卡与候选干员头像做**掩膜 NCC**，打印最佳匹配，
用来判断"是列检测错、还是头像匹配错"。
"""
from __future__ import annotations

import os
import sys

import cv2

VISION = r'C:\Users\23922\Documents\ds_harness\ak\code\vision'
sys.path.insert(0, VISION)
from plugins.recognize.operator_card import OperatorCardMatcher, _ncc, PRTS_RES  # noqa: E402

SQUAD4 = ['卡缇', '安赛尔', '芬', '泡普卡', '安德切尔', '月见夜', '斑点', '香草',
          '玫兰莎', '克洛丝', '史都华德']
NAME2ID = {
    '卡缇': 'char_130_doberm', '安赛尔': 'char_212_ansel', '芬': 'char_123_fang',
    '泡普卡': 'char_281_popka', '安德切尔': 'char_211_adnach', '月见夜': 'char_283_midn',
    '斑点': 'char_284_spot', '香草': 'char_240_wyvern', '玫兰莎': 'char_127_estell',
    '克洛丝': 'char_124_kroos', '史都华德': 'char_210_stward',
}
DEPLOY_Y = 1007
HALF = 85
Y_RANGE = (912, 1078)


def main() -> int:
    img = cv2.imread(sys.argv[1])
    m = OperatorCardMatcher()
    print(f'图：{sys.argv[1]}  {img.shape[1]}x{img.shape[0]}')
    for n in (10, 11, 12):
        pitch = (1959.0 - 139.0) / n
        print(f'\n=== n={n}  pitch={pitch:.1f} ===')
        for i in range(n):
            cx = int(139 + pitch * (i + 0.5))
            x0, x1 = max(0, cx - HALF), min(img.shape[1], cx + HALF)
            patch = img[Y_RANGE[0]:Y_RANGE[1], x0:x1]
            best = []
            for nm in SQUAD4:
                cid = NAME2ID[nm]
                p = os.path.join(PRTS_RES, 'avatar', f'{cid}.png')
                if not os.path.exists(p):
                    continue
                av = cv2.imread(p, cv2.IMREAD_UNCHANGED)
                if av is None or av.shape[2] < 4:
                    continue
                bgr, alpha = av[:, :, :3], av[:, :, 3]
                h, w = bgr.shape[:2]
                # 待部署区头像区(166 高)比头像(180)矮 ⇒ 缩放到同尺寸再比
                patch_r = cv2.resize(patch, (w, h), interpolation=cv2.INTER_AREA)
                sc = _ncc(patch_r, bgr, alpha)
                best.append((sc, nm))
            best.sort(reverse=True)
            top = '  '.join(f'{nm}:{sc:.3f}' for sc, nm in best[:3])
            print(f'  #{i:<2} cx={cx:<5} {top}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
