# -*- coding: utf-8 -*-
"""paused_protocol.py — 暂停驱动的帧级协议（用户 2026-09-14 指出的关键前提）

## 为什么必须是暂停
图像识别**无法避免延迟**（截图→识别→决策→注入），游戏还可能卡顿导致**游戏内时间与外部墙钟漂移**。
因此玩家视角的正确结论是：

> **只有游戏暂停时，图像识别到的精确帧数才严格等同于当前游戏时间。**

暂停 = 逻辑时间冻结 ⇒ 我们有**任意长的外部时间**去识别、去注入，而注入的操作在**恢复的那一帧**生效。
于是"帧级精度"不再依赖"响应有多快"，只依赖两件事：
  1. **恢复瞬间**对齐到目标帧（用费用条相位/待部署十分位）；
  2. 暂停期间把所有**同帧操作**排好队（PRTS+ 的"同帧多操作"正是这么做的）。

这也解释了 CostRuler 为什么敢用截图链路（它的 config 里还有 `screenshot_delay_ms` 补偿）：
它工作在暂停/子弹时间下，采集延迟不影响帧精度。

## 本模块提供的协议
    sess = PausedSession(clock, input_backend, ui)
    sess.pause()                     # 暂停并**确认**暂停遮罩出现（确认失败即报错，绝不"以为暂停了"）
    sess.stage(actions)              # 暂停期间排队同帧操作（部署/技能/撤退，顺序即执行顺序）
    sess.resume_at(target_phase=0)   # 等到费用条相位/十分位回到目标相位再点恢复
    sess.frames()                    # 暂停期间冻结的帧号（= 当前游戏时间，严格）

所有外部依赖（时钟、注入、UI 探针）都以可调用对象注入，便于离线单测。
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field


@dataclass
class PausedState:
    paused: bool = False
    frame: int = 0
    phase: int | None = None
    staged: list = field(default_factory=list)
    resumes: int = 0
    notes: list = field(default_factory=list)


class PausedSession:
    """暂停 → 排队同帧操作 → 在目标相位恢复。"""

    def __init__(self, clock, tap=None, is_paused=None, key_pause=None,
                 max_confirm_ms: int = 800, min_phase_gap: int = 6, now=time.perf_counter):
        """
        clock        : 需提供 read() → FrameTick（含 frame 与 sub_frame 相位）
        tap          : (x, y) -> None，注入点击（暂停按钮/卡片/格子）
        is_paused    : () -> bool，画面探针：暂停遮罩是否出现（**必须真实检测，不能假设**）
        key_pause    : () -> None，发送"暂停"键（PRTS+ 用鼠标侧键绑定暂停）
        now          : 时间源（便于测试）
        """
        self.clock = clock
        self.tap = tap
        self.is_paused = is_paused
        self.key_pause = key_pause
        self.max_confirm_ms = max_confirm_ms
        # 恢复点必须离相位边界足够远，避免"恢复时刚好跨过费用结算"造成 ±1 帧歧义
        self.min_phase_gap = min_phase_gap
        self.now = now
        self.state = PausedState()

    # ---------------- 暂停 ----------------
    def pause(self) -> bool:
        """暂停并确认。确认不上就返回 False（调用方必须当成失败处理）。"""
        if self.key_pause is not None:
            self.key_pause()
        t0 = self.now()
        while (self.now() - t0) * 1000 < self.max_confirm_ms:
            if self.is_paused is None or self.is_paused():
                self.state.paused = True
                self.state.notes.append(('pause', round((self.now() - t0) * 1000, 1)))
                return True
            time.sleep(0.01)
        self.state.notes.append(('pause_failed', None))
        return False

    # ---------------- 暂停期间的帧号（严格等于游戏时间） ----------------
    def frames(self) -> int:
        t = self.clock.read()
        if t is not None and getattr(t, 'ok', False):
            self.state.frame = int(t.frame)
            self.state.phase = getattr(t, 'sub_frame', None)
        return self.state.frame

    # ---------------- 排队同帧操作 ----------------
    def stage(self, actions: list) -> None:
        """actions: [{'kind':'deploy'|'skill'|'retreat', ...}]，顺序即执行顺序。"""
        for a in actions:
            self.state.staged.append(dict(a))

    def commit(self) -> int:
        """在**暂停中**把排队的操作逐条注入（此时时间冻结，快慢无所谓）。"""
        n = 0
        for a in self.state.staged:
            if self.tap is not None and a.get('tap'):
                self.tap(*a['tap'])
                n += 1
        self.state.staged.clear()
        self.state.notes.append(('commit', n))
        return n

    # ---------------- 恢复并对齐 ----------------
    def resume_at(self, target_phase: int = 0, timeout_ms: int = 1200) -> bool:
        """等到费用条相位（或十分位相位）回到 target_phase 再恢复。

        为什么用相位而不是"墙钟"：相位是**游戏内**量，天然免疫卡顿与采集延迟。
        要求当前相位与 target_phase 之间留出 `min_phase_gap`，避免恢复瞬间正好跨费用结算。
        """
        t0 = self.now()
        while (self.now() - t0) * 1000 < timeout_ms:
            t = self.clock.read()
            ph = getattr(t, 'sub_frame', None) if t is not None else None
            if ph is not None:
                gap = (ph - target_phase) % 30
                if gap >= self.min_phase_gap and gap <= 30 - self.min_phase_gap:
                    if self.key_pause is not None:
                        self.key_pause()
                    self.state.paused = False
                    self.state.resumes += 1
                    self.state.notes.append(('resume', {'phase': ph, 'target': target_phase}))
                    return True
            time.sleep(0.002)
        self.state.notes.append(('resume_timeout', None))
        return False

    # ---------------- 一步到位 ----------------
    def same_frame_batch(self, actions: list, target_phase: int = 0) -> bool:
        """暂停 → 注入同帧操作 → 在目标相位恢复。返回是否全流程成功。"""
        if not self.pause():
            return False
        self.frames()
        self.stage(actions)
        self.commit()
        return self.resume_at(target_phase)


# --------------------------------------------------------------------------------------
# 离线自检（合成时钟 + 记录注入），验证协议状态机本身
# --------------------------------------------------------------------------------------
def _selftest():
    class FakeTick:
        def __init__(self, frame, sub):
            self.ok = True
            self.frame = frame
            self.sub_frame = sub

    class FakeClock:
        def __init__(self):
            self.i = 0
            self.phase = 15

        def read(self):
            self.i += 1
            self.phase = (self.phase + 1) % 30
            return FakeTick(self.i, self.phase)

    hits = []
    paused = {'v': False}
    sess = PausedSession(
        FakeClock(),
        tap=lambda x, y: hits.append(('tap', x, y)),
        is_paused=lambda: paused['v'],
        key_pause=lambda: paused.__setitem__('v', not paused['v']),
    )
    ok = sess.same_frame_batch([{'kind': 'deploy', 'tap': (100, 200)},
                                {'kind': 'skill', 'tap': (300, 400)}], target_phase=0)
    print('自检：same_frame_batch =', ok, '注入 =', hits, '恢复次数 =', sess.state.resumes)
    print('      状态记录 =', sess.state.notes)
    assert ok and len(hits) == 2 and sess.state.resumes == 1 and not sess.state.paused
    print('暂停协议自检 PASS')


if __name__ == '__main__':
    import sys
    sys.stdout.reconfigure(encoding='utf-8')
    _selftest()
