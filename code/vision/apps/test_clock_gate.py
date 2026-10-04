# -*- coding: utf-8 -*-
"""test_clock_gate.py — ★回归：费用条时钟的"战斗 HUD 门控"真的生效（离线，用本机截图当"引擎"）。

复现实机教训：在「任务失败」结算页上，`CostBarRecognizer` 会给出伪读数（frame≈26/30），
而**带门控的 `CostBarClock` 必须拒绝该读数**（`ok=False`、绝对帧不推进）；
在真正的战斗截图上则必须正常读数并累加。
"""
from __future__ import annotations

import os
import sys

import cv2

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding='utf-8')

from plugins.clock.cost_ruler import CostBarClock          # noqa: E402

TMP = r'C:\Users\23922\Documents\ds_harness\ak\.tmp'
FAILED = []


class _Shot:
    """把一张静态截图伪装成采集后端（`origin` 必须给，识别器会下标取用）。"""

    def __init__(self, path):
        self.img = cv2.imread(path)
        self.origin = (0, 0)

    def grab(self):
        class _F:
            pass
        f = _F()
        f.image = self.img
        f.origin = self.origin
        return f


class _Engine:
    def __init__(self, path):
        self._shot = _Shot(path)

    def grab(self):
        return self._shot.grab()


def check(name, cond, detail=''):
    print(f'  {"✅" if cond else "❌"} {name}{("  — " + detail) if detail else ""}')
    if not cond:
        FAILED.append(name)


def main():
    print('=== 门控开（默认）：非战斗画面必须拒绝读数 ===')
    for fn in ('live_24_now.png', 'live_26_state.png', 'live_home.png'):
        p = os.path.join(TMP, fn)
        if not os.path.exists(p):
            continue
        c = CostBarClock(_Engine(p), {})
        st = c.read()
        check(f'{fn} → ok=False（被门控拦下）', st.ok is False,
              f"reason={c.gate_state['reason'] if c.gate_state else '-'}")
        check(f'{fn} → 绝对帧不推进', st.elapsed_frames == 0, f'elapsed={st.elapsed_frames}')

    print('\n=== 门控开：战斗画面必须正常读数 ===')
    for fn in ('live_07_battle2.png', 'live_11_final.png'):
        p = os.path.join(TMP, fn)
        if not os.path.exists(p):
            continue
        c = CostBarClock(_Engine(p), {})
        st = c.read()
        check(f'{fn} → ok=True（在战斗中被放行）', st.ok is True,
              f'frame_in_cost={st.frame_in_cost} cycle={st.cycle_frames}')

    print('\n=== 门控关（require_battle=False，仅对照）：同样的失败页会给出伪读数 ===')
    p = os.path.join(TMP, 'live_24_now.png')
    if os.path.exists(p):
        c = CostBarClock(_Engine(p), {'require_battle': False})
        st = c.read()
        check('关闭门控后失败页**被当成有效读数**（证明门控确有必要）', st.ok is True,
              f'frame_in_cost={st.frame_in_cost} → 若被采信即污染绝对时间基准')

    print()
    if FAILED:
        print(f'❌ 未通过 {len(FAILED)} 项：{FAILED}')
        return 1
    print('✅ 通过：费用条时钟已按"是否在战斗中"正确门控')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
