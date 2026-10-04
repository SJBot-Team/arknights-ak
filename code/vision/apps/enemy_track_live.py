# -*- coding: utf-8 -*-
"""enemy_track_live.py — ★**实机帧精确敌人轨迹测量**（用时钟 + 宏键暂停 + 已标定格点）。

## 为什么这样做（D14 的关键实验）
D14 的缺口是"**敌人在地图上的位置随时间**"：模拟器与标定在"第 2 只敌人到达芬范围的时刻"上差 ~25 帧，
而移速与出生点约定均已排除。此前尝试从**录像**测轨迹失败（遮挡 + 运动块不唯一）。
现在有了三件新工具，可以做**干净且帧精确**的测量：

1. **费用条帧时钟**（绝对帧 = 满条次数×30 + 相位，实测 ~30 帧/秒，且战斗 HUD 门控可用）；
2. **宏键 `F`（PostMessage）暂停/恢复**（实测可用，且暂停**不会**取消任何东西）；
3. **格点标定**：`col = (1556 − x)/124.5`、`row = 3 + (y − 502)/138`（已三重互证）。

## 流程
对每个目标帧：等时钟到点 → `F` 暂停 → 截图 → **定位敌人**（暗色团块，取离上一位置最近者）→
换算成格坐标 → `F` 恢复。最终打印 `(帧, 屏幕坐标, 格坐标)` 轨迹。

## 安全
只做"暂停/恢复 + 截图"；**不注入其它操作、不部署**；演习不消耗理智。
"""
from __future__ import annotations

import os
import sys
import time

import cv2
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding='utf-8')

from plugins.action.win_input import WinInput                     # noqa: E402
from plugins.capture.emu_window import make_capture              # noqa: E402
from plugins.recognize.battle_hud import BattleHudGate           # noqa: E402
from plugins.recognize.cost_bar import CostBarRecognizer         # noqa: E402
import nav_to_drill                                              # noqa: E402

TMP = r'C:\Users\23922\Documents\ds_harness\ak\.tmp'
MAP_ROI = (60, 130, 1860, 930)          # 战场区（排除 HUD）
# 格点标定（本机实测，已三重互证）
COL0_X, COL_PX = 559.0, 124.5      # ★修正：x 随 col 递增（原 1556 为镜像误值）
ROW0_Y, ROW_PX = 502.0, 138.0


def to_grid(x, y):
    col = (x - COL0_X) / COL_PX
    row = 3.0 + (y - ROW0_Y) / ROW_PX
    return round(row, 2), round(col, 2)


def find_enemy(img, prev=None):
    """[旧] 暗色团块法 —— 会误抓固定 UI 元素，已由"帧差法"取代（保留供对照）。"""
    x0, y0, x1, y1 = MAP_ROI
    sub = img[y0:y1, x0:x1]
    g = cv2.cvtColor(sub, cv2.COLOR_BGR2GRAY)
    mask = (g < 58).astype(np.uint8) * 255
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
    n, lab, stats, cent = cv2.connectedComponentsWithStats(mask, 8)
    cands = []
    for k in range(1, n):
        a = int(stats[k, 4])
        w, h = int(stats[k, 2]), int(stats[k, 3])
        if a < 120 or a > 20000:
            continue
        if not (0.4 < w / max(1, h) < 3.5):
            continue
        cands.append((x0 + cent[k][0], y0 + cent[k][1], a))
    if not cands:
        return None
    if prev is None:
        return min(cands, key=lambda c: c[0])
    return min(cands, key=lambda c: (c[0] - prev[0]) ** 2 + (c[1] - prev[1]) ** 2)


def find_movers(a, b, prev=None, min_area=150):
    """★帧差法：返回在 a→b 之间**发生移动**的团块 `(cx, cy, area)`。

    相机静止、HUD 静止 ⇒ 只有**单位**在动；比"最暗团块"可靠得多
    （后者会误抓固定的暗色 UI/地图阴影）。
    """
    x0, y0, x1, y1 = MAP_ROI
    d = cv2.absdiff(a[y0:y1, x0:x1], b[y0:y1, x0:x1])
    g = cv2.cvtColor(d, cv2.COLOR_BGR2GRAY)
    _, m = cv2.threshold(g, 24, 255, cv2.THRESH_BINARY)
    m = cv2.morphologyEx(m, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
    m = cv2.dilate(m, np.ones((5, 5), np.uint8), iterations=1)
    n, lab, stats, cent = cv2.connectedComponentsWithStats(m, 8)
    cands = []
    for k in range(1, n):
        area = int(stats[k, 4])
        w, h = int(stats[k, 2]), int(stats[k, 3])
        if area < min_area or area > 60000:
            continue
        if w > 260 or h > 260:                    # 敌人剪影不会太大
            continue
        cands.append((x0 + cent[k][0], y0 + cent[k][1], area))
    if not cands:
        return None
    if prev is None:
        return min(cands, key=lambda c: c[0])     # 最早出现的敌人自左侧进入
    return min(cands, key=lambda c: (c[0] - prev[0]) ** 2 + (c[1] - prev[1]) ** 2)


def main() -> int:
    targets = [int(v) for v in (sys.argv[1:] or ['90', '150', '210', '270', '330', '390'])]
    cap = make_capture('adb')
    wi, gate, bar = WinInput(), BattleHudGate(), CostBarRecognizer()

    img = cap.grab().image
    if not gate.check(img)['in_battle']:
        print('不在战斗中 → 先自动导航进 1-1 演习')
        if nav_to_drill.main() != 0:
            print('⚠️ 导航失败')
            return 1

    # 建立绝对帧基准
    print('\n采样（帧, 屏幕坐标, 格坐标）')
    prev = None
    t0 = time.perf_counter()
    wraps, ph0, cur = 0, None, 0
    prev_ph = None
    for tg in targets:
        # 等到时钟到达目标帧
        while cur < tg and time.perf_counter() - t0 < 180:
            fr = cap.grab()
            ms = bar.run(fr.image, {}, None, fr.origin)
            if ms:
                ph = int(ms[0].extra['frame'])
                if prev_ph is not None and ph < prev_ph:
                    wraps += 1
                if ph0 is None:
                    ph0 = ph
                prev_ph = ph
                cur = wraps * 30 + ph - (ph0 or 0)
                if not gate.check(fr.image)['in_battle']:
                    print('  ⚠️ 已离开战斗，停止采样')
                    return 1
            time.sleep(0.02)
        wi.post_key('f')                     # 宏键暂停（可选的"取证截图"）
        time.sleep(0.45)
        img_p = cap.grab().image
        cv2.imwrite(os.path.join(TMP, f'trk_{tg}.png'), img_p)
        wi.post_key('f')                     # 恢复
        time.sleep(0.25)
        # ★帧差法：运行态取两帧，只有单位在动
        a = cap.grab().image
        time.sleep(0.07)
        b = cap.grab().image
        cv2.imwrite(os.path.join(TMP, f'trk_{tg}_b.png'), b)
        hit = find_movers(a, b, prev)
        if hit:
            prev = (hit[0], hit[1])
            r, c = to_grid(hit[0], hit[1])
            print(f'  帧 {cur:>4}（目标 {tg:>3}）  屏幕 ({hit[0]:.0f},{hit[1]:.0f})  '
                  f'面积 {hit[2]:>5}  →  **格 (row={r}, col={c})**')
        else:
            print(f'  帧 {cur:>4}（目标 {tg:>3}）  未定位到运动单位')
        time.sleep(0.1)
    print(f'\n共 {len(targets)} 个采样点；截图存于 {TMP}\\trk_*.png')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
