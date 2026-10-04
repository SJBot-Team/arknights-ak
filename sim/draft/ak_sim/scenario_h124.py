# -*- coding: utf-8 -*-
"""scenario_h124.py — h12-4 令+蕾缪安 前半段：轴表驱动模拟 + 与参考轴比对

流程：
  1) 解析赛博塑料 xlsm 轴表（费用 + 费用内帧锚点 + 绝对时间参考）
  2) 载入 h12-4 关卡（本地 levels json）
  3) 自动标定坐标变换（用「部署合法性」打分）
  4) 以费用时钟执行轴表，记录每次操作的实际帧，并与参考绝对帧比对
  5) 输出逐帧切片（可选）与统计
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding='utf-8')

from ak_sim import fp
from ak_sim.axis import Axis, calibrate_coord_transform, coord_to_rc, parse_cyberplastic
from ak_sim.data import get_operator, load_table
from ak_sim.engine import Battle

XLSM = r'E:\__file\舟数据\关卡\h12-4\赛博塑料h12-4.xlsm'
LEVEL = 'obt/hard/level_hard_12-04'

# 轴表坐标 → 地图 (row, col) 的变换（见 battlemap.BattleMap.__init__ 的说明）：
# 表里的「字母」= 关卡自己的 row（字母序号即 row），「数字」= 关卡 col，
# 因为 BattleMap 已把 mapData.map 按行反转成关卡坐标系，所以这里**不需要任何翻转**。
COORD_TRANSFORM = 'rc_normal'


def build_name_map() -> dict:
    """从 character_table 动态构建 名称/称号 → charId（含召唤物 token）。"""
    ct = load_table('character_table.json')
    m = {}
    for cid, v in ct.items():
        nm = (v.get('name') or '').strip()
        if nm:
            m.setdefault(nm, cid)
            m.setdefault(nm.strip('“”"'), cid)
        app = (v.get('appellation') or '').strip()
        if app:
            m.setdefault(app, cid)
    # 手工补充（轴表简称）
    m.update({
        '弦惊': 'token_10020_ling_soul3',
        '“弦惊”': 'token_10020_ling_soul3',
        'U-Official': 'char_4091_ulika',
        '麒麟R夜刀': 'char_1029_yato2',
    })
    return m


NAME_MAP = build_name_map()

# 案例配置：满配（E2 90 满潜满信赖 + 模组）
UNIT_CONFIG = {
    'char_2023_ling': dict(elite=2, level=90, potential=6, trust=200, module='uniequip_002_ling',
                           module_level=3, skill_index=2, skill_level=10),
    'char_4193_lemuen': dict(elite=2, level=90, potential=6, trust=200, module='uniequip_002_lemuen',
                             module_level=3, skill_index=0, skill_level=10),
    'token_10020_ling_soul3': dict(elite=2, level=90, potential=6, trust=200, skill_index=0, skill_level=10),
    'char_4091_ulika': dict(elite=0, level=30, potential=6, trust=200),
    'char_1029_yato2': dict(elite=2, level=90, potential=6, trust=200, module='uniequip_002_yato2',
                            module_level=3, skill_index=0, skill_level=10),
}


def main():
    ax = parse_cyberplastic(XLSM)
    print(f'轴表：{len(ax.ops)} 条操作（来源 {ax.meta.get("source")}，关卡代号 {ax.level}）')
    b = Battle(LEVEL, seed=0)
    print(f'关卡：{b.level_id} 地图 {b.map.height}x{b.map.width} 路线 {len(b.routes)} '
          f'波次动作 {len(b.schedule)} 敌人引用 {len(b.enemy_refs)}')
    print(f'关卡参数：初始费用 {b.cost} 上限 {b.cost_max} 生命 {b.life} moveMultiplier {b.move_multiplier}')

    # 坐标标定：用轴表部署点 + 干员位置类型
    deploy_ops = [o for o in ax.ops if o.op == 'deploy' and o.coord]
    coords, melee_flags = [], []
    for o in deploy_ops:
        cid = NAME_MAP.get(o.unit)
        melee = True
        if cid:
            try:
                melee = get_operator(cid, elite=2, level=90).get('position') != 'RANGED'
            except Exception:
                melee = True
        coords.append(o.coord)
        melee_flags.append(melee)
    best_tf, score = calibrate_coord_transform(b.map, coords, melee_flags)
    print(f'坐标标定：最佳变换 = {best_tf}（合法率 {score:.0%}，样本 {len(coords)} 个部署点）')
    for (o, mf) in list(zip(deploy_ops, melee_flags))[:8]:
        r, c = coord_to_rc(o.coord, b.map.height, b.map.width, best_tf)
        t = b.map.tile(r, c)
        print(f'   {o.unit:<8} {o.coord:<5} → (r{r},c{c}) tile={t.key if t else None} '
              f'buildable={t.buildable_type if t else None} 需{"近战" if mf else "远程"}')

    # 执行
    ops = []
    for o in ax.ops:
        d = o.to_dict()
        d['char'] = NAME_MAP.get(o.unit, o.unit)
        cfg = UNIT_CONFIG.get(d['char'], {})
        for k, v in cfg.items():
            d.setdefault(k, v)
        ops.append(d)

    # 静态帧计划（与打图端 code/vision/plugins/clock/cost_ruler.py::build_frame_schedule 同公式）
    unit_costs = {}
    for nm in {o.unit for o in ax.ops if o.op == 'deploy'}:
        cid = NAME_MAP.get(nm)
        if not cid:
            continue
        try:
            unit_costs[nm] = int(get_operator(cid, elite=2, level=90)['attrs'].get('cost') or 0)
        except Exception:
            pass
    plan = ax.resolve_frames(initial_cost=float(b.cost), unit_costs=unit_costs)
    print(f'静态帧计划：{len(plan)} 条（部署费用表 {unit_costs}）')

    fired = b.run_axis(ops, name_map=NAME_MAP, coord_transform=COORD_TRANSFORM, max_frames=30 * 400,
                       continue_after_fail=True)
    print(f'\n执行完成：{b.frame} 帧（{b.frame/fp.FPS:.1f}s） 结果={b.result} 生命={b.life}')
    ok = sum(1 for f in fired if f.get('ok'))
    print(f'轴操作：{len(fired)}/{len(ops)} 触发，成功 {ok}')
    # 动态执行 vs 静态计划：逐条帧差（两者独立实现，差异=执行端时序语义）
    diffs = [(i, f['frame'] - plan[i]['frame']) for i, f in enumerate(fired) if i < len(plan)]
    exact = sum(1 for _, d in diffs if d == 0)
    worst = max((abs(d) for _, d in diffs), default=0)
    print(f'动态 vs 静态计划：完全一致 {exact}/{len(diffs)} 条，最大帧差 {worst}')
    print('  非零帧差（前 10 条）:', [(i + 1, d) for i, d in diffs if d != 0][:10])
    print('\n操作触发对照（模拟帧 / 参考绝对帧 / 差异）：')
    print(f'{"#":>3} {"操作":<8} {"单位":<10} {"模拟帧":>7} {"模拟秒":>8} {"参考帧":>8} {"差异帧":>7} {"结果":<6}')
    for i, f in enumerate(fired[:40]):
        ref = f.get('abs_ref_frames')
        diff = (f['frame'] - ref) if ref else None
        print(f'{i+1:>3} {f["op"]:<8} {f["unit"]:<10} {f["frame"]:>7} {f["frame"]/fp.FPS:>8.2f} '
              f'{ref if ref else "-":>8} {diff if diff is not None else "-":>7} {"OK" if f.get("ok") else "FAIL":<6}')
    # 保存本次轴（转为本库格式）与运行摘要
    out_axis = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', '..',
                            'data', 'derived', 'axis_h12-4_cyberplastic.json')
    ax.meta['coord_transform'] = best_tf
    ax.meta['coord_transform_legal_rate'] = round(score, 3)
    ax.meta['sim_verify'] = {
        'matched_ops': sum(1 for f in fired if f.get('abs_ref_frames')),
        'max_frame_diff': max([abs(f['frame'] - f['abs_ref_frames'])
                               for f in fired if f.get('abs_ref_frames')] or [0]),
        'sim_result': b.result, 'sim_frames': b.frame,
    }
    ax.save(os.path.abspath(out_axis))
    md_path = os.path.abspath(out_axis).replace('.json', '.md')
    with open(md_path, 'w', encoding='utf-8') as fp_:
        fp_.write(ax.to_markdown()
                  + f'\n\n> 模拟校验：{ax.meta["sim_verify"]}\n'
                  + '\n'.join(f'- op{i+1} 模拟帧={f["frame"]} 参考帧={f.get("abs_ref_frames")} '
                              f'{"OK" if f.get("ok") else "FAIL"} {f["op"]} {f["unit"]}'
                              for i, f in enumerate(fired)))
    # 逐帧切片与日志
    frames_path = os.path.abspath(os.path.join(os.path.dirname(out_axis), 'frames_h12-4_sim.jsonl'))
    b.dump_frames(frames_path)
    logs_path = os.path.abspath(os.path.join(os.path.dirname(out_axis), 'logs_h12-4_sim.json'))
    b.dump_logs(logs_path)
    print(f'\n轴表已保存：{os.path.abspath(out_axis)}（+ .md 可读版）')
    print(f'逐帧切片：{frames_path}（{os.path.getsize(frames_path)//1024} KB，{len(b.frames)} 帧）')
    print(f'事件日志：{logs_path}')
    return b, fired


if __name__ == '__main__':
    main()
