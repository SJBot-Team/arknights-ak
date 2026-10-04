# -*- coding: utf-8 -*-
"""frame_clock.py — 帧级时钟（合规：不读内存，只用画面 + 墙钟）

用户 2026-09-14 给出的两种玩家常用精确计时法，作为本模块的两个主源：

**方法 1「费用条相位 + 费用整数格」**
    AK 的费用条每获得 1 点费用回绕一次，正好 **30 帧**（30 fps 逻辑帧）。
    于是  绝对帧 = 30 ×（显示费用 − 初始费用 + 净消耗）+ 条内帧偏移
    条内帧偏移 = round(填充比例 × 30)，取值 0..29 ⇒ **帧级分辨率**。
    ⚠ 关键前提：**费用顶到上限时条会停住**，此时相位不再推进。
      用户给的解法是"快满时故意消耗它，让费用条保持跳动"——执行端可以部署+撤退一个便宜干员
      （合规操作）来维持跳动；本模块在检测到条停住时会置 `stalled=True` 并降权。

**方法 2「待部署时间十分位」（计时器干员）**
    开局 0 帧暂停 → 部署 3 名干员 → 隔 1 帧撤退。每 3 帧相当于待部署时间过 0.1 秒，
    三名干员的十分位数字**错开跳动** ⇒ 每一帧至少有一个在跳，
    于是"这一帧有没有跳"就是 1 帧分辨率的判据，而且**完全不依赖费用环境**。
    本模块把它实现成：每帧读三个十分位 → 有任意一个变化即计 1 帧（多数表决抗抖）。

辅助源：
**方法 3「外部计时 + 倍速/暂停识别」**：墙钟 × HUD 倍速（1X/2X），暂停遮罩期间不计时；
**方法 4**：外部尺子进程（PC 端 ruler-app 的 WS/HTTP，已在 `cost_ruler.RulerClock`）。

融合规则（`FrameClock.tick()`）：
    按优先级挑选**当前可用**的源 → 强制**单调不减** → 记录与次优源的**残差**（用于自检）。
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field

import numpy as np

FPS = 30.0
FRAMES_PER_COST = 30

# --------------------------------------------------------------------------------------
# 官方标定表：费用条**像素长度 ↔ 精确帧**（直接查表，不做线性近似）
# 来源：ArknightsCostBarRuler 的 calibration/profile_1767884246_30f_1920x1080.json
#      （用户 2026-09-14 指出"费用尺应当包含完整的费用条相对长度与精确帧的比对信息，可以直接参考"）
# 条宽 180px / 30 帧 ⇒ 每帧约 6.2px；实测我方 MuMu 1920×1080 下条的亮列范围为 1739–1919 = 180px ✓
# --------------------------------------------------------------------------------------
PIXEL_MAP_30F = {
    0: 0, 6: 1, 13: 2, 19: 3, 25: 4, 31: 5, 38: 6, 44: 7, 50: 8, 56: 9,
    63: 10, 69: 11, 75: 12, 81: 13, 87: 14, 94: 15, 100: 16, 106: 17, 112: 18, 119: 19,
    125: 20, 131: 21, 137: 22, 144: 23, 150: 24, 156: 25, 162: 26, 169: 27, 175: 28, 180: 29,
}
# 60 帧口径（profile_1769254296_60f_1920x1080.json，total_frames=60）——用于核对帧率口径
PIXEL_MAP_60F = {
    0: 0, 3: 2, 6: 3, 10: 4, 13: 5, 16: 6, 19: 7, 22: 8, 25: 9, 28: 10,
    31: 11, 35: 12, 38: 13, 41: 14, 44: 15, 47: 16, 50: 17, 53: 18, 56: 19, 59: 20,
    63: 21, 66: 22, 69: 23, 72: 24, 75: 25, 78: 26, 81: 27, 84: 28, 87: 29, 91: 30,
}
BAR_LEFT_X_1920 = 1739        # 费用条左端（实测亮列起点）
BAR_WIDTH_PX_1920 = 180       # 费用条总宽（= pixel_map 的最大键）


def frame_from_width(px: float, pixel_map: dict | None = None) -> int:
    """填充像素宽度 → **精确帧**（查表：取不大于 px 的最大键）。

    这比 `round(比例 × 30)` 更准：官方标定表本身就带非线性（每帧 6~7px 不等）。
    """
    pm = pixel_map or PIXEL_MAP_30F
    ks = sorted(pm)
    if not ks:
        return 0
    best = ks[0]
    for k in ks:
        if px >= k:
            best = k
        else:
            break
    return int(pm[best])


def signed_phase_delta(p0: int, p1: int, modulus: int = 30) -> int:
    """把相位差规范到 [-modulus/2, modulus/2)。**算帧数必须用它，不能用 mod 30。**

    §7.133 的教训：采样间隔 ≈28 帧（略小于 30）时，每跨过一次费用结算，
    净相位会**倒退约 2 帧**；若用 `(p1-p0) mod 30`，p1<p0 的情形会被**多算一整圈（+30 帧）**，
    表现为"误差恒定 +30 帧"的自证陷阱。
    """
    d = (int(p1) - int(p0)) % modulus
    if d >= modulus // 2:
        d -= modulus
    return d


def frames_between(c0: int, p0: int, c1: int, p1: int, modulus: int = 30) -> int:
    """两帧之间的**逻辑帧数** = Δ费用×30 + Δ相位（Δ相位为带符号、规范到 [-15,15)）。

    例：费用 11→12、相位 27→24 ⇒ 30 + (-3) = 27 帧（不是 57）。
    """
    return (int(c1) - int(c0)) * modulus + signed_phase_delta(p0, p1, modulus)


# --------------------------------------------------------------------------------------
# 基础：费用条相位（纯函数，便于合成图像回归）
# --------------------------------------------------------------------------------------
def bar_phase(crop, thr_ratio: float = 0.55, x_left: int | None = None,
              x_right: int | None = None, full_px: int | None = None):
    """从费用条 ROI 图像估计填充比例与"条内帧偏移"。

    返回 dict(fill_px, width_px, frac, sub_frame, ok)
      · fill_px  = 最右侧被填充的列号 + 1（与 recognize/cost_bar.py 同口径）
      · frac     = fill_px / full_px
      · sub_frame= clip(round(frac * 30), 0, 29)  ← 帧级分辨率的关键
    """
    if crop is None or getattr(crop, 'size', 0) == 0:
        return {'ok': False, 'fill_px': 0, 'width_px': 0, 'frac': 0.0, 'sub_frame': 0}
    gray = crop[..., :3].mean(axis=2) if crop.ndim == 3 else crop.astype('float32')
    col_max = gray.max(axis=0)
    peak = float(col_max.max()) if col_max.size else 0.0
    if peak <= 1e-6:
        # 全空条：刚结算完新费用，条内偏移 0
        return {'ok': True, 'fill_px': 0, 'width_px': int(col_max.size), 'frac': 0.0, 'sub_frame': 0}
    thr = peak * float(thr_ratio)
    filled = np.where(col_max >= thr)[0]
    fill_px = int(filled.max() + 1) if filled.size else 0
    left = 0 if x_left is None else int(x_left)
    right = int(col_max.size) if x_right is None else int(x_right)
    width = max(1, right - left)
    span = int(full_px) if full_px else width
    frac = min(1.0, max(0.0, (fill_px - left) / max(1, span)))
    sub = int(round(frac * FRAMES_PER_COST))
    sub = 0 if sub >= FRAMES_PER_COST else max(0, sub)     # 满格即回绕
    return {'ok': True, 'fill_px': fill_px, 'width_px': width, 'frac': frac, 'sub_frame': sub}


def render_cost_bar(sub_frame: int, width: int = 240, height: int = 10,
                    filled: float = 1.0, noise: float = 0.0, seed: int = 0):
    """合成一张费用条图（用于帧级精度回归）：给定条内帧偏移，画出对应填充宽度。"""
    img = np.zeros((height, width, 3), np.float32)
    frac = (sub_frame % FRAMES_PER_COST) / FRAMES_PER_COST
    w = int(round(frac * width))
    if w > 0:
        img[:, :w, :] = 255.0 * float(filled)
    if noise > 0:
        rng = np.random.default_rng(seed)
        img += rng.normal(0.0, noise, img.shape).astype('float32')
    return np.clip(img, 0, 255).astype('uint8')


# --------------------------------------------------------------------------------------
# 统一 tick
# --------------------------------------------------------------------------------------
@dataclass
class FrameTick:
    ok: bool = False
    frame: int = 0                 # 绝对逻辑帧（战斗开始 = 0）
    confidence: float = 0.0
    source: str = 'none'
    sub_frame: int | None = None   # 条内帧偏移（方法1）
    stalled: bool = False          # 费用条停住（顶上限）
    detail: dict = field(default_factory=dict)

    def as_dict(self) -> dict:
        return {'ok': self.ok, 'frame': self.frame, 'conf': round(self.confidence, 3),
                'source': self.source, 'sub': self.sub_frame, 'stalled': self.stalled,
                **{k: v for k, v in self.detail.items()}}


# --------------------------------------------------------------------------------------
# 源 1：费用格 + 费用条相位（方法 1）
# --------------------------------------------------------------------------------------
class CostLatticeClock:
    """读「费用数字」（整数格）+「费用条相位」（秒内帧）⇒ 绝对帧。

    spec:
      initial_cost       初始费用（关卡 options.initialCost，h12-4 = 10）
      frames_per_cost    每费帧数（默认 30）
      bar_roi            费用条 ROI（绝对像素 (x0,y0,x1,y1) 或相对 (0..1)×4）
      stall_tolerance    连续多少次相位不变即判定"条停住"（默认 12 ≈ 0.4s）
    """

    name = 'cost_lattice'

    def __init__(self, grab, read_cost, spec: dict | None = None):
        self.grab = grab
        self.read_cost = read_cost
        self.spec = dict(spec or {})
        self.initial_cost = float(self.spec.get('initial_cost', 10.0))
        self.fpc = int(self.spec.get('frames_per_cost', FRAMES_PER_COST))
        self.primed = bool(self.spec.get('primed', False))   # 是否含预备阶段（暂停不计时）
        self.net_spent = 0.0
        self.stall_tol = int(self.spec.get('stall_tolerance', 12))
        self._prev_sub = None
        self._same = 0
        self._last_frame = None
        self._wraps = 0
        self.stalled = False

    def note_spent(self, cost: float) -> None:
        """记账：我方消耗的费用（部署/撤退返还按净值传入）。"""
        self.net_spent += float(cost)

    def frame_from(self, cost: int, sub: int) -> int:
        return int(round(self.fpc * (cost - self.initial_cost + self.net_spent))) + int(sub)

    def read(self) -> FrameTick:
        cost = None
        try:
            cost = self.read_cost()
        except Exception:
            cost = None
        fr = None
        if self.grab is not None:
            try:
                fr = self.grab()
            except Exception:
                fr = None
        sub = None
        frac = None
        if fr is not None:
            img = getattr(fr, 'image', fr)
            roi = self.spec.get('bar_roi')
            if img is not None and roi:
                h, w = img.shape[:2]
                if len(roi) == 4 and all(isinstance(v, (int, float)) and v > 1.5 for v in roi):
                    x0, y0, x1, y1 = [int(v) for v in roi]
                else:
                    x0, y0, x1, y1 = int(roi[0] * w), int(roi[1] * h), int(roi[2] * w), int(roi[3] * h)
                ph = bar_phase(img[max(0, y0):y1, max(0, x0):x1],
                               thr_ratio=float(self.spec.get('thr_ratio', 0.55)),
                               full_px=self.spec.get('full_px'))
                if ph['ok']:
                    sub = ph['sub_frame']
                    frac = ph['frac']
        # 停住检测
        if sub is not None:
            if self._prev_sub is not None and sub == self._prev_sub:
                self._same += 1
            else:
                self._same = 0
            self._prev_sub = sub
            self.stalled = self._same >= self.stall_tol
        if cost is None:
            return FrameTick(ok=False, source=self.name, sub_frame=sub, stalled=self.stalled,
                             detail={'reason': 'no_cost'})
        if sub is None:
            # 只有整数格：给 30 帧粒度的下界，置信度低
            f = self.frame_from(cost, 0)
            return FrameTick(ok=True, frame=f, confidence=0.35, source=self.name, sub_frame=None,
                             stalled=self.stalled, detail={'cost': cost, 'coarse': True})
        f = self.frame_from(cost, sub)
        if self._last_frame is not None and f < self._last_frame:
            f = self._last_frame          # 单调性保护（消耗/回绕抖动）
        self._last_frame = f
        conf = 0.9 if not self.stalled else 0.5
        return FrameTick(ok=True, frame=f, confidence=conf, source=self.name, sub_frame=sub,
                         stalled=self.stalled,
                         detail={'cost': cost, 'frac': round(frac or 0.0, 4)})


# --------------------------------------------------------------------------------------
# 源 2：待部署时间十分位（方法 2）
# --------------------------------------------------------------------------------------
class RedeployTenthsClock:
    """三名「计时器干员」的待部署时间十分位：每 3 帧推进 0.1s，错开后每帧至少一个跳。

    spec:
      read_digits() -> list[int|None]   # 三名干员的十分位（None = 读不到）
      n_operators  期望的计时器干员数（默认 3）
      anchor_frame 锚点帧（默认 0 = 开局暂停那一刻）
    规则：本帧与上一帧相比，**任意一位发生变化**即认为走了一帧（多数表决可选）。
    """

    name = 'redeploy_tenths'

    def __init__(self, read_digits, spec: dict | None = None):
        self.read_digits = read_digits
        self.spec = dict(spec or {})
        self.n = int(self.spec.get('n_operators', 3))
        self.anchor_frame = int(self.spec.get('anchor_frame', 0))
        self.frames = 0
        self._prev = None
        self._miss = 0
        self.history: list[tuple[int, tuple]] = []

    @staticmethod
    def _expected_advance(prev: int, cur: int) -> int:
        """单个十分位：0..9 循环，(cur - prev) mod 10 是推进的 0.1s 数（0..9）。"""
        return (cur - prev) % 10

    def read(self, elapsed_wall: float | None = None) -> FrameTick:
        try:
            digits = list(self.read_digits())
        except Exception:
            digits = []
        digits = (digits + [None] * self.n)[:self.n]
        if all(d is None for d in digits):
            self._miss += 1
            return FrameTick(ok=False, source=self.name, frame=self.anchor_frame + self.frames,
                             detail={'reason': 'no_digits', 'miss': self._miss})
        if self._prev is not None:
            changed = [i for i in range(self.n)
                       if digits[i] is not None and self._prev[i] is not None
                       and digits[i] != self._prev[i]]
            if changed:
                # 每 3 帧一位推进 0.1 ⇒ 若一位跳了 k 步，视作 k 帧（时间片对齐由调用方兜底）
                step = max(self._expected_advance(self._prev[i], digits[i]) for i in changed)
                self.frames += max(1, min(step, 3))
                self.history.append((self.frames, tuple(digits)))
        self._prev = tuple(digits)
        conf = 0.95 if len([d for d in digits if d is not None]) >= 2 else 0.6
        return FrameTick(ok=True, frame=self.anchor_frame + self.frames, confidence=conf,
                         source=self.name,
                         detail={'digits': digits, 'n_read': len([d for d in digits if d is not None])})


# --------------------------------------------------------------------------------------
# 源 3：墙钟 × 倍速 − 暂停（外部计时辅助）
# --------------------------------------------------------------------------------------
class WallRateClock:
    """墙钟 + HUD 倍速（1X/2X）+ 暂停状态 ⇒ 逻辑帧（外部计时辅助，最省识别）。"""

    name = 'wall_rate'

    def __init__(self, read_speed, read_paused, spec: dict | None = None,
                 now=time.perf_counter):
        self.read_speed = read_speed        # () -> 1 or 2
        self.read_paused = read_paused      # () -> bool
        self.spec = dict(spec or {})
        self.now = now
        self.frames = 0.0
        self._t = None

    def read(self) -> FrameTick:
        t = self.now()
        if self._t is None:
            self._t = t
        dt = t - self._t
        self._t = t
        try:
            paused = bool(self.read_paused())
        except Exception:
            paused = False
        try:
            speed = float(self.read_speed())
        except Exception:
            speed = 1.0
        if not paused and dt > 0:
            self.frames += dt * FPS * max(1.0, speed)
        return FrameTick(ok=True, frame=int(self.frames), confidence=0.5 if paused else 0.7,
                         source=self.name,
                         detail={'paused': paused, 'speed': speed, 'raw': round(self.frames, 2)})


# --------------------------------------------------------------------------------------
# 融合
# --------------------------------------------------------------------------------------
class FrameClock:
    """按优先级融合多个帧级时钟；强制单调；输出残差用于自检。"""

    def __init__(self, sources: list, priority: list[str] | None = None,
                 max_jump: int = 90):
        self.sources = {s.name: s for s in sources}
        self.order = priority or [s.name for s in sources]
        self.max_jump = int(max_jump)
        self.frame = 0
        self.last: FrameTick | None = None
        self.residual: dict[str, float] = {}
        self.anomalies: list[dict] = []

    def note_spent(self, cost: float) -> None:
        for s in self.sources.values():
            if hasattr(s, 'note_spent'):
                s.note_spent(cost)

    def tick(self) -> FrameTick:
        ticks = {}
        for name in self.order:
            s = self.sources.get(name)
            if s is None:
                continue
            try:
                ticks[name] = s.read()
            except Exception as e:                       # 单个源坏掉不影响整体
                ticks[name] = FrameTick(ok=False, source=name, detail={'error': str(e)[:80]})
        chosen = None
        for name in self.order:
            t = ticks.get(name)
            if t is not None and t.ok:
                chosen = t
                break
        if chosen is None:
            self.last = FrameTick(ok=False, source='none')
            return self.last
        # 单调 + 跳变保护
        f = max(self.frame, int(chosen.frame))
        if f - self.frame > self.max_jump:
            self.anomalies.append({'kind': 'jump', 'from': self.frame, 'to': f,
                                   'source': chosen.source})
        self.frame = f
        chosen.frame = f
        self.residual = {n: float(self.frame - int(t.frame))
                         for n, t in ticks.items() if t.ok and n != chosen.source}
        self.last = chosen
        return chosen


# --------------------------------------------------------------------------------------
# 合成：十分位序列（用于方法 2 的帧级回归）
# --------------------------------------------------------------------------------------
def synth_tenths(frames: int, offsets=(0, 1, 2), dtype_frames: int = 3):
    """生成 n 名计时器干员在 frames 帧内的十分位序列。

    每位每 `dtype_frames` 帧推进 0.1s（默认 3 帧 = 0.1s @30fps），
    各自相位由 offsets 错开 ⇒ 任意一帧至少有一位在跳。
    """
    out = []
    for f in range(frames):
        row = tuple(((f + off) // dtype_frames) % 10 for off in offsets)
        out.append(row)
    return out
