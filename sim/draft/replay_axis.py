# -*- coding: utf-8 -*-
"""replay_axis.py — ★**按共用轴表复刻并校验**（1-1 标定对局的轴表版）。

与 `replay_verify5.py` 的区别：
- **不再把部署与对应表硬编码在脚本里**，而是从 `ak/axis/1-1.yaml` 读取
  ⇒ 轴表成为**模拟器 / 打图端 / 校验器共用**的唯一事实来源（用户需求）；
- 其余（严格口径、逐条偏差统计）不变，便于与旧结果逐条对照。

用法：`python replay_axis.py [轴表名=1-1]`
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding='utf-8')

from ak_sim.engine import Battle              # noqa: E402
from ak_sim.events import extract_events      # noqa: E402
from ak_sim.scenario import Scenario          # noqa: E402
from axis_io import (axis_expect_table, axis_to_deploy_plan,  # noqa: E402
                     cells_letter_to_rc, load_axis)


def main():
    name = sys.argv[1] if len(sys.argv) > 1 else '1-1'
    ax = load_axis(name)
    sc = Scenario(name)
    plan = axis_to_deploy_plan(ax)
    table = axis_expect_table(ax)
    max_frame = max([t['frame'] for t in table] + list(plan)) + 240

    b = Battle(sc.stage_code, seed=0, record=True, record_every=1, max_frames=max_frame)
    for _ in range(max_frame):
        b.tick()
        for char, (r, c), _dir, cov in plan.get(b.frame, []):
            m = next(x for x in ax['squad'] if x['id'] == char)
            b.deploy(char, r, c, direction=_dir, elite=m.get('elite', 2),
                     level=m.get('level', 90), potential=m.get('potential', 6),
                     trust=m.get('trust', 200), skill_index=m.get('skill_index', 0),
                     skill_level=m.get('skill_level', 7),
                     cost=cov if cov is not None else None)

    ev = extract_events(b.frames)
    order, n = {}, 0
    for e in sorted((x for x in ev if x['type'] == 'spawn'), key=lambda z: z['frame']):
        if str(e.get('name') or '') in ('芬', '月见夜', '令', '蕾缪安'):
            continue
        n += 1
        order[e.get('uid')] = n
    idx: dict[tuple, list[int]] = {}
    for e in ev:
        t, uid = e['type'], e.get('uid')
        nm = str(e.get('name') or '')
        if t == 'spawn' and uid in order:
            idx.setdefault(('spawn', nm, None), []).append(e['frame'])
        elif t in ('damage', 'damage_first'):
            idx.setdefault(('dmg', nm, str(e.get('src') or '-') or None), []).append(e['frame'])
        elif t in ('despawn', 'kill') and uid in order:
            idx.setdefault(('kill', nm, None), []).append(e['frame'])
    # `block` 事件只在 `Battle.logs` 里（`extract_events` 不含），单独索引
    for l in b.logs:
        if l.kind == 'block':
            idx.setdefault(('block', str(l.detail.get('enemy') or ''),
                            str(l.detail.get('by') or '')), []).append(l.frame)
    for k in idx:
        idx[k] = sorted(set(idx[k]))

    print(f'轴表 {name}：{len(plan)} 次部署、{len(table)} 条期望事件'
          f'（模拟 {max_frame} 帧）\n')
    print(f'{"标定帧":>6} {"类别":>6} {"受害者":>9} {"攻击者":>9} {"#":>3} {"模拟器帧":>9} '
          f'{"偏差":>6}  {"说明"}')
    print('-' * 88)
    diffs = []
    for t in table:
        key = (t['kind'], t['victim'], t['src'] if t['kind'] == 'dmg' else
               ('芬' if t['kind'] == 'block' else None))
        if t['kind'] == 'block':
            key = ('block', t['victim'], t['src'])
        frames = idx.get(key, [])
        if t['n'] < len(frames):
            ef = frames[t['n']]
            d = abs(ef - t['frame'])
            diffs.append(d)
            print(f'{t["frame"]:>6} {t["kind"]:>6} {str(t["victim"]):>9} {str(t["src"]):>9} '
                  f'{t["n"]:>3} {ef:>9} {ef - t["frame"]:>+6}  {"OK" if d <= 6 else "★偏大"}'
                  f'  {t.get("note") or ""}')
        else:
            print(f'{t["frame"]:>6} {t["kind"]:>6} {str(t["victim"]):>9} {str(t["src"]):>9} '
                  f'{t["n"]:>3} {"(缺)":>9} {"-":>6}  {t.get("note") or ""}')
    print('-' * 88)
    if diffs:
        print(f'可对齐 {len(diffs)}/{len(table)}；|偏差|≤6 帧 '
              f'{sum(1 for d in diffs if d <= 6)} 条；平均 {sum(diffs) / len(diffs):.2f} 帧；'
              f'最大 {max(diffs)} 帧')
        print('偏差分布: ' + ', '.join(str(d) for d in sorted(diffs)))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
