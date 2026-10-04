# -*- coding: utf-8 -*-
"""maa_wakeup.py — 按 MAA 的启动流程（StartUpThemes 候选链）推进"开始唤醒"

## 依据
来源：`D:\\__soft\\MAA\\resource\\tasks\\tasks.json`
- `GameStart`：`action: ClickSelf, roi [550,600,200,120], templThreshold 0.7, postDelay 3000`
- `StartToWakeUp`：`ClickSelf, roi [520,460,240,100]`
- `StartToWakeUpOCR`：OCR ["开始唤醒","登录","登","录"]  ← **登录相关，照 MAA 只做界面级点击**
- `StartUpConnectingFlag` / `StartLoginBServer`：ClickSelf + 各自 roi
- `GameStartCheckResourceOCR`：OCR ["资源完整性","不消耗流量"]（资源完整性检测）
- `GameStartUpdateOCR`：OCR ["正在释放神经递质","MB"]（更新下载）⇒ 需耐心等待

## 做法
按**候选取第一个命中者**（MAA 的 next 候选思想）逐个尝试：模板类任务用 `MaaTask` 判定，
命中即按其 `action`（ClickSelf）点击识别位置；每轮打印状态，直到 `StartUp`（主界面）命中。
**不做任何凭据相关操作**；若出现需要人工输入的登录界面，则停止并报告。
"""
from __future__ import annotations

import os
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding='utf-8')

from plugins.capture.emu_window import make_capture, EmuWindowCapture       # noqa: E402
from plugins.recognize.maa_task import MaaTask                             # noqa: E402

ADB = r'D:\__soft\MuMu Player 12\shell\adb.exe'
DEV = '127.0.0.1:16384'
# MAA 的 StartUpThemes 候选（模板类可判定的部分，按 MAA 原文顺序）
CANDIDATES = ['GameStart', 'StartToWakeUp', 'StartUpConnectingFlag', 'StartLoginBServer',
              'LeidianGoogleFrameworkConfirm', 'BiliBiliNoMorePromptsNextTime']
# 需要 OCR 的（本阶段未接入 OCR，仅记录命中情况供人工判断）
OCR_ONLY = ['GameStartCheckResourceOCR', 'GameStartUpdateOCR', 'StartToWakeUpOCR',
            'AccountManagerLoginButton']


def tap(x, y):
    subprocess.run([ADB, '-s', DEV, 'shell', 'input', 'tap', str(int(x)), str(int(y))],
                   capture_output=True)


def main():
    rounds = int(sys.argv[1]) if len(sys.argv) > 1 else 12
    cap = make_capture('adb')
    EmuWindowCapture().open().bring_to_front()
    mt = MaaTask()
    for i in range(rounds):
        img = cap.grab().image
        # 1) 主界面？(MAA: StartUp)
        r = mt.evaluate_one(img, 'StartUp')
        if r.get('status') == 'hit':
            print(f'[{i}] ★ 主界面（StartUp 命中 {r["score"]:.3f}）')
            return 0
        # 2) 候选逐个尝试
        acted = False
        for name in CANDIDATES:
            rr = mt.evaluate_one(img, name)
            if rr.get('status') == 'hit':
                cx, cy = rr['center_frame']
                print(f'[{i}] {name} 命中 {rr["score"]:.3f} → 按 MAA ClickSelf 点击 {cx},{cy}'
                      f'（postDelay 3s）')
                tap(cx, cy)
                time.sleep(3.0)
                acted = True
                break
        if not acted:
            hits = mt.scan_all(img, topn=3)
            print(f'[{i}] 无候选命中；全任务扫描 top3: {hits}（均值 {img.mean():.1f}）')
            time.sleep(2.0)
    print('轮次用尽')
    return 1


if __name__ == '__main__':
    raise SystemExit(main())
