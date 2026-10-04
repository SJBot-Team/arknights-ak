# -*- coding: utf-8 -*-
"""real_drag_run.py — 运行态**快速真实鼠标拖拽**（"划火柴"本体）落格尝试。

## 逻辑
1. 取消当前悬停（点「点击取消」）
2. 用宏键 `F`（PostMessage）确保处于**运行态**（若相位冻结则再发一次）
3. **快速**真实鼠标拖拽：卡片 → D6（`steps=6, between≈12ms, hold≈50ms` ⇒ 全程 ≈0.2s）
   —— "划火柴"的关键就是**快**：在极短时间内完成按下—移动—抬起
4. 判定：剩余区是否回到 84（悬停结束）+ 右侧「剩余可放置角色」是否 8→7 + 卡片是否变灰

安全：仅界面级鼠标操作；失败即取消；演习不消耗理智。
"""
from __future__ import annotations

import ctypes
import os
import sys
import time

import cv2

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding='utf-8')

from plugins.action.deploy import Deployer                     # noqa: E402
from plugins.action.win_input import WinInput                   # noqa: E402
from plugins.capture.emu_window import make_capture            # noqa: E402
from plugins.recognize.cost_bar import CostBarRecognizer       # noqa: E402

TMP = r'C:\Users\23922\Documents\ds_harness\ak\.tmp'
u32 = ctypes.windll.user32
LD, LU = 0x0002, 0x0004
CARD, CELL, CANCEL = (63, 949), (934, 502), (732, 304)


def fast_real_drag(wi, pts_frame, steps=6, hold=0.05, between=0.012):
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
    u32.mouse_event(LU, 0, 0, 0, 0)


def rest(img):
    return round(float(cv2.cvtColor(img[880:950, 1620:1920], cv2.COLOR_BGR2GRAY).mean()), 1)


def frame_rate(cap, dur=1.4):
    rec = CostBarRecognizer()
    t0 = time.perf_counter()
    ph0 = ph1 = None
    prev, wraps = None, 0
    while time.perf_counter() - t0 < dur:
        fr = cap.grab()
        ms = rec.run(fr.image, {}, None, fr.origin)
        if ms:
            ph = int(ms[0].extra['frame'])
            if prev is not None and ph < prev:
                wraps += 1
            if ph0 is None:
                ph0 = ph
            ph1 = ph
            prev = ph
        time.sleep(0.02)
    span = time.perf_counter() - t0
    return (wraps * 30 + (ph1 or 0) - (ph0 or 0)) / max(1e-6, span)


def main() -> int:
    cap = make_capture('adb')
    dep, wi = Deployer(cap), WinInput()

    print('① 取消当前悬停')
    dep.tap(*CANCEL)
    time.sleep(0.9)
    img = cap.grab().image
    print(f'   剩余区={rest(img)}（84≈正常，52≈悬停中）')

    print('② 确认运行态（相位应 ~30 帧/秒）')
    r = frame_rate(cap, 1.4)
    print(f'   实测 {r:.1f} 帧/秒 ⇒ {"运行态" if r > 15 else "**暂停态**（发宏键 F 恢复）"}')
    if r <= 15:
        wi.post_key('f')
        time.sleep(0.8)
        r = frame_rate(cap, 1.4)
        print(f'   发 F 后 {r:.1f} 帧/秒 ⇒ {"运行态 ✓" if r > 15 else "仍暂停 ✗"}')

    print('③ 运行态快速真实鼠标拖拽（卡片 → D6，≈0.2s）')
    cv2.imwrite(os.path.join(TMP, 'rdr_before.png'), cap.grab().image)
    fast_real_drag(wi, [CARD, (500, 750), CELL])
    time.sleep(1.2)
    img2 = cap.grab().image
    cv2.imwrite(os.path.join(TMP, 'rdr_after.png'), img2)
    print(f'   拖后：剩余区={rest(img2)}')
    print('\n=== 判定 ===')
    print('剩余区回到 ≈84 ⇒ 悬停已结束；是否为"落格"请看 rdr_after.png（芬是否在 D6、'
          '「剩余可放置角色」是否 8→7）')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
