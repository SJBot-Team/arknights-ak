# -*- coding: utf-8 -*-
"""render_guard.py — 实机脚本的**渲染前置**守卫（§7.72/§7.75 规程）

## 为什么必须有
`adb exec-out screencap -d 2` 读的是模拟器帧缓冲。**MuMu 窗口被遮挡/最小化时会停止渲染**，
帧缓冲冻结 ⇒ 截图只是"最后一帧"的拷贝：
  · 点击后"画面变化 = 0.0"（实测，见 §7.72）；
  · 差分法找不到"在动的东西"，会把静止帧误解释成"费用封顶、条停住"（这正是我此前犯过的错）；
  · 任何基于画面的判断（状态机、相位、精度比对）全部失真。

⇒ 规程：**任何实机脚本在做任何判断之前，先过这道守卫；不通过就报错退出，不做任何注入动作。**

## 用法
    from plugins.capture.render_guard import ensure_foreground, assert_rendering
    ensure_foreground()                      # 尽力把模拟器拉回前台（可能与前台锁搏斗，失败不算错）
    if not assert_rendering(cam):            # 连采若干帧，要求画面确有变化
        raise SystemExit('模拟器未在渲染（被遮挡/最小化？）——按规程退出')
"""
from __future__ import annotations

import time

import cv2
import numpy as np


def ensure_foreground(titles=None) -> bool:
    """尽力把模拟器窗口拉到前台。返回是否调用成功（不代表渲染已恢复）。"""
    try:
        from plugins.capture.emu_window import EmuWindowCapture
        kw = {'titles': titles} if titles else {}
        EmuWindowCapture(**kw).open().bring_to_front()
        return True
    except Exception:
        return False


def _fingerprint(img):
    return cv2.resize(cv2.cvtColor(img, cv2.COLOR_BGR2GRAY), (64, 36)).astype('float32')


def assert_rendering(cam, tries: int = 4, interval: float = 0.5,
                     thresh: float = 0.05, quiet: bool = False) -> bool:
    """连采 `tries` 帧，只要相邻两帧的缩略图平均绝对差 > `thresh` 即认为"在渲染"。

    阈值 0.05（0~255 灰度尺度）非常宽松——正常战斗画面里飘字/特效/计时器都会远超它；
    冻结帧则是**精确的 0.0**（实测），因此该判据不会漏报。
    """
    prev = None
    for i in range(max(2, tries)):
        try:
            img = cam.grab().image
        except Exception:
            time.sleep(interval)
            continue
        fp = _fingerprint(img)
        if prev is not None:
            d = float(np.abs(fp - prev).mean())
            if d > thresh:
                if not quiet:
                    print(f'渲染校验通过（相邻帧差异 {d:.3f} > {thresh}）')
                return True
        prev = fp
        time.sleep(interval)
    if not quiet:
        print('渲染校验未通过：画面完全静止 ⇒ 模拟器可能被遮挡/最小化（§7.72）')
    return False


def guard_or_exit(cam, titles=None, quiet: bool = False):
    """一行式守卫：置前台 → 校验 → 不通过则 SystemExit。"""
    ensure_foreground(titles)
    if not assert_rendering(cam, quiet=quiet):
        raise SystemExit('模拟器未在渲染 —— 请让它可见/恢复窗口后重试（§7.72 规程）')
    return True
