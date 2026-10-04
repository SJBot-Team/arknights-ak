# -*- coding: utf-8 -*-
"""test_paused_protocol.py — 暂停驱动协议（帧级精度核心）的边界测试

覆盖：①暂停遮罩未出现 ⇒ pause() 必须失败（绝不"以为暂停了"）；
     ②相位永不满足 ⇒ resume_at 必须超时失败且状态一致；
     ③多批 stage/commit 的顺序与清空；
     ④same_frame_batch 成功路径；
     ⑤恢复点必须离相位边界足够远（min_phase_gap）。
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding='utf-8')

from plugins.clock.paused_protocol import PausedSession        # noqa: E402


class FakeTick:
    def __init__(self, frame, sub):
        self.ok = True
        self.frame = frame
        self.sub_frame = sub


class Clock:
    """可控时钟：按给定策略产出相位。"""

    def __init__(self, seq=None, fixed=None):
        self.seq = list(seq or [])
        self.fixed = fixed
        self.i = 0

    def read(self):
        if self.fixed is not None:
            self.i += 1
            return FakeTick(self.i, self.fixed)
        ph = self.seq[self.i % len(self.seq)]
        self.i += 1
        return FakeTick(self.i, ph)


def t1_pause_not_confirmed():
    taps, keys = [], []
    s = PausedSession(Clock(fixed=0), tap=lambda *a: taps.append(a),
                      is_paused=lambda: False, key_pause=lambda: keys.append(1),
                      max_confirm_ms=80)
    ok = s.pause()
    assert ok is False, '遮罩未出现时 pause() 必须返回 False'
    assert s.state.paused is False
    assert ('pause_failed', None) in s.state.notes
    print('  A 暂停未确认 ⇒ 判失败        PASS（绝不"以为暂停了"）')


def t2_resume_timeout():
    # 相位恒为 0，目标相位 0，min_phase_gap=6 ⇒ 永远不满足 gap 条件
    s = PausedSession(Clock(fixed=0), tap=lambda *a: None,
                      is_paused=lambda: True, key_pause=lambda: None,
                      min_phase_gap=6)
    assert s.pause() is True
    assert s.resume_at(target_phase=0, timeout_ms=60) is False, '相位不满足时必须超时失败'
    assert s.state.paused is True, '恢复失败时不应把 paused 置 False'
    assert ('resume_timeout', None) in s.state.notes
    print('  B 相位永不满足 ⇒ 恢复超时失败  PASS（状态保持一致）')


def t3_stage_order_and_clear():
    hits = []
    s = PausedSession(Clock(fixed=0), tap=lambda x, y: hits.append((x, y)),
                      is_paused=lambda: True, key_pause=lambda: None)
    s.pause()
    s.stage([{'kind': 'deploy', 'tap': (10, 20)}])
    s.stage([{'kind': 'skill', 'tap': (30, 40)}, {'kind': 'retreat', 'tap': (50, 60)}])
    n = s.commit()
    assert n == 3 and hits == [(10, 20), (30, 40), (50, 60)], f'顺序/清空有误: {hits}'
    assert s.state.staged == [], 'commit 后必须清空队列'
    print('  C 多批 stage/commit 顺序与清空 PASS（同帧操作按排队顺序注入）')


def t4_same_frame_batch_ok():
    hits = []
    paused = {'v': False}
    # 相位序列：能在 target=0 且距边界 ≥6 帧处命中
    s = PausedSession(Clock(seq=[5, 10, 15, 20, 25, 3, 8, 13]),
                      tap=lambda x, y: hits.append((x, y)),
                      is_paused=lambda: paused['v'],
                      key_pause=lambda: paused.__setitem__('v', not paused['v']),
                      min_phase_gap=6)
    ok = s.same_frame_batch([{'kind': 'deploy', 'tap': (100, 200)},
                             {'kind': 'skill', 'tap': (300, 400)}], target_phase=0)
    assert ok and len(hits) == 2 and s.state.resumes == 1 and not s.state.paused, f'{ok} {hits}'
    print('  D same_frame_batch 成功路径     PASS')


def t5_gap_rule():
    """恢复点必须距相位边界 ≥ min_phase_gap（避开跨费用结算的 ±1 帧歧义）。"""
    picked = []

    class C:
        def __init__(self):
            self.ph = [1, 2, 28, 29, 0, 7, 8]

        def read(self):
            v = self.ph.pop(0) if self.ph else 0
            return FakeTick(1, v)

    s = PausedSession(C(), tap=lambda *a: None, is_paused=lambda: True,
                      key_pause=lambda: None, min_phase_gap=6)
    s.pause()
    ok = s.resume_at(target_phase=0, timeout_ms=200)
    # 相位 7 距 0 的 gap=7 ≥6 ⇒ 应在此恢复（而不是在 1/2/28/29/0 上恢复）
    rec = [n for n in s.state.notes if n[0] == 'resume']
    assert ok and rec and rec[0][1]['phase'] == 7, f'未按 gap 规则恢复: {rec}'
    print('  E 恢复点距边界 ≥6 帧          PASS（避开跨费用结算的 ±1 帧歧义）')


def main():
    print('暂停协议边界测试：')
    for fn in (t1_pause_not_confirmed, t2_resume_timeout, t3_stage_order_and_clear,
               t4_same_frame_batch_ok, t5_gap_rule):
        fn()
    print('汇总: 暂停协议 A/B/C/D/E 全部 PASS')


if __name__ == '__main__':
    main()
