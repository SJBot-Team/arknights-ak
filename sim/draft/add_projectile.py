# -*- coding: utf-8 -*-
"""add_projectile.py — 给引擎加入"弹道（投射物）"机制

## 依用户补充
> 远程攻击需考虑**是否为存在弹道的远程攻击**；若是，**子弹出现位置（依皮肤）**、
> **子弹与敌人的追击过程**均需考虑。

## 实现（最小可用、可关闭）
1. `__init__`：新增 `self.pending_hits = []`（延迟结算队列）与
   `self.projectile_enabled = bool(opts.get('projectile', True))`；
2. `_is_ranged(u)`：按 `rangeId` 判定远程（如芬 `1-1` 近战、月见夜 `2-3` 远程）；
3. `_projectile_frames(src, tgt)`：飞行帧数 = `round(格距 / PROJECTILE_SPEED_CELLS_PER_FRAME)`
   ⇒ **体现"随距离变化"与"追击"**（用目标当前格距，每帧重算为"发射时刻的距离"）；
4. `_do_attack`：若**远程且开启弹道** ⇒ 把伤害**入队延迟结算**；否则维持"立即结算"；
5. `tick`：在单位更新后调用 `_tick_pending_hits()` 结算到期的伤害。

**默认参数**：`PROJECTILE_SPEED_CELLS_PER_FRAME = 0.1667`（≈1 格 / 6 帧，由 1-1 标定
「帧432 芬命中」vs「帧438 月见夜远程命中」的 6 帧差反推）。
可关闭：`Battle(..., options={'projectile': False})` 恢复旧行为。
"""
from __future__ import annotations

import io
import os
import re
import sys

sys.stdout.reconfigure(encoding='utf-8')

ENGINE = r'C:\Users\23922\Documents\ds_harness\ak\sim\draft\ak_sim\engine.py'

# ---------- ① __init__ 注入字段 ----------
INIT_ANCHOR = '        self.frame = 0'
INIT_CODE = '''        self.frame = 0
        # ★弹道（投射物）：远程攻击的"延迟结算队列"
        #   依用户 2026-09-15 补充：远程攻击若带弹道，则"命中时刻"晚于"出手时刻"，
        #   且随距离变化（子弹需飞向目标/追击）。本队列保存"待结算的伤害"。
        #   可用 options={'projectile': False} 关闭以恢复旧行为。
        self.projectile_enabled = bool(opts.get('projectile', True))
        self.pending_hits = []'''

# ---------- ② _do_attack 改为"可延迟" ----------
DO_ANCHOR = '''        for t in targets:
            dmg = combat.calc_damage(fp.from_int(int(src.eff_atk())), fp.from_float(scale_v),
                                     combat.PHYSIC, target_def=t.df, target_res=t.res)
            dealt = combat.apply_damage(t, dmg)'''
DO_NEW = '''        for t in targets:
            dmg = combat.calc_damage(fp.from_int(int(src.eff_atk())), fp.from_float(scale_v),
                                     combat.PHYSIC, target_def=t.df, target_res=t.res)
            # ★弹道判定：远程攻击若带弹道 ⇒ 伤害改为"延迟到子弹到达时结算"
            if self.projectile_enabled and self._is_ranged(src):
                n = self._projectile_frames(src, t)
                self.pending_hits.append({'f': self.frame + n, 'tgt': t, 'dmg': dmg,
                                          'src': src, 'born': self.frame})
                self.logs.append(OpLog(self.frame, 'projectile', {
                    'src': src.name, 'tgt': t.name, 'frames': n}))
                continue
            dealt = combat.apply_damage(t, dmg)'''

# ---------- ③ 新方法 ----------
METHODS = '''
    # ---------------- ★弹道（投射物） ----------------
    PROJECTILE_SPEED_CELLS_PER_FRAME = 0.1667   # ≈1 格 / 6 帧（由 1-1 标定反推）

    @staticmethod
    def _is_ranged(u) -> bool:
        """是否远程单位（带弹道的候选）。

        依据 `rangeId`：芬（近战）为 `1-1`，月见夜（远程）为 `2-3`
        ⇒ 首段数字 > 1 视为远程。数据表中没有直接的"是否弹道"字段（见 probe_projectile.py），
        故用攻击范围作启发式；后续可按干员/皮肤细化"发射点偏移"。
        """
        rid = str(getattr(u, 'range_id', '') or '')
        m = re.match(r'(\\d+)', rid)
        try:
            return int(m.group(1)) > 1 if m else False
        except Exception:
            return False

    def _projectile_frames(self, src, tgt) -> int:
        """子弹飞行帧数 = round(格距 / 速度)。随距离变化 ⇒ 体现"追击"的时序后果。"""
        try:
            sx, sy = float(src.x), float(src.y)
            tx, ty = float(tgt.x), float(tgt.y)
            dist = ((sx - tx) ** 2 + (sy - ty) ** 2) ** 0.5
        except Exception:
            dist = 1.0
        spd = float(getattr(self, 'projectile_speed', self.PROJECTILE_SPEED_CELLS_PER_FRAME))
        return max(0, int(round(dist / max(1e-6, spd))))

    def _tick_pending_hits(self) -> None:
        """结算到期的"弹道伤害"。"""
        if not self.pending_hits:
            return
        keep = []
        for ph in self.pending_hits:
            if self.frame < ph['f']:
                keep.append(ph)
                continue
            t = ph['tgt']
            src = ph['src']
            if getattr(t, 'alive', False):
                combat.apply_damage(t, ph['dmg'])
                self.logs.append(OpLog(self.frame, 'hit', {
                    'src': src.name if src else '?', 'tgt': t.name,
                    'dmg': round(fp.to_float(ph['dmg']), 2), 'hp_after': t.hp}))
                if t.dead:
                    t.extra['killed_by'] = src.name if src else '?'
                    if t.side == 'DEVICE':
                        self.logs.append(OpLog(self.frame, 'device_killed',
                                               {'tgt': t.name, 'by': src.name if src else '?'}))
                    else:
                        self.logs.append(OpLog(self.frame, 'kill',
                                               {'tgt': t.name, 'by': src.name if src else '?'}))
            # 目标已死 ⇒ 子弹消散（不结算）
        self.pending_hits = keep

'''


def main():
    s = io.open(ENGINE, encoding='utf-8').read()
    changed = []

    if 'pending_hits' not in s:
        if INIT_ANCHOR in s:
            s = s.replace(INIT_ANCHOR, INIT_CODE, 1)
            changed.append('__init__')
        else:
            print('★未找到 __init__ 锚点')
    if '★弹道判定' not in s:
        if DO_ANCHOR in s:
            s = s.replace(DO_ANCHOR, DO_NEW, 1)
            changed.append('_do_attack')
        else:
            print('★未找到 _do_attack 锚点')
    if 'def _tick_pending_hits' not in s:
        # 插到 _do_attack 定义之前
        idx = s.find('    def _do_attack(self, src: Unit, tgt: Unit) -> None:')
        if idx > 0:
            s = s[:idx] + METHODS + s[idx:]
            changed.append('methods')
        else:
            print('★未找到插入点')

    # ④ tick 中调用结算
    if '_tick_pending_hits()' in s and s.count('_tick_pending_hits()') < 2:
        # 在 tick 的 _record_frame 之前插入
        anchor = '            self._record_frame()'
        if anchor in s:
            s = s.replace(anchor, '            self._tick_pending_hits()\n' + anchor, 1)
            changed.append('tick')
        else:
            print('★未找到 tick 锚点')

    io.open(ENGINE, 'w', encoding='utf-8', newline='').write(s)
    print('已修改:', ', '.join(changed) if changed else '（无变化）')


if __name__ == '__main__':
    main()
