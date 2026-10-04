# -*- coding: utf-8 -*-
r"""t200_prts_cardid2.py — **忠实复刻 prts+ 的 `locate_avatar`**（T-200c；用户裁决②）

源码依据：`ak\.tmp\t200g_39_la.txt`（T-200g 从 prts+ 冻结包反汇编出的 `locate_avatar` 字节码）。

复原出的算法（逐句对应字节码）：
```python
def locate_avatar(action):
    avatars      = get_avatars(action.oper)                 # 该干员的全部头像变体
    oper_area_img = capture_game_window(ratioconfig.OPERATOR_AREA_RATIO)   # 截图→1280×720→裁下方 20%
    max_val, max_pos, max_avatar = 0, (0, 0), None
    for avatar in avatars:
        matched = cv2.matchTemplate(oper_area_img, avatar, cv2.TM_CCOEFF_NORMED)
        _, val, _, pos = cv2.minMaxLoc(matched)
        if val > max_val:  max_val, max_pos, max_avatar = val, pos, avatar
    if max_val < imgconfig.TEMPLATE_MATCH_THRESHOLD:   # 0.8
        logger.error(...)                                  # 未在待部署区找到干员
    else:
        oper_area_img = replace_avatar(oper_area_img, max_pos, max_avatar)  # 抹掉，防重复命中
        avatar_ratio_x = OPERATOR_AREA_RATIO[0] + (max_pos[0] + max_avatar.shape[1]/2) / SCREEN_STANDARD_SIZE[0]
        avatar_ratio_y = OPERATOR_AREA_RATIO[1] + (max_pos[1] + max_avatar.shape[0]/2) / SCREEN_STANDARD_SIZE[1]
        action.avatar_pos = (avatar_ratio_x, avatar_ratio_y)
```
用法：python t200_prts_cardid2.py [中文名 ...]
"""
from __future__ import annotations

import glob
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
SHOT = r'C:\Users\23922\Documents\ds_harness\ak\.tmp\_prts2.png'

AREA_RATIO = (0.0, 0.8, 1.0, 1.0)
SCREEN_STANDARD = (1280, 720)
AVATAR_STANDARD = (120, 120)
THRESHOLD = 0.8


def grab_standard():
    subprocess.run([ADB, '-s', DEV, 'shell', 'screencap', '-p', '/sdcard/p2.png'], capture_output=True)
    subprocess.run([ADB, '-s', DEV, 'pull', '/sdcard/p2.png', SHOT], capture_output=True)
    img = cv2.imread(SHOT)
    return cv2.resize(img, SCREEN_STANDARD, interpolation=cv2.INTER_AREA)


def get_avatars(char_id: str):
    """该干员的全部头像变体（对应 prts+ 的 `get_avatars`），统一缩放到 AVATAR_STANDARD。"""
    out = []
    for p in sorted(glob.glob(os.path.join(AV_DIR, f'{char_id}.png')) +
                    glob.glob(os.path.join(AV_DIR, f'{char_id}_*.png'))):
        a = cv2.imread(p, cv2.IMREAD_UNCHANGED)
        if a is None or a.shape[2] != 4:
            continue
        a = cv2.resize(a, AVATAR_STANDARD, interpolation=cv2.INTER_AREA)
        # 用 alpha 掩膜把背景置为均值，避免透明区干扰 TM_CCOEFF_NORMED
        f = a[..., :3].astype(np.float32)
        m = (a[..., 3:4].astype(np.float32) / 255.0)
        f = f * m + f.mean() * (1 - m)
        out.append(f.astype(np.uint8))
    return out


def replace_avatar(area, pos, avatar, fill=None):
    h, w = avatar.shape[:2]
    area = area.copy()
    area[pos[1]:pos[1] + h, pos[0]:pos[0] + w] = (fill if fill is not None else int(area.mean()))
    return area


def locate(area, char_id):
    best = (0.0, (0, 0), None)
    for av in get_avatars(char_id):
        if av.shape[0] > area.shape[0] or av.shape[1] > area.shape[1]:
            continue
        res = cv2.matchTemplate(area, av, cv2.TM_CCOEFF_NORMED)
        _, val, _, pos = cv2.minMaxLoc(res)
        if val > best[0]:
            best = (float(val), pos, av)
    return best


def main() -> int:
    names = sys.argv[1:] or ['芬', '月见夜', '玫兰莎', '克洛丝', '卡缇', '安赛尔',
                             '泡普卡', '安德切尔', '斑点', '香草', '史都华德']
    mp = json.load(open(MAP_JSON, encoding='utf-8'))
    img = grab_standard()
    H, W = img.shape[:2]
    x0, y0 = int(AREA_RATIO[0] * W), int(AREA_RATIO[1] * H)
    x1, y1 = int(AREA_RATIO[2] * W), int(AREA_RATIO[3] * H)
    area = img[y0:y1, x0:x1].copy()
    print(f'标准尺度 {W}×{H}｜待部署区 ({x0},{y0})-({x1},{y1}) = {area.shape[1]}×{area.shape[0]}｜阈值 {THRESHOLD}')
    print(f'{"干员":<6}{"char_id":<18}{"最佳NCC":>9}{"屏幕x":>8}{"屏幕y":>8}  判定')
    rows = []
    for nm in names:
        ids = mp.get(nm) or []
        if not ids:
            print(f'{nm:<6}(无映射)'); continue
        val, pos, av = locate(area, ids[0])
        ax = AREA_RATIO[0] + (pos[0] + (av.shape[1] / 2 if av is not None else 0)) / W
        ay = AREA_RATIO[1] + (pos[1] + (av.shape[0] / 2 if av is not None else 0)) / H
        rows.append((nm, ids[0], val, ax, ay, pos, av, area))
    rows.sort(key=lambda r: -r[2])
    for nm, cid, val, ax, ay, pos, av, _ in rows:
        sx, sy = int(ax * 1920), int(ay * 1080)
        flag = '✅' if val >= THRESHOLD else ('🟡' if val >= 0.6 else '✗')
        print(f'{nm:<6}{cid:<18}{val:>9.3f}{sx:>8}{sy:>8}  {flag}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
