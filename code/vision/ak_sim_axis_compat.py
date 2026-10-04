# -*- coding: utf-8 -*-
"""ak_sim_axis_compat.py — 轴表坐标变换（与 sim/draft/ak_sim/axis.py 保持同一实现）

放在 vision 侧，使打图执行器不依赖 sim 包路径即可解析同一种轴表坐标。
"""
from __future__ import annotations

COORD_TRANSFORMS = {
    'rc_normal':   dict(row_from='letter', row_flip=False, col_from='number', col_flip=False),
    'rc_rowflip':  dict(row_from='letter', row_flip=True,  col_from='number', col_flip=False),
    'rc_colflip':  dict(row_from='letter', row_flip=False, col_from='number', col_flip=True),
    'rc_bothflip': dict(row_from='letter', row_flip=True,  col_from='number', col_flip=True),
    'cr_normal':   dict(row_from='number', row_flip=False, col_from='letter', col_flip=False),
    'cr_rowflip':  dict(row_from='number', row_flip=True,  col_from='letter', col_flip=False),
    'cr_colflip':  dict(row_from='number', row_flip=False, col_from='letter', col_flip=True),
    'cr_bothflip': dict(row_from='number', row_flip=True,  col_from='letter', col_flip=True),
}


def coord_to_rc(coord: str, rows: int, cols: int, transform: str = 'rc_rowflip') -> tuple[int, int]:
    coord = coord.strip().upper()
    letters = ''.join(ch for ch in coord if ch.isalpha())
    digits = ''.join(ch for ch in coord if ch.isdigit())
    if not letters or not digits:
        raise ValueError(f'bad coord: {coord}')
    li = 0
    for ch in letters:
        li = li * 26 + (ord(ch) - ord('A') + 1)
    li -= 1
    ni = int(digits) - 1
    t = COORD_TRANSFORMS.get(transform, COORD_TRANSFORMS['rc_rowflip'])
    r = li if t['row_from'] == 'letter' else ni
    c = ni if t['col_from'] == 'number' else li
    if t['row_flip']:
        r = (rows - 1) - r
    if t['col_flip']:
        c = (cols - 1) - c
    return r, c


# --------------------------------------------------------------------------------------
# 技能 SP 数据（供执行端做「技能必须 SP 足够」的门控，与模拟器同判据）
# --------------------------------------------------------------------------------------
_SKILL_CACHE: dict | None = None
DATA_DIR = r'C:\Users\23922\Documents\ds_harness\ak\data\gamedata_akgd'


def _load_skill_tables():
    global _SKILL_CACHE
    if _SKILL_CACHE is not None:
        return _SKILL_CACHE
    import json
    import os
    ct = {}
    st = {}
    try:
        with open(os.path.join(DATA_DIR, 'character_table.json'), encoding='utf-8') as f:
            ct = json.load(f)
        with open(os.path.join(DATA_DIR, 'skill_table.json'), encoding='utf-8') as f:
            st = json.load(f)
    except Exception:
        ct, st = {}, {}
    _SKILL_CACHE = {'ct': ct, 'st': st}
    return _SKILL_CACHE


def find_char_id(name_or_id: str) -> str | None:
    """干员名（含“弦惊”这类召唤物）→ charId。"""
    t = _load_skill_tables()['ct']
    if name_or_id in t:
        return name_or_id
    for cid, v in t.items():
        if (v.get('name') or '').strip().strip('“”"') == name_or_id.strip().strip('“”"'):
            return cid
    return None


def skill_sp_profile(name_or_id: str, skill_index: int = 0) -> dict:
    """技能充能参数：{init, cost, type, inc, name, bat}（与模拟器同一套表值）。"""
    t = _load_skill_tables()
    cid = find_char_id(name_or_id)
    if not cid:
        return {}
    c = t['ct'][cid]
    skills = c.get('skills') or []
    if not skills:
        return {}
    sk = skills[min(max(0, skill_index), len(skills) - 1)]
    sd = t['st'].get(sk.get('skillId')) or {}
    lv = (sd.get('levels') or [{}])[-1]
    spd = lv.get('spData') or {}
    ph = (c.get('phases') or [{}])[-1]
    frames = ph.get('attributesKeyFrames') or [{}]
    bat = 1.0
    if frames:
        bat = float((frames[-1].get('data') or {}).get('baseAttackTime') or 1.0)
    bb = {}
    for b in (lv.get('blackboard') or []):
        v = b.get('valueStr')
        bb[b['key']] = v if v is not None else b.get('value')
    return {'char_id': cid, 'init': float(spd.get('initSp') or 0.0),
            'cost': float(spd.get('spCost') or 0.0), 'type': spd.get('spType'),
            'inc': float(spd.get('increment') or 1.0),
            'duration': float(lv.get('duration') or 0.0),
            'name': lv.get('name'), 'blackboard': bb, 'bat': bat,
            'desc': lv.get('description') or ''}


def sp_after(elapsed_s: float, profile: dict) -> float:
    """按表值推算从技能上一次结束/部署起经过 elapsed_s 后的 SP（不超过 spCost）。"""
    if not profile:
        return 0.0
    t = profile.get('type')
    inc = profile.get('inc', 1.0)
    if t == 'INCREASE_WITH_TIME':
        return min(profile['cost'], profile['init'] + inc * elapsed_s)
    if t == 'INCREASE_WHEN_ATTACK':
        # 攻击回复：按基础攻击间隔折算
        return min(profile['cost'], profile['init'] + inc * elapsed_s / max(0.1, profile.get('bat', 1.0)))
    return profile.get('init', 0.0)
