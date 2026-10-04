# -*- coding: utf-8 -*-
"""test_skill_ready.py — 技能栏识别器自检（合成图，无需游戏）

覆盖：
  A. mode=ready ：就绪（亮金按钮）/ 充能中（暗灰）/ 激活中（另一色）三态判别
  B. mode=sp_bar：条状 SP 条 0/25/50/75/100% 填充比例
  C. mode=sp_arc：环形 SP 表 0/25/50/75/100% 圆弧占比
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)

import numpy as np          # noqa: E402
from plugins.recognize.skill_ready import SkillReadyRecognizer   # noqa: E402


def synth_button(kind: str, size=(64, 64)) -> np.ndarray:
    """合成技能按钮：ready=亮金、charging=暗灰、active=亮蓝。"""
    h, w = size
    img = np.zeros((h, w, 3), dtype=np.uint8)
    if kind == 'ready':
        img[:, :] = (40, 180, 240)          # BGR 金黄（高亮 + 高饱和）
        img[10:54, 10:54] = (60, 200, 255)
    elif kind == 'charging':
        img[:, :] = (30, 30, 34)            # 暗灰（低饱和）
        img[10:54, 10:54] = (46, 46, 50)
    else:                                   # active
        img[:, :] = (230, 120, 40)          # BGR 蓝
        img[10:54, 10:54] = (255, 150, 60)
    return img


def synth_bar(ratio: float, size=(12, 100)) -> np.ndarray:
    h, w = size
    img = np.zeros((h, w, 3), dtype=np.uint8)
    fill = int(round(ratio * w))
    img[:, :fill] = 235
    img[:, fill:] = 40
    return img


def synth_arc(ratio: float, size=(80, 80)) -> np.ndarray:
    h, w = size
    img = np.zeros((h, w, 3), dtype=np.uint8)
    cy, cx = (h - 1) / 2.0, (w - 1) / 2.0
    r = min(h, w) / 2.0 - 3.0
    n = 720
    lit_n = int(round(ratio * n))
    for k in range(n):
        ang = -np.pi / 2 + 2 * np.pi * k / n
        y = int(round(cy + r * np.sin(ang)))
        x = int(round(cx + r * np.cos(ang)))
        if 0 <= y < h and 0 <= x < w:
            img[y, x] = (235, 235, 235) if k < lit_n else (50, 50, 50)
    return img


def test_ready_states():
    print('=== A. 技能按钮三态 ===')
    rec = SkillReadyRecognizer()
    spec = {'mode': 'ready', 'ready_ratio': 0.20, 'ready_sat': 0.35,
            'ready_hue': 45.0, 'ready_hue_tol': 50.0}
    cases = [('ready', True, 'ready'), ('charging', False, 'charging'), ('active', False, 'active')]
    ok = 0
    for kind, expect, expect_state in cases:
        img = synth_button(kind)
        ms = rec.run(img, spec, None, (0, 0))
        ex = ms[0].extra if ms else {}
        good = (ex.get('ready') == expect)
        ok += good
        print(f'  {kind:<9} 期望 ready={expect!s:<5} 实得={ex.get("ready")!s:<5} '
              f'状态={ex.get("state"):<9} 彩色占比={ex.get("color_ratio")} '
              f'色相={ex.get("hue")} {"OK" if good else "DIFF"}')
    print(f'  通过 {ok}/{len(cases)}')
    return ok == len(cases)


def test_sp_bar():
    print('\n=== B. 条状 SP 条 ===')
    rec = SkillReadyRecognizer()
    ok = 0
    for ratio in (0.0, 0.25, 0.5, 0.75, 1.0):
        img = synth_bar(ratio)
        ms = rec.run(img, {'mode': 'sp_bar'}, None, (0, 0))
        got = ms[0].extra['sp_ratio']
        good = abs(got - ratio) <= 0.06
        ok += good
        print(f'  期望 {ratio:<5} 实得 {got:<6.3f} {"OK" if good else "DIFF"}')
    print(f'  通过 {ok}/5')
    return ok == 5


def test_sp_arc():
    print('\n=== C. 环形 SP 表 ===')
    rec = SkillReadyRecognizer()
    ok = 0
    for ratio in (0.0, 0.25, 0.5, 0.75, 1.0):
        img = synth_arc(ratio)
        ms = rec.run(img, {'mode': 'sp_arc', 'samples': 360}, None, (0, 0))
        got = ms[0].extra['sp_ratio']
        good = abs(got - ratio) <= 0.08
        ok += good
        print(f'  期望 {ratio:<5} 实得 {got:<6.3f} 就绪={ms[0].extra["ready"]} '
              f'{"OK" if good else "DIFF"}')
    print(f'  通过 {ok}/5')
    return ok == 5


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    res = {'A_ready': test_ready_states(), 'B_sp_bar': test_sp_bar(), 'C_sp_arc': test_sp_arc()}
    print('\n汇总: ' + '  '.join(f'{k}={"PASS" if v else "FAIL"}' for k, v in res.items()))
    sys.exit(0 if all(res.values()) else 1)
