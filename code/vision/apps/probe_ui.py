# -*- coding: utf-8 -*-
"""probe_ui.py — 界面探测器：扫描当前画面命中了哪些 MAA 模板，一次摸清"这是哪个界面"

## 为什么需要（用户 2026-09-15 点名）
> 尤其是你昨天在关卡识别进入的界面出了很多问题，效率很低。

昨天的低效根源之一是"人肉试错猜界面"。MAA 的 resource 里有成套界面模板，
本工具把当前帧与**界面类模板**逐一匹配，按分数排序输出 —— 于是：
- 不必猜"这是哪个界面"，直接看命中证据；
- 选定某个界面后，直接用命中的模板做**后续流水线的识别条件**（`pipeline` 的 `recognize.template`）。

## 用法
    python apps/probe_ui.py [图片路径] [topN]
不传图片则实时抓一帧（adb display 通道，遮挡无关）。
"""
from __future__ import annotations

import os
import sys

import cv2

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding='utf-8')

from plugins.recognize.maa_anchor import MaaAnchor              # noqa: E402

MAA_TEMPLATE = r'D:\__soft\MAA\resource\template'
# 只扫"界面类"目录（排除 items/infrast 这类海量图标，避免无谓开销）
UI_DIRS = ('Battle', 'StageNavigation', 'ReturnButton', 'WakeUp', 'UiTheme',
           'OperBox', 'Recruit', 'Depot', 'Award', 'Credit', 'QuickSwitch',
           'Roguelike', 'RA', 'MiniGame', 'MiningActivity')
# 顶层单文件模板
UI_FILES = ('LoadingIcon.png', 'OfflineConfirm.png', 'PopupCancel.png', 'PopupConfirm.png')


def collect_templates():
    out = []
    for d in UI_DIRS:
        p = os.path.join(MAA_TEMPLATE, d)
        if not os.path.isdir(p):
            continue
        for root, _dd, fs in os.walk(p):
            for f in fs:
                if f.lower().endswith('.png'):
                    rel = os.path.relpath(os.path.join(root, f), MAA_TEMPLATE)
                    out.append(rel.replace('\\', '/'))
    for f in UI_FILES:
        if os.path.exists(os.path.join(MAA_TEMPLATE, f)):
            out.append(f)
    return out


def main():
    img_path = sys.argv[1] if len(sys.argv) > 1 else None
    topn = int(sys.argv[2]) if len(sys.argv) > 2 else 12
    if img_path:
        img = cv2.imread(img_path)
    else:
        from plugins.capture.emu_window import make_capture
        img = make_capture('adb').grab().image
    if img is None:
        print('读不到画面'); return 1

    rels = collect_templates()
    print(f'扫描 {len(rels)} 个界面类模板（帧 {img.shape[1]}x{img.shape[0]}）……')
    ma = MaaAnchor(thr=0.55)          # 先用低阈值看"像什么"，再由人挑高分的
    hits = []
    for rel in rels:
        h = ma.match(img, rel, thr=0.55)
        if h:
            hits.append((h['score'], rel, tuple(int(round(v)) for v in h['center_frame'])))
    hits.sort(reverse=True)
    print(f'\n命中 {len(hits)} 个（按分数排序，前 {topn}）：')
    for s, rel, c in hits[:topn]:
        print(f'  {s:.3f}  {rel:<52} 位置{c}')
    if not hits:
        print('  无命中（可能是纯动画/加载画面，或该界面不在 MAA 模板覆盖内）')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
