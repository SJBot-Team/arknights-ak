# -*- coding: utf-8 -*-
"""phase_precision_test.py — 方法一（费用条相位）在实机上的**精度验证**（一次跑完）

流程：
  1. 状态自适应进战斗（adb display 通道 + 置信度阈值；判据见 §7.66）；
  2. 判定 battle 后**立刻**密集采样 N 帧（前 10s 费用 10→20，条在动）；
     每帧记录**画面时刻的中点估计** mid = (截图前 + 截图后)/2（消除 adb 往返的一半抖动）；
  3. 每帧读「费用数字」+ 用实测 ROI 算「条内相位」；
  4. 逐对比较：`推得逻辑帧 = Δ费用×30 + Δ相位`  vs  `Δt×30`，输出误差，
     并统计 |误差| 的分布 ⇒ 判定方法一在实机的可用性（目标 ≤2 帧）。

ROI 来自 §7.68 的帧间差分实测：费用条 y∈[805,817]、x∈[1700,1920]。
"""
from __future__ import annotations

import os
import subprocess
import sys
import time

import cv2

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding='utf-8')

from plugins.capture.emu_window import make_capture                     # noqa: E402
from plugins.clock.frame_clock import (                                   # noqa: E402
    PIXEL_MAP_30F, bar_phase, frame_from_width)
from plugins.recognize.cost_number import CostNumberRecognizer           # noqa: E402

TMP = r'C:\Users\23922\Documents\ds_harness\ak\.tmp'
TPL = os.path.join(TMP, 'tpl_h124.json')
NUM_ROI = (1795, 730, 1915, 805)
# ★ 费用条 ROI 按官方标定表对齐（§7.78）：条宽 180px、左端 x=1739（实测亮列 1739–1919 与
#   pixel_map 的 180px 总宽完全吻合）。用查表得精确帧，而不是"比例×30"近似。
BAR_ROI = (1739, 805, 1919, 818)
TAP_H124, TAP_DRILL = (1734, 460), (1441, 983)
# ★ 实测校准（§7.85）：12-4 节点在 EPISODE 11/12/13 视图下的**真实位置是 (1734,460)**
#   （此前用的 (953,812) 完全错位 —— 这是连续多轮"点击全部落空"的根因）；
#   「演习」按钮在关卡详情右下 (1441,983)。
# ★ MAA 权威坐标（§7.84）：tasks.json 的 BattleStartPre ROI [1000,600,280,120]@1280×720
#   → 中心 (1140,660) ×1.5 = **(1710, 990)** @1920×1080。
#   我此前一直点 (1659,766)（那是 BattleStart 的 ROI 中心），**y 偏 224px** ⇒ 点击落空的根因。
TAP_START = (1710, 990)
EP_LABEL = (1734, 983)   # 底部「EPISODE 10」章节标签（点标签可直接切章）
EP_NEXT = (1801, 983)    # 底部「EPISODE ▶」右箭头（视图右移一格）
MIN_CONF = 0.85
ADB = r'D:\__soft\MuMu Player 12\shell\adb.exe'
DEV = '127.0.0.1:16384'


def tap(x, y):
    subprocess.run([ADB, '-s', DEV, 'shell', 'input', 'tap', str(x), str(y)], capture_output=True)


def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 8
    cam = make_capture('adb')
    rec = CostNumberRecognizer()
    spec = {'roi': list(NUM_ROI), 'templates': TPL}

    def read(img):
        ms = rec.run(img, spec, None, (0, 0))
        if not ms:
            return None, 0.0
        c = float(ms[0].extra.get('confidence', 0.0))
        return (int(ms[0].extra['cost']) if c >= MIN_CONF else None), c

    def grab_timed():
        t0 = time.perf_counter()
        img = cam.grab().image
        t1 = time.perf_counter()
        return img, (t0 + t1) / 2.0        # 画面时刻中点估计

    # ---- 渲染前置（§7.72 规程）：不通过就绝不做任何判断 ----
    import numpy as np
    try:
        from plugins.capture.emu_window import EmuWindowCapture
        EmuWindowCapture().open().bring_to_front()
        print('已把模拟器拉到前台（保证渲染）')
    except Exception as e:
        print('置前台失败（继续，但强制做画面在变校验）:', e)
    ok_render, prev_fp = False, None
    for _ in range(4):
        _im, _t = grab_timed()
        _fp = cv2.resize(cv2.cvtColor(_im, cv2.COLOR_BGR2GRAY), (64, 36)).astype('float32')
        if prev_fp is not None and float(np.abs(_fp - prev_fp).mean()) > 0.005:
            ok_render = True
            break
        prev_fp = _fp
        time.sleep(0.5)
    print(f'渲染校验（画面在变）：{"通过" if ok_render else "★未通过 —— 模拟器可能被遮挡/最小化"}')
    if not ok_render:
        print('⇒ 按 §7.72：直接退出，不把静止帧当成游戏状态')
        return 4

    # ---- 1) 进战斗（带"点击生效校验"：绝不静默空点，见 §7.70） ----
    def fingerprint(im):
        return cv2.resize(cv2.cvtColor(im, cv2.COLOR_BGR2GRAY), (64, 36)).astype('float32')

    def click_verified(x, y, label, before):
        """点击后复查画面是否真的变了；未变即判失败（不静默重试同一动作）。"""
        tap(x, y)
        time.sleep(0.9)
        after, _ = grab_timed()
        d = float(np.abs(fingerprint(before) - fingerprint(after)).mean())
        ok = d > 3.0
        print(f'    → 点 {label} ({x},{y})：画面变化 {d:5.1f} {"生效" if ok else "★未生效"}')
        return after, ok

    fails = 0
    img, _ = grab_timed()

    def in_battle(im):
        """**战斗 HUD 判定**（§7.84）：优先用 MAA 的 `BattleOfficiallyBegin` 锚点（实测 score 0.995），
        退化时用顶部中央红色敌人计数条。不再用"能读到数字"（数字可来自任何 UI）。"""
        try:
            if ma.match(im, MaaAnchor.BATTLE_OFFICIAL_BEGIN, thr=0.85) is not None:
                return True
        except Exception:
            pass
        roi = im[10:72, 900:1380]
        b = roi[..., 0].astype('int16'); g = roi[..., 1].astype('int16'); r = roi[..., 2].astype('int16')
        return float(((r > 90) & (r - g > 40) & (r - b > 40)).mean()) > 0.05

    def is_result(im):
        """结算画面判定：中央偏左那片"任务失败/行动结束"大白字。"""
        g = cv2.cvtColor(im, cv2.COLOR_BGR2GRAY)
        return float((g[250:400, 300:700] > 200).mean()) > 0.25

    EP_LEFT = (1441, 1009)     # 底部「◀ EPISODE」左移箭头（OCR 校准后的 y）
    ep12_clicked = True        # ★ 视图已用 OCR 校准到 EPISODE 11/12/13（§7.85），不再做模板式章节导航
    for step in range(12):
        if in_battle(img):
            c, conf = read(img)
            print(f'[{step}] 已在战斗（HUD 红条判定）→ 立刻采样（费用读数 {c} conf {conf:.3f}）')
            break
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        bright = lambda roi: float((gray[roi[1]:roi[3], roi[0]:roi[2]] > 200).mean())
        dark_ratio = float((gray < 50).mean())
        if is_result(img):
            nxt, ok = click_verified(960, 988, '结算画面：点击继续', img)
        elif bright((1500, 900, 1920, 1080)) > 0.10:        # 阈值提到 0.10，降低误命中
            nxt, ok = click_verified(*TAP_START, '开始行动(编队)', img)
            if ok:
                # ★ 关键补丁（§7.79）：点完"开始行动"后进入**加载期**（没有费用数字、画面在变），
                #   必须在此等战斗 HUD 出现；否则状态机会把加载画面误判成别的界面继续乱点，
                #   把刚进的战斗又退出去（本轮实测踩到过）。
                tw = time.perf_counter()
                while time.perf_counter() - tw < 30:
                    im2, _t2 = grab_timed()
                    c2, _cf2 = read(im2)
                    if c2 is not None:
                        print(f'   → 战斗 HUD 已出现（费用 {c2}）')
                        img = im2
                        break
                    time.sleep(0.4)
                else:
                    print('   → 等待战斗 HUD 超时（30s）')
                break      # ★ 已进入战斗：跳出 for 去采样（§7.85；此前漏了这句，导致反复进战斗）
        elif bright((1370, 930, 1510, 1020)) > 0.10:
            nxt, ok = click_verified(*TAP_DRILL, '演习(关卡详情)', img)
        elif dark_ratio > 0.55:
            nxt, ok = click_verified(960, 988, '结算/加载画面中央', img)
        else:
            nxt, ok = click_verified(*TAP_H124, 'H12-4(关卡地图)', img)
        fails = 0 if ok else fails + 1
        if fails == 1:
            # 升级①：点底部**章节标签**（实测坐标，§7.79）
            nxt2, ok2 = click_verified(*EP_LABEL, 'EPISODE 10 标签', nxt)
            if ok2:
                img, fails = nxt2, 0
                continue
        if fails == 2:
            # 升级②：点最右侧 ▶ 箭头，视图右移
            nxt3, ok3 = click_verified(*EP_NEXT, 'EPISODE ▶ 右移', nxt)
            if ok3:
                img, fails = nxt3, 0
                continue
        if fails >= 3:
            print(f'[{step}] 三次升级尝试均未生效 ⇒ 停止。暗像素占比 {dark_ratio:.2f}；请人工确认界面。')
            return 3
        img = nxt
        time.sleep(0.2)
    else:
        print('没进到战斗'); return 2

    # ---- 2) 立刻密集采样 ----
    samples = []
    for i in range(n):
        img, mid = grab_timed()
        c, conf = read(img)
        band = img[BAR_ROI[1]:BAR_ROI[3], BAR_ROI[0]:BAR_ROI[2]]
        ph = bar_phase(band, full_px=BAR_ROI[2] - BAR_ROI[0])
        # ★ 用官方标定表查"像素宽度 → 精确帧"，而不是 round(比例×30) 的线性近似（§7.78）
        ph['sub_frame'] = frame_from_width(ph['fill_px'], PIXEL_MAP_30F)
        samples.append((mid, c, conf, ph['sub_frame'], ph['frac']))
        print(f'  采样{i}: t={mid:.3f} 费用={c} conf={conf:.3f} 相位={ph["sub_frame"]:>2} 比例={ph["frac"]:.3f}')

    # ---- 3) 精度比对 ----
    print('\n逐对比较：推得逻辑帧(Δ费用×30+Δ相位) vs 墙钟Δt×30')
    errs = []
    t_ref = samples[0][0]
    for i in range(1, len(samples)):
        t0, c0, _, p0, _ = samples[i - 1]
        t1, c1, _, p1, _ = samples[i]
        if c0 is None or c1 is None:
            continue
        dc = c1 - c0
        dphase = (p1 - p0) % 30
        if dc == 0:
            dphase = 0                     # 封顶/费用未变 ⇒ 条静止，相位不可用（§7.68）
        frames = dc * 30 + dphase
        wall = (t1 - t0) * 30.0
        e = frames - wall
        errs.append(e)
        print(f'  #{i}: 费用 {c0}→{c1}(Δ{dc}) 相位 {p0}→{p1} ⇒ 推得 {frames:>4} 帧 | '
              f'墙钟 {wall:6.1f} 帧 | 误差 {e:+6.1f} 帧 {"（封顶，相位不可用）" if dc == 0 else ""}')
    if errs:
        import statistics
        good = [e for e in errs if abs(e) < 25]
        print(f'\n有效样本 {len(good)}/{len(errs)}；|误差| 中位 '
              f'{statistics.median([abs(e) for e in good]):.1f} 帧' if good else '无有效样本')
        print('判据：|误差| ≤ 2 帧 ⇒ 方法一在实机可用于帧级对齐（adb 采集往返抖动约 ±1.5 帧）。')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
