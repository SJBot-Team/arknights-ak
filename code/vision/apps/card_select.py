# -*- coding: utf-8 -*-
"""card_select.py — ★**按干员名选卡（自校验）**：点卡 → OCR 面板名 → 确认。

## 流程（最终定型）
1. 由 `card_plan.json` 的**费用升序**算出目标位次（**快速定位**，但同费用不唯一 ⇒ 仅作起点）；
2. 依次点选候选卡片（先点费用预测的位次，再扫其余），每次：
   **点点卡片 → 抓图 → `read_selected_name()` 读面板名 → 与目标名比对**；
3. 命中即返回该卡片的像素中心；全部试完仍未命中则返回 None。

## 为什么这样做（用户指出的三点）
- **练度影响费用** ⇒ 费用表可能不准；**多干员费用可能一致**（本编队 3 人同为 9 费）；**局内费用可变**
  ⇒ **费用不能作为唯一判据**；
- 头像模板匹配已实测不可行（头像=脸部特写、卡片=半身，NCC≈0）；
- **名称 OCR 已实测可靠**（`live_08_select.png`/`live_13_deploy_fang.png` → '芬'；未选中 → None 无误报）。

安全：只做"点卡 + 截图 + OCR"；确认后才由调用方执行部署。
"""
from __future__ import annotations

import os
import sys
import time

import cv2

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding='utf-8')

from plugins.recognize.operator_name import read_selected_name          # noqa: E402


def card_centers(cap, dep, n_expected=None, row_left=66.0, row_right=1880.0,
                 y=1007):
    """取卡片行中心：先 `find_cards`，不足 n_expected 时用**均匀网格**补全。"""
    cards = sorted(dep.find_cards(img=cap.grab().image) or [], key=lambda k: k['cx'])
    xs = [c['cx'] for c in cards]
    n = n_expected or len(xs)
    if n <= 0:
        return []
    if len(xs) >= max(3, n - 1):
        return [(x, y) for x in xs[:n]] if len(xs) >= n else _grid(n, row_left, row_right, y)
    return _grid(n, row_left, row_right, y)


def _grid(n, left, right, y):
    pitch = (right - left) / n
    return [(int(round(left + pitch * (i + 0.5))), y) for i in range(n)]


def select_card_by_avatar(cap, dep, target_name, plan=None, deployed=None,
                          squad=None, verbose=True):
    """★**头像识别快速选卡**（单次截屏，不需点击）：返回目标卡中心 `(x, y)` 或 None。

    依据（已实测）：**待部署区头像就是 `avatar/char_*.png`**（同构图，仅下缘被裁）；
    编队页 10/11、战斗区 8/10（NCC 0.3~0.6、边际 0.04~0.23）；
    **且能区分"同费用"干员**（费用法做不到）。
    """
    from plugins.recognize.operator_card import OperatorCardMatcher
    deployed = set(deployed or ())
    order = [nm for nm in (plan or {}).get('order', []) if nm not in deployed]
    n = len(order) if order else (len(squad) if squad else 11)
    img = cap.grab().image
    m = OperatorCardMatcher(candidates=squad or order or None)
    row = m.identify_deploy_row(img, n_cards=n, candidates=squad or order or None)
    if verbose:
        print('  头像识别结果:')
        for i, r in enumerate(row):
            exp = order[i] if i < len(order) else '?'
            print(f'    卡#{i} x={r["cx"]} → {r["name"]} '
                  f'({r["score"]:.3f}/边际{r["margin"]:.3f})  费用序预期={exp}')
    for i, r in enumerate(row):
        if r['name'] == target_name:
            return (r['cx'], 1007)
    return None


def select_card_by_name(cap, dep, target_name, plan=None, deployed=None,
                        try_first=None, max_tries=13, settle=0.55, verbose=True,
                        cancel_at=None):
    """点卡 → OCR 面板名 → 命中则返回该卡中心 `(x, y)`；否则 None。

    `try_first`：先试的**位次**（由费用升序算出，可为 None）；随后按 0..n-1 顺序扫其余。
    """
    deployed = set(deployed or ())
    n = len([nm for nm in (plan or {}).get('order', []) if nm not in deployed]) or 11
    centers = card_centers(cap, dep, n_expected=n)
    if not centers:
        return None
    order = []
    if try_first is not None and 0 <= try_first < len(centers):
        order.append(try_first)
    order += [i for i in range(len(centers)) if i not in order]
    order = order[:max_tries]
    if verbose:
        print(f'  选卡：目标 {target_name}；候选位次 {order[:6]}'
              f'（共 {len(centers)} 张，先试费用预测位次 {try_first}）')
    for i in order:
        cx, cy = centers[i]
        dep.tap(cx, cy)
        time.sleep(settle)
        img = cap.grab().image
        nm = read_selected_name(img)
        ok = (nm == target_name)
        if verbose:
            print(f'    卡#{i} (x={cx}) → OCR 名={nm!r} {"✅ 命中" if ok else ""}')
        if ok:
            if cancel_at:                      # 收起面板（点空白处），避免影响后续拖拽
                dep.tap(*cancel_at)
                time.sleep(0.4)
            return (cx, cy)
    return None
