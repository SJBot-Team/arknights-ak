# -*- coding: utf-8 -*-
"""rework_attack_timing.py — ★把普攻时序改为"统一时间基准"，杜绝前摇叠加

## 问题（上一轮断点）
"前摇 + 冷却"两套计时器交互导致**前摇被叠加一次**：
实测"芬打猎狗"的命中间隔 = **49 帧**（= 32 + 17），而应为 **32 帧**。

## 方案：单一时间基准 `atk_start_frame`
每个单位的攻击周期只用一个状态：
```
if atk_start_frame is None:            # 空闲 ⇒ 尝试起手
    if 有目标: atk_start_frame = frame; atk_hit_done = False; atk_target = tgt
else:
    el = frame - atk_start_frame
    if el >= interval:                 # 周期结束 ⇒ 空闲（下一帧可再起手）
        atk_start_frame = None
    elif (not atk_hit_done) and el >= windup:   # 前摇结束 ⇒ 结算一次
        _do_attack(tgt); atk_hit_done = True
```
⇒ **命中发生在 `start + windup`、下一周期从 `start + interval` 起算**
⇒ **命中间隔恒为 `interval`**（前摇含在周期内，结构上不可能叠加）。

## 兼容性
- 保留 `attack_cd_frames` 字段（切片与其它代码在使用），在周期内同步维护为剩余帧数；
- `attack_windup_left` 亦保留（用于切片观察）。
"""
from __future__ import annotations

import io
import sys

sys.stdout.reconfigure(encoding='utf-8')

ENGINE = r'C:\Users\23922\Documents\ds_harness\ak\sim\draft\ak_sim\engine.py'

# ---------------- 干员侧 ----------------
OP_OLD = """        if u.attack_cd_frames <= 0:
            tgt = self.pick_operator_target(u)
            if tgt is None:
                # 无目标 ⇒ 前摇重置（下次接触重新起手）
                u.attack_windup_left = None
            else:
                # ★攻击前摇（wind-up）——依 1-1 实机标定：
                #   实机「帧207 芬 进入攻击前摇」→「帧221 芬首次命中」⇒ 前摇 14 帧，
                #   而攻击周期 32 帧 ⇒ 比例 = 14/32 = 0.4375。
                #   模拟器此前是"冷却归零即结算伤害"（前摇 0）⇒ 首次命中比实机早 19 帧。
                #   注：数据表中查无前摇字段（应源自动画资源），故用"周期比例"参数化。
                wl = getattr(u, 'attack_windup_left', None)
                if wl is None:
                    u.attack_windup_left = self._windup_frames(u)
                    # ★起手即开始计周期（前摇含在周期内）：
                    #   否则 cd 递减到 0 后不再增加 ⇒ 每帧都满足"可攻击"⇒ 命中间隔会退化成"前摇帧数"。
                    u.attack_cd_frames = u.attack_interval_frames
                if u.attack_windup_left > 0:
                    u.attack_windup_left -= 1
                if u.attack_windup_left > 0:
                    pass                      # 仍在前摇，本帧不结算
                else:
                    self._do_attack(u, tgt)   # ★前摇结束 ⇒ 结算伤害
                    u.attack_windup_left = None
                    # ★冷却在"起手"时已重置 ⇒ 此处不再重置，
                    #   以保证"命中间隔 = attack_interval_frames"（前摇含在周期内）。
"""
OP_NEW = """        # ★普攻时序：**统一时间基准**（`atk_start_frame`）——
        #   命中在 `start + windup`、下一周期从 `start + interval` 起算
        #   ⇒ **命中间隔恒为 `interval`**（前摇含在周期内，结构上不可能叠加）。
        st = getattr(u, 'atk_start_frame', None)
        if st is None:
            tgt = self.pick_operator_target(u)
            if tgt is not None:
                u.atk_start_frame = self.frame
                u.atk_hit_done = False
                u.atk_target = tgt
                u.attack_windup_left = self._windup_frames(u)
                u.attack_cd_frames = u.attack_interval_frames
            # 无目标 ⇒ 保持空闲
        else:
            el = self.frame - st
            if el >= u.attack_interval_frames:
                u.atk_start_frame = None          # 周期结束 ⇒ 空闲（下一帧可再起手）
                u.attack_cd_frames = 0
                u.attack_windup_left = None
            else:
                u.attack_cd_frames = u.attack_interval_frames - el
                u.attack_windup_left = max(0, self._windup_frames(u) - el)
                wl = self._windup_frames(u)
                if (not getattr(u, 'atk_hit_done', False)) and el >= wl:
                    tgt = getattr(u, 'atk_target', None)
                    if tgt is not None and getattr(tgt, 'alive', False):
                        self._do_attack(u, tgt)
                    u.atk_hit_done = True
"""

# ---------------- 敌人侧 ----------------
EN_OLD = """        if e.attack_cd_frames <= 0:
            targets = self.operators_attackable_by(e)
            if not targets:
                e.attack_windup_left = None          # 无目标 ⇒ 前摇重置
            else:
                wl = getattr(e, 'attack_windup_left', None)
                if wl is None:
                    e.attack_windup_left = self._windup_frames(e)
                    e.attack_cd_frames = e.attack_interval_frames   # ★起手即计周期
                if e.attack_windup_left > 0:
                    e.attack_windup_left -= 1
                if e.attack_windup_left > 0:
                    pass                             # 仍在前摇，本帧不结算
                else:
                    self._do_attack(e, targets[0])   # ★前摇结束 ⇒ 结算伤害
                    e.attack_windup_left = None      # 冷却已在起手时重置
"""
EN_NEW = """        # ★普攻时序：与干员侧相同的"统一时间基准"（见 _operator_tick 注释）
        st = getattr(e, 'atk_start_frame', None)
        if st is None:
            targets = self.operators_attackable_by(e)
            if targets:
                e.atk_start_frame = self.frame
                e.atk_hit_done = False
                e.atk_target = targets[0]
                e.attack_windup_left = self._windup_frames(e)
                e.attack_cd_frames = e.attack_interval_frames
        else:
            el = self.frame - st
            if el >= e.attack_interval_frames:
                e.atk_start_frame = None
                e.attack_cd_frames = 0
                e.attack_windup_left = None
            else:
                e.attack_cd_frames = e.attack_interval_frames - el
                wl = self._windup_frames(e)
                e.attack_windup_left = max(0, wl - el)
                if (not getattr(e, 'atk_hit_done', False)) and el >= wl:
                    tgt = getattr(e, 'atk_target', None)
                    if tgt is not None and getattr(tgt, 'alive', False):
                        self._do_attack(e, tgt)
                    e.atk_hit_done = True
"""


def main():
    s = io.open(ENGINE, encoding='utf-8').read()
    n = 0
    if OP_OLD in s:
        s = s.replace(OP_OLD, OP_NEW, 1)
        n += 1
    else:
        print('★干员侧锚点未匹配')
    if EN_OLD in s:
        s = s.replace(EN_OLD, EN_NEW, 1)
        n += 1
    else:
        print('★敌人侧锚点未匹配')
    io.open(ENGINE, 'w', encoding='utf-8', newline='').write(s)
    print(f'已替换 {n}/2 处')
    import ast
    ast.parse(io.open(ENGINE, encoding='utf-8').read())
    print('语法 OK')


if __name__ == '__main__':
    main()
