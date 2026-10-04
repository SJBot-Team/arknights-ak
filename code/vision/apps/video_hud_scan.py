# -*- coding: utf-8 -*-
"""video_hud_scan.py — ★★整段视频的「游戏原生 HUD」逐帧扫描（费用数字 + 费用条相位）

## 目的
为"视频帧 ↔ 游戏帧"的映射提供**不依赖外部费用尺**的原始通道：
- **费用条填充宽度**（px） ⇒ 相位 tick（本片实测满条 ≈167px ↔ 30 帧）
- **费用数字**（大号白字，位于菱形图标右侧） ⇒ 部署导致的费用阶跃

## 方法（两遍）
**第 1 遍（一次顺序读完整段视频，纯 numpy）**
  逐帧取两个 ROI：
  - 费用条 `BAR_ROI` → 从固定起点 x=1734 起的连续白列数 = 填充 px
  - 费用数字 `NUM_ROI` → 阈值 → 连通域 → 每个数字归一化为 16×22 二值 → 352bit 向量
  对字形做**在线容忍聚类**（汉明距离 ≤ TOL 归入同一簇）。逐帧只记 `(帧, px, 簇id序列)`。

**第 2 遍（毫秒级）**
  只对**每簇代表图**跑一次 tesseract（~簇数 次，而不是每帧一次），得到"簇 → 数字"标签。

## 为什么这样做（性能）
逐帧 tesseract ≈0.1s/帧 → 10579 帧要 18 分钟；把 OCR 次数降到 ~20 次后，整片扫描 ~30s。

用法：
    python apps/video_hud_scan.py <video> <out.jsonl> [--start 0] [--end -1] [--step 1]
                                  [--templates out.json] [--montage out.png]
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys

import cv2
import numpy as np

sys.stdout.reconfigure(encoding='utf-8')

TESS = r'D:\__soft\ak\prts+\_internal\Tesseract-OCR\tesseract.exe'
TESSDATA = r'D:\__soft\ak\prts+\_internal\Tesseract-OCR\tessdata'
TMP = r'C:\Users\23922\Documents\ds_harness\ak\.tmp'

# 由 apps/locate_costbar_video.py 精确测得（帧 800/1500 完全一致）
BAR_X0, BAR_X1 = 1734, 1908
BAR_Y0, BAR_Y1 = 814, 823
BAR_FULL_PX = 167                # 满条 ≈167px ↔ 30 帧
NUM_X0, NUM_X1 = 1806, 1904
NUM_Y0, NUM_Y1 = 742, 812
GLYPH_W, GLYPH_H = 16, 22
TOL_BITS = 22                    # 容忍聚类的汉明距离阈值（共 352 bit）


def read_bar(img: np.ndarray) -> tuple[int, float]:
    """返回 (填充px, 相位tick)。

    ★阈值必须取 **110**：实测本片费用条的灰度有两种状态——
      - **运行中：254/255**
      - **暂停时 HUD 整体变暗：≈154**
      - **空条处的背景：44~66**
    因此 110 是能同时"读得到暗态、又不误吞背景"的阈值（165 会把暂停态整段漏读）。
    """
    sub = img[BAR_Y0:BAR_Y1, BAR_X0:BAR_X1]
    if sub.size == 0:
        return 0, 0.0
    g = cv2.cvtColor(sub, cv2.COLOR_BGR2GRAY)
    cols = (g > 110).sum(axis=0) >= 3
    n = 0
    for v in cols:
        if not v:
            break
        n += 1
    return n, round(n / BAR_FULL_PX * 30.0, 2)


def _vec(crop: np.ndarray) -> np.ndarray:
    small = cv2.resize(crop, (GLYPH_W, GLYPH_H), interpolation=cv2.INTER_AREA)
    return (small > 110).astype(np.uint8).ravel()


def _digit_crops(img: np.ndarray) -> list[tuple[int, np.ndarray]]:
    sub = img[NUM_Y0:NUM_Y1, NUM_X0:NUM_X1]
    if sub.size == 0:
        return []
    g = cv2.cvtColor(sub, cv2.COLOR_BGR2GRAY)
    # ★阈值必须自适应：**暂停时 HUD 会整体变暗**（实测白字降到 ~150 灰），
    #   固定 175 会整帧漏读；而固定低阈值又会把暗背景噪声带进来。
    th = max(115, int(0.60 * float(g.max())))
    _, b = cv2.threshold(g, th, 255, cv2.THRESH_BINARY)
    n, _lab, stats, _c = cv2.connectedComponentsWithStats(b, 8)
    out = []
    for i in range(1, n):
        x, y, w, h, area = (int(stats[i, 0]), int(stats[i, 1]), int(stats[i, 2]),
                            int(stats[i, 3]), int(stats[i, 4]))
        # ★宽度上限必须 ≥ 46：本字体里 '0' 的包围盒实测 **宽 43**（"10" 的 0 被 42 上限滤掉，
        #   导致费用被读成 1 ⇒ 曾出现"费用 1↔10 跳变"的假象）
        if not (26 <= h <= 60 and 6 <= w <= 60 and area >= 120):
            continue
        if area < 0.10 * w * h:
            continue
        out.append((NUM_X0 + x + w // 2, b[y:y + h, x:x + w].copy()))
    out.sort(key=lambda t: t[0])
    return out


def ocr_glyph(crop: np.ndarray) -> str:
    big = cv2.resize(crop, None, fx=8, fy=8, interpolation=cv2.INTER_CUBIC)
    big = cv2.copyMakeBorder(big, 30, 30, 30, 30, cv2.BORDER_CONSTANT, value=0)
    p = os.path.join(TMP, '_glyph.png')
    cv2.imwrite(p, big)
    for psm in ('10', '8'):
        try:
            r = subprocess.run([TESS, p, 'stdout', '-l', 'eng', '--tessdata-dir', TESSDATA,
                                '--psm', psm, '-c', 'tessedit_char_whitelist=0123456789'],
                               capture_output=True, encoding='utf-8', errors='replace',
                               timeout=15)
            t = ''.join((r.stdout or '').split())
            if t.isdigit():
                return t
        except Exception:
            pass
    return '?'


def shape_feats(crop: np.ndarray) -> tuple[int, float, float]:
    """返回 (孔洞数, 宽高比, 孔洞中心相对纵坐标)。

    ★为什么需要它：tesseract 在本字体上会**稳定误读**——
    实测 `0 → 6`、`5 → 6`（本片两个最大簇都被读成 6）。
    用"孔洞数 + 宽高比 + 孔洞纵向位置"即可无歧义地区分 `0/6/8/9/5`：
      - `8`：2 孔
      - `0`：1 孔且**宽高比大**（本字体实测 43/50 ≈ 0.86）
      - `6`：1 孔且孔洞**偏下**    `9`：1 孔且孔洞**偏上**
      - `5`：**无孔**（误读成 6 时以此纠正）
    """
    b = (crop > 0).astype(np.uint8)
    inv = 1 - b
    n, lab = cv2.connectedComponents(inv, 4)
    border = set(int(v) for v in lab[0, :]) | set(int(v) for v in lab[-1, :]) \
        | set(int(v) for v in lab[:, 0]) | set(int(v) for v in lab[:, -1])
    holes, hy = 0, 0.5
    h, w = b.shape
    for i in range(1, n):
        if i in border:
            continue
        m = (lab == i)
        if m.sum() < 4:
            continue
        holes += 1
        ys = np.nonzero(m)[0]
        hy = float(ys.mean()) / max(1, h)
    return holes, round(w / max(1, h), 3), round(hy, 3)


def label_glyph(crop: np.ndarray) -> tuple[str, str, int, float, float]:
    """★判据**不依赖 tesseract 的输出**（它在本字体上会稳定误读 `0→6`、`5→6`，
    且对部分渲染返回 `?`），而是用**字形拓扑**判定；tesseract 只作交叉印证。

    本字体实测签名（16×22 归一化前的原始包围盒）：
    | 数字 | 孔洞 | 宽高比 | 孔洞中心 y |
    |---|---|---|---|
    | 0 | 1 | **0.86** | 0.49 |
    | 4 | 1 | 0.78 | **0.47** |
    | 6 | 1 | 0.74 | **0.66** |
    | 9 | 1 | 0.74 | **0.32** |
    | 8 | **2** | 0.72 | 0.71 |
    | 1 | 0 | 0.35 | — |
    | 2/3/5/7 | 0 | 0.66~0.71 | — |
    """
    raw = ocr_glyph(crop)
    holes, aspect, hy = shape_feats(crop)
    if holes >= 2:
        lab = '8'
    elif holes == 1:
        if aspect >= 0.83:
            lab = '0'
        elif hy > 0.58:
            lab = '6'
        elif hy < 0.40:
            lab = '9'
        else:
            lab = '4'
    else:
        # 无孔洞：1/2/3/5/7（tesseract 在无孔数字上未见误读，仅 5→6 需纠正）
        lab = '5' if raw == '6' else raw
    if lab not in '0123456789':
        lab = '?'
    return lab, raw, holes, aspect, hy


class Bank:
    """在线容忍聚类：medoid 向量 + 计数。"""

    def __init__(self, tol: int = TOL_BITS, cap: int = 300):
        self.tol, self.cap = tol, cap
        self.vecs: list[np.ndarray] = []
        self.crops: list[np.ndarray] = []
        self.counts: list[int] = []
        self.labels: list[str] = []

    def add(self, crop: np.ndarray) -> int:
        v = _vec(crop)
        best, bd = -1, 10 ** 9
        for i, u in enumerate(self.vecs):
            d = int(np.count_nonzero(u != v))
            if d < bd:
                best, bd = i, d
        if best >= 0 and bd <= self.tol:
            self.counts[best] += 1
            return best
        if len(self.vecs) >= self.cap:
            self.counts[best] += 1
            return best
        self.vecs.append(v)
        self.crops.append(crop)
        self.counts.append(1)
        self.labels.append('?')
        return len(self.vecs) - 1


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('video')
    ap.add_argument('out')
    ap.add_argument('--start', type=int, default=0)
    ap.add_argument('--end', type=int, default=-1)
    ap.add_argument('--step', type=int, default=1)
    ap.add_argument('--templates', default=None)
    ap.add_argument('--montage', default=None)
    a = ap.parse_args()

    cap = cv2.VideoCapture(a.video)
    if not cap.isOpened():
        print('打不开视频')
        return 2
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    end = total if a.end < 0 else min(a.end, total)

    bank = Bank()
    rows = []
    f, kept = 0, 0
    while f < end:
        if not cap.grab():
            break
        if f >= a.start and (f - a.start) % a.step == 0:
            ok, img = cap.retrieve()
            if ok and img is not None:
                px, tick = read_bar(img)
                ids = [bank.add(c) for _x, c in _digit_crops(img)]
                rows.append([f, px, tick, ids])
                kept += 1
        f += 1
    cap.release()
    print(f'扫描完成：遍历 {f} 帧，采样 {kept} 帧；字形簇 {len(bank.vecs)} 个')

    for i, crop in enumerate(bank.crops):
        bank.labels[i] = label_glyph(crop)
    print('簇标签（按出现次数）：')
    order = sorted(range(len(bank.vecs)), key=lambda i: -bank.counts[i])
    for i in order:
        lab, raw, holes, aspect, hy = bank.labels[i]
        print(f'  簇{i:>3}  n={bank.counts[i]:<7} -> "{lab}"'
              f'   (tesseract="{raw}" 孔洞={holes} 宽高比={aspect} 孔y={hy})')

    with open(a.out, 'w', encoding='utf-8') as fh:
        for fr, px, tick, ids in rows:
            s = ''.join(bank.labels[i][0] for i in ids)
            fh.write(json.dumps({'f': fr, 'cost': int(s) if s.isdigit() and s else None,
                                 'bar_px': px, 'tick': tick, 'raw': s},
                                ensure_ascii=False) + '\n')
    print('已写出', a.out, len(rows), '行')

    if a.templates:
        json.dump({'labels': [l[0] for l in bank.labels],
                   'raw': [l[1] for l in bank.labels],
                   'counts': bank.counts},
                  open(a.templates, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
        print('模板标签已存', a.templates)

    if a.montage:
        cw, ch, cols = 64, 96, 8
        rr = (len(bank.vecs) + cols - 1) // cols
        sheet = np.zeros((max(1, rr) * (ch + 20), cols * cw, 3), np.uint8)
        for pos, k in enumerate(order):
            r0, c0 = divmod(pos, cols)
            y = r0 * (ch + 20)
            cv2.putText(sheet, f'{bank.labels[k][0]} n={bank.counts[k]}', (c0 * cw + 2, y + 14),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.38, (0, 255, 0), 1, cv2.LINE_AA)
            crop = bank.crops[k]
            im = cv2.resize(crop, (cw - 8, min(ch - 10, int((ch - 10)))),
                            interpolation=cv2.INTER_NEAREST)
            im = cv2.cvtColor(im, cv2.COLOR_GRAY2BGR)
            sheet[y + 18:y + 18 + im.shape[0], c0 * cw + 4:c0 * cw + 4 + im.shape[1]] = im
        cv2.imwrite(a.montage, sheet)
        print('模板拼图已存', a.montage)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
