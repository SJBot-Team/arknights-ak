# -*- coding: utf-8 -*-
"""
data.py — 模拟器标准数据访问层（"按名称即用即取"）

数据根：
  TABLES : E:\\__file\\ak_kb\\gamedata\\latest     主仓 26-09-03 全量表（character/skill/battle_equip/enemy_database/range...）
  LEVELS : E:\\__file\\ak_kb\\gamedata\\levels     关卡 json（fetch_level.py 抓取）
  DERIVED: E:\\__file\\ak_kb\\gamedata\\derived    派生（碰撞/动画/模板）
  CLIENT : E:\\__file\\ak_kb\\client_res           客户端资源备份（prefab/anim 等）

对应知识：
  knowledge/04/31（数据链与缺口）、26/27（提取流程）、34（随机数）、02/24（机制）
"""
from __future__ import annotations

import json
import os
import functools
from typing import Any

TABLES = r'E:\__file\ak_kb\gamedata\latest'
LEVELS = r'E:\__file\ak_kb\gamedata\levels'
DERIVED = r'E:\__file\ak_kb\gamedata\derived'
CLIENT = r'E:\__file\ak_kb\client_res'
AKGD = r'E:\__file\ak_kb\gamedata'

# 属性键（与 character_table attributes 一致）
ATTR_KEYS = ['maxHp', 'atk', 'def', 'magicResistance', 'cost', 'blockCnt', 'moveSpeed',
             'attackSpeed', 'baseAttackTime', 'respawnTime', 'hpRecoveryPerSec',
             'spRecoveryPerSec', 'maxDeployCount', 'maxDeckStackCnt', 'tauntLevel',
             'massLevel', 'baseForceLevel', 'stunImmune', 'silenceImmune', 'sleepImmune',
             'frozenImmune', 'levitateImmune', 'disarmedCombatImmune', 'fearedImmune',
             'palsyImmune', 'attractImmune', 'teleportImmune', 'groundBoundImmune']


@functools.lru_cache(maxsize=64)
def load_table(name: str) -> Any:
    """加载最新表（带缓存）。name 可含子目录，如 'character_table.json'。"""
    path = os.path.join(TABLES, name)
    if not os.path.exists(path):
        # 回退到仓库根（旧表）
        path = os.path.join(AKGD, name)
    with open(path, encoding='utf-8') as f:
        return json.load(f)


@functools.lru_cache(maxsize=8)
def _enemy_db() -> dict:
    """敌人权威库（2130 形态组）：{enemyId: {level: enemyData}}"""
    path = os.path.join(AKGD, 'enemy_database_full.json')
    raw = json.load(open(path, encoding='utf-8'))
    out: dict[str, dict[int, dict]] = {}
    for item in raw['enemies']:
        key = item['Key']
        lvmap = {}
        for v in item['Value']:
            lvmap[v['level']] = v['enemyData']
        out[key] = lvmap
    return out


def _attr_value(d: dict, key: str, default=0):
    """enemyData 属性是 {m_defined, m_value} 包装。"""
    v = d.get(key)
    if isinstance(v, dict):
        return v.get('m_value', default) if v.get('m_defined') else default
    return v if v is not None else default


def get_enemy(enemy_id: str, level: int = 0, overwrite: dict | None = None) -> dict:
    """取敌人实例数据（基值 → 关卡等级 → overwrittenData）。"""
    db = _enemy_db()
    lvmap = db.get(enemy_id)
    if lvmap is None:
        raise KeyError(f'enemy not found: {enemy_id}')
    data = lvmap.get(level) or lvmap.get(0) or next(iter(lvmap.values()))
    attrs = data.get('attributes') or {}
    out = {
        'id': enemy_id,
        'name': _attr_value(data, 'name', enemy_id),
        'level': level,
        'maxHp': _attr_value(attrs, 'maxHp'),
        'atk': _attr_value(attrs, 'atk'),
        'def': _attr_value(attrs, 'def'),
        'magicResistance': _attr_value(attrs, 'magicResistance'),
        'cost': _attr_value(attrs, 'cost'),
        'blockCnt': _attr_value(attrs, 'blockCnt'),
        'moveSpeed': _attr_value(attrs, 'moveSpeed'),
        'attackSpeed': _attr_value(attrs, 'attackSpeed', 100.0),
        'baseAttackTime': _attr_value(attrs, 'baseAttackTime', 1.0),
        'weight': _attr_value(attrs, 'massLevel'),
        'baseForceLevel': _attr_value(attrs, 'baseForceLevel'),
        'lifePointReduce': _attr_value(data, 'lifePointReduce', 1),
        'applyWay': _attr_value(data, 'applyWay', 'MELEE'),
        'motion': _attr_value(data, 'motion', 'WALK'),
        'rangeRadius': _attr_value(data, 'rangeRadius', 0.0),
        'raw': data,
    }
    # 关卡覆盖
    if overwrite:
        out['overwrite'] = overwrite
    return out


def _interp_frames(frames: list[dict], level: int, key: str, default=0.0):
    """在 attributesKeyFrames（[{level, data}]）上按等级线性插值。"""
    if not frames:
        return default
    pts = sorted(frames, key=lambda f: f['level'])
    if level <= pts[0]['level']:
        return pts[0]['data'].get(key, default)
    if level >= pts[-1]['level']:
        return pts[-1]['data'].get(key, default)
    for a, b in zip(pts, pts[1:]):
        if a['level'] <= level <= b['level']:
            va, vb = a['data'].get(key, default), b['data'].get(key, default)
            t = (level - a['level']) / (b['level'] - a['level'])
            if isinstance(va, bool) or isinstance(vb, bool):
                return va
            return va + (vb - va) * t
    return pts[-1]['data'].get(key, default)


def get_range(range_id: str) -> list[list[int]]:
    """取攻击范围格点（相对坐标 [dx, dy] 列表）。"""
    try:
        rt = load_table('range_table.json')
    except Exception:
        return [[0, 0]]
    r = rt.get(range_id)
    if not r:
        return [[0, 0]]
    grids = r.get('grids') or []
    if grids and isinstance(grids[0], dict):
        return [[g.get('col', 0), g.get('row', 0)] for g in grids]
    return [[g[0], g[1]] for g in grids] if grids else [[0, 0]]


def get_operator(char_id: str, elite: int = 2, level: int = 90, potential: int = 6,
                 trust: int = 200, module: str | None = None, module_level: int = 3,
                 skill_index: int = 0, skill_level: int = 10) -> dict:
    """组装干员实例：基值(阶段插值) + 信赖 + 潜能 + 模组 + 技能黑板 + 天赋。"""
    ct = load_table('character_table.json')
    if char_id not in ct:
        raise KeyError(f'operator not found: {char_id}')
    c = ct[char_id]
    phases = c.get('phases') or []
    ph = phases[min(elite, len(phases) - 1)]
    frames = ph.get('attributesKeyFrames') or []
    attrs = {k: _interp_frames(frames, level, k, 0) for k in ATTR_KEYS}

    # 信赖
    fav = c.get('favorKeyFrames') or []
    if fav and trust > 0:
        for k in ('maxHp', 'atk', 'def', 'magicResistance', 'cost', 'blockCnt',
                  'moveSpeed', 'attackSpeed', 'baseAttackTime', 'respawnTime'):
            attrs[k] = attrs.get(k, 0) + _interp_frames(fav, trust, k, 0)

    # 潜能
    pots = c.get('potentialRanks') or []
    for i, pr in enumerate(pots[:max(0, potential)]):
        buff = (pr or {}).get('buff') or {}
        for m in ((buff.get('attributes') or {}).get('attributeModifiers') or []):
            key = m.get('attributeType')
            val = m.get('value', 0)
            fk = {'MAX_HP': 'maxHp', 'ATK': 'atk', 'DEF': 'def', 'COST': 'cost',
                  'BLOCK_CNT': 'blockCnt', 'ATTACK_SPEED': 'attackSpeed',
                  'MAGIC_RESISTANCE': 'magicResistance', 'RESPAWN_TIME': 'respawnTime'}.get(key)
            if not fk:
                continue
            if m.get('formulaItem') == 'MULTIPLIER':
                attrs[fk] = attrs.get(fk, 0) * (1 + val)
            else:
                attrs[fk] = attrs.get(fk, 0) + val

    # 模组（battle_equip_table: attributeBlackboard + 覆盖特性/天赋）
    mod_info = None
    if module:
        bet = load_table('battle_equip_table.json')
        me = bet.get(module)
        if me:
            idx = max(0, min(module_level, len(me.get('phases') or []) - 1))
            phd = (me.get('phases') or [])[idx]
            for bb in (phd.get('attributeBlackboard') or []):
                k = {'max_hp': 'maxHp', 'atk': 'atk', 'def': 'def',
                     'magicResistance': 'magicResistance', 'cost': 'cost'}.get(bb['key'])
                if k:
                    attrs[k] = attrs.get(k, 0) + bb.get('value', 0)
            mod_info = phd

    # ★天赋对**部署费用**的影响（2026-09-29，用户指出：「芬的费用不一致是由于天赋导致费用减1，
    #   干员天赋、关卡机制等均存在这类影响」）
    #   实证：`char_123_fang` 天赋「轻量化」= `{'cost': -1.0}`（描述"自身部署费用-1"），
    #   叠加潜能里的两次"部署费用-1"后 ⇒ **数据表 11 / 潜能 9 / 天赋再 −1 = 8**，
    #   正是 1-1 标定里"芬花费 8"的来源（此前模拟器给 9，长期记为"费用 −1 未解"残差）。
    #   ⚠️ 本层**只施加 `cost`**：其余属性（atk/def/max_hp 等）的天赋多为**百分比 + 条件触发**，
    #   在本层无条件相加会算错，须等"条件型天赋管线"（见 04/73 §6）。
    for _t in (c.get('talents') or []):
        for _cand in (_t.get('candidates') or []):
            _uc = _cand.get('unlockCondition') or {}
            _phase = str(_uc.get('phase') or 'PHASE_0')
            _need_elite = {'PHASE_0': 0, 'PHASE_1': 1, 'PHASE_2': 2}.get(_phase, 0)
            if _need_elite > elite or int(_uc.get('level') or 1) > level:
                continue
            for _bb in (_cand.get('blackboard') or []):
                if _bb.get('key') == 'cost':
                    attrs['cost'] = attrs.get('cost', 0) + float(_bb.get('value') or 0)

    # 技能
    sk = None
    skills = c.get('skills') or []
    if skills:
        sk = skills[min(skill_index, len(skills) - 1)]
        st = load_table('skill_table.json')
        sd = st.get(sk['skillId'])
        if sd:
            lv = (sd.get('levels') or [])[max(0, min(skill_level - 1, len(sd.get('levels') or []) - 1))]
            sk = dict(sk)
            sk['name'] = lv.get('name')
            sk['rangeId'] = lv.get('rangeId')
            sk['spData'] = lv.get('spData')
            sk['blackboard'] = {b['key']: (b.get('valueStr') if b.get('valueStr') is not None else b.get('value'))
                                for b in (lv.get('blackboard') or [])}
            sk['description'] = lv.get('description')
            sk['duration'] = lv.get('duration')          # 秒；-1 表示弹药型/无限（按描述判定）
            sk['spData'] = lv.get('spData')
            # ★技能类型/时长类型（用于"自动释放"与"弹药/持续"判定）
            #   实测：`skillType` 在**技能表顶层**（`sd['skillType']`），不在 level 里；
            #   芬「冲锋号令·α型」= `AUTO` ⇒ SP 满即自动发动（无需玩家点击）。
            sk['skillType'] = sd.get('skillType') or lv.get('skillType')
            sk['durationType'] = sd.get('durationType') or lv.get('durationType')
            sk['prefabId'] = sd.get('prefabId')
            sk['skillId'] = sk.get('skillId') or sk.get('skillId')

    return {
        'charId': char_id,
        'name': c.get('name'),
        'profession': c.get('profession'),
        'subProfessionId': c.get('subProfessionId'),
        'rarity': c.get('rarity'),
        'position': c.get('position'),
        'attrs': attrs,
        'rangeId': ph.get('rangeId'),
        'talents': c.get('talents') or [],
        'skill': sk,
        'module': module,
        'moduleInfo': mod_info,
        'trait': c.get('trait'),
        'raw': c,
    }


def load_level(level_id: str) -> dict:
    """加载关卡 json（level_id 如 'obt/hard/level_hard_12-04'）。"""
    path = os.path.join(LEVELS, level_id + '.json')
    if not os.path.exists(path):
        path = os.path.join(LEVELS, level_id.replace('/', os.sep) + '.json')
    with open(path, encoding='utf-8') as f:
        return json.load(f)


def level_dir_index() -> list[str]:
    """列出已本地化关卡（相对 levelId）。"""
    out = []
    for root, _dirs, files in os.walk(LEVELS):
        for fn in files:
            if fn.endswith('.json'):
                rel = os.path.relpath(os.path.join(root, fn), LEVELS)[:-5].replace(os.sep, '/')
                out.append(rel)
    return sorted(out)


def animation_assets(unit_key: str) -> dict:
    """按名称返回动画/资源路径（表现层；模拟不依赖，供 auto/验证使用）。"""
    return {
        'charpack': os.path.join(CLIENT, 'charpack', f'{unit_key}.ab'),
        'effects': os.path.join(CLIENT, 'battle_skill_' + unit_key.replace('char_', '').split('_', 1)[-1] + '.ab'),
        'chararts': os.path.join(CLIENT, f'chararts_{unit_key}.ab'),
        'skinpack': os.path.join(CLIENT, f'skinpack_{unit_key}.ab'),
    }


if __name__ == '__main__':
    import sys
    sys.stdout.reconfigure(encoding='utf-8')
    op = get_operator('char_2023_ling', elite=2, level=90, potential=6, trust=200,
                      module='uniequip_002_ling', module_level=3, skill_index=2, skill_level=10)
    print('令:', op['name'], op['attrs']['maxHp'], op['attrs']['atk'], op['attrs']['def'],
          'cost', op['attrs']['cost'], 'block', op['attrs']['blockCnt'], 'interval', op['attrs']['baseAttackTime'])
    print('技能:', op['skill']['name'] if op['skill'] else None)
    print('范围 1-1:', get_range('1-1')[:5])
    print('关卡索引样例:', level_dir_index()[:5])
    e = get_enemy('enemy_1007_slime', 0)
    print('敌人:', e['name'], e['maxHp'], e['atk'], e['baseAttackTime'])
