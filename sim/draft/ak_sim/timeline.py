# -*- coding: utf-8 -*-
"""timeline.py — **时间层：本体口径的唯一真源**（T-200c，2026-09-29）

## 为什么需要这个模块
`ak_sim` 各处的"帧化"此前是**分散的、浮点取整的**：
  · `units.Unit.recompute_attack_interval()` 用 `ceil(BAT*100/aspd*30 - 1e-9)`
  · `engine._windup_frames()` 用 `round(interval_frames * 比例)`
  · 波次用 `round(t*FPS)`
但本体（`knowledge/04/68`，T-079 指令级核验）**不是这样**的：

| 本体事实 | 出处（类.方法 + RVA） |
|---|---|
| 攻击间隔 = `baseAttackTime / (clamp(攻速,10,600)/100)`，**全函数零取整指令** | `BattleFormula.CalculateAttackInterval` **0x3584F10** |
| 时间量是 **FP 定点（Q32.32）**，逐帧**累加**推进 | `FP.FastAdd`；`BattleController.s_fixedFrameCnt //0x14`（`get_fixedFrameCnt` **0x3563340**） |
| 定步长 1/30 s | `Time.fixedDeltaTime = 0.03333330154418945` |
| 出手时刻由**动画事件帧**决定（`ON_ATTACK_CHECK_POINT = 7`） | `AbilityStandard.Event`(TypeDefIndex 8426)、`AbilityStandard.OnEvent` **0x34F26A0** |
| 前摇 = `_preDelay //0x180`(float 秒) → `m_preDelay //0x1A0`(FP)，是**等事件帧的窗口** | `AbstractAnimatedAbility`；`get_preDelay` **0xA6E9F0** |

⇒ **"多少帧"不是算出来的，是"FP 累加到 ≥ 该时间量"自然产生的**（帧量化表现为"跨过阈值的那一帧"）。

## 本模块提供三件事
1. `FixedClock`：复刻 `s_fixedFrameCnt` + FP 累加的时间轴；
2. `attack_interval_fp()`：**逐字复刻** `CalculateAttackInterval`（含 Clamp 上下限常量）；
3. `AttackCycle`：前摇/冷却的**累加式**状态机（默认本体口径），并保留**旧浮点口径**作对照开关，
   便于量化"旧算法与本体口径差在哪"。

## 已知缺口（见 `knowledge/04/69`、`04/70`）
- `_preDelay` 的**真值**来自 prefab 序列化字段，本地 JSON 表**没有**（`character_table.json` 里
  只有 1 处 `"key": "predelay"` 的黑板键，非干员字段）⇒ 目前只能"比例反推"兜底（🟡，标 `fallback`）。
- "FP 秒 → 帧"的**官方取整点**仍待 T-200a 定论 ⇒ 本模块把两种口径都实现并可切换。
"""
from __future__ import annotations

from dataclasses import dataclass, field

from ak_sim import fp

# ---------------- 常量（本体） ----------------
FIXED_DELTA_TIME_F32 = 0.03333330154418945      # Unity TimeManager 实读
FPS = 30                                         # = 1 / FIXED_DELTA_TIME 的整数语义
FRAME_TIME_FP = fp.from_float(FIXED_DELTA_TIME_F32)   # 一帧的 FP 时长

MIN_ATTACK_SPEED = 10                            # BattleFormula..cctor 静态 +0x10
MAX_ATTACK_SPEED = 600                           #  同上 +0x8
ATTACK_SPEED_DIVIDER = 100                       #  同上 +0x18

_DIVIDER_FP = fp.from_float(float(ATTACK_SPEED_DIVIDER))
_MIN_SPEED_FP = fp.from_float(float(MIN_ATTACK_SPEED))
_MAX_SPEED_FP = fp.from_float(float(MAX_ATTACK_SPEED))


# ---------------- 1. 固定步长时钟 ----------------
@dataclass
class FixedClock:
    """复刻 `BattleController.s_fixedFrameCnt`（uint）+ FP 时间累加。

    本体每帧：`s_fixedFrameCnt++`，时间量由 `FP.FastAdd` 累加
    （见 `knowledge/04/35` §tick 与 `04/68 §1`）。
    """
    frame: int = 0
    time_fp: int = 0

    def tick(self) -> int:
        self.frame += 1
        self.time_fp = fp.add(self.time_fp, FRAME_TIME_FP)
        return self.frame

    @property
    def seconds(self) -> float:
        return fp.to_float(self.time_fp)


# ---------------- 2. 攻击间隔（本体公式） ----------------
def attack_interval_fp(base_attack_time_fp: int, attack_speed: float) -> int:
    """**逐字复刻** `BattleFormula.CalculateAttackInterval`（RVA 0x3584F10）。

    反汇编要点（T-079 全函数读完）：
        0x3584FD8  call 0x5502C30   → TSMath.Clamp(attackSpeed, static[0x10]=10, static[0x8]=600)
        0x3585010  call 0x54E4080   → FP.op_Division(clamped, static[0x18]=100)
        0x3585032  jmp  0x54E4080   → FP.op_Division(baseAttackTime, 上一步)
    **无任何取整/下限夹取指令**（保底属抗性结算环节，不在这里）。
    """
    s = float(attack_speed)
    if s < MIN_ATTACK_SPEED:
        s = float(MIN_ATTACK_SPEED)
    elif s > MAX_ATTACK_SPEED:
        s = float(MAX_ATTACK_SPEED)
    denom = fp.div(fp.from_float(s), _DIVIDER_FP)
    return fp.div(base_attack_time_fp, denom)


def interval_frames(interval_fp: int) -> int:
    """**本体口径**：需要多少帧才让 FP 累加跨过该时间量（= 跨阈值那一帧）。

    语义 = `最小 n 使 n*FRAME_TIME_FP ≥ interval_fp`。
    注意这是**累加产生的结果**，不是公式层的取整——与 `04/36 K-004` 的
    "公式向上取整"是两回事（后者已被 `04/68` 否定）。
    """
    return fp.fp_seconds_to_frames_ceil(interval_fp)


def interval_frames_legacy(base_attack_time_fp: int, attack_speed: float) -> int:
    """**旧口径**（`04/41` 首版）：float 上先乘除再 `ceil(秒*30 - 1e-9)`。

    保留用于对照：量化"旧算法与本体口径"的帧差（见 `__main__` 自检）。
    """
    eff = fp.to_float(base_attack_time_fp) * 100.0 / max(1e-6, float(attack_speed))
    return max(1, int(__import__('math').ceil(eff * FPS - 1e-9)))


import os as _os

# 时间口径开关（**唯一换算点** `frames_for()` 的行为）：
#   'frame_ceil'    = `ceil(float32(BAT) × 100/攻速 × 30)`  ← **1-1 标定实证的口径（默认）**
#   'fp_accumulate' = FP 逐帧累加、跨过阈值那一帧（"纯定点累加"假设，**已被 1-1 标定否证**：
#                     猎狗pro BAT=1.4 会算成 43 帧，实机是 42 帧 —— 见 t200_rounding_probe.py）
#   'floor' / 'round' = 对照
# 可用环境变量 `AK_SIM_TIME_MODE` 覆盖（A/B 对拍用）。
TIME_MODE = _os.environ.get('AK_SIM_TIME_MODE', 'frame_ceil').lower()

_ALIAS = {'legacy': 'frame_ceil', 'native': 'fp_accumulate'}


def frames_for(base_attack_time_fp: int, attack_speed: float, mode: str | None = None) -> int:
    """攻击间隔 → 帧数（**唯一换算点**，口径可切换）。

    | mode | 语义 | 1.05s | 1.4s | 证据 |
    |---|---|---|---|---|
    | `frame_ceil`（默认） | `ceil(float32(BAT) × 100/攻速 × 30)` | **32** ✓ | **42** ✓ | 1-1 标定：芬 32/32/32/32、猎狗pro …42 |
    | `fp_accumulate` | FP 逐帧累加跨阈值 | 32 ✓ | 43 ✗ | 被 1-1 标定否证（猎狗实机 42） |
    | `floor` / `round` | 对照 | 31 ✗ | 42 ✓ | 芬 不吻合（31≠32） |

    ⇒ **帧数 = 对"帧值化的间隔"向上取整**：公式层（`CalculateAttackInterval 0x3584F10`）确实
    **零取整**（04/68 实证），取整发生在**更下层的帧换算**，且用**单精度**参与 ⇒ `04/36 K-004`
    的"向上取整"在**换算层**成立（两层说法并不矛盾）。
    """
    m = _ALIAS.get((mode or TIME_MODE).lower(), (mode or TIME_MODE).lower())
    iv = attack_interval_fp(base_attack_time_fp, attack_speed)
    if m == 'frame_ceil':
        return interval_frames_legacy(base_attack_time_fp, attack_speed)
    if m == 'floor':
        return max(1, fp.fp_to_frames_floor(iv))
    if m == 'round':
        import math as _m
        return max(1, int(_m.floor(fp.to_float(iv) * FPS + 0.5)))
    return max(1, interval_frames(iv))          # fp_accumulate


# ---------------- 3. 攻击周期（前摇 + 冷却） ----------------@dataclass
class AttackCycle:
    """攻击周期状态机（**累加式**，本体口径）。

    本体形态（`knowledge/04/68 §2`、`67a §9`）：
      · 起手时把 `m_attackTime //0x1A8` 作为整段长度，`m_preDelay //0x1A0` 作为**等待窗口**；
      · 真正出手由**动画事件帧**触发（`ON_ATTACK_CHECK_POINT=7` 经 `OnEvent 0x34F26A0` 分发）；
      · 后摇无独立字段，是 `m_attackTime` 的剩余量（`GetDuration 0xA6D720`）。

    本模拟器不加载动画（`04/31 §3.2` 设计约束）⇒ 用 **前摇时长**代替"事件帧到达"：
      出手时刻 = 累加时间 ≥ `pre_delay_fp` 的那一帧；
      下一周期起点 = 累加时间 ≥ `interval_fp` 的那一帧。
    `pre_delay_fp` 的来源见 `windup_fp()`（真值缺 ⇒ 比例兜底，🟡）。
    """
    interval_fp: int
    pre_delay_fp: int = 0
    elapsed_fp: int = 0
    fired: bool = False
    armed: bool = False              # 是否处于攻击周期中（起手后为 True）
    source: str = 'unknown'          # 'prefab'(真值) / 'ratio'(兜底) / 'zero'

    @property
    def active(self) -> bool:
        return self.armed

    def start(self) -> None:
        """起手（对应 `AttackState._StartAttack 0x71B350` 之后的第一个 tick）。"""
        self.elapsed_fp = 0
        self.fired = False
        self.armed = True

    def tick(self) -> str:
        """推进一帧。返回：'' 空闲 / 'fire' 本帧出手 / 'cycle_end' 本周期结束。"""
        if not self.armed:
            return ''
        self.elapsed_fp = fp.add(self.elapsed_fp, FRAME_TIME_FP)
        if not self.fired and self.elapsed_fp >= self.pre_delay_fp:
            self.fired = True
            return 'fire'
        if self.elapsed_fp >= self.interval_fp:
            self.elapsed_fp = 0
            self.fired = False
            self.armed = False
            return 'cycle_end'
        return ''

    @property
    def windup_left_frames(self) -> int:
        if self.fired:
            return 0
        return max(0, fp.fp_seconds_to_frames_ceil(self.pre_delay_fp - self.elapsed_fp))

    @property
    def cooldown_left_frames(self) -> int:
        return max(0, fp.fp_seconds_to_frames_ceil(self.interval_fp - self.elapsed_fp))


# ---------------- 4. 前摇时长（真值缺失时的兜底链） ----------------
def windup_fp(unit, interval_fp_value: int) -> tuple[int, str]:
    """返回 `(前摇 FP, 来源标签)`。

    优先级（**真值优先**）：
      1. `unit.pre_delay_fp`（FP）或 `unit.pre_delay_sec`（float 秒）—— 来自本体 prefab 的真值；
      2. `unit._windup_ratio`（单点覆盖，标定用）；
      3. 职业比例表 `WINDUP_RATIO_BY_PROFESSION`（反推值，🟡）；
      4. 默认比例。

    ⚠️ 2~4 都是**反推/兜底**，不是本体数据：本体 `_preDelay` 是 prefab 序列化字段，
    本地 JSON 表没有（见模块头"已知缺口"）。调用方必须把来源标签记录下来。
    """
    v = getattr(unit, 'pre_delay_fp', None)
    if v:
        return int(v), 'prefab'
    sec = getattr(unit, 'pre_delay_sec', None)
    if sec:
        return fp.from_float(float(sec)), 'prefab'
    r = getattr(unit, '_windup_ratio', None)
    if r is None:
        prof = (getattr(unit, 'profession', None) or '').upper()
        table = getattr(unit, '_windup_table', None)
        if table is None:
            from ak_sim.engine import WINDUP_RATIO_BY_PROFESSION, \
                WINDUP_RATIO_DEFAULT_ALLY, WINDUP_RATIO_DEFAULT_ENEMY
            table = WINDUP_RATIO_BY_PROFESSION
            r = table.get(prof)
            if r is None:
                r = WINDUP_RATIO_DEFAULT_ALLY if getattr(unit, 'is_operator', False) \
                    else WINDUP_RATIO_DEFAULT_ENEMY
                return fp.mul(interval_fp_value, fp.from_float(float(r))), 'ratio_default'
        else:
            r = table.get((getattr(unit, 'profession', None) or '').upper(), 0.5)
    return fp.mul(interval_fp_value, fp.from_float(float(r))), 'ratio'


# ---------------- 自检 ----------------
if __name__ == '__main__':
    print('=== timeline 自检（本体口径 vs 旧口径）===')
    print(f'FRAME_TIME_FP = {FRAME_TIME_FP} (= {fp.to_float(FRAME_TIME_FP)!r} s)')
    c = FixedClock()
    for _ in range(30):
        c.tick()
    print(f'30 帧后 time_fp = {c.time_fp} ⇒ {c.seconds:.9f}s（应≈1.0）')

    # 攻击间隔：本体公式 vs 旧浮点口径
    print('\n干员(baseAttackTime, attackSpeed) → 本体FP秒 / 本体帧 / 旧口径帧')
    cases = [('芬', 1.05, 100.0), ('月见夜', 1.3, 100.0), ('夜刀', 0.93, 100.0),
             ('能天使', 1.0, 100.0), ('高攻速', 1.0, 160.0), ('低攻速', 1.0, 60.0),
             ('边界600', 1.0, 700.0), ('边界10', 1.0, 5.0)]
    bad = []
    for name, bat, aspd in cases:
        iv = attack_interval_fp(fp.from_float(bat), aspd)
        n_new = interval_frames(iv)
        n_old = interval_frames_legacy(fp.from_float(bat), aspd)
        mark = '' if n_new == n_old else '  ★口径差异'
        if n_new != n_old:
            bad.append((name, n_new, n_old))
        print(f'  {name:<6} BAT={bat:<5} 攻速={aspd:<6} → {fp.to_float(iv):.9f}s  '
              f'本体={n_new:>3} 帧  旧={n_old:>3} 帧{mark}')
    print(f'\n口径差异 {len(bad)} 例：{bad if bad else "无"}')

    # 周期状态机
    print('\n=== AttackCycle 自检（芬：间隔 1.05s、前摇比例 0.55）===')
    iv = attack_interval_fp(fp.from_float(1.05), 100.0)
    wu = fp.mul(iv, fp.from_float(0.55))
    cyc = AttackCycle(interval_fp=iv, pre_delay_fp=wu)
    cyc.start()
    for i in range(1, 40):
        ev = cyc.tick()
        if ev:
            print(f'  第 {i:>2} 帧（{i/30:.3f}s）: {ev}'
                  f'{"  ← 出手" if ev == "fire" else ""}')
