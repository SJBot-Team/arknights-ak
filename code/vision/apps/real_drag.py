# -*- coding: utf-8 -*-
"""real_drag.py — ★**真实鼠标拖拽**落格（最后一条未试通道）。

## 为什么是它
`click_rel:mouse` / SendMessage / PostMessage 都只做"点击"或"消息"，**不做拖拽**。
而键鼠方案的工作方式是把**真实鼠标的按下—移动—抬起**翻译成触摸拖拽
（既有结论亦称「**划火柴需真实鼠标**」）。因此落格必须用：
**真实光标 + 真实左键按下 → 沿路径移动 → 在目标格抬起**。

用户亦提示：「游戏版本更新后**可直接在暂停态拖出干员**实现 0 帧操作」⇒ 本脚本默认**暂停态**执行。

## 判定
落格成功 ⇒ 右侧「剩余可放置角色」由 8 → 7、费用 −8、卡片变灰、地图上出现干员。
脚本会在前后各截一图并比较该区域，并打印结论（也保留图片供人工确认）。

安全：仅界面级鼠标操作；失败即取消；演习不消耗理智。
"""
from __future__ import annotations

import ctypes
import os
import sys
import time

import cv2
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding='utf-8')

from plugins.action.deploy import Deployer                    # noqa: E402
from plugins.action.win_input import WinInput                  # noqa: E402
from plugins.capture.emu_window import make_capture           # noqa: E402

TMP = r'C:\Users\23922\Documents\ds_harness\ak\.tmp'
u32 = ctypes.windll.user32
MOUSEEVENTF_LEFTDOWN, MOUSEEVENTF_LEFTUP = 0x0002, 0x0004
CARD, CELL = (63, 949), (934, 502)          # 帧坐标：芬卡片 → D6


def real_drag(wi, pts_frame, steps=14, hold=0.12, between=0.035):
    """真实鼠标拖拽：SetCursorPos + mouse_event（真实输入层，非消息）。"""
    pts = [wi.to_screen(x, y) for (x, y) in pts_frame]
    u32.SetCursorPos(int(pts[0][0]), int(pts[0][1]))
    time.sleep(hold)
    u32.mouse_event(MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
    time.sleep(hold)
    path = []
    for (x0, y0), (x1, y1) in zip(pts[:-1], pts[1:]):
        for k in range(1, steps + 1):
            t = k / (steps + 1.0)
            path.append((x0 + (x1 - x0) * t, y0 + (y1 - y0) * t))
    path.append(pts[-1])
    for (x, y) in path:
        u32.SetCursorPos(int(x), int(y))
        time.sleep(between)
    time.sleep(hold)
    u32.mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
    return pts[0], pts[-1]


def rest_band(img):
    return round(float(cv2.cvtColor(img[880:950, 1620:1920], cv2.COLOR_BGR2GRAY).mean()), 1)


def main() -> int:
    cap = make_capture('adb')
    dep, wi = Deployer(cap), WinInput()
    img0 = cap.grab().image
    cv2.imwrite(os.path.join(TMP, 'rd_before.png'), img0)
    a = rest_band(img0)
    print(f'起点：剩余区均值={a}（有"剩余可放置角色"文本时≈94）')

    print('\n真实鼠标拖拽：芬卡片 → D6（暂停态，0 帧操作）')
    p0, p1 = real_drag(wi, [CARD, (500, 750), CELL])
    print(f'  屏幕坐标 {p0} → {p1}')
    time.sleep(1.4)
    img1 = cap.grab().image
    cv2.imwrite(os.path.join(TMP, 'rd_after.png'), img1)
    b = rest_band(img1)

    # 卡片是否变灰：比较第 1 张卡片区域的平均亮度（部署后变暗/变灰）
    def card_gray(im):
        return round(float(cv2.cvtColor(im[915:1075, 20:110], cv2.COLOR_BGR2GRAY).mean()), 1)
    print(f'  拖后：剩余区均值={b}（{a}→{b}）  首卡亮度 {card_gray(img0)}→{card_gray(img1)}')
    print('\n=== 判定 ===')
    if abs(b - a) > 6 or abs(card_gray(img1) - card_gray(img0)) > 8:
        print('画面出现明显变化 ⇒ **可能已落格**，请查看 rd_after.png 确认芬是否在 D6')
    else:
        print('画面无显著变化 ⇒ 仍未落格（请查看 rd_after.png）')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
