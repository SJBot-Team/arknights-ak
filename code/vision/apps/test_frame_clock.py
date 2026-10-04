# -*- coding: utf-8 -*-
"""test_frame_clock.py — 帧级时钟回归（合成图像 + 合成十分位序列，逐帧校验）

覆盖：
  A. 费用条相位：30 个条内帧偏移**逐个精确恢复**（含噪声与半亮度）
  B. 费用格 + 相位（方法1）：300 帧连续恢复，误差 0 帧；并验证
     · 不做消耗记账 ⇒ 恰好偏 10 费 = 300 帧（说明"净消耗账本"不可省）
     · 顶上限后条停住 ⇒ stalled=True 且降权
  C. 待部署十分位（方法2）：3 名错开相位，逐帧判定"是否走了一帧"，300 帧误差 0
  D. 融合：主源失效自动回退、倒退跳变被单调性拦住、残差可读
"""
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding='utf-8')

from plugins.clock.frame_clock import (                     # noqa: E402
    CostLatticeClock, FrameClock, FrameTick, RedeployTenthsClock,
    bar_phase, render_cost_bar, synth_tenths, FRAMES_PER_COST)

RESULTS = {}


def test_bar_phase_exact():
    """A：30 个相位逐个精确恢复。"""
    bad = []
    for sub in range(FRAMES_PER_COST):
        img = render_cost_bar(sub, width=240)
        got = bar_phase(img)['sub_frame']
        if got != sub:
            bad.append((sub, got))
    # 带噪声（模拟实机压缩/抖动）
    bad_noisy = []
    for sub in range(FRAMES_PER_COST):
        worst = 0
        for seed in range(5):
            img = render_cost_bar(sub, width=240, noise=12.0, seed=seed)
            got = bar_phase(img)['sub_frame']
            worst = max(worst, abs(got - sub))
        if worst > 0:
            bad_noisy.append((sub, worst))
    print(f'A 费用条相位：干净 {FRAMES_PER_COST - len(bad)}/{FRAMES_PER_COST} 精确；'
          f'带噪 5 种子最大偏差 {max([w for _, w in bad_noisy], default=0)} 帧')
    if bad:
        print('   干净样本错例：', bad[:6])
    if bad_noisy:
        print('   带噪样本错例：', bad_noisy[:6])
    return (not bad) and (not bad_noisy)


def test_cost_lattice_300_frames():
    """B：300 帧逐帧恢复（含一次消耗），并验证账本不可省 + 停住检测。"""
    initial, fpc = 10, FRAMES_PER_COST
    spend_frame, spend_units = 40, 10

    state = {'frame': 0}

    def make_readers(clock):
        def read_cost():
            cost = initial + state['frame'] // fpc - (spend_units if state['frame'] >= spend_frame else 0)
            return max(0, int(cost))
        return read_cost

    def grab_factory():
        def grab():
            sub = state['frame'] % fpc
            return type('F', (), {'image': render_cost_bar(sub, width=240)})()
        return grab

    clock = CostLatticeClock(grab_factory(), make_readers(None),
                             {'initial_cost': initial, 'bar_roi': (0, 0, 240, 10),
                              'stall_tolerance': 999})
    errs = []
    for f in range(300):
        state['frame'] = f
        if f == spend_frame:
            clock.note_spent(spend_units)
        t = clock.read()
        if (not t.ok) or t.frame != f:
            errs.append((f, t.frame, t.ok))
    print(f'B 费用格+相位：300 帧逐帧恢复，误差样本 {len(errs)} 个'
          + (f'，前几个 {errs[:5]}' if errs else '（全部精确）'))

    # 账本不可省：不记账会偏 spend_units×30 帧
    clock2 = CostLatticeClock(grab_factory(), make_readers(None),
                              {'initial_cost': initial, 'bar_roi': (0, 0, 240, 10)})
    state['frame'] = 200
    t2 = clock2.read()
    drift = t2.frame - 200
    print(f'   不记账时偏差 = {drift} 帧（幅值期望 {spend_units * fpc}，'
          f'符号为负 = 少算，因为显示费用被消耗拉低）')

    # 停住检测：费用顶上限，条不动
    stall = CostLatticeClock(lambda: type('F', (), {'image': render_cost_bar(20, width=240)})(),
                             lambda: initial + 10, {'initial_cost': initial,
                                                    'bar_roi': (0, 0, 240, 10),
                                                    'stall_tolerance': 5})
    flags = [stall.read().stalled for _ in range(8)]
    print(f'   顶上限不动时的 stalled 序列 = {flags}（期望后段为 True）')
    return (not errs) and abs(drift) == spend_units * fpc and flags[-1] is True


def test_redeploy_tenths():
    """C：3 名计时器干员的十分位 ⇒ 逐帧计数精确。"""
    frames = 300
    seq = synth_tenths(frames, offsets=(0, 1, 2))
    it = iter(seq)
    cur = {'d': seq[0]}

    def read_digits():
        return list(cur['d'])

    clock = RedeployTenthsClock(read_digits, {'n_operators': 3, 'anchor_frame': 0})
    clock.read()                       # 第 0 帧（建立基准）
    errs = []
    for f in range(1, frames):
        cur['d'] = seq[f]
        t = clock.read()
        if not t.ok or t.frame != f:
            errs.append((f, t.frame))
    print(f'C 十分位法：{frames} 帧逐帧计数，误差样本 {len(errs)} 个'
          + (f'，前几个 {errs[:5]}' if errs else '（全部精确）'))

    # 丢帧鲁棒性：随机 5% 读不到
    rng = np.random.default_rng(0)
    cur2 = {'d': seq[0]}
    clock2 = RedeployTenthsClock(lambda: list(cur2['d']), {'n_operators': 3})
    clock2.read()
    dropped = 0
    for f in range(1, frames):
        cur2['d'] = seq[f]
        if rng.random() < 0.05:
            cur2['d'] = (None, None, None)
            dropped += 1
        clock2.read()
    lag = frames - 1 - clock2.frames
    print(f'   丢读 {dropped} 次后：计数 {clock2.frames}（真值 {frames - 1}），滞后 {lag} 帧')
    return (not errs) and lag <= dropped


def test_fusion():
    """D：融合的优先级 / 回退 / 单调 / 残差。"""
    class Src:
        def __init__(self, name, values):
            self.name = name
            self.values = list(values)
            self.i = 0

        def read(self):
            v = self.values[min(self.i, len(self.values) - 1)]
            self.i += 1
            if v is None:
                return FrameTick(ok=False, source=self.name)
            return FrameTick(ok=True, frame=v, confidence=0.9, source=self.name)

    a = Src('a', [10, 11, None, None, 14, 13, 15])     # 中途失效 + 一次倒退
    b = Src('b', [10, 11, 12, 13, 14, 15, 16])
    fc = FrameClock([a, b], priority=['a', 'b'])
    seq = [fc.tick() for _ in range(7)]
    frames = [t.frame for t in seq]
    srcs = [t.source for t in seq]
    print(f'D 融合：frames={frames}')
    print(f'   选中的源={srcs}  残差={fc.residual}  异常={fc.anomalies}')
    monotonic = all(frames[i] <= frames[i + 1] for i in range(len(frames) - 1))
    fell_back = ('b' in srcs)
    print(f'   单调={monotonic} 回退到 b={fell_back}')
    return monotonic and fell_back


def main():
    RESULTS['A_bar_phase'] = test_bar_phase_exact()
    RESULTS['B_cost_lattice'] = test_cost_lattice_300_frames()
    RESULTS['C_redeploy'] = test_redeploy_tenths()
    RESULTS['D_fusion'] = test_fusion()
    print('\n汇总: ' + '  '.join(f'{k}={"PASS" if v else "FAIL"}' for k, v in RESULTS.items()))
    return 0 if all(RESULTS.values()) else 1


if __name__ == '__main__':
    raise SystemExit(main())
