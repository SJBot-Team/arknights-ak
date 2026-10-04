# -*- coding: utf-8 -*-
"""fix_windup_in_period.py — ★修正：前摇属于攻击周期"之内"（冷却在起手时重置）

## 问题（本轮定位）
模拟器"芬→猎狗"的命中间隔实测为 **49 帧**（219/268/317/366/415），
而配置 `attack_interval_frames = 32` —— **多了 17 帧 ≈ 前摇 18 帧**。
⇒ 说明本方把前摇**额外加在了周期之外**，正确语义应为：
**一个 32 帧的攻击周期 = 前摇 + 后摇** ⇒ **命中间隔应恒为 `attack_interval_frames`**。

## 修正
- **起手时**（设置 `attack_windup_left` 的同一处）立即 `attack_cd_frames = attack_interval_frames`；
- **命中时**不再重置冷却（前摇结束时只结算伤害）。
干员侧与敌人侧同时修正。
"""
from __future__ import annotations

import io
import sys

sys.stdout.reconfigure(encoding='utf-8')

ENGINE = r'C:\Users\23922\Documents\ds_harness\ak\sim\draft\ak_sim\engine.py'

PAIRS = [
    # 干员侧：命中处不再重置
    ("""                if u.attack_windup_left > 0:
                    pass                      # 仍在前摇，本帧不结算
                else:
                    self._do_attack(u, tgt)
                    u.attack_cd_frames = u.attack_interval_frames
                    u.attack_windup_left = None""",
     """                if u.attack_windup_left > 0:
                    pass                      # 仍在前摇，本帧不结算
                else:
                    self._do_attack(u, tgt)   # ★前摇结束 ⇒ 结算伤害
                    u.attack_windup_left = None
                    # ★冷却在"起手"时已重置 ⇒ 此处不再重置，
                    #   以保证"命中间隔 = attack_interval_frames"（前摇含在周期内）。"""),
    # 干员侧：起手处重置
    ("""                if u.attack_windup_left is None:
                    u.attack_windup_left = self._windup_frames(u)""",
     """                if u.attack_windup_left is None:
                    u.attack_windup_left = self._windup_frames(u)
                    # ★起手即开始计周期（前摇含在周期内）
                    u.attack_cd_frames = u.attack_interval_frames"""),
    # 敌人侧：命中处不再重置
    ("""                if e.attack_windup_left > 0:
                    pass                             # 仍在前摇，本帧不结算
                else:
                    self._do_attack(e, targets[0])
                    e.attack_cd_frames = e.attack_interval_frames
                    e.attack_windup_left = None""",
     """                if e.attack_windup_left > 0:
                    pass                             # 仍在前摇，本帧不结算
                else:
                    self._do_attack(e, targets[0])   # ★前摇结束 ⇒ 结算伤害
                    e.attack_windup_left = None      # 冷却已在起手时重置"""),
    # 敌人侧：起手处重置
    ("""                if e.attack_windup_left is None:
                    e.attack_windup_left = self._windup_frames(e)""",
     """                if e.attack_windup_left is None:
                    e.attack_windup_left = self._windup_frames(e)
                    e.attack_cd_frames = e.attack_interval_frames   # ★起手即计周期"""),
]


def main():
    s = io.open(ENGINE, encoding='utf-8').read()
    done = []
    for old, new in PAIRS:
        if old in s:
            s = s.replace(old, new, 1)
            done.append(new.strip().split('\n')[0][:44])
        else:
            print('★未匹配:', old.strip().split('\n')[-1][:60])
    io.open(ENGINE, 'w', encoding='utf-8', newline='').write(s)
    print(f'已修正 {len(done)}/{len(PAIRS)} 处')


if __name__ == '__main__':
    main()
