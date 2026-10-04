# -*- coding: utf-8 -*-
"""add_block_snap.py — ★阻挡发生时把敌人"吸附到与阻挡者相邻的格中心"

## 依据（1-1 标定反推）
- 第 2 只猎狗沿 route4 直线逼近芬，**直线路径上距芬最近 1.083 格**（数学验证：斜率/截距均正确）；
- 若严格沿直线，它**永远不会进入芬（近战 1 格）的攻击范围** ⇒ 芬不可能命中它；
- 但实机标定显示**芬确实打了它**（帧432 命中 / 443 阻挡 / 461 被击 / 464 击杀）
  ⇒ 只能是**阻挡发生时，敌人被对齐到"与阻挡者相邻的格"**（AK 的常见表现：
  敌人被挡后会停在阻挡者相邻格的中心/边界，而不是停在"接触点"）。

## 实现
在 `_block_scan` 建立阻挡关系后，把敌人位置**吸附到"朝向阻挡者最近的相邻格中心"**：
- 候选 = 阻挡者的 4 邻格中"与敌人当前位置最近、且可通行"者；
- 吸附后清空 `inertia`（贴住不再移动）。

可用 `options={'block_snap': False}` 关闭。
"""
from __future__ import annotations

import io
import sys

sys.stdout.reconfigure(encoding='utf-8')

ENGINE = r'C:\Users\23922\Documents\ds_harness\ak\sim\draft\ak_sim\engine.py'

OLD = """        if best is not None:
            e.blocked_by.append(best.uid)
            best.blocking.append(e.uid)
            self.logs.append(OpLog(self.frame, 'block', {'enemy': e.name, 'by': best.name}))"""

NEW = """        if best is not None:
            e.blocked_by.append(best.uid)
            best.blocking.append(e.uid)
            self.logs.append(OpLog(self.frame, 'block', {'enemy': e.name, 'by': best.name}))
            # ★阻挡吸附（依 1-1 标定反推）：把敌人对齐到"与阻挡者相邻的格中心"。
            #   理由：1-1 第 2 只沿 route4 直线逼近芬，**直线最近距离 1.083 格 > 近战 1 格**
            #   ⇒ 若停在接触点，芬永远打不到它；但实机标定中芬确实打了它
            #   ⇒ AK 语义应是"被挡后停在阻挡者相邻格"。
            if getattr(self, 'block_snap', True):
                self._snap_blocked_enemy(e, best)"""

SNAP = '''
    def _snap_blocked_enemy(self, e: Unit, blocker: Unit) -> None:
        """把被阻挡的敌人吸附到"与阻挡者相邻（4 邻接）且可通行"的格中心。"""
        import math as _m
        br, bc = blocker.grid()
        ex, ey = fp.to_float(e.pos[0]), fp.to_float(e.pos[1])
        best, best_d = None, 1e9
        for dr, dc in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            r, c = br + dr, bc + dc
            if not self.map.is_passable(r, c, flying=e.flying):
                continue
            cx, cy = c + 0.5, r + 0.5
            d = _m.hypot(cx - ex, cy - ey)
            if d < best_d:
                best, best_d = (r, c), d
        if best is not None:
            e.pos = self.map.grid_to_world(best[0], best[1])
            e.inertia = (0, 0)
            e.next_node = None
            self.logs.append(OpLog(self.frame, 'block_snap',
                                   {'enemy': e.name, 'by': blocker.name, 'to': best}))
'''


def main():
    s = io.open(ENGINE, encoding='utf-8').read()
    n = 0
    if '★阻挡吸附' not in s:
        if OLD in s:
            s = s.replace(OLD, NEW, 1)
            n += 1
        else:
            print('★阻挡锚点未匹配')
    else:
        print('吸附逻辑已存在')
    if 'def _snap_blocked_enemy' not in s:
        idx = s.find('    def _on_token_lost(self, tok: Unit) -> None:')
        if idx > 0:
            s = s[:idx] + SNAP + '\n' + s[idx:]
            n += 1
        else:
            print('★插入点未找到')
    if 'self.block_snap' not in s:
        s = s.replace("        self.straight_path = bool(opts.get('straight_path', True))",
                      "        self.straight_path = bool(opts.get('straight_path', True))\n"
                      "        # ★阻挡吸附：被挡后把敌人对齐到阻挡者相邻格中心（依 1-1 标定反推）\n"
                      "        self.block_snap = bool(opts.get('block_snap', True))", 1)
        n += 1
    io.open(ENGINE, 'w', encoding='utf-8', newline='').write(s)
    print(f'已修改 {n} 处')
    import ast
    ast.parse(io.open(ENGINE, encoding='utf-8').read())
    print('语法 OK')


if __name__ == '__main__':
    main()
