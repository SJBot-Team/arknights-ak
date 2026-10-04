# -*- coding: utf-8 -*-
"""test_costbar_roi.py — ★回归：费用条识别器**必须按 ROI 取条**（修掉"整幅图取列最大值"的老 bug）。

## 老 bug（本次实机诊断发现）
`run()` 完全没有使用 `spec['roi']`，而是 `gray.max(axis=0)` 对**整幅图**取列最大值
⇒ `fill_px` 恒为 **1920**（HUD 右缘总有亮像素）
⇒ 无标定时 `frames = 1920/1920 × 30 = 30` ⇒ **恒报"满条"**。

## 本测试断言
1. **`roi_w` 必须等于 ROI 宽度**（而不是图像宽度 1920）；
2. `fill_px` 必须 **≤ bar_px**（不再恒等于图像宽）；
3. `frame` 落在 0..30，且在实机战斗截图上给出**非满条**的合理值；
4. **单调性**：把费用条 ROI 人为"填满"后 `frame` 必须增大（识别确实在量填充）；
5. **空条**：把 ROI 涂黑后 `frame == 0`。
"""
from __future__ import annotations

import os
import sys

import cv2
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding='utf-8')

from plugins.recognize.cost_bar import CostBarRecognizer       # noqa: E402

TMP = r'C:\Users\23922\Documents\ds_harness\ak\.tmp'
FAILED = []


def check(name, cond, detail=''):
    print(f'  {"✅" if cond else "❌"} {name}{("  — " + detail) if detail else ""}')
    if not cond:
        FAILED.append(name)


def _m(img, spec=None):
    ms = CostBarRecognizer().run(img, spec or {}, None, (0, 0))
    return ms[0].extra if ms else None


def main():
    p = os.path.join(TMP, 'live_11_final.png')
    if not os.path.exists(p):
        print('缺样本 live_11_final.png')
        return 1
    img = cv2.imread(p)
    e = _m(img)
    print('=== 实机战斗截图 ===')
    print(f"  读数: {e}")
    check('roi_w 等于 ROI 宽度（不再是 1920）', e['roi_w'] < 1920, f"roi_w={e['roi_w']}")
    check('fill_px ≤ bar_px（不再恒等于图像宽）', e['fill_px'] <= e['bar_px'] + 1,
          f"fill_px={e['fill_px']} bar_px={e['bar_px']}")
    check('frame 落在 0..30', 0 <= e['frame'] <= 30, f"frame={e['frame']}")
    check('★不再是恒定的"满条 30"', e['frame'] < 30, f"frame={e['frame']}（老版本恒为 30）")

    print('\n=== 人为改造 ROI：验证"识别确实在量填充" ===')
    rx0, ry0, rx1, ry1 = CostBarRecognizer.DEFAULT_ROI
    full = img.copy()
    full[ry0:ry1, rx0:rx1] = 255                     # 整条涂白 ⇒ 应≈满
    e_full = _m(full)
    check('涂满后 frame 明显增大', e_full['frame'] > e['frame'],
          f"{e['frame']} → {e_full['frame']}")
    check('涂满后 ≈ 满条(30)', e_full['frame'] >= 28, f"frame={e_full['frame']}")

    empty = img.copy()
    empty[ry0:ry1, rx0:rx1] = 0                      # 涂黑 ⇒ 空条
    e_empty = _m(empty)
    check('涂黑后 frame == 0', e_empty['frame'] == 0, f"frame={e_empty['frame']}")

    print('\n=== ROI 参数形式：绝对像素 / 相对 0~1 等价 ===')
    e_abs = _m(img, {'roi': [rx0, ry0, rx1, ry1]})
    e_rel = _m(img, {'roi': [rx0 / 1920, ry0 / 1080, rx1 / 1920, ry1 / 1080]})
    check('两种写法结果一致', e_abs['fill_px'] == e_rel['fill_px'],
          f"abs={e_abs['fill_px']} rel={e_rel['fill_px']}")

    print()
    if FAILED:
        print(f'❌ 未通过 {len(FAILED)} 项：{FAILED}')
        return 1
    print('✅ 通过：费用条识别器已按 ROI 取条，填充/帧读数合理')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
