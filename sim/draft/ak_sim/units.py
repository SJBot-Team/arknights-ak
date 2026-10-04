# -*- coding: utf-8 -*-
"""
units.py — 单位模型（干员/敌人/召唤物/装置）

数值约定：位置/时间用 FP(Q32.32)；HP 用 int（游戏内 HP 为 int）；伤害结算后取整规则见 combat。
对应知识：24（伪代码）、02（机制）、33（cpp 字段）
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from . import fp

DEFAULT_ATTACK_PRE_DELAY_FRAMES = 0   # 前摇（🟡 实际在 prefab ability，未逐干员取得）


@dataclass
class Unit:
    uid: int
    side: str                       # ALLY / ENEMY
    key: str
    name: str
    pos: tuple[int, int]            # 世界坐标 (x, y) FP
    hp: int
    max_hp: int
    atk: int
    df: int
    res: float
    block_cnt: int = 0
    base_attack_time: int = fp.from_float(1.0)   # FP 秒
    attack_speed: float = 100.0                  # 百分比
    move_speed: int = fp.from_float(1.0)         # FP 格/秒
    flying: bool = False
    weight: int = 0
    is_operator: bool = False
    is_token: bool = False
    range_id: str = '1-1'
    range_grids: list[list[int]] = field(default_factory=list)
    attack_interval_frames: int = 30
    attack_cd_frames: int = 0
    state: str = 'MOVE'             # MOVE / ATTACK / BLOCKED / STUNNED / DEAD ...
    blocked_by: list[int] = field(default_factory=list)     # 阻挡本单位的干员 uid
    blocking: list[int] = field(default_factory=list)       # 本单位阻挡的敌人 uid
    deploy_time_frame: int = 0      # 部署帧（仇恨参考）
    created_frame: int = 0
    dead: bool = False
    escaped: bool = False
    # 敌人专用
    route_index: int | None = None
    navmap: dict | None = None
    next_node: tuple[int, int] | None = None
    inertia: tuple[int, int] = (0, 0)      # 惯性速度 FP
    cached_avoid: tuple[int, int] = (0, 0)
    checkpoint_idx: int = 0
    checkpoints: list[dict] = field(default_factory=list)
    route_end: tuple[int, int] | None = None
    life_point_reduce: int = 1
    hidden: bool = False                  # DISAPPEAR 检查点后：离场（不移动/不被攻击），等 APPEAR_AT_POS
    wait_until: int | None = None         # WAIT_FOR_SECONDS 检查点：停留到该帧
    # 干员专用
    cost: int = 0
    respawn_time: int = 70
    skill: dict | None = None
    skill_charge: int = 0                 # SP（整数显示值，兼容旧切片字段）
    skill_active_until: int | None = None
    # ---- 技能 / 增益状态（2026-09-14 新增） ----
    sp: float = 0.0                       # 当前 SP（可为小数：INCREASE_WITH_TIME 每帧累加 increment/30）
    sp_cost: float = 0.0                  # 技能消耗 SP（M3 值）
    sp_type: str | None = None            # INCREASE_WITH_TIME / INCREASE_WHEN_ATTACK / INCREASE_WHEN_TAKEN
    sp_increment: float = 1.0
    skill_active: bool = False
    skill_until: int | None = None        # 技能结束帧（duration<0 时为 None）
    skill_ammo: int | None = None         # 弹药型技能剩余弹药（打完即结束）
    skill_id: str | None = None
    skill_type: str | None = None         # AUTO / MANUAL / PASSIVE（AUTO ⇒ SP 满自动发动）
    skill_cost_gain: float = 0.0          # 技能发动时回复的**费用**（如芬「冲锋号令·α型」+6）
    # ---- ★★「体积」两个语义必须分开（用户 2026-09-15 明确） ----
    #   ① `collider_radius`：**碰撞体积** —— 只用于**阻挡判定 / 位移 / 寻路**；
    #   ② `hit_radius`     ：**受击判定体积** —— 只用于**索敌**（能否被选为目标）；
    #   ★二者语义不同、数值也不必相同：碰撞体积来自客户端 prefab 的 CircleCollider2D，
    #     受击判定体积由标定反推（1-1：0.5）。**不要把碰撞体积拿去索敌。**
    collider_radius: float = 0.25
    hit_radius: float = 0.25
    # 受击判定体积的**中心偏移**（相对单位"位置"锚点）。
    #   ★为什么需要：客户端 prefab 实测敌人的碰撞体并非"以位置为心的圆"——
    #   例如 `CapsuleCollider2D m_Size=(0.2,0.4) m_Offset=(0.0,-0.1)`（见 collider_report.json）
    #   ⇒ 判定体有**方向相关**的触及范围。当前默认 (0,0)，逐单位真实值待从 prefab 抽取后填入。
    hit_offset: tuple[float, float] = (0.0, 0.0)
    # ---- ★移动惯性（用户 2026-09-15；见 engine._enemy_move docstring）----
    #   `inertia` = **当前速度向量**（Q32.32，格/秒）；敌人**出生时为 (0,0)**。
    #   每帧：`v ← v + (v_desired − v)·steeringFactor·dt`，其中 steeringFactor 地面 8 / 飞行 20
    #   （等价每帧 ×4/15）；加速度模长上限 `max_steering_force`（0 = 用默认 10/100）。
    max_steering_force: float = 0.0
    buffs: list = field(default_factory=list)   # [{src, atk, def, attack_speed, until}]
    summon_charges: int = 0               # 可部署召唤物次数（召唤类技能发放）
    talents: list = field(default_factory=list)   # 天赋原始数据（character_table）
    extra: dict[str, Any] = field(default_factory=dict)

    def talent_bb(self, key: str):
        """取天赋黑板上某键的值（取最后一个已解锁候选，即满配值）。"""
        found = None
        for t in self.talents or []:
            for cand in (t.get('candidates') or []):
                for b in (cand.get('blackboard') or []):
                    if b.get('key') == key:
                        v = b.get('valueStr')
                        found = v if v is not None else b.get('value')
        return found

    # ---------- 便捷属性 ----------
    @property
    def alive(self) -> bool:
        return not self.dead and not self.escaped

    def buff_sum(self, key: str) -> float:
        return sum(float(b.get(key) or 0.0) for b in self.buffs)

    def eff_atk(self) -> float:
        """有效攻击力（含技能/增益的乘算加成）。"""
        return self.atk * (1.0 + self.buff_sum('atk'))

    def eff_def(self) -> float:
        return self.df * (1.0 + self.buff_sum('def'))

    def eff_attack_speed(self) -> float:
        return self.attack_speed + self.buff_sum('attack_speed')

    def purge_expired_buffs(self, frame: int) -> None:
        self.buffs = [b for b in self.buffs if b.get('until') is None or frame < b['until']]

    def world_xy(self) -> tuple[float, float]:
        return fp.to_float(self.pos[0]), fp.to_float(self.pos[1])

    def grid(self) -> tuple[int, int]:
        return (int(fp.to_float(self.pos[1])), int(fp.to_float(self.pos[0])))

    def tile_center(self) -> tuple[int, int]:
        r, c = self.grid()
        return fp.from_float(c + 0.5), fp.from_float(r + 0.5)

    def dist_to(self, other: 'Unit') -> float:
        import math
        return math.hypot(fp.to_float(self.pos[0] - other.pos[0]),
                          fp.to_float(self.pos[1] - other.pos[1]))

    def recompute_attack_interval(self):
        """攻击间隔：**本体口径**（`BattleFormula.CalculateAttackInterval` 0x3584F10）。

        ★2026-09-29（T-200c）改为走 `timeline.frames_for()` —— **唯一换算点**：
          1. 公式 = `BAT / (clamp(攻速, 10, 600) / 100)`（FP 定点，**公式层无取整**）；
          2. 帧数口径由 `timeline.TIME_MODE` 决定（默认 `native` = FP 累加跨阈值），
             可用环境变量 `AK_SIM_TIME_MODE=legacy` 回到旧的浮点 `ceil` 口径做对拍。
        旧实现（保留对照）：`ceil(BAT*100/攻速*30 − 1e-9)`，且**未应用攻速 10/600 夹取**。
        """
        from ak_sim import timeline
        self.attack_interval_fp = timeline.attack_interval_fp(
            self.base_attack_time, self.eff_attack_speed())
        self.attack_interval_frames = timeline.frames_for(
            self.base_attack_time, self.eff_attack_speed())


import math  # noqa: E402  (放此处避免与 dataclass 默认值求值顺序冲突)


def make_operator(uid: int, spec: dict, pos_fp: tuple[int, int], deploy_frame: int,
                  range_grids: list[list[int]], flying: bool = False) -> Unit:
    a = spec['attrs']
    u = Unit(
        uid=uid, side='ALLY', key=spec['charId'], name=spec['name'], pos=pos_fp,
        hp=int(a['maxHp']), max_hp=int(a['maxHp']), atk=int(a['atk']), df=int(a['def']),
        res=float(a['magicResistance']), block_cnt=int(a['blockCnt']),
        base_attack_time=fp.from_float(float(a['baseAttackTime'])),
        attack_speed=float(a['attackSpeed'] or 100.0),
        move_speed=fp.from_float(float(a['moveSpeed'] or 1.0)),
        flying=flying, is_operator=True,
        is_token=(spec.get('profession') == 'TOKEN'),
        range_id=spec.get('rangeId') or '1-1', range_grids=range_grids,
        deploy_time_frame=deploy_frame, created_frame=deploy_frame,
        cost=int(a['cost']), respawn_time=int(a['respawnTime'] or 70),
        skill=spec.get('skill'), talents=spec.get('talents') or [],
    )
    # ---- 技能初始状态（表驱动：spData.initSp / spCost / spType / increment）----
    sk = spec.get('skill') or {}
    spd = sk.get('spData') or {}
    u.skill_id = sk.get('skillId')
    u.skill_type = sk.get('skillType')          # AUTO / MANUAL / PASSIVE …
    u.skill_cost_gain = float((sk.get('blackboard') or {}).get('cost') or 0.0)
    # ★体积：干员碰撞体实测 0.25（458 个全部一致）；受击判定体积干员取 0.25。
    #   ★碰撞体积只用于阻挡/位移；受击判定体积只用于索敌（见 engine 头部对照表）。
    u.collider_radius = float(spec.get('colliderRadius') or 0.25)
    u.hit_radius = float(spec.get('hitRadius') or 0.25)
    u.sp = float(spd.get('initSp') or 0.0)
    u.sp_cost = float(spd.get('spCost') or 0.0)
    u.sp_type = spd.get('spType')
    u.sp_increment = float(spd.get('increment') or 1.0)
    u.skill_charge = int(u.sp)
    u.recompute_attack_interval()
    return u


def make_enemy(uid: int, edata: dict, pos_fp: tuple[int, int], route, frame: int) -> Unit:
    """构造敌人。

    ★注意 `edata` 里的体积字段来自**关卡/敌人表的数据层**，与干员 prefab 的碰撞体**不同源**；
    敌人逐个体的真实碰撞半径需要读客户端 prefab（`collider_report.json`），
    当前先用默认值（碰撞 0.1 / 受击 0.5），并按需要逐单位覆盖。
    """
    u = Unit(
        uid=uid, side='ENEMY', key=edata['id'], name=edata['name'], pos=pos_fp,
        hp=int(edata['maxHp']), max_hp=int(edata['maxHp']), atk=int(edata['atk']),
        df=int(edata['def']), res=float(edata['magicResistance']),
        block_cnt=0,
        base_attack_time=fp.from_float(float(edata.get('baseAttackTime') or 1.0)),
        attack_speed=float(edata.get('attackSpeed') or 100.0),
        move_speed=fp.from_float(float(edata.get('moveSpeed') or 1.0)),
        flying=str(edata.get('motion', 'WALK')).upper().startswith('FLY'),
        weight=int(edata.get('weight') or 0),
        created_frame=frame, state='MOVE',
        route_index=getattr(route, 'index', None),
        route_end=getattr(route, 'end', None),
        checkpoints=getattr(route, 'checkpoints', []),
        life_point_reduce=int(edata.get('lifePointReduce') or 1),
        # ★体积：①碰撞体积（阻挡/位移用）②受击判定体积（索敌用）—— 两者分开，勿混用。
        #   敌人实测半径分布 0.1/0.5/1.0/1.5/2.0/2.5/3.0（见 collider_report.json）；
        #   受击判定体积默认 0.5（由 1-1 标定反推）。
        collider_radius=float(edata.get('colliderRadius') or 0.1),
        hit_radius=float(edata.get('hitRadius') or 0.5),
        extra={'applyWay': edata.get('applyWay'), 'rangeRadius': edata.get('rangeRadius', 0.0),
               'is_civilian': bool(edata.get('_is_civilian')),
               'civilian_max_cost': 2.0},
    )
    u.recompute_attack_interval()
    return u
