# -*- coding: utf-8 -*-
"""video_cost_timeline.py — 从录像中自动读出「费用数字」轨迹（离线，不接触游戏）

用途（对应 knowledge/04/41 §7.5 的开放问题）：
  * 判定录像的**回费速率/倍速**（DP 每秒增速 → 1× 还是 2×）
  * 定位每一次**消耗事件**（费用骤降的幅度 = 落场单位的费用）→ 与轴表操作表按费用配对
  * 为 `cost_bar.roi` 提供实测旁证（ROI 自动定位）

方法（零外部依赖，仅 numpy+cv2）：
  1. 自动定位右下角费用数字（白色数字，位于战场 UI 右下角带）；
  2. 按列投影切出数字字形，归一化到 16×24 二值图；
  3. **自举模板**：给少量已知时刻的读数（人工从拼图读出）→ 建立 0~9 模板；
  4. 全片扫描 → 每帧匹配最近模板 → 输出 (时间, 读数, 置信度) 与「消耗事件」列表。

命令行：
  # 1) 自举模板（labels 为 JSON：{"2": 4, "5": 10, ...}，键=秒，值=读数）
  python video_cost_timeline.py bootstrap --video X.mp4 --labels labels.json --templates tpl.json
  # 2) 全片扫描
  python video_cost_timeline.py scan --video X.mp4 --templates tpl.json --step 0.1 --out tl.json
  # 3) 生成人工复核拼图
  python video_cost_timeline.py montage --video X.mp4 --templates tpl.json --t0 0 --t1 120 --step 2 --out m.png
"""
from __future__ import annotations

import argparse
import json
import os
import sys

import cv2
import numpy as np

GLYPH_W, GLYPH_H = 16, 24


# --------------------------------------------------------------------------------------
# ROI 定位与字形切分
# --------------------------------------------------------------------------------------
def locate_cost_roi(frame: np.ndarray) -> tuple[int, int, int, int]:
    """在右下带内定位**费用数字**区域。

    关键：右下带里有多个白色数字（费用、剩余可放置角色…）。费用行在最上面，
    因此做法是：候选连通域 → 按 y 聚成若干「行」→ 取**最上面那行** → 取该行最右一段。
    """
    h, w = frame.shape[:2]
    bx, by = int(w * 0.76), int(h * 0.56)
    band = frame[by:int(h * 0.84), bx:w]
    g = cv2.cvtColor(band, cv2.COLOR_BGR2GRAY)
    ink = (g > 195).astype(np.uint8)
    n, lab, stats, cent = cv2.connectedComponentsWithStats(ink, 8)
    cand = []
    for i in range(1, n):
        x, y, bw, bh, area = stats[i]
        if bh < h * 0.014 or bh > h * 0.055 or bw < 2 or bw > w * 0.05 or area < 12:
            continue
        cand.append([x, y, bw, bh])
    if not cand:
        return 0, 0, 0, 0
    med_h = float(np.median([c[3] for c in cand]))
    # 按 y 中心分「行」（行距阈值 = 中位字高）
    cand.sort(key=lambda c: c[1] + c[3] / 2)
    rows: list[list[list[int]]] = []
    for c in cand:
        cy = c[1] + c[3] / 2
        if rows and abs(cy - (rows[-1][0][1] + rows[-1][0][3] / 2)) <= med_h * 0.9:
            rows[-1].append(c)
        else:
            rows.append([c])
    row = rows[0]                                     # 最上面一行 = 费用行
    row.sort(key=lambda c: c[0])
    # 从最右往左吸收相邻字形（多位数的各位数字 + 左侧费用图标）
    group = [row[-1]]
    left = row[-1][0]
    for c in reversed(row[:-1]):
        if left - (c[0] + c[2]) > med_h * 1.2:
            break
        group.append(c)
        left = c[0]
    x0 = min(c[0] for c in group)
    x1 = max(c[0] + c[2] for c in group)
    y0 = min(c[1] for c in group)
    y1 = max(c[1] + c[3] for c in group)
    pad = max(2, int(med_h * 0.25))
    return (bx + max(0, x0 - pad), by + max(0, y0 - pad),
            bx + min(band.shape[1], x1 + pad), by + min(band.shape[0], y1 + pad))


def lock_roi(cap, fps: float, n: int = 14, span: float = 40.0, verbose: bool = True):
    """在一段采样帧上投票锁定费用数字 ROI（同一录像内 UI 布局固定，锁定后全程复用更稳）。

    返回 (x0, y0, x1, y1, 命中率, 样本数)。命中率过低说明自动定位不可靠，应人工给 --roi。
    """
    boxes = {}
    for k in range(n):
        t = span * (k + 0.5) / n
        fr = frame_at(cap, fps, t)
        if fr is None:
            continue
        b = locate_cost_roi(fr)
        if b[2] <= b[0] or b[3] <= b[1]:
            continue
        key = (round(b[0] / 8) * 8, round(b[1] / 8) * 8, round(b[2] / 8) * 8, round(b[3] / 8) * 8)
        boxes[key] = boxes.get(key, 0) + 1
    if not boxes:
        return 0, 0, 0, 0, 0.0, 0
    best, hits = max(boxes.items(), key=lambda kv: kv[1])
    total = sum(boxes.values())
    if verbose:
        print(f'  ROI 投票：{hits}/{total} 命中 {best}（其余候选 {len(boxes)-1} 个）')
    return best[0], best[1], best[2], best[3], hits / max(1, total), total


def _segment(roi: np.ndarray) -> list[tuple[int, int, np.ndarray]]:
    """ROI 内按列投影切出候选字形：返回 [(x0, x1, 字形二值图), ...]（含费用图标）。"""
    g = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY) if roi.ndim == 3 else roi
    ink = (g > 195).astype(np.uint8)
    if ink.sum() == 0:
        return []
    cols = ink.sum(axis=0)
    groups, start = [], None
    for i, c in enumerate(cols):
        if c > 0 and start is None:
            start = i
        elif c == 0 and start is not None:
            groups.append((start, i))
            start = None
    if start is not None:
        groups.append((start, len(cols)))
    out = []
    for (a, b) in groups:
        sub = ink[:, a:b]
        rows = np.where(sub.sum(axis=1) > 0)[0]
        if len(rows) == 0:
            continue
        top, bot = rows[0], rows[-1] + 1
        out.append((a, b, sub[top:bot]))
    return out


def lock_digit_zone(cap, fps: float, roi: tuple, n: int = 16, span: float = 45.0,
                    verbose: bool = True) -> int:
    """学习「数字区左边界」：费用图标在锁定 ROI 内位置固定，跨帧重复出现的字形即图标。

    返回数字区左边界 x（ROI 内相对坐标）；0 表示不做过滤。
    """
    x0, y0, x1, y1 = roi
    if x1 <= x0:
        return 0
    sig: dict[tuple[int, int], int] = {}
    frames = 0
    for k in range(n):
        t = span * (k + 0.5) / n
        fr = frame_at(cap, fps, t)
        if fr is None:
            continue
        frames += 1
        for (a, b, _g) in _segment(fr[y0:y1, x0:x1]):
            sig[(round(a / 3) * 3, round(b / 3) * 3)] = sig.get((round(a / 3) * 3, round(b / 3) * 3), 0) + 1
    if frames == 0 or not sig:
        return 0
    cand = max(sig.items(), key=lambda kv: kv[1])
    (a, b), cnt = cand
    if cnt < frames * 0.6 or a > (x1 - x0) * 0.5:
        if verbose:
            print(f'  数字区学习：无可信固定字形（最高重复 {cnt}/{frames}）→ 不过滤')
        return 0
    if verbose:
        print(f'  数字区学习：固定字形 x∈[{x0+a},{x0+b}] 出现 {cnt}/{frames} 帧 → 判为费用图标')
    return b + 2


def glyphs_in_roi(roi: np.ndarray, x_min: int = 0) -> list[np.ndarray]:
    """切出 ROI 内的数字字形（按 x 排序），丢弃数字区左侧的固定图标与尺寸异常白块。"""
    segs = _segment(roi)
    if not segs:
        return []
    if x_min > 0:
        segs = [s for s in segs if s[0] >= x_min]
    if not segs:
        return []
    hmax = max(s[2].shape[0] for s in segs)
    keep = [s for s in segs if s[2].shape[0] >= hmax * 0.55]
    return [cv2.resize(s[2], (GLYPH_W, GLYPH_H), interpolation=cv2.INTER_AREA) for s in keep]


def glyph_vec(gly: np.ndarray) -> np.ndarray:
    return (gly.reshape(-1) > 0.5).astype(np.float32)


# --------------------------------------------------------------------------------------
# 模板匹配
# --------------------------------------------------------------------------------------
def classify(glyphs: list[np.ndarray], templates: dict) -> tuple[str | None, float]:
    if not glyphs:
        return None, 0.0
    digits, scores = [], []
    for g in glyphs:
        v = glyph_vec(g)
        best_d, best_s = None, -1.0
        for d, vecs in templates.items():
            for tv in vecs:
                t = np.asarray(tv, dtype=np.float32).reshape(-1)
                if t.shape != v.shape:
                    continue
                s = float((v == t).mean())
                if s > best_s:
                    best_s, best_d = s, d
        digits.append(best_d)
        scores.append(best_s)
    if any(d is None for d in digits):
        return None, 0.0
    return ''.join(digits), float(np.mean(scores))


def load_templates(path: str) -> dict:
    raw = json.load(open(path, encoding='utf-8'))
    return {d: [np.asarray(v, dtype=np.float32) for v in vs] for d, vs in raw.items()}


def save_templates(tpl: dict, path: str) -> None:
    out = {d: [v.astype(int).tolist() for v in vs] for d, vs in tpl.items()}
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(out, f)
    print(f'模板已保存：{path}（数字 {"".join(sorted(tpl))}）')


# --------------------------------------------------------------------------------------
# 视频读取
# --------------------------------------------------------------------------------------
def frame_at(cap, fps: float, t: float):
    cap.set(cv2.CAP_PROP_POS_FRAMES, int(round(t * fps)))
    ok, fr = cap.read()
    return fr if ok else None


def cmd_bootstrap(args):
    labels = json.load(open(args.labels, encoding='utf-8'))
    cap = cv2.VideoCapture(args.video)
    fps = cap.get(cv2.CAP_PROP_FPS)
    roi = tuple(args.roi) if (args.roi and args.roi[2] > 0) else None
    if roi is None:
        roi = lock_roi(cap, fps)[:4]
        print(f'  锁定 ROI = {roi}')
    xmin = lock_digit_zone(cap, fps, roi)
    tpl: dict[str, list] = {}
    for tstr, value in labels.items():
        t = float(tstr)
        fr = frame_at(cap, fps, t)
        if fr is None:
            continue
        x0, y0, x1, y1 = roi
        if x1 <= x0:
            print(f'  t={t}: ROI 无效')
            continue
        gl = glyphs_in_roi(fr[y0:y1, x0:x1], xmin)
        ds = str(value)
        if len(gl) != len(ds):
            print(f'  t={t}: 字形数 {len(gl)} ≠ 期望位数 {len(ds)}（值 {value}）→ 跳过')
            continue
        for g, d in zip(gl, ds):
            tpl.setdefault(d, [])
            v = (g.reshape(-1) > 0.5)
            dup = False
            for tv in tpl[d]:
                same = ((np.asarray(tv, dtype=np.float32).reshape(-1) > 0.5) == v).mean()
                if same > 0.97:
                    dup = True
                    break
            if not dup:
                tpl[d].append(g)
        print(f'  t={t:<6} 值={value:<3} 字形={len(gl)}')
    cap.release()
    save_templates(tpl, args.templates)
    print(f'ROI（像素）：{roi}')


def cmd_scan(args):
    tpl = load_templates(args.templates)
    cap = cv2.VideoCapture(args.video)
    fps = cap.get(cv2.CAP_PROP_FPS)
    n = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    roi = tuple(args.roi) if (args.roi and args.roi[2] > 0) else None
    if roi is None:
        roi = lock_roi(cap, fps)[:4]
        print(f'  锁定 ROI = {roi}')
    x0, y0, x1, y1 = roi
    xmin = lock_digit_zone(cap, fps, roi)
    rows = []
    t = args.t0
    while t <= args.t1:
        fr = frame_at(cap, fps, t)
        if fr is None:
            break
        val, conf = classify(glyphs_in_roi(fr[y0:y1, x0:x1], xmin), tpl) if x1 > x0 else (None, 0.0)
        rows.append({'t': round(t, 3), 'cost': (int(val) if val is not None and val.isdigit() else None),
                     'raw': val, 'conf': round(conf, 4)})
        t += args.step
    cap.release()

    # 消耗事件：相邻样本的下降量（扣除**局部**自然回复速率，避免倍速切换造成的误判）
    def local_regen(idx: int, win: float = 1.5) -> float:
        lo, hi = rows[idx]['t'] - win, rows[idx]['t'] + win
        deltas = []
        for a, b in zip(rows, rows[1:]):
            if lo <= a['t'] <= hi and a['cost'] is not None and b['cost'] is not None and b['cost'] >= a['cost']:
                dt = b['t'] - a['t']
                if dt > 0:
                    deltas.append((b['cost'] - a['cost']) / dt)
        return float(np.median(deltas)) if deltas else args.regen

    spend = []
    for i, (a, b) in enumerate(zip(rows, rows[1:])):
        if a['cost'] is None or b['cost'] is None:
            continue
        dt = b['t'] - a['t']
        delta = b['cost'] - a['cost']
        rg = local_regen(i)
        if delta - rg * dt < -1.5:
            spend.append({'t': b['t'], 'drop': round(rg * dt - delta, 2),
                          'from': a['cost'], 'to': b['cost'], 'conf': b['conf'],
                          'regen_local': round(rg, 3)})
    # 速率估计：分窗统计
    rate = []
    win = 10.0
    for start in range(int(rows[0]['t']), int(rows[-1]['t']), int(win)):
        seg = [r for r in rows if start <= r['t'] < start + win and r['cost'] is not None]
        if len(seg) >= 3:
            rate.append({'t0': start, 'cost_start': seg[0]['cost'], 'cost_end': seg[-1]['cost'],
                         'per_sec': round((seg[-1]['cost'] - seg[0]['cost'])
                                          / max(0.1, seg[-1]['t'] - seg[0]['t']), 3)})
    out = {'video': os.path.basename(args.video), 'fps': fps, 'frames': n, 'roi': list(roi or []),
           'samples': rows, 'spends': spend, 'rate_windows': rate}
    with open(args.out, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print(f'扫描完成：{len(rows)} 个样本，{len(spend)} 次消耗事件 → {args.out}')
    print('  消耗事件（时间 / 降幅≈单位费用 / 前后读数）：')
    for s in spend[:40]:
        print(f'    t={s["t"]:>7.1f}s  降 {s["drop"]:>5.2f}  {s["from"]}→{s["to"]}  conf={s["conf"]}')
    print('  速率窗口（DP/s；≈1 = 1×，≈2 = 2×）：')
    for r in rate[:16]:
        print(f'    t={r["t0"]:>5.0f}s  {r["cost_start"]}→{r["cost_end"]}  {r["per_sec"]:>5.2f}/s')
    return out


def cmd_montage(args):
    tpl = load_templates(args.templates)
    cap = cv2.VideoCapture(args.video)
    fps = cap.get(cv2.CAP_PROP_FPS)
    roi = tuple(args.roi) if (args.roi and args.roi[2] > 0) else None
    if roi is None:
        roi = lock_roi(cap, fps)[:4]
        print(f'  锁定 ROI = {roi}')
    tiles = []
    x0, y0, x1, y1 = roi
    xmin = lock_digit_zone(cap, fps, roi)
    t = args.t0
    while t <= args.t1:
        fr = frame_at(cap, fps, t)
        if fr is None:
            break
        crop = fr[y0:y1, x0:x1] if x1 > x0 else fr[0:10, 0:10]
        val, conf = classify(glyphs_in_roi(crop, xmin), tpl)
        crop = cv2.resize(crop, (170, 54), interpolation=cv2.INTER_CUBIC)
        cv2.putText(crop, f'{t:.0f}s', (3, 14), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (0, 255, 0), 1)
        cv2.putText(crop, f'{val}', (110, 48), cv2.FONT_HERSHEY_SIMPLEX, 0.6,
                    (0, 255, 255) if val is not None else (0, 0, 255), 2)
        tiles.append(crop)
        t += args.step
    cap.release()
    rows = []
    for i in range(0, len(tiles), 5):
        chunk = tiles[i:i + 5]
        while len(chunk) < 5:
            chunk.append(np.zeros_like(tiles[0]))
        rows.append(np.hstack(chunk))
    cv2.imwrite(args.out, np.vstack(rows))
    print(f'复核拼图 → {args.out}（{len(tiles)} 格）')


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest='cmd', required=True)
    for name in ('bootstrap', 'scan', 'montage'):
        p = sub.add_parser(name)
        p.add_argument('--video', required=True)
        p.add_argument('--roi', type=int, nargs=4, default=[0, 0, 0, 0])
        p.add_argument('--auto-roi', action='store_true', default=True)
        if name == 'bootstrap':
            p.add_argument('--labels', required=True)
            p.add_argument('--templates', required=True)
        elif name == 'scan':
            p.add_argument('--templates', required=True)
            p.add_argument('--t0', type=float, default=0.0)
            p.add_argument('--t1', type=float, default=1e9)
            p.add_argument('--step', type=float, default=0.2)
            p.add_argument('--regen', type=float, default=1.0, help='自然回复速率（1× 时 1.0/s）')
            p.add_argument('--out', required=True)
        else:
            p.add_argument('--templates', required=True)
            p.add_argument('--t0', type=float, default=0.0)
            p.add_argument('--t1', type=float, default=120.0)
            p.add_argument('--step', type=float, default=3.0)
            p.add_argument('--out', required=True)
    args = ap.parse_args()
    if args.cmd == 'bootstrap':
        cmd_bootstrap(args)
    elif args.cmd == 'scan':
        cmd_scan(args)
    else:
        cmd_montage(args)
    return 0


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    raise SystemExit(main())
