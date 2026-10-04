# -*- coding: utf-8 -*-
"""case_summary.py — 全部已知机制齐备后的案例总览（结果/击杀/漏怪/费用/时间线）"""
import os
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding='utf-8')

from ak_sim import scenario_h124 as S            # noqa: E402
from ak_sim.axis import parse_cyberplastic        # noqa: E402
from ak_sim.engine import Battle                  # noqa: E402

FPS = 30


def main():
    ax = parse_cyberplastic(S.XLSM)
    ops = []
    for o in ax.ops:
        d = o.to_dict()
        d['char'] = S.NAME_MAP.get(o.unit, o.unit)
        for k, v in S.UNIT_CONFIG.get(d['char'], {}).items():
            d.setdefault(k, v)
        ops.append(d)
    plan = ax.resolve_frames(initial_cost=10.0, unit_costs={}, timebase='abs-seconds')

    # ① 严格模式：判负即停 —— 这才是**保真度**指标
    bs = Battle(S.LEVEL, seed=0, record=False)
    bs.run_axis(ops, name_map=S.NAME_MAP, coord_transform=S.COORD_TRANSFORM,
                max_frames=30 * 400, continue_after_fail=False,
                retry_on_cost=True, retry_on_sp=False,
                schedule=[int(p['frame']) for p in plan])
    ks = Counter(l.kind for l in bs.logs)
    print(f'【严格模式·判负即停】战果 {bs.result}  生命 {bs.life}/{bs.life_max}  '
          f'帧 {bs.frame}（{bs.frame/FPS:.1f}s）  出怪 {ks.get("spawn",0)}  '
          f'击杀 {ks.get("kill",0) + ks.get("device_killed",0)}  漏怪 {ks.get("escape",0)}  '
          f'费用上限 {bs.cost_max:.0f}')

    # ② 对轴模式：判负后复活战场继续推进时间轴（仅用于逐条对轴，战果不作数）
    b = Battle(S.LEVEL, seed=0, record=False)
    print(f'关卡机制：上限 rune={b.cost_max:.0f}(ceil {b.cost_cap_ceil:.0f})、'
          f'敌人属性乘区={b.enemy_attr_mul}、预置装置={sum(1 for u in b.units.values() if u.side=="DEVICE")} 个')
    fired = b.run_axis(ops, name_map=S.NAME_MAP, coord_transform=S.COORD_TRANSFORM,
                       max_frames=30 * 400, continue_after_fail=True,
                       retry_on_cost=True, retry_on_sp=False,
                       schedule=[int(p['frame']) for p in plan])
    kinds = Counter(l.kind for l in b.logs)
    kills = [l for l in b.logs if l.kind == 'kill']
    hits = Counter(l.detail.get('src') for l in b.logs if l.kind == 'hit')
    ally_hits = sum(v for k, v in hits.items() if k in ('令', '蕾缪安', 'U-Official', '弦惊', '“弦惊”',
                                                        '麒麟R夜刀', '傀影', '艾拉', '雷鸣地雷'))
    # 只统计**真正落地**的弦惊（ok=True）；失败尝试（占格/费用）不算落地（§7.51）
    drag = [round(x['frame'] / FPS, 1) for x in fired
            if x['op'] == 'deploy' and x['unit'] == 'token_10020_ling_soul3' and x.get('ok')]
    drag_fail = [round(x['frame'] / FPS, 1) for x in fired
                 if x['op'] == 'deploy' and x['unit'] == 'token_10020_ling_soul3' and not x.get('ok')]
    print(f'\n轴操作 {len(fired)}/{len(ops)} 条触发；成功 {sum(1 for x in fired if x.get("ok"))}')
    print(f'【对轴模式·战果不作数】战果：{b.result}  生命 {b.life}  帧 {b.frame}（{b.frame/FPS:.0f}s）')
    print(f'击杀 {len(kills)}  漏怪 {kinds.get("escape", 0)}  我方出手 {ally_hits} 次'
          f'（令 {hits.get("令",0)}、蕾缪安 {hits.get("蕾缪安",0)}、U-Official {hits.get("U-Official",0)}）')
    print(f'事件：装置摧毁 {kinds.get("device_destroyed",0)}、平民到达 {kinds.get("civilian_arrived",0)}、'
          f'部署失败 {kinds.get("deploy_failed",0)}、技能被拒 {kinds.get("skill_reject",0)}、'
          f'召唤物 AoE {kinds.get("summon_aoe",0)} 次')
    print(f'费用上限最终 {b.cost_max:.0f}')
    print(f'弦惊落地（仅计成功）：{drag[:6]}  失败尝试：{drag_fail[:6]}')
    print(f'作者 Sheet1：{S.SHEET1_DRAGONS if hasattr(S, "SHEET1_DRAGONS") else [66.1, 86.4, 153.3]}')


if __name__ == '__main__':
    main()
