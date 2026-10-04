# -*- coding: utf-8 -*-
"""nav_check.py — 只读"我在哪一页"信号，供逐步导航校验（避免盲点）。

信号：
  battle   : BattleHudGate.in_battle
  cards    : 底部卡片行分段数（编队页/战斗页都多）
  btn_blue : 「开始行动」按钮区域(1540..1780, 930..1050) 的蓝色占比（关卡详情页高）
  btn_drill: 「演习」按钮区域(1450..1570, 950..1030) 的灰白亮度（关卡详情页有）
"""
from __future__ import annotations

import os
import sys

import cv2
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding='utf-8')

from plugins.action.deploy import Deployer                    # noqa: E402
from plugins.capture.emu_window import make_capture           # noqa: E402
from plugins.recognize.battle_hud import BattleHudGate        # noqa: E402


def main() -> int:
    tag = sys.argv[1] if len(sys.argv) > 1 else ''
    img = make_capture('adb').grab().image
    out = os.path.join(r'C:\Users\23922\Documents\ds_harness\ak\.tmp', f'nav_{tag}.png')
    cv2.imwrite(out, img)
    gate = BattleHudGate()
    st = gate.check(img)
    cards = st['cards']
    blue = img[930:1050, 1540:1780]
    b, g, r = blue[..., 0].astype(float), blue[..., 1].astype(float), blue[..., 2].astype(float)
    blue_frac = float(((b > 120) & (b > r + 30)).mean())
    drill = float(cv2.cvtColor(img[950:1030, 1450:1570], cv2.COLOR_BGR2GRAY).mean())
    print(f'[{tag}] battle={st["in_battle"]} cards={cards} '
          f'btn_blue={blue_frac:.3f} btn_drill={drill:.0f} mean={img.mean():.0f} → {out}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
