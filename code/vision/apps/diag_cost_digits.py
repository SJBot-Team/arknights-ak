# -*- coding: utf-8 -*-
"""diag_cost_digits.py — 诊断费用数字识别：为什么两位数字会丢首位/误判。

用**已有实机帧**做带标签回归（标签从抽样时序图人工读出）：
  runframes/f005..f012（费用 10,10,12,14,15,17,19,20）、r29_battle.png（20）
逐帧打印：ROI → 字形切分框 → 分类结果，定位是"切分没切出两位"还是"模板匹配错"。
"""
import os
import sys

import cv2
import numpy as np

APP = r'C:\Users\23922\Documents\ds_harness\ak\code\vision\apps'
sys.path.insert(0, APP)
sys.path.insert(0, os.path.dirname(APP))
sys.stdout.reconfigure(encoding='utf-8')

from video_cost_timeline import _segment, classify, glyphs_in_roi, load_templates  # noqa: E402

TMP = r'C:\Users\23922\Documents\ds_harness\ak\.tmp'
TPL = os.path.join(TMP, 'tpl_h124.json')
ROI = (1795, 730, 1915, 805)

CASES = [
    (os.path.join(TMP, 'runframes', 'f005.png'), 10),
    (os.path.join(TMP, 'runframes', 'f006.png'), 10),
    (os.path.join(TMP, 'runframes', 'f007.png'), 12),
    (os.path.join(TMP, 'runframes', 'f008.png'), 14),
    (os.path.join(TMP, 'runframes', 'f009.png'), 15),
    (os.path.join(TMP, 'runframes', 'f010.png'), 17),
    (os.path.join(TMP, 'runframes', 'f011.png'), 19),
    (os.path.join(TMP, 'runframes', 'f012.png'), 20),
    (os.path.join(TMP, 'r29_battle.png'), 20),
]


def main():
    tpl = load_templates(TPL) if os.path.exists(TPL) else {}
    print(f'模板位数={len(tpl)} 数字={sorted(tpl)}')
    for path, expect in CASES:
        img = cv2.imread(path, cv2.IMREAD_GRAYSCALE)
        if img is None:
            print(f'{os.path.basename(path):<16} 读不到')
            continue
        x0, y0, x1, y1 = ROI
        crop = img[y0:y1, x0:x1]
        segs = _segment(crop)
        boxes = [(s[0], s[1], s[2].shape[1], s[2].shape[0]) for s in segs]
        gl = glyphs_in_roi(crop, 0)
        val, conf = classify(gl, tpl) if gl else (None, 0.0)
        ok = 'OK ' if (val is not None and int(val) == expect) else 'BAD'
        print(f'{ok} {os.path.basename(path):<16} 期望 {expect:<3} 得到 {str(val):<4} conf={conf:.3f} '
              f'切分 {len(segs)} 段 {boxes}')


if __name__ == '__main__':
    main()
