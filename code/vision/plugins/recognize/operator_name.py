# -*- coding: utf-8 -*-
"""operator_name.py — ★读**干员详情面板**上的名称（点卡后弹出），用于卡片身份确认。

## 依据（用户指示"借鉴 MAA 实现"）
- MAA 的战斗资源含 `template/Battle/Formation/BattleFormationOCRNameFlag.png`
  ⇒ **MAA 用 OCR 读名称**，而不是匹配头像；
- 本项目实机实测：**点选卡片弹出干员详情面板，面板标题即大号干员名**（如「芬」）。
- **实测标定（本机 1920×1080）**：名称 ROI = **(20, 250, 150, 330)**；
  **tesseract `--psm 6`** 有效（`--psm 7` 无效）；原始输出含噪声（如 `'芬imm。mm'`）
  ⇒ **与候选名单做"包含匹配"** 即可稳定判定（本场景只需在 ~11 人中区分）。

## 用法
```python
from plugins.recognize.operator_name import read_selected_name
print(read_selected_name(img, candidates=SQUAD))   # → '芬' / None
```
"""
from __future__ import annotations

import os
import subprocess

import cv2
import numpy as np

TESS = r'D:\__soft\ak\prts+\_internal\Tesseract-OCR\tesseract.exe'
NAME_ROI = (20, 250, 150, 330)          # 本机实测
NAME_ROI_ALT = (18, 244, 190, 336)      # 备选（略宽）

DEFAULT_SQUAD = ['卡缇', '安赛尔', '芬', '泡普卡', '安德切尔', '月见夜',
                 '斑点', '香草', '玫兰莎', '克洛丝', '史都华德']


def _ocr(img, psm=6, lang='chi_sim') -> str:
    import tempfile
    p = os.path.join(tempfile.gettempdir(), '_dsh_name_ocr.png')
    cv2.imwrite(p, img)
    try:
        r = subprocess.run([TESS, p, 'stdout', '-l', lang, '--psm', str(psm)],
                           capture_output=True, encoding='utf-8', timeout=12)
    except Exception:                                            # noqa: BLE001
        return ''
    return (r.stdout or '').replace(' ', '').replace('\n', '')


def read_selected_name(img, candidates=None, scale=2.5) -> str | None:
    """读当前画面上"被选中干员"的名称；识别不到返回 None。

    策略：对 2 个 ROI × 2 个 psm 组合做 OCR，取**最长包含匹配**的候选名。
    """
    cands = list(candidates or DEFAULT_SQUAD)
    best, best_len = None, 0
    for roi in (NAME_ROI, NAME_ROI_ALT):
        x0, y0, x1, y1 = roi
        sub = img[y0:y1, x0:x1]
        if sub.size == 0:
            continue
        big = cv2.resize(sub, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
        for psm in (6, 4):
            t = _ocr(big, psm=psm)
            if not t:
                continue
            for nm in cands:
                if nm and nm in t and len(nm) > best_len:
                    best, best_len = nm, len(nm)
    return best


def read_selected_name_debug(img) -> dict:
    """调试用：返回各组合的原始 OCR 文本。"""
    out = {}
    for roi in (NAME_ROI, NAME_ROI_ALT):
        x0, y0, x1, y1 = roi
        big = cv2.resize(img[y0:y1, x0:x1], None, fx=2.5, fy=2.5,
                         interpolation=cv2.INTER_CUBIC)
        for psm in (6, 4):
            out[f'roi{roi}_psm{psm}'] = _ocr(big, psm=psm)
    return out


if __name__ == '__main__':
    import sys
    sys.stdout.reconfigure(encoding='utf-8')
    TMP = r'C:\Users\23922\Documents\ds_harness\ak\.tmp'
    for fn in (sys.argv[1:] or ['live_08_select.png']):
        p = os.path.join(TMP, fn)
        if not os.path.exists(p):
            print('缺样本', fn)
            continue
        img = cv2.imread(p)
        print(f'--- {fn} ---  识别 = {read_selected_name(img)!r}')
        for k, v in read_selected_name_debug(img).items():
            print(f'    {k}: {v!r}')
