# -*- coding: utf-8 -*-
"""deploy_two_step.py — ★按用户指点的**两段式部署**（有朝向干员）：拖拽→松手→**再拖拽朝向**→松手。

## 用户指点（2026-09-15）
> 「干员部署有两类，一类**先拖拽，松手后再拖拽朝向，松手部署**；
>   一类单位**没有朝向**，拖拽后松开自动部署。」
> 「**暂停不会打断正在进行的拖拽**，**暂停时也可以直接拖拽**。」

## 由此修正的认知（D1）
此前"拖拽→松手"后画面仍显示干员悬停 + 「点击取消」，我们判定为"未提交"；
**按用户指点，那其实正是"朝向选择阶段"** —— 只差**第二次拖拽定朝向再松手**。
（也解释了为何"剩余可放置角色"与费用当时都未变化：费用在**确认**时才扣。）

## 本脚本
1. 自动导航进 1-1 演习战斗；
2. 暂停（宏键 F）→ 在暂停态**直接拖拽**；
3. **第一段**：卡片 → D6(934,502)，松手；
4. **第二段**：从 D6 → 朝向点（按轴表"朝左" = 屏幕向右，即朝 D4 方向 (1182,502)），松手；
5. 判定：费用是否 −8、「剩余可放置角色」是否 8→7、卡片是否变灰；
6. 截图存档（d2s_*.png）。

安全：仅界面级拖拽与截图；演习不消耗理智。
"""
from __future__ import annotations

import ctypes
import os
import sys
import time

import cv2

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding='utf-8')

from plugins.action.win_input import WinInput                    # noqa: E402
from plugins.capture.emu_window import make_capture             # noqa: E402
from plugins.recognize.battle_hud import BattleHudGate          # noqa: E402
import nav_to_drill                                             # noqa: E402

TMP = r'C:\Users\23922\Documents\ds_harness\ak\.tmp'
u32 = ctypes.windll.user32
LD, LU = 0x0002, 0x0004
CARD = (63, 949)
from plugins.action.grid_px import coord_to_px as _c2p
D6 = _c2p("D6")          # ★修正后 = (1182, 502)
DIR_LEFT_AXIS = _c2p("D4")   # 轴表"朝左"= 屏幕向左 = col 4（(row3,col4)）


def drag(wi, pts_frame, steps=8, hold=0.07, between=0.02, release=True):
    pts = [wi.to_screen(x, y) for (x, y) in pts_frame]
    u32.SetCursorPos(int(pts[0][0]), int(pts[0][1]))
    time.sleep(hold)
    u32.mouse_event(LD, 0, 0, 0, 0)
    time.sleep(hold)
    for (x0, y0), (x1, y1) in zip(pts[:-1], pts[1:]):
        for k in range(1, steps + 1):
            t = k / (steps + 1.0)
            u32.SetCursorPos(int(x0 + (x1 - x0) * t), int(y0 + (y1 - y0) * t))
            time.sleep(between)
    u32.SetCursorPos(int(pts[-1][0]), int(pts[-1][1]))
    time.sleep(hold)
    if release:
        u32.mouse_event(LU, 0, 0, 0, 0)


def cost_roi(img):
    """费用数字区域的平均亮度（用于粗略判断变化）。"""
    return round(float(cv2.cvtColor(img[730:805, 1795:1915], cv2.COLOR_BGR2GRAY).mean()), 1)


def card0(img):
    return round(float(cv2.cvtColor(img[915:1075, 20:110], cv2.COLOR_BGR2GRAY).mean()), 1)


def main() -> int:
    cap = make_capture('adb')
    wi, gate = WinInput(), BattleHudGate()
    if not gate.check(cap.grab().image)['in_battle']:
        print('不在战斗 → 自动导航')
        if nav_to_drill.main() != 0:
            return 1

    img = cap.grab().image
    cv2.imwrite(os.path.join(TMP, 'd2s_0_before.png'), img)
    c0, k0 = cost_roi(img), card0(img)
    print(f'起手：费用区 {c0}  首卡 {k0}  in_battle={gate.check(img)["in_battle"]}')

    print('\n暂停（宏键 F）—— 用户：暂停不会打断拖拽，暂停时也可直接拖拽')
    wi.post_key('f')
    time.sleep(0.6)

    print('第一段：卡片 → D6，松手（应进入"朝向选择"）')
    drag(wi, [CARD, (500, 750), D6], release=True)
    time.sleep(0.9)
    img = cap.grab().image
    cv2.imwrite(os.path.join(TMP, 'd2s_1_released.png'), img)
    print(f'  松手后：费用区 {cost_roi(img)}  首卡 {card0(img)}')

    print('第二段：从 D6 拖向朝向（轴表"朝左" = 屏幕向右），松手提交')
    drag(wi, [D6, DIR_LEFT_AXIS], steps=6, hold=0.08, release=True)
    time.sleep(1.2)
    img = cap.grab().image
    cv2.imwrite(os.path.join(TMP, 'd2s_2_committed.png'), img)
    c1, k1 = cost_roi(img), card0(img)
    print(f'  提交后：费用区 {c1}  首卡 {k1}')

    print('\n=== 判定 ===')
    print(f'费用区 {c0}→{c1}（部署成功通常伴随明显变化）；首卡 {k0}→{k1}（成功会变灰变暗）')
    print('请查看 d2s_2_committed.png 确认：D6 是否出现芬、「剩余可放置角色」是否 8→7')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
