# -*- coding: utf-8 -*-
r"""t200_prts_cardid.py — **按「赛博塑料 prts+」的方案做卡位识别**（T-200c 收官 / 用户 2026-09-29 裁决②）

复刻 prts+ 的实测常量（由 T-200g 从其打包常量表直读，`04/76 §2`）：
    OPERATOR_AREA_RATIO   = (0, 0.8, 1, 1)      # 待部署区 = 屏幕下方 20%
    SCREEN_STANDARD_SIZE  = (1280, 720)         # 参考分辨率
    AVATAR_STANDARD_SIZE  = (120, 120)
    AVATAR_CROP_SIZE      = (60, 60)            # 用于匹配的头像裁切
    TEMPLATE_MATCH_THRESHOLD = 0.8
    WHITE_THRESHOLD       = 160
头像库：`D:\__soft\ak\prts+\_internal\resource\avatar\char_<id>.png`（180×180 RGBA）。
名称映射：`operator_mapping.json`（中文名 → [char_id]）。

用法：python t200_prts_cardid.py [中文名 ...]
"""
from __future__ import annotations

import json
import os
import subprocess
import sys

import cv2
import numpy as np

sys.stdout.reconfigure(encoding='utf-8')

PRTS = r'D:\__soft\ak\prts+\_internal\resource'
AV_DIR = os.path.join(PRTS, 'avatar')
MAP_JSON = os.path.join(PRTS, 'operator_mapping.json')
ADB = r'D:\__soft\MuMu Player 12\shell\adb.exe'
DEV = '127.0.0.1:16384'
SHOT = r'C:\Users\23922\Documents\ds_harness\ak\.tmp\_prts_card.png'

AREA_RATIO = (0.0, 0.8, 1.0, 1.0)
THRESH = 0.8


def grab() -> "cv2.Mat":
    subprocess.run([ADB, '-s', DEV, 'shell', 'screencap', '-p', '/sdcard/pc.png'], capture_output=True)
    subprocess.run([ADB, '-s', DEV, 'pull', '/sdcard/pc.png', SHOT], capture_output=True)
    return cv2.imread(SHOT)


def load_avatar(char_id: str):
    p = os.path.join(AV_DIR, f'{char_id}.png')
    if not os.path.exists(p):
        return None
    return cv2.imread(p, cv2.IMREAD_UNCHANGED)


def match_in_area(area_bgr, avatar_rgba, scales=(0.75, 0.85, 0.95, 1.05)):
    """在待部署区里找该头像的最佳匹配（多尺度，取最大 NCC）。返回 (score, cx, cy)。"""
    h, w = avatar_rgba.shape[:2]
    # 用"头部"裁切（脸在上半部中央），避开被裁掉的下缘
    crop = avatar_rgba[0:int(h * 0.62), int(w * 0.16):int(w * 0.84)]
    bgr = crop[..., :3].astype(np.float32)
    alpha = (crop[..., 3:4].astype(np.float32) / 255.0) if crop.shape[2] == 4 else 1.0
    bgr = bgr * alpha
    best = (0.0, 0, 0)
    for s in scales:
        th, tw = max(8, int(crop.shape[0] * s)), max(8, int(crop.shape[1] * s))
        if th >= area_bgr.shape[0] or tw >= area_bgr.shape[1]:
            continue
        tpl = cv2.resize(bgr, (tw, th), interpolation=cv2.INTER_AREA)
        res = cv2.matchTemplate(area_bgr.astype(np.float32), tpl, cv2.TM_CCOEFF_NORMED)
        _, mx, _, ml = cv2.minMaxLoc(res)
        if mx > best[0]:
            best = (float(mx), int(ml[0] + tw / 2), int(ml[1] + th / 2))
    return best


def main() -> int:
    names = sys.argv[1:] or ['芬', '月见夜', '玫兰莎', '克洛丝', '卡缇', '安赛尔',
                             '泡普卡', '安德切尔', '斑点', '香草', '史都华德']
    mp = json.load(open(MAP_JSON, encoding='utf-8'))
    img = grab()
    H, W = img.shape[:2]
    x0, y0 = int(AREA_RATIO[0] * W), int(AREA_RATIO[1] * H)
    x1, y1 = int(AREA_RATIO[2] * W), int(AREA_RATIO[3] * H)
    area = img[y0:y1, x0:x1]
    # 抹掉卡片上方的费用/职业角标（顶部 ~12px）以免干扰
    print(f'待部署区 = ({x0},{y0})-({x1},{y1})  尺寸 {area.shape[1]}×{area.shape[0]}')
    out = []
    for nm in names:
        ids = mp.get(nm) or []
        if not ids:
            print(f'{nm:>5}: operator_mapping 里没有'); continue
        av = load_avatar(ids[0])
        if av is None:
            print(f'{nm:>5}: 缺头像文件 {ids[0]}.png'); continue
        sc, cx, cy = match_in_area(area, av)
        out.append((nm, ids[0], sc, cx + x0, cy + y0))
    out.sort(key=lambda t: -t[2])
    print(f'{"干员":<6}{"char_id":<18}{"NCC":>7}{"x":>7}{"y":>7}  判定')
    for nm, cid, sc, cx, cy in out:
        print(f'{nm:<6}{cid:<18}{sc:>7.3f}{cx:>7}{cy:>7}  {"✅" if sc >= THRESH else ("🟡" if sc >= 0.6 else "✗")}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
