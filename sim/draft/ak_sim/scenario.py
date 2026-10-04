# -*- coding: utf-8 -*-
"""scenario.py — **通用关卡场景加载**（取代专关专用的 scenario_h124）

## 依用户"方向性修正 1"
> 确保工程有很强的复用性，在搭建中一次到位探索必要的框架和随情景变动的信息的标准提取流程：
> **关卡-关联单位-关联机制一次探明**，变动性强的信息便于调整，如**干员练度、敌方 tag 加成**等局外输入的信息。

## 本模块做三件事
1. **关卡定位**：把玩家可读的关卡名（如 `12-4`、`H12-4`、`1-7`）解析成游戏内部的关卡目录
   （`obt/hard/level_hard_12-04` 这类），优先用 PRTS+ 的 `level_code_mapping.json`；
2. **一次探明**：加载关卡后输出**可核对的探明报告**——关卡机制（runes）、波次、出怪、路线、
   预置装置、初始费用/上限/生命等，便于"预置验证定位"；
3. **外部输入**：练度/潜能/模组/技能等级、敌方 tag 加成等**变动项全部由参数注入**，
   不写死在模块里（`scenario_h124` 那样）。

## 用法
    sc = Scenario('12-4', unit_config={'char_2023_ling': {'elite':2,'level':90,'potential':6,
                                                          'module':'uniequip_002_ling','module_level':3}})
    print(sc.report())          # 探明报告
    b = sc.build(seed=0)        # Battle 实例
"""
from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass, field

_AK = r'C:\Users\23922\Documents\ds_harness\ak'
if _AK not in sys.path:
    sys.path.insert(0, os.path.join(_AK, 'sim', 'draft'))

from ak_sim import data as D                       # noqa: E402
from ak_sim.engine import Battle                   # noqa: E402

PRTS_RES = r'D:\__soft\ak\prts+\_internal\resource'
LEVELS_ROOT = r'E:\__file\ak_kb\gamedata\levels'


def _load_mapping():
    """PRTS+ 的关卡代码↔名称映射（关卡 ID 解析用）。"""
    out = {}
    for fn in ('level_code_mapping.json', 'level_name_mapping.json'):
        p = os.path.join(PRTS_RES, fn)
        if os.path.exists(p):
            try:
                out[fn] = json.load(open(p, encoding='utf-8'))
            except Exception:
                pass
    return out


@dataclass
class Scenario:
    stage: str                                   # 玩家可读关卡名，如 '12-4' / 'H12-4' / '1-7'
    unit_config: dict = field(default_factory=dict)   # 外部输入：干员练度/潜能/模组
    enemy_tags: dict = field(default_factory=dict)    # 外部输入：敌方 tag 加成
    stage_code: str | None = None                # 可选：直接指定内部目录

    def __post_init__(self):
        if self.stage_code is None:
            self.stage_code = self.resolve_stage(self.stage)

    # ---------------- 关卡定位 ----------------
    @staticmethod
    def resolve_stage(name: str) -> str:
        """把可读关卡名解析为内部关卡目录 —— **按文件存在性探测**（不靠猜）。

        实测目录（`E:\\__file\\ak_kb\\gamedata\\levels`）：
          · `obt/main/level_main_01-07.json`   （1-7）
          · `obt/hard/level_hard_12-04.json`   （12-4 / H12-4 —— 本仓只有 hard 版本）
          · `obt/training/level_training_*.json`（训练关，待确认）
        规则：`H12-4` 与 `12-4` 都先试 main 再试 hard，取**实际存在**的那个；
        传入含 '/' 的字符串视为内部目录，原样返回。
        """
        if '/' in name:
            return name
        n = name.strip().upper()
        if n.startswith('TR-'):
            for cand in (f'obt/training/level_training_{n[3:]}',
                         f'obt/main/level_main_TR-{n[3:]}'):
                if os.path.exists(os.path.join(LEVELS_ROOT, cand + '.json')):
                    return cand
            return f'obt/training/level_training_{n[3:]}'
        hard = n.startswith('H')
        body = n[1:] if hard else n
        if '-' not in body:
            return name
        a, b = body.split('-', 1)
        try:
            chap, idx = int(a), int(b)
        except ValueError:
            return name
        stem_main = f'obt/main/level_main_{chap:02d}-{idx:02d}'
        stem_hard = f'obt/hard/level_hard_{chap:02d}-{idx:02d}'
        order = [stem_hard, stem_main] if hard else [stem_main, stem_hard]
        for cand in order:
            if os.path.exists(os.path.join(LEVELS_ROOT, cand + '.json')):
                return cand
        return order[0]

    # ---------------- 一次探明 ----------------
    def discover(self) -> dict:
        """加载关卡并汇总**关卡-关联单位-关联机制**（字段名依实测的关卡 JSON 结构）。

        实测结构（`level_main_01-07.json`）：
          options = {characterLimit, maxLifePoint, initialCost, maxCost, costIncreaseTime,
                     moveMultiplier, isTrainingLevel, ...}
          mapData.map = [[int]]（7×11，数字编码的格子）
          waves[].fragments[].actions[] = {actionType:'SPAWN'|'STORY'|..., key, count,
                                           preDelay, interval, routeIndex}
          runes[] = {key, blackboard, difficultyMask, professionMask, buildableMask}
          enemyDbRefs[] = {useDb, id, level, overwrittenData}
          predefines = {characterInsts, tokenInsts, characterCards, tokenCards}
          randomSeed = 整数（★关卡自带随机种子，对应需求"随机数可控"）
        """
        lv = D.load_level(self.stage_code)
        opts = lv.get('options') or {}
        info = {'stage': self.stage, 'stage_code': self.stage_code,
                'level_id': lv.get('levelId'), 'map_id': lv.get('mapId'),
                'random_seed': lv.get('randomSeed')}
        info['initial_cost'] = opts.get('initialCost')
        info['max_life'] = opts.get('maxLifePoint')
        info['max_cost_ceil'] = opts.get('maxCost')
        info['move_multiplier'] = opts.get('moveMultiplier')
        info['cost_interval'] = opts.get('costIncreaseTime')
        info['char_limit'] = opts.get('characterLimit')
        info['is_training'] = opts.get('isTrainingLevel') or opts.get('isHardTrainingLevel')
        # 地图（数字编码的行列）
        m = ((lv.get('mapData') or {}).get('map')) or []
        info['map_rows'] = len(m)
        info['map_cols'] = len(m[0]) if m else 0
        info['map_codes'] = sorted({c for row in m for c in row})[:20]
        # 机制（runes 是每关机制的所在）
        info['runes'] = [{'key': r.get('key'), 'blackboard': r.get('blackboard'),
                          'difficultyMask': r.get('difficultyMask'),
                          'professionMask': r.get('professionMask'),
                          'buildableMask': r.get('buildableMask')}
                         for r in (lv.get('runes') or [])]
        # 出怪：waves → fragments → actions(SPAWN)
        spawns, kinds = [], set()
        for wi, w in enumerate(lv.get('waves') or []):
            for fr in (w.get('fragments') or []):
                for a in (fr.get('actions') or []):
                    if a.get('actionType') == 'SPAWN':
                        spawns.append({'wave': wi, 'key': a.get('key'), 'count': a.get('count'),
                                       'preDelay': a.get('preDelay'), 'interval': a.get('interval'),
                                       'routeIndex': a.get('routeIndex')})
                        if a.get('key'):
                            kinds.add(a['key'])
        info['spawn_actions'] = spawns
        info['spawn_kinds'] = sorted(kinds)
        info['wave_count'] = len(lv.get('waves') or [])
        # 敌人引用（关卡显式声明的敌人 id）
        info['enemy_refs'] = [e.get('id') for e in (lv.get('enemyDbRefs') or []) if e.get('id')]
        # 路线
        routes = lv.get('routes') or []
        info['route_count'] = len(routes)
        info['routes'] = [{'start': r.get('startPosition'), 'end': r.get('endPosition'),
                           'checkpoints': len(r.get('checkpoints') or []),
                           'motionMode': r.get('motionMode'),
                           'allowDiagonalMove': r.get('allowDiagonalMove')}
                          for r in routes[:20]]
        # 预置单位（装置/召唤物等）
        pre = lv.get('predefines') or {}
        devs = []
        for slot, items in pre.items():
            for it in (items if isinstance(items, list) else []):
                devs.append({'slot': slot, 'key': it.get('characterKey'),
                             'position': it.get('position'), 'direction': it.get('direction')})
        info['predefined_units'] = devs
        # 单位数据可提取性自检（"按名称即用即取"）
        checks = []
        for k in info['enemy_refs'][:6]:
            try:
                D.get_enemy(k)
                checks.append((k, True))
            except Exception:
                checks.append((k, False))
        info['enemy_data_available'] = checks
        return info

    def report(self) -> str:
        d = self.discover()
        S = lambda k: str(d.get(k) if d.get(k) is not None else '?')
        L = [f'=== 关卡探明报告：{d["stage"]}  ({d["stage_code"]}) ===']
        L.append(f'  初始费用={S("initial_cost")}  生命={S("max_life")}  '
                 f'费用上限(ceil)={S("max_cost_ceil")}  移速倍率={S("move_multiplier")}')
        L.append(f'  地图 {S("map_rows")}×{S("map_cols")}   波次 {S("wave_count")}   '
                 f'路线 {S("route_count")}')
        refs = d.get('enemy_refs') or []
        kinds = d.get('spawn_kinds') or []
        L.append(f'  敌人引用 {len(refs)} 个: {refs[:8]}')
        L.append(f'  出怪动作 {len(d.get("spawn_actions") or [])} 条，种类 {len(kinds)}: {kinds[:8]}')
        L.append(f'  随机种子 randomSeed = {S("random_seed")}   角色上限 = {S("char_limit")}   '
                 f'费用间隔 = {S("cost_interval")}s')
        L.append('  ★关卡机制（runes）:')
        for r in d['runes'][:12]:
            L.append(f'     {r["key"]}: {json.dumps(r["blackboard"], ensure_ascii=False)[:100]}')
        L.append('  预置单位:')
        for u in d['predefined_units'][:8]:
            L.append(f'     {str(u.get("slot")):<14} {str(u.get("key")):<28} {u.get("position")}')
        ok = sum(1 for _k, v in d['enemy_data_available'] if v)
        L.append(f'  敌人数据可提取性: {ok}/{len(d["enemy_data_available"])} 成功（抽样）')
        if self.unit_config:
            L.append(f'  外部输入·干员配置 {len(self.unit_config)} 项')
        if self.enemy_tags:
            L.append(f'  外部输入·敌方 tag {self.enemy_tags}')
        return '\n'.join(L)

    def build(self, **kw) -> Battle:
        """构建 Battle（练度等由 unit_config 注入）。"""
        b = Battle(self.stage_code, **kw)
        if self.unit_config:
            setattr(b, 'unit_config_override', dict(self.unit_config))
        if self.enemy_tags:
            setattr(b, 'enemy_tags', dict(self.enemy_tags))
        return b


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    stages = sys.argv[1:] or ['1-7', '12-4', 'H12-4', 'TR-1']
    for s in stages:
        try:
            print(Scenario(s).report())
        except Exception as e:
            print(f'=== {s}: 加载失败 {type(e).__name__}: {e} ===')
        print()
