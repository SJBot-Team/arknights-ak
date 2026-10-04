# -*- coding: utf-8 -*-
"""maa_act.py — **照 MAA 定义执行动作**的通用入口（关卡外工作流的基本算子）

## 依用户要求
> 你不需要模仿人类与图形界面交互的逻辑来一步一步直接操控，而是使用更高效精确的工作流来完成。
> 你仅负责启动-监控-排查-修正；工作流的搭建可以参考 prts+ 和 MAA 的现成实现。

⇒ 本脚本把"**匹配 MAA 任务 → 按该任务的 action 执行**"做成一个原子操作：
- 支持的 MAA action：`ClickSelf`（点识别到/roi中心的位置）、`DoNothing`、`Swipe`（按 specificRect→rectMove）
- `next` 语义：`#self`（可重复）、`Stop`（终止）、`#next`（透传）、`#back`（回退）
- 对 `template` 为数组或带路径（如 `Default/Terminal.png`）的写法一并支持（见 maa_task）

用法：
    python apps/maa_act.py Terminal-Entry            # 试一个任务（只报告，不点击）
    python apps/maa_act.py Terminal-Entry --do       # 命中就按 action 执行
    python apps/maa_act.py --scan                    # 扫描所有 Terminal* 任务，报告当前主题
"""
from __future__ import annotations

import os
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding='utf-8')

from plugins.capture.emu_window import make_capture, EmuWindowCapture     # noqa: E402
from plugins.recognize.maa_task import MaaTask                            # noqa: E402

ADB = r'D:\__soft\MuMu Player 12\shell\adb.exe'
DEV = '127.0.0.1:16384'


def tap(x, y):
    subprocess.run([ADB, '-s', DEV, 'shell', 'input', 'tap', str(int(x)), str(int(y))],
                   capture_output=True)


def swipe(r1, r2, dur=300):
    """MAA Swipe：specificRect → rectMove（1280×720 基准，换算 ×1.5）。"""
    s = 1.5
    x1, y1 = int((r1[0] + r1[2] / 2) * s), int((r1[1] + r1[3] / 2) * s)
    x2, y2 = int((r2[0] + r2[2] / 2) * s), int((r2[1] + r2[3] / 2) * s)
    subprocess.run([ADB, '-s', DEV, 'shell', 'input', 'swipe',
                    str(x1), str(y1), str(x2), str(y2), str(dur)], capture_output=True)


def main():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    do = '--do' in sys.argv
    scan = '--scan' in sys.argv
    cap = make_capture('adb')
    EmuWindowCapture().open().bring_to_front()
    mt = MaaTask()
    img = cap.grab().image

    if scan:
        hits = []
        for k in mt.tasks:
            if 'Terminal' in k:
                r = mt.evaluate_one(img, k)
                if r.get('status') == 'hit':
                    hits.append((r['score'], k, r.get('center_frame'), r.get('template')))
        hits.sort(reverse=True)
        print('终端相关任务命中（按分数）：')
        for s, k, c, t in hits:
            print(f'   {s:.3f}  {k:<22} {c}  模板={t}')
        return 0

    name = args[0] if args else 'TerminalDefault'
    r = mt.evaluate_one(img, name)
    print(f'{name}: {r.get("status")}  {r.get("score", "")}  {r.get("center_frame", "")}'
          f'  模板={r.get("template", "")}  {r.get("note", "")}')
    if do and r.get('status') == 'hit':
        t = mt.tasks.get(name, {})
        act = t.get('action', 'ClickSelf')
        if act == 'ClickSelf':
            x, y = r['center_frame']
            if 'roi' in t and 'template' not in t and 'algorithm' not in t:
                # 无模板/无算法但给了 roi：MAA 语义=直接点 roi 中心
                x, y = int((t['roi'][0] + t['roi'][2] / 2) * 1.5), int((t['roi'][1] + t['roi'][3] / 2) * 1.5)
            print(f'   按 MAA 执行 action=ClickSelf → 点击 {x},{y}'
                  f'（postDelay {t.get("postDelay", 0)}ms）')
            tap(x, y)
            time.sleep(float(t.get('postDelay', 0)) / 1000.0 + 0.5)
        elif act == 'Swipe':
            swipe(t['specificRect'], t['rectMove'], int((t.get('specialParams') or [300])[0]))
            print('   按 MAA 执行 action=Swipe')
        else:
            print(f'   action={act}（暂不执行）')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
