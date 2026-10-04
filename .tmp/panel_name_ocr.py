# -*- coding: utf-8 -*-
"""panel_name_ocr.py — ★读"干员详情面板"上的**大号干员名**（点卡后弹出）。

## 依据
- 用户指示借鉴 MAA：MAA 的战斗资源含 `template/Battle/Formation/BattleFormationOCRNameFlag.png`
  ⇒ **MAA 用 OCR 读名称**，而非匹配头像；
- 本项目实机实测：**点选卡片会弹出干员详情面板，面板标题即大号干员名**（如「芬」）。
- 本脚本先用**已有 tesseract**（`D:\\__soft\\ak\\prts+\\_internal\\Tesseract-OCR\\tesseract.exe`，
  含 `chi_sim`）读取；MAA 的 `PaddleCharOCR`（`rec/inference.onnx` + `keys.txt`）作为后续升级。

## 做法
在给定截图上，对若干候选 ROI 做 OCR，并与**编队名单**比对，输出最可能的名字。
"""
from __future__ import annotations

import os
import subprocess
import sys

import cv2

sys.stdout.reconfigure(encoding='utf-8')

TMP = r'C:\Users\23922\Documents\ds_harness\ak\.tmp'
TESS = r'D:\__soft\ak\prts+\_internal\Tesseract-OCR\tesseract.exe'
SQUAD = ['卡缇', '安赛尔', '芬', '泡普卡', '安德切尔', '月见夜',
         '斑点', '香草', '玫兰莎', '克洛丝', '史都华德']


def ocr(img, lang='chi_sim', psm=7):
    p = os.path.join(TMP, '_ocr_tmp.png')
    cv2.imwrite(p, img)
    r = subprocess.run([TESS, p, 'stdout', '-l', lang, '--psm', str(psm)],
                       capture_output=True, encoding='utf-8')
    return (r.stdout or '').strip().replace(' ', '').replace('\n', '')


def main() -> int:
    fn = sys.argv[1] if len(sys.argv) > 1 else 'live_08_select.png'
    img = cv2.imread(os.path.join(TMP, fn))
    print(f'样本 {fn}  shape={img.shape}')
    # 候选名称 ROI：**由 `panel_left.png` 目视测得** —— 「芬」位于原图 ≈(30..80, 268..312)
    cands = [(22, 258, 130, 322), (20, 250, 150, 330), (30, 265, 100, 315),
             (22, 258, 200, 322)]
    for (x0, y0, x1, y1) in cands:
        sub = img[y0:y1, x0:x1]
        big = cv2.resize(sub, None, fx=2.5, fy=2.5, interpolation=cv2.INTER_CUBIC)
        for psm in (7, 6):
            t = ocr(big, psm=psm)
            hit = [nm for nm in SQUAD if nm and nm in t]
            print(f'  ROI({x0},{y0},{x1},{y1}) psm={psm}: {t!r}'
                  f'{"  ★命中编队: " + str(hit) if hit else ""}')
        cv2.imwrite(os.path.join(TMP, f'_roi_{x0}_{y0}.png'), big)
    print(f'\n已导出各候选 ROI 放大图到 {TMP}\\_roi_*.png')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
