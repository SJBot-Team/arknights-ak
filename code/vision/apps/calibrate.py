# -*- coding: utf-8 -*-
"""calibrate.py — 实机标定助手（离线可用：对任意截图/录像帧做 ROI 标定）

设计目标：把"实机标定"从"现场摸索"变成"离线预演 + 现场确认"。
本工具不接触游戏进程：输入是**一张截图**（或录像帧），输出是标注图 + 可直接写入配置的 JSON 补丁。

子命令
  auto    自动探测可自动化的 ROI（费用数字 / 待部署卡槽行 / 战场区域估计），输出标注图 + 补丁
  mark    手工标注：把 `名称=l,t,r,b` 画到截图上（用于技能按钮、撤退按钮等只能目视标定的项）
  grid    在截图叠加带像素坐标的网格（便于人工读坐标）
  apply   把补丁合并进配置 JSON（自动备份原文件）

用法示例
  python apps/calibrate.py auto  --image shot.png --out marked.png --patch patch.json
  python apps/calibrate.py mark  --image shot.png --boxes "ui.skill_button=1490,820,1560,890" --out m.png
  python apps/calibrate.py grid  --image shot.png --step 100 --out grid.png
  python apps/calibrate.py apply --patch patch.json --config configs/axis_h12-4.json
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys

import cv2
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, ROOT)


# --------------------------------------------------------------------------------------
# 自动探测
# --------------------------------------------------------------------------------------
def detect_cost_roi(frame) -> tuple[int, int, int, int] | None:
    """费用数字 ROI。

    单帧下比"取最上面一行"更可靠的判据：**字号最大**（费用数字比「剩余可放置角色」等小字大得多），
    同在右下带内、白色（低饱和高亮）。做法：候选连通域 → 按 y 聚行 → 取中位字高最大的一行 → 该行最右段。
    """
    h, w = frame.shape[:2]
    bx, by = int(w * 0.74), int(h * 0.56)
    band = frame[by:int(h * 0.86), bx:w]
    gray = cv2.cvtColor(band, cv2.COLOR_BGR2GRAY)
    hsv = cv2.cvtColor(band, cv2.COLOR_BGR2HSV)
    white = ((gray > 195) & (hsv[..., 1] < 90)).astype(np.uint8)
    n, _lab, stats, _c = cv2.connectedComponentsWithStats(white, 8)
    cand = []
    for i in range(1, n):
        x, y, bw, bh, area = stats[i]
        if bh < h * 0.016 or bh > h * 0.06 or bw < 2 or bw > w * 0.05 or area < 12:
            continue
        cand.append([int(x), int(y), int(bw), int(bh)])
    if not cand:
        return None
    med_all = float(np.median([c[3] for c in cand]))
    cand.sort(key=lambda c: c[1] + c[3] / 2)
    rows: list[list[list[int]]] = []
    for c in cand:
        cy = c[1] + c[3] / 2
        if rows and abs(cy - (rows[-1][0][1] + rows[-1][0][3] / 2)) <= med_all * 0.9:
            rows[-1].append(c)
        else:
            rows.append([c])
    # 取中位字高最大的行（= 费用数字那一行）
    rows.sort(key=lambda r: -float(np.median([c[3] for c in r])))
    row = sorted(rows[0], key=lambda c: c[0])
    group, left = [row[-1]], row[-1][0]
    for c in reversed(row[:-1]):
        if left - (c[0] + c[2]) > med_all * 1.2:
            break
        group.append(c)
        left = c[0]
    x0 = min(c[0] for c in group)
    x1 = max(c[0] + c[2] for c in group)
    y0 = min(c[1] for c in group)
    y1 = max(c[1] + c[3] for c in group)
    pad = max(2, int(med_all * 0.25))
    return (bx + max(0, x0 - pad), by + max(0, y0 - pad),
            bx + min(band.shape[1], x1 + pad), by + min(band.shape[0], y1 + pad))


def detect_deck_row(frame, band=(0.76, 0.99), min_cards=4) -> dict | None:
    """待部署卡槽行：底部带内按列能量分段找出卡片块（卡与卡之间有暗缝）。

    返回 {'band': [y0,y1], 'cards': [[x0,y0,x1,y1], ...], 'n': N, 'width_median': w}。
    说明：真实卡面之间偶有相邻无暗缝的情况，分段会漏掉个别卡；因此调用方可用
    `--cards N` 按**等距**方式在整行上重建 N 个卡槽中心（默认 12），通常更省事。
    """
    h, w = frame.shape[:2]
    y0, y1 = int(h * band[0]), int(h * band[1])
    strip = frame[y0:y1]
    gray = cv2.cvtColor(strip, cv2.COLOR_BGR2GRAY)
    hsv = cv2.cvtColor(strip, cv2.COLOR_BGR2HSV)
    energy = hsv[..., 1].astype('float32').mean(axis=0) + gray.astype('float32').std(axis=0)
    e = cv2.GaussianBlur(energy.reshape(1, -1), (1, 15), 0).ravel()
    thr = max(float(e.mean()) * 0.5, float(np.median(e)) * 0.6)
    lit = e >= thr
    segs, start = [], None
    for i, v in enumerate(lit):
        if v and start is None:
            start = i
        elif not v and start is not None:
            if i - start >= w * 0.03:
                segs.append((start, i))
            start = None
    if start is not None and len(lit) - start >= w * 0.03:
        segs.append((start, len(lit)))
    if len(segs) < min_cards:
        return None
    widths = np.array([b - a for a, b in segs], dtype='float32')
    med_w = float(np.median(widths))
    keep = [(a, b) for a, b in segs if 0.55 * med_w <= (b - a) <= 1.6 * med_w]
    if len(keep) < min_cards:
        return None
    rows = np.where(gray.mean(axis=1) > gray.mean() * 0.85)[0]
    ry0 = y0 + (int(rows.min()) if rows.size else 0)
    ry1 = y0 + (int(rows.max()) + 1 if rows.size else (y1 - y0))
    return {'band': [int(ry0), int(ry1)],
            'cards': [[int(a), int(ry0), int(b), int(ry1)] for a, b in keep],
            'n': len(keep), 'width_median': int(med_w)}


def detect_skill_button(frame) -> tuple[int, int, int, int] | None:
    """技能按钮候选：左下操作面板顶部的**方形技能图标**（高饱和块）。

    返回候选框；实机仍需人工确认（不同分辨率/皮肤下位置略有差异）。
    """
    h, w = frame.shape[:2]
    # 左下操作面板：x∈[0,0.28w]，y∈[0.28h,0.75h]
    x0, y0, x1, y1 = int(w * 0.00), int(h * 0.28), int(w * 0.28), int(h * 0.78)
    roi = frame[y0:y1, x0:x1]
    hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
    sat = hsv[..., 1]
    mask = (sat > 120).astype(np.uint8) * 255
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((7, 7), np.uint8))
    n, _lab, stats, _c = cv2.connectedComponentsWithStats(mask, 8)
    best = None
    for i in range(1, n):
        x, y, bw, bh, area = stats[i]
        if bw < w * 0.02 or bh < h * 0.02 or bw > w * 0.2 or bh > h * 0.2:
            continue
        ratio = bw / max(1, bh)
        if not (0.6 <= ratio <= 1.7):
            continue
        if best is None or area > best[0]:
            best = (area, x, y, bw, bh)
    if best is None:
        return None
    _a, x, y, bw, bh = best
    return (x0 + x, y0 + y, x0 + x + bw, y0 + y + bh)


def draw_boxes(frame, boxes: dict, out_path: str):
    img = frame.copy()
    palette = [(0, 215, 255), (0, 255, 0), (255, 128, 0), (255, 0, 200), (0, 100, 255)]
    for i, (name, box) in enumerate(boxes.items()):
        if box is None:
            continue
        if isinstance(box[0], (list, tuple)):          # 多框（卡槽）
            for j, b in enumerate(box):
                x0, y0, x1, y1 = [int(v) for v in b]
                col = palette[(i + j) % len(palette)]
                cv2.rectangle(img, (x0, y0), (x1, y1), col, 2)
                if j == 0:
                    cv2.putText(img, f'{name}[{j}]', (x0 + 2, max(12, y0 - 4)),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.45, col, 1)
            continue
        x0, y0, x1, y1 = [int(v) for v in box]
        col = palette[i % len(palette)]
        cv2.rectangle(img, (x0, y0), (x1, y1), col, 2)
        cv2.putText(img, name, (x0 + 2, max(14, y0 - 5)), cv2.FONT_HERSHEY_SIMPLEX, 0.5, col, 1)
    cv2.imwrite(out_path, img)
    print(f'标注图 → {out_path}')


# --------------------------------------------------------------------------------------
# 子命令
# --------------------------------------------------------------------------------------
def cmd_auto(args):
    frame = cv2.imread(args.image)
    if frame is None:
        print(f'读不到图片：{args.image}')
        return 2
    h, w = frame.shape[:2]
    boxes = {}
    patch = {}
    cost = detect_cost_roi(frame)
    if cost:
        boxes['cost_bar.roi'] = cost
        patch.setdefault('axis_runner', {})['cost_bar'] = {'roi': list(cost)}
    else:
        print('  ⚠ 费用数字 ROI 自动探测失败（请用 grid 子命令手工读取坐标）')
    deck = detect_deck_row(frame)
    if deck:
        boxes['deck_row'] = deck['cards']
        # 等距重建 N 个卡槽中心（默认 12 = 常规编队上限），比逐个检测更稳
        n = int(getattr(args, 'cards', 12) or 12)
        xs0 = min(c[0] for c in deck['cards'])
        xs1 = max(c[2] for c in deck['cards'])
        # 检测段常漏掉边缘卡片；卡槽行通常铺满整行 → 覆盖不足 88% 则按整行等距重建
        if (xs1 - xs0) < w * 0.88:
            xs0, xs1 = 0, w
            note_span = '（检测覆盖不足，按整行等距重建）'
        else:
            note_span = ''
        cy = (deck['band'][0] + deck['band'][1]) // 2
        step = (xs1 - xs0) / max(1, n)
        slots = {f'_slot{i+1}': [int(xs0 + step * (i + 0.5)), int(cy)] for i in range(n)}
        boxes['deck_slots'] = [[int(xs0 + step * i), deck['band'][0],
                                int(xs0 + step * (i + 1)), deck['band'][1]] for i in range(n)]
        patch.setdefault('axis_runner', {})['unit_slots_auto'] = {
            '_note': f'按等距重建的 {n} 个卡槽中心（x,y）{note_span}，实机请核对数量并把键改成干员名',
            **slots}
        # 战场区域：卡槽行之上、顶部 HUD 之下
        top = int(h * 0.10)
        bot = deck['band'][0]
        boxes['battle_area'] = (0, top, w, bot)
        patch['axis_runner']['battle_area'] = {'left': 0, 'top': top, 'right': w, 'bottom': bot,
                                               '_todo': '自动估计，实机需按地形四角微调'}
    else:
        print('  ⚠ 待部署卡槽行未探测到（可能不在战斗界面）')
    skill = detect_skill_button(frame)
    if skill:
        boxes['ui.skill_button(候选)'] = skill
    print(f'图像 {w}x{h}；探测结果：')
    for k, v in boxes.items():
        print(f'  {k}: {v}')
    if args.out:
        draw_boxes(frame, boxes, args.out)
    if args.patch:
        with open(args.patch, 'w', encoding='utf-8') as f:
            json.dump(patch, f, ensure_ascii=False, indent=1)
        print(f'配置补丁 → {args.patch}（用 apply 子命令合并）')
    return 0


def cmd_mark(args):
    frame = cv2.imread(args.image)
    if frame is None:
        print(f'读不到图片：{args.image}')
        return 2
    boxes = {}
    patch = {'axis_runner': {}}
    for spec in args.boxes:
        name, _, coords = spec.partition('=')
        vals = [int(float(v)) for v in coords.split(',')]
        if len(vals) != 4:
            print(f'  跳过格式错误的框：{spec}')
            continue
        boxes[name] = tuple(vals)
        # 名称里带点 → 作为配置路径
        if name.startswith('ui.'):
            patch['axis_runner'].setdefault('ui', {})[name.split('.', 1)[1]] = vals
        elif name.startswith('unit_slots.'):
            patch['axis_runner'].setdefault('unit_slots', {})[name.split('.', 1)[1]] = vals
    draw_boxes(frame, boxes, args.out)
    if args.patch:
        with open(args.patch, 'w', encoding='utf-8') as f:
            json.dump(patch if patch['axis_runner'] else {}, f, ensure_ascii=False, indent=1)
        print(f'配置补丁 → {args.patch}')
    return 0


def cmd_grid(args):
    frame = cv2.imread(args.image)
    if frame is None:
        print(f'读不到图片：{args.image}')
        return 2
    img = frame.copy()
    h, w = img.shape[:2]
    step = int(args.step)
    for x in range(0, w, step):
        cv2.line(img, (x, 0), (x, h), (0, 255, 0), 1)
        for y in range(0, h, step):
            cv2.putText(img, f'{x},{y}', (x + 2, y + 14), cv2.FONT_HERSHEY_SIMPLEX,
                        0.38, (0, 255, 0), 1)
    for y in range(0, h, step):
        cv2.line(img, (0, y), (w, y), (0, 255, 0), 1)
    cv2.imwrite(args.out, img)
    print(f'网格图 → {args.out}（步长 {step}px，标注为像素坐标 x,y）')
    return 0


def cmd_apply(args):
    cfg = json.load(open(args.config, encoding='utf-8'))
    patch = json.load(open(args.patch, encoding='utf-8'))
    if not patch:
        print('补丁为空，未修改配置')
        return 0
    bak = args.config + '.bak'
    shutil.copyfile(args.config, bak)
    merged = _deep_merge(cfg.get('axis_runner', {}), patch.get('axis_runner', {}))
    cfg['axis_runner'] = merged
    with open(args.config, 'w', encoding='utf-8') as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)
    print(f'已合并补丁到 {args.config}（原文件备份为 {bak}）')
    return 0


def _deep_merge(base: dict, patch: dict) -> dict:
    out = dict(base)
    for k, v in patch.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest='cmd', required=True)
    p = sub.add_parser('auto'); p.add_argument('--image', required=True)
    p.add_argument('--out'); p.add_argument('--patch')
    p.add_argument('--cards', type=int, default=12, help='编队卡槽数量（等距重建用）')
    p = sub.add_parser('mark'); p.add_argument('--image', required=True)
    p.add_argument('--boxes', nargs='+', required=True); p.add_argument('--out', required=True)
    p.add_argument('--patch')
    p = sub.add_parser('grid'); p.add_argument('--image', required=True)
    p.add_argument('--step', type=int, default=100); p.add_argument('--out', required=True)
    p = sub.add_parser('apply'); p.add_argument('--patch', required=True)
    p.add_argument('--config', required=True)
    args = ap.parse_args()
    return {'auto': cmd_auto, 'mark': cmd_mark, 'grid': cmd_grid, 'apply': cmd_apply}[args.cmd](args)


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    raise SystemExit(main())
