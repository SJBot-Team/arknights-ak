# -*- coding: utf-8 -*-
"""diag_range_cover.py — 打印干员实际位置上「攻击范围覆盖了哪些格」，判断谁能打到应急储备。

核心问题：首条弦惊要 23 费、上限被 rune 压到 20 ⇒ 29.0s（作者作战记录 r7）之前
必须把上限抬到 ≥23。抬升只有两条路：打掉应急储备(+5/+5) 或 平民到达(+2)。
若**没有任何单位**能在 29s 前打到储备，则作者的 29s 落龙在我们的机制模型下不可能，
说明还有一处机制/坐标没对齐（这一脚本就是用来判定的）。
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding='utf-8')

from ak_sim import scenario_h124 as S               # noqa: E402
from ak_sim.engine import Battle                    # noqa: E402

RESERVES = [(5, 6), (5, 7)]
FPS = 30


def main():
    b = Battle(S.LEVEL, seed=0, record=False)
    b.cost_max = 99.0          # 只是看范围，不受费用上限约束
    b.cost = 99.0
    plan = [
        ('令', 2, 11, '上'),
        ('蕾缪安', 6, 8, '下'),
        ('弦惊', 3, 10, '左'),
        ('弦惊', 6, 7, '上'),
        ('弦惊', 6, 10, '下'),
        ('弦惊', 5, 7, '上'),
        ('弦惊', 7, 3, '右'),
        ('弦惊', 2, 3, '上'),
        ('弦惊', 3, 3, '右'),
        ('弦惊', 3, 4, '左'),
        ('弦惊', 7, 4, '右'),
        ('艾拉', 6, 11, '上'),
        ('U-Official', 1, 7, '左'),
        ('蕾缪安', 4, 4, '左'),
    ]
    for name, r, c, d in plan:
        cid = S.NAME_MAP.get(name, name)
        try:
            u = b.deploy(cid, r, c, d, elite=2, level=90, potential=6, trust=200,
                         is_token=str(cid).startswith('token_'),
                         token_owner=b.token_owner_map.get(cid))
        except Exception as e:
            print(f'{name} {r},{c} {d}: 部署异常 {e}')
            continue
        if u is None:
            print(f'{name} {r},{c} {d}: 部署失败')
            continue
        cells = b.cells_in_range(u)
        hits = [rc for rc in RESERVES if rc in cells]
        tile = b.map.tile(r, c)
        print(f'{name:<11} ({r:>2},{c:>2}) {d} 在 {tile.key}/{tile.height_type}  '
              f'范围 {len(cells)} 格  覆盖储备={hits}')
        # 范围画成 9x13 网格
        H, W = b.map.height, b.map.width
        for rr in range(H - 1, -1, -1):
            line = ''
            for cc in range(W):
                if (rr, cc) == (r, c):
                    line += ' O'
                elif (rr, cc) in cells and (rr, cc) in RESERVES:
                    line += ' R'
                elif (rr, cc) in cells:
                    line += ' *'
                elif (rr, cc) in RESERVES:
                    line += ' r'
                else:
                    t = b.map.tile(rr, cc)
                    line += ' #' if t and not t.is_ground_passable else ' .'
            print('     ' + line)
        b.retreat(cid)


if __name__ == '__main__':
    main()
