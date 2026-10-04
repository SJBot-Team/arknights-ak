# -*- coding: utf-8 -*-
"""test_auto_enter.py — 自动进关导航的**离线**测试（用真实帧序列驱动决策链）

用已录制的真实界面帧做"假采集器"，验证导航在几种界面序列下的决策是否正确：
  A 已在战斗            → 立即返回 True，**不点任何东西**
  B 详情 → 编队 → 战斗   → 点「演习」→ 点模板给出的「开始行动」→ 返回 True
  C 结算(unknown) → 详情 → 编队 → 战斗 → 先点"继续"再走完
  D 一直是结算          → 步数用尽返回 False（不得死循环，且**只点"继续"**）
另断言：合规——**全过程从未点击关卡详情的「开始行动」(1710,990)/(1751,991) 等消耗理智位置**。
"""
from __future__ import annotations

import os
import sys

import cv2

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding='utf-8')

from plugins.nav.auto_enter import AutoEnter                       # noqa: E402
from plugins.recognize.ui_state import UiState                     # noqa: E402

TMP = r'C:\Users\23922\Documents\ds_harness\ak\.tmp'


def load(name):
    img = cv2.imread(os.path.join(TMP, name))
    if img is None:
        raise SystemExit(f'缺少测试帧 {name}')
    return img


class FakeCap:
    """按给定循环序列产出帧（用完则重复最后一帧）。"""

    def __init__(self, frames):
        self.frames = frames
        self.i = 0
        self.n = 0

    def grab(self):
        f = self.frames[min(self.i, len(self.frames) - 1)]
        self.i += 1
        self.n += 1
        return type('Frame', (), {'image': f, 'origin': (0, 0), 'rect': None})()


class FakeTap:
    def __init__(self):
        self.hits = []

    def __call__(self, x, y):
        self.hits.append((int(x), int(y)))


# 可能消耗理智的位置（关卡详情的「开始行动」）——导航**绝不允许**点这些
FORBIDDEN = {(1710, 990), (1751, 991), (1770, 986), (1753, 1054)}


def run_case(tag, frames, expect_ok, expect_taps=None):
    cap, tap = FakeCap(frames), FakeTap()
    logs = []
    ae = AutoEnter(cap, tap, UiState(), log=logs.append,
                   wait_battle_sleep=0.0, max_steps=6)
    ok = ae.enter()
    bad_forbidden = [p for p in tap.hits if p in FORBIDDEN]
    status = 'OK ' if (ok == expect_ok and not bad_forbidden) else 'BAD'
    print(f'  {status} {tag}: enter()={ok} 期望 {expect_ok}；点击 {tap.hits}；'
          f'状态序列 {[t["state"] for t in ae.trace]}')
    if bad_forbidden:
        print(f'      ★ 违规：点了可能消耗理智的位置 {bad_forbidden}')
    if expect_taps is not None:
        for want in expect_taps:
            if want not in tap.hits:
                print(f'      ★ 期望点击 {want} 未出现'); return False
    return (ok == expect_ok) and not bad_forbidden


def main():
    battle = load('battle_in.png')
    squad = load('battle_ready.png')
    detail = load('detail.png')
    unknown = load('diag_battle_0.png')      # 任务失败结算：UiState 判 unknown

    print('自动进关导航离线测试：')
    res = []
    # A 已在战斗
    res.append(run_case('A 已在战斗 → 立即返回', [battle], True, expect_taps=[]))
    # B 详情 →(点演习) 编队 →(点模板给出的开始行动) 战斗
    #   注意 mock 序列要能体现"点完演习后画面变成编队帧"，否则测不到 squad 分支
    res.append(run_case('B 详情→演习→编队→开始行动→战斗',
                        [detail, squad, squad, battle, battle, battle],
                        True, expect_taps=[(1441, 983), (1655, 759)]))
    # C 结算 →(继续) 详情 →(演习) 编队 →(开始行动) 战斗
    res.append(run_case('C 结算→继续→详情→编队→战斗',
                        [unknown, unknown, detail, squad, squad, battle, battle],
                        True, expect_taps=[(960, 988), (1441, 983), (1655, 759)]))
    # D 一直 unknown ⇒ 步数用尽失败
    res.append(run_case('D 一直 unknown → 失败退出', [unknown] * 8, False))
    print(f'汇总: 自动进关 A/B/C/D {"全部 PASS" if all(res) else "存在失败"}')
    return 0 if all(res) else 1


if __name__ == '__main__':
    raise SystemExit(main())
