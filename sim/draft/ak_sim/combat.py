# -*- coding: utf-8 -*-
"""
combat.py — 伤害结算（复刻 knowledge/24 §5、knowledge/01）

公式（T1 解包验证）：
  物理: max(0.05*atk, atk*scale - max(0, def - def_penetrate))
  法术: max(0.05*atk, 0.01*atk*scale*max(0, 100 - (res - res_penetrate)))
  真实: atk*scale
  元素: max(0.05*atk, 0.01*atk*scale*max(0, 100 - ep_damage_res))
注意：游戏内 0.01 实为 0.00999999978（定点数），此处以 FP 运算保留该效应（TODO 逐位核对）。
"""
from __future__ import annotations

from . import fp

PHYSICAL = 'PHYSIC'
MAGICAL = 'MAGICAL'
PURE = 'PURE'
ELEMENTAL = 'ELEMENTAL'
PHYSIC = PHYSICAL   # 兼容别名

MIN_RATIO = 0.05
MAGIC_FACTOR = 0.01     # 定点近似 0.00999999978


def calc_damage(atk_fp: int, atk_scale_fp: int, dmg_type: str, target_def: int = 0,
                target_res: float = 0.0, def_penetrate: int = 0, res_penetrate: float = 0.0,
                dmg_scale: float = 1.0, ep_damage_res: float = 0.0) -> int:
    """返回伤害（FP）。"""
    raw = fp.mul(atk_fp, atk_scale_fp)            # atk * scale
    floor_dmg = fp.mul(atk_fp, fp.from_float(MIN_RATIO))
    if dmg_type == PURE:
        dmg = raw
    elif dmg_type == PHYSICAL:
        eff_def = max(0, target_def - def_penetrate)
        dmg = raw - fp.from_int(eff_def)
        if dmg < floor_dmg:
            dmg = floor_dmg
    elif dmg_type == MAGICAL:
        eff_res = max(0.0, target_res - res_penetrate)
        factor = fp.mul(raw, fp.from_float(MAGIC_FACTOR * max(0.0, 100.0 - eff_res)))
        dmg = factor if factor > floor_dmg else floor_dmg
    elif dmg_type == ELEMENTAL:
        factor = fp.mul(raw, fp.from_float(MAGIC_FACTOR * max(0.0, 100.0 - ep_damage_res)))
        dmg = factor if factor > floor_dmg else floor_dmg
    else:
        raise ValueError(f'unknown damage type {dmg_type}')
    if dmg_scale != 1.0:
        dmg = fp.mul(dmg, fp.from_float(dmg_scale))
    return dmg


def apply_damage(target, dmg_fp: int) -> int:
    """扣血（HP 为 int：伤害 FP → int 取整后扣除）。返回实际扣血。"""
    d = fp.to_int(dmg_fp)
    if d <= 0:
        return 0
    target.hp -= d
    if target.hp <= 0:
        target.hp = 0
        target.dead = True
    return d


def heal(target, amount_fp: int) -> int:
    h = fp.to_int(amount_fp)
    if h <= 0:
        return 0
    before = target.hp
    target.hp = min(target.max_hp, target.hp + h)
    return target.hp - before
